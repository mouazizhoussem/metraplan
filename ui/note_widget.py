# ui/note_widget.py
"""NoteWidget — cadre de commentaire redimensionnable sur le canvas.
Même logique de handles que LegendWidget, mais largeur ET hauteur manuelles.
Double-clic → active les handles de redimensionnement.
Clic extérieur → sort du mode redimensionnement.
Double-clic sur le texte → édition inline.
"""
from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsTextItem,
                              QGraphicsItem, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QFont

# ── Constantes ────────────────────────────────────────────────────────────────
_BG        = QColor(255, 252, 180, 235)   # jaune clair
_BORDER    = QColor(200, 175, 40, 220)
_TEXT_COL  = QColor(30, 30, 30)
_HDL_BLUE  = QColor(33, 150, 243)
_HDL_GOLD  = QColor(255, 193, 7)

_H_TL, _H_TC, _H_TR = 0, 1, 2
_H_ML,         _H_MR = 3, 4
_H_BL, _H_BC, _H_BR = 5, 6, 7

_ROLES = (_H_TL, _H_TC, _H_TR, _H_ML, _H_MR, _H_BL, _H_BC, _H_BR)
_CURSORS = {
    _H_TL: Qt.SizeFDiagCursor, _H_TC: Qt.SizeVerCursor,  _H_TR: Qt.SizeBDiagCursor,
    _H_ML: Qt.SizeHorCursor,                               _H_MR: Qt.SizeHorCursor,
    _H_BL: Qt.SizeBDiagCursor, _H_BC: Qt.SizeVerCursor,   _H_BR: Qt.SizeFDiagCursor,
}
_MIN_W, _MIN_H = 120, 60


# ── Handle de redimensionnement ───────────────────────────────────────────────

class _NoteHandle(QGraphicsRectItem):
    SIZE = 10

    def __init__(self, role, note, parent):
        s = self.SIZE
        super().__init__(-s / 2, -s / 2, s, s, parent)
        self.role = role
        self.note = note
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setZValue(2010)
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
            self._orig_rect   = QRectF(self.note.rect())
            self._orig_pos    = QPointF(self.note.pos())
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
            r.setWidth(nw)
            p.setX(self._orig_pos.x() + self._orig_rect.width() - nw)

        # Verticale
        if self.role in (_H_BL, _H_BC, _H_BR):
            r.setHeight(max(_MIN_H, r.height() + dy))
        elif self.role in (_H_TL, _H_TC, _H_TR):
            nh = max(_MIN_H, r.height() - dy)
            r.setHeight(nh)
            p.setY(self._orig_pos.y() + self._orig_rect.height() - nh)

        self.note._apply_rect(r, p)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()


# ── Widget Note ───────────────────────────────────────────────────────────────

class NoteWidget(QGraphicsRectItem):
    """Cadre de commentaire jaune redimensionnable et éditable."""

    DEFAULT_W = 220
    DEFAULT_H = 100

    def __init__(self, pos: QPointF, text: str = "Note…", parent=None):
        super().__init__(0, 0, self.DEFAULT_W, self.DEFAULT_H, parent)
        self.setPos(pos)
        self._text = text
        self._resize_mode = False
        self._handles: list[_NoteHandle] = []

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(1500)
        self.setAcceptHoverEvents(True)

        # Fond jaune + ombre légère
        self.setBrush(QBrush(_BG))
        self.setPen(QPen(_BORDER, 1.5))
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setOffset(2, 2)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

        # Texte éditable
        self._text_item = QGraphicsTextItem(self)
        self._text_item.setDefaultTextColor(_TEXT_COL)
        self._text_item.setFont(QFont("Arial", 10))
        self._text_item.setTextInteractionFlags(Qt.NoTextInteraction)
        self._text_item.setPos(8, 8)
        self._text_item.setPlainText(self._text)
        self._update_text_width()

        self._create_handles()
        self._show_handles(False)

    # ── Handles ───────────────────────────────────────────────────────────────

    def _create_handles(self):
        for role in _ROLES:
            h = _NoteHandle(role, self, self)
            self._handles.append(h)
        self._reposition_handles()

    def _reposition_handles(self):
        r = self.rect()
        cx, cy = r.width() / 2, r.height() / 2
        positions = {
            _H_TL: (0,        0),
            _H_TC: (cx,       0),
            _H_TR: (r.width(), 0),
            _H_ML: (0,        cy),
            _H_MR: (r.width(), cy),
            _H_BL: (0,        r.height()),
            _H_BC: (cx,       r.height()),
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
        self._update_text_width()
        self._reposition_handles()

    def _update_text_width(self):
        w = max(_MIN_W - 16, self.rect().width() - 16)
        self._text_item.setTextWidth(w)

    def exit_resize_mode(self):
        self._resize_mode = False
        self._show_handles(False)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)

    # ── Texte ─────────────────────────────────────────────────────────────────

    def get_text(self) -> str:
        return self._text_item.toPlainText()

    def set_text(self, text: str):
        self._text = text
        self._text_item.setPlainText(text)

    def enable_text_editing(self):
        self._text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
        self._text_item.setFocus()
        cursor = self._text_item.textCursor()
        cursor.select(cursor.Document)
        self._text_item.setTextCursor(cursor)

    def disable_text_editing(self):
        self._text_item.setTextInteractionFlags(Qt.NoTextInteraction)
        self._text = self._text_item.toPlainText()
        if hasattr(self, '_canvas_view'):
            self._canvas_view.scene().clearFocus()

    # ── Événements ────────────────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        if not self._resize_mode:
            # Premier double-clic → mode resize
            self._resize_mode = True
            self._show_handles(True)
            self.setFlag(QGraphicsItem.ItemIsMovable, False)
        else:
            # Deuxième double-clic en mode resize → éditer le texte
            self.enable_text_editing()
        event.accept()

    def mousePressEvent(self, event):
        if self._text_item.textInteractionFlags() & Qt.TextEditorInteraction:
            # Propager au texte pour positionner le curseur
            super().mousePressEvent(event)
            return
        super().mousePressEvent(event)

    def focusOutEvent(self, event):
        self.disable_text_editing()
        super().focusOutEvent(event)

    def hoverEnterEvent(self, event):
        if not self._resize_mode:
            self.setCursor(Qt.SizeAllCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    # ── Sérialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            'widget_type': 'note',
            'x': self.pos().x(),
            'y': self.pos().y(),
            'width': self.rect().width(),
            'height': self.rect().height(),
            'text': self.get_text(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NoteWidget':
        pos = QPointF(data.get('x', 100), data.get('y', 100))
        widget = cls(pos=pos, text=data.get('text', 'Note…'))
        r = widget.rect()
        r.setWidth(data.get('width', cls.DEFAULT_W))
        r.setHeight(data.get('height', cls.DEFAULT_H))
        widget.setRect(r)
        widget._update_text_width()
        widget._reposition_handles()
        return widget
