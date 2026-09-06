"""
Factory de brosses de remplissage pour les surfaces Metraplan.

Gère à la fois les motifs Qt natifs (identifiés par int/Qt.BrushStyle)
et les motifs personnalisés (identifiés par une chaîne de caractères).
Compatibilité ascendante : un int existant est traité comme Qt.BrushStyle.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QPixmap, QPainter, QPen

# Correspondance string → Qt.BrushStyle pour les motifs natifs
_QT_PATTERNS = {
    "solid":      Qt.SolidPattern,
    "hlines":     Qt.HorPattern,
    "vlines":     Qt.VerPattern,
    "grid":       Qt.CrossPattern,
    "diag_back":  Qt.BDiagPattern,
    "diag_fwd":   Qt.FDiagPattern,
    "cross_diag": Qt.DiagCrossPattern,
}

# Motifs personnalisés basés sur une texture pixmap
_CUSTOM_PATTERNS = {"brick", "brick_offset", "tile", "dots"}


def make_brush(color: QColor, pattern) -> QBrush:
    """
    Crée un QBrush à partir d'une couleur et d'un identifiant de motif.

    :param color:   QColor de remplissage.
    :param pattern: Qt.BrushStyle, int (compat anciens fichiers) ou str (nouveau).
    :return: QBrush prêt à l'emploi.
    """
    # --- Compat ascendante : int ou Qt.BrushStyle ---
    if isinstance(pattern, int):
        try:
            return QBrush(color, Qt.BrushStyle(pattern))
        except Exception:
            return QBrush(color, Qt.SolidPattern)

    if isinstance(pattern, Qt.BrushStyle):
        return QBrush(color, pattern)

    # --- Nouveau système : string ---
    if not isinstance(pattern, str):
        return QBrush(color, Qt.SolidPattern)

    # Motifs Qt natifs
    qt_style = _QT_PATTERNS.get(pattern)
    if qt_style is not None:
        return QBrush(color, qt_style)

    # Motifs personnalisés (texture pixmap)
    if pattern in _CUSTOM_PATTERNS:
        pixmap = _build_texture(color, pattern)
        return QBrush(pixmap)

    return QBrush(color, Qt.SolidPattern)


def pattern_to_storage(pattern) -> object:
    """Convertit un motif en valeur sérialisable (int ou str)."""
    if isinstance(pattern, str):
        return pattern
    if isinstance(pattern, Qt.BrushStyle):
        return int(pattern)
    return int(pattern) if isinstance(pattern, int) else 1  # SolidPattern


def pattern_from_storage(value) -> object:
    """Restitue un motif depuis une valeur sérialisée."""
    if isinstance(value, str):
        return value
    # int → Qt.BrushStyle (compat anciens fichiers)
    return int(value) if value is not None else Qt.SolidPattern


# ---------------------------------------------------------------------------
# Générateurs de textures
# ---------------------------------------------------------------------------

def _build_texture(color: QColor, pattern: str) -> QPixmap:
    """Génère un pixmap tuilé pour un motif personnalisé."""
    if pattern == "brick":
        return _texture_brick(color, offset=False)
    if pattern == "brick_offset":
        return _texture_brick(color, offset=True)
    if pattern == "tile":
        return _texture_tile(color)
    if pattern == "dots":
        return _texture_dots(color)
    return _texture_solid(color)


def _base_pixmap(w: int, h: int, bg: QColor) -> tuple:
    """Crée un pixmap transparent et son QPainter."""
    pix = QPixmap(w, h)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, False)
    # Fond semi-transparent
    fill = QColor(bg)
    fill.setAlpha(max(40, bg.alpha() // 2))
    p.fillRect(0, 0, w, h, fill)
    return pix, p


def _joint_pen(color: QColor) -> QPen:
    """Stylet pour les joints (couleur pleine légèrement assombrie)."""
    c = color.darker(160)
    c.setAlpha(220)
    pen = QPen(c, 1, Qt.SolidLine)
    pen.setCosmetic(True)
    return pen


def _texture_solid(color: QColor) -> QPixmap:
    pix = QPixmap(4, 4)
    pix.fill(color)
    return pix


def _texture_brick(color: QColor, offset: bool) -> QPixmap:
    """
    Motif brique horizontal.
    - offset=False : brique classique (joints verticaux alignés)
    - offset=True  : brique décalée (joint décalé d'une demi-brique)
    """
    W, H = 24, 12   # taille du carreau (2 rangées)
    bh = 6           # hauteur d'une brique
    pix, p = _base_pixmap(W, H, color)

    pen = _joint_pen(color)
    p.setPen(pen)

    # Rangée 0 (y=0..bh-1) — joints verticaux à x=0, 12
    p.drawLine(0, 0, W, 0)      # joint horizontal haut
    p.drawLine(0, bh, W, bh)    # joint horizontal milieu
    p.drawLine(0, H, W, H)      # joint horizontal bas (wrapping)
    p.drawLine(0, 0, 0, bh)
    p.drawLine(12, 0, 12, bh)

    # Rangée 1 (y=bh..H-1) — décalage de 6 si offset
    off = 6 if offset else 0
    p.drawLine(off, bh, off, H)
    p.drawLine(off + 12, bh, off + 12, H)
    if off > 0:
        p.drawLine(off - 12, bh, off - 12, H)

    p.end()
    return pix


def _texture_tile(color: QColor) -> QPixmap:
    """Motif carrelage carré."""
    S = 16  # taille d'un carreau
    pix, p = _base_pixmap(S, S, color)

    pen = _joint_pen(color)
    p.setPen(pen)

    p.drawLine(0, 0, S, 0)
    p.drawLine(0, 0, 0, S)
    p.drawLine(S - 1, 0, S - 1, S)
    p.drawLine(0, S - 1, S, S - 1)

    p.end()
    return pix


def _texture_dots(color: QColor) -> QPixmap:
    """Motif points espacés."""
    S = 8
    pix, p = _base_pixmap(S, S, color)

    pen = _joint_pen(color)
    p.setPen(pen)
    p.setBrush(QBrush(pen.color()))
    p.drawEllipse(1, 1, 2, 2)

    p.end()
    return pix
