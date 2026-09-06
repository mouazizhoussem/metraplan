from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsEllipseItem, QGraphicsPolygonItem
from PyQt5.QtGui import QPen, QColor, QPolygonF, QPainterPath, QBrush


class EditableHandle(QGraphicsEllipseItem):
    """Handle déplaçable pour éditer les sommets d'un polygone"""

    def __init__(self, position, index, editable_surface):
        radius = 6
        super().__init__(-radius, -radius, 2*radius, 2*radius)

        self.editable_surface = editable_surface
        self.vertex_index = index
        self.is_dragging = False
        self.drag_start_pos = None

        # Style du handle
        self.setPen(QPen(Qt.red, 2))
        self.setBrush(QBrush(QColor(255, 100, 100, 180)))
        self.setPos(position)

        # Propriétés d'interaction
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setZValue(1000)  # Au-dessus de tout

        # Marquer comme handle
        self.setData(0, "editable_handle")
        self.setData(1, index)

    def mousePressEvent(self, event):
        """Début du glissement"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Pendant le glissement"""
        if self.is_dragging:
            # Met à jour la position du handle
            super().mouseMoveEvent(event)
            # Notifie la surface éditée de la nouvelle position
            self.editable_surface.update_vertex(self.vertex_index, self.pos())

    def mouseReleaseEvent(self, event):
        """Fin du glissement"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.drag_start_pos = None
            # Finalise la mise à jour
            self.editable_surface.finalize_vertex_update()
        super().mouseReleaseEvent(event)


class EditableSurface(QGraphicsItem):
    """Surface avec handles éditables pour modifier la forme"""

    def __init__(self, points, canvas, openings=None):
        super().__init__()
        self.canvas = canvas
        self.original_points = [QPointF(p) for p in points]
        self.current_points = [QPointF(p) for p in points]
        self.openings = openings or []
        self.handles = []
        self.is_editing = False

        # Éléments graphiques - INITIALISATION DIFFÉRÉE
        self.polygon_item = None
        self.text_item = None
        self.text_bg = None
        self.opening_items = []

        # Propriétés
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setData(0, "editable_surface")

        # NE PAS créer la surface ici - sera créé après ajout à la scène

    def initialize_surface(self):
        """Initialise la surface après ajout à la scène"""
        self.create_surface()
        self.create_handles()

    def boundingRect(self):
        """Rectangle englobant pour Qt"""
        if not self.current_points:
            return QRectF(0, 0, 100, 100)  # Rectangle par défaut

        min_x = min(p.x() for p in self.current_points)
        max_x = max(p.x() for p in self.current_points)
        min_y = min(p.y() for p in self.current_points)
        max_y = max(p.y() for p in self.current_points)

        margin = 20  # Marge pour les handles
        return QRectF(min_x - margin, min_y - margin,
                      (max_x - min_x) + 2*margin, (max_y - min_y) + 2*margin)

    def paint(self, painter, option, widget):
        """Méthode paint requise par QGraphicsItem (vide car on utilise des sous-items)"""
        pass

    def create_surface(self):
        """Crée la surface graphique"""
        if not self.scene():
            return  # Pas encore dans une scène

        # Supprime l'ancienne surface si elle existe
        if self.polygon_item:
            if self.polygon_item.scene():
                self.scene().removeItem(self.polygon_item)

        # Supprime les anciens éléments d'ouverture
        for item in self.opening_items:
            if item.scene():
                self.scene().removeItem(item)
        self.opening_items = []

        # Calcule les surfaces
        gross_area = self.canvas.parent_window.calculator.calculate_area(
            self.current_points)
        net_area = gross_area

        # Déduit les ouvertures
        for opening in self.openings:
            opening_area = self.canvas.parent_window.calculator.calculate_area(
                opening)
            net_area -= opening_area

        # Crée la surface avec trous si nécessaire
        if self.openings:
            main_path = QPainterPath()
            main_path.addPolygon(QPolygonF(self.current_points))

            for opening_points in self.openings:
                opening_path = QPainterPath()
                opening_path.addPolygon(QPolygonF(opening_points))
                main_path = main_path.subtracted(opening_path)

            self.polygon_item = self.scene().addPath(
                main_path,
                QPen(Qt.green, 2),
                QColor(0, 255, 0, 80)
            )
        else:
            self.polygon_item = self.scene().addPolygon(
                QPolygonF(self.current_points),
                QPen(Qt.green, 2),
                QColor(0, 255, 0, 80)
            )

        self.polygon_item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.polygon_item.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.polygon_item.setData(0, "surface_polygon")
        self.polygon_item.setParentItem(self)

        # Ajoute les contours des ouvertures pour les rendre visibles
        for opening_points in self.openings:
            opening_contour = self.scene().addPolygon(
                QPolygonF(opening_points),
                QPen(Qt.red, 1, Qt.DashLine),
                QColor(0, 0, 0, 0)  # Transparent
            )
            opening_contour.setFlag(QGraphicsItem.ItemIsSelectable, True)
            opening_contour.setFlag(QGraphicsItem.ItemIsMovable, True)
            opening_contour.setData(0, "surface_opening")
            opening_contour.setParentItem(self)
            self.opening_items.append(opening_contour)

        # Met à jour le texte
        self.update_text(net_area, gross_area)

    def update_text(self, net_area, gross_area):
        """Met à jour le texte de surface"""
        if not self.scene():
            return

        # Supprime l'ancien texte
        if self.text_item:
            if self.text_item.scene():
                self.scene().removeItem(self.text_item)
        if self.text_bg:
            if self.text_bg.scene():
                self.scene().removeItem(self.text_bg)

        # Formate le nouveau texte
        if self.canvas.parent_window.calculator.px_per_m:
            net_area_m2 = net_area / \
                (self.canvas.parent_window.calculator.px_per_m ** 2)
            gross_area_m2 = gross_area / \
                (self.canvas.parent_window.calculator.px_per_m ** 2)
            text = f"{net_area_m2:.2f} m²"
            tooltip_text = f"Surface brute: {gross_area_m2:.2f} m² - Surface nette: {net_area_m2:.2f} m²"
        else:
            text = f"{net_area:.2f} px²"
            tooltip_text = f"Surface brute: {gross_area:.2f} px² - Surface nette: {net_area:.2f} px²"

        # Crée le nouveau texte
        centroid = self.get_centroid()
        self.text_item, self.text_bg = self.canvas.create_text_with_background(
            text, centroid)
        self.text_item.setDefaultTextColor(Qt.green)
        self.text_item.setParentItem(self)
        self.text_bg.setParentItem(self)

        # Met à jour le tooltip
        if self.polygon_item:
            self.polygon_item.setToolTip(tooltip_text)

    def get_centroid(self):
        """Calcule le centroïde du polygone"""
        if not self.current_points:
            return QPointF(0, 0)

        sum_x = sum(p.x() for p in self.current_points)
        sum_y = sum(p.y() for p in self.current_points)

        return QPointF(sum_x / len(self.current_points), sum_y / len(self.current_points))

    def create_handles(self):
        """Crée les handles d'édition"""
        if not self.scene():
            return

        # Supprime les anciens handles
        self.delete_handles()

        self.handles = []
        for i, point in enumerate(self.current_points):
            handle = EditableHandle(point, i, self)
            self.scene().addItem(handle)
            handle.setVisible(False)  # Cachés par défaut
            self.handles.append(handle)

    def show_handles(self):
        """Affiche les handles d'édition"""
        self.is_editing = True
        for handle in self.handles:
            handle.setVisible(True)

    def hide_handles(self):
        """Cache les handles d'édition"""
        self.is_editing = False
        for handle in self.handles:
            handle.setVisible(False)

    def update_vertex(self, index, new_position):
        """Met à jour un sommet pendant le glissement"""
        if 0 <= index < len(self.current_points):
            self.current_points[index] = QPointF(new_position)
            self.create_surface()  # Redessine en temps réel

    def finalize_vertex_update(self):
        """Finalise la mise à jour après le glissement"""
        # Met à jour le label principal
        gross_area = self.canvas.parent_window.calculator.calculate_area(
            self.current_points)
        net_area = gross_area

        for opening in self.openings:
            opening_area = self.canvas.parent_window.calculator.calculate_area(
                opening)
            net_area -= opening_area

        if self.canvas.parent_window.calculator.px_per_m:
            net_area_m2 = net_area / \
                (self.canvas.parent_window.calculator.px_per_m ** 2)
            text = f"{net_area_m2:.2f} m²"
        else:
            text = f"{net_area:.2f} px²"

        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                f"Surface mise à jour : {text}")

    def toggle_edit_mode(self):
        """Bascule entre mode édition et mode normal"""
        if self.is_editing:
            self.hide_handles()
        else:
            self.show_handles()

    def delete_handles(self):
        """Supprime tous les handles"""
        for handle in self.handles:
            if handle.scene():
                self.scene().removeItem(handle)
        self.handles = []
