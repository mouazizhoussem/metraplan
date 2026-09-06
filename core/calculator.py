import math
from PyQt5.QtCore import QPointF

class Calculator:
    def __init__(self):
        self.px_per_m = None  # Pixels per meter (échelle)

    def calculate_distance(self, point1, point2):
        """Calcule la distance entre deux points"""
        if isinstance(point1, QPointF) and isinstance(point2, QPointF):
            dx = point2.x() - point1.x()
            dy = point2.y() - point1.y()
            return math.sqrt(dx * dx + dy * dy)
        return 0

    def calculate_area(self, points):
        """Calcule l'aire d'un polygone using the shoelace formula"""
        if len(points) < 3:
            return 0
        
        area = 0
        n = len(points)
        
        for i in range(n):
            j = (i + 1) % n
            if isinstance(points[i], QPointF) and isinstance(points[j], QPointF):
                area += points[i].x() * points[j].y()
                area -= points[j].x() * points[i].y()
        
        return abs(area) / 2

    def calculate_perimeter(self, points):
        """Calcule le périmètre d'un polygone"""
        if len(points) < 2:
            return 0
        
        perimeter = 0
        for i in range(1, len(points)):
            perimeter += self.calculate_distance(points[i-1], points[i])
        
        return perimeter

    def set_scale(self, pixel_distance, real_distance_meters):
        """Définit l'échelle en pixels par mètre"""
        if real_distance_meters > 0:
            self.px_per_m = pixel_distance / real_distance_meters
            return True
        return False

    def pixels_to_meters(self, pixels):
        """Convertit les pixels en mètres"""
        if self.px_per_m:
            return pixels / self.px_per_m
        return pixels

    def format_distance(self, distance_pixels):
        """Formate une distance pour l'affichage"""
        if self.px_per_m:
            distance_m = self.pixels_to_meters(distance_pixels)
            return f"{distance_m:.2f} m"
        else:
            return f"{distance_pixels:.2f} px"

    def format_area(self, area_pixels):
        """Formate une aire pour l'affichage"""
        if self.px_per_m:
            area_m2 = area_pixels / (self.px_per_m ** 2)
            return f"{area_m2:.2f} m²"
        else:
            return f"{area_pixels:.2f} px²"