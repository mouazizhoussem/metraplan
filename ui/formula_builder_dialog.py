# ui/formula_builder_dialog.py
"""
Constructeur de formule visuel — dialogue Métraplan.

Ouverture par double-clic sur le champ Formule dans l'onglet Affectations.

Disposition :
  ┌────────────────────────────────────────────────────────────┐
  │  CONSTRUCTEUR DE FORMULE                                   │
  │  ┌──────────────────────────────────────┐  [✕ Effacer]    │
  │  │  surface_nette × 2 + perimetre_...  │                  │
  │  └──────────────────────────────────────┘                  │
  │                                                            │
  │  Opérateurs :  [+]  [-]  [×]  [÷]  [(]  [)]              │
  │                                                            │
  │  ──────────────────────────────────────────────────────── │
  │  Résultats du groupe — double-clic pour insérer           │
  │                                                            │
  │  ┌──────────────────┬──────────┬────────────────────────┐ │
  │  │ Variable          │ Valeur   │ Description             │ │
  │  ├──────────────────┼──────────┼────────────────────────┤ │
  │  │ surface_nette     │ 45.30 m² │ Aire après déductions  │ │
  │  │ surface_brute     │ 48.50 m² │ Aire totale brute      │ │
  │  │ perimetre_surface │ 28.60 ml │ Longueur du contour    │ │
  │  │ hauteur           │  2.80 m  │ Hauteur saisie         │ │
  │  └──────────────────┴──────────┴────────────────────────┘ │
  │                                                            │
  │  → Résultat aperçu : surface_nette × 2 = 90.60            │
  │                                                            │
  │                              [Annuler]   [✓ Valider]      │
  └────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QSizePolicy, QDialogButtonBox, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QColor, QBrush, QKeySequence

from core.formula_engine import (
    build_variables, evaluate_formula,
    VARIABLE_DESCRIPTIONS, get_available_variables,
)


# ── Dialogue principal ────────────────────────────────────────────────────────

class FormulaBuilderDialog(QDialog):
    """
    Dialogue de construction visuelle de formule.

    Usage :
        dlg = FormulaBuilderDialog(entity, parent=self, initial_formula=expr)
        if dlg.exec_() == QDialog.Accepted:
            formula = dlg.formula()
    """

    def __init__(self, entity, parent=None, initial_formula: str = ""):
        super().__init__(parent)
        self._entity   = entity
        self._vars: Dict[str, float] = {}
        if entity is not None:
            self._vars = build_variables(entity)

        self.setWindowTitle("Constructeur de formule")
        self.setMinimumWidth(600)
        self.setMinimumHeight(420)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._build_ui(initial_formula)

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self, initial_formula: str):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Titre ─────────────────────────────────────────────────────────────
        title = QLabel("Constructeur de formule")
        title.setStyleSheet(
            "font-size:13px; font-weight:bold; color:#0d47a1;")
        root.addWidget(title)

        subtitle = QLabel(
            "Composez la formule en cliquant sur les opérateurs et les variables ci-dessous.\n"
            "Vous pouvez aussi saisir directement au clavier.")
        subtitle.setStyleSheet("font-size:11px; color:#607080;")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        sep0 = QFrame(); sep0.setFrameShape(QFrame.HLine)
        sep0.setStyleSheet("color:#c8d4e8;"); root.addWidget(sep0)

        # ── Champ de formule ──────────────────────────────────────────────────
        lbl_formula = QLabel("Formule :")
        lbl_formula.setStyleSheet("font-size:11px; font-weight:bold;")
        root.addWidget(lbl_formula)

        formula_row = QHBoxLayout()
        self._formula_edit = QLineEdit()
        self._formula_edit.setText(initial_formula)
        self._formula_edit.setPlaceholderText(
            "Ex : surface_nette × 2   ou   longueur_nette × hauteur")
        self._formula_edit.setStyleSheet("""
            QLineEdit {
                font-size: 13px; font-family: Consolas, monospace;
                padding: 6px 8px; border: 2px solid #1976d2;
                border-radius: 5px; background: #f0f7ff; color: #0d47a1;
            }
            QLineEdit:focus { border-color: #0d47a1; background: #e8f0fe; }
        """)
        self._formula_edit.textChanged.connect(self._update_preview)
        formula_row.addWidget(self._formula_edit, 1)

        btn_clear = QPushButton("✕")
        btn_clear.setToolTip("Effacer la formule")
        btn_clear.setFixedSize(30, 30)
        btn_clear.setStyleSheet("""
            QPushButton { border:1px solid #e57373; border-radius:4px;
                          color:#c62828; background:#fff5f5; font-size:13px; }
            QPushButton:hover { background:#ffcdd2; }
        """)
        btn_clear.clicked.connect(lambda: self._formula_edit.clear())
        formula_row.addWidget(btn_clear)
        root.addLayout(formula_row)

        # ── Opérateurs ────────────────────────────────────────────────────────
        ops_row = QHBoxLayout()
        ops_row.addWidget(QLabel("Opérateurs :"))

        btn_style = """
            QPushButton {
                border: 1px solid #b0c4de; border-radius: 5px;
                padding: 5px 12px; font-size: 15px; font-weight: bold;
                color: #1565c0; background: #e8f0fe; min-width: 36px;
            }
            QPushButton:hover   { background: #bbdefb; border-color: #1976d2; }
            QPushButton:pressed { background: #90caf9; }
        """
        for symbol, insert in [
            ("+", " + "), ("−", " - "), ("×", " × "), ("÷", " ÷ "),
            ("(", "("), (")", ")"),
        ]:
            btn = QPushButton(symbol)
            btn.setStyleSheet(btn_style)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _, s=insert: self._insert_text(s))
            ops_row.addWidget(btn)

        ops_row.addStretch()

        # Bouton backspace
        btn_back = QPushButton("⌫")
        btn_back.setToolTip("Supprimer le dernier caractère")
        btn_back.setFixedHeight(34)
        btn_back.setStyleSheet("""
            QPushButton { border:1px solid #b0c4de; border-radius:5px;
                          padding:5px 10px; font-size:14px;
                          color:#607080; background:#f5f5f5; }
            QPushButton:hover { background:#eeeeee; }
        """)
        btn_back.clicked.connect(self._backspace)
        ops_row.addWidget(btn_back)

        root.addLayout(ops_row)

        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color:#c8d4e8;"); root.addWidget(sep1)

        # ── Tableau des variables ─────────────────────────────────────────────
        lbl_vars = QLabel(
            "Résultats du groupe — double-clic sur une ligne pour l'insérer dans la formule")
        lbl_vars.setStyleSheet("font-size:11px; font-weight:bold; color:#2a3a5a;")
        root.addWidget(lbl_vars)

        self._vars_table = QTableWidget(0, 3)
        self._vars_table.setHorizontalHeaderLabels(
            ["Variable", "Valeur", "Description"])
        self._vars_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self._vars_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents)
        self._vars_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        self._vars_table.verticalHeader().setVisible(False)
        self._vars_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._vars_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._vars_table.setAlternatingRowColors(True)
        self._vars_table.setShowGrid(False)
        self._vars_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #c8d4e8; border-radius: 4px;
                font-size: 12px; background: #ffffff;
            }
            QTableWidget::item { padding: 4px 6px; cursor: pointer; }
            QTableWidget::item:selected { background: #bbdefb; color: #0d47a1; }
            QTableWidget::item:hover    { background: #e3f2fd; }
            QHeaderView::section {
                background: #e3f2fd; color: #0d47a1;
                font-weight: bold; font-size: 10px;
                border: none; padding: 4px 6px;
            }
        """)
        self._vars_table.itemDoubleClicked.connect(self._on_var_double_clicked)
        self._vars_table.setMinimumHeight(160)
        root.addWidget(self._vars_table)

        self._populate_vars_table()

        # ── Aperçu résultat ───────────────────────────────────────────────────
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:#c8d4e8;"); root.addWidget(sep2)

        self._preview_label = QLabel("→  —")
        self._preview_label.setStyleSheet("""
            QLabel {
                font-size: 12px; font-style: italic;
                color: #1565c0; padding: 4px 8px;
                background: #e8f0fe; border-radius: 4px;
                border: 1px solid #90caf9;
            }
        """)
        self._preview_label.setWordWrap(True)
        root.addWidget(self._preview_label)
        self._update_preview()

        # ── Boutons OK / Annuler ──────────────────────────────────────────────
        btns = QDialogButtonBox()
        btn_ok = QPushButton("✓  Valider")
        btn_ok.setDefault(True)
        btn_ok.setStyleSheet("""
            QPushButton { border:1px solid #43a047; border-radius:5px;
                          padding:6px 20px; font-size:12px; font-weight:bold;
                          color:#1b5e20; background:#e8f5e9; }
            QPushButton:hover { background:#c8e6c9; }
        """)
        btn_ok.clicked.connect(self.accept)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet("""
            QPushButton { border:1px solid #b0c4de; border-radius:5px;
                          padding:6px 16px; font-size:12px;
                          color:#5a7090; background:#f0f4fa; }
            QPushButton:hover { background:#e0e8f4; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    # ── Peuplement du tableau des variables ───────────────────────────────────

    def _populate_vars_table(self):
        """Remplit le tableau avec les variables disponibles pour ce type d'entité."""
        self._vars_table.setRowCount(0)
        if not self._entity:
            return

        etype = getattr(self._entity, "entity_type", "")
        available = get_available_variables(etype)

        bold_font = QFont()
        bold_font.setBold(True)
        mono_font = QFont("Consolas, monospace")
        mono_font.setPointSize(10)

        for var_info in available:
            name  = var_info["name"]
            unit  = var_info["unit"]
            desc  = var_info["desc"]
            value = self._vars.get(name, 0.0)

            row = self._vars_table.rowCount()
            self._vars_table.insertRow(row)

            # Colonne 0 : nom de la variable (code)
            name_item = QTableWidgetItem(name)
            name_item.setFont(mono_font)
            name_item.setForeground(QBrush(QColor("#1565c0")))
            name_item.setData(Qt.UserRole, name)   # stocker le nom pour l'insertion
            self._vars_table.setItem(row, 0, name_item)

            # Colonne 1 : valeur calculée
            if unit in ("m²", "m³"):
                val_str = f"{value:.2f} {unit}"
            elif unit in ("ml", "m"):
                val_str = f"{value:.2f} {unit}"
            elif unit == "U":
                val_str = f"{int(round(value))} U"
            else:
                val_str = f"{value:.2f}"

            val_item = QTableWidgetItem(val_str)
            val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_item.setFont(bold_font)
            # Colorer en bleu si > 0, gris si = 0
            if value > 0:
                val_item.setForeground(QBrush(QColor("#0d47a1")))
            else:
                val_item.setForeground(QBrush(QColor("#b0bec5")))
            val_item.setData(Qt.UserRole, name)
            self._vars_table.setItem(row, 1, val_item)

            # Colonne 2 : description
            desc_item = QTableWidgetItem(desc)
            desc_item.setForeground(QBrush(QColor("#607080")))
            desc_item.setData(Qt.UserRole, name)
            self._vars_table.setItem(row, 2, desc_item)

        self._vars_table.resizeRowsToContents()

    # ── Insertion dans le champ de formule ────────────────────────────────────

    def _insert_text(self, text: str):
        """Insère du texte à la position du curseur dans le champ de formule."""
        edit = self._formula_edit
        cursor_pos = edit.cursorPosition()
        current = edit.text()
        new_text = current[:cursor_pos] + text + current[cursor_pos:]
        edit.setText(new_text)
        edit.setCursorPosition(cursor_pos + len(text))
        edit.setFocus()

    def _backspace(self):
        """Supprime le dernier caractère."""
        edit = self._formula_edit
        cursor_pos = edit.cursorPosition()
        if cursor_pos > 0:
            current = edit.text()
            edit.setText(current[:cursor_pos - 1] + current[cursor_pos:])
            edit.setCursorPosition(cursor_pos - 1)
        edit.setFocus()

    def _on_var_double_clicked(self, item: QTableWidgetItem):
        """Double-clic sur une ligne → insère le nom de la variable."""
        var_name = item.data(Qt.UserRole)
        if var_name:
            self._insert_text(var_name)

    # ── Aperçu en temps réel ──────────────────────────────────────────────────

    def _update_preview(self):
        """Évalue la formule en temps réel et affiche le résultat."""
        expr = self._formula_edit.text().strip()
        if not expr:
            self._preview_label.setText("→  Entrez une formule ci-dessus")
            self._preview_label.setStyleSheet(
                "font-size:12px; color:#90a0b0; font-style:italic;"
                "padding:4px 8px; background:#f5f5f5;"
                "border-radius:4px; border:1px solid #ddd;")
            return

        qty, err = evaluate_formula(expr, self._vars, 1.0)
        if err:
            self._preview_label.setText(f"→  ⚠  {err}")
            self._preview_label.setStyleSheet(
                "font-size:12px; color:#c62828; font-style:italic;"
                "padding:4px 8px; background:#fff5f5;"
                "border-radius:4px; border:1px solid #ef9a9a;")
        else:
            # Construire la ligne de détail : remplacer les noms par leurs valeurs
            detail = expr
            for name in sorted(self._vars.keys(), key=len, reverse=True):
                v = self._vars[name]
                detail = detail.replace(name, f"{v:.2f}")
            self._preview_label.setText(f"→  {detail}  =  <b>{qty:.4g}</b>")
            self._preview_label.setStyleSheet(
                "font-size:12px; color:#1565c0; font-style:italic;"
                "padding:4px 8px; background:#e8f0fe;"
                "border-radius:4px; border:1px solid #90caf9;")

    # ── Accesseur résultat ────────────────────────────────────────────────────

    def formula(self) -> str:
        """Retourne la formule validée."""
        return self._formula_edit.text().strip()
