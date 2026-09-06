# tools/marker_tool.py
"""Outil Marqueur — trace un rectangle de surbrillance sur le plan."""
from PyQt5.QtCore import Qt, QRectF, QRect, QSize
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QRubberBand
from .base_tool import BaseTool
from entities.marker_entity import MarkerEntity


class MarkerTool(BaseTool):

    def __init__(self, canvas):
        super().__init__(canvas)
        self._rb = None
        self._origin = None       # viewport coords QPoint

    # ── Cycle de vie ──────────────────────────────────────────────────────────

    def activate(self):
        super().activate()
        self._rb = None
        self._origin = None
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.CrossCursor)
        self._status("📌 Marqueur — Maintenez et glissez pour surligner une zone du plan")

    def deactivate(self):
        self._cleanup()
        super().deactivate()

    def cancel(self):
        self._cleanup()
        self.is_active = False

    # ── Événements souris ─────────────────────────────────────────────────────

    def mouse_press(self, event, pos):
        if not self.is_active or event.button() != Qt.LeftButton:
            return False
        self._origin = self.canvas.mapFromScene(pos)
        self._rb = QRubberBand(QRubberBand.Rectangle, self.canvas)
        self._rb.setGeometry(QRect(self._origin, QSize()))
        self._rb.show()
        return True

    def mouse_move(self, event, pos):
        if not self.is_active or self._origin is None or self._rb is None:
            return False
        vp = self.canvas.mapFromScene(pos)
        self._rb.setGeometry(QRect(self._origin, vp).normalized())
        return True

    def mouse_release(self, event, pos):
        if not self.is_active or self._origin is None:
            return False
        if event.button() == Qt.LeftButton:
            vp = self.canvas.mapFromScene(pos)
            vp_rect = QRect(self._origin, vp).normalized()
            self._cleanup()
            if vp_rect.width() >= 8 and vp_rect.height() >= 8:
                tl = self.canvas.mapToScene(vp_rect.topLeft())
                br = self.canvas.mapToScene(vp_rect.bottomRight())
                self._create_marker(QRectF(tl, br))
            return True
        return False

    # ── Création de l'entité ──────────────────────────────────────────────────

    def _create_marker(self, scene_rect: QRectF):
        em = getattr(self.canvas, 'entity_manager', None)
        count = (
            sum(1 for e in em.get_all_entities()
                if getattr(e, 'entity_type', '') == 'marker')
            if em else 0
        )
        name = f"Marqueur {count + 1}"
        entity = MarkerEntity(rect=scene_rect, color=QColor(255, 255, 0, 80), name=name)

        if em:
            eid = em.add_entity(entity)
            entity.entity_id = eid

        entity.draw(self.canvas.scene)

        mw = getattr(self.canvas, 'parent_window', None)
        if mw:
            if hasattr(mw, 'on_entity_added'):
                mw.on_entity_added(entity)
            if hasattr(mw, 'measure_label'):
                mw.measure_label.setText(f"✅ Marqueur '{name}' créé")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _cleanup(self):
        if self._rb:
            self._rb.hide()
            self._rb = None
        self._origin = None
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.ArrowCursor)

    def _status(self, msg: str):
        mw = getattr(self.canvas, 'parent_window', None)
        if mw and hasattr(mw, 'measure_label'):
            mw.measure_label.setText(msg)
