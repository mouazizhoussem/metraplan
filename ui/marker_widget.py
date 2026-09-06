# ui/marker_widget.py
"""MarkerWidget — rectangle de surbrillance redimensionnable.
Double-clic → affiche les handles.  Clic extérieur → masque les handles.
Même logique de handles que NoteWidget (8 poignées, coins + milieux).
"""
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPen, QBrush, QColor

# ── Constantes handles ────────────────────────────────────────────────────────
_HDL_BLUE = QColor(33, 150, 243)
_HDL_GOLD = QColor(255, 193, 7)

_H_TL, _H_TC, _H_TR = 0, 1, 2
_H_ML,         _H_MR = 3, 4
_H_BL, _H_BC, _H_BR = 5, 6, 7

_ROLES = (_H_TL, _H_TC, _H_TR, _H_ML, _H_MR, _H_BL, _H_BC, _H_BR)
_CURSORS = {
    _H_TL: Qt.SizeFDiagCursor, _H_TC: Qt.SizeVerCursor,  _H_TR: Qt.SizeBDiagCursor,
    _H_ML: Qt.SizeHorCursor,                               _H_MR: Qt.SizeHorCursor,
    _H_BL: Qt.SizeBDiagCursor, _H_BC: Qt.SizeVerCursor,   _H_BR: Qt.SizeFDiagCursor,
}
_MIN_W, _MIN_H = 30, 20


# ── Handle ────────────────────────────────────────────────────────────────────

class _MarkerHandle(QGraphicsRectItem):
    SIZE = 10

    def __init__(self, role, widget, parent):
        s = self.SIZE
        super().__init__(-s / 2, -s / 2, s, s, parent)
        self.role = role
        self.widget = widget
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setZValue(2020)
        self._dragging = False
        self._press_scene = None
        self._orig_rect = None
        self._orig_pos  = None
        self._draw_normal()

    def _draw_normal(self):
        self.setBrush(QBrush(_HDL_BLUE))
        self.setPen(QPen(QColor(255, 255, 255), 1.5))

    def _draw_hover(self):
        self.setBrush(QBrush(_HDL_GOLD))
        self.setPen(QPen(QColor(255, 255, 255), 1.5))

    def hoverEnterEvent(self, event):
        self._draw_hover()
        self.setCursor(_CURSORS.get(self.role, Qt.SizeAllCursor))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._draw_normal()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._press_scene = event.scenePos()
            self._orig_rect   = QRectF(self.widget.rect())
            self._orig_pos    = QPointF(self.widget.pos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._dragging:
            super().mouseMoveEvent(event)
            return
        dx = (event.scenePos() - self._press_scene).x()
        dy = (event.scenePos() - self._press_scene).y()
        r = QRectF(self._orig_rect)
        p = QPointF(self._orig_pos)

        # Horizontale
        if self.role in (_H_TR, _H_MR, _H_BR):
            r.setWidth(max(_MIN_W, r.width() + dx))
        elif self.role in (_H_TL, _H_ML, _H_BL):
            nw = max(_MIN_W, r.width() - dx)
            p.setX(self._orig_pos.x() + self._orig_rect.width() - nw)
            r.setWidth(nw)

        # Verticale
        if self.role in (_H_BL, _H_BC, _H_BR):
            r.setHeight(max(_MIN_H, r.height() + dy))
        elif self.role in (_H_TL, _H_TC, _H_TR):
            nh = max(_MIN_H, r.height() - dy)
            p.setY(self._orig_pos.y() + self._orig_rect.height() - nh)
            r.setHeight(nh)

        self.widget._apply_rect(r, p)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        # Synchroniser l'entité après relâchement
        if self.widget.entity_ref is not None:
            from PyQt5.QtCore import QRectF
            p = self.widget.pos()
            r = self.widget.rect()
            self.widget.entity_ref.rect = QRectF(p.x(), p.y(), r.width(), r.height())
        event.accept()


# ── MarkerWidget ──────────────────────────────────────────────────────────────

class MarkerWidget(QGraphicsRectItem):
    """Rectangle de surbrillance interactif (redimensionnable au double-clic)."""

    def __init__(self, rect: QRectF, color: QColor, entity_ref=None, parent=None):
        # On stocke la position dans setPos, le rect commence en (0,0)
        super().__init__(0, 0, rect.width(), rect.height(), parent)
        self.setPos(rect.x(), rect.y())
        self.entity_ref = entity_ref   # référence à MarkerEntity pour sync
        self._resize_mode = False
        self._handles: list = []

        # Drag manuel (ItemIsMovable ne fonctionne pas avec le mode NoDrag de la vue)
        self._dragging = False
        self._drag_start_scene = None
        self._drag_start_pos   = None

        self.setFlag(QGraphicsItem.ItemIsMovable, False)   # géré manuellement
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(50)
        self.setAcceptHoverEvents(True)

        self._apply_color(color)
        self._create_handles()
        self._show_handles(False)

    # ── Couleur ───────────────────────────────────────────────────────────────

    def _apply_color(self, color: QColor):
        fill = QColor(color)
        fill.setAlpha(max(20, min(200, color.alpha())))
        border = QColor(color)
        border.setAlpha(220)
        self.setBrush(QBrush(fill))
        self.setPen(QPen(border.darker(140), 2, Qt.DashLine))

    def update_color(self, color: QColor):
        self._apply_color(color)
        self.update()

    # ── Handles ───────────────────────────────────────────────────────────────

    def _create_handles(self):
        for role in _ROLES:
            h = _MarkerHandle(role, self, self)
            self._handles.append(h)
        self._reposition_handles()

    def _reposition_handles(self):
        r = self.rect()
        cx, cy = r.width() / 2, r.height() / 2
        positions = {
            _H_TL: (0,         0),
            _H_TC: (cx,        0),
            _H_TR: (r.width(), 0),
            _H_ML: (0,         cy),
            _H_MR: (r.width(), cy),
            _H_BL: (0,         r.height()),
            _H_BC: (cx,        r.height()),
            _H_BR: (r.width(), r.height()),
        }
        for h in self._handles:
            x, y = positions[h.role]
            h.setPos(x, y)

    def _show_handles(self, visible: bool):
        for h in self._handles:
            h.setVisible(visible)

    # ── Redimensionnement ────────────────────────────────────────────────────

    def _apply_rect(self, new_rect: QRectF, new_pos: QPointF):
        self.setRect(new_rect)
        self.setPos(new_pos)
        self._reposition_handles()

    def exit_resize_mode(self):
        self._resize_mode = False
        self._show_handles(False)
        self._sync_entity()

    def _sync_entity(self):
        if self.entity_ref is not None:
            p = self.pos()
            r = self.rect()
            self.entity_ref.rect = QRectF(p.x(), p.y(), r.width(), r.height())

    # ── Drag fluide (implémentation manuelle) ────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._resize_mode:
            self._dragging = True
            self._drag_start_scene = event.scenePos()
            self._drag_start_pos   = QPointF(self.pos())
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            delta = event.scenePos() - self._drag_start_scene
            self.setPos(self._drag_start_pos + delta)
            self._sync_entity()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.SizeAllCursor)
            self._sync_entity()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # ── Double-clic → mode resize ─────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        if not self._resize_mode:
            self._resize_mode = True
            self._show_handles(True)
        else:
            self.exit_resize_mode()
        event.accept()

    # ── Hover ────────────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event):
        if not self._resize_mode and not self._dragging:
            self.setCursor(Qt.SizeAllCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self._dragging:
            self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)
