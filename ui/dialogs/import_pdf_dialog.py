"""
Boîte de dialogue d'importation PDF avec options.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple, Dict

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QSpinBox,
    QRadioButton,
    QButtonGroup,
    QDialogButtonBox,
    QCheckBox,
)


class ImportPDFDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importer un PDF")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        # Fichier
        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        browse_btn = QPushButton("Parcourir…")
        browse_btn.clicked.connect(self._browse_pdf)
        file_row.addWidget(QLabel("Fichier PDF :"))
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # DPI
        dpi_row = QHBoxLayout()
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(150)
        dpi_row.addWidget(QLabel("Résolution (DPI) :"))
        dpi_row.addWidget(self.dpi_spin)
        dpi_row.addStretch()
        layout.addLayout(dpi_row)

        # Mode d'import : noir et blanc ou couleur
        self.grayscale_check = QCheckBox("Importer en noir et blanc")
        self.grayscale_check.setChecked(False)  # Par défaut : couleur
        layout.addWidget(self.grayscale_check)

        # Plage de pages
        range_row = QHBoxLayout()
        self.all_pages_radio = QRadioButton("Toutes les pages")
        self.range_radio = QRadioButton("Plage")
        self.all_pages_radio.setChecked(True)

        self.range_start = QSpinBox()
        self.range_end = QSpinBox()
        self.range_start.setRange(1, 9999)
        self.range_end.setRange(1, 9999)
        self.range_start.setValue(1)
        self.range_end.setValue(1)
        self._toggle_range_inputs(False)

        group = QButtonGroup(self)
        group.addButton(self.all_pages_radio)
        group.addButton(self.range_radio)

        self.all_pages_radio.toggled.connect(
            lambda checked: self._toggle_range_inputs(not checked))

        range_row.addWidget(QLabel("Pages :"))
        range_row.addWidget(self.all_pages_radio)
        range_row.addWidget(self.range_radio)
        range_row.addWidget(QLabel("de"))
        range_row.addWidget(self.range_start)
        range_row.addWidget(QLabel("à"))
        range_row.addWidget(self.range_end)
        range_row.addStretch()
        layout.addLayout(range_row)

        # Boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _toggle_range_inputs(self, enabled: bool):
        self.range_start.setEnabled(enabled)
        self.range_end.setEnabled(enabled)

    def _browse_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un PDF", "", "PDF (*.pdf)")
        if file_path:
            self.file_edit.setText(file_path)

    def _validate_and_accept(self):
        file_path = self.file_edit.text().strip()
        if not file_path or not os.path.isfile(file_path):
            return
        if not file_path.lower().endswith(".pdf"):
            return
        self.accept()

    def get_selection(self) -> Optional[Tuple[str, Dict]]:
        if self.result() != QDialog.Accepted:
            return None
        file_path = self.file_edit.text().strip()
        dpi = int(self.dpi_spin.value())

        page_range = None
        if self.range_radio.isChecked():
            start = int(self.range_start.value())
            end = int(self.range_end.value())
            if end < start:
                start, end = end, start
            # Conversion 1-based -> 0-based
            page_range = (start - 1, end - 1)

        grayscale = self.grayscale_check.isChecked()
        options = {"dpi": dpi, "page_range": page_range, "grayscale": grayscale}
        return file_path, options
