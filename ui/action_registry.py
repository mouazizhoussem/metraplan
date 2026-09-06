from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class ActionDef:
    action_id: str
    label: str
    icon_key: str = ""
    shortcut: str = ""
    enabled_when: Callable[[dict], bool] = lambda ctx: True
    handler: Optional[Callable[[], None]] = None
    checkable: bool = False
    checked_when: Optional[Callable[[dict], bool]] = None


class ActionRegistry:
    """Registre central des actions du menu contextuel."""

    def __init__(self, main_window, canvas_view, tool_manager):
        self.main_window = main_window
        self.canvas_view = canvas_view
        self.tool_manager = tool_manager
        self._actions: Dict[str, ActionDef] = {}
        self._register_defaults()

    def get(self, action_id: str) -> ActionDef:
        return self._actions[action_id]

    def list_for_tool(self, tool_name: str) -> List[str]:
        global_actions = [
            "edit.undo", "edit.redo", "sep",
            "edit.copy", "edit.cut", "edit.paste", "edit.delete", "sep",
            "edit.properties", "sep",
            "view.zoom_selection", "view.fit",
        ]
        tool_map = {
            "surface": [
                "sep",
                "tool.finish", "tool.undo_last_point", "tool.mode_switch",
                "tool.ortho_toggle", "tool.cancel",
            ],
            "perimeter": [
                "sep",
                "tool.finish", "tool.undo_last_point", "tool.ortho_toggle",
                "perimeter.add_opening", "perimeter.set_wall_props", "tool.cancel",
            ],
            "opening": [
                "sep",
                "tool.finish", "tool.undo_last_point", "tool.mode_switch",
                "opening.set_height", "tool.ortho_toggle", "tool.cancel",
            ],
            "distance": [
                "sep",
                "tool.finish", "distance.reset", "distance.keep_line",
                "tool.ortho_toggle", "tool.cancel",
            ],
            "counter": [
                "sep",
                "counter.reset_series", "counter.rename_series", "tool.cancel",
            ],
            "scale": [
                "sep",
                "tool.finish", "scale.redefine", "scale.refline_toggle",
                "tool.ortho_toggle", "tool.cancel",
            ],
        }
        return global_actions + tool_map.get(tool_name or "idle", [])

    def list_for_context(self, ctx: dict) -> List[str]:
        """
        Construit la liste d'actions selon l'outil actif ET la selection.
        Priorite: actions globales -> actions outil -> actions metier selon selection.
        """
        tool_name = ctx.get("tool_name", "idle")
        actions = list(self.list_for_tool(tool_name))

        selected_types = set(ctx.get("selected_entity_types", []) or [])
        primary_type = ctx.get("primary_selection_type", "")

        # Ajouter des actions metier si la selection est parlante, meme hors outil actif.
        if "perimeter" in selected_types or primary_type == "perimeter":
            for a in ("sep", "perimeter.add_opening", "perimeter.set_wall_props", "opening.set_height"):
                if a not in actions:
                    actions.append(a)

        if "point" in selected_types or primary_type == "point":
            for a in ("sep", "counter.rename_series"):
                if a not in actions:
                    actions.append(a)

        if "line" in selected_types or primary_type == "line":
            for a in ("sep", "scale.refline_toggle"):
                if a not in actions:
                    actions.append(a)

        return actions

    def _register(self, action_def: ActionDef):
        self._actions[action_def.action_id] = action_def

    def _call_first(self, target, method_names):
        if target is None:
            return False
        for name in method_names:
            if hasattr(target, name):
                try:
                    return getattr(target, name)()
                except Exception as e:
                    return False
        return False

    def _active_tool(self):
        if not self.tool_manager:
            return None
        try:
            return self.tool_manager.get_active_tool()
        except Exception:
            return None

    def _call_on_active_tool(self, method_names):
        return self._call_first(self._active_tool(), method_names)

    def _open_properties_for_selection(self):
        if self._call_first(self.main_window, ["open_properties_for_selection"]):
            return True
        try:
            entity = None
            if hasattr(self.main_window, "get_selected_entity"):
                entity = self.main_window.get_selected_entity()
            if entity and hasattr(self.main_window, "properties_dock") and self.main_window.properties_dock:
                self.main_window.properties_dock.display_entity_properties(entity)
                return True
        except Exception as e:
            pass
        return False

    def _register_defaults(self):
        self._register(ActionDef(
            "edit.undo", "Annuler", "undo", "Ctrl+Z",
            enabled_when=lambda c: c.get("can_undo", False),
            handler=lambda: self._call_first(self.main_window.undo_redo_manager, ["undo"])
            if hasattr(self.main_window, "undo_redo_manager") else False
        ))
        self._register(ActionDef(
            "edit.redo", "Retablir", "redo", "Ctrl+Y",
            enabled_when=lambda c: c.get("can_redo", False),
            handler=lambda: self._call_first(self.main_window.undo_redo_manager, ["redo"])
            if hasattr(self.main_window, "undo_redo_manager") else False
        ))
        self._register(ActionDef(
            "edit.copy", "Copier", "copy", "Ctrl+C",
            enabled_when=lambda c: c.get("has_selection", False),
            handler=lambda: self._call_first(self.main_window, ["copy_entity", "copy_selected_entity"])
        ))
        self._register(ActionDef(
            "edit.cut", "Couper", "cut", "Ctrl+X",
            enabled_when=lambda c: c.get("has_selection", False),
            handler=lambda: self._call_first(self.main_window, ["cut_entity", "cut_selected_entity"])
        ))
        self._register(ActionDef(
            "edit.paste", "Coller", "paste", "Ctrl+V",
            enabled_when=lambda c: c.get("clipboard_has_data", False),
            handler=lambda: self._call_first(self.main_window, ["paste_entity"])
        ))
        self._register(ActionDef(
            "edit.delete", "Supprimer", "delete", "Del",
            enabled_when=lambda c: c.get("has_selection", False),
            handler=lambda: self._call_first(self.canvas_view, ["delete_selected_entities"])
        ))
        self._register(ActionDef(
            "edit.properties", "Proprietes", "properties", "Alt+Enter",
            enabled_when=lambda c: c.get("has_selection", False),
            handler=self._open_properties_for_selection
        ))
        self._register(ActionDef(
            "view.zoom_selection", "Zoom sur selection", "zoom-selection", "Z",
            enabled_when=lambda c: c.get("has_selection", False),
            handler=lambda: self._call_first(self.canvas_view, ["zoom_to_selection", "fit_in_view"])
        ))
        self._register(ActionDef(
            "view.fit", "Ajuster a la vue", "fit-view", "F",
            enabled_when=lambda c: True,
            handler=lambda: self._call_first(self.canvas_view, ["fit_in_view"])
        ))

        self._register(ActionDef(
            "tool.finish", "Terminer", "check", "Enter",
            enabled_when=lambda c: c.get("tool_active", False) and c.get("is_drawing", False) and c.get("point_count", 0) >= 2,
            handler=lambda: self._call_first(self.tool_manager, ["finish_current_tool"])
        ))
        self._register(ActionDef(
            "tool.undo_last_point", "Annuler dernier point", "undo-point", "Backspace",
            enabled_when=lambda c: c.get("tool_active", False) and c.get("point_count", 0) >= 1,
            handler=lambda: self._call_first(self.tool_manager, ["undo_last_point_current_tool"])
        ))
        self._register(ActionDef(
            "tool.mode_switch", "Basculer mode", "shape-switch", "Tab",
            enabled_when=lambda c: c.get("tool_name") in ("surface", "opening"),
            handler=lambda: self._call_first(self.tool_manager, ["toggle_current_tool_mode"])
        ))
        self._register(ActionDef(
            "tool.ortho_toggle", "Mode ortho", "ortho", "O",
            enabled_when=lambda c: True,
            handler=lambda: self._call_first(self.main_window, ["toggle_ortho_mode"]),
            checkable=True,
            checked_when=lambda c: c.get("is_ortho_enabled", False)
        ))
        self._register(ActionDef(
            "tool.cancel", "Annuler l'outil", "cancel", "Esc",
            enabled_when=lambda c: c.get("tool_active", False),
            handler=lambda: self._call_first(self.canvas_view, ["cancel_all_tools"])
        ))

        self._register(ActionDef(
            "perimeter.add_opening", "Ajouter ouverture lineaire", "door-cut", "A",
            enabled_when=lambda c: c.get("tool_name") == "perimeter" or c.get("primary_selection_type") == "perimeter",
            handler=lambda: self._call_first(self.main_window, ["start_linear_opening_on_selected_perimeter"])
        ))
        self._register(ActionDef(
            "perimeter.set_wall_props", "Hauteur / Epaisseur", "wall-props", "H",
            enabled_when=lambda c: c.get("tool_name") == "perimeter" or c.get("primary_selection_type") == "perimeter",
            handler=lambda: self._call_first(self.main_window, ["prompt_perimeter_wall_props"])
        ))
        self._register(ActionDef(
            "opening.set_height", "Definir hauteur ouverture", "height", "H",
            enabled_when=lambda c: c.get("tool_name") == "opening" or c.get("primary_selection_type") == "perimeter",
            handler=lambda: self._call_first(self.main_window, ["prompt_opening_height_for_target", "prompt_opening_height"])
        ))
        self._register(ActionDef(
            "distance.reset", "Reinitialiser mesure", "reset", "R",
            enabled_when=lambda c: c.get("tool_name") == "distance" and c.get("point_count", 0) >= 1,
            handler=lambda: self._call_first(self.tool_manager, ["reset_current_tool_measure"])
        ))
        self._register(ActionDef(
            "distance.keep_line", "Conserver comme ligne", "save-line", "",
            enabled_when=lambda c: c.get("tool_name") == "distance",
            handler=lambda: self._call_first(self.tool_manager, ["persist_current_tool_measure"]) or
            self._call_on_active_tool(["persist_last_measure"])
        ))
        self._register(ActionDef(
            "counter.reset_series", "Remettre serie a zero", "reset", "",
            enabled_when=lambda c: c.get("tool_name") == "counter",
            handler=lambda: self._call_on_active_tool(["reset_counter"])
        ))
        self._register(ActionDef(
            "counter.rename_series", "Renommer serie", "rename", "F2",
            enabled_when=lambda c: c.get("tool_name") == "counter" or c.get("primary_selection_type") == "point",
            handler=lambda: self._call_first(self.main_window, ["rename_counter_series"])
        ))
        self._register(ActionDef(
            "scale.redefine", "Redefinir echelle", "scale-reset", "",
            enabled_when=lambda c: c.get("tool_name") == "scale" or c.get("has_scale", False),
            handler=lambda: self._call_first(self.main_window, ["activate_scale_tool"])
        ))
        self._register(ActionDef(
            "scale.refline_toggle", "Afficher/Masquer ligne d'echelle", "ruler", "",
            enabled_when=lambda c: True,
            handler=lambda: self._call_first(self.main_window, ["toggle_scale_reference_visibility"])
        ))
