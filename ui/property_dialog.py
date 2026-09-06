# ui/property_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QColorDialog, QFormLayout, QDialogButtonBox, QTabWidget,
    QComboBox, QListWidget, QGroupBox, QSpinBox, QDoubleSpinBox, QWidget,
    QSlider, QFrame, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QPointF, QPropertyAnimation, QEasingCurve, QRect, QRectF, pyqtProperty
from PyQt5.QtGui import (
    QColor, QPixmap, QIcon, QBrush, QPainter, QPen,
    QPolygonF, QPainterPath, QFont, QLinearGradient, QConicalGradient
)
import math
from core.pattern_brush import make_brush, pattern_to_storage, pattern_from_storage


class MaterialLineEdit(QLineEdit):
    """QLineEdit standard aligné avec le thème Metraplan."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hérite du QSS global — pas de surcharge nécessaire


class ColorSwatchWidget(QWidget):
    """Menu déroulant (QComboBox) de couleurs — thème Metraplan.

    Chaque ligne affiche une pastille colorée + nom.
    Dernière entrée «Autre couleur…» ouvre le sélecteur Qt complet.
    Émet ``colorSelected(QColor)`` lors de chaque sélection.
    """

    colorSelected = __import__('PyQt5.QtCore', fromlist=['pyqtSignal']).pyqtSignal(QColor)

    _PALETTE = [
        ("Bleu ciel",    QColor(100, 181, 246, 180)),
        ("Turquoise",    QColor( 38, 198, 218, 180)),
        ("Vert menthe",  QColor(102, 187, 106, 180)),
        ("Vert olive",   QColor(156, 175, 136, 180)),
        ("Corail",       QColor(255, 138, 128, 180)),
        ("Rose poudré",  QColor(240,  98, 146, 180)),
        ("Lavande",      QColor(179, 157, 219, 180)),
        ("Pêche",        QColor(255, 183,  77, 180)),
        ("Gris ardoise", QColor(120, 144, 156, 180)),
        ("Beige sable",  QColor(215, 204, 200, 180)),
    ]
    _CUSTOM_IDX = len(_PALETTE)  # index de l'entrée «Autre couleur…»

    def __init__(self, initial_color=None, parent=None):
        super().__init__(parent)
        self._current = QColor(initial_color) if initial_color else QColor(100, 181, 246, 180)
        self._build()

    def _make_icon(self, color: QColor) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.transparent)
        from PyQt5.QtGui import QPainter as _P, QPen as _Pen, QBrush as _Brush
        p = _P(pixmap)
        p.setRenderHint(_P.Antialiasing)
        p.setBrush(_Brush(color))
        p.setPen(_Pen(QColor(160, 180, 200), 1))
        p.drawRoundedRect(1, 1, 16, 16, 3, 3)
        p.end()
        return QIcon(pixmap)

    def _build(self):
        from PyQt5.QtWidgets import QHBoxLayout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._combo = QComboBox()
        self._combo.setIconSize(__import__('PyQt5.QtCore', fromlist=['QSize']).QSize(18, 18))

        for name, color in self._PALETTE:
            self._combo.addItem(self._make_icon(color), name, color)

        # Entrée spéciale «Autre couleur…»
        self._combo.addItem("  Autre couleur…", None)

        self._combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self._combo)

        # Sélectionner la couleur initiale
        self.set_color(self._current)

    def _is_custom_trigger(self, index: int) -> bool:
        """Retourne True si l'entrée sélectionnée est «Autre couleur…» (data=None)."""
        return self._combo.itemData(index) is None

    def _on_index_changed(self, index: int):
        if self._is_custom_trigger(index):
            # Revenir à la sélection précédente avant d'ouvrir le dialog
            self._combo.blockSignals(True)
            self._restore_current_index()
            self._combo.blockSignals(False)

            dlg = QColorDialog(self._current, self)
            dlg.setOption(QColorDialog.ShowAlphaChannel, True)
            # Forcer le thème clair pour correspondre à l'interface globale
            dlg.setStyleSheet(
                "QColorDialog, QColorDialog * {"
                "  background-color: #f0f4f8;"
                "  color: #263238;"
                "}"
                "QPushButton {"
                "  background-color: #1976d2; color: white;"
                "  border-radius: 4px; padding: 6px 16px;"
                "  border: none;"
                "}"
                "QPushButton:hover { background-color: #1565c0; }"
                "QPushButton[text='Cancel'], QPushButton[text='Annuler'] {"
                "  background-color: #eceff1; color: #546e7a;"
                "}"
                "QLineEdit, QSpinBox {"
                "  background-color: white; color: #263238;"
                "  border: 1px solid #b0bec5; border-radius: 3px;"
                "  padding: 3px 6px;"
                "}"
            )
            if dlg.exec_():
                color = dlg.currentColor()
            else:
                color = QColorDialog.getColor()  # invalide par défaut
            if color.isValid():
                self._current = color
                self._upsert_custom_entry(color)
                self.colorSelected.emit(color)
        else:
            color = self._combo.itemData(index)
            if color and color.isValid():
                self._current = color
                self.colorSelected.emit(color)

    def _restore_current_index(self):
        """Repositionne le combo sur la couleur courante."""
        for i in range(self._combo.count()):
            c = self._combo.itemData(i)
            if c and c.red() == self._current.red() and c.green() == self._current.green() \
                    and c.blue() == self._current.blue():
                self._combo.setCurrentIndex(i)
                return

    def _upsert_custom_entry(self, color: QColor):
        """Met à jour ou insère l'entrée «Personnalisée» juste avant «Autre couleur…»."""
        self._combo.blockSignals(True)
        # Supprimer une éventuelle entrée «Personnalisée» précédente (data != None, pas dans palette)
        palette_colors = {id(c) for _, c in self._PALETTE}
        for i in range(self._combo.count() - 1, -1, -1):
            c = self._combo.itemData(i)
            if c is not None and id(c) not in palette_colors:
                self._combo.removeItem(i)
                break
        # Trouver l'index de «Autre couleur…» (data = None)
        autre_idx = next(
            (i for i in range(self._combo.count()) if self._combo.itemData(i) is None),
            self._combo.count()
        )
        self._combo.insertItem(autre_idx, self._make_icon(color), "Personnalisée", color)
        self._combo.setCurrentIndex(autre_idx)
        self._combo.blockSignals(False)

    # ── API publique ──────────────────────────────────────────────────────────

    def set_color(self, color):
        """Synchronise la liste déroulante avec la couleur fournie."""
        if isinstance(color, str):
            color = QColor(color)
        if not color or not color.isValid():
            return
        self._current = color
        self._combo.blockSignals(True)
        for i in range(self._CUSTOM_IDX):
            c = self._combo.itemData(i)
            if c and c.red() == color.red() and c.green() == color.green() \
                    and c.blue() == color.blue():
                self._combo.setCurrentIndex(i)
                self._combo.blockSignals(False)
                return
        # Couleur hors palette → entrée personnalisée
        self._upsert_custom_entry(color)
        self._combo.blockSignals(False)

    def current_color(self) -> QColor:
        return self._current


class PropertyDialog(QDialog):
    def __init__(self, parent=None, entity_type="surface", default_name="",
                 default_color=QColor(0, 0, 255), default_show_measure=False,
                 default_pattern=Qt.SolidPattern, default_width=2.0, default_height=0.0,
                 default_shape="circle", default_size=14):
        super().__init__(parent)

        # Titre selon le type
        if entity_type == "perimeter":
            self.setWindowTitle("Nouveau périmètre")
        elif entity_type == "surface":
            self.setWindowTitle("Nouvelle surface")
        elif entity_type == "opening":
            self.setWindowTitle("Nouvelle ouverture")
        elif entity_type == "counter":
            self.setWindowTitle("Nouveau compteur")
        else:
            self.setWindowTitle("Propriétés")

        self.setModal(True)
        self.resize(600, 550)  # ✨ Taille réduite

        self.entity_type = entity_type
        self.name = default_name
        self.color = default_color
        self.show_measure = default_show_measure
        # Normaliser : int/BrushStyle → string canonical (pour le nouveau système)
        self.fill_pattern = pattern_from_storage(default_pattern)
        self.extensions = []
        self.width = default_width
        self.height = default_height
        self.shape = default_shape
        self.size = default_size
        self.save_as_template = False

        # Surcharges minimales — le reste hérite de assets/style/app.qss
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f2f5;
            }
            QTabWidget::pane {
                border: 1px solid #c0cce0;
                border-radius: 6px;
                background-color: #f7f9fc;
            }
            QTabBar::tab {
                background: transparent;
                color: #5a7090;
                padding: 7px 20px;
                border: none;
                border-bottom: 2px solid transparent;
                font-size: 11px;
                font-weight: bold;
            }
            QTabBar::tab:hover { color: #1565c0; background: #e8f0fa; }
            QTabBar::tab:selected {
                color: #1565c0;
                border-bottom: 2px solid #1976d2;
            }
            QListWidget::item:selected {
                background-color: #dce8f8;
                color: #1565c0;
            }
        """)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # En-tête Material
        header = self.create_header()
        layout.addWidget(header)

        self.tabs = QTabWidget()

        # Onglet Propriétés
        self.tab_properties = self.create_properties_tab()
        self.tabs.addTab(self.tab_properties, "Propriétés")

        layout.addWidget(self.tabs)

        # Boutons alignés sur le thème Metraplan
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Annuler")
        cancel_button.setCursor(Qt.PointingHandCursor)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5a7090;
                border: 1px solid #b8c8dc;
                padding: 7px 22px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #dce8f8; color: #1565c0; }
            QPushButton:pressed { background-color: #c8d8f0; }
        """)
        cancel_button.clicked.connect(self.reject)

        ok_button = QPushButton("OK")
        ok_button.setCursor(Qt.PointingHandCursor)
        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 7px 32px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
            QPushButton:pressed { background-color: #0d47a1; }
        """)
        ok_button.clicked.connect(self.accept)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def create_header(self):
        """En-tête aligné sur le thème Metraplan."""
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background-color: #eef2f8; border: 1px solid #c0cce0;"
            " border-radius: 6px; }"
        )
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(2)

        if self.entity_type == "perimeter":
            title_text = "Nouveau périmètre"
            subtitle = "Définissez les propriétés de mesure"
        elif self.entity_type == "surface":
            title_text = "Nouvelle surface"
            subtitle = "Configurez l'apparence et le remplissage"
        elif self.entity_type == "counter":
            title_text = "Nouveau compteur"
            subtitle = "Configurez la forme et la couleur"
        else:
            title_text = "Propriétés"
            subtitle = "Configuration de l'objet"

        title_label = QLabel(title_text)
        title_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1565c0;"
            " background: transparent; border: none;"
        )

        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(
            "font-size: 11px; color: #5a7090; background: transparent; border: none;"
        )

        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        header.setLayout(header_layout)
        return header

    def create_properties_tab(self):
        """Onglet Propriétés Material - Version compacte"""
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(24)

        # Partie gauche
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(20)

        # Carte détails
        details_card = QFrame()
        details_card.setStyleSheet(
            "QFrame { background-color: #eef2f8; border: 1px solid #c0cce0;"
            " border-radius: 6px; }"
        )

        details_layout = QVBoxLayout()
        details_layout.setContentsMargins(20, 20, 20, 20)
        details_layout.setSpacing(20)

        section_label = QLabel("Détails")
        section_label.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #1565c0;"
            " background: transparent; border: none;"
        )
        details_layout.addWidget(section_label)

        name_label = QLabel("Nom")
        name_label.setStyleSheet("font-size: 11px; color: #5a7090; border: none; background: transparent;")
        details_layout.addWidget(name_label)

        self.name_edit = MaterialLineEdit(self.name)
        self.name_edit.textChanged.connect(self.update_preview)
        details_layout.addWidget(self.name_edit)

        color_label = QLabel("Couleur")
        color_label.setStyleSheet("font-size: 11px; color: #5a7090; border: none; background: transparent;")
        details_layout.addWidget(color_label)

        self.color_swatches = ColorSwatchWidget(initial_color=self.color)
        self.color_swatches.colorSelected.connect(self._on_swatch_selected)
        details_layout.addWidget(self.color_swatches)

        # Forme + Taille (compteur)
        if self.entity_type == "counter":
            shape_label = QLabel("Forme")
            shape_label.setStyleSheet("font-size: 11px; color: #5a7090; border: none; background: transparent;")
            details_layout.addWidget(shape_label)

            self.shape_combo = QComboBox()
            shapes = [
                ("Cercle", "circle"),
                ("Carré", "square"),
                ("Triangle", "triangle"),
                ("Triangle inversé", "triangle_inverted"),
                ("Trapèze", "trapezoid"),
                ("Trapèze inversé", "trapezoid_inverted"),
                ("Étoile", "star")
            ]
            for label, value in shapes:
                self.shape_combo.addItem(label, value)

            for i in range(self.shape_combo.count()):
                if self.shape_combo.itemData(i) == self.shape:
                    self.shape_combo.setCurrentIndex(i)
                    break
            self.shape_combo.currentIndexChanged.connect(self.update_preview)
            details_layout.addWidget(self.shape_combo)

            size_label = QLabel("Taille")
            size_label.setStyleSheet("font-size: 11px; color: #5a7090; border: none; background: transparent;")
            details_layout.addWidget(size_label)

            size_layout = QHBoxLayout()
            self.size_value_label = QLabel(str(int(self.size)))
            self.size_value_label.setFixedWidth(35)
            self.size_value_label.setAlignment(Qt.AlignCenter)
            self.size_value_label.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #1565c0;"
                " border: none; background: transparent;"
            )
            size_layout.addWidget(self.size_value_label)

            self.size_slider = QSlider(Qt.Horizontal)
            self.size_slider.setRange(8, 40)
            self.size_slider.setValue(int(self.size))
            self.size_slider.valueChanged.connect(self.update_preview)
            size_layout.addWidget(self.size_slider, 1)

            details_layout.addLayout(size_layout)

        # Motif (surfaces)
        if self.entity_type == "surface":
            pattern_label = QLabel("Motif de remplissage")
            pattern_label.setStyleSheet("font-size: 11px; color: #5a7090; border: none; background: transparent;")
            details_layout.addWidget(pattern_label)

            self.pattern_combo = QComboBox()
            self.populate_pattern_combo()
            # Sélectionner le motif initial
            for i in range(self.pattern_combo.count()):
                if self.pattern_combo.itemData(i) == self.fill_pattern:
                    self.pattern_combo.setCurrentIndex(i)
                    break
            self.pattern_combo.currentIndexChanged.connect(
                self.on_pattern_changed)
            details_layout.addWidget(self.pattern_combo)

        # Épaisseur (périmètres)
        if self.entity_type == "perimeter":
            width_label = QLabel("Épaisseur")
            width_label.setStyleSheet("font-size: 11px; color: #5a7090; border: none; background: transparent;")
            details_layout.addWidget(width_label)

            width_layout = QHBoxLayout()

            self.width_value_label = QLabel(str(int(self.width)))
            self.width_value_label.setFixedWidth(35)
            self.width_value_label.setAlignment(Qt.AlignCenter)
            self.width_value_label.setStyleSheet(
                "font-size: 13px; font-weight: bold; color: #1565c0;"
                " border: none; background: transparent;"
            )
            width_layout.addWidget(self.width_value_label)

            self.width_slider = QSlider(Qt.Horizontal)
            self.width_slider.setRange(1, 20)
            self.width_slider.setValue(int(self.width))
            self.width_slider.valueChanged.connect(self.update_width_value)
            width_layout.addWidget(self.width_slider, 1)

            details_layout.addLayout(width_layout)

            height_label = QLabel("Hauteur (optionnel)")
            height_label.setStyleSheet("font-size: 11px; color: #5a7090; border: none; background: transparent;")
            details_layout.addWidget(height_label)

            self.height_spinbox = QDoubleSpinBox()
            self.height_spinbox.setRange(0.0, 10.0)
            self.height_spinbox.setValue(self.height)
            self.height_spinbox.setSuffix(" m")
            details_layout.addWidget(self.height_spinbox)

        # Afficher mesure
        if self.entity_type != "counter":
            self.show_measure_checkbox = QCheckBox("Afficher la mesure")
            self.show_measure_checkbox.setChecked(self.show_measure)
            self.show_measure_checkbox.setStyleSheet("margin-top: 12px;")
            details_layout.addWidget(self.show_measure_checkbox)

        details_layout.addStretch()
        details_card.setLayout(details_layout)
        left_layout.addWidget(details_card)
        left_widget.setLayout(left_layout)

        main_layout.addWidget(left_widget, 2)

        # Partie droite - Aperçu (plus compact)
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        preview_card = QFrame()
        preview_card.setStyleSheet(
            "QFrame { background-color: #eef2f8; border: 1px solid #c0cce0;"
            " border-radius: 6px; }"
        )

        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(16, 16, 16, 16)

        preview_title = QLabel("Aperçu")
        preview_title.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #1565c0;"
            " background: transparent; border: none;"
        )
        preview_layout.addWidget(preview_title)

        self.preview_label = QLabel()
        self.preview_label.setFixedSize(140, 140)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet(
            "background-color: #f7f9fc; border: 1px solid #d4dce8;"
            " border-radius: 5px;"
        )
        self.update_preview()
        preview_layout.addWidget(self.preview_label)

        self.preview_text_label = QLabel(self.name)
        self.preview_text_label.setAlignment(Qt.AlignCenter)
        self.preview_text_label.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #1e2130;"
            " background: transparent; border: none;"
        )
        preview_layout.addWidget(self.preview_text_label)

        preview_card.setLayout(preview_layout)
        right_layout.addWidget(preview_card)
        right_layout.addStretch()
        right_widget.setLayout(right_layout)

        main_layout.addWidget(right_widget, 1)

        widget.setLayout(main_layout)
        return widget

    def create_extensions_tab(self):
        """Onglet Extensions Material"""
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Extensions disponibles")
        title.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #1565c0;"
            " background: transparent; border: none;"
        )
        layout.addWidget(title)

        subtitle = QLabel("Associez des calculs complémentaires")
        subtitle.setStyleSheet(
            "font-size: 11px; color: #5a7090; background: transparent; border: none;"
        )
        layout.addWidget(subtitle)

        self.extensions_list = QListWidget()
        self.extensions_list.setSelectionMode(QListWidget.MultiSelection)

        extensions_available = [
            "Calcul de volume (avec hauteur)",
            "Surface des murs (périmètre × hauteur)",
            "Surface de plafond",
            "Quantité de matériaux",
            "Coût estimatif",
            "Export vers tableur"
        ]

        for ext in extensions_available:
            self.extensions_list.addItem(ext)

        layout.addWidget(self.extensions_list)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        remove_btn = QPushButton("Retirer")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #5a7090;
                border: 1px solid #b8c8dc;
                padding: 6px 14px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #dce8f8; color: #1565c0; }
        """)
        remove_btn.clicked.connect(self.remove_extension)

        config_btn = QPushButton("Configurer")
        config_btn.setCursor(Qt.PointingHandCursor)
        config_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        config_btn.clicked.connect(self.configure_extension)

        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(config_btn)
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def _on_swatch_selected(self, color: QColor):
        """Mise à jour de la couleur courante depuis la palette."""
        self.color = color
        self.update_preview()

    def populate_pattern_combo(self):
        """Motifs de remplissage — natifs Qt + motifs de construction personnalisés."""
        patterns = [
            ("Solide",              "solid"),
            ("Lignes horizontales", "hlines"),
            ("Lignes verticales",   "vlines"),
            ("Grille",              "grid"),
            ("Diagonales \\",       "diag_back"),
            ("Diagonales /",        "diag_fwd"),
            ("Croisillons",         "cross_diag"),
            ("Brique",              "brick"),
            ("Brique décalée",      "brick_offset"),
            ("Carrelage",           "tile"),
        ]
        for name, key in patterns:
            self.pattern_combo.addItem(name, key)

    def on_pattern_changed(self, index):
        self.fill_pattern = self.pattern_combo.itemData(index) or "solid"
        self.update_preview()

    def update_preview(self):
        """Aperçu Material"""
        pixmap = QPixmap(140, 140)
        pixmap.fill(QColor(250, 250, 250))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.entity_type == "counter":
            color = self.color
            if isinstance(color, str):
                color = QColor(color)
            size = self.size_slider.value() if hasattr(
                self, "size_slider") else self.size
            shape = self.shape_combo.currentData() if hasattr(
                self, "shape_combo") else self.shape

            painter.setPen(QPen(color.darker(130), 2))
            painter.setBrush(QBrush(color))

            center = QPointF(70, 70)
            half = size / 2.0

            def draw_polygon(points):
                painter.drawPolygon(QPolygonF(points))

            if shape == "circle":
                painter.drawEllipse(center, half, half)
            elif shape == "square":
                painter.drawRect(QRectF(center.x() - half,
                                        center.y() - half,
                                        size, size))
            elif shape == "triangle":
                draw_polygon([
                    QPointF(center.x(), center.y() - half),
                    QPointF(center.x() - half, center.y() + half),
                    QPointF(center.x() + half, center.y() + half)
                ])
            elif shape == "triangle_inverted":
                draw_polygon([
                    QPointF(center.x() - half, center.y() - half),
                    QPointF(center.x() + half, center.y() - half),
                    QPointF(center.x(), center.y() + half)
                ])
            elif shape == "trapezoid":
                top = size * 0.6
                draw_polygon([
                    QPointF(center.x() - top / 2, center.y() - half),
                    QPointF(center.x() + top / 2, center.y() - half),
                    QPointF(center.x() + half, center.y() + half),
                    QPointF(center.x() - half, center.y() + half)
                ])
            elif shape == "trapezoid_inverted":
                top = size * 0.6
                draw_polygon([
                    QPointF(center.x() - half, center.y() - half),
                    QPointF(center.x() + half, center.y() - half),
                    QPointF(center.x() + top / 2, center.y() + half),
                    QPointF(center.x() - top / 2, center.y() + half)
                ])
            elif shape == "star":
                points = []
                outer = half
                inner = half * 0.5
                for i in range(10):
                    angle = math.radians(-90 + i * 36)
                    radius = outer if i % 2 == 0 else inner
                    points.append(QPointF(
                        center.x() + math.cos(angle) * radius,
                        center.y() + math.sin(angle) * radius
                    ))
                draw_polygon(points)

            painter.setPen(QPen(Qt.white))
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            painter.drawText(QRectF(0, 0, 140, 140),
                             Qt.AlignCenter, "1")

        elif self.entity_type == "perimeter":
            pen = QPen(self.color)
            if hasattr(self, 'width_slider'):
                pen.setWidth(self.width_slider.value())
            else:
                pen.setWidth(int(self.width))
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)

            points = [
                QPointF(40, 40),
                QPointF(40, 100),
                QPointF(100, 100),
                QPointF(100, 70)
            ]

            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])

            # Points Material
            for point in points:
                painter.setBrush(QBrush(self.color))
                painter.setPen(QPen(self.color.darker(120), 2))
                painter.drawEllipse(point, 5, 5)

        elif self.entity_type == "surface":
            brush = make_brush(self.color, self.fill_pattern)
            painter.setBrush(brush)
            painter.setPen(QPen(self.color.darker(130), 2))

            points = [
                QPointF(40, 40),
                QPointF(40, 100),
                QPointF(100, 100),
                QPointF(100, 40)
            ]
            polygon = QPolygonF(points)
            painter.drawPolygon(polygon)

        painter.end()
        self.preview_label.setPixmap(pixmap)

        if hasattr(self, 'preview_text_label') and hasattr(self, 'name_edit'):
            self.preview_text_label.setText(self.name_edit.text())

        if self.entity_type == "counter" and hasattr(self, "size_value_label") and hasattr(self, "size_slider"):
            self.size_value_label.setText(str(self.size_slider.value()))

    def update_width_value(self):
        value = self.width_slider.value()
        self.width_value_label.setText(str(value))
        self.update_preview()

    def configure_extension(self):
        selected = self.extensions_list.selectedItems()
        if selected:
            pass

    def remove_extension(self):
        selected = self.extensions_list.selectedItems()
        for item in selected:
            item.setSelected(False)

    def get_properties(self):
        props = {
            'name': self.name_edit.text(),
            'color': self.color,
            'show_measure': self.show_measure_checkbox.isChecked() if hasattr(self, 'show_measure_checkbox') else False,
            'save_as_template': False
        }

        if self.entity_type == "surface":
            props['fill_pattern'] = self.fill_pattern
            props['extensions'] = []

        if self.entity_type == "perimeter":
            props['width'] = self.width_slider.value()
            props['height'] = self.height_spinbox.value()

        if self.entity_type == "counter":
            props['shape'] = self.shape_combo.currentData(
            ) if hasattr(self, 'shape_combo') else self.shape
            props['size'] = self.size_slider.value(
            ) if hasattr(self, 'size_slider') else self.size

        return props


# TEST
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    dialog = PropertyDialog(
        entity_type="surface",
        default_name="Surface 4",
        default_color=QColor(244, 67, 54, 180),
        default_width=6.0
    )

    if dialog.exec_() == QDialog.Accepted:
        props = dialog.get_properties()
        for key, value in props.items():
            pass

    sys.exit(app.exec_())
