from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtWidgets import QGraphicsPathItem, QGraphicsSimpleTextItem
from PyQt5.QtGui import QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF
from .base_entity import BaseEntity
import math


class PointEntity(BaseEntity):
    def __init__(self, position, properties=None):
        super().__init__("point")
        props = properties or {}

        self.position = QPointF(position)
        self.counter_number = props.get('counter_number', 0)
        self.name = props.get('name') or (
            f"Compteur {self.counter_number}" if self.counter_number else "Compteur")
        self.group_id = props.get('group_id')
        self.show_label = props.get('show_label', True)
        self.debug = False
        self.length = props.get('length', 0.0)
        self.height = props.get('height', 0.0)
        self.thickness = props.get('thickness', 0.0)

        self.point_item = None
        self.text_item = None
        self.name_item = None
        self.scene_ref = None

        self.shape = props.get('shape', 'circle')
        self.size = props.get('size', 14)

        color = props.get('color', QColor(255, 0, 0, 200))
        self.set_color(color)

    def _shape_path(self, size):
        half = size / 2.0
        path = QPainterPath()

        if self.shape == "circle":
            path.addEllipse(-half, -half, size, size)
        elif self.shape == "square":
            path.addRect(-half, -half, size, size)
        elif self.shape == "triangle":
            points = [
                QPointF(0, -half),
                QPointF(-half, half),
                QPointF(half, half)
            ]
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.closeSubpath()
        elif self.shape == "triangle_inverted":
            points = [
                QPointF(-half, -half),
                QPointF(half, -half),
                QPointF(0, half)
            ]
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.closeSubpath()
        elif self.shape == "trapezoid":
            top = size * 0.6
            points = [
                QPointF(-top / 2, -half),
                QPointF(top / 2, -half),
                QPointF(half, half),
                QPointF(-half, half)
            ]
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.closeSubpath()
        elif self.shape == "trapezoid_inverted":
            top = size * 0.6
            points = [
                QPointF(-half, -half),
                QPointF(half, -half),
                QPointF(top / 2, half),
                QPointF(-top / 2, half)
            ]
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.closeSubpath()
        elif self.shape == "star":
            points = []
            outer = half
            inner = half * 0.5
            for i in range(10):
                angle = math.radians(-90 + i * 36)
                radius = outer if i % 2 == 0 else inner
                points.append(QPointF(
                    math.cos(angle) * radius,
                    math.sin(angle) * radius
                ))
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.closeSubpath()
        else:
            path.addEllipse(-half, -half, size, size)

        return path

    def _create_items(self):
        display_size = self.get_scaled_size(self.size)
        pen_width = self.get_scaled_pen_width(2)
        font_size = self.get_scaled_font_size(8)
        name_font_size = self.get_scaled_font_size(8)

        color = QColor(self.color) if isinstance(self.color, str) else self.color

        # Forme
        self.point_item = QGraphicsPathItem(self._shape_path(display_size))
        self.point_item.setPos(self.position)
        self.point_item.setPen(QPen(color.darker(120), pen_width))
        self.point_item.setBrush(QBrush(color))
        self.point_item.setData(0, "point_entity")
        self.point_item.setData(1, self.entity_id)
        self.point_item.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
        self.point_item.setFlag(QGraphicsPathItem.ItemIsFocusable, True)
        self.point_item.setAcceptedMouseButtons(Qt.LeftButton)

        # Numéro
        self.text_item = QGraphicsSimpleTextItem(str(self.counter_number))
        self.text_item.setFont(QFont("Arial", font_size, QFont.Bold))
        self.text_item.setBrush(QBrush(Qt.white))
        self.text_item.setData(0, "point_text")
        self.text_item.setData(1, self.entity_id)
        self.text_item.setAcceptedMouseButtons(Qt.NoButton)

        # Nom
        self.name_item = QGraphicsSimpleTextItem(self.name)
        self.name_item.setFont(QFont("Arial", name_font_size))
        self.name_item.setBrush(QBrush(Qt.black))
        self.name_item.setData(0, "point_name")
        self.name_item.setData(1, self.entity_id)
        self.name_item.setAcceptedMouseButtons(Qt.NoButton)
        self.name_item.setVisible(self.show_label)

        self._update_text_positions()

    def _update_text_positions(self):
        display_size = self.get_scaled_size(self.size)
        half = display_size / 2.0

        if self.text_item:
            rect = self.text_item.boundingRect()
            self.text_item.setPos(
                self.position.x() - rect.width() / 2,
                self.position.y() - rect.height() / 2
            )

        if self.name_item:
            rect = self.name_item.boundingRect()
            margin = self.get_scaled_offset(4)
            self.name_item.setPos(
                self.position.x() - rect.width() / 2,
                self.position.y() + half + margin
            )

    def draw(self, scene):
        """Dessine le point sur la scène"""
        self.scene_ref = scene

        # Nettoyage si déjà présents
        if self.point_item and self.point_item.scene():
            scene.removeItem(self.point_item)
        if self.text_item and self.text_item.scene():
            scene.removeItem(self.text_item)
        if self.name_item and self.name_item.scene():
            scene.removeItem(self.name_item)

        self._create_items()
        scene.addItem(self.point_item)
        scene.addItem(self.text_item)
        scene.addItem(self.name_item)
        if self.debug and self.name_item:
            pass

    def draw_text(self, scene):
        """Met à jour le texte (nom + numéro)"""
        if self.text_item:
            self.text_item.setText(str(self.counter_number))
        if self.name_item:
            self.name_item.setText(self.name)
            self.name_item.setVisible(self.show_label)
        self._update_text_positions()

    def move_by(self, dx, dy):
        """Déplace le compteur"""
        self.position = QPointF(self.position.x() + dx, self.position.y() + dy)
        if self.point_item:
            self.point_item.setPos(self.position)
        self._update_text_positions()

    def remove(self, scene):
        """Supprime le point de la scène"""
        if self.point_item and self.point_item in scene.items():
            scene.removeItem(self.point_item)
        if self.text_item and self.text_item in scene.items():
            scene.removeItem(self.text_item)
        if self.name_item and self.name_item in scene.items():
            scene.removeItem(self.name_item)

    def delete(self, scene):
        """Supprime complètement l'entité (alias de remove pour compatibilité)"""
        self.remove(scene)

    # IMPLÉMENTATION DES MÉTHODES ABSTRAITES
    def to_dict(self):
        """Convertit l'entité en dictionnaire pour la sérialisation"""
        return {
            'type': 'point',
            'position': {'x': self.position.x(), 'y': self.position.y()},
            'entity_id': self.entity_id,
            'counter_number': self.counter_number,
            'name': self.name,
            'color': self.color,
            'shape': self.shape,
            'size': self.size,
            'group_id': self.group_id,
            'show_label': self.show_label,
            'length': self.length,
            'height': self.height,
            'thickness': self.thickness
        }

    @classmethod
    def from_dict(cls, data):
        """Crée une entité à partir d'un dictionnaire"""
        position = QPointF(data['position']['x'], data['position']['y'])
        entity = cls(position, {
            'counter_number': data.get('counter_number', 0),
            'name': data.get('name', 'Compteur'),
            'color': data.get('color', '#ff0000'),
            'shape': data.get('shape', 'circle'),
            'size': data.get('size', 14),
            'group_id': data.get('group_id'),
            'show_label': data.get('show_label', True),
            'length': data.get('length', 0.0),
            'height': data.get('height', 0.0),
            'thickness': data.get('thickness', 0.0)
        })
        entity.entity_id = data.get('entity_id')
        return entity

    def calculate_length(self):
        return float(self.length or 0.0)

    def calculate_area(self):
        return float(self.length or 0.0) * float(self.height or 0.0)

    def calculate_volume(self):
        return float(self.length or 0.0) * float(self.height or 0.0) * float(self.thickness or 0.0)

    def set_color(self, color):
        """Définit la couleur du compteur"""
        if isinstance(color, str):
            qcolor = QColor(color)
        elif isinstance(color, QColor):
            qcolor = color
        else:
            qcolor = QColor(255, 0, 0, 200)

        if not qcolor.isValid():
            qcolor = QColor(255, 0, 0, 200)

        self.color = qcolor.name(QColor.HexArgb)

        if self.point_item:
            self.point_item.setPen(
                QPen(qcolor.darker(120), self.get_scaled_pen_width(2)))
            self.point_item.setBrush(QBrush(qcolor))

    def set_shape(self, shape):
        """Met à jour la forme"""
        self.shape = shape
        if self.scene_ref:
            self.draw(self.scene_ref)

    def set_size(self, size):
        """Met à jour la taille"""
        self.size = int(size)
        if self.scene_ref:
            self.draw(self.scene_ref)

    def set_selected(self, selected):
        """Met à jour l'affichage sélectionné"""
        super().set_selected(selected)
        if self.point_item:
            color = QColor(self.color) if isinstance(
                self.color, str) else self.color
            width = self.get_scaled_pen_width(3 if selected else 2)
            self.point_item.setPen(QPen(color.darker(130), width))
