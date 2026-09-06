# core/scale_manager.py
"""
Gestionnaire d'échelle automatique pour adapter tous les éléments graphiques
à la taille du plan chargé.
"""
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFont, QPen


class ScaleManager(QObject):
    """
    Gestionnaire central pour l'échelle automatique des éléments graphiques.
    
    Calcule un ratio d'échelle basé sur la taille de l'image chargée et
    fournit des méthodes pour scaler tous les éléments graphiques de manière cohérente.
    """
    
    # Signal émis quand l'échelle change
    scale_changed = pyqtSignal(float)  # nouveau scale_factor
    
    def __init__(self):
        super().__init__()
        
        # Dimensions de référence (plan "standard" de référence)
        # Ces valeurs servent de base pour l'échelle 1.0
        # ✅ AJUSTÉ : Référence basée sur une image de taille moyenne-grande
        # pour que les petites images aient des bulles vraiment petites
        self.reference_width = 3500  # pixels (au lieu de 2000)
        self.reference_height = 2500  # pixels (au lieu de 1500)
        
        # Échelle actuelle
        self._scale_factor = 1.0
        
        # Dimensions actuelles du plan
        self.current_width = 0
        self.current_height = 0
        
        # Limites d'échelle resserrées : évite les bulles géantes sur petits plans
        # et les bulles illisibles sur très grands plans
        self.min_scale = 0.6
        self.max_scale = 1.3
        
        # Facteurs de correction par type d'élément
        # Ces facteurs permettent d'ajuster finement chaque type d'élément
        self.font_scale_factor = 1.15  # +15% pour améliorer la lisibilité sur grandes images
        self.pen_scale_factor = 1.0
        self.icon_scale_factor = 1.0
        self.bubble_scale_factor = 1.15  # +15% pour bulles plus lisibles sur grandes images
        # Contrôle de verbosité des logs d'échelle
        self.verbose = False
    
    @property
    def scale_factor(self):
        """Retourne le facteur d'échelle actuel"""
        return self._scale_factor
    
    def calculate_scale_from_image(self, image_width, image_height):
        """
        Calcule le facteur d'échelle basé sur les dimensions de l'image.
        
        Args:
            image_width: Largeur de l'image en pixels
            image_height: Hauteur de l'image en pixels
        
        Returns:
            float: Facteur d'échelle calculé
        """
        if image_width <= 0 or image_height <= 0:
            return 1.0
        
        # Stocker les dimensions actuelles
        self.current_width = image_width
        self.current_height = image_height
        
        # Calculer le ratio : INVERSE pour que les grandes images = bulles plus petites
        # image > référence → scale < 1 (bulles réduites) ; image < référence → scale > 1
        width_ratio = self.reference_width / image_width
        height_ratio = self.reference_height / image_height
        
        # Moyenne géométrique pour un équilibre
        scale = (width_ratio * height_ratio) ** 0.5
        
        # Appliquer les limites
        scale = max(self.min_scale, min(self.max_scale, scale))
        
        return scale
    
    def set_scale_from_image(self, image_width, image_height):
        """
        Définit l'échelle basée sur les dimensions de l'image et émet le signal.
        
        Args:
            image_width: Largeur de l'image en pixels
            image_height: Hauteur de l'image en pixels
        """
        old_scale = self._scale_factor
        new_scale = self.calculate_scale_from_image(image_width, image_height)
        
        if self.verbose:
            pass
        
        if new_scale != old_scale:
            self._scale_factor = new_scale
            self.scale_changed.emit(new_scale)
            if self.verbose:
                pass
        else:
            if self.verbose:
                pass
        if self.verbose:
            pass
    
    def set_manual_scale(self, scale):
        """
        Définit manuellement le facteur d'échelle.
        
        Args:
            scale: Facteur d'échelle (ex: 1.0 = normal, 0.5 = réduit de moitié)
        """
        scale = max(self.min_scale, min(self.max_scale, scale))
        if scale != self._scale_factor:
            self._scale_factor = scale
            self.scale_changed.emit(scale)
    
    # =========================================================================
    # MÉTHODES DE SCALING PAR TYPE D'ÉLÉMENT
    # =========================================================================
    
    def scale_font_size(self, base_size, verbose: bool = None):
        """
        Scale une taille de police dans la plage [min_scale, max_scale].
        """
        effective_scale = self._scale_factor * self.font_scale_factor
        scaled = int(base_size * effective_scale)
        result = max(6, scaled)  # Minimum 6pt pour lisibilité grands plans
        if verbose is None:
            verbose = self.verbose
        if verbose:
            pass
        return result
    
    def scale_font(self, font, verbose: bool = None):
        """
        Scale un objet QFont.
        
        Args:
            font: QFont à scaler
        
        Returns:
            QFont: Nouveau font scalé
        """
        scaled_font = QFont(font)
        base_size = font.pointSize() if font.pointSize() > 0 else 10
        scaled_size = self.scale_font_size(base_size, verbose=verbose)
        scaled_font.setPointSize(scaled_size)
        return scaled_font
    
    def scale_pen_width(self, base_width, verbose: bool = None):
        """
        Scale une épaisseur de ligne.
        
        Args:
            base_width: Épaisseur de base en pixels
        
        Returns:
            float: Épaisseur scalée
        """
        scaled = base_width * self._scale_factor * self.pen_scale_factor
        result = max(1.0, scaled)  # Minimum 1px
        if verbose is None:
            verbose = self.verbose
        if verbose:
            pass
        return result
    
    def scale_pen(self, pen):
        """
        Scale un objet QPen.
        
        Args:
            pen: QPen à scaler
        
        Returns:
            QPen: Nouveau pen scalé
        """
        scaled_pen = QPen(pen)
        base_width = pen.widthF()
        scaled_width = self.scale_pen_width(base_width)
        scaled_pen.setWidthF(scaled_width)
        return scaled_pen
    
    def scale_size(self, base_size, verbose: bool = None):
        """
        Scale une dimension générique (icône, bulle, etc.).
        
        Args:
            base_size: Taille de base en pixels
        
        Returns:
            float: Taille scalée
        """
        result = base_size * self._scale_factor * self.icon_scale_factor
        if verbose is None:
            verbose = self.verbose
        if verbose:
            pass
        return result
    
    def scale_bubble_padding(self, base_padding, verbose: bool = None):
        """
        Scale le padding d'une bulle de texte dans la plage [min_scale, max_scale].
        """
        effective_scale = self._scale_factor * self.bubble_scale_factor
        scaled = int(base_padding * effective_scale)
        result = max(2, scaled)  # Minimum 2px pour lisibilité grands plans
        if verbose is None:
            verbose = self.verbose
        if verbose:
            pass
        return result
    
    def scale_bubble_offset(self, base_offset, verbose: bool = None):
        """
        Scale l'offset/décalage d'une bulle par rapport à sa position.
        """
        effective_scale = self._scale_factor * self.bubble_scale_factor
        result = base_offset * effective_scale
        if verbose is None:
            verbose = self.verbose
        if verbose:
            pass
        return result
    
    def scale_anchor_size(self, base_size):
        """
        Scale la taille des points d'ancrage (handles).
        
        Args:
            base_size: Taille de base en pixels
        
        Returns:
            float: Taille scalée
        """
        return base_size * self._scale_factor * self.icon_scale_factor
    
    # =========================================================================
    # MÉTHODES UTILITAIRES
    # =========================================================================
    
    def get_scale_info(self):
        """
        Retourne les informations sur l'échelle actuelle.
        
        Returns:
            dict: Informations d'échelle
        """
        return {
            'scale_factor': self._scale_factor,
            'current_width': self.current_width,
            'current_height': self.current_height,
            'reference_width': self.reference_width,
            'reference_height': self.reference_height,
            'font_scale': self.font_scale_factor,
            'pen_scale': self.pen_scale_factor,
            'icon_scale': self.icon_scale_factor,
            'bubble_scale': self.bubble_scale_factor
        }
    
    def reset_scale(self):
        """Réinitialise l'échelle à 1.0"""
        if self._scale_factor != 1.0:
            self._scale_factor = 1.0
            self.scale_changed.emit(1.0)
    
    def set_reference_dimensions(self, width, height):
        """
        Définit les dimensions de référence.
        
        Args:
            width: Largeur de référence
            height: Hauteur de référence
        """
        self.reference_width = width
        self.reference_height = height
        
        # Recalculer l'échelle si une image est chargée
        if self.current_width > 0 and self.current_height > 0:
            self.set_scale_from_image(self.current_width, self.current_height)
    
    def adjust_font_scale_factor(self, factor):
        """
        Ajuste le facteur de correction pour les polices.
        
        Args:
            factor: Facteur multiplicateur (1.0 = normal, 1.2 = 20% plus grand)
        """
        self.font_scale_factor = max(0.5, min(2.0, factor))
    
    def adjust_pen_scale_factor(self, factor):
        """
        Ajuste le facteur de correction pour les lignes.
        
        Args:
            factor: Facteur multiplicateur
        """
        self.pen_scale_factor = max(0.5, min(2.0, factor))
    
    def adjust_bubble_scale_factor(self, factor):
        """
        Ajuste le facteur de correction pour les bulles.
        
        Args:
            factor: Facteur multiplicateur
        """
        self.bubble_scale_factor = max(0.5, min(2.0, factor))

