from PyQt5.QtCore import QPointF

class BaseTool:
    def __init__(self, canvas):
        self.canvas = canvas
        self.is_active = False
    
    def activate(self):
        """Active l'outil"""
        self.is_active = True
    
    def deactivate(self):
        """Désactive l'outil"""
        self.is_active = False
    
    def mouse_press(self, event, pos):
        """Gère les clics de souris - à surcharger"""
        return False
    
    def mouse_move(self, event, pos):
        """Gère les mouvements de souris - à surcharger"""
        return False
    
    def cancel(self):
        """Annule l'outil"""
        self.is_active = False
        self.canvas.mode = "idle"

    # ------------------------------------------------------------------
    # Contrat commun pour pilotage par menu contextuel / ToolManager
    # ------------------------------------------------------------------
    def finish_current(self):
        """Finalise l'opération en cours de l'outil (si applicable)."""
        return False

    def undo_last_point(self):
        """Annule le dernier point saisi (si applicable)."""
        return False

    def toggle_drawing_mode(self):
        """Bascule le mode de dessin de l'outil (si applicable)."""
        return False

    def reset_measure(self):
        """Réinitialise une mesure en cours (si applicable)."""
        return False

    def persist_last_measure(self):
        """Conserve explicitement la dernière mesure (si applicable)."""
        return False

    def get_point_count(self):
        """Retourne le nombre de points courants manipulés par l'outil."""
        points = getattr(self, "points", None)
        if isinstance(points, list):
            return len(points)
        return 0

    def is_drawing_in_progress(self):
        """Indique si l'outil est en cours d'édition/dessin."""
        return self.get_point_count() > 0