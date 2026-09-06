# tools/distance_tool.py
from PyQt5.QtCore import Qt, QPointF, QLineF
from PyQt5.QtGui import QPen, QColor, QBrush
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem
from entities.line_entity import LineEntity
from .base_tool import BaseTool
from .segment_label_helper import SegmentLabelHelper
import math


class DistanceTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.points = []
        self.temp_line = None
        self.point_items = []

        # Ajoutez ces attributs pour le mode Ortho
        self.start_point = None
        self.last_point = None

        # Bulle fantôme pendant le tracé
        self._seg_helper = SegmentLabelHelper(canvas, text_color="#1F2933")

    def activate(self):
        """Active l'outil de distance"""
        super().activate()
        self.points = []
        self.start_point = None
        self.last_point = None
        self._seg_helper = SegmentLabelHelper(self.canvas, text_color="#1F2933")
        self.cleanup_temp_elements()
        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Mode distance: Cliquez pour le point de départ")

    def deactivate(self):
        """Désactive l'outil de distance"""
        super().deactivate()
        self.cleanup_temp_elements()
        self.points = []
        self.start_point = None
        self.last_point = None

    def get_ortho_point(self, current_pos):
        """Retourne le point orthogonal le plus proche (horizontal ou vertical)"""
        if not self.points:
            return current_pos

        last_point = self.points[-1]
        dx = abs(current_pos.x() - last_point.x())
        dy = abs(current_pos.y() - last_point.y())

        # Si le mouvement est plus horizontal que vertical
        if dx > dy:
            return QPointF(current_pos.x(), last_point.y())
        else:
            return QPointF(last_point.x(), current_pos.y())

    def calculate_distance(self, point1, point2):
        """Calcule la distance entre deux points avec l'échelle actuelle"""
        dx = point2.x() - point1.x()
        dy = point2.y() - point1.y()
        distance_px = math.sqrt(dx**2 + dy**2)

        # Utilisez TOUJOURS self.canvas.pixels_per_meter directement
        if hasattr(self.canvas, 'pixels_per_meter') and self.canvas.pixels_per_meter > 0:
            distance_m = distance_px / self.canvas.pixels_per_meter
        else:
            distance_m = distance_px  # Fallback si aucune échelle n'est définie

        return distance_m, distance_px

    def mouse_press(self, event, pos):
        """Gère les clics de souris"""
        if not self.is_active:
            return False

        if event.button() == Qt.LeftButton:
            # Utiliser le mode ortho si activé
            ortho_mode = hasattr(
                self.canvas, 'ortho_manager') and self.canvas.ortho_manager.is_ortho_enabled()
            if ortho_mode and self.points:
                final_pos = self.get_ortho_point(pos)
            else:
                final_pos = pos

            self.points.append(final_pos)
            self.last_point = final_pos  # Mettre à jour pour le mode Ortho

            if not self.start_point:
                self.start_point = final_pos

            # Dessiner le point
            point_item = QGraphicsEllipseItem(-3, -3, 6, 6)
            point_item.setPos(final_pos)
            point_item.setBrush(QBrush(QColor(0, 0, 255)))
            point_item.setPen(QPen(Qt.NoPen))
            point_item.setData(0, "distance_temp_point")
            self.canvas.scene.addItem(point_item)
            self.point_items.append(point_item)

            if len(self.points) == 1:
                if hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        "Cliquez pour le point d'arrivée")
                return True
            elif len(self.points) == 2:
                self.finish_distance()
                return True

        return False

    def mouse_move(self, event, pos):
        """Gère les mouvements de souris avec mode ortho"""
        if not self.is_active or not self.points:
            return False

        # Utiliser le mode ortho si activé
        ortho_mode = hasattr(
            self.canvas, 'ortho_manager') and self.canvas.ortho_manager.is_ortho_enabled()
        if ortho_mode:
            final_pos = self.get_ortho_point(pos)
        else:
            final_pos = pos

        # Supprimer l'ancienne ligne temporaire
        if self.temp_line:
            self.canvas.scene.removeItem(self.temp_line)

        # Créer la nouvelle ligne temporaire
        line = QLineF(self.points[0], final_pos)
        self.temp_line = QGraphicsLineItem(line)
        self.temp_line.setPen(QPen(QColor(0, 0, 255), 2, Qt.DashLine))
        self.temp_line.setData(0, "distance_temp_line")
        self.canvas.scene.addItem(self.temp_line)

        # Bulle fantôme sur le segment en cours
        self._seg_helper.set_preview(self.points[0], final_pos)

        # Calculer et afficher la distance en temps réel avec l'échelle actuelle
        distance_m, distance_px = self.calculate_distance(
            self.points[0], final_pos)

        # Afficher la distance en temps réel
        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                f"Distance: {distance_m:.2f} m - Cliquez pour le point d'arrivée"
            )

        return True

    def finish_distance(self):
        """Finalise la mesure de distance"""
        if len(self.points) < 2:
            return

        # Nettoyer les éléments temporaires
        self.cleanup_temp_elements()

        # Calculer la distance avec l'échelle actuelle
        distance_m, distance_px = self.calculate_distance(
            self.points[0], self.points[1])

        # Créer l'entité ligne avec l'échelle actuelle du canvas
        distance_entity = LineEntity(
            self.points[0], self.points[1],
            color=QColor(0, 0, 255), width=3,
            pixels_per_meter=self.canvas.pixels_per_meter  # ← Utilise l'échelle du canvas
        )

        # Utiliser un nom par défaut
        line_count = len(self.canvas.entity_manager.get_entities_by_type('line')) if hasattr(
            self.canvas, 'entity_manager') and self.canvas.entity_manager else 0
        distance_entity.name = f"Distance {line_count + 1}"

        # ✅ CORRECTION: Ajouter au gestionnaire AVANT de dessiner
        if hasattr(self.canvas, 'entity_manager') and self.canvas.entity_manager:
            entity_id = self.canvas.entity_manager.add_entity(distance_entity)
            distance_entity.entity_id = entity_id
        # Dessiner APRÈS (pour avoir le scale_manager)
        distance_entity.draw(self.canvas.scene)

        # ✅ CRITIQUE: Mettre à jour le data(1) maintenant que entity_id existe
        if hasattr(self.canvas, 'entity_manager') and self.canvas.entity_manager:
            if hasattr(distance_entity, 'line_item') and distance_entity.line_item:
                distance_entity.line_item.setData(1, entity_id)

        # Afficher le message
        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                f"Distance mesurée: {distance_m:.2f} m"
            )

        self.points = []
        self.start_point = None
        self.last_point = None
        self.is_active = False

    # ------------------------------------------------------------------
    # Contrat menu contextuel / ToolManager
    # ------------------------------------------------------------------
    def finish_current(self):
        """Finalise la mesure en cours si 2 points sont disponibles."""
        if not self.is_active or len(self.points) < 2:
            return False
        self.finish_distance()
        return True

    def reset_measure(self):
        """Réinitialise la mesure en cours sans quitter l'outil."""
        self.cleanup_temp_elements()
        self.points = []
        self.start_point = None
        self.last_point = None
        self.is_active = True
        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Mode distance: Cliquez pour le point de départ")
        return True

    def persist_last_measure(self):
        """La mesure est deja persistée lors de finish_distance()."""
        # Pas d'action additionnelle tant que finish_distance crée deja l'entité.
        return False

    def get_point_count(self):
        """Retourne le nombre de points de mesure en cours."""
        return len(self.points)

    def is_drawing_in_progress(self):
        """Indique si une mesure est en cours."""
        return len(self.points) > 0

    def cleanup_temp_elements(self):
        """Nettoie tous les éléments temporaires"""
        # Supprimer les points temporaires
        for item in self.point_items:
            if item in self.canvas.scene.items():
                self.canvas.scene.removeItem(item)
        self.point_items = []

        # Supprimer la ligne temporaire
        if self.temp_line:
            if self.temp_line in self.canvas.scene.items():
                self.canvas.scene.removeItem(self.temp_line)
            self.temp_line = None

        # Supprimer la bulle fantôme
        if hasattr(self, '_seg_helper'):
            self._seg_helper.clear_all()

    def cancel(self):
        """Annule l'outil distance"""
        self.cleanup_temp_elements()
        self.points = []
        self.start_point = None
        self.last_point = None
        if hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Mesure de distance annulée")
        self.is_active = False
