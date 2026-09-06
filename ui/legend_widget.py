# ui/legend_widget.py
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter, QFont, QPainterPath


# ── Positions des 6 handles (TC/BC supprimés : hauteur = auto-contenu) ───────
_H_TL = 0   # top-left
_H_TR = 2   # top-right
_H_ML = 3   # mid-left
_H_MR = 4   # mid-right
_H_BL = 5   # bottom-left
_H_BR = 7   # bottom-right

_HANDLE_ROLES = (_H_TL, _H_TR, _H_ML, _H_MR, _H_BL, _H_BR)

_HANDLE_CURSORS = {
    _H_TL: Qt.SizeFDiagCursor, _H_TR: Qt.SizeBDiagCursor,
    _H_BL: Qt.SizeBDiagCursor, _H_BR: Qt.SizeFDiagCursor,
    _H_ML: Qt.SizeHorCursor,   _H_MR: Qt.SizeHorCursor,
}


class _ResizeHandle(QGraphicsRectItem):
    """Handle de redimensionnement pour la LegendWidget."""

    SIZE = 10

    def __init__(self, role, legend, parent):
        super().__init__(-self.SIZE / 2, -self.SIZE / 2, self.SIZE, self.SIZE, parent)
        self.role = role
        self.legend = legend
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, False)
        self.setAcceptHoverEvents(True)
        self.setZValue(1010)
        self._dragging = False
        self._press_scene = None
        self._orig_rect = None
        self._orig_pos = None
        self._draw_normal()

    def _draw_normal(self):
        self.setBrush(QBrush(QColor(33, 150, 243)))
        self.setPen(QPen(QColor(255, 255, 255), 1.5))

    def _draw_hover(self):
        self.setBrush(QBrush(QColor(255, 193, 7)))
        self.setPen(QPen(QColor(255, 255, 255), 1.5))

    def hoverEnterEvent(self, event):
        self._draw_hover()
        self.setCursor(_HANDLE_CURSORS.get(self.role, Qt.SizeAllCursor))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._draw_normal()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._press_scene = event.scenePos()
            self._orig_rect  = QRectF(self.legend.rect())
            self._orig_pos   = QPointF(self.legend.pos())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._dragging:
            super().mouseMoveEvent(event)
            return
        dx = (event.scenePos() - self._press_scene).x()
        r = QRectF(self._orig_rect)
        p = QPointF(self._orig_pos)
        min_w = 160

        # Handles droits (MR, TR, BR) : étendre vers la droite
        if self.role in (_H_MR, _H_TR, _H_BR):
            r.setWidth(max(min_w, r.width() + dx))
        # Handles gauches (ML, TL, BL) : étendre vers la gauche (déplace x)
        elif self.role in (_H_ML, _H_TL, _H_BL):
            new_w = max(min_w, r.width() - dx)
            r.setWidth(new_w)
            p.setX(self._orig_pos.x() + self._orig_rect.width() - new_w)

        # La hauteur n'est jamais modifiée manuellement : elle suit le contenu
        self.legend._resize_to(r, p)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()


class LegendWidget(QGraphicsRectItem):
    """Widget de légende Material Design pour afficher les objets et leurs mesures"""

    def __init__(self, entity_manager, scale_manager=None, parent=None):
        super().__init__(parent)
        self.entity_manager = entity_manager
        self.scale_manager = scale_manager
        self.setFlag(QGraphicsItem.ItemIsMovable, True)    # déplaçable librement sauf en mode resize
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setZValue(1000)  # Toujours au-dessus

        # Style Material Design
        self.bg_color = QColor(255, 255, 255, 250)
        self.border_color = QColor(224, 224, 224)
        self.title_color = QColor(66, 66, 66)
        self.text_color = QColor(97, 97, 97)
        self.accent_color = QColor(33, 150, 243)

        # Dimensions de base (avant échelle)
        self.base_padding = 16
        self.base_line_height = 28
        self.base_icon_size = 16
        self.base_min_width = 250
        self.base_title_height = 40
        self.base_gap_icon_text = 8
        self.base_gap_name_measure = 28

        # Dimensions scalées (initialisées via apply_scale)
        self.padding = self.base_padding
        self.line_height = self.base_line_height
        self.icon_size = self.base_icon_size
        self.min_width = self.base_min_width
        self.title_height = self.base_title_height
        self.gap_icon_text = self.base_gap_icon_text
        self.gap_name_measure = self.base_gap_name_measure

        # Police (base)
        self.base_title_font = QFont("Segoe UI", 13, QFont.Bold)
        self.base_content_font = QFont("Segoe UI", 10)
        self.base_measure_font = QFont("Segoe UI", 10, QFont.Bold)
        self.title_font = QFont(self.base_title_font)
        self.content_font = QFont(self.base_content_font)
        self.measure_font = QFont(self.base_measure_font)

        # Ombre portée
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        # Position initiale (coin supérieur gauche)
        self.initial_pos = QPointF(20, 20)
        self.setPos(self.initial_pos)

        # Appliquer l'échelle au démarrage et écouter les changements
        self.apply_scale()
        if self.scale_manager:
            self.scale_manager.scale_changed.connect(self.on_scale_changed)

        # Cache de layout
        self._name_col_width = 0
        self._measure_col_width = 0

        # Mode redimensionnement manuel (toggle par double-clic)
        self._resize_mode = False
        self._handles: list = []
        self.setAcceptHoverEvents(True)
        # Dimensions imposées manuellement (None = auto)
        self._manual_width: float = None
        self._manual_height: float = None
        # Facteur d'échelle utilisateur (calculé depuis la taille manuelle)
        self._user_scale: float = 1.0
        # Taille auto de référence (calculée sans user_scale)
        self._base_auto_width: float = None
        self._base_auto_height: float = None

        self.update_legend()

    def on_scale_changed(self, new_scale):
        """Réagit aux changements d'échelle"""
        self.apply_scale()
        self.update_legend()

    def apply_scale(self):
        """Applique l'échelle aux dimensions et polices"""
        if not self.scale_manager:
            self.padding          = self.base_padding
            self.line_height      = self.base_line_height
            self.icon_size        = self.base_icon_size
            self.min_width        = self.base_min_width
            self.title_height     = self.base_title_height
            self.gap_icon_text    = self.base_gap_icon_text
            self.gap_name_measure = self.base_gap_name_measure
            self.title_font       = QFont(self.base_title_font)
            self.content_font     = QFont(self.base_content_font)
            self.measure_font     = QFont(self.base_measure_font)
            # Appliquer le facteur d'échelle utilisateur
            us = getattr(self, '_user_scale', 1.0)
            if us != 1.0:
                self.padding          = int(self.padding         * us)
                self.line_height      = int(max(14, self.line_height  * us))
                self.icon_size        = int(max(8,  self.icon_size    * us))
                self.min_width        = int(self.min_width       * us)
                self.title_height     = int(max(20, self.title_height * us))
                self.gap_icon_text    = int(max(4,  self.gap_icon_text   * us))
                self.gap_name_measure = int(max(6,  self.gap_name_measure * us))
                self.title_font.setPointSizeF(
                    max(5.0, self.title_font.pointSizeF() * us))
                self.content_font.setPointSizeF(
                    max(5.0, self.content_font.pointSizeF() * us))
                self.measure_font.setPointSizeF(
                    max(5.0, self.measure_font.pointSizeF() * us))
            return

        self.padding = self.scale_manager.scale_bubble_padding(self.base_padding)
        self.icon_size = int(self.scale_manager.scale_size(self.base_icon_size))
        self.line_height = int(self.scale_manager.scale_size(self.base_line_height))
        self.min_width = int(self.scale_manager.scale_size(self.base_min_width))
        self.title_height = int(self.scale_manager.scale_size(self.base_title_height))
        self.gap_icon_text = int(self.scale_manager.scale_size(self.base_gap_icon_text))
        self.gap_name_measure = int(self.scale_manager.scale_size(self.base_gap_name_measure))

        # Garantir des minimums lisibles
        self.icon_size = max(10, self.icon_size)
        self.line_height = max(18, self.line_height)
        self.title_height = max(26, self.title_height)
        self.gap_icon_text = max(6, self.gap_icon_text)
        self.gap_name_measure = max(8, self.gap_name_measure)

        # Polices scalées
        scaled_title_font = QFont(self.base_title_font)
        scaled_title_font.setPointSize(
            self.scale_manager.scale_font_size(self.base_title_font.pointSize()))
        self.title_font = scaled_title_font

        scaled_content_font = QFont(self.base_content_font)
        scaled_content_font.setPointSize(
            self.scale_manager.scale_font_size(self.base_content_font.pointSize()))
        self.content_font = scaled_content_font

        scaled_measure_font = QFont(self.base_measure_font)
        scaled_measure_font.setPointSize(
            self.scale_manager.scale_font_size(self.base_measure_font.pointSize()))
        self.measure_font = scaled_measure_font

        # Appliquer le facteur d'échelle utilisateur (redimensionnement manuel)
        us = getattr(self, '_user_scale', 1.0)
        if us != 1.0:
            self.padding         = int(self.padding         * us)
            self.line_height     = int(max(14, self.line_height  * us))
            self.icon_size       = int(max(8,  self.icon_size    * us))
            self.min_width       = int(self.min_width       * us)
            self.title_height    = int(max(20, self.title_height * us))
            self.gap_icon_text   = int(max(4,  self.gap_icon_text   * us))
            self.gap_name_measure = int(max(6, self.gap_name_measure * us))
            self.title_font.setPointSizeF(
                max(5.0, self.title_font.pointSizeF() * us))
            self.content_font.setPointSizeF(
                max(5.0, self.content_font.pointSizeF() * us))
            self.measure_font.setPointSizeF(
                max(5.0, self.measure_font.pointSizeF() * us))

    def update_legend(self):
        """Met à jour le contenu de la légende"""
        from PyQt5.QtGui import QFontMetrics

        entities = self.get_visible_entities()

        if entities:
            max_name_text    = max((e['name']    for e in entities), key=len, default="")
            max_measure_text = max((e['measure'] for e in entities), key=len, default="")
        else:
            max_name_text    = "Aucun objet"
            max_measure_text = "0,00 m²"

        # ── Passe 1 : taille auto de référence (user_scale=1.0) ──────────────
        saved_us = self._user_scale
        self._user_scale = 1.0
        self.apply_scale()

        nm1 = QFontMetrics(self.content_font)
        mm1 = QFontMetrics(self.measure_font)
        nc1 = max(nm1.horizontalAdvance(max_name_text), 60)
        mc1 = max(mm1.horizontalAdvance(max_measure_text), 60)
        auto_w = max(self.min_width, int(
            self.padding * 2 + self.icon_size + self.gap_icon_text
            + nc1 + self.gap_name_measure + mc1))
        content_h1     = len(entities) * self.line_height if entities else self.line_height
        auto_h         = self.title_height + content_h1 + self.padding * 2
        self._base_auto_width  = auto_w
        self._base_auto_height = auto_h

        # ── Calcul du facteur d'échelle utilisateur ──────────────────────────
        if self._manual_width is not None:
            self._user_scale = max(0.3, self._manual_width / max(self._base_auto_width, 1))
        else:
            self._user_scale = 1.0

        # ── Passe 2 : appliquer l'échelle finale ─────────────────────────────
        self.apply_scale()

        name_metrics    = QFontMetrics(self.content_font)
        measure_metrics = QFontMetrics(self.measure_font)
        self._name_col_width    = max(name_metrics.horizontalAdvance(max_name_text),    60)
        self._measure_col_width = max(measure_metrics.horizontalAdvance(max_measure_text), 60)

        computed_width = (
            self.padding * 2
            + self.icon_size
            + self.gap_icon_text
            + self._name_col_width
            + self.gap_name_measure
            + self._measure_col_width
        )
        total_width  = max(self.min_width, int(computed_width))
        content_height = len(entities) * self.line_height if entities else self.line_height
        total_height   = self.title_height + content_height + self.padding * 2

        # Largeur manuelle respectée ; hauteur TOUJOURS auto selon le contenu
        if self._manual_width is not None:
            total_width = max(160, int(self._manual_width))

        self.setRect(0, 0, total_width, total_height)

        if self._handles:
            self._reposition_handles()

        self.update()

    def _smart_qty(self, entity):
        """Calcule une quantité dynamique (m, m², m³, U) selon le type et dimensions."""
        etype = getattr(entity, 'entity_type', '')
        height = float(getattr(entity, 'height', 0.0) or 0.0)
        thick = float(getattr(entity, 'thickness', 0.0) or 0.0)
        is_grp = bool(getattr(entity, 'is_group_parent', False))
        children = list(getattr(entity, 'child_entities', []) or [])
        members = [entity] + children if (is_grp and children) else [entity]

        # Surface
        if etype in ('polygon', 'surface'):
            # Volume si épaisseur (dalle) OU hauteur renseignée
            if height > 0 or thick > 0:
                vol = 0.0
                for m in members:
                    if hasattr(m, 'calculate_volume'):
                        try:
                            vol += float(m.calculate_volume() or 0.0)
                        except Exception:
                            pass
                return vol, "m³"
            if is_grp and children and hasattr(entity, 'calculate_total_group_area'):
                try:
                    return float(entity.calculate_total_group_area() or 0.0), "m²"
                except Exception:
                    pass
            try:
                if getattr(entity, 'openings', None):
                    return float(entity.calculate_net_area() or 0.0), "m²"
                return float(entity.calculate_area() or 0.0), "m²"
            except Exception:
                return 0.0, "m²"

        # Périmètre / ligne
        if etype in ('perimeter', 'line', 'distance'):
            if height > 0 and thick > 0:
                vol = 0.0
                for m in members:
                    if hasattr(m, 'calculate_volume'):
                        try:
                            vol += float(m.calculate_volume() or 0.0)
                        except Exception:
                            pass
                return vol, "m³"
            if height > 0:
                surf = 0.0
                for m in members:
                    if hasattr(m, 'calculate_surface_laterale'):
                        try:
                            surf += float(m.calculate_surface_laterale() or 0.0)
                        except Exception:
                            pass
                return surf, "m²"
            if is_grp and children and hasattr(entity, 'calculate_total_group_length'):
                try:
                    return float(entity.calculate_total_group_length() or 0.0), "m"
                except Exception:
                    pass
            try:
                return float(entity.calculate_perimeter_length() or 0.0), "m"
            except Exception:
                if hasattr(entity, 'calculate_distance'):
                    try:
                        return float(entity.calculate_distance() or 0.0), "m"
                    except Exception:
                        pass
                return 0.0, "m"

        # Compteur
        if etype == 'point':
            count = 1
            gid = getattr(entity, 'group_id', None)
            if gid and self.entity_manager and hasattr(self.entity_manager, 'get_points_by_group'):
                try:
                    count = len(self.entity_manager.get_points_by_group(gid))
                except Exception:
                    pass
            length = float(getattr(entity, 'length', 0.0) or 0.0)
            height = float(getattr(entity, 'height', 0.0) or 0.0)
            thick = float(getattr(entity, 'thickness', 0.0) or 0.0)
            if length > 0 and height > 0 and thick > 0:
                return length * height * thick * count, "m³"
            if length > 0 and height > 0:
                return length * height * count, "m²"
            if length > 0:
                return length * count, "m"
            return float(count), "u."

        return 0.0, ""

    def _fmt_qty(self, value: float, unit: str) -> str:
        if unit == "m³":
            return f"{value:.2f} m³"
        if unit == "m²":
            return f"{value:.2f} m²"
        if unit == "m":
            return f"{value:.2f} m"
        if unit == "u.":
            return f"{int(round(value))} U"
        return f"{value:.2f}" if value else "0.00"

    def get_visible_entities(self):
        """Récupère la liste des entités visibles, regroupées par groupe ou par nom"""
        if not self.entity_manager or not hasattr(self.entity_manager, 'entities'):
            return []

        # Dictionnaire pour regrouper: {clé: {'color': ..., 'type': ..., 'values': [], 'entity': ...}}
        grouped_entities = {}
        processed_entities = set()  # Pour éviter de traiter les enfants

        for entity_id, entity in self.entity_manager.entities.items():
            # Ignorer les entités déjà traitées (enfants)
            if entity_id in processed_entities:
                continue

            is_visible = True
            if hasattr(entity, 'is_visible'):
                try:
                    is_visible = bool(entity.is_visible())
                except Exception:
                    is_visible = bool(getattr(entity, 'visible', True))
            else:
                is_visible = bool(getattr(entity, 'visible', True))

            if is_visible:
                # Filtrer les types non pertinents pour la légende
                # (ouvertures et distances — toujours à 0.00)
                entity_type = getattr(entity, 'entity_type', '')
                if entity_type in ('opening', 'distance'):
                    continue

                # Ignorer les surfaces enfants (elles seront comptées avec leur parent)
                if hasattr(entity, 'parent_entity') and entity.parent_entity is not None:
                    processed_entities.add(entity_id)
                    continue

                name = getattr(entity, 'name', f'Objet {entity_id}')
                # Ne jamais afficher l'échelle de référence dans la légende
                if isinstance(name, str) and name.strip().lower() == "échelle de référence":
                    continue
                color = getattr(entity, 'color', QColor(100, 100, 100))
                entity_type = getattr(entity, 'entity_type', 'unknown')

                # Déterminer la clé de regroupement
                # Si c'est un parent de groupe, utiliser le group_id
                # Sinon, utiliser le nom
                is_group_parent = getattr(entity, 'is_group_parent', False)
                if is_group_parent:
                    group_key = f"group_{getattr(entity, 'group_id', name)}"
                else:
                    group_key = f"name_{name}"

                # Récupérer la valeur numérique
                # Pour les groupes parents, utiliser le total du groupe
                if is_group_parent:
                    # Pour les surfaces
                    if hasattr(entity, 'calculate_total_group_area'):
                        value = entity.calculate_total_group_area()
                    # ✅ NOUVEAU: Pour les périmètres
                    elif hasattr(entity, 'calculate_total_group_length'):
                        value = entity.calculate_total_group_length()
                    else:
                        value = self.get_entity_numeric_value(entity)

                    # Compter le parent + les enfants
                    count = 1 + len(getattr(entity, 'child_entities', []))
                    # Marquer les enfants comme traités
                    for child in getattr(entity, 'child_entities', []):
                        if hasattr(child, 'entity_id'):
                            processed_entities.add(child.entity_id)
                else:
                    value = self.get_entity_numeric_value(entity)
                    count = 1

                # Regrouper
                if group_key not in grouped_entities:
                    grouped_entities[group_key] = {
                        'name': name,
                        'color': color,
                        'type': entity_type,
                        'entities': [],
                        'values': [],
                        'count': 0
                    }

                # Ajouter la valeur au groupe
                grouped_entities[group_key]['entities'].append(entity)
                grouped_entities[group_key]['values'].append(value)
                grouped_entities[group_key]['count'] += count

        # Convertir en liste avec totaux
        entities_data = []
        for group_key, data in grouped_entities.items():
            # Calculer le total
            total_value = sum(data['values'])
            count = data['count']

            # Calcul dynamique aligné avec le relevé quantitatif
            entities = data.get('entities', [])
            ref = entities[0] if entities else None
            if ref:
                qty_val, qty_unit = self._smart_qty(ref)
                # Agrégation fallback si plusieurs entités sans liens de groupe explicites
                if getattr(ref, 'entity_type', '') != 'point' and len(entities) > 1:
                    has_linked_group = any(
                        bool(getattr(ent, 'is_group_parent', False))
                        and bool(getattr(ent, 'child_entities', []) or [])
                        for ent in entities
                    )
                    if not has_linked_group:
                        agg_val = 0.0
                        same_unit_only = True
                        for ent in entities:
                            ev, eu = self._smart_qty(ent)
                            if eu != qty_unit:
                                same_unit_only = False
                                break
                            agg_val += float(ev or 0.0)
                        if same_unit_only:
                            qty_val = agg_val
                total_value = qty_val
                measure_text = self._fmt_qty(qty_val, qty_unit)
            else:
                measure_text = f"{total_value:.2f}"

            # Ajouter le nombre d'items si > 1
            if count > 1:
                display_name = f"{data['name']} (×{count})"
            else:
                display_name = data['name']

            entities_data.append({
                'name': display_name,
                'color': data['color'],
                'type': data['type'],
                'measure': measure_text
            })

        return entities_data

    def get_entity_numeric_value(self, entity):
        """Récupère la valeur numérique d'une entité (pour addition) - TOUJOURS avec surface nette"""
        if hasattr(entity, 'entity_type'):
            if entity.entity_type == 'surface' or entity.entity_type == 'polygon':
                # ✅ TOUJOURS utiliser calculate_net_area() qui gère automatiquement les ouvertures
                if hasattr(entity, 'calculate_net_area'):
                    return entity.calculate_net_area()
                elif hasattr(entity, 'calculate_area'):
                    return entity.calculate_area()
            elif entity.entity_type == 'perimeter':
                if hasattr(entity, 'calculate_perimeter_length'):
                    return entity.calculate_perimeter_length()
            elif entity.entity_type == 'distance':
                if hasattr(entity, 'calculate_distance'):
                    return entity.calculate_distance()
            elif entity.entity_type == 'point':
                return 1.0

        return 0.0

    def get_entity_measure(self, entity):
        """Récupère la mesure d'une entité (version texte - gardée pour compatibilité)"""
        value = self.get_entity_numeric_value(entity)

        if hasattr(entity, 'entity_type'):
            if entity.entity_type == 'surface' or entity.entity_type == 'polygon':
                return f"{value:.2f} m²"
            elif entity.entity_type == 'perimeter':
                return f"{value:.2f} m"
            elif entity.entity_type == 'distance':
                return f"{value:.2f} m"

        return "---"

    def paint(self, painter, option, widget=None):
        """Dessine la légende avec style Material Design"""
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()

        # Fond blanc avec coins arrondis
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        painter.fillPath(path, QBrush(self.bg_color))

        # Bordure subtile
        painter.setPen(QPen(self.border_color, 1))
        painter.drawPath(path)

        # En-tête avec ligne d'accent
        painter.fillRect(
            QRectF(0, 0, rect.width(), 4),
            QBrush(self.accent_color)
        )

        # Titre "Légende"
        painter.setPen(QPen(self.title_color))
        painter.setFont(self.title_font)
        title_rect = QRectF(self.padding, 10, rect.width() -
                            self.padding * 2, self.title_height)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, "Légende")

        # Ligne de séparation sous le titre
        y_separator = self.title_height
        painter.setPen(QPen(QColor(224, 224, 224), 1))
        painter.drawLine(
            QPointF(self.padding, y_separator),
            QPointF(rect.width() - self.padding, y_separator)
        )

        # Contenu - Liste des entités
        entities = self.get_visible_entities()

        if not entities:
            # Message si aucun objet
            painter.setPen(QPen(QColor(158, 158, 158)))
            painter.setFont(QFont("Segoe UI", 9, QFont.StyleItalic))
            no_data_rect = QRectF(
                self.padding,
                self.title_height + self.padding,
                rect.width() - self.padding * 2,
                self.line_height
            )
            painter.drawText(no_data_rect, Qt.AlignLeft |
                             Qt.AlignVCenter, "Aucun objet")
        else:
            y_offset = self.title_height + self.padding

            for entity_info in entities:
                # Icône de couleur (carré arrondi)
                icon_rect = QRectF(
                    self.padding,
                    y_offset + (self.line_height - self.icon_size) / 2,
                    self.icon_size,
                    self.icon_size
                )
                
                # CORRECTION: Gérer entity_info['color'] qui peut être string ou tuple
                color_data = entity_info['color']
                if isinstance(color_data, str):
                    # C'est une string comme "#45ffb74d"
                    q_color = QColor(color_data)
                elif isinstance(color_data, tuple):
                    # C'est un tuple (R, G, B, A)
                    q_color = QColor(*color_data)
                else:
                    # Fallback
                    q_color = QColor(0, 0, 255, 179)
                
                painter.setBrush(QBrush(q_color))
                painter.setPen(QPen(q_color.darker(120), 1))
                painter.drawRoundedRect(icon_rect, 3, 3)

                # ⭐ NOUVEAU: Badge de comptage si > 1
                if entity_info.get('count', 1) > 1:
                    badge_size = 14
                    badge_x = self.padding + self.icon_size - badge_size / 2
                    badge_y = y_offset + \
                        (self.line_height - self.icon_size) / 2 - badge_size / 2

                    # Cercle pour le badge
                    painter.setBrush(QBrush(self.accent_color))
                    painter.setPen(QPen(Qt.white, 1))
                    painter.drawEllipse(
                        QRectF(badge_x, badge_y, badge_size, badge_size))

                    # Nombre dans le badge
                    painter.setPen(QPen(Qt.white))
                    painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                    badge_rect = QRectF(
                        badge_x, badge_y, badge_size, badge_size)
                    painter.drawText(badge_rect, Qt.AlignCenter,
                                     str(entity_info['count']))

                # Nom de l'entité
                painter.setPen(QPen(self.text_color))
                painter.setFont(self.content_font)
                name_x = self.padding + self.icon_size + self.gap_icon_text
                name_rect = QRectF(
                    name_x,
                    y_offset,
                    self._name_col_width,
                    self.line_height
                )
                painter.drawText(name_rect, Qt.AlignLeft |
                                 Qt.AlignVCenter, entity_info['name'])

                # Mesure (à droite, en gras)
                painter.setPen(QPen(self.accent_color))
                painter.setFont(self.measure_font)
                measure_x = name_x + self._name_col_width + self.gap_name_measure
                measure_rect = QRectF(
                    measure_x,
                    y_offset,
                    self._measure_col_width,
                    self.line_height
                )
                painter.drawText(measure_rect, Qt.AlignRight |
                                 Qt.AlignVCenter, entity_info['measure'])

                y_offset += self.line_height

    # ── Handles de redimensionnement ────────────────────────────────────────

    def _create_handles(self):
        """Crée les 6 handles de redimensionnement (largeur seulement)."""
        for h in self._handles:
            if h.scene():
                h.scene().removeItem(h)
        self._handles.clear()
        for role in _HANDLE_ROLES:
            h = _ResizeHandle(role, self, self)
            self._handles.append(h)
        self._reposition_handles()

    def _reposition_handles(self):
        """Place les 6 handles aux coins/milieux-gauche/milieux-droit du rect actuel."""
        r = self.rect()
        x0, y0, w, h = r.x(), r.y(), r.width(), r.height()
        cy = y0 + h / 2
        positions = {
            _H_TL: QPointF(x0,     y0),
            _H_TR: QPointF(x0 + w, y0),
            _H_ML: QPointF(x0,     cy),
            _H_MR: QPointF(x0 + w, cy),
            _H_BL: QPointF(x0,     y0 + h),
            _H_BR: QPointF(x0 + w, y0 + h),
        }
        for hdl in self._handles:
            hdl.setPos(positions[hdl.role])

    def _show_handles(self, visible: bool):
        for h in self._handles:
            h.setVisible(visible)

    def _resize_to(self, new_rect: QRectF, new_pos: QPointF):
        """Redimensionne la légende en largeur ; hauteur reste auto-contenu."""
        self._manual_width = new_rect.width()
        # _manual_height n'est jamais stocké : hauteur suit toujours le contenu
        self.setPos(new_pos)
        self.update_legend()  # recalcule user_scale, fonts, setRect, repositionne handles

    # ── Événements souris ───────────────────────────────────────────────────

    def snap_to_plan_corner(self, plan_rect: QRectF, margin: int = 20):
        """Positionne la légende dans le coin supérieur-gauche du plan chargé."""
        self.setPos(plan_rect.left() + margin, plan_rect.top() + margin)

    # ── Événements souris ───────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        """Double-clic : entre en mode redimensionnement (bloque le déplacement)."""
        if event.button() == Qt.LeftButton:
            if not self._resize_mode:
                self._resize_mode = True
                if not self._handles:
                    self._create_handles()
                self._show_handles(True)
                self.setFlag(QGraphicsItem.ItemIsMovable, False)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def exit_resize_mode(self):
        """Cache les handles, quitte le mode resize et réactive le déplacement."""
        if self._resize_mode:
            self._resize_mode = False
            self._show_handles(False)
            self.setFlag(QGraphicsItem.ItemIsMovable, True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._resize_mode:
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        if not self._resize_mode:
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)
