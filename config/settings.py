from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPen

# Couleurs par défaut
COLORS = {
    'surface_fill': QColor(0, 255, 0, 80),
    'surface_border': Qt.green,
    'distance_line': Qt.darkMagenta,
    'perimeter_line': Qt.darkYellow,
    'counter_circle': Qt.blue,
    'selection_highlight': Qt.red,
    'text_bg': QColor(255, 255, 255, 220),
    'text_color': Qt.black
}

# Styles de ligne
PENS = {
    'surface': QPen(COLORS['surface_border'], 2),
    'distance': QPen(COLORS['distance_line'], 2),
    'perimeter': QPen(COLORS['perimeter_line'], 2),
    'counter': QPen(COLORS['counter_circle'], 2),
    'selection': QPen(COLORS['selection_highlight'], 3),
    'temp_line': QPen(Qt.gray, 1, Qt.DashLine)
}

# Paramètres de l'interface
UI_SETTINGS = {
    'window_title': "Metraplan",
    'window_size': (1200, 800),
    'font_size': 10,
    'text_padding': 8,
    'counter_radius': 15,
    'point_radius': 3
}