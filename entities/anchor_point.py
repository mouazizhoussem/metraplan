# plan/entities/anchor_point.py
from PyQt5.QtWidgets import QGraphicsEllipseItem
from PyQt5.QtCore import QPointF, pyqtSignal
from PyQt5.QtGui import QColor


class AnchorPoint(QGraphicsEllipseItem):
    """Point d'ancrage pour l'édition de géométrie"""
    positionChanged = pyqtSignal(int, QPointF)  # index, nouvelle position

    def __init__(self, x, y, index, parent_entity):
        # Cercle de 10x10 pixels
        super().__init__(-5, -5, 10, 10)
        self.setPos(x, y)
        self.index = index
        self.parent_entity = parent_entity
        self.setBrush(QColor(255, 0, 0))
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)
        self.setZValue(100)  # Toujours au-dessus des autres éléments

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.ItemPositionChange:
            # Émettre le changement de position
            self.positionChanged.emit(self.index, value)
        return super().itemChange(change, value)
