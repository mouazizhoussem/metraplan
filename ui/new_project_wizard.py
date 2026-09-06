# ui/new_project_wizard.py
"""
Assistant de création de nouveau projet Métraplan — 2 étapes :
  Étape 1 : Détails du projet et du contact
  Étape 2 : Choix du plan (PDF / Image / Sans plan)
"""
from datetime import date

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QWidget,
    QStackedWidget, QFileDialog, QButtonGroup,
    QRadioButton, QFrame, QSizePolicy, QDateEdit,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor, QPalette


# ── Palette / style ───────────────────────────────────────────────────────────
_QSS = """
QDialog { background: #f4f6fa; }
QLabel#stepTitle {
    font-size: 15px; font-weight: bold; color: #1976d2;
}
QLabel#stepSub {
    font-size: 11px; color: #6080a0;
}
QLabel#fieldLabel { font-size: 11px; color: #2a3a5a; }
QLabel#required   { font-size: 11px; color: #e53935; font-weight: bold; }
QLineEdit {
    border: 1px solid #c0cce0; border-radius: 4px;
    padding: 5px 8px; font-size: 11px; background: white;
    min-height: 24px;
}
QLineEdit:focus  { border: 1px solid #1976d2; }
QLineEdit[readOnly="true"] { background: #f0f4fa; color: #7090b0; }
QDateEdit {
    border: 1px solid #c0cce0; border-radius: 4px;
    padding: 4px 8px; font-size: 11px; background: white;
}
QPushButton#browse {
    border: 1px solid #90b0d8; border-radius: 4px;
    background: #dce8f8; padding: 5px 12px;
    font-size: 11px; color: #1a3060; min-width: 90px;
}
QPushButton#browse:hover { background: #1976d2; color: white; }
QPushButton#navBtn {
    border: 1px solid #c0cce0; border-radius: 5px;
    background: #e8ecf4; padding: 6px 20px;
    font-size: 11px; color: #2a3a5a; min-width: 90px;
}
QPushButton#navBtn:hover { background: #d0dce8; }
QPushButton#primaryBtn {
    border: none; border-radius: 5px;
    background: #1976d2; padding: 6px 24px;
    font-size: 11px; color: white; font-weight: bold;
    min-width: 110px;
}
QPushButton#primaryBtn:hover { background: #1565c0; }
QPushButton#primaryBtn:disabled { background: #b0c4d8; color: #e0e8f0; }
QFrame#card {
    background: white; border: 2px solid #d0dce8;
    border-radius: 8px; padding: 4px;
}
QFrame#card:hover { border-color: #1976d2; background: #f0f6ff; }
QRadioButton { font-size: 12px; color: #1a2a4a; spacing: 10px; }
QRadioButton::indicator { width: 16px; height: 16px; }
QRadioButton::indicator:checked {
    background: #1976d2; border: 2px solid #1976d2; border-radius: 8px;
}
QRadioButton::indicator:unchecked {
    background: white; border: 2px solid #b0c0d8; border-radius: 8px;
}
"""

_HEADER_QSS = """
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #1976d2, stop:1 #42a5f5);
    border-radius: 0px;
"""


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("background: #d8e4f0; margin: 4px 0;")
    f.setFixedHeight(1)
    return f


def _lbl(text, obj_name="fieldLabel") -> QLabel:
    l = QLabel(text)
    l.setObjectName(obj_name)
    return l


# ── Page 1 : Détails du projet ────────────────────────────────────────────────

class _PageDetails(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(6)
        v.setContentsMargins(28, 16, 28, 10)

        # Sous-titre
        sub = _lbl(
            "Renseignez les informations du projet. "
            "Seul le nom du projet est obligatoire.", "stepSub")
        sub.setWordWrap(True)
        v.addWidget(sub)
        v.addWidget(_sep())
        v.addSpacing(4)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(14)

        def _field(placeholder="", readonly=False):
            e = QLineEdit()
            e.setPlaceholderText(placeholder)
            e.setReadOnly(readonly)
            return e

        # Nom du projet (obligatoire)
        name_row = QHBoxLayout()
        self.project_name = _field("Ex : Résidence Les Pins")
        req = _lbl(" *", "required")
        req.setToolTip("Champ obligatoire")
        name_row.addWidget(self.project_name)
        name_row.addWidget(req)
        form.addRow(_lbl("Nom du projet :"), name_row)

        # Numéro de projet
        self.project_number = _field("Ex : 2024-001")
        form.addRow(_lbl("Numéro du projet :"), self.project_number)

        # Date de création (auto)
        self.created_date = QDateEdit()
        self.created_date.setCalendarPopup(True)
        self.created_date.setDate(QDate.currentDate())
        self.created_date.setDisplayFormat("dd/MM/yyyy")
        form.addRow(_lbl("Date de création :"), self.created_date)

        v.addLayout(form)
        v.addWidget(_sep())

        form2 = QFormLayout()
        form2.setSpacing(8)
        form2.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form2.setHorizontalSpacing(14)

        self.owner      = _field("Nom du maître d'ouvrage")
        self.architect  = _field("Nom du maître d'œuvre / architecte")
        self.company    = _field("Nom de l'entreprise")
        form2.addRow(_lbl("Maître d'ouvrage :"), self.owner)
        form2.addRow(_lbl("Maître d'œuvre :"),   self.architect)
        form2.addRow(_lbl("Entreprise :"),         self.company)

        v.addLayout(form2)
        v.addWidget(_sep())

        # Répertoire
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self.directory = _field("Choisir un répertoire…")
        self.directory.setReadOnly(True)
        self.btn_browse = QPushButton("Parcourir…")
        self.btn_browse.setObjectName("browse")
        self.btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.directory)
        dir_row.addWidget(self.btn_browse)

        form3 = QFormLayout()
        form3.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form3.setHorizontalSpacing(14)
        form3.addRow(_lbl("Répertoire :"), dir_row)
        v.addLayout(form3)

        v.addStretch()

        # Message d'erreur
        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(
            "color: #e53935; font-size: 11px; padding: 2px 0;")
        v.addWidget(self.error_lbl)

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Choisir le répertoire du projet")
        if path:
            self.directory.setText(path)

    def validate(self) -> bool:
        if not self.project_name.text().strip():
            self.error_lbl.setText("⚠  Le nom du projet est obligatoire.")
            self.project_name.setFocus()
            self.project_name.setStyleSheet(
                "border: 1px solid #e53935; border-radius: 4px; "
                "padding: 5px 8px; background: #fff5f5;")
            return False
        self.error_lbl.setText("")
        self.project_name.setStyleSheet("")
        return True

    def get_data(self) -> dict:
        return {
            "project_name":   self.project_name.text().strip(),
            "project_number": self.project_number.text().strip(),
            "created_date":   self.created_date.date().toString("dd/MM/yyyy"),
            "owner":          self.owner.text().strip(),
            "architect":      self.architect.text().strip(),
            "company":        self.company.text().strip(),
            "directory":      self.directory.text().strip(),
        }


# ── Page 2 : Choix du plan ────────────────────────────────────────────────────

class _PlanCard(QFrame):
    """Carte cliquable pour une option de plan."""
    def __init__(self, icon_char: str, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(80)
        self.setCursor(Qt.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(14)

        # Icône
        ico = QLabel(icon_char)
        ico.setFont(QFont("Segoe UI", 26))
        ico.setFixedWidth(40)
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("color: #1976d2; background: transparent;")
        h.addWidget(ico)

        # Texte
        tv = QVBoxLayout()
        tv.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #1a2a4a; background: transparent;")
        d = QLabel(desc)
        d.setStyleSheet("font-size: 10px; color: #6080a0; background: transparent;")
        tv.addWidget(t)
        tv.addWidget(d)
        h.addLayout(tv)

        self.radio = QRadioButton()
        self.radio.setStyleSheet("background: transparent;")
        h.addWidget(self.radio, alignment=Qt.AlignRight | Qt.AlignVCenter)

    def mousePressEvent(self, e):
        self.radio.setChecked(True)
        super().mousePressEvent(e)


class _PagePlan(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(12)
        v.setContentsMargins(28, 16, 28, 10)

        sub = _lbl(
            "Choisissez comment démarrer votre projet.", "stepSub")
        sub.setWordWrap(True)
        v.addWidget(sub)
        v.addWidget(_sep())

        # Groupe de boutons radio
        self._group = QButtonGroup(self)

        self.card_pdf   = _PlanCard("📄", "Importer depuis un PDF",
                                    "Charger un fichier PDF multi-pages comme plan de base.")
        self.card_image = _PlanCard("🖼", "Charger une image",
                                    "Ouvrir un fichier image (JPG, PNG, TIFF…) comme plan.")
        self.card_none  = _PlanCard("📋", "Créer sans plan",
                                    "Démarrer un projet vide et importer un plan plus tard.")

        self._group.addButton(self.card_pdf.radio,   0)
        self._group.addButton(self.card_image.radio, 1)
        self._group.addButton(self.card_none.radio,  2)
        self.card_none.radio.setChecked(True)   # défaut

        # Style sélection
        for card in [self.card_pdf, self.card_image, self.card_none]:
            card.radio.toggled.connect(lambda checked, c=card: self._on_toggle(c, checked))

        v.addWidget(self.card_pdf)
        v.addWidget(self.card_image)
        v.addWidget(self.card_none)
        v.addStretch()

    def _on_toggle(self, card: _PlanCard, checked: bool):
        if checked:
            card.setStyleSheet(
                "QFrame#card { background: #e8f0ff; border: 2px solid #1976d2; "
                "border-radius: 8px; }")
        else:
            card.setStyleSheet("")

    def get_choice(self) -> str:
        idx = self._group.checkedId()
        return {0: "pdf", 1: "image", 2: "none"}.get(idx, "none")


# ── Wizard principal ──────────────────────────────────────────────────────────

class NewProjectWizard(QDialog):
    """
    Retourne via exec_() :
      QDialog.Accepted → get_result() pour les données
      QDialog.Rejected → annulé
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau projet — Métraplan")
        self.setMinimumWidth(520)
        self.setMinimumHeight(500)
        self.setStyleSheet(_QSS)
        self._result = None
        self._build()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build(self):
        main = QVBoxLayout(self)
        main.setSpacing(0)
        main.setContentsMargins(0, 0, 0, 0)

        # En-tête
        self._header = QLabel()
        self._header.setFixedHeight(52)
        self._header.setStyleSheet(_HEADER_QSS)
        self._header.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._header.setStyleSheet(
            _HEADER_QSS + "color: white; padding-left: 20px;")
        main.addWidget(self._header)

        # Indicateur d'étapes
        step_bar = QWidget()
        step_bar.setFixedHeight(32)
        step_bar.setStyleSheet("background: #dde8f8;")
        sh = QHBoxLayout(step_bar)
        sh.setContentsMargins(20, 0, 20, 0)
        sh.setSpacing(0)
        self._step_labels = []
        for i, txt in enumerate(["1  Détails du projet", "2  Chargement du plan"]):
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignCenter)
            self._step_labels.append(lbl)
            sh.addWidget(lbl)
            if i == 0:
                sep2 = QLabel("›")
                sep2.setAlignment(Qt.AlignCenter)
                sep2.setStyleSheet("color: #90b0d0; font-size: 14px;")
                sh.addWidget(sep2)
        main.addWidget(step_bar)

        # Pages
        self._stack = QStackedWidget()
        self._page1 = _PageDetails()
        self._page2 = _PagePlan()
        self._stack.addWidget(self._page1)
        self._stack.addWidget(self._page2)
        main.addWidget(self._stack, 1)

        # Barre de navigation
        nav = QFrame()
        nav.setStyleSheet(
            "background: #eef2f8; border-top: 1px solid #d0dce8;")
        nav.setFixedHeight(54)
        nh = QHBoxLayout(nav)
        nh.setContentsMargins(20, 8, 20, 8)
        nh.setSpacing(10)

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setObjectName("navBtn")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_back = QPushButton("‹ Précédent")
        self.btn_back.setObjectName("navBtn")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._go_back)

        self.btn_next = QPushButton("Suivant ›")
        self.btn_next.setObjectName("primaryBtn")
        self.btn_next.setStyleSheet(
            "QPushButton { background: #1976d2; color: white; font-weight: bold;"
            " border: none; border-radius: 5px; padding: 6px 24px;"
            " font-size: 11px; min-width: 110px; }"
            "QPushButton:hover { background: #1565c0; }"
            "QPushButton:disabled { background: #b0c4d8; color: #e0e8f0; }"
        )
        self.btn_next.clicked.connect(self._go_next)

        nh.addWidget(self.btn_cancel)
        nh.addStretch()
        nh.addWidget(self.btn_back)
        nh.addWidget(self.btn_next)
        main.addWidget(nav)

        self._update_page(0)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _update_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        titles = ["Détails du projet et du contact",
                  "Charger un plan de travail"]
        self._header.setText(f"  {titles[idx]}")
        self.btn_back.setEnabled(idx > 0)
        if idx == 0:
            self.btn_next.setText("Suivant ›")
        else:
            self.btn_next.setText("✔  Créer le projet")
        for i, lbl in enumerate(self._step_labels):
            if i == idx:
                lbl.setStyleSheet(
                    "font-weight: bold; color: #1976d2; font-size: 11px;")
            else:
                lbl.setStyleSheet("color: #90a0b8; font-size: 11px;")

    def _go_back(self):
        self._update_page(0)

    def _go_next(self):
        if self._stack.currentIndex() == 0:
            if not self._page1.validate():
                return
            self._update_page(1)
        else:
            self._finish()

    def _finish(self):
        data = self._page1.get_data()
        data["plan_source"] = self._page2.get_choice()
        self._result = data
        self.accept()

    # ── Résultat ──────────────────────────────────────────────────────────────

    def get_result(self) -> dict:
        """Retourne les données saisies (après accept())."""
        return self._result or {}
