# ui/page_items_panel.py
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPainter, QPixmap, QIcon, QBrush, QPen
from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QToolButton, QLabel, QHeaderView,
)

from ui.icon_manager import IconManager


# ---------------------------------------------------------------------------
# Helpers de dessin d'icônes de type
# ---------------------------------------------------------------------------

def _make_type_icon(entity_type: str, size: int = 14) -> QIcon:
    """Génère une petite icône de type pour l'arbre."""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    if entity_type in ("polygon", "surface"):
        p.setPen(QPen(QColor("#0D47A1"), 1))
        p.setBrush(QBrush(QColor(21, 101, 192, 160)))
        p.drawRect(2, 2, size - 4, size - 4)

    elif entity_type in ("perimeter", "line"):
        p.setPen(QPen(QColor("#2E7D32"), 2, Qt.SolidLine, Qt.RoundCap))
        m = size // 4
        p.drawLine(m, size - m, size // 2, m)
        p.drawLine(size // 2, m, size - m, size - m)

    elif entity_type == "point":
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#E65100")))
        r = max(3, size // 3)
        cx, cy = size // 2, size // 2
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

    else:
        p.setPen(QPen(QColor("#757575"), 1))
        p.setBrush(QBrush(QColor(200, 200, 200, 120)))
        p.drawRect(2, 2, size - 4, size - 4)

    p.end()
    return QIcon(pix)


# ---------------------------------------------------------------------------
# Calcul de quantité pour une entité (individuelle ou groupe)
# ---------------------------------------------------------------------------

def _quantity_single(entity) -> float:
    """Retourne la quantité brute (float) d'une entité individuelle."""
    etype = getattr(entity, "entity_type", "")

    if etype in ("polygon", "surface"):
        try:
            if getattr(entity, "openings", None):
                return entity.calculate_net_area()
            return entity.calculate_area()
        except Exception:
            return 0.0

    elif etype in ("perimeter", "line"):
        # Utiliser la méthode native de l'entité (retourne déjà en mètres)
        if hasattr(entity, "calculate_perimeter_length"):
            try:
                return entity.calculate_perimeter_length()
            except Exception:
                pass
        # Fallback manuel
        try:
            import math
            points = getattr(entity, "points", [])
            if len(points) < 2:
                return 0.0
            ppm = getattr(entity, "pixels_per_meter", None) or 1
            total_px = sum(
                math.hypot(points[i + 1][0] - points[i][0],
                           points[i + 1][1] - points[i][1])
                for i in range(len(points) - 1)
            )
            for op in getattr(entity, "linear_openings", []):
                op_pts = getattr(op, "points", [])
                if len(op_pts) >= 2:
                    total_px -= math.hypot(
                        op_pts[-1][0] - op_pts[0][0],
                        op_pts[-1][1] - op_pts[0][1]
                    )
            return max(0.0, total_px / ppm) if ppm else 0.0
        except Exception:
            return 0.0

    elif etype == "point":
        return 1.0

    return 0.0


def _quantity_group_total(parent_entity) -> float:
    """
    Retourne la quantité totale d'un groupe (parent + tous les enfants).
    Utilise les méthodes groupées natives si disponibles.
    """
    etype = getattr(parent_entity, "entity_type", "")

    if etype in ("perimeter", "line"):
        if hasattr(parent_entity, "calculate_total_group_length"):
            try:
                return parent_entity.calculate_total_group_length()
            except Exception:
                pass

    if etype in ("polygon", "surface"):
        if hasattr(parent_entity, "calculate_total_group_area"):
            try:
                return parent_entity.calculate_total_group_area()
            except Exception:
                pass

    # Fallback : somme manuelle parent + enfants
    total = _quantity_single(parent_entity)
    for child in getattr(parent_entity, "child_entities", []):
        total += _quantity_single(child)
    return total


def _format_quantity(value: float, entity_type: str) -> str:
    """Formate une valeur numérique selon le type d'entité."""
    if entity_type in ("polygon", "surface"):
        return f"{value:.2f} m²"
    elif entity_type in ("perimeter", "line"):
        return f"{value:.2f} ml"
    elif entity_type == "point":
        return f"{int(round(value))} unité(s)"
    return f"{value:.2f}"


def _group_member_count(parent_entity) -> int:
    """Retourne le nombre total de membres dans un groupe (parent + enfants)."""
    children = getattr(parent_entity, "child_entities", []) or []
    return 1 + len(children)


# ---------------------------------------------------------------------------
# Panneau principal
# ---------------------------------------------------------------------------

class PageItemsPanel(QDockWidget):
    """
    Panneau dock affichant, pour la page PDF courante, les entités mesurées
    regroupées : une seule ligne par groupe avec la quantité totale.
    Colonnes : [icône type | nom | quantité totale | ampoule visibilité]
    """

    def __init__(self, main_window):
        super().__init__("Éléments de la page", main_window)
        self.main_window = main_window
        self._icon_manager = IconManager()
        self._bulb_on = self._icon_manager.icon("bulb_on")
        self._bulb_off = self._icon_manager.icon("bulb_off")
        self._build_ui()
        self.setMinimumWidth(240)

    # ------------------------------------------------------------------
    # Construction UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # Label page courante
        self.page_label = QLabel("Page —")
        self.page_label.setStyleSheet(
            "font-size: 10px; font-style: italic; color: #546E7A; padding: 0 2px;"
        )
        layout.addWidget(self.page_label)

        # Titre section
        title = QLabel("Éléments mesurés")
        title.setStyleSheet("font-weight: bold; font-size: 11px; color: #37474F;")
        layout.addWidget(title)

        # Arbre
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Type", "Nom", "Quantité", ""])
        self.tree.setRootIsDecorated(False)   # Pas d'arbre : tout à plat (une ligne/groupe)
        self.tree.setUniformRowHeights(True)
        self.tree.setIconSize(QSize(14, 14))
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.NoSelection)

        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.tree.setColumnWidth(3, 28)

        self.tree.setStyleSheet("""
            QTreeWidget { border: none; background: #FAFAFA; font-size: 11px; }
            QTreeWidget::item { padding: 3px 2px; }
            QTreeWidget::item:alternate { background: #F0F4F8; }
        """)

        layout.addWidget(self.tree)
        self.setWidget(container)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def refresh(self):
        """Vide et reconstruit l'arbre en temps réel depuis l'EntityManager."""
        self.tree.clear()

        # --- Mettre à jour le label de la page courante ---
        self._update_page_label()

        em = self._get_entity_manager()
        if em is None:
            return

        all_entities = em.get_all_entities()

        # --- Regroupement : une seule entrée par groupe ---
        # On ne garde que les entités "racines" (parent_entity is None)
        # Les enfants de groupe sont comptés dans le total du parent.
        seen_group_ids = set()
        rows = []  # liste de (entity, is_group, member_count)

        for ent in all_entities:
            # Ignorer les ouvertures et les enfants de groupe
            if getattr(ent, "entity_type", "") == "opening":
                continue
            if getattr(ent, "parent_entity", None) is not None:
                continue

            group_id = getattr(ent, "group_id", None)
            if group_id:
                if group_id in seen_group_ids:
                    continue  # déjà représenté par le parent
                seen_group_ids.add(group_id)
                is_group_parent = getattr(ent, "is_group_parent", False)
                if is_group_parent:
                    member_count = _group_member_count(ent)
                    rows.append((ent, True, member_count))
                else:
                    rows.append((ent, False, 1))
            else:
                rows.append((ent, False, 1))

        for (ent, is_group, count) in rows:
            item = self._make_row_item(ent, is_group, count)
            self.tree.addTopLevelItem(item)
            # Injecter le bouton ampoule
            self._add_bulb_button(item, ent)

    # ------------------------------------------------------------------
    # Construction d'une ligne
    # ------------------------------------------------------------------
    def _make_row_item(self, entity, is_group: bool, member_count: int) -> QTreeWidgetItem:
        etype = getattr(entity, "entity_type", "")
        name = getattr(entity, "name", "") or etype

        # Quantité : totale du groupe si applicable
        if is_group and member_count > 1:
            qty_value = _quantity_group_total(entity)
            # Suffixe indiquant le nombre de mesures dans le groupe
            count_suffix = f"  ×{member_count}"
        else:
            qty_value = _quantity_single(entity)
            count_suffix = ""

        quantity_str = _format_quantity(qty_value, etype)

        # Nom avec indication de groupe si plusieurs membres
        display_name = name
        if is_group and member_count > 1:
            display_name = f"{name}{count_suffix}"

        item = QTreeWidgetItem(["", display_name, quantity_str, ""])
        item.setIcon(0, _make_type_icon(etype))
        item.setData(0, Qt.UserRole, entity)
        item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)

        # Police en gras pour les groupes multi-membres
        if is_group and member_count > 1:
            from PyQt5.QtGui import QFont
            f = item.font(1)
            f.setBold(True)
            item.setFont(1, f)
            item.setFont(2, f)
            item.setForeground(1, QColor("#1A237E"))

        return item

    # ------------------------------------------------------------------
    # Bouton ampoule
    # ------------------------------------------------------------------
    def _add_bulb_button(self, item: QTreeWidgetItem, entity):
        """Ajoute le bouton ampoule dans la colonne 3 de l'item."""
        btn = QToolButton()
        btn.setFixedSize(22, 22)
        btn.setAutoRaise(True)
        visible = getattr(entity, "visible", True)
        btn.setIcon(self._bulb_on if visible else self._bulb_off)
        btn.setToolTip("Masquer" if visible else "Afficher")
        btn.clicked.connect(lambda _checked, e=entity, b=btn: self._toggle_visibility(e, b))
        self.tree.setItemWidget(item, 3, btn)

    # ------------------------------------------------------------------
    # Toggle visibilité (propage aux enfants du groupe)
    # ------------------------------------------------------------------
    def _toggle_visibility(self, entity, btn: QToolButton):
        """Bascule la visibilité de l'entité (et de ses enfants de groupe)."""
        em = self._get_entity_manager()
        if em is None:
            return
        new_visible = not getattr(entity, "visible", True)
        # apply_entity_visibility propage déjà aux child_entities
        em.apply_entity_visibility(entity, new_visible)
        btn.setIcon(self._bulb_on if new_visible else self._bulb_off)
        btn.setToolTip("Masquer" if new_visible else "Afficher")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_page_label(self):
        """Met à jour le label de la page PDF courante."""
        try:
            idx = getattr(self.main_window, "current_pdf_page_index", None)
            doc = getattr(self.main_window, "pdf_document", None)
            if idx is not None and doc is not None:
                page = doc.get_page(idx)
                page_name = getattr(page, "name", None) or f"Page {idx + 1}"
                self.page_label.setText(f"📄 {page_name}")
                return
        except Exception:
            pass
        self.page_label.setText("Page courante")

    def _get_entity_manager(self):
        try:
            return self.main_window.canvas_view.entity_manager
        except AttributeError:
            return None
