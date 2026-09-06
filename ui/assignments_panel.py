# ui/assignments_panel.py
"""
Panneau d'affectation des items de devis à un groupe de mesure.

Affiché comme onglet supplémentaire dans le PropertyPanel lorsqu'un groupe
(surface, périmètre ou compteur) est sélectionné.

Disposition :
  ┌─────────────────────────────────────────────────────────┐
  │  MESURES DISPONIBLES                                    │
  │  surface_nette = 45.30 m²   hauteur = 2.80 m  ...      │
  ├─────────────────────────────────────────────────────────┤
  │  ITEMS AFFECTÉS                          [+ Ajouter]    │
  │  ┌──────────────────────────────────────────────────┐   │
  │  │ Lot  │ Désignation │ Formule │ Coef │ PU  │ Total│   │
  │  │ 04   │ Brique 25cm │ s_nette │ 1.0  │2500 │87500 │[✕]│
  │  └──────────────────────────────────────────────────┘   │
  │  Sous-total groupe : 116 550 DA                         │
  ├─────────────────────────────────────────────────────────┤
  │  [AJOUTER UN ITEM]                                      │
  │  Lot  : [04 – Maçonnerie ▼]                             │
  │  Item : [04.01 Brique 25cm ▼]                           │
  │  Formule : [surface_nette ▼]  × [1.00]                  │
  │  Prix U. : [2 500]  → 45.30 m²  = 113 250 DA           │
  │                            [Valider] [Annuler]          │
  └─────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QDoubleSpinBox, QFrame, QSizePolicy, QScrollArea,
    QLineEdit, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

if TYPE_CHECKING:
    pass

from core.devis_manager import DevisManager, AssignedItem, GroupAssignment
from core.formula_engine import (
    build_variables, evaluate_formula, preview_formula,
    get_available_variables, VARIABLE_DESCRIPTIONS
)


# ── Helpers de formatage ──────────────────────────────────────────────────────

def _fmt_money(v: float) -> str:
    """Formate un montant en DA avec séparateur de milliers."""
    if v == 0.0:
        return "—"
    return f"{v:,.0f} DA".replace(",", " ")


def _fmt_qty(v: float, unit: str) -> str:
    if unit in ("m²", "m³"):
        return f"{v:.2f} {unit}"
    if unit in ("ml", "m"):
        return f"{v:.2f} {unit}"
    if unit == "U":
        return f"{int(round(v))} U"
    return f"{v:.2f}"


# ── Widget principal ──────────────────────────────────────────────────────────

class AssignmentsPanel(QWidget):
    """
    Panneau d'affectation — s'intègre comme onglet dans PropertyPanel.
    """

    # Émis quand les affectations changent (pour rafraîchir le rapport)
    assignments_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entity   = None
        self._group_id = None
        self._dm       = DevisManager.instance()
        self._build_ui()
        # Se connecter au signal pour rafraîchir les combos si la bibliothèque change
        self._dm.devis_structure_changed.connect(self._on_devis_library_changed)

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Zone mesures disponibles ──────────────────────────────────────────
        lbl_mes = QLabel("MESURES DISPONIBLES")
        lbl_mes.setStyleSheet(
            "font-size:9px; font-weight:bold; color:#607080; letter-spacing:1px;")
        root.addWidget(lbl_mes)

        self._vars_label = QLabel("—")
        self._vars_label.setWordWrap(True)
        self._vars_label.setStyleSheet(
            "background:#f0f4fa; border:1px solid #c8d4e8; border-radius:4px;"
            "padding:4px 6px; font-size:11px; color:#2a3a5a;")
        root.addWidget(self._vars_label)

        # ── Séparateur ────────────────────────────────────────────────────────
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color:#c8d4e8;")
        root.addWidget(sep1)

        # ── Tableau des items affectés ────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl_aff = QLabel("ITEMS AFFECTÉS")
        lbl_aff.setStyleSheet(
            "font-size:9px; font-weight:bold; color:#607080; letter-spacing:1px;")
        hdr.addWidget(lbl_aff)
        hdr.addStretch()
        root.addLayout(hdr)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Lot", "Désignation", "Formule", "Coef.", "Quantité"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setMinimumHeight(100)
        self._table.setMaximumHeight(200)
        self._table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #c8d4e8; border-radius: 4px;
                font-size: 11px; background: #ffffff;
            }
            QTableWidget::item { padding: 2px 4px; cursor: pointer; }
            QTableWidget::item:selected { background: #bbdefb; color: #0d47a1; }
            QTableWidget::item:hover { background: #e3f2fd; }
            QHeaderView::section {
                background: #e3f2fd; color: #0d47a1;
                font-weight: bold; font-size: 10px;
                border: none; padding: 3px 4px;
            }
        """)
        self._table.setToolTip(
            "Double-clic sur Formule → constructeur de formule\n"
            "Double-clic sur Nombre → modifier le coefficient")
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self._table.itemChanged.connect(self._on_table_item_changed)
        root.addWidget(self._table)

        # Hint
        hint = QLabel("✎  Double-cliquez sur une ligne pour modifier la formule")
        hint.setStyleSheet(
            "font-size:10px; color:#78909c; font-style:italic; padding:1px 2px;")
        root.addWidget(hint)

        # Sous-total
        self._subtotal_label = QLabel("Sous-total : —")
        self._subtotal_label.setStyleSheet(
            "font-size:11px; font-weight:bold; color:#0d47a1;"
            "padding:2px 4px; text-align:right;")
        self._subtotal_label.setAlignment(Qt.AlignRight)
        root.addWidget(self._subtotal_label)

        # Bouton supprimer la ligne sélectionnée
        btn_del = QPushButton("✕  Supprimer l'item sélectionné")
        btn_del.setStyleSheet("""
            QPushButton { border:1px solid #e57373; border-radius:4px;
                          padding:3px 8px; font-size:11px; color:#c62828;
                          background:#fff5f5; }
            QPushButton:hover { background:#ffcdd2; }
        """)
        btn_del.clicked.connect(self._remove_selected)
        root.addWidget(btn_del)

        # ── Séparateur ────────────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:#c8d4e8;")
        root.addWidget(sep2)

        # ── Formulaire d'ajout ────────────────────────────────────────────────
        lbl_add = QLabel("AJOUTER UN ITEM")
        lbl_add.setStyleSheet(
            "font-size:9px; font-weight:bold; color:#607080; letter-spacing:1px;")
        root.addWidget(lbl_add)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(4)

        # Lot
        row_lot = QHBoxLayout()
        row_lot.addWidget(QLabel("Lot :"))
        self._combo_lot = QComboBox()
        self._combo_lot.setMinimumWidth(180)
        self._combo_lot.currentIndexChanged.connect(self._on_lot_changed)
        row_lot.addWidget(self._combo_lot, 1)
        form_layout.addLayout(row_lot)

        # Item
        row_item = QHBoxLayout()
        row_item.addWidget(QLabel("Item :"))
        self._combo_item = QComboBox()
        self._combo_item.setMinimumWidth(180)
        self._combo_item.currentIndexChanged.connect(self._on_item_changed)
        row_item.addWidget(self._combo_item, 1)
        form_layout.addLayout(row_item)

        # Formule + coefficient
        row_formula = QHBoxLayout()
        row_formula.addWidget(QLabel("Formule :"))
        self._combo_formula = QComboBox()
        self._combo_formula.setMinimumWidth(130)
        self._combo_formula.setEditable(True)
        self._combo_formula.setToolTip(
            "Double-cliquez pour ouvrir le Constructeur de formule")
        self._combo_formula.currentTextChanged.connect(self._update_preview)
        # Double-clic sur la zone de saisie → ouvrir le constructeur
        self._combo_formula.lineEdit().mouseDoubleClickEvent = (
            lambda _e: self._open_formula_builder())
        row_formula.addWidget(self._combo_formula, 1)

        # Bouton "..." pour ouvrir le constructeur de formule
        btn_builder = QPushButton("…")
        btn_builder.setToolTip("Ouvrir le Constructeur de formule")
        btn_builder.setFixedSize(26, 26)
        btn_builder.setStyleSheet("""
            QPushButton { border:1px solid #1976d2; border-radius:4px;
                          font-size:13px; color:#1565c0; background:#e8f0fe; }
            QPushButton:hover { background:#bbdefb; }
        """)
        btn_builder.clicked.connect(self._open_formula_builder)
        row_formula.addWidget(btn_builder)

        row_formula.addWidget(QLabel("×"))
        self._spin_coef = QDoubleSpinBox()
        self._spin_coef.setRange(0.001, 999.0)
        self._spin_coef.setValue(1.0)
        self._spin_coef.setDecimals(3)
        self._spin_coef.setFixedWidth(70)
        self._spin_coef.valueChanged.connect(self._update_preview)
        row_formula.addWidget(self._spin_coef)
        form_layout.addLayout(row_formula)

        # Aperçu résultat
        self._preview_label = QLabel("→ —")
        self._preview_label.setStyleSheet(
            "font-size:11px; color:#1565c0; font-style:italic; padding:2px 4px;")
        self._preview_label.setWordWrap(True)
        form_layout.addWidget(self._preview_label)

        # Bouton valider
        row_btn = QHBoxLayout()
        row_btn.addStretch()
        btn_ok = QPushButton("✓  Ajouter")
        btn_ok.setStyleSheet("""
            QPushButton { border:1px solid #43a047; border-radius:4px;
                          padding:4px 14px; font-size:11px; color:#1b5e20;
                          background:#e8f5e9; font-weight:bold; }
            QPushButton:hover { background:#c8e6c9; }
        """)
        btn_ok.clicked.connect(self._add_item)
        row_btn.addWidget(btn_ok)
        form_layout.addLayout(row_btn)

        root.addWidget(form_widget)
        root.addStretch()

        # Remplir les lots
        self._populate_lots()

    # ── Peuplement des combos ─────────────────────────────────────────────────

    def _open_formula_builder(self):
        """Ouvre le dialogue Constructeur de formule."""
        from ui.formula_builder_dialog import FormulaBuilderDialog
        from PyQt5.QtWidgets import QDialog

        dlg = FormulaBuilderDialog(
            entity=self._entity,
            parent=self,
            initial_formula="",   # toujours vide — l'utilisateur saisit sa propre formule
        )
        if dlg.exec_() == QDialog.Accepted:
            new_formula = dlg.formula()
            if new_formula:
                # Insérer dans le combo (ou remplacer le texte actuel)
                idx = self._combo_formula.findText(new_formula)
                if idx >= 0:
                    self._combo_formula.setCurrentIndex(idx)
                else:
                    self._combo_formula.setCurrentText(new_formula)
                self._update_preview()

    def _populate_lots(self):
        self._combo_lot.blockSignals(True)
        self._combo_lot.clear()
        for lot in self._dm.lots:
            self._combo_lot.addItem(f"{lot.id} – {lot.label}", lot.id)
        self._combo_lot.blockSignals(False)
        self._on_lot_changed(0)

    def _on_devis_library_changed(self):
        """La bibliothèque a changé (ajout/suppression lot/item) → rafraîchir les combos."""
        self._populate_lots()

    def _on_lot_changed(self, _idx: int):
        lot_id = self._combo_lot.currentData()
        lot = self._dm.get_lot(lot_id) if lot_id else None
        self._combo_item.blockSignals(True)
        self._combo_item.clear()
        if lot:
            for item in lot.items:
                self._combo_item.addItem(
                    f"{item.id}  {item.label}  [{item.unit}]",
                    (item.id, item.unit, item.default_formula)
                )
        self._combo_item.blockSignals(False)
        self._on_item_changed(0)

    # Formule par défaut selon l'unité (surface / périmètre)
    _UNIT_DEFAULT_FORMULA = {
        "m²":  "surface_nette",
        "m2":  "surface_nette",
        "m³":  "volume",
        "m3":  "volume",
        "ml":  "longueur_nette",
        "m":   "longueur_nette",
        "U":   "nombre",
        "u":   "nombre",
        "ens": "nombre",
        "ft":  "longueur_nette",
    }

    # Formule par défaut pour les compteurs (point) — remplace _UNIT_DEFAULT_FORMULA
    _UNIT_DEFAULT_FORMULA_POINT = {
        "m²":  "surface_compteur",
        "m2":  "surface_compteur",
        "m³":  "volume_compteur",
        "m3":  "volume_compteur",
        "ml":  "nombre",
        "m":   "nombre",
        "U":   "nombre",
        "u":   "nombre",
        "ens": "nombre",
        "ft":  "nombre",
    }

    def _on_item_changed(self, _idx: int):
        data = self._combo_item.currentData()
        if not data:
            return
        _item_id, _unit, default_formula = data

        # La formule basée sur l'unité est TOUJOURS prioritaire.
        # Pour les compteurs, utiliser le dictionnaire spécifique aux points.
        etype = getattr(self._entity, "entity_type", "") if self._entity else ""
        if etype == "point":
            unit_formula = self._UNIT_DEFAULT_FORMULA_POINT.get(_unit.strip(), "")
        else:
            unit_formula = self._UNIT_DEFAULT_FORMULA.get(_unit.strip(), "")
        default_formula = unit_formula or default_formula

        self._combo_formula.blockSignals(True)
        self._combo_formula.clear()
        # Proposer les variables compatibles avec le type d'entité courant
        for v in get_available_variables(etype):
            self._combo_formula.addItem(v["name"])
        if default_formula:
            idx = self._combo_formula.findText(default_formula)
            if idx >= 0:
                self._combo_formula.setCurrentIndex(idx)
            else:
                self._combo_formula.setCurrentText(default_formula)
        self._combo_formula.blockSignals(False)
        self._update_preview()

    # ── Aperçu temps réel ─────────────────────────────────────────────────────

    def _update_preview(self):
        if not self._entity:
            self._preview_label.setText("→ —")
            return
        formula = self._combo_formula.currentText().strip()
        coef    = self._spin_coef.value()

        data = self._combo_item.currentData()
        unit = data[1] if data else ""

        vars_ = build_variables(self._entity)
        qty, err = evaluate_formula(formula, vars_, coef)

        if err:
            self._preview_label.setText(f"→ ⚠ {err}")
            return

        qty_str = _fmt_qty(qty, unit)
        self._preview_label.setText(f"→  <b>{qty_str}</b>")

    # ── Chargement de l'entité ────────────────────────────────────────────────

    def load_entity(self, entity):
        """
        Charge les affectations pour l'entité (groupe) sélectionnée.

        Remonte TOUJOURS au parent du groupe : l'affectation BPU porte
        sur le total du groupe complet, même si l'utilisateur a cliqué
        sur un enfant.
        """
        if entity is not None:
            from core.formula_engine import _resolve_group_root
            entity = _resolve_group_root(entity)

        self._entity = entity
        if not entity:
            self._group_id = None
            self._vars_label.setText("—")
            self._table.setRowCount(0)
            self._subtotal_label.setText("Aucun article affecté")
            return

        # Identifier le groupe (toujours via le parent résolu)
        # Priorité : group_id persistant → entity_id stable → fallback str(id)
        self._group_id = (getattr(entity, "group_id", None)
                          or getattr(entity, "entity_id", None)
                          or str(id(entity)))

        # Afficher les variables disponibles (total du groupe complet)
        vars_ = build_variables(entity)
        etype = getattr(entity, "entity_type", "")
        children = getattr(entity, "child_entities", []) or []
        n_members = 1 + len(children)

        visible_keys = {
            "polygon":   ["surface_brute", "surface_nette",
                          "perimetre_surface", "perimetre_ouvertures", "hauteur"],
            "perimeter": ["longueur_brute", "longueur_nette",
                          "surface_brute", "surface_nette", "volume",
                          "hauteur", "epaisseur", "perimetre_ouvertures"],
            "point":     ["nombre", "longueur_unitaire", "hauteur", "epaisseur"],
        }.get(etype, list(vars_.keys()))

        parts = []
        for k in visible_keys:
            v = vars_.get(k, 0.0)
            info = VARIABLE_DESCRIPTIONS.get(k, {})
            unit = info.get("unit", "")
            if v != 0.0:
                parts.append(f"<b>{k}</b> = {v:.2f} {unit}")

        group_name = getattr(entity, "name", "Sans nom")
        group_info = (f"Groupe : <b>{group_name}</b>"
                      + (f" ({n_members} éléments)" if n_members > 1 else ""))
        display_text = (group_info + "   —   " + "   ".join(parts)
                        if parts else group_info + "   —   (aucune mesure)")
        self._vars_label.setText(display_text)

        # Mettre à jour le combo formule selon le type
        self._on_item_changed(self._combo_item.currentIndex())

        # Rafraîchir le tableau
        self._refresh_table()
        self._populate_lots()

    def _refresh_table(self):
        """Recharge le tableau des items affectés depuis DevisManager."""
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        if not self._group_id:
            self._table.blockSignals(False)
            return

        ga = self._dm.get_assignment(self._group_id)
        if not ga:
            self._table.blockSignals(False)
            self._subtotal_label.setText("Aucun article affecté")
            return

        vars_ = build_variables(self._entity) if self._entity else {}
        item_count = 0
        bold = QFont()
        bold.setBold(True)

        for row_idx, ai in enumerate(ga.items):
            qty, total, err = 0.0, 0.0, ""
            if self._entity:
                from core.formula_engine import compute_assignment_item
                qty, total, err = compute_assignment_item(self._entity, ai)
            item_count += 1

            item_label = self._dm.get_item_label(ai.lot_id, ai.item_id)
            item_unit  = self._dm.get_item_unit(ai.lot_id, ai.item_id)
            lot_obj    = self._dm.get_lot(ai.lot_id)
            lot_label  = f"{ai.lot_id} – {lot_obj.label}" if lot_obj else ai.lot_id

            self._table.insertRow(row_idx)
            item_unit = self._dm.get_item_unit(ai.lot_id, ai.item_id)
            qty_str   = _fmt_qty(qty, item_unit) if not err else f"⚠ {err}"
            vals = [
                lot_label,
                item_label,
                ai.formula_expr,
                f"{ai.coefficient:.3g}",
                qty_str,
            ]
            for col, txt in enumerate(vals):
                cell = QTableWidgetItem(txt)
                if col == 4:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if not err:
                        cell.setForeground(QBrush(QColor("#1565c0")))
                        cell.setFont(bold)
                self._table.setItem(row_idx, col, cell)

        self._table.blockSignals(False)
        self._subtotal_label.setText(
            f"{item_count} article(s) affecté(s) — Prix U. à saisir dans l'onglet Devis")

    # ── Double-clic sur une ligne : modifier la formule ou le coefficient ────

    def _on_row_double_clicked(self, row: int, col: int):
        """
        Col 2 (Formule)      → ouvre le constructeur de formule.
        Col 3 (Coefficient)  → dialogue de saisie du nombre.
        """
        ga = self._dm.get_assignment(self._group_id) if self._group_id else None
        if not ga or row >= len(ga.items):
            return
        ai = ga.items[row]

        if col == 3:
            # ── Modifier le coefficient (Nombre) ──────────────────────────
            from PyQt5.QtWidgets import QInputDialog
            cur = float(getattr(ai, "coefficient", 1.0) or 1.0)
            val, ok = QInputDialog.getDouble(
                self, "Modifier le nombre",
                "Nombre (coefficient multiplicateur) :",
                cur, 0.001, 9999.0, 3)
            if ok:
                self._dm.update_assignment_item(
                    self._group_id, row, coefficient=val)
                self._refresh_table()
                self.assignments_changed.emit()
            return

        if col in (0, 1, 2, 4):
            # ── Modifier la formule (comportement existant) ────────────────
            from ui.formula_builder_dialog import FormulaBuilderDialog
            from PyQt5.QtWidgets import QDialog

            item_lbl = self._dm.get_item_label(ai.lot_id, ai.item_id)
            dlg = FormulaBuilderDialog(
                entity=self._entity,
                parent=self,
                initial_formula=ai.formula_expr,
            )
            dlg.setWindowTitle(
                f"Modifier la formule — {ai.lot_id}.{ai.item_id}  {item_lbl}")
            if dlg.exec_() == QDialog.Accepted:
                new_formula = dlg.formula()
                if new_formula:
                    self._dm.update_assignment_item(
                        self._group_id, row, formula_expr=new_formula)
                    self._refresh_table()
                    self.assignments_changed.emit()

    # ── Événement modification tableau (conservé pour rétrocompat) ────────────

    def _on_table_item_changed(self, item: QTableWidgetItem):
        """Inutilisé depuis passage à NoEditTriggers — conservé pour sécurité."""
        pass

    # ── Ajout d'un item ───────────────────────────────────────────────────────

    def _add_item(self):
        if not self._entity or not self._group_id:
            QMessageBox.warning(self, "Aucun groupe",
                                "Sélectionnez d'abord un groupe sur le canvas.")
            return

        lot_id = self._combo_lot.currentData()
        item_data = self._combo_item.currentData()
        if not lot_id or not item_data:
            return
        item_id, _unit, _ = item_data
        formula  = self._combo_formula.currentText().strip()
        coef     = self._spin_coef.value()
        pu       = 0.0  # Le prix unitaire est saisi dans le tableau Devis

        if not formula:
            QMessageBox.warning(self, "Formule vide", "Entrez une formule de calcul.")
            return

        # Valider la formule
        vars_ = build_variables(self._entity)
        from core.formula_engine import evaluate_formula
        _, err = evaluate_formula(formula, vars_, coef)
        if err:
            QMessageBox.warning(self, "Formule invalide", err)
            return

        group_name = getattr(self._entity, "name", "Sans nom")
        group_type = getattr(self._entity, "entity_type", "")
        page_name  = ""  # sera renseigné par le contexte si disponible

        self._dm.add_assignment_item(
            group_id    = self._group_id,
            group_name  = group_name,
            group_type  = group_type,
            page_name   = page_name,
            lot_id      = lot_id,
            item_id     = item_id,
            formula_expr = formula,
            coefficient = coef,
            prix_unitaire = pu,
        )
        self._refresh_table()
        self.assignments_changed.emit()

    # ── Suppression ───────────────────────────────────────────────────────────

    def _remove_selected(self):
        if not self._group_id:
            return
        rows = sorted(
            {idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._dm.remove_assignment_item(self._group_id, row)
        self._refresh_table()
        self.assignments_changed.emit()
