# entities/base_entity.py
from PyQt5.QtCore import QObject, pyqtSignal
from abc import ABC, abstractmethod
from PyQt5.QtGui import QColor
from core.app_logger import get_logger
_log = get_logger(__name__)


class QObjectABCMeta(type(QObject), type(ABC)):
    pass


class BaseEntity(QObject, ABC, metaclass=QObjectABCMeta):
    # Signal émis lorsque l'entité est modifiée
    geometryChanged = pyqtSignal()

    def __init__(self, entity_type):
        # CORRECT: Utiliser super() pour l'héritage multiple
        super().__init__()
        self.entity_type = entity_type
        self.entity_id = None
        self.name = "Unnamed"
        self.visible = True
        self.selected = False
        # Par défaut, les bulles/mesures sont masquées.
        # L'utilisateur les active explicitement depuis le panneau Propriétés.
        self.show_measure = False
        # IMPORTANT: Stocker la couleur comme string avec alpha (format #AARRGGBB)
        self.color = QColor(0, 0, 255, 178).name(QColor.HexArgb)  # 70% opacité par défaut
        self.scale_manager = None

    def notify_entity_manager(self):
        """Méthode à implémenter par les classes dérivées pour notifier les modifications"""
        # Implémentation par défaut - les classes dérivées doivent surcharger
        try:
            if hasattr(self, 'scene_ref') and self.scene_ref:
                # CORRIGER: Protection complète de l'accès à views()
                if hasattr(self.scene_ref, 'views'):
                    try:
                        views = self.scene_ref.views()
                        if views and len(views) > 0:
                            canvas_view = views[0]
                            if (canvas_view and
                                hasattr(canvas_view, 'entity_manager') and
                                    canvas_view.entity_manager):
                                if hasattr(canvas_view.entity_manager, 'notify_entity_modified'):
                                    canvas_view.entity_manager.notify_entity_modified(
                                        self)
                    except (AttributeError, IndexError, TypeError) as e:
                        _log.warning(f"Erreur notify_entity_manager (views): {e}")
        except Exception as e:
            _log.warning(f"Erreur inattendue notify_entity_manager: {e}")

    @abstractmethod
    def draw(self, scene):
        """Dessine l'entité sur la scène"""
        pass

    @abstractmethod
    def delete(self, scene):
        """Supprime l'entité de la scène"""
        pass

    def remove_from_scene(self, scene):
        """Supprime l'entité de la scène (alias pour delete)"""
        # CORRIGER: Protection avant appel à delete
        if scene and hasattr(self, 'delete'):
            try:
                self.delete(scene)
            except Exception as e:
                _log.warning(f"Erreur remove_from_scene: {e}")

    def get_properties(self):
        """Retourne les propriétés de l'entité sous forme de dictionnaire"""
        try:
            # CORRIGER: Protection de l'accès à color (maintenant string avec alpha)
            color_tuple = (0, 0, 255, 178)  # Valeur par défaut (70% opacité)
            if self.color:
                try:
                    # Convertir string en QColor si nécessaire
                    qcolor = QColor(self.color) if isinstance(self.color, str) else self.color
                    if qcolor.isValid():
                        color_tuple = (qcolor.red(),
                                       qcolor.green(),
                                       qcolor.blue(),
                                       qcolor.alpha())
                except (AttributeError, RuntimeError) as e:
                    _log.warning(f"Erreur lecture couleur: {e}")

            return {
                "type": self.entity_type,
                "id": self.entity_id,
                "name": self.name,
                "visible": self.visible,
                "selected": self.selected,
                "color": color_tuple
            }
        except Exception as e:
            _log.warning(f"Erreur get_properties: {e}")
            # Retourner un dictionnaire minimal en cas d'erreur
            return {
                "type": getattr(self, 'entity_type', 'unknown'),
                "id": getattr(self, 'entity_id', None),
                "name": getattr(self, 'name', 'Unnamed'),
                "visible": getattr(self, 'visible', True),
                "selected": getattr(self, 'selected', False),
                "color": (0, 0, 255, 255)
            }

    def set_properties(self, properties):
        """Définit les propriétés de l'entité à partir d'un dictionnaire"""
        if not isinstance(properties, dict):
            _log.warning(f"Erreur set_properties: properties doit être un dictionnaire")
            return

        try:
            if "name" in properties:
                self.name = properties["name"]
            if "visible" in properties:
                self.visible = properties["visible"]
            if "selected" in properties:
                self.selected = properties["selected"]
            if "color" in properties:
                # CORRIGER: Protection de la création de QColor et stockage comme string avec alpha
                color_data = properties["color"]
                try:
                    qcolor = None
                    if isinstance(color_data, (list, tuple)) and len(color_data) >= 3:
                        # Format (R, G, B) ou (R, G, B, A)
                        if len(color_data) == 4:
                            qcolor = QColor(
                                color_data[0], color_data[1], color_data[2], color_data[3])
                        else:
                            qcolor = QColor(
                                color_data[0], color_data[1], color_data[2], 178)  # 70% par défaut
                    elif isinstance(color_data, str):
                        # Format hexadécimal "#RRGGBB" ou "#RRGGBBAA"
                        qcolor = QColor(color_data)
                    elif isinstance(color_data, QColor):
                        qcolor = color_data
                    else:
                        _log.warning(f"Format de couleur non supporté: {color_data}")
                        qcolor = QColor(0, 0, 255, 178)

                    # Vérifier que la couleur est valide
                    if not qcolor or not qcolor.isValid():
                        _log.info(f"Couleur invalide, utilisation de la valeur par défaut")
                        qcolor = QColor(0, 0, 255, 178)
                    
                    # IMPORTANT: Stocker comme string avec alpha
                    self.color = qcolor.name(QColor.HexArgb)
                except (ValueError, TypeError, AttributeError) as e:
                    _log.warning(f"Erreur création QColor: {e}")
                    self.color = QColor(0, 0, 255, 178).name(QColor.HexArgb)
        except Exception as e:
            _log.warning(f"Erreur set_properties: {e}")

    def emit_changed(self):
        """Émet le signal de modification"""
        try:
            # CORRIGER: Protection de l'émission du signal
            if hasattr(self, 'geometryChanged'):
                self.geometryChanged.emit()
        except (RuntimeError, AttributeError) as e:
            _log.warning(f"Erreur emit_changed: {e}")
        except Exception as e:
            _log.warning(f"Erreur inattendue emit_changed: {e}")

    @abstractmethod
    def to_dict(self):
        """Convertit l'entité en dictionnaire pour la sérialisation"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data):
        """Crée une entité à partir d'un dictionnaire"""
        pass

    def set_selected(self, selected):
        """Définit l'état de sélection de l'entité"""
        self.selected = selected
        # Mettre à jour l'apparence visuelle si nécessaire

    def is_selected(self):
        """Retourne True si l'entité est sélectionnée"""
        return self.selected

    def set_color(self, color):
        """Définit la couleur de l'entité (stockée comme string avec alpha)"""
        try:
            # Convertir en QColor si c'est une string
            if isinstance(color, str):
                qcolor = QColor(color)
            elif isinstance(color, QColor):
                qcolor = color
            else:
                qcolor = QColor(0, 0, 255)
            
            # Vérifier validité
            if not qcolor.isValid():
                qcolor = QColor(0, 0, 255)
            
            # IMPORTANT: Stocker comme string avec alpha (format #AARRGGBB)
            self.color = qcolor.name(QColor.HexArgb)

            # CORRIGER: Protection complète de l'accès à polygon_item
            if hasattr(self, 'polygon_item') and self.polygon_item:
                if hasattr(self.polygon_item, 'setPen'):
                    try:
                        # Créer un QPen si nécessaire
                        from PyQt5.QtGui import QPen
                        self.polygon_item.setPen(QPen(qcolor))
                    except (AttributeError, RuntimeError) as e:
                        _log.warning(f"Erreur setPen polygon_item: {e}")
        except Exception as e:
            _log.warning(f"Erreur set_color: {e}")

    def move_by(self, dx, dy):
        """Déplace l'entité par le déplacement spécifié"""
        # Implémentation par défaut, à surcharger dans les classes dérivées
        pass

    def rotate(self, angle, center):
        """Fait pivoter l'entité autour du centre spécifié"""
        # Implémentation par défaut, à surcharger dans les classes dérivées
        pass

    def scale(self, factor, center):
        """Redimensionne l'entité à partir du centre spécifié"""
        # Implémentation par défaut, à surcharger dans les classes dérivées
        pass
    
    # ✅ NOUVEAU: Méthodes helper pour l'échelle automatique
    
    def get_scaled_font_size(self, base_size):
        """
        Retourne une taille de police scalée selon l'échelle automatique.
        
        Args:
            base_size: Taille de base en points
        
        Returns:
            int: Taille scalée
        """
        if self.scale_manager:
            return self.scale_manager.scale_font_size(base_size)
        return base_size
    
    def get_scaled_font(self, base_font):
        """
        Retourne un QFont scalé selon l'échelle automatique.
        
        Args:
            base_font: QFont de base
        
        Returns:
            QFont: Font scalé
        """
        if self.scale_manager:
            return self.scale_manager.scale_font(base_font)
        return base_font
    
    def get_scaled_pen_width(self, base_width):
        """
        Retourne une épaisseur de ligne scalée.
        
        Args:
            base_width: Épaisseur de base
        
        Returns:
            float: Épaisseur scalée
        """
        if self.scale_manager:
            return self.scale_manager.scale_pen_width(base_width)
        return base_width
    
    def get_scaled_size(self, base_size):
        """
        Retourne une dimension scalée (pour icônes, bulles, etc.).
        
        Args:
            base_size: Taille de base
        
        Returns:
            float: Taille scalée
        """
        if self.scale_manager:
            return self.scale_manager.scale_size(base_size)
        return base_size
    
    def get_scaled_padding(self, base_padding):
        """
        Retourne un padding scalé pour les bulles de texte.
        
        Args:
            base_padding: Padding de base
        
        Returns:
            int: Padding scalé
        """
        if self.scale_manager:
            return self.scale_manager.scale_bubble_padding(base_padding)
        return base_padding
    
    def get_scaled_offset(self, base_offset):
        """
        Retourne un offset scalé pour le positionnement des bulles.
        
        Args:
            base_offset: Offset de base
        
        Returns:
            float: Offset scalé
        """
        if self.scale_manager:
            return self.scale_manager.scale_bubble_offset(base_offset)
        return base_offset