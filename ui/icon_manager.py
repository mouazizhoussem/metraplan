from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QImage, QPixmap, QColor, QPainter, QBrush, QPen, QPolygonF
from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtWidgets import QStyle


class IconManager:
    """Gestion centralisée des icônes personnalisées (SVG/PNG) avec cache et fallback."""

    def __init__(self, project_root=None, widget=None):
        if project_root is None:
            # ui/icon_manager.py -> racine projet
            project_root = Path(__file__).resolve().parents[1]

        self.project_root = Path(project_root)
        self.icons_dir = self.project_root / "assets" / "icons" / "context"
        self.fallback_icon = self.project_root / "assets" / "icons" / "fallback.svg"
        self.widget = widget

        self._cache = {}
        # Mapping clé -> liste de candidats (tolérance de nommage)
        self._map = {
            "add_group": ["add_group.svg"],
            "opening": ["opening.svg"],
            "perimeter_from_surface": ["perimeter_from_surface.svg", "Perimeter.svg"],
            "cut": ["cut.svg"],
            "copy": ["copy.svg"],
            "paste": ["paste.svg"],
            "delete": ["delete.svg"],
            "bring_front": ["bring_front.svg"],
            "send_back": ["send_back.svg"],
            "select_group": ["select_group.svg", "select_groupe.svg"],
            "select_type": ["select_type.svg", "surface.svg"],
            "select_layer": ["select_layer.svg", "move_layer.svg"],
            "clear_selection": ["clear_selection.svg", "delete.svg"],
            "move_layer": ["move_layer.svg"],
            "move_group": ["move_group.svg", "surface.svg"],
            "move_new_group": ["move_new_group.svg", "add_group.svg"],
            # Icônes dédiées menu périmètre (distinctes de Surface)
            "perimeter.insert_point": ["perimeter_insert_point.svg"],
            "perimeter.insert_point.black": ["perimeter_insert_point.svg"],
            "perimeter.add_group": ["perimeter_add_group.svg"],
            "perimeter.opening": ["perimeter_opening.svg"],
            "perimeter.opening_height": ["perimeter_opening_height.svg"],
            "perimeter.cut": ["perimeter_cut.svg", "cut.svg"],
            "perimeter.copy": ["perimeter_copy.svg", "copy.svg"],
            "perimeter.paste": ["perimeter_paste.svg", "paste.svg"],
            "perimeter.delete": ["perimeter_delete.svg", "delete.svg"],
            "perimeter.bring_front": ["perimeter_bring_front.svg", "bring_front.svg"],
            "perimeter.send_back": ["perimeter_send_back.svg", "send_back.svg"],
            # Icônes dédiées menu compteur
            "counter.add_group": ["counter_add_group.svg"],
            "counter.cut": ["counter_cut.svg", "cut.svg"],
            "counter.copy": ["counter_copy.svg", "copy.svg"],
            "counter.paste": ["counter_paste.svg", "paste.svg"],
            "counter.delete": ["counter_delete.svg", "delete.svg"],
            "counter.bring_front": ["counter_bring_front.svg", "bring_front.svg"],
            "counter.send_back": ["counter_send_back.svg", "send_back.svg"],
        }

        # Couleurs de teinte pour icônes monochromes.
        self._tint_colors = {
            "add_group": "#D4B000",
            "opening": "#D4B000",
            "perimeter_from_surface": "#D4B000",
            "cut": "#DB4437",
            "copy": "#4285F4",
            "paste": "#0F9D58",
            "delete": "#DB4437",
            "bring_front": "#5E35B1",
            "send_back": "#5E35B1",
            "select_group": "#00897B",
            "select_type": "#00897B",
            "select_layer": "#00897B",
            "clear_selection": "#6D6D6D",
            "move_layer": "#FB8C00",
            "move_group": "#FB8C00",
            "move_new_group": "#FB8C00",
            "perimeter.insert_point": "#26A69A",
            "perimeter.add_group": "#00796B",
            "perimeter.opening": "#039BE5",
            "perimeter.opening_height": "#1E88E5",
            "perimeter.cut": "#EF5350",
            "perimeter.copy": "#42A5F5",
            "perimeter.paste": "#66BB6A",
            "perimeter.delete": "#E53935",
            "perimeter.bring_front": "#7E57C2",
            "perimeter.send_back": "#5C6BC0",
            "perimeter.insert_point.black": "#000000",
            # Compteur – palette orange/ambre distincte
            "counter.add_group": "#E65100",
            "counter.cut": "#C62828",
            "counter.copy": "#1565C0",
            "counter.paste": "#2E7D32",
            "counter.delete": "#B71C1C",
            "counter.bring_front": "#4527A0",
            "counter.send_back": "#283593",
        }

        self._qt_fallback_map = {
            "add_group": QStyle.SP_FileDialogNewFolder,
            "opening": QStyle.SP_DirOpenIcon,
            "perimeter_from_surface": QStyle.SP_FileDialogDetailedView,
            "cut": QStyle.SP_TrashIcon,
            "copy": QStyle.SP_FileIcon,
            "paste": QStyle.SP_DialogOpenButton,
            "delete": QStyle.SP_TrashIcon,
            "bring_front": QStyle.SP_ArrowUp,
            "send_back": QStyle.SP_ArrowDown,
            "select_group": QStyle.SP_DialogYesButton,
            "select_type": QStyle.SP_FileDialogListView,
            "select_layer": QStyle.SP_DirIcon,
            "clear_selection": QStyle.SP_DialogCancelButton,
            "move_layer": QStyle.SP_DirIcon,
            "move_group": QStyle.SP_DialogYesButton,
            "move_new_group": QStyle.SP_FileDialogNewFolder,
            "perimeter.insert_point": QStyle.SP_DialogApplyButton,
            "perimeter.add_group": QStyle.SP_FileDialogNewFolder,
            "perimeter.opening": QStyle.SP_DirOpenIcon,
            "perimeter.opening_height": QStyle.SP_TitleBarShadeButton,
            "perimeter.cut": QStyle.SP_TrashIcon,
            "perimeter.copy": QStyle.SP_FileIcon,
            "perimeter.paste": QStyle.SP_DialogOpenButton,
            "perimeter.delete": QStyle.SP_TrashIcon,
            "perimeter.bring_front": QStyle.SP_ArrowUp,
            "perimeter.send_back": QStyle.SP_ArrowDown,
            "counter.add_group": QStyle.SP_FileDialogNewFolder,
            "counter.cut": QStyle.SP_TrashIcon,
            "counter.copy": QStyle.SP_FileIcon,
            "counter.paste": QStyle.SP_DialogOpenButton,
            "counter.delete": QStyle.SP_TrashIcon,
            "counter.bring_front": QStyle.SP_ArrowUp,
            "counter.send_back": QStyle.SP_ArrowDown,
        }

    def _load_custom_icon(self, key):
        candidates = self._map.get(key, [])
        for filename in candidates:
            file_path = self.icons_dir / filename
            if file_path.exists():
                return QIcon(str(file_path))
        return None

    def _is_monochrome(self, image):
        # Détecte une icône majoritairement monochrome (gris/noir/blanc).
        if image.isNull():
            return False
        w = image.width()
        h = image.height()
        for y in range(h):
            for x in range(w):
                c = QColor(image.pixel(x, y))
                if c.alpha() == 0:
                    continue
                if abs(c.red() - c.green()) > 12 or abs(c.green() - c.blue()) > 12:
                    return False
        return True

    def _tint_icon_if_needed(self, key, icon):
        if icon is None or icon.isNull():
            return icon
        tint_hex = self._tint_colors.get(key)
        if not tint_hex:
            return icon

        pix = icon.pixmap(20, 20)
        if pix.isNull():
            return icon

        img = pix.toImage().convertToFormat(QImage.Format_ARGB32)
        if not self._is_monochrome(img):
            return icon

        tint = QColor(tint_hex)
        for y in range(img.height()):
            for x in range(img.width()):
                src = QColor(img.pixel(x, y))
                a = src.alpha()
                if a == 0:
                    continue
                # Teinte pure en conservant l'alpha.
                img.setPixelColor(x, y, QColor(tint.red(), tint.green(), tint.blue(), a))

        return QIcon(QPixmap.fromImage(img))

    def _stabilize_icon_modes(self, icon):
        """
        Evite que Qt remplace certaines icônes par des variantes grises
        peu lisibles en état Disabled.
        """
        if icon is None or icon.isNull():
            return icon

        stabilized = QIcon()
        for size in (16, 18, 20, 24):
            pm = icon.pixmap(size, size, QIcon.Normal, QIcon.Off)
            if pm.isNull():
                continue
            for mode in (QIcon.Normal, QIcon.Active, QIcon.Selected, QIcon.Disabled):
                stabilized.addPixmap(pm, mode, QIcon.Off)
        return stabilized if not stabilized.isNull() else icon

    # ------------------------------------------------------------------
    # Icônes surface — menu contextuel
    # ------------------------------------------------------------------

    def _house_polygon(self, size: int) -> QPolygonF:
        """Pentagone 'maison' identique à icon_surface du ruban, normalisé à `size`."""
        s = size
        return QPolygonF([
            QPointF(s * 0.50, s * 0.08),   # faîte
            QPointF(s * 0.88, s * 0.46),   # coin haut-droit
            QPointF(s * 0.88, s * 0.90),   # coin bas-droit
            QPointF(s * 0.12, s * 0.90),   # coin bas-gauche
            QPointF(s * 0.12, s * 0.46),   # coin haut-gauche
        ])

    def _make_surface_add_group_icon(self, size: int = 20) -> QIcon:
        """Pentagon vert rempli + signe + vert foncé dans le coin sup. droit."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        # Pentagone rempli vert (style surface)
        green_fill = QColor(105, 240, 174, 160)
        green_pen  = QColor(30, 160, 90)
        p.setPen(QPen(green_pen, max(1, size * 0.08)))
        p.setBrush(QBrush(green_fill))
        p.drawPolygon(self._house_polygon(size))

        # Signe + vert foncé en haut à droite
        cx = int(size * 0.76)
        cy = int(size * 0.24)
        arm = max(3, int(size * 0.17))
        pen_plus = QPen(QColor("#1b5e20"), max(2, int(size * 0.12)),
                        Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen_plus)
        p.drawLine(cx - arm, cy, cx + arm, cy)
        p.drawLine(cx, cy - arm, cx, cy + arm)

        p.end()
        return QIcon(pix)

    def _make_surface_opening_icon(self, size: int = 20) -> QIcon:
        """Pentagon vert rempli + carré vide (contour rouge) symbolisant l'ouverture."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        # Pentagone rempli vert (légèrement plus transparent pour voir le carré)
        green_fill = QColor(105, 240, 174, 130)
        green_pen  = QColor(30, 160, 90)
        p.setPen(QPen(green_pen, max(1, size * 0.07)))
        p.setBrush(QBrush(green_fill))
        p.drawPolygon(self._house_polygon(size))

        # Carré vide centré dans la zone mur (sous le toit)
        sq_x = int(size * 0.30)
        sq_y = int(size * 0.52)
        sq_w = int(size * 0.40)
        sq_h = int(size * 0.32)
        p.setPen(QPen(QColor("#c62828"), max(1, int(size * 0.10)),
                      Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
        p.setBrush(QBrush(QColor(255, 255, 255, 120)))
        p.drawRect(QRectF(sq_x, sq_y, sq_w, sq_h))

        p.end()
        return QIcon(pix)

    def _make_surface_perimeter_icon(self, size: int = 20) -> QIcon:
        """Pentagon vert rempli (clair) + même pentagon contour épais bleu."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        house = self._house_polygon(size)

        # Fond vert très léger
        green_fill = QColor(105, 240, 174, 90)
        green_pen  = QColor(30, 160, 90)
        p.setPen(QPen(green_pen, max(1, size * 0.06)))
        p.setBrush(QBrush(green_fill))
        p.drawPolygon(house)

        # Contour épais bleu par dessus = périmètre
        blue = QColor("#1976d2")
        p.setPen(QPen(blue, max(2, int(size * 0.14)),
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(house)

        p.end()
        return QIcon(pix)

    def _make_perimeter_add_group_icon(self, size: int = 20) -> QIcon:
        """Pentagon contour bleu épais (style périmètre) + signe + vert foncé."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        house = self._house_polygon(size)

        # Contour épais bleu sans remplissage = style périmètre
        blue = QColor("#1976d2")
        p.setPen(QPen(blue, max(2, int(size * 0.13)),
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QBrush(QColor(25, 118, 210, 30)))
        p.drawPolygon(house)

        # Signe + vert foncé en haut à droite
        cx = int(size * 0.76)
        cy = int(size * 0.24)
        arm = max(3, int(size * 0.17))
        pen_plus = QPen(QColor("#1b5e20"), max(2, int(size * 0.12)),
                        Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen_plus)
        p.drawLine(cx - arm, cy, cx + arm, cy)
        p.drawLine(cx, cy - arm, cx, cy + arm)

        p.end()
        return QIcon(pix)

    def _make_perimeter_opening_height_icon(self, size: int = 20) -> QIcon:
        """Pentagon périmètre + flèche verticale double symbolisant la hauteur."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        # Pentagon contour bleu (périmètre) légèrement décalé à gauche
        s = size
        house = QPolygonF([
            QPointF(s * 0.42, s * 0.08),
            QPointF(s * 0.72, s * 0.38),
            QPointF(s * 0.72, s * 0.90),
            QPointF(s * 0.10, s * 0.90),
            QPointF(s * 0.10, s * 0.38),
        ])
        blue = QColor("#1976d2")
        p.setPen(QPen(blue, max(1, int(s * 0.10)),
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QBrush(QColor(25, 118, 210, 25)))
        p.drawPolygon(house)

        # Flèche verticale double (hauteur) sur le côté droit
        arr_x = int(s * 0.84)
        top_y = int(s * 0.18)
        bot_y = int(s * 0.88)
        mid_y = (top_y + bot_y) // 2
        arm = max(3, int(s * 0.14))

        orange = QColor("#e65100")
        pen_arr = QPen(orange, max(2, int(s * 0.11)),
                       Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen_arr)
        # Trait vertical
        p.drawLine(arr_x, top_y, arr_x, bot_y)
        # Pointe haut
        p.drawLine(arr_x, top_y, arr_x - arm, top_y + arm)
        p.drawLine(arr_x, top_y, arr_x + arm, top_y + arm)
        # Pointe bas
        p.drawLine(arr_x, bot_y, arr_x - arm, bot_y - arm)
        p.drawLine(arr_x, bot_y, arr_x + arm, bot_y - arm)

        p.end()
        return QIcon(pix)

    def _make_dot_icon(self, size=20, dot_radius=2, color="#000000"):
        """Crée directement un QIcon avec un petit point centré via QPainter."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.NoPen)
        cx = size // 2
        cy = size // 2
        painter.drawEllipse(cx - dot_radius, cy - dot_radius, dot_radius * 2, dot_radius * 2)
        painter.end()
        return QIcon(pix)

    def _make_counter_add_group_icon(self, size=20):
        """Icône 'ajouter compteur au groupe' : point coloré + signe + en haut à droite."""
        from PyQt5.QtGui import QPen, QFont

        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        orange = QColor("#E65100")
        dark   = QColor("#BF360C")

        # Cercle principal (représente le point compteur)
        r = int(size * 0.32)
        cx = int(size * 0.42)
        cy = int(size * 0.55)
        p.setPen(QPen(dark, max(1, int(size * 0.06))))
        p.setBrush(QBrush(orange))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Signe '+' en haut à droite
        plus_cx = int(size * 0.74)
        plus_cy = int(size * 0.26)
        arm = max(3, int(size * 0.18))
        pen_plus = QPen(QColor("#1B5E20"), max(2, int(size * 0.10)), Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen_plus)
        p.drawLine(plus_cx - arm, plus_cy, plus_cx + arm, plus_cy)
        p.drawLine(plus_cx, plus_cy - arm, plus_cx, plus_cy + arm)

        p.end()
        return QIcon(pix)

    def _make_linear_opening_icon(self, size=20):
        """Icône 'ouverture linéaire' : segment avec zone lumineuse centrale et points d'extrémité."""
        from PyQt5.QtCore import QRectF
        from PyQt5.QtGui import QPen

        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        cy    = size // 2          # centre vertical
        left  = int(size * 0.06)   # x extrémité gauche
        right = int(size * 0.94)   # x extrémité droite
        gap_l = int(size * 0.36)   # début zone ouverte
        gap_r = int(size * 0.64)   # fin zone ouverte
        ep_r  = max(2, int(size * 0.12))  # rayon des points d'extrémité
        tick_h = max(3, int(size * 0.28)) # hauteur des tirets verticaux

        dark  = QColor("#2C3E50")
        light = QColor("#87CEEB")

        # Zone lumineuse de l'ouverture
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(135, 206, 235, 180)))  # bleu ciel semi-transparent
        p.drawRect(gap_l, cy - tick_h // 2, gap_r - gap_l, tick_h)

        # Segments gauche et droit (partie solide du périmètre)
        pen = QPen(dark, max(2, int(size * 0.12)), Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(left + ep_r, cy, gap_l, cy)
        p.drawLine(gap_r, cy, right - ep_r, cy)

        # Tirets verticaux aux limites de l'ouverture
        pen2 = QPen(dark, max(1, int(size * 0.08)), Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen2)
        p.drawLine(gap_l, cy - tick_h // 2, gap_l, cy + tick_h // 2)
        p.drawLine(gap_r, cy - tick_h // 2, gap_r, cy + tick_h // 2)

        # Points d'extrémité
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(dark))
        p.drawEllipse(left, cy - ep_r, ep_r * 2, ep_r * 2)
        p.drawEllipse(right - ep_r * 2, cy - ep_r, ep_r * 2, ep_r * 2)

        p.end()
        return QIcon(pix)

    def _make_bulb_on_icon(self, size=16):
        """Ampoule allumée : cercle jaune + trait vertical en bas."""
        from PyQt5.QtGui import QPen
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        r = max(4, int(size * 0.36))
        cx = size // 2
        cy = int(size * 0.40)

        # Éclat (halo)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 230, 80, 80)))
        p.drawEllipse(cx - r - 2, cy - r - 2, (r + 2) * 2, (r + 2) * 2)

        # Corps de l'ampoule
        p.setPen(QPen(QColor("#B8860B"), max(1, int(size * 0.08))))
        p.setBrush(QBrush(QColor("#FFE040")))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Culot (trait vertical en bas)
        base_w = max(2, int(size * 0.22))
        base_h = max(2, int(size * 0.22))
        base_x = cx - base_w // 2
        base_y = cy + r
        p.setPen(QPen(QColor("#888"), max(1, int(size * 0.08))))
        p.setBrush(QBrush(QColor("#CCC")))
        p.drawRect(base_x, base_y, base_w, base_h)

        p.end()
        return QIcon(pix)

    def _make_bulb_off_icon(self, size=16):
        """Ampoule éteinte : même forme en gris."""
        from PyQt5.QtGui import QPen
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        r = max(4, int(size * 0.36))
        cx = size // 2
        cy = int(size * 0.40)

        # Corps gris
        p.setPen(QPen(QColor("#888"), max(1, int(size * 0.08))))
        p.setBrush(QBrush(QColor("#BDBDBD")))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Culot
        base_w = max(2, int(size * 0.22))
        base_h = max(2, int(size * 0.22))
        base_x = cx - base_w // 2
        base_y = cy + r
        p.setPen(QPen(QColor("#888"), max(1, int(size * 0.08))))
        p.setBrush(QBrush(QColor("#9E9E9E")))
        p.drawRect(base_x, base_y, base_w, base_h)

        p.end()
        return QIcon(pix)

    def icon(self, key):
        # Icônes générées programmatiquement (rendu garanti, pas de SVG).
        if key == "add_group":
            return self._make_surface_add_group_icon(size=20)
        if key == "opening":
            return self._make_surface_opening_icon(size=20)
        if key == "perimeter_from_surface":
            return self._make_surface_perimeter_icon(size=20)
        if key == "perimeter.add_group":
            return self._make_perimeter_add_group_icon(size=20)
        if key == "perimeter.opening_height":
            return self._make_perimeter_opening_height_icon(size=20)
        if key == "perimeter.insert_point.black":
            return self._make_dot_icon(size=20, dot_radius=2, color="#000000")
        if key == "perimeter.opening":
            return self._make_linear_opening_icon(size=20)
        if key == "counter.add_group":
            return self._make_counter_add_group_icon(size=20)
        if key == "bulb_on":
            return self._make_bulb_on_icon(size=16)
        if key == "bulb_off":
            return self._make_bulb_off_icon(size=16)

        # Les icônes périmètre changent souvent pendant les ajustements UX :
        # on évite le cache pour refléter immédiatement les SVG modifiés.
        use_cache = not str(key).startswith("perimeter.")
        if use_cache and key in self._cache:
            return self._cache[key]

        icon = self._load_custom_icon(key)

        if icon is not None and not icon.isNull():
            icon = self._tint_icon_if_needed(key, icon)

        # Fallback style Qt si custom absent
        if (icon is None or icon.isNull()) and self.widget:
            pixmap_enum = self._qt_fallback_map.get(key)
            if pixmap_enum is not None:
                icon = self.widget.style().standardIcon(pixmap_enum)

        # Fallback final fichier
        if icon is None or icon.isNull():
            if self.fallback_icon.exists():
                icon = QIcon(str(self.fallback_icon))
            else:
                icon = QIcon()

        icon = self._stabilize_icon_modes(icon)

        if use_cache:
            self._cache[key] = icon
        return icon
