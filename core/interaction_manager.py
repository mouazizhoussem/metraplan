from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QApplication


class InteractionManager:
    def __init__(self, canvas_view):
        self.canvas_view = canvas_view
        self.tool_manager = canvas_view.tool_manager
        self._pan = False
        self._pan_start = QPoint()

    def handle_wheel_event(self, event):
        """Gère le zoom avec la molette"""
        if self.canvas_view.image_item is None:
            return False

        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor

        self.canvas_view.scale(zoom_factor, zoom_factor)
        return True

    def handle_mouse_press(self, event):
        """Gère les clics de souris"""
        if event.button() == Qt.MiddleButton:
            # Mode déplacement (pan) avec la molette
            self._pan = True
            self._pan_start = event.pos()
            self.canvas_view.setCursor(Qt.ClosedHandCursor)
            return True

        if self.canvas_view.image_item is None:
            return False

        scene_pos = self.canvas_view.mapToScene(event.pos())

        # Délégation au gestionnaire d'outils
        return self.tool_manager.handle_mouse_press(event, scene_pos)

    def handle_mouse_move(self, event):
        """Gère les mouvements de souris"""
        if self.canvas_view.image_item is None:
            return False

        scene_pos = self.canvas_view.mapToScene(event.pos())

        # Appliquer le mode ortho si activé
        if (hasattr(self.canvas_view, 'ortho_manager') and self.canvas_view.ortho_manager
                and self.canvas_view.ortho_manager.is_ortho_enabled()):

            # Délégation au gestionnaire d'outils pour l'ajustement ortho
            scene_pos = self.tool_manager.adjust_position_for_ortho(scene_pos)

        # Délégation au gestionnaire d'outils
        if self.tool_manager.handle_mouse_move(event, scene_pos):
            return True

        # Gestion du pan
        if self._pan:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.canvas_view.horizontalScrollBar().setValue(
                self.canvas_view.horizontalScrollBar().value() - delta.x())
            self.canvas_view.verticalScrollBar().setValue(
                self.canvas_view.verticalScrollBar().value() - delta.y())
            return True

        return False

    def handle_mouse_release(self, event):
        """Gère le relâchement de souris"""
        if event.button() == Qt.MiddleButton and self._pan:
            self._pan = False
            self.canvas_view.setCursor(Qt.ArrowCursor)
            return True

        if self.canvas_view.image_item is None:
            return False

        scene_pos = self.canvas_view.mapToScene(event.pos())

        # Délégation au gestionnaire d'outils
        return self.tool_manager.handle_mouse_release(event, scene_pos)

    def handle_mouse_double_click(self, event):
        """Gère les double-clics"""
        if self.canvas_view.image_item is None:
            return False

        scene_pos = self.canvas_view.mapToScene(event.pos())

        # Délégation au gestionnaire d'outils
        return self.tool_manager.handle_mouse_double_click(event, scene_pos)

    def handle_key_press(self, event):
        """Gère les touches du clavier"""
        if event.key() == Qt.Key_Escape:
            self.canvas_view.cancel_all_tools()
            return True

        if event.key() == Qt.Key_Delete:
            self.canvas_view.delete_selected_entities()
            return True

        # Gestion du mode ortho avec la touche O
        if event.key() == Qt.Key_O:
            if (hasattr(self.canvas_view, 'ortho_manager') and self.canvas_view.ortho_manager
                    and hasattr(self.canvas_view.parent_window, 'toggle_ortho_mode')):
                self.canvas_view.parent_window.toggle_ortho_mode()
                return True

        # Délégation au gestionnaire d'outils
        return self.tool_manager.handle_key_press(event)

    def is_panning(self):
        """Retourne si le mode pan est actif"""
        return self._pan
