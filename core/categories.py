from PyQt5.QtGui import QColor
from collections import defaultdict

class CategoryManager:
    def __init__(self):
        self.categories = {
            'surface': {
                'name': 'Surface',
                'color': QColor(0, 255, 0, 80),
                'border_color': QColor(0, 255, 0),
                'objects': []
            },
            'opening': {
                'name': 'Ouverture',
                'color': QColor(255, 0, 0, 80),
                'border_color': QColor(255, 0, 0),
                'objects': []
            },
            'distance': {
                'name': 'Distance',
                'color': QColor(255, 0, 255),
                'border_color': QColor(255, 0, 255),
                'objects': []
            },
            'perimeter': {
                'name': 'Périmètre',
                'color': QColor(255, 255, 0),
                'border_color': QColor(255, 255, 0),
                'objects': []
            },
            'counter': {
                'name': 'Compteur',
                'color': QColor(0, 0, 255, 180),
                'border_color': QColor(0, 0, 255),
                'objects': []
            }
        }
        
        self.zones = ['Zone 1', 'Zone 2', 'Zone 3', 'Zone 4', 'Zone 5']
        self.current_zone = 'Zone 1'
        
        # Compteurs par type et par zone
        self.counters = defaultdict(lambda: defaultdict(int))

    def add_category(self, category_id, name, color, border_color):
        """Ajoute une nouvelle catégorie"""
        self.categories[category_id] = {
            'name': name,
            'color': color,
            'border_color': border_color,
            'objects': []
        }

    def get_category(self, category_id):
        """Récupère une catégorie"""
        return self.categories.get(category_id, None)

    def get_category_color(self, category_id):
        """Récupère la couleur d'une catégorie"""
        category = self.get_category(category_id)
        if category:
            return category['color']
        return QColor(128, 128, 128, 80)

    def get_category_border_color(self, category_id):
        """Récupère la couleur de bordure d'une catégorie"""
        category = self.get_category(category_id)
        if category:
            return category['border_color']
        return QColor(128, 128, 128)

    def add_object_to_category(self, category_id, obj):
        """Ajoute un objet à une catégorie"""
        if category_id in self.categories:
            self.categories[category_id]['objects'].append(obj)

    def get_category_objects(self, category_id):
        """Récupère tous les objets d'une catégorie"""
        category = self.get_category(category_id)
        if category:
            return category['objects']
        return []

    def set_current_zone(self, zone):
        """Définit la zone courante"""
        if zone in self.zones:
            self.current_zone = zone

    def get_current_zone(self):
        """Récupère la zone courante"""
        return self.current_zone

    def get_zones(self):
        """Récupère toutes les zones"""
        return self.zones

    def increment_counter(self, object_type, zone=None):
        """Incrémente le compteur pour un type d'objet dans une zone"""
        if zone is None:
            zone = self.current_zone
        self.counters[zone][object_type] += 1

    def get_counter(self, object_type, zone=None):
        """Récupère la valeur du compteur pour un type d'objet dans une zone"""
        if zone is None:
            zone = self.current_zone
        return self.counters[zone][object_type]