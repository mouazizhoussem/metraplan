# ui/page_tab_bar.py
"""
Barre d'onglets représentant les pages ouvertes du projet Métraplan.
Chaque onglet correspond à une PDFPage de self._all_pages dans MainWindow.

Signaux exposés
---------------
page_changed(int)       → l'utilisateur a sélectionné un onglet
page_closed(int)        → l'utilisateur a cliqué sur la croix d'un onglet
page_add_requested()    → l'utilisateur a cliqué sur le bouton "+"
page_renamed(int, str)  → l'utilisateur a renommé un onglet (double-clic)
page_moved(int, int)    → l'utilisateur a réordonné un onglet (drag&drop)
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QTabBar, QToolButton, QInputDialog,
)

# Style CSS du bouton "×" de fermeture d'onglet
_CLOSE_BTN_CSS = """
    QToolButton {
        color: #c62828;
        font-size: 13px;
        font-weight: bold;
        background: transparent;
        border: none;
        border-radius: 3px;
        padding: 0px;
        margin: 1px;
    }
    QToolButton:hover {
        background: #ffcdd2;
        color: #b71c1c;
    }
    QToolButton:pressed {
        background: #ef9a9a;
    }
"""


class PageTabBar(QWidget):
    """Barre d'onglets synchronisée avec la liste _all_pages de MainWindow."""

    page_changed       = pyqtSignal(int)
    page_closed        = pyqtSignal(int)
    page_add_requested = pyqtSignal()
    page_renamed       = pyqtSignal(int, str)
    page_moved         = pyqtSignal(int, int)   # (from_index, to_index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False   # garde contre les boucles de signaux

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 0)
        layout.setSpacing(0)

        # ── QTabBar ────────────────────────────────────────────────────────
        self._tab_bar = QTabBar()
        self._tab_bar.setTabsClosable(False)    # boutons de fermeture gérés manuellement
        self._tab_bar.setMovable(True)           # drag & drop réordonnement
        self._tab_bar.setExpanding(False)        # taille minimale par onglet
        self._tab_bar.setDocumentMode(True)      # style navigateur
        self._tab_bar.setElideMode(Qt.ElideRight)
        self._tab_bar.setUsesScrollButtons(True)

        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabMoved.connect(self._on_tab_moved)
        self._tab_bar.tabBarDoubleClicked.connect(self._on_tab_double_clicked)

        # ── Bouton "+" ─────────────────────────────────────────────────────
        self._btn_add = QToolButton()
        self._btn_add.setText("+")
        self._btn_add.setFixedSize(QSize(28, 28))
        self._btn_add.setToolTip("Ouvrir une page")
        f = QFont("Segoe UI", 15, QFont.Bold)
        self._btn_add.setFont(f)
        self._btn_add.setObjectName("btn_add")
        self._btn_add.clicked.connect(self.page_add_requested)

        layout.addWidget(self._tab_bar, 1)
        layout.addWidget(self._btn_add, 0, Qt.AlignVCenter)

        self.setFixedHeight(32)
        self._apply_style()

    # ── Style ──────────────────────────────────────────────────────────────

    def _apply_style(self):
        self.setStyleSheet("""
            PageTabBar {
                background: #ecf0f5;
                border-bottom: 1px solid #b0bec5;
            }
            QTabBar {
                background: transparent;
            }
            QTabBar::tab {
                background: #dce6f0;
                border: 1px solid #b0bec5;
                border-bottom: none;
                border-radius: 4px 4px 0 0;
                padding: 3px 14px 3px 10px;
                min-width: 80px;
                max-width: 200px;
                color: #37474f;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1565c0;
                font-weight: bold;
                border-bottom: 2px solid #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #e3eaf5;
            }
            /* Bouton "+" : foncé et gras */
            QToolButton#btn_add {
                background: #455a64;
                border: 1px solid #37474f;
                color: #ffffff;
                font-weight: bold;
                margin-left: 6px;
                border-radius: 4px;
            }
            QToolButton#btn_add:hover {
                background: #1565c0;
                border-color: #0d47a1;
            }
            QToolButton#btn_add:pressed {
                background: #0d47a1;
            }
        """)

    # ── API publique ───────────────────────────────────────────────────────

    def _make_close_btn(self) -> QToolButton:
        """Crée un bouton '×' rouge pour fermer un onglet."""
        btn = QToolButton()
        btn.setText("✕")
        btn.setFixedSize(QSize(16, 16))
        btn.setStyleSheet(_CLOSE_BTN_CSS)
        btn.setToolTip("Fermer cet onglet")

        def _on_click():
            # Retrouver dynamiquement l'indice de l'onglet contenant ce bouton
            for j in range(self._tab_bar.count()):
                if self._tab_bar.tabButton(j, QTabBar.RightSide) is btn:
                    self.page_closed.emit(j)
                    return

        btn.clicked.connect(_on_click)
        return btn

    def populate(self, pages: list, current_index: int):
        """
        Reconstruit entièrement la barre depuis la liste des pages.
        Appelé chaque fois que _all_pages change (import, load, delete…).
        """
        self._updating = True
        try:
            while self._tab_bar.count():
                self._tab_bar.removeTab(0)
            for i, page in enumerate(pages):
                label = getattr(page, 'name', None) or f"Page {i + 1}"
                self._tab_bar.addTab(label)
                # Installer le bouton × rouge sur chaque onglet
                self._tab_bar.setTabButton(i, QTabBar.RightSide,
                                           self._make_close_btn())
            safe_idx = max(0, min(current_index, self._tab_bar.count() - 1))
            if self._tab_bar.count() > 0:
                self._tab_bar.setCurrentIndex(safe_idx)
        finally:
            self._updating = False

    def set_current(self, index: int):
        """Sélectionne un onglet sans déclencher le signal page_changed."""
        self._updating = True
        try:
            if 0 <= index < self._tab_bar.count():
                self._tab_bar.setCurrentIndex(index)
        finally:
            self._updating = False

    def rename_tab(self, index: int, name: str):
        """Renomme un onglet depuis l'extérieur."""
        if 0 <= index < self._tab_bar.count():
            self._tab_bar.setTabText(index, name)

    def current_index(self) -> int:
        return self._tab_bar.currentIndex()

    def tab_count(self) -> int:
        return self._tab_bar.count()

    # ── Slots internes ─────────────────────────────────────────────────────

    def _on_tab_changed(self, index: int):
        if not self._updating and index >= 0:
            self.page_changed.emit(index)

    def _on_tab_moved(self, from_idx: int, to_idx: int):
        """Réordonnement par drag & drop."""
        if not self._updating:
            self.page_moved.emit(from_idx, to_idx)

    def _on_tab_double_clicked(self, index: int):
        """Renommage interactif par double-clic sur l'onglet."""
        if index < 0:
            return
        current_name = self._tab_bar.tabText(index)
        new_name, ok = QInputDialog.getText(
            self, "Renommer la page", "Nouveau nom :", text=current_name
        )
        if ok and new_name.strip():
            self._tab_bar.setTabText(index, new_name.strip())
            self.page_renamed.emit(index, new_name.strip())
