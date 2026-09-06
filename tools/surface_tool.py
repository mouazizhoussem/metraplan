# tools/surface_tool.py
from PyQt5.QtWidgets import (QGraphicsEllipseItem, QGraphicsLineItem,
                             QGraphicsPolygonItem)
from PyQt5.QtCore import Qt, QPointF, QLineF
from PyQt5.QtGui import QPen, QColor, QBrush, QPolygonF

from .base_tool import BaseTool
from entities.perimeter_entity import RightAngleMarker
from entities.polygon_entity import PolygonEntity
from ui.property_dialog import PropertyDialog
from .segment_label_helper import SegmentLabelHelper
from services.geometry_builder import get_ortho_point, is_too_close, build_rectangle_points

import math


class SurfaceTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.points = []
        self.temp_lines = []
        self.point_items = []
        self.temp_polygon = None
        self.current_temp_line = None

        # Attributs pour le mode Ortho
        self.start_point = None
        self.last_point = None

        # Pour le mode édition
        self.editing_entity = None

        # Gestionnaire d'angles droits
        self.right_angle_marker = RightAngleMarker()

        # Mode rectangle (drag avec clic GAUCHE)
        self.rect_start_point = None
        self.rect_current_point = None
        self.is_rect_dragging = False
        self.temp_rect = None

        # Détection du mode (rectangle vs polygone)
        self.mode = None
        self.click_start_pos = None
        self.has_moved = False
        self.drag_threshold = 5

        # Propriétés pré-configurées via le dialogue
        self.preconfigured_name = None
        self.preconfigured_color = None
        self.preconfigured_pattern = None
        self.preconfigured_show_measure = False
        self.preconfigured_extensions = []

        # Mode groupe (pour touche M)
        self.group_mode = False
        self.group_id = None
        self.parent_entity = None

        # Bulles d'annotation des segments (mutualisées)
        self.label_helper = SegmentLabelHelper(canvas)
        self.labels_visible = True

    def key_press(self, event):
        """Raccourci L : afficher/masquer les bulles de mesure pendant le tracé."""
        if self.is_active and event.key() == Qt.Key_L:
            self.labels_visible = not self.labels_visible
            if not self.labels_visible:
                self.label_helper.clear_all()
            else:
                # Reconstruire les bulles des segments déjà validés
                self.label_helper.clear_all()
                if len(self.points) >= 2:
                    for idx in range(1, len(self.points)):
                        self._add_segment_label(self.points[idx - 1], self.points[idx])
            return True
        return False

    def _notify_group_snapshot_update(self, entity):
        """Demande à la fenêtre principale de mettre à jour le snapshot Undo/Redo d'un groupe"""
        if not entity:
            return
        parent_window = getattr(self.canvas, 'parent_window', None)
        if parent_window and hasattr(parent_window, '_refresh_group_snapshot'):
            parent_window._refresh_group_snapshot(entity)

    def _clear_preview_labels(self):
        self.label_helper.clear_preview()

    def _clear_all_segment_labels(self):
        self.label_helper.clear_all()

    def _add_segment_label(self, start_point, end_point):
        if not self.labels_visible:
            return
        self.label_helper.add_segment(start_point, end_point)

    def _update_preview_labels(self, segments):
        if not self.labels_visible:
            return
        self.label_helper.clear_preview()
        for start_point, end_point in segments:
            self.label_helper.add_preview(start_point, end_point, clear=False)

    def activate(self):
        """Active l'outil de surface"""
        super().activate()
        self.points = []
        self.start_point = None
        self.last_point = None

        # Réinitialiser le mode
        self.mode = None
        self.click_start_pos = None
        self.has_moved = False

        self.cleanup_temp_elements()

        # IMPORTANT: Si en mode groupe, ne PAS ouvrir le dialogue ni réinitialiser
        if self.group_mode and self.parent_entity:
            if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                count = len(self.parent_entity.child_entities) + 1
                self.canvas.parent_window.measure_label.setText(
                    f"➕ Surface {count} pour '{self.preconfigured_name}' - Dessinez"
                )
            return True  # Skip le dialogue

        # Si propriétés préconfigurées SANS mode groupe → réinitialiser
        # (cela signifie qu'on réactive l'outil normalement après une utilisation précédente)
        if self.preconfigured_name and not self.group_mode:
            self.preconfigured_name = None
            self.preconfigured_color = None
            self.preconfigured_pattern = None
            self.preconfigured_show_measure = None
            self.preconfigured_extensions = None

        # Ouvrir le dialogue normalement
        parent_window = getattr(self.canvas, 'parent_window', None)

        # Nom par défaut
        if hasattr(self.canvas, 'entity_manager') and self.canvas.entity_manager:
            entity_count = len(self.canvas.entity_manager.entities)
            default_name = f"Surface {entity_count + 1}"
        else:
            default_name = "Surface 1"

        dialog = PropertyDialog(
            parent=parent_window,
            entity_type="surface",
            default_name=default_name,
            default_color=QColor(0, 255, 0, 100),
            default_show_measure=False,
            default_pattern=Qt.SolidPattern
        )

        # Afficher le dialogue
        if dialog.exec_():
            props = dialog.get_properties()

            # Stocker les propriétés
            self.preconfigured_name = props['name']
            self.preconfigured_color = props['color']
            self.preconfigured_pattern = props['fill_pattern']
            self.preconfigured_show_measure = props['show_measure']
            self.preconfigured_extensions = props.get('extensions', [])

            if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                self.canvas.parent_window.measure_label.setText(
                    f"Surface '{self.preconfigured_name}' - Dessinez | ESC pour annuler"
                )

            return True
        else:
            # Dialogue annulé
            return False

    def deactivate(self):
        """Désactive l'outil de surface"""
        super().deactivate()
        self.cleanup_temp_elements()

        # NE PAS réinitialiser les propriétés ici
        # Elles seront réinitialisées au prochain activate() si nécessaire

        # Réinitialiser uniquement le mode groupe lors de la désactivation
        self.group_mode = False
        self.group_id = None
        self.parent_entity = None

        # Déconnecter les signaux et désactiver l'édition en cours
        if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
            for entity in self.canvas.entity_manager.get_entities_by_type('polygon'):
                try:
                    entity.geometryChanged.disconnect()
                except (TypeError, RuntimeError):
                    pass
                except Exception as e:
                    pass

        if self.editing_entity:
            self.finish_editing()

    def get_ortho_point(self, current_pos):
        """Retourne le point orthogonal le plus proche (horizontal ou vertical)"""
        if not self.points:
            return current_pos
        return get_ortho_point(self.points[-1], current_pos)

    def mouse_press(self, event, pos):
        """Gère les clics de souris"""

        if event.button() == Qt.MiddleButton:
            return False

        if self.editing_entity:
            return False

        if not self.is_active:
            return False

        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return False

        # Clic droit : Terminer le polygone
        if event.button() == Qt.RightButton:
            if self.mode == "polygon" and len(self.points) >= 3:
                self.finish_polygon()
                return True
            return False

        # Clic gauche : Démarrer (mode à déterminer)
        if event.button() == Qt.LeftButton:
            # Si aucun mode n'est actif, on commence
            if self.mode is None:
                self.click_start_pos = pos
                self.has_moved = False
                return True

            # Si on est en mode polygone, ajouter un point
            elif self.mode == "polygon":
                ortho_mode = (hasattr(self.canvas, 'ortho_manager') and
                              self.canvas.ortho_manager and
                              self.canvas.ortho_manager.is_ortho_enabled())

                if ortho_mode and self.points:
                    final_pos = self.get_ortho_point(pos)
                else:
                    final_pos = pos

                MIN_DISTANCE = 5
                if self.points and is_too_close(self.points[-1], final_pos, MIN_DISTANCE):
                    return True

                self.points.append(final_pos)
                self.last_point = final_pos

                if not self.start_point:
                    self.start_point = final_pos

                # Dessiner le point
                point_item = QGraphicsEllipseItem(-3, -3, 6, 6)
                point_item.setPos(final_pos)
                point_item.setBrush(QBrush(QColor(255, 0, 0)))
                point_item.setPen(QPen(Qt.NoPen))
                point_item.setData(0, "surface_temp_point")
                self.canvas.scene.addItem(point_item)
                self.point_items.append(point_item)

                # Dessiner les lignes
                if len(self.points) > 1:
                    line = QLineF(self.points[-2], self.points[-1])
                    line_item = QGraphicsLineItem(line)
                    line_item.setPen(QPen(QColor(255, 0, 0), 2))
                    line_item.setData(0, "surface_temp_line")
                    self.canvas.scene.addItem(line_item)
                    self.temp_lines.append(line_item)
                    self._add_segment_label(self.points[-2], self.points[-1])
                    self._clear_preview_labels()

                # Supprimer la ligne temporaire
                if self.current_temp_line:
                    self.canvas.scene.removeItem(self.current_temp_line)
                    self.current_temp_line = None

                # Mettre à jour le polygone temporaire
                self.update_temp_polygon()

                return True

        return False

    def mouse_move(self, event, pos):
        """Gère les mouvements de souris avec mode ortho"""
        if self.editing_entity:
            return False

        if not self.is_active:
            return False

        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return False

        # Détection du mode : drag vs clics
        if self.mode is None and self.click_start_pos:
            distance = ((pos.x() - self.click_start_pos.x())**2 +
                        (pos.y() - self.click_start_pos.y())**2)**0.5

            if distance > self.drag_threshold:
                # C'est un drag : mode rectangle
                self.mode = "rectangle"
                self.is_rect_dragging = True
                self.rect_start_point = self.click_start_pos
                if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        "Mode Rectangle: Glissez pour définir la taille"
                    )

        # Mode rectangle : mettre à jour le rectangle
        if self.mode == "rectangle" and self.is_rect_dragging:
            adjusted_pos = self.apply_ortho_constraint_rectangle(pos)
            self.rect_current_point = adjusted_pos
            self.update_temp_rectangle()
            rectangle_points = build_rectangle_points(
                self.rect_start_point, self.rect_current_point)
            if len(rectangle_points) == 4:
                segments = []
                for idx, point in enumerate(rectangle_points):
                    next_point = rectangle_points[(idx + 1) % 4]
                    segments.append((point, next_point))
                self._update_preview_labels(segments)
            return True

        # Mode polygone : afficher la ligne de suivi
        elif self.mode == "polygon" and self.points:
            ortho_mode = (hasattr(self.canvas, 'ortho_manager') and
                          self.canvas.ortho_manager and
                          self.canvas.ortho_manager.is_ortho_enabled())

            if ortho_mode:
                final_pos = self.get_ortho_point(pos)
            else:
                final_pos = pos

            # Mettre à jour la ligne temporaire
            if self.current_temp_line:
                self.canvas.scene.removeItem(self.current_temp_line)

            line = QLineF(self.points[-1], final_pos)
            self.current_temp_line = QGraphicsLineItem(line)
            self.current_temp_line.setPen(
                QPen(QColor(255, 0, 0), 2, Qt.DashLine))
            self.current_temp_line.setData(0, "surface_temp_line")
            self.canvas.scene.addItem(self.current_temp_line)

            # Détection d'angles droits EN TEMPS RÉEL
            if len(self.points) >= 3:
                temp_points = self.points + [final_pos, self.points[0]]
                self.right_angle_marker.detect_and_display_right_angles(
                    temp_points,
                    self.canvas.scene
                )
            elif len(self.points) >= 2:
                temp_points = self.points + [final_pos]
                self.right_angle_marker.detect_and_display_right_angles(
                    temp_points,
                    self.canvas.scene
                )

            # Mettre à jour le polygone temporaire
            self.update_temp_polygon_with_point(final_pos)
            self._update_preview_labels([(self.points[-1], final_pos)])

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
                # Ajouter le premier point
                self.points.append(self.click_start_pos)
                self.start_point = self.click_start_pos
                self.last_point = self.click_start_pos

                # Dessiner le point
                point_item = QGraphicsEllipseItem(-3, -3, 6, 6)
                point_item.setPos(self.click_start_pos)
                point_item.setBrush(QBrush(QColor(255, 0, 0)))
                point_item.setPen(QPen(Qt.NoPen))
                point_item.setData(0, "surface_temp_point")
                self.canvas.scene.addItem(point_item)
                self.point_items.append(point_item)

                self.click_start_pos = None
                return True

            # Mode rectangle : finaliser
            elif self.mode == "rectangle" and self.is_rect_dragging:
                final_pos = self.apply_ortho_constraint_rectangle(pos)
                self.finish_rectangle(final_pos)
                self.reset_tool()
                return True

        return False

    def mouse_double_click(self, event, pos):
        """Gère les double-clics de souris"""
        if event.button() == Qt.LeftButton:
            # Vérifier que scene existe
            if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
                return False

            # Vérifier si on a cliqué sur une entité existante
            item = self.canvas.scene.itemAt(pos, self.canvas.transform())
            if item and item.data(0) == "polygon_entity":
                # Trouver l'entité correspondante
                entity_id = item.data(1)
                if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                    entity = self.canvas.entity_manager.get_entity(entity_id)
                    if entity and isinstance(entity, PolygonEntity):
                        self.start_editing(entity)
                        return True

            # Sinon, terminer le polygone en cours (si on est en mode création)
            if self.points and len(self.points) >= 3:
                self.finish_polygon()
                return True

        return False

    def draw_temp_lines(self):
        """Dessine les lignes temporaires entre les points"""
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return

        # Supprimer les anciennes lignes temporaires
        for line in self.temp_lines:
            try:
                if line.scene() and line.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(line)
            except (AttributeError, RuntimeError):
                pass
        self.temp_lines = []

        # Dessiner les nouvelles lignes
        for i in range(len(self.points) - 1):
            line = QLineF(self.points[i], self.points[i + 1])
            line_item = QGraphicsLineItem(line)
            line_item.setPen(QPen(QColor(255, 0, 0), 2))
            line_item.setData(0, "surface_temp_line")
            self.canvas.scene.addItem(line_item)
            self.temp_lines.append(line_item)

        if len(self.points) >= 3:
            self.right_angle_marker.detect_and_display_right_angles(
                self.points,
                self.canvas.scene
            )

    def update_temp_polygon(self):
        """Met à jour le polygone temporaire"""
        if len(self.points) < 2:
            return

        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return

        # Supprimer l'ancien polygone temporaire
        if self.temp_polygon:
            try:
                if self.temp_polygon.scene() and self.temp_polygon.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(self.temp_polygon)
            except (AttributeError, RuntimeError):
                pass

        # Créer un nouveau polygone temporaire
        polygon = QPolygonF(self.points)

        self.temp_polygon = QGraphicsPolygonItem(polygon)
        self.temp_polygon.setPen(QPen(Qt.darkGreen, 2))
        self.temp_polygon.setBrush(QBrush(QColor(0, 255, 0, 100)))
        self.temp_polygon.setData(0, "surface_temp_polygon")
        self.canvas.scene.addItem(self.temp_polygon)

    def update_temp_polygon_with_point(self, current_pos):
        """Met à jour le polygone temporaire avec le point courant"""
        if len(self.points) < 1:
            return

        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return

        # Supprimer l'ancien polygone temporaire
        if self.temp_polygon:
            try:
                if self.temp_polygon.scene() and self.temp_polygon.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(self.temp_polygon)
            except (AttributeError, RuntimeError):
                pass

        # Créer un nouveau polygone avec le point courant
        polygon_points = self.points + [current_pos]
        polygon = QPolygonF(polygon_points)

        self.temp_polygon = QGraphicsPolygonItem(polygon)
        self.temp_polygon.setPen(QPen(Qt.darkGreen, 2))
        self.temp_polygon.setBrush(QBrush(QColor(0, 255, 0, 100)))
        self.temp_polygon.setData(0, "surface_temp_polygon")
        self.canvas.scene.addItem(self.temp_polygon)

    def finish_polygon(self):
        """Termine le dessin du polygone et crée l'entité"""
        if len(self.points) < 3:
            self.cleanup_temp_elements()
            return

        try:
            pixels_per_meter = self._safe_pixels_per_meter()
            polygon_entity = self._create_polygon_entity(pixels_per_meter)
            group_parent_for_snapshot = self._handle_grouping(polygon_entity)
            self._add_entity_to_scene_and_manager(
                polygon_entity, group_parent_for_snapshot)
            self._connect_geometry_signal(polygon_entity)
            self._log_area_updates(polygon_entity, group_parent_for_snapshot)
            self._reset_after_creation(polygon_entity)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.cleanup_temp_elements()

    def _safe_pixels_per_meter(self):
        """Retourne un pixels_per_meter valide avec fallback."""
        pixels_per_meter = getattr(self.canvas, 'pixels_per_meter', 100)
        if not isinstance(pixels_per_meter, (int, float)) or pixels_per_meter <= 0:
            pixels_per_meter = 100
        return pixels_per_meter

    def _create_polygon_entity(self, pixels_per_meter):
        """Crée l'entité PolygonEntity et applique les propriétés préconfigurées."""
        polygon_entity = PolygonEntity(self.points, pixels_per_meter)

        # Nom explicite
        if self.preconfigured_name:
            polygon_entity.set_name(self.preconfigured_name)
        else:
            fallback_name = self._compute_fallback_name()
            polygon_entity.set_name(fallback_name)


        if self.preconfigured_color:
            polygon_entity.set_color(self.preconfigured_color)

        polygon_entity.fill_pattern = self.preconfigured_pattern or Qt.SolidPattern
        polygon_entity.show_measure = self.preconfigured_show_measure
        return polygon_entity

    def _compute_fallback_name(self):
        """Construit un nom par défaut basé sur le nombre d'entités existantes."""
        if hasattr(self.canvas, 'entity_manager') and self.canvas.entity_manager:
            entity_count = len(self.canvas.entity_manager.entities)
            return f"Surface {entity_count + 1}"
        return "Surface 1"

    def _handle_grouping(self, polygon_entity):
        """Gère le mode groupe ou le regroupement automatique et retourne le parent utilisé pour le snapshot."""
        group_parent_for_snapshot = None

        if self.group_mode and self.parent_entity:
            polygon_entity.group_id = self.group_id
            polygon_entity.parent_entity = self.parent_entity
            polygon_entity.is_group_parent = False
            self.parent_entity.child_entities.append(polygon_entity)
            group_parent_for_snapshot = self.parent_entity
            polygon_entity.show_measure = False

            # Hériter du nom de groupe (lisible) depuis le parent
            gname = getattr(self.parent_entity, 'group_name', None) or getattr(self.parent_entity, 'name', None)
            if gname:
                polygon_entity.group_name = gname
                if not getattr(self.parent_entity, 'group_name', None):
                    self.parent_entity.group_name = gname

            # CRITIQUE : Hériter des dimensions du parent (hauteur, épaisseur)
            # Ceci garantit que toutes les surfaces d'un groupe calculent le même volume
            polygon_entity.height = getattr(self.parent_entity, 'height', 0.0)
            polygon_entity.thickness = getattr(self.parent_entity, 'thickness', 0.0)

            return group_parent_for_snapshot


        if not (self.preconfigured_name and hasattr(self.canvas, 'entity_manager')):
            polygon_entity.group_id = None
            polygon_entity.parent_entity = None
            polygon_entity.is_group_parent = False
            return group_parent_for_snapshot

        all_entities = self.canvas.entity_manager.get_all_entities()

        existing_parent = None
        for idx, existing_entity in enumerate(all_entities):
            is_same_name_polygon = (
                getattr(existing_entity, 'name', None) == self.preconfigured_name and
                getattr(existing_entity, 'entity_type', None) == 'polygon' and
                existing_entity is not polygon_entity
            )
            if is_same_name_polygon:
                if getattr(existing_entity, 'is_group_parent', False):
                    existing_parent = existing_entity
                    break
                if not getattr(existing_entity, 'parent_entity', None):
                    import uuid
                    existing_entity.is_group_parent = True
                    existing_entity.group_id = f"group_{uuid.uuid4().hex[:8]}"
                    if not hasattr(existing_entity, 'child_entities'):
                        existing_entity.child_entities = []
                    existing_parent = existing_entity
                    self._notify_group_snapshot_update(existing_parent)
                    break

        if existing_parent:

            polygon_entity.group_id = existing_parent.group_id
            polygon_entity.parent_entity = existing_parent
            polygon_entity.is_group_parent = False
            existing_parent.child_entities.append(polygon_entity)
            group_parent_for_snapshot = existing_parent
            polygon_entity.show_measure = False
            
            # CRITIQUE : Hériter des dimensions du parent (hauteur, épaisseur)
            # Ceci garantit que toutes les surfaces d'un groupe calculent le même volume
            # Important pour le groupement automatique par nom
            polygon_entity.height = getattr(existing_parent, 'height', 0.0)
            polygon_entity.thickness = getattr(existing_parent, 'thickness', 0.0)

        else:
            # Première surface avec ce nom : elle devient immédiatement parent de son propre groupe.
            # Le groupe porte le nom de la surface dès le départ.
            import uuid as _uuid
            polygon_entity.is_group_parent = True
            polygon_entity.group_id = f"group_{_uuid.uuid4().hex[:8]}"
            polygon_entity.parent_entity = None
            if not hasattr(polygon_entity, 'child_entities'):
                polygon_entity.child_entities = []
            group_parent_for_snapshot = polygon_entity

        return group_parent_for_snapshot

    def _add_entity_to_scene_and_manager(self, polygon_entity, group_parent_for_snapshot):
        """Dessine l'entité puis l'enregistre dans l'EntityManager avec métadonnées."""
        # ✅ CORRECTION: Ajouter au gestionnaire AVANT de dessiner
        if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
            entity_id = self.canvas.entity_manager.add_entity(polygon_entity)
            polygon_entity.entity_id = entity_id
            
            if getattr(polygon_entity, 'surface_item', None):
                polygon_entity.surface_item.setData(0, "polygon_entity")
                polygon_entity.surface_item.setData(1, entity_id)

            if group_parent_for_snapshot:
                self._notify_group_snapshot_update(group_parent_for_snapshot)
        
        # Dessiner APRÈS (pour avoir le scale_manager)
        polygon_entity.draw(self.canvas.scene)

    def _connect_geometry_signal(self, polygon_entity):
        """Connecte geometryChanged pour propager les modifications."""
        if hasattr(polygon_entity, 'geometryChanged'):
            try:
                polygon_entity.geometryChanged.connect(
                    lambda ent=polygon_entity: self.on_entity_modified(ent))
            except (TypeError, RuntimeError):
                pass

    def _log_area_updates(self, polygon_entity, group_parent_for_snapshot):
        """Trace les aires, met à jour l'UI et les regroupements."""
        area_m2 = polygon_entity.calculate_area()

        if self.group_mode and self.parent_entity:
            total_area = self.parent_entity.calculate_total_group_area()
            if hasattr(self.parent_entity, 'draw_text') and hasattr(self.parent_entity, 'scene_ref'):
                self.parent_entity.draw_text(self.parent_entity.scene_ref)
        else:
            pass

        if hasattr(self.canvas, 'update_legend'):
            self.canvas.update_legend()

        if hasattr(self.canvas, "parent_window") and self.canvas.parent_window:
            if hasattr(self.canvas.parent_window, "update_quantities_table"):
                self.canvas.parent_window.update_quantities_table()
            if hasattr(self.canvas.parent_window, 'update_properties_entities_list'):
                self.canvas.parent_window.update_properties_entities_list()

        if self.group_mode and self.parent_entity and hasattr(self.parent_entity, 'geometryChanged'):
            self.parent_entity.geometryChanged.emit()

    def _reset_after_creation(self, polygon_entity):
        """Réinitialise l'état de l'outil après création et nettoie les éléments temporaires."""
        self.points = []
        self.start_point = None
        self.last_point = None
        self.mode = None
        self.labels_visible = True
        self.cleanup_temp_elements()

    def start_editing(self, entity):
        """Démarre l'édition d'une entité"""
        try:
            if self.editing_entity:
                self.finish_editing()

            self.editing_entity = entity

            # Vérifier que scene existe
            if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
                return

            # Essayer d'utiliser SurfaceItem pour l'édition
            if hasattr(entity, 'enable_editing'):
                entity.enable_editing(self.canvas.scene)
            else:
                # Fallback à la méthode traditionnelle
                if hasattr(entity, 'enable_editing_fallback'):
                    entity.enable_editing_fallback(self.canvas.scene)

            # Connecter le signal de modification avec lambda pour passer l'entité explicitement
            try:
                if hasattr(entity, 'geometryChanged'):
                    # Utiliser lambda pour passer explicitement l'entité au callback
                    entity.geometryChanged.connect(
                        lambda: self.on_entity_modified(entity))
            except (TypeError, RuntimeError) as e:
                pass
            except Exception as e:
                pass

            if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                if hasattr(entity, 'is_perimeter') and entity.is_perimeter:
                    self.canvas.parent_window.measure_label.setText(
                        "Mode édition: Déplacez les points pour modifier le périmètre")
                else:
                    self.canvas.parent_window.measure_label.setText(
                        "Mode édition: Déplacez les points pour modifier la surface")

        except Exception as e:
            import traceback
            traceback.print_exc()

    def finish_editing(self):
        """Termine l'édition en cours"""
        if self.editing_entity:
            # Déconnecter le signal de modification
            try:
                if hasattr(self.editing_entity, 'geometryChanged'):
                    # Essayer de déconnecter tous les slots (plus sûr)
                    self.editing_entity.geometryChanged.disconnect()
            except (TypeError, RuntimeError):
                # Signal non connecté ou déjà déconnecté
                pass
            except Exception as e:
                pass

            # Désactiver l'édition
            if hasattr(self.canvas, 'scene') and self.canvas.scene:
                if hasattr(self.editing_entity, 'disable_editing'):
                    try:
                        self.editing_entity.disable_editing(self.canvas.scene)
                    except Exception as e:
                        pass

            self.editing_entity = None

            if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                self.canvas.parent_window.measure_label.setText(
                    "Édition terminée. Cliquez pour définir les points de la surface.")

    def on_entity_modified(self, entity=None):
        """Callback lorsqu'une entité est modifiée"""
        # Si entity n'est pas fourni en paramètre, utiliser l'entité en cours d'édition
        if entity is None:
            entity = self.editing_entity

        if not entity:
            return

        # Mettre à jour l'affichage des mesures
        if hasattr(entity, 'draw_text') and hasattr(entity, 'scene_ref'):
            try:
                entity.draw_text(entity.scene_ref)
            except Exception as e:
                pass

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            try:
                if hasattr(entity, 'is_perimeter') and entity.is_perimeter:
                    measure_text = entity.get_perimeter_text() if hasattr(
                        entity, 'get_perimeter_text') else "N/A"
                    self.canvas.parent_window.measure_label.setText(
                        f"Périmètre modifié: {measure_text}")
                else:
                    measure_text = entity.get_area_text() if hasattr(
                        entity, 'get_area_text') else "N/A"
                    self.canvas.parent_window.measure_label.setText(
                        f"Surface modifiée: {measure_text}")
            except Exception as e:
                pass

        # Notifier le entity_manager de la modification
        if hasattr(entity, 'notify_entity_manager'):
            try:
                entity.notify_entity_manager()
            except Exception as e:
                pass

    def cleanup_temp_elements(self):
        """Nettoie tous les éléments temporaires"""
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return

        # Nettoyer les points
        for point in self.point_items:
            try:
                if point.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(point)
            except (AttributeError, RuntimeError):
                pass

        # Nettoyer les lignes
        for line in self.temp_lines:
            try:
                if line.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(line)
            except (AttributeError, RuntimeError):
                pass

        # Nettoyer le polygone temporaire
        if self.temp_polygon:
            try:
                if self.temp_polygon.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(self.temp_polygon)
            except (AttributeError, RuntimeError):
                pass

        # Nettoyer la ligne de prévisualisation
        if self.current_temp_line:
            try:
                if self.current_temp_line.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(self.current_temp_line)
            except (AttributeError, RuntimeError):
                pass

        # ✅ CORRIGÉ: Utiliser clear_indicators() au lieu de clear_symbols()
        self.right_angle_marker.clear_indicators(self.canvas.scene)
        self._clear_all_segment_labels()

        # Réinitialiser les listes
        self.point_items = []
        self.temp_lines = []
        self.temp_polygon = None
        self.current_temp_line = None

        # ✅ NOUVEAU: Nettoyer aussi le rectangle
        self.cleanup_rectangle()

    def cancel(self):
        """Annule l'opération en cours"""
        # Si on est en mode édition, terminer l'édition
        if self.editing_entity:
            self.finish_editing()

        # Annuler la création en cours
        self.cleanup_temp_elements()

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Mesure de surface annulée")

    # ------------------------------------------------------------------
    # Contrat menu contextuel / ToolManager
    # ------------------------------------------------------------------
    def finish_current(self):
        """Finalise la création en cours selon le mode actif."""
        if not self.is_active:
            return False

        if self.mode == "polygon" and len(self.points) >= 3:
            self.finish_polygon()
            return True

        if self.mode == "rectangle" and self.is_rect_dragging and self.rect_current_point:
            self.finish_rectangle(self.rect_current_point)
            self.reset_tool()
            return True

        return False

    def undo_last_point(self):
        """Annule le dernier point en mode polygone."""
        if not self.is_active:
            return False

        # Mode rectangle: annulation douce de la prévisualisation en cours.
        if self.mode == "rectangle":
            self.reset_tool()
            return True

        if self.mode != "polygon" or not self.points:
            return False

        self.points.pop()
        self.start_point = self.points[0] if self.points else None
        self.last_point = self.points[-1] if self.points else None

        # Recréer proprement la géométrie temporaire depuis la liste restante.
        self.cleanup_temp_elements()
        if not self.points:
            self.mode = None
            return True

        for p in self.points:
            point_item = QGraphicsEllipseItem(-3, -3, 6, 6)
            point_item.setPos(p)
            point_item.setBrush(QBrush(QColor(255, 0, 0)))
            point_item.setPen(QPen(Qt.NoPen))
            point_item.setData(0, "surface_temp_point")
            self.canvas.scene.addItem(point_item)
            self.point_items.append(point_item)

        self.draw_temp_lines()
        if len(self.points) >= 2:
            self.update_temp_polygon()
        return True

    def toggle_drawing_mode(self):
        """Bascule entre rectangle et polygone avec reset sécurisé de l'état temporaire."""
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
        """Retourne un nombre de points cohérent avec le mode de dessin actif."""
        if self.mode == "polygon":
            return len(self.points)
        if self.mode == "rectangle" and (self.is_rect_dragging or self.rect_start_point):
            return 1
        return len(self.points)

    def is_drawing_in_progress(self):
        """Indique si un dessin est en cours (points, drag ou clic initial)."""
        return bool(
            self.get_point_count() > 0 or
            self.is_rect_dragging or
            self.click_start_pos is not None
        )

    def apply_ortho_constraint_rectangle(self, pos):
        """Contrainte ortho pour rectangle : force un carré si ortho activé"""
        if not self.rect_start_point:
            return pos

        # Vérifier si le mode ortho est activé
        ortho_enabled = (hasattr(self.canvas, 'ortho_manager') and
                         self.canvas.ortho_manager and
                         self.canvas.ortho_manager.is_ortho_enabled())

        if not ortho_enabled:
            # Mode normal : rectangle libre
            return pos

        # Mode ortho : forcer un carré
        dx = pos.x() - self.rect_start_point.x()
        dy = pos.y() - self.rect_start_point.y()
        size = min(abs(dx), abs(dy))

        adjusted_dx = size if dx >= 0 else -size
        adjusted_dy = size if dy >= 0 else -size

        return QPointF(
            self.rect_start_point.x() + adjusted_dx,
            self.rect_start_point.y() + adjusted_dy
        )

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
            QPen(QColor(0, 255, 0), 2, Qt.DashLine),
            QBrush(QColor(0, 255, 0, 30))
        )
        self.temp_rect.setZValue(1000)

    def finish_rectangle(self, end_pos):
        """Finalise le rectangle et crée la surface"""
        if not self.rect_start_point:
            return

        x1 = min(self.rect_start_point.x(), end_pos.x())
        y1 = min(self.rect_start_point.y(), end_pos.y())
        x2 = max(self.rect_start_point.x(), end_pos.x())
        y2 = max(self.rect_start_point.y(), end_pos.y())

        # Vérifier taille minimale
        if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
            self.cleanup_rectangle()
            return

        rectangle_points = build_rectangle_points(
            self.rect_start_point, end_pos)


        # Utiliser la méthode finish_polygon existante avec ces points
        self.points = rectangle_points
        self.finish_polygon()

        # Nettoyer le mode rectangle
        self.cleanup_rectangle()

    def cleanup_rectangle(self):
        """Nettoie les éléments du mode rectangle"""
        if self.temp_rect and self.temp_rect.scene():
            self.canvas.scene.removeItem(self.temp_rect)

        self.temp_rect = None
        self.rect_start_point = None
        self.rect_current_point = None
        self.is_rect_dragging = False
        self.right_button_pressed_pos = None
        self._clear_preview_labels()

    def reset_tool(self):
        """Réinitialise l'outil pour une nouvelle forme"""
        self.cleanup_temp_elements()
        self.mode = None
        self.rect_start_point = None
        self.rect_current_point = None
        self.is_rect_dragging = False
        self.click_start_pos = None
        self.has_moved = False

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
            self.canvas.parent_window.measure_label.setText(
                "Surface: Drag = Rectangle | Clics = Polygone | Clic droit = Terminer"
            )
