from PyQt5.QtCore import QObject, pyqtSignal
from .undo_redo_snapshot import (
    create_entity_snapshot,
    recreate_entity_from_data,
    restore_entity_connections,
    restore_group_connections,
)


class Command:
    """Classe de base pour une commande réversible"""

    def __init__(self, description=""):
        self.description = description

    def execute(self):
        pass

    def undo(self):
        pass

    def redo(self):
        self.execute()


class AddEntityCommand(Command):
    """Commande pour ajouter une entité"""

    def __init__(self, entity_manager, scene, entity_data, description="Ajouter entité"):
        super().__init__(description)
        self.entity_manager = entity_manager
        self.scene = scene
        self.entity_data = entity_data
        self.entity_id = None
        self.entity = None

    def execute(self):
        self.entity = recreate_entity_from_data(self, self.entity_data)

        if self.entity:
            undo_manager = None
            if hasattr(self.entity_manager, 'main_window') and hasattr(self.entity_manager.main_window, 'undo_redo_manager'):
                undo_manager = self.entity_manager.main_window.undo_redo_manager
                undo_manager.set_enabled(False)

            self.entity_id = self.entity_manager.add_entity(self.entity)
            self.entity.entity_id = self.entity_id

            if undo_manager:
                undo_manager.set_enabled(True)

            if self.scene:
                self.entity.draw(self.scene)
                restore_entity_connections(self, self.entity)
                restore_group_connections(self, self.entity)

    def undo(self):
        if self.entity_id:
            if hasattr(self.entity_manager, 'main_window') and hasattr(self.entity_manager.main_window, 'undo_redo_manager'):
                undo_manager = self.entity_manager.main_window.undo_redo_manager
                undo_manager.set_enabled(False)

            self.entity_manager.remove_entity(self.entity_id, self.scene)

            if self.entity_manager and hasattr(self.entity_manager, 'main_window'):
                self.entity_manager.main_window.update_quantities_table()
                self.entity_manager.main_window.update_toolbar_summary()

            if hasattr(self.entity_manager, 'main_window') and hasattr(self.entity_manager.main_window, 'undo_redo_manager'):
                undo_manager.set_enabled(True)


class RemoveEntityCommand(Command):
    """Commande pour supprimer une entité"""

    def __init__(self, entity_manager, scene, entity, description="Supprimer entité"):
        super().__init__(description)
        self.entity_manager = entity_manager
        self.scene = scene
        self.entity_id = getattr(entity, 'entity_id', None)
        self.entity_data = create_entity_snapshot(entity)

    def execute(self):
        if self.entity_id:
            self.entity_manager.remove_entity(self.entity_id, self.scene)
            if hasattr(self.entity_manager, 'main_window'):
                self.entity_manager.main_window.update_quantities_table()
                self.entity_manager.main_window.update_toolbar_summary()

    def undo(self):
        add_cmd = AddEntityCommand(self.entity_manager, self.scene,
                                   self.entity_data,
                                   description=f"Restaurer '{self.entity_data.get('name', 'entité')}'")
        add_cmd.execute()


class ModifyEntityCommand(Command):
    """Commande pour modifier une entité (positions, ouvertures, etc.)"""

    def __init__(self, entity_manager, scene, entity_id, old_data, new_data, description="Modifier entité"):
        super().__init__(description)
        self.entity_manager = entity_manager
        self.scene = scene
        self.entity_id = entity_id
        self.old_data = old_data
        self.new_data = new_data

    def execute(self):
        entity = self.entity_manager.get_entity(self.entity_id)
        if not entity:
            entity = recreate_entity_from_data(self, self.new_data)
            if entity:
                self.entity_manager.add_entity(entity)
                if self.scene:
                    entity.draw(self.scene)
                    restore_entity_connections(self, entity)
                    restore_group_connections(self, entity)
        else:
            self._apply_data_to_entity(entity, self.new_data)

    def undo(self):
        entity = self.entity_manager.get_entity(self.entity_id)
        if entity:
            self._apply_data_to_entity(entity, self.old_data)

    def _apply_data_to_entity(self, entity, data):
        # Cette méthode peut être enrichie selon les types d'entités
        if hasattr(entity, 'points') and 'points' in data:
            from PyQt5.QtCore import QPointF
            entity.points = [QPointF(x, y) for x, y in data['points']]
            if hasattr(entity, 'update_polygon'):
                entity.update_polygon()
        if hasattr(entity, 'color') and 'color' in data:
            from PyQt5.QtGui import QColor
            entity.set_color(QColor(data['color']))


class PropertyChangeCommand(Command):
    """Commande générique pour changement de propriété (couleur, nom, etc.)"""

    def __init__(self, entity_manager, scene, entity_id, property_name, old_value, new_value, description="Changer propriété"):
        super().__init__(description)
        self.entity_manager = entity_manager
        self.scene = scene
        self.entity_id = entity_id
        self.property_name = property_name
        self.old_value = old_value
        self.new_value = new_value

    def execute(self):
        self._apply(self.new_value)

    def undo(self):
        self._apply(self.old_value)

    def _apply(self, value):
        entity = self.entity_manager.get_entity(self.entity_id)
        if not entity:
            return

        if self.property_name == 'color':
            from PyQt5.QtGui import QColor
            if hasattr(entity, 'set_color'):
                entity.set_color(QColor(value))
            elif hasattr(entity, 'color'):
                entity.color = QColor(value)
        elif self.property_name == 'name':
            if hasattr(entity, 'set_name'):
                entity.set_name(value)
            elif hasattr(entity, 'name'):
                entity.name = value
        elif self.property_name == 'position':
            # TODO: implémentation selon structure de l'entité
            pass

        if hasattr(entity, 'draw') and hasattr(entity, 'scene_ref'):
            try:
                entity.draw(entity.scene_ref)
            except Exception:
                pass

        if hasattr(self.entity_manager, 'main_window'):
            mw = self.entity_manager.main_window
            if hasattr(mw, 'update_quantities_table'):
                mw.update_quantities_table()
            if hasattr(mw, 'update_toolbar_summary'):
                mw.update_toolbar_summary()

