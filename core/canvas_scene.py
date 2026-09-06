# core/canvas_scene.py
from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.QtCore import Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QColor


class CanvasScene(QGraphicsScene):
    # Signal pour émettre l'entité sélectionnée
    entitySelected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_canvas = parent
        self.setBackgroundBrush(Qt.lightGray)
        self.entity_manager = None
        self.main_window = None

    def create_text_with_background(self, text, position):
        """Crée un texte avec un fond coloré"""
        # ... code existant inchangé ...

    def afficher_proprietes_item(self, item):
        """Affiche les propriétés d'un item - méthode appelée par les entités"""

        # Récupérer l'entité via l'entity_id stocké dans l'item
        entity_id = item.data(1) if hasattr(item, 'data') else None

        if entity_id and self.entity_manager:
            entity = self.entity_manager.get_entity(entity_id)
            if entity:
                # Appeler MainWindow pour mettre à jour le panneau
                self.update_properties_panel(entity)
            else:
                pass
        else:
            pass

    def update_properties_panel(self, entity):
        """Met à jour le panneau de propriétés via MainWindow"""

        if self.main_window:
            # Appeler la méthode directe de MainWindow
            self.main_window.update_properties_panel(entity)
        else:
            pass

    def mousePressEvent(self, event):
        """Gère les clics de souris sur la scène - VERSION OPTIMISÉE"""
        # CORRIGER: Laisser les items gérer leurs propres événements d'abord
        # Appeler la méthode parente pour la sélection standard
        super().mousePressEvent(event)

        # CORRIGER: Ne pas interférer si un item a déjà géré l'événement
        if event.isAccepted():
            # L'item a déjà géré le clic, ne rien faire de plus
            return

        # Vérifier si un élément a été cliqué (fallback si les items n'ont pas géré)
        items = self.items(event.scenePos())

        for item in items:
            # Vérifier si l'item a une entité associée
            if not hasattr(item, 'data'):
                continue

            try:
                entity_id = item.data(1)  # data(1) contient l'entity_id
                if entity_id and self.entity_manager:
                    entity = self.entity_manager.get_entity(entity_id)
                    if entity:
                        # CORRIGER: Utiliser la méthode centralisée de mise à jour
                        self.update_properties_panel(entity)
                        # Émettre aussi le signal pour compatibilité
                        if hasattr(self, 'entitySelected'):
                            self.entitySelected.emit(entity)
                        break
            except (TypeError, AttributeError):
                continue

        # Si aucun élément avec entité n'a été cliqué, effacer la sélection
        if not items or not any(hasattr(item, 'data') and item.data(1) for item in items):
            if self.main_window and hasattr(self.main_window, 'properties_dock'):
                self.main_window.properties_dock.clear_selection()

    def set_entity_manager(self, entity_manager):
        """Définit le gestionnaire d'entités"""
        self.entity_manager = entity_manager

    def set_main_window(self, main_window):
        """Définit la référence à la fenêtre principale"""
        self.main_window = main_window
