# entities/marker_entity.py
"""Entité Marqueur — zone rectangulaire de surbrillance sans mesure.
Affichage via MarkerWidget (handles de redimensionnement au double-clic).
Aucune étiquette de nom affichée sur le canvas.
"""
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QColor
from .base_entity import BaseEntity


class MarkerEntity(BaseEntity):
    """Rectangle semi-transparent coloré (surbrillance) placé sur le plan."""

    def __init__(self, rect: QRectF, color: QColor = None, name: str = "Marqueur"):
        super().__init__("marker")
        self.rect = QRectF(rect)
        self.color = QColor(color) if color else QColor(255, 255, 0, 80)
        self.name = name
        self.show_measure = False  # Jamais de bulle de mesure

        self.rect_item = None   # référence au MarkerWidget affiché
        self.scene_ref = None

    # ── Dessin ────────────────────────────────────────────────────────────────

    def draw(self, scene):
        self.scene_ref = scene
        self._clear_items(scene)

        if not self.visible:
            return

        from ui.marker_widget import MarkerWidget
        widget = MarkerWidget(rect=self.rect, color=self.color, entity_ref=self)
        widget.setData(0, "marker")
        widget.setData(1, self.entity_id)
        scene.addItem(widget)
        self.rect_item = widget

    def _clear_items(self, scene):
        if self.rect_item:
            try:
                if self.rect_item.scene():
                    scene.removeItem(self.rect_item)
            except Exception:
                pass
        self.rect_item = None

    def delete(self, scene):
        self._clear_items(scene)
        self.scene_ref = None

    # ── Couleur ───────────────────────────────────────────────────────────────

    def set_color(self, color: QColor):
        """Met à jour la couleur et rafraîchit le widget si affiché."""
        c = QColor(color)
        if c.alpha() == 255 and self.color.alpha() != 255:
            c.setAlpha(self.color.alpha())
        self.color = c
        if self.rect_item is not None:
            try:
                self.rect_item.update_color(c)
            except Exception:
                pass

    def set_selected(self, selected: bool):
        if self.rect_item:
            self.rect_item.setSelected(selected)

    # ── Sérialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        # Récupérer la rect courante depuis le widget (peut avoir été redimensionné)
        r = self.rect
        if self.rect_item is not None:
            try:
                p = self.rect_item.pos()
                wr = self.rect_item.rect()
                r = QRectF(p.x(), p.y(), wr.width(), wr.height())
                self.rect = r  # maintenir en sync
            except Exception:
                pass
        return {
            'entity_type': 'marker',
            'entity_id': self.entity_id,
            'name': self.name,
            'rect': [r.x(), r.y(), r.width(), r.height()],
            'color': [self.color.red(), self.color.green(),
                      self.color.blue(), self.color.alpha()],
            'visible': self.visible,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MarkerEntity':
        r = data.get('rect', [0, 0, 100, 50])
        rect = QRectF(r[0], r[1], r[2], r[3])
        c = data.get('color', [255, 255, 0, 80])
        color = QColor(c[0], c[1], c[2], c[3])
        entity = cls(rect=rect, color=color, name=data.get('name', 'Marqueur'))
        entity.entity_id = data.get('entity_id', entity.entity_id)
        entity.visible = data.get('visible', True)
        return entity
