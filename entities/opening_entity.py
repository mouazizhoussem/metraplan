# entities/opening_entity.py
"""
Entité représentant une ouverture à déduire d'une surface
"""
from PyQt5.QtCore import Qt, QPointF, QRectF, QEvent
from PyQt5.QtGui import QPen, QColor, QBrush, QPolygonF, QFont, QPainterPath
from PyQt5.QtWidgets import QGraphicsPolygonItem, QGraphicsTextItem, QGraphicsRectItem
from .base_entity import BaseEntity
from .calculations import polygon_area
from typing import Optional


class AnchorPoint(QGraphicsRectItem):
    """Point d'ancrage pour l'édition d'ouvertures - VERSION UNIFIÉE"""

    def __init__(self, x, y, index, parent_entity):
        # Tailles de base
        base_visible_size = 16
        base_click_size = 40
        base_pen_width = 3
        
        # ✅ NOUVEAU: Tailles scalées
        if hasattr(parent_entity, 'scale_manager') and parent_entity.scale_manager:
            self.visible_size = parent_entity.scale_manager.scale_size(base_visible_size)
            self.click_size = parent_entity.scale_manager.scale_size(base_click_size)
            pen_width = parent_entity.scale_manager.scale_pen_width(base_pen_width)
        else:
            self.visible_size = base_visible_size
            self.click_size = base_click_size
            pen_width = base_pen_width

        # Le rectangle de base (pour le dessin) est le petit carré visible
        super().__init__(-self.visible_size/2, -self.visible_size/2,
                         self.visible_size, self.visible_size)
        self.setPos(x, y)
        self.index = index
        self.parent_entity = parent_entity

        # Style carré noir avec contour blanc épais (scalé)
        self.setBrush(QColor(0, 0, 0))
        self.setPen(QPen(QColor(255, 255, 255), pen_width))

        # ✅ CORRECTION: TOUS les flags nécessaires (comme PolygonEntity)
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemIsFocusable, True)
        self.setFlag(QGraphicsRectItem.ItemIgnoresTransformations, False)
        self.setFlag(QGraphicsRectItem.ItemStacksBehindParent, False)

        # Z-value ULTRA-ÉLEVÉ pour être au premier plan
        self.setZValue(20000)  # ✅ Z extrêmement élevé pour être devant TOUT
        self.setCursor(Qt.SizeAllCursor)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFiltersChildEvents(False)


    def shape(self):
        """Zone cliquable ÉLARGIE"""
        path = QPainterPath()
        extended_rect = QRectF(
            -self.click_size/2,
            -self.click_size/2,
            self.click_size,
            self.click_size
        )
        path.addRect(extended_rect)
        return path

    def boundingRect(self):
        """Zone de détection élargie - DOIT être la grande zone !"""
        return QRectF(
            -self.click_size/2,
            -self.click_size/2,
            self.click_size,
            self.click_size
        )

    def paint(self, painter, option, widget=None):
        """Dessiner le petit carré visible"""
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRect(self.rect())

    def contains(self, point):
        """Vérifie si le point est dans la zone cliquable élargie"""
        extended_rect = QRectF(
            -self.click_size/2,
            -self.click_size/2,
            self.click_size,
            self.click_size
        )
        is_inside = extended_rect.contains(point)
        # Log supprimé : trop verbeux lors du déplacement
        return is_inside

    def itemChange(self, change, value):
        """Appelé quand le point est déplacé"""
        # Debug TOUS les types de changements
        change_types = {
            0: "ItemEnabledChange",
            1: "ItemEnabledHasChanged",
            2: "ItemMatrixChange",
            3: "ItemVisibleChange",
            4: "ItemVisibleHasChanged",
            5: "ItemParentChange",
            6: "ItemParentHasChanged",
            7: "ItemChildAddedChange",
            8: "ItemChildRemovedChange",
            9: "ItemTransformChange",
            10: "ItemTransformHasChanged",
            11: "ItemPositionChange",
            12: "ItemPositionHasChanged",
            13: "ItemSceneChange",
            14: "ItemSceneHasChanged",
            16: "ItemCursorChange",
            17: "ItemCursorHasChanged",
            18: "ItemToolTipChange",
            19: "ItemToolTipHasChanged",
            20: "ItemFlagsChange",
            21: "ItemFlagsHaveChanged",
            22: "ItemZValueChange",
            23: "ItemZValueHasChanged",
            24: "ItemOpacityChange",
            25: "ItemOpacityHasChanged",
            26: "ItemScenePositionHasChanged",
            28: "ItemRotationChange",
            29: "ItemRotationHasChanged",
            30: "ItemScaleChange",
            31: "ItemScaleHasChanged",
            32: "ItemTransformOriginPointChange",
            33: "ItemTransformOriginPointHasChanged",
            34: "ItemSelectedChange",
            35: "ItemSelectedHasChanged"
        }
        change_name = change_types.get(change, f"Unknown({change})")

        if change == QGraphicsRectItem.ItemPositionChange:
            new_pos = value
            # Logs supprimés : trop verbeux lors du déplacement

            # Notifier l'entité parente si elle est en mode édition
            if self.scene() and hasattr(self.parent_entity, 'is_editing') and self.parent_entity.is_editing:
                if hasattr(self.parent_entity, 'on_anchor_moved'):
                    self.parent_entity.on_anchor_moved(self.index, new_pos)
        # Logs supprimés pour les autres changements

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """Gère le clic sur le point d'ancrage"""
        # Logs supprimés : trop verbeux

        if event.button() == Qt.LeftButton:
            self.setSelected(True)
            # ✅ CRITIQUE: Empêcher la propagation de l'événement vers les items en dessous
            event.accept()
            # Ne pas appeler super() pour éviter que l'événement se propage
            # super().mousePressEvent(event)  # COMMENTÉ
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        """Gérer le déplacement"""
        # Logs supprimés : trop verbeux lors du déplacement
        event.accept()
        # ✅ IMPORTANT: Appeler super() pour que Qt gère le déplacement
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Relâchement"""
        if event.button() == Qt.LeftButton:
            # Logs supprimés
            self.setSelected(False)
        event.accept()
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """Feedback visuel au survol"""
        # Logs supprimés
        self.setScale(1.3)
        if not self.isSelected():
            self.setBrush(QColor(255, 150, 0))  # Orange
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Retour à la normale"""
        # Logs supprimés
        self.setScale(1.0)
        if not self.isSelected():
            self.setBrush(QColor(0, 0, 0))  # Noir
        super().hoverLeaveEvent(event)


class OpeningEntity(BaseEntity):
    """Entité représentant une ouverture (déduction de surface)"""

    def __init__(self, points, pixels_per_meter=100, color=QColor(255, 0, 0), name="Ouverture"):
        super().__init__("opening")
        self.points = points if points else []
        self.pixels_per_meter = pixels_per_meter
        self.color = color
        self.name = name

        # Alias pour la cohérence avec le système de propriétés
        self.nom = name
        self.couleur = color

        # ✅ NOUVEAU: Lien avec la surface parente
        self.parent_surface = None  # PolygonEntity parent

        # Éléments graphiques
        self.polygon_item = None
        self.text_item = None
        self.text_bg = None
        self.scene_ref = None

        # ✅ NOUVEAU: Système d'édition (comme PolygonEntity)
        self.is_editing = False
        self.anchor_points = []

        # ✅ AJOUT: Pour le filtre d'événements
        self._event_filter_installed = False

    def calculate_area(self):
        """Calcule l'aire de l'ouverture en m², arrondie au cm²."""
        return round(polygon_area(self.points, self.pixels_per_meter), 2)

    def get_centroid(self):
        """Calcule le centroïde (centre géométrique) du polygone"""
        if not self.points:
            return QPointF(0, 0)

        sum_x = sum(p.x() for p in self.points)
        sum_y = sum(p.y() for p in self.points)

        return QPointF(sum_x / len(self.points), sum_y / len(self.points))

    def draw(self, scene):
        """Dessine l'ouverture sur la scène"""
        self.scene_ref = scene

        # Créer le polygone de l'ouverture
        polygon = QPolygonF(self.points)

        if not self.polygon_item:
            self.polygon_item = QGraphicsPolygonItem(polygon)
            scene.addItem(self.polygon_item)
        else:
            self.polygon_item.setPolygon(polygon)

        # Style du polygone
        # ✅ NOUVEAU: Utiliser la couleur de la surface parente pour le contour
        contour_color = self.color  # Rouge par défaut

        # Si l'ouverture est liée à une surface, prendre sa couleur
        if hasattr(self, 'parent_surface') and self.parent_surface:
            if hasattr(self.parent_surface, 'color'):
                contour_color = self.parent_surface.color
            elif hasattr(self.parent_surface, 'surface_item') and self.parent_surface.surface_item:
                # Essayer de récupérer la couleur du pen de la surface
                surface_pen = self.parent_surface.surface_item.pen()
                if surface_pen:
                    contour_color = surface_pen.color()

        # Appliquer le contour avec épaisseur scalée
        scaled_pen_width = self.get_scaled_pen_width(2)
        
        # ✅ Convertir la couleur en QColor si c'est une chaîne
        if isinstance(contour_color, str):
            contour_color = QColor(contour_color)
        
        self.polygon_item.setPen(QPen(contour_color, scaled_pen_width, Qt.DashLine))

        # ✅ Garder les hachures rouges semi-transparentes
        brush = QBrush(QColor(255, 0, 0, 30))
        brush.setStyle(Qt.BDiagPattern)  # Hachures diagonales
        self.polygon_item.setBrush(brush)

        # Rendre sélectionnable pour la suppression
        self.polygon_item.setFlag(QGraphicsPolygonItem.ItemIsSelectable, True)
        self.polygon_item.setFlag(QGraphicsPolygonItem.ItemIsFocusable, True)

        # ✅ CRUCIAL: Empêcher que les événements remontent au parent
        self.polygon_item.setFlag(
            QGraphicsPolygonItem.ItemStacksBehindParent, False)
        self.polygon_item.setFiltersChildEvents(False)

        # Métadonnées
        self.polygon_item.setData(0, "opening_entity")
        if hasattr(self, 'entity_id'):
            self.polygon_item.setData(1, self.entity_id)

        # Z-value ULTRA-ÉLEVÉ pour être AU-DESSUS de tout (même des handles)
        # BEAUCOUP plus haut que la surface (100)
        self.polygon_item.setZValue(5000)

        # ✅ NOUVEAU: Connecter le double-clic pour permettre l'édition
        self.polygon_item.mouseDoubleClickEvent = self.mouseDoubleClickEvent

        # ✅ NOUVEAU: Vérifier et établir le lien parent à CHAQUE fois si nécessaire
        if hasattr(self, 'parent_surface') and self.parent_surface and hasattr(self.parent_surface, 'surface_item'):
            if self.parent_surface.surface_item:
                # Vérifier si le parent actuel est le bon
                current_parent = self.polygon_item.parentItem()
                if current_parent != self.parent_surface.surface_item:
                    self.polygon_item.setParentItem(
                        self.parent_surface.surface_item)
                # Respecter la visibilité de la surface parente (ampoule)
                parent_vis = getattr(self.parent_surface, 'visible', True)
                self.polygon_item.setVisible(parent_vis)

        # ❌ NE PLUS DESSINER LE TEXTE DE VALEUR
        # Les ouvertures n'affichent plus leur valeur individuellement
        # Seule la surface parent affiche la valeur nette

    def draw_text(self, scene):
        """Dessine le texte de l'aire (négative pour indiquer déduction)"""
        # Supprimer l'ancien texte s'il existe
        if self.text_item and scene:
            scene.removeItem(self.text_item)
            self.text_item = None
        if self.text_bg and scene:
            scene.removeItem(self.text_bg)
            self.text_bg = None

        # Calculer l'aire
        area_m2 = self.calculate_area()
        text = f"-{area_m2:.2f} m²"
        centroid = self.get_centroid()

        # Créer le fond blanc
        self.text_bg = QGraphicsRectItem()
        self.text_bg.setBrush(QBrush(QColor(255, 255, 255, 220)))
        self.text_bg.setPen(QPen(self.color, 1))
        self.text_bg.setZValue(949)

        # Créer le texte
        self.text_item = QGraphicsTextItem(text)
        self.text_item.setDefaultTextColor(self.color)
        self.text_item.setFont(QFont("Arial", 10, QFont.Bold))
        self.text_item.setZValue(950)

        # Positionner le texte au centre
        text_rect = self.text_item.boundingRect()
        text_width = text_rect.width()
        text_height = text_rect.height()
        self.text_item.setPos(centroid.x() - text_width/2,
                              centroid.y() - text_height/2)

        # Ajuster le fond autour du texte
        self.text_bg.setRect(text_rect.adjusted(-4, -2, 4, 2))
        self.text_bg.setPos(self.text_item.pos())

        # Métadonnées
        if hasattr(self, 'entity_id'):
            self.text_item.setData(1, self.entity_id)
            self.text_bg.setData(1, self.entity_id)

        # Ajouter à la scène
        scene.addItem(self.text_bg)
        scene.addItem(self.text_item)

    def delete(self, scene):
        """Supprime l'ouverture de la scène"""

        # ✅ NOUVEAU: Retirer de la surface parente si liée
        if self.parent_surface:
            self.parent_surface.remove_opening(self)

        # ✅ Vérifier si les items sont encore dans une scène avant de les retirer
        if self.polygon_item and scene:
            if self.polygon_item.scene() is not None:
                try:
                    scene.removeItem(self.polygon_item)
                except Exception as e:
                    pass
            else:
                pass

        if self.text_item and scene:
            if self.text_item.scene() is not None:
                try:
                    scene.removeItem(self.text_item)
                except Exception as e:
                    pass

        if self.text_bg and scene:
            if self.text_bg.scene() is not None:
                try:
                    scene.removeItem(self.text_bg)
                except Exception as e:
                    pass


    def set_selected(self, selected):
        """Définit l'état de sélection de l'ouverture"""
        super().set_selected(selected)

        # ✅ Activer/désactiver la sélection Qt native
        if self.polygon_item:
            self.polygon_item.setSelected(selected)

            # Changer l'apparence visuelle
            if selected:
                self.polygon_item.setPen(QPen(Qt.yellow, 3))
            else:
                self.polygon_item.setPen(QPen(self.color, 2))

    def mousePressEvent(self, event):
        """Gère le clic simple sur l'ouverture"""
        if event.button() == Qt.LeftButton:

            # ✅ Activer la sélection Qt native pour que Delete fonctionne
            self.set_selected(True)
            if self.polygon_item:
                self.polygon_item.setSelected(True)

            # Émettre le signal pour notifier la sélection
            try:
                self.entityClicked.emit(self)
            except Exception as e:
                pass

            event.accept()

    def update_pixels_per_meter(self, new_pixels_per_meter):
        """Met à jour l'échelle pixels/mètres"""
        self.pixels_per_meter = new_pixels_per_meter
        if self.scene_ref:
            self.draw_text(self.scene_ref)

    def to_dict(self):
        """Convertit l'entité en dictionnaire pour la sérialisation"""
        return {
            "type": "opening",
            "points": [(p.x(), p.y()) for p in self.points],
            "pixels_per_meter": self.pixels_per_meter,
            "name": self.name,
            "color": (self.color.red(), self.color.green(), self.color.blue()),
            "visible": self.visible,
            "selected": self.selected,
            "entity_id": self.entity_id
        }

    @classmethod
    def from_dict(cls, data):
        """Crée une entité à partir d'un dictionnaire"""
        points = [QPointF(x, y) for x, y in data["points"]]
        entity = cls(points, data["pixels_per_meter"])
        entity.name = data["name"]
        entity.color = QColor(*data["color"])
        entity.visible = data["visible"]
        entity.selected = data["selected"]
        entity.entity_id = data.get("entity_id")
        return entity

    def detach_from_parent(self):
        """Détache l'ouverture de sa surface parente"""
        if self.polygon_item and self.polygon_item.parentItem():
            self.polygon_item.setParentItem(None)

    def mouseDoubleClickEvent(self, event):
        """Gère le double-clic pour activer l'édition"""
        if event.button() == Qt.LeftButton:

            if not self.is_editing and self.scene_ref:
                self.enable_editing(self.scene_ref)
            elif self.is_editing:
                self.disable_editing(self.scene_ref)

            # ✅ CRUCIAL: Accepter l'événement pour qu'il ne remonte PAS au parent
            event.accept()
            # ✅ CRUCIAL: Arrêter la propagation
            event.setAccepted(True)
            return True

        event.ignore()
        return False

    def eventFilter(self, source, event):
        """Filtre les événements pour gérer les touches (notamment ESC)"""
        from PyQt5.QtCore import QEvent
        from PyQt5.QtCore import Qt

        if event.type() == QEvent.KeyPress:
            # Touche Escape : désactiver l'édition
            if event.key() == Qt.Key_Escape and self.is_editing:
                if self.scene_ref:
                    self.disable_editing(self.scene_ref)
                return True  # Événement traité

        return False  # Laisser passer les autres événements

    def enable_editing(self, scene):
        """Active le mode édition pour l'ouverture"""
        if self.is_editing:
            return

        self.is_editing = True
        self.scene_ref = scene

        # Configure the parent surface to be non-interactive
        if self.parent_surface and self.parent_surface.surface_item:
            # Save original state
            self.parent_surface._original_z = self.parent_surface.surface_item.zValue()
            self.parent_surface._original_opacity = self.parent_surface.surface_item.opacity()

            # Disable ALL mouse interaction
            self.parent_surface.surface_item.setAcceptedMouseButtons(
                Qt.NoButton)
            self.parent_surface.surface_item.setAcceptHoverEvents(False)
            self.parent_surface.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsSelectable, False)
            self.parent_surface.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsFocusable, False)

            # CRITICAL: Completely disable to prevent all interaction
            self.parent_surface.surface_item.setEnabled(False)

            # Put behind handles and make semi-transparent
            self.parent_surface.surface_item.setZValue(50)
            self.parent_surface.surface_item.setOpacity(0.5)


        # Configure the opening polygon
        if self.polygon_item:
            self.polygon_item.setZValue(100)
            self.polygon_item.setAcceptedMouseButtons(Qt.NoButton)
            self.polygon_item.setAcceptHoverEvents(False)
            self.polygon_item.setFlag(
                QGraphicsPolygonItem.ItemIsSelectable, False)
            self.polygon_item.setOpacity(0.7)

        # Create anchor points
        self.create_anchor_points(scene)

        # Event filter for ESC key
        if scene and scene.views():
            view = scene.views()[0]
            view.installEventFilter(self)

    def disable_editing(self, scene):
        """Désactive le mode édition pour l'ouverture"""
        if not self.is_editing:
            return

        self.is_editing = False

        # Restore parent surface to normal state
        if self.parent_surface and self.parent_surface.surface_item:
            # Restore Z-value
            if hasattr(self.parent_surface, '_original_z'):
                self.parent_surface.surface_item.setZValue(
                    self.parent_surface._original_z)

            # Restore opacity
            if hasattr(self.parent_surface, '_original_opacity'):
                self.parent_surface.surface_item.setOpacity(
                    self.parent_surface._original_opacity)
            else:
                self.parent_surface.surface_item.setOpacity(1.0)

            # Re-enable all interaction
            self.parent_surface.surface_item.setEnabled(True)
            self.parent_surface.surface_item.setAcceptedMouseButtons(
                Qt.LeftButton)
            self.parent_surface.surface_item.setAcceptHoverEvents(True)
            self.parent_surface.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsSelectable, True)
            self.parent_surface.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsFocusable, True)


        # Re-enable the opening polygon
        if self.polygon_item:
            self.polygon_item.setAcceptedMouseButtons(Qt.LeftButton)
            self.polygon_item.setAcceptHoverEvents(True)
            self.polygon_item.setFlag(
                QGraphicsPolygonItem.ItemIsSelectable, True)
            self.polygon_item.setZValue(150)
            brush = QBrush(QColor(255, 0, 0, 30))
            brush.setStyle(Qt.BDiagPattern)
            self.polygon_item.setBrush(brush)
            self.polygon_item.setOpacity(1.0)

        # Remove anchor points
        self.remove_anchor_points(scene)

        # Redraw
        if scene:
            self.draw(scene)
            if self.parent_surface and hasattr(self.parent_surface, 'update_visual_with_openings'):
                self.parent_surface.update_visual_with_openings()

        # Remove ESC event filter
        if scene and scene.views():
            view = scene.views()[0]
            view.removeEventFilter(self)

    def create_anchor_points(self, scene):
        """Crée les points d'ancrage aux sommets de l'ouverture"""
        self.remove_anchor_points(scene)

        for i, point in enumerate(self.points):
            anchor = AnchorPoint(point.x(), point.y(), i, self)
            anchor.setEnabled(True)
            anchor.setVisible(True)
            anchor.setAcceptedMouseButtons(Qt.LeftButton)

            scene.addItem(anchor)

            # Z extrêmement élevé
            anchor.setZValue(20000)

            self.anchor_points.append(anchor)

        # Vérification finale
        if self.anchor_points:
            h = self.anchor_points[0]

    def remove_anchor_points(self, scene):
        """Supprime tous les points d'ancrage"""
        for anchor in self.anchor_points:
            if anchor and scene:
                # Cacher avant suppression pour éviter problèmes visuels
                anchor.hide()
                try:
                    scene.removeItem(anchor)
                except:
                    pass
        self.anchor_points = []

    def on_anchor_moved(self, index, new_pos):
        """Callback lorsqu'un point d'ancrage est déplacé"""
        # Logs supprimés : trop verbeux lors du déplacement

        if index < 0 or index >= len(self.points):
            return

        # Mettre à jour le point correspondant
        self.points[index] = QPointF(new_pos.x(), new_pos.y())

        # Mettre à jour le visuel de l'ouverture
        if self.polygon_item:
            self.polygon_item.setPolygon(QPolygonF(self.points))

        # Mettre à jour la surface parente pour refaire l'éviscération
        if self.parent_surface and hasattr(self.parent_surface, 'update_visual_with_openings'):
            self.parent_surface.update_visual_with_openings()

            # Mettre à jour le texte de la surface pour afficher la nouvelle surface nette
            if self.scene_ref and hasattr(self.parent_surface, 'draw_text'):
                self.parent_surface.draw_text(self.scene_ref)

            # Recalculer la surface nette pour le quantitatif
            if hasattr(self.parent_surface, 'calculate_net_area'):
                try:
                    self.parent_surface.calculate_net_area()
                except Exception as e:
                    pass

            # ✅ CRITIQUE: Émettre le signal geometryChanged de la surface parente
            # pour déclencher la mise à jour du relevé et de la légende EN TEMPS RÉEL
            if hasattr(self.parent_surface, 'geometryChanged'):
                self.parent_surface.geometryChanged.emit()

            # ✅ Sécuriser la MAJ temps réel du quantitatif (surface) via MainWindow si connecté
            try:
                if (self.scene_ref and hasattr(self.scene_ref, 'main_window')
                        and self.scene_ref.main_window):
                    self.scene_ref.main_window.on_entity_modified(
                        self.parent_surface)
            except Exception as e:
                pass
        else:
            pass
