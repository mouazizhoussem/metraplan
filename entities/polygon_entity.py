# entities/polygon_entity.py
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QEvent, QObject, QLineF
from PyQt5.QtGui import QPolygonF, QPen, QBrush, QColor, QMouseEvent, QPainterPath, QFont
from PyQt5.QtWidgets import QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QGraphicsPathItem, QGraphicsItem
from .base_entity import BaseEntity
import math
from .perimeter_entity import RightAngleMarker
from .calculations import (
    polygon_area,
    net_area_with_openings,
    total_area_with_children,
    total_group_area,
)
from core.pattern_brush import make_brush, pattern_to_storage, pattern_from_storage


class AnchorPoint(QGraphicsRectItem):  # ✅ CHANGÉ: RectItem au lieu de EllipseItem
    """Point d'ancrage pour l'édition de polygones - VERSION UNIFIÉE AVEC PÉRIMÈTRE"""

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

        # ✅ UNIFIÉ: Style carré noir avec contour blanc épais (scalé)
        self.setBrush(QColor(0, 0, 0))
        self.setPen(QPen(QColor(255, 255, 255), pen_width))

        # ✅ TOUS les flags nécessaires
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemIsFocusable, True)
        self.setFlag(QGraphicsRectItem.ItemIgnoresTransformations, False)
        self.setFlag(QGraphicsRectItem.ItemStacksBehindParent, False)

        # ✅ UNIFIÉ: Z-value ULTRA-ÉLEVÉ (10000 comme périmètre)
        self.setZValue(10000)
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
        """Zone de détection élargie"""
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

    def keyPressEvent(self, event):
        """Gérer les événements clavier pour supprimer le point avec X"""
        if event.key() == Qt.Key_X:
            # Demander à l'entité parente de supprimer ce point
            if hasattr(self.parent_entity, 'remove_point_at_index'):
                self.parent_entity.remove_point_at_index(self.index)
            event.accept()
        else:
            super().keyPressEvent(event)

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


class PolygonEntity(BaseEntity):
    # NOUVEAU: Signal de sélection (avec un nom différent pour éviter le conflit)
    entityClicked = pyqtSignal(object)

    def __init__(self, points, pixels_per_meter=100):
        """
        Initialise une entité polygone

        Args:
            points: Liste de QPointF représentant les sommets du polygone
            pixels_per_meter: Échelle de conversion pixels/mètres
        """
        super().__init__("polygon")
        self.points = points
        self.polygon = QPolygonF(points)
        self.pixels_per_meter = pixels_per_meter

        # ✅ NOUVEAU: Liste des ouvertures associées à cette surface
        self.openings = []  # Liste d'OpeningEntity
        self.net_area = 0  # Surface nette (avec déductions)

        # ✅ CORRECTION: Ajouter l'attribut manquant
        self.is_perimeter = False  # False pour une surface, True pour un périmètre

        # ✅ NOUVEAU: Dimensions pour calculs surfaciques/volumiques
        self.height = 0.0      # Hauteur (m)
        self.thickness = 0.0   # Épaisseur (m) – optionnelle

        # CORRECTION: Synchroniser nom et name dès l'initialisation
        self.nom = self.name  # Utiliser le nom hérité de BaseEntity
        self.couleur = QColor(0, 255, 0, 100)

        # ✅ CORRECTION: Ajouter l'attribut color aussi (utilisé dans plusieurs endroits)
        # IMPORTANT: Stocker comme string avec alpha (format #AARRGGBB)
        self.color = QColor(0, 255, 0, 178).name(QColor.HexArgb)  # 70% opacité = 178/255

        # ⭐ NOUVEAU: Motif de remplissage
        self.fill_pattern = Qt.SolidPattern

        # ⭐ NOUVEAU: Extensions
        self.extensions = []

        # Système de groupement pour mesures composites
        # ID du groupe (partagé par toutes les surfaces liées)
        self.group_id = None
        self.is_group_parent = False  # True si c'est la surface d'origine
        self.parent_entity = None  # Référence vers la surface parent si c'est un enfant
        self.child_entities = []  # Liste des surfaces enfants si c'est un parent

        self.right_angle_items = []

        # Éléments graphiques
        self.polygon_item = None
        self.text_item = None
        self.text_bg = None
        self.surface_item = None

        # Points d'ancrage pour l'édition
        self.anchor_points = []
        self.is_editing = False
        self.scene_ref = None

        # ✅ NOUVEAU: Gestionnaire d'angles droits
        self.right_angle_marker = RightAngleMarker()

    def get_properties(self):
        """Retourne toutes les propriétés sous forme de dictionnaire"""
        area = self.calculate_area()
        perimeter = self.calculate_perimeter_length()

        # Convertir self.color en QColor si nécessaire pour get_properties
        color_for_props = QColor(self.color) if isinstance(self.color, str) else self.color
        
        return {
            'nom': self.name,
            'type': 'Périmètre' if self.is_perimeter else 'Surface',
            'couleur': color_for_props.name() if hasattr(self, 'color') else self.couleur.name(),
            'surface': f"{area:.2f} m²" if not self.is_perimeter else "N/A",
            'surface_cm²': f"{area * 10000:.2f} cm²" if area < 1 and not self.is_perimeter else "N/A",
            'perimetre': f"{perimeter:.2f} m",
            'nombre_points': len(self.points),
            'echelle': f"1:{self.pixels_per_meter}",
            'en_edition': "Oui" if self.is_editing else "Non",
            'visible': "Oui" if self.visible else "Non",
            'selectionne': "Oui" if self.selected else "Non"
        }

    def calculate_area(self):
        """Aire brute en m², arrondie au cm² pour cohérence affichage ↔ calcul."""
        return round(polygon_area(self.points, self.pixels_per_meter), 2)

    def calculate_net_area(self):
        """Surface nette (aire brute - ouvertures), arrondie au cm²."""
        net = round(net_area_with_openings(self), 2)
        self.net_area = net
        return net

    def calculate_total_area(self):
        """Aire brute du parent + enfants, arrondie au cm²."""
        return round(total_area_with_children(self), 2)

    def calculate_total_group_area(self):
        """Aire nette du groupe (parent + enfants)."""
        return total_group_area(self)

    def calculate_volume(self):
        """
        Volume dérivé de la surface nette (ou brute) et de la hauteur/épaisseur.
        
        IMPORTANT : Cette méthode est utilisée pour calculer le volume des surfaces
        dans les groupes. Toute modification doit préserver la logique :
        - Priorité à la hauteur sur l'épaisseur
        - Utilisation de la surface nette si ouvertures présentes
        - Propagation automatique aux enfants de groupe
        """
        area = self.calculate_net_area() if self.openings else self.calculate_area()

        if self.height and self.height > 0:
            return round(area * self.height, 3)
        if self.thickness and self.thickness > 0:
            return round(area * self.thickness, 3)
        return 0.0

    def get_group_display_name(self):
        """Retourne le nom d'affichage avec compteur si groupé"""
        if self.is_group_parent and self.child_entities:
            return f"{self.name} (×{len(self.child_entities) + 1})"
        return self.name

    # ⭐ NOUVELLES MÉTHODES POUR PROPERTIESDIALOG
    def set_fill_pattern(self, pattern):
        """Applique un motif de remplissage à la surface"""
        self.fill_pattern = pattern

        # Mettre à jour l'affichage
        if self.surface_item:
            brush = QBrush(self.color, pattern)
            self.surface_item.setBrush(brush)

    def set_color(self, color):
        """Change la couleur de la surface (stockée comme string avec alpha)"""
        # Convertir en QColor si c'est une string
        if isinstance(color, str):
            qcolor = QColor(color)
        elif isinstance(color, QColor):
            qcolor = color
        else:
            qcolor = QColor(0, 255, 0, 178)
        
        # IMPORTANT: Stocker comme string avec alpha (format #AARRGGBB)
        self.color = qcolor.name(QColor.HexArgb)
        self.couleur = qcolor  # Garder la compatibilité (QColor)

        # Mettre à jour l'affichage avec le motif actuel
        if self.surface_item:
            brush = make_brush(qcolor, self.fill_pattern)
            self.surface_item.setBrush(brush)

            # Mettre à jour le contour aussi
            pen = QPen(qcolor, 2)
            self.surface_item.setPen(pen)

    def set_name(self, name):
        """Change le nom de la surface"""
        self.name = name
        self.nom = name  # Garder la compatibilité

        # Mettre à jour le texte affiché si visible
        if self.text_item:
            self.update_text_display()

    def update_text_display(self):
        """Met à jour l'affichage du texte (nom + mesures)"""
        if not self.text_item:
            return
        if hasattr(self, 'show_measure') and not self.show_measure:
            if self.text_item:
                self.text_item.setVisible(False)
            if hasattr(self, 'text_bg') and self.text_bg:
                self.text_bg.setVisible(False)
            return

        area = self.calculate_net_area() if self.openings else self.calculate_area()

        text_content = f"{self.name}\n"
        if self.show_measure:
            text_content += f"{area:.2f} m²"
            thick = float(getattr(self, 'thickness', 0.0) or 0.0)
            if thick > 0:
                vol = area * thick
                text_content += f"\n{vol:.3f} m³"

        self.text_item.setPlainText(text_content)

    def add_opening(self, opening_entity):
        """Ajoute une ouverture à cette surface et la lie graphiquement"""
        if opening_entity not in self.openings:
            self.openings.append(opening_entity)
            opening_entity.parent_surface = self

            # Logs de debug supprimés : trop verbeux

            # ✅ Lien graphique parent-enfant avec Qt
            if (hasattr(opening_entity, 'polygon_item') and opening_entity.polygon_item and
                    hasattr(self, 'surface_item') and self.surface_item):

                # Log réduit : supprimé détails de liaison
                try:
                    opening_entity.polygon_item.setParentItem(
                        self.surface_item)
                    # Logs de vérification supprimés

                except Exception as e:
                    pass
            else:
                pass

            # Propager la visibilité du parent à l'ouverture
            
            # Propager la visibilité du parent à l'ouverture
            if hasattr(self, 'surface_item') and self.surface_item:
                visible = self.surface_item.isVisible()
                for attr in ('text_item', 'text_bg'):
                    item = getattr(opening_entity, attr, None)
                    if item:
                        item.setVisible(visible)
                for attr in ('text_items', 'text_bgs'):
                    for item in (getattr(opening_entity, attr, None) or []):
                        if item:
                            item.setVisible(visible)

            # Recalculer et redessiner
            self.calculate_net_area()
            if self.scene_ref:
                # Log supprimé
                self.update_visual_with_openings()
                # Redessiner le texte avec la nouvelle surface nette
                self.draw_text(self.scene_ref)

            # ✅ CRITIQUE: Émettre le signal pour mettre à jour le relevé EN TEMPS RÉEL
            if hasattr(self, 'geometryChanged'):
                # Log supprimé
                self.geometryChanged.emit()

        else:
            pass

    def remove_opening(self, opening_entity):
        """Retire une ouverture de cette surface"""
        if opening_entity in self.openings:
            self.openings.remove(opening_entity)
            opening_entity.parent_surface = None

            # ✅ NOUVEAU: Détacher le lien graphique
            if hasattr(opening_entity, 'detach_from_parent'):
                opening_entity.detach_from_parent()


            # Recalculer et redessiner
            self.calculate_net_area()
            if self.scene_ref:
                self.update_visual_with_openings()
                self.draw_text(self.scene_ref)

            # ✅ CRITIQUE: Émettre le signal pour mettre à jour le relevé EN TEMPS RÉEL
            if hasattr(self, 'geometryChanged'):
                self.geometryChanged.emit()

    def rebuild_openings_path(self):
        """Met à jour le visuel avec les ouvertures évidées - VERSION OPTIMISÉE"""
        if not self.scene_ref:
            return

        # Si pas d'ouvertures, revenir à un polygone simple
        if not self.openings:
            if isinstance(self.surface_item, QGraphicsPathItem):
                # Supprimer l'ancien PathItem
                if self.surface_item.scene():
                    self.scene_ref.removeItem(self.surface_item)

                # ✅ CORRIGÉ: Forcer la recréation complète
                self.surface_item = None
                self.draw(self.scene_ref)

                # ✅ NOUVEAU: S'assurer que les métadonnées sont présentes
                if self.surface_item and hasattr(self, 'entity_id'):
                    self.surface_item.setData(0, "polygon_entity")
                    self.surface_item.setData(1, self.entity_id)
                    # Rétablir les événements
                    self.surface_item.mouseDoubleClickEvent = self.mouseDoubleClickEvent
                    self.surface_item.mousePressEvent = self.mousePressEvent
            return

        # Il y a des ouvertures : créer un chemin avec trous
        main_path = QPainterPath()
        main_path.addPolygon(self.polygon)

        # Soustraire chaque ouverture
        for opening in self.openings:
            if opening.points:
                opening_polygon = QPolygonF(opening.points)
                opening_path = QPainterPath()
                opening_path.addPolygon(opening_polygon)
                main_path = main_path.subtracted(opening_path)

        # ✅ OPTIMISATION CRITIQUE: Réutiliser le PathItem existant si possible
        if isinstance(self.surface_item, QGraphicsPathItem):
            # Ne PAS détruire, juste mettre à jour le path
            self.surface_item.setPath(main_path)
            
            # ✅ CORRECTION CRITIQUE: Ré-attacher les ouvertures au PathItem mis à jour
            for opening in self.openings:
                if hasattr(opening, 'polygon_item') and opening.polygon_item:
                    # Vérifier si l'ouverture n'est pas déjà attachée
                    if opening.polygon_item.parentItem() != self.surface_item:
                        opening.polygon_item.setParentItem(self.surface_item)
            
            # Log supprimé : trop répétitif
            return

        # ❌ Si on arrive ici, c'est la première fois ou conversion nécessaire
        # Log supprimé pour la création initiale aussi

        # Supprimer l'ancien item (si PolygonItem)
        old_item = self.surface_item
        if old_item and self.scene_ref:
            try:
                # Détacher les enfants avant suppression
                for child in old_item.childItems():
                    child.setParentItem(None)
                self.scene_ref.removeItem(old_item)
            except:
                pass

        # Créer un nouveau PathItem avec le chemin évidé
        self.surface_item = QGraphicsPathItem(main_path)

        # Style
        # ✅ Convertir la couleur en QColor si c'est une chaîne
        if hasattr(self, 'color'):
            color = QColor(self.color) if isinstance(self.color, str) else self.color
        else:
            color = QColor(0, 255, 0)
        
        # ✅ CRUCIAL : Préserver le motif de remplissage existant
        fp = self.fill_pattern if hasattr(self, 'fill_pattern') and self.fill_pattern else Qt.SolidPattern
        brush = make_brush(color, fp)
        self.surface_item.setBrush(brush)
        self.surface_item.setPen(QPen(color, 2))

        # Rendre sélectionnable
        self.surface_item.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
        self.surface_item.setFlag(QGraphicsPathItem.ItemIsFocusable, True)

        # Métadonnées
        self.surface_item.setData(0, "polygon_entity")
        if hasattr(self, 'entity_id'):
            self.surface_item.setData(1, self.entity_id)

        # Z-value et opacité
        self.surface_item.setZValue(100)
        self.surface_item.setOpacity(0.7)

        # Event handlers
        if hasattr(self, 'mousePressEvent'):
            self.surface_item.mousePressEvent = self.mousePressEvent
        if hasattr(self, 'mouseDoubleClickEvent'):
            self.surface_item.mouseDoubleClickEvent = self.mouseDoubleClickEvent

        # Ajouter à la scène
        self.scene_ref.addItem(self.surface_item)

        # Attacher les ouvertures comme enfants graphiques
        for opening in self.openings:
            if hasattr(opening, 'polygon_item') and opening.polygon_item:
                opening.polygon_item.setParentItem(self.surface_item)

        # Respecter l'état de visibilité courant (ex : ampoule désactivée)
        if not getattr(self, 'visible', True):
            self.surface_item.setVisible(False)

    # Compatibilité : ancien nom conservé
    def update_visual_with_openings(self):
        return self.rebuild_openings_path()

    def calculate_perimeter_length(self):
        """Calcule la longueur du périmètre en mètres"""
        if len(self.points) < 2:
            return 0

        total_length = 0
        for i in range(len(self.points)):
            j = (i + 1) % len(self.points)
            dx = self.points[j].x() - self.points[i].x()
            dy = self.points[j].y() - self.points[i].y()
            segment_length = math.sqrt(dx**2 + dy**2)
            total_length += segment_length

        # Convertir de pixels en mètres
        length_m = total_length / self.pixels_per_meter
        return length_m

    def get_polygon_centroid(self):
        """
        Calcule le centroïde (centre géométrique) du polygone

        Returns:
            QPointF: Point représentant le centroïde
        """
        if not self.points:
            return QPointF(0, 0)

        # Méthode simple : moyenne arithmétique des coordonnées
        sum_x = sum(p.x() for p in self.points)
        sum_y = sum(p.y() for p in self.points)

        centroid_x = sum_x / len(self.points)
        centroid_y = sum_y / len(self.points)

        return QPointF(centroid_x, centroid_y)

    def get_area_text(self):
        """Retourne le texte de la surface formaté, avec volume si épaisseur saisie."""
        if self.openings and hasattr(self, 'calculate_net_area'):
            area = self.calculate_net_area()
        else:
            area = self.calculate_area()

        if area < 1:
            base = f"{area * 10000:.2f} cm²"
        else:
            base = f"{area:.2f} m²"

        thick = float(getattr(self, 'thickness', 0.0) or 0.0)
        if thick > 0:
            vol = area * thick
            base += f"  →  {vol:.3f} m³"
        return base

    def get_perimeter_text(self):
        """Retourne le texte du périmètre formaté"""
        perimeter = self.calculate_perimeter_length()
        return f"{perimeter:.2f} m"
    
    def sync_openings_visibility(self):
        """Synchronise la visibilité de toutes les ouvertures avec celle de la surface"""
        if not hasattr(self, 'openings') or not self.openings:
            return

        # Utiliser l'attribut Python 'visible' comme source de vérité,
        # car surface_item peut être recréé (nouveau PathItem) et repartirait visible.
        visible = getattr(self, 'visible', True)
        
        for opening in self.openings:
            if hasattr(opening, 'polygon_item') and opening.polygon_item:
                opening.polygon_item.setVisible(visible)
            for attr in ('text_item', 'text_bg'):
                item = getattr(opening, attr, None)
                if item:
                    item.setVisible(visible)
            for attr in ('text_items', 'text_bgs'):
                for item in (getattr(opening, attr, None) or []):
                    if item:
                        item.setVisible(visible)

    def draw(self, scene):
        """Dessine le polygone sur la scène"""
        try:
            self.scene_ref = scene

            # Configuration des couleurs - CORRIGER: convertir string en QColor
            if self.is_perimeter:
                color = QColor(0, 0, 255)
                brush = QBrush(QColor(0, 0, 255, 50))
            else:
                # Convertir self.color (string) en QColor
                color = QColor(self.color) if isinstance(self.color, str) else self.color
                brush = QBrush(color)

            # Créer ou mettre à jour l'item de surface
            if not self.surface_item:
                self.surface_item = QGraphicsPolygonItem(
                    QPolygonF(self.points))
                scene.addItem(self.surface_item)

            # ✅ Métadonnées pour la sélection/drag (nécessaire à CHAQUE redraw)
            if hasattr(self, 'entity_id'):
                self.surface_item.setData(0, "polygon_entity")
                self.surface_item.setData(1, self.entity_id)

            # ✅ CORRECTION: Configuration à CHAQUE redraw (pas seulement à la création)
            self.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsSelectable, True)
            self.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsFocusable, True)
            self.surface_item.setAcceptHoverEvents(True)
            # ✅ Clic gauche uniquement pour éviter le drag au clic droit
            self.surface_item.setAcceptedMouseButtons(Qt.LeftButton)
            self.surface_item.setEnabled(True)  # ✅ S'assure que l'item est interactif

            # ✅ CORRECTION: Connecter les événements à CHAQUE redraw
            self.surface_item.mousePressEvent = self.mousePressEvent
            self.surface_item.mouseDoubleClickEvent = self.mouseDoubleClickEvent

            # Mettre à jour l'apparence avec épaisseur scalée
            scaled_pen_width = self.get_scaled_pen_width(2)
            self.surface_item.setPen(QPen(color, scaled_pen_width))
            # Créer le brush avec le motif - utiliser color (déjà converti)
            brush = make_brush(color, self.fill_pattern)
            self.surface_item.setBrush(brush)

            # ✅ CORRECTION: Vérifier le type avant d'appeler setPolygon
            if isinstance(self.surface_item, QGraphicsPolygonItem):
                self.surface_item.setPolygon(QPolygonF(self.points))
            elif isinstance(self.surface_item, QGraphicsPathItem):
                # Si c'est un PathItem (avec ouvertures), recréer le path
                if self.openings:
                    self.update_visual_with_openings()
                else:
                    # Pas d'ouvertures, convertir en simple polygone
                    path = QPainterPath()
                    path.addPolygon(QPolygonF(self.points))
                    self.surface_item.setPath(path)

            # Mettre à jour l'apparence si sélectionné
            if self.selected:
                self.surface_item.setPen(QPen(Qt.yellow, 3))
            else:
                self.surface_item.setPen(QPen(color, 2))

            # Dessiner le texte
            self.draw_text(scene)

            # Si en mode édition, créer les points d'ancrage
            if self.is_editing:
                self.create_anchor_points(scene)
            
            # Synchroniser la visibilité des ouvertures avec la surface
            self.sync_openings_visibility()

            # Restaurer l'état de visibilité si l'entité était cachée via l'ampoule
            if not getattr(self, 'visible', True):
                if self.surface_item:
                    self.surface_item.setVisible(False)
                if self.text_item:
                    self.text_item.setVisible(False)
                if self.text_bg:
                    self.text_bg.setVisible(False)

        except Exception as e:
            self.draw_fallback(scene)

    # NOUVEAU: Implémentation robuste du clic
    def mousePressEvent(self, event):
        """Gère le clic simple sur le polygone - SOLUTION ROBUSTE"""
        if event.button() != Qt.LeftButton:
            # Ignorer tout bouton autre que le clic gauche (empêche le drag au clic droit)
            event.ignore()
            return

        # NOUVEAU: Si on est en mode édition, laisser les handles gérer
        if self.is_editing:
            event.ignore()
            return

        # NOUVEAU: Vérifier si on est en train de dessiner (outil actif)
        if self.scene_ref and hasattr(self.scene_ref, 'views') and self.scene_ref.views():
            canvas_view = self.scene_ref.views()[0]
            if hasattr(canvas_view, '_is_tool_active') and canvas_view._is_tool_active():
                # Un outil est actif, laisser passer l'événement
                event.ignore()
                return


        # ✅ NOUVEAU: Activer la sélection Qt native pour que Delete fonctionne
        self.set_selected(True)
        if self.surface_item:
            self.surface_item.setSelected(True)

        # Émettre le signal pour notifier la sélection
        try:
            self.entityClicked.emit(self)
        except Exception as e:
            pass

        event.accept()

    def mouseDoubleClickEvent(self, event):
        """Gère le double-clic sur le polygone"""
        if event.button() == Qt.LeftButton:
            # ✅ NOUVEAU: Vérifier si le clic est sur une ouverture AVANT de traiter
            if self.openings and self.scene_ref:
                click_pos = event.scenePos()

                # Vérifier chaque ouverture dans l'ordre Z (du plus haut au plus bas)
                for opening in sorted(self.openings, key=lambda o: o.polygon_item.zValue() if o.polygon_item else 0, reverse=True):
                    if opening.polygon_item and opening.polygon_item.isVisible():
                        # Vérifier si le clic est dans le bounding rect de l'ouverture
                        opening_scene_pos = opening.polygon_item.mapToScene(
                            opening.polygon_item.boundingRect().center())
                        opening_rect = opening.polygon_item.sceneBoundingRect()

                        if opening_rect.contains(click_pos):
                            # Convertir en coordonnées locales de l'ouverture
                            local_pos = opening.polygon_item.mapFromScene(
                                click_pos)
                            if opening.polygon_item.shape().contains(local_pos):
                                # Déléguer l'événement à l'ouverture
                                opening.mouseDoubleClickEvent(event)
                                event.accept()
                                return

            # Si aucune ouverture n'a été cliquée, gérer normalement
            if self.is_editing:
                self.disable_editing(self.scene_ref)
            else:
                self.enable_editing(self.scene_ref)
            event.accept()
        else:
            # Appeler la méthode parente si ce n'est pas un left button
            if hasattr(super(), 'mouseDoubleClickEvent'):
                super().mouseDoubleClickEvent(event)

    def set_selected(self, selected):
        """Définit l'état de sélection de l'entité"""
        super().set_selected(selected)

        # ✅ NOUVEAU: Activer/désactiver la sélection Qt native
        if self.surface_item:
            self.surface_item.setSelected(selected)

            # CORRIGER: Conserver la couleur d'origine ET l'opacité
            color = QColor(self.color) if isinstance(self.color, str) else self.color
            self.surface_item.setPen(QPen(color, 2))
            # Ne pas modifier l'opacité ici, elle est gérée par enable/disable_editing
            # L'opacité reste à 0.7 par défaut

    def draw_fallback(self, scene):
        """Version de fallback sans SurfaceItem"""
        if self.is_perimeter:
            color = QColor(0, 0, 255)
            brush = QBrush(QColor(0, 0, 0, 0))
        else:
            color = QColor(0, 255, 0)
            brush = QBrush(QColor(0, 255, 0, 100))

        if not self.surface_item:
            self.surface_item = QGraphicsPolygonItem(QPolygonF(self.points))
            scene.addItem(self.surface_item)

        self.surface_item.setPen(QPen(color, 2))
        self.surface_item.setBrush(brush)
        self.surface_item.setData(0, "polygon_entity")
        self.surface_item.setData(1, self.entity_id)

        # ✅ CORRECTION: Vérifier le type avant d'appeler setPolygon
        if isinstance(self.surface_item, QGraphicsPolygonItem):
            self.surface_item.setPolygon(QPolygonF(self.points))
        elif isinstance(self.surface_item, QGraphicsPathItem):
            # Si c'est un PathItem, utiliser setPath
            path = QPainterPath()
            path.addPolygon(QPolygonF(self.points))
            self.surface_item.setPath(path)

        # ✅ CORRECTION: Configuration à CHAQUE redraw (pas seulement à la création)
        self.surface_item.setFlag(QGraphicsPolygonItem.ItemIsSelectable, True)
        self.surface_item.setFlag(QGraphicsPolygonItem.ItemIsFocusable, True)
        self.surface_item.setAcceptHoverEvents(True)
        # ✅ Clic gauche uniquement pour éviter le drag au clic droit
        self.surface_item.setAcceptedMouseButtons(Qt.LeftButton)
        self.surface_item.setEnabled(True)  # ✅ S'assure que l'item est interactif
        
        # ✅ CORRECTION: Connecter les événements à CHAQUE redraw
        self.surface_item.mousePressEvent = self.mousePressEvent
        self.surface_item.mouseDoubleClickEvent = self.mouseDoubleClickEvent

        self.draw_text(scene)

        # Restaurer l'état de visibilité si l'entité était cachée via l'ampoule
        if not getattr(self, 'visible', True):
            if self.surface_item:
                self.surface_item.setVisible(False)
            if self.text_item:
                self.text_item.setVisible(False)
            if self.text_bg:
                self.text_bg.setVisible(False)

    def mouseDoubleClickEvent(self, event):
        """Gère le double-clic sur le polygone"""
        if event.button() == Qt.LeftButton:
            if self.is_editing:
                self.disable_editing(self.scene_ref)
            else:
                self.enable_editing(self.scene_ref)
            event.accept()
        else:
            # Appeler la méthode parente si ce n'est pas un left button
            if hasattr(super(), 'mouseDoubleClickEvent'):
                super().mouseDoubleClickEvent(event)

    def draw_text(self, scene):
        """Dessine le texte de la surface avec surface nette si ouvertures"""
        # ✅ AMÉLIORATION: Vérification plus robuste avant suppression
        if self.text_item:
            try:
                if hasattr(self.text_item, 'setParentItem'):
                    self.text_item.setParentItem(None)
                if self.text_item.scene() == scene:  # Vérifier que c'est bien dans cette scène
                    scene.removeItem(self.text_item)
            except (RuntimeError, AttributeError):
                pass  # Ignorer si déjà supprimé
            self.text_item = None

        if self.text_bg:
            try:
                if hasattr(self.text_bg, 'setParentItem'):
                    self.text_bg.setParentItem(None)
                if self.text_bg.scene() == scene:
                    scene.removeItem(self.text_bg)
            except (RuntimeError, AttributeError):
                pass
            self.text_bg = None

        # Si l'affichage de la mesure est désactivé, ne pas recréer la bulle
        if hasattr(self, 'show_measure') and not self.show_measure:
            return

        # Calculer la surface
        area_total = self.calculate_area()
        thick = float(getattr(self, 'thickness', 0.0) or 0.0)

        # Afficher surface nette si des ouvertures existent, puis volume si épaisseur saisie
        if self.openings:
            area_net = self.calculate_net_area()
            text = f"{area_total:.2f} m²\n(net: {area_net:.2f} m²)"
            if thick > 0:
                vol = area_net * thick
                text += f"\n{vol:.3f} m³"
        else:
            text = f"{area_total:.2f} m²"
            if thick > 0:
                vol = area_total * thick
                text += f"\n{vol:.3f} m³"

        # Calculer le centroïde
        centroid = self.get_polygon_centroid()

        # Créer le fond
        self.text_bg = QGraphicsRectItem()
        self.text_bg.setBrush(QBrush(QColor(255, 255, 255, 200)))
        self.text_bg.setPen(QPen(Qt.NoPen))
        self.text_bg.setZValue(949)
        
        # ✅ CORRECTION COMPLÈTE: Rendre le fond 100% transparent aux clics
        self.text_bg.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.text_bg.setAcceptHoverEvents(False)
        self.text_bg.setAcceptedMouseButtons(Qt.NoButton)  # ✅ Crucial: aucun bouton accepté
        self.text_bg.setEnabled(False)  # ✅ Désactive complètement l'interaction

        # Créer le texte avec font scalé
        self.text_item = QGraphicsTextItem(text)
        self.text_item.setDefaultTextColor(Qt.black)
        
        # Police style CAO
        base_font = QFont("Arial", 9, QFont.Bold)
        if self.scale_manager:
            scaled_font = self.scale_manager.scale_font(base_font)
            self.text_item.setFont(scaled_font)
        else:
            self.text_item.setFont(base_font)
        
        self.text_item.setZValue(950)
        
        # ✅ CORRECTION COMPLÈTE: Rendre le texte 100% transparent aux clics
        self.text_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.text_item.setAcceptHoverEvents(False)
        self.text_item.setAcceptedMouseButtons(Qt.NoButton)  # ✅ Crucial: aucun bouton accepté
        self.text_item.setEnabled(False)  # ✅ Désactive complètement l'interaction
        self.text_item.setFlag(QGraphicsItem.ItemIgnoresParentOpacity, False)

        # Positionner le texte
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(
            centroid.x() - text_rect.width() / 2,
            centroid.y() - text_rect.height() / 2
        )

        # Ajuster le fond avec padding scalé
        padding = self.get_scaled_padding(4)  # ✅ Scalé automatiquement
        self.text_bg.setRect(
            text_rect.adjusted(-padding, -padding, padding, padding)
        )
        self.text_bg.setPos(self.text_item.pos())

        # Métadonnées
        if hasattr(self, 'entity_id'):
            self.text_item.setData(1, self.entity_id)
            self.text_bg.setData(1, self.entity_id)

        # ✅ CORRECTION CRITIQUE: Ajouter DIRECTEMENT à la scène, PAS comme enfant
        # Si on utilise setParentItem(), le texte bloque les clics sur le parent !
        scene.addItem(self.text_bg)
        scene.addItem(self.text_item)

        # Restaurer l'état caché si l'entité est invisible via l'ampoule
        if not getattr(self, 'visible', True):
            self.text_item.setVisible(False)
            self.text_bg.setVisible(False)

    def delete(self, scene):
        """Supprime le polygone de la scène - VERSION COMPLÈTE"""

        # Désactiver le mode édition si actif
        if self.is_editing:
            self.disable_editing(scene)

        if self.polygon_item and scene:
            try:
                scene.removeItem(self.polygon_item)
            except Exception as e:
                pass

        if self.text_item and scene:
            try:
                scene.removeItem(self.text_item)
            except Exception as e:
                pass

        if self.text_bg and scene:
            try:
                scene.removeItem(self.text_bg)
            except Exception as e:
                pass

        if self.surface_item and scene:
            try:
                scene.removeItem(self.surface_item)
            except Exception as e:
                pass

        # ✅ NOUVEAU: Nettoyer les indicateurs d'angles droits si présents
        if hasattr(self, 'right_angle_marker') and self.right_angle_marker and scene:
            try:
                self.right_angle_marker.clear_indicators(scene)
            except Exception as e:
                pass


    def move_by(self, dx, dy):
        """Déplace l'entité en mettant à jour tous les points"""
        
        # Déplacer tous les points de la surface
        for i in range(len(self.points)):
            self.points[i] = QPointF(
                self.points[i].x() + dx,
                self.points[i].y() + dy
            )
        self.polygon = QPolygonF(self.points)

        # Déplacer les points de chaque ouverture (pour cohérence interne)
        if self.openings:
            for opening in self.openings:
                for i in range(len(opening.points)):
                    opening.points[i] = QPointF(
                        opening.points[i].x() + dx,
                        opening.points[i].y() + dy
                    )
                # ✅ Mettre à jour le polygon_item de l'ouverture SANS recréer
                if hasattr(opening, 'polygon_item') and opening.polygon_item:
                    opening.polygon_item.setPolygon(QPolygonF(opening.points))

        # Si on est en mode édition, déplacer les handles
        if self.is_editing and hasattr(self, 'anchor_points'):
            for anchor in self.anchor_points:
                if anchor and anchor.scene():
                    current_pos = anchor.pos()
                    anchor.setPos(current_pos.x() + dx, current_pos.y() + dy)

        # Redessiner la surface (surface + texte)
        if self.scene_ref:
            self.draw(self.scene_ref)

    def to_dict(self):
        """Sérialise l'entité en dictionnaire"""
        # Convertir self.color en QColor si nécessaire
        color_obj = QColor(self.color) if isinstance(self.color, str) else self.color
        
        return {
            'type': self.entity_type,
            'entity_id': self.entity_id,
            'name': self.name,
            'points': [(p.x(), p.y()) for p in self.points],
            'color': color_obj.name(),
            'color_alpha': color_obj.alpha(),
            'fill_pattern': pattern_to_storage(self.fill_pattern),
            'show_measure': self.show_measure,
            'visible': self.visible,
            'pixels_per_meter': self.pixels_per_meter,
            'height': getattr(self, 'height', 0.0),
            'thickness': getattr(self, 'thickness', 0.0),
            'openings': [opening.to_dict() for opening in self.openings],
            'extensions': getattr(self, 'extensions', []),  # ⭐ NOUVEAU
            'group_id': getattr(self, 'group_id', None),
            'is_group_parent': getattr(self, 'is_group_parent', False)
        }

    @classmethod
    def from_dict(cls, data):
        """Désérialise depuis un dictionnaire"""
        points = [QPointF(x, y) for x, y in data['points']]
        entity = cls(points, data.get('pixels_per_meter', 100))
        entity.entity_id = data.get('entity_id')
        entity.name = data.get('name', 'Surface')

        # Restaurer la couleur
        color = QColor(data.get('color', '#00FF00'))
        color.setAlpha(data.get('color_alpha', 100))
        entity.color = color.name(QColor.HexArgb)
        entity.couleur = color

        entity.fill_pattern = pattern_from_storage(data.get('fill_pattern', Qt.SolidPattern))

        # ⭐ NOUVEAU: Restaurer les extensions
        entity.extensions = data.get('extensions', [])

        entity.show_measure = data.get('show_measure', False)
        entity.visible = data.get('visible', True)
        entity.height = data.get('height', 0.0)
        entity.thickness = data.get('thickness', 0.0)
        entity.group_id = data.get('group_id', None)
        entity.is_group_parent = data.get('is_group_parent', False)
        entity.child_entities = []
        entity.parent_entity = None
        # Conserver les ouvertures pour restauration ultérieure (PDF)
        entity._pending_openings_data = data.get('openings', [])

        return entity

    def enable_editing(self, scene):
        """Active le mode édition avec points d'ancrage"""
        self.is_editing = True
        self.scene_ref = scene

        # ✅ CORRECTION CRITIQUE: Désactiver COMPLÈTEMENT le polygone
        if self.surface_item:
            # Désactiver TOUS les événements
            self.surface_item.setAcceptedMouseButtons(Qt.NoButton)
            self.surface_item.setAcceptHoverEvents(False)
            self.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsSelectable, False)
            self.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsFocusable, False)

            # ✅ CRUCIAL: Désactiver pour qu'il n'intercepte RIEN
            self.surface_item.setEnabled(False)

            # Z-value BAS (handles à 10000)
            self.surface_item.setZValue(50)

            # Semi-transparent pour indiquer mode édition
            self.surface_item.setOpacity(0.5)

        # Créer les points d'ancrage
        self.create_anchor_points(scene)

        # ✅ NOUVEAU: Afficher les symboles d'angles droits en mode édition
        if len(self.points) >= 3:
            self.right_angle_marker.detect_and_display_right_angles(
                self.points,
                scene,
                is_closed=True  # ✅ AJOUTÉ: Polygone fermé
            )
            # ❌ SUPPRIMER:
            # print(f"   🔺 Symboles d'angles droits affichés en mode édition (tous les points)")

        # Event filter pour ESC
        if scene and scene.views():
            view = scene.views()[0]
            view.installEventFilter(self)

        # ✅ NOUVEAU : Reconnecter le signal de MainWindow si nécessaire
        if hasattr(self, '_mainwindow_connected') and self._mainwindow_connected:
            # Vérifier le nombre de connexions
            nb_receivers = self.receivers(self.geometryChanged)

            if nb_receivers == 0:
                # Émettre un événement pour demander à MainWindow de reconnecter
                if hasattr(scene, 'main_window') and scene.main_window:
                    scene.main_window.on_entity_added(self)

    def disable_editing(self, scene):
        """Désactive le mode édition pour le polygone"""
        if not self.is_editing:
            return

        self.is_editing = False

        # ✅ NOUVEAU: Nettoyer les symboles d'angles droits
        if hasattr(self, 'right_angle_marker') and self.right_angle_marker and scene:
            self.right_angle_marker.clear_indicators(scene)

        # Réactiver le polygone
        if self.surface_item:
            self.surface_item.setAcceptedMouseButtons(Qt.AllButtons)
            self.surface_item.setAcceptHoverEvents(True)
            self.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsSelectable, True)
            self.surface_item.setFlag(
                QGraphicsPolygonItem.ItemIsFocusable, True)
            self.surface_item.setEnabled(True)
            self.surface_item.setZValue(100)
            self.surface_item.setOpacity(0.7)  # Opacité par défaut

        # Supprimer les points d'ancrage
        self.remove_anchor_points(scene)

        # Retirer event filter
        if scene and scene.views():
            view = scene.views()[0]
            view.removeEventFilter(self)

    def create_anchor_points(self, scene):
        """Crée les points d'ancrage aux sommets du polygone"""
        self.remove_anchor_points(scene)  # Nettoyer les anciens points

        for i, point in enumerate(self.points):
            anchor = AnchorPoint(point.x(), point.y(), i, self)
            scene.addItem(anchor)
            self.anchor_points.append(anchor)

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
        self.polygon = QPolygonF(self.points)

        # Mettre à jour le visuel du polygone
        if self.surface_item:
            if isinstance(self.surface_item, QGraphicsPolygonItem):
                self.surface_item.setPolygon(self.polygon)
            elif isinstance(self.surface_item, QGraphicsPathItem):
                # Si on a des ouvertures, mettre à jour via update_visual_with_openings
                if self.openings:
                    self.update_visual_with_openings()
                else:
                    # Pas d'ouvertures, mais c'est un PathItem - reconvertir en PolygonItem
                    path = QPainterPath()
                    path.addPolygon(self.polygon)
                    self.surface_item.setPath(path)

        # ✅ NOUVEAU: Mettre à jour les symboles d'angles droits en temps réel
        if self.is_editing and self.scene_ref and hasattr(self, 'right_angle_marker'):
            if self.right_angle_marker and len(self.points) >= 3:
                self.right_angle_marker.detect_and_display_right_angles(
                    self.points,
                    self.scene_ref,
                    is_closed=True  # Polygone fermé
                )

        # Recalculer l'aire et mettre à jour le texte
        if self.scene_ref:
            self.draw_text(self.scene_ref)

        # Émettre le signal de modification
        if hasattr(self, 'geometryChanged'):
            # NOUVEAU - Compter les connexions (sans argument)
            try:
                nb_receivers = self.receivers(self.geometryChanged)
            except Exception as e:
                pass

            self.geometryChanged.emit()

            # ✅ Sécuriser la MAJ temps réel du quantitatif (surface) via MainWindow si connecté
            try:
                if self.scene_ref and hasattr(self.scene_ref, 'main_window') and self.scene_ref.main_window:
                    self.scene_ref.main_window.on_entity_modified(self)
            except Exception as e:
                pass
        else:
            pass

    def remove_point_at_index(self, index):
        """Supprime un point d'ancrage à l'index donné"""
        if not self.is_editing:
            return False

        # Vérifier qu'on a assez de points (minimum 3 pour un polygone)
        if len(self.points) <= 3:
            if self.scene_ref and self.scene_ref.views():
                view = self.scene_ref.views()[0]
                if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                    view.parent_window.measure_label.setText(
                        "❌ Impossible : une surface doit avoir au moins 3 points"
                    )
            return False

        if index < 0 or index >= len(self.points):
            return False


        # Supprimer le point
        del self.points[index]
        self.polygon = QPolygonF(self.points)

        # Redessiner la surface
        if self.scene_ref:
            self.draw(self.scene_ref)

        # Recréer les handles avec les nouveaux indices
        self.remove_anchor_points(self.scene_ref)
        self.create_anchor_points(self.scene_ref)

        # Afficher un message de confirmation
        if self.scene_ref and self.scene_ref.views():
            view = self.scene_ref.views()[0]
            if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                area_m2 = self.calculate_area()
                view.parent_window.measure_label.setText(
                    f"✅ Point supprimé ! Surface: {area_m2:.2f} m² ({len(self.points)} points)"
                )

        # Émettre le signal de modification
        if hasattr(self, 'geometryChanged'):
            self.geometryChanged.emit()

        return True

    def insert_point_at_cursor(self, cursor_pos):
        """Insère un nouveau point sur le segment le plus proche du curseur"""
        if not self.is_editing:
            return False

        if len(self.points) < 2:
            return False

        # Trouver le segment le plus proche du curseur
        closest_segment = None
        closest_distance = float('inf')
        closest_point = None
        insert_index = None

        for i in range(len(self.points)):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % len(self.points)]

            # Calculer la distance du curseur au segment
            line = QLineF(p1, p2)
            
            # ✅ Ignorer les segments de longueur nulle (points au même endroit)
            line_length = line.length()
            if line_length < 0.001:
                continue

            # Point le plus proche sur le segment
            t = max(0, min(1, (
                (cursor_pos.x() - p1.x()) * (p2.x() - p1.x()) +
                (cursor_pos.y() - p1.y()) * (p2.y() - p1.y())
            ) / (line_length ** 2)))

            point_on_line = QPointF(
                p1.x() + t * (p2.x() - p1.x()),
                p1.y() + t * (p2.y() - p1.y())
            )

            distance = QLineF(cursor_pos, point_on_line).length()

            if distance < closest_distance:
                closest_distance = distance
                closest_segment = (i, (i + 1) % len(self.points))
                closest_point = point_on_line
                insert_index = i + 1

        # Insérer le point s'il est assez proche (< 20 pixels)
        if closest_distance < 20 and closest_point and insert_index is not None:
            # Insérer le nouveau point
            self.points.insert(insert_index, closest_point)
            self.polygon = QPolygonF(self.points)


            # Redessiner la surface
            if self.scene_ref:
                self.draw(self.scene_ref)

            # Recréer les handles avec le nouveau point
            self.remove_anchor_points(self.scene_ref)
            self.create_anchor_points(self.scene_ref)

            # Émettre le signal de modification
            if hasattr(self, 'geometryChanged'):
                self.geometryChanged.emit()

            return True
        else:
            return False

    def eventFilter(self, source, event):
        """Filtre les événements pour gérer les touches"""
        if event.type() == QEvent.KeyPress:
            # Touche Escape : désactiver l'édition
            if event.key() == Qt.Key_Escape and self.is_editing:
                self.disable_editing(self.scene_ref)
                return True

            # ✅ NOUVEAU : Touche I : insérer un point
            elif event.key() == Qt.Key_I and self.is_editing:
                # Obtenir la position du curseur
                if self.scene_ref and self.scene_ref.views():
                    view = self.scene_ref.views()[0]
                    cursor_pos = view.mapToScene(
                        view.mapFromGlobal(view.cursor().pos()))
                    if self.insert_point_at_cursor(cursor_pos):
                        if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                            view.parent_window.measure_label.setText(
                                "✅ Point inséré ! Déplacez-le pour ajuster la forme"
                            )
                return True

        return False
