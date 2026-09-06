# ui/pdf_measurements_panel.py
"""
Panneau unifié "Pages PDF + Mesures" — style CAO compact.

Structure : 2 colonnes
  Col 0 : [icône] nom  (stretch)
  Col 1 : [quantité  💡]  widget collé au bord droit (largeur fixe)
"""
from __future__ import annotations

import math
from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import (
    QColor, QFont, QFontMetrics, QIcon, QPainter, QBrush, QPen, QPixmap,
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
    QPushButton, QLabel, QToolButton, QMenu, QFrame,
    QSizePolicy,
)

from models.pdf_document import PDFPage
from ui.icon_manager import IconManager


# ──────────────────────────────────────────────────────────────────────────
# Constantes layout
# ──────────────────────────────────────────────────────────────────────────
_THUMB_W   = 64
_THUMB_H   = 48
_COL1_W    = 130   # largeur fixe colonne droite [qty + bulb]
_ICON_SIZE = 16    # icône type entité

_COLOR_PAGE_ACTIVE   = QColor("#E3F2FD")
_COLOR_PAGE_INACTIVE = QColor("#F5F5F5")
_COLOR_QTY_GROUP     = QColor("#1A237E")
_COLOR_QTY           = QColor("#1565C0")
_COLOR_ENTITY_NAME   = QColor("#37474F")
_COLOR_SAVED         = QColor("#90A4AE")


# ──────────────────────────────────────────────────────────────────────────
# Icônes de type
# ──────────────────────────────────────────────────────────────────────────

def _entity_color(entity) -> QColor:
    """Retourne la couleur réelle de l'entité (attr .color en #AARRGGBB ou #RRGGBB)."""
    raw = getattr(entity, "color", None)
    if raw:
        try:
            c = QColor(raw)
            if c.isValid():
                # On force alpha = 200 pour un rendu opaque mais visible
                c.setAlpha(200)
                return c
        except Exception:
            pass
    return QColor(21, 101, 192, 200)   # bleu par défaut


# ──────────────────────────────────────────────────────────────────────────
# Icônes barre d'outils du panneau
# ──────────────────────────────────────────────────────────────────────────

def _icon_add_page(size: int = 18) -> QIcon:
    """Page blanche avec badge '+' vert en bas-droite."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    # Corps de la page (rectangle arrondi gris clair)
    p.setPen(QPen(QColor("#78909C"), 1.2))
    p.setBrush(QBrush(QColor("#ECEFF1")))
    p.drawRoundedRect(1, 1, size - 6, size - 2, 2, 2)
    # Lignes de texte simulées
    p.setPen(QPen(QColor("#B0BEC5"), 1))
    for y in range(5, size - 5, 3):
        p.drawLine(3, y, size - 7, y)
    # Badge vert "+" en bas-droite
    badge_r = max(4, size // 3)
    bx = size - badge_r - 1
    by = size - badge_r - 1
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#2E7D32")))
    p.drawEllipse(bx - badge_r, by - badge_r, badge_r * 2, badge_r * 2)
    p.setPen(QPen(QColor("white"), max(1, badge_r // 2),
                  Qt.SolidLine, Qt.RoundCap))
    h = max(2, badge_r - 1)
    p.drawLine(bx - h // 2, by, bx + h // 2, by)
    p.drawLine(bx, by - h // 2, bx, by + h // 2)
    p.end()
    return QIcon(pix)


def _icon_del_page(size: int = 18) -> QIcon:
    """Page légèrement rosée avec badge '×' rouge en bas-droite."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    # Corps de la page
    p.setPen(QPen(QColor("#78909C"), 1.2))
    p.setBrush(QBrush(QColor("#FFEBEE")))
    p.drawRoundedRect(1, 1, size - 6, size - 2, 2, 2)
    # Lignes de texte simulées
    p.setPen(QPen(QColor("#FFCDD2"), 1))
    for y in range(5, size - 5, 3):
        p.drawLine(3, y, size - 7, y)
    # Badge rouge "×" en bas-droite
    badge_r = max(4, size // 3)
    bx = size - badge_r - 1
    by = size - badge_r - 1
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#C62828")))
    p.drawEllipse(bx - badge_r, by - badge_r, badge_r * 2, badge_r * 2)
    p.setPen(QPen(QColor("white"), max(1, badge_r // 2),
                  Qt.SolidLine, Qt.RoundCap))
    h = max(2, badge_r - 2)
    p.drawLine(bx - h, by - h, bx + h, by + h)
    p.drawLine(bx + h, by - h, bx - h, by + h)
    p.end()
    return QIcon(pix)


def _icon_expand_all(size: int = 18) -> QIcon:
    """Deux chevrons ›› orientés vers le bas = développer tout."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#1565C0"), max(1, size // 7),
               Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    # Chevron supérieur (pointe vers le bas)
    m = size // 4
    mid = size // 2
    top = size // 5
    p.drawLine(m, top, mid, top + m - 1)
    p.drawLine(mid, top + m - 1, size - m, top)
    # Chevron inférieur (pointe vers le bas)
    bot = size // 2 + 1
    p.drawLine(m, bot, mid, bot + m - 1)
    p.drawLine(mid, bot + m - 1, size - m, bot)
    p.end()
    return QIcon(pix)


def _icon_collapse_all(size: int = 18) -> QIcon:
    """Deux chevrons ‹‹ orientés vers le haut = réduire tout."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#1565C0"), max(1, size // 7),
               Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    # Chevron supérieur (pointe vers le haut)
    m = size // 4
    mid = size // 2
    bot1 = size // 2 - 1
    p.drawLine(m, bot1, mid, bot1 - m + 1)
    p.drawLine(mid, bot1 - m + 1, size - m, bot1)
    # Chevron inférieur (pointe vers le haut)
    bot2 = size - size // 5
    p.drawLine(m, bot2, mid, bot2 - m + 1)
    p.drawLine(mid, bot2 - m + 1, size - m, bot2)
    p.end()
    return QIcon(pix)


def _icon_move_up(size: int = 18) -> QIcon:
    """Flèche vers le haut = monter la page."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#546E7A")))
    # Triangle plein pointant vers le haut
    m   = size // 5
    mid = size // 2
    top = size // 5
    bot = size - size // 5
    from PyQt5.QtGui import QPolygon
    from PyQt5.QtCore import QPoint
    tri = QPolygon([QPoint(mid, top), QPoint(size - m, bot), QPoint(m, bot)])
    p.drawPolygon(tri)
    p.end()
    return QIcon(pix)


def _icon_move_down(size: int = 18) -> QIcon:
    """Flèche vers le bas = descendre la page."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#546E7A")))
    # Triangle plein pointant vers le bas
    m   = size // 5
    mid = size // 2
    top = size // 5
    bot = size - size // 5
    from PyQt5.QtGui import QPolygon
    from PyQt5.QtCore import QPoint
    tri = QPolygon([QPoint(m, top), QPoint(size - m, top), QPoint(mid, bot)])
    p.drawPolygon(tri)
    p.end()
    return QIcon(pix)


def _surface_icon(entity, size: int = _ICON_SIZE) -> QIcon:
    """Carré dont la couleur suit celle de la surface."""
    color = _entity_color(entity)
    border = color.darker(140)
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(border, 1))
    p.setBrush(QBrush(color))
    p.drawRect(1, 1, size - 2, size - 2)
    p.end()
    return QIcon(pix)


def _perimeter_icon(entity=None, size: int = _ICON_SIZE) -> QIcon:
    """
    Icône périmètre : plan stylisé en L avec cotes (trait + tirets aux extrémités),
    couleur calquée sur l'entité si disponible.
    """
    color = _entity_color(entity) if entity else QColor("#2E7D32")
    # Forcer une couleur lisible (pas trop transparente)
    color.setAlpha(230)
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    pen = QPen(color, max(1, int(size * 0.13)), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    # Forme en L (angle de plan architectural)
    m  = max(1, int(size * 0.12))   # marge
    cx = size // 2
    # Segment horizontal bas
    p.drawLine(m, size - m - 1, size - m, size - m - 1)
    # Segment vertical gauche
    p.drawLine(m, m + 1, m, size - m - 1)
    # Angle intérieur : petit carré symbolique
    inner = max(1, int(size * 0.18))
    p.setBrush(QBrush(color))
    p.setPen(Qt.NoPen)
    p.drawRect(m, size - m - 1 - inner, inner, inner)

    # Tirets de cote aux extrémités (haut et droite)
    tick_pen = QPen(color, max(1, int(size * 0.09)), Qt.SolidLine, Qt.RoundCap)
    p.setPen(tick_pen)
    tick = max(2, int(size * 0.22))
    # Extrémité haute (segment vertical)
    p.drawLine(m - tick // 2, m + 1, m + tick // 2 + 1, m + 1)
    # Extrémité droite (segment horizontal)
    p.drawLine(size - m - 1, size - m - 1 - tick // 2,
               size - m - 1, size - m - 1 + tick // 2 + 1)

    p.end()
    return QIcon(pix)


def _counter_icon(size: int = _ICON_SIZE) -> QIcon:
    """Point compteur orange."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#E65100")))
    r  = max(3, size // 3)
    cx = size // 2
    cy = size // 2
    p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
    p.end()
    return QIcon(pix)


def _generic_icon(size: int = _ICON_SIZE) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setPen(QPen(QColor("#90A4AE"), 1))
    p.setBrush(QBrush(QColor(180, 180, 180, 80)))
    p.drawRect(1, 1, size - 2, size - 2)
    p.end()
    return QIcon(pix)


def _entity_icon(entity) -> QIcon:
    """Dispatche vers la bonne icône selon le type et la couleur de l'entité."""
    etype = getattr(entity, "entity_type", "")
    if etype in ("polygon", "surface"):
        return _surface_icon(entity)
    if etype in ("perimeter", "line"):
        return _perimeter_icon(entity)
    if etype == "point":
        return _counter_icon()
    return _generic_icon()


def _saved_entity_icon(etype: str) -> QIcon:
    """Icône pour les entités sauvegardées (pas d'entité live disponible)."""
    if etype in ("polygon", "surface"):
        return _surface_icon(None)
    if etype in ("perimeter", "line"):
        return _perimeter_icon(None)
    if etype == "point":
        return _counter_icon()
    return _generic_icon()


# ──────────────────────────────────────────────────────────────────────────
# Miniature page
# ──────────────────────────────────────────────────────────────────────────

def _page_thumb_icon(thumbnail: Optional[QPixmap], w: int = _THUMB_W, h: int = _THUMB_H) -> QIcon:
    if thumbnail and not thumbnail.isNull():
        scaled  = thumbnail.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        framed  = QPixmap(w, h)
        framed.fill(QColor("#CFD8DC"))
        painter = QPainter(framed)
        ox = (w - scaled.width())  // 2
        oy = (h - scaled.height()) // 2
        painter.drawPixmap(ox, oy, scaled)
        painter.setPen(QPen(QColor("#90A4AE"), 1))
        painter.drawRect(0, 0, w - 1, h - 1)
        painter.end()
        return QIcon(framed)
    pix = QPixmap(w, h)
    pix.fill(QColor("#ECEFF1"))
    p = QPainter(pix)
    p.setPen(QPen(QColor("#B0BEC5"), 1))
    p.drawRect(0, 0, w - 1, h - 1)
    for y in range(5, h - 3, 5):
        p.setPen(QPen(QColor("#CFD8DC"), 1))
        p.drawLine(4, y, w - 4, y)
    p.end()
    return QIcon(pix)


# ──────────────────────────────────────────────────────────────────────────
# Calcul quantités
# ──────────────────────────────────────────────────────────────────────────

def _smart_qty(entity, em=None) -> tuple:
    """
    Retourne (valeur: float, unité: str) selon le type et les propriétés de l'entité.
    - Surface  : m²  si pas de hauteur,  m³  si hauteur > 0
    - Périmètre: ml  si pas de hauteur,  m²  si hauteur seule,  m³  si hauteur + épaisseur
    - Compteur : nombre d'unités dans le groupe (via entity_manager si disponible)
    Si l'entité est un parent de groupe, le total du groupe est retourné.
    """
    etype    = getattr(entity, "entity_type", "")
    height   = getattr(entity, "height",    0.0) or 0.0
    thick    = getattr(entity, "thickness", 0.0) or 0.0
    is_grp   = getattr(entity, "is_group_parent", False)
    children = getattr(entity, "child_entities", []) or []
    members  = [entity] + list(children) if (is_grp and children) else [entity]

    # ── Surface / Polygon ────────────────────────────────────────────────────
    if etype in ("polygon", "surface"):
        # Volume si épaisseur (dalle) OU hauteur (mur/voile horizontal) est renseignée
        if height > 0 or thick > 0:
            vol = 0.0
            for m in members:
                try:
                    vol += m.calculate_volume() if hasattr(m, "calculate_volume") else 0.0
                except Exception:
                    pass
            return vol, "m³"
        # Aire nette
        if is_grp and children and hasattr(entity, "calculate_total_group_area"):
            try:
                return entity.calculate_total_group_area(), "m²"
            except Exception:
                pass
        try:
            area = entity.calculate_net_area() if getattr(entity, "openings", None) \
                else entity.calculate_area()
            return area, "m²"
        except Exception:
            return 0.0, "m²"

    # ── Périmètre / Ligne ────────────────────────────────────────────────────
    if etype in ("perimeter", "line"):
        if height > 0 and thick > 0:
            vol = 0.0
            for m in members:
                try:
                    vol += m.calculate_volume() if hasattr(m, "calculate_volume") else 0.0
                except Exception:
                    pass
            return vol, "m³"
        if height > 0:
            surf = 0.0
            for m in members:
                try:
                    surf += m.calculate_surface_laterale() \
                        if hasattr(m, "calculate_surface_laterale") else 0.0
                except Exception:
                    pass
            return surf, "m²"
        # Longueur nette
        if is_grp and children and hasattr(entity, "calculate_total_group_length"):
            try:
                return entity.calculate_total_group_length(), "ml"
            except Exception:
                pass
        try:
            return entity.calculate_perimeter_length(), "ml"
        except Exception:
            return 0.0, "ml"

    # ── Compteur / Point ─────────────────────────────────────────────────────
    if etype == "point":
        count = 1
        if em is not None:
            gid = getattr(entity, "group_id", None)
            if gid:
                try:
                    count = len(em.get_points_by_group(gid))
                except Exception:
                    pass

        length    = float(getattr(entity, "length",    0.0) or 0.0)
        height    = float(getattr(entity, "height",    0.0) or 0.0)
        thickness = float(getattr(entity, "thickness", 0.0) or 0.0)

        if length > 0:
            if height > 0 and thickness > 0:
                return length * height * thickness * count, "m³"
            if height > 0:
                return length * height * count, "m²"
            return length * count, "m"

        return float(count), "u."

    return 0.0, ""


def _fmt_qty(value: float, unit: str) -> str:
    if unit == "m³":
        return f"{value:.2f} m³"
    if unit == "m²":
        return f"{value:.2f} m²"
    if unit == "ml":
        return f"{value:.2f} ml"
    if unit == "m":
        return f"{value:.2f} m"
    if unit == "u.":
        n = int(round(value))
        return f"{n} Unité" if n <= 1 else f"{n} Unités"
    return f"{value:.2f}" if value else "-"


# ──────────────────────────────────────────────────────────────────────────
# Widget page : [triangle  |  miniature  |  nom]
# ──────────────────────────────────────────────────────────────────────────

class _PageHeaderWidget(QWidget):
    """
    Widget affiché dans la col 0 de chaque item de page.
    Contient : triangle expand/collapse + miniature + nom de page.
    """
    def __init__(self, tree: "QTreeWidget", item: "QTreeWidgetItem",
                 thumb_icon: "QIcon", name: str,
                 thumb_w: int, thumb_h: int, parent=None):
        super().__init__(parent)
        self._tree = tree
        self._item = item
        self._full_name = name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(4)

        # Triangle expand/collapse
        self._tri = QToolButton()
        self._tri.setFixedSize(16, 16)
        self._tri.setAutoRaise(True)
        self._tri.setStyleSheet(
            "QToolButton { border: none; padding: 0; margin: 0; font-size: 10px; }")
        self._tri.clicked.connect(self._toggle)
        layout.addWidget(self._tri)

        # Miniature
        lbl_icon = QLabel()
        lbl_icon.setFixedSize(thumb_w, thumb_h)
        lbl_icon.setPixmap(thumb_icon.pixmap(thumb_w, thumb_h))
        lbl_icon.setScaledContents(True)
        layout.addWidget(lbl_icon)

        # Nom
        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet("font-weight: bold; font-size: 8pt;")
        self._name_lbl.setWordWrap(False)
        self._name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._name_lbl, 1)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._apply_elided_name()
        self._refresh_triangle()

    def _refresh_triangle(self):
        expanded = self._item.isExpanded()
        self._tri.setText("▼" if expanded else "▶")
        self._tri.setToolTip("Masquer les items" if expanded else "Afficher les items")

    def _toggle(self):
        expanded = self._item.isExpanded()
        self._item.setExpanded(not expanded)
        self._refresh_triangle()

    def update_expanded(self, expanded: bool):
        """Appelé depuis l'extérieur pour synchroniser l'icône."""
        self._refresh_triangle()

    def set_name(self, name: str):
        self._full_name = name
        self._apply_elided_name()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elided_name()

    def _apply_elided_name(self):
        """Évite que le titre déborde/chevauche la miniature quand le panneau est étroit."""
        if not hasattr(self, "_name_lbl") or self._name_lbl is None:
            return
        metrics = QFontMetrics(self._name_lbl.font())
        available = max(8, self._name_lbl.width())
        self._name_lbl.setText(metrics.elidedText(self._full_name, Qt.ElideRight, available))


# ──────────────────────────────────────────────────────────────────────────
# Widget droite : [quantité  |  ampoule]
# ──────────────────────────────────────────────────────────────────────────

class _RightWidget(QWidget):
    """
    Widget compact placé dans la colonne droite de chaque item entité.
    Contient le label de quantité + le bouton ampoule collé au bord droit.
    """
    def __init__(self, qty_str: str, bulb_on_icon: QIcon, bulb_off_icon: QIcon,
                 entity, entity_manager_getter, is_bold: bool = False,
                 color: QColor = None, parent=None):
        super().__init__(parent)
        self._entity        = entity
        self._em_getter     = entity_manager_getter
        self._bulb_on_icon  = bulb_on_icon
        self._bulb_off_icon = bulb_off_icon

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Label quantité
        self._lbl = QLabel(qty_str)
        self._lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        font = QFont()
        font.setPointSize(8)
        if is_bold:
            font.setBold(True)
        self._lbl.setFont(font)
        fg = color or _COLOR_QTY
        self._lbl.setStyleSheet(f"color: {fg.name()}; padding-right: 2px;")
        layout.addWidget(self._lbl, 1)

        # Bouton ampoule
        self._btn = QToolButton()
        self._btn.setFixedSize(20, 20)
        self._btn.setAutoRaise(True)
        self._btn.setContentsMargins(0, 0, 0, 0)
        self._btn.setStyleSheet("QToolButton { border: none; padding: 0; margin: 0; }")
        self._update_bulb()
        self._btn.clicked.connect(self._toggle)
        layout.addWidget(self._btn)

        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def _update_bulb(self):
        vis = getattr(self._entity, "visible", True)
        self._btn.setIcon(self._bulb_on_icon if vis else self._bulb_off_icon)
        self._btn.setToolTip("Masquer" if vis else "Afficher")

    def _toggle(self):
        em = self._em_getter()
        if em is None:
            return
        new_vis = not getattr(self._entity, "visible", True)
        em.apply_entity_visibility(self._entity, new_vis)
        self._update_bulb()

    def update_qty(self, qty_str: str):
        self._lbl.setText(qty_str)


# ──────────────────────────────────────────────────────────────────────────
# Rôles
# ──────────────────────────────────────────────────────────────────────────
_ROLE_ENTITY   = Qt.UserRole
_ROLE_KIND     = Qt.UserRole + 1
_ROLE_PAGE_IDX = Qt.UserRole + 2


# ──────────────────────────────────────────────────────────────────────────
# Panneau principal
# ──────────────────────────────────────────────────────────────────────────

class PDFMeasurementsPanel(QWidget):
    """
    Panneau unifié Pages PDF + Mesures (QWidget, placé dans un QDockWidget externe).
    Drop-in compatible avec PDFNavigator (mêmes signaux & méthodes publiques).
    """

    page_selected       = pyqtSignal(int)
    entity_selected     = pyqtSignal(object)
    rename_requested    = pyqtSignal(int)
    delete_requested    = pyqtSignal(int)
    duplicate_requested = pyqtSignal(int, bool)
    add_pdf_requested   = pyqtSignal()        # bouton + → PDF
    add_img_requested   = pyqtSignal()        # bouton + → Image
    move_page_requested = pyqtSignal(int, int)  # (from_index, to_index)

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window    = main_window
        self._pages: List[Optional[PDFPage]] = []
        self._current_index = 0
        self._icon_mgr  = IconManager()
        self._bulb_on   = self._icon_mgr.icon("bulb_on")
        self._bulb_off  = self._icon_mgr.icon("bulb_off")
        self._build_ui()
        self.setMinimumWidth(210)

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(2)

        # ── Barre d'outils pages ─────────────────────────────────────────────
        _btn_base = (
            "QToolButton{"
            "  border:1px solid #CFD8DC; border-radius:4px;"
            "  background:#ECEFF1; padding:2px;"
            "}"
            "QToolButton:hover{background:#B0BEC5; border-color:#90A4AE;}"
            "QToolButton:pressed{background:#90A4AE;}"
        )
        _btn_del_style = (
            "QToolButton{"
            "  border:1px solid #EF9A9A; border-radius:4px;"
            "  background:#FFEBEE; padding:2px;"
            "}"
            "QToolButton:hover{background:#FFCDD2; border-color:#E57373;}"
            "QToolButton:pressed{background:#EF9A9A;}"
        )

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 3, 4, 3)
        toolbar.setSpacing(3)

        # Bouton + (ajouter page) avec menu déroulant
        self._btn_add = QToolButton()
        self._btn_add.setFixedSize(28, 24)
        self._btn_add.setIcon(_icon_add_page(18))
        self._btn_add.setIconSize(QSize(18, 18))
        self._btn_add.setStyleSheet(_btn_base)
        self._btn_add.setToolTip("Ajouter une page (PDF ou Image)")
        self._btn_add.clicked.connect(self._on_add_page_clicked)
        toolbar.addWidget(self._btn_add)

        # Bouton × (supprimer page sélectionnée)
        self._btn_del = QToolButton()
        self._btn_del.setFixedSize(28, 24)
        self._btn_del.setIcon(_icon_del_page(18))
        self._btn_del.setIconSize(QSize(18, 18))
        self._btn_del.setStyleSheet(_btn_del_style)
        self._btn_del.setToolTip("Supprimer la page sélectionnée")
        self._btn_del.clicked.connect(self._on_delete_page_clicked)
        toolbar.addWidget(self._btn_del)

        # Séparateur vertical fin
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        sep1.setStyleSheet("color:#CFD8DC;")
        sep1.setFixedSize(6, 20)
        toolbar.addWidget(sep1)

        # Bouton Monter la page ▲
        self._btn_up = QToolButton()
        self._btn_up.setFixedSize(28, 24)
        self._btn_up.setIcon(_icon_move_up(18))
        self._btn_up.setIconSize(QSize(18, 18))
        self._btn_up.setStyleSheet(_btn_base)
        self._btn_up.setToolTip("Monter la page")
        self._btn_up.clicked.connect(self._move_page_up)
        toolbar.addWidget(self._btn_up)

        # Bouton Descendre la page ▼
        self._btn_down = QToolButton()
        self._btn_down.setFixedSize(28, 24)
        self._btn_down.setIcon(_icon_move_down(18))
        self._btn_down.setIconSize(QSize(18, 18))
        self._btn_down.setStyleSheet(_btn_base)
        self._btn_down.setToolTip("Descendre la page")
        self._btn_down.clicked.connect(self._move_page_down)
        toolbar.addWidget(self._btn_down)

        # Séparateur vertical fin
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("color:#CFD8DC;")
        sep.setFixedSize(6, 20)
        toolbar.addWidget(sep)

        # Bouton Développer tout
        self._btn_expand = QToolButton()
        self._btn_expand.setFixedSize(28, 24)
        self._btn_expand.setIcon(_icon_expand_all(18))
        self._btn_expand.setIconSize(QSize(18, 18))
        self._btn_expand.setStyleSheet(_btn_base)
        self._btn_expand.setToolTip("Développer tout")
        self._btn_expand.clicked.connect(self._expand_all)
        toolbar.addWidget(self._btn_expand)

        # Bouton Réduire tout
        self._btn_collapse = QToolButton()
        self._btn_collapse.setFixedSize(28, 24)
        self._btn_collapse.setIcon(_icon_collapse_all(18))
        self._btn_collapse.setIconSize(QSize(18, 18))
        self._btn_collapse.setStyleSheet(_btn_base)
        self._btn_collapse.setToolTip("Réduire tout")
        self._btn_collapse.clicked.connect(self._collapse_all)
        toolbar.addWidget(self._btn_collapse)

        toolbar.addStretch(1)

        # Compteur de pages (ex: 2 / 5)
        self._lbl_count = QLabel("0 / 0")
        self._lbl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lbl_count.setStyleSheet("font-size:9px; color:#78909C;")
        toolbar.addWidget(self._lbl_count)

        layout.addLayout(toolbar)

        # ── Barre navigation compacte (◀ / ▶) ────────────────────────────────
        nav = QHBoxLayout()
        nav.setContentsMargins(4, 0, 4, 0)
        nav.setSpacing(2)
        _btn_style = (
            "QPushButton{border:1px solid #CFD8DC;border-radius:3px;"
            "background:#ECEFF1;font-size:9px;padding:0;}"
            "QPushButton:hover{background:#B0BEC5;}")
        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedSize(24, 20)
        self._btn_prev.setStyleSheet(_btn_style)
        self._btn_prev.clicked.connect(self._go_prev)
        self._lbl_page = QLabel("0 / 0")
        self._lbl_page.setAlignment(Qt.AlignCenter)
        self._lbl_page.setStyleSheet("font-size:10px;color:#546E7A;font-weight:bold;")
        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedSize(24, 20)
        self._btn_next.setStyleSheet(_btn_style)
        self._btn_next.clicked.connect(self._go_next)
        nav.addWidget(self._btn_prev)
        nav.addWidget(self._lbl_page, 1)
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)

        # Arbre — 2 colonnes : [nom | widget(qty+bulb)]
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.header().hide()
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        # Synchroniser le triangle du header quand expand/collapse change
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        # Pas de scrollbar horizontale inutile
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setStretchLastSection(False)
        hdr.setMinimumSectionSize(0)
        self.tree.setColumnWidth(1, _COL1_W)

        self.tree.setIconSize(QSize(_THUMB_W, _THUMB_H))

        self.tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                background: #FAFAFA;
                font-size: 12px;
                outline: 0;
                margin: 0;
                padding: 0;
            }
            QTreeWidget::item {
                border-bottom: 1px solid #ECEFF1;
                padding: 3px 0px;
                min-height: 22px;
            }
            QTreeWidget::item:selected {
                background: #E3F2FD;
                color: #0D47A1;
            }
            QTreeWidget::branch {
                background: transparent;
                width: 0px;
            }
        """)

        layout.addWidget(self.tree)

    # ── Actions barre d'outils ────────────────────────────────────────────

    def _on_add_page_clicked(self):
        """Menu déroulant pour ajouter une page PDF ou Image."""
        menu = QMenu(self)
        a_pdf = menu.addAction("📄  Importer un PDF…")
        a_img = menu.addAction("🖼️  Importer une Image…")
        action = menu.exec_(self._btn_add.mapToGlobal(
            self._btn_add.rect().bottomLeft()))
        if action == a_pdf:
            self.add_pdf_requested.emit()
        elif action == a_img:
            self.add_img_requested.emit()

    def _on_delete_page_clicked(self):
        """Supprime la page actuellement sélectionnée."""
        if self._pages:
            self.delete_requested.emit(self._current_index)

    def _move_page_up(self):
        """Monte la page sélectionnée d'une position."""
        if self._current_index > 0:
            self.move_page_requested.emit(self._current_index, self._current_index - 1)

    def _move_page_down(self):
        """Descend la page sélectionnée d'une position."""
        if self._current_index < len(self._pages) - 1:
            self.move_page_requested.emit(self._current_index, self._current_index + 1)

    def _expand_all(self):
        """Développe toutes les pages pour afficher toutes les mesures."""
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            self.tree.expandItem(item)
            hw = self.tree.itemWidget(item, 0)
            if isinstance(hw, _PageHeaderWidget):
                hw.update_expanded(True)

    def _collapse_all(self):
        """Réduit toutes les pages pour n'afficher que les en-têtes."""
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            self.tree.collapseItem(item)
            hw = self.tree.itemWidget(item, 0)
            if isinstance(hw, _PageHeaderWidget):
                hw.update_expanded(False)

    # ── API publique (compat PDFNavigator) ───────────────────────────────

    def set_pages(self, pages: List[Optional[PDFPage]]):
        self._pages = pages or []
        self.tree.clear()
        for idx, page in enumerate(self._pages):
            page_item = self._make_page_item(idx, page)
            self.tree.addTopLevelItem(page_item)
            self._attach_page_header(page_item)
            if page and page.entities_data:
                self._populate_saved_entities(page_item, page)
            # Au chargement, ouvrir uniquement la page active
            if idx == self._current_index:
                page_item.setExpanded(True)
        self._update_nav_label()
        self._highlight_current_page()

    def set_current_page(self, index: int):
        self._current_index = index
        # Ne pas toucher à l'état expand/collapse des pages —
        # seul le clic sur le triangle doit ouvrir/fermer les items.
        self._update_nav_label()
        self._highlight_current_page()

    def update_page_thumbnail(self, index: int, thumbnail: QPixmap):
        if index < len(self._pages) and self._pages[index]:
            self._pages[index].thumbnail = thumbnail
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, _ROLE_PAGE_IDX) == index:
                # Mettre à jour la miniature dans Qt.UserRole + 20
                old_data = item.data(0, Qt.UserRole + 20)
                if old_data is not None:
                    name, _ = old_data
                    item.setData(0, Qt.UserRole + 20, (name, thumbnail))
                # Recréer le header avec la nouvelle miniature
                self._attach_page_header(item)
                break

    def update_page_name(self, index: int, name: str):
        display_name = name or f"Page {index + 1}"
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, _ROLE_PAGE_IDX) == index:
                # Mettre à jour le label visible du header widget
                hw = self.tree.itemWidget(item, 0)
                if isinstance(hw, _PageHeaderWidget):
                    hw.set_name(display_name)
                else:
                    item.setText(0, display_name)
                # Mettre à jour la donnée stockée (utilisée lors de la reconstruction)
                old_data = item.data(0, Qt.UserRole + 20)
                if old_data is not None:
                    _, thumb = old_data
                    item.setData(0, Qt.UserRole + 20, (display_name, thumb))
                # Mettre à jour aussi le nom dans _pages
                if 0 <= index < len(self._pages) and self._pages[index]:
                    self._pages[index].name = display_name
                break

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Synchronise le triangle du header lors d'un expand."""
        if item.data(0, _ROLE_KIND) == "page":
            hw = self.tree.itemWidget(item, 0)
            if isinstance(hw, _PageHeaderWidget):
                hw.update_expanded(True)

    def _on_item_collapsed(self, item: QTreeWidgetItem):
        """Synchronise le triangle du header lors d'un collapse."""
        if item.data(0, _ROLE_KIND) == "page":
            hw = self.tree.itemWidget(item, 0)
            if isinstance(hw, _PageHeaderWidget):
                hw.update_expanded(False)

    def refresh(self):
        """Reconstruction complète des items de la page active (ajout/suppression)."""
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            page_item = root.child(i)
            if page_item.data(0, _ROLE_PAGE_IDX) == self._current_index:
                self._rebuild_live_entities(page_item)
                break

    def update_quantities(self, entity=None):
        """
        Mise à jour rapide des quantités en place — sans reconstruire l'arbre.
        Appelé à chaque entity_modified pour une réactivité immédiate.
        Si entity est fourni, cherche d'abord son item ; sinon met tout à jour.
        """
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            page_item = root.child(i)
            if page_item.data(0, _ROLE_PAGE_IDX) != self._current_index:
                continue
            for j in range(page_item.childCount()):
                child = page_item.child(j)
                if child.data(0, _ROLE_KIND) != "entity":
                    continue
                ent = child.data(0, _ROLE_ENTITY)
                if ent is None:
                    continue
                # Si on cible une entité précise, ne rafraîchir que son groupe/elle-même
                if entity is not None:
                    # Remonter à la racine de l'entité modifiée (enfant → parent)
                    mod_root = entity
                    while getattr(mod_root, "parent_entity", None) is not None:
                        mod_root = mod_root.parent_entity
                    # L'arbre affiche uniquement la racine du groupe
                    gid_ent = getattr(ent, "group_id", None)
                    gid_mod = getattr(mod_root, "group_id", None)
                    same = (ent is mod_root) or (gid_ent and gid_ent == gid_mod)
                    if not same:
                        continue
                em_ref  = self._get_entity_manager()
                qty_val, unit = _smart_qty(ent, em_ref)
                qty_str = _fmt_qty(qty_val, unit)
                rw = self.tree.itemWidget(child, 1)
                if isinstance(rw, _RightWidget):
                    rw.update_qty(qty_str)
            break

    # ── Items de page ────────────────────────────────────────────────────

    def _make_page_item(self, index: int, page: Optional[PDFPage]) -> QTreeWidgetItem:
        name  = page.name if page and page.name else f"Page {index + 1}"
        item  = QTreeWidgetItem(["", ""])
        item.setData(0, _ROLE_KIND, "page")
        item.setData(0, _ROLE_PAGE_IDX, index)
        item.setSizeHint(0, QSize(0, _THUMB_H + 8))
        self._apply_page_colors(item, active=False)
        # Le widget header (triangle + miniature + nom) est attaché après
        # addTopLevelItem / addChild dans _attach_page_header
        item.setData(0, Qt.UserRole + 20, (name, page.thumbnail if page else None))
        return item

    def _attach_page_header(self, item: QTreeWidgetItem):
        """Crée et attache le _PageHeaderWidget à un item de page (après insertion dans l'arbre)."""
        data = item.data(0, Qt.UserRole + 20)
        if data is None:
            return
        name, thumb = data
        icon = _page_thumb_icon(thumb)
        hw = _PageHeaderWidget(self.tree, item, icon, name, _THUMB_W, _THUMB_H)
        self.tree.setItemWidget(item, 0, hw)

    @staticmethod
    def _apply_page_colors(item: QTreeWidgetItem, active: bool):
        bg = _COLOR_PAGE_ACTIVE if active else _COLOR_PAGE_INACTIVE
        fg = QColor("#0D47A1") if active else QColor("#37474F")
        item.setBackground(0, bg)
        item.setBackground(1, bg)
        item.setForeground(0, fg)

    # ── Entités sauvegardées (pages inactives) ───────────────────────────

    def _populate_saved_entities(self, page_item: QTreeWidgetItem, page: PDFPage):
        page_item.takeChildren()
        groups: dict = {}
        for data in (page.entities_data or []):
            etype = data.get("type", "")
            if etype == "opening" or data.get("parent_entity_id"):
                continue
            name     = data.get("name", "") or etype
            group_id = data.get("group_id")
            key      = group_id if group_id else id(data)
            if key not in groups:
                groups[key] = {"name": name, "type": etype, "count": 0}
            groups[key]["count"] += 1

        for g in groups.values():
            suffix = f" ×{g['count']}" if g["count"] > 1 else ""
            child  = QTreeWidgetItem([f"{g['name']}{suffix}", ""])
            child.setIcon(0, _saved_entity_icon(g["type"]))
            child.setData(0, _ROLE_KIND, "saved_entity")
            child.setForeground(0, _COLOR_SAVED)
            page_item.addChild(child)

    # ── Entités live (page active) ───────────────────────────────────────

    def _rebuild_live_entities(self, page_item: QTreeWidgetItem):
        # Mémoriser si la page était vide avant reconstruction
        was_empty = (page_item.childCount() == 0)

        page_item.takeChildren()
        # Ré-attacher le header après takeChildren (sinon Qt le supprime)
        self._attach_page_header(page_item)
        em = self._get_entity_manager()
        if em is None:
            return

        seen_groups: set = set()
        rows = []
        _HIDDEN_TYPES = {"opening", "line", "scale", "marker"}
        for ent in em.get_all_entities():
            if getattr(ent, "entity_type", "") in _HIDDEN_TYPES:
                continue
            if getattr(ent, "parent_entity", None) is not None:
                continue
            gid = getattr(ent, "group_id", None)
            if gid:
                if gid in seen_groups:
                    continue
                seen_groups.add(gid)
            rows.append(ent)

        for ent in rows:
            child_item = self._make_entity_item(ent)
            page_item.addChild(child_item)
            # setItemWidget DOIT être appelé après addChild (item attaché à l'arbre)
            wdata = child_item.data(0, Qt.UserRole + 10)
            if wdata:
                qty_str, is_bold, color, entity = wdata
                rw = _RightWidget(
                    qty_str, self._bulb_on, self._bulb_off,
                    entity, self._get_entity_manager,
                    is_bold=is_bold, color=color,
                )
                self.tree.setItemWidget(child_item, 1, rw)

        # Auto-ouvrir uniquement si la page vient de recevoir sa première entité
        # (transition 0 → N). Si l'utilisateur a fermé manuellement, on respecte son choix.
        if was_empty and len(rows) > 0 and not page_item.isExpanded():
            page_item.setExpanded(True)
            hw = self.tree.itemWidget(page_item, 0)
            if isinstance(hw, _PageHeaderWidget):
                hw.update_expanded(True)

    def _make_entity_item(self, entity) -> QTreeWidgetItem:
        etype = getattr(entity, "entity_type", "")
        name  = getattr(entity, "name", "") or etype

        em = self._get_entity_manager()
        qty_val, unit = _smart_qty(entity, em)
        qty_str = _fmt_qty(qty_val, unit)

        item = QTreeWidgetItem([name, ""])
        item.setIcon(0, _entity_icon(entity))
        item.setData(0, _ROLE_KIND, "entity")
        item.setData(0, _ROLE_ENTITY, entity)

        # Style uniforme : nom toujours en noir, police 8pt normale
        f = QFont()
        f.setPointSize(8)
        item.setFont(0, f)
        item.setForeground(0, _COLOR_ENTITY_NAME)

        # Stocker les infos pour que le parent puisse appeler setItemWidget
        # APRÈS avoir ajouté l'item à l'arbre (requis par Qt)
        item.setData(0, Qt.UserRole + 10, (qty_str, False, _COLOR_QTY, entity))

        return item

    # ── Interactions ─────────────────────────────────────────────────────

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int):
        kind = item.data(0, _ROLE_KIND)
        if kind == "page":
            idx = item.data(0, _ROLE_PAGE_IDX)
            if idx is not None and idx != self._current_index:
                self._current_index = idx
                self._update_nav_label()
                self._highlight_current_page()
                self.page_selected.emit(idx)
        elif kind == "entity":
            entity = item.data(0, _ROLE_ENTITY)
            if entity is not None:
                self.entity_selected.emit(entity)

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item or item.data(0, _ROLE_KIND) != "page":
            return
        idx = item.data(0, _ROLE_PAGE_IDX)
        if idx is None:
            return
        menu    = QMenu(self)
        a_ren   = menu.addAction("Renommer")
        a_dup_w = menu.addAction("Dupliquer (avec mesures)")
        a_dup_n = menu.addAction("Dupliquer (sans mesures)")
        a_del   = menu.addAction("Supprimer")
        action  = menu.exec_(self.tree.mapToGlobal(pos))
        if action == a_ren:
            self.rename_requested.emit(idx)
        elif action == a_dup_w:
            self.duplicate_requested.emit(idx, True)
        elif action == a_dup_n:
            self.duplicate_requested.emit(idx, False)
        elif action == a_del:
            self.delete_requested.emit(idx)

    def _go_prev(self):
        if self._current_index > 0:
            self._current_index -= 1
            self._update_nav_label()
            self._highlight_current_page()
            self.page_selected.emit(self._current_index)

    def _go_next(self):
        if self._current_index < len(self._pages) - 1:
            self._current_index += 1
            self._update_nav_label()
            self._highlight_current_page()
            self.page_selected.emit(self._current_index)

    def _update_nav_label(self):
        total = len(self._pages)
        txt = f"{self._current_index + 1} / {total}" if total else "0 / 0"
        self._lbl_page.setText(txt)
        self._lbl_count.setText(txt)

    def _highlight_current_page(self):
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            page_item = root.child(i)
            idx       = page_item.data(0, _ROLE_PAGE_IDX)
            is_active = (idx == self._current_index)
            self._apply_page_colors(page_item, active=is_active)
            if is_active:
                # Rafraîchir les items de la page active sans toucher à l'état expand/collapse
                self._rebuild_live_entities(page_item)
            # Ne jamais forcer l'ouverture/fermeture — seul le triangle contrôle ça

    def _get_entity_manager(self):
        try:
            return self.main_window.canvas_view.entity_manager
        except AttributeError:
            return None
