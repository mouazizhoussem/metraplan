# tools/counter_tool.py
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from .base_tool import BaseTool
from entities.point_entity import PointEntity
from ui.property_dialog import PropertyDialog


def _refresh_point_group_links(all_pts: list) -> None:
    """
    Recalcule les liens parent/enfant pour une liste de PointEntity
    partageant le même group_id.

    Appelé immédiatement après l'ajout ou la suppression d'un point,
    de sorte que formula_engine voit toujours child_entities à jour
    et retourne le bon nombre (nombre ≠ 1 quand il y a plusieurs points).
    """
    if not all_pts:
        return
    parent = all_pts[0]
    parent.is_group_parent = True
    parent.parent_entity   = None
    parent.child_entities  = []
    for pt in all_pts[1:]:
        pt.is_group_parent = False
        pt.parent_entity   = parent
        if pt not in parent.child_entities:
            parent.child_entities.append(pt)


class CounterTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.counter = 0
        self.counter_entities = []

        # Propriétés configurables
        self.preconfigured_name = "Compteur"
        self.preconfigured_color = QColor(255, 0, 0, 200)
        self.preconfigured_shape = "circle"
        self.preconfigured_size = 14
        self.group_mode = False
        self.group_id = None

    def activate(self):
        """Active l'outil compteur"""
        super().activate()
        # Conserver le compteur existant
        self.counter = len(self.counter_entities)

        if self.group_mode and self.preconfigured_name:
            if hasattr(self.canvas.parent_window, "measure_label"):
                self.canvas.parent_window.measure_label.setText(
                    f"➕ Ajouter à '{self.preconfigured_name}' - Cliquez pour ajouter un compteur"
                )
            return True

        dialog = PropertyDialog(
            parent=self.canvas.parent_window,
            entity_type="counter",
            default_name=self.preconfigured_name or "Compteur",
            default_color=self.preconfigured_color,
            default_shape=self.preconfigured_shape,
            default_size=self.preconfigured_size
        )

        if dialog.exec_():
            props = dialog.get_properties()
            self.preconfigured_name = props.get("name", "Compteur")
            self.preconfigured_color = props.get(
                "color", QColor(255, 0, 0, 200))
            self.preconfigured_shape = props.get("shape", "circle")
            self.preconfigured_size = props.get("size", 14)

            if hasattr(self.canvas.parent_window, "measure_label"):
                self.canvas.parent_window.measure_label.setText(
                    "Compteur activé - Cliquez pour ajouter un point")
            return True

        return False

    def mouse_press(self, event, pos):
        """Gère les clics pour ajouter des points de comptage"""
        if not self.is_active:
            return False

        if event.button() == Qt.LeftButton:
            # Créer l'entité point
            base_name = self.preconfigured_name or "Compteur"
            group_id = None
            group_properties = None
            if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                if self.group_mode and self.group_id:
                    group_id = self.group_id
                    group_points = self.canvas.entity_manager.get_points_by_group(
                        group_id)
                else:
                    group_id = self.canvas.entity_manager.ensure_point_group(
                        base_name)
                    group_points = self.canvas.entity_manager.get_points_by_group(
                        group_id)

                if group_points:
                    leader = group_points[0]
                    group_properties = {
                        "color": getattr(leader, "color", self.preconfigured_color),
                        "shape": getattr(leader, "shape", self.preconfigured_shape),
                        "size": getattr(leader, "size", self.preconfigured_size),
                        "show_label": getattr(leader, "show_label", True),
                        "length": getattr(leader, "length", 0.0),
                        "height": getattr(leader, "height", 0.0),
                        "thickness": getattr(leader, "thickness", 0.0)
                    }

                next_number = self.canvas.entity_manager.get_next_point_number(
                    base_name, group_id)
            else:
                next_number = 1

            self.counter = next_number

            point_entity = PointEntity(pos, {
                'counter_number': next_number,
                'name': base_name,
                'color': group_properties["color"] if group_properties else self.preconfigured_color,
                'shape': group_properties["shape"] if group_properties else self.preconfigured_shape,
                'size': group_properties["size"] if group_properties else self.preconfigured_size,
                'group_id': group_id,
                'show_label': group_properties["show_label"] if group_properties else True,
                'length': group_properties["length"] if group_properties else 0.0,
                'height': group_properties["height"] if group_properties else 0.0,
                'thickness': group_properties["thickness"] if group_properties else 0.0
            })

            # ✅ CORRECTION: Ajouter au gestionnaire AVANT de dessiner
            if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                entity_id = self.canvas.entity_manager.add_entity(point_entity)
                point_entity.entity_id = entity_id
                # Stocker la référence à l'entity_manager pour le fallback de formula_engine
                point_entity._entity_manager = self.canvas.entity_manager
            
            # Dessiner APRÈS (pour avoir le scale_manager)
            point_entity.draw(self.canvas.scene)

            # ✅ CRITIQUE: Mettre à jour le data(1) maintenant que entity_id existe
            if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                if hasattr(point_entity, 'point_item') and point_entity.point_item:
                    point_entity.point_item.setData(1, entity_id)
                if hasattr(point_entity, 'text_item') and point_entity.text_item:
                    point_entity.text_item.setData(1, entity_id)
                if hasattr(point_entity, 'name_item') and point_entity.name_item:
                    point_entity.name_item.setData(1, entity_id)

            # Ajouter à la liste des entités de compteur
            self.counter_entities.append(point_entity)

            # ── Mettre à jour les liens parent/enfant du groupe en temps réel ──
            # Sans cela, formula_engine voit child_entities=[] et retourne nombre=1
            if group_id and hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                _refresh_point_group_links(
                    self.canvas.entity_manager.get_points_by_group(group_id))

            # Mettre à jour l'affichage
            if hasattr(self.canvas.parent_window, "measure_label"):
                self.canvas.parent_window.measure_label.setText(
                    f"Compteur: {self.counter} - Cliquez pour ajouter un point")

            return True

        return False

    def reset_counter(self):
        """Remet le compteur à zéro et supprime tous les points"""
        # Supprimer toutes les entités de compteur de la scène
        for point_entity in self.counter_entities:
            point_entity.delete(self.canvas.scene)

        # Vider la liste
        self.counter_entities = []
        self.counter = 0

        # Mettre à jour l'affichage
        if hasattr(self.canvas.parent_window, "counter_label"):
            self.canvas.parent_window.counter_label.setText("Compteur: 0")
        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Compteur remis à zéro")

    def remove_counter_entity(self, entity_id):
        """Supprime une entité de compteur spécifique"""
        removed_group_id = None
        for i, point_entity in enumerate(self.counter_entities):
            if point_entity.entity_id == entity_id:
                removed_group_id = getattr(point_entity, "group_id", None)
                point_entity.delete(self.canvas.scene)
                self.counter_entities.pop(i)
                self.counter = len(self.counter_entities)

                # Mettre à jour l'affichage
                if hasattr(self.canvas.parent_window, "counter_label"):
                    self.canvas.parent_window.counter_label.setText(
                        f"Compteur: {self.counter}")
                break

        # Recalculer les liens après suppression
        if removed_group_id and hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
            remaining = self.canvas.entity_manager.get_points_by_group(removed_group_id)
            _refresh_point_group_links(remaining)

    def cancel(self):
        """Annule l'opération en cours"""
        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Mode compteur annulé")

    def deactivate(self):
        """Désactive l'outil compteur"""
        self.is_active = False
        self.group_mode = False
        self.group_id = None
        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                f"Compteur: {self.counter} points")
