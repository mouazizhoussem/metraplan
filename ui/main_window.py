# ui/main_window.py
import sys
import time
from PyQt5.QtWidgets import (QMainWindow, QAction, QLabel,
                             QStatusBar, QFileDialog, QMessageBox, QDockWidget,
                             QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
                             QHBoxLayout, QPushButton, QColorDialog, QSizePolicy,
                             QDialog, QInputDialog, QHeaderView, QComboBox, QProgressDialog,
                             QFrame, QSplitter, QStackedWidget,
                             QApplication)
from PyQt5.QtCore import Qt, QSize, QPointF, QEvent
from PyQt5.QtGui import QIcon, QColor, QPixmap

from core.canvas_view import CanvasView
from core.project_manager import (
    PROJECT_FILTER,
    ensure_project_extension,
    load_project as load_project_file,
    save_project as save_project_file,
)
from ui.property_panel import PropertyPanel
from ui.toolbar_factory import build_main_toolbar
from ui.legend_quantities import LegendQuantitiesHelper
from ui.selection_helper import SelectionHelper
from services.pdf_converter import PDFConverter
from models.pdf_document import PDFDocument, PDFPage
from ui.pdf_measurements_panel import PDFMeasurementsPanel
from ui.dialogs.import_pdf_dialog import ImportPDFDialog
from entities.opening_entity import OpeningEntity
from ui.page_tab_bar import PageTabBar
import uuid


class _LegendResizeBar(QFrame):
    """Barre de redimensionnement en bas du panneau Relevé quantitatif.
    • Double-clic  => toggle handles / affiche l'état actif
    • Drag (quand actif) => redimensionne la largeur ET la hauteur du dock
    """

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._mw = main_window
        self.setFixedHeight(22)
        self._update_style(False)

        from PyQt5.QtWidgets import QHBoxLayout
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(10, 0, 10, 0)
        self._lbl = QLabel("↕  Double-clic pour redimensionner")
        self._lbl.setStyleSheet("color:#1565C0; font-size:10px;")
        lyt.addWidget(self._lbl)

        self._drag = False
        self._start_global = None
        self._start_h = 0
        self._start_w = 0

    def _update_style(self, active):
        if active:
            self.setStyleSheet(
                "QFrame { background:#BBDEFB; border-top:2px solid #1565C0; border-radius:2px; }")
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setStyleSheet(
                "QFrame { background:#E3F2FD; border-top:1px solid #90CAF9; border-radius:2px; }")
            self.setCursor(Qt.PointingHandCursor)

    def set_active(self, active):
        self._update_style(active)
        if active:
            self._lbl.setText("↕↔  Glisser pour redimensionner  •  Double-clic pour masquer")
        else:
            self._lbl.setText("↕  Double-clic pour redimensionner")

    def mouseDoubleClickEvent(self, event):
        before = getattr(self._mw, "_legend_handles_visible", False)
        self._mw._set_legend_handles_visible(not before)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and getattr(self._mw, "_legend_handles_visible", False):
            self._drag = True
            self._start_global = event.globalPos()
            self._start_h = self._mw.quantities_dock.height()
            self._start_w = self._mw.quantities_dock.width()
            self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._drag or self._start_global is None:
            return
        dx = event.globalPos().x() - self._start_global.x()
        dy = event.globalPos().y() - self._start_global.y()
        tw = max(280, min(1200, self._start_w + dx))
        th = max(180, min(1200, self._start_h + dy))
        self._mw._apply_legend_size(width=tw, height=th)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag:
            try:
                self.releaseMouse()
            except Exception:
                pass
            self._drag = False
            self._start_global = None
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Metraplan")
        self.setGeometry(100, 100, 1200, 800)

        # ── Persistance fenêtre & fichiers récents ────────────────────────────
        from PyQt5.QtCore import QSettings
        self._settings = QSettings("Metraplan", "Metraplan4")
        self._recent_files: list[str] = list(
            self._settings.value("recent_files", []) or [])
        self._MAX_RECENT = 8

        # Initialisation de la vue Canvas
        self.canvas_view = CanvasView(self)

        # ── Barre d'onglets au-dessus du canvas ───────────────────────────
        self._page_tab_bar = PageTabBar(self)
        self._page_tab_bar.hide()   # invisible au démarrage (aucune page)

        # Conteneur : tab bar + canvas empilés verticalement
        self._canvas_container = QWidget()
        _cc_layout = QVBoxLayout(self._canvas_container)
        _cc_layout.setContentsMargins(0, 0, 0, 0)
        _cc_layout.setSpacing(0)
        _cc_layout.addWidget(self._page_tab_bar)
        _cc_layout.addWidget(self.canvas_view, 1)

        # ── Vue centrale empilée : canvas (0) | Devis (1) | Rapport (2) ──────
        # Les panneaux Devis et Rapport seront insérés dans ce stack par
        # _create_devis_dock / _create_report_dock après initialisation.
        self._view_stack = QStackedWidget()
        self._view_stack.addWidget(self._canvas_container)   # index 0 = canvas + tabs
        self.setCentralWidget(self._view_stack)

        # Connecter les signaux de la barre d'onglets
        # page_changed émet l'indice dans la tab bar (→ mappé vers _all_pages via _open_tabs)
        self._page_tab_bar.page_changed.connect(self._on_tab_selected)
        self._page_tab_bar.page_closed.connect(self._on_tab_page_closed)
        self._page_tab_bar.page_add_requested.connect(self._on_tab_add_page)
        self._page_tab_bar.page_renamed.connect(self._on_tab_page_renamed)
        self._page_tab_bar.page_moved.connect(self._on_tab_page_moved)

        # État de visibilité des docks latéraux avant bascule plein écran
        self._side_docks_visible: dict = {}

        # ✅ NOUVEAU: Timer pour débounce des mises à jour ultra-rapides
        from PyQt5.QtCore import QTimer
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(8)  # ~120 FPS pour plus de réactivité
        self._update_timer.timeout.connect(self._do_deferred_update)
        self._pending_update = False

        # ── Autosave toutes les 10 minutes ────────────────────────────────────
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(10 * 60 * 1000)   # 10 min en ms
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()
        self._last_grouped_data = []  # Cache pour mise à jour intelligente
        self._last_quantities_sync_feedback_ts = 0.0

        # Dans __init__, après la ligne 31 (après self._last_grouped_data = [])
        # Ajouter les attributs pour copier/coller
        self.clipboard_entity = None  # Entité copiée
        self.cut_mode = False  # True si c'est un couper (pas un copier)

        # ✅ NOUVEAU : Gestionnaire Undo/Redo
        from core.undo_redo_manager import UndoRedoManager
        self.undo_redo_manager = UndoRedoManager(max_history=50)

        # ✅ NOUVEAU: Gestionnaire PDF
        self.pdf_converter = PDFConverter()
        self.pdf_document = None
        self.current_pdf_page_index = None
        self._pdf_file_path = None
        self._project_file_path = None
        self._unsaved_changes = False   # True dès qu'une modification non sauvegardée existe
        self.aggregate_pdf_quantities = True
        self.pdf_progress_dialog = None  # Dialogue de progression pour l'import PDF

        # Liste maîtresse de toutes les pages (multi-import PDF + images)
        self._all_pages: list = []
        self._pdf_import_offset: int = 0  # index de départ lors d'un import PDF
        # Indices des pages actuellement ouvertes comme onglets (sous-ensemble de _all_pages)
        self._open_tabs: list = []

        self.pdf_converter.conversion_started.connect(
            self.on_pdf_conversion_started)
        self.pdf_converter.page_converted.connect(
            self.on_pdf_page_converted)
        self.pdf_converter.conversion_finished.connect(
            self.on_pdf_conversion_finished)
        self.pdf_converter.conversion_error.connect(
            self.on_pdf_conversion_error)

        # Helpers UI
        self.selection_helper = SelectionHelper(self)

        # Initialisation de l'interface
        self.init_ui()

        # Configuration des références
        self.setup_scene_references()

    def setup_scene_references(self):
        """Configure les références entre les composants"""
        if hasattr(self.canvas_view, 'scene'):
            # Passer la référence à la fenêtre principale et au gestionnaire d'entités
            self.canvas_view.scene.main_window = self
            if hasattr(self.canvas_view, 'entity_manager'):
                self.canvas_view.scene.entity_manager = self.canvas_view.entity_manager

                # ✅ NOUVEAU : Référence bidirectionnelle pour Undo/Redo
                self.canvas_view.entity_manager.main_window = self

            # Connecter le signal entitySelected de la scène
            if hasattr(self.canvas_view.scene, 'entitySelected'):
                self.canvas_view.scene.entitySelected.connect(
                    self.on_entity_selected_from_scene)
  
            # ✅ NOUVEAU : Connecter les signaux geometryChanged de toutes les entités existantes
            self.reconnect_all_entity_signals()

    def on_entity_selected_from_scene(self, entity):
        """Quand une entité est sélectionnée via clic dans la scène"""
        return self.selection_helper.on_entity_selected_from_scene(entity)

    def on_pdf_entity_selected_from_panel(self, entity):
        """
        Quand l'utilisateur clique une entité dans Pages & Mesures,
        afficher immédiatement toutes ses propriétés (comme un clic canvas).
        """
        if not entity:
            return
        try:
            # Réutiliser le chemin de sélection standard pour garder
            # un comportement homogène (propriétés, toolbar, etc.).
            self.on_entity_selected_from_scene(entity)
        except Exception:
            # Fallback robuste sur le panneau propriétés
            if hasattr(self, 'properties_dock') and self.properties_dock:
                self.properties_dock.select_entity(entity)
                self.properties_dock.display_entity_properties(entity)

    def on_entity_clicked(self, entity):
        """Callback lorsqu'une entité est cliquée sur la scène (méthode alternative)"""
        if hasattr(self, 'properties_dock'):
            self.properties_dock.select_entity(entity)

            # Mettre à jour la liste des entités pour synchroniser la combo box
            self.update_properties_entities_list()

    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.create_actions()
        self.create_menu()
        self.create_toolbar()
        self.create_statusbar()
        self.create_dock_widgets()
        self.create_quantities_dock()

        # Connecter les signaux du gestionnaire d'entités
        if hasattr(self.canvas_view, 'entity_manager'):
            self.canvas_view.entity_manager.entity_added.connect(
                self.on_entity_added)
            self.canvas_view.entity_manager.entity_removed.connect(
                self.on_entity_removed)
            # Vérifier si le signal entity_modified existe avant de le connecter
            if hasattr(self.canvas_view.entity_manager, 'entity_modified'):
                self.canvas_view.entity_manager.entity_modified.connect(
                    self.on_entity_modified)

        # Connecter les signaux selected des entités existantes
        self.setup_entity_signals()

    def setup_entity_signals(self):
        """Connecte les signaux selected des entités existantes"""
        return self.selection_helper.setup_entity_signals()

    def connect_entity_signals(self, entity):
        """Connecte les signaux d'une entité spécifique"""
        return self.selection_helper.connect_entity_signals(entity)

    def create_quantities_dock(self):
        """Crée le dock des quantités (maintenu en mémoire, non affiché)."""
        self.quantities_dock = QDockWidget("Relevé quantitatif")  # pas de parent = jamais affiché
        self.quantities_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Contenu
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        # Tableau
        self.quantities_table = QTableWidget()
        self.quantities_table.setColumnCount(5)
        self.quantities_table.setHorizontalHeaderLabels(
            ["Type", "Nom", "Quantité", "Prix unitaire", "Total"])

        # Édition autorisée uniquement pour "Prix unitaire"
        self.quantities_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)

        self.quantities_table.setAlternatingRowColors(True)
        self.quantities_table.setSelectionBehavior(QTableWidget.SelectRows)
        header = self.quantities_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Interactive)
        self.quantities_table.setColumnWidth(0, 90)
        self.quantities_table.setColumnWidth(1, 220)
        self.quantities_table.setColumnWidth(2, 100)
        self.quantities_table.setColumnWidth(3, 120)
        self.quantities_table.setColumnWidth(4, 120)

        # Ajout au layout
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Quantités mesurées:"))
        header_layout.addStretch()
        self.quantities_scope_combo = QComboBox()
        self.quantities_scope_combo.addItem("Page courante", "current")
        self.quantities_scope_combo.addItem("Toutes les pages", "all")
        self.quantities_scope_combo.setCurrentIndex(1 if self.aggregate_pdf_quantities else 0)
        self.quantities_scope_combo.currentIndexChanged.connect(
            self.on_quantities_scope_changed)
        header_layout.addWidget(self.quantities_scope_combo)
        layout.addLayout(header_layout)
        layout.addWidget(self.quantities_table)

        self.quantities_dock.setWidget(widget)
        self._legend_content_widget = widget
        self.quantities_dock.hide()  # s'assure qu'il n'apparaît jamais
        # Le dock N'EST PAS ajouté à la fenêtre (supprimé de l'UI).
        # quantities_table reste en mémoire pour que les appels update_quantities_table()
        # fonctionnent sans erreur, mais rien n'est affiché.

        # Initialiser le helper pour la légende canvas (utilisé par legend_widget)
        self.legend_quantities = LegendQuantitiesHelper(self)
        self._quantities_unit_prices = {}
        self._quantities_block_updates = False
        self.quantities_table.itemChanged.connect(self.on_quantities_price_changed)

        # Variables drag (conservées pour compatibilité)
        self._legend_drag_h = False
        self._legend_drag_v = False
        self._legend_drag_zone = False
        self._legend_drag_start_global = None
        self._legend_start_width = 0
        self._legend_start_height = 0
        self._legend_handles_visible = False

    def eventFilter(self, obj, event):
        # Toggle handles au double-clic dans le panneau de légende
        if event.type() == QEvent.MouseButtonDblClick:
            quantities_widget = getattr(getattr(self, "quantities_dock", None), "widget", lambda: None)()
            is_legend_object = obj in (
                getattr(self, "quantities_dock", None),
                getattr(self, "quantities_table", None),
                getattr(getattr(self, "quantities_table", None), "viewport", lambda: None)(),
                quantities_widget,
            )
            if not is_legend_object and quantities_widget is not None:
                try:
                    is_legend_object = bool(
                        hasattr(obj, "parent") and quantities_widget.isAncestorOf(obj))
                except Exception:
                    is_legend_object = False

            if is_legend_object:
                self._set_legend_handles_visible(not getattr(self, "_legend_handles_visible", False))
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def _set_legend_handles_visible(self, visible: bool):
        self._legend_handles_visible = bool(visible)
        # Notifier la barre de redimensionnement de son état actif/inactif
        if hasattr(self, "legend_resize_bar") and self.legend_resize_bar:
            self.legend_resize_bar.set_active(self._legend_handles_visible)
        if hasattr(self, "statusBar"):
            if self._legend_handles_visible:
                self.statusBar().showMessage(
                    "Mode redimensionnement actif — glisser la barre bleue  •  double-clic pour quitter", 2500)
            else:
                self.statusBar().showMessage("Mode redimensionnement désactivé", 1500)

    def _install_legend_dblclick_filters(self, root_widget):
        """Installe l'eventFilter double-clic sur tous les widgets du panneau."""
        if not root_widget:
            return
        try:
            root_widget.installEventFilter(self)
            for child in root_widget.findChildren(QWidget):
                child.installEventFilter(self)
            if hasattr(self, "quantities_table") and self.quantities_table:
                self.quantities_table.horizontalHeader().installEventFilter(self)
                self.quantities_table.verticalHeader().installEventFilter(self)
                self.quantities_table.viewport().installEventFilter(self)
        except Exception:
            pass

    def _on_legend_double_click(self, event):
        """Toggle explicite des handles de redimensionnement sur double-clic."""
        self._set_legend_handles_visible(not getattr(self, "_legend_handles_visible", False))
        try:
            event.accept()
        except Exception:
            pass

    def _on_legend_handle_h_press(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._legend_drag_h = True
        self._legend_drag_start_global = event.globalPos()
        self._legend_start_width = self.quantities_dock.width()
        try:
            self.legend_resize_h_handle.grabMouse()
        except Exception:
            pass
        event.accept()

    def _on_legend_handle_h_move(self, event):
        if not self._legend_drag_h or self._legend_drag_start_global is None:
            return
        dx = event.globalPos().x() - self._legend_drag_start_global.x()
        target = max(280, min(1200, self._legend_start_width + dx))
        self._apply_legend_size(width=target)
        event.accept()

    def _on_legend_handle_h_release(self, event):
        try:
            self.legend_resize_h_handle.releaseMouse()
        except Exception:
            pass
        self._legend_drag_h = False
        self._legend_drag_start_global = None
        event.accept()

    def _on_legend_handle_v_press(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._legend_drag_v = True
        self._legend_drag_start_global = event.globalPos()
        self._legend_start_height = self.quantities_dock.height()
        try:
            self.legend_resize_v_handle.grabMouse()
        except Exception:
            pass
        event.accept()

    def _on_legend_handle_v_move(self, event):
        if not self._legend_drag_v or self._legend_drag_start_global is None:
            return
        dy = event.globalPos().y() - self._legend_drag_start_global.y()
        target = max(180, min(1200, self._legend_start_height + dy))
        self._apply_legend_size(height=target)
        event.accept()

    def _on_legend_handle_v_release(self, event):
        try:
            self.legend_resize_v_handle.releaseMouse()
        except Exception:
            pass
        self._legend_drag_v = False
        self._legend_drag_start_global = None
        event.accept()

    def _on_legend_zone_press(self, event):
        """Début de redimensionnement auto (largeur + hauteur)."""
        if event.button() != Qt.LeftButton or not getattr(self, "_legend_handles_visible", False):
            return
        self._legend_drag_zone = True
        self._legend_drag_start_global = event.globalPos()
        self._legend_start_width = self.quantities_dock.width()
        self._legend_start_height = self.quantities_dock.height()
        try:
            self.legend_resize_zone.grabMouse()
        except Exception:
            pass
        event.accept()

    def _on_legend_zone_move(self, event):
        """Glisser la zone redimensionne automatiquement la légende."""
        if not self._legend_drag_zone or self._legend_drag_start_global is None:
            return
        dx = event.globalPos().x() - self._legend_drag_start_global.x()
        dy = event.globalPos().y() - self._legend_drag_start_global.y()
        target_w = max(280, min(1200, self._legend_start_width + dx))
        target_h = max(180, min(1200, self._legend_start_height + dy))
        self._apply_legend_size(width=target_w, height=target_h)
        event.accept()

    def _on_legend_zone_release(self, event):
        try:
            self.legend_resize_zone.releaseMouse()
        except Exception:
            pass
        self._legend_drag_zone = False
        self._legend_drag_start_global = None
        event.accept()

    def _apply_legend_size(self, width=None, height=None):
        """Applique la taille du dock + contenu de façon robuste."""
        try:
            if width is not None:
                w = int(max(280, min(1200, width)))
                self.quantities_dock.setMinimumWidth(280)
                self.quantities_dock.setMaximumWidth(16777215)
                self.resizeDocks([self.quantities_dock], [w], Qt.Horizontal)
                self.quantities_dock.resize(w, self.quantities_dock.height())
                if hasattr(self, "_legend_content_widget") and self._legend_content_widget:
                    self._legend_content_widget.setMinimumWidth(max(260, w - 18))

            if height is not None:
                h = int(max(180, min(1200, height)))
                # En mode docké, la hauteur peut être contrainte; on force surtout le contenu.
                self.quantities_dock.setMinimumHeight(180)
                self.quantities_dock.setMaximumHeight(16777215)
                self.resizeDocks([self.quantities_dock], [h], Qt.Vertical)
                self.quantities_dock.resize(self.quantities_dock.width(), h)
                if hasattr(self, "_legend_content_widget") and self._legend_content_widget:
                    self._legend_content_widget.setMinimumHeight(max(150, h - 26))
                    self._legend_content_widget.resize(
                        self._legend_content_widget.width(),
                        max(150, h - 26)
                    )
                if hasattr(self, "quantities_table") and self.quantities_table:
                    self.quantities_table.setMinimumHeight(max(120, h - 90))
        except Exception as e:
            pass

    # ------------------------------------------------------------------
    # Helpers pour réafficher les docks depuis le menu Affichage
    # ------------------------------------------------------------------
    def show_properties_dock(self):
        """Réaffiche le dock des propriétés"""
        if not getattr(self, "properties_dock", None):
            # Recréer si besoin
            self.properties_dock = PropertyPanel(self)
            self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.properties_dock.show()
        self.properties_dock.raise_()
        self.properties_dock.activateWindow()

    def show_quantities_dock(self):
        """Réaffiche le dock du relevé quantitatif"""
        if not getattr(self, "quantities_dock", None):
            self.create_quantities_dock()
        self.quantities_dock.show()
        self.quantities_dock.raise_()
        self.quantities_dock.activateWindow()

    def on_quantities_scope_changed(self):
        """Change le périmètre du relevé quantitatif (page courante / toutes pages)."""
        if not hasattr(self, 'quantities_scope_combo'):
            return
        scope = self.quantities_scope_combo.currentData()
        self.aggregate_pdf_quantities = (scope == "all")
        self._sync_current_pdf_page_entities_for_quantities(
            notify=True, reason="mode")
        self.update_quantities_table()

    def _show_quantities_sync_feedback(self, reason="", force=False):
        """Affiche un feedback discret de synchro dans la barre de statut."""
        if not self.aggregate_pdf_quantities:
            return
        now = time.monotonic()
        if not force and (now - self._last_quantities_sync_feedback_ts) < 1.2:
            return
        self._last_quantities_sync_feedback_ts = now
        suffix = f" ({reason})" if reason else ""
        try:
            self.statusBar().showMessage(
                f"Relevé toutes pages synchronisé{suffix}", 1200)
        except Exception:
            pass

    def _sync_current_pdf_page_entities_for_quantities(self, notify=False, reason=""):
        """Synchronise la page PDF courante pour le mode agrégé sans effet de bord."""
        if not self.aggregate_pdf_quantities:
            return
        if getattr(self, '_is_switching_pdf_page', False):
            return
        if not self._all_pages or self.current_pdf_page_index is None:
            return
        try:
            self._save_current_page_entities()
            if notify:
                self._show_quantities_sync_feedback(reason=reason)
        except Exception as e:
            pass

    def show_pdf_dock(self):
        """Réaffiche le dock Pages & Mesures."""
        if not getattr(self, "pdf_dock", None):
            self.pdf_navigator = PDFMeasurementsPanel(self)
            self.pdf_dock = QDockWidget("Pages & Mesures", self)
            self.pdf_dock.setWidget(self.pdf_navigator)
            self.pdf_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
            self.addDockWidget(Qt.LeftDockWidgetArea, self.pdf_dock)
            self.pdf_navigator.page_selected.connect(self.on_pdf_page_selected)
            self.pdf_navigator.entity_selected.connect(self.on_pdf_entity_selected_from_panel)
            self.pdf_navigator.rename_requested.connect(self.on_pdf_rename_page)
            self.pdf_navigator.delete_requested.connect(self.on_pdf_delete_page)
            self.pdf_navigator.duplicate_requested.connect(self.on_pdf_duplicate_page)
            self.pdf_navigator.add_pdf_requested.connect(self.import_pdf)
            self.pdf_navigator.add_img_requested.connect(self.open_image)
            self.pdf_navigator.move_page_requested.connect(self.on_pdf_move_page)
        self.pdf_dock.show()
        self.pdf_dock.raise_()
        self.pdf_dock.activateWindow()
        # Afficher le panneau propriétés avec le plan
        if hasattr(self, 'properties_dock') and self.properties_dock:
            self.properties_dock.show()

    def update_properties_panel(self, entity):
        """Met à jour le panneau de propriétés - appelé par CanvasScene"""

        if not hasattr(self, 'properties_dock') or not self.properties_dock:
            return

        try:
            # Afficher les propriétés de l'entité
            self.properties_dock.display_entity_properties(entity)

            # Mettre à jour la liste des entités (pour synchroniser la combo box)
            self.update_properties_entities_list()

            # Sélectionner l'entité dans la combo box
            self.select_entity_in_combo(entity)


        except Exception as e:
            pass

    def select_entity_in_combo(self, entity):
        """Sélectionne une entité dans la combo box du PropertyPanel"""
        if not hasattr(self, 'properties_dock') or not self.properties_dock:
            return

        try:
            entity_id = getattr(entity, 'entity_id', None)
            if entity_id:
                # Parcourir la combo box pour trouver l'entité
                for i in range(self.properties_dock.entity_combo.count()):
                    if self.properties_dock.entity_combo.itemData(i) == entity_id:
                        self.properties_dock.entity_combo.setCurrentIndex(i)
                        break
        except Exception as e:
            pass

    def on_entity_added(self, entity):
        """Appelé quand une nouvelle entité est ajoutée"""
        if not entity:
            return

        self._unsaved_changes = True
        self._connect_entity_signals_safe(entity)
        # Assurer la synchro immédiate des données page -> relevé "Toutes les pages"
        self._sync_current_pdf_page_entities_for_quantities()
        self.update_quantities_table()
        self.update_properties_entities_list()

        self._handle_undo_redo_registration(entity)

    def _connect_entity_signals_safe(self, entity):
        """Connecte les signaux de l'entité (geometryChanged + selection)."""
        if hasattr(entity, 'geometryChanged'):
            try:
                entity.geometryChanged.connect(
                    lambda ent=entity: self.on_entity_modified(ent))
            except Exception as e:
                pass

        self.selection_helper.connect_entity_signals(entity)

    def _handle_undo_redo_registration(self, entity):
        """Enregistre l'entité dans l'historique Undo/Redo si activé."""
        if not hasattr(self, 'undo_redo_manager') or not entity:
            return
        if not self.undo_redo_manager._enabled:
            return

        if self._should_skip_opening_recording(entity):
            return

        try:
            from core.undo_redo_manager import AddEntityCommand

            entity_data = self._snapshot_entity_for_undo(entity)

            command = AddEntityCommand(
                self.canvas_view.entity_manager,
                self.canvas_view.scene,
                entity_data,
                description=f"Créer '{entity.name}'"
            )

            command.entity_id = entity.entity_id
            command.entity = entity

            self.undo_redo_manager.push_command(command)

        except Exception as e:
            import traceback
            traceback.print_exc()

    def _should_skip_opening_recording(self, entity):
        """Vrai si l'ouverture ne doit pas être enregistrée séparément (déjà dans la surface)."""
        if getattr(entity, 'entity_type', None) != 'opening':
            return False
        if hasattr(entity, 'parent_surface') and entity.parent_surface:
            self._update_parent_surface_snapshot(entity.parent_surface, entity)
            return True
        return False

    def _snapshot_entity_for_undo(self, entity):
        """Construit le snapshot utilisé par AddEntityCommand."""
        from PyQt5.QtCore import Qt
        import copy

        # CORRIGER: Gérer le cas où entity.color est une string
        entity_color = '#000000'
        if hasattr(entity, 'color'):
            if isinstance(entity.color, str):
                entity_color = entity.color
            elif isinstance(entity.color, QColor):
                entity_color = entity.color.name(QColor.HexArgb)

        entity_data = {
            'type': entity.entity_type,
            'entity_type': entity.entity_type,
            'entity_id': getattr(entity, 'entity_id', None),
            'name': entity.name,
            'visible': getattr(entity, 'visible', True),
            'points': [(p.x(), p.y()) for p in entity.points] if hasattr(entity, 'points') else None,
            'start_point': (entity.start_point.x(), entity.start_point.y()) if hasattr(entity, 'start_point') else None,
            'end_point': (entity.end_point.x(), entity.end_point.y()) if hasattr(entity, 'end_point') else None,
            'color': entity_color,
            'pixels_per_meter': getattr(entity, 'pixels_per_meter', 1.0),
            'width': getattr(entity, 'width', 2),
            'fill_pattern': getattr(entity, 'fill_pattern', Qt.SolidPattern),
            'is_perimeter': getattr(entity, 'is_perimeter', False),
            'reference_distance': getattr(entity, 'reference_distance', 0),
            'counter_items': [(item.x(), item.y()) for item in entity.counter_items] if hasattr(entity, 'counter_items') else [],
            'height': float(getattr(entity, 'height', 0.0)),
            'thickness': float(getattr(entity, 'thickness', 0.0)),
            'length': float(getattr(entity, 'length', 0.0)),
            'openings': [],
            'linear_openings': [],
            'is_group_parent': getattr(entity, 'is_group_parent', False),
            'group_id': getattr(entity, 'group_id', None),
            'parent_entity_id': getattr(entity.parent_entity, 'entity_id', None) if hasattr(entity, 'parent_entity') and entity.parent_entity else None,
            'child_entity_ids': [child.entity_id for child in getattr(entity, 'child_entities', [])]
        }

        if entity.entity_type == 'polygon' and hasattr(entity, 'openings') and entity.openings:
            for opening in entity.openings:
                # CORRIGER: Gérer le cas où opening.color est une string
                opening_color = '#ff0000'
                if hasattr(opening, 'color'):
                    if isinstance(opening.color, str):
                        opening_color = opening.color
                    elif isinstance(opening.color, QColor):
                        opening_color = opening.color.name(QColor.HexArgb)

                entity_data['openings'].append({
                    'points': [(p.x(), p.y()) for p in opening.points],
                    'name': opening.name,
                    'color': opening_color,
                    'pixels_per_meter': opening.pixels_per_meter
                })

        if entity.entity_type == 'perimeter' and hasattr(entity, 'linear_openings') and entity.linear_openings:
            entity_data['linear_openings'] = copy.deepcopy(
                entity.linear_openings)

        return entity_data

    def on_entity_modified(self, entity):
        """
        Callback lorsqu'une entité est modifiée.

        Gère la mise à jour en temps réel :
        - Légende : immédiate (pas de débounce)
        - Relevé quantitatif : différé de 500 ms (débounce pour performance)
        - Propriétés : immédiate si l'entité est sélectionnée
        """
        self._unsaved_changes = True
        # Légende immédiate (très rapide, pas de débounce)
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'update_legend'):
            self.canvas_view.update_legend()

        # Maintenir les données de la page courante à jour pour le mode "Toutes les pages"
        self._sync_current_pdf_page_entities_for_quantities()

        # ✅ OPTIMISATION 2: Relevé quantitatif avec débounce intelligent
        if not self._pending_update:
            self._pending_update = True
            self._update_timer.start()

        # Mettre à jour les propriétés si cette entité est sélectionnée (sans débounce)
        if hasattr(self, 'properties_dock') and self.properties_dock.current_entity == entity:
            self.properties_dock.display_entity_properties(entity)

        # Mise à jour immédiate des quantités dans Pages & Mesures (sans débounce)
        if hasattr(self, 'pdf_navigator'):
            self.pdf_navigator.update_quantities(entity)

        # ✅ IMPORTANT : Mettre à jour le snapshot Undo/Redo avec la géométrie actuelle
        self._refresh_entity_geometry_snapshot(entity)

    def _do_deferred_update(self):
        """Effectue la mise à jour différée (appelée par le timer)"""
        self._pending_update = False

        # Garantir que l'agrégation lit les dernières entités de la page active.
        self._sync_current_pdf_page_entities_for_quantities(
            notify=True, reason="temps réel")

        # ✅ Mise à jour intelligente : valeurs uniquement si possible
        self.update_quantities_values_only()
    def force_refresh_quantities_ui(self):
        """Force un rafraîchissement visuel complet du relevé quantitatif."""
        try:
            self.update_quantities_table()
            if hasattr(self, "quantities_table") and self.quantities_table:
                self.quantities_table.viewport().repaint()
                self.quantities_table.repaint()
            QApplication.processEvents()
        except Exception as e:
            pass

    def prompt_opening_height(self, default_value=2.10):
        """Boîte de dialogue pour saisir la hauteur d'une ouverture (m). Retourne None si annulé."""
        try:
            val, ok = QInputDialog.getDouble(
                self,
                "Hauteur de l'ouverture",
                "Saisir la hauteur de l'ouverture (m) :",
                float(default_value),
                0.0, 1000.0, 2
            )
            if ok:
                return val
        except Exception as e:
            pass
        return None

    def on_entity_removed(self, entity_id):
        """Appelé quand une entité est supprimée"""
        self._unsaved_changes = True
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'update_legend'):
            self.canvas_view.update_legend()

        # Logs de mise à jour supprimés : garder seulement les actions
        self.update_quantities_table()
        self.update_properties_entities_list()
        # ✅ CORRECTION : Supprimer le deuxième appel redondant
        # Log global supprimé

        if hasattr(self, 'properties_dock'):
            current = getattr(self.properties_dock, 'current_entity', None)
            current_id = getattr(current, 'entity_id',
                                 None) if current else None
            if current_id == entity_id:
                self.properties_dock.clear_selection()
                self.update_toolbar_selection(None)

    def update_quantities_table_for_entity(self, entity):
        """Met à jour uniquement l'entité en question dans le tableau"""
        return self.legend_quantities.update_quantities_table()

    def update_entity_row(self, entity):
        """Met à jour uniquement la ligne correspondant à une entité spécifique"""
        # Colonne Actions supprimée -> rafraîchir l'ensemble
        self.update_quantities_table()

    def update_table_row(self, row, entity):
        """Met à jour une ligne spécifique du tableau"""
        return self.legend_quantities.update_table_row(row, entity)

    def update_quantities_table(self):
        """Met à jour le tableau des quantités avec toutes les entités"""
        return self.legend_quantities.update_quantities_table()

    def update_quantities_table_fast(self):
        """Version ultra-rapide de la mise à jour - VALEURS UNIQUEMENT si structure identique"""
        return self.legend_quantities.update_quantities_table_fast()

    def update_quantities_values_only(self):
        """Met à jour UNIQUEMENT les valeurs sans recréer le tableau (ultra-rapide)"""
        return self.legend_quantities.update_quantities_values_only()

    def on_quantities_price_changed(self, item):
        """Met à jour le total quand le prix unitaire change."""
        if getattr(self, '_quantities_block_updates', False):
            return
        if not item or item.column() != 3:
            return
        group_key = item.data(Qt.UserRole)
        if group_key is None:
            return
        try:
            text = item.text().replace(" ", "").replace("\u202f", "").replace(",", ".").strip()
            unit_price = float(text) if text else 0.0
        except ValueError:
            unit_price = 0.0
        self._quantities_unit_prices[group_key] = unit_price

        try:
            quantity_item = self.quantities_table.item(item.row(), 2)
            quantity_value = 0.0
            if quantity_item:
                quantity_value = float(quantity_item.data(Qt.UserRole) or 0.0)
            total = quantity_value * unit_price
            total_item = self.quantities_table.item(item.row(), 4)
            if total_item:
                self._quantities_block_updates = True
                item.setText(self.legend_quantities.format_number(unit_price))
                total_item.setText(self.legend_quantities.format_money(total))
                self.legend_quantities.update_grand_total_row()
                self._quantities_block_updates = False
        except Exception:
            self._quantities_block_updates = False

    def get_grouped_entities(self):
        """Regroupe les entités par group_id puis par nom/type - VERSION OPTIMISÉE"""
        return self.legend_quantities.get_grouped_entities()

    def get_entity_numeric_value(self, entity):
        """Récupère la valeur numérique d'une entité - TOUJOURS avec surface nette"""
        return self.legend_quantities.get_entity_numeric_value(entity)

    def delete_entity_group(self, entities):
        """Supprime un groupe d'entités (toutes celles ayant le même nom)"""
        return self.legend_quantities.delete_entity_group(entities)

    def delete_entity(self, entity):
        """Supprime une entité depuis le tableau"""
        if hasattr(entity, 'entity_id') and hasattr(self.canvas_view, 'entity_manager'):
            entity_id = entity.entity_id
            self.canvas_view.entity_manager.remove_entity(
                entity_id, self.canvas_view.scene)
            self.update_quantities_table()

            # Mettre à jour aussi l'affichage principal
            self.canvas_view.clean_orphaned_items()

    def create_actions(self):
        """Crée les actions de menu"""
        from ui.ribbon_icons import get_icon

        # Action Ouvrir
        self.open_action = QAction(get_icon("open"), "Ouvrir plan", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.setStatusTip("Ouvrir une image (JPG, PNG, TIFF…)")
        self.open_action.triggered.connect(self.open_image)

        # Action Importer PDF
        self.import_pdf_action = QAction(get_icon("import_pdf"), "PDF", self)
        self.import_pdf_action.setShortcut("Ctrl+I")
        self.import_pdf_action.setStatusTip("Importer un PDF multi-pages")
        self.import_pdf_action.triggered.connect(self.import_pdf)

        # Actions Sauvegarde / Chargement de projet
        self.new_project_action = QAction(get_icon("new_project"), "Nouveau", self)
        self.new_project_action.setShortcut("Ctrl+N")
        self.new_project_action.setStatusTip("Créer un nouveau projet vide")
        self.new_project_action.triggered.connect(self.new_project)

        self.save_project_action = QAction(get_icon("save"), "Enregistrer", self)
        self.save_project_action.setShortcut("Ctrl+S")
        self.save_project_action.setStatusTip("Enregistrer le projet (.mtp)")
        self.save_project_action.triggered.connect(self.save_project)

        self.save_project_as_action = QAction(get_icon("save_as"), "Enreg. sous…", self)
        self.save_project_as_action.setShortcut("Ctrl+Shift+S")
        self.save_project_as_action.setStatusTip("Enregistrer sous un nouveau nom")
        self.save_project_as_action.triggered.connect(self.save_project_as)

        self.load_project_action = QAction(get_icon("open_project"), "Ouvrir projet", self)
        self.load_project_action.setShortcut("Ctrl+Shift+O")
        self.load_project_action.setStatusTip("Ouvrir un projet Metraplan (.mtp)")
        self.load_project_action.triggered.connect(self.load_project)

        # Action Quitter
        self.quit_action = QAction(get_icon("quit"), "Quitter", self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.setStatusTip("Quitter l'application")
        self.quit_action.triggered.connect(self.close)

        # Actions des outils
        self.surface_action = QAction(get_icon("surface"), "Surface", self)
        self.surface_action.setCheckable(True)
        self.surface_action.setShortcut("S")
        self.surface_action.setStatusTip("Mesurer une surface polygonale")
        self.surface_action.triggered.connect(self.activate_surface_tool)

        self.distance_action = QAction(get_icon("distance"), "Distance", self)
        self.distance_action.setCheckable(True)
        self.distance_action.setShortcut("D")
        self.distance_action.setStatusTip("Mesurer une distance entre deux points")
        self.distance_action.triggered.connect(self.activate_distance_tool)

        self.counter_action = QAction(get_icon("counter"), "Compteur", self)
        self.counter_action.setCheckable(True)
        self.counter_action.setShortcut("C")
        self.counter_action.setStatusTip("Compter des éléments ponctuels")
        self.counter_action.triggered.connect(self.activate_counter_tool)

        self.scale_action = QAction(get_icon("scale"), "Échelle", self)
        self.scale_action.setCheckable(True)
        self.scale_action.setShortcut("E")
        self.scale_action.setStatusTip("Définir l'échelle du plan")
        self.scale_action.triggered.connect(self.activate_scale_tool)

        self.perimeter_action = QAction(get_icon("perimeter"), "Périmètre", self)
        self.perimeter_action.setCheckable(True)
        self.perimeter_action.setStatusTip("Mesurer un périmètre linéaire")
        self.perimeter_action.triggered.connect(self.activate_perimeter_tool)

        self.opening_action = QAction(get_icon("opening"), "Ouverture", self)
        self.opening_action.setCheckable(True)
        self.opening_action.setShortcut("W")
        self.opening_action.setStatusTip("Créer une ouverture à déduire d'une surface")
        self.opening_action.triggered.connect(self.activate_opening_tool)

        # ── Actions Navigation (Pointeur + Pan) ──────────────────────────────────
        self.pointer_action = QAction(get_icon("pointer"), "Pointeur", self)
        self.pointer_action.setCheckable(True)
        self.pointer_action.setShortcut("V")
        self.pointer_action.setStatusTip("Mode sélection — aucun outil de mesure actif")
        self.pointer_action.triggered.connect(self._activate_pointer_mode)

        self.pan_action = QAction(get_icon("pan"), "Déplacer", self)
        self.pan_action.setCheckable(True)
        self.pan_action.setShortcut("H")
        self.pan_action.setStatusTip("Déplacer la vue par cliquer-glisser (sans souris : H)")
        self.pan_action.triggered.connect(self._activate_pan_mode)

        # Action Mode Ortho
        self.ortho_action = QAction(get_icon("ortho"), "Ortho", self)
        self.ortho_action.setCheckable(True)
        self.ortho_action.setShortcut("Q")
        self.ortho_action.setStatusTip("Activer/désactiver le mode orthogonal (0°/90°)")
        self.ortho_action.triggered.connect(self.toggle_ortho_mode)

        # Action Effacer tout
        self.clear_action = QAction(get_icon("clear"), "Effacer", self)
        self.clear_action.setStatusTip("Effacer toutes les mesures de la page courante")
        self.clear_action.triggered.connect(self.clear_all)

        self.edit_scale_action = QAction(get_icon("scale"), "Modifier l'échelle", self)
        self.edit_scale_action.setStatusTip("Modifier l'échelle de mesure")
        self.edit_scale_action.triggered.connect(self.show_scale_editor)

        # Action Légende
        self.legend_action = QAction(get_icon("legend"), "Légende", self)
        self.legend_action.setCheckable(True)
        self.legend_action.setChecked(True)
        self.legend_action.setShortcut("Ctrl+L")
        self.legend_action.setStatusTip("Afficher/masquer la légende sur le canvas")
        self.legend_action.triggered.connect(self.toggle_legend)

        # ── Actions Zoom ──────────────────────────────────────────────────────────
        self.zoom_in_action = QAction(get_icon("zoom_in"), "Zoom +", self)
        self.zoom_in_action.setShortcut("Ctrl++")
        self.zoom_in_action.setStatusTip("Zoom avant")
        self.zoom_in_action.triggered.connect(
            lambda: self.canvas_view.zoom_in() if hasattr(self, 'canvas_view') else None)

        self.zoom_out_action = QAction(get_icon("zoom_out"), "Zoom −", self)
        self.zoom_out_action.setShortcut("Ctrl+-")
        self.zoom_out_action.setStatusTip("Zoom arrière")
        self.zoom_out_action.triggered.connect(
            lambda: self.canvas_view.zoom_out() if hasattr(self, 'canvas_view') else None)

        self.zoom_select_action = QAction(get_icon("zoom_select"), "Sélection", self)
        self.zoom_select_action.setStatusTip("Zoom sur une zone sélectionnée")
        self.zoom_select_action.triggered.connect(
            lambda: self.canvas_view.start_zoom_selection()
            if hasattr(self, 'canvas_view') else None)

        self.zoom_100_action = QAction(get_icon("zoom_100"), "100 %", self)
        self.zoom_100_action.setShortcut("Ctrl+0")
        self.zoom_100_action.setStatusTip("Afficher le plan à sa taille réelle (100 %)")
        self.zoom_100_action.triggered.connect(
            lambda: self.canvas_view.zoom_to_percent(100)
            if hasattr(self, 'canvas_view') else None)

        # ── Actions Annotation ────────────────────────────────────────────────────
        self.marker_action = QAction(get_icon("marker"), "Marqueur", self)
        self.marker_action.setCheckable(True)
        self.marker_action.setStatusTip("Surligner une zone rectangulaire du plan")
        self.marker_action.triggered.connect(self.activate_marker_tool)

        self.note_action = QAction(get_icon("note"), "Insérer une note", self)
        self.note_action.setCheckable(True)
        self.note_action.setStatusTip("Insérer un commentaire directement sur le plan")
        self.note_action.triggered.connect(self.activate_note_tool)

        # ── Action Imprimer ───────────────────────────────────────────────────────
        self.print_action = QAction(get_icon("print"), "Imprimer", self)
        self.print_action.setShortcut("Ctrl+P")
        self.print_action.setStatusTip("Imprimer la page courante avec ses mesures")
        self.print_action.triggered.connect(self.print_page)

        # ── Actions menu Fichier (complément) ────────────────────────────────────
        self.close_project_action = QAction("Fermer", self)
        self.close_project_action.setShortcut("Ctrl+W")
        self.close_project_action.setStatusTip(
            "Fermer le projet courant et revenir à l'écran d'accueil")
        self.close_project_action.triggered.connect(self.close_project)

        self.help_action = QAction("Aide", self)
        self.help_action.setShortcut("F1")
        self.help_action.setStatusTip("Afficher l'aide hors ligne")
        self.help_action.triggered.connect(self.show_help)

        self.tutorial_action = QAction("Tutoriel en ligne", self)
        self.tutorial_action.setStatusTip(
            "Accéder aux tutoriels vidéo en ligne")
        self.tutorial_action.triggered.connect(self.open_tutorial)

        self.about_action = QAction("À propos de Métraplan", self)
        self.about_action.setStatusTip(
            "Informations sur la version et la licence")
        self.about_action.triggered.connect(self.show_about)

        self.deactivate_action = QAction(
            "Désactiver / transférer la clé de produit", self)
        self.deactivate_action.setStatusTip(
            "Désactiver ce logiciel sur cet ordinateur")
        self.deactivate_action.triggered.connect(self.deactivate_license)

        # ── Actions onglet Page ──────────────────────────────────────────────────
        self.rotate_left_action = QAction("Gauche", self)
        self.rotate_left_action.setStatusTip("Pivoter la page de 90° à gauche")
        self.rotate_left_action.triggered.connect(lambda: self._rotate_page(-90))

        self.rotate_right_action = QAction("Droite", self)
        self.rotate_right_action.setStatusTip("Pivoter la page de 90° à droite")
        self.rotate_right_action.triggered.connect(lambda: self._rotate_page(90))

        self.rotate_180_action = QAction("180°", self)
        self.rotate_180_action.setStatusTip("Pivoter la page de 180°")
        self.rotate_180_action.triggered.connect(lambda: self._rotate_page(180))

        self.flip_h_action = QAction("Horizontal", self)
        self.flip_h_action.setStatusTip("Retourner la page horizontalement")
        self.flip_h_action.triggered.connect(lambda: self._flip_page(horizontal=True))

        self.flip_v_action = QAction("Vertical", self)
        self.flip_v_action.setStatusTip("Retourner la page verticalement")
        self.flip_v_action.triggered.connect(lambda: self._flip_page(horizontal=False))

        self.brightness_action = QAction("Luminosité", self)
        self.brightness_action.setStatusTip("Ajuster la luminosité de la page")
        self.brightness_action.triggered.connect(self._adjust_brightness)

        self.crop_page_action = QAction("Rogner", self)
        self.crop_page_action.setStatusTip("Rogner la page comme nouvelle page")
        self.crop_page_action.triggered.connect(self._crop_page)

        # ✅ NOUVEAU: Actions Copier/Coller/Couper
        self.copy_action = QAction("Copier", self)
        self.copy_action.setShortcut("Ctrl+C")
        self.copy_action.setStatusTip("Copier l'entité sélectionnée")
        self.copy_action.triggered.connect(self.copy_entity)

        self.cut_action = QAction("Couper", self)
        self.cut_action.setShortcut("Ctrl+X")
        self.cut_action.setStatusTip("Couper l'entité sélectionnée")
        self.cut_action.triggered.connect(self.cut_entity)

        self.paste_action = QAction("Coller", self)
        self.paste_action.setShortcut("Ctrl+V")
        self.paste_action.setStatusTip("Coller l'entité du presse-papier")
        self.paste_action.triggered.connect(self.paste_entity)

        # Ajouter les actions au widget pour qu'elles soient toujours actives
        self.addAction(self.copy_action)
        self.addAction(self.cut_action)
        self.addAction(self.paste_action)

        # Actions Undo/Redo
        self.undo_action = QAction(get_icon("undo"), "Annuler", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setStatusTip("Annuler la dernière action")
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False)

        self.redo_action = QAction(get_icon("redo"), "Refaire", self)
        self.redo_action.setShortcuts(["Ctrl+Y", "Ctrl+Shift+Z"])
        self.redo_action.setStatusTip("Refaire la dernière action annulée")
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setEnabled(False)

        # Ajouter les actions au widget
        self.addAction(self.undo_action)
        self.addAction(self.redo_action)

        # Connecter les signaux du gestionnaire Undo/Redo
        if hasattr(self, 'undo_redo_manager'):
            self.undo_redo_manager.canUndoChanged.connect(
                self.undo_action.setEnabled)
            self.undo_redo_manager.canRedoChanged.connect(
                self.redo_action.setEnabled)
            self.undo_redo_manager.historyChanged.connect(
                self.on_history_changed)

    def create_menu(self):
        """Crée les menus — barre masquée, les QAction restent actives (raccourcis clavier)."""
        menu_bar = self.menuBar()
        menu_bar.setVisible(False)   # masquer la barre, garder les raccourcis

        # ── Menu Fichier ──────────────────────────────────────────────────────
        file_menu = menu_bar.addMenu("Fichier")
        file_menu.setToolTipsVisible(True)

        # Nouveau
        self.new_project_action.setText("Nouveau")
        self.new_project_action.setShortcut("Ctrl+N")
        file_menu.addAction(self.new_project_action)

        # Ouvrir (projet .mtp)
        self.load_project_action.setText("Ouvrir…")
        self.load_project_action.setShortcut("Ctrl+O")
        self.load_project_action.setStatusTip(
            "Ouvrir un projet Métraplan (.mtp) existant")
        file_menu.addAction(self.load_project_action)

        # Fichiers récents
        self._recent_menu = file_menu.addMenu("Ouvrir récent")
        self._refresh_recent_menu()

        file_menu.addSeparator()

        # Enregistrer
        self.save_project_action.setText("Enregistrer")
        self.save_project_action.setShortcut("Ctrl+S")
        file_menu.addAction(self.save_project_action)

        # Enregistrer sous
        self.save_project_as_action.setText("Enregistrer sous…")
        self.save_project_as_action.setShortcut("Ctrl+Shift+S")
        file_menu.addAction(self.save_project_as_action)

        file_menu.addSeparator()

        # Fermer
        file_menu.addAction(self.close_project_action)

        file_menu.addSeparator()

        # Aide
        file_menu.addAction(self.help_action)

        # Tutoriel en ligne
        file_menu.addAction(self.tutorial_action)

        file_menu.addSeparator()

        # À propos
        file_menu.addAction(self.about_action)

        # Désactiver / transférer
        file_menu.addAction(self.deactivate_action)

        file_menu.addSeparator()

        # Quitter
        self.quit_action.setShortcut("Alt+F4")
        file_menu.addAction(self.quit_action)

        # ── Menu Affichage ────────────────────────────────────────────────────
        view_menu = menu_bar.addMenu("Affichage")
        view_menu.addAction(self.legend_action)
        view_menu.addSeparator()

        self.show_properties_action = QAction("Propriétés", self)
        self.show_properties_action.triggered.connect(self.show_properties_dock)
        view_menu.addAction(self.show_properties_action)

        self.show_pdf_action = QAction("Pages & Mesures", self)
        self.show_pdf_action.triggered.connect(self.show_pdf_dock)
        view_menu.addAction(self.show_pdf_action)

    def create_toolbar(self):
        """Crée la barre d'outils"""
        build_main_toolbar(self)

    def create_statusbar(self):
        """Crée la barre de statut enrichie"""
        sb = self.statusBar()
        sb.showMessage("Prêt — Ouvrez un plan pour commencer")

        # Outil actif (gauche)
        self.status_tool_label = QLabel("  Outil : Sélection")
        self.status_tool_label.setMinimumWidth(160)
        sb.addWidget(self.status_tool_label)

        # Séparateur
        sep1 = QLabel("│")
        sep1.setStyleSheet("color:#a0aabb; padding: 0;")
        sb.addWidget(sep1)

        # Coordonnées curseur (centre)
        self.status_coords_label = QLabel("X: —   Y: —")
        self.status_coords_label.setMinimumWidth(140)
        sb.addWidget(self.status_coords_label)

        # Label pour les mesures (historique)
        self.measure_label = QLabel("Aucune mesure")
        self.measure_label.setStyleSheet("color:#1e2130;")
        sb.addPermanentWidget(self.measure_label)

        # Échelle courante (permanent, droite)
        self.status_scale_label = QLabel("Échelle : N/D")
        self.status_scale_label.setObjectName("toolbarScale")
        self.status_scale_label.setMinimumWidth(130)
        sb.addPermanentWidget(self.status_scale_label)

        # Indicateur mode Ortho
        self.ortho_label = QLabel("ORTHO: OFF")
        self.ortho_label.setStyleSheet(
            "QLabel { background-color: lightgray; padding: 2px; }")
        self.statusBar().addPermanentWidget(self.ortho_label)

    def create_dock_widgets(self):
        """Crée les widgets ancrables"""
        # Dock widget pour les propriétés
        self.properties_dock = PropertyPanel(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.properties_dock)
        self.properties_dock.hide()  # masqué au démarrage, affiché quand un plan est chargé

        # Connecter les signaux du properties dock
        self.properties_dock.colorChanged.connect(self.on_entity_color_changed)
        self.properties_dock.nameChanged.connect(self.on_entity_name_changed)
        self.properties_dock.visibilityChanged.connect(
            self.on_measure_visibility_changed)
        self.properties_dock.widthChanged.connect(self.on_entity_width_changed)
        self.properties_dock.patternChanged.connect(self.on_entity_pattern_changed)

        # Panneau unifié Pages PDF + Mesures (remplace pdf_navigator + page_items_panel)
        self.pdf_navigator = PDFMeasurementsPanel(self)
        self.pdf_dock = QDockWidget("Pages & Mesures", self)
        self.pdf_dock.setWidget(self.pdf_navigator)
        self.pdf_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.pdf_dock.setMinimumWidth(280)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.pdf_dock)
        self.pdf_dock.hide()

        self.pdf_navigator.page_selected.connect(self.on_pdf_page_selected)
        self.pdf_navigator.entity_selected.connect(self.on_pdf_entity_selected_from_panel)
        self.pdf_navigator.rename_requested.connect(self.on_pdf_rename_page)
        self.pdf_navigator.delete_requested.connect(self.on_pdf_delete_page)
        self.pdf_navigator.duplicate_requested.connect(self.on_pdf_duplicate_page)
        self.pdf_navigator.add_pdf_requested.connect(self.import_pdf)
        self.pdf_navigator.add_img_requested.connect(self.open_image)
        self.pdf_navigator.move_page_requested.connect(self.on_pdf_move_page)

        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'entity_manager'):
            # Connecter le ScaleManager à l'EntityManager
            if hasattr(self.canvas_view, 'scale_manager'):
                self.canvas_view.entity_manager.scale_manager = self.canvas_view.scale_manager

            # Rafraîchissement en temps réel des mesures
            em = self.canvas_view.entity_manager
            # Correction C : bloquer refresh() pendant un switch de page.
            # Sans cette garde, entity_added déclenché pendant _restore_page_entities()
            # appelait refresh() avec l'ancien _current_index → reconstruisait l'item
            # de la MAUVAISE page avec les entités du canvas en cours de restauration.
            em.entity_added.connect(lambda _: (
                None if getattr(self, '_is_switching_pdf_page', False)
                else self.pdf_navigator.refresh()
            ))
            em.entity_removed.connect(lambda _: (
                None if getattr(self, '_is_switching_pdf_page', False)
                else self.pdf_navigator.refresh()
            ))
            # entity_modified → mise à jour rapide en place (pas de reconstruction)
            em.entity_modified.connect(
                lambda ent: (
                    None if getattr(self, '_is_switching_pdf_page', False)
                    else self.pdf_navigator.update_quantities(ent)
                ))

        # Connecter le signal entitySelected si disponible
        if hasattr(self.canvas_view, 'scene'):
            if hasattr(self.canvas_view.scene, 'entitySelected'):
                self.canvas_view.scene.entitySelected.connect(
                    self.on_entity_selected_from_scene)
            else:
                # Fallback: méthode legacy
                if hasattr(self.canvas_view.scene, 'selectionChanged'):
                    self.canvas_view.scene.selectionChanged.connect(
                        self.on_selection_changed)

        # ── Panneau Rapport de quantités ──────────────────────────────────────
        self._create_devis_dock()
        self._create_report_dock()

    # ── Bibliothèque de devis ─────────────────────────────────────────────────

    def _create_devis_dock(self):
        """Crée le panneau Devis plein écran (index 1 du view stack)."""
        from ui.devis_library_panel import DevisLibraryPanel
        self.devis_library_panel = DevisLibraryPanel(self)
        self._view_stack.insertWidget(1, self.devis_library_panel)
        self.devis_dock = None  # compat legacy

    # ── Rapport de quantités ──────────────────────────────────────────────────

    def _create_report_dock(self):
        """Crée le panneau Rapport plein écran (index 2 du view stack)."""
        from ui.report_panel import ReportPanel
        self.report_panel = ReportPanel(self)
        self._view_stack.insertWidget(2, self.report_panel)
        self.report_dock = None  # compat legacy

        # Rafraîchir le rapport automatiquement si affiché
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'entity_manager'):
            em = self.canvas_view.entity_manager
            em.entity_added.connect(self._auto_refresh_report)
            em.entity_removed.connect(self._auto_refresh_report)
            em.entity_modified.connect(self._auto_refresh_report)

        # Connecter le changement d'onglet du ruban via la référence directe
        ribbon_tab_bar = getattr(self, "ribbon_tab_bar", None)
        if ribbon_tab_bar is not None:
            ribbon_tab_bar.currentChanged.connect(self._on_ribbon_tab_changed)

    # ── Gestion des vues plein écran (Devis / Rapport) ───────────────────────

    def _collect_side_docks(self) -> list:
        """Retourne la liste des docks latéraux gérés (pages, propriétés…)."""
        docks = []
        for attr in ("pdf_dock", "properties_dock"):
            d = getattr(self, attr, None)
            if d is not None:
                docks.append(d)
        return docks

    def _enter_fullscreen_panel(self, view_index: int):
        """
        Bascule vers la vue plein écran (Devis ou Rapport) :
        - Sauvegarde la visibilité des docks latéraux UNIQUEMENT quand on vient
          du canvas (index 0), pour ne pas écraser la sauvegarde lors d'un
          passage Devis → Rapport ou Rapport → Devis.
        - Masque les docks latéraux et affiche le panneau demandé.
        """
        if self._view_stack.currentIndex() == 0:
            for dock in self._collect_side_docks():
                self._side_docks_visible[id(dock)] = dock.isVisible()
        for dock in self._collect_side_docks():
            dock.hide()
        self._view_stack.setCurrentIndex(view_index)

    def _leave_fullscreen_panel(self):
        """
        Revient au canvas (vue 0) et restaure la visibilité des docks latéraux.
        """
        self._view_stack.setCurrentIndex(0)
        for dock in self._collect_side_docks():
            was_visible = self._side_docks_visible.get(id(dock), True)
            dock.setVisible(was_visible)

    def _on_ribbon_tab_changed(self, index: int):
        """
        Onglet 0 = Fichier, 1 = Accueil, 2 = Page, 3 = Devis, 4 = Rapport
        """
        if index == 3:
            self._enter_fullscreen_panel(1)   # Devis
        elif index == 4:
            self._enter_fullscreen_panel(2)   # Rapport
            self.report_panel.refresh()
        else:
            self._leave_fullscreen_panel()    # Canvas + docks latéraux

    def _auto_refresh_report(self, *_args):
        """Rafraîchit le rapport seulement si la vue Rapport est active."""
        if getattr(self, '_view_stack', None) and self._view_stack.currentIndex() == 2:
            self.report_panel.refresh()

    def on_entity_color_changed(self, entity, color):
        """Quand la couleur d'une entité est modifiée"""
        if entity:
            if hasattr(entity, 'entity_type') and entity.entity_type == 'point':
                manager = getattr(self.canvas_view, 'entity_manager', None)
                group_id = getattr(entity, 'group_id', None)
                if manager and not group_id:
                    group_id = manager.ensure_point_group(
                        getattr(entity, 'name', 'Compteur'))
                    entity.group_id = group_id

                points = []
                if manager and group_id:
                    points = manager.get_points_by_group(group_id)
                if not points:
                    points = [entity]

                for point in points:
                    if hasattr(point, 'set_color'):
                        point.set_color(QColor(color))
                    elif hasattr(point, 'color'):
                        point.color = QColor(color).name(QColor.HexArgb)

                    if hasattr(point, 'draw') and hasattr(point, 'scene_ref') and point.scene_ref:
                        point.draw(point.scene_ref)

                if hasattr(self.canvas_view, 'update_legend'):
                    self.canvas_view.update_legend()
                self.update_quantities_table()
                if hasattr(self.canvas_view, 'scene') and self.canvas_view.scene:
                    self.canvas_view.scene.update()
                return

            # ✅ AMÉLIORATION: Si c'est un enfant, remonter au parent
            target_entity = entity
            if hasattr(entity, 'parent_entity') and entity.parent_entity is not None:
                target_entity = entity.parent_entity

            # ✅ ENREGISTRER DANS L'HISTORIQUE UNDO/REDO AVANT LA MODIFICATION
            if hasattr(self, 'undo_redo_manager') and self.undo_redo_manager._enabled:
                from core.undo_redo_manager import PropertyChangeCommand

                # Capturer l'ancienne couleur (avec alpha) - CORRIGER: gérer string et QColor
                old_color = "#000000"
                if hasattr(target_entity, 'color'):
                    if isinstance(target_entity.color, str):
                        old_color = target_entity.color
                    elif isinstance(target_entity.color, QColor):
                        old_color = target_entity.color.name(QColor.HexArgb)
                new_color = QColor(color).name(QColor.HexArgb)

                if old_color != new_color:
                    command = PropertyChangeCommand(
                        self.canvas_view.entity_manager,
                        self.canvas_view.scene,
                        target_entity.entity_id,
                        'color',
                        old_color,
                        new_color,
                        description=f"Couleur de '{target_entity.name}'"
                    )
                    self.undo_redo_manager.push_command(command)

            # Mettre à jour la couleur de l'entité cible (parent ou entité simple)
            # CORRIGER: Utiliser toujours set_color pour préserver l'alpha
            if hasattr(target_entity, 'set_color'):
                target_entity.set_color(QColor(color))
            elif hasattr(target_entity, 'color'):
                # Si pas de set_color, stocker comme string avec alpha
                target_entity.color = QColor(color).name(QColor.HexArgb)

            # ✅ Si c'est un parent de groupe, propager aux enfants
            if hasattr(target_entity, 'is_group_parent') and target_entity.is_group_parent:
                if hasattr(target_entity, 'child_entities') and target_entity.child_entities:
                    for child in target_entity.child_entities:
                        if hasattr(child, 'set_color'):
                            child.set_color(QColor(color))
                        elif hasattr(child, 'color'):
                            # Stocker comme string avec alpha
                            child.color = QColor(color).name(QColor.HexArgb)

                        # Redessiner l'enfant
                        if hasattr(child, 'draw') and hasattr(child, 'scene_ref'):
                            child.draw(child.scene_ref)

            # Redessiner l'entité parent
            if hasattr(target_entity, 'draw') and hasattr(target_entity, 'scene_ref'):
                target_entity.draw(target_entity.scene_ref)

            # ✅ NOUVEAU : Mettre à jour la légende en temps réel
            if hasattr(self.canvas_view, 'update_legend'):
                self.canvas_view.update_legend()

            # ✅ NOUVEAU : Mettre à jour le relevé quantitatif en temps réel
            self.update_quantities_table()

            # Mettre à jour l'affichage de la scène
            if hasattr(self.canvas_view, 'scene') and self.canvas_view.scene:
                self.canvas_view.scene.update()

            # Rafraîchir le panneau des propriétés pour refléter les changements
            if hasattr(self, 'properties_dock'):
                # Bloquer temporairement pour éviter les boucles
                if hasattr(self.properties_dock, 'updating_ui'):
                    old_state = self.properties_dock.updating_ui
                    self.properties_dock.updating_ui = True
                    self.properties_dock.display_entity_properties(
                        target_entity)
                    self.properties_dock.updating_ui = old_state
                else:
                    self.properties_dock.display_entity_properties(
                        target_entity)

            # ✅ NOUVEAU : Émettre le signal geometryChanged pour cohérence (même si c'est juste la couleur)
            if hasattr(target_entity, 'geometryChanged'):
                target_entity.geometryChanged.emit()

            self.statusBar().showMessage(
                f"✅ Couleur modifiée pour '{target_entity.name}'", 2000)

    def on_entity_name_changed(self, entity, name):
        """Quand le nom d'une entité est modifié"""
        if entity:
            # ✅ CORRECTION: Ne pas accepter un nom vide
            if not name or name.strip() == "":
                # Restaurer le nom actuel dans le champ
                if hasattr(self, 'properties_dock') and self.properties_dock:
                    current_name = getattr(entity, 'name', 'Sans nom')
                    if current_name:
                        self.properties_dock.name_edit.setText(current_name)
                return

            if hasattr(entity, 'entity_type') and entity.entity_type == 'point':
                old_name = getattr(entity, 'name', 'Sans nom')
                manager = getattr(self.canvas_view, 'entity_manager', None)
                group_id = getattr(entity, 'group_id', None)
                points = []
                if manager and group_id:
                    points = manager.get_points_by_group(group_id)
                if not points:
                    points = [entity]

                if manager:
                    new_group_id = manager.ensure_point_group(name)
                else:
                    new_group_id = group_id

                for point in points:
                    point.name = name
                    point.group_id = new_group_id
                    if hasattr(point, 'draw_text') and hasattr(point, 'scene_ref') and point.scene_ref:
                        point.draw_text(point.scene_ref)

                self.update_quantities_table()
                self.update_properties_entities_list()
                if hasattr(self.canvas_view, 'update_legend'):
                    self.canvas_view.update_legend()
                self.statusBar().showMessage(
                    f"✅ Nom modifié: '{name}'", 2000)
                return

            old_name = getattr(entity, 'name', 'Sans nom')

            # Remonter à la racine du groupe (enfant → parent)
            grp_root = entity
            while getattr(grp_root, "parent_entity", None) is not None:
                grp_root = grp_root.parent_entity

            all_members = [grp_root] + list(getattr(grp_root, "child_entities", None) or [])

            # ✅ ENREGISTRER DANS L'HISTORIQUE UNDO/REDO AVANT LA MODIFICATION
            if hasattr(self, 'undo_redo_manager') and self.undo_redo_manager._enabled:
                from core.undo_redo_manager import PropertyChangeCommand
                if old_name != name:
                    command = PropertyChangeCommand(
                        self.canvas_view.entity_manager,
                        self.canvas_view.scene,
                        grp_root.entity_id,
                        'name',
                        old_name,
                        name,
                        description=f"Renommer '{old_name}'"
                    )
                    self.undo_redo_manager.push_command(command)

            # Appliquer le nom à tous les membres du groupe
            for member in all_members:
                member.name = name
                if hasattr(member, 'draw_text') and hasattr(member, 'scene_ref') and member.scene_ref:
                    member.draw_text(member.scene_ref)

            # Légende et quantitatif
            if hasattr(self.canvas_view, 'update_legend'):
                self.canvas_view.update_legend()
            self.update_quantities_table()
            self.update_properties_entities_list()

            # Rafraîchir le panneau des propriétés sur l'entité cliquée
            if hasattr(self, 'properties_dock'):
                self.properties_dock.name_edit.blockSignals(True)
                self.properties_dock.display_entity_properties(entity)
                self.properties_dock.name_edit.blockSignals(False)

            # Rafraîchir "Pages & Mesures" pour afficher le nouveau nom
            if hasattr(self, 'pdf_navigator'):
                self.pdf_navigator.refresh()

            self.statusBar().showMessage(f"✅ Nom modifié: '{name}'", 2000)

    def on_measure_visibility_changed(self, entity, visible):
        """Quand la visibilité de la mesure est modifiée"""
        if entity:
            # ✅ AMÉLIORATION: Si c'est un enfant, remonter au parent
            target_entity = entity
            if hasattr(entity, 'parent_entity') and entity.parent_entity is not None:
                target_entity = entity.parent_entity

            # ✅ Fonction helper pour appliquer la visibilité à une entité
            def apply_visibility_to_entity(ent, vis):
                # Enregistrer la préférence pour éviter le retour lors des redraw
                if hasattr(ent, 'show_measure'):
                    ent.show_measure = vis

                # Bulles de texte uniques (surfaces, distances, etc.)
                if hasattr(ent, 'text_item') and ent.text_item:
                    ent.text_item.setVisible(vis)
                if hasattr(ent, 'text_bg') and ent.text_bg:
                    ent.text_bg.setVisible(vis)

                # Bulles de texte multiples (périmètres avec plusieurs segments)
                if hasattr(ent, 'text_items') and ent.text_items:
                    for text in ent.text_items:
                        if text:
                            text.setVisible(vis)
                if hasattr(ent, 'text_bgs') and ent.text_bgs:
                    for bg in ent.text_bgs:
                        if bg:
                            bg.setVisible(vis)

                # ✅ Appliquer aussi aux ouvertures (surfaces et périmètres avec ouvertures)
                openings = None
                if hasattr(ent, 'openings') and ent.openings:
                    openings = ent.openings
                elif hasattr(ent, 'linear_openings') and ent.linear_openings:
                    openings = ent.linear_openings

                if openings:
                    for opening in openings:
                        if hasattr(opening, 'text_item') and opening.text_item:
                            opening.text_item.setVisible(vis)
                        if hasattr(opening, 'text_bg') and opening.text_bg:
                            opening.text_bg.setVisible(vis)

                # Bulles de hauteur d'ouverture (périmètre)
                if hasattr(ent, 'opening_label_items') and ent.opening_label_items:
                    for item in ent.opening_label_items:
                        if item:
                            item.setVisible(vis)
                if hasattr(ent, 'preview_opening_label') and ent.preview_opening_label:
                    ent.preview_opening_label.setVisible(vis)

                # Compteurs (points)
                if hasattr(ent, 'point_item') and ent.point_item:
                    ent.point_item.setVisible(vis)
                if hasattr(ent, 'name_item') and ent.name_item:
                    ent.name_item.setVisible(vis)

            # Appliquer la visibilité à l'entité cible
            apply_visibility_to_entity(target_entity, visible)

            # Si c'est un parent de groupe, propager aux enfants
            if hasattr(target_entity, 'is_group_parent') and target_entity.is_group_parent:
                if hasattr(target_entity, 'child_entities') and target_entity.child_entities:
                    for child in target_entity.child_entities:
                        apply_visibility_to_entity(child, visible)

            # Si on réactive, recréer les bulles si nécessaire
            if visible:
                entities_to_refresh = [target_entity]
                if hasattr(target_entity, 'is_group_parent') and target_entity.is_group_parent:
                    entities_to_refresh.extend(
                        getattr(target_entity, 'child_entities', []) or [])
                for ent in entities_to_refresh:
                    if hasattr(ent, 'draw_text') and hasattr(ent, 'scene_ref') and ent.scene_ref:
                        ent.draw_text(ent.scene_ref)

            # Mettre à jour l'affichage
            if hasattr(self.canvas_view, 'scene') and self.canvas_view.scene:
                self.canvas_view.scene.update()

    def update_properties_entities_list(self):
        """Met à jour la liste des entités dans le properties dock"""
        if hasattr(self, 'properties_dock') and hasattr(self.canvas_view, 'entity_manager'):
            entities = self.canvas_view.entity_manager.get_all_entities()
            self.properties_dock.update_entities_list(entities)

    def on_selection_changed(self):
        """Quand la sélection change dans la scène"""
        return self.selection_helper.on_selection_changed()

    def open_image(self):
        """Ouvre une image"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir une image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )

        if file_path:
            success = self.canvas_view.load_image(file_path)
            if success:
                import os
                self.statusBar().showMessage(f"Image chargée: {file_path}")

                if hasattr(self, 'legend_action'):
                    self.legend_action.setChecked(True)
                    self.legend_action.setText("Masquer la légende")

                # ✅ NOUVEAU : Reconnecter les signaux après chargement
                self.reconnect_all_entity_signals()

                # Afficher le panneau Pages & Mesures avec une page représentant l'image
                self._show_image_as_page(file_path)
            else:
                QMessageBox.warning(
                    self, "Erreur", "Impossible de charger l'image")

    def _show_image_as_page(self, file_path: str):
        """Crée une PDFPage synthétique pour l'image et l'ajoute en bas des pages existantes."""
        import os
        try:
            name = os.path.splitext(os.path.basename(file_path))[0]

            # Miniature depuis le pixmap déjà chargé dans canvas_view
            pixmap = getattr(self.canvas_view, "pixmap", None)
            thumb  = None
            if pixmap and not pixmap.isNull():
                thumb = pixmap.scaled(
                    52, 39,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )

            # Sauvegarder les entités de la page courante avant de changer de page
            self._save_current_page_entities()

            # Créer la nouvelle page avec un index correspondant à sa position finale
            new_index = len(self._all_pages)
            page = PDFPage(page_index=new_index, name=name)
            page.pixmap    = pixmap
            page.thumbnail = thumb

            # Appender à la liste maîtresse
            self._all_pages.append(page)

            # Afficher le dock
            if not getattr(self, "pdf_dock", None):
                self.show_pdf_dock()
            self.pdf_dock.show()
            self.pdf_dock.raise_()
            if hasattr(self, 'properties_dock') and self.properties_dock:
                self.properties_dock.show()

            # Mettre à jour le panneau et naviguer vers la nouvelle page
            self.pdf_navigator.set_pages(self._all_pages)
            self.pdf_navigator.set_current_page(new_index)

            # Synchroniser l'index courant et afficher la nouvelle page
            self.current_pdf_page_index = new_index
            # Ouvrir uniquement cette page comme onglet (contrôle utilisateur)
            if new_index not in self._open_tabs:
                self._open_tabs.append(new_index)
            self._sync_tab_bar(new_index)

        except Exception as e:
            pass

    def import_pdf(self):
        """Importer un fichier PDF"""
        dialog = ImportPDFDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        selection = dialog.get_selection()
        if not selection:
            return
        file_path, options = selection
        self.start_pdf_conversion(file_path, options)

    def start_pdf_conversion(self, file_path, options):
        """Lance la conversion PDF — les nouvelles pages sont ajoutées en bas des existantes."""
        self._pdf_file_path = file_path
        self.pdf_document = None
        # Sauvegarder la page courante et noter le décalage pour l'import
        self._save_current_page_entities()
        self._pdf_import_offset = len(self._all_pages)

        dpi = int(options.get("dpi", 200))
        page_range = options.get("page_range")
        grayscale = options.get("grayscale", False)

        # Créer le dialogue de progression
        self.pdf_progress_dialog = QProgressDialog(
            "Chargement du plan en cours...",
            None,  # Pas de bouton Annuler
            0,
            100,  # Sera ajusté dans on_pdf_conversion_started
            self
        )
        self.pdf_progress_dialog.setWindowTitle("Import PDF")
        self.pdf_progress_dialog.setWindowModality(Qt.WindowModal)
        self.pdf_progress_dialog.setMinimumDuration(0)  # Afficher immédiatement
        self.pdf_progress_dialog.setAutoClose(False)
        self.pdf_progress_dialog.setAutoReset(False)
        self.pdf_progress_dialog.setValue(0)
        
        # Forcer l'affichage du dialogue immédiatement
        self.pdf_progress_dialog.show()
        
        # Forcer le traitement des événements Qt pour que le dialogue soit bien créé
        QApplication.processEvents()

        if hasattr(self, 'measure_label'):
            self.measure_label.setText(
                "Conversion PDF en cours…")

        if hasattr(self, 'pdf_dock') and self.pdf_dock:
            self.pdf_dock.show()
        if hasattr(self, 'properties_dock') and self.properties_dock:
            self.properties_dock.show()

        self.pdf_converter.start_conversion(
            file_path=file_path,
            dpi=dpi,
            page_range=page_range,
            thumb_width=180,
            grayscale=grayscale,
        )

    def on_pdf_conversion_started(self, total_pages):
        """Callback conversion démarrée — on ajoute N pages placeholder en bas de la liste."""
        self.pdf_document = PDFDocument(self._pdf_file_path, total_pages)
        # Ajouter des pages placeholder à la liste maîtresse
        for i in range(total_pages):
            abs_idx = self._pdf_import_offset + i
            placeholder = PDFPage(page_index=abs_idx, name=f"Page {abs_idx + 1}")
            self._all_pages.append(placeholder)
        if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
            self.pdf_navigator.set_pages(self._all_pages)
        if hasattr(self, 'measure_label'):
            self.measure_label.setText(
                f"PDF: {total_pages} page(s) - conversion…")
        
        # Configurer le dialogue de progression avec le nombre total de pages
        if hasattr(self, 'pdf_progress_dialog') and self.pdf_progress_dialog is not None:
            try:
                if not self.pdf_progress_dialog.wasCanceled():
                    self.pdf_progress_dialog.setMaximum(total_pages)
                    self.pdf_progress_dialog.setLabelText(f"Chargement: 0 / {total_pages} page(s)...")
            except (RuntimeError, AttributeError):
                # Le dialogue a été fermé/détruit
                self.pdf_progress_dialog = None

    def on_pdf_page_converted(self, index, image, thumb):
        """Callback page convertie — on remplace le placeholder dans _all_pages."""
        pixmap = QPixmap.fromImage(image)
        thumb_pixmap = QPixmap.fromImage(thumb)
        abs_idx = self._pdf_import_offset + index
        page = PDFPage(abs_idx, name=f"Page {abs_idx + 1}")
        page.set_pixmaps(pixmap, thumb_pixmap)
        # Remplacer le placeholder dans la liste maîtresse
        if abs_idx < len(self._all_pages):
            self._all_pages[abs_idx] = page
        # Garder pdf_document synchronisé (pour normalize_pages)
        if self.pdf_document:
            pdf_page_local = PDFPage(index, name=f"Page {abs_idx + 1}")
            pdf_page_local.set_pixmaps(pixmap, thumb_pixmap)
            self.pdf_document.add_page(pdf_page_local)
        if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
            self.pdf_navigator.update_page_thumbnail(abs_idx, thumb_pixmap)
        
        # Mettre à jour le dialogue de progression (vérification robuste)
        if hasattr(self, 'pdf_progress_dialog') and self.pdf_progress_dialog is not None:
            try:
                if not self.pdf_progress_dialog.wasCanceled():
                    current_value = self.pdf_progress_dialog.value() + 1
                    total_pages = self.pdf_progress_dialog.maximum()
                    self.pdf_progress_dialog.setValue(current_value)
                    self.pdf_progress_dialog.setLabelText(
                        f"Chargement: {current_value} / {total_pages} page(s)..."
                    )
            except (RuntimeError, AttributeError):
                # Le dialogue a été fermé/détruit
                self.pdf_progress_dialog = None

    def on_pdf_conversion_finished(self):
        """Callback conversion terminée."""
        # Fermer le dialogue de progression
        if hasattr(self, 'pdf_progress_dialog') and self.pdf_progress_dialog is not None:
            try:
                self.pdf_progress_dialog.close()
            except (RuntimeError, AttributeError):
                pass  # Déjà fermé
            finally:
                self.pdf_progress_dialog = None

        if hasattr(self, 'measure_label'):
            self.measure_label.setText("Conversion PDF terminée")

        if self.pdf_document:
            self.pdf_document.normalize_pages()
            # Synchroniser les pages normalisées de pdf_document vers _all_pages
            for i, p in enumerate(self.pdf_document.pages):
                abs_idx = self._pdf_import_offset + i
                if p and abs_idx < len(self._all_pages):
                    # Conserver le nom/index absolu mais récupérer le pixmap normalisé
                    p.page_index = abs_idx
                    self._all_pages[abs_idx] = p

        if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
            self.pdf_navigator.set_pages(self._all_pages)

        if self._all_pages:
            # Naviguer vers la première page du nouvel import
            first_new = self._pdf_import_offset
            # N'ouvrir QUE la première page comme onglet — l'utilisateur ouvrira les autres
            if first_new not in self._open_tabs:
                self._open_tabs.append(first_new)
            self.on_pdf_page_selected(first_new)
            if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
                self.pdf_navigator.set_current_page(first_new)
            self._sync_tab_bar(first_new)

    def on_pdf_conversion_error(self, message):
        """Callback erreur conversion"""
        # Fermer le dialogue de progression
        if hasattr(self, 'pdf_progress_dialog') and self.pdf_progress_dialog is not None:
            try:
                self.pdf_progress_dialog.close()
            except (RuntimeError, AttributeError):
                pass  # Déjà fermé
            finally:
                self.pdf_progress_dialog = None
        
        # Construire un message lisible selon la nature de l'erreur
        if "password" in message.lower() or "encrypt" in message.lower():
            user_msg = "Ce fichier PDF est protégé par un mot de passe.\n\nVeuillez déverrouiller le PDF avant de l'importer."
        elif "no objects" in message.lower() or "cannot open" in message.lower() or "not a pdf" in message.lower():
            user_msg = "Le fichier sélectionné n'est pas un PDF valide ou il est corrompu.\n\nVérifiez que le fichier s'ouvre correctement dans un lecteur PDF."
        elif "pymupdf" in message.lower() or "fitz" in message.lower():
            user_msg = "Le composant de lecture PDF (PyMuPDF) n'est pas disponible.\n\nVeuillez réinstaller l'application."
        else:
            user_msg = f"Impossible d'importer le fichier PDF.\n\nDétail technique :\n{message}"
        QMessageBox.warning(self, "Erreur d'importation PDF", user_msg)
        if hasattr(self, 'measure_label'):
            self.measure_label.setText("Erreur import PDF")

    def on_pdf_page_selected(self, page_index: int):
        """Affiche la page PDF sélectionnée"""
        # ── Correction A : arrêter le timer debounce AVANT tout changement ──────
        if hasattr(self, '_update_timer') and self._update_timer.isActive():
            self._update_timer.stop()
            self._pending_update = False

        # IMPORTANT: fonctionner en mode PDF ET en mode image (pages gérées)
        page = self._get_managed_page(page_index)
        if not page or not page.pixmap:
            return

        # ── Correction B : mettre à jour _current_index du navigateur TÔT ───────
        # Garantit que tout signal entity_added déclenché pendant la restauration
        # (ci-dessous) reconstruira l'item du BON onglet, pas celui de la page
        # précédente.
        if hasattr(self, 'pdf_navigator'):
            self.pdf_navigator._current_index = page_index

        self._is_switching_pdf_page = True
        try:
            self._save_current_page_entities()
            self.current_pdf_page_index = page_index

            # Nettoyer les entités de la page précédente
            if hasattr(self, 'canvas_view'):
                self.canvas_view.clear_scene()

            # Afficher la page
            self.canvas_view.display_pixmap(page.pixmap)

            # Restaurer l'échelle de la page si disponible
            self.canvas_view.pixels_per_meter = getattr(
                page, "pixels_per_meter", 100) or 100

            # Restaurer les entités
            self._restore_page_entities(page)
        finally:
            self._is_switching_pdf_page = False

        # Reconnexion des signaux ICI — après la fin du switch, jamais pendant
        if hasattr(self, 'reconnect_all_entity_signals'):
            self.reconnect_all_entity_signals()

        # Mettre à jour la légende et le relevé
        if hasattr(self.canvas_view, 'update_legend'):
            self.canvas_view.update_legend()
        if hasattr(self, 'update_quantities_table'):
            self.update_quantities_table()

        # Activer/désactiver les outils selon que la page a été calibrée manuellement
        _calibrated = getattr(page, "scale_calibrated", False)
        self._update_tools_for_scale_state(_calibrated)
        # ── Correction A (suite) : set_current_page() met à jour _current_index
        # ET reconstruit le bon item du panneau (remplace l'ancien refresh() qui
        # utilisait _current_index potentiellement obsolète → item de mauvaise page).
        if hasattr(self, 'pdf_navigator'):
            self.pdf_navigator.set_current_page(page_index)
        # Synchroniser la tab bar — JAMAIS de création automatique d'onglet.
        # Deux cas :
        #   • Aucun onglet ouvert (ex: premier import) → créer le premier onglet.
        #   • Des onglets existent → mettre à jour UNIQUEMENT l'onglet actif.
        if hasattr(self, '_open_tabs') and hasattr(self, '_page_tab_bar'):
            pg = self.current_pdf_page_index
            if pg is None:
                pass
            elif not self._open_tabs:
                # Premier chargement : créer le premier (et unique) onglet
                self._open_tabs.append(pg)
                self._sync_tab_bar(pg)
            else:
                # Onglets déjà présents : afficher la page dans l'onglet ACTIF
                active_tab = self._page_tab_bar.current_index()
                if 0 <= active_tab < len(self._open_tabs):
                    self._open_tabs[active_tab] = pg
                    page_obj = self._get_managed_page(pg)
                    label = (getattr(page_obj, 'name', None) or f"Page {pg + 1}")
                    self._page_tab_bar.rename_tab(active_tab, label)

    def _save_current_page_entities(self):
        """Sauvegarde les entités de la page courante"""
        # Ne jamais sauvegarder pendant un switch de page : le canvas est en état
        # transitoire (clear_scene fait, restore pas encore terminé). Une sauvegarde
        # à ce moment écraserait les données correctes avec un état incomplet.
        if getattr(self, '_is_switching_pdf_page', False):
            return
        if self.current_pdf_page_index is None:
            return
        page = self._get_managed_page(self.current_pdf_page_index)
        if not page:
            return
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'entity_manager'):
            entities = [
                ent for ent in self.canvas_view.entity_manager.get_all_entities()
                # Les ouvertures de surface sont déjà sérialisées dans la surface parente.
                # Si on les sauvegarde aussi comme entités autonomes, elles réapparaissent
                # en double (hachures rouges visibles) au rechargement.
                if getattr(ent, 'entity_type', '') != 'opening'
            ]
            page.save_entities(entities)
            page.pixels_per_meter = getattr(
                self.canvas_view, "pixels_per_meter", 100) or 100

    def _restore_page_entities(self, page: PDFPage):
        """Restaure les entités d'une page"""
        if not page:
            return
        entities = page.create_entities()
        if not entities:
            return
        # Ignorer les ouvertures standalone (compat anciens fichiers)
        # et recréer uniquement via _pending_openings_data des surfaces.
        filtered_entities = [
            ent for ent in entities
            if getattr(ent, "entity_type", "") != "opening"
        ]

        for ent in filtered_entities:
            if hasattr(self.canvas_view, 'entity_manager'):
                self.canvas_view.entity_manager.add_entity(ent)
            if hasattr(ent, 'draw'):
                ent.draw(self.canvas_view.scene)

        # Restaurer les ouvertures des surfaces si présentes
        for ent in filtered_entities:
            openings_data = getattr(ent, "_pending_openings_data", None)
            if not openings_data:
                continue
            for opening_data in openings_data:
                try:
                    points = [QPointF(x, y) for x, y in opening_data.get('points', [])]
                    opening = OpeningEntity(
                        points,
                        opening_data.get('pixels_per_meter', ent.pixels_per_meter)
                    )
                    opening.name = opening_data.get('name', 'Ouverture')
                    color_data = opening_data.get('color', '#000000')
                    if isinstance(color_data, (tuple, list)):
                        opening.color = QColor(*color_data)
                    else:
                        opening.color = QColor(color_data)
                    if hasattr(self.canvas_view, 'entity_manager'):
                        self.canvas_view.entity_manager.add_entity(opening)
                    opening.draw(self.canvas_view.scene)
                    if hasattr(ent, 'add_opening'):
                        ent.add_opening(opening)
                except Exception as e:
                    pass
            try:
                delattr(ent, "_pending_openings_data")
            except Exception:
                pass

        # Restaurer les liens de groupe (group_id / parent / enfants)
        self._rebuild_group_links(filtered_entities)
        # Auto-groupement par nom/type si group_id absent
        self._auto_group_entities_in_scene(filtered_entities)

        # Ré-appliquer la visibilité persistée à TOUTES les entités restaurées.
        # Cela garantit que l'état de l'ampoule (on/off) reste cohérent après
        # changement de page et après rechargement du projet.
        em = getattr(self.canvas_view, "entity_manager", None)
        if em and hasattr(em, "apply_entity_visibility"):
            for ent in filtered_entities:
                try:
                    em.apply_entity_visibility(ent, getattr(ent, "visible", True))
                except Exception as e:
                    pass
        # NOTE : reconnect_all_entity_signals() est intentionnellement absent ici.
        # Il est appelé dans on_pdf_page_selected() APRÈS la fin du switch complet
        # (_is_switching_pdf_page = False), pour éviter les déclenchements prématurés
        # de on_entity_modified pendant la restauration.

    def get_pdf_entities_for_quantities(self):
        """Retourne toutes les entités de toutes les pages pour le relevé."""
        if not self.aggregate_pdf_quantities:
            return None
        if not self._all_pages:
            return None
        entities = []
        point_group_map = {}
        from models.pdf_document import create_entity_from_dict
        for page in self._all_pages:
            if not page or not getattr(page, 'entities_data', None):
                continue
            for data in page.entities_data:
                ent = create_entity_from_dict(data)
                if ent:
                    if getattr(ent, 'entity_type', '') == 'point':
                        name = getattr(ent, 'name', '') or 'Compteur'
                        if name not in point_group_map:
                            point_group_map[name] = f"group_{uuid.uuid4().hex[:8]}"
                        ent.group_id = point_group_map[name]
                    entities.append(ent)
        return entities

    # ── Barre d'onglets ───────────────────────────────────────────────────────
    #
    # Architecture :
    #   _all_pages       = liste complète (toutes les pages du projet, jamais réduite)
    #   _open_tabs       = liste ordonnée d'indices dans _all_pages actuellement ouverts
    #   tab_index i  ↔  _all_pages[ _open_tabs[i] ]
    #
    # Fermer un onglet NE supprime PAS la page de _all_pages (données conservées).
    # Le panneau "Pages & Mesures" montre toujours toutes les pages.

    def _sync_tab_bar(self, current_page_index: int = 0):
        """Reconstruit la tab bar depuis _open_tabs (sous-ensemble de _all_pages)."""
        if not hasattr(self, '_page_tab_bar'):
            return
        # Nettoyer les indices obsolètes
        self._open_tabs = [i for i in self._open_tabs
                           if 0 <= i < len(self._all_pages)]
        if not self._open_tabs:
            self._page_tab_bar.hide()
            return
        # Construire la liste de pages à afficher
        pages_to_show = [self._all_pages[i] for i in self._open_tabs]
        # Calculer l'indice de l'onglet actif
        if current_page_index in self._open_tabs:
            tab_idx = self._open_tabs.index(current_page_index)
        else:
            tab_idx = 0
        self._page_tab_bar.populate(pages_to_show, tab_idx)
        self._page_tab_bar.show()

    def _open_page_as_tab(self, page_index: int, navigate: bool = True):
        """Crée TOUJOURS un nouvel onglet pour la page donnée (appelé via '+')."""
        self._open_tabs.append(page_index)
        self._sync_tab_bar(page_index)
        if navigate:
            self.on_pdf_page_selected(page_index)

    def _on_tab_selected(self, tab_idx: int):
        """Clic sur un onglet → mapper l'indice tab vers _all_pages et naviguer."""
        if 0 <= tab_idx < len(self._open_tabs):
            page_idx = self._open_tabs[tab_idx]
            self.on_pdf_page_selected(page_idx)

    def _on_tab_page_closed(self, tab_idx: int):
        """Fermeture d'un onglet — retire de _open_tabs sans supprimer la page."""
        if not (0 <= tab_idx < len(self._open_tabs)):
            return
        page_idx = self._open_tabs[tab_idx]

        # Sauvegarder la page active UNE SEULE FOIS ici.
        # on_pdf_page_selected() appellera aussi _save_current_page_entities() mais
        # comme current_pdf_page_index sera None, cette deuxième sauvegarde sera
        # annulée par la garde au début de _save_current_page_entities().
        if page_idx == self.current_pdf_page_index:
            self._save_current_page_entities()

        self._open_tabs.pop(tab_idx)

        if not self._open_tabs:
            # Plus aucun onglet ouvert : vider le canvas proprement
            self.current_pdf_page_index = None
            if hasattr(self, 'canvas_view'):
                self.canvas_view.clear_scene()
            self._page_tab_bar.hide()
            if hasattr(self, 'update_quantities_table'):
                self.update_quantities_table()
            return

        # Naviguer vers un onglet adjacent
        new_tab = min(tab_idx, len(self._open_tabs) - 1)
        new_page = self._open_tabs[new_tab]
        # Invalider current_pdf_page_index : _save_current_page_entities() dans
        # on_pdf_page_selected() sera alors bloqué par la garde (index None)
        # → évite toute double écriture.
        self.current_pdf_page_index = None
        self._sync_tab_bar(new_page)
        self.on_pdf_page_selected(new_page)

    def _on_tab_add_page(self):
        """Bouton '+' : crée un nouvel onglet. L'utilisateur choisit la page à afficher.
        Toutes les pages sont proposées (même celles déjà ouvertes dans d'autres onglets).
        """
        all_pages = [(i, self._all_pages[i]) for i in range(len(self._all_pages))
                     if self._all_pages[i] is not None]
        if all_pages:
            self._show_open_page_picker(all_pages)
        else:
            self._create_blank_page()

    def _show_open_page_picker(self, closed_pages: list):
        """Affiche un sélecteur pour choisir quelle page ouvrir comme onglet."""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QListWidget,
                                     QListWidgetItem, QDialogButtonBox, QLabel)
        dlg = QDialog(self)
        dlg.setWindowTitle("Ouvrir dans un nouvel onglet")
        dlg.setMinimumWidth(320)
        dlg.setStyleSheet("""
            QDialog { background: #f0f2f5; }
            QLabel  { color: #1a2a3a; font-size: 12px; }
            QListWidget {
                background: white;
                color: #1a2a3a;
                border: 1px solid #c0cce0;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #1976d2;
                color: white;
            }
            QPushButton {
                background: #e8f0fa;
                color: #1565c0;
                border: 1px solid #90b8e8;
                border-radius: 4px;
                padding: 5px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background: #d0e4f8; }
            QDialogButtonBox QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 18px;
                font-weight: bold;
                min-width: 70px;
            }
            QDialogButtonBox QPushButton:hover  { background: #1565c0; }
            QDialogButtonBox QPushButton:pressed { background: #0d47a1; }
        """)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 16, 16, 12)
        v.setSpacing(10)
        v.addWidget(QLabel("Choisissez la page à afficher dans le nouvel onglet :"))
        lst = QListWidget()
        for page_idx, page in closed_pages:
            label = page.name or f"Page {page_idx + 1}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, page_idx)
            lst.addItem(item)
        lst.setCurrentRow(0)
        v.addWidget(lst)
        # Bouton "Nouvelle page vierge"
        from PyQt5.QtWidgets import QPushButton
        btn_blank = QPushButton("+ Nouvelle page vierge")
        btn_blank.clicked.connect(lambda: (dlg.reject(), self._create_blank_page()))
        v.addWidget(btn_blank)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        # Double-clic = validation directe
        lst.itemDoubleClicked.connect(lambda _: dlg.accept())
        if dlg.exec_() != QDialog.Accepted:
            return
        sel = lst.currentItem()
        if sel:
            page_idx = sel.data(Qt.UserRole)
            self._save_current_page_entities()
            self._open_page_as_tab(page_idx)

    def _create_blank_page(self):
        """Crée une page vierge, l'ajoute à _all_pages et l'ouvre comme onglet."""
        default_name = f"Page {len(self._all_pages) + 1}"
        name, ok = QInputDialog.getText(
            self, "Nouvelle page vierge", "Nom de la page :", text=default_name
        )
        if not ok:
            return
        name = name.strip() or default_name
        new_idx = len(self._all_pages)
        new_page = PDFPage(page_index=new_idx, name=name)
        self._save_current_page_entities()
        self._all_pages.append(new_page)
        self._open_tabs.append(new_idx)
        if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
            self.pdf_navigator.set_pages(self._all_pages)
        self._sync_tab_bar(new_idx)
        self.on_pdf_page_selected(new_idx)
        self._unsaved_changes = True

    def _on_tab_page_renamed(self, tab_idx: int, new_name: str):
        """Double-clic sur un onglet → renomme la page correspondante."""
        if 0 <= tab_idx < len(self._open_tabs):
            page_idx = self._open_tabs[tab_idx]
            if 0 <= page_idx < len(self._all_pages):
                self._all_pages[page_idx].name = new_name
                if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
                    self.pdf_navigator.update_page_name(page_idx, new_name)
                self._unsaved_changes = True

    def _on_tab_page_moved(self, from_tab: int, to_tab: int):
        """Drag & drop d'onglet → réordonne _open_tabs uniquement."""
        if from_tab == to_tab:
            return
        if not (0 <= from_tab < len(self._open_tabs)
                and 0 <= to_tab < len(self._open_tabs)):
            return
        page_idx = self._open_tabs.pop(from_tab)
        self._open_tabs.insert(to_tab, page_idx)
        # Mettre à jour l'index courant
        self.current_pdf_page_index = page_idx
        self._unsaved_changes = True

    # ── Helpers pages (PDF + image) ──────────────────────────────────────────

    def _managed_pages(self) -> list:
        """Retourne la liste maîtresse de toutes les pages (PDF + images)."""
        return self._all_pages

    def _get_managed_page(self, page_index: int):
        """Retourne la PDFPage à l'index donné, quel que soit le mode."""
        pages = self._managed_pages()
        if 0 <= page_index < len(pages):
            return pages[page_index]
        return None

    def _apply_pages_to_navigator(self, pages: list, current_index: int):
        """Met à jour la liste maîtresse et le panneau Pages & Mesures."""
        self._all_pages = list(pages)
        idx = max(0, min(current_index, len(self._all_pages) - 1))
        if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
            # CRITIQUE : mettre à jour _current_index dans le panneau AVANT set_pages.
            # set_pages appelle _highlight_current_page() à la fin, qui appelle
            # _rebuild_live_entities() pour la page active. Si _current_index est
            # encore l'ANCIEN index (avant réordonnancement), _rebuild_live_entities
            # s'exécute sur la MAUVAISE page et lui injecte les entités du canvas
            # → items fantômes visibles dans le panneau.
            self.pdf_navigator._current_index = idx
            self.pdf_navigator.set_pages(self._all_pages)
            self.pdf_navigator.set_current_page(idx)
        # S'assurer que la page courante est dans les onglets ouverts
        if idx not in self._open_tabs:
            self._open_tabs.append(idx)
        self._sync_tab_bar(idx)

    # ── Handlers actions sur les pages ───────────────────────────────────────

    def on_pdf_rename_page(self, page_index: int):
        """Renomme une page (PDF ou image)."""
        page = self._get_managed_page(page_index)
        if page is None:
            return
        current_name = page.name or f"Page {page_index + 1}"
        new_name, ok = QInputDialog.getText(
            self, "Renommer la page", "Nom de la page :", text=current_name
        )
        if ok and new_name.strip():
            page.name = new_name.strip()
            if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
                self.pdf_navigator.update_page_name(page_index, page.name)

    # ── Manipulation de page (onglet Page) ───────────────────────────────────

    def _current_page_pixmap(self):
        """Retourne (page, pixmap) de la page courante, ou (None, None)."""
        if self.current_pdf_page_index is None:
            return None, None
        page = self._get_managed_page(self.current_pdf_page_index)
        if page is None:
            return None, None
        px = getattr(page, 'pixmap', None)
        if px is None or px.isNull():
            return page, None
        return page, px

    def _apply_page_pixmap(self, page, new_pixmap):
        """Remplace le pixmap d'une page et rafraîchit le canvas."""
        page.pixmap = new_pixmap
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'image_item'):
            img_item = self.canvas_view.image_item
            if img_item:
                img_item.setPixmap(new_pixmap)
                self.canvas_view.fitInView(img_item, Qt.KeepAspectRatio)
        # Mettre à jour la miniature dans le panneau Pages & Mesures
        if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
            thumb = new_pixmap.scaled(120, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            page.thumbnail = thumb
            self.pdf_navigator.refresh()

    def _rotate_page(self, angle: int):
        """Pivote la page courante de `angle` degrés."""
        from PyQt5.QtGui import QTransform
        page, px = self._current_page_pixmap()
        if px is None:
            self.statusBar().showMessage("Aucun plan chargé à pivoter.", 2000)
            return
        t = QTransform().rotate(angle)
        self._apply_page_pixmap(page, px.transformed(t, Qt.SmoothTransformation))
        self.statusBar().showMessage(f"Page pivotée de {angle}°.", 2000)

    def _flip_page(self, horizontal: bool):
        """Retourne la page courante horizontalement ou verticalement."""
        from PyQt5.QtGui import QTransform
        page, px = self._current_page_pixmap()
        if px is None:
            self.statusBar().showMessage("Aucun plan chargé à retourner.", 2000)
            return
        if horizontal:
            t = QTransform(-1, 0, 0, 1, px.width(), 0)
        else:
            t = QTransform(1, 0, 0, -1, 0, px.height())
        self._apply_page_pixmap(page, px.transformed(t))
        label = "horizontalement" if horizontal else "verticalement"
        self.statusBar().showMessage(f"Page retournée {label}.", 2000)

    def _adjust_brightness(self):
        """Ajuste la luminosité en temps réel via QPainter (accéléré, sans boucle pixel)."""
        from PyQt5.QtWidgets import (QDialog, QSlider, QDialogButtonBox,
                                     QVBoxLayout, QHBoxLayout, QLabel)
        from PyQt5.QtGui import QPainter, QColor, QPixmap

        page, original_px = self._current_page_pixmap()
        if original_px is None:
            self.statusBar().showMessage("Aucun plan chargé.", 2000)
            return

        # Copie immuable de l'original pour restauration
        _orig = QPixmap(original_px)

        def _apply_fast(delta: int) -> QPixmap:
            """QPainter overlay — instantané, aucune boucle pixel."""
            result = QPixmap(_orig)
            if delta == 0:
                return result
            p = QPainter(result)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            alpha = min(255, int(abs(delta) * 2.55))
            color = QColor(255, 255, 255, alpha) if delta > 0 else QColor(0, 0, 0, alpha)
            p.fillRect(result.rect(), color)
            p.end()
            return result

        def _preview(delta: int):
            """Mise à jour canvas en temps réel sans sauvegarder."""
            lbl_val.setText(f"{delta:+d}" if delta != 0 else "0")
            if hasattr(self, 'canvas_view') and self.canvas_view.image_item:
                self.canvas_view.image_item.setPixmap(_apply_fast(delta))

        def _restore():
            """Remet l'original si annulation."""
            if hasattr(self, 'canvas_view') and self.canvas_view.image_item:
                self.canvas_view.image_item.setPixmap(_orig)

        # Dialogue
        dlg = QDialog(self)
        dlg.setWindowTitle("Luminosité de la page")
        dlg.setMinimumWidth(340)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Glissez pour ajuster la luminosité :"))

        row = QHBoxLayout()
        lbl_min = QLabel("Sombre")
        lbl_min.setStyleSheet("color:#888; font-size:10px;")
        lbl_max = QLabel("Claire")
        lbl_max.setStyleSheet("color:#888; font-size:10px;")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(25)
        row.addWidget(lbl_min)
        row.addWidget(slider)
        row.addWidget(lbl_max)
        v.addLayout(row)

        lbl_val = QLabel("0")
        lbl_val.setAlignment(Qt.AlignCenter)
        lbl_val.setStyleSheet("font-weight:bold; font-size:13px;")
        v.addWidget(lbl_val)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        v.addWidget(btns)

        # Connexion temps réel
        slider.valueChanged.connect(_preview)

        if dlg.exec_() == QDialog.Accepted:
            delta = slider.value()
            if delta != 0:
                new_px = _apply_fast(delta)
                self._apply_page_pixmap(page, new_px)
                self.statusBar().showMessage(f"✅ Luminosité ajustée ({delta:+d}).", 2000)
            else:
                _restore()
                self.statusBar().showMessage("Luminosité inchangée.", 1500)
        else:
            _restore()
            self.statusBar().showMessage("Luminosité annulée.", 1500)

    def _crop_page(self):
        """Active le mode recadrage : l'utilisateur trace un rectangle sur le plan."""
        if not hasattr(self, 'canvas_view') or not self.canvas_view:
            return
        _, px = self._current_page_pixmap()
        if px is None:
            self.statusBar().showMessage("Aucun plan chargé.", 2000)
            return
        self.statusBar().showMessage(
            "✂️  Tracez la zone à rogner — la sélection crée une nouvelle page", 0)
        self.canvas_view.start_crop_selection(self._on_crop_region_selected)

    def _on_crop_region_selected(self, viewport_rect):
        """Callback : rogne le pixmap et crée une nouvelle page."""
        from PyQt5.QtCore import QRect

        page, px = self._current_page_pixmap()
        if px is None:
            self.statusBar().showMessage("Aucun plan chargé.", 2000)
            return

        # Convertir viewport → scène → coordonnées locales de l'image
        scene_poly = self.canvas_view.mapToScene(viewport_rect)
        scene_rect = scene_poly.boundingRect()

        img_item = getattr(self.canvas_view, 'image_item', None)
        if img_item:
            local_rect = img_item.mapFromScene(scene_rect).boundingRect()
        else:
            local_rect = scene_rect

        # Clipper aux limites du pixmap
        crop_rect = QRect(
            max(0, int(local_rect.x())),
            max(0, int(local_rect.y())),
            int(local_rect.width()),
            int(local_rect.height()),
        ).intersected(QRect(0, 0, px.width(), px.height()))

        if crop_rect.width() < 10 or crop_rect.height() < 10:
            self.statusBar().showMessage(
                "⚠️ Zone trop petite — tracez un rectangle plus grand.", 3000)
            return

        # Rogner le pixmap
        cropped_px = px.copy(crop_rect)

        # Créer la nouvelle page
        pages = self._managed_pages()
        new_index = (self.current_pdf_page_index or 0) + 1
        new_page = PDFPage(page_index=new_index, name="Nouvelle page rognée")
        new_page.pixmap = cropped_px
        new_page.thumbnail = cropped_px.scaled(
            120, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        new_page.entities_data = []

        # Insérer dans la liste maîtresse après la page courante
        new_pages = list(self._all_pages)
        new_pages.insert(new_index, new_page)

        # Mettre à jour le panneau et naviguer vers la nouvelle page
        self._apply_pages_to_navigator(new_pages, new_index)
        self.on_pdf_page_selected(new_index)

        self.statusBar().showMessage(
            "✅ Nouvelle page rognée créée — calibrez son échelle pour des mesures précises.", 5000)

    def on_pdf_delete_page(self, page_index: int):
        """Supprime une page (PDF ou image)."""
        pages = self._managed_pages()
        if len(pages) <= 1:
            QMessageBox.warning(
                self, "Suppression impossible",
                "Le document doit contenir au moins une page."
            )
            return

        page = self._get_managed_page(page_index)
        page_label = (page.name or f"Page {page_index + 1}") if page else f"Page {page_index + 1}"
        reply = QMessageBox.question(
            self, "Supprimer la page",
            f"Supprimer « {page_label} » ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Sauvegarder les entités de la page active AVANT suppression
        self._save_current_page_entities()

        new_pages = [p for i, p in enumerate(self._all_pages) if i != page_index]
        new_index = max(0, min(page_index, len(new_pages) - 1))
        self._apply_pages_to_navigator(new_pages, new_index)
        self.on_pdf_page_selected(new_index)

    def on_pdf_duplicate_page(self, page_index: int, include_measures: bool):
        """Duplique une page (PDF ou image), avec ou sans mesures."""
        pages = self._managed_pages()
        page  = self._get_managed_page(page_index)
        if page is None:
            return

        # Sauvegarder les entités de la page active AVANT duplication
        self._save_current_page_entities()

        # Cloner la page source — include_measures contrôle si on copie les entités
        new_index = page_index + 1
        new_page  = page.clone(new_index, include_measures=include_measures)
        base_name = page.name or f"Page {page_index + 1}"
        suffix    = " (copie)" if include_measures else " (vide)"
        new_page.name = base_name + suffix

        if include_measures:
            # IMPORTANT: isoler totalement la copie de la page source.
            # Sans cette étape, des IDs/group_ids identiques peuvent provoquer
            # des effets de liaison entre la source et la copie.
            self._reseed_page_entities_identity(new_page)
            self._auto_group_page_entities_data(new_page)

        new_pages = list(self._all_pages)
        new_pages.insert(new_index, new_page)

        self._apply_pages_to_navigator(new_pages, new_index)
        self.on_pdf_page_selected(new_index)

    def on_pdf_move_page(self, from_index: int, to_index: int):
        """Déplace une page vers le haut ou le bas dans la liste maîtresse."""
        pages = self._managed_pages()
        n = len(pages)
        if not (0 <= from_index < n and 0 <= to_index < n and from_index != to_index):
            return

        # 1) Sauvegarder les entités de la page actuellement affichée.
        self._save_current_page_entities()

        # 2) Réordonner la liste maîtresse.
        new_pages = list(pages)
        moved_page = new_pages.pop(from_index)
        new_pages.insert(to_index, moved_page)

        # 3) Resynchroniser les page_index (cosmétique uniquement).
        for i, p in enumerate(new_pages):
            if p:
                p.page_index = i

        # 4) Remanier _open_tabs pour que les indices pointent toujours vers
        #    les mêmes pages après le réordonnancement.
        #    - La page déplacée (from_index) est maintenant à to_index.
        #    - Les pages entre from_index et to_index décalent d'un cran.
        def _remap(idx):
            if idx == from_index:
                return to_index
            if from_index < to_index:
                # Déplacement vers le bas : les pages entre from+1 et to montent
                if from_index < idx <= to_index:
                    return idx - 1
            else:
                # Déplacement vers le haut : les pages entre to et from-1 descendent
                if to_index <= idx < from_index:
                    return idx + 1
            return idx

        self._open_tabs = [_remap(i) for i in self._open_tabs]

        # 5) Remanier current_pdf_page_index de la même façon.
        if self.current_pdf_page_index is not None:
            self.current_pdf_page_index = _remap(self.current_pdf_page_index)

        # 6) Mettre à jour la liste maîtresse et le panneau Pages & Mesures
        #    SANS créer de nouvel onglet (contrairement à _apply_pages_to_navigator).
        self._all_pages = list(new_pages)
        if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
            self.pdf_navigator._current_index = self.current_pdf_page_index
            self.pdf_navigator.set_pages(self._all_pages)
            self.pdf_navigator.set_current_page(self.current_pdf_page_index)

        # 7) Resynchroniser la tab bar avec les indices remappés (sans ajout).
        self._sync_tab_bar(self.current_pdf_page_index)

        # 8) Remplacer les items "saved_entity" par les entités live du canvas.
        if hasattr(self, 'pdf_navigator') and self.pdf_navigator:
            self.pdf_navigator.refresh()

        # 9) Mettre à jour la légende et les quantités.
        if hasattr(self.canvas_view, 'update_legend'):
            self.canvas_view.update_legend()
        if hasattr(self, 'update_quantities_table'):
            self.update_quantities_table()

    def _reseed_page_entities_identity(self, page: PDFPage):
        """Régénère entity_id/group_id pour rendre une page dupliquée indépendante."""
        if not page or not getattr(page, 'entities_data', None):
            return

        id_map = {}
        group_map = {}

        # 1) Nouveaux entity_id
        for data in page.entities_data:
            if not isinstance(data, dict):
                continue
            old_id = data.get('entity_id')
            if not old_id:
                continue
            etype = data.get('type') or data.get('entity_type') or 'entity'
            new_id = f"{etype}_{uuid.uuid4().hex[:10]}"
            id_map[old_id] = new_id
            data['entity_id'] = new_id

        # 2) Nouveaux group_id
        for data in page.entities_data:
            if not isinstance(data, dict):
                continue
            old_gid = data.get('group_id')
            if not old_gid:
                continue
            if old_gid not in group_map:
                group_map[old_gid] = f"group_{uuid.uuid4().hex[:8]}"
            data['group_id'] = group_map[old_gid]

        # 3) Réécrire les références parent/enfants avec les nouveaux IDs
        for data in page.entities_data:
            if not isinstance(data, dict):
                continue

            parent_id = data.get('parent_entity_id')
            if parent_id:
                data['parent_entity_id'] = id_map.get(parent_id, parent_id)

            child_ids = data.get('child_entity_ids')
            if isinstance(child_ids, list):
                data['child_entity_ids'] = [id_map.get(cid, cid) for cid in child_ids]

    def _auto_group_page_entities_data(self, page: PDFPage):
        """Assure le groupement automatique des entités par nom/type dans une page."""
        if not page or not page.entities_data:
            return

        groups = {}
        for idx, data in enumerate(page.entities_data):
            entity_type = data.get('type')
            if entity_type not in ('polygon', 'perimeter'):
                continue
            name = data.get('name') or ""
            if not name:
                continue
            if data.get('group_id'):
                # Déjà groupé, ne pas toucher
                continue
            key = (entity_type, name)
            groups.setdefault(key, []).append(idx)

        for (_, _), indices in groups.items():
            if len(indices) < 2:
                continue
            group_id = f"group_{uuid.uuid4().hex[:8]}"
            for i, data_idx in enumerate(indices):
                data = page.entities_data[data_idx]
                data['group_id'] = group_id
                data['is_group_parent'] = (i == 0)

    def _rebuild_group_links(self, entities):
        """Recrée les liens parent/enfants à partir des group_id."""
        if not entities:
            return
        # Regrouper par group_id
        groups = {}
        for ent in entities:
            group_id = getattr(ent, 'group_id', None)
            if group_id:
                groups.setdefault(group_id, []).append(ent)

        for group_id, group_entities in groups.items():
            parent = None
            for ent in group_entities:
                if getattr(ent, 'is_group_parent', False):
                    parent = ent
                    break
            if parent is None and group_entities:
                # Fallback: prendre le premier comme parent
                parent = group_entities[0]
                parent.is_group_parent = True
                parent.group_id = group_id

            if parent:
                if not hasattr(parent, 'child_entities') or parent.child_entities is None:
                    parent.child_entities = []
                for ent in group_entities:
                    if ent is parent:
                        continue
                    ent.parent_entity = parent
                    ent.group_id = group_id
                    ent.is_group_parent = False
                    if ent not in parent.child_entities:
                        parent.child_entities.append(ent)

    def _auto_group_entities_in_scene(self, entities):
        """Groupement par nom/type pour surfaces et périmètres si non groupés."""
        if not entities:
            return
        groups = {}
        for ent in entities:
            if getattr(ent, 'entity_type', '') not in ('polygon', 'perimeter'):
                continue
            if getattr(ent, 'parent_entity', None):
                continue
            name = getattr(ent, 'name', None)
            if not name:
                continue
            key = (ent.entity_type, name)
            groups.setdefault(key, []).append(ent)

        for (_, _), group_entities in groups.items():
            if len(group_entities) < 2:
                continue
            # Réutiliser un group_id existant si présent
            existing_group_id = None
            for ent in group_entities:
                if getattr(ent, 'group_id', None):
                    existing_group_id = ent.group_id
                    break
            group_id = existing_group_id or f"group_{uuid.uuid4().hex[:8]}"

            # Choisir un parent : priorité aux parents existants
            parent = None
            for ent in group_entities:
                if getattr(ent, 'is_group_parent', False):
                    parent = ent
                    break
            if parent is None:
                parent = group_entities[0]
            parent.is_group_parent = True
            parent.group_id = group_id
            if not hasattr(parent, 'child_entities'):
                parent.child_entities = []
            for child in group_entities[1:]:
                if child is parent:
                    continue
                child.group_id = group_id
                child.is_group_parent = False
                child.parent_entity = parent
                if child not in parent.child_entities:
                    parent.child_entities.append(child)

    def show_calibration_dialog(self):
        """Affiche un message d'avertissement pour définir l'échelle"""
        try:
            # Vérifier si l'image est chargée
            if not hasattr(self.canvas_view, 'image_item') or not self.canvas_view.image_item:
                return

            # Vérifier si l'échelle a déjà été définie
            if (hasattr(self.canvas_view, 'pixels_per_meter') and
                    self.canvas_view.pixels_per_meter != 100):
                # Échelle déjà définie, ne pas afficher le message
                return

            QMessageBox.warning(
                self,
                "Échelle non configurée",
                "Échelle non configurée.\n\n"
                "Attention !\n\n"
                "L'échelle pour ce plan n'est pas encore configurée.\n\n"
                "N'oubliez pas de définir l'échelle avant de commencer à mesurer.\n\n"
                "Pour définir l'échelle : Utilisez l'outil Échelle dans la barre d'outils.",
                QMessageBox.Ok
            )

            # Mettre à jour le message de statut après confirmation
            self._update_tools_for_scale_state(False)

        except Exception as e:
            import traceback
            traceback.print_exc()

    def connect_distance_tool_to_dialog(self, dialog):
        """Connecte l'outil distance au dialogue pour mettre à jour automatiquement"""
        try:
            # Trouver l'outil distance
            if hasattr(self.canvas_view, 'tool_manager'):
                distance_tool = self.canvas_view.tool_manager.get_tool(
                    'distance')
                if distance_tool:
                    # Activer l'outil distance
                    self.activate_distance_tool()

                    # Créer un slot temporaire pour capturer la mesure
                    def on_distance_created():
                        # Récupérer la dernière ligne créée
                        if hasattr(self.canvas_view, 'entity_manager'):
                            entities = self.canvas_view.entity_manager.get_all_entities()
                            for entity in entities:
                                if hasattr(entity, 'entity_type') and entity.entity_type == 'line':
                                    # Calculer la distance en pixels
                                    if hasattr(entity, 'start_point') and hasattr(entity, 'end_point'):
                                        dx = entity.end_point.x() - entity.start_point.x()
                                        dy = entity.end_point.y() - entity.start_point.y()
                                        distance_px = (dx**2 + dy**2) ** 0.5
                                        dialog.set_measured_distance(
                                            distance_px)
                                        break

                    # Connecter le signal entity_added pour détecter la création d'une ligne
                    if hasattr(self.canvas_view, 'entity_manager'):
                        self.canvas_view.entity_manager.entity_added.connect(
                            on_distance_created)
        except Exception as e:
            pass

    def deactivate_all_tools(self):
        """Désactive tous les outils en utilisant le ToolManager"""
        # 1. Désactiver le mode pan EN PREMIER pour remettre le curseur flèche
        #    avant que les outils individuels ne tentent eux-mêmes de modifier le curseur.
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'set_pan_mode'):
            self.canvas_view.set_pan_mode(False)

        # 2. Désactiver les outils (certains remettent le curseur ArrowCursor eux-mêmes)
        if hasattr(self.canvas_view, 'tool_manager'):
            self.canvas_view.tool_manager.deactivate_all_tools()
        self.canvas_view.mode = "idle"

        # 3. Désélectionner tous les boutons d'outils (y compris navigation)
        if hasattr(self, 'tool_actions'):
            for action in self.tool_actions:
                action.setChecked(False)

        if hasattr(self, 'measure_label'):
            self.measure_label.setText("Aucun outil activé")

    def _set_active_tool_label(self, label: str):
        """Met à jour le label de l'outil actif dans la barre de statut."""
        if hasattr(self, 'status_tool_label'):
            self.status_tool_label.setText(f"  ✏ {label}")

    def activate_surface_tool(self):
        """Active l'outil de surface"""
        self.deactivate_all_tools()
        self.deselect_other_tools(self.surface_action)
        self.canvas_view.set_mode("surface")
        self.surface_action.setChecked(True)
        self._set_active_tool_label("Surface")
        self.statusBar().showMessage(
            "Surface — Clic gauche : ajouter des sommets   |   Double-clic : fermer   |   ESC : annuler")

    def activate_distance_tool(self):
        """Active l'outil de distance"""
        self.deactivate_all_tools()
        self.deselect_other_tools(self.distance_action)
        self.canvas_view.set_mode("distance")
        self.distance_action.setChecked(True)
        self._set_active_tool_label("Distance")
        self.statusBar().showMessage(
            "Distance — Clic gauche : point départ → point arrivée   |   ESC : annuler")

    def activate_counter_tool(self):
        """Active l'outil de compteur"""
        self.deactivate_all_tools()
        self.deselect_other_tools(self.counter_action)
        self.canvas_view.set_mode("counter")
        self.counter_action.setChecked(True)
        self._set_active_tool_label("Compteur")
        self.statusBar().showMessage(
            "Compteur — Clic gauche : ajouter un point   |   ESC : annuler")

    def _activate_pointer_mode(self):
        """Mode pointeur : aucun outil actif, curseur flèche normale."""
        # deactivate_all_tools gère déjà set_pan_mode(False) et le curseur flèche
        self.deactivate_all_tools()
        self.pointer_action.setChecked(True)
        self._set_active_tool_label("Pointeur")
        self.statusBar().showMessage("Pointeur — cliquez pour sélectionner une entité")

    def _activate_pan_mode(self):
        """Mode pan : déplacer la vue par cliquer-glisser gauche."""
        # deactivate_all_tools remet d'abord le curseur flèche + désactive tous les outils
        self.deactivate_all_tools()
        if hasattr(self, 'canvas_view'):
            self.canvas_view.set_pan_mode(True)   # active la main APRÈS la désactivation
        self.pan_action.setChecked(True)
        self._set_active_tool_label("Déplacer")
        self.statusBar().showMessage(
            "Déplacer — Clic gauche + glisser pour naviguer dans le plan   |   V : retour pointeur")

    def activate_scale_tool(self):
        """Active l'outil d'échelle"""
        self.deactivate_all_tools()
        self.deselect_other_tools(self.scale_action)
        self.canvas_view.set_mode("scale")
        self.scale_action.setChecked(True)
        self._set_active_tool_label("Échelle")
        self.statusBar().showMessage(
            "Échelle — Tracez une ligne de longueur connue   |   ESC : annuler")

    def activate_perimeter_tool(self):
        """Active l'outil de périmètre"""
        self.deactivate_all_tools()
        self.deselect_other_tools(self.perimeter_action)
        self.canvas_view.set_mode("perimeter")
        self.perimeter_action.setChecked(True)
        self._set_active_tool_label("Périmètre")
        self.statusBar().showMessage(
            "Périmètre — Clic gauche : ajouter des points   |   Double-clic : fermer   |   ESC : annuler")

    def activate_opening_tool(self):
        """Active l'outil d'ouverture"""
        self.deactivate_all_tools()
        self.deselect_other_tools(self.opening_action)
        self.canvas_view.set_mode("opening")
        self.opening_action.setChecked(True)
        self._set_active_tool_label("Ouverture")
        self.statusBar().showMessage(
            "Ouverture — Tracez la zone à déduire   |   Clic droit : fermer   |   ESC : annuler")

    def _ensure_annotation_tools_registered(self):
        """S'assure que les outils marqueur et note sont enregistrés dans le tool_manager."""
        if not (hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'tool_manager')):
            return
        tm = self.canvas_view.tool_manager
        if 'marker' not in tm.tools:
            tm.register_tool('marker', 'MarkerTool')
        if 'note' not in tm.tools:
            tm.register_tool('note', 'NoteTool')

    def activate_marker_tool(self):
        """Active l'outil Marqueur (surbrillance rectangulaire)."""
        self.deactivate_all_tools()
        self.deselect_other_tools(self.marker_action)
        self.marker_action.setChecked(True)
        self._set_active_tool_label("Marqueur")
        self._ensure_annotation_tools_registered()
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'tool_manager'):
            self.canvas_view.tool_manager.activate_tool('marker')

    def activate_note_tool(self):
        """Active l'outil Note (commentaire sur le canvas)."""
        self.deactivate_all_tools()
        self.deselect_other_tools(self.note_action)
        self.note_action.setChecked(True)
        self._set_active_tool_label("Note")
        self._ensure_annotation_tools_registered()
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'tool_manager'):
            self.canvas_view.tool_manager.activate_tool('note')

    def deactivate_current_tool(self):
        """Désactive l'outil courant et repasse en mode idle."""
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'tool_manager'):
            self.canvas_view.tool_manager.deactivate_all_tools()
        self.deselect_other_tools(None)
        if hasattr(self, 'marker_action'):
            self.marker_action.setChecked(False)
        if hasattr(self, 'note_action'):
            self.note_action.setChecked(False)

    def deselect_other_tools(self, current_action):
        """Désélectionne les autres outils"""
        if hasattr(self, 'tool_actions'):
            for action in self.tool_actions:
                if action != current_action:
                    action.setChecked(False)
        # Désélectionner aussi les actions annotation
        for attr in ('marker_action', 'note_action'):
            act = getattr(self, attr, None)
            if act and act != current_action:
                act.setChecked(False)

    def get_entity_value_text(self, entity):
        """Retourne le texte de la valeur de l'entité"""
        # Périmètre
        if hasattr(entity, 'is_perimeter') and entity.is_perimeter:
            return entity.get_perimeter_text() if hasattr(entity, 'get_perimeter_text') else "N/A"

        # Surface (aire)
        if hasattr(entity, 'calculate_area') and hasattr(entity, 'get_area_text'):
            return entity.get_area_text()

        # Distance (longueur)
        if hasattr(entity, 'calculate_length') and hasattr(entity, 'get_length_text'):
            return entity.get_length_text()

        # Point de comptage
        if hasattr(entity, 'entity_type') and entity.entity_type == "point":
            length = float(getattr(entity, 'length', 0.0) or 0.0)
            height = float(getattr(entity, 'height', 0.0) or 0.0)
            thickness = float(getattr(entity, 'thickness', 0.0) or 0.0)
            if length > 0 and height > 0 and thickness > 0:
                return f"{length * height * thickness:.2f} m³"
            if length > 0 and height > 0:
                return f"{length * height:.2f} m²"
            if length > 0:
                return f"{length:.2f} m"
            return "1U"

        # Par défaut
        return "N/A"

    def get_entity_type_label(self, entity):
        """Retourne le libellé du type d'entité"""
        if hasattr(entity, 'is_perimeter') and entity.is_perimeter:
            return "Périmètre"

        if hasattr(entity, 'entity_type'):
            entity_type = entity.entity_type
            if entity_type == "line":
                return "Distance"
            elif entity_type == "point":
                length = float(getattr(entity, 'length', 0.0) or 0.0)
                height = float(getattr(entity, 'height', 0.0) or 0.0)
                thickness = float(getattr(entity, 'thickness', 0.0) or 0.0)
                if length > 0 and height > 0 and thickness > 0:
                    return "Volume"
                if length > 0 and height > 0:
                    return "Surface"
                if length > 0:
                    return "Distance"
                return "Point"
            elif entity_type == "polygon":
                return "Périmètre" if getattr(entity, 'is_perimeter', False) else "Surface"

        return "Surface"  # Par défaut

    def toggle_ortho_mode(self):
        """Active/désactive le mode ortho"""
        if hasattr(self.canvas_view, 'ortho_manager') and self.canvas_view.ortho_manager:
            current_state = self.canvas_view.ortho_manager.is_ortho_enabled()
            new_state = not current_state
            self.canvas_view.ortho_manager.set_ortho_enabled(new_state)

            # Mettre à jour l'indicateur visuel
            self.update_ortho_indicator(new_state)
            if new_state:
                self.statusBar().showMessage("Mode orthographique activé", 2000)
                self.measure_label.setText("Mode Ortho ACTIVÉ")
            else:
                self.statusBar().showMessage("Mode orthographique désactivé", 2000)
                self.measure_label.setText("Mode Ortho DÉSACTIVÉ")
        else:
            self.ortho_action.setChecked(False)
            if hasattr(self, 'ortho_label'):
                self.update_ortho_indicator(False)

    def update_ortho_indicator(self, enabled):
        """Met à jour l'indicateur de mode Ortho"""
        if hasattr(self, 'ortho_label'):
            if enabled:
                self.ortho_label.setText("ORTHO: ON")
                self.ortho_label.setStyleSheet(
                    "QLabel { background-color: green; color: white; padding: 2px; }")
            else:
                self.ortho_label.setText("ORTHO: OFF")
                self.ortho_label.setStyleSheet(
                    "QLabel { background-color: lightgray; padding: 2px; }")

    def clear_all(self):
        """Efface toutes les mesures"""
        try:
            # Demander confirmation à l'utilisateur
            reply = QMessageBox.question(
                self, "Confirmation",
                "Voulez-vous vraiment effacer toutes les mesures?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # Désactiver tous les outils
                self.deactivate_all_tools()

                # Nettoyer la scène via canvas_view
                if hasattr(self.canvas_view, 'clear_scene'):
                    self.canvas_view.clear_scene()

                # Mettre à jour les tableaux et listes
                self.update_quantities_table()
                self.update_properties_entities_list()

                # Effacer la sélection dans le panneau de propriétés
                if hasattr(self, 'properties_dock'):
                    self.properties_dock.clear_selection()

                # Mettre à jour les messages
                self.statusBar().showMessage("Toutes les mesures ont été effacées", 3000)
                if hasattr(self, 'measure_label'):
                    self.measure_label.setText("Toutes les mesures effacées")

                self.update_toolbar_selection(None)
        except Exception as e:
            QMessageBox.warning(
                self, "Erreur",
                f"Une erreur est survenue lors de l'effacement: {e}"
            )

    def on_entity_width_changed(self, entity, width):
        """Callback lorsque l'épaisseur d'une entité est modifiée"""
        if entity and hasattr(entity, 'set_width'):
            try:
                # ✅ AMÉLIORATION: Si c'est un enfant, remonter au parent
                target_entity = entity
                if hasattr(entity, 'parent_entity') and entity.parent_entity is not None:
                    target_entity = entity.parent_entity

                # Mettre à jour l'épaisseur de l'entité cible
                target_entity.set_width(width)

                # Si c'est un parent de groupe, propager aux enfants
                if hasattr(target_entity, 'is_group_parent') and target_entity.is_group_parent:
                    if hasattr(target_entity, 'child_entities') and target_entity.child_entities:
                        for child in target_entity.child_entities:
                            if hasattr(child, 'set_width'):
                                child.set_width(width)
                                # Redessiner l'enfant
                                if hasattr(child, 'draw') and hasattr(child, 'scene_ref') and child.scene_ref:
                                    child.draw(child.scene_ref)

                # Redessiner l'entité parent pour appliquer le changement
                if hasattr(target_entity, 'draw') and hasattr(target_entity, 'scene_ref') and target_entity.scene_ref:
                    target_entity.draw(target_entity.scene_ref)

                # Mettre à jour l'affichage
                if hasattr(self.canvas_view, 'scene') and self.canvas_view.scene:
                    self.canvas_view.scene.update()

                if hasattr(self, 'properties_dock'):
                    self.properties_dock.display_entity_properties(
                        target_entity)

            except Exception as e:
                pass

    def on_entity_pattern_changed(self, entity, pattern_key):
        """Callback lorsque le motif de remplissage d'une surface est modifié depuis le panneau."""
        if not entity:
            return
        try:
            entity.fill_pattern = pattern_key
            # Rafraîchir la scène
            if hasattr(self.canvas_view, 'scene') and self.canvas_view.scene:
                self.canvas_view.scene.update()
            # Sauvegarder l'état de la page courante
            self._save_current_page_entities()
        except Exception:
            pass

    def show_scale_editor(self):
        """Affiche le dialogue pour modifier l'échelle"""
        try:
            if not hasattr(self.canvas_view, 'image_item') or not self.canvas_view.image_item:
                QMessageBox.warning(
                    self,
                    "Aucune image",
                    "Veuillez d'abord charger une image."
                )
                return

            # Créer le dialogue avec l'échelle actuelle
            # from ui.scale_dialog import ScaleCalibrationDialog # This import is no longer needed
            # dialog = ScaleCalibrationDialog(self, self.canvas_view)

            # Si une échelle existe déjà, proposer de la modifier
            if hasattr(self.canvas_view, 'pixels_per_meter'):
                # Préremplir avec l'échelle actuelle si possible
                # (nécessiterait de connaître une mesure de référence)
                pass

            # dialog.exec_() # This line is no longer needed
        except Exception as e:
            QMessageBox.warning(
                self,
                "Erreur",
                f"Une erreur est survenue lors de l'ouverture de l'éditeur d'échelle:\n{e}"
            )

    def toggle_legend(self):
        """Affiche/masque la légende"""
        if not hasattr(self.canvas_view, 'toggle_legend'):
            return

        self.canvas_view.toggle_legend()

        # Mettre à jour le statut
        is_visible = self.legend_action.isChecked()
        status = "affichée" if is_visible else "masquée"
        self.statusBar().showMessage(f"Légende {status}", 3000)

        # Mettre à jour le texte de l'action
        if is_visible:
            self.legend_action.setText("Masquer la légende")
        else:
            self.legend_action.setText("Afficher la légende")

    def on_table_item_changed(self, item):
        """Callback quand une cellule du tableau est modifiée par l'utilisateur"""
        # ✅ Cette méthode ne devrait JAMAIS être appelée car le signal n'est pas connecté
        # Mais par sécurité absolue, ne rien faire du tout
        # Ne RIEN faire - absolument rien pour éviter toute boucle
        pass

    def reconnect_all_entity_signals(self):
        """Reconnecte les signaux geometryChanged de TOUTES les entités existantes"""
        if not hasattr(self.canvas_view, 'entity_manager'):
            return

        entities = self.canvas_view.entity_manager.get_all_entities()

        for entity in entities:
            if hasattr(entity, 'geometryChanged'):
                try:
                    # Déconnecter d'abord pour éviter les connexions multiples
                    try:
                        entity.geometryChanged.disconnect()
                    except (TypeError, RuntimeError):
                        # Pas de connexion existante, c'est normal
                        pass

                    # Reconnecter proprement
                    entity.geometryChanged.connect(
                        lambda ent=entity: self.on_entity_modified(ent))

                except Exception as e:
                    pass

    def get_selected_entity(self):
        """Retourne l'entité actuellement sélectionnée"""
        # ✅ PRIORITÉ 1: Via la sélection Qt dans la scène (TOUJOURS LA PLUS À JOUR)
        if hasattr(self.canvas_view, 'scene') and self.canvas_view.scene:
            selected_items = self.canvas_view.scene.selectedItems()

            # Parcourir tous les items sélectionnés pour trouver une entité valide
            for item in selected_items:
                if hasattr(item, 'data'):
                    try:
                        entity_id = item.data(1)
                        if entity_id and hasattr(self.canvas_view, 'entity_manager'):
                            entity = self.canvas_view.entity_manager.get_entity(
                                entity_id)
                            if entity:
                                # ✅ NOUVEAU: Vérifier que c'est bien une entité copiable
                                if hasattr(entity, 'entity_type') and entity.entity_type in ['polygon', 'perimeter', 'scale', 'point']:
                                    return entity
                    except (TypeError, AttributeError):
                        continue

        # ✅ PRIORITÉ 2: Via le PropertyPanel (FALLBACK si rien n'est sélectionné dans la scène)
        if hasattr(self, 'properties_dock') and self.properties_dock:
            if hasattr(self.properties_dock, 'current_entity') and self.properties_dock.current_entity:
                entity = self.properties_dock.current_entity
                return entity

        # ✅ PRIORITÉ 3: Dernière entité cliquée ou sélectionnée (DERNIER RECOURS)
        if hasattr(self.canvas_view, 'last_selected_entity') and self.canvas_view.last_selected_entity:
            entity = self.canvas_view.last_selected_entity
            return entity

        return None

    def open_properties_for_selection(self):
        """Ouvre/rafraîchit le panneau de propriétés pour l'entité sélectionnée."""
        entity = self.get_selected_entity()
        if not entity:
            self.statusBar().showMessage("❌ Aucune entité sélectionnée", 3000)
            return False

        if hasattr(self, 'show_properties_dock'):
            self.show_properties_dock()

        if hasattr(self, 'properties_dock') and self.properties_dock:
            try:
                if hasattr(self.properties_dock, 'select_entity'):
                    self.properties_dock.select_entity(entity)
                else:
                    self.properties_dock.display_entity_properties(entity)
                return True
            except Exception as e:
                pass

        return False

    def start_linear_opening_on_selected_perimeter(self):
        """
        Lance le mode création d'ouverture linéaire sur le périmètre sélectionné.
        Le tracé se fait ensuite avec 2 clics gauche directement sur le périmètre en édition.
        """
        entity = self.get_selected_entity()
        if not entity or getattr(entity, 'entity_type', None) != 'perimeter':
            self.statusBar().showMessage("❌ Sélectionnez un périmètre", 3000)
            return False

        try:
            scene = getattr(self.canvas_view, 'scene', None)
            if hasattr(entity, 'enable_editing') and not getattr(entity, 'is_editing', False):
                entity.enable_editing(scene)

            entity.opening_creation_mode = True
            entity.opening_start_pos = None

            if hasattr(entity, 'set_selected'):
                entity.set_selected(True)
            if hasattr(entity, 'entityClicked'):
                entity.entityClicked.emit(entity)

            self.statusBar().showMessage(
                "🚪 Mode ouverture linéaire actif: cliquez début puis fin sur le périmètre", 4000)
            if hasattr(self, 'measure_label'):
                self.measure_label.setText(
                    "🚪 [1/2] Cliquez sur le DEBUT de l'ouverture (sur un segment)"
                )
            return True
        except Exception as e:
            self.statusBar().showMessage(
                f"❌ Impossible de lancer le mode ouverture: {e}", 3000)
            return False

    def _get_perimeter_group_targets(self, entity):
        """Retourne les périmètres à mettre à jour (groupe complet si applicable)."""
        if not entity:
            return []
        if getattr(entity, 'is_group_parent', False):
            return [entity] + list(getattr(entity, 'child_entities', []) or [])
        parent = getattr(entity, 'parent_entity', None)
        if parent:
            return [parent] + list(getattr(parent, 'child_entities', []) or [])
        return [entity]

    def prompt_perimeter_wall_props(self):
        """Demande puis applique hauteur/épaisseur au périmètre sélectionné (ou groupe)."""
        entity = self.get_selected_entity()
        if not entity or getattr(entity, 'entity_type', None) != 'perimeter':
            self.statusBar().showMessage("❌ Sélectionnez un périmètre", 3000)
            return False

        current_height = float(getattr(entity, 'height', 0.0) or 0.0)
        current_thickness = float(getattr(entity, 'thickness', 0.0) or 0.0)

        height, ok_h = QInputDialog.getDouble(
            self, "Hauteur du périmètre", "Hauteur (m):",
            current_height, 0.0, 1000.0, 2
        )
        if not ok_h:
            return False

        thickness, ok_t = QInputDialog.getDouble(
            self, "Épaisseur du périmètre", "Épaisseur (m):",
            current_thickness, 0.0, 1000.0, 2
        )
        if not ok_t:
            return False

        targets = self._get_perimeter_group_targets(entity)
        scene = getattr(self.canvas_view, 'scene', None)
        for ent in targets:
            ent.height = max(0.0, float(height))
            ent.thickness = max(0.0, float(thickness))
            if hasattr(ent, 'draw'):
                ent.draw(getattr(ent, 'scene_ref', None) or scene)

        self.on_entity_modified(entity)
        self.statusBar().showMessage(
            f"✅ Hauteur/épaisseur appliquées ({len(targets)} élément(s))", 3000)
        return True

    def prompt_opening_height_for_target(self):
        """Demande une hauteur et l'applique aux ouvertures linéaires du périmètre sélectionné."""
        entity = self.get_selected_entity()
        if not entity or getattr(entity, 'entity_type', None) != 'perimeter':
            self.statusBar().showMessage("❌ Sélectionnez un périmètre", 3000)
            return False

        openings = list(getattr(entity, 'linear_openings', []) or [])
        if not openings:
            self.statusBar().showMessage(
                "⚠️ Ce périmètre n'a pas d'ouverture linéaire", 3000)
            return False

        default_height = float(
            openings[-1].get('height', getattr(entity, 'default_opening_height', 2.10))
        )
        new_height = self.prompt_opening_height(default_value=default_height)
        if new_height is None:
            return False

        new_height = max(0.0, float(new_height))
        for opening in openings:
            opening['height'] = new_height
        entity.linear_openings = openings

        if hasattr(entity, 'draw'):
            entity.draw(getattr(entity, 'scene_ref', None) or getattr(self.canvas_view, 'scene', None))

        self.on_entity_modified(entity)
        self.statusBar().showMessage(
            f"✅ Hauteur appliquée aux ouvertures: {new_height:.2f} m", 3000)
        return True

    def rename_counter_series(self):
        """Renomme la série de compteurs (même group_id ou même nom)."""
        entity = self.get_selected_entity()
        if not entity or getattr(entity, 'entity_type', None) != 'point':
            self.statusBar().showMessage("❌ Sélectionnez un compteur", 3000)
            return False

        current_name = getattr(entity, 'name', 'Compteur') or 'Compteur'
        new_name, ok = QInputDialog.getText(
            self, "Renommer série de compteurs", "Nouveau nom :", text=current_name
        )
        if not ok or not new_name.strip():
            return False
        new_name = new_name.strip()

        manager = getattr(self.canvas_view, 'entity_manager', None)
        targets = []
        group_id = getattr(entity, 'group_id', None)
        if manager:
            if group_id and hasattr(manager, 'get_points_by_group'):
                targets = manager.get_points_by_group(group_id)
            elif hasattr(manager, 'get_points_by_name'):
                targets = manager.get_points_by_name(current_name)

        if not targets:
            targets = [entity]

        for point in targets:
            point.name = new_name
            if hasattr(point, 'draw_text') and getattr(point, 'scene_ref', None):
                point.draw_text(point.scene_ref)
            elif hasattr(point, 'draw'):
                point.draw(getattr(self.canvas_view, 'scene', None))

        self.on_entity_modified(entity)
        self.statusBar().showMessage(
            f"✅ Série renommée: '{new_name}' ({len(targets)} compteur(s))", 3000)
        return True

    def toggle_scale_reference_visibility(self):
        """Affiche/masque les lignes nommées 'Échelle de référence'."""
        manager = getattr(self.canvas_view, 'entity_manager', None)
        if not manager:
            return False

        refs = []
        for ent in manager.get_entities_by_type('line'):
            name = (getattr(ent, 'name', '') or '').strip().lower()
            if name in ("échelle de référence", "echelle de reference"):
                refs.append(ent)

        if not refs:
            self.statusBar().showMessage(
                "⚠️ Aucune ligne d'échelle de référence trouvée", 3000)
            return False

        current_vis = []
        for ent in refs:
            if hasattr(ent, 'line_item') and ent.line_item:
                current_vis.append(ent.line_item.isVisible())
            else:
                current_vis.append(bool(getattr(ent, 'visible', True)))
        # Si toutes visibles => masquer, sinon afficher.
        target_visible = not all(current_vis)

        for ent in refs:
            ent.visible = target_visible
            for attr in ('line_item', 'text_item', 'text_bg', 'start_anchor', 'end_anchor'):
                item = getattr(ent, attr, None)
                if item:
                    item.setVisible(target_visible)

        state_txt = "affichée" if target_visible else "masquée"
        self.statusBar().showMessage(
            f"✅ Échelle de référence {state_txt}", 3000)
        return True

    def copy_entity(self):
        """Copie l'entité sélectionnée dans le presse-papier"""
        selected = []
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'get_selected_entities'):
            selected = self.canvas_view.get_selected_entities()
        if selected and len(selected) > 1:
            self._copy_or_cut_entities(selected, cut_mode=False)
            return
        entity = self.get_selected_entity()
        self._copy_or_cut_entity(entity, cut_mode=False)

    def cut_entity(self):
        """Coupe l'entité sélectionnée (copie + suppression immédiate)"""
        selected = []
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'get_selected_entities'):
            selected = self.canvas_view.get_selected_entities()
        if selected and len(selected) > 1:
            self._copy_or_cut_entities(selected, cut_mode=True)
            return
        entity = self.get_selected_entity()
        self._copy_or_cut_entity(entity, cut_mode=True)

    def _serialize_entity_for_clipboard(self, entity):
        """Sérialise une entité pour le presse-papier."""
        if not entity:
            return None
        if not hasattr(entity, 'entity_type') or entity.entity_type not in ['polygon', 'perimeter', 'point']:
            return None

        from PyQt5.QtCore import QPointF
        import copy

        parent = getattr(entity, 'parent_entity', None)
        parent_id = parent.entity_id if parent and hasattr(parent, 'entity_id') else None

        if entity.entity_type == 'point':
            return {
                'entity_type': 'point',
                'position': QPointF(entity.position.x(), entity.position.y()),
                'name': entity.name,
                'color': QColor(entity.color),
                'shape': getattr(entity, 'shape', 'circle'),
                'size': getattr(entity, 'size', 14),
                'counter_number': getattr(entity, 'counter_number', 0),
                'group_id': getattr(entity, 'group_id', None),
                'length': getattr(entity, 'length', 0.0),
                'height': getattr(entity, 'height', 0.0),
                'thickness': getattr(entity, 'thickness', 0.0)
            }

        clipboard = {
            'entity_type': entity.entity_type,
            'points': [QPointF(p.x(), p.y()) for p in entity.points],
            'name': entity.name,
            'color': QColor(entity.color),
            'pixels_per_meter': entity.pixels_per_meter,
            'fill_pattern': getattr(entity, 'fill_pattern', Qt.SolidPattern),
            'is_perimeter': getattr(entity, 'is_perimeter', False),
            'width': getattr(entity, 'width', 2),
            'parent_entity_id': parent_id,
            'group_id': getattr(entity, 'group_id', None),
            'is_group_parent': getattr(entity, 'is_group_parent', False),
            'openings': [],
            'show_measure': getattr(entity, 'show_measure', False),
            'height': getattr(entity, 'height', 0.0),
            'thickness': getattr(entity, 'thickness', 0.0),
        }

        if entity.entity_type == 'polygon' and getattr(entity, 'openings', None):
            for opening in entity.openings:
                opening_data = {
                    'points': [QPointF(p.x(), p.y()) for p in opening.points],
                    'name': opening.name,
                    'color': QColor(opening.color),
                    'pixels_per_meter': opening.pixels_per_meter
                }
                clipboard['openings'].append(opening_data)

        if entity.entity_type == 'perimeter':
            clipboard['linear_openings'] = copy.deepcopy(
                getattr(entity, 'linear_openings', []))
        else:
            clipboard['linear_openings'] = []

        return clipboard

    def _copy_or_cut_entities(self, entities, cut_mode=False):
        """Copie ou coupe une sélection multiple."""
        if not entities:
            self.statusBar().showMessage("❌ Aucune entité sélectionnée", 3000)
            return

        serialized = []
        for entity in entities:
            data = self._serialize_entity_for_clipboard(entity)
            if data:
                serialized.append(data)

        if not serialized:
            self.statusBar().showMessage("❌ Aucun type d'entité copiabled", 3000)
            return

        self.clipboard_entity = {'multiple': True, 'entities': serialized}
        self.cut_mode = cut_mode

        if cut_mode:
            count = len(entities)
            for entity in entities:
                if hasattr(entity, 'entity_id') and hasattr(self.canvas_view, 'entity_manager'):
                    self.canvas_view.entity_manager.remove_entity(
                        entity.entity_id,
                        self.canvas_view.scene
                    )
            self.statusBar().showMessage(
                f"✅ {count} entité(s) coupée(s) - Utilisez Ctrl+V pour coller", 3000)
        else:
            self.statusBar().showMessage(
                f"✅ {len(entities)} entité(s) copiée(s) - Utilisez Ctrl+V pour coller", 3000)

    def _copy_or_cut_entity(self, entity, cut_mode=False):
        """Sérialise une entité dans le presse-papier (copie ou coupe)."""
        if not entity:
            self.statusBar().showMessage("❌ Aucune entité sélectionnée", 3000)
            return

        if not hasattr(entity, 'entity_type') or entity.entity_type not in ['polygon', 'perimeter', 'point']:
            self.statusBar().showMessage("❌ Ce type d'entité ne peut pas être copié", 3000)
            return

        clipboard = self._serialize_entity_for_clipboard(entity)
        if not clipboard:
            self.statusBar().showMessage("❌ Ce type d'entité ne peut pas être copié", 3000)
            return

        self.clipboard_entity = clipboard
        self.cut_mode = cut_mode

        if cut_mode:
            entity_name = entity.name
            if hasattr(entity, 'entity_id') and hasattr(self.canvas_view, 'entity_manager'):
                self.canvas_view.entity_manager.remove_entity(
                    entity.entity_id,
                    self.canvas_view.scene
                )
            self.statusBar().showMessage(
                f"✅ '{entity_name}' coupé - Utilisez Ctrl+V pour coller", 3000)
        else:
            self.statusBar().showMessage(
                f"✅ '{entity.name}' copié - Utilisez Ctrl+V pour coller", 3000)

    def paste_entity(self):
        """Colle l'entité depuis le presse-papier"""
        if not self.clipboard_entity:
            self.statusBar().showMessage("❌ Presse-papier vide - Copiez d'abord une entité", 3000)
            return

        try:
            data = self.clipboard_entity

            # Collage multiple
            if isinstance(data, dict) and data.get('multiple'):
                items = data.get('entities', [])
                offset_x, offset_y = self._compute_paste_offset(data)
                for item in items:
                    self._paste_single_entity(item, offset_x, offset_y, clear_clipboard=False)
                if self.cut_mode:
                    self.clipboard_entity = None
                    self.cut_mode = False
                return

            # Collage simple
            offset_x, offset_y = self._compute_paste_offset(data)
            self._paste_single_entity(data, offset_x, offset_y, clear_clipboard=True)
            return
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(
                f"❌ Erreur lors du collage: {e}", 3000)

    def _clipboard_anchor_point(self, data):
        """
        Retourne un point d'ancrage pour une donnée presse-papier.
        - point: position
        - polygon/perimeter: premier point
        - multiple: ancrage du premier item
        """
        if not data:
            return None
        if isinstance(data, dict) and data.get('multiple'):
            items = data.get('entities', [])
            return self._clipboard_anchor_point(items[0]) if items else None

        entity_type = data.get('entity_type')
        if entity_type == 'point':
            return data.get('position')

        points = data.get('points', [])
        if points:
            return points[0]
        return None

    def _compute_paste_offset(self, clipboard_data):
        """
        Calcule le décalage de collage.
        Priorité:
        1) Coller à la dernière position de clic gauche utilisateur
        2) Fallback historique (50,50) pour copie / (0,0) pour couper
        """
        # Fallback legacy
        default_dx = 50 if not self.cut_mode else 0
        default_dy = 50 if not self.cut_mode else 0

        target_pos = getattr(self.canvas_view, 'last_left_click_scene_pos', None)
        if target_pos is None:
            return default_dx, default_dy

        source_anchor = self._clipboard_anchor_point(clipboard_data)
        if source_anchor is None:
            return default_dx, default_dy

        try:
            return (target_pos.x() - source_anchor.x(),
                    target_pos.y() - source_anchor.y())
        except Exception:
            return default_dx, default_dy

    def _paste_single_entity(self, data, offset_x, offset_y, clear_clipboard=True):
        """Colle une seule entité sérialisée."""
        try:
            from PyQt5.QtCore import QPointF
            from entities.polygon_entity import PolygonEntity
            from entities.perimeter_entity import PerimeterEntity
            from entities.opening_entity import OpeningEntity
            from entities.point_entity import PointEntity
            import uuid

            if data.get('entity_type') == 'point':
                new_pos = QPointF(
                    data['position'].x() + offset_x,
                    data['position'].y() + offset_y
                )

                group_id = data.get('group_id')
                if hasattr(self.canvas_view, 'entity_manager') and self.canvas_view.entity_manager:
                    if not group_id:
                        group_id = self.canvas_view.entity_manager.ensure_point_group(
                            data.get('name', 'Compteur'))
                point_entity = PointEntity(new_pos, {
                    'counter_number': data.get('counter_number', 0),
                    'name': data.get('name', 'Compteur'),
                    'color': data.get('color', QColor(255, 0, 0, 200)),
                    'shape': data.get('shape', 'circle'),
                    'size': data.get('size', 14),
                    'group_id': group_id,
                    'length': data.get('length', 0.0),
                    'height': data.get('height', 0.0),
                    'thickness': data.get('thickness', 0.0)
                })

                if hasattr(self.canvas_view, 'entity_manager') and self.canvas_view.entity_manager:
                    entity_id = self.canvas_view.entity_manager.add_entity(
                        point_entity)
                    point_entity.entity_id = entity_id

                if hasattr(self.canvas_view, 'scene'):
                    point_entity.draw(self.canvas_view.scene)

                if hasattr(point_entity, 'point_item') and point_entity.point_item:
                    point_entity.point_item.setData(1, point_entity.entity_id)
                if hasattr(point_entity, 'text_item') and point_entity.text_item:
                    point_entity.text_item.setData(1, point_entity.entity_id)
                if hasattr(point_entity, 'name_item') and point_entity.name_item:
                    point_entity.name_item.setData(1, point_entity.entity_id)

                if self.cut_mode and clear_clipboard:
                    self.clipboard_entity = None
                    self.cut_mode = False

                self.update_quantities_table()
                self.update_properties_entities_list()
                if hasattr(self.canvas_view, 'update_legend'):
                    self.canvas_view.update_legend()

                self.statusBar().showMessage(
                    f"✅ '{point_entity.name}' collé", 3000)
                return

            # ✅ CRUCIAL : Déterminer le parent du groupe AVANT de créer l'entité
            target_parent = None

            if data.get('parent_entity_id'):
                # Cas 1 : L'entité source était déjà un enfant → retrouver le parent par ID
                if hasattr(self.canvas_view, 'entity_manager'):
                    target_parent = self.canvas_view.entity_manager.get_entity(
                        data['parent_entity_id'])
                    if target_parent:
                        pass
                    else:
                        pass

            elif data['is_group_parent']:
                # Cas 2 : L'entité source était un parent → utiliser comme parent
                if hasattr(self.canvas_view, 'entity_manager'):
                    all_entities = self.canvas_view.entity_manager.get_all_entities()
                    for entity in all_entities:
                        if (hasattr(entity, 'name') and entity.name == data['name'] and
                                hasattr(entity, 'is_group_parent') and entity.is_group_parent):
                            target_parent = entity
                            break

            else:
                # Cas 3 : Pas de groupe → Trouver l'original et le transformer en parent
                if not self.cut_mode and hasattr(self.canvas_view, 'entity_manager'):
                    all_entities = self.canvas_view.entity_manager.get_all_entities()
                    for entity in all_entities:
                        if (hasattr(entity, 'name') and entity.name == data['name'] and
                            hasattr(entity, 'entity_type') and entity.entity_type == data['entity_type'] and
                            not getattr(entity, 'is_group_parent', False) and
                                not getattr(entity, 'parent_entity', None)):
                            # Transformer en parent de groupe
                            entity.is_group_parent = True
                            entity.group_id = f"group_{uuid.uuid4().hex[:8]}"
                            if not hasattr(entity, 'child_entities'):
                                entity.child_entities = []
                            target_parent = entity

                            # Synchroniser l'historique Undo/Redo avec le nouveau statut du parent
                            self._refresh_group_snapshot(target_parent)

                            # Mettre à jour l'affichage
                            if hasattr(entity, 'draw') and hasattr(entity, 'scene_ref') and entity.scene_ref:
                                entity.draw(entity.scene_ref)
                            break

            # Créer la nouvelle entité selon le type
            if data['entity_type'] == 'polygon':
                # Créer les nouveaux points avec décalage
                new_points = [QPointF(p.x() + offset_x, p.y() + offset_y)
                              for p in data['points']]

                new_entity = PolygonEntity(
                    points=new_points,
                    pixels_per_meter=data['pixels_per_meter']
                )

                # Restaurer les propriétés
                new_entity.name = data['name']
                new_entity.color = QColor(data['color'])
                new_entity.fill_pattern = data['fill_pattern']
                new_entity.is_perimeter = data['is_perimeter']
                
                # CRITIQUE : Restaurer les dimensions (hauteur, épaisseur) lors du collage
                # Sans ceci, les surfaces collées perdent leur volume
                new_entity.height = data.get('height', 0.0)
                new_entity.thickness = data.get('thickness', 0.0)

                # Restaurer l'affichage des mesures : la copie suit l'original
                new_entity.show_measure = data.get('show_measure', False)

                # ✅ IMPORTANT : Configurer le groupement avec le parent identifié
                if target_parent:
                    new_entity.parent_entity = target_parent
                    new_entity.group_id = target_parent.group_id
                    new_entity.is_group_parent = False

                    # Ajouter aux enfants du parent
                    if not hasattr(target_parent, 'child_entities'):
                        target_parent.child_entities = []
                    target_parent.child_entities.append(new_entity)
                    
                    # CRITIQUE : Si l'entité collée n'a pas de dimensions, hériter du parent
                    # Ceci permet de coller des surfaces simples dans un groupe avec volume
                    if new_entity.height == 0.0:
                        new_entity.height = getattr(target_parent, 'height', 0.0)
                    if new_entity.thickness == 0.0:
                        new_entity.thickness = getattr(target_parent, 'thickness', 0.0)

                    action = 'restaurée' if self.cut_mode else 'ajoutée'
                else:
                    # Standalone : créer un group_id propre pour pouvoir recevoir des affectations
                    new_group_id = f"group_{uuid.uuid4().hex[:8]}"
                    new_entity.is_group_parent = True
                    new_entity.group_id = new_group_id
                    if not hasattr(new_entity, 'child_entities'):
                        new_entity.child_entities = []

                    # Copier les affectations de l'entité source vers la nouvelle
                    source_group_id = data.get('group_id')
                    if source_group_id and hasattr(self, 'devis_manager') and self.devis_manager:
                        self.devis_manager.copy_assignments(
                            source_group_id, new_group_id,
                            target_name=new_entity.name,
                            target_type='polygon'
                        )

                # Dessiner la nouvelle entité
                if hasattr(self.canvas_view, 'scene'):
                    new_entity.draw(self.canvas_view.scene)

                # Ajouter au gestionnaire d'entités
                if hasattr(self.canvas_view, 'entity_manager') and self.canvas_view.entity_manager:
                    entity_id = self.canvas_view.entity_manager.add_entity(
                        new_entity)
                    new_entity.entity_id = entity_id

                    # Mettre à jour le data(1) de l'item graphique
                    if hasattr(new_entity, 'surface_item') and new_entity.surface_item:
                        new_entity.surface_item.setData(1, entity_id)

                    # Après l'ajout, mettre à jour le snapshot du parent avec les bons IDs d'enfants
                    if target_parent:
                        self._refresh_group_snapshot(target_parent)

                # ✅ NOUVEAU : Recréer les ouvertures si elles existent
                if 'openings' in data and data['openings']:

                    for opening_data in data['openings']:
                        # Créer les points de l'ouverture avec le même décalage
                        opening_points = [QPointF(p.x() + offset_x, p.y() + offset_y)
                                          for p in opening_data['points']]

                        # Créer l'ouverture
                        new_opening = OpeningEntity(
                            points=opening_points,
                            pixels_per_meter=opening_data['pixels_per_meter'],
                            color=QColor(opening_data['color']),
                            name=opening_data['name']
                        )

                        # Dessiner l'ouverture
                        if hasattr(self.canvas_view, 'scene'):
                            new_opening.draw(self.canvas_view.scene)

                        # ✅ CRITIQUE : Lier l'ouverture à la surface AVANT add_entity
                        # pour que on_entity_added() sache que c'est une ouverture attachée
                        new_entity.add_opening(new_opening)

                        # Ajouter au gestionnaire APRÈS avoir établi le lien parent
                        if hasattr(self.canvas_view, 'entity_manager') and self.canvas_view.entity_manager:
                            opening_id = self.canvas_view.entity_manager.add_entity(
                                new_opening)
                            new_opening.entity_id = opening_id

                            if hasattr(new_opening, 'polygon_item') and new_opening.polygon_item:
                                new_opening.polygon_item.setData(1, opening_id)

                    # Mettre à jour l'affichage de la surface avec les ouvertures
                    if hasattr(new_entity, 'scene_ref') and new_entity.scene_ref:
                        new_entity.draw(new_entity.scene_ref)


            elif data['entity_type'] == 'perimeter':
                # Créer les nouveaux points avec décalage
                new_points = [QPointF(p.x() + offset_x, p.y() + offset_y)
                              for p in data['points']]

                # Créer la nouvelle entité
                new_entity = PerimeterEntity(
                    points=new_points,
                    color=QColor(data['color']),
                    width=data['width'],
                    pixels_per_meter=data['pixels_per_meter'],
                    name=data['name']
                )
                
                # CRITIQUE : Restaurer les dimensions (hauteur, épaisseur) lors du collage
                # Sans ceci, les périmètres collés perdent leur volume/surface latérale
                new_entity.height = data.get('height', 0.0)
                new_entity.thickness = data.get('thickness', 0.0)

                # Restaurer l'affichage des mesures : la copie suit l'original
                new_entity.show_measure = data.get('show_measure', False)

                # Restaurer le groupement pour les périmètres
                if target_parent:
                    new_entity.parent_entity = target_parent
                    new_entity.group_id = target_parent.group_id
                    new_entity.is_group_parent = False

                    if not hasattr(target_parent, 'child_entities'):
                        target_parent.child_entities = []
                    target_parent.child_entities.append(new_entity)
                    
                    # CRITIQUE : Si le périmètre collé n'a pas de dimensions, hériter du parent
                    # Ceci permet de coller des périmètres simples dans un groupe avec volume
                    if new_entity.height == 0.0:
                        new_entity.height = getattr(target_parent, 'height', 0.0)
                    if new_entity.thickness == 0.0:
                        new_entity.thickness = getattr(target_parent, 'thickness', 0.0)
                else:
                    # Standalone : créer un group_id propre pour pouvoir recevoir des affectations
                    new_group_id = f"group_{uuid.uuid4().hex[:8]}"
                    new_entity.is_group_parent = True
                    new_entity.group_id = new_group_id
                    if not hasattr(new_entity, 'child_entities'):
                        new_entity.child_entities = []

                    # Copier les affectations de l'entité source vers la nouvelle
                    source_group_id = data.get('group_id')
                    if source_group_id and hasattr(self, 'devis_manager') and self.devis_manager:
                        self.devis_manager.copy_assignments(
                            source_group_id, new_group_id,
                            target_name=new_entity.name,
                            target_type='perimeter'
                        )


                # Dessiner
                if hasattr(self.canvas_view, 'scene'):
                    new_entity.draw(self.canvas_view.scene)

                # Ajouter au gestionnaire
                if hasattr(self.canvas_view, 'entity_manager') and self.canvas_view.entity_manager:
                    entity_id = self.canvas_view.entity_manager.add_entity(
                        new_entity)
                    new_entity.entity_id = entity_id

                    if hasattr(new_entity, 'path_item') and new_entity.path_item:
                        new_entity.path_item.setData(1, entity_id)

                # ✅ NOUVEAU : Restaurer les ouvertures linéaires si elles existent
                if 'linear_openings' in data and data['linear_openings']:

                    import copy
                    new_entity.linear_openings = copy.deepcopy(
                        data['linear_openings'])

                    # Redessiner le périmètre avec les ouvertures
                    if hasattr(new_entity, 'scene_ref') and new_entity.scene_ref:
                        new_entity.draw(new_entity.scene_ref)

                    # Vérifier le calcul
                    total_length = new_entity.calculate_perimeter_length()

                    for i, opening in enumerate(new_entity.linear_openings):
                        pass

            else:
                self.statusBar().showMessage("❌ Type d'entité non supporté", 3000)
                return

            # ✅ CRUCIAL : Émettre le signal du parent pour mise à jour automatique
            if target_parent:
                if hasattr(target_parent, 'geometryChanged'):
                    target_parent.geometryChanged.emit()

                # Mettre à jour l'affichage du parent pour refléter le nouveau total
                if hasattr(target_parent, 'draw') and hasattr(target_parent, 'scene_ref') and target_parent.scene_ref:
                    target_parent.draw(target_parent.scene_ref)

            # ✅ Si c'était un couper, vider le presse-papier
            if self.cut_mode and clear_clipboard:
                self.clipboard_entity = None
                self.cut_mode = False

            # Mettre à jour l'interface
            self.update_quantities_table()
            self.update_properties_entities_list()

            # Mettre à jour la légende
            if hasattr(self.canvas_view, 'update_legend'):
                self.canvas_view.update_legend()

            action_text = "restaurée" if self.cut_mode else "collée"
            group_info = f" dans le groupe '{target_parent.name}'" if target_parent else ""
            self.statusBar().showMessage(
                f"✅ '{new_entity.name}' {action_text}{group_info}", 3000)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(
                f"❌ Erreur lors du collage: {e}", 3000)

    def _update_tools_for_scale_state(self, has_scale: bool) -> None:
        """Active ou désactive les outils de mesure selon que l'échelle est définie.

        has_scale=False → outils de dessin grisés + bannière orange dans la barre de statut.
                          scale_action reste TOUJOURS actif.
        has_scale=True  → tous les outils réactivés + message vert.
        """
        # S'assurer que scale_action est TOUJOURS actif (jamais bloqué)
        if hasattr(self, "scale_action"):
            self.scale_action.setEnabled(True)

        # Activer/désactiver les outils de dessin (hors échelle)
        for action in getattr(self, "_measurement_actions", []):
            action.setEnabled(has_scale)

        # Mise à jour du measure_label (barre de statut)
        if hasattr(self, "measure_label"):
            if not has_scale:
                self.measure_label.setText(
                    "⚠️  Calibrez l'échelle avant de dessiner des mesures")
                self.measure_label.setStyleSheet(
                    "color:#bf360c; font-weight:bold; background:#fff3e0;"
                    "padding:2px 8px; border-radius:3px;")
            else:
                self.measure_label.setText("✅  Échelle définie — vous pouvez mesurer")
                self.measure_label.setStyleSheet(
                    "color:#1b5e20; font-weight:bold; background:#e8f5e9;"
                    "padding:2px 8px; border-radius:3px;")

    def _refresh_all_panels_after_undo_redo(self):
        """Rafraîchit tous les panneaux après un undo/redo complet.

        Appelé APRÈS que toutes les entités ont été ajoutées/supprimées
        ET que les liens de groupe ont été rétablis (_restore_group_connections).
        Ceci corrige le bug où le dernier enfant redone apparaissait en standalone
        car refresh() était déclenché avant que son parent_entity soit réassigné.
        """
        self.update_quantities_table()
        self.update_properties_entities_list()
        if hasattr(self, 'canvas_view') and hasattr(self.canvas_view, 'update_legend'):
            self.canvas_view.update_legend()
        # Reconstruire complètement le panneau Pages & Mesures avec les liens de groupe corrects
        if hasattr(self, 'pdf_navigator'):
            try:
                self.pdf_navigator.refresh()
            except Exception as e:
                pass

    def undo(self):
        """Annule la dernière action"""
        if hasattr(self, 'undo_redo_manager'):
            if self.undo_redo_manager.undo():
                self._refresh_all_panels_after_undo_redo()

    def redo(self):
        """Refait la dernière action annulée"""
        if hasattr(self, 'undo_redo_manager'):
            if self.undo_redo_manager.redo():
                self._refresh_all_panels_after_undo_redo()

    def on_history_changed(self):
        """Appelé quand l'historique Undo/Redo change"""
        if hasattr(self, 'undo_redo_manager'):
            # Mettre à jour les tooltips des actions
            if hasattr(self, 'undo_action'):
                self.undo_action.setToolTip(
                    self.undo_redo_manager.get_undo_text())
            if hasattr(self, 'redo_action'):
                self.redo_action.setToolTip(
                    self.undo_redo_manager.get_redo_text())

    def _update_parent_surface_snapshot(self, parent_surface, opening):
        """Met à jour le snapshot de la surface parent pour inclure la nouvelle ouverture"""
        if not hasattr(self, 'undo_redo_manager'):
            return

        # Trouver la commande AddEntityCommand correspondant à cette surface
        from core.undo_redo_manager import AddEntityCommand

        for command in reversed(self.undo_redo_manager.undo_stack):
            # ✅ Vérifier que c'est bien une AddEntityCommand (pas PropertyChangeCommand)
            if not isinstance(command, AddEntityCommand):
                continue

            if (hasattr(command, 'entity_id') and
                hasattr(parent_surface, 'entity_id') and
                    command.entity_id == parent_surface.entity_id):

                # Mettre à jour le snapshot avec les ouvertures actuelles
                if 'openings' not in command.entity_data:
                    command.entity_data['openings'] = []

                # Ajouter cette ouverture au snapshot
                command.entity_data['openings'].append({
                    'points': [(p.x(), p.y()) for p in opening.points],
                    'name': opening.name,
                    'color': opening.color.name(),
                    'pixels_per_meter': opening.pixels_per_meter
                })
                break

    def _refresh_group_snapshot(self, entity):
        """Met à jour le snapshot Undo/Redo d'une entité avec ses informations de groupe"""
        if not entity or not hasattr(entity, 'entity_id'):
            return
        if not hasattr(self, 'undo_redo_manager'):
            return

        from core.undo_redo_manager import AddEntityCommand

        for command in reversed(self.undo_redo_manager.undo_stack):
            if not isinstance(command, AddEntityCommand):
                continue
            if getattr(command, 'entity_id', None) != entity.entity_id:
                continue

            command.entity_data['is_group_parent'] = getattr(
                entity, 'is_group_parent', False)
            command.entity_data['group_id'] = getattr(
                entity, 'group_id', None)

            parent = getattr(entity, 'parent_entity', None)
            command.entity_data['parent_entity_id'] = parent.entity_id if parent else None

            child_entities = getattr(entity, 'child_entities', [])
            child_ids = [child.entity_id for child in child_entities if hasattr(
                child, 'entity_id') and child.entity_id]
            command.entity_data['child_entity_ids'] = child_ids
            break

    def _refresh_entity_geometry_snapshot(self, entity):
        """Actualise les données géométriques utilisées lors d'un futur REDO"""
        if not entity or not hasattr(entity, 'entity_id'):
            return
        if not hasattr(self, 'undo_redo_manager') or not self.undo_redo_manager._enabled:
            return

        from core.undo_redo_manager import AddEntityCommand

        entity_id = getattr(entity, 'entity_id', None)
        if not entity_id:
            return

        for command in reversed(self.undo_redo_manager.undo_stack):
            if not isinstance(command, AddEntityCommand):
                continue
            if getattr(command, 'entity_id', None) != entity_id:
                continue

            try:
                snapshot = self.undo_redo_manager.snapshot_entity_geometry(
                    entity)
                if snapshot:
                    command.entity_data = snapshot
                else:
                    pass
            except Exception as e:
                pass
            break

    def _format_area(self, value):
        """Formate une valeur de surface en m² avec séparateur français"""
        if value is None:
            return "0,00 m²"
        formatted = f"{value:,.2f}"
        formatted = formatted.replace(",", " ").replace(".", ",")
        return f"{formatted} m²"

    def _safe_entity_area(self, entity):
        """Retourne l'aire nette ou totale du groupe en toute sécurité"""
        if not entity:
            return None
        try:
            if getattr(entity, 'is_group_parent', False) and getattr(entity, 'child_entities', []):
                if hasattr(entity, 'calculate_total_group_area'):
                    return entity.calculate_total_group_area()
            if hasattr(entity, 'calculate_net_area'):
                return entity.calculate_net_area()
        except Exception as e:
            pass
        return None

    def update_toolbar_selection(self, entity):
        """Met à jour le badge de sélection dans la barre d'outils"""
        if not hasattr(self, 'toolbar_selection_label'):
            return

        focus_entity = entity
        if focus_entity and hasattr(focus_entity, 'parent_entity') and focus_entity.parent_entity:
            focus_entity = focus_entity.parent_entity

        if focus_entity:
            display_name = getattr(focus_entity, 'name', 'Entité')
            child_count = len(
                getattr(focus_entity, 'child_entities', []) or [])
            if getattr(focus_entity, 'is_group_parent', False) and child_count:
                text = f"Sélection : {display_name} (×{child_count + 1})"
            else:
                text = f"Sélection : {display_name}"

            area = self._safe_entity_area(focus_entity)
            if area is not None:
                text += f" • {self._format_area(area)}"
        else:
            text = "Sélection : aucune"

        self.toolbar_selection_label.setText(text)

    def update_toolbar_summary(self):
        """Met à jour la synthèse de surface globale"""
        if not hasattr(self, 'toolbar_summary_label'):
            return

        manager = getattr(self.canvas_view, 'entity_manager', None)
        if not manager:
            self.toolbar_summary_label.setText("Total : 0,00 m²")
            return

        total_area = 0.0
        group_count = 0

        for entity in manager.get_all_entities():
            if getattr(entity, 'entity_type', None) != 'polygon':
                continue
            if getattr(entity, 'parent_entity', None):
                continue

            if getattr(entity, 'is_group_parent', False) and getattr(entity, 'child_entities', []):
                group_count += 1
                total_area += self._safe_entity_area(entity) or 0.0
            else:
                total_area += self._safe_entity_area(entity) or 0.0

        summary = f"Total : {self._format_area(total_area)}"
        if group_count:
            summary += f" • Groupes : {group_count}"
        self.toolbar_summary_label.setText(summary)

    # ------------------------------------------------------------------
    # Projet (.mtp)
    # ------------------------------------------------------------------
    # ── Impression ────────────────────────────────────────────────────────────

    def print_page(self):
        """Imprime la page courante (plan + mesures) via QPrinter."""
        from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt5.QtGui import QPainter
        from PyQt5.QtCore import QRectF, Qt

        if not hasattr(self, 'canvas_view') or not self.canvas_view.scene:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "Impression",
                                    "Aucun plan à imprimer. Chargez d'abord un plan.")
            return

        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageOrientation(
            __import__('PyQt5.QtGui', fromlist=['QPageLayout']).QPageLayout.Landscape)

        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("Imprimer la page")
        if dlg.exec_() != QPrintDialog.Accepted:
            return

        painter = QPainter(printer)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Zone d'impression disponible
        page_rect = QRectF(printer.pageRect())

        # En-tête : nom du projet + page
        meta = getattr(self, 'project_metadata', {})
        proj_name = meta.get('name', 'Métraplan')
        page_idx  = getattr(self, 'current_pdf_page_index', None)
        pages     = self._managed_pages() if hasattr(self, '_managed_pages') else []
        page_name = ""
        if page_idx is not None and 0 <= page_idx < len(pages):
            page_name = getattr(pages[page_idx], 'name', f"Page {page_idx+1}")

        from PyQt5.QtGui import QFont
        hdr_font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(hdr_font)
        header_h = printer.logicalDpiY() * 0.3   # ~0.3 pouce
        header_rect = QRectF(page_rect.left(), page_rect.top(),
                             page_rect.width(), header_h)
        painter.drawText(header_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         f"  {proj_name}  —  {page_name}")
        painter.drawLine(
            int(page_rect.left()), int(page_rect.top() + header_h),
            int(page_rect.right()), int(page_rect.top() + header_h))

        # Zone plan
        content_rect = QRectF(
            page_rect.left(), page_rect.top() + header_h + 6,
            page_rect.width(), page_rect.height() - header_h - 6)

        # Rendu de la scène
        self.canvas_view.scene.render(painter, content_rect,
                                      self.canvas_view.scene.itemsBoundingRect())
        painter.end()
        self.statusBar().showMessage("Page envoyée à l'impression.", 3000)

    # ── Handlers menu Fichier ─────────────────────────────────────────────────

    def close_project(self):
        """Ferme le projet courant et réinitialise l'espace de travail."""
        reply = QMessageBox.question(
            self,
            "Fermer le projet",
            "Voulez-vous fermer le projet courant ?\n"
            "Les modifications non enregistrées seront perdues.",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply == QMessageBox.Cancel:
            return
        if reply == QMessageBox.Save:
            self.save_project()
        # Réinitialiser l'espace de travail
        try:
            if hasattr(self.canvas_view, "entity_manager"):
                self.canvas_view.entity_manager.clear_all(self.canvas_view.scene)
            if hasattr(self.canvas_view, "scene"):
                self.canvas_view.scene.clear()
            self.pdf_document = None
            self._all_pages = []
            self._pdf_import_offset = 0
            self.current_pdf_page_index = None
            self.pdf_dock.hide()
            self.canvas_view.image_item = None
            self.statusBar().showMessage("Projet fermé.", 3000)
        except Exception as e:
            pass

    def show_help(self):
        """Affiche l'aide hors ligne."""
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Aide Métraplan",
            "L'aide hors ligne sera disponible dans une prochaine version.\n\n"
            "Pour toute question, consultez le tutoriel en ligne via\n"
            "Fichier → Tutoriel en ligne."
        )

    def open_tutorial(self):
        """Ouvre le tutoriel en ligne dans le navigateur par défaut."""
        import webbrowser
        webbrowser.open("https://www.metraplan.com/tutoriels")

    def show_about(self):
        """Affiche la boîte de dialogue À propos."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont

        dlg = QDialog(self)
        dlg.setWindowTitle("À propos de Métraplan")
        dlg.setFixedWidth(400)
        dlg.setStyleSheet("background: white;")

        v = QVBoxLayout(dlg)
        v.setSpacing(8)
        v.setContentsMargins(24, 20, 24, 20)

        # Titre
        title = QLabel("Métraplan")
        f = QFont("Segoe UI", 18, QFont.Bold)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1976d2;")
        v.addWidget(title)

        # Version
        from version import APP_VERSION, APP_COPYRIGHT
        ver = QLabel(f"Version {APP_VERSION}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color: #5a7090; font-size: 12px;")
        v.addWidget(ver)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #d0dce8;")
        v.addWidget(sep)

        # Lire les infos de licence depuis le stockage local
        from core.license_manager import LicenseManager
        _stored = LicenseManager().get_stored_info()
        if _stored:
            _key     = _stored.get("license_key", "—")
            _exp     = _stored.get("expires_at", "")[:10] or "—"
            _client  = _stored.get("client_name", "")
            _lic_lines = [
                f"Numéro de licence : {_key}",
                f"Expiration : {_exp}",
            ]
            if _client:
                _lic_lines.insert(0, f"Client : {_client}")
        else:
            _lic_lines = ["Numéro de licence : Non activé"]

        # Infos
        for ligne in [
            "Logiciel de métré et de prise de quantités",
            APP_COPYRIGHT,
            "",
            *_lic_lines,
            "",
            "Support : support@metraplan.com",
        ]:
            lbl = QLabel(ligne)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 11px; color: #444;")
            v.addWidget(lbl)

        v.addSpacing(8)
        btn = QPushButton("Fermer")
        btn.setFixedWidth(100)
        btn.clicked.connect(dlg.accept)
        btn.setStyleSheet(
            "QPushButton { background:#1976d2; color:white; border-radius:4px;"
            "padding:5px 16px; font-size:11px; }"
            "QPushButton:hover { background:#1565c0; }"
        )
        v.addWidget(btn, alignment=Qt.AlignCenter)
        dlg.exec_()

    def deactivate_license(self):
        """Dialogue de désactivation / transfert de licence."""
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.warning(
            self,
            "Désactiver la clé de produit",
            "Attention : Cette action désactivera Métraplan sur cet ordinateur.\n\n"
            "Vous devrez réintroduire votre numéro de licence pour réactiver\n"
            "le logiciel sur un autre ordinateur.\n\n"
            "Êtes-vous sûr de vouloir continuer ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            from core.license_manager import LicenseManager
            LicenseManager().deactivate()
            QMessageBox.information(
                self, "Désactivation réussie",
                "Métraplan a été désactivé sur cet ordinateur.\n\n"
                "Vous pouvez maintenant activer votre licence sur un autre PC.\n"
                "Le logiciel va se fermer."
            )
            import sys
            sys.exit(0)

    def new_project(self):
        """Ouvre l'assistant de nouveau projet."""
        from ui.new_project_wizard import NewProjectWizard

        # Si un projet est ouvert, demander confirmation
        if self._project_file_path or self.pdf_document or self._all_pages or (
                hasattr(self, 'canvas_view') and
                hasattr(self.canvas_view, 'entity_manager') and
                self.canvas_view.entity_manager.get_all_entities()):
            reply = QMessageBox.question(
                self,
                "Nouveau projet",
                "Créer un nouveau projet ?\n"
                "Les modifications non enregistrées seront perdues.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        wizard = NewProjectWizard(self)
        if wizard.exec_() != NewProjectWizard.Accepted:
            return

        data = wizard.get_result()

        # ── Réinitialiser l'espace de travail ─────────────────────────────
        try:
            if hasattr(self.canvas_view, "entity_manager"):
                self.canvas_view.entity_manager.clear_all(self.canvas_view.scene)
            if hasattr(self.canvas_view, "scene") and self.canvas_view.scene:
                self.canvas_view.scene.clear()
        except Exception as e:
            pass

        self.pdf_document = None
        self._all_pages = []
        self._pdf_import_offset = 0
        self.current_pdf_page_index = None
        self._pdf_file_path = None
        self._project_file_path = None

        # ── Stocker les métadonnées du projet ─────────────────────────────
        self.project_metadata = {
            "name":           data.get("project_name", ""),
            "number":         data.get("project_number", ""),
            "created_date":   data.get("created_date", ""),
            "owner":          data.get("owner", ""),
            "architect":      data.get("architect", ""),
            "company":        data.get("company", ""),
            "directory":      data.get("directory", ""),
        }

        # Répertoire de sauvegarde automatique si fourni
        directory = data.get("directory", "")
        project_name = data.get("project_name", "NouveauProjet")
        if directory:
            import os
            auto_path = os.path.join(directory, f"{project_name}.mtp")
            self._project_file_path = auto_path

        if hasattr(self, "pdf_navigator") and self.pdf_navigator:
            self.pdf_navigator.set_pages([])

        self.update_quantities_table()
        self.update_properties_entities_list()
        self.setWindowTitle(f"Métraplan — {project_name}")
        self.statusBar().showMessage(
            f"Nouveau projet « {project_name} » créé.", 3000)

        # ── Charger le plan selon le choix de l'étape 2 ───────────────────
        plan_source = data.get("plan_source", "none")
        if plan_source == "pdf":
            self.import_pdf()
        elif plan_source == "image":
            self.open_image()

    def save_project(self):
        """Enregistre le projet courant (ou ouvre Enregistrer sous si nécessaire)."""
        if not self._project_file_path:
            return self.save_project_as()

        if save_project_file(self, self._project_file_path):
            self._unsaved_changes = False
            self._add_to_recent(self._project_file_path)
            self.statusBar().showMessage(
                f"Projet enregistré: {self._project_file_path}", 3000)
            return True
        QMessageBox.warning(self, "Erreur", "Impossible d'enregistrer le projet.")
        return False

    def save_project_as(self):
        """Demande un chemin puis enregistre le projet."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le projet",
            self._project_file_path or "",
            PROJECT_FILTER,
        )
        if not file_path:
            return False

        file_path = ensure_project_extension(file_path)
        if save_project_file(self, file_path):
            self._project_file_path = file_path
            self._unsaved_changes = False
            self._add_to_recent(file_path)
            self.statusBar().showMessage(f"Projet enregistré: {file_path}", 3000)
            return True

        QMessageBox.warning(self, "Erreur", "Impossible d'enregistrer le projet.")
        return False

    def load_project(self):
        """Charge un projet .mtp et restaure pages + mesures."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un projet",
            "",
            PROJECT_FILTER,
        )
        if not file_path:
            return False

        if load_project_file(self, file_path):
            self._project_file_path = file_path
            self._unsaved_changes = False
            self._add_to_recent(file_path)
            self.statusBar().showMessage(f"Projet chargé: {file_path}", 3000)
            self.update_quantities_table()
            self.update_properties_entities_list()
            # Afficher les panneaux latéraux au chargement du projet
            if hasattr(self, 'pdf_dock') and self.pdf_dock:
                self.pdf_dock.show()
            if hasattr(self, 'properties_dock') and self.properties_dock:
                self.properties_dock.show()
            # Au chargement : ouvrir seulement la page courante comme onglet
            cur = self.current_pdf_page_index or 0
            self._open_tabs = [cur] if self._all_pages else []
            self._sync_tab_bar(cur)
            return True

        QMessageBox.warning(self, "Erreur", "Impossible de charger le projet.")
        return False

    # ── Autosave ──────────────────────────────────────────────────────────────

    def _autosave(self) -> None:
        """Sauvegarde silencieuse toutes les 10 min si des modifications existent."""
        if not self._unsaved_changes:
            return
        import os, tempfile
        # Chemin autosave : fichier courant + suffixe .autosave.mtp
        if self._project_file_path:
            base = self._project_file_path
        else:
            base = os.path.join(tempfile.gettempdir(), "metraplan_autosave.mtp")
        autosave_path = base + ".autosave.mtp"
        from core.project_manager import save_project as save_project_file
        try:
            save_project_file(self, autosave_path)
            self.statusBar().showMessage(
                f"Autosave : {os.path.basename(autosave_path)}", 3000)
        except Exception:
            pass   # Autosave silencieux — ne jamais interrompre l'utilisateur

    # ── Fichiers récents ──────────────────────────────────────────────────────

    def _add_to_recent(self, path: str) -> None:
        """Ajoute un chemin en tête de la liste des fichiers récents."""
        if not path:
            return
        if path in self._recent_files:
            self._recent_files.remove(path)
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:self._MAX_RECENT]
        self._settings.setValue("recent_files", self._recent_files)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        """Met à jour le sous-menu Fichiers récents."""
        menu = getattr(self, "_recent_menu", None)
        if menu is None:
            return
        menu.clear()
        for path in self._recent_files:
            import os
            act = menu.addAction(os.path.basename(path))
            act.setToolTip(path)
            act.setStatusTip(path)
            act.triggered.connect(lambda checked, p=path: self._open_recent(p))
        if not self._recent_files:
            placeholder = menu.addAction("(aucun fichier récent)")
            placeholder.setEnabled(False)

    def _open_recent(self, path: str) -> None:
        """Ouvre un projet récent après vérification d'existence."""
        import os
        if not os.path.exists(path):
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Fichier introuvable",
                                f"Le fichier n'existe plus :\n{path}")
            self._recent_files = [f for f in self._recent_files if f != path]
            self._settings.setValue("recent_files", self._recent_files)
            self._refresh_recent_menu()
            return
        from core.project_manager import load_project as load_project_file
        if load_project_file(self, path):
            self._project_file_path = path
            self._unsaved_changes = False
            self._add_to_recent(path)
            self.statusBar().showMessage(f"Projet chargé : {path}", 3000)
            self.update_quantities_table()
            self.update_properties_entities_list()

    # ── Protection à la fermeture ─────────────────────────────────────────────

    def closeEvent(self, event):
        """Avertit l'utilisateur si des modifications non sauvegardées existent
        et sauvegarde la géométrie de la fenêtre pour la prochaine session."""
        if self._unsaved_changes:
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Modifications non sauvegardées",
                "Des modifications n'ont pas été enregistrées.\n\n"
                "Voulez-vous enregistrer avant de quitter ?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Save:
                if not self.save_project():
                    event.ignore()   # Sauvegarde échouée → ne pas fermer
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        # Sauvegarder la géométrie et l'état des docks
        self._settings.setValue("geometry",    self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        self._settings.setValue("recent_files", self._recent_files)
        event.accept()
