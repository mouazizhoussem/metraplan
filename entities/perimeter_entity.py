from PyQt5.QtCore import Qt, QPointF, QLineF, QEvent, pyqtSignal, QRectF
from PyQt5.QtGui import QPen, QColor, QBrush, QPainterPath, QPainterPathStroker, QFont, QPainter, QCursor
from PyQt5.QtWidgets import (QGraphicsPathItem, QGraphicsTextItem,
                             QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem)
from .base_entity import BaseEntity
import math

# ✅ FLAG DE DEBUG POUR LES OUVERTURES
DEBUG_PERIMETER_OPENINGS = True  # Mettre à False pour désactiver


def debug_print(message):
    """Print conditionnel pour le debug des ouvertures"""
    if DEBUG_PERIMETER_OPENINGS:
        pass


class RightAngleSymbol(QGraphicsItem):
    """
    Symbole graphique d'angle droit - STYLE 3: TRIANGLE PLEIN
    Affiche un triangle plein aux coins à 90° (style architectural moderne)
    """

    def __init__(self, corner_point, vector1, vector2, size=14):
        """
        Args:
            corner_point: QPointF du coin où se trouve l'angle droit
            vector1: Vecteur normalisé du premier segment
            vector2: Vecteur normalisé du second segment
            size: Taille du symbole en pixels (défaut: 14)
        """
        super().__init__()

        self.corner = corner_point
        self.vector1 = vector1
        self.vector2 = vector2
        self.size = size

        # Position au coin
        self.setPos(corner_point)

        # Z-value ultra-élevé pour être visible au-dessus de tout
        self.setZValue(2000)

        # Calculer les points du symbole
        self.calculate_symbol_points()

    def calculate_symbol_points(self):
        """Calcule les 3 points du triangle d'angle droit"""
        # Point 1 : le coin (origine)
        self.p1 = QPointF(0, 0)

        # Point 2 : le long du premier vecteur
        self.p2 = QPointF(
            self.vector1.x() * self.size,
            self.vector1.y() * self.size
        )

        # Point 3 : le long du deuxième vecteur
        self.p3 = QPointF(
            self.vector2.x() * self.size,
            self.vector2.y() * self.size
        )

    def boundingRect(self):
        """Définit la zone englobante pour le rendu"""
        margin = 5
        return QRectF(
            -self.size - margin,
            -self.size - margin,
            self.size * 2 + margin * 2,
            self.size * 2 + margin * 2
        )

    def paint(self, painter, option, widget=None):
        """Dessine le symbole d'angle droit - STYLE TRIANGLE PLEIN"""
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Créer le triangle
        triangle_path = QPainterPath()
        triangle_path.moveTo(self.p1)
        triangle_path.lineTo(self.p2)
        triangle_path.lineTo(self.p3)
        triangle_path.closeSubpath()

        # Style : Remplissage rouge/orange vif avec contour sombre
        pen = QPen(QColor(180, 0, 0), 1.5)  # Rouge foncé, 1.5px
        painter.setPen(pen)

        # Remplissage rouge semi-transparent
        painter.setBrush(QBrush(QColor(255, 80, 80, 200)))

        painter.drawPath(triangle_path)


class RightAngleMarker:
    """
    Gestionnaire de marqueurs d'angles droits pour une entité
    Détecte et affiche automatiquement les symboles d'angles de 90°
    """

    def __init__(self):
        self.angle_indicators = []  # ✅ Renommé pour cohérence

    @staticmethod
    def calculate_angle_between_segments(p1, p2, p3):
        """
        Calcule l'angle entre deux segments : (p1→p2) et (p2→p3)

        Returns:
            float: Angle en degrés (0-180)
        """
        # Vecteur 1: p1 → p2
        v1_x = p2.x() - p1.x()
        v1_y = p2.y() - p1.y()

        # Vecteur 2: p2 → p3
        v2_x = p3.x() - p2.x()
        v2_y = p3.y() - p2.y()

        # Produit scalaire
        dot_product = v1_x * v2_x + v1_y * v2_y

        # Magnitudes
        mag1 = math.sqrt(v1_x**2 + v1_y**2)
        mag2 = math.sqrt(v2_x**2 + v2_y**2)

        # Éviter la division par zéro
        if mag1 == 0 or mag2 == 0:
            return 0

        # Calculer le cosinus de l'angle
        cos_angle = dot_product / (mag1 * mag2)

        # Limiter à [-1, 1] pour éviter les erreurs d'arrondi
        cos_angle = max(-1, min(1, cos_angle))

        # Angle en radians puis en degrés
        angle_rad = math.acos(cos_angle)
        angle_deg = math.degrees(angle_rad)

        return angle_deg

    @staticmethod
    def is_right_angle(angle, tolerance=2.0):
        """
        Vérifie si un angle est proche de 90°

        Args:
            angle: Angle en degrés
            tolerance: Tolérance en degrés (défaut: 2.0° pour précision)

        Returns:
            bool: True si l'angle est entre 88° et 92°
        """
        return abs(angle - 90.0) <= tolerance

    @staticmethod
    def normalize_vector(vx, vy):
        """
        Normalise un vecteur (magnitude = 1)

        Returns:
            QPointF: Vecteur normalisé
        """
        magnitude = math.sqrt(vx**2 + vy**2)
        if magnitude == 0:
            return QPointF(0, 0)
        return QPointF(vx / magnitude, vy / magnitude)

    def detect_and_display_right_angles(self, points, scene, symbol_size=18, is_closed=False):
        """
        Détecte et affiche tous les angles droits dans une liste de points

        Args:
            points: Liste de QPointF
            scene: QGraphicsScene où afficher les symboles
            symbol_size: Taille du symbole en pixels (défaut: 18)
            is_closed: True si c'est un polygone fermé (surface), False sinon (périmètre)
        """
        # Nettoyer les anciens symboles
        self.clear_indicators(scene)

        if len(points) < 3:
            return

        # ✅ CORRECTION: Pour les polygones fermés, vérifier TOUS les points
        if is_closed:
            # Pour un polygone fermé, vérifier tous les points (y compris le premier et le dernier)
            indices_to_check = range(len(points))
        else:
            # Pour un périmètre ouvert, ne vérifier que les points intermédiaires
            indices_to_check = range(1, len(points) - 1)

        # Parcourir les points à vérifier
        for i in indices_to_check:
            # ✅ CORRECTION: Utiliser modulo pour boucler sur les points (fermeture)
            p1 = points[(i - 1) % len(points)]  # Point précédent
            p2 = points[i]                      # Point du coin
            p3 = points[(i + 1) % len(points)]  # Point suivant

            # Calculer l'angle
            angle = self.calculate_angle_between_segments(p1, p2, p3)

            # Si c'est un angle droit
            if self.is_right_angle(angle):
                # Calculer les vecteurs normalisés
                # Vecteur 1: p2 → p1 (inversé pour pointer vers l'extérieur)
                v1_x = p1.x() - p2.x()
                v1_y = p1.y() - p2.y()
                vector1 = self.normalize_vector(v1_x, v1_y)

                # Vecteur 2: p2 → p3
                v2_x = p3.x() - p2.x()
                v2_y = p3.y() - p2.y()
                vector2 = self.normalize_vector(v2_x, v2_y)

                # Créer le symbole graphique moderne (triangle rouge)
                symbol = RightAngleSymbol(p2, vector1, vector2, symbol_size)
                scene.addItem(symbol)
                self.angle_indicators.append(symbol)

    def clear_indicators(self, scene):
        """Supprime tous les symboles d'angles droits"""
        for indicator in self.angle_indicators:
            if indicator and scene:
                try:
                    scene.removeItem(indicator)
                except Exception as e:
                    pass

        self.angle_indicators = []


class PerimeterAnchorPoint(QGraphicsRectItem):
    """Point d'ancrage pour l'édition du périmètre - VERSION ULTRA-AMÉLIORÉE"""

    def __init__(self, x, y, index, parent_entity):
        # Tailles de base
        base_visible_size = 16
        base_click_size = 40
        base_pen_width = 3

        # ✅ NOUVEAU: Tailles scalées
        if hasattr(parent_entity, 'scale_manager') and parent_entity.scale_manager:
            self.visible_size = parent_entity.scale_manager.scale_size(
                base_visible_size)
            self.click_size = parent_entity.scale_manager.scale_size(
                base_click_size)
            pen_width = parent_entity.scale_manager.scale_pen_width(
                base_pen_width)
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

        # ✅ STYLE: Carré noir avec contour blanc TRÈS épais (scalé)
        self.setBrush(QColor(0, 0, 0))
        # Contour blanc épais scalé
        self.setPen(QPen(QColor(255, 255, 255), pen_width))

        # ✅ TOUS les flags nécessaires
        self.setFlag(QGraphicsRectItem.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.ItemIsFocusable, True)
        self.setFlag(QGraphicsRectItem.ItemIgnoresTransformations, False)
        # ✅ NOUVEAU: Bloquer la propagation aux parents
        self.setFlag(QGraphicsRectItem.ItemStacksBehindParent, False)

        # ✅ CRUCIAL: Z-value ULTRA-ÉLEVÉ
        self.setZValue(10000)  # AUGMENTÉ de 5000 à 10000
        self.setCursor(Qt.SizeAllCursor)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)

        # ✅ Forcer la capture des événements
        self.setFiltersChildEvents(False)


    def shape(self):
        """
        ✅ CORRECTION CRITIQUE: Zone cliquable ÉLARGIE
        La zone cliquable est BEAUCOUP PLUS GRANDE que le carré visible
        """
        path = QPainterPath()
        # Zone cliquable élargie (32x32) même si le carré visible fait 16x16
        extended_rect = QRectF(
            -self.click_size/2,
            -self.click_size/2,
            self.click_size,
            self.click_size
        )
        path.addRect(extended_rect)
        return path

    def boundingRect(self):
        """
        ✅ Zone de détection élargie pour inclure la zone cliquable
        """
        # Retourner la GRANDE zone cliquable
        return QRectF(
            -self.click_size/2,
            -self.click_size/2,
            self.click_size,
            self.click_size
        )

    def paint(self, painter, option, widget=None):
        """
        ✅ Dessiner seulement le PETIT carré visible
        (mais la zone cliquable reste grande)
        """
        # Dessiner le petit carré visible
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRect(self.rect())

        # ✅ DEBUG: Dessiner la zone cliquable élargie en semi-transparent
        # Décommenter pour visualiser la zone de clic
        # debug_pen = QPen(QColor(0, 255, 0, 100), 1, Qt.DashLine)
        # painter.setPen(debug_pen)
        # painter.setBrush(QBrush(QColor(0, 255, 0, 30)))
        # painter.drawRect(QRectF(-self.click_size/2, -self.click_size/2,
        #                         self.click_size, self.click_size))

    def contains(self, point):
        """
        ✅ Vérifier si un point est dans la zone cliquable ÉLARGIE
        """
        # Utiliser la grande zone
        extended_rect = QRectF(
            -self.click_size/2,
            -self.click_size/2,
            self.click_size,
            self.click_size
        )
        result = extended_rect.contains(point)
        if result:
            pass
        return result

    def itemChange(self, change, value):
        """Gérer les changements de position"""
        if change == QGraphicsRectItem.ItemPositionHasChanged:
            # Éviter les réentrances lors d'un repositionnement programmatique
            if getattr(self.parent_entity, "_suppress_anchor_move", False):
                return super().itemChange(change, value)
            if self.parent_entity:
                self.parent_entity.on_anchor_moved(self.index, self.pos())

        elif change == QGraphicsRectItem.ItemPositionChange:
            # Éviter les réentrances lors d'un repositionnement programmatique
            if getattr(self.parent_entity, "_suppress_anchor_move", False):
                return super().itemChange(change, value)
            if self.parent_entity and hasattr(self.parent_entity, "clamp_anchor_position"):
                # Contraindre immédiatement le handle s'il appartient à une ouverture
                value = self.parent_entity.clamp_anchor_position(
                    self.index, value)

        elif change == QGraphicsRectItem.ItemSelectedChange:
            # Changer l'apparence quand sélectionné
            if value:
                self.setBrush(QColor(255, 0, 0))  # Rouge
                # Contour plus épais
                self.setPen(QPen(QColor(255, 255, 255), 3))
            else:
                self.setBrush(QColor(0, 0, 0))  # Noir
                self.setPen(QPen(QColor(255, 255, 255), 2))  # Contour normal

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
        """Gérer le clic sur le handle"""

        if event.button() == Qt.LeftButton:
            # Désélectionner les autres handles
            if hasattr(self.parent_entity, 'deselect_all_anchors_except'):
                self.parent_entity.deselect_all_anchors_except(self)

        self.setSelected(True)
        # ✅ CRUCIAL: Accepter l'événement IMMÉDIATEMENT
        event.accept()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Gérer le déplacement du handle"""
        # ✅ CRUCIAL: Accepter l'événement
        event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Relâchement du handle"""
        if event.button() == Qt.LeftButton:
            self.setSelected(False)
        event.accept()
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """Feedback visuel au survol"""
        # Agrandir et changer la couleur
        self.setScale(1.3)
        if not self.isSelected():
            self.setBrush(QColor(255, 150, 0))  # Orange
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Retour à la normale"""
        self.setScale(1.0)
        if not self.isSelected():
            self.setBrush(QColor(0, 0, 0))  # Noir
        super().hoverLeaveEvent(event)


class LinearPathItem(QGraphicsPathItem):
    """
    QGraphicsPathItem personnalisé avec zone de sélection LINÉAIRE uniquement.
    Ne sélectionne PAS la surface intérieure, seulement les segments.
    """

    def __init__(self, path=None, stroke_width=2):
        super().__init__(path if path else QPainterPath())
        self.stroke_width = stroke_width

    def shape(self):
        """
        ✅ CORRECTION CRITIQUE: Zone de sélection LINÉAIRE uniquement
        Utilise QPainterPathStroker pour créer une zone de sélection
        qui suit les lignes avec une largeur définie, SANS remplir l'intérieur
        """
        # Créer un stroker pour définir la zone cliquable autour des lignes
        stroker = QPainterPathStroker()

        # Largeur de la zone cliquable = largeur du trait + marge de tolérance
        # Plus la largeur est grande, plus c'est facile de cliquer
        click_tolerance = 10  # pixels de tolérance de chaque côté
        stroker.setWidth(self.stroke_width + click_tolerance)

        # Arrondir les extrémités pour une sélection plus naturelle
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)

        # Créer le path de sélection (seulement autour des lignes)
        selection_path = stroker.createStroke(self.path())

        return selection_path

    def setStrokeWidth(self, width):
        """Mettre à jour la largeur du trait (pour recalculer la zone de sélection)"""
        self.stroke_width = width
        self.update()  # Forcer le recalcul de la zone


class PerimeterEntity(BaseEntity):
    entityClicked = pyqtSignal(object)

    def __init__(self, points=None, color=QColor(0, 0, 255), width=2,
                 pixels_per_meter=100, name="Périmètre"):
        super().__init__("perimeter")
        self.points = points or []

        # IMPORTANT: Stocker la couleur comme string avec alpha (format #AARRGGBB)
        if isinstance(color, str):
            self.color = color
        elif isinstance(color, QColor):
            self.color = color.name(QColor.HexArgb)
        else:
            self.color = QColor(0, 0, 255, 178).name(
                QColor.HexArgb)  # 70% opacité par défaut

        self.width = width
        self.pixels_per_meter = pixels_per_meter
        self.name = name

        # Alias pour la cohérence avec le système de propriétés
        self.nom = name
        self.couleur = QColor(self.color) if isinstance(
            self.color, str) else color

        # ✅ NOUVEAU: Dimensions pour surface/volume dérivés
        # Hauteur (m) -> surface latérale = longueur × hauteur
        self.height = 0.0
        # Épaisseur (m) -> volume = longueur × hauteur × épaisseur
        self.thickness = 0.0

        # Éléments graphiques
        self.path_item = None
        # ✅ CHANGÉ: Listes pour gérer plusieurs textes (un par segment)
        self.text_items = []  # Liste de QGraphicsTextItem
        self.text_bgs = []    # Liste de rectangles de fond
        self.scene_ref = None
        # Affichage des mesures (bulles) masqué par défaut
        self.show_measure = False

        # Points d'ancrage pour l'édition
        self.anchor_points = []
        self.is_editing = False
        self.is_perimeter = True

        # ✅ NOUVEAU: Gestionnaire d'angles droits
        self.right_angle_marker = RightAngleMarker()

        # ✅ NOUVEAU: Ouvertures linéaires (déductions de segments)
        self.linear_openings = []  # Liste des ouvertures linéaires
        self.opening_creation_mode = False  # Mode création d'ouverture actif
        self.opening_start_pos = None  # Position du premier clic
        # Items graphiques des ouvertures (pointillés)
        self.opening_line_items = []
        self.preview_line = None  # ✅ NOUVEAU: Ligne de prévisualisation en temps réel
        # ✅ NOUVEAU: Bulle de mesure pendant le tracé d'ouverture
        self.preview_opening_label = None
        # ✅ NOUVEAU: Libellés des ouvertures (longueur + hauteur)
        self.opening_label_items = []
        # ✅ NOUVEAU: Hauteur par défaut pour les ouvertures (en mètres)
        self.default_opening_height = 2.10

        # ✅ NOUVEAU: Attributs pour le groupement (comme PolygonEntity)
        # ID du groupe (même pour tous les périmètres du groupe)
        self.group_id = None
        self.is_group_parent = False  # True si c'est le périmètre parent du groupe
        self.parent_entity = None  # Référence au périmètre parent si c'est un enfant
        self.child_entities = []  # Liste des périmètres enfants si c'est un parent

    def get_properties(self):
        """Retourne toutes les propriétés sous forme de dictionnaire"""
        perimeter_length = self.calculate_perimeter_length()

        # Convertir self.color en QColor si nécessaire
        color_obj = QColor(self.color) if isinstance(
            self.color, str) else self.color

        return {
            'nom': self.name,
            'type': 'Périmètre',
            'couleur': color_obj.name(),
            'longueur_totale': f"{perimeter_length:.2f} m",
            'nombre_points': len(self.points),
            'nombre_segments': max(0, len(self.points) - 1),
            'epaisseur': f"{self.width} px",
            'echelle': f"1:{self.pixels_per_meter}",
            'en_edition': "Oui" if self.is_editing else "Non",
            'visible': "Oui" if self.visible else "Non",
            'selectionne': "Oui" if self.selected else "Non"
        }

    def draw(self, scene):
        """Dessine le périmètre - VERSION AVEC GESTION DES OUVERTURES"""
        self.scene_ref = scene

        # ✅ NOUVEAU: Créer le chemin en excluant les segments d'ouverture
        path = QPainterPath()
        if self.points:
            # Identifier les segments à exclure (ceux qui sont des ouvertures)
            excluded_segments = set()
            for opening in self.linear_openings:
                # Un segment d'ouverture va de start_point_index à end_point_index
                start_idx = opening['start_point_index']

                # Marquer ce segment comme exclu
                if start_idx < len(self.points) - 1:
                    excluded_segments.add(start_idx)

            # Dessiner le périmètre segment par segment
            path_started = False
            for i in range(len(self.points) - 1):
                # Si ce segment n'est PAS une ouverture, le dessiner
                if i not in excluded_segments:
                    if not path_started:
                        path.moveTo(self.points[i])
                        path_started = True
                    path.lineTo(self.points[i + 1])
                else:
                    # C'est une ouverture, ne pas la dessiner et réinitialiser le path
                    path_started = False

        # Créer ou mettre à jour l'item graphique
        if not self.path_item:
            # ✅ CHANGÉ: Utiliser LinearPathItem au lieu de QGraphicsPathItem
            self.path_item = LinearPathItem(path, self.width)
            scene.addItem(self.path_item)

            # Z-value inférieur aux handles
            self.path_item.setZValue(100)

            # ✅ Opacité par défaut à 70%
            self.path_item.setOpacity(0.7)

            # CONFIGURATION FORCÉE
            self.path_item.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
            self.path_item.setFlag(QGraphicsPathItem.ItemIsFocusable, True)
            self.path_item.setAcceptHoverEvents(True)
            self.path_item.setCursor(Qt.PointingHandCursor)

            # Stocker les données IMPORTANTES
            self.path_item.setData(0, "perimeter_entity")
            if hasattr(self, 'entity_id'):
                self.path_item.setData(1, self.entity_id)

            # Gestionnaires d'événements
            def mouse_press_event(event):
                if event.button() == Qt.LeftButton:
                    # Vérifier si on est en train de dessiner
                    if scene and hasattr(scene, 'views') and scene.views():
                        canvas_view = scene.views()[0]
                        if hasattr(canvas_view, '_is_tool_active') and canvas_view._is_tool_active():
                            event.ignore()
                            return

                    # 1. Nettoyer la sélection
                    scene.clearSelection()
                    # 2. Sélectionner cet item
                    self.path_item.setSelected(True)
                    # 3. Émettre le signal centralisé
                    self.entityClicked.emit(self)
                    # 4. Forcer la mise à jour visuelle
                    self.set_selected(True)
                    # 5. Accepter l'événement
                    event.accept()

                elif event.button() == Qt.RightButton:
                    event.ignore()
                    return

                else:
                    super(QGraphicsPathItem, self.path_item).mousePressEvent(event)

            def mouse_move_event(event):
                """En mode édition, laisser les handles gérer le mouvement"""
                if self.is_editing:
                    event.ignore()
                    return
                super(QGraphicsPathItem, self.path_item).mouseMoveEvent(event)

            def mouse_double_click_event(event):
                """Gestionnaire de double-clic pour activer/désactiver l'édition"""

                if event.button() == Qt.LeftButton:
                    if self.is_editing:
                        self.disable_editing(self.scene_ref)
                    else:
                        self.enable_editing(self.scene_ref)
                    event.accept()
                else:
                    super(QGraphicsPathItem,
                          self.path_item).mouseDoubleClickEvent(event)

            def hover_enter_event(event):
                """Gestionnaire de survol (entrée)"""
                if not self.selected:
                    sw = self.get_scaled_pen_width(self.width)
                    _hp = QPen(Qt.red, sw + 1)
                    _hp.setCapStyle(Qt.FlatCap)
                    self.path_item.setPen(_hp)
                event.accept()

            def hover_leave_event(event):
                """Gestionnaire de survol (sortie)"""
                if not self.selected:
                    color = QColor(self.color) if isinstance(
                        self.color, str) else self.color
                    sw = self.get_scaled_pen_width(self.width)
                    _hlp = QPen(color, sw)
                    _hlp.setCapStyle(Qt.FlatCap)
                    self.path_item.setPen(_hlp)
                event.accept()

            # Assigner les gestionnaires
            self.path_item.mousePressEvent = mouse_press_event
            self.path_item.mouseMoveEvent = mouse_move_event
            self.path_item.mouseDoubleClickEvent = mouse_double_click_event
            self.path_item.hoverEnterEvent = hover_enter_event
            self.path_item.hoverLeaveEvent = hover_leave_event

        # Mettre à jour le chemin et l'apparence
        self.path_item.setPath(path)
        # ✅ NOUVEAU: Mettre à jour la largeur de trait pour la zone de sélection
        if isinstance(self.path_item, LinearPathItem):
            self.path_item.setStrokeWidth(self.width)

        # Conserver la couleur d'origine avec épaisseur scalée
        scaled_width = self.get_scaled_pen_width(self.width)

        color = QColor(self.color) if isinstance(
            self.color, str) else self.color
        _pp = QPen(color, scaled_width)
        _pp.setCapStyle(Qt.FlatCap)
        self.path_item.setPen(_pp)

        # (Ré)stocker les métadonnées
        self.path_item.setData(0, "perimeter_entity")
        if hasattr(self, 'entity_id'):
            self.path_item.setData(1, self.entity_id)

        # Dessiner le texte
        self.draw_text(scene)

        # ✅ NOUVEAU: Dessiner les ouvertures (segments transparents)
        if self.linear_openings:
            self.draw_opening_segments(scene)

        # ✅ NOUVEAU DEBUG après la boucle for
        if self.linear_openings:
            pass

    def set_width(self, width):
        """Définit l'épaisseur du périmètre et met à jour le visuel"""
        self.width = width

        # Mettre à jour le visuel immédiatement
        if self.path_item:
            # Convertir self.color en QColor si c'est une string
            color = QColor(self.color) if isinstance(
                self.color, str) else self.color

            # ✅ CORRECTION: Utiliser l'épaisseur scalée comme dans draw()
            scaled_width = self.get_scaled_pen_width(self.width)

            _sp = QPen(color, scaled_width)
            _sp.setCapStyle(Qt.FlatCap)
            self.path_item.setPen(_sp)

            # Mettre à jour la zone de sélection (stroke width non scalée)
            if isinstance(self.path_item, LinearPathItem):
                self.path_item.setStrokeWidth(self.width)

        # Émettre le signal de modification
        if hasattr(self, 'geometryChanged'):
            self.geometryChanged.emit()

    def force_property_display(self):
        """Force l'affichage des propriétés - méthode robuste"""

        # Méthode 1: Via la scène
        if self.scene_ref and hasattr(self.scene_ref, 'update_properties_panel'):
            self.scene_ref.update_properties_panel(self)
            return

        # Méthode 2: Via main_window direct
        if self.scene_ref and hasattr(self.scene_ref, 'main_window'):
            main_window = self.scene_ref.main_window
            if hasattr(main_window, 'update_properties_panel'):
                main_window.update_properties_panel(self)
                return

        # Méthode 3: Via entity_manager
        if hasattr(self, 'entity_id') and self.scene_ref and hasattr(self.scene_ref, 'entity_manager'):
            entity_manager = self.scene_ref.entity_manager
            if hasattr(entity_manager, 'main_window'):
                main_window = entity_manager.main_window
                if hasattr(main_window, 'update_properties_panel'):
                    main_window.update_properties_panel(self)
                    return


    def afficher_proprietes_immediat(self):
        """Affiche les propriétés IMMÉDIATEMENT au clic"""
        if not self.scene_ref:
            return
        if hasattr(self.scene_ref, 'main_window'):
            main_window = self.scene_ref.main_window
            if hasattr(main_window, 'properties_dock'):
                main_window.properties_dock.afficher_proprietes_instantane(
                    self)

    def afficher_info_rapide(self):
        """Affiche une info rapide au survol"""
        if not self.scene_ref:
            return
        if hasattr(self.scene_ref, 'main_window'):
            main_window = self.scene_ref.main_window
            if hasattr(main_window, 'properties_dock'):
                main_window.properties_dock.afficher_info_rapide(self)

    def cacher_info_rapide(self):
        """Cache l'info rapide quand la souris quitte"""
        if not self.scene_ref:
            return
        if hasattr(self.scene_ref, 'main_window'):
            main_window = self.scene_ref.main_window
            if hasattr(main_window, 'cacher_info_rapide'):
                main_window.cacher_info_rapide()

    def mousePressEvent(self, event):
        """Gère le clic simple sur le périmètre - version améliorée"""
        if event.button() == Qt.LeftButton:
            # NOUVEAU: Si on est en mode édition, laisser les handles gérer
            if self.is_editing:
                event.ignore()
                return

            # NOUVEAU: Vérifier si on est en train de dessiner
            if self.scene_ref and hasattr(self.scene_ref, 'views') and self.scene_ref.views():
                canvas_view = self.scene_ref.views()[0]
                if hasattr(canvas_view, '_is_tool_active') and canvas_view._is_tool_active():
                    # Un outil est actif, laisser passer l'événement
                    event.ignore()
                    return


            # Émettre le signal pour notifier la sélection
            try:
                self.entityClicked.emit(self)
            except Exception as e:
                pass

            # ✅ NOUVEAU: Activer la sélection Qt native pour que Delete fonctionne
            self.set_selected(True)
            if self.path_item:
                self.path_item.setSelected(True)

            # Ne pas accepter immédiatement, laisser CanvasView décider
            event.accept()

        # Le clic droit n'est plus utilisé pour le déplacement
        elif event.button() == Qt.RightButton:
            event.ignore()
            return

        else:
            # Comportement par défaut
            super_per = super(PerimeterEntity, self)
            if hasattr(super_per, 'mousePressEvent'):
                super_per.mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Gestionnaire d'événement de double-clic pour le périmètre"""

        if event.button() == Qt.LeftButton:
            if self.is_editing:
                self.disable_editing(self.scene_ref)
            else:
                self.enable_editing(self.scene_ref)
            event.accept()
        else:
            event.ignore()


    def hoverEnterEvent(self, event):
        """Gestionnaire de survol (entrée)"""
        if not self.selected:
            sw = self.get_scaled_pen_width(self.width)
            _hep = QPen(Qt.red, sw + 1)
            _hep.setCapStyle(Qt.FlatCap)
            self.path_item.setPen(_hep)
        event.accept()

    def hoverLeaveEvent(self, event):
        """Gestionnaire de survol (sortie)"""
        if not self.selected:
            color = QColor(self.color) if isinstance(
                self.color, str) else self.color
            sw = self.get_scaled_pen_width(self.width)
            _hlp = QPen(color, sw)
            _hlp.setCapStyle(Qt.FlatCap)
            self.path_item.setPen(_hlp)
        event.accept()

    def set_selected(self, selected):
        """Définit l'état de sélection de l'entité"""
        super().set_selected(selected)
        if self.path_item:
            # Conserver la couleur d'origine avec épaisseur scalée (stabilité visuelle)
            color = QColor(self.color) if isinstance(
                self.color, str) else self.color
            sw = self.get_scaled_pen_width(self.width)
            _dp = QPen(color, sw)
            _dp.setCapStyle(Qt.FlatCap)
            self.path_item.setPen(_dp)
            # Ne pas modifier l'opacité ici, elle est gérée par enable/disable_editing
            # L'opacité reste à 0.7 par défaut

    def calculate_perimeter_length(self):
        """
        Longueur nette du périmètre en mètres.
        = longueur brute (pixels→m, arrondie) − Σ largeurs nominales des ouvertures (arrondies).
        Les largeurs nominales (length_m) sont les valeurs confirmées par l'utilisateur
        lors du tracé (bulle affichée en :.2f) — source de vérité pour les déductions.
        """
        if len(self.points) < 2:
            return 0.0

        gross_m = self._calculate_gross_perimeter_length_m()   # déjà arrondi à 2 déc.

        # Déduction = Σ des largeurs nominales arrondies (pas pixel-based)
        nominal_ded = round(
            sum(round(float(op.get("length_m", 0.0) or 0.0), 2)
                for op in self.linear_openings),
            2)

        net_m = round(max(0.0, gross_m - nominal_ded), 2)

        if self.linear_openings:
            pass

        return net_m

    def _calculate_gross_perimeter_length_m(self):
        """
        Calcule la longueur BRUTE du périmètre (sans déduire les ouvertures).

        Returns:
            float: Longueur totale en mètres
        """
        if len(self.points) < 2:
            return 0.0

        total_length_px = 0.0
        for i in range(len(self.points) - 1):
            segment_length = QLineF(
                self.points[i], self.points[i + 1]).length()
            total_length_px += segment_length

        return round(total_length_px / self.pixels_per_meter, 2)

    def calculate_gross_perimeter_length_m(self):
        """Alias public de _calculate_gross_perimeter_length_m (longueur BRUTE)."""
        return self._calculate_gross_perimeter_length_m()

    def calculate_surface_laterale(self):
        """
        Surface nette = (Longueur brute × Hauteur mur) - Σ(Longueur ouverture × Hauteur ouverture).

        Returns:
            float: Surface latérale nette en m²
        """
        if not self.height or self.height <= 0:
            return 0.0

        # Surface brute = longueur brute × hauteur du mur
        gross_length_m = self._calculate_gross_perimeter_length_m()
        gross_surface = gross_length_m * self.height

        # Surface des ouvertures = Σ(largeur × hauteur) — valeurs nominales arrondies
        # pour être cohérent avec la bulle d'affichage (:.2f) lors du tracé
        openings_surface = 0.0
        for opening in self.linear_openings:
            opening_width_m  = round(float(opening.get('length_m', 0.0) or 0.0), 2)
            opening_height_m = round(float(opening.get('height',   0.0) or 0.0), 2)
            openings_surface += round(opening_width_m * opening_height_m, 2)

        # Surface nette — arrondir au cm² (cohérence affichage ↔ calcul)
        gross_surface    = round(gross_surface, 2)
        openings_surface = round(openings_surface, 2)
        net_surface      = round(max(0.0, gross_surface - openings_surface), 2)

        if self.linear_openings:
            pass

        return net_surface

    def calculate_volume(self):
        """
        Volume = Surface nette × Épaisseur.

        Returns:
            float: Volume en m³
        """
        if not self.height or self.height <= 0 or not self.thickness or self.thickness <= 0:
            return 0.0

        net_surface = self.calculate_surface_laterale()
        volume      = round(net_surface * self.thickness, 3)

        if self.linear_openings:
            pass

        return volume

    def get_perimeter_text(self):
        """Retourne le texte du périmètre formaté"""
        length = self.calculate_perimeter_length()
        return f"{length:.2f} m"

    def calculate_total_group_length(self):
        """Calcule la longueur totale du groupe (parent + enfants)"""
        if not self.group_id:
            # Pas de groupe, retourner juste la longueur de ce périmètre
            return self.calculate_perimeter_length()

        total_length = 0

        # Si c'est le parent, additionner tous les enfants + soi-même
        if self.is_group_parent:
            # Ajouter la longueur du parent
            total_length += self.calculate_perimeter_length()

            # Ajouter les longueurs de tous les enfants
            for child in self.child_entities:
                if hasattr(child, 'calculate_perimeter_length'):
                    total_length += child.calculate_perimeter_length()

        # Si c'est un enfant, remonter au parent et calculer
        elif self.parent_entity:
            return self.parent_entity.calculate_total_group_length()

        # Sinon, juste ce périmètre
        else:
            total_length = self.calculate_perimeter_length()

        return total_length

    def get_group_display_name(self):
        """Retourne le nom d'affichage pour le groupe"""
        if not self.group_id:
            return self.name

        # Si c'est un enfant, utiliser le nom du parent
        if self.parent_entity:
            return self.parent_entity.name

        # Si c'est le parent
        return self.name

    def draw_text(self, scene):
        """Dessine le texte de distance sur CHAQUE segment du périmètre"""
        # ✅ Supprimer tous les anciens éléments texte
        for text_item in self.text_items:
            if text_item and scene:
                scene.removeItem(text_item)
        for text_bg in self.text_bgs:
            if text_bg and scene:
                scene.removeItem(text_bg)

        # Réinitialiser les listes
        self.text_items = []
        self.text_bgs = []

        # Si l'affichage des mesures est désactivé, ne rien recréer
        if hasattr(self, 'show_measure') and not self.show_measure:
            return

        if not self.points or len(self.points) < 2:
            return

        # ✅ NOUVEAU: Créer un texte pour CHAQUE segment
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]

            # Calculer la distance de ce segment
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            distance_px = math.sqrt(dx**2 + dy**2)
            distance_m = distance_px / self.pixels_per_meter

            # Point milieu du segment
            mid_x = (p1.x() + p2.x()) / 2
            mid_y = (p1.y() + p2.y()) / 2
            mid_point = QPointF(mid_x, mid_y)

            # Créer le texte de distance
            text = f"{distance_m:.2f} m"
            text_item = QGraphicsTextItem(text)

            # Police style CAO
            base_font = QFont("Arial", 8)
            if self.scale_manager:
                scaled_font = self.scale_manager.scale_font(base_font)
                text_item.setFont(scaled_font)
            else:
                text_item.setFont(base_font)

            # ✅ STYLE UNIFIÉ: Exactement comme surface et ligne
            # FORCER la couleur noire de multiple façons
            text_item.setDefaultTextColor(QColor(0, 0, 0))  # Noir pur RGB
            text_item.document().setDefaultStyleSheet("color: black !important;")

            # ✅ NOUVEAU: Stocker les données pour la sélection
            text_item.setData(0, "perimeter_text")
            if hasattr(self, 'entity_id'):
                text_item.setData(1, self.entity_id)

            scene.addItem(text_item)
            self.text_items.append(text_item)

            # ✅ STYLE UNIFIÉ: Créer l'arrière-plan avec padding scalé
            text_rect = text_item.boundingRect()
            margin = self.get_scaled_padding(2)  # ✅ Scalé automatiquement
            text_bg = scene.addRect(
                text_rect.adjusted(-margin, -margin, margin, margin),
                QPen(Qt.black),  # ✅ Contour noir (au lieu de Qt.NoPen)
                # ✅ Fond blanc à 200 d'alpha
                QBrush(QColor(255, 255, 255, 200))
            )

            # ✅ NOUVEAU: Stocker les données pour le fond
            text_bg.setData(0, "perimeter_text_bg")
            if hasattr(self, 'entity_id'):
                text_bg.setData(1, self.entity_id)

            self.text_bgs.append(text_bg)

            # ✅ Positionner et orienter le texte au milieu du segment
            angle = math.degrees(math.atan2(dy, dx))
            # Garder le texte lisible (éviter l'inversion)
            if angle > 90:
                angle -= 180
            elif angle < -90:
                angle += 180

            # Décalage perpendiculaire au segment avec offset scalé
            # Forcer le texte vers le haut (ny <= 0) quelle que soit la direction
            offset = self.get_scaled_offset(15)  # ✅ Scalé automatiquement
            length = math.hypot(dx, dy) or 1.0
            nx = -dy / length
            ny = dx / length
            if ny > 0:
                nx, ny = -nx, -ny
            # DEBUG: Log du placement pour comprendre l'orientation

            text_x = mid_point.x() - text_rect.width() / 2 + nx * offset
            text_y = mid_point.y() - text_rect.height() / 2 + ny * offset

            text_item.setPos(text_x, text_y)
            text_bg.setPos(text_x, text_y)

            # Appliquer la rotation autour du centre
            text_item.setTransformOriginPoint(text_rect.center())
            bg_rect = text_rect.adjusted(-margin, -margin, margin, margin)
            text_bg.setTransformOriginPoint(bg_rect.center())
            text_item.setRotation(angle)
            text_bg.setRotation(angle)

            # ✅ STYLE UNIFIÉ: Z-values comme surface (1000/999 au lieu de 950/949)
            text_item.setZValue(1000)
            text_bg.setZValue(999)

            # Appliquer l'opacité courante (si en mode édition)
            if self.is_editing:
                text_item.setOpacity(0.7)
                text_bg.setOpacity(0.7)
            else:
                # ✅ Opacité normale (au lieu de variable)
                text_item.setOpacity(1.0)
                text_bg.setOpacity(1.0)

        # DEBUG

        # ❌ SUPPRIMÉ: Ne plus afficher les angles droits sur l'entité finale
        # self.right_angle_marker.detect_and_display_right_angles(
        #     self.points, scene)

    def enable_editing(self, scene=None):
        """Active le mode édition avec gestion des handles"""
        if self.is_editing:
            return


        self.is_editing = True
        self.scene_ref = scene


        # Désactiver le path_item
        if self.path_item:
            self.path_item.setAcceptedMouseButtons(Qt.NoButton)
            self.path_item.setAcceptHoverEvents(False)
            self.path_item.setFlag(QGraphicsPathItem.ItemIsSelectable, False)
            self.path_item.setFlag(QGraphicsPathItem.ItemIsFocusable, False)
            self.path_item.setEnabled(False)
            self.path_item.setZValue(50)
            self.path_item.setOpacity(0.5)

        # Gérer la liste de textes
        for text_item in self.text_items:
            text_item.setOpacity(0.7)
        for text_bg in self.text_bgs:
            text_bg.setOpacity(0.7)

        # ✅ NETTOYER les anciens handles avant d'en créer des nouveaux
        self.remove_anchor_points(scene)

        # Créer les points d'ancrage
        self.create_anchor_points(scene)

        # ✅ NOUVEAU: Afficher les symboles d'angles droits en mode édition
        if len(self.points) >= 3:
            self.right_angle_marker.detect_and_display_right_angles(
                self.points,
                scene
            )
            # ❌ SUPPRIMER: Plus de print ici

        # ✅ MODIFIER: Event filter sur la VIEW (pour clavier) ET sur la SCÈNE (pour souris)
        if scene:
            # Pour les événements de souris de la scène (GraphicsSceneMouseMove)
            scene.installEventFilter(self)

            if scene.views():
                view = scene.views()[0]
                # Pour les événements clavier
                view.installEventFilter(self)
                view.setFocusPolicy(Qt.StrongFocus)  # Forcer le focus
                view.setFocus()  # Activer le focus immédiatement

        # ✅ CRITICAL: Redessiner le périmètre pour assurer l'épaisseur visuelle correcte
        if self.scene_ref:
            self.draw(self.scene_ref)


    def disable_editing(self, scene=None):
        """Désactive le mode édition et nettoie tous les éléments visuels"""
        if not self.is_editing:
            return


        self.is_editing = False
        self.opening_creation_mode = False
        self.opening_start_pos = None

        # ✅ 1. Nettoyer la ligne de prévisualisation
        if self.preview_line and self.scene_ref:
            self.scene_ref.removeItem(self.preview_line)
            self.preview_line = None

        # ✅ 2. Nettoyer les symboles d'angle droit (triangles rouges)
        if hasattr(self, 'right_angle_marker') and self.right_angle_marker:
            self.right_angle_marker.clear_indicators(
                self.scene_ref)  # ✅ Ajouter self.scene_ref

        # ✅ 3. Restaurer le path_item complètement
        if hasattr(self, 'path_item') and self.path_item:
            self.path_item.setEnabled(True)
            self.path_item.setOpacity(0.7)
            self.path_item.setZValue(100)

            # ✅ CRITIQUE : Réactiver tous les flags d'interaction
            self.path_item.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
            self.path_item.setFlag(QGraphicsPathItem.ItemIsFocusable, True)
            self.path_item.setAcceptHoverEvents(True)
            self.path_item.setAcceptedMouseButtons(
                Qt.LeftButton | Qt.RightButton)


        # ✅ 4. Restaurer l'opacité des textes
        if hasattr(self, 'text_items'):
            for text_item in self.text_items:
                if text_item:
                    text_item.setOpacity(1.0)

        # ✅ 5. Supprimer les points d'ancrage (handles)
        scene_to_use = scene or self.scene_ref
        if scene_to_use:
            num_handles = len(self.anchor_points)
            self.remove_anchor_points(scene_to_use)

        # ✅ 6. Supprimer les filtres d'événements
        if self.scene_ref:
            # Retirer de la scène
            try:
                self.scene_ref.removeEventFilter(self)
            except:
                pass

            # Retirer de la view
            if self.scene_ref.views():
                view = self.scene_ref.views()[0]
                try:
                    view.removeEventFilter(self)
                except:
                    pass


        # ✅ CRITICAL: Redessiner le périmètre pour restaurer l'épaisseur visuelle
        if self.scene_ref:
            self.draw(self.scene_ref)

        if self.linear_openings:
            pass

    def create_anchor_points(self, scene):
        """Crée les points d'ancrage aux sommets du périmètre"""

        for i, point in enumerate(self.points):
            anchor = PerimeterAnchorPoint(point.x(), point.y(), i, self)
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
        # Empêcher les réentrances si on est en repositionnement auto
        if getattr(self, "_suppress_anchor_move", False):
            return
        if index < 0 or index >= len(self.points):
            return

        # Mettre à jour le point correspondant
        self.points[index] = QPointF(new_pos.x(), new_pos.y())

        # Réajuster les ouvertures linéaires pour rester alignées sur leur segment
        self._recompute_openings_after_point_move(index)

        # ✅ CORRECTION : Redessiner complètement avec la logique d'exclusion des ouvertures
        if self.scene_ref:
            self.draw(self.scene_ref)

        # ✅ NOUVEAU: Mettre à jour les symboles d'angles droits en temps réel
        if self.is_editing and self.scene_ref and hasattr(self, 'right_angle_marker'):
            if self.right_angle_marker and len(self.points) >= 3:
                self.right_angle_marker.detect_and_display_right_angles(
                    self.points,
                    self.scene_ref,
                    is_closed=False  # Périmètre ouvert
                )

        # Émettre le signal de modification
        if hasattr(self, 'geometryChanged'):
            self.geometryChanged.emit()

    def _project_point_on_segment(self, point, seg_a, seg_b):
        """Projette un point sur un segment et renvoie (projection, ratio 0..1)."""
        ab_x = seg_b.x() - seg_a.x()
        ab_y = seg_b.y() - seg_a.y()
        ab_len2 = ab_x * ab_x + ab_y * ab_y
        if ab_len2 == 0:
            return seg_a, 0.0
        ap_x = point.x() - seg_a.x()
        ap_y = point.y() - seg_a.y()
        t = (ap_x * ab_x + ap_y * ab_y) / ab_len2
        t = max(0.0, min(1.0, t))
        proj = QPointF(seg_a.x() + ab_x * t, seg_a.y() + ab_y * t)
        return proj, t

    def _recompute_single_opening(self, opening):
        """Recalcule une ouverture après déplacement d'un point pour rester sur le segment d'origine.

        Les points d'ouverture sont insérés dans self.points. Le « vrai » segment porteur
        est donc le point juste avant start_point_index et juste après end_point_index.
        """
        start_idx = opening.get('start_point_index', -1)
        end_idx = opening.get('end_point_index', -1)
        if start_idx <= 0 or end_idx >= len(self.points) - 1:
            return

        # Segment porteur (points originaux encadrant l'ouverture)
        base_start_idx = start_idx - 1
        base_end_idx = end_idx + 1
        if base_start_idx < 0 or base_end_idx >= len(self.points):
            return

        a = self.points[base_start_idx]
        b = self.points[base_end_idx]
        start_pt = self.points[start_idx]
        end_pt = self.points[end_idx]

        proj_start, t_start = self._project_point_on_segment(start_pt, a, b)
        proj_end, t_end = self._project_point_on_segment(end_pt, a, b)

        # Garantir l'ordre début -> fin
        if t_start > t_end:
            t_start, t_end = t_end, t_start
            proj_start, proj_end = proj_end, proj_start

        # Mettre à jour les points pour rester sur le segment
        self.points[start_idx] = proj_start
        self.points[end_idx] = proj_end

        # Mettre à jour les données de l'ouverture (ratios relatifs au segment porteur)
        opening['start_ratio'] = t_start
        opening['end_ratio'] = t_end
        opening_length_px = QLineF(proj_start, proj_end).length()
        opening['length_px'] = opening_length_px
        opening['length_m'] = opening_length_px / \
            self.pixels_per_meter if self.pixels_per_meter else 0
        # Mettre à jour le segment index pour rester cohérent
        opening['segment_index'] = base_start_idx

        debug_print(
            f"[OPENING_DRAW] Recompute ouverture seg={base_start_idx} ratios={t_start:.3f}->{t_end:.3f} "
            f"len={opening['length_m']:.2f} m | points={len(self.points)}"
        )

    def clamp_anchor_position(self, index, proposed_pos):
        """Contraint un handle lié à une ouverture à rester sur son segment porteur."""
        if not getattr(self, 'linear_openings', None):
            return proposed_pos

        for opening in self.linear_openings:
            start_idx = opening.get('start_point_index', -1)
            end_idx = opening.get('end_point_index', -1)
            if index not in (start_idx, end_idx):
                continue

            # Segment porteur = points encadrant l'ouverture
            if start_idx <= 0 or end_idx >= len(self.points) - 1:
                return proposed_pos

            base_start_idx = start_idx - 1
            base_end_idx = end_idx + 1
            if base_start_idx < 0 or base_end_idx >= len(self.points):
                return proposed_pos

            a = self.points[base_start_idx]
            b = self.points[base_end_idx]
            clamped, _ = self._project_point_on_segment(proposed_pos, a, b)
            return clamped

        # Pas une ouverture : ne pas contraindre
        return proposed_pos

    def _recompute_openings_after_point_move(self, moved_index):
        """Réajuste les ouvertures si un point d'ouverture ou de segment a bougé."""
        if not getattr(self, 'linear_openings', None):
            return
        for opening in self.linear_openings:
            start_idx = opening.get('start_point_index', -1)
            end_idx = opening.get('end_point_index', -1)
            if start_idx <= 0 or end_idx >= len(self.points) - 1:
                continue
            base_start_idx = start_idx - 1
            base_end_idx = end_idx + 1
            # Recalculer si l'un des points du segment porteur ou de l'ouverture a bougé
            if moved_index in (base_start_idx, base_end_idx, start_idx, end_idx):
                self._recompute_single_opening(opening)
                # Repositionner visuellement les handles correspondants
                self._update_anchor_position(start_idx)
                self._update_anchor_position(end_idx)

    def _update_anchor_position(self, idx):
        """Déplace le handle graphique à la nouvelle position du point idx."""
        if not self.anchor_points or idx < 0 or idx >= len(self.anchor_points):
            return
        if idx < len(self.points):
            # Bloquer temporairement les callbacks de déplacement
            self._suppress_anchor_move = True
            try:
                self.anchor_points[idx].setPos(self.points[idx])
            finally:
                self._suppress_anchor_move = False

    def remove_point_at_index(self, index):
        """Supprime un point d'ancrage à l'index donné"""
        if not self.is_editing:
            return False

        # Vérifier qu'on a assez de points (minimum 2 pour un périmètre)
        if len(self.points) <= 2:
            if self.scene_ref and self.scene_ref.views():
                view = self.scene_ref.views()[0]
                if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                    view.parent_window.measure_label.setText(
                        "❌ Impossible : un périmètre doit avoir au moins 2 points"
                    )
            return False

        if index < 0 or index >= len(self.points):
            return False


        # Supprimer le point
        del self.points[index]

        # Redessiner le périmètre
        if self.scene_ref:
            self.draw(self.scene_ref)

        # Recréer les handles avec les nouveaux indices
        self.remove_anchor_points(self.scene_ref)
        self.create_anchor_points(self.scene_ref)

        # Afficher un message de confirmation
        if self.scene_ref and self.scene_ref.views():
            view = self.scene_ref.views()[0]
            if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                view.parent_window.measure_label.setText(
                    f"✅ Point supprimé ! Périmètre a maintenant {len(self.points)} points"
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

        # Pour un périmètre, on ne boucle pas sur le dernier segment (pas fermé)
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]

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
                closest_segment = (i, i + 1)
                closest_point = point_on_line
                insert_index = i + 1

        # Insérer le point s'il est assez proche (< 20 pixels)
        if closest_distance < 20 and closest_point and insert_index is not None:
            # ✅ Ajuster les indices des ouvertures existantes avant insertion
            # On insère 1 point sur le segment closest_segment[0]
            try:
                self._shift_openings_on_insert(
                    segment_idx=closest_segment[0],
                    insert_at=insert_index,
                    added_points=1
                )
            except Exception as e:
                pass

            # Insérer le nouveau point
            self.points.insert(insert_index, closest_point)


            # Redessiner le périmètre
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
        """Filtre les événements pour gérer les touches et le mouvement de souris"""

        # ✅ Gestion du mouvement de souris pour la prévisualisation
        if event.type() == QEvent.GraphicsSceneMouseMove:
            if self.opening_creation_mode and self.opening_start_pos is not None:
                # Afficher la ligne de prévisualisation en temps réel
                mouse_pos = event.scenePos()

                # ✅ NOUVEAU DEBUG
                if not hasattr(self, '_mouse_move_debug_counter'):
                    self._mouse_move_debug_counter = 0

                self._mouse_move_debug_counter += 1
                # Projeter la position du curseur sur le segment
                # Trouver le segment du point de départ
                start_segment = self.find_closest_segment(
                    self.opening_start_pos)

                if start_segment:
                    segment_idx = start_segment['index']

                    # Projeter le curseur sur le même segment
                    p1 = self.points[segment_idx]
                    p2 = self.points[segment_idx + 1]

                    # Calculer la projection du curseur sur le segment
                    line_vec = QPointF(p2.x() - p1.x(), p2.y() - p1.y())
                    line_length_sq = line_vec.x()**2 + line_vec.y()**2

                    if line_length_sq > 0:
                        # Vecteur du point 1 vers le curseur
                        to_cursor = QPointF(
                            mouse_pos.x() - p1.x(), mouse_pos.y() - p1.y())

                        # Projection (produit scalaire / longueur²)
                        t = (to_cursor.x() * line_vec.x() + to_cursor.y()
                             * line_vec.y()) / line_length_sq

                        # Contraindre t entre 0 et 1 pour rester sur le segment
                        t = max(0, min(1, t))

                        # Position projetée sur le segment
                        projected_pos = QPointF(
                            p1.x() + t * line_vec.x(),
                            p1.y() + t * line_vec.y()
                        )
                    else:
                        projected_pos = p1

                    # Supprimer l'ancienne ligne de prévisualisation
                    if self.preview_line and self.scene_ref:
                        self.scene_ref.removeItem(self.preview_line)

                    # Créer une nouvelle ligne de prévisualisation
                    self.preview_line = QGraphicsLineItem(
                        self.opening_start_pos.x(),
                        self.opening_start_pos.y(),
                        projected_pos.x(),
                        projected_pos.y()
                    )

                    # Style: ligne rouge pointillée
                    pen = QPen(QColor(255, 0, 0), 2)
                    pen.setStyle(Qt.DashLine)
                    self.preview_line.setPen(pen)
                    self.preview_line.setZValue(9999)  # Au premier plan

                    if self.scene_ref:
                        self.scene_ref.addItem(self.preview_line)
                        # ✅ Afficher la bulle de longueur en temps réel sur la ligne rouge
                        self._update_opening_preview_label(
                            self.opening_start_pos, projected_pos)

                return False  # Ne pas consommer l'événement

        if event.type() == QEvent.KeyPress:
            # Touche Escape
            if event.key() == Qt.Key_Escape and self.is_editing:
                if self.opening_creation_mode:
                    # ✅ Annuler le mode création d'ouverture
                    debug_print(
                        "❌ [OPENING] Création d'ouverture ANNULÉE par Escape")
                    self.opening_creation_mode = False
                    self.opening_start_pos = None

                    # ✅ Nettoyer la ligne de prévisualisation
                    if self.preview_line and self.scene_ref:
                        self.scene_ref.removeItem(self.preview_line)
                        self.preview_line = None
                    self._clear_preview_opening_label()

                    if self.scene_ref and self.scene_ref.views():
                        view = self.scene_ref.views()[0]
                        if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                            view.parent_window.measure_label.setText(
                                "✏️ Mode édition : [X] Supprimer | [I] Insérer | [P] Ouverture | [H] Hauteur ouverture | [ESC] Quitter")
                    return True
                else:
                    # ✅ Quitter le mode édition complètement
                    self.disable_editing(self.scene_ref)
                    return True

            # Touche I - Insertion de point
            elif event.key() == Qt.Key_I and self.is_editing and not self.opening_creation_mode:
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

            # Touche P - Création d'ouverture
            elif event.key() == Qt.Key_P and self.is_editing:

                self.opening_creation_mode = True
                self.opening_start_pos = None

                if self.scene_ref and self.scene_ref.views():
                    view = self.scene_ref.views()[0]
                    if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                        view.parent_window.measure_label.setText(
                            "🚪 [1/2] Cliquez sur le DÉBUT de l'ouverture sur un segment"
                        )
                return True

            # Touche H - Modification de hauteur d'ouverture
            elif event.key() == Qt.Key_H and self.is_editing and not self.opening_creation_mode:
                if self._handle_opening_height_modification():
                    return True
                return True

        # ✅ NE PLUS GÉRER LES CLICS ICI (délégation directe dans canvas_view)
        return False

    def move_by(self, dx, dy):
        """Déplace le périmètre en mettant à jour tous les points"""

        # Déplacer tous les points
        for i in range(len(self.points)):
            self.points[i] = QPointF(
                self.points[i].x() + dx,
                self.points[i].y() + dy
            )

        # Mettre à jour le chemin (path) en excluant les segments d'ouverture
        if self.path_item:
            path = QPainterPath()
            if self.points:
                # Identifier les segments à exclure (ceux qui sont des ouvertures)
                excluded_segments = set()
                for opening in self.linear_openings:
                    start_idx = opening['start_point_index']
                    if start_idx < len(self.points) - 1:
                        excluded_segments.add(start_idx)

                # Dessiner le périmètre segment par segment (comme dans draw())
                path_started = False
                for i in range(len(self.points) - 1):
                    if i not in excluded_segments:
                        if not path_started:
                            path.moveTo(self.points[i])
                            path_started = True
                        path.lineTo(self.points[i + 1])
                    else:
                        # C'est une ouverture, ne pas la dessiner
                        path_started = False

                self.path_item.setPath(path)

        # Si en mode édition, déplacer les handles
        if self.is_editing and hasattr(self, 'anchor_points'):
            for anchor in self.anchor_points:
                if anchor and anchor.scene():
                    current_pos = anchor.pos()
                    anchor.setPos(current_pos.x() + dx, current_pos.y() + dy)

        # Redessiner les segments d'ouverture si présents
        if self.linear_openings and self.scene_ref:
            self.draw_opening_segments(self.scene_ref)

        # Mettre à jour le texte (affichage des distances)
        if self.scene_ref:
            self.draw_text(self.scene_ref)

        # Émettre le signal de modification
        if hasattr(self, 'geometryChanged'):
            self.geometryChanged.emit()


    def find_closest_segment(self, pos):
        """Trouve le segment le plus proche - VERSION DEBUG"""
        if len(self.points) < 2:
            debug_print(f"      ⚠️ Pas assez de points ({len(self.points)})")
            return None

        debug_print(
            f"      Recherche parmi {len(self.points) - 1} segments...")

        closest_distance = float('inf')
        closest_segment_idx = None
        closest_point_on_segment = None

        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]
            line = QLineF(p1, p2)

            # Projection
            line_length_sq = line.length() ** 2
            if line_length_sq == 0:
                continue

            t = max(0, min(1, (
                (pos.x() - p1.x()) * (p2.x() - p1.x()) +
                (pos.y() - p1.y()) * (p2.y() - p1.y())
            ) / line_length_sq))

            point_on_line = QPointF(
                p1.x() + t * (p2.x() - p1.x()),
                p1.y() + t * (p2.y() - p1.y())
            )

            distance = QLineF(pos, point_on_line).length()

            debug_print(f"         Segment {i}: distance = {distance:.1f} px")

            if distance < closest_distance:
                closest_distance = distance
                closest_segment_idx = i
                closest_point_on_segment = point_on_line

        if closest_distance < 30:  # Tolérance
            debug_print(
                f"      ✅ Segment {closest_segment_idx} trouvé (distance: {closest_distance:.1f} px)")
            return {
                'index': closest_segment_idx,
                'distance': closest_distance,
                'point': closest_point_on_segment
            }

        debug_print(
            f"      ❌ Aucun segment assez proche (min: {closest_distance:.1f} px > 30 px)")
        return None

    def get_point_ratio_on_segment(self, pos, segment_idx):
        """Calcule la position relative (0-1) d'un point sur un segment"""
        if segment_idx >= len(self.points) - 1:
            return None

        p1 = self.points[segment_idx]
        p2 = self.points[segment_idx + 1]

        line_length_sq = QLineF(p1, p2).length() ** 2
        if line_length_sq == 0:
            return 0

        t = max(0, min(1, (
            (pos.x() - p1.x()) * (p2.x() - p1.x()) +
            (pos.y() - p1.y()) * (p2.y() - p1.y())
        ) / line_length_sq))

        return t

    # === Gestion de la bulle de mesure pendant le tracé d'ouverture ===
    def _clear_preview_opening_label(self):
        """Supprime la bulle de mesure temporaire de l'ouverture en cours."""
        if self.preview_opening_label and self.scene_ref:
            try:
                self.scene_ref.removeItem(self.preview_opening_label)
            except Exception:
                pass
        self.preview_opening_label = None

    # === Helpers bulles et identification d'ouverture ===
    def _is_opening_segment(self, seg_idx):
        """Retourne (True, opening) si le segment appartient à une ouverture."""
        for op in self.linear_openings:
            if seg_idx >= op.get('start_point_index', -1) and seg_idx < op.get('end_point_index', -1):
                return True, op
        return False, None

    def _make_segment_label(self, scene, p1, p2, text, z=1000, use_normal_offset=True,
                            vertical_offset=0, perpendicular_sign=1):
        """
        Crée une bulle centrée sur un segment, avec le style des segments standard.

        perpendicular_sign: 1 ou -1 pour placer la bulle d'un côté ou de l'autre du segment.
        Utile pour éviter le chevauchement (ex: largeur d'un côté, hauteur de l'autre).
        """
        txt = QGraphicsTextItem(text)
        # ✅ Style identique aux bulles standard des segments
        txt.setDefaultTextColor(QColor(0, 0, 0))  # Noir pur

        # Police style CAO (ouvertures)
        base_font = QFont("Arial", 8)
        if self.scale_manager:
            scaled_font = self.scale_manager.scale_font(base_font)
            txt.setFont(scaled_font)

        rect = txt.boundingRect()
        margin = self.get_scaled_padding(1)  # ✅ Padding scalé
        w = rect.width() + margin * 2
        h = rect.height() + margin * 2

        bg = QGraphicsRectItem(0, 0, w, h)
        # ✅ Même transparence (200)
        bg.setBrush(QBrush(QColor(255, 255, 255, 200)))
        bg.setPen(QPen(Qt.black))  # ✅ Contour noir
        bg.setZValue(z)

        txt.setParentItem(bg)
        txt.setPos(margin, margin)

        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if use_normal_offset and length:
            # Décalage perpendiculaire au segment (fonctionne pour horizontal ET vertical)
            offset_dist = self.get_scaled_offset(vertical_offset or 10)
            offset = offset_dist * perpendicular_sign
            nx = -dy / length
            ny = dx / length
            mid_x += nx * offset
            mid_y += ny * offset

        # Rotation alignée avec le segment (texte lisible)
        angle = math.degrees(math.atan2(dy, dx))
        if angle > 90:
            angle -= 180
        elif angle < -90:
            angle += 180

        bg.setTransformOriginPoint(w / 2, h / 2)
        bg.setRotation(angle)
        bg.setPos(mid_x - w / 2, mid_y - h / 2)
        scene.addItem(bg)
        return bg

    def _update_opening_preview_label(self, start_point, end_point):
        """Crée/met à jour la bulle de mesure (largeur) centrée sur la ligne rouge."""
        if not self.scene_ref or start_point is None or end_point is None:
            return

        # Nettoyer la bulle précédente
        self._clear_preview_opening_label()

        # Calculer la largeur de l'ouverture
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length_px = math.hypot(dx, dy)
        ppm = getattr(self, 'pixels_per_meter', 100) or 100
        width_m = length_px / ppm
        text = f"{width_m:.2f} m"

        # ✅ Utiliser le même style que les segments standard
        self.preview_opening_label = self._make_segment_label(
            self.scene_ref, start_point, end_point, text,
            z=1000, use_normal_offset=True, vertical_offset=0
        )

    def _handle_opening_height_modification(self):
        """Modifie la hauteur de l'ouverture sous le curseur"""
        if not self.scene_ref or not self.scene_ref.views():
            return False

        view = self.scene_ref.views()[0]

        # Obtenir la position actuelle du curseur en coordonnées scène
        cursor_pos = view.mapToScene(view.mapFromGlobal(QCursor.pos()))

        # Chercher l'ouverture sous le curseur
        opening_idx, opening = self._find_opening_at_position(cursor_pos)

        if opening_idx is None:
            # Aucune ouverture sous le curseur
            if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                view.parent_window.measure_label.setText(
                    "⚠️ Aucune ouverture sous le curseur. Positionnez le curseur sur une ouverture et appuyez sur 'H'."
                )
            return False

        # Obtenir la hauteur actuelle
        current_height = opening.get('height', self.default_opening_height)

        # Afficher la boîte de dialogue
        if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'prompt_opening_height'):
            new_height = view.parent_window.prompt_opening_height(
                current_height)

            if new_height is not None:
                # Mettre à jour la hauteur
                self.linear_openings[opening_idx]['height'] = new_height

                # Redessiner le périmètre
                self.draw(self.scene_ref)

                # Mise à jour temps réel du tableau quantitatif
                if hasattr(view.parent_window, 'on_entity_modified'):
                    view.parent_window.on_entity_modified(self)

                # Message de confirmation
                if hasattr(view.parent_window, 'measure_label'):
                    view.parent_window.measure_label.setText(
                        f"✅ Hauteur de l'ouverture #{opening_idx+1} modifiée : {new_height:.2f} m"
                    )

                return True
            else:
                # L'utilisateur a annulé
                if hasattr(view.parent_window, 'measure_label'):
                    view.parent_window.measure_label.setText(
                        "❌ Modification annulée")
                return False

        return False

    def _find_opening_at_position(self, scene_pos, tolerance=15):
        """
        Trouve l'ouverture sous la position donnée.

        Args:
            scene_pos: Position en coordonnées scène
            tolerance: Distance maximale en pixels pour considérer qu'on est "sur" l'ouverture

        Returns:
            (index, opening_dict) ou (None, None) si aucune ouverture trouvée
        """
        for idx, opening in enumerate(self.linear_openings):
            start_idx = opening.get('start_point_index', -1)
            end_idx = opening.get('end_point_index', -1)

            # Vérifier les indices valides
            if start_idx < 0 or end_idx >= len(self.points):
                continue

            # Obtenir les points de début et fin de l'ouverture
            p1 = self.points[start_idx]
            p2 = self.points[end_idx]

            # Calculer la distance du curseur au segment de l'ouverture
            distance = self._distance_point_to_segment(scene_pos, p1, p2)

            if distance <= tolerance:
                return idx, opening

        return None, None

    def _distance_point_to_segment(self, point, seg_start, seg_end):
        """
        Calcule la distance minimale entre un point et un segment de ligne.

        Returns:
            Distance en pixels
        """
        # Vecteur du segment
        dx = seg_end.x() - seg_start.x()
        dy = seg_end.y() - seg_start.y()

        # Longueur au carré du segment
        length_sq = dx * dx + dy * dy

        if length_sq == 0:
            # Segment de longueur nulle, retourner distance au point
            return math.hypot(point.x() - seg_start.x(), point.y() - seg_start.y())

        # Projection du point sur la ligne du segment (paramètre t)
        t = ((point.x() - seg_start.x()) * dx +
             (point.y() - seg_start.y()) * dy) / length_sq

        # Limiter t entre 0 et 1 pour rester sur le segment
        t = max(0, min(1, t))

        # Point le plus proche sur le segment
        closest_x = seg_start.x() + t * dx
        closest_y = seg_start.y() + t * dy

        # Distance entre le point et le point le plus proche
        return math.hypot(point.x() - closest_x, point.y() - closest_y)

    def create_linear_opening_on_segment(self, segment_idx, start_ratio, end_ratio):
        """Crée une ouverture linéaire sur un segment donné"""

        if segment_idx >= len(self.points) - 1:
            return

        p1 = self.points[segment_idx]
        p2 = self.points[segment_idx + 1]

        # Calculer les positions exactes
        start_x = p1.x() + (p2.x() - p1.x()) * start_ratio
        start_y = p1.y() + (p2.y() - p1.y()) * start_ratio
        end_x = p1.x() + (p2.x() - p1.x()) * end_ratio
        end_y = p1.y() + (p2.y() - p1.y()) * end_ratio

        # Calculer la longueur de l'ouverture
        opening_length_px = ((end_x - start_x)**2 + (end_y - start_y)**2)**0.5
        opening_length_m = opening_length_px / self.pixels_per_meter


        # ⚠️ IMPORTANT : avant d'insérer de nouveaux points, décaler les indices des ouvertures existantes
        insert_at = segment_idx + 1  # premier point inséré
        self._shift_openings_on_insert(segment_idx, insert_at, added_points=2)

        # Insérer les nouveaux points dans la liste
        start_point = QPointF(start_x, start_y)
        end_point = QPointF(end_x, end_y)

        # Insérer les points dans l'ordre
        self.points.insert(segment_idx + 1, start_point)
        self.points.insert(segment_idx + 2, end_point)


        # Enregistrer l'ouverture
        opening_data = {
            'segment_index': segment_idx,
            'start_point_index': segment_idx + 1,
            'end_point_index': segment_idx + 2,
            'start_ratio': start_ratio,
            'end_ratio': end_ratio,
            'length_m': opening_length_m,
            'length_px': opening_length_px
        }

        debug_print(
            f"[OPENING_DRAW] Création ouverture seg={segment_idx} ratios={start_ratio:.3f}->{end_ratio:.3f} "
            f"len={opening_length_m:.2f} m | points={len(self.points)} | ouvertures_avant={len(self.linear_openings)}"
        )

        # Mettre à jour la longueur totale
        old_length = self.calculate_perimeter_length()
        self.linear_openings.append(opening_data)
        new_length = self.calculate_perimeter_length()


        # Redessiner le périmètre
        if self.scene_ref:
            self.draw(self.scene_ref)
        else:
            pass

        # ✅ NOUVEAU: Émettre le signal pour mettre à jour la légende et le relevé quantitatif
        if hasattr(self, 'geometryChanged'):
            self.geometryChanged.emit()


    def _shift_openings_on_insert(self, segment_idx, insert_at, added_points=2):
        """Décale les indices des ouvertures existantes après insertion de points.

        - Les segments situés APRÈS le segment inséré sont décalés.
        - Les indices start/end des ouvertures situées APRÈS insert_at sont décalés.
        """
        if not getattr(self, 'linear_openings', None):
            return

        for op in self.linear_openings:
            # Si l'ouverture est sur un segment suivant, décaler son segment_index
            if op.get('segment_index', -1) > segment_idx:
                op['segment_index'] = op['segment_index'] + added_points

            # Décaler les points si insertion avant eux
            if op.get('start_point_index', -1) >= insert_at:
                op['start_point_index'] = op['start_point_index'] + added_points
            if op.get('end_point_index', -1) >= insert_at:
                op['end_point_index'] = op['end_point_index'] + added_points

    def draw_opening_segments(self, scene):
        """Dessine les segments d'ouverture avec une visualisation subtile"""
        if not scene:
            return


        # Nettoyer les anciens items (lignes + labels) pour n'afficher qu'une bulle (longueur+hauteur)
        for item in self.opening_line_items:
            if item.scene():
                scene.removeItem(item)
        self.opening_line_items.clear()
        for item in self.opening_label_items:
            if item.scene():
                scene.removeItem(item)
        self.opening_label_items.clear()
        # Nettoyer aussi toute bulle de prévisualisation résiduelle (longueur seule)
        self._clear_preview_opening_label()

        if not self.linear_openings:
            return

        # Obtenir la couleur du périmètre (du path_item)
        if hasattr(self, 'path_item') and self.path_item:
            perimeter_color = self.path_item.pen().color()
        else:
            perimeter_color = QColor(255, 255, 255)

        # Dessiner chaque ouverture
        for idx, opening in enumerate(self.linear_openings):
            start_idx = opening['start_point_index']
            end_idx = opening['end_point_index']

            if start_idx < len(self.points) and end_idx < len(self.points):
                p1 = self.points[start_idx]
                p2 = self.points[end_idx]

                line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())

                # ✅ Même couleur que le périmètre, avec épaisseur scalée
                scaled_width = self.get_scaled_pen_width(self.width)
                pen = QPen(perimeter_color, scaled_width)
                pen.setStyle(Qt.SolidLine)
                line.setPen(pen)
                line.setOpacity(0.15)
                # ✅ CHANGÉ : Z-value beaucoup plus élevé pour garantir qu'il soit AU-DESSUS
                line.setZValue(500)

                scene.addItem(line)
                self.opening_line_items.append(line)

                # Bulle hauteur (H) toujours du côté opposé à la bulle du segment du périmètre
                if getattr(self, 'show_measure', False):
                    opening_h_m = opening.get('height', getattr(
                        self, 'default_opening_height', 0.0))
                    # La bulle du périmètre est forcée vers le haut (ny<0 après flip si ny>0).
                    # On calcule ny_natural = dx/length (composante y de la perpendiculaire).
                    # Si ny_natural > 0 → le périmètre flip → l'ouverture prend sign=+1 (bas) ✓
                    # Si ny_natural <= 0 → le périmètre ne flip pas → l'ouverture prend sign=-1 (bas) ✓
                    # Résultat : la bulle ouverture va TOUJOURS du côté opposé au périmètre,
                    # quelle que soit l'orientation du segment (horizontal, vertical, diagonal).
                    _dx = p2.x() - p1.x()
                    _dy = p2.y() - p1.y()
                    _len = math.hypot(_dx, _dy) or 1.0
                    _ny_natural = _dx / _len
                    opening_sign = 1 if _ny_natural > 0 else -1

                    label_text = f"\u25a1 H={opening_h_m:.2f}m"
                    combined_label = self._make_segment_label(
                        scene, p1, p2, label_text, z=1001,
                        use_normal_offset=True, vertical_offset=25,
                        perpendicular_sign=opening_sign)
                    self.opening_label_items.append(combined_label)



    def delete(self, scene):
        """Supprime le périmètre de la scène"""

        # Désactiver le mode édition si actif
        if self.is_editing:
            self.disable_editing(scene)

        # ✅ NOUVEAU: Supprimer les segments d'ouverture
        for item in self.opening_line_items:
            if item and scene:
                try:
                    scene.removeItem(item)
                except Exception as e:
                    pass
        for item in self.opening_label_items:
            if item and scene:
                try:
                    scene.removeItem(item)
                except Exception as e:
                    pass
        # Supprimer la ligne de prévisualisation et sa bulle éventuelle
        if self.preview_line and scene:
            try:
                scene.removeItem(self.preview_line)
            except Exception as e:
                pass
        self.preview_line = None
        self._clear_preview_opening_label()

        # Supprimer le chemin (path_item)
        if self.path_item and scene:
            try:
                scene.removeItem(self.path_item)
            except Exception as e:
                pass

        # Supprimer tous les textes de distance
        if hasattr(self, 'text_items') and self.text_items:
            for text_item in self.text_items:
                if text_item and scene:
                    try:
                        scene.removeItem(text_item)
                    except Exception as e:
                        pass

        # Supprimer tous les fonds de texte
        if hasattr(self, 'text_bgs') and self.text_bgs:
            for text_bg in self.text_bgs:
                if text_bg and scene:
                    try:
                        scene.removeItem(text_bg)
                    except Exception as e:
                        pass


    def to_dict(self):
        """Convertit l'entité en dictionnaire pour la sérialisation"""
        # Convertir self.color en QColor si nécessaire
        color_obj = QColor(self.color) if isinstance(
            self.color, str) else self.color

        return {
            "type": "perimeter",
            "points": [(p.x(), p.y()) for p in self.points],
            "pixels_per_meter": self.pixels_per_meter,
            "name": self.name,
            "color": color_obj.name(QColor.HexArgb),
            "width": self.width,
            "show_measure": getattr(self, "show_measure", False),
            "visible": self.visible,
            "selected": self.selected,
            "entity_id": self.entity_id,
            "group_id": getattr(self, "group_id", None),
            "is_group_parent": getattr(self, "is_group_parent", False),
            "linear_openings": getattr(self, "linear_openings", []),
            "height": getattr(self, "height", 0.0),
            "thickness": getattr(self, "thickness", 0.0)
        }

    @classmethod
    def from_dict(cls, data):
        """Crée une entité à partir d'un dictionnaire"""
        points = [QPointF(x, y) for x, y in data["points"]]
        entity = cls(
            points=points,
            pixels_per_meter=data.get("pixels_per_meter", 100),
            name=data.get("name", "Périmètre"),
            color=data.get("color", QColor(0, 0, 255, 178)),
            width=data.get("width", 2),
        )

        # Définir les propriétés supplémentaires
        entity.name = data.get("name", "Périmètre")
        color_data = data.get("color", QColor(0, 0, 255, 178))
        if isinstance(color_data, str):
            entity.color = color_data
        elif isinstance(color_data, (tuple, list)):
            entity.color = QColor(*color_data).name(QColor.HexArgb)
        elif isinstance(color_data, QColor):
            entity.color = color_data.name(QColor.HexArgb)
        entity.show_measure = data.get("show_measure", False)
        entity.visible = data.get("visible", True)
        entity.selected = data.get("selected", False)
        entity.entity_id = data.get("entity_id")
        entity.group_id = data.get("group_id", None)
        entity.is_group_parent = data.get("is_group_parent", False)
        entity.child_entities = []
        entity.parent_entity = None
        entity.linear_openings = data.get("linear_openings", [])
        entity.height = data.get("height", 0.0)
        entity.thickness = data.get("thickness", 0.0)

        return entity

    def handle_opening_click(self, scene_pos, event):
        """Gère les clics pour la création d'ouverture"""
        debug_print(f"\n🖱️ [OPENING] handle_opening_click appelé")
        debug_print(f"   opening_creation_mode: {self.opening_creation_mode}")
        debug_print(f"   Position: ({scene_pos.x():.1f}, {scene_pos.y():.1f})")

        if not self.opening_creation_mode:
            debug_print(f"   ⚠️ Mode non actif, ignorer")
            return

        if self.opening_start_pos is None:
            # ✅ PREMIER CLIC

            self.opening_start_pos = scene_pos
            # ... rest of code ...

            if self.scene_ref and self.scene_ref.views():
                view = self.scene_ref.views()[0]
                if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                    view.parent_window.measure_label.setText(
                        "🚪 [2/2] Cliquez sur la FIN de l'ouverture (MÊME segment)"
                    )
        else:
            # ✅ DEUXIÈME CLIC

            # ✅ CRITIQUE : Sauvegarder AVANT de réinitialiser
            start_pos_saved = self.opening_start_pos
            end_pos_saved = scene_pos

            # ✅ Nettoyer la ligne de prévisualisation
            if self.preview_line and self.scene_ref:
                self.scene_ref.removeItem(self.preview_line)
            self._clear_preview_opening_label()
            self.preview_line = None

            # Trouver le segment le plus proche pour les deux points

            # ✅ CORRECTION : find_closest_segment retourne un DICTIONNAIRE
            start_segment_data = self.find_closest_segment(start_pos_saved)
            end_segment_data = self.find_closest_segment(end_pos_saved)

            if start_segment_data is None or end_segment_data is None:
                # Réinitialiser
                self.opening_creation_mode = False
                self.opening_start_pos = None
                return

            # Extraire l'index du segment
            segment_idx = start_segment_data['index']

            # Calculer les ratios avec get_point_ratio_on_segment
            start_ratio = self.get_point_ratio_on_segment(
                start_pos_saved, segment_idx)
            end_ratio = self.get_point_ratio_on_segment(
                end_pos_saved, segment_idx)


            # S'assurer que start_ratio < end_ratio
            if start_ratio > end_ratio:
                start_ratio, end_ratio = end_ratio, start_ratio

            # ✅ APPEL CRITIQUE
            self.create_linear_opening_on_segment(
                segment_idx, start_ratio, end_ratio)

            # ✅ Demander la hauteur spécifique de l'ouverture (boîte de dialogue)
            try:
                if self.scene_ref and self.scene_ref.views():
                    view = self.scene_ref.views()[0]
                    if hasattr(view, 'parent_window') and view.parent_window:
                        new_height = view.parent_window.prompt_opening_height(
                            default_value=getattr(self, 'default_opening_height', 2.10))
                        # Appliquer la hauteur à la dernière ouverture créée
                        if new_height is not None and len(self.linear_openings) > 0:
                            self.linear_openings[-1]['height'] = max(
                                0.0, float(new_height))
                            # ✅ Mise à jour temps réel du tableau quantitatif
                            if hasattr(view.parent_window, 'on_entity_modified'):
                                view.parent_window.on_entity_modified(self)
            except Exception as e:
                pass

            # ✅ Rester en mode ouverture pour enchaîner une nouvelle ouverture
            self.opening_start_pos = None

            # Mettre à jour le label
            if self.scene_ref and self.scene_ref.views():
                view = self.scene_ref.views()[0]
                if hasattr(view, 'parent_window') and hasattr(view.parent_window, 'measure_label'):
                    view.parent_window.measure_label.setText(
                        "✅ Ouverture créée ! Cliquez pour la prochaine (ESC pour quitter)"
                    )

