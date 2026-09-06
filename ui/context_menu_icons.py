from PyQt5.QtWidgets import QStyle


def create_icon_provider(widget):
    """
    Retourne une fonction icon_provider(icon_key) basee sur les icones standard Qt.
    Cela permet un rendu professionnel sans dependre d'un pack d'icones externe.
    """
    style = widget.style() if widget else None

    # Mapping des cles metier vers des icones natives Qt.
    icon_map = {
        "undo": QStyle.SP_ArrowBack,
        "redo": QStyle.SP_ArrowForward,
        "copy": QStyle.SP_FileIcon,
        "cut": QStyle.SP_TrashIcon,
        "paste": QStyle.SP_DialogOpenButton,
        "delete": QStyle.SP_TrashIcon,
        "properties": QStyle.SP_FileDialogDetailedView,
        "zoom-selection": QStyle.SP_ComputerIcon,
        "fit-view": QStyle.SP_TitleBarMaxButton,
        "check": QStyle.SP_DialogApplyButton,
        "cancel": QStyle.SP_DialogCancelButton,
        "reset": QStyle.SP_BrowserReload,
        "ruler": QStyle.SP_FileDialogInfoView,
        "rename": QStyle.SP_FileDialogContentsView,
        "scale-reset": QStyle.SP_BrowserReload,
        "save-line": QStyle.SP_DialogSaveButton,
        "shape-switch": QStyle.SP_BrowserReload,
        "undo-point": QStyle.SP_ArrowBack,
        "ortho": QStyle.SP_DialogYesButton,
        "door-cut": QStyle.SP_DirOpenIcon,
        "wall-props": QStyle.SP_FileDialogDetailedView,
        "height": QStyle.SP_ArrowUp,
    }

    def _provider(icon_key):
        if not style:
            return None
        pixmap_enum = icon_map.get(icon_key)
        if pixmap_enum is None:
            return None
        return style.standardIcon(pixmap_enum)

    return _provider
