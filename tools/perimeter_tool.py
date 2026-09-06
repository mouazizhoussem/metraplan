# tools/perimeter_tool.py
from PyQt5.QtCore import Qt, QPointF, QLineF
from PyQt5.QtGui import QPen, QColor, QBrush
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem, QDialog
from entities.perimeter_entity import PerimeterEntity, RightAngleMarker
from ui.property_dialog import PropertyDialog
from .segment_label_helper import SegmentLabelHelper
from services.geometry_builder import get_ortho_point, is_too_close
import math


class PerimeterTool:
    def __init__(self, canvas):
        self.canvas = canvas
        self.is_active = False
        self.points = []
        self.temp_lines = []
        self.point_items = []
        self.current_temp_line = None
        self.perimeter_entity = None

        self.start_point = None
        self.last_point = None

        # Gestionnaire d'angles droits pour le dessin en temps réel
        self.right_angle_marker = RightAngleMarker()

        # Stocker les propriétés configurées
        self.perimeter_properties = None

        # Propriétés préconfigurées (pour touche M)
        self.preconfigured_name = None
        self.preconfigured_color = None
        self.preconfigured_show_measure = False
        self.preconfigured_width = 3.0

        # ✅ NOUVEAU: Mode groupe (pour touche M)
        self.group_mode = False
        self.group_id = None
        self.parent_entity = None

        # Annotations des segments (mutualisées)
        self.label_helper = SegmentLabelHelper(canvas)
        self.labels_visible = True

    def key_press(self, event):
        """Raccourci L : afficher/masquer les bulles de mesure pendant le tracé."""
        if self.is_active and event.key() == Qt.Key_L:
            self.labels_visible = not self.labels_visible
            if not self.labels_visible:
                self.label_helper.clear_all()
            else:
                self._rebuild_labels()
            return True
        return False

    # === Helpers d'annotations ===
    def _rebuild_labels(self):
        """Reconstruit uniquement les bulles des segments déjà validés."""
        if not self.labels_visible:
            return
        self._clear_segment_labels()
        if len(self.points) >= 2:
            for idx in range(1, len(self.points)):
                self._add_segment_label(self.points[idx-1], self.points[idx])

    def _clear_preview_labels(self):
        self.label_helper.clear_preview()

    def _clear_segment_labels(self):
        self.label_helper.clear_all()

    def _add_segment_label(self, start_point, end_point):
        self.label_helper.add_segment(start_point, end_point)

    def _update_preview_labels(self, start_point, end_point):
        self.label_helper.set_preview(start_point, end_point)

    def activate(self):
        """Active l'outil de périmètre"""
        # ✅ AMÉLIORATION: Si en mode groupe, ne PAS ouvrir le dialogue
        if self.group_mode and self.parent_entity:

            # ✅ CRITIQUE: Créer perimeter_properties à partir des propriétés préconfigurées
            self.perimeter_properties = {
                'name': self.preconfigured_name,
                'color': self.preconfigured_color,
                'width': self.preconfigured_width if self.preconfigured_width else 3.0,
                'show_measure': self.preconfigured_show_measure if self.preconfigured_show_measure is not None else False,
                'height': 0.0
            }

            # Activer l'outil
            self.is_active = True
            self.points = []
            self.perimeter_entity = None
            self.start_point = None
            self.last_point = None
            self.cleanup_temp_elements()

            if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, "measure_label"):
                count = len(self.parent_entity.child_entities) + 1
                self.canvas.parent_window.measure_label.setText(
                    f"➕ Périmètre {count} pour '{self.preconfigured_name}' - Dessinez"
                )
            return True  # Skip le dialogue

        # Si propriétés préconfigurées SANS mode groupe → réinitialiser
        if self.preconfigured_name and not self.group_mode:
            self.preconfigured_name = None
            self.preconfigured_color = None
            self.preconfigured_show_measure = None
            self.preconfigured_width = None

        # Si les propriétés sont déjà préconfigurées (touche M), ne pas ouvrir le dialogue
        if (hasattr(self, 'preconfigured_name') and self.preconfigured_name and
                hasattr(self, 'preconfigured_color') and self.preconfigured_color):

            # Activer l'outil
            self.is_active = True
            self.points = []
            self.perimeter_entity = None
            self.start_point = None
            self.last_point = None
            self.cleanup_temp_elements()

            if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
                if hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        f"Mode périmètre: '{self.preconfigured_name}' - Cliquez pour ajouter des points, Clic droit pour terminer")

            return True

        # Sinon, ouvrir le dialogue normalement
        parent_window = None
        if hasattr(self.canvas, 'parent_window'):
            parent_window = self.canvas.parent_window

        # Déterminer un nom par défaut
        if hasattr(self.canvas, 'entity_manager') and self.canvas.entity_manager:
            existing_count = sum(1 for e in self.canvas.entity_manager.entities.values()
                                 if hasattr(e, 'entity_type') and e.entity_type == "perimeter")
            default_name = f"Périmètre {existing_count + 1}"
        else:
            default_name = "Périmètre 1"

        dialog = PropertyDialog(
            parent=parent_window,
            entity_type="perimeter",
            default_name=default_name,
            default_color=QColor(0, 0, 255, 200),
            default_show_measure=False,
            default_width=3.0,
            default_height=0.0
        )

        # Afficher le dialogue
        if dialog.exec_() != QDialog.Accepted:
            # L'utilisateur a annulé, ne pas activer l'outil
            if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
                if hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        "Création de périmètre annulée")
            return False

        # Sauvegarder les propriétés configurées
        self.perimeter_properties = dialog.get_properties()

        # Activer l'outil
        self.is_active = True
        self.points = []
        self.perimeter_entity = None
        self.start_point = None
        self.last_point = None
        self.cleanup_temp_elements()

        if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
            if hasattr(self.canvas.parent_window, "measure_label"):
                self.canvas.parent_window.measure_label.setText(
                    f"Mode périmètre: '{self.perimeter_properties['name']}' - Cliquez pour ajouter des points, Clic droit pour terminer")

        return True

    def deactivate(self):
        """Désactive l'outil de périmètre - NE PAS désactiver l'édition ici"""
        self.is_active = False
        # NE PAS nettoyer les éléments ici - laisser les handles visibles
        # Seulement nettoyer les éléments temporaires de création
        self.cleanup_creation_elements_only()

        # ✅ NOUVEAU: Réinitialiser seulement les flags de groupe
        self.group_mode = False
        self.group_id = None
        self.parent_entity = None

        if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
            if hasattr(self.canvas.parent_window, "measure_label"):
                self.canvas.parent_window.measure_label.setText(
                    "Outil périmètre désactivé - Les handles restent actifs")

    def cleanup_creation_elements_only(self):
        """
        Nettoie uniquement les éléments temporaires de création
        (points rouges, lignes temporaires, symboles d'angles droits temporaires)
        SANS désactiver l'édition des handles
        """

        # Nettoyer les points temporaires
        if hasattr(self.canvas, 'scene') and self.canvas.scene:
            for point in self.point_items:
                try:
                    if point.scene() == self.canvas.scene:
                        self.canvas.scene.removeItem(point)
                except Exception as e:
                    pass

            # Nettoyer les lignes temporaires
            for line in self.temp_lines:
                try:
                    if line.scene() == self.canvas.scene:
                        self.canvas.scene.removeItem(line)
                except Exception as e:
                    pass

            # Nettoyer la ligne de prévisualisation
            if self.current_temp_line:
                try:
                    if self.current_temp_line.scene() == self.canvas.scene:
                        self.canvas.scene.removeItem(self.current_temp_line)
                except Exception as e:
                    pass

            # ✅ CORRIGÉ: Utiliser clear_indicators() au lieu de clear_symbols()
            self.right_angle_marker.clear_indicators(self.canvas.scene)
        self._clear_preview_labels()
        self._clear_segment_labels()

        # Réinitialiser les listes
        self.point_items = []
        self.temp_lines = []
        self.current_temp_line = None

    def get_ortho_point(self, current_pos):
        """Retourne le point orthogonal le plus proche (horizontal ou vertical)"""
        if not self.points:
            return current_pos

        try:
            last_point = self.points[-1]
            dx = abs(current_pos.x() - last_point.x())
            dy = abs(current_pos.y() - last_point.y())

            # Si le mouvement est plus horizontal que vertical
            if dx > dy:
                return QPointF(current_pos.x(), last_point.y())
            else:
                return QPointF(last_point.x(), current_pos.y())
        except (AttributeError, IndexError):
            return current_pos

    def mouse_press(self, event, pos):
        """Gère les clics de souris"""
        # CORRIGER: Ignorer le MiddleButton (pan) - il doit être géré par la vue
        if event.button() == Qt.MiddleButton:
            return False  # Laisser le pan gérer cet événement

        if not self.is_active:
            return False

        # CORRIGER: Vérifier que scene existe
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return False

        # VÉRIFIER SI ON CLIQUE SUR UN PÉRIMÈTRE EXISTANT POUR L'ÉDITION
        try:
            items = self.canvas.scene.items(pos)
        except Exception as e:
            return False

        # Ne bloquer le clic sur un périmètre existant que si aucun dessin n'est en cours
        if not self.points:
            for item in items:
                if not hasattr(item, 'data'):
                    continue
                try:
                    if (item.data(0) == "perimeter_entity" and
                            hasattr(self.canvas, "entity_manager")):
                        return False
                except (TypeError, AttributeError):
                    continue

        # Si on est en mode édition, laisser les handles gérer les clics
        if self.perimeter_entity and hasattr(self.perimeter_entity, 'is_editing') and self.perimeter_entity.is_editing:
            return False

        if event.button() == Qt.LeftButton:
            # Utiliser le mode ortho si activé
            ortho_mode = False
            if (hasattr(self.canvas, 'ortho_manager') and
                self.canvas.ortho_manager and
                    hasattr(self.canvas.ortho_manager, 'is_ortho_enabled')):
                try:
                    ortho_mode = self.canvas.ortho_manager.is_ortho_enabled()
                except Exception as e:
                    pass

            if ortho_mode and self.points:
                final_pos = get_ortho_point(self.points[-1], pos)
            else:
                final_pos = pos

            # ✅ NOUVEAU: Vérifier que le point n'est pas trop proche du dernier
            MIN_DISTANCE = 5  # Distance minimale en pixels
            if self.points and is_too_close(self.points[-1], final_pos, MIN_DISTANCE):
                return True  # Ignorer ce clic

            self.points.append(final_pos)
            self.last_point = final_pos

            if not self.start_point:
                self.start_point = final_pos

            try:
                # Dessiner le point
                point_item = QGraphicsEllipseItem(-3, -3, 6, 6)
                point_item.setPos(final_pos)
                point_item.setBrush(QBrush(QColor(255, 0, 0)))
                point_item.setPen(QPen(Qt.NoPen))
                point_item.setData(0, "perimeter_temp_point")
                self.canvas.scene.addItem(point_item)
                self.point_items.append(point_item)

                # Dessiner les lignes entre les points
                if len(self.points) > 1:
                    line = QLineF(self.points[-2], self.points[-1])
                    line_item = QGraphicsLineItem(line)
                    line_item.setPen(QPen(QColor(0, 0, 255), 2))
                    line_item.setData(0, "perimeter_temp_line")
                    self.canvas.scene.addItem(line_item)
                    self.temp_lines.append(line_item)
                    # Recréer toutes les bulles des segments validés
                    self._clear_preview_labels()
                    self._rebuild_labels()

                # ✅ Détecter et afficher les angles droits en temps réel
                if len(self.points) >= 3:
                    # Afficher les symboles pour tous les angles droits détectés
                    self.right_angle_marker.detect_and_display_right_angles(
                        self.points,
                        self.canvas.scene
                    )
                    # ❌ SUPPRIMER:
                    # print(
                    #     f"�� Détection d'angles droits: {len(self.points)} points")

                # Supprimer la ligne temporaire
                if self.current_temp_line:
                    self.canvas.scene.removeItem(self.current_temp_line)
                    self.current_temp_line = None

                return True
            except Exception as e:
                return False

        elif event.button() == Qt.RightButton and len(self.points) >= 2:
            # Clic droit pour terminer le périmètre
            try:
                self.finish_perimeter()
                return True
            except Exception as e:
                return False

        return False

    def mouse_move(self, event, pos):
        """Gère les mouvements de souris avec mode ortho"""
        if not self.is_active or not self.points:
            return False

        # CORRIGER: Vérifier que scene existe
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return False

        # Si on est en mode édition, ne pas interférer
        if self.perimeter_entity and hasattr(self.perimeter_entity, 'is_editing') and self.perimeter_entity.is_editing:
            return False

        # Utiliser le mode ortho si activé
        ortho_mode = False
        if (hasattr(self.canvas, 'ortho_manager') and
            self.canvas.ortho_manager and
                hasattr(self.canvas.ortho_manager, 'is_ortho_enabled')):
            try:
                ortho_mode = self.canvas.ortho_manager.is_ortho_enabled()
            except Exception as e:
                pass

        if ortho_mode:
            final_pos = self.get_ortho_point(pos)
        else:
            final_pos = pos

        try:
            # Mettre à jour la ligne temporaire
            if self.current_temp_line:
                if self.current_temp_line.scene() == self.canvas.scene:
                    self.canvas.scene.removeItem(self.current_temp_line)

            line = QLineF(self.points[-1], final_pos)
            self.current_temp_line = QGraphicsLineItem(line)
            self.current_temp_line.setPen(
                QPen(QColor(0, 255, 0), 2, Qt.DashLine))
            self.current_temp_line.setData(0, "perimeter_temp_line")
            self.canvas.scene.addItem(self.current_temp_line)
            if self.points and self.labels_visible:
                # Bulles des segments validés (inchangés) + prévisualisation unique du segment courant
                self._rebuild_labels()
                self._update_preview_labels(self.points[-1], final_pos)

            # ✅ NOUVEAU: Détection d'angles droits EN TEMPS RÉEL pendant le mouvement
            if len(self.points) >= 2:
                # Créer une liste temporaire avec tous les points + position actuelle de la souris
                temp_points = self.points + [final_pos]

                # Afficher les symboles d'angles droits pour guider l'utilisateur
                self.right_angle_marker.detect_and_display_right_angles(
                    temp_points,
                    self.canvas.scene
                )
                # ❌ SUPPRIMER:
                # print(f"�� Détection d'angles droits: {len(temp_points)} points")

            return True
        except Exception as e:
            return False

    def finish_perimeter(self):
        """Finalise le périmètre (ouvert)"""
        if len(self.points) < 2:
            if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
                if hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        "Erreur: Au moins 2 points requis pour un périmètre")
            self.cleanup_temp_elements()
            return

        # CORRIGER: Vérifier que scene existe
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            self.cleanup_temp_elements()
            return

        try:
            return self._finish_perimeter_refactored()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.cleanup_temp_elements()
            return

        try:
            # ⭐ Utiliser les propriétés déjà configurées
            if not self.perimeter_properties:
                self.cleanup_temp_elements()
                return

            # CORRIGER: Vérifier et valider pixels_per_meter
            pixels_per_meter = getattr(self.canvas, 'pixels_per_meter', 100)
            if not isinstance(pixels_per_meter, (int, float)) or pixels_per_meter <= 0:
                pixels_per_meter = 100

            # Créer l'entité périmètre avec les propriétés configurées
            self.perimeter_entity = PerimeterEntity(
                self.points,
                color=self.perimeter_properties['color'],
                width=self.perimeter_properties['width'],
                pixels_per_meter=pixels_per_meter,
                name=self.perimeter_properties['name']
            )

            # Appliquer la hauteur si spécifiée
            if self.perimeter_properties.get('height', 0.0) > 0:
                self.perimeter_entity.height = self.perimeter_properties['height']

            # ✅ NOUVEAU: Assigner les propriétés de groupe si en mode groupe
            if self.group_mode and self.group_id and self.parent_entity:
                self.perimeter_entity.group_id = self.group_id
                self.perimeter_entity.parent_entity = self.parent_entity
                self.perimeter_entity.is_group_parent = False

                # Hériter du nom de groupe (lisible) depuis le parent
                gname = getattr(self.parent_entity, 'group_name', None) or getattr(self.parent_entity, 'name', None)
                if gname:
                    self.perimeter_entity.group_name = gname
                    if not getattr(self.parent_entity, 'group_name', None):
                        self.parent_entity.group_name = gname

                # Ajouter à la liste des enfants du parent
                if not hasattr(self.parent_entity, 'child_entities'):
                    self.parent_entity.child_entities = []
                self.parent_entity.child_entities.append(self.perimeter_entity)


            # ✅ CORRECTION: Ajouter au gestionnaire AVANT de dessiner (pour recevoir le scale_manager)
            if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
                entity_id = self.canvas.entity_manager.add_entity(
                    self.perimeter_entity)
                if hasattr(self.perimeter_entity, 'entity_id'):
                    self.perimeter_entity.entity_id = entity_id
                
                # ✅ CRITIQUE: Mettre à jour le data(1) maintenant que entity_id existe
                if hasattr(self.perimeter_entity, 'path_item') and self.perimeter_entity.path_item:
                    self.perimeter_entity.path_item.setData(1, entity_id)
            
            # Dessiner l'entité (maintenant qu'elle a le scale_manager)
            self.perimeter_entity.draw(self.canvas.scene)

            # ✅ NOUVEAU: Stocker comme dernière entité créée pour la touche M
            if hasattr(self.canvas, 'last_entity_created'):
                self.canvas.last_entity_created = self.perimeter_entity

            # Sélectionner le périmètre pour afficher les propriétés
            self.perimeter_entity.set_selected(True)
            if hasattr(self.perimeter_entity, 'entityClicked'):
                self.perimeter_entity.entityClicked.emit(self.perimeter_entity)

            # Afficher le message avec le périmètre total
            if hasattr(self.perimeter_entity, 'calculate_perimeter_length'):
                try:
                    perimeter_length = self.perimeter_entity.calculate_perimeter_length()
                    if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
                        if hasattr(self.canvas.parent_window, "measure_label"):
                            # ✅ Message différent si en mode groupe
                            if self.group_mode and self.parent_entity:
                                total_length = self.parent_entity.calculate_total_group_length()
                                count = len(self.parent_entity.child_entities)
                                self.canvas.parent_window.measure_label.setText(
                                    f"✅ Périmètre {count} ajouté à '{self.perimeter_properties['name']}' | Total groupe: {total_length:.2f} m | Clic droit pour le prochain ou ESC pour terminer"
                                )
                            else:
                                self.canvas.parent_window.measure_label.setText(
                                    f"Périmètre '{self.perimeter_properties['name']}' créé: {perimeter_length:.2f} mètres ({len(self.points)} points) - Double-cliquez pour modifier")
                except Exception as e:
                    if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
                        if hasattr(self.canvas.parent_window, "measure_label"):
                            self.canvas.parent_window.measure_label.setText(
                                f"Périmètre créé ({len(self.points)} points)")

            # ✅ NOUVEAU: Mettre à jour la légende et le relevé
            if hasattr(self.canvas, 'update_legend'):
                self.canvas.update_legend()

            if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, 'update_quantities_table'):
                self.canvas.parent_window.update_quantities_table()

            # Nettoyer uniquement les éléments de création
            self.cleanup_creation_elements_only()

            # ✅ NOUVEAU: Réinitialiser l'outil pour permettre un nouveau dessin
            self.points = []
            self.start_point = None
            self.last_point = None
            self.perimeter_entity = None


        except Exception as e:
            import traceback
            traceback.print_exc()
            self.cleanup_temp_elements()

    def _finish_perimeter_refactored(self):
        """Flux principal extrait pour clarifier finish_perimeter."""
        self._ensure_perimeter_properties()
        pixels_per_meter = self._safe_pixels_per_meter()

        self.perimeter_entity = self._create_perimeter_entity(pixels_per_meter)
        
        # Étape 1 : Attacher au groupe si mode groupe actif (touche M)
        attached_to_group = self._attach_group_if_needed(self.perimeter_entity)
        
        # Étape 2 : Si pas encore en groupe, vérifier le groupement automatique par nom
        if not attached_to_group:
            self._auto_group_by_name_if_needed(self.perimeter_entity)
        
        self._add_entity_to_scene_and_manager(self.perimeter_entity)
        self._store_last_created(self.perimeter_entity)
        self._select_and_emit(self.perimeter_entity)
        self._update_measure_labels(self.perimeter_entity)
        self._refresh_ui_tables()
        self._reset_after_finish(self.perimeter_entity)

    def _ensure_perimeter_properties(self):
        """Valide la présence des propriétés du périmètre."""
        if not self.perimeter_properties:
            self.cleanup_temp_elements()
            raise ValueError("Propriétés périmètre manquantes")

    def _safe_pixels_per_meter(self):
        """Retourne un pixels_per_meter valide (fallback 100)."""
        pixels_per_meter = getattr(self.canvas, 'pixels_per_meter', 100)
        if not isinstance(pixels_per_meter, (int, float)) or pixels_per_meter <= 0:
            pixels_per_meter = 100
        return pixels_per_meter

    def _create_perimeter_entity(self, pixels_per_meter):
        """Instancie PerimeterEntity avec les propriétés configurées."""
        perimeter_entity = PerimeterEntity(
            self.points,
            color=self.perimeter_properties['color'],
            width=self.perimeter_properties['width'],
            pixels_per_meter=pixels_per_meter,
            name=self.perimeter_properties['name']
        )
        perimeter_entity.show_measure = self.perimeter_properties.get(
            'show_measure', False)
        if self.perimeter_properties.get('height', 0.0) > 0:
            perimeter_entity.height = self.perimeter_properties['height']
        return perimeter_entity

    def _attach_group_if_needed(self, perimeter_entity):
        """
        Associe l'entité au groupe si le mode groupe est actif (touche M).
        Retourne True si le périmètre a été attaché à un groupe.
        """
        if self.group_mode and self.group_id and self.parent_entity:
            perimeter_entity.group_id = self.group_id
            perimeter_entity.parent_entity = self.parent_entity
            perimeter_entity.is_group_parent = False

            if not hasattr(self.parent_entity, 'child_entities'):
                self.parent_entity.child_entities = []
            self.parent_entity.child_entities.append(perimeter_entity)
            
            # CRITIQUE : Hériter des dimensions du parent (hauteur, épaisseur)
            # Ceci garantit que tous les périmètres d'un groupe calculent le même volume/surface latérale
            perimeter_entity.height = getattr(self.parent_entity, 'height', 0.0)
            perimeter_entity.thickness = getattr(self.parent_entity, 'thickness', 0.0)

            return True
        return False
    
    def _auto_group_by_name_if_needed(self, perimeter_entity):
        """
        CRITIQUE : Groupement automatique par nom (comme pour les surfaces).
        Si un périmètre avec le même nom existe déjà, ils sont automatiquement groupés.
        Ceci est essentiel pour que le copier-coller agrège correctement les résultats.
        """
        # Ne rien faire si déjà attaché à un groupe (mode M)
        if getattr(perimeter_entity, 'parent_entity', None) or getattr(perimeter_entity, 'is_group_parent', False):
            return
        
        # Vérifier les conditions pour le groupement automatique
        perimeter_name = perimeter_entity.name
        if not perimeter_name or not hasattr(self.canvas, 'entity_manager'):
            return
        
        
        # Rechercher un périmètre existant avec le même nom
        all_entities = self.canvas.entity_manager.get_all_entities()
        existing_parent = None
        
        for existing_entity in all_entities:
            is_same_name_perimeter = (
                getattr(existing_entity, 'name', None) == perimeter_name and
                getattr(existing_entity, 'entity_type', None) == 'perimeter' and
                existing_entity is not perimeter_entity
            )
            
            if is_same_name_perimeter:
                # Si déjà un parent de groupe, l'utiliser
                if getattr(existing_entity, 'is_group_parent', False):
                    existing_parent = existing_entity
                    break
                # Sinon, si pas encore dans un groupe, le transformer en parent
                if not getattr(existing_entity, 'parent_entity', None):
                    import uuid
                    existing_entity.is_group_parent = True
                    existing_entity.group_id = f"group_{uuid.uuid4().hex[:8]}"
                    if not hasattr(existing_entity, 'child_entities'):
                        existing_entity.child_entities = []
                    existing_parent = existing_entity
                    break
        
        if existing_parent:
            
            # Attacher au groupe
            perimeter_entity.group_id = existing_parent.group_id
            perimeter_entity.parent_entity = existing_parent
            perimeter_entity.is_group_parent = False
            existing_parent.child_entities.append(perimeter_entity)
            perimeter_entity.show_measure = False
            
            # CRITIQUE : Hériter des dimensions du parent
            perimeter_entity.height = getattr(existing_parent, 'height', 0.0)
            perimeter_entity.thickness = getattr(existing_parent, 'thickness', 0.0)
            
        else:
            # Premier périmètre avec ce nom : il devient immédiatement parent de son propre groupe.
            # Le groupe porte le nom du périmètre dès le départ.
            import uuid as _uuid
            perimeter_entity.is_group_parent = True
            perimeter_entity.group_id = f"group_{_uuid.uuid4().hex[:8]}"
            perimeter_entity.parent_entity = None
            if not hasattr(perimeter_entity, 'child_entities'):
                perimeter_entity.child_entities = []

    def _add_entity_to_scene_and_manager(self, perimeter_entity):
        """Dessine et enregistre l'entité, met à jour les métadonnées."""
        # ✅ CORRECTION: Ajouter au gestionnaire AVANT de dessiner
        if hasattr(self.canvas, "entity_manager") and self.canvas.entity_manager:
            entity_id = self.canvas.entity_manager.add_entity(perimeter_entity)
            if hasattr(perimeter_entity, 'entity_id'):
                perimeter_entity.entity_id = entity_id
            
            if hasattr(perimeter_entity, 'path_item') and perimeter_entity.path_item:
                perimeter_entity.path_item.setData(1, entity_id)
        
        # Dessiner APRÈS (pour avoir le scale_manager)
        perimeter_entity.draw(self.canvas.scene)

    def _store_last_created(self, perimeter_entity):
        """Mémorise le périmètre comme dernier créé (touche M)."""
        if hasattr(self.canvas, 'last_entity_created'):
            self.canvas.last_entity_created = perimeter_entity

    def _select_and_emit(self, perimeter_entity):
        """Sélectionne le périmètre et émet l'événement click pour propriétés."""
        perimeter_entity.set_selected(True)
        if hasattr(perimeter_entity, 'entityClicked'):
            perimeter_entity.entityClicked.emit(perimeter_entity)

    def _update_measure_labels(self, perimeter_entity):
        """Met à jour les labels de mesure (normal ou groupe)."""
        if not hasattr(perimeter_entity, 'calculate_perimeter_length'):
            return
        try:
            perimeter_length = perimeter_entity.calculate_perimeter_length()
            if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
                if hasattr(self.canvas.parent_window, "measure_label"):
                    if self.group_mode and self.parent_entity:
                        total_length = self.parent_entity.calculate_total_group_length()
                        count = len(self.parent_entity.child_entities)
                        self.canvas.parent_window.measure_label.setText(
                            f"✅ Périmètre {count} ajouté à '{self.perimeter_properties['name']}' | Total groupe: {total_length:.2f} m | Clic droit pour le prochain ou ESC pour terminer"
                        )
                    else:
                        self.canvas.parent_window.measure_label.setText(
                            f"Périmètre '{self.perimeter_properties['name']}' créé: {perimeter_length:.2f} mètres ({len(self.points)} points) - Double-cliquez pour modifier")
        except Exception as e:
            if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
                if hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        f"Périmètre créé ({len(self.points)} points)")

    def _refresh_ui_tables(self):
        """Met à jour légende et relevé quantitatif."""
        if hasattr(self.canvas, 'update_legend'):
            self.canvas.update_legend()

        if hasattr(self.canvas, 'parent_window') and hasattr(self.canvas.parent_window, 'update_quantities_table'):
            self.canvas.parent_window.update_quantities_table()

    def _reset_after_finish(self, perimeter_entity):
        """Nettoie les éléments temporaires et réinitialise l'outil."""
        self.cleanup_creation_elements_only()
        self.points = []
        self.start_point = None
        self.last_point = None
        self.perimeter_entity = None
        self.labels_visible = True

    def cleanup_temp_elements(self):
        """Nettoie tous les éléments temporaires (y compris les handles)"""
        # CORRIGER: Vérifier que scene existe
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            # Si pas de scene, juste nettoyer les listes
            self.point_items = []
            self.temp_lines = []
            self.current_temp_line = None
            self.points = []
            self.start_point = None
            self.last_point = None
            return

        # Désactiver l'édition si active
        if self.perimeter_entity and hasattr(self.perimeter_entity, 'is_editing') and self.perimeter_entity.is_editing:
            if hasattr(self.perimeter_entity, 'disable_editing'):
                try:
                    self.perimeter_entity.disable_editing(self.canvas.scene)
                except Exception as e:
                    pass

        # Nettoyer les éléments de création
        self.cleanup_creation_elements_only()
        self._clear_segment_labels()

    def cancel(self):
        """Annule l'opération en cours"""
        try:
            self.cleanup_temp_elements()
            if hasattr(self.canvas, 'parent_window') and self.canvas.parent_window:
                if hasattr(self.canvas.parent_window, "measure_label"):
                    self.canvas.parent_window.measure_label.setText(
                        "Mesure de périmètre annulée")
        except Exception as e:
            pass

    # ------------------------------------------------------------------
    # Contrat menu contextuel / ToolManager
    # ------------------------------------------------------------------
    def _rebuild_creation_graphics_from_points(self):
        """Reconstruit points/lignes temporaires à partir de self.points."""
        if not hasattr(self.canvas, 'scene') or not self.canvas.scene:
            return

        # Nettoyage des éléments temporaires de création uniquement
        self.cleanup_creation_elements_only()

        # Recréer les points rouges
        for p in self.points:
            point_item = QGraphicsEllipseItem(-3, -3, 6, 6)
            point_item.setPos(p)
            point_item.setBrush(QBrush(QColor(255, 0, 0)))
            point_item.setPen(QPen(Qt.NoPen))
            point_item.setData(0, "perimeter_temp_point")
            self.canvas.scene.addItem(point_item)
            self.point_items.append(point_item)

        # Recréer les lignes bleues validées
        for idx in range(1, len(self.points)):
            line = QLineF(self.points[idx - 1], self.points[idx])
            line_item = QGraphicsLineItem(line)
            line_item.setPen(QPen(QColor(0, 0, 255), 2))
            line_item.setData(0, "perimeter_temp_line")
            self.canvas.scene.addItem(line_item)
            self.temp_lines.append(line_item)

        # Recréer les indicateurs visuels
        self._rebuild_labels()
        self._clear_preview_labels()
        if len(self.points) >= 3:
            self.right_angle_marker.detect_and_display_right_angles(
                self.points,
                self.canvas.scene
            )

    def finish_current(self):
        """Finalise le périmètre en cours."""
        if not self.is_active:
            return False
        if len(self.points) < 2:
            return False
        self.finish_perimeter()
        return True

    def undo_last_point(self):
        """Annule le dernier point saisi du périmètre."""
        if not self.is_active or not self.points:
            return False

        self.points.pop()
        self.start_point = self.points[0] if self.points else None
        self.last_point = self.points[-1] if self.points else None

        if not self.points:
            self.cleanup_creation_elements_only()
            return True

        self._rebuild_creation_graphics_from_points()
        return True

    def get_point_count(self):
        """Retourne le nombre de points en cours de création."""
        return len(self.points)

    def is_drawing_in_progress(self):
        """Indique si un dessin de périmètre est en cours."""
        return len(self.points) > 0
