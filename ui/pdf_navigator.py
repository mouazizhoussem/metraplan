"""
Widget de navigation des pages PDF.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
)

from models.pdf_document import PDFPage


class PDFNavigator(QWidget):
    page_selected = pyqtSignal(int)
    rename_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    duplicate_requested = pyqtSignal(int, bool)  # index, include_measures

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: List[Optional[PDFPage]] = []
        self._current_index = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        header = QHBoxLayout()
        self.prev_button = QPushButton("◀")
        self.next_button = QPushButton("▶")
        self.page_label = QLabel("Page 0 / 0")
        self.page_label.setAlignment(Qt.AlignCenter)

        header.addWidget(self.prev_button)
        header.addWidget(self.page_label, 1)
        header.addWidget(self.next_button)

        self.list_widget = QListWidget()
        
        # Configuration pour miniatures agrandies avec texte en dessous
        self.list_widget.setViewMode(QListWidget.IconMode)  # Mode icône avec texte en dessous
        self.list_widget.setIconSize(QSize(200, 150))  # Taille des miniatures (largeur x hauteur)
        self.list_widget.setResizeMode(QListWidget.Adjust)  # Ajustement automatique
        self.list_widget.setSpacing(10)  # Espacement entre les miniatures
        self.list_widget.setWordWrap(True)  # Retour à la ligne pour les noms longs
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(
            self._show_context_menu)

        layout.addLayout(header)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

        self.prev_button.clicked.connect(self._go_prev)
        self.next_button.clicked.connect(self._go_next)
        self.list_widget.currentItemChanged.connect(
            self._on_item_changed)

    def set_pages(self, pages: List[Optional[PDFPage]]):
        self._pages = pages or []
        self.list_widget.clear()
        for idx, page in enumerate(self._pages):
            name = page.name if page and page.name else f"Page {idx + 1}"
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, idx)
            if page and page.thumbnail:
                item.setIcon(QIcon(page.thumbnail))
            self.list_widget.addItem(item)
        self._update_label()

    def update_page_thumbnail(self, index: int, thumbnail):
        if index < 0 or index >= self.list_widget.count():
            return
        item = self.list_widget.item(index)
        if item and thumbnail:
            item.setIcon(QIcon(thumbnail))

    def set_current_page(self, index: int):
        if 0 <= index < self.list_widget.count():
            self.list_widget.setCurrentRow(index)

    def _on_item_changed(self, current: QListWidgetItem, _previous):
        if not current:
            return
        index = current.data(Qt.UserRole)
        if index is None:
            return
        self._current_index = index
        self._update_label()
        self.page_selected.emit(index)

    def _go_prev(self):
        if self._current_index > 0:
            self.set_current_page(self._current_index - 1)

    def _go_next(self):
        if self._current_index < self.list_widget.count() - 1:
            self.set_current_page(self._current_index + 1)

    def _update_label(self):
        total = self.list_widget.count()
        if total == 0:
            self.page_label.setText("Page 0 / 0")
            return
        self.page_label.setText(
            f"Page {self._current_index + 1} / {total}")

    def update_page_name(self, index: int, name: str):
        if 0 <= index < self.list_widget.count():
            item = self.list_widget.item(index)
            if item:
                item.setText(name)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        index = item.data(Qt.UserRole)
        if index is None:
            return

        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        rename_action = menu.addAction("Renommer")
        duplicate_with = menu.addAction("Dupliquer (avec mesures)")
        duplicate_without = menu.addAction("Dupliquer (sans mesures)")
        delete_action = menu.addAction("Supprimer")

        action = menu.exec_(self.list_widget.mapToGlobal(pos))
        if action == rename_action:
            self.rename_requested.emit(index)
        elif action == duplicate_with:
            self.duplicate_requested.emit(index, True)
        elif action == duplicate_without:
            self.duplicate_requested.emit(index, False)
        elif action == delete_action:
            self.delete_requested.emit(index)
