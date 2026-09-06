# ui/property_panel.py
from PyQt5.QtWidgets import (QDockWidget, QVBoxLayout, QWidget, QLabel,
                             QComboBox, QGroupBox, QFormLayout, QLineEdit,
                             QPushButton, QCheckBox, QScrollArea, QFrame,
                             QColorDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                             QSlider, QHBoxLayout, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QColor, QPixmap
from ui.property_dialog import ColorSwatchWidget
from core.pattern_brush import make_brush, pattern_to_storage, pattern_from_storage


class PropertyPanel(QDockWidget):
    """Volet des propriétés pour afficher et modifier les propriétés des entités"""

    # Signaux pour communiquer avec la fenêtre principale
    colorChanged = pyqtSignal(object, QColor)  # entity, color
    nameChanged = pyqtSignal(object, str)      # entity, name
    visibilityChanged = pyqtSignal(object, bool)  # entity, visible
    widthChanged = pyqtSignal(object, int)  # entity, width
    patternChanged = pyqtSignal(object, object)  # entity, pattern_key

    def __init__(self, parent=None):
        super().__init__("Propriétés", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Référence à la fenêtre principale
        self.main_window = parent

        # Widget principal
        self.main_widget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setSpacing(4)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.main_widget.setLayout(self.layout)

        # NOUVEAU: Label pour l'info rapide (survol)
        self.info_rapide_label = QLabel()
        self.info_rapide_label.setStyleSheet("""
            QLabel {
                background-color: #FFFFCC;
                border: 1px solid #FFAA00;
                padding: 4px 6px;
                border-radius: 5px;
                color: #333333;
                font-weight: bold;
                margin: 2px;
            }
        """)
        self.info_rapide_label.setAlignment(Qt.AlignCenter)
        self.info_rapide_label.setWordWrap(True)
        self.info_rapide_label.hide()  # Caché au départ
        self.layout.addWidget(self.info_rapide_label)

        # NOUVEAU: Label pour indiquer la sélection
        self.selection_label = QLabel("Aucun élément sélectionné")
        self.selection_label.setStyleSheet("""
            QLabel {
                background-color: #E6F3FF;
                border: 1px solid #0078D7;
                padding: 4px 6px;
                border-radius: 5px;
                color: #003366;
                font-weight: bold;
                margin: 2px;
            }
        """)
        self.selection_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.selection_label)

        # ComboBox pour sélectionner l'entité
        self.entity_combo = QComboBox()
        self.entity_combo.currentIndexChanged.connect(self.on_entity_selected)
        self.layout.addWidget(QLabel("Navigation manuelle:"))
        self.layout.addWidget(self.entity_combo)

        # ------------------------------------------------------------------
        # Section Propriétés
        # ------------------------------------------------------------------
        self.properties_group = QGroupBox("Propriétés")
        self.properties_group.setStyleSheet(
            "QGroupBox { font-weight: bold; margin-top: 14px; }"
            "QGroupBox::title { subcontrol-origin: margin; top: -2px; left: 8px; padding: 0 4px; }"
        )
        self.properties_layout = QFormLayout()
        self.properties_layout.setVerticalSpacing(4)
        self.properties_layout.setContentsMargins(6, 8, 6, 4)
        self.properties_group.setLayout(self.properties_layout)

        # Nom de l'objet
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nom de l'objet")
        self.name_edit.textChanged.connect(self.on_name_changed)
        self.properties_layout.addRow("Nom de l'objet :", self.name_edit)

        # Couleur de l'objet — palette de pastilles cliquables
        self._color_data = QColor(100, 181, 246, 180)
        self.color_swatches = ColorSwatchWidget(initial_color=self._color_data)
        self.color_swatches.colorSelected.connect(self._on_swatch_color_selected)
        self.properties_layout.addRow("Couleur :", self.color_swatches)

        # Motif de remplissage (surfaces uniquement) — caché par défaut
        self.pattern_label = QLabel("Motif :")
        self.pattern_combo = QComboBox()
        _patterns = [
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
        for _name, _key in _patterns:
            self.pattern_combo.addItem(_name, _key)
        self.pattern_combo.currentIndexChanged.connect(self._on_pattern_changed)
        self.properties_layout.addRow(self.pattern_label, self.pattern_combo)
        self.pattern_label.hide()
        self.pattern_combo.hide()

        # Opacité
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(70)
        self.opacity_slider.setFixedWidth(140)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        self.opacity_value_label = QLabel("70 %")
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity_slider)
        opacity_row.addWidget(self.opacity_value_label)
        self.properties_layout.addRow("Opacité :", opacity_row)

        # Taille compteur (groupe) - cachée par défaut
        self.counter_size_label = QLabel("Taille (groupe) :")
        self.counter_size_slider = QSlider(Qt.Horizontal)
        self.counter_size_slider.setRange(8, 40)
        self.counter_size_slider.setValue(14)
        self.counter_size_slider.setFixedWidth(140)
        self.counter_size_value_label = QLabel("14")
        counter_size_row = QHBoxLayout()
        counter_size_row.addWidget(self.counter_size_slider)
        counter_size_row.addWidget(self.counter_size_value_label)
        self.counter_size_container = QWidget()
        self.counter_size_container.setLayout(counter_size_row)
        self.properties_layout.addRow(
            self.counter_size_label, self.counter_size_container)
        self.counter_size_slider.valueChanged.connect(
            lambda v: self.on_point_size_changed(v, self.counter_size_value_label))
        self.counter_size_label.hide()
        self.counter_size_container.hide()

        # Forme compteur (groupe) - cachée par défaut
        self.counter_shape_label = QLabel("Forme (groupe) :")
        self.counter_shape_combo = QComboBox()
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
            self.counter_shape_combo.addItem(label, value)
        self.counter_shape_combo.currentIndexChanged.connect(
            lambda: self.on_point_shape_changed(self.counter_shape_combo.currentData()))
        self.properties_layout.addRow(
            self.counter_shape_label, self.counter_shape_combo)
        self.counter_shape_label.hide()
        self.counter_shape_combo.hide()

        # Épaisseur ligne (slider seul, sans valeur affichée)
        self.thickness_slider = QSlider(Qt.Horizontal)
        self.thickness_slider.setRange(5, 30)
        self.thickness_slider.setValue(8)
        self.thickness_slider.setFixedWidth(140)
        self.thickness_slider.valueChanged.connect(self.on_thickness_changed)
        self.thickness_label = QLabel("Épaisseur ligne :")
        self.properties_layout.addRow(self.thickness_label, self.thickness_slider)

        # Afficher mesure / texte
        self.show_measure_checkbox = QCheckBox("Afficher la mesure")
        self.show_measure_checkbox.stateChanged.connect(
            self.on_text_visibility_changed)
        self.properties_layout.addRow(self.show_measure_checkbox)


        # ------------------------------------------------------------------
        # Section Résultats
        # ------------------------------------------------------------------
        self.results_group = QGroupBox("Résultats")
        self.results_group.setStyleSheet(
            "QGroupBox { font-weight: bold; margin-top: 14px; }"
            "QGroupBox::title { subcontrol-origin: margin; top: -2px; left: 8px; padding: 0 4px; }"
        )
        self.results_layout = QFormLayout()
        self.results_layout.setVerticalSpacing(4)
        self.results_layout.setContentsMargins(6, 8, 6, 4)
        self.results_group.setLayout(self.results_layout)

        def make_label():
            lbl = QLabel("-")
            lbl.setStyleSheet("font-weight: normal; color: #222;")
            return lbl

        self.result_count = make_label()
        self.result_counter_number = make_label()
        self.result_counter_group_count = make_label()
        self.result_surface_brute = make_label()
        self.result_deduction = make_label()
        self.result_surface_nette = make_label()
        self.result_surface_group = make_label()
        self.result_volume = make_label()
        self.result_perimetre = make_label()
        self.result_perimetre_deduction = make_label()
        self.result_nb_deductions = make_label()

        # ── Champs spécifiques périmètre ──
        self.result_perim_brut      = make_label()
        self.result_perim_ded_lin   = make_label()
        self.result_perim_net       = make_label()
        self.result_perim_surf_brut = make_label()
        self.result_perim_surf_ded  = make_label()
        self.result_perim_surf_net  = make_label()
        self.result_perim_grp_total = make_label()

        # ── Champs spécifiques compteur ──
        self.result_point_unit_val  = make_label()   # valeur unitaire (m, m², m³)
        self.result_point_grp_total = make_label()   # total groupe

        self.results_layout.addRow("Nombre d'objets :", self.result_count)
        self.results_layout.addRow("Numéro :", self.result_counter_number)
        self.results_layout.addRow("Nb compteur :", self.result_counter_group_count)
        self.results_layout.addRow("Surface brute :", self.result_surface_brute)
        self.results_layout.addRow("Déduction :", self.result_deduction)
        self.results_layout.addRow("Surface nette :", self.result_surface_nette)
        self.results_layout.addRow("Total groupe :", self.result_surface_group)
        self.results_layout.addRow("Volume :", self.result_volume)
        self.results_layout.addRow("Périmètre :", self.result_perimetre)
        self.results_layout.addRow("Périmètre des ouvertures :", self.result_perimetre_deduction)
        self.results_layout.addRow("Nombre de déductions :", self.result_nb_deductions)
        # Périmètre détaillé
        self.results_layout.addRow("Périmètre brut :",    self.result_perim_brut)
        self.results_layout.addRow("Déduction (lin.) :",  self.result_perim_ded_lin)
        self.results_layout.addRow("Périmètre net :",     self.result_perim_net)
        self.results_layout.addRow("Surface brute :",     self.result_perim_surf_brut)
        self.results_layout.addRow("Surf. déduction :",   self.result_perim_surf_ded)
        self.results_layout.addRow("Surface nette :",     self.result_perim_surf_net)
        self.results_layout.addRow("Total groupe :",      self.result_perim_grp_total)
        # Compteur détaillé
        self.results_layout.addRow("Valeur unitaire :",   self.result_point_unit_val)
        self.results_layout.addRow("Total groupe :",      self.result_point_grp_total)

        # ✅ Stocker les indices des rows pour pouvoir les cacher/afficher
        # Row 0: Nombre d'objets | 1: Numéro | 2: Nb compteur
        # Row 3: Surface brute (surface polygon) | 4: Déduction | 5: Surface nette
        # Row 6: Total groupe (polygon) | 7: Volume
        # Row 8: Périmètre (legacy) | 9: Périm+ded (legacy) | 10: Nb déductions (legacy)
        # Row 11-17: champs périmètre détaillés
        self.surface_result_rows = [3, 4, 5]  # Indices des rows de surface polygon

        # Propriétés spécifiques
        self.specific_properties_group = QGroupBox("Propriétés spécifiques")
        self.specific_properties_group.setStyleSheet(
            "QGroupBox { font-weight: bold; margin-top: 14px; }"
            "QGroupBox::title { subcontrol-origin: margin; top: -2px; left: 8px; padding: 0 4px; }"
        )
        self.specific_layout = QFormLayout()
        self.specific_layout.setVerticalSpacing(4)
        self.specific_layout.setContentsMargins(6, 8, 6, 4)
        self.specific_properties_group.setLayout(self.specific_layout)

        # Ajouter au layout principal avec espacement entre sections
        self.layout.addWidget(self.properties_group)
        self.layout.addSpacing(8)
        self.layout.addWidget(self.results_group)
        self.layout.addSpacing(8)
        self.layout.addWidget(self.specific_properties_group)
        self.layout.addStretch()

        # ── Onglets Propriétés / Affectations ─────────────────────────────────
        from ui.assignments_panel import AssignmentsPanel
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                padding: 5px 14px; font-size: 11px; color: #5a7090;
                border: none; border-bottom: 2px solid transparent;
                background: transparent;
            }
            QTabBar::tab:selected {
                color: #1565c0; border-bottom: 2px solid #1565c0;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected { color: #1a3a70; background: #e8f0fa; }
        """)
        self._tab_widget.addTab(self.main_widget, "Propriétés")
        self._assignments_panel = AssignmentsPanel(self)
        self._assignments_panel.assignments_changed.connect(
            self._on_assignments_changed)
        self._tab_widget.addTab(self._assignments_panel, "Affectations")

        self.setWidget(self._tab_widget)

        # Données actuelles
        self.current_entity = None
        self.updating_ui = False

    # =========================================================================
    # NOUVELLES MÉTHODES POUR L'AFFICHAGE INSTANTANÉ
    # =========================================================================

    def afficher_proprietes_instantane(self, entity):
        """Affiche les propriétés INSTANTANÉMENT quand on clique sur une entité"""
        try:
            entity_name = getattr(entity, 'name', 'Sans nom')

            self.current_entity = entity
            self.display_entity_properties(entity)

            # Mettre à jour le label de sélection
            entity_type = "Surface"
            if hasattr(entity, 'is_perimeter') and entity.is_perimeter:
                entity_type = "Périmètre"
            elif hasattr(entity, 'entity_type'):
                type_val = entity.entity_type
                if type_val == 'line':
                    entity_type = "Distance"
                elif type_val == 'point':
                    entity_type = "Point"

            self.selection_label.setText(
                f"{entity_type} sélectionné: {entity_name}")

            # Cacher l'info rapide si elle était affichée
            self.cacher_info_rapide()
        except Exception as e:
            pass

    def afficher_info_rapide(self, entity):
        """Affiche une info rapide quand on survole une entité"""
        try:
            if hasattr(entity, 'get_properties'):
                proprietes = entity.get_properties()

                # Extraire les infos importantes
                nom = proprietes.get('nom', 'Sans nom')
                type_entite = proprietes.get('type', 'Élément')

                if type_entite == 'Périmètre':
                    longueur = proprietes.get('longueur_totale', 'N/A')
                    info_text = f"📏 {nom} - {longueur}"
                else:
                    surface = proprietes.get(
                        'surface', proprietes.get('surface_cm²', 'N/A'))
                    info_text = f"🔷 {nom} - {surface}"

                self.info_rapide_label.setText(info_text)
                self.info_rapide_label.show()
        except (AttributeError, TypeError) as e:
            pass

    def _clear_layout_items(self, layout):
        """Supprime proprement les widgets et sous-layouts."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout_items(child.layout())

    def cacher_info_rapide(self):
        """Cache l'info rapide"""
        self.info_rapide_label.hide()

    def effacer_affichage(self):
        """Efface tout l'affichage quand rien n'est sélectionné"""
        try:
            self.updating_ui = True
            self.current_entity = None
            self.selection_label.setText("Aucun élément sélectionné")
            # Réinitialiser les sections
            self._reset_results()
            self.result_count.setText("0 Unité")

            # Réinitialiser champs propriétés
            self.name_edit.clear()
            self.update_color_button(QColor(0, 0, 255))
            
            # IMPORTANT: Bloquer les signaux pendant la réinitialisation
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(70)
            self.opacity_slider.blockSignals(False)
            
            self.thickness_slider.blockSignals(True)
            self.thickness_slider.setValue(8)
            self.thickness_slider.blockSignals(False)
            self.show_measure_checkbox.blockSignals(True)
            self.show_measure_checkbox.setChecked(False)
            self.show_measure_checkbox.blockSignals(False)
            self.counter_size_label.hide()
            self.counter_size_container.hide()
            self.counter_shape_label.hide()
            self.counter_shape_combo.hide()
            self.show_measure_checkbox.setText("Afficher la mesure")
            self.name_edit.clear()
            self.update_color_button(QColor(0, 0, 255))
            self.show_measure_checkbox.blockSignals(True)
            self.show_measure_checkbox.setChecked(False)
            self.show_measure_checkbox.blockSignals(False)

            # Nettoyer les propriétés spécifiques
            self._clear_layout_items(self.specific_layout)
        except Exception as e:
            pass
        finally:
            self.updating_ui = False

    # =========================================================================
    # MÉTHODES EXISTANTES CORRIGÉES
    # =========================================================================

    def _on_assignments_changed(self):
        """Appelé quand les affectations changent — rafraîchit le rapport si visible."""
        mw = getattr(self, 'main_window', None)
        if mw:
            if hasattr(mw, '_auto_refresh_report'):
                mw._auto_refresh_report()

    def display_entity_properties(self, entity):
        """Affiche les propriétés d'une entité (méthode unifiée)"""
        # CORRIGER: Toujours réinitialiser updating_ui au début
        self.current_entity = entity

        # Charger l'entité dans le panneau d'affectations
        if hasattr(self, '_assignments_panel'):
            etype = getattr(entity, 'entity_type', '') if entity else ''
            if etype in ('polygon', 'perimeter', 'point'):
                self._assignments_panel.load_entity(entity)
                self._tab_widget.setTabEnabled(1, True)
            else:
                self._assignments_panel.load_entity(None)
                self._tab_widget.setTabEnabled(1, False)

        if not entity:
            self.clear_auto_display()
            self.updating_ui = False  # S'assurer qu'on réinitialise
            return

        # CORRIGER: S'assurer que updating_ui est False avant de commencer
        if self.updating_ui:
            self.updating_ui = False

        self.updating_ui = True

        try:
            # Mettre à jour les champs éditables - BLOQUER les signaux pendant la mise à jour
            self.name_edit.blockSignals(True)
            self.name_edit.setText(getattr(entity, 'name', 'Sans nom'))
            self.name_edit.blockSignals(False)

            # Couleur - CORRIGER: convertir la string en QColor si nécessaire
            color_raw = getattr(entity, 'color', QColor(0, 0, 255))
            
            if isinstance(color_raw, str):
                color = QColor(color_raw)
            else:
                color = color_raw if isinstance(color_raw, QColor) else QColor(0, 0, 255)
            
            self.update_color_button(color)

            # Opacité (basée sur l'alpha de la couleur)
            alpha = color.alphaF()
            alpha_pct = int(round(alpha * 100))
            alpha_pct = max(10, min(100, alpha_pct))
            
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(alpha_pct)
            self.opacity_slider.blockSignals(False)
            self.opacity_value_label.setText(f"{alpha_pct} %")

            # Visibilité de la mesure / texte
            visible = True  # Par défaut visible
            # Compteurs: utiliser show_label (texte sous le point), pas le numéro interne
            if getattr(entity, 'entity_type', '') == 'point':
                if hasattr(entity, 'show_label'):
                    visible = bool(getattr(entity, 'show_label', True))
                elif hasattr(entity, 'name_item') and entity.name_item:
                    try:
                        visible = entity.name_item.isVisible()
                    except (AttributeError, RuntimeError):
                        visible = True
            # ✅ Surfaces / périmètres : utiliser show_measure si disponible
            elif hasattr(entity, 'show_measure'):
                visible = bool(getattr(entity, 'show_measure', False))
            # ✅ Fallback: vérifier text_item (surfaces, distances) ou text_items (périmètres)
            elif hasattr(entity, 'text_items') and entity.text_items and len(entity.text_items) > 0:
                try:
                    visible = entity.text_items[0].isVisible()
                except (AttributeError, RuntimeError):
                    visible = True
            elif hasattr(entity, 'text_item') and entity.text_item:
                try:
                    visible = entity.text_item.isVisible()
                except (AttributeError, RuntimeError):
                    visible = True
            self.show_measure_checkbox.blockSignals(True)
            self.show_measure_checkbox.setChecked(visible)
            if getattr(entity, 'entity_type', '') == 'point':
                self.show_measure_checkbox.setText("Afficher le texte")
                if hasattr(entity, 'debug') and entity.debug:
                    name_item_visible = None
                    if hasattr(entity, 'name_item') and entity.name_item:
                        try:
                            name_item_visible = entity.name_item.isVisible()
                        except Exception:
                            name_item_visible = None
            else:
                self.show_measure_checkbox.setText("Afficher la mesure")
            self.show_measure_checkbox.blockSignals(False)
            # Propriétés spécifiques
            self.update_specific_properties(entity)

            # Mettre à jour les résultats (surface, périmètre, déductions)
            self.update_results(entity)

            # Épaisseur ligne pour périmètres ET distances
            is_perimeter = (
                (hasattr(entity, 'is_perimeter') and entity.is_perimeter)
                or getattr(entity, 'entity_type', '') == 'perimeter'
            )
            is_line = getattr(entity, 'entity_type', '') == 'line'

            self.thickness_slider.blockSignals(True)
            if is_perimeter or is_line:
                self.thickness_label.show()
                self.thickness_slider.show()
                width_val = getattr(entity, 'width', 8)
                width_val = max(5, min(30, int(width_val)))
                self.thickness_slider.setValue(width_val)
            else:
                self.thickness_label.hide()
                self.thickness_slider.hide()
            self.thickness_slider.blockSignals(False)

            # Motif de remplissage (surfaces/polygones uniquement)
            is_surface = getattr(entity, 'entity_type', '') in ('polygon', 'surface')
            if is_surface:
                current_pattern = pattern_from_storage(
                    getattr(entity, 'fill_pattern', 'solid'))
                self.pattern_combo.blockSignals(True)
                for i in range(self.pattern_combo.count()):
                    if self.pattern_combo.itemData(i) == current_pattern:
                        self.pattern_combo.setCurrentIndex(i)
                        break
                self.pattern_combo.blockSignals(False)
                self.pattern_label.show()
                self.pattern_combo.show()
            else:
                self.pattern_label.hide()
                self.pattern_combo.hide()

            # Taille + forme groupe compteur (points)
            is_point = getattr(entity, 'entity_type', '') == 'point'
            if is_point:
                size_value = int(getattr(entity, 'size', 14))
                manager = None
                if self.main_window and hasattr(self.main_window, 'canvas_view'):
                    manager = getattr(
                        self.main_window.canvas_view, 'entity_manager', None)
                group_id = getattr(entity, 'group_id', None)
                if manager and group_id:
                    points = manager.get_points_by_group(group_id)
                    if points:
                        size_value = int(getattr(points[0], 'size', size_value))

                self.counter_size_slider.blockSignals(True)
                self.counter_size_slider.setValue(size_value)
                self.counter_size_value_label.setText(str(size_value))
                self.counter_size_slider.blockSignals(False)
                self.counter_size_label.show()
                self.counter_size_container.show()

                shape_value = getattr(entity, 'shape', 'circle')
                if manager and group_id and points:
                    shape_value = getattr(points[0], 'shape', shape_value)
                self.counter_shape_combo.blockSignals(True)
                for i in range(self.counter_shape_combo.count()):
                    if self.counter_shape_combo.itemData(i) == shape_value:
                        self.counter_shape_combo.setCurrentIndex(i)
                        break
                self.counter_shape_combo.blockSignals(False)
                self.counter_shape_label.show()
                self.counter_shape_combo.show()
            else:
                self.counter_size_label.hide()
                self.counter_size_container.hide()
                self.counter_shape_label.hide()
                self.counter_shape_combo.hide()

            # L'épaisseur est gérée par le slider de la section "Propriétés"

        except (AttributeError, TypeError) as e:
            self.clear_auto_display()
        except Exception as e:
            self.clear_auto_display()
        finally:
            # CORRIGER: Toujours réinitialiser updating_ui dans finally
            self.updating_ui = False

    def display_properties_in_table(self, properties):
        """Compatibilité arrière : non utilisée dans la nouvelle mise en page."""
        return

    def update_color_preview(self, color_hex):
        """Compatibilité arrière - plus utilisé dans la nouvelle mise en page."""
        return

    def clear_auto_display(self):
        """Vide l'affichage automatique"""
        self.updating_ui = True
        self._reset_results()
        self.result_count.setText("0 Unité")
        self.name_edit.blockSignals(True)
        self.name_edit.clear()
        self.name_edit.blockSignals(False)
        self.update_color_button(QColor(0, 0, 255))
        
        # IMPORTANT: Bloquer les signaux pendant la réinitialisation
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(70)
        self.opacity_slider.blockSignals(False)
        
        self.thickness_slider.blockSignals(True)
        self.thickness_slider.setValue(8)
        self.thickness_slider.blockSignals(False)

        self.pattern_label.hide()
        self.pattern_combo.hide()

        self.show_measure_checkbox.blockSignals(True)
        self.show_measure_checkbox.setChecked(False)
        self.show_measure_checkbox.blockSignals(False)
        self.updating_ui = False

    def display_entity_properties_legacy(self, entity):
        """Compatibilité arrière - non utilisée dans la nouvelle mise en page."""
        return

    def update_entities_list(self, entities):
        """Met à jour la liste des entités disponibles"""
        try:
            self.updating_ui = True
            self.entity_combo.clear()
            self.entity_combo.addItem("Aucune sélection", None)

            for entity in entities:
                entity_name = getattr(entity, 'name', 'Sans nom')
                entity_type = getattr(entity, 'entity_type', 'inconnu')
                entity_id = getattr(entity, 'entity_id', '')

                display_text = f"{entity_name} ({entity_type})"
                self.entity_combo.addItem(display_text, entity_id)

            self.updating_ui = False
        except Exception as e:
            self.updating_ui = False

    def on_entity_selected(self, index):
        """Quand une entité est sélectionnée dans la combo box"""
        if self.updating_ui or index == -1 or index == 0:
            return

        try:
            entity_id = self.entity_combo.itemData(index)
            # CORRIGER: Vérifications complètes en chaîne
            if (self.main_window and
                hasattr(self.main_window, 'canvas_view') and
                self.main_window.canvas_view and
                hasattr(self.main_window.canvas_view, 'entity_manager') and
                    self.main_window.canvas_view.entity_manager):

                entity = self.main_window.canvas_view.entity_manager.get_entity(
                    entity_id)
                if entity:
                    self.display_entity_properties(entity)
        except (AttributeError, TypeError) as e:
            pass

    def update_specific_properties(self, entity):
        """Met à jour les propriétés spécifiques selon le type d'entité"""
        try:
            # Nettoyer le layout des propriétés spécifiques
            self._clear_layout_items(self.specific_layout)

            entity_type = getattr(entity, 'entity_type', 'inconnu')

            if entity_type == 'polygon':
                if hasattr(entity, 'is_perimeter') and entity.is_perimeter:
                    self.add_perimeter_properties(entity)
                else:
                    self.add_surface_properties(entity)
            elif entity_type == 'line':
                self.add_distance_properties(entity)
            elif entity_type == 'point':
                self.add_point_properties(entity)
            elif entity_type == 'perimeter':
                self.add_perimeter_properties(entity)
        except Exception as e:
            pass

    # ------------------------------------------------------------------
    # Nouvelle section Résultats
    # ------------------------------------------------------------------
    def _format_area(self, value):
        return f"{value:.2f} m²" if value is not None else "-"

    def _format_length(self, value):
        return f"{value:.2f} m" if value is not None else "-"

    def _format_volume(self, value):
        return f"{value:.2f} m³" if value is not None else "-"

    def _reset_results(self):
        self.result_counter_number.setText("-")
        self.result_counter_group_count.setText("-")
        self.result_surface_brute.setText("-")
        self.result_deduction.setText("-")
        self.result_surface_nette.setText("-")
        self.result_surface_group.setText("-")
        self.result_volume.setText("-")
        self.result_perimetre.setText("-")
        self.result_perimetre_deduction.setText("-")
        self.result_nb_deductions.setText("0 Unité")
        # Champs compteur + périmètre détaillés — masqués par défaut
        for field in [
            self.result_perim_brut, self.result_perim_ded_lin, self.result_perim_net,
            self.result_perim_surf_brut, self.result_perim_surf_ded, self.result_perim_surf_net,
            self.result_perim_grp_total,
            self.result_point_unit_val, self.result_point_grp_total,
        ]:
            field.setText("-")
            lbl = self.results_layout.labelForField(field)
            if lbl:
                lbl.setVisible(False)
            field.setVisible(False)

    def update_results(self, entity):
        """Met à jour les champs de résultats (surface, déductions, périmètre)."""
        self._reset_results()
        if not entity:
            self.result_count.setText("0 Unité")
            return

        # Nombre d'objets (toujours 1 dans ce contexte)
        self.result_count.setText("1 Unité")

        # Compteurs: affichage spécifique
        if getattr(entity, 'entity_type', '') == 'point':
            counter_number = getattr(entity, 'counter_number', None)
            self.result_counter_number.setText(
                str(counter_number) if counter_number is not None else "-")

            group_count = 1
            manager = None
            if self.main_window and hasattr(self.main_window, 'canvas_view'):
                manager = getattr(
                    self.main_window.canvas_view, 'entity_manager', None)
            group_id = getattr(entity, 'group_id', None)
            if manager and not group_id:
                group_id = manager.ensure_point_group(
                    getattr(entity, 'name', 'Compteur'))
                entity.group_id = group_id
            if manager and group_id:
                group_count = len(manager.get_points_by_group(group_id))
            n_txt = f"{group_count} Unité" if group_count <= 1 else f"{group_count} Unités"
            self.result_counter_group_count.setText(n_txt)

            # Masquer les champs surface/périmètre/déductions
            for field in [
                self.result_surface_brute, self.result_deduction,
                self.result_surface_nette, self.result_surface_group,
                self.result_perimetre, self.result_perimetre_deduction,
                self.result_nb_deductions,
            ]:
                lbl = self.results_layout.labelForField(field)
                if lbl:
                    lbl.setVisible(False)
                field.setVisible(False)

            # Afficher les champs compteur de base
            for field in [self.result_counter_number, self.result_counter_group_count]:
                lbl = self.results_layout.labelForField(field)
                if lbl:
                    lbl.setVisible(True)
                field.setVisible(True)

            # ── Valeur unitaire + total groupe selon dimensions ──────────────
            length    = float(getattr(entity, 'length',    0.0) or 0.0)
            height    = float(getattr(entity, 'height',    0.0) or 0.0)
            thickness = float(getattr(entity, 'thickness', 0.0) or 0.0)

            def _show_pt(field, text, bold=False, color="#222"):
                field.setText(text)
                field.setStyleSheet(
                    f"font-weight: {'bold' if bold else 'normal'}; color: {color};")
                lbl = self.results_layout.labelForField(field)
                if lbl:
                    lbl.setVisible(True)
                field.setVisible(True)

            if length > 0:
                if height > 0 and thickness > 0:
                    unit_val  = length * height * thickness
                    grp_total = unit_val * group_count
                    unit_lbl_name = "Volume unitaire :"
                    unit_txt  = f"{unit_val:.2f} m³"
                    grp_txt   = f"{grp_total:.2f} m³  (×{group_count})"
                elif height > 0:
                    unit_val  = length * height
                    grp_total = unit_val * group_count
                    unit_lbl_name = "Surface unitaire :"
                    unit_txt  = f"{unit_val:.2f} m²"
                    grp_txt   = f"{grp_total:.2f} m²  (×{group_count})"
                else:
                    unit_val  = length
                    grp_total = unit_val * group_count
                    unit_lbl_name = "Longueur unitaire :"
                    unit_txt  = f"{unit_val:.2f} m"
                    grp_txt   = f"{grp_total:.2f} m  (×{group_count})"

                # Mettre à jour le label de la ligne unitaire
                lbl_item = self.results_layout.labelForField(self.result_point_unit_val)
                if lbl_item:
                    lbl_item.setText(unit_lbl_name)

                _show_pt(self.result_point_unit_val,  unit_txt)
                _show_pt(self.result_point_grp_total, grp_txt, bold=True, color="#1A237E")
            return
        
        # ✅ Déterminer si c'est un périmètre pour cacher les résultats de surface
        is_perimeter = False
        if hasattr(entity, 'is_perimeter') and entity.is_perimeter:
            is_perimeter = True
        elif getattr(entity, 'entity_type', '') == 'perimeter':
            is_perimeter = True
        
        # Cacher ou afficher les rows de surface selon le type d'entité
        for row_index in self.surface_result_rows:
            label_item = self.results_layout.itemAt(row_index, QFormLayout.LabelRole)
            field_item = self.results_layout.itemAt(row_index, QFormLayout.FieldRole)
            
            if label_item and label_item.widget():
                label_item.widget().setVisible(not is_perimeter)
            if field_item and field_item.widget():
                field_item.widget().setVisible(not is_perimeter)

        # Surface brute / nette / déduction
        brute = None
        nette = None
        deduction = 0.0

        if hasattr(entity, "calculate_area"):
            try:
                brute = entity.calculate_area()
            except Exception:
                brute = None

        if hasattr(entity, "calculate_net_area"):
            try:
                nette = entity.calculate_net_area()
            except Exception:
                nette = None

        if brute is not None and nette is not None:
            deduction = max(0.0, brute - nette)
        elif brute is not None:
            nette = brute
            deduction = 0.0

        # Afficher les champs compteur pour les autres types
        for field in [self.result_counter_number, self.result_counter_group_count]:
            label = self.results_layout.labelForField(field)
            if label:
                label.setVisible(False)
            field.setVisible(False)

        self.result_surface_brute.setText(self._format_area(brute) if brute is not None else "-")
        self.result_surface_nette.setText(self._format_area(nette) if nette is not None else "-")
        self.result_deduction.setText(self._format_area(deduction) if deduction is not None else "-")

        # Total groupe — remonter au parent racine si l'entité est un enfant
        group_lbl = self.results_layout.labelForField(self.result_surface_group)
        if not is_perimeter and hasattr(entity, "calculate_total_group_area"):
            # Remonter à la racine du groupe (enfant → parent)
            grp_root = entity
            while getattr(grp_root, "parent_entity", None) is not None:
                grp_root = grp_root.parent_entity

            # Vérifier si la racine est bien un groupe (parent avec enfants)
            root_children = getattr(grp_root, "child_entities", None) or []
            in_group = getattr(grp_root, "is_group_parent", False) or bool(root_children)

            if in_group:
                try:
                    grp_total = grp_root.calculate_total_group_area()
                    nb = 1 + len(root_children)
                    self.result_surface_group.setText(
                        f"{self._format_area(grp_total)}  (×{nb})")
                    lbl_txt = self.results_layout.labelForField(self.result_surface_group)
                    if lbl_txt:
                        lbl_txt.setVisible(True)
                    self.result_surface_group.setVisible(True)
                    self.result_surface_group.setStyleSheet(
                        "font-weight: bold; color: #1A237E;")
                except Exception:
                    if group_lbl:
                        group_lbl.setVisible(False)
                    self.result_surface_group.setVisible(False)
            else:
                if group_lbl:
                    group_lbl.setVisible(False)
                self.result_surface_group.setVisible(False)
        else:
            if group_lbl:
                group_lbl.setVisible(False)
            self.result_surface_group.setVisible(False)

        # Volume
        volume = None
        if hasattr(entity, "calculate_volume"):
            try:
                volume = entity.calculate_volume()
            except Exception:
                volume = None

        volume_label = self.results_layout.labelForField(self.result_volume)
        if volume is not None and volume > 0:
            self.result_volume.setText(self._format_volume(volume))
            if volume_label:
                volume_label.setVisible(True)
            self.result_volume.setVisible(True)
        else:
            if volume_label:
                volume_label.setVisible(False)
            self.result_volume.setVisible(False)

        # ── Périmètre détaillé (champs dédiés) ───────────────────────────────
        if is_perimeter:
            self._update_perimeter_results(entity)

        # Legacy périmètre (polygon) — masqués pour les vrais périmètres
        for field in [self.result_perimetre, self.result_perimetre_deduction, self.result_nb_deductions]:
            lbl = self.results_layout.labelForField(field)
            if lbl:
                lbl.setVisible(not is_perimeter)
            field.setVisible(not is_perimeter)

        if not is_perimeter:
            perim = None
            perim_gross = None
            if hasattr(entity, "calculate_perimeter_length"):
                try:
                    perim = entity.calculate_perimeter_length()
                except Exception:
                    perim = None
            if hasattr(entity, "_calculate_gross_perimeter_length_m"):
                try:
                    perim_gross = entity._calculate_gross_perimeter_length_m()
                except Exception:
                    perim_gross = perim
            else:
                perim_gross = perim
            self.result_perimetre.setText(self._format_length(perim) if perim is not None else "-")

            # Périmètre des ouvertures : somme des contours de chaque ouverture polygonale
            import math
            perim_ouv = 0.0
            nb_ded = 0
            openings = []
            if hasattr(entity, "openings") and entity.openings is not None:
                try:
                    openings = list(entity.openings)
                    nb_ded = len(openings)
                except Exception:
                    pass
            ppm_m = float(getattr(entity, "pixels_per_meter", 1.0) or 1.0)
            if ppm_m <= 0:
                ppm_m = 1.0
            for op in openings:
                try:
                    pts = getattr(op, "points", []) or []
                    ppm_op = float(getattr(op, "pixels_per_meter", ppm_m) or ppm_m)
                    if ppm_op <= 0:
                        ppm_op = ppm_m
                    n = len(pts)
                    if n >= 2:
                        perim_px = sum(
                            math.hypot(pts[(i + 1) % n].x() - pts[i].x(),
                                       pts[(i + 1) % n].y() - pts[i].y())
                            for i in range(n)
                        )
                        perim_ouv += perim_px / ppm_op
                except Exception:
                    pass

            if nb_ded > 0:
                self.result_perimetre_deduction.setText(self._format_length(perim_ouv))
            else:
                self.result_perimetre_deduction.setText("—")
            self.result_nb_deductions.setText(f"{nb_ded} Unité")

    def _show_perim_field(self, field, text, bold=False, color="#222"):
        """Affiche un champ périmètre avec son label."""
        field.setText(text)
        if bold:
            field.setStyleSheet(f"font-weight: bold; color: {color};")
        else:
            field.setStyleSheet("font-weight: normal; color: #222;")
        lbl = self.results_layout.labelForField(field)
        if lbl:
            lbl.setVisible(True)
        field.setVisible(True)

    def _update_perimeter_results(self, entity):
        """Calcule et affiche tous les résultats pour un périmètre."""
        # ── Longueurs ────────────────────────────────────────────────────────
        brut = 0.0
        net  = 0.0
        try:
            brut = entity._calculate_gross_perimeter_length_m() \
                if hasattr(entity, "_calculate_gross_perimeter_length_m") \
                else entity.calculate_perimeter_length()
        except Exception:
            pass
        try:
            net = entity.calculate_perimeter_length() \
                if hasattr(entity, "calculate_perimeter_length") else 0.0
        except Exception:
            pass
        ded_lin = max(0.0, brut - net)

        self._show_perim_field(self.result_perim_brut,    self._format_length(brut))
        self._show_perim_field(self.result_perim_ded_lin, self._format_length(ded_lin))
        self._show_perim_field(self.result_perim_net,     self._format_length(net))

        # ── Surfaces latérales / Volumes (si hauteur > 0) ────────────────────
        height    = float(getattr(entity, "height",    0.0) or 0.0)
        thickness = float(getattr(entity, "thickness", 0.0) or 0.0)

        if height > 0:
            surf_brut = brut * height

            # Déduction surface = Σ(largeur × hauteur) de chaque ouverture linéaire
            surf_ded = 0.0
            for op in (getattr(entity, "linear_openings", None) or []):
                op_w = op.get("length_m", 0.0)
                op_h = op.get("height", 0.0)
                surf_ded += op_w * op_h

            surf_net = max(0.0, surf_brut - surf_ded)

            if thickness > 0:
                # ── Mode Volume (m³) ─────────────────────────────────────────
                vol_brut = surf_brut * thickness
                vol_ded  = surf_ded  * thickness
                vol_net  = max(0.0, surf_net * thickness)

                def _set_lbl(field, text):
                    lbl = self.results_layout.labelForField(field)
                    if lbl:
                        lbl.setText(text)

                _set_lbl(self.result_perim_surf_brut, "Volume brut :")
                _set_lbl(self.result_perim_surf_ded,  "Vol. déduction :")
                _set_lbl(self.result_perim_surf_net,  "Volume net :")

                self._show_perim_field(self.result_perim_surf_brut,
                                       self._format_volume(vol_brut))
                self._show_perim_field(self.result_perim_surf_ded,
                                       self._format_volume(vol_ded))
                self._show_perim_field(self.result_perim_surf_net,
                                       self._format_volume(vol_net),
                                       bold=True, color="#1b5e20")
            else:
                # ── Mode Surface (m²) ────────────────────────────────────────
                def _set_lbl(field, text):
                    lbl = self.results_layout.labelForField(field)
                    if lbl:
                        lbl.setText(text)

                _set_lbl(self.result_perim_surf_brut, "Surface brute :")
                _set_lbl(self.result_perim_surf_ded,  "Surf. déduction :")
                _set_lbl(self.result_perim_surf_net,  "Surface nette :")

                self._show_perim_field(self.result_perim_surf_brut,
                                       self._format_area(surf_brut))
                self._show_perim_field(self.result_perim_surf_ded,
                                       self._format_area(surf_ded))
                self._show_perim_field(self.result_perim_surf_net,
                                       self._format_area(surf_net),
                                       bold=True, color="#1b5e20")
        else:
            # Restaurer les labels par défaut et masquer les champs
            for field, default_lbl in [
                (self.result_perim_surf_brut, "Surface brute :"),
                (self.result_perim_surf_ded,  "Surf. déduction :"),
                (self.result_perim_surf_net,  "Surface nette :"),
            ]:
                lbl = self.results_layout.labelForField(field)
                if lbl:
                    lbl.setText(default_lbl)
                    lbl.setVisible(False)
                field.setVisible(False)

        # ── Total groupe ──────────────────────────────────────────────────────
        grp_root = entity
        while getattr(grp_root, "parent_entity", None) is not None:
            grp_root = grp_root.parent_entity

        root_children = getattr(grp_root, "child_entities", None) or []
        in_group = getattr(grp_root, "is_group_parent", False) or bool(root_children)

        if in_group and hasattr(grp_root, "calculate_total_group_length"):
            try:
                grp_len = grp_root.calculate_total_group_length()
                nb = 1 + len(root_children)
                members = [grp_root] + list(root_children)

                if height > 0 and thickness > 0:
                    # Total volume du groupe = Σ surface_laterale × épaisseur
                    grp_vol = 0.0
                    for m in members:
                        if hasattr(m, "calculate_surface_laterale"):
                            try:
                                grp_vol += m.calculate_surface_laterale() * \
                                           float(getattr(m, "thickness", thickness) or thickness)
                            except Exception:
                                pass
                    total_txt = f"{self._format_volume(grp_vol)}  (×{nb})"
                elif height > 0:
                    # Total surface nette du groupe = Σ surface_laterale
                    grp_surf = 0.0
                    for m in members:
                        if hasattr(m, "calculate_surface_laterale"):
                            try:
                                grp_surf += m.calculate_surface_laterale()
                            except Exception:
                                pass
                    total_txt = f"{self._format_area(grp_surf)}  (×{nb})"
                else:
                    total_txt = f"{self._format_length(grp_len)}  (×{nb})"

                self._show_perim_field(
                    self.result_perim_grp_total, total_txt, bold=True, color="#1A237E")
            except Exception:
                lbl = self.results_layout.labelForField(self.result_perim_grp_total)
                if lbl:
                    lbl.setVisible(False)
                self.result_perim_grp_total.setVisible(False)
        else:
            lbl = self.results_layout.labelForField(self.result_perim_grp_total)
            if lbl:
                lbl.setVisible(False)
            self.result_perim_grp_total.setVisible(False)

    def add_surface_properties(self, entity):
        """Ajoute les propriétés spécifiques aux surfaces"""
        try:
            if not hasattr(entity, 'calculate_area'):
                return

            area = entity.calculate_area()
            area_text_str = f"{area:.2f} m²"
            if hasattr(entity, 'get_area_text'):
                area_text_str = entity.get_area_text()

            area_text = QLabel(area_text_str)
            area_text.setStyleSheet("font-weight: bold; color: #0066CC;")
            self.specific_layout.addRow("Surface:", area_text)

            # Épaisseur (m) — surface × épaisseur = volume dalle (ex : plancher, dalle)
            # (la surface est déjà 2D : hauteur non pertinente pour les surfaces)
            if hasattr(entity, 'thickness'):
                thick_edit = QLineEdit()
                thick_edit.setPlaceholderText("Épaisseur en mètres")
                thick_edit.setText(f"{getattr(entity, 'thickness', 0.0):.2f}")
                thick_edit.editingFinished.connect(
                    lambda ent=entity, edit=thick_edit: self.on_dimension_changed(ent, edit, "thickness"))
                self.specific_layout.addRow("Épaisseur  e (m):", thick_edit)

        except (AttributeError, TypeError) as e:
            pass

    def add_perimeter_properties(self, entity):
        """Ajoute les propriétés spécifiques aux périmètres"""
        try:
            if not hasattr(entity, 'get_perimeter_text'):
                return

            perimeter_text = entity.get_perimeter_text()
            perimeter_label = QLabel(perimeter_text)
            perimeter_label.setStyleSheet("font-weight: bold; color: #0066CC;")
            self.specific_layout.addRow("Périmètre:", perimeter_label)

            # L'épaisseur est maintenant gérée uniquement dans la section "Propriétés" principale

            # Hauteur (m) pour surface latérale/volume
            if hasattr(entity, 'height'):
                height_edit = QLineEdit()
                height_edit.setPlaceholderText("Hauteur en mètres")
                height_edit.setText(f"{getattr(entity, 'height', 0.0):.2f}")
                height_edit.editingFinished.connect(
                    lambda ent=entity, edit=height_edit: self.on_dimension_changed(ent, edit, "height"))
                self.specific_layout.addRow("Hauteur  h (m):", height_edit)

            # Épaisseur (m) pour volume
            if hasattr(entity, 'thickness'):
                thickness_edit = QLineEdit()
                thickness_edit.setPlaceholderText("Épaisseur en mètres")
                thickness_edit.setText(f"{getattr(entity, 'thickness', 0.0):.2f}")
                thickness_edit.editingFinished.connect(
                    lambda ent=entity, edit=thickness_edit: self.on_dimension_changed(ent, edit, "thickness"))
                self.specific_layout.addRow("Épaisseur  e (m):", thickness_edit)
        except (AttributeError, TypeError) as e:
            pass

    def add_distance_properties(self, entity):
        """Ajoute les propriétés spécifiques aux distances"""
        try:
            if not hasattr(entity, 'calculate_length'):
                return

            length = entity.calculate_length()
            length_text_str = f"{length:.2f} m"
            if hasattr(entity, 'get_length_text'):
                length_text_str = entity.get_length_text()

            length_label = QLabel(length_text_str)
            length_label.setStyleSheet("font-weight: bold; color: #0066CC;")
            self.specific_layout.addRow("Distance:", length_label)
        except (AttributeError, TypeError) as e:
            pass

    def add_point_properties(self, entity):
        """Ajoute les propriétés spécifiques aux points"""
        try:
            current = entity

            def make_number_edit(attr_name):
                value = getattr(current, attr_name, 0.0)
                edit = QLineEdit()
                edit.setPlaceholderText("0.00")
                edit.setText(f"{float(value):.2f}")
                edit.editingFinished.connect(
                    lambda e=edit, a=attr_name: self.on_point_dimension_changed(e, a))
                return edit

            self.specific_layout.addRow("Côté  a (m):", make_number_edit("length"))
            self.specific_layout.addRow("Côté  b (m):", make_number_edit("thickness"))
            self.specific_layout.addRow("Hauteur  h (m):", make_number_edit("height"))
        except Exception as e:
            pass

    def _get_selected_points(self):
        if not self.main_window or not hasattr(self.main_window, "canvas_view"):
            return []
        selected = self.main_window.canvas_view.get_selected_entities()
        return [e for e in selected if getattr(e, "entity_type", "") == "point"]

    def _apply_to_selected_points(self, apply_fn):
        points = self._get_selected_points()
        if points:
            # Si tous les points sélectionnés appartiennent au même groupe,
            # appliquer la modification à tout le groupe.
            group_ids = {getattr(p, "group_id", None) for p in points}
            if len(group_ids) == 1:
                group_id = next(iter(group_ids))
                if not group_id and self.main_window and hasattr(self.main_window, 'canvas_view'):
                    manager = getattr(
                        self.main_window.canvas_view, 'entity_manager', None)
                    if manager:
                        group_id = manager.ensure_point_group(
                            getattr(points[0], 'name', 'Compteur'))
                        for point in points:
                            point.group_id = group_id
                if group_id and self.main_window and hasattr(self.main_window, 'canvas_view'):
                    manager = getattr(
                        self.main_window.canvas_view, 'entity_manager', None)
                    if manager:
                        group_points = manager.get_points_by_group(group_id)
                        if group_points:
                            for point in group_points:
                                apply_fn(point)
                            return True

            # Sinon, appliquer aux points sélectionnés uniquement
            for point in points:
                apply_fn(point)
            return True

        if self.current_entity and getattr(self.current_entity, "entity_type", "") == "point":
            group_id = getattr(self.current_entity, "group_id", None)
            if not group_id and self.main_window and hasattr(self.main_window, 'canvas_view'):
                manager = getattr(
                    self.main_window.canvas_view, 'entity_manager', None)
                if manager:
                    group_id = manager.ensure_point_group(
                        getattr(self.current_entity, 'name', 'Compteur'))
                    self.current_entity.group_id = group_id
            if group_id and self.main_window and hasattr(self.main_window, 'canvas_view'):
                manager = getattr(
                    self.main_window.canvas_view, 'entity_manager', None)
                if manager:
                    group_points = manager.get_points_by_group(group_id)
                    if group_points:
                        for point in group_points:
                            apply_fn(point)
                        return True
            apply_fn(self.current_entity)
            return True
        return False

    def on_point_dimension_changed(self, editor: QLineEdit, attr_name: str):
        """Met à jour longueur/hauteur/épaisseur pour les compteurs (groupe)."""
        if not editor or not self.current_entity:
            return
        try:
            text = editor.text().strip().replace(",", ".")
            value = float(text) if text else 0.0
        except ValueError:
            value = 0.0
            editor.setText("0.00")

        def apply(ent):
            setattr(ent, attr_name, value)

        self._apply_to_selected_points(apply)

        if hasattr(self.main_window, 'on_entity_modified'):
            self.main_window.on_entity_modified(self.current_entity)

    def on_point_shape_changed(self, shape):
        if self.updating_ui:
            return
        self._apply_to_selected_points(lambda ent: ent.set_shape(shape))
        self._log_counter_group_change("forme", shape)

    def on_point_size_changed(self, size, label=None):
        if self.updating_ui:
            return
        if label:
            label.setText(str(int(size)))
        self._apply_to_selected_points(lambda ent: ent.set_size(size))
        self._log_counter_group_change("taille", int(size))

    def _log_counter_group_change(self, prop_name, value):
        """Log minimal pour suivre les modifications de groupe de compteurs."""
        try:
            if not self.current_entity or getattr(self.current_entity, "entity_type", "") != "point":
                return

            group_id = getattr(self.current_entity, "group_id", None)
            group_name = getattr(self.current_entity, "name", "Compteur")
            group_count = 1

            manager = None
            if self.main_window and hasattr(self.main_window, "canvas_view"):
                manager = getattr(self.main_window.canvas_view, "entity_manager", None)
            if manager and group_id:
                group_count = len(manager.get_points_by_group(group_id))

        except Exception as e:
            pass

    def update_color_button(self, color):
        """Synchronise la palette de pastilles avec la couleur de l'entité."""
        try:
            if isinstance(color, str):
                color = QColor(color)
            self._color_data = color
            self.color_swatches.set_color(color)
        except Exception:
            pass

    def _on_swatch_color_selected(self, color: QColor):
        """Appelé quand l'utilisateur clique sur une pastille ou valide une couleur custom."""
        try:
            if self.current_entity and hasattr(self.current_entity, 'color'):
                entity_color_raw = self.current_entity.color
                if isinstance(entity_color_raw, str):
                    entity_color = QColor(entity_color_raw)
                elif isinstance(entity_color_raw, QColor):
                    entity_color = entity_color_raw
                else:
                    entity_color = QColor(0, 0, 255)
                color.setAlpha(entity_color.alpha())
            self.update_color_button(color)
            if self.current_entity:
                self.colorChanged.emit(self.current_entity, color)
        except Exception:
            pass

    def on_opacity_changed(self, value):
        """Met à jour l'opacité (alpha) de la couleur de l'entité."""
        self.opacity_value_label.setText(f"{value} %")
        
        if not self.updating_ui and self.current_entity:
            try:
                # Lire la couleur actuelle
                color_raw = getattr(self.current_entity, "color", None)
                
                if isinstance(color_raw, str):
                    color = QColor(color_raw)
                elif isinstance(color_raw, QColor):
                    color = QColor(color_raw)  # copie
                else:
                    color = QColor(0, 0, 255)
                
                # Appliquer la nouvelle opacité
                color.setAlphaF(value / 100.0)

                # Pour les compteurs: appliquer au groupe via le signal
                if getattr(self.current_entity, "entity_type", "") == "point":
                    self.colorChanged.emit(self.current_entity, color)
                    self.update_color_button(color)
                    return
                
                # Appliquer directement à l'entité
                if hasattr(self.current_entity, "set_color"):
                    self.current_entity.set_color(color)
                else:
                    self.current_entity.color = color.name(QColor.HexArgb)
                
                # Redessiner immédiatement
                if hasattr(self.current_entity, "draw") and hasattr(self.current_entity, "scene_ref") and self.current_entity.scene_ref:
                    self.current_entity.draw(self.current_entity.scene_ref)
                
                # Notifier le reste de l'app (undo/redo, légende, quantitatif)
                self.colorChanged.emit(self.current_entity, color)
                
                # Rafraîchir l'icône bouton couleur
                self.update_color_button(color)
                
            except Exception as e:
                import traceback
                traceback.print_exc()

    def on_thickness_changed(self, value):
        """Met à jour l'épaisseur de ligne (périmètre uniquement)."""
        if self.updating_ui:
            return
        if not self.current_entity:
            return
        try:
            # Limiter aux périmètres et distances
            is_perimeter = (
                (hasattr(self.current_entity, 'is_perimeter') and self.current_entity.is_perimeter)
                or getattr(self.current_entity, 'entity_type', '') == 'perimeter'
            )
            is_line = getattr(self.current_entity, 'entity_type', '') == 'line'

            if not is_perimeter and not is_line:
                return

            width_val = max(5, min(30, int(value)))
            
            # Appliquer immédiatement à l'entité
            if hasattr(self.current_entity, "set_width"):
                self.current_entity.set_width(width_val)
            else:
                self.current_entity.width = width_val

            # Redessiner immédiatement
            if hasattr(self.current_entity, "draw") and hasattr(self.current_entity, "scene_ref") and self.current_entity.scene_ref:
                self.current_entity.draw(self.current_entity.scene_ref)

            # Propager au reste de l'appli (undo/redo, légende, quantitatif)
            if hasattr(self, 'widthChanged'):
                self.widthChanged.emit(self.current_entity, width_val)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _on_pattern_changed(self, index):
        """Applique le nouveau motif de remplissage à la surface sélectionnée."""
        if self.updating_ui:
            return
        if not self.current_entity:
            return
        try:
            pattern_key = self.pattern_combo.itemData(index)
            if not pattern_key:
                return

            # Appliquer le motif à l'entité
            self.current_entity.fill_pattern = pattern_key

            # Reconstruire le brush et rafraîchir l'affichage
            color_raw = getattr(self.current_entity, 'color', None)
            if isinstance(color_raw, str):
                from PyQt5.QtGui import QColor as _QColor
                color = _QColor(color_raw)
            elif color_raw is not None:
                color = color_raw
            else:
                from PyQt5.QtGui import QColor as _QColor
                color = _QColor(0, 200, 0, 150)

            if hasattr(self.current_entity, 'surface_item') and self.current_entity.surface_item:
                brush = make_brush(color, pattern_key)
                self.current_entity.surface_item.setBrush(brush)

            # Notifier (undo/redo, sauvegarde)
            self.patternChanged.emit(self.current_entity, pattern_key)

        except Exception:
            import traceback
            traceback.print_exc()

    def on_name_changed(self, text):
        """Quand le nom est modifié"""
        if not self.updating_ui and self.current_entity:
            try:
                # ✅ CORRECTION: Ne pas émettre si le texte est vide
                if not text or text.strip() == "":
                    # IMPORTANT: Restaurer le nom actuel dans le champ
                    self.updating_ui = True
                    self.name_edit.setText(self.current_entity.name)
                    self.updating_ui = False
                    return
                
                self.nameChanged.emit(self.current_entity, text)
            except Exception as e:
                pass

    def on_text_visibility_changed(self, state):
        """Quand l'affichage du texte (compteur) est modifié"""
        if not self.updating_ui and self.current_entity:
            try:
                is_visible = state == Qt.Checked
                if getattr(self.current_entity, 'entity_type', '') != 'point':
                    self.visibilityChanged.emit(
                        self.current_entity, is_visible)
                    return

                def apply_label_visibility(ent):
                    ent.show_label = is_visible
                    if hasattr(ent, 'name_item') and ent.name_item:
                        ent.name_item.setVisible(is_visible)
                    if hasattr(ent, 'debug') and ent.debug:
                        pass

                manager = None
                if self.main_window and hasattr(self.main_window, 'canvas_view'):
                    manager = getattr(
                        self.main_window.canvas_view, 'entity_manager', None)
                group_id = getattr(self.current_entity, 'group_id', None)
                if manager and not group_id:
                    group_id = manager.ensure_point_group(
                        getattr(self.current_entity, 'name', 'Compteur'))
                    self.current_entity.group_id = group_id

                if manager and group_id:
                    group_points = manager.get_points_by_group(group_id)
                    if group_points:
                        for point in group_points:
                            apply_label_visibility(point)
                    else:
                        apply_label_visibility(self.current_entity)
                else:
                    apply_label_visibility(self.current_entity)

                if hasattr(self.current_entity, 'scene_ref') and self.current_entity.scene_ref:
                    self.current_entity.scene_ref.update()
            except Exception as e:
                pass

    def on_dimension_changed(self, entity, editor: QLineEdit, attr_name: str):
        """
        Met à jour height/thickness et déclenche la mise à jour temps réel.
        
        IMPORTANT : Cette méthode propage automatiquement les dimensions :
        - Pour les compteurs : à tous les points du même groupe
        - Pour les surfaces/périmètres : du parent vers tous les enfants
        Cette logique est CRITIQUE pour le calcul correct des volumes dans les groupes.
        """
        if not entity or not editor:
            return
        try:
            text = editor.text().strip().replace(",", ".")
            value = float(text) if text else 0.0
        except ValueError:
            value = 0.0
            editor.setText("0.00")

        try:
            # Si c'est un compteur, propager à tout le groupe
            if getattr(entity, 'entity_type', '') == 'point':
                manager = None
                if self.main_window and hasattr(self.main_window, 'canvas_view'):
                    manager = getattr(
                        self.main_window.canvas_view, 'entity_manager', None)
                group_id = getattr(entity, 'group_id', None)
                if manager and not group_id:
                    group_id = manager.ensure_point_group(
                        getattr(entity, 'name', 'Compteur'))
                    entity.group_id = group_id
                if manager and group_id:
                    group_points = manager.get_points_by_group(group_id)
                    if group_points:
                        for point in group_points:
                            setattr(point, attr_name, value)
                    else:
                        setattr(entity, attr_name, value)
                else:
                    setattr(entity, attr_name, value)
            else:
                # Pour les surfaces et périmètres : remonter à la racine du groupe
                # puis appliquer la valeur à TOUS les membres (parent + enfants)
                grp_root = entity
                while getattr(grp_root, "parent_entity", None) is not None:
                    grp_root = grp_root.parent_entity

                all_members = [grp_root] + list(getattr(grp_root, "child_entities", None) or [])
                for member in all_members:
                    setattr(member, attr_name, value)

            # ── Récupérer le main_window ──────────────────────────────────────
            mw = None
            if hasattr(entity, 'scene_ref') and entity.scene_ref \
                    and hasattr(entity.scene_ref, 'main_window'):
                mw = entity.scene_ref.main_window
            if mw is None and self.main_window:
                mw = self.main_window

            if mw:
                em = None
                if hasattr(mw, 'canvas_view'):
                    em = getattr(mw.canvas_view, 'entity_manager', None)

                if getattr(entity, 'entity_type', '') == 'point':
                    # Compteurs : notifier tous les points du groupe
                    group_id = getattr(entity, 'group_id', None)
                    if em and group_id:
                        for pt in em.get_points_by_group(group_id):
                            if hasattr(em, 'notify_entity_modified'):
                                em.notify_entity_modified(pt)
                    elif hasattr(mw, 'on_entity_modified'):
                        mw.on_entity_modified(entity)
                else:
                    # Surfaces / périmètres : notifier tous les membres du groupe
                    # + déclencher on_entity_modified sur la racine pour Pages & Mesures
                    for member in all_members:
                        # Rafraîchir la bulle texte sur le canvas si c'est une surface
                        if hasattr(member, 'draw_text') and hasattr(member, 'scene_ref') \
                                and member.scene_ref is not None:
                            try:
                                member.draw_text(member.scene_ref)
                            except Exception:
                                pass
                        elif hasattr(member, 'update_text_display'):
                            try:
                                member.update_text_display()
                            except Exception:
                                pass
                        if em and hasattr(em, 'notify_entity_modified'):
                            em.notify_entity_modified(member)

                    if hasattr(mw, 'on_entity_modified'):
                        mw.on_entity_modified(grp_root)
                    # Forcer aussi un refresh complet de la légende pour les changements
                    # d'unité (m² -> m³, m -> m²/m³, etc.)
                    if hasattr(mw, 'update_quantities_table'):
                        mw.update_quantities_table()
                    if hasattr(mw, 'force_refresh_quantities_ui'):
                        mw.force_refresh_quantities_ui()

                # Rafraîchir le panneau propriétés sur l'entité réellement cliquée
                if hasattr(mw, 'properties_dock') and mw.properties_dock.current_entity is entity:
                    mw.properties_dock.display_entity_properties(entity)
        except Exception as e:
            pass

    def select_entity(self, entity):
        """Sélectionne une entité spécifique et affiche ses propriétés"""
        if not entity:
            self.clear_selection()
            return

        try:
            # Toujours afficher l'entité réellement cliquée (parent OU enfant)
            entity_name = getattr(entity, 'name', 'Sans nom')
            entity_type = getattr(entity, 'entity_type', 'inconnu')

            self.current_entity = entity
            self.display_entity_properties(entity)

            # Synchroniser la combo box
            self.updating_ui = True
            entity_id = getattr(entity, 'entity_id', None)
            if entity_id:
                for i in range(self.entity_combo.count()):
                    if self.entity_combo.itemData(i) == entity_id:
                        self.entity_combo.setCurrentIndex(i)
                        break
            self.updating_ui = False

            # Mettre à jour l'affichage du titre
            self.selection_label.setText(
                f"Élément sélectionné: {entity_name} ({entity_type})")
        except Exception as e:
            pass

    def clear_selection(self):
        """Efface la sélection courante"""
        try:
            self.current_entity = None
            self.effacer_affichage()
            self.entity_combo.setCurrentIndex(0)
        except Exception:
            pass
