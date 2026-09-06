# core/perimeter_item.py
from PyQt5.QtCore import QObject, pyqtSignal, QEvent, Qt
from entities.line_entity import LineEntity


class PerimeterItem(QObject):
    geometryChanged = pyqtSignal()

    def __init__(self, lines=None):
        super().__init__()
        self.lines = lines or []  # Liste de LineEntity
        self.is_editing = False
        self.scene_ref = None

    def add_line(self, line_entity):
        self.lines.append(line_entity)
        self.geometryChanged.emit()

    def enable_editing(self, scene):
        """Activer l'édition pour toutes les lignes du périmètre"""
        if self.is_editing:
            return

        self.is_editing = True
        self.scene_ref = scene

        for line in self.lines:
            line.enable_editing(scene)

        # Installer un event filter pour capturer la touche Escape
        if scene and scene.views():
            view = scene.views()[0]
            view.installEventFilter(self)

    def disable_editing(self, scene):
        """Désactiver l'édition pour toutes les lignes du périmètre"""
        if not self.is_editing:
            return

        self.is_editing = False

        for line in self.lines:
            line.disable_editing(scene)

        # Retirer l'event filter
        if scene and scene.views():
            view = scene.views()[0]
            view.removeEventFilter(self)

    def eventFilter(self, obj, event):
        """Filtrer les événements pour capturer la touche Escape"""
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.disable_editing(self.scene_ref)
            return True
        return super().eventFilter(obj, event)

    def delete(self, scene):
        """Supprimer tout le périmètre"""
        self.disable_editing(scene)
        for line in self.lines:
            line.delete(scene)
        self.lines = []

    def calculate_total_length(self):
        """Calcule la longueur totale du périmètre"""
        total = 0
        for line in self.lines:
            total += line.calculate_length()
        return total

    def update_all_texts(self):
        """Met à jour tous les textes des lignes"""
        for line in self.lines:
            if hasattr(line, 'draw_text') and self.scene_ref:
                line.draw_text(self.scene_ref)
