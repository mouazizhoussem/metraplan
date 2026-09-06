from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QMenu


class ContextMenuService:
    """Construit et affiche le menu contextuel a partir du registre d'actions."""

    def __init__(self, parent_widget, registry, context_adapter, icon_provider=None):
        self.parent_widget = parent_widget
        self.registry = registry
        self.context_adapter = context_adapter
        self.icon_provider = icon_provider or (lambda icon_key: QIcon())

    def build_menu(self):
        ctx = self.context_adapter.build_context()
        action_ids = self.registry.list_for_context(ctx)

        menu = QMenu(self.parent_widget)
        if hasattr(menu, "setToolTipsVisible"):
            menu.setToolTipsVisible(True)
        for action_id in action_ids:
            if action_id == "sep":
                menu.addSeparator()
                continue

            action_def = self.registry.get(action_id)
            action = QAction(action_def.label, menu)

            icon = self.icon_provider(action_def.icon_key)
            if icon and not icon.isNull():
                action.setIcon(icon)

            if action_def.shortcut:
                action.setShortcut(action_def.shortcut)
                if hasattr(action, "setShortcutVisibleInContextMenu"):
                    action.setShortcutVisibleInContextMenu(True)

            enabled = False
            try:
                enabled = bool(action_def.enabled_when(ctx))
            except Exception:
                enabled = False
            action.setEnabled(enabled)

            if action_def.checkable:
                action.setCheckable(True)
                checked = False
                if action_def.checked_when:
                    try:
                        checked = bool(action_def.checked_when(ctx))
                    except Exception:
                        checked = False
                action.setChecked(checked)

            if action_def.handler:
                action.triggered.connect(action_def.handler)

            menu.addAction(action)

        return menu, ctx

    def exec_if_needed(self, global_pos):
        """
        Affiche le menu contextuel si le clic droit n'est pas reserve a l'outil.
        Retourne True si menu affiche, sinon False.
        """
        ctx = self.context_adapter.build_context()
        if self.context_adapter.tool_consumes_right_click(ctx):
            return False

        menu, _ = self.build_menu()
        menu.exec_(global_pos)
        return True
