class ToolContextAdapter:
    """Construit le contexte runtime utilise pour activer/desactiver les actions."""

    def __init__(self, main_window, canvas_view, tool_manager):
        self.main_window = main_window
        self.canvas_view = canvas_view
        self.tool_manager = tool_manager

    def build_context(self):
        tool_name = self.tool_manager.get_active_tool_name() if self.tool_manager else "idle"
        tool_active = self.tool_manager.get_active_tool() is not None if self.tool_manager else False

        selected_entities = []
        if hasattr(self.canvas_view, "get_selected_entities"):
            try:
                selected_entities = self.canvas_view.get_selected_entities() or []
            except Exception:
                selected_entities = []

        can_undo = False
        can_redo = False
        undo_mgr = getattr(self.main_window, "undo_redo_manager", None)
        if undo_mgr:
            try:
                can_undo = bool(undo_mgr.can_undo())
                can_redo = bool(undo_mgr.can_redo())
            except Exception:
                pass

        is_ortho_enabled = False
        ortho_mgr = getattr(self.canvas_view, "ortho_manager", None)
        if ortho_mgr and hasattr(ortho_mgr, "is_ortho_enabled"):
            try:
                is_ortho_enabled = bool(ortho_mgr.is_ortho_enabled())
            except Exception:
                pass

        point_count = 0
        is_drawing = False
        if self.tool_manager:
            try:
                point_count = int(self.tool_manager.get_current_tool_point_count())
            except Exception:
                point_count = 0
            try:
                is_drawing = bool(self.tool_manager.is_current_tool_drawing())
            except Exception:
                is_drawing = point_count > 0

        clipboard_has_data = bool(getattr(self.main_window, "clipboard_entity", None))
        has_scale = bool(getattr(self.canvas_view, "pixels_per_meter", 0) > 0)

        return {
            "tool_name": tool_name or "idle",
            "tool_active": tool_active,
            "is_drawing": is_drawing,
            "point_count": point_count,
            "has_selection": len(selected_entities) > 0,
            "selection_count": len(selected_entities),
            "selected_entity_types": [getattr(e, "entity_type", "") for e in selected_entities],
            "primary_selection_type": getattr(selected_entities[0], "entity_type", "") if selected_entities else "",
            "clipboard_has_data": clipboard_has_data,
            "can_undo": can_undo,
            "can_redo": can_redo,
            "is_ortho_enabled": is_ortho_enabled,
            "has_scale": has_scale,
        }

    def tool_consumes_right_click(self, ctx):
        """Regle UX: en dessin actif, certains outils consomment le clic droit."""
        if not ctx.get("tool_active", False):
            return False
        if not ctx.get("is_drawing", False):
            return False
        return ctx.get("tool_name") in ("surface", "perimeter", "opening")
