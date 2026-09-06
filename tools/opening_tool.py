# tools/opening_tool.py
"""
Outil pour créer des ouvertures à déduire des surfaces
Modes : Rectangle (drag) ou Polygone libre (clics successifs)
"""
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsEllipseItem, QGraphicsLineItem
from PyQt5.QtGui import QPen, QColor, QPolygonF, QBrush
from .base_tool import BaseTool
from entities.opening_entity import OpeningEntity
from .segment_label_helper import SegmentLabelHelper


class OpeningTool(BaseTool):
    """Outil hybride pour dessiner des ouvertures rectangulaires ou polygonales"""

    def __init__(self, canvas):
        super().__init__(canvas)

        # Mode rectangle (drag)
        self.rect_start_point = None
        self.rect_current_point = None
        self.is_dragging = False
        self.temp_rect = None
        self.drag_threshold = 5  # pixels pour détecter un drag vs un clic

        # Mode polygone (clics successifs)
        self.points = []  # Points du polygone
        self.temp_lines = []  # Lignes entre les points
        self.point_items = []  # Points affichés
        self.temp_line = None  # Ligne de suivi de la souris
        self.temp_polygon = None  # Polygone temporaire affiché

        # Détection du mode
        self.mode = None  # None, "rectangle", ou "polygon"
        self.click_start_pos = None
        self.has_moved = False

        # Mesures dynamiques (mêmes bulles que périmètre/surface)
        self.label_helper = SegmentLabelHelper(canvas, text_color="#AA0000")

    def activate(self):
        """Active l'outil ouverture"""
        super().activate()
        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Ouverture: Drag = Rectangle | Clics = Polygone | Clic droit = Terminer"
            )

    def mouse_press(self, event, pos):
        """Gère le clic initial"""
        if not self.is_active:
            return False

        # Clic droit : terminer le polygone
        if event.button() == Qt.RightButton:
            if self.mode == "polygon" and len(self.points) >= 3:
                self.finish_polygon()
                return True
            return False

        # Clic gauche
        if event.button() == Qt.LeftButton:
            # Si aucun mode n'est actif, on commence
            if self.mode is None:
                self.click_start_pos = pos
                self.rect_start_point = pos
                self.has_moved = False
                return True

            # Si on est en mode polygone, ajouter un point
            elif self.mode == "polygon":
                self.add_polygon_point(pos)
                return True

        return False

    def mouse_move(self, event, pos):
        """Gère le mouvement de la souris"""
        if not self.is_active:
            return False

        # Détection du mode : drag vs clics
        if self.mode is None and self.click_start_pos:
            distance = ((pos.x() - self.click_start_pos.x())**2 +
                        (pos.y() - self.click_start_pos.y())**2)**0.5

            if distance > self.drag_threshold:
                # C'est un drag : mode rectangle
                self.mode = "rectangle"
                self.is_dragging = True
                if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        "Mode Rectangle: Glissez pour définir la taille"
                    )

        # Mode rectangle : mettre à jour le rectangle
        if self.mode == "rectangle" and self.is_dragging:
            adjusted_pos = self.apply_ortho_constraint_rectangle(pos)
            self.rect_current_point = adjusted_pos
            self.update_temp_rectangle()
            return True

        # Mode polygone : afficher la ligne de suivi
        elif self.mode == "polygon" and self.points:
            adjusted_pos = self.apply_ortho_constraint_polygon(pos)
            self.update_temp_line(adjusted_pos)
            self.update_temp_polygon(adjusted_pos)
            return True

        return False

    def mouse_release(self, event, pos):
        """Gère le relâchement de la souris"""
        if not self.is_active:
            return False

        if event.button() == Qt.LeftButton:
            # Si on n'a pas bougé, c'est un clic simple : mode polygone
            if self.mode is None and self.click_start_pos:
                self.mode = "polygon"
                if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        "Mode Polygone: Cliquez pour ajouter des points | Clic droit pour terminer"
                    )
                self.add_polygon_point(self.click_start_pos)
                self.click_start_pos = None
                return True

            # Mode rectangle : finaliser
            elif self.mode == "rectangle" and self.is_dragging:
                final_pos = self.apply_ortho_constraint_rectangle(pos)
                self.finish_rectangle(final_pos)
                self.reset_tool()
                return True

        return False

    def add_polygon_point(self, pos):
        """Ajoute un point au polygone"""
        # Appliquer le mode ortho
        adjusted_pos = self.apply_ortho_constraint_polygon(pos)

        # Vérifier la distance minimale avec le dernier point
        if self.points:
            last_point = self.points[-1]
            distance = ((adjusted_pos.x() - last_point.x())**2 +
                        (adjusted_pos.y() - last_point.y())**2)**0.5
            if distance < 5:  # Distance minimale
                return

        self.points.append(adjusted_pos)

        # Dessiner le point
        point_item = self.canvas.scene.addEllipse(
            adjusted_pos.x()-3, adjusted_pos.y()-3, 6, 6,
            QPen(Qt.red, 2),
            QColor(255, 100, 100)
        )
        point_item.setData(0, "opening_temp_point")
        point_item.setZValue(1001)
        self.point_items.append(point_item)

        # Dessiner une ligne depuis le point précédent
        if len(self.points) > 1:
            line_item = self.canvas.scene.addLine(
                self.points[-2].x(), self.points[-2].y(),
                self.points[-1].x(), self.points[-1].y(),
                QPen(Qt.red, 2)
            )
            line_item.setData(0, "opening_temp_line")
            line_item.setZValue(1000)
            self.temp_lines.append(line_item)


    def apply_ortho_constraint_rectangle(self, pos):
        """Contrainte ortho pour rectangle : force un carré SEULEMENT si ortho activé"""
        if not self.rect_start_point:
            return pos

        # Vérifier si le mode ortho est activé
        ortho_enabled = (hasattr(self.canvas, 'ortho_manager') and
                         self.canvas.ortho_manager and
                         self.canvas.ortho_manager.is_ortho_enabled())

        # ✅ MODIFICATION: Rectangle libre par défaut
        if not ortho_enabled:
            # Mode normal : rectangle libre selon le curseur
            return pos

        # ✅ Mode ortho activé : forcer un carré (côtés égaux)
        dx = pos.x() - self.rect_start_point.x()
        dy = pos.y() - self.rect_start_point.y()
        size = min(abs(dx), abs(dy))

        adjusted_dx = size if dx >= 0 else -size
        adjusted_dy = size if dy >= 0 else -size

        return QPointF(
            self.rect_start_point.x() + adjusted_dx,
            self.rect_start_point.y() + adjusted_dy
        )

    def apply_ortho_constraint_polygon(self, pos):
        """Contrainte ortho pour polygone : alignement H/V"""
        if not self.points:
            return pos

        # Vérifier si le mode ortho est activé
        ortho_enabled = (hasattr(self.canvas, 'ortho_manager') and
                         self.canvas.ortho_manager and
                         self.canvas.ortho_manager.is_ortho_enabled())

        if not ortho_enabled:
            return pos

        # Aligner sur le dernier point
        last_point = self.points[-1]
        dx = abs(pos.x() - last_point.x())
        dy = abs(pos.y() - last_point.y())

        # Choisir l'axe dominant
        if dx > dy:
            # Alignement horizontal
            return QPointF(pos.x(), last_point.y())
        else:
            # Alignement vertical
            return QPointF(last_point.x(), pos.y())

    def update_temp_rectangle(self):
        """Met à jour le rectangle temporaire"""
        if not self.rect_start_point or not self.rect_current_point:
            return

        # Supprimer l'ancien
        if self.temp_rect and self.temp_rect.scene():
            self.canvas.scene.removeItem(self.temp_rect)

        # Calculer les coordonnées
        x1 = min(self.rect_start_point.x(), self.rect_current_point.x())
        y1 = min(self.rect_start_point.y(), self.rect_current_point.y())
        x2 = max(self.rect_start_point.x(), self.rect_current_point.x())
        y2 = max(self.rect_start_point.y(), self.rect_current_point.y())

        # Créer le rectangle
        self.temp_rect = self.canvas.scene.addRect(
            x1, y1, x2-x1, y2-y1,
            QPen(QColor(255, 0, 0), 2, Qt.DashLine),
            QBrush(QColor(255, 0, 0, 30))
        )
        self.temp_rect.setZValue(1000)

    def update_temp_line(self, pos):
        """Met à jour la ligne de suivi"""
        if self.temp_line and self.temp_line.scene():
            self.canvas.scene.removeItem(self.temp_line)

        if self.points:
            last_point = self.points[-1]
            self.temp_line = self.canvas.scene.addLine(
                last_point.x(), last_point.y(),
                pos.x(), pos.y(),
                QPen(Qt.red, 1, Qt.DashLine)
            )
            self.temp_line.setZValue(1000)
            # ✅ Étiquette de mesure en temps réel, centrée sur le segment rouge
            self.label_helper.set_preview(last_point, pos)
        else:
            # Pas de point ⇒ aucune prévisualisation
            self.label_helper.clear_preview()
            self.temp_line = None

    def update_temp_polygon(self, pos):
        """Met à jour le polygone temporaire"""
        if self.temp_polygon and self.temp_polygon.scene():
            self.canvas.scene.removeItem(self.temp_polygon)

        if len(self.points) >= 2:
            # Créer un polygone avec tous les points + la position actuelle
            temp_points = self.points + [pos]
            polygon = QPolygonF(temp_points)

            self.temp_polygon = self.canvas.scene.addPolygon(
                polygon,
                QPen(QColor(255, 0, 0), 1, Qt.DashLine),
                QBrush(QColor(255, 0, 0, 20))
            )
            self.temp_polygon.setZValue(999)

    def finish_rectangle(self, end_pos):
        """Finalise le rectangle"""
        if not self.rect_start_point:
            return

        x1 = min(self.rect_start_point.x(), end_pos.x())
        y1 = min(self.rect_start_point.y(), end_pos.y())
        x2 = max(self.rect_start_point.x(), end_pos.x())
        y2 = max(self.rect_start_point.y(), end_pos.y())

        # Vérifier taille minimale
        if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
            return

        # Créer les 4 points
        points = [
            QPointF(x1, y1),
            QPointF(x2, y1),
            QPointF(x2, y2),
            QPointF(x1, y2),
        ]

        self.create_opening_entity(points)

    def finish_polygon(self):
        """Finalise le polygone"""
        if len(self.points) < 3:
            return

        self.create_opening_entity(self.points.copy())
        self.reset_tool()

    def create_opening_entity(self, points):
        """Crée l'entité ouverture"""
        try:
            pixels_per_meter = getattr(self.canvas, 'pixels_per_meter', 100)
            if not isinstance(pixels_per_meter, (int, float)) or pixels_per_meter <= 0:
                pixels_per_meter = 100

            # Compter les ouvertures
            opening_count = 0
            if hasattr(self.canvas, 'entity_manager') and self.canvas.entity_manager:
                opening_count = len(
                    self.canvas.entity_manager.get_entities_by_type('opening'))

            # Créer l'entité
            opening_entity = OpeningEntity(
                points=points,
                pixels_per_meter=pixels_per_meter,
                color=QColor(255, 0, 0),
                name=f"Ouverture {opening_count + 1}"
            )

            # Chercher la surface parente
            parent_surface = self.find_surface_containing_opening(
                opening_entity)

            # ✅ CRITIQUE : Associer à la surface AVANT add_entity
            # pour que on_entity_added() sache que c'est une ouverture attachée
            if parent_surface:
                parent_surface.add_opening(opening_entity)
                area_m2 = opening_entity.calculate_area()
                if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        f"✅ Ouverture ajoutée à '{parent_surface.name}' : -{area_m2:.2f} m²"
                    )
            else:
                area_m2 = opening_entity.calculate_area()
                if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        f"⚠️ Ouverture créée : -{area_m2:.2f} m²"
                    )

            # Ajouter au gestionnaire APRÈS avoir établi le lien parent
            if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                entity_id = self.canvas.entity_manager.add_entity(opening_entity)
                opening_entity.entity_id = entity_id
                if hasattr(opening_entity, 'polygon_item') and opening_entity.polygon_item:
                    opening_entity.polygon_item.setData(1, entity_id)

            # Dessiner APRÈS add_entity (pour avoir le scale_manager)
            opening_entity.draw(self.canvas.scene)

        except Exception as e:
            import traceback
            traceback.print_exc()

    def find_surface_containing_opening(self, opening_entity):
        """Trouve la surface contenant l'ouverture"""
        if not hasattr(self.canvas, 'entity_manager') or not self.canvas.entity_manager:
            return None

        surfaces = self.canvas.entity_manager.get_entities_by_type('polygon')
        opening_centroid = opening_entity.get_centroid()

        for surface in surfaces:
            if hasattr(surface, 'points') and len(surface.points) >= 3:
                if hasattr(surface, 'surface_item') and surface.surface_item:
                    offset = surface.surface_item.pos()
                    adjusted_points = [QPointF(p.x() + offset.x(), p.y() + offset.y())
                                       for p in surface.points]
                    polygon = QPolygonF(adjusted_points)
                else:
                    polygon = QPolygonF(surface.points)

                if polygon.containsPoint(opening_centroid, Qt.OddEvenFill):
                    return surface

        return None

    def cleanup_temp_elements(self):
        """Nettoie tous les éléments temporaires"""
        if self.temp_rect and self.temp_rect.scene():
            self.canvas.scene.removeItem(self.temp_rect)
        if self.temp_line and self.temp_line.scene():
            self.canvas.scene.removeItem(self.temp_line)
        if self.temp_polygon and self.temp_polygon.scene():
            self.canvas.scene.removeItem(self.temp_polygon)

        for item in self.temp_lines + self.point_items:
            if item and item.scene():
                self.canvas.scene.removeItem(item)

        self.temp_rect = None
        self.temp_line = None
        self.temp_polygon = None
        self.temp_lines = []
        self.point_items = []
        self.label_helper.clear_all()

    def reset_tool(self):
        """Réinitialise l'outil pour une nouvelle forme"""
        self.cleanup_temp_elements()
        self.mode = None
        self.rect_start_point = None
        self.rect_current_point = None
        self.is_dragging = False
        self.points = []
        self.click_start_pos = None
        self.has_moved = False

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Ouverture: Drag = Rectangle | Clics = Polygone | Clic droit = Terminer"
            )

    # ------------------------------------------------------------------
    # Contrat menu contextuel / ToolManager
    # ------------------------------------------------------------------
    def _rebuild_polygon_temp_graphics(self):
        """Reconstruit les éléments temporaires du mode polygone."""
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return
        self.cleanup_temp_elements()

        for p in self.points:
            point_item = self.canvas.scene.addEllipse(
                p.x()-3, p.y()-3, 6, 6,
                QPen(Qt.red, 2),
                QColor(255, 100, 100)
            )
            point_item.setData(0, "opening_temp_point")
            point_item.setZValue(1001)
            self.point_items.append(point_item)

        for i in range(1, len(self.points)):
            line_item = self.canvas.scene.addLine(
                self.points[i - 1].x(), self.points[i - 1].y(),
                self.points[i].x(), self.points[i].y(),
                QPen(Qt.red, 2)
            )
            line_item.setData(0, "opening_temp_line")
            line_item.setZValue(1000)
            self.temp_lines.append(line_item)

    def finish_current(self):
        """Finalise l'ouverture en cours selon le mode actif."""
        if not self.is_active:
            return False

        if self.mode == "polygon" and len(self.points) >= 3:
            self.finish_polygon()
            return True

        if self.mode == "rectangle" and self.is_dragging and self.rect_current_point:
            self.finish_rectangle(self.rect_current_point)
            self.reset_tool()
            return True

        return False

    def undo_last_point(self):
        """Annule le dernier point du polygone d'ouverture."""
        if not self.is_active:
            return False

        if self.mode == "rectangle":
            self.reset_tool()
            return True

        if self.mode != "polygon" or not self.points:
            return False

        self.points.pop()
        if not self.points:
            self.reset_tool()
            return True

        self._rebuild_polygon_temp_graphics()
        return True

    def toggle_drawing_mode(self):
        """Bascule rectangle/polygone en réinitialisant l'état temporaire."""
        if not self.is_active:
            return False

        if self.mode == "rectangle":
            self.reset_tool()
            self.mode = "polygon"
            target_msg = "Mode Polygone: Cliquez pour ajouter des points | Clic droit pour terminer"
        elif self.mode == "polygon":
            self.reset_tool()
            self.mode = "rectangle"
            target_msg = "Mode Rectangle: Cliquez-glissez pour définir la taille"
        else:
            self.reset_tool()
            self.mode = "polygon"
            target_msg = "Mode Polygone: Cliquez pour ajouter des points | Clic droit pour terminer"

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(target_msg)
        return True

    def get_point_count(self):
        """Retourne un nombre de points cohérent avec le mode d'ouverture actif."""
        if self.mode == "polygon":
            return len(self.points)
        if self.mode == "rectangle" and (self.is_dragging or self.rect_start_point):
            return 1
        return len(self.points)

    def is_drawing_in_progress(self):
        """Indique si une ouverture est en cours de création."""
        return bool(
            self.get_point_count() > 0 or
            self.is_dragging or
            self.click_start_pos is not None
        )

    def deactivate(self):
        """Désactive l'outil"""
        super().deactivate()
        self.reset_tool()

    def cancel(self):
        """Annule l'opération en cours"""
        self.reset_tool()
        self.deactivate()
