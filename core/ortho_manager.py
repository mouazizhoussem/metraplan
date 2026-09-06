# core/ortho_manager.py
from PyQt5.QtCore import QPointF


class OrthoManager:
    def __init__(self):
        self.ortho_enabled = False
        self.ortho_threshold = 5  # Seuil en pixels pour éviter les oscillations

    def is_ortho_enabled(self):
        return self.ortho_enabled

    def set_ortho_enabled(self, enabled):
        self.ortho_enabled = enabled

    def toggle_ortho(self):
        """Active/désactive le mode ortho et retourne le nouvel état"""
        self.ortho_enabled = not self.ortho_enabled
        return self.ortho_enabled

    def toggle_ortho_mode(self):
        """Alias pour toggle_ortho (compatibilité)"""
        return self.toggle_ortho()

    def constrain_to_axis(self, reference_point, current_point):
        """Contraint le point courant à l'axe X ou Y par rapport au point de référence"""
        if not self.ortho_enabled:
            return current_point

        delta_x = abs(current_point.x() - reference_point.x())
        delta_y = abs(current_point.y() - reference_point.y())

        # Appliquer un seuil pour éviter les oscillations
        if abs(delta_x - delta_y) < self.ortho_threshold:
            return current_point

        # Déterminer l'axe dominant
        if delta_x > delta_y:
            # Mouvement horizontal dominant - contraindre à l'axe Y
            return QPointF(current_point.x(), reference_point.y())
        else:
            # Mouvement vertical dominant - contraindre à l'axe X
            return QPointF(reference_point.x(), current_point.y())
