from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
import importlib


class ToolManager:
    def __init__(self, canvas_view):
        self.canvas_view = canvas_view
        self.tools = {}
        self.current_tool = None
        self.current_tool_name = None

    def register_tool(self, tool_name, class_name):
        """Enregistre un outil avec son nom et sa classe"""
        try:
            # Importation dynamique du module
            module = importlib.import_module(f"tools.{tool_name}_tool")

            # Récupération de la classe (la classe doit avoir le même nom que le fichier en CamelCase)
            # Par exemple: surface_tool.py -> SurfaceTool
            class_name_formatted = ''.join(
                word.capitalize() for word in tool_name.split('_')) + 'Tool'
            tool_class = getattr(module, class_name_formatted)

            self.tools[tool_name] = tool_class(self.canvas_view)
            return True
        except ImportError as e:
            return False
        except AttributeError as e:
            return False

    def activate_tool(self, tool_name):
        """Active un outil spécifique"""
        if tool_name in self.tools:
            if self.current_tool:
                self.current_tool.deactivate()
            self.current_tool = self.tools[tool_name]
            self.current_tool_name = tool_name

            # Vérifier si l'activation réussit
            activation_result = self.current_tool.activate()

            # Si activate() retourne False, annuler l'activation
            if activation_result is False:
                self.current_tool = None
                self.current_tool_name = None
                return False

            return True
        return False

    def deactivate_all_tools(self):
        """Désactive tous les outils"""
        if self.current_tool:
            self.current_tool.deactivate()
        self.current_tool = None
        self.current_tool_name = None

    def cancel_current_tool(self):
        """Annule l'outil actuel"""
        if self.current_tool and hasattr(self.current_tool, 'cancel'):
            self.current_tool.cancel()
        self.current_tool = None
        self.current_tool_name = None

    def cancel_all_tools(self):
        """Annule tous les outils"""
        for tool_name, tool in self.tools.items():
            if hasattr(tool, 'cancel'):
                tool.cancel()
        self.current_tool = None
        self.current_tool_name = None

    def handle_mouse_press(self, event, scene_pos):
        """Gère l'événement de pression de souris"""
        # Ignorer le MiddleButton - le pan doit gérer cet événement
        if event.button() == Qt.MiddleButton:
            return False

        if self.current_tool and hasattr(self.current_tool, 'mouse_press'):
            return self.current_tool.mouse_press(event, scene_pos)
        return False

    def handle_mouse_move(self, event, scene_pos):
        """Gère l'événement de mouvement de souris"""
        # Si le pan est actif, ne pas interférer
        if hasattr(self.canvas_view, '_pan') and self.canvas_view._pan:
            return False

        if self.current_tool and hasattr(self.current_tool, 'mouse_move'):
            return self.current_tool.mouse_move(event, scene_pos)
        return False

    def handle_mouse_release(self, event, scene_pos):
        """Gère l'événement de relâchement de souris"""
        # Ignorer le MiddleButton - le pan doit gérer cet événement
        if event.button() == Qt.MiddleButton:
            return False

        if self.current_tool and hasattr(self.current_tool, 'mouse_release'):
            return self.current_tool.mouse_release(event, scene_pos)
        return False

    def handle_mouse_double_click(self, event, scene_pos):
        """Gère l'événement de double-clic"""
        if self.current_tool and hasattr(self.current_tool, 'mouse_double_click'):
            return self.current_tool.mouse_double_click(event, scene_pos)
        return False

    def handle_key_press(self, event):
        """Gère l'événement de pression de touche"""
        if self.current_tool and hasattr(self.current_tool, 'key_press'):
            return self.current_tool.key_press(event)
        return False

    def adjust_position_for_ortho(self, pos):
        """Ajuste la position pour le mode ortho"""
        if (not self.current_tool or
            not hasattr(self.canvas_view, 'ortho_manager') or
            not self.canvas_view.ortho_manager or
                not self.canvas_view.ortho_manager.is_ortho_enabled()):
            return pos

        # Récupère le dernier point de l'outil courant pour l'ajustement ortho
        last_point = None
        if (hasattr(self.current_tool, 'points') and
            self.current_tool.points and
                len(self.current_tool.points) > 0):
            last_point = self.current_tool.points[-1]

        if last_point:
            return self.canvas_view.ortho_manager.adjust_point_to_ortho(last_point, pos)

        return pos

    def get_tool(self, tool_name):
        """Récupère un outil par son nom"""
        return self.tools.get(tool_name)

    def is_tool_active(self, tool_name):
        """Vérifie si un outil spécifique est actif"""
        return self.current_tool_name == tool_name and self.current_tool is not None

    def get_active_tool_name(self):
        """Retourne le nom de l'outil actuellement actif"""
        return self.current_tool_name

    def get_active_tool(self):
        """Retourne l'outil actuellement actif"""
        return self.current_tool

    # ------------------------------------------------------------------
    # Wrappers contextuels pour menus / commandes globales
    # ------------------------------------------------------------------
    def _call_current_tool_method(self, method_name):
        """Appelle une méthode de l'outil courant si disponible."""
        if not self.current_tool or not hasattr(self.current_tool, method_name):
            return False
        try:
            method = getattr(self.current_tool, method_name)
            return bool(method())
        except Exception as e:
            return False

    def finish_current_tool(self):
        """Finalise l'opération en cours de l'outil actif."""
        return self._call_current_tool_method('finish_current')

    def undo_last_point_current_tool(self):
        """Annule le dernier point de l'outil actif."""
        return self._call_current_tool_method('undo_last_point')

    def toggle_current_tool_mode(self):
        """Bascule le mode de dessin de l'outil actif."""
        return self._call_current_tool_method('toggle_drawing_mode')

    def reset_current_tool_measure(self):
        """Réinitialise la mesure de l'outil actif."""
        return self._call_current_tool_method('reset_measure')

    def persist_current_tool_measure(self):
        """Conserve explicitement la dernière mesure de l'outil actif."""
        return self._call_current_tool_method('persist_last_measure')

    def get_current_tool_point_count(self):
        """Retourne le nombre de points manipulés par l'outil actif."""
        if not self.current_tool:
            return 0
        if hasattr(self.current_tool, 'get_point_count'):
            try:
                return int(self.current_tool.get_point_count())
            except Exception:
                pass
        points = getattr(self.current_tool, 'points', None)
        if isinstance(points, list):
            return len(points)
        return 0

    def is_current_tool_drawing(self):
        """Indique si l'outil actif est en cours de dessin/édition."""
        if not self.current_tool:
            return False
        if hasattr(self.current_tool, 'is_drawing_in_progress'):
            try:
                return bool(self.current_tool.is_drawing_in_progress())
            except Exception:
                pass
        # Fallback robuste pour outils hétérogènes existants.
        if self.get_current_tool_point_count() > 0:
            return True
        return bool(getattr(self.current_tool, 'is_dragging', False) or
                    getattr(self.current_tool, 'is_rect_dragging', False))
