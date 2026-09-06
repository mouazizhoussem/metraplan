# core/entity_manager.py
from typing import List, Dict, Optional, Any
import uuid
from PyQt5.QtCore import QObject, pyqtSignal


class EntityManager(QObject):
    """Gestionnaire central pour toutes les entités graphiques."""

    entity_added = pyqtSignal(object)
    entity_removed = pyqtSignal(str)
    entity_modified = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.entities: Dict[str, object] = {}
        self.entity_count = 0
        self.counter_count = 0
        self.main_window = None
        self.debug = False
        self.scale_manager = None

    def add_entity(self, entity, layer_id=None):
        """Ajoute une entité au gestionnaire."""
        entity_type = getattr(entity, "entity_type", "entity")

        if entity_type == "point":
            entity_id = f"counter_{self.counter_count}"
            self.counter_count += 1
        else:
            entity_id = f"{entity_type}_{self.entity_count}"
            self.entity_count += 1

        if hasattr(entity, "entity_id"):
            entity.entity_id = entity_id

        self.entities[entity_id] = entity

        if self.scale_manager and hasattr(entity, '__dict__'):
            entity.scale_manager = self.scale_manager

        self.entity_added.emit(entity)
        return entity_id

    def remove_entity(self, entity_id: str, scene) -> bool:
        """Supprime une entité."""
        if entity_id not in self.entities:
            return False

        entity = self.entities[entity_id]

        # Entité enfant dans un groupe
        if hasattr(entity, 'parent_entity') and entity.parent_entity:
            parent = entity.parent_entity
            if entity in parent.child_entities:
                parent.child_entities.remove(entity)

            if len(parent.child_entities) > 1:
                if hasattr(parent, 'draw') and hasattr(parent, 'scene_ref') and parent.scene_ref:
                    parent.draw(parent.scene_ref)
                if hasattr(parent, 'geometryChanged'):
                    parent.geometryChanged.emit()

            elif len(parent.child_entities) == 1:
                only_child = parent.child_entities[0]
                only_child.parent_entity = None
                only_child.group_id = None
                only_child.is_group_parent = False
                if hasattr(only_child, 'draw') and hasattr(only_child, 'scene_ref') and only_child.scene_ref:
                    only_child.draw(only_child.scene_ref)
                if hasattr(only_child, 'geometryChanged'):
                    only_child.geometryChanged.emit()

        # Parent de groupe
        elif hasattr(entity, 'is_group_parent') and entity.is_group_parent:
            if hasattr(entity, 'child_entities') and entity.child_entities:
                children_copy = entity.child_entities.copy()

                if len(children_copy) > 1:
                    new_parent = children_copy[0]
                    new_parent.is_group_parent = True
                    new_parent.parent_entity = None
                    if not hasattr(new_parent, 'child_entities'):
                        new_parent.child_entities = []
                    for child in children_copy[1:]:
                        child.parent_entity = new_parent
                        new_parent.child_entities.append(child)
                    if hasattr(new_parent, 'draw') and hasattr(new_parent, 'scene_ref') and new_parent.scene_ref:
                        new_parent.draw(new_parent.scene_ref)
                    if hasattr(new_parent, 'geometryChanged'):
                        new_parent.geometryChanged.emit()

                elif len(entity.child_entities) == 1:
                    only_child = entity.child_entities[0]
                    only_child.parent_entity = None
                    only_child.group_id = None
                    only_child.is_group_parent = False
                    if hasattr(only_child, 'draw') and hasattr(only_child, 'scene_ref') and only_child.scene_ref:
                        only_child.draw(only_child.scene_ref)
                    if hasattr(only_child, 'geometryChanged'):
                        only_child.geometryChanged.emit()

        if hasattr(entity, "remove_from_scene"):
            entity.remove_from_scene(scene)
        elif hasattr(entity, "delete"):
            entity.delete(scene)

        del self.entities[entity_id]
        self.entity_removed.emit(entity_id)
        return True

    def apply_entity_visibility(self, entity, visible: bool):
        """Applique la visibilité à une entité et tous ses items graphiques."""
        entity.visible = visible

        _fields = [
            "surface_item", "path_item", "polygon_item", "line_item",
            "point_item", "text_item", "text_bg", "name_item",
        ]
        for f in _fields:
            item = getattr(entity, f, None)
            if item:
                item.setVisible(visible)

        for f in ("text_items", "text_bgs", "anchor_points"):
            for item in (getattr(entity, f, None) or []):
                if item:
                    item.setVisible(visible)

        # Ouvertures de surface
        for op in getattr(entity, "openings", []):
            for f in _fields:
                item = getattr(op, f, None)
                if item:
                    item.setVisible(visible)
            for f in ("text_items", "text_bgs"):
                for item in (getattr(op, f, None) or []):
                    if item:
                        item.setVisible(visible)

        # Ouvertures linéaires de périmètre
        for item in getattr(entity, "opening_line_items", []):
            if item:
                item.setVisible(visible)
        for item in getattr(entity, "opening_label_items", []):
            if item:
                item.setVisible(visible)

        # Propager aux enfants du groupe
        for child in getattr(entity, "child_entities", []):
            self.apply_entity_visibility(child, visible)

    def get_entity(self, entity_id: str) -> Optional[object]:
        return self.entities.get(entity_id)

    def get_all_entities(self) -> List[object]:
        return list(self.entities.values())

    def clear_all(self, scene=None) -> None:
        for entity_id in list(self.entities.keys()):
            self.remove_entity(entity_id, scene)
        self.counter_count = 0

    def get_statistics(self):
        stats = {"total": len(self.entities), "polygons": 0, "lines": 0, "points": 0, "other": 0}
        for entity in self.entities.values():
            t = getattr(entity, "entity_type", "inconnu")
            if t == "polygon":
                stats["polygons"] += 1
            elif t == "line":
                stats["lines"] += 1
            elif t == "point":
                stats["points"] += 1
            else:
                stats["other"] += 1
        return stats

    def notify_entity_modified(self, entity):
        self.entity_modified.emit(entity)

    def get_entities_by_type(self, entity_type):
        return [e for e in self.entities.values() if getattr(e, "entity_type", None) == entity_type]

    def get_points_by_name(self, name):
        return [e for e in self.get_entities_by_type("point") if getattr(e, "name", None) == name]

    def get_points_by_group(self, group_id):
        if not group_id:
            return []
        return [e for e in self.get_entities_by_type("point") if getattr(e, "group_id", None) == group_id]

    def ensure_point_group(self, name):
        if not name:
            return None
        existing = self.get_points_by_name(name)
        for point in existing:
            group_id = getattr(point, "group_id", None)
            if group_id:
                return group_id
        group_id = f"group_{uuid.uuid4().hex[:8]}"
        for point in existing:
            point.group_id = group_id
        return group_id

    def get_next_point_number(self, name=None, group_id=None):
        points = []
        if group_id:
            points = self.get_points_by_group(group_id)
        elif name:
            points = self.get_points_by_name(name)
        if not points:
            return 1
        max_number = 0
        for point in points:
            try:
                max_number = max(max_number, int(point.counter_number))
            except Exception:
                continue
        return max_number + 1

    def get_counter_points(self):
        return [
            e for e in self.entities.values()
            if getattr(e, "entity_type", None) == "point"
            and hasattr(e, "entity_id")
            and e.entity_id.startswith("counter_")
        ]

    def renumber_counter_points(self, scene):
        counter_points = self.get_counter_points()
        counter_points.sort(key=lambda x: int(x.entity_id.split('_')[1]) if hasattr(
            x, 'entity_id') and '_' in x.entity_id else 0)
        for i, point in enumerate(counter_points):
            old_id = point.entity_id
            new_id = f"counter_{i}"
            if old_id != new_id:
                point.entity_id = new_id
                if old_id in self.entities:
                    self.entities[new_id] = self.entities.pop(old_id)
                if hasattr(point, 'delete') and hasattr(point, 'draw'):
                    point.delete(scene)
                    point.draw(scene)
