# ui/ribbon_icons.py
"""
Icônes programmatiques pour le ruban principal de Metraplan.
Toutes dessinées avec QPainter — aucune dépendance fichier.
"""
from PyQt5.QtGui import (
    QIcon, QPixmap, QPainter, QPen, QBrush, QColor,
    QPainterPath, QFont, QPolygonF,
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QSize
from PyQt5.QtWidgets import QApplication


# ── Palette ──────────────────────────────────────────────────────────────────
_C_BG        = QColor(0, 0, 0, 0)          # transparent
_C_WHITE     = QColor(255, 255, 255)
_C_BLUE      = QColor(41, 182, 246)         # accent bleu clair
_C_BLUE_D    = QColor(21, 101, 192)         # bleu foncé
_C_GREEN     = QColor(105, 240, 174)        # vert mesure
_C_ORANGE    = QColor(255, 183, 77)         # orange échelle
_C_RED       = QColor(239, 83, 80)          # rouge suppression
_C_GREY      = QColor(180, 200, 220)        # gris clair
_C_GREY_D    = QColor(100, 130, 160)        # gris moyen


def _canvas(size: int) -> tuple:
    """Retourne (pixmap, painter) initialisés."""
    px = QPixmap(size, size)
    px.fill(_C_BG)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    return px, p


def _icon(size: int, draw_fn) -> QIcon:
    px, p = _canvas(size)
    draw_fn(p, size)
    p.end()
    return QIcon(px)


def _pen(color, width=1.6, cap=Qt.RoundCap, join=Qt.RoundJoin):
    pen = QPen(color, width, Qt.SolidLine, cap, join)
    return pen


def _brush(color):
    return QBrush(color)


# ── Icônes fichier ───────────────────────────────────────────────────────────

def icon_new_project(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s * 0.1
        w, h = s - m * 2, s - m * 2
        # Feuille
        path = QPainterPath()
        fold = s * 0.25
        path.moveTo(m, m)
        path.lineTo(m + w - fold, m)
        path.lineTo(m + w, m + fold)
        path.lineTo(m + w, m + h)
        path.lineTo(m, m + h)
        path.closeSubpath()
        p.setPen(_pen(_C_BLUE, 1.8))
        p.setBrush(_brush(QColor(30, 80, 160, 100)))
        p.drawPath(path)
        # Corner fold
        fold_path = QPainterPath()
        fold_path.moveTo(m + w - fold, m)
        fold_path.lineTo(m + w - fold, m + fold)
        fold_path.lineTo(m + w, m + fold)
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(_C_BLUE, 1.4))
        p.drawPath(fold_path)
        # Lignes de texte
        p.setPen(_pen(_C_GREY, 1.3))
        for i in range(3):
            y = m + h * 0.38 + i * h * 0.15
            p.drawLine(QPointF(m + s * 0.15, y), QPointF(m + w * 0.75, y))
    return _icon(size, draw)


def icon_open(size=32) -> QIcon:
    """Icône importer une image — chargée depuis le PNG dédié."""
    import os
    png_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "icons", "open_image.png"
    )
    if os.path.isfile(png_path):
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(
                QSize(size, size),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
    # Fallback dessiné si le fichier est absent
    def draw(p: QPainter, s):
        m = s * 0.1
        body = QPainterPath()
        body.addRoundedRect(QRectF(m, m + s * 0.18, s - m * 2, s - m * 2 - s * 0.12), 3, 3)
        p.setPen(_pen(_C_ORANGE, 1.8))
        p.setBrush(_brush(QColor(180, 120, 30, 140)))
        p.drawPath(body)
    return _icon(size, draw)


def icon_import_pdf(size=32) -> QIcon:
    """Icône importer un PDF — chargée depuis le PNG dédié."""
    import os
    png_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "icons", "import_pdf.png"
    )
    if os.path.isfile(png_path):
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(
                QSize(size, size),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
    # Fallback dessiné si le fichier est absent
    def draw(p: QPainter, s):
        m = s * 0.08
        path = QPainterPath()
        fold = s * 0.22
        path.moveTo(m, m)
        path.lineTo(m + (s - m * 2) - fold, m)
        path.lineTo(s - m, m + fold)
        path.lineTo(s - m, s - m)
        path.lineTo(m, s - m)
        path.closeSubpath()
        p.setPen(_pen(_C_RED, 1.8))
        p.setBrush(_brush(QColor(200, 40, 40, 90)))
        p.drawPath(path)
        font = QFont("Arial", int(s * 0.23), QFont.Bold)
        p.setFont(font)
        p.setPen(_pen(_C_WHITE, 1))
        p.drawText(QRectF(m, s * 0.4, s - m * 2, s * 0.35), Qt.AlignCenter, "PDF")
    return _icon(size, draw)


def icon_save(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s * 0.1
        # Disquette modernisée (base)
        p.setPen(_pen(_C_BLUE, 1.8))
        p.setBrush(_brush(QColor(21, 101, 192, 120)))
        p.drawRoundedRect(QRectF(m, m, s - m * 2, s - m * 2), 4, 4)
        # Zone étiquette (haut)
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(QColor(41, 182, 246, 160)))
        p.drawRect(QRectF(m + s * 0.1, m + s * 0.06, s * 0.55, s * 0.25))
        # Zone disque (bas centre)
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(QColor(180, 200, 230, 180)))
        p.drawEllipse(QRectF(s * 0.32, s * 0.54, s * 0.36, s * 0.36))
        p.setBrush(_brush(QColor(21, 101, 192, 200)))
        p.drawEllipse(QRectF(s * 0.41, s * 0.63, s * 0.18, s * 0.18))
    return _icon(size, draw)


def icon_save_as(size=32) -> QIcon:
    def draw(p: QPainter, s):
        # Même que save mais plus petit + "+" en coin
        m = s * 0.12
        p.setPen(_pen(_C_BLUE, 1.8))
        p.setBrush(_brush(QColor(21, 101, 192, 120)))
        p.drawRoundedRect(QRectF(m, m, s * 0.7, s * 0.7), 4, 4)
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(QColor(41, 182, 246, 160)))
        p.drawRect(QRectF(m + s * 0.08, m + s * 0.05, s * 0.4, s * 0.2))
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(QColor(180, 200, 230, 180)))
        p.drawEllipse(QRectF(s * 0.27, s * 0.44, s * 0.28, s * 0.28))
        p.setBrush(_brush(QColor(21, 101, 192, 200)))
        p.drawEllipse(QRectF(s * 0.34, s * 0.51, s * 0.14, s * 0.14))
        # "+" badge
        p.setPen(_pen(_C_GREEN, 2.2))
        cx, cy = s * 0.82, s * 0.82
        r = s * 0.1
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
    return _icon(size, draw)


def icon_open_project(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s * 0.1
        # Dossier
        p.setPen(_pen(_C_BLUE, 1.8))
        p.setBrush(_brush(QColor(21, 101, 192, 120)))
        tab = QPainterPath()
        tab.addRoundedRect(m, m + s * 0.1, s * 0.38, s * 0.12, 3, 3)
        p.drawPath(tab)
        body = QPainterPath()
        body.addRoundedRect(QRectF(m, m + s * 0.2, s - m * 2, s - m * 2 - s * 0.14), 4, 4)
        p.setBrush(_brush(QColor(30, 80, 160, 110)))
        p.drawPath(body)
        # "M" pour Metraplan
        font = QFont("Arial", int(s * 0.28), QFont.Bold)
        p.setFont(font)
        p.setPen(_pen(_C_WHITE, 1))
        p.drawText(QRectF(m, s * 0.32, s - m * 2, s * 0.45), Qt.AlignCenter, "M")
    return _icon(size, draw)


# ── Icônes historique ────────────────────────────────────────────────────────

def icon_undo(size=32) -> QIcon:
    """Flèche courbe vers la gauche — annuler."""
    def draw(p: QPainter, s):
        cx, cy = s * 0.56, s * 0.52
        r = s * 0.28
        p.setPen(_pen(_C_BLUE, 2.6))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 60 * 16, 300 * 16)
        # Pointe de flèche (haut-gauche de l'arc)
        ax, ay = cx - r * 0.72, cy - r * 0.72
        arr = QPolygonF([
            QPointF(ax - s * 0.11, ay + s * 0.02),
            QPointF(ax + s * 0.06, ay - s * 0.12),
            QPointF(ax + s * 0.06, ay + s * 0.12),
        ])
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(_C_BLUE))
        p.drawPolygon(arr)
    return _icon(size, draw)


def icon_redo(size=32) -> QIcon:
    """Flèche courbe vers la droite — refaire."""
    def draw(p: QPainter, s):
        cx, cy = s * 0.44, s * 0.52
        r = s * 0.28
        p.setPen(_pen(_C_BLUE, 2.6))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 240 * 16, 300 * 16)
        # Pointe de flèche (haut-droit de l'arc)
        ax, ay = cx + r * 0.72, cy - r * 0.72
        arr = QPolygonF([
            QPointF(ax + s * 0.11, ay + s * 0.02),
            QPointF(ax - s * 0.06, ay - s * 0.12),
            QPointF(ax - s * 0.06, ay + s * 0.12),
        ])
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(_C_BLUE))
        p.drawPolygon(arr)
    return _icon(size, draw)


# ── Icônes outils de mesure ──────────────────────────────────────────────────

def icon_surface(size=32) -> QIcon:
    """Forme maison remplie = surface (m²)."""
    def draw(p: QPainter, s):
        # Points de la maison : faîte + 4 coins du mur
        house = QPolygonF([
            QPointF(s * 0.50, s * 0.08),   # faîte
            QPointF(s * 0.88, s * 0.46),   # coin haut-droit
            QPointF(s * 0.88, s * 0.90),   # coin bas-droit
            QPointF(s * 0.12, s * 0.90),   # coin bas-gauche
            QPointF(s * 0.12, s * 0.46),   # coin haut-gauche
        ])
        p.setPen(_pen(_C_GREEN, 1.8))
        p.setBrush(_brush(QColor(105, 240, 174, 110)))
        p.drawPolygon(house)
        # Texte "m²" centré dans le corps du mur
        font = QFont("Arial", int(s * 0.20), QFont.Bold)
        p.setFont(font)
        p.setPen(_pen(QColor(30, 160, 90), 1))
        p.drawText(QRectF(s * 0.12, s * 0.50, s * 0.76, s * 0.36),
                   Qt.AlignCenter, "m²")
    return _icon(size, draw)


def icon_perimeter(size=32) -> QIcon:
    """Forme maison contour seul = périmètre."""
    def draw(p: QPainter, s):
        # Même forme maison que surface, sans remplissage
        house = QPolygonF([
            QPointF(s * 0.50, s * 0.08),   # faîte
            QPointF(s * 0.88, s * 0.46),   # coin haut-droit
            QPointF(s * 0.88, s * 0.90),   # coin bas-droit
            QPointF(s * 0.12, s * 0.90),   # coin bas-gauche
            QPointF(s * 0.12, s * 0.46),   # coin haut-gauche
        ])
        p.setPen(_pen(_C_BLUE, 2.2))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(house)
        # Petite flèche sur le côté droit du toit (montre le pourtour)
        mid_x = (s * 0.50 + s * 0.88) / 2
        mid_y = (s * 0.08 + s * 0.46) / 2
        # Vecteur perpendiculaire au côté toit-droit, pointant vers l'extérieur
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(_C_BLUE))
        arr = QPolygonF([
            QPointF(mid_x + s * 0.10, mid_y - s * 0.03),
            QPointF(mid_x + s * 0.02, mid_y - s * 0.11),
            QPointF(mid_x + s * 0.02, mid_y + s * 0.06),
        ])
        p.drawPolygon(arr)
    return _icon(size, draw)


def icon_distance(size=32) -> QIcon:
    """Icône règle + flèches doubles pour l'outil distance."""
    import os
    png_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "icons", "distance.png"
    )
    if os.path.isfile(png_path):
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    # Fallback : flèches doubles dessinées si le fichier est absent
    def draw(p: QPainter, s):
        m = s * 0.15
        cy = s * 0.5
        p.setPen(_pen(_C_ORANGE, 2.0))
        p.drawLine(QPointF(m, cy), QPointF(s - m, cy))
        for x, dx in [(m, 1), (s - m, -1)]:
            p.setPen(Qt.NoPen)
            p.setBrush(_brush(_C_ORANGE))
            arr = QPolygonF([
                QPointF(x, cy),
                QPointF(x + dx * s * 0.14, cy - s * 0.09),
                QPointF(x + dx * s * 0.14, cy + s * 0.09),
            ])
            p.drawPolygon(arr)
        p.setPen(_pen(_C_ORANGE, 1.5))
        for x in [m, s - m]:
            p.drawLine(QPointF(x, cy - s * 0.14), QPointF(x, cy + s * 0.14))
        p.setPen(_pen(QColor(255, 183, 77, 200), 1))
        font = QFont("Arial", int(s * 0.18))
        p.setFont(font)
        p.drawText(QRectF(m, cy + s * 0.12, s - m * 2, s * 0.25), Qt.AlignCenter, "m")
    return _icon(size, draw)


def _remove_black_background(pixmap: QPixmap, threshold: int = 40) -> QPixmap:
    """Rend transparents tous les pixels quasi-noirs d'un QPixmap."""
    from PyQt5.QtGui import QImage
    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            if c.red() < threshold and c.green() < threshold and c.blue() < threshold:
                img.setPixelColor(x, y, QColor(0, 0, 0, 0))
    return QPixmap.fromImage(img)


def icon_counter(size=32) -> QIcon:
    """Icône compteur — cercles bleus 1-2-3 sur fond transparent."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Essayer d'abord counter_raw.png (fond noir à supprimer),
    # puis counter.png (déjà transparent).
    for fname, remove_bg in [("counter_raw.png", True), ("counter.png", False)]:
        png_path = os.path.join(base, "assets", "icons", fname)
        if os.path.isfile(png_path):
            pixmap = QPixmap(png_path)
            if not pixmap.isNull():
                if remove_bg:
                    pixmap = _remove_black_background(pixmap)
                return QIcon(pixmap.scaled(size, size, Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation))
    # Fallback dessiné
    def draw(p: QPainter, s):
        positions = [(0.25, 0.3), (0.7, 0.25), (0.5, 0.55), (0.2, 0.7), (0.75, 0.68)]
        colors = [_C_BLUE, _C_GREEN, _C_ORANGE, _C_BLUE, _C_GREEN]
        for i, (fx, fy) in enumerate(positions):
            cx, cy = fx * s, fy * s
            p.setPen(Qt.NoPen)
            p.setBrush(_brush(colors[i]))
            p.drawEllipse(QRectF(cx - s * 0.07, cy - s * 0.07, s * 0.14, s * 0.14))
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(QColor(239, 83, 80)))
        p.drawEllipse(QRectF(s * 0.6, s * 0.0, s * 0.38, s * 0.38))
        font = QFont("Arial", int(s * 0.2), QFont.Bold)
        p.setFont(font)
        p.setPen(_pen(_C_WHITE, 1))
        p.drawText(QRectF(s * 0.6, s * 0.0, s * 0.38, s * 0.38), Qt.AlignCenter, "5")
    return _icon(size, draw)


def icon_scale(size=32) -> QIcon:
    """Icône mètre ruban pour l'outil échelle."""
    import os
    png_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "icons", "scale.png"
    )
    if os.path.isfile(png_path):
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    # Fallback : règle graduée dessinée si le fichier est absent
    def draw(p: QPainter, s):
        m = s * 0.1
        rh = s * 0.28
        ry = (s - rh) / 2
        p.setPen(_pen(_C_ORANGE, 1.5))
        p.setBrush(_brush(QColor(255, 183, 77, 80)))
        p.drawRoundedRect(QRectF(m, ry, s - m * 2, rh), 3, 3)
        p.setPen(_pen(_C_ORANGE, 1.5))
        n_ticks = 8
        for i in range(n_ticks + 1):
            x = m + (s - m * 2) * i / n_ticks
            tick_h = rh * (0.7 if i % 4 == 0 else (0.5 if i % 2 == 0 else 0.3))
            p.drawLine(QPointF(x, ry), QPointF(x, ry + tick_h))
        cy2 = ry + rh + s * 0.14
        p.setPen(_pen(_C_ORANGE, 1.5))
        p.drawLine(QPointF(m + s * 0.08, cy2), QPointF(s - m - s * 0.08, cy2))
        for x, dx in [(m + s * 0.08, 1), (s - m - s * 0.08, -1)]:
            p.setPen(Qt.NoPen)
            p.setBrush(_brush(_C_ORANGE))
            arr = QPolygonF([
                QPointF(x, cy2),
                QPointF(x + dx * s * 0.09, cy2 - s * 0.06),
                QPointF(x + dx * s * 0.09, cy2 + s * 0.06),
            ])
            p.drawPolygon(arr)
    return _icon(size, draw)


def icon_opening(size=32) -> QIcon:
    """Mur avec ouverture (porte/fenêtre)."""
    def draw(p: QPainter, s):
        m = s * 0.1
        wall_h = s * 0.22
        cy = s * 0.5
        gap = s * 0.3
        # Mur gauche
        p.setPen(_pen(_C_GREY, 1.5))
        p.setBrush(_brush(QColor(180, 200, 220, 100)))
        p.drawRect(QRectF(m, cy - wall_h / 2, s * 0.22, wall_h))
        # Mur droit
        p.drawRect(QRectF(s - m - s * 0.22, cy - wall_h / 2, s * 0.22, wall_h))
        # Gap rouge (ouverture)
        p.setPen(_pen(_C_RED, 1.8))
        p.drawLine(QPointF(m + s * 0.22, cy - wall_h / 2),
                   QPointF(s - m - s * 0.22, cy - wall_h / 2))
        p.drawLine(QPointF(m + s * 0.22, cy + wall_h / 2),
                   QPointF(s - m - s * 0.22, cy + wall_h / 2))
        # Flèche coupure
        p.setPen(_pen(_C_RED, 1.4))
        p.drawLine(QPointF(s * 0.5, cy - wall_h / 2 - s * 0.08),
                   QPointF(s * 0.5, cy + wall_h / 2 + s * 0.08))
        # Tirets
        p.setPen(QPen(_C_RED, 1.0, Qt.DashLine))
        p.drawLine(QPointF(m + s * 0.22, cy), QPointF(s - m - s * 0.22, cy))
    return _icon(size, draw)


# ── Icônes modes ─────────────────────────────────────────────────────────────

def icon_ortho(size=32) -> QIcon:
    """Grille + angle droit = mode ortho."""
    def draw(p: QPainter, s):
        m = s * 0.12
        # Grille légère
        p.setPen(QPen(QColor(80, 120, 180, 80), 0.8, Qt.DotLine))
        step = (s - m * 2) / 4
        for i in range(5):
            x = m + step * i
            p.drawLine(QPointF(x, m), QPointF(x, s - m))
            p.drawLine(QPointF(m, x), QPointF(s - m, x))
        # Angle droit principal
        cx, cy = m, s - m
        l = s * 0.52
        p.setPen(_pen(_C_BLUE, 2.2))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy - l))  # vertical
        p.drawLine(QPointF(cx, cy), QPointF(cx + l, cy))  # horizontal
        # Petit carré = angle droit
        sq = s * 0.1
        p.setPen(_pen(_C_BLUE, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(cx, cy - sq, sq, sq))
    return _icon(size, draw)


def icon_clear(size=32) -> QIcon:
    """Balai / corbeille = effacer."""
    def draw(p: QPainter, s):
        m = s * 0.15
        # Corps poubelle
        p.setPen(_pen(_C_RED, 1.8))
        p.setBrush(_brush(QColor(239, 83, 80, 80)))
        body = QRectF(m + s * 0.06, m + s * 0.2, s - (m + s * 0.06) * 2, s - m - m - s * 0.2)
        p.drawRoundedRect(body, 3, 3)
        # Couvercle
        p.setPen(_pen(_C_RED, 2.0))
        p.drawLine(QPointF(m, m + s * 0.2), QPointF(s - m, m + s * 0.2))
        # Poignée
        p.drawLine(QPointF(s * 0.38, m + s * 0.2), QPointF(s * 0.38, m + s * 0.06))
        p.drawLine(QPointF(s * 0.38, m + s * 0.06), QPointF(s * 0.62, m + s * 0.06))
        p.drawLine(QPointF(s * 0.62, m + s * 0.06), QPointF(s * 0.62, m + s * 0.2))
        # Rayures intérieures
        p.setPen(QPen(_C_RED, 1.2, Qt.SolidLine))
        for i in range(3):
            x = body.left() + body.width() * (0.25 + i * 0.25)
            p.drawLine(QPointF(x, body.top() + body.height() * 0.2),
                       QPointF(x, body.bottom() - body.height() * 0.1))
    return _icon(size, draw)


def icon_legend(size=32) -> QIcon:
    """Petite légende avec icônes + lignes = toggle légende."""
    def draw(p: QPainter, s):
        m = s * 0.1
        # Cadre
        p.setPen(_pen(_C_GREY_D, 1.4))
        p.setBrush(_brush(QColor(30, 50, 80, 120)))
        p.drawRoundedRect(QRectF(m, m, s - m * 2, s - m * 2), 4, 4)
        # Barre titre
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(_C_BLUE_D))
        p.drawRoundedRect(QRectF(m, m, s - m * 2, s * 0.2), 4, 4)
        # Items
        items_c = [_C_GREEN, _C_BLUE, _C_ORANGE]
        for i, c in enumerate(items_c):
            y = m + s * 0.26 + i * s * 0.22
            p.setPen(Qt.NoPen)
            p.setBrush(_brush(c))
            p.drawRoundedRect(QRectF(m + s * 0.08, y, s * 0.14, s * 0.12), 2, 2)
            p.setPen(_pen(_C_GREY, 1.0))
            p.drawLine(QPointF(m + s * 0.28, y + s * 0.06),
                       QPointF(s - m - s * 0.08, y + s * 0.06))
    return _icon(size, draw)


def icon_zoom_fit(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s * 0.15
        # Plan dans le cadre
        p.setPen(_pen(_C_GREY_D, 1.5))
        p.setBrush(_brush(QColor(40, 60, 100, 100)))
        p.drawRoundedRect(QRectF(m, m, s - m * 2, s - m * 2), 3, 3)
        # Flèches vers les coins (ajuster vue)
        p.setPen(_pen(_C_BLUE, 1.8))
        corners = [(m + s * 0.06, m + s * 0.06), (s - m - s * 0.06, m + s * 0.06),
                   (m + s * 0.06, s - m - s * 0.06), (s - m - s * 0.06, s - m - s * 0.06)]
        cx2, cy2 = s / 2, s / 2
        for cx, cy in corners:
            dx, dy = cx - cx2, cy - cy2
            nd = (dx ** 2 + dy ** 2) ** 0.5
            ndx, ndy = dx / nd * s * 0.12, dy / nd * s * 0.12
            p.drawLine(QPointF(cx2 + ndx, cy2 + ndy), QPointF(cx, cy))
    return _icon(size, draw)


def icon_quit(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s * 0.12
        # Porte
        p.setPen(_pen(_C_GREY_D, 1.5))
        p.setBrush(_brush(QColor(40, 60, 80, 80)))
        p.drawRoundedRect(QRectF(m + s * 0.18, m, s * 0.54, s - m * 2), 3, 3)
        # Flèche sortie
        p.setPen(_pen(_C_RED, 2.2))
        cy2 = s / 2
        p.drawLine(QPointF(m, cy2), QPointF(m + s * 0.5, cy2))
        arr = QPolygonF([
            QPointF(m + s * 0.5, cy2),
            QPointF(m + s * 0.36, cy2 - s * 0.12),
            QPointF(m + s * 0.36, cy2 + s * 0.12),
        ])
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(_C_RED))
        p.drawPolygon(arr)
    return _icon(size, draw)


# ── Icônes édition & impression ──────────────────────────────────────────────

def icon_zoom_in(size=32) -> QIcon:
    def draw(p: QPainter, s):
        cx, cy, r = s*0.44, s*0.44, s*0.28
        p.setPen(_pen(_C_BLUE, 2.2))
        p.setBrush(_brush(QColor(41, 182, 246, 50)))
        p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))
        p.setPen(_pen(_C_BLUE, 2.4))
        p.drawLine(QPointF(cx-r*0.5, cy), QPointF(cx+r*0.5, cy))
        p.drawLine(QPointF(cx, cy-r*0.5), QPointF(cx, cy+r*0.5))
        p.setPen(_pen(_C_BLUE_D, 2.4))
        p.drawLine(QPointF(cx+r*0.72, cy+r*0.72), QPointF(s-s*0.1, s-s*0.1))
    return _icon(size, draw)


def icon_zoom_out(size=32) -> QIcon:
    def draw(p: QPainter, s):
        cx, cy, r = s*0.44, s*0.44, s*0.28
        p.setPen(_pen(_C_BLUE, 2.2))
        p.setBrush(_brush(QColor(41, 182, 246, 50)))
        p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))
        p.setPen(_pen(_C_BLUE, 2.4))
        p.drawLine(QPointF(cx-r*0.5, cy), QPointF(cx+r*0.5, cy))
        p.setPen(_pen(_C_BLUE_D, 2.4))
        p.drawLine(QPointF(cx+r*0.72, cy+r*0.72), QPointF(s-s*0.1, s-s*0.1))
    return _icon(size, draw)


def icon_zoom_select(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s*0.1
        # Rectangle de sélection pointillé
        p.setPen(QPen(_C_BLUE, 1.6, Qt.DashLine))
        p.setBrush(_brush(QColor(41, 182, 246, 30)))
        p.drawRect(QRectF(m, m+s*0.12, s*0.58, s*0.58))
        # Loupe en coin bas-droit
        cx, cy, r = s*0.72, s*0.72, s*0.18
        p.setPen(_pen(_C_BLUE_D, 2.0))
        p.setBrush(_brush(QColor(41, 182, 246, 60)))
        p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))
        p.setPen(_pen(_C_BLUE_D, 2.2))
        p.drawLine(QPointF(cx+r*0.7, cy+r*0.7),
                   QPointF(cx+r*1.4, cy+r*1.4))
    return _icon(size, draw)


def icon_zoom_100(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s*0.08
        # Cadre plan
        p.setPen(_pen(_C_GREY_D, 1.3))
        p.setBrush(_brush(QColor(200, 215, 235, 70)))
        p.drawRoundedRect(QRectF(m, m+s*0.1, s-m*2, s-m*2-s*0.1), 3, 3)
        # Texte "100%"
        font = QFont("Arial", int(s*0.22), QFont.Bold)
        p.setFont(font)
        p.setPen(_pen(_C_BLUE_D, 1))
        p.drawText(QRectF(0, s*0.3, s, s*0.45), Qt.AlignCenter, "100%")
    return _icon(size, draw)


def icon_marker(size=32) -> QIcon:
    """Icône marqueur chargée depuis le fichier PNG dédié."""
    import os
    png_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "icons", "marker.png"
    )
    if os.path.isfile(png_path):
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(
                QSize(size, size),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
    # Fallback dessiné si le fichier est absent
    def draw(p: QPainter, s):
        m = s * 0.1
        p.setBrush(_brush(QColor(255, 165, 0, 180)))
        p.setPen(_pen(QColor(120, 80, 0), 2.0))
        p.drawRect(QRectF(m, m + s * 0.2, s - m * 2, s - m * 2 - s * 0.1))
    return _icon(size, draw)


def icon_note(size=32) -> QIcon:
    """Icône bloc-note avec crayon."""
    import os
    png_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "icons", "note.png"
    )
    if os.path.isfile(png_path):
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    # Fallback dessiné si le fichier est absent
    def draw(p: QPainter, s):
        m = s * 0.08
        path = QPainterPath()
        fold = s * 0.22
        path.moveTo(m, m + s * 0.15)
        path.lineTo(s - m - fold, m + s * 0.15)
        path.lineTo(s - m, m + s * 0.15 + fold)
        path.lineTo(s - m, s - m)
        path.lineTo(m, s - m)
        path.closeSubpath()
        p.setBrush(_brush(QColor(255, 252, 180, 230)))
        p.setPen(_pen(QColor(180, 155, 30), 1.8))
        p.drawPath(path)
        fold_path = QPainterPath()
        fold_path.moveTo(s - m - fold, m + s * 0.15)
        fold_path.lineTo(s - m - fold, m + s * 0.15 + fold)
        fold_path.lineTo(s - m, m + s * 0.15 + fold)
        p.setBrush(_brush(QColor(200, 175, 30, 120)))
        p.setPen(_pen(QColor(160, 130, 20), 1.2))
        p.drawPath(fold_path)
        p.setPen(_pen(QColor(80, 60, 0), 1.5))
        for frac in [0.45, 0.58, 0.71]:
            y = s * frac
            p.drawLine(QPointF(m + s * 0.1, y), QPointF(s - m - s * 0.08, y))
    return _icon(size, draw)


def icon_copy(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s*0.1
        # Feuille arrière (décalée)
        p.setPen(_pen(_C_GREY_D, 1.4))
        p.setBrush(_brush(QColor(180, 200, 220, 80)))
        p.drawRoundedRect(QRectF(m+s*0.12, m, s*0.62, s*0.72), 3, 3)
        # Feuille avant
        p.setPen(_pen(_C_BLUE, 1.7))
        p.setBrush(_brush(QColor(41, 182, 246, 100)))
        fold = s*0.18
        path = QPainterPath()
        path.moveTo(m, m+s*0.18)
        path.lineTo(m+s*0.52-fold, m+s*0.18)
        path.lineTo(m+s*0.52, m+s*0.18+fold)
        path.lineTo(m+s*0.52, m+s*0.9)
        path.lineTo(m, m+s*0.9)
        path.closeSubpath()
        p.drawPath(path)
        # Lignes texte
        p.setPen(_pen(_C_BLUE_D, 1.1))
        for i in range(3):
            y = m+s*0.42+i*s*0.14
            p.drawLine(QPointF(m+s*0.08, y), QPointF(m+s*0.40, y))
    return _icon(size, draw)


def icon_cut(size=32) -> QIcon:
    def draw(p: QPainter, s):
        import math
        # Lame de ciseaux gauche
        p.setPen(_pen(_C_GREY_D, 2.0))
        p.drawLine(QPointF(s*0.5, s*0.5), QPointF(s*0.15, s*0.88))
        # Lame droite
        p.drawLine(QPointF(s*0.5, s*0.5), QPointF(s*0.85, s*0.88))
        # Trait supérieur (le fil)
        p.setPen(_pen(_C_GREY_D, 1.8))
        p.drawLine(QPointF(s*0.2, s*0.14), QPointF(s*0.5, s*0.5))
        p.drawLine(QPointF(s*0.8, s*0.14), QPointF(s*0.5, s*0.5))
        # Anneaux
        p.setPen(_pen(_C_BLUE, 1.8))
        p.setBrush(_brush(QColor(41, 182, 246, 80)))
        p.drawEllipse(QRectF(s*0.10, s*0.06, s*0.22, s*0.22))
        p.drawEllipse(QRectF(s*0.68, s*0.06, s*0.22, s*0.22))
    return _icon(size, draw)


def icon_paste(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s*0.1
        # Presse-papier (fond)
        p.setPen(_pen(_C_GREY_D, 1.5))
        p.setBrush(_brush(QColor(220, 230, 245, 120)))
        p.drawRoundedRect(QRectF(m, m+s*0.16, s-m*2, s-m*2-s*0.1), 4, 4)
        # Clip du haut
        p.setPen(_pen(_C_BLUE_D, 1.8))
        p.setBrush(_brush(QColor(21, 101, 192, 200)))
        p.drawRoundedRect(QRectF(s*0.32, m, s*0.36, s*0.22), 3, 3)
        # Feuille collée
        p.setPen(_pen(_C_BLUE, 1.5))
        p.setBrush(_brush(QColor(41, 182, 246, 90)))
        p.drawRoundedRect(QRectF(m+s*0.08, m+s*0.28, s*0.62, s*0.54), 3, 3)
        p.setPen(_pen(_C_BLUE_D, 1.0))
        for i in range(3):
            y = m+s*0.38+i*s*0.13
            p.drawLine(QPointF(m+s*0.15, y), QPointF(m+s*0.65, y))
    return _icon(size, draw)


def icon_print(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s*0.1
        # Corps imprimante
        p.setPen(_pen(_C_GREY_D, 1.5))
        p.setBrush(_brush(QColor(180, 200, 220, 120)))
        p.drawRoundedRect(QRectF(m, s*0.32, s-m*2, s*0.36), 5, 5)
        # Feuille sortante (bas)
        p.setPen(_pen(_C_WHITE, 1.2))
        p.setBrush(_brush(QColor(255, 255, 255, 220)))
        p.drawRect(QRectF(s*0.26, s*0.52, s*0.48, s*0.34))
        # Lignes sur la feuille
        p.setPen(_pen(_C_GREY_D, 1.0))
        for i in range(2):
            y = s*0.62 + i*s*0.12
            p.drawLine(QPointF(s*0.32, y), QPointF(s*0.68, y))
        # Feuille entrante (haut)
        p.setPen(_pen(_C_BLUE, 1.5))
        p.setBrush(_brush(QColor(41, 182, 246, 120)))
        p.drawRect(QRectF(s*0.30, m, s*0.40, s*0.34))
        # Bouton imprimante
        p.setPen(Qt.NoPen)
        p.setBrush(_brush(_C_BLUE))
        p.drawEllipse(QRectF(s*0.68, s*0.39, s*0.10, s*0.10))
    return _icon(size, draw)


# ── Icônes onglet Page ───────────────────────────────────────────────────────

def icon_rotate_left(size=32) -> QIcon:
    def draw(p: QPainter, s):
        cx, cy, r = s*0.5, s*0.5, s*0.3
        p.setPen(_pen(_C_BLUE, 2.2))
        p.setBrush(Qt.NoBrush)
        p.drawArc(int(cx-r), int(cy-r), int(r*2), int(r*2), 60*16, 240*16)
        # flèche gauche
        ax = cx - r*0.86; ay = cy - r*0.5
        arr = QPolygonF([QPointF(ax, ay), QPointF(ax+s*0.12, ay-s*0.08),
                         QPointF(ax+s*0.04, ay+s*0.1)])
        p.setPen(Qt.NoPen); p.setBrush(_brush(_C_BLUE)); p.drawPolygon(arr)
        # barre verticale
        p.setPen(_pen(_C_BLUE, 2.0))
        p.drawLine(QPointF(cx, cy-r-s*0.06), QPointF(cx, cy+r+s*0.06))
    return _icon(size, draw)


def icon_rotate_right(size=32) -> QIcon:
    def draw(p: QPainter, s):
        cx, cy, r = s*0.5, s*0.5, s*0.3
        p.setPen(_pen(_C_BLUE, 2.2))
        p.setBrush(Qt.NoBrush)
        p.drawArc(int(cx-r), int(cy-r), int(r*2), int(r*2), 120*16, -240*16)
        ax = cx + r*0.86; ay = cy - r*0.5
        arr = QPolygonF([QPointF(ax, ay), QPointF(ax-s*0.12, ay-s*0.08),
                         QPointF(ax-s*0.04, ay+s*0.1)])
        p.setPen(Qt.NoPen); p.setBrush(_brush(_C_BLUE)); p.drawPolygon(arr)
        p.setPen(_pen(_C_BLUE, 2.0))
        p.drawLine(QPointF(cx, cy-r-s*0.06), QPointF(cx, cy+r+s*0.06))
    return _icon(size, draw)


def icon_rotate_180(size=32) -> QIcon:
    def draw(p: QPainter, s):
        cx, cy, r = s*0.5, s*0.52, s*0.28
        p.setPen(_pen(_C_BLUE, 2.0))
        p.setBrush(Qt.NoBrush)
        # arc haut
        p.drawArc(int(cx-r), int(cy-r), int(r*2), int(r*2), 0, 180*16)
        ax1, ay1 = cx-r, cy
        arr1 = QPolygonF([QPointF(ax1, ay1), QPointF(ax1+s*0.1, ay1-s*0.07),
                          QPointF(ax1+s*0.1, ay1+s*0.07)])
        p.setPen(Qt.NoPen); p.setBrush(_brush(_C_BLUE)); p.drawPolygon(arr1)
        # arc bas
        p.setPen(_pen(_C_BLUE, 2.0)); p.setBrush(Qt.NoBrush)
        p.drawArc(int(cx-r), int(cy-r), int(r*2), int(r*2), 180*16, 180*16)
        ax2, ay2 = cx+r, cy
        arr2 = QPolygonF([QPointF(ax2, ay2), QPointF(ax2-s*0.1, ay2-s*0.07),
                          QPointF(ax2-s*0.1, ay2+s*0.07)])
        p.setPen(Qt.NoPen); p.setBrush(_brush(_C_BLUE)); p.drawPolygon(arr2)
        font = QFont("Arial", int(s*0.16), QFont.Bold)
        p.setFont(font); p.setPen(_pen(_C_BLUE_D, 1))
        p.drawText(QRectF(0, s*0.62, s, s*0.24), Qt.AlignCenter, "180°")
    return _icon(size, draw)


def icon_flip_h(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s*0.12
        # Ligne centrale verticale
        p.setPen(QPen(_C_GREY_D, 1.5, Qt.DashLine))
        p.drawLine(QPointF(s*0.5, m), QPointF(s*0.5, s-m))
        # Rectangle gauche (original)
        p.setPen(_pen(_C_BLUE, 1.6))
        p.setBrush(_brush(QColor(41, 182, 246, 70)))
        p.drawRect(QRectF(m, m+s*0.1, s*0.32, s*0.55))
        # Rectangle droit (miroir) - symétrique
        p.setBrush(_brush(QColor(41, 182, 246, 30)))
        p.drawRect(QRectF(s*0.5+s*0.06, m+s*0.1, s*0.32, s*0.55))
        # Flèches doubles
        p.setPen(_pen(_C_BLUE, 1.8))
        cy = s*0.72
        p.drawLine(QPointF(s*0.28, cy), QPointF(s*0.72, cy))
        for x, dx in [(s*0.28, -1), (s*0.72, 1)]:
            arr = QPolygonF([QPointF(x, cy), QPointF(x+dx*s*0.1, cy-s*0.07),
                             QPointF(x+dx*s*0.1, cy+s*0.07)])
            p.setPen(Qt.NoPen); p.setBrush(_brush(_C_BLUE)); p.drawPolygon(arr)
    return _icon(size, draw)


def icon_flip_v(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s*0.12
        p.setPen(QPen(_C_GREY_D, 1.5, Qt.DashLine))
        p.drawLine(QPointF(m, s*0.5), QPointF(s-m, s*0.5))
        p.setPen(_pen(_C_BLUE, 1.6))
        p.setBrush(_brush(QColor(41, 182, 246, 70)))
        p.drawRect(QRectF(m+s*0.1, m, s*0.55, s*0.32))
        p.setBrush(_brush(QColor(41, 182, 246, 30)))
        p.drawRect(QRectF(m+s*0.1, s*0.5+s*0.06, s*0.55, s*0.32))
        p.setPen(_pen(_C_BLUE, 1.8))
        cx = s*0.78
        p.drawLine(QPointF(cx, s*0.28), QPointF(cx, s*0.72))
        for y, dy in [(s*0.28, -1), (s*0.72, 1)]:
            arr = QPolygonF([QPointF(cx, y), QPointF(cx-s*0.07, y+dy*s*0.1),
                             QPointF(cx+s*0.07, y+dy*s*0.1)])
            p.setPen(Qt.NoPen); p.setBrush(_brush(_C_BLUE)); p.drawPolygon(arr)
    return _icon(size, draw)


def icon_brightness(size=32) -> QIcon:
    def draw(p: QPainter, s):
        cx, cy, r = s*0.5, s*0.5, s*0.22
        # Soleil
        p.setPen(_pen(_C_ORANGE, 2.0))
        p.setBrush(_brush(QColor(255, 183, 77, 120)))
        p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))
        # Rayons
        import math
        for i in range(8):
            a = math.radians(i*45)
            r1, r2 = r+s*0.06, r+s*0.13
            p.drawLine(QPointF(cx+math.cos(a)*r1, cy+math.sin(a)*r1),
                       QPointF(cx+math.cos(a)*r2, cy+math.sin(a)*r2))
        # Curseur en bas
        bar_y = s*0.84; bar_x0 = s*0.15; bar_x1 = s*0.85
        p.setPen(_pen(_C_GREY_D, 1.5))
        p.drawLine(QPointF(bar_x0, bar_y), QPointF(bar_x1, bar_y))
        # Indicateur à 65%
        ind_x = bar_x0 + (bar_x1-bar_x0)*0.65
        p.setPen(_pen(_C_ORANGE, 2.2))
        p.setBrush(_brush(_C_ORANGE))
        p.drawEllipse(QRectF(ind_x-s*0.05, bar_y-s*0.05, s*0.1, s*0.1))
    return _icon(size, draw)


def icon_crop_page(size=32) -> QIcon:
    def draw(p: QPainter, s):
        m = s*0.1
        # Plan original (grisé)
        p.setPen(_pen(_C_GREY_D, 1.2))
        p.setBrush(_brush(QColor(180, 200, 220, 60)))
        p.drawRect(QRectF(m, m, s-m*2, s-m*2))
        # Zone de recadrage
        x0, y0 = s*0.22, s*0.2
        x1, y1 = s*0.82, s*0.78
        p.setPen(_pen(_C_ORANGE, 2.0))
        p.setBrush(_brush(QColor(255, 183, 77, 40)))
        p.drawRect(QRectF(x0, y0, x1-x0, y1-y0))
        # Coins épais
        c = s*0.1
        p.setPen(_pen(_C_ORANGE, 3.0))
        for cx2, cy2, dx, dy in [(x0,y0,1,1),(x1,y0,-1,1),(x0,y1,1,-1),(x1,y1,-1,-1)]:
            p.drawLine(QPointF(cx2, cy2), QPointF(cx2+dx*c, cy2))
            p.drawLine(QPointF(cx2, cy2), QPointF(cx2, cy2+dy*c))
    return _icon(size, draw)


# ── Icônes Navigation ────────────────────────────────────────────────────────

def icon_pointer(size=32) -> QIcon:
    """Curseur flèche — mode sélection / pointeur."""
    import os
    png_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "icons", "pointer.png"
    )
    if os.path.isfile(png_path):
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    # Fallback QPainter si fichier absent
    def draw(p: QPainter, s):
        m = s * 0.12
        tip_x, tip_y = m, m
        arrow = QPolygonF([
            QPointF(tip_x, tip_y),
            QPointF(m + s*0.32, m + s*0.76),
            QPointF(m + s*0.18, m + s*0.50),
            QPointF(m + s*0.42, m + s*0.66),
            QPointF(m + s*0.56, m + s*0.82),
            QPointF(m + s*0.64, m + s*0.74),
            QPointF(m + s*0.50, m + s*0.58),
            QPointF(m + s*0.46, m + s*0.62),
        ])
        p.setPen(_pen(_C_BLUE_D, 1.5))
        p.setBrush(_brush(_C_BLUE))
        p.drawPolygon(arrow)
    return _icon(size, draw)


def icon_pan(size=32) -> QIcon:
    """Main ouverte — mode déplacement de la vue."""
    import os
    png_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "icons", "pan.png"
    )
    if os.path.isfile(png_path):
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            return QIcon(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    # Fallback QPainter si fichier absent
    def draw(p: QPainter, s):
        palm_t = s * 0.55
        p.setPen(_pen(_C_BLUE_D, 1.4))
        p.setBrush(_brush(QColor(41, 182, 246, 200)))
        p.drawEllipse(QRectF(s*0.16, palm_t, s*0.68, s*0.36))
        finger_w = s * 0.13
        finger_r = s * 0.06
        for fx in [s*0.19, s*0.33, s*0.47, s*0.61]:
            p.drawRoundedRect(QRectF(fx, s*0.12, finger_w, s*0.50), finger_r, finger_r)
        p.drawRoundedRect(QRectF(s*0.06, s*0.32, finger_w*0.9, s*0.34), finger_r, finger_r)
    return _icon(size, draw)


# ── Registre centralisé ──────────────────────────────────────────────────────

_REGISTRY = {
    "new_project":    icon_new_project,
    "open":           icon_open,
    "import_pdf":     icon_import_pdf,
    "save":           icon_save,
    "save_as":        icon_save_as,
    "open_project":   icon_open_project,
    "undo":           icon_undo,
    "redo":           icon_redo,
    "surface":        icon_surface,
    "perimeter":      icon_perimeter,
    "distance":       icon_distance,
    "counter":        icon_counter,
    "scale":          icon_scale,
    "opening":        icon_opening,
    "ortho":          icon_ortho,
    "clear":          icon_clear,
    "legend":         icon_legend,
    "zoom_fit":       icon_zoom_fit,
    "quit":           icon_quit,
    # Zoom
    "zoom_in":        icon_zoom_in,
    "zoom_out":       icon_zoom_out,
    "zoom_select":    icon_zoom_select,
    "zoom_100":       icon_zoom_100,
    # Annotations
    "marker":         icon_marker,
    "note":           icon_note,
    # Édition & impression
    "copy":           icon_copy,
    "cut":            icon_cut,
    "paste":          icon_paste,
    "print":          icon_print,
    # Onglet Page
    "rotate_left":    icon_rotate_left,
    "rotate_right":   icon_rotate_right,
    "rotate_180":     icon_rotate_180,
    "flip_h":         icon_flip_h,
    "flip_v":         icon_flip_v,
    "brightness":     icon_brightness,
    "crop_page":      icon_crop_page,
    # Navigation
    "pointer":        icon_pointer,
    "pan":            icon_pan,
}

_cache: dict = {}  # vidé à chaque démarrage


def get_icon(name: str, size: int = 32) -> QIcon:
    """Retourne l'icône depuis le registre (mise en cache)."""
    key = (name, size)
    if key not in _cache:
        fn = _REGISTRY.get(name)
        if fn:
            try:
                _cache[key] = fn(size)
            except Exception as e:
                _cache[key] = QIcon()
        else:
            _cache[key] = QIcon()
    return _cache[key]
