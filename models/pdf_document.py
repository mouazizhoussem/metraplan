"""
Modèles de données pour représenter les documents PDF.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import copy

from PyQt5.QtGui import QPixmap


@dataclass
class PDFPage:
    page_index: int
    name: str = ""
    pixmap: Optional[QPixmap] = None          # Haute résolution (300 DPI)
    pixmap_low: Optional[QPixmap] = None      # Basse résolution (100 DPI, vue page complète)
    thumbnail: Optional[QPixmap] = None
    entities_data: List[Dict[str, Any]] = field(default_factory=list)
    pixels_per_meter: float = 100.0
    scale_calibrated: bool = False   # True uniquement après calibration manuelle

    def set_pixmaps(self, pixmap: QPixmap,
                    thumbnail: QPixmap,
                    pixmap_low: Optional[QPixmap] = None):
        self.pixmap = pixmap
        self.thumbnail = thumbnail
        self.pixmap_low = pixmap_low

    def clone(self, new_index: int, include_measures: bool = True) -> "PDFPage":
        new_page = PDFPage(page_index=new_index, name=self.name)
        if self.pixmap:
            new_page.pixmap = self.pixmap.copy()
        if self.pixmap_low:
            new_page.pixmap_low = self.pixmap_low.copy()
        if self.thumbnail:
            new_page.thumbnail = self.thumbnail.copy()
        new_page.pixels_per_meter  = self.pixels_per_meter
        new_page.scale_calibrated  = self.scale_calibrated
        if include_measures:
            new_page.entities_data = copy.deepcopy(self.entities_data)
        return new_page

    def save_entities(self, entities: List[object]):
        data = []
        for ent in entities:
            if hasattr(ent, "to_dict"):
                try:
                    data.append(ent.to_dict())
                except Exception:
                    continue
        self.entities_data = data

    def create_entities(self) -> List[object]:
        entities = []
        for data in self.entities_data:
            ent = create_entity_from_dict(data)
            if ent:
                entities.append(ent)
        return entities


class PDFDocument:
    def __init__(self, file_path: str, total_pages: int):
        self.file_path = file_path
        self.pages: List[Optional[PDFPage]] = [None] * total_pages
        self.current_page_index = 0

    def add_page(self, page: PDFPage):
        if 0 <= page.page_index < len(self.pages):
            self.pages[page.page_index] = page

    def get_page(self, index: int) -> Optional[PDFPage]:
        if 0 <= index < len(self.pages):
            return self.pages[index]
        return None

    def page_count(self) -> int:
        return len(self.pages)

    def set_current_page(self, index: int):
        if 0 <= index < len(self.pages):
            self.current_page_index = index

    def get_current_page(self) -> Optional[PDFPage]:
        return self.get_page(self.current_page_index)

    def normalize_pages(self):
        """Supprime les pages None et réindexe."""
        pages = [p for p in self.pages if p is not None]
        for idx, page in enumerate(pages):
            page.page_index = idx
            if not page.name:
                page.name = f"Page {idx + 1}"
        self.pages = pages

    def insert_page(self, index: int, page: PDFPage):
        if index < 0:
            index = 0
        if index > len(self.pages):
            index = len(self.pages)
        self.pages.insert(index, page)
        self.normalize_pages()

    def remove_page(self, index: int):
        if 0 <= index < len(self.pages):
            self.pages.pop(index)
            self.normalize_pages()


def create_entity_from_dict(data: Dict[str, Any]) -> Optional[object]:
    if not data:
        return None
    # Accepter les clés 'type' et 'entity_type' pour la compatibilité
    entity_type = data.get("type") or data.get("entity_type")
    if not entity_type:
        return None

    # Imports locaux pour éviter les cycles
    from entities.polygon_entity import PolygonEntity
    from entities.perimeter_entity import PerimeterEntity
    from entities.line_entity import LineEntity
    from entities.point_entity import PointEntity
    from entities.opening_entity import OpeningEntity
    from entities.marker_entity import MarkerEntity

    mapping = {
        "polygon": PolygonEntity,
        "perimeter": PerimeterEntity,
        "line": LineEntity,
        "point": PointEntity,
        "opening": OpeningEntity,
        "marker": MarkerEntity,
    }

    cls = mapping.get(entity_type)
    if not cls or not hasattr(cls, "from_dict"):
        return None

    try:
        return cls.from_dict(data)
    except Exception:
        return None
