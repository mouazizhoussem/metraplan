# entities/line_entity.py
from PyQt5.QtCore import Qt, QPointF, QLineF, QEvent, QRectF, pyqtSignal
from PyQt5.QtGui import QPen, QColor, QBrush, QPainterPath, QFont
from PyQt5.QtWidgets import (QGraphicsLineItem, QGraphicsTextItem,
                             QGraphicsRectItem)
from .base_entity import BaseEntity
import math


class LineAnchorPoint(QGraphicsRectItem):  # ✅ CHANGÉ: RectItem au lieu de EllipseItem
    """Point d'ancrage pour l'édition des lignes - VERSION UNIFIÉE"""

    def __init__(self, x, y, is_start_point, parent_entity):
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
        # True pour point de départ, False pour point d'arrivée
        self.is_start_point = is_start_point
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

        # ✅ UNIFIÉ: Z-value ULTRA-ÉLEVÉ (10000)
        self.setZValue(10000)
        self.setCursor(Qt.SizeAllCursor)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setFiltersChildEvents(False)

        point_type = "départ" if is_start_point else "arrivée"

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
        """Vérifier si un point est dans la zone cliquable ÉLARGIE"""
        extended_rect = QRectF(
            -self.click_size/2,
            -self.click_size/2,
            self.click_size,
            self.click_size
        )
        result = extended_rect.contains(point)
        if result:
            point_type = "départ" if self.is_start_point else "arrivée"
        return result

    def itemChange(self, change, value):
        """Gérer les changements de position"""
        if change == QGraphicsRectItem.ItemPositionHasChanged:
            point_type = "départ" if self.is_start_point else "arrivée"
            if self.parent_entity:
                self.parent_entity.on_anchor_moved(self.is_start_point, self.pos())

        elif change == QGraphicsRectItem.ItemPositionChange:
            point_type = "départ" if self.is_start_point else "arrivée"

        elif change == QGraphicsRectItem.ItemSelectedChange:
            # Changer l'apparence quand sélectionné
            if value:
                self.setBrush(QColor(255, 0, 0))  # Rouge
                self.setPen(QPen(QColor(255, 255, 255), 3))
            else:
                self.setBrush(QColor(0, 0, 0))  # Noir
                self.setPen(QPen(QColor(255, 255, 255), 3))

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """Gérer le clic sur le handle"""
        point_type = "départ" if self.is_start_point else "arrivée"

        if event.button() == Qt.LeftButton:
            if hasattr(self.parent_entity, 'deselect_all_anchors_except'):
                self.parent_entity.deselect_all_anchors_except(self)

            self.setSelected(True)
            event.accept()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Gérer le déplacement"""
        point_type = "départ" if self.is_start_point else "arrivée"
        event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Relâchement"""
        point_type = "départ" if self.is_start_point else "arrivée"
        if event.button() == Qt.LeftButton:
            self.setSelected(False)
        event.accept()
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """Feedback visuel au survol"""
        point_type = "départ" if self.is_start_point else "arrivée"
        self.setScale(1.3)
        if not self.isSelected():
            self.setBrush(QColor(255, 150, 0))  # Orange
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Retour à la normale"""
        point_type = "départ" if self.is_start_point else "arrivée"
        self.setScale(1.0)
        if not self.isSelected():
            self.setBrush(QColor(0, 0, 0))  # Noir
        super().hoverLeaveEvent(event)


class LineEntity(BaseEntity):
    # NOUVEAU: Ajouter le signal entityClicked
    entityClicked = pyqtSignal(object)

    def __init__(self, start_point, end_point, color=QColor(0, 0, 255), width=2, pixels_per_meter=100, name="Distance"):
        """
        Initialise une entité ligne pour les mesures de distance

        Args:
            start_point: QPointF du point de départ
            end_point: QPointF du point d'arrivée
            color: Couleur de la ligne
            width: Épaisseur de la ligne
            pixels_per_meter: Échelle de conversion pixels/mètres
            name: Nom de la mesure
        """
        super().__init__("line")
        self.start_point = start_point
        self.end_point = end_point
        self.color = color
        self.width = width
        self.pixels_per_meter = pixels_per_meter
        # NOTE: self.color peut être un QColor OU une str HexArgb après
        # un changement de couleur/opacité — toujours passer par _qcolor().

        # NOUVEAU: S'assurer qu'il y a toujours un nom valide
        self.name = name if name and name.strip() else "Distance"

        # Bulles visibles par défaut pour distance/échelle
        self.show_measure = True

        # Éléments graphiques
        self.line_item = None
        self.text_item = None
        self.text_bg = None
        self.scene_ref = None

        # Points d'ancrage pour l'édition
        self.start_anchor = None
        self.end_anchor = None
        self.is_editing = False

    def _qcolor(self):
        """Retourne toujours un QColor valide, même si self.color est une str."""
        from PyQt5.QtGui import QColor as _QColor
        c = self.color
        if isinstance(c, _QColor):
            return c
        if isinstance(c, str):
            return _QColor(c)
        return _QColor(30, 144, 255)   # bleu par défaut

    def set_color(self, color):
        """Accepte un QColor ou une str, normalise et stocke en QColor."""
        from PyQt5.QtGui import QColor as _QColor
        if isinstance(color, _QColor):
            self.color = _QColor(color)
        elif isinstance(color, str):
            self.color = _QColor(color)
        else:
            self.color = _QColor(30, 144, 255)

    def notify_entity_manager(self):
        """Notifier les modifications"""
        super().notify_entity_manager()

    # Dans les méthodes de modification :
    def update_points(self, new_start, new_end):
        """Met à jour les points de la ligne et recalcule la distance"""
        self.start_point = new_start
        self.end_point = new_end

        # Redessiner si la scène est disponible
        if self.scene_ref:
            self.draw(self.scene_ref)

        # Émettre le signal de changement
        self.geometryChanged.emit()
        self.notify_entity_manager()

    def calculate_length(self):
        """Calcule la longueur en mètres"""
        dx = self.end_point.x() - self.start_point.x()
        dy = self.end_point.y() - self.start_point.y()
        distance_px = (dx**2 + dy**2) ** 0.5
        return distance_px / self.pixels_per_meter

    def get_length_text(self):
        """Retourne le texte de la longueur formaté"""
        length = self.calculate_length()
        if length < 1:
            return f"{length * 100:.2f} cm"  # Conversion en cm
        else:
            return f"{length:.2f} m"

    def draw(self, scene):
        """Dessine la ligne sur la scène"""
        self.scene_ref = scene

        # Créer ou mettre à jour la ligne avec QLineF
        line = QLineF(self.start_point, self.end_point)

        if not self.line_item:
            self.line_item = QGraphicsLineItem(line)
            scene.addItem(self.line_item)
        else:
            self.line_item.setLine(line)

        # ✅ NOUVEAU: Épaisseur de ligne scalée
        scaled_width = self.get_scaled_pen_width(self.width)
        _lpen = QPen(self._qcolor(), scaled_width)
        _lpen.setCapStyle(Qt.FlatCap)
        self.line_item.setPen(_lpen)
        self.line_item.setData(0, "line_entity")
        if hasattr(self, 'entity_id'):
            self.line_item.setData(1, self.entity_id)

        # Configurer les flags pour permettre la sélection
        self.line_item.setFlag(QGraphicsLineItem.ItemIsSelectable, True)
        self.line_item.setFlag(QGraphicsLineItem.ItemIsFocusable, True)
        self.line_item.setAcceptHoverEvents(True)

        # Connecter le clic simple ET laisser passer le clic droit
        self.line_item.mousePressEvent = self.mousePressEvent
        self.line_item.mouseDoubleClickEvent = self.mouseDoubleClickEvent

        # Dessiner le texte
        self.draw_text(scene)

        # Si en mode édition, créer les points d'ancrage
        if self.is_editing:
            self.create_anchor_points(scene)

    def mouseDoubleClickEvent(self, event):
        """Gère le double-clic sur la ligne"""
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

    def mousePressEvent(self, event):
        """Gère le clic sur la ligne"""
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


            # Forcer la désélection des autres entités
            if self.scene_ref:
                try:
                    self.scene_ref.clearSelection()
                    # Désélectionner toutes les entités dans le manager
                    if hasattr(self.scene_ref, 'views') and self.scene_ref.views():
                        canvas_view = self.scene_ref.views()[0]
                        if hasattr(canvas_view, 'entity_manager'):
                            for other_entity in canvas_view.entity_manager.get_all_entities():
                                if other_entity != self and hasattr(other_entity, 'set_selected'):
                                    try:
                                        other_entity.set_selected(False)
                                    except Exception:
                                        pass
                except Exception as e:
                    pass

            # Sélectionner cette ligne
            if self.line_item:
                self.line_item.setSelected(True)
            self.set_selected(True)

            # Émettre le signal entityClicked
            try:
                self.entityClicked.emit(self)
            except Exception as e:
                pass

            event.accept()

        # NOUVEAU: Laisser passer le clic droit pour permettre le déplacement
        elif event.button() == Qt.RightButton:
            # Ne pas accepter l'événement pour qu'il remonte à la vue
            event.ignore()
            return

        else:
            # Laisser le traitement par défaut
            if hasattr(super(), 'mousePressEvent'):
                super().mousePressEvent(event)

    def draw_text(self, scene):
        """Dessine le texte de distance"""
        # Supprimer les anciens éléments texte
        if self.text_item and scene:
            scene.removeItem(self.text_item)
        if self.text_bg and scene:
            scene.removeItem(self.text_bg)

        # Si l'affichage des mesures est désactivé, ne rien recréer
        if hasattr(self, 'show_measure') and not self.show_measure:
            return

        # Calculer le milieu de la ligne
        mid_x = (self.start_point.x() + self.end_point.x()) / 2
        mid_y = (self.start_point.y() + self.end_point.y()) / 2

        # Créer le texte
        text = f"{self.name}\n{self.get_length_text()}"
        self.text_item = QGraphicsTextItem(text)
        
        # ✅ NOUVEAU: Appliquer un font scalé
        base_font = QFont("Arial", 10)
        if self.scale_manager:
            scaled_font = self.scale_manager.scale_font(base_font)
            self.text_item.setFont(scaled_font)
        else:
            self.text_item.setFont(base_font)

        # FORCER la couleur noire de multiple façons
        self.text_item.setDefaultTextColor(QColor(0, 0, 0))  # Noir pur RGB
        self.text_item.document().setDefaultStyleSheet("color: black !important;")
        self.text_item.setOpacity(1.0)  # Opacité maximale

        # AJOUTER LES FLAGS DE SÉLECTION POUR LE TEXTE
        self.text_item.setFlag(QGraphicsTextItem.ItemIsSelectable, True)
        self.text_item.setFlag(QGraphicsTextItem.ItemIsFocusable, True)
        self.text_item.setAcceptHoverEvents(True)

        # STOCKER L'ID DE L'ENTITÉ DANS LE TEXTE
        self.text_item.setData(0, "distance_text")
        if hasattr(self, 'entity_id'):
            self.text_item.setData(1, self.entity_id)

        scene.addItem(self.text_item)

        # Créer l'arrière-plan du texte avec padding scalé
        text_rect = self.text_item.boundingRect()
        margin = self.get_scaled_padding(2)  # ✅ Scalé automatiquement
        self.text_bg = scene.addRect(
            text_rect.adjusted(-margin, -margin, margin, margin),
            QPen(Qt.black),
            QBrush(QColor(255, 255, 255, 200))
        )

        # AJOUTER LES FLAGS DE SÉLECTION POUR LE FOND DU TEXTE
        self.text_bg.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
        self.text_bg.setFlag(QGraphicsRectItem.ItemIsFocusable, True)
        self.text_bg.setAcceptHoverEvents(True)

        # STOCKER L'ID DE L'ENTITÉ DANS LE FOND DU TEXTE
        self.text_bg.setData(0, "distance_text_bg")
        if hasattr(self, 'entity_id'):
            self.text_bg.setData(1, self.entity_id)

        # Positionner le texte et gérer l'ordre d'empilement
        self.text_item.setPos(mid_x - text_rect.width()/2,
                              mid_y - text_rect.height()/2)
        self.text_bg.setPos(mid_x - text_rect.width()/2,
                            mid_y - text_rect.height()/2)

        # S'assurer que le texte est bien visible
        self.text_item.setZValue(1000)
        self.text_bg.setZValue(999)

    def delete(self, scene):
        """Supprime la ligne de la scène"""
        self.disable_editing(scene)
        if self.line_item:
            scene.removeItem(self.line_item)
        if self.text_item:
            scene.removeItem(self.text_item)
        if self.text_bg:
            scene.removeItem(self.text_bg)

    def remove_from_scene(self, scene):
        """Supprime la ligne de la scène (alias pour delete)"""
        self.delete(scene)

    def to_dict(self):
        """Convertit l'entité en dictionnaire pour la sérialisation"""
        return {
            "type": "line",
            "start_point": (self.start_point.x(), self.start_point.y()),
            "end_point": (self.end_point.x(), self.end_point.y()),
            "color": (self._qcolor().red(), self._qcolor().green(), self._qcolor().blue(), self._qcolor().alpha()),
            "width": self.width,
            "pixels_per_meter": self.pixels_per_meter,
            "name": self.name,
            "show_measure": getattr(self, "show_measure", False),
            "visible": self.visible,
            "selected": self.selected,
            "entity_id": self.entity_id
        }

    @classmethod
    def from_dict(cls, data):
        """Crée une entité à partir d'un dictionnaire"""
        start_point = QPointF(data["start_point"][0], data["start_point"][1])
        end_point = QPointF(data["end_point"][0], data["end_point"][1])
        entity = cls(start_point, end_point)

        # Définir les propriétés supplémentaires
        entity.color = QColor(*data["color"])
        entity.width = data["width"]
        entity.show_measure = data.get("show_measure", True)
        entity.pixels_per_meter = data["pixels_per_meter"]
        entity.name = data["name"]
        entity.visible = data["visible"]
        entity.selected = data["selected"]
        entity.entity_id = data["entity_id"]

        return entity

    def move_by(self, dx, dy):
        """Déplace l'entité par le déplacement spécifié"""
        # Déplacer les points de départ et d'arrivée
        self.start_point = QPointF(
            self.start_point.x() + dx, self.start_point.y() + dy)
        self.end_point = QPointF(
            self.end_point.x() + dx, self.end_point.y() + dy)

        # Mettre à jour l'affichage avec QLineF
        if self.line_item:
            self.line_item.setLine(QLineF(self.start_point, self.end_point))

        # Mettre à jour les points d'ancrage si en mode édition
        if self.is_editing:
            if self.start_anchor:
                self.start_anchor.setPos(self.start_point)
            if self.end_anchor:
                self.end_anchor.setPos(self.end_point)

        # Mettre à jour le texte
        if self.scene_ref:
            self.draw_text(self.scene_ref)

        # Émettre le signal de modification
        self.geometryChanged.emit()

    def enable_editing(self, scene):
        """Active le mode édition pour la ligne"""
        if self.is_editing:
            return

        self.is_editing = True
        self.scene_ref = scene

        # ✅ CORRECTION CRITIQUE: Désactiver COMPLÈTEMENT la ligne
        if self.line_item:
            # Désactiver TOUS les événements
            self.line_item.setAcceptedMouseButtons(Qt.NoButton)
            self.line_item.setAcceptHoverEvents(False)
            self.line_item.setFlag(QGraphicsLineItem.ItemIsSelectable, False)
            self.line_item.setFlag(QGraphicsLineItem.ItemIsFocusable, False)
            
            # ✅ CRUCIAL: Désactiver pour qu'elle n'intercepte RIEN
            self.line_item.setEnabled(False)
            
            # Z-value BAS (handles à 10000)
            self.line_item.setZValue(50)
            
            # Semi-transparent pour indiquer mode édition
            self.line_item.setOpacity(0.5)
            

        self.create_anchor_points(scene)

        # Event filter pour ESC
        if scene and scene.views():
            view = scene.views()[0]
            view.installEventFilter(self)


    def disable_editing(self, scene):
        """Désactive le mode édition pour la ligne"""
        if not self.is_editing:
            return

        self.is_editing = False

        # ✅ Réactiver la ligne
        if self.line_item:
            self.line_item.setAcceptedMouseButtons(Qt.AllButtons)
            self.line_item.setAcceptHoverEvents(True)
            self.line_item.setFlag(QGraphicsLineItem.ItemIsSelectable, True)
            self.line_item.setFlag(QGraphicsLineItem.ItemIsFocusable, True)
            self.line_item.setEnabled(True)
            self.line_item.setZValue(100)
            self.line_item.setOpacity(0.7)  # Opacité par défaut
            

        self.remove_anchor_points(scene)

        # Retirer event filter
        if scene and scene.views():
            view = scene.views()[0]
            view.removeEventFilter(self)


    def eventFilter(self, obj, event):
        """Filtrer les événements pour capturer la touche Escape"""
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.disable_editing(self.scene_ref)
            return True
        return super().eventFilter(obj, event)

    def create_anchor_points(self, scene):
        """Crée les points d'ancrage aux extrémités de la ligne"""
        self.remove_anchor_points(scene)

        # Point de départ
        self.start_anchor = LineAnchorPoint(
            self.start_point.x(), self.start_point.y(), True, self)
        scene.addItem(self.start_anchor)
        self.start_anchor.setZValue(10000)
        self.start_anchor.show()
        self.start_anchor.setEnabled(True)

        # Point d'arrivée
        self.end_anchor = LineAnchorPoint(
            self.end_point.x(), self.end_point.y(), False, self)
        scene.addItem(self.end_anchor)
        self.end_anchor.setZValue(10000)
        self.end_anchor.show()
        self.end_anchor.setEnabled(True)

    def remove_anchor_points(self, scene):
        """Supprime tous les points d'ancrage"""
        if self.start_anchor and scene and self.start_anchor in scene.items():
            scene.removeItem(self.start_anchor)
        if self.end_anchor and scene and self.end_anchor in scene.items():
            scene.removeItem(self.end_anchor)

        self.start_anchor = None
        self.end_anchor = None

    def deselect_all_anchors_except(self, except_anchor=None):
        """Désélectionne tous les points d'ancrage sauf celui spécifié"""
        if self.start_anchor and self.start_anchor != except_anchor:
            self.start_anchor.setSelected(False)
        if self.end_anchor and self.end_anchor != except_anchor:
            self.end_anchor.setSelected(False)

    def on_anchor_moved(self, is_start_point, new_pos):
        """Callback lorsqu'un point d'ancrage est déplacé"""

        # Mettre à jour le point correspondant
        if is_start_point:
            self.start_point = new_pos
        else:
            self.end_point = new_pos

        # Mettre à jour l'affichage de la ligne avec QLineF
        if self.line_item:
            self.line_item.setLine(QLineF(self.start_point, self.end_point))

        # Mettre à jour le texte (calcul en temps réel)
        if self.scene_ref:
            self.draw_text(self.scene_ref)

        # Émettre le signal de modification
        self.geometryChanged.emit()

    def update_pixels_per_meter(self, new_pixels_per_meter):
        """Met à jour l'échelle pixels/mètres"""
        self.pixels_per_meter = new_pixels_per_meter
        if self.scene_ref:
            self.draw_text(self.scene_ref)
