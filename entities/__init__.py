"""
Module entities - Représentation des formes graphiques comme objets métiers
"""

from .base_entity import BaseEntity
from .point_entity import PointEntity
from .line_entity import LineEntity
from .polygon_entity import PolygonEntity

__all__ = [
    'BaseEntity',
    'PointEntity', 
    'LineEntity',
    'PolygonEntity'
]