# tools/note_tool.py
"""Outil Note — place un cadre de commentaire sur le canvas au clic."""
from PyQt5.QtCore import Qt, QPointF
from .base_tool import BaseTool


class NoteTool(BaseTool):

    def __init__(self, canvas):
        super().__init__(canvas)

    # ── Cycle de vie ──────────────────────────────────────────────────────────

    def activate(self):
        super().activate()
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.CrossCursor)
        self._status("📝 Note — Cliquez sur le plan pour insérer une note")

    def deactivate(self):
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.ArrowCursor)
        super().deactivate()

    def cancel(self):
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.ArrowCursor)
        self.is_active = False

    # ── Événements souris ─────────────────────────────────────────────────────

    def mouse_press(self, event, pos):
        if not self.is_active or event.button() != Qt.LeftButton:
            return False
        self._place_note(pos)
        return True

    # ── Création de la note ───────────────────────────────────────────────────

    def _place_note(self, scene_pos: QPointF):
        from ui.note_widget import NoteWidget
        scene = getattr(self.canvas, 'scene', None)
        if scene is None:
            return

        # Compter les notes existantes pour nommer
        existing = [i for i in scene.items()
                    if isinstance(i, NoteWidget)]
        count = len(existing) + 1

        note = NoteWidget(pos=scene_pos, text=f"Note {count}…")
        note._canvas_view = self.canvas
        scene.addItem(note)

        # Immédiatement activer l'édition du texte
        note.enable_text_editing()

        self._status(f"✅ Note {count} insérée — éditez le texte, puis cliquez ailleurs")

        # Désactiver l'outil après placement (une note à la fois)
        mw = getattr(self.canvas, 'parent_window', None)
        if mw and hasattr(mw, 'deactivate_current_tool'):
            mw.deactivate_current_tool()

    # ── Helper ───────────────────────────────────────────────────────────────

    def _status(self, msg: str):
        mw = getattr(self.canvas, 'parent_window', None)
        if mw and hasattr(mw, 'measure_label'):
            mw.measure_label.setText(msg)
