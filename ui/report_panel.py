# ui/report_panel.py
"""
Panneau du rapport de quantités — onglet Rapport du ruban.

4 onglets :
  1. Par page      — arbre des mesures par page avec items BPU
  2. Devis général — tableau récapitulatif financier (édition prix inline)
  3. Attachement   — justificatif détaillé des calculs par article
  4. B.P.U.        — bordereau des prix avec montants en lettres (standard algérien)
"""
from __future__ import annotations

import re as _re
from typing import TYPE_CHECKING, Optional, Dict, List, Tuple
from core.precision import P as _P

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QSizePolicy,
    QFileDialog, QMessageBox, QFrame, QTextBrowser,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QPixmap, QPainter, QPen

if TYPE_CHECKING:
    from ui.main_window import MainWindow

from ui.report_generator import (
    generate_report, fmt_qty, type_label, ReportData,
    build_html_report, build_html_header, build_html_pages_section,
    build_html_global_section, build_html_bpu_recap_section,
    _rh_wrap, _rh_th, _rh_th_green, _rh_td, _rh_h2, _rh_h3,
    _number_to_words_fr, BpuLotRow, _decimals_for_unit,
)


# ── Helpers format monétaire français ────────────────────────────────────────

def _fmt_fr(val: float) -> str:
    """Format monétaire français : 30 000,00 (espace milliers, virgule décimale, 2 décimales)."""
    formatted = f"{val:,.2f}"                       # "30,000.00"
    int_part, dec_part = formatted.split(".")
    int_part = int_part.replace(",", "\u00a0")      # espace insécable comme séparateur
    return f"{int_part},{dec_part}"


def _parse_fr(text: str) -> str:
    """Convertit un montant formaté en français vers chaîne float-compatible."""
    s = text.strip()
    s = s.replace("\u00a0", "").replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    s = s.replace(",", ".")
    s = s.replace("DA", "").strip()
    return s


# ── Helpers visuels ───────────────────────────────────────────────────────────

_BTN_QSS = """
QPushButton {
    border: 1px solid #b0c4de; border-radius: 5px;
    padding: 4px 12px; font-size: 12px;
    color: #2a3a5a; background: #eef2fa;
}
QPushButton:hover   { background: #d0e4ff; border-color: #1976d2; }
QPushButton:pressed { background: #bbdefb; }
"""

_TREE_QSS = """
QTreeWidget {
    border: 1px solid #c8d4e8; border-radius: 4px;
    background: #ffffff; font-size: 12px;
}
QTreeWidget::item { padding: 2px 4px; }
QTreeWidget::item:selected { background: #bbdefb; color: #0d47a1; }
QHeaderView::section {
    background: #e3f2fd; color: #0d47a1;
    font-weight: bold; font-size: 11px;
    border: none; border-right: 1px solid #c8d4e8;
    padding: 4px 6px;
}
"""

_TABLE_QSS = """
QTableWidget {
    border: 1px solid #c8d4e8; border-radius: 4px;
    background: #ffffff; font-size: 12px;
    gridline-color: #e8eef8;
}
QTableWidget::item { padding: 3px 8px; }
QTableWidget::item:selected { background: #bbdefb; color: #0d47a1; }
QTableWidget::item:focus { background: #fff9c4; color: #000000;
                            border: 1px solid #f9a825; }
QHeaderView::section {
    background: #e3f2fd; color: #0d47a1;
    font-weight: bold; font-size: 11px;
    border: none; border-right: 1px solid #c8d4e8;
    border-bottom: 1px solid #c8d4e8; padding: 4px 6px;
}
"""


def _vline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setStyleSheet("color:#b0c4de; max-width:1px;")
    return f


# ── Widget principal ──────────────────────────────────────────────────────────

class ReportPanel(QWidget):
    """Panneau complet du rapport — 4 onglets."""

    def __init__(self, main_window: "MainWindow", parent=None):
        super().__init__(parent)
        self._mw   = main_window
        self._data: Optional[ReportData] = None

        # Métadonnées de table (Devis général)
        self._row_meta:              list = []
        self._lot_for_row:           Dict[int, str] = {}
        self._subtotal_row_for_lot:  Dict[str, int] = {}
        self._row_total_ht           = -1
        self._row_tva                = -1
        self._row_ttc                = -1

        self._build_ui()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Onglets
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                padding: 7px 20px; font-size: 12px;
                color: #445566; background: #dde8f5;
                border: 1px solid #c0cfe0;
                border-bottom: none; border-radius: 4px 4px 0 0;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff; color: #0d47a1;
                font-weight: bold; border-bottom: 2px solid #ffffff;
            }
            QTabBar::tab:hover:!selected { background: #c8d8f0; }
        """)

        self._tabs.addTab(self._build_tab_page(),        "📄  Par page")
        self._tabs.addTab(self._build_tab_devis(),       "💰  Devis général")
        self._tabs.addTab(self._build_tab_attachment(),  "📋  Attachement")
        self._tabs.addTab(self._build_tab_bpu(),         "📝  B.P.U.")

        root.addWidget(self._tabs, 1)

        # Barre d'état (sert aussi de compteur dynamique)
        self._status_bar = QLabel(
            "Cliquez sur « Actualiser » pour générer le rapport.")
        self._status_bar.setStyleSheet(
            "font-size:11px; color:#607080; padding:4px 10px;"
            "border-top:1px solid #c8d4e8;")
        root.addWidget(self._status_bar)
        # Alias : _lbl_counts pointe sur la même barre d'état
        self._lbl_counts = self._status_bar

    # ── Onglet 1 : Par page ───────────────────────────────────────────────────

    def _build_tab_page(self) -> QWidget:
        w  = QWidget()
        lv = QVBoxLayout(w)
        lv.setContentsMargins(8, 8, 8, 8)
        lv.setSpacing(4)

        lbl = QLabel("MESURES PAR PAGE")
        lbl.setStyleSheet(
            "font-size:10px; font-weight:bold; color:#607080; letter-spacing:1px;")
        lv.addWidget(lbl)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Désignation", "Type", "Quantité"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(16)
        self._tree.setStyleSheet(_TREE_QSS)
        lv.addWidget(self._tree)
        return w

    # ── Onglet 2 : Devis général ──────────────────────────────────────────────

    def _build_tab_devis(self) -> QWidget:
        w  = QWidget()
        rv = QVBoxLayout(w)
        rv.setContentsMargins(8, 8, 8, 8)
        rv.setSpacing(4)

        lbl = QLabel("DEVIS GÉNÉRAL")
        lbl.setStyleSheet(
            "font-size:10px; font-weight:bold; color:#0d47a1; letter-spacing:2px;")
        rv.addWidget(lbl)

        hint = QLabel(
            "Cliquez directement sur la colonne P.U. pour saisir ou modifier le prix unitaire")
        hint.setStyleSheet("font-size:10px; color:#78909c; font-style:italic;")
        rv.addWidget(hint)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Désignation", "Unité", "Quantité", "P.U. (DA)", "Total (DA)"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QTableWidget.SelectedClicked | QTableWidget.AnyKeyPressed)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(True)
        self._table.setStyleSheet(_TABLE_QSS)
        self._table.itemChanged.connect(self._on_pu_changed)
        rv.addWidget(self._table)
        return w

    # ── Onglet 3 : Attachement ────────────────────────────────────────────────

    # Définition des 8 colonnes du tableau Attachement
    # (index, label affiché, visible par défaut)
    _ATT_COLUMNS = [
        (0, "N°",               False),   # peu utile, masqué par défaut
        (1, "Désignation",      True),
        (2, "Page",             False),   # masqué par défaut
        (3, "Groupe",           False),  # masqué par défaut
        (4, "Formule",          True),
        (5, "Calcul détaillé",  True),
        (6, "Nombre",           True),    # coefficient multiplicateur (× N)
        (7, "Quantité",         True),
        (8, "Unité",            True),
    ]

    def _build_tab_attachment(self) -> QWidget:
        w  = QWidget()
        av = QVBoxLayout(w)
        av.setContentsMargins(8, 8, 8, 8)
        av.setSpacing(4)

        # ── Titre ─────────────────────────────────────────────────────────────
        lbl = QLabel("ATTACHEMENT — JUSTIFICATIF DES CALCULS")
        lbl.setStyleSheet(
            "font-size:10px; font-weight:bold; color:#4a148c; letter-spacing:1px;")
        av.addWidget(lbl)

        # ── Barre de visibilité des colonnes ──────────────────────────────────
        vis_row = QHBoxLayout()
        vis_row.setSpacing(4)
        vis_lbl = QLabel("Colonnes :")
        vis_lbl.setStyleSheet("font-size:10px; color:#546e7a;")
        vis_row.addWidget(vis_lbl)

        self._att_col_btns = []  # liste des boutons (un par colonne)
        _btn_qss_on  = ("QPushButton{background:#1565c0;color:#fff;border-radius:3px;"
                        "padding:2px 7px;font-size:10px;font-weight:bold;border:none;}"
                        "QPushButton:hover{background:#1976d2;}")
        _btn_qss_off = ("QPushButton{background:#e0e0e0;color:#546e7a;border-radius:3px;"
                        "padding:2px 7px;font-size:10px;border:none;}"
                        "QPushButton:hover{background:#bdbdbd;}")

        for col_idx, col_label, col_visible in self._ATT_COLUMNS:
            btn = QPushButton(col_label)
            btn.setCheckable(True)
            btn.setChecked(col_visible)
            btn.setFixedHeight(22)
            btn.setStyleSheet(_btn_qss_on if col_visible else _btn_qss_off)
            # Closure correcte sur col_idx
            def _make_toggle(cidx, b, qss_on, qss_off):
                def _toggle(checked):
                    self._att_table.setColumnHidden(cidx, not checked)
                    b.setStyleSheet(qss_on if checked else qss_off)
                return _toggle
            btn.toggled.connect(_make_toggle(col_idx, btn, _btn_qss_on, _btn_qss_off))
            self._att_col_btns.append(btn)
            vis_row.addWidget(btn)

        vis_row.addStretch()
        av.addLayout(vis_row)

        # ── Tableau 9 colonnes ────────────────────────────────────────────────
        self._att_table = QTableWidget(0, 9)
        self._att_table.setHorizontalHeaderLabels([
            col_label for _, col_label, _ in self._ATT_COLUMNS
        ])
        hdr = self._att_table.horizontalHeader()
        # Mode Interactive = toutes les colonnes librement redimensionnables par glisser
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        # Largeurs initiales (l'utilisateur peut les modifier librement)
        self._att_table.setColumnWidth(0, 36)   # N°
        self._att_table.setColumnWidth(1, 180)  # Désignation
        self._att_table.setColumnWidth(2, 80)   # Page
        self._att_table.setColumnWidth(3, 100)  # Groupe
        self._att_table.setColumnWidth(4, 220)  # Formule
        self._att_table.setColumnWidth(5, 340)  # Calcul détaillé (la plus large)
        self._att_table.setColumnWidth(6, 55)   # Nombre
        self._att_table.setColumnWidth(7, 75)   # Quantité
        self._att_table.setColumnWidth(8, 50)   # Unité
        # Double-clic sur séparateur d'en-tête → ajustement automatique au contenu
        hdr.sectionDoubleClicked.connect(self._att_table.resizeColumnToContents)
        self._att_table.verticalHeader().setVisible(False)
        self._att_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._att_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._att_table.setAlternatingRowColors(False)
        self._att_table.setShowGrid(True)
        self._att_table.setStyleSheet(_TABLE_QSS)

        # Appliquer la visibilité initiale
        for col_idx, _, col_visible in self._ATT_COLUMNS:
            self._att_table.setColumnHidden(col_idx, not col_visible)

        av.addWidget(self._att_table)
        return w

    # ── Onglet 4 : B.P.U. ────────────────────────────────────────────────────

    def _build_tab_bpu(self) -> QWidget:
        w  = QWidget()
        bv = QVBoxLayout(w)
        bv.setContentsMargins(8, 8, 8, 8)
        bv.setSpacing(4)

        lbl = QLabel(
            "B.P.U. — BORDEREAU DES PRIX UNITAIRES  (montants en toutes lettres)")
        lbl.setStyleSheet(
            "font-size:10px; font-weight:bold; color:#1b5e20; letter-spacing:1px;")
        bv.addWidget(lbl)

        self._bpu_browser = QTextBrowser()
        self._bpu_browser.setOpenExternalLinks(False)
        self._bpu_browser.setStyleSheet(
            "background:#ffffff; border:1px solid #c8d4e8; border-radius:4px;")
        bv.addWidget(self._bpu_browser)
        return w


    # ── Rafraîchissement ──────────────────────────────────────────────────────

    def refresh(self):
        """Recalcule et affiche le rapport complet dans les 4 onglets."""
        try:
            self._data = generate_report(self._mw)
        except Exception as exc:
            self._status_bar.setText(f"Erreur lors du calcul : {exc}")
            return

        self._populate_tree()
        self._populate_table()
        self._populate_attachment()
        self._populate_bpu()
        self._update_counts()

    # ── Onglet 1 — Arbre par page ─────────────────────────────────────────────

    def _populate_tree(self):
        self._tree.clear()
        if not self._data:
            return

        bold_f  = QFont(); bold_f.setBold(True)
        small_f = QFont(); small_f.setPointSize(9)
        small_i = QFont(); small_i.setPointSize(9); small_i.setItalic(True)

        type_icons  = {"polygon": "■", "perimeter": "╱", "point": "●"}
        type_colors = {
            "polygon":   QColor("#1565c0"),
            "perimeter": QColor("#2e7d32"),
            "point":     QColor("#e65100"),
        }
        bpu_col = QColor("#5d4037")
        err_col = QColor("#c62828")
        tot_col = QColor("#1b5e20")
        ra = Qt.AlignRight | Qt.AlignVCenter

        for pr in self._data.page_reports:
            if not pr.items:
                continue
            page_node = QTreeWidgetItem(self._tree)
            page_node.setText(0, f"📄  {pr.page_name}")
            page_node.setFont(0, bold_f)
            page_node.setForeground(0, QBrush(QColor("#0d47a1")))
            page_node.setExpanded(True)

            for item in pr.items:
                icon   = type_icons.get(item["type"], "•")
                count  = item["count"]
                suffix = f"  ×{count}" if count > 1 else ""
                g_node = QTreeWidgetItem(page_node)
                g_node.setText(0, f"  {icon}  {item['name']}{suffix}")
                g_node.setText(1, type_label(item["type"]))
                g_node.setText(2, fmt_qty(item["qty"], item["unit"]))
                g_node.setTextAlignment(2, ra)
                g_node.setForeground(0, QBrush(type_colors.get(item["type"], QColor("#424242"))))
                g_node.setForeground(1, QBrush(QColor("#607080")))
                qty_f = QFont(); qty_f.setBold(True)
                g_node.setFont(2, qty_f)
                g_node.setForeground(2, QBrush(QColor("#0d47a1")))

                bpu_items = item.get("bpu_items", [])
                if bpu_items:
                    g_node.setExpanded(True)
                    for bpu in bpu_items:
                        b_node = QTreeWidgetItem(g_node)
                        if bpu.error:
                            b_node.setText(0, f"      ⚠  {bpu.item_label}")
                            b_node.setText(1, "—")
                            b_node.setText(2, f"Erreur : {bpu.error}")
                            b_node.setForeground(0, QBrush(err_col))
                            b_node.setForeground(2, QBrush(err_col))
                        else:
                            fhint = f"  [{bpu.formula_expr}]" if bpu.formula_expr else ""
                            b_node.setText(
                                0, f"      →  {bpu.lot_label}  ›  {bpu.item_label}{fhint}")
                            b_node.setText(1, bpu.unit)
                            qty_s = f"{bpu.qty:,.2f}"
                            if bpu.prix_unitaire > 0:
                                b_node.setText(
                                    2, f"{qty_s}  ×  {_fmt_fr(bpu.prix_unitaire)} DA"
                                       f"  =  {_fmt_fr(bpu.total)} DA")
                                b_node.setForeground(2, QBrush(tot_col))
                            else:
                                b_node.setText(2, qty_s)
                                b_node.setForeground(2, QBrush(QColor("#78909c")))
                            b_node.setForeground(0, QBrush(bpu_col))
                            b_node.setForeground(1, QBrush(QColor("#78909c")))
                        b_node.setFont(0, small_f)
                        b_node.setFont(2, small_f)
                        b_node.setTextAlignment(2, ra)
                else:
                    no = QTreeWidgetItem(g_node)
                    no.setText(0, "      —  aucune affectation BPU")
                    no.setForeground(0, QBrush(QColor("#b0bec5")))
                    no.setFont(0, small_i)

        self._tree.expandAll()

    # ── Onglet 2 — Tableau Devis général ─────────────────────────────────────

    def _populate_table(self):
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        self._row_meta = []
        self._lot_for_row = {}
        self._subtotal_row_for_lot = {}
        self._row_total_ht = -1
        self._row_tva      = -1
        self._row_ttc      = -1

        if not self._data:
            self._table.blockSignals(False)
            return

        bpu = getattr(self._data, "bpu", None)
        has_bpu = bpu is not None and bpu.rows

        bold_f  = QFont(); bold_f.setBold(True)
        lot_f   = QFont(); lot_f.setBold(True); lot_f.setPointSize(11)
        small_f = QFont(); small_f.setPointSize(10)
        ra = Qt.AlignRight | Qt.AlignVCenter

        def _add_row(texts, bg=None, fonts=None, fg=None, alignments=None,
                     meta=None, row_tag=None, lot_id=None):
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_meta.append(meta)
            if lot_id and meta is not None:
                self._lot_for_row[r] = lot_id
            for col, txt in enumerate(texts):
                cell = QTableWidgetItem(str(txt) if txt is not None else "")
                if meta is not None and col == 3:
                    cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                    cell.setBackground(QBrush(QColor("#fffde7")))
                    cell.setToolTip("Cliquez pour saisir le prix unitaire")
                else:
                    cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if bg and not (meta is not None and col == 3):
                    cell.setBackground(QBrush(QColor(bg)))
                if fonts and col < len(fonts) and fonts[col]:
                    cell.setFont(fonts[col])
                if fg and col < len(fg) and fg[col]:
                    cell.setForeground(QBrush(QColor(fg[col])))
                if alignments and col < len(alignments) and alignments[col]:
                    cell.setTextAlignment(alignments[col])
                self._table.setItem(r, col, cell)
            if row_tag == "total_ht":  self._row_total_ht = r
            elif row_tag == "tva":     self._row_tva      = r
            elif row_tag == "ttc":     self._row_ttc      = r
            return r

        if not has_bpu:
            _add_row(
                ["Aucun item de devis affecté. "
                 "Sélectionnez un groupe et utilisez l'onglet « Affectations ».",
                 "", "", "", ""],
                fg=["#78909c"] + [None] * 4,
            )
            self._table.resizeRowsToContents()
            self._table.blockSignals(False)
            return

        dm = None
        try:
            from core.devis_manager import DevisManager
            dm = DevisManager.instance()
        except Exception:
            pass

        for lot_id in bpu.lots:
            rows_lot = bpu.rows_for_lot(lot_id)
            if not rows_lot:
                continue
            lot_label = rows_lot[0].lot_label
            _add_row(
                [f"  {lot_label}", "", "", "", ""],
                bg="#dde8f5",
                fonts=[lot_f] + [None] * 4,
                fg=["#0d47a1"] + [None] * 4,
            )

            for bpu_row in rows_lot:
                pu_str    = _fmt_fr(bpu_row.prix_unitaire) if bpu_row.prix_unitaire > 0 else ""
                total_str = _fmt_fr(bpu_row.total)        if bpu_row.prix_unitaire > 0 else "—"

                meta = None
                if dm is not None:
                    occurrences = []
                    for gid, ga in dm._assignments.items():
                        for idx, ai in enumerate(ga.items):
                            if ai.lot_id == bpu_row.lot_id and ai.item_id == bpu_row.item_id:
                                occurrences.append((gid, idx))
                    if occurrences:
                        meta = {
                            "lot_id":      bpu_row.lot_id,
                            "item_id":     bpu_row.item_id,
                            "occurrences": occurrences,
                            "qty":         bpu_row.qty_total,
                        }

                _nd = _decimals_for_unit(bpu_row.unit)
                item_row = _add_row(
                    [f"    {bpu_row.item_id}  {bpu_row.item_label}",
                     bpu_row.unit,
                     f"{bpu_row.qty_total:,.{_nd}f}",
                     pu_str,
                     total_str],
                    fonts=[small_f] * 5,
                    fg=[None, "#607080", "#0d47a1",
                        "#424242" if bpu_row.prix_unitaire > 0 else "#b0bec5",
                        "#1b5e20" if bpu_row.prix_unitaire > 0 else "#78909c"],
                    alignments=[None, Qt.AlignCenter, ra, ra, ra],
                    meta=meta,
                    lot_id=lot_id,
                )
                qty_cell = self._table.item(item_row, 2)
                if qty_cell:
                    qty_cell.setData(Qt.UserRole, bpu_row.qty_total)

            st     = bpu.subtotal_lot(lot_id)
            st_row = _add_row(
                ["", "", "", f"Sous-total {lot_id} :", f"{_fmt_fr(st)} DA"],
                bg="#f0f4fb",
                fonts=[None, None, None, bold_f, bold_f],
                fg=[None, None, None, "#424242", "#0d47a1"],
                alignments=[None, None, None, ra, ra],
            )
            self._subtotal_row_for_lot[lot_id] = st_row

        _add_row(["", "", "", "", ""], bg="#c8d4e8")

        _add_row(["", "", "", "TOTAL HT :", f"{_fmt_fr(bpu.total_ht)} DA"],
                 bg="#e3f2fd",
                 fonts=[None, None, None, bold_f, bold_f],
                 fg=[None, None, None, "#0d47a1", "#0d47a1"],
                 alignments=[None, None, None, ra, ra],
                 row_tag="total_ht")

        tva_rate = getattr(bpu, "tva_rate", 19.0)
        _add_row(["", "", "", f"TVA {tva_rate:.0f}% :", f"{_fmt_fr(bpu.tva_amount)} DA"],
                 bg="#fff8e1",
                 fonts=[None, None, None, bold_f, bold_f],
                 fg=[None, None, None, "#e65100", "#e65100"],
                 alignments=[None, None, None, ra, ra],
                 row_tag="tva")

        ttc_f = QFont(); ttc_f.setBold(True); ttc_f.setPointSize(12)
        _add_row(["", "", "", "TOTAL TTC :", f"{_fmt_fr(bpu.total_ttc)} DA"],
                 bg="#e8f5e9",
                 fonts=[None, None, None, ttc_f, ttc_f],
                 fg=[None, None, None, "#1b5e20", "#1b5e20"],
                 alignments=[None, None, None, ra, ra],
                 row_tag="ttc")

        self._table.resizeRowsToContents()
        self._table.blockSignals(False)

    # ── Onglet 3 — Attachement ────────────────────────────────────────────────

    @staticmethod
    def _normalize_etype(raw: str) -> str:
        """Normalise l'entity_type vers polygon / perimeter / point."""
        raw = (raw or "").lower()
        if raw in ("polygon", "surface"):
            return "polygon"
        if raw in ("perimeter", "line"):
            return "perimeter"
        if raw in ("point", "compteur", "counter"):
            return "point"
        return raw

    def _populate_attachment(self):
        """
        Tableau justificatif — structure « fusion Excel » :
          • Article avec 1 mesure  → 1 seule ligne (N° | Désig | Page | Groupe | Formule | Calcul | Qty | Unité)
          • Article avec N mesures → colonne N° et Désignation fusionnées sur N+1 lignes
                                     chaque mesure sur sa propre ligne,
                                     ligne finale = total
        """
        tbl = self._att_table
        tbl.setRowCount(0)
        if not self._data:
            return

        NCOLS = 9
        ra = Qt.AlignRight  | Qt.AlignVCenter
        ca = Qt.AlignCenter | Qt.AlignVCenter

        lot_f  = QFont(); lot_f.setBold(True);  lot_f.setPointSize(11)
        art_f  = QFont(); art_f.setBold(True);  art_f.setPointSize(10)
        val_f  = QFont(); val_f.setPointSize(10)
        tot_f  = QFont(); tot_f.setBold(True);  tot_f.setPointSize(10)
        mono_f = QFont("Consolas"); mono_f.setPointSize(9)

        # Couleurs par type d'entité : (fg article, bg article, bg sous-lignes)
        _TC = {
            "polygon":   ("#0d47a1", "#ddeeff", "#f4f8ff"),
            "perimeter": ("#b84000", "#ffeedd", "#fff9f5"),
            "point":     ("#1b5e20", "#ddf5e4", "#f4fff7"),
            "unknown":   ("#4a148c", "#f3e5f5", "#fdf8ff"),
        }

        # ── Construire l'index ────────────────────────────────────────────────
        index:       Dict[Tuple[str, str], List] = {}
        lot_labels:  Dict[str, str] = {}
        item_labels: Dict[Tuple[str, str], Tuple[str, str]] = {}

        for pr in self._data.page_reports:
            for item in pr.items:
                for bi in item.get("bpu_items", []):
                    key = (bi.lot_id, bi.item_id)
                    index.setdefault(key, []).append(bi)
                    lot_labels[bi.lot_id] = bi.lot_label
                    item_labels[key] = (bi.item_label, bi.unit)

        if not index:
            r = tbl.rowCount(); tbl.insertRow(r)
            c = QTableWidgetItem(
                "Aucune affectation — utilisez l'onglet Affectations pour affecter des articles.")
            c.setForeground(QBrush(QColor("#78909c")))
            c.setFlags(Qt.ItemIsEnabled)
            tbl.setItem(r, 0, c)
            tbl.setSpan(r, 0, 1, NCOLS)
            return

        # ── Helpers ───────────────────────────────────────────────────────────
        def _cell(text, font=None, fg=None, bg=None, align=None, flags=None):
            c = QTableWidgetItem(str(text) if text is not None else "")
            c.setFlags(flags or (Qt.ItemIsEnabled | Qt.ItemIsSelectable))
            if font:  c.setFont(font)
            if fg:    c.setForeground(QBrush(QColor(fg)))
            if bg:    c.setBackground(QBrush(QColor(bg)))
            if align: c.setTextAlignment(align)
            return c

        def _add_row(cells: list) -> int:
            r = tbl.rowCount(); tbl.insertRow(r)
            for col, c in enumerate(cells):
                if c is not None:
                    tbl.setItem(r, col, c)
            return r

        def _span_row(text, font, fg, bg, height=None) -> int:
            r = tbl.rowCount(); tbl.insertRow(r)
            c = _cell(text, font=font, fg=fg, bg=bg)
            c.setFlags(Qt.ItemIsEnabled)
            # Ancrer sur col 0 ET col 1 : col 0 peut être masquée (N°),
            # la fusion part de col 0 pour couvrir toute la largeur mais
            # on duplique le contenu en col 1 (Désignation — toujours visible)
            # pour que Qt puisse afficher le texte même si col 0 est cachée.
            tbl.setItem(r, 0, c)
            tbl.setItem(r, 1, _cell(text, font=font, fg=fg, bg=bg,
                                    flags=Qt.ItemIsEnabled))
            tbl.setSpan(r, 0, 1, NCOLS)
            if height:
                tbl.setRowHeight(r, height)
            return r

        # ── Formule développée ────────────────────────────────────────────────
        _COMPOSED_VARS = {
            # Noms unifiés
            "volume":                        "surface_nette × epaisseur",
            # Aliases rétro-compatibles
            "volume_dalle":                  "surface_nette × epaisseur",
            "volume_mur":                    "surface_nette × epaisseur",
            "surface_laterale":              "surface_brute - surface_deduction_ouvertures",
            "surface_brute_mur":             "longueur_brute × hauteur",
            "surface_nette_mur":             "surface_brute - surface_deduction_ouvertures",
            "surface_deduction_ouvertures":  "Σ(L_ouv × H_ouv)",
            "deduction_ouvertures":          "Σ(surface ouvertures)",
            "surface_compteur":              "longueur_unitaire × hauteur × nombre",
            "volume_compteur":               "longueur_unitaire × epaisseur × hauteur × nombre",
        }

        def _expand_formula(expr: str, v: dict, openings: list,
                            unit: str = "",
                            dims_brute=None,
                            members_detail=None) -> tuple:
            """
            Style BTP algérien avec précision adaptée à l'unité.

            Si members_detail contient plusieurs membres (groupe multi-surfaces),
            affiche le détail par membre :
              Surf. 1       : 8.50 × 6.00  =  51.00
                Ouv.1       : 1.20 × 2.10  =  −2.52
                Nette       :               =  48.48
              Surf. 2       : 10.00 × 5.00 =  50.00
              ────────────────────────────────────
              Surface brute :               = 101.00
              Surface nette :               =  98.48

            Sinon (surface unique) :
              Surface brute : 8.50 × 6.00  =  51.00
              Ouverture 1   : 1.20 × 2.10  =  −2.52
              ─────────────────────────────────────
              Surface nette :  =  48.48
            """
            from core.formula_engine import _ALLOWED_NAMES

            # Précision finale selon l'unité de l'article
            nd = _decimals_for_unit(unit)   # ex: 2 pour m², 3 pour m³
            # Les surfaces intermédiaires (brut, ouvertures) sont toujours en m² → 2 déc.
            ns = 2

            # ── Helper : ligne de volume informatif ───────────────────────────
            _VOLUME_FORMULAS = {
                "volume_dalle", "volume", "volume_mur",
                "volume_compteur", "surface_compteur",
            }

            def _make_vol_line(ex_s, vars_, net_val, col_w, item_unit=""):
                """
                Retourne une ligne 'Volume xxx : nette × e = vol m³', ou None.
                Conditions : article en m³, formule non volumique, épaisseur > 0.
                  - Polygon  → surface_brute > 0 → Volume : S × e
                  - Périmètre → longueur_brute > 0 :
                      longueur_nette/brute → Volume mur : L × h × e
                      surface_laterale … → Volume mur : S × e
                """
                if item_unit.strip() not in ("m³", "m3"):
                    return None
                if ex_s in _VOLUME_FORMULAS:
                    return None
                if net_val is None or float(net_val) <= 0:
                    return None
                nv = round(float(net_val), ns)
                e  = round(float(vars_.get("epaisseur", 0.0) or 0.0), 2)
                h  = round(float(vars_.get("hauteur",   0.0) or 0.0), 2)
                # Polygon : surface × épaisseur
                if e > 0 and float(vars_.get("surface_brute", 0.0) or 0.0) > 0:
                    vol = round(nv * e, 3)
                    return (f"{'Volume':<{col_w}}: "
                            f"{nv:.{ns}f} × {e:.{ns}f}  =  {vol:.3f} m³")
                # Périmètre : surface_nette × épaisseur
                if e > 0 and float(vars_.get("longueur_brute", 0.0) or 0.0) > 0:
                    sn = round(float(vars_.get("surface_nette", 0.0) or 0.0), 2)
                    if sn > 0:
                        vol = round(sn * e, 3)
                        return (f"{'Volume':<{col_w}}: "
                                f"{sn:.{ns}f} × {e:.{ns}f}  =  {vol:.3f} m³")
                return None

            # ── Branche multi-membres : détail par surface ────────────────────
            if members_detail and len(members_detail) > 1:
                W_m      = 14
                SEP      = "─" * 36
                lines    = []
                ouv_ctr  = 1   # compteur global d'ouvertures sur toutes les surfaces
                for sidx, m in enumerate(members_detail, start=1):
                    surf_lbl = f"Surface {sidx}"   # numérotation séquentielle
                    # Ligne de la surface du membre
                    if m.get("dims"):
                        L_m, l_m = m["dims"]
                        lines.append(
                            f"{surf_lbl:<{W_m}}: "
                            f"{L_m:.{ns}f} × {l_m:.{ns}f}  =  {m['area_brute']:.{ns}f}")
                    else:
                        lines.append(
                            f"{surf_lbl:<{W_m}}:  =  {m['area_brute']:.{ns}f}")
                    # Ouvertures du membre — numérotation continue
                    for op in m.get("openings", []):
                        lm   = round(float(op.get("length_m", 0.0) or 0.0), 2)
                        oh   = round(float(op.get("height",   0.0) or 0.0), 2)
                        area = round(float(op.get("area",     0.0) or 0.0), 2)
                        lbl  = f"Ouv.{ouv_ctr}"
                        ouv_ctr += 1
                        if lm > 0 and oh > 0:
                            det = f"{lm:.{ns}f} × {oh:.{ns}f}  =  −{area:.{ns}f}"
                        else:
                            det = f"S  =  −{area:.{ns}f}"
                        lines.append(f"  {lbl:<{W_m-2}}: {det}")
                    # Surface nette du membre (seulement si ouvertures)
                    if m.get("openings"):
                        lines.append(
                            f"  {'Nette':<{W_m-2}}:  =  {m['area_nette']:.{ns}f}")

                # Totaux groupe
                total_brute = round(sum(m["area_brute"] for m in members_detail), 2)
                total_nette = round(sum(m["area_nette"] for m in members_detail), 2)
                lines.append(SEP)
                # Afficher uniquement la surface nette (le brut se déduit des lignes ci-dessus)
                lines.append(f"{'Surface nette':<{W_m}}:  =  {total_nette:.{ns}f}")
                # Ligne volume
                net_for_vol = total_nette if total_nette < total_brute else total_brute
                vl = _make_vol_line(expr.strip(), v, net_for_vol, W_m, item_unit=unit)
                if vl:
                    lines.append(vl)
                else:
                    # Formules volumiques : calculer directement la ligne volume
                    ex_mm = expr.strip()
                    e_mm  = round(float(v.get("epaisseur", 0.0) or 0.0), 2)
                    h_mm  = round(float(v.get("hauteur",   0.0) or 0.0), 2)
                    if net_for_vol > 0:
                        if ex_mm in ("volume", "volume_dalle", "volume_mur") and e_mm > 0:
                            vol_mm = round(net_for_vol * e_mm, 3)
                            lines.append(
                                f"{'Volume':<{W_m}}: {net_for_vol:.{ns}f} × {e_mm:.2f}"
                                f"  =  {vol_mm:.3f} m³")

                return expr.strip(), "\n".join(lines)

            # ── Branche surface unique (comportement existant) ─────────────────
            expr_s       = expr.strip()
            composed_def = _COMPOSED_VARS.get(expr_s)
            if composed_def:
                col_formula = f"{expr_s}  =  {composed_def}"
                working     = composed_def
            else:
                col_formula = expr_s
                working     = expr_s

            # Substituer les variables par leurs valeurs (affichage à 2 déc. pour les dim.)
            display = working
            for name in sorted(_ALLOWED_NAMES, key=len, reverse=True):
                val = v.get(name)
                if val is not None and name in display:
                    display = display.replace(name, f"{float(val):.{ns}f}")

            # Évaluer le résultat (déjà net si la formule contient les déductions)
            try:
                norm        = display.replace("×", "*").replace("÷", "/")
                result_brut = float(eval(norm, {"__builtins__": {}}, {}))  # noqa: S307
                brut_str    = f"{result_brut:.{nd}f}"
            except Exception:
                result_brut = None
                brut_str    = "?"

            # ── Formules volumiques : affichage étiqueté (avec ET sans ouvertures) ──
            # "volume", "volume_dalle", "volume_mur" utilisent tous surface_nette × epaisseur
            _VOL_FORMULAS = {"volume", "volume_dalle", "volume_mur"}
            if expr_s in _VOL_FORMULAS:
                surf_brut = round(float(v.get("surface_brute", 0.0) or 0.0), ns)
                surf_net  = round(float(v.get("surface_nette", 0.0) or 0.0), ns)
                e_val     = round(float(v.get("epaisseur",     0.0) or 0.0), 2)

                W_v   = 14
                SEP_v = "─" * 36
                vlines_v = []

                # Périmètre : on peut montrer longueur_brute × hauteur pour la surface brute
                _lb = round(float(v.get("longueur_brute", 0.0) or 0.0), ns)
                _h  = round(float(v.get("hauteur",        0.0) or 0.0), 2)
                _is_perim = (_lb > 0 and _h > 0)

                if openings:
                    # Surface brute obligatoire avec ouvertures : justifie la déduction
                    if _is_perim:
                        vlines_v.append(
                            f"{'Surface brute':<{W_v}}: {_lb:.{ns}f} × {_h:.2f}"
                            f"  =  {surf_brut:.{ns}f}")
                    elif dims_brute:
                        L_m, l_m = dims_brute
                        vlines_v.append(
                            f"{'Surface brute':<{W_v}}: {L_m:.{ns}f} × {l_m:.{ns}f}"
                            f"  =  {surf_brut:.{ns}f}")
                    else:
                        vlines_v.append(f"{'Surface brute':<{W_v}}:  =  {surf_brut:.{ns}f}")

                    for i, op in enumerate(openings, start=1):
                        lm_o  = round(float(op.get("length_m", 0.0) or 0.0), 2)
                        oh_o  = round(float(op.get("height",   0.0) or 0.0), 2)
                        a_raw = float(op.get("area", 0.0) or 0.0)
                        a_o   = round(lm_o * oh_o, 2) if (lm_o > 0 and oh_o > 0) else round(a_raw, 2)
                        det_o = (f"{lm_o:.{ns}f} × {oh_o:.{ns}f}  =  −{a_o:.{ns}f}"
                                 if lm_o > 0 and oh_o > 0 else f"S  =  −{a_o:.{ns}f}")
                        vlines_v.append(f"{'Ouverture ' + str(i):<{W_v}}: {det_o}")

                    vlines_v.append(SEP_v)
                    vlines_v.append(f"{'Surface nette':<{W_v}}:  =  {surf_net:.{ns}f}")
                else:
                    # Sans ouvertures : dimensions si connu
                    if _is_perim:
                        vlines_v.append(
                            f"{'Surface nette':<{W_v}}: {_lb:.{ns}f} × {_h:.2f}"
                            f"  =  {surf_net:.{ns}f}")
                    elif dims_brute:
                        L_m, l_m = dims_brute
                        vlines_v.append(
                            f"{'Surface nette':<{W_v}}: {L_m:.{ns}f} × {l_m:.{ns}f}"
                            f"  =  {surf_net:.{ns}f}")
                    else:
                        vlines_v.append(f"{'Surface nette':<{W_v}}:  =  {surf_net:.{ns}f}")

                # Ligne volume
                if surf_net > 0 and e_val > 0:
                    vol_v = round(surf_net * e_val, 3)
                    vlines_v.append(
                        f"{'Volume':<{W_v}}: {surf_net:.{ns}f} × {e_val:.2f}"
                        f"  =  {vol_v:.3f} m³")

                return col_formula, "\n".join(vlines_v)

            # ── Formules compteur : affichage a × b × h × nombre ─────────────────
            _CPT_FORMULAS = {"surface_compteur", "volume_compteur"}
            if expr_s in _CPT_FORMULAS:
                a_c  = round(float(v.get("longueur_unitaire", 0.0) or 0.0), ns)
                b_c  = round(float(v.get("epaisseur",         0.0) or 0.0), 2)
                h_c  = round(float(v.get("hauteur",           0.0) or 0.0), 2)
                n_c  = int(round(float(v.get("nombre",        1.0) or 1.0)))
                W_c  = 14
                clines = []
                if expr_s == "surface_compteur":
                    # a × h × nombre
                    if a_c > 0 and h_c > 0:
                        surf_c = round(a_c * h_c * n_c, ns)
                        clines.append(
                            f"{'Surface':<{W_c}}: "
                            f"{a_c:.{ns}f} × {h_c:.2f} × {n_c}"
                            f"  =  {surf_c:.{ns}f} m²")
                    else:
                        clines.append(f"{display}  =  {brut_str}")
                else:
                    # volume_compteur : a × b × h × nombre
                    if a_c > 0 and b_c > 0 and h_c > 0:
                        vol_c = round(a_c * b_c * h_c * n_c, 3)
                        clines.append(
                            f"{'Section':<{W_c}}: "
                            f"{a_c:.{ns}f} × {b_c:.2f}")
                        clines.append(
                            f"{'Volume':<{W_c}}: "
                            f"{a_c:.{ns}f} × {b_c:.2f} × {h_c:.2f} × {n_c}"
                            f"  =  {vol_c:.3f} m³")
                    else:
                        clines.append(f"{display}  =  {brut_str}")
                return col_formula, "\n".join(clines)

            # ── Formule composite : détection AVANT le bloc "sans ouvertures" ────────
            # (le bloc if not openings: retournait tôt et ajoutait _make_vol_line par erreur)
            # Exception : si la formule contient surface_deduction_ouvertures / deduction_ouvertures
            # ET qu'il y a des ouvertures réelles, on laisse tomber dans le bloc BTP pour afficher
            # le détail ligne par ligne (Surface brute / Ouvertures / Surface nette).
            _DEDUCTION_VARS = {"surface_deduction_ouvertures", "deduction_ouvertures"}
            _has_deduction_var = any(dv in expr_s for dv in _DEDUCTION_VARS)
            _is_composite = bool(_re.search(r'[\w\)]\s*[+\-]', expr_s))
            if _is_composite and not (_has_deduction_var and openings):
                col_calcul = f"{display}  =  {brut_str}"
                return col_formula, col_calcul

            if not openings:
                W_v  = 14

                # ── "surface_X × epaisseur" sans ouvertures ───────────────────────
                # Même affichage que le bloc _VOL_FORMULAS :
                #   Surface nette : L × l  =  val
                #   Volume        : val × e  =  vol m³
                # Évite la double multiplication par épaisseur via _make_vol_line.
                _SE_SURF_KEYS = [
                    ("surface_nette", "Surface nette"),
                    ("surface_brute", "Surface brute"),
                ]
                _se_match = next(
                    ((sk, sl) for sk, sl in _SE_SURF_KEYS if sk in expr_s),
                    None)
                if _se_match and "epaisseur" in expr_s:
                    sk, sl   = _se_match
                    sv_val   = round(float(v.get(sk, 0.0) or 0.0), ns)
                    e_val    = round(float(v.get("epaisseur", 0.0) or 0.0), 2)
                    _lb      = round(float(v.get("longueur_brute", 0.0) or 0.0), ns)
                    _h       = round(float(v.get("hauteur",        0.0) or 0.0), 2)
                    vlines_se = []
                    if _lb > 0 and _h > 0:
                        vlines_se.append(
                            f"{sl:<{W_v}}: {_lb:.{ns}f} × {_h:.2f}"
                            f"  =  {sv_val:.{ns}f}")
                    elif dims_brute:
                        L_m, l_m = dims_brute
                        vlines_se.append(
                            f"{sl:<{W_v}}: {L_m:.{ns}f} × {l_m:.{ns}f}"
                            f"  =  {sv_val:.{ns}f}")
                    else:
                        vlines_se.append(f"{sl:<{W_v}}:  =  {sv_val:.{ns}f}")
                    if sv_val > 0 and e_val > 0:
                        vol_se = round(sv_val * e_val, 3)
                        vlines_se.append(
                            f"{'Volume':<{W_v}}: {sv_val:.{ns}f} × {e_val:.2f}"
                            f"  =  {vol_se:.3f} m³")
                    return col_formula, "\n".join(vlines_se)

                # Pour les formules de surface/longueur pure, éviter "66.63 = 66.63"
                # et afficher les dimensions si le polygone est rectangulaire
                _SURF_VARS = {
                    "surface_nette", "surface_brute",
                    "longueur_nette", "longueur_brute",
                    # Aliases rétro-compatibles
                    "surface_laterale", "surface_brute_mur", "surface_nette_mur",
                }
                if expr_s in _SURF_VARS:
                    if dims_brute and "surface" in expr_s:
                        L_m, l_m = dims_brute
                        display_line = (
                            f"{L_m:.{ns}f} × {l_m:.{ns}f}  =  {brut_str}")
                    elif display.strip() == brut_str.strip():
                        # Valeur identique après substitution : éviter "X = X"
                        display_line = f"=  {brut_str}"
                    else:
                        display_line = f"{display}  =  {brut_str}"
                else:
                    display_line = f"{display}  =  {brut_str}"
                lines_v = [display_line]
                vl = _make_vol_line(expr_s, v, result_brut, W_v, item_unit=unit)
                if vl:
                    lines_v.append(vl)
                col_calcul = "\n".join(lines_v)
                return col_formula, col_calcul

            # ── Formule composite périmètre-volume : surface_nette × epaisseur (alias compris)
            # Ex: "surface_nette × epaisseur", "surface_laterale × epaisseur"
            # result_brut est un VOLUME (m³) — le bloc BTP ne doit pas mélanger m³ et m².
            _PERIM_NET_VARS = ("surface_nette", "surface_laterale", "surface_nette_mur")
            _pnv = next((pv for pv in _PERIM_NET_VARS if pv in expr_s), None)
            if _pnv and "epaisseur" in expr_s and openings:
                surf_brut_p = round(float(v.get("surface_brute", 0.0) or 0.0), ns)
                surf_net_p  = round(float(v.get("surface_nette", 0.0) or 0.0), ns)
                e_val_p     = round(float(v.get("epaisseur",      0.0) or 0.0), 2)
                lb_val_p    = round(float(v.get("longueur_brute", 0.0) or 0.0), ns)
                h_val_p     = round(float(v.get("hauteur",        0.0) or 0.0), 2)

                W_p   = 14
                SEP_p = "─" * 36
                vlines_p = []

                # Surface brute obligatoire avec ouvertures : justifie la déduction
                if lb_val_p > 0 and h_val_p > 0:
                    vlines_p.append(
                        f"{'Surface brute':<{W_p}}: {lb_val_p:.{ns}f} × {h_val_p:.2f}"
                        f"  =  {surf_brut_p:.{ns}f}")
                elif dims_brute:
                    L_m, l_m = dims_brute
                    vlines_p.append(
                        f"{'Surface brute':<{W_p}}: {L_m:.{ns}f} × {l_m:.{ns}f}"
                        f"  =  {surf_brut_p:.{ns}f}")
                else:
                    vlines_p.append(f"{'Surface brute':<{W_p}}:  =  {surf_brut_p:.{ns}f}")

                for i, op in enumerate(openings, start=1):
                    lm_p  = round(float(op.get("length_m", 0.0) or 0.0), 2)
                    oh_p  = round(float(op.get("height",   0.0) or 0.0), 2)
                    ar_p  = float(op.get("area", 0.0) or 0.0)
                    a_p   = round(lm_p * oh_p, 2) if (lm_p > 0 and oh_p > 0) else round(ar_p, 2)
                    det_p = (f"{lm_p:.{ns}f} × {oh_p:.{ns}f}  =  −{a_p:.{ns}f}"
                             if lm_p > 0 and oh_p > 0 else f"S  =  −{a_p:.{ns}f}")
                    vlines_p.append(f"{'Ouverture ' + str(i):<{W_p}}: {det_p}")

                vlines_p.append(SEP_p)
                vlines_p.append(f"{'Surface nette':<{W_p}}:  =  {surf_net_p:.{ns}f}")

                if e_val_p > 0 and surf_net_p > 0:
                    vol_p = round(surf_net_p * e_val_p, 3)
                    vlines_p.append(
                        f"{'Volume':<{W_p}}: {surf_net_p:.{ns}f} × {e_val_p:.2f}"
                        f"  =  {vol_p:.3f} m³")

                return col_formula, "\n".join(vlines_p)

            # ── Style BTP : bloc structuré avec déductions ────────────────────
            W   = 14
            SEP = "─" * 36

            # Formules qui retournent directement une valeur BRUTE
            # (les déductions ne sont pas encore incluses dans result_brut)
            _GROSS_FORMULAS = {
                "surface_brute", "longueur_brute",
                "volume", "volume_dalle", "volume_mur",
                # Alias rétro-compatible
                "surface_brute_mur",
            }
            is_gross_formula = expr_s in _GROSS_FORMULAS

            # Calculer les déductions depuis les ouvertures
            total_ded = 0.0
            ouvs = []
            for i, op in enumerate(openings, start=1):
                lm       = round(float(op.get("length_m", 0.0) or 0.0), 2)
                oh       = round(float(op.get("height",   0.0) or 0.0), 2)
                area_raw = float(op.get("area", 0.0) or 0.0)
                area     = round(lm * oh, 2) if (lm > 0 and oh > 0) else round(area_raw, 2)
                total_ded += area
                lbl_ouv   = f"Ouverture {i}"
                if lm > 0 and oh > 0:
                    detail = f"{lm:.{ns}f} × {oh:.{ns}f}  =  −{area:.{ns}f}"
                else:
                    detail = f"S  =  −{area:.{ns}f}"
                ouvs.append((lbl_ouv, detail))

            lines = []

            if result_brut is not None:
                if is_gross_formula:
                    gross_val = result_brut
                    net_val   = round(result_brut - total_ded, ns)
                else:
                    gross_val = round(result_brut + total_ded, ns)
                    net_val   = result_brut

                # Ligne "Surface brute" avant les déductions
                _lb_btp = round(float(v.get("longueur_brute", 0.0) or 0.0), ns)
                _h_btp  = round(float(v.get("hauteur",        0.0) or 0.0), 2)
                if dims_brute:
                    L_m, l_m = dims_brute
                    lines.append(
                        f"{'Surface brute':<{W}}: {L_m:.{ns}f} × {l_m:.{ns}f}"
                        f"  =  {gross_val:.{ns}f}")
                elif _lb_btp > 0 and _h_btp > 0:
                    lines.append(
                        f"{'Surface brute':<{W}}: {_lb_btp:.{ns}f} × {_h_btp:.2f}"
                        f"  =  {gross_val:.{ns}f}")
                else:
                    lines.append(f"{'Surface brute':<{W}}:  =  {gross_val:.{ns}f}")
            else:
                net_val = None

            # Formule brute : on n'affiche pas les déductions d'ouvertures —
            # la quantité brute est déjà correcte, inutile de détailler les soustractions.
            if is_gross_formula:
                vl = _make_vol_line(expr_s, v, gross_val, W, item_unit=unit)
                if vl:
                    lines.append(vl)
                col_calcul = "\n".join(lines)
                return col_formula, col_calcul

            # Formule nette : on affiche les ouvertures puis la surface nette
            for lbl_ouv, detail in ouvs:
                lines.append(f"{lbl_ouv:<{W}}: {detail}")

            lines.append(SEP)

            net_str = f"{net_val:.{ns}f}" if net_val is not None else "?"
            lines.append(f"{'Surface nette':<{W}}:  =  {net_str}")
            # Ligne volume (si épaisseur renseignée et formule non volumique)
            vl = _make_vol_line(expr_s, v, net_val, W, item_unit=unit)
            if vl:
                lines.append(vl)

            col_calcul = "\n".join(lines)
            return col_formula, col_calcul

        # ── Remplissage ───────────────────────────────────────────────────────
        lots_seen = sorted(set(lot_labels.keys()))
        line_no   = 0

        for lot_id in lots_seen:
            _span_row(f"  LOT  {lot_labels[lot_id]}",
                      font=lot_f, fg="#0d47a1", bg="#dde8f5", height=26)

            art_keys = sorted(
                [k for k in index if k[0] == lot_id], key=lambda k: k[1])

            for key in art_keys:
                item_id       = key[1]
                ilabel, iunit = item_labels[key]
                occurrences   = index[key]
                n_occ         = len(occurrences)
                qty_total     = _P.somme(*(bi.qty for bi in occurrences))
                line_no      += 1

                # Type dominant
                dom_type = "unknown"
                for bi in occurrences:
                    t = self._normalize_etype(bi.group_type)
                    if t != "unknown":
                        dom_type = t
                        break
                type_fg, art_bg, sub_bg = _TC.get(dom_type, _TC["unknown"])

                # Ligne de total finale (si plusieurs occurrences)
                has_total_row = n_occ > 1
                span_rows     = n_occ + (1 if has_total_row else 0)
                first_row     = tbl.rowCount()

                # ── Une ligne par occurrence (page / groupe) ──────────────────
                for i, bi in enumerate(occurrences):
                    is_first = (i == 0)
                    bg       = art_bg if is_first else sub_bg

                    nd_u   = _decimals_for_unit(iunit)
                    err_t  = f"⚠ {bi.error}" if bi.error else ""
                    qty_t  = err_t if bi.error else f"{bi.qty:.{nd_u}f}"
                    qty_fg = "#c62828" if bi.error else "#1565c0"

                    col_formula, col_calcul = _expand_formula(
                        bi.formula_expr, bi.variables,
                        getattr(bi, "openings_detail", []) or [],
                        unit=iunit,
                        dims_brute=getattr(bi, "dims_brute", None),
                        members_detail=getattr(bi, "members_detail", None))

                    # Coefficient (Nombre) : vide si 1.0, sinon valeur formatée
                    coef = getattr(bi, "coefficient", 1.0) or 1.0
                    if abs(coef - 1.0) < 1e-9:
                        nombre_t  = ""
                        nombre_fg = "#546e7a"
                    else:
                        nombre_t  = (f"{coef:.0f}" if coef == int(coef)
                                     else f"{coef:.3g}")
                        nombre_fg = "#e65100"  # orange pour attirer l'attention

                    # Col 0 (N°) et Col 1 (Désignation) : remplies sur la 1re ligne seulement
                    # Les lignes suivantes auront des cellules vides (masquées par setSpan)
                    _add_row([
                        _cell(str(line_no) if is_first else "",
                              font=art_f, fg=type_fg, bg=art_bg, align=ca),
                        _cell(f"{item_id}  {ilabel}" if is_first else "",
                              font=art_f, fg=type_fg, bg=art_bg),
                        _cell(bi.page_name,  font=val_f,  fg="#546e7a", bg=bg),
                        _cell(bi.group_name, font=val_f,  fg="#546e7a", bg=bg),
                        _cell(col_formula,   font=mono_f, fg="#1565c0", bg=bg),
                        _cell(col_calcul,    font=mono_f, fg="#000000", bg=bg),
                        _cell(nombre_t, font=tot_f, fg=nombre_fg, bg=bg, align=ca),
                        _cell(qty_t, font=tot_f, fg=qty_fg, bg=bg, align=ra),
                        _cell(iunit, font=val_f if not is_first else art_f,
                              fg=type_fg if is_first else "#607080",
                              bg=bg, align=ca),
                    ])

                # ── Ligne total (si plusieurs occurrences) ────────────────────
                if has_total_row:
                    tot_bg = "#fffde7"
                    r = tbl.rowCount(); tbl.insertRow(r)
                    # cols 0 et 1 vides (fusionnées avec 1re ligne par setSpan)
                    tbl.setItem(r, 0, _cell("", bg=art_bg))
                    tbl.setItem(r, 1, _cell("", bg=art_bg))
                    # cols 2-6 : libellé "Total" centré
                    lbl_c = _cell("  ▶  Total", font=tot_f, fg="#e65100", bg=tot_bg)
                    lbl_c.setFlags(Qt.ItemIsEnabled)
                    tbl.setItem(r, 2, lbl_c)
                    tbl.setSpan(r, 2, 1, 5)
                    for c in range(3, 7):
                        tbl.setItem(r, c, _cell("", bg=tot_bg))
                    tbl.setItem(r, 7, _cell(f"{qty_total:.{_decimals_for_unit(iunit)}f}",
                                            font=tot_f, fg="#e65100",
                                            bg=tot_bg, align=ra))
                    tbl.setItem(r, 8, _cell(iunit, font=tot_f,
                                            fg="#e65100", bg=tot_bg, align=ca))

                # ── Fusion des colonnes N° et Désignation sur toutes les lignes ──
                if span_rows > 1:
                    tbl.setSpan(first_row, 0, span_rows, 1)  # colonne N°
                    tbl.setSpan(first_row, 1, span_rows, 1)  # colonne Désignation

        # Ligne de séparation finale
        _span_row("", font=val_f, fg="#ffffff", bg="#c8d4e8", height=6)
        tbl.resizeRowsToContents()

    # ── Onglet 4 — B.P.U. (prix en lettres) ──────────────────────────────────

    def _populate_bpu(self):
        """
        Génère un document HTML affichant chaque article avec :
        - N° | Désignation | Unité | Quantité | Prix unitaire (chiffres)
        - Prix unitaire en toutes lettres (standard algérien)
        """
        if not self._data:
            self._bpu_browser.setHtml("<p style='color:#78909c'>Aucune donnée.</p>")
            return

        bpu = getattr(self._data, "bpu", None)
        if not bpu or not bpu.rows:
            self._bpu_browser.setHtml(
                "<p style='color:#78909c;font-style:italic'>"
                "Aucun item de devis affecté. "
                "Affectez des articles aux groupes via l'onglet Affectations.</p>")
            return

        meta   = self._data.metadata
        today  = __import__("datetime").date.today().strftime("%d/%m/%Y")
        tva    = getattr(bpu, "tva_rate", 19.0)

        # ── En-tête projet ────────────────────────────────────────────────────
        def _meta_row(label, key):
            v = meta.get(key, "")
            return (f"<tr><td style='color:#666;width:170px'>{label}</td>"
                    f"<td><b>{v}</b></td></tr>") if v else ""

        header = "".join([
            _meta_row("Projet",           "name"),
            _meta_row("N° de projet",     "number"),
            _meta_row("Maître d'ouvrage", "owner"),
            _meta_row("Maître d'œuvre",   "architect"),
            _meta_row("Entreprise",       "company"),
        ])

        # ── Lots & articles ───────────────────────────────────────────────────
        lots_html = ""
        for lot_id in bpu.lots:
            rows = bpu.rows_for_lot(lot_id)
            if not rows:
                continue
            lot_label = rows[0].lot_label
            articles_html = ""
            for row in rows:
                pu      = row.prix_unitaire
                qty     = row.qty_total
                total   = row.total
                pu_int  = int(round(pu))
                tot_int = int(round(total))

                pu_lettres  = _number_to_words_fr(pu_int).capitalize()  \
                              if pu > 0 else "—"
                tot_lettres = _number_to_words_fr(tot_int).capitalize()  \
                              if total > 0 else "—"

                _nd_bpu     = _decimals_for_unit(row.unit)
                pu_num_str  = f"{pu:,.2f} DA".replace(",", " ")  if pu > 0  else "—"
                qty_str     = f"{qty:,.{_nd_bpu}f}".replace(",", " ")
                total_str   = f"{total:,.2f} DA".replace(",", " ") if total > 0 else "—"

                articles_html += f"""
                <tr style="background:#fafafa">
                    <td style="padding:6px 8px;vertical-align:top;
                               font-weight:bold;color:#4a148c;width:70px">
                        {row.item_id}
                    </td>
                    <td style="padding:6px 8px;vertical-align:top">
                        <b>{row.item_label}</b>
                        <br/>
                        <span style="font-size:10px;color:#78909c;font-style:italic">
                            Prix unitaire : {pu_num_str}
                        </span>
                        <br/>
                        <span style="font-size:10px;color:#555">
                            <i>({pu_lettres} dinars algériens)</i>
                        </span>
                    </td>
                    <td style="padding:6px 8px;text-align:center;vertical-align:top;
                               color:#607080;width:40px">{row.unit}</td>
                    <td style="padding:6px 8px;text-align:right;vertical-align:top;
                               font-weight:bold;width:80px">{qty_str}</td>
                    <td style="padding:6px 8px;text-align:right;vertical-align:top;
                               width:110px;color:#607080">{pu_num_str}</td>
                    <td style="padding:6px 8px;vertical-align:top;width:160px">
                        <b style="color:#1b5e20">{total_str}</b>
                        <br/>
                        <span style="font-size:10px;color:#555;font-style:italic">
                            {tot_lettres} dinars
                        </span>
                    </td>
                </tr>
                <tr style="border-bottom:1px solid #e0e0e0">
                    <td colspan="6"
                        style="padding:0 8px 8px 8px;font-size:10px;color:#888">
                    </td>
                </tr>"""

            st     = bpu.subtotal_lot(lot_id)
            st_str = f"{st:,.2f} DA".replace(",", " ")
            lots_html += f"""
            <div style="margin-top:18px;page-break-inside:avoid">
                <div style="background:#c8e6c9;padding:6px 10px;
                            font-weight:bold;font-size:13px;color:#1b5e20;
                            border-radius:4px 4px 0 0">
                    LOT {lot_label}
                </div>
                <table width="100%" cellspacing="0" cellpadding="0"
                       style="border-collapse:collapse;font-size:12px;
                              border:1px solid #c8d4e8">
                    <thead>
                        <tr style="background:#e8f5e9">
                            <th style="padding:4px 8px;text-align:left">N°</th>
                            <th style="padding:4px 8px;text-align:left">Désignation / Prix en lettres</th>
                            <th style="padding:4px 8px;text-align:center">U.</th>
                            <th style="padding:4px 8px;text-align:right">Quantité</th>
                            <th style="padding:4px 8px;text-align:right">P.U. (DA)</th>
                            <th style="padding:4px 8px;text-align:right">Montant (DA)</th>
                        </tr>
                    </thead>
                    <tbody>{articles_html}</tbody>
                    <tfoot>
                        <tr style="background:#f1f8e9">
                            <td colspan="5"
                                style="padding:5px 10px;text-align:right;
                                       font-weight:bold;color:#2e7d32">
                                Sous-total LOT {lot_id}
                            </td>
                            <td style="padding:5px 10px;text-align:right;
                                       font-weight:bold;color:#1b5e20">
                                {st_str}
                            </td>
                        </tr>
                    </tfoot>
                </table>
            </div>"""

        # ── Totaux finaux ─────────────────────────────────────────────────────
        ht_str  = f"{bpu.total_ht:,.2f} DA".replace(",", " ")
        tva_str = f"{bpu.tva_amount:,.2f} DA".replace(",", " ")
        ttc_str = f"{bpu.total_ttc:,.2f} DA".replace(",", " ")
        ttc_int = int(round(bpu.total_ttc))
        ttc_lettres = _number_to_words_fr(ttc_int).capitalize()

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
  body {{ font-family:'Segoe UI',Arial,sans-serif; font-size:12px;
          color:#212121; margin:20px; }}
  h1   {{ color:#1b5e20; margin-bottom:4px; font-size:18px; }}
  p    {{ margin:2px 0; }}
</style>
</head>
<body>
<h1>BORDEREAU DES PRIX UNITAIRES</h1>
<p style="color:#777;margin-bottom:12px">Généré le {today}</p>
<table style="font-size:12px;margin-bottom:16px;border-collapse:collapse">
  {header}
</table>
{lots_html}

<table width="55%" style="margin-left:45%;margin-top:20px;
       border-collapse:collapse;font-size:12px">
    <tr>
        <td style="padding:5px 10px;border:1px solid #ccc">TOTAL HORS TAXE</td>
        <td style="padding:5px 10px;border:1px solid #ccc;
                   text-align:right;font-weight:bold">{ht_str}</td>
    </tr>
    <tr style="background:#f5f5f5">
        <td style="padding:5px 10px;border:1px solid #ccc">TVA {tva:.0f} %</td>
        <td style="padding:5px 10px;border:1px solid #ccc;text-align:right">{tva_str}</td>
    </tr>
    <tr style="background:#e8f5e9">
        <td style="padding:6px 10px;border:2px solid #2e7d32;
                   font-weight:bold;color:#1b5e20">MONTANT TOTAL T.T.C.</td>
        <td style="padding:6px 10px;border:2px solid #2e7d32;
                   text-align:right;font-weight:bold;font-size:14px;
                   color:#1b5e20">{ttc_str}</td>
    </tr>
</table>

<div style="margin-top:20px;padding:12px 16px;border:1px solid #a5d6a7;
            border-radius:4px;background:#f1f8e9">
    <p style="font-size:11px;color:#333;margin:0">
        <b>Arrêté le présent bordereau à la somme de :</b>
    </p>
    <p style="font-size:13px;font-style:italic;color:#1b5e20;margin:6px 0 0 0">
        <b>{ttc_lettres} dinars algériens (T.T.C.)</b>
    </p>
</div>
</body></html>"""

        self._bpu_browser.setHtml(html)

    # ── Édition inline du prix unitaire (Onglet 2) ───────────────────────────

    def _on_pu_changed(self, item: "QTableWidgetItem"):
        if item.column() != 3:
            return
        row = item.row()
        if row >= len(self._row_meta) or self._row_meta[row] is None:
            return

        meta = self._row_meta[row]
        txt  = _parse_fr(item.text())
        try:
            new_pu = float(txt) if txt else 0.0
        except ValueError:
            return

        try:
            from core.devis_manager import DevisManager
            dm = DevisManager.instance()
            for gid, idx in meta["occurrences"]:
                dm.update_assignment_item(gid, idx, prix_unitaire=new_pu)
        except Exception:
            return

        # Mettre à jour le BpuLotRow en mémoire pour que l'onglet BPU
        # reflète immédiatement le nouveau prix sans recharger tout le rapport.
        bpu = getattr(self._data, "bpu", None)
        if bpu and new_pu >= 0:
            key = (meta.get("lot_id", ""), meta.get("item_id", ""))
            bpu_row = bpu._rows.get(key)
            if bpu_row is not None:
                bpu_row.prix_unitaire = new_pu

        self._table.blockSignals(True)
        try:
            qty_cell = self._table.item(row, 2)
            qty      = qty_cell.data(Qt.UserRole) if qty_cell else 0.0
            row_total = qty * new_pu

            pu_cell = self._table.item(row, 3)
            if pu_cell:
                pu_cell.setText(_fmt_fr(new_pu) if new_pu > 0 else "")
                pu_cell.setForeground(QBrush(QColor("#424242" if new_pu > 0 else "#b0bec5")))

            tot_cell = self._table.item(row, 4)
            if tot_cell:
                tot_cell.setText(_fmt_fr(row_total) if new_pu > 0 else "—")
                tot_cell.setForeground(QBrush(QColor("#1b5e20" if new_pu > 0 else "#78909c")))

            lot_id = self._lot_for_row.get(row)
            if lot_id and lot_id in self._subtotal_row_for_lot:
                st_row = self._subtotal_row_for_lot[lot_id]
                lot_total = 0.0
                for r2, lot2 in self._lot_for_row.items():
                    if lot2 == lot_id:
                        tc = self._table.item(r2, 4)
                        if tc:
                            v = _parse_fr(tc.text())
                            try:
                                lot_total += float(v) if v and v != "—" else 0.0
                            except ValueError:
                                pass
                st_cell = self._table.item(st_row, 4)
                if st_cell:
                    st_cell.setText(f"{_fmt_fr(lot_total)} DA")

            total_ht = 0.0
            for r2, meta2 in enumerate(self._row_meta):
                if meta2 is not None:
                    tc = self._table.item(r2, 4)
                    if tc:
                        v = _parse_fr(tc.text())
                        try:
                            total_ht += float(v) if v and v != "—" else 0.0
                        except ValueError:
                            pass

            tva_rate = getattr(getattr(self._data, "bpu", None), "tva_rate", 19.0)
            tva_amt  = total_ht * tva_rate / 100.0
            ttc      = total_ht + tva_amt

            for attr, row_idx, txt in [
                ("_row_total_ht", self._row_total_ht, f"{_fmt_fr(total_ht)} DA"),
                ("_row_tva",      self._row_tva,      f"{_fmt_fr(tva_amt)} DA"),
                ("_row_ttc",      self._row_ttc,      f"{_fmt_fr(ttc)} DA"),
            ]:
                if row_idx >= 0:
                    c = self._table.item(row_idx, 4)
                    if c:
                        c.setText(txt)

            self._lbl_counts.setText(
                self._lbl_counts.text().split("·TTC")[0].rstrip()
                + f"  ·  TTC : {_fmt_fr(ttc)} DA")
        finally:
            self._table.blockSignals(False)

        # Rafraîchir l'onglet BPU pour afficher les prix en lettres mis à jour
        self._populate_bpu()

    # ── Compteurs ─────────────────────────────────────────────────────────────

    def _update_counts(self):
        if not self._data:
            return
        n_pages = len(self._data.page_reports)
        n_items = sum(len(pr.items) for pr in self._data.page_reports)
        bpu     = getattr(self._data, "bpu", None)
        n_bpu   = len(bpu.rows) if (bpu and bpu.rows) else 0
        ttc_str = f"  ·  TTC : {bpu.total_ttc:,.0f} DA" if (bpu and bpu.rows) else ""
        self._lbl_counts.setText(
            f"{n_pages} page(s) · {n_items} mesure(s) · {n_bpu} article(s) BPU{ttc_str}")
        self._status_bar.setText(
            "Rapport calculé. Cliquez sur « Imprimer » ou « Exporter PDF ».")

    # ── Impression / Export PDF ───────────────────────────────────────────────

    def _ensure_data(self) -> bool:
        if self._data is None:
            self.refresh()
        if not self._data or not self._data.page_reports:
            QMessageBox.information(
                self, "Rapport vide",
                "Aucune mesure à rapporter.\n"
                "Chargez un plan et dessinez des mesures avant d'imprimer.")
            return False
        return True

    # ── Export Excel ──────────────────────────────────────────────────────────

    def _export_devis_excel(self):
        if not self._ensure_data():
            return
        from PyQt5.QtWidgets import QFileDialog
        default = (getattr(self._data.metadata, "get", lambda k, d=None: d)("name", "")
                   or (self._data.metadata.get("name", "") if self._data.metadata else "")) or "devis"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le Devis en Excel",
            f"{default}_devis.xlsx",
            "Fichiers Excel (*.xlsx)")
        if not path:
            return
        try:
            from ui.excel_exporter import export_devis_xlsx
            export_devis_xlsx(self, path)
            QMessageBox.information(self, "Export réussi",
                                    f"Fichier Excel enregistré :\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur export Excel", str(exc))

    def _export_attachment_excel(self):
        if not self._ensure_data():
            return
        from PyQt5.QtWidgets import QFileDialog
        default = (self._data.metadata.get("name", "") if self._data.metadata else "") or "attachement"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter l'Attachement en Excel",
            f"{default}_attachement.xlsx",
            "Fichiers Excel (*.xlsx)")
        if not path:
            return
        try:
            from ui.excel_exporter import export_attachment_xlsx
            export_attachment_xlsx(self, path)
            QMessageBox.information(self, "Export réussi",
                                    f"Fichier Excel enregistré :\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur export Excel", str(exc))

    @staticmethod
    def _setup_printer(printer, landscape: bool = False) -> None:
        """Configure l'imprimante : A4, haute résolution.
        landscape=True → orientation paysage avec marges réduites (10 mm)
        pour l'attachement ; sinon portrait marges 15 mm.
        """
        from PyQt5.QtPrintSupport import QPrinter
        margin = 10 if landscape else 15
        try:
            from PyQt5.QtGui import QPageLayout, QPageSize
            from PyQt5.QtCore import QMarginsF
            layout = printer.pageLayout()
            layout.setPageSize(QPageSize(QPageSize.A4))
            layout.setOrientation(
                QPageLayout.Landscape if landscape else QPageLayout.Portrait)
            layout.setMargins(QMarginsF(margin, margin, margin, margin))
            printer.setPageLayout(layout)
        except Exception:
            # Fallback PyQt5 ancien
            try:
                printer.setPageSize(QPrinter.A4)
                printer.setOrientation(
                    QPrinter.Landscape if landscape else QPrinter.Portrait)
                printer.setPageMargins(margin, margin, margin, margin,
                                       QPrinter.Millimeter)
            except Exception:
                pass

    # ── Sélecteur de section à exporter ──────────────────────────────────────

    _SECTION_LABELS = [
        ("pages",      "📄  Relevé quantitatif par page"),
        ("devis",      "💰  Devis général (toutes pages + synthèse + BPU)"),
        ("attachment", "📋  Attachement — justificatif des calculs"),
        ("bpu",        "📝  B.P.U. — Bordereau des Prix Unitaires"),
        ("all",        "🗂️  Rapport complet (toutes sections)"),
    ]
    _TAB_TO_SECTION = {0: "pages", 1: "devis", 2: "attachment", 3: "bpu"}

    def _ask_export_section(self, default_tab_idx: int) -> str | None:
        """
        Affiche une boîte de dialogue permettant de choisir la section à exporter.
        Retourne la clé de section choisie ou None si annulé.
        """
        from PyQt5.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QButtonGroup, QRadioButton, QPushButton,
        )
        from PyQt5.QtCore import Qt

        dlg = QDialog(self)
        dlg.setWindowTitle("Exporter en PDF")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet("QDialog{background:#fafafa;} QLabel{color:#1a1a2e;}")

        vl = QVBoxLayout(dlg)
        vl.setSpacing(8)
        vl.setContentsMargins(20, 18, 20, 14)

        title = QLabel("Choisissez la section à exporter :")
        title.setStyleSheet(
            "font-size:11px;font-weight:bold;color:#0d47a1;margin-bottom:6px;")
        vl.addWidget(title)

        group   = QButtonGroup(dlg)
        radios  = {}
        default = self._TAB_TO_SECTION.get(default_tab_idx, "pages")

        for key, label in self._SECTION_LABELS:
            rb = QRadioButton(label)
            rb.setStyleSheet("QRadioButton{font-size:10px;padding:3px 0;}")
            group.addButton(rb)
            radios[key] = rb
            vl.addWidget(rb)
            if key == default:
                rb.setChecked(True)

        if not any(rb.isChecked() for rb in radios.values()):
            radios["pages"].setChecked(True)

        vl.addSpacing(8)

        _btn_qss = (
            "QPushButton{border-radius:4px;padding:5px 18px;"
            "font-size:10px;font-weight:bold;}"
        )
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("Exporter")
        btn_ok.setDefault(True)
        btn_ok.setStyleSheet(_btn_qss +
            "QPushButton{background:#1565c0;color:#fff;border:none;}"
            "QPushButton:hover{background:#1976d2;}")
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet(_btn_qss +
            "QPushButton{background:#e0e0e0;color:#37474f;border:none;}"
            "QPushButton:hover{background:#bdbdbd;}")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        vl.addLayout(btn_row)

        if dlg.exec_() != QDialog.Accepted:
            return None
        for key, rb in radios.items():
            if rb.isChecked():
                return key
        return "pages"

    def _build_section_html(self, section: str) -> str | None:
        """
        Génère le HTML pour la section demandée.
        Retourne None si la section n'est pas disponible.
        """
        today  = __import__("datetime").date.today().strftime("%d/%m/%Y")
        header = build_html_header(self._data.metadata, today)

        if section == "pages":
            body = header + build_html_pages_section(self._data)
            return _rh_wrap(body)

        if section == "devis":
            body = (header
                    + build_html_pages_section(self._data)
                    + build_html_global_section(self._data)
                    + build_html_bpu_recap_section(self._data, page_break=True))
            return _rh_wrap(body)

        if section == "attachment":
            return self._build_att_html()

        if section == "bpu":
            return self._bpu_browser.toHtml()

        if section == "all":
            att_html = self._build_att_html()
            body = (header
                    + build_html_pages_section(self._data)
                    + build_html_global_section(self._data)
                    + build_html_bpu_recap_section(self._data, page_break=True))
            combined = _rh_wrap(body)
            if att_html:
                combined = combined.replace(
                    "</body></html>",
                    att_html.replace("<!DOCTYPE html><html><head><meta charset='utf-8'/>", "")
                            .replace("</html>", "")
                    + "</body></html>")
            return combined

        return None

    def _build_att_html(self) -> str:
        """Génère le HTML de l'attachement — optimisé pour A4 paysage.

        table-layout:fixed + largeurs en % garantissent que les colonnes
        respectent leurs proportions et que rien ne déborde de la page.
        Le <thead> est répété automatiquement à chaque saut de page par Qt.
        """
        today  = __import__("datetime").date.today().strftime("%d/%m/%Y")

        # En-tête spécifique à l'attachement :
        # - Pas de titre "Devis Quantitatif et Estimatif"
        # - Infos projet espacées des titres
        meta = self._data.metadata or {}
        _meta_rows = ""
        for label, key in [
            ("Projet",            "name"),
            ("N° de projet",      "number"),
            ("Maître d'ouvrage",  "owner"),
            ("Maître d'œuvre",    "architect"),
            ("Entreprise",        "company"),
            ("Date",              "date"),
        ]:
            val = meta.get(key, "")
            if val:
                _meta_rows += (
                    f"<tr>"
                    f"<td style='border:none;color:#546e7a;font-size:9pt;"
                    f"width:170px;padding:4pt 12pt;vertical-align:top'>{label}</td>"
                    f"<td style='border:none;font-weight:bold;font-size:10pt;"
                    f"padding:4pt 12pt'>{val}</td>"
                    f"</tr>"
                )
        header = f"""
<p style="font-size:9pt;color:#78909c;margin:0 0 8px 0">
  Métraplan &mdash; Généré le {today}
</p>
<table style="border-collapse:collapse;margin-bottom:20px;
              border-left:5px solid #1565c0;background:#f8fbff;width:60%">
  {_meta_rows}
</table>
<hr style="border:none;border-top:2px solid #1565c0;margin:0 0 24px 0"/>"""

        tbl    = self._att_table
        n_cols = tbl.columnCount()
        n_rows = tbl.rowCount()

        col_labels = [tbl.horizontalHeaderItem(c).text()
                      if tbl.horizontalHeaderItem(c) else ""
                      for c in range(n_cols)]
        visible   = [not tbl.isColumnHidden(c) for c in range(n_cols)]
        n_visible = sum(visible)

        # ── Largeurs proportionnelles lues depuis les colonnes réelles du tableau
        # Respecte exactement l'espacement que l'utilisateur a configuré à l'écran.
        _vis_widths = {c: tbl.columnWidth(c) for c in range(n_cols) if not tbl.isColumnHidden(c)}
        _total_w    = sum(_vis_widths.values()) or 1
        _col_pct    = {
            c: f"{_vis_widths[c] / _total_w * 100:.1f}%"
            for c in range(n_cols)
            if c in _vis_widths          # ignorer les colonnes masquées
        }

        # ── Constantes de style ──────────────────────────────────────────────
        _FONT_MAIN  = "9pt"    # corps du tableau (portrait = 7.5pt, paysage = 9pt)
        _FONT_CALC  = "8.5pt"  # colonne calcul (monospace)
        _FONT_LOT   = "10pt"   # en-têtes de lot
        _CELL_PAD      = "3pt 6pt"
        _CELL_PAD_CALC = "3pt 5pt"

        # ── En-tête du tableau ───────────────────────────────────────────────
        # Utilise <th> avec width="X%" pour guider table-layout:fixed.
        # Qt répète automatiquement le <thead> sur chaque page.
        th_cells = ""
        for c in range(n_cols):
            if not visible[c]:
                continue
            al  = "center" if c in (0, 6, 7, 8) else "left"
            pct = _col_pct.get(c, "")
            w_attr = f"width='{pct}'" if pct else ""
            th_cells += (
                f"<th {w_attr} style='"
                f"background:#0d47a1;color:#ffffff;"
                f"font-weight:bold;font-size:{_FONT_MAIN};"
                f"padding:{_CELL_PAD};text-align:{al};"
                f"border:1px solid #1565c0;"
                f"white-space:nowrap;'>"
                f"{col_labels[c]}</th>"
            )

        # ── Corps du tableau ─────────────────────────────────────────────────
        rows_html = ""
        alt       = False
        for r in range(n_rows):

            # Lignes fusionnées (en-têtes de lot ou séparateurs)
            col_span_0 = tbl.columnSpan(r, 0)
            if col_span_0 > 1:
                item = tbl.item(r, 0)
                txt  = (item.text() if item else "").strip()
                if txt:
                    rows_html += (
                        f"<tr><td colspan='{n_visible}' style='"
                        f"background:#dde8f5;color:#0d47a1;"
                        f"font-weight:bold;font-size:{_FONT_LOT};"
                        f"padding:5pt 10pt;"
                        f"border:1px solid #b0c4de;"
                        f"border-left:4px solid #0d47a1;'>"
                        f"&#128194;&nbsp;&nbsp;{txt}"
                        f"</td></tr>"
                    )
                else:
                    rows_html += (
                        f"<tr><td colspan='{n_visible}' style='"
                        f"background:#c8d4e8;height:3px;padding:0;border:none;'>"
                        f"</td></tr>"
                    )
                continue

            # Lignes normales
            bg     = "#f4f7ff" if alt else "#ffffff"
            alt    = not alt
            is_sub = tbl.item(r, 0) and not tbl.item(r, 0).text()
            row_bg = "#f9f9f9" if is_sub else bg
            cells  = ""

            for c in range(n_cols):
                if not visible[c]:
                    continue
                item = tbl.item(r, c)
                txt  = item.text() if item else ""
                al   = "right" if c in (6, 7) else ("center" if c in (0, 8) else "left")
                bd   = "bold" if c in (1, 7) else "normal"
                col_color = "#1565c0" if c == 7 else "#1a1a2e"

                if c == 5:
                    # Calcul détaillé : monospace, \n → saut de ligne réel
                    safe = (txt.replace("&", "&amp;")
                               .replace("<", "&lt;")
                               .replace(">", "&gt;"))
                    cells += (
                        f"<td style='border:1px solid #cfd8dc;"
                        f"padding:{_CELL_PAD_CALC};"
                        f"background:{row_bg};vertical-align:top;'>"
                        f"<pre style='"
                        f"font-family:Consolas,\"Courier New\",monospace;"
                        f"font-size:{_FONT_CALC};color:#000000;"
                        f"margin:0;padding:0;"
                        f"white-space:pre;line-height:1.4;"
                        f"word-break:break-all;'>"
                        f"{safe}</pre></td>"
                    )
                else:
                    # Désignation (col 1) : word-wrap pour les noms longs
                    wrap = ("word-wrap:break-word;word-break:break-word;"
                            if c == 1 else "white-space:nowrap;")
                    cells += (
                        f"<td style='border:1px solid #cfd8dc;"
                        f"padding:{_CELL_PAD};"
                        f"font-size:{_FONT_MAIN};"
                        f"background:{row_bg};"
                        f"text-align:{al};"
                        f"font-weight:{bd};"
                        f"color:{col_color};"
                        f"vertical-align:top;{wrap}'>"
                        f"{txt}</td>"
                    )
            rows_html += f"<tr>{cells}</tr>"

        # ── Assemblage ───────────────────────────────────────────────────────
        h2 = _rh_h2("ATTACHEMENT — JUSTIFICATIF DES CALCULS",
                    color="#0d47a1", bg="#e3f2fd", accent="#1565c0")
        body = f"""
{header}
{h2}
<p style="font-size:{_FONT_MAIN};color:#78909c;margin-bottom:10px">
  Généré le {today}
</p>
<table width="100%"
       style="border-collapse:collapse;margin-bottom:20px;
              font-size:{_FONT_MAIN};table-layout:fixed">
  <thead>
    <tr>{th_cells}</tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>"""
        return _rh_wrap(body)

    def _print_report(self):
        if not self._ensure_data():
            return
        try:
            from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt5.QtGui import QTextDocument
            # Choisir la section d'abord pour configurer l'orientation avant
            # d'ouvrir le dialogue d'impression.
            section = self._ask_export_section(self._tabs.currentIndex())
            if section is None:
                return
            printer = QPrinter(QPrinter.HighResolution)
            self._setup_printer(printer, landscape=(section == "attachment"))
            dlg = QPrintDialog(printer, self)
            dlg.setWindowTitle("Imprimer le rapport")
            if dlg.exec_() != QPrintDialog.Accepted:
                return
            html = self._build_section_html(section)
            if not html:
                QMessageBox.warning(self, "Section vide", "Aucun contenu à imprimer.")
                return
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(printer)
            self._status_bar.setText("Rapport envoyé à l'imprimante.")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'impression", str(exc))

    def _export_pdf(self):
        if not self._ensure_data():
            return
        try:
            from PyQt5.QtPrintSupport import QPrinter
            from PyQt5.QtGui import QTextDocument

            section = self._ask_export_section(self._tabs.currentIndex())
            if section is None:
                return

            # Détermine le suffixe du nom de fichier selon la section choisie
            _suffixes = {
                "pages":      "releve_par_page",
                "devis":      "devis_general",
                "attachment": "attachement",
                "bpu":        "BPU",
                "all":        "rapport_complet",
            }
            default_name = self._data.metadata.get("name", "rapport") or "rapport"
            suffix = _suffixes.get(section, "rapport")
            path, _ = QFileDialog.getSaveFileName(
                self, "Exporter en PDF",
                f"{default_name}_{suffix}.pdf",
                "Fichiers PDF (*.pdf)")
            if not path:
                return

            html = self._build_section_html(section)
            if not html:
                QMessageBox.warning(self, "Section vide",
                                    "Aucun contenu à exporter pour cette section.")
                return

            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            self._setup_printer(printer, landscape=(section == "attachment"))
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(printer)

            self._status_bar.setText(f"Exporté : {path}")
            QMessageBox.information(
                self, "Export réussi",
                f"Le rapport a été exporté avec succès :\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'export", str(exc))
