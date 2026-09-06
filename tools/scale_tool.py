# tools/scale_tool.py
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtGui import QColor, QPen, QBrush, QCursor
from .base_tool import BaseTool
from .segment_label_helper import SegmentLabelHelper
from entities.line_entity import LineEntity


class ScaleTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.points = []
        self.temp_line = None
        self.temp_line_entity = None
        self.point_items = []
        self._initialized = False  # NOUVEAU: Flag pour suivre l'initialisation

        # NOUVEAU: Attributs pour le mode Ortho
        self.start_point = None
        self.last_point = None

        # Bulle fantôme pendant le tracé
        self._seg_helper = SegmentLabelHelper(canvas, text_color="#1F6B2C")

    def get_ortho_point(self, current_pos):
        """Retourne le point orthogonal le plus proche (horizontal ou vertical)"""
        if not self.points or len(self.points) < 1:
            return current_pos

        last_point = self.points[-1]
        dx = abs(current_pos.x() - last_point.x())
        dy = abs(current_pos.y() - last_point.y())

        # Si le mouvement est plus horizontal que vertical
        if dx > dy:
            return QPointF(current_pos.x(), last_point.y())
        else:
            return QPointF(last_point.x(), current_pos.y())

    def activate(self):
        """Active l'outil échelle"""
        super().activate()

        # CORRECTION: Vérifier que la scène est disponible
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            self._initialized = False
            return

        # CORRECTION CRITIQUE: S'assurer que le suivi de la souris est activé
        if hasattr(self.canvas, 'setMouseTracking'):
            self.canvas.setMouseTracking(True)
        if hasattr(self.canvas, 'viewport') and hasattr(self.canvas.viewport(), 'setMouseTracking'):
            self.canvas.viewport().setMouseTracking(True)

        # CORRECTION: Mettre à jour le curseur pour indiquer que l'outil est actif
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.CrossCursor)

        # CORRECTION: S'assurer que la vue est à jour
        if hasattr(self.canvas, 'update'):
            self.canvas.update()

        self.points = []
        self.start_point = None
        self.last_point = None
        self._seg_helper = SegmentLabelHelper(self.canvas, text_color="#1F6B2C")
        self.cleanup_temp_elements()
        self._initialized = True  # NOUVEAU: Marquer comme initialisé

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "📐 Calibrage — Tracez sur la cote la plus longue connue du plan "
                "(façade, mur principal…) — Cliquez pour le 1er point")

    def mouse_press(self, event, pos):
        """Gère les clics pour définir l'échelle"""
        if not self.is_active:
            return False

        # CORRECTION: Vérifier que la scène est disponible
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return False

        if event.button() == Qt.LeftButton:
            self.points.append(QPointF(pos))

            # Dessiner un point temporaire
            try:
                point_item = self.canvas.scene.addEllipse(
                    pos.x() - 3, pos.y() - 3, 6, 6,
                    QPen(Qt.green, 2), QBrush(QColor(0, 255, 0))
                )
                point_item.setData(0, "scale_temp_point")
                self.point_items.append(point_item)

                # CORRECTION: Forcer la mise à jour de la vue après ajout du point
                if hasattr(self.canvas, 'update'):
                    self.canvas.update()
            except Exception as e:
                return False

            if len(self.points) == 1:
                if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        "Cliquez pour le deuxième point")

                # CORRECTION CRITIQUE: Forcer l'activation du suivi de la souris après le premier clic
                if hasattr(self.canvas, 'setMouseTracking'):
                    self.canvas.setMouseTracking(True)
                if hasattr(self.canvas, 'viewport') and hasattr(self.canvas.viewport(), 'setMouseTracking'):
                    self.canvas.viewport().setMouseTracking(True)

                # CORRECTION: Créer immédiatement une ligne temporaire initiale
                # pour que la ligne fantôme soit visible dès le premier mouvement
                # Obtenir la position actuelle de la souris
                try:
                    if hasattr(self.canvas, 'mapFromGlobal') and hasattr(self.canvas, 'mapToScene'):
                        cursor_pos = self.canvas.mapToScene(
                            self.canvas.mapFromGlobal(self.canvas.cursor().pos()))
                        # Créer une ligne initiale de 1 pixel pour forcer l'affichage
                        self.temp_line = self.canvas.scene.addLine(
                            self.points[0].x(), self.points[0].y(),
                            cursor_pos.x(), cursor_pos.y(),
                            QPen(Qt.green, 2, Qt.DashLine)
                        )
                        self.temp_line.setData(0, "scale_temp_line")
                        if hasattr(self.canvas, 'update'):
                            self.canvas.update()
                except Exception as e:
                    pass

                return True
            elif len(self.points) == 2:
                self.finish_scale()
                return True

        return False

    def mouse_move(self, event, pos):
        """Met à jour la ligne temporaire pendant le mouvement"""
        # CORRECTION: Vérifier l'initialisation et l'état actif
        if not self.is_active or not self._initialized:
            return False

        # CORRECTION: La ligne fantôme ne doit s'afficher qu'après le premier clic
        if len(self.points) != 1:
            return False

        # CORRECTION: Vérifier que la scène est disponible
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return False

        # CORRECTION: Utiliser le mode ortho si activé
        ortho_mode = False
        if (hasattr(self.canvas, 'ortho_manager') and
                self.canvas.ortho_manager and
                hasattr(self.canvas.ortho_manager, 'is_ortho_enabled')):
            try:
                ortho_mode = self.canvas.ortho_manager.is_ortho_enabled()
            except Exception as e:
                pass

        # CORRECTION: Appliquer le mode ortho pour obtenir la position finale
        if ortho_mode:
            final_pos = self.get_ortho_point(pos)
        else:
            final_pos = pos

        # CORRECTION: Supprimer l'ancienne ligne temporaire de manière plus robuste
        if self.temp_line:
            try:
                # Vérifier que la ligne appartient à la scène avant de la supprimer
                if self.temp_line.scene() and self.temp_line.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(self.temp_line)
                    self.temp_line = None
            except (AttributeError, RuntimeError):
                # L'item a déjà été supprimé ou n'appartient plus à la scène
                self.temp_line = None
            except Exception as e:
                self.temp_line = None

        # CORRECTION: Vérifier que le premier point est valide
        if not self.points or len(self.points) < 1:
            return False

        # CORRECTION: Créer une nouvelle ligne temporaire avec la position ortho si activée
        try:
            # Utiliser la position ortho si le mode est activé
            self.temp_line = self.canvas.scene.addLine(
                self.points[0].x(), self.points[0].y(),
                final_pos.x(), final_pos.y(),
                QPen(Qt.green, 2, Qt.DashLine)
            )
            self.temp_line.setData(0, "scale_temp_line")

            # CORRECTION: S'assurer que la ligne est visible et au-dessus
            # Mettre au-dessus des autres éléments
            self.temp_line.setZValue(1000)

            # CORRECTION CRITIQUE: Forcer la mise à jour de la vue après création de la ligne
            # pour s'assurer qu'elle est visible immédiatement
            if hasattr(self.canvas, 'update'):
                self.canvas.update()
            elif hasattr(self.canvas, 'viewport') and hasattr(self.canvas.viewport(), 'update'):
                self.canvas.viewport().update()

            # CORRECTION: Forcer le rafraîchissement de la scène
            if hasattr(self.canvas.scene, 'update'):
                self.canvas.scene.update()

        except Exception as e:
            import traceback
            traceback.print_exc()
            return False

        # Calculer et afficher le feedback qualité en temps réel
        dx = final_pos.x() - self.points[0].x()
        dy = final_pos.y() - self.points[0].y()
        distance_px = (dx**2 + dy**2) ** 0.5

        if distance_px < 200:
            qualite = "📏 Ligne courte — tracez plus long pour plus de précision"
        elif distance_px < 500:
            qualite = "📏 Longueur acceptable"
        else:
            qualite = "📏 ✅ Bonne référence"

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                f"{qualite} — cliquez pour le 2e point"
            )

        # CORRECTION: Retourner True pour indiquer que l'événement a été traité
        # Cela garantit que la ligne est mise à jour correctement
        return True

    def finish_scale(self):
        """Demande la distance réelle et définit l'échelle"""
        if len(self.points) < 2:
            return

        # CORRECTION: Vérifier que la scène est disponible
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            self.points = []
            return

        # Nettoyer les éléments temporaires
        self.cleanup_temp_elements()

        # Calculer la distance en pixels (nécessaire pour le calcul mais non affiché)
        dx = self.points[1].x() - self.points[0].x()
        dy = self.points[1].y() - self.points[0].y()
        distance_px = (dx**2 + dy**2) ** 0.5

        # CORRECTION: Message simplifié sans afficher les pixels
        real_distance, ok = QInputDialog.getDouble(
            self.canvas.parent_window if hasattr(
                self.canvas, 'parent_window') else None,
            "Définir l'échelle",
            "Quelle est la distance réelle entre les deux points sélectionnés ?\n(En mètres)",
            1.0, 0.01, 1000.0, 2
        )

        if ok and real_distance > 0:
            # Calculer l'échelle métrique (pixels par mètre)
            pixels_per_meter = distance_px / real_distance

            # ✅ CORRECTION : Mettre à jour l'échelle métrique du canvas
            # Note : scale_manager gère l'échelle VISUELLE, pas l'échelle MÉTRIQUE
            self.canvas.pixels_per_meter = pixels_per_meter

            # Créer la ligne d'échelle sans boîte de dialogue de nommage
            try:
                scale_entity = LineEntity(
                    self.points[0],
                    self.points[1],
                    color=QColor(0, 200, 0),
                    width=4,
                    pixels_per_meter=pixels_per_meter,
                    name="Échelle de référence"
                )
                scale_entity.show_measure = True
                scale_entity.is_scale_reference = True  # Marqueur pour menu contextuel

                # Propager la nouvelle échelle à toutes les entités existantes
                if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                    for ent in self.canvas.entity_manager.get_all_entities():
                        ent.pixels_per_meter = pixels_per_meter
                        # Ne redessiner que les entités avec une scène active
                        ent_scene = getattr(ent, "scene_ref", None)
                        if ent_scene and hasattr(ent, "draw"):
                            try:
                                ent.draw(ent_scene)
                            except Exception:
                                pass

                scale_entity.draw(self.canvas.scene)

                # Ajouter l'entité au gestionnaire
                if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                    entity_id = self.canvas.entity_manager.add_entity(
                        scale_entity)
                    scale_entity.entity_id = entity_id

                # Mettre à jour l'échelle dans tous les outils
                self.update_tools_scale(pixels_per_meter)

                # Marquer la page courante comme calibrée
                mw = getattr(self.canvas, "parent_window", None)
                if mw and hasattr(mw, "current_pdf_page_index"):
                    page = (mw._get_managed_page(mw.current_pdf_page_index)
                            if hasattr(mw, "_get_managed_page") else None)
                    if page is not None:
                        page.scale_calibrated = True

                # Rafraîchir tous les panneaux (Pages & Mesures, propriétés, légende)
                if mw and hasattr(mw, "_refresh_all_panels_after_undo_redo"):
                    mw._refresh_all_panels_after_undo_redo()

                # Activer tous les outils de mesure maintenant que l'échelle est définie
                if mw and hasattr(mw, "_update_tools_for_scale_state"):
                    mw._update_tools_for_scale_state(True)
                mw2 = getattr(self.canvas, "parent_window", None)
                if mw2 and hasattr(mw2, "statusBar"):
                    mw2.statusBar().showMessage(
                        "⚠ La précision des mesures dépend de la précision "
                        "du calage de l'échelle. Vérifiez le segment de référence.",
                        6000
                    )
            except Exception as e:
                if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        f"Erreur lors de la définition de l'échelle: {e}")
        else:
            if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                self.canvas.parent_window.measure_label.setText(
                    "Définition d'échelle annulée")

        self.points = []
        if hasattr(self.canvas, 'mode'):
            self.canvas.mode = "idle"
        self.is_active = False
        self._initialized = False

    def update_tools_scale(self, pixels_per_meter):
        """Met à jour l'échelle dans tous les outils"""
        # CORRECTION : Mettre à jour l'échelle globale du canvas d'abord
        self.canvas.pixels_per_meter = pixels_per_meter
        if hasattr(self.canvas, 'scale_factor'):
            self.canvas.scale_factor = pixels_per_meter

        # Mettre à jour tous les outils de mesure
        tools_to_update = [
            'surface_tool', 'distance_tool', 'perimeter_tool',
            'angle_tool', 'measure_tool'  # Ajouter tous les outils pertinents
        ]

        for tool_name in tools_to_update:
            if hasattr(self.canvas, tool_name) and getattr(self.canvas, tool_name):
                tool = getattr(self.canvas, tool_name)
                if hasattr(tool, 'pixels_per_meter'):
                    tool.pixels_per_meter = pixels_per_meter
                # CORRECTION : Forcer la mise à jour de l'affichage si nécessaire
                if hasattr(tool, 'update_display'):
                    tool.update_display()

    # ------------------------------------------------------------------
    # Contrat menu contextuel / ToolManager
    # ------------------------------------------------------------------
    def finish_current(self):
        """Finalise la definition d'echelle si les 2 points existent."""
        if not self.is_active or len(self.points) < 2:
            return False
        self.finish_scale()
        return True

    def reset_measure(self):
        """Reinitialise la ligne d'echelle en cours sans quitter l'outil."""
        self.cleanup_temp_elements()
        self.points = []
        self.start_point = None
        self.last_point = None
        self._initialized = True
        self.is_active = True
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.CrossCursor)
        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Tracez une ligne de reference pour l'echelle - Cliquez pour le premier point")
        return True

    def get_point_count(self):
        """Retourne le nombre de points de reference deja poses."""
        return len(self.points)

    def is_drawing_in_progress(self):
        """Indique si la definition d'echelle est en cours."""
        return len(self.points) > 0

    def cleanup_temp_elements(self):
        """Nettoie tous les éléments temporaires"""
        # CORRECTION: Vérifier que la scène est disponible avant de nettoyer
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            # Si pas de scène, juste vider les listes
            self.point_items = []
            self.temp_line = None
            return

        # Supprimer les points temporaires
        for item in self.point_items:
            try:
                if item.scene() and item.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(item)
            except (AttributeError, RuntimeError):
                pass
            except Exception as e:
                pass
        self.point_items = []

        # Supprimer la ligne temporaire
        if self.temp_line:
            try:
                if self.temp_line.scene() and self.temp_line.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(self.temp_line)
            except (AttributeError, RuntimeError):
                pass
            except Exception as e:
                pass
            self.temp_line = None

        # Supprimer la bulle fantôme
        if hasattr(self, '_seg_helper'):
            self._seg_helper.clear_all()

    def cancel(self):
        """Annule l'outil échelle"""
        self.cleanup_temp_elements()
        self.points = []
        self._initialized = False  # NOUVEAU: Réinitialiser le flag

        # CORRECTION: Remettre le curseur par défaut
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.ArrowCursor)

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Définition d'échelle annulée")
        super().cancel()

    def deactivate(self):
        """Désactive l'outil échelle"""
        self.cleanup_temp_elements()
        self.points = []
        self._initialized = False  # NOUVEAU: Réinitialiser le flag

        # CORRECTION: Remettre le curseur par défaut
        if hasattr(self.canvas, 'setCursor'):
            self.canvas.setCursor(Qt.ArrowCursor)

        super().deactivate()
