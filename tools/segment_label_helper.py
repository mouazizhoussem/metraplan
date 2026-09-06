from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsRectItem
from PyQt5.QtGui import QFont, QColor, QBrush, QPen
from PyQt5.QtCore import QLineF
import math
from services.measurement import format_length_points


class SegmentLabelHelper:
    """
    Gestion des bulles de longueur pour les segments temporaires ou validés.
    Permet de mutualiser l'affichage entre SurfaceTool et PerimeterTool.
    """

    def __init__(self, canvas, text_color="#1F2933"):
        self.canvas = canvas
        self.text_color = text_color
        self.segment_labels = []
        self.preview_labels = []
        
        # ✅ Accès au scale_manager pour adapter les tailles
        self.scale_manager = getattr(canvas, 'scale_manager', None)

    def _format_length(self, start_point, end_point):
        ppm = getattr(self.canvas, 'pixels_per_meter', 100) or 100
        return format_length_points(start_point, end_point, ppm)

    def _create_label_item(self, start_point, end_point):
        scene = getattr(self.canvas, 'scene', None)
        if not scene:
            return None

        text = self._format_length(start_point, end_point)
        txt = QGraphicsTextItem(text)
        
        # Police style CAO : compact et lisible
        base_font = QFont("Inter", 9)
        if self.scale_manager:
            scaled_font = self.scale_manager.scale_font(base_font, verbose=False)
            txt.setFont(scaled_font)
        else:
            txt.setFont(base_font)
        
        txt.setDefaultTextColor(QColor(self.text_color))
        rect = txt.boundingRect()
        
        # Padding réduit style CAO
        base_padding = 3
        if self.scale_manager:
            padding = self.scale_manager.scale_bubble_padding(base_padding, verbose=False)
        else:
            padding = base_padding
            
        w = rect.width() + padding * 2
        h = rect.height() + padding * 2

        bg = QGraphicsRectItem(0, 0, w, h)
        bg.setBrush(QBrush(QColor(255, 255, 255, 235)))
        bg.setPen(QPen(QColor("#CBD2D9")))
        bg.setZValue(4000)

        txt.setParentItem(bg)
        txt.setPos(padding, padding)

        mid_x = (start_point.x() + end_point.x()) / 2
        mid_y = (start_point.y() + end_point.y()) / 2
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.hypot(dx, dy)
        
        # Offset réduit style CAO
        base_offset = 8
        if self.scale_manager:
            offset = self.scale_manager.scale_bubble_offset(base_offset, verbose=False)
        else:
            offset = base_offset
            
        if length:
            nx = -dy / length
            ny = dx / length
            # Forcer le texte vers le haut (ny <= 0) quelle que soit la direction
            if ny > 0:
                nx, ny = -nx, -ny
            # DEBUG: log pour vérifier l'orientation
            mid_x += nx * offset
            mid_y += ny * offset

        bg.setPos(mid_x - w / 2, mid_y - h / 2)
        scene.addItem(bg)
        
        return bg

    def _remove(self, item):
        if not item:
            return
        try:
            sc = item.scene()
            if sc:
                sc.removeItem(item)
        except Exception:
            pass

    def clear_preview(self):
        for itm in self.preview_labels:
            self._remove(itm)
        self.preview_labels = []

    def clear_all(self):
        self.clear_preview()
        for itm in self.segment_labels:
            self._remove(itm)
        self.segment_labels = []

    def add_segment(self, start_point, end_point):
        label = self._create_label_item(start_point, end_point)
        if label:
            self.segment_labels.append(label)

    def add_preview(self, start_point, end_point, clear=False):
        if clear:
            self.clear_preview()
        label = self._create_label_item(start_point, end_point)
        if label:
            self.preview_labels.append(label)

    def set_preview(self, start_point, end_point):
        self.add_preview(start_point, end_point, clear=True)

    def rebuild(self, points, preview_end=None):
        """
        Recrée toutes les bulles des segments validés.
        Optionnellement, ajoute une bulle de prévisualisation entre le dernier point et preview_end.
        """
        self.clear_all()
        if points and len(points) >= 2:
            for idx in range(1, len(points)):
                self.add_segment(points[idx-1], points[idx])
        if preview_end is not None and points:
            self.set_preview(points[-1], preview_end)

