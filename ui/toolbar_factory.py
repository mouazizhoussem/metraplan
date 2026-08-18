# ui/toolbar_factory.py
"""
Ruban à onglets Metraplan — style CAO professionnel.
  Onglet 0 – Accueil : outils de mesure, historique, vues
  Onglet 1 – Page    : rotation, retournement, luminosité, recadrage
  Onglet 2 – Rapport : (à venir)
"""
from PyQt5.QtWidgets import (
    QToolBar, QWidget, QSizePolicy, QLabel, QFrame,
    QActionGroup, QTabBar, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QToolButton, QMenu, QAction,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont

from ui.ribbon_icons import get_icon

# ── Constantes ────────────────────────────────────────────────────────────────
_ICON    = QSize(32, 32)
_ICON_SM = QSize(26, 26)
_TAB_H   = 82   # hauteur zone boutons
_BTN_QSS = """
QToolButton {
    border: none; border-radius: 5px;
    padding: 5px 8px;
    color: #2a3a5a;
    font-size: 11px;
    min-width: 48px;
    background: transparent;
}
QToolButton:hover  { background: #d0ddf0; }
QToolButton:checked { background: #1976d2; color: white; }
QToolButton:pressed { background: #1565c0; color: white; }
QToolButton:disabled { color: #aabbc8; }
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assign_icon(action, name: str, size: int = 36):
    icon = get_icon(name, size)
    if not icon.isNull():
        action.setIcon(icon)


def _vline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setFixedWidth(1)
    f.setStyleSheet("background: #c0ccd8; margin: 6px 2px;")
    return f


def _btn(action, icon_size=None, style=Qt.ToolButtonTextUnderIcon) -> QToolButton:
    b = QToolButton()
    b.setDefaultAction(action)
    b.setIconSize(icon_size or _ICON)
    b.setToolButtonStyle(style)
    b.setAutoRaise(True)
    b.setStyleSheet(_BTN_QSS)
    return b


def _group(title: str, buttons: list) -> QWidget:
    """Groupe de boutons avec étiquette en bas (style ruban CAO)."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setSpacing(2)
    v.setContentsMargins(5, 4, 5, 0)

    row = QHBoxLayout()
    row.setSpacing(3)
    row.setContentsMargins(0, 0, 0, 0)
    row.setAlignment(Qt.AlignHCenter)
    for b in buttons:
        row.addWidget(b)
    v.addLayout(row)
    v.addStretch()

    lbl = QLabel(title)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedHeight(16)
    lbl.setStyleSheet(
        "font-size: 10px; color: #7090b0; font-weight: bold;"
        "border-top: 1px solid #d0d8e8; padding-top: 2px;"
    )
    v.addWidget(lbl)
    return w


def _tab_row(*groups) -> QWidget:
    """Ligne de groupes séparés pour un onglet."""
    w = QWidget()
    w.setStyleSheet("background: #e8ecf2;")
    h = QHBoxLayout(w)
    h.setSpacing(0)
    h.setContentsMargins(8, 2, 8, 0)
    h.setAlignment(Qt.AlignLeft)
    for i, g in enumerate(groups):
        h.addWidget(g)
        if i < len(groups) - 1:
            h.addWidget(_vline())
    h.addStretch()
    return w


# ── Construction des onglets ──────────────────────────────────────────────────

def _build_fichier(window) -> QWidget:
    """Widget vide — l'onglet Fichier s'affiche comme un menu déroulant."""
    w = QWidget()
    w.setStyleSheet("background: #e8ecf2;")
    return w


def _build_accueil(window) -> QWidget:
    w = window

    # — Groupe exclusif pour tous les outils de dessin/mesure —
    tool_grp = QActionGroup(w)
    tool_grp.setExclusive(True)

    # — Navigation (Pointeur + Pan) —
    _assign_icon(w.pointer_action, "pointer"); w.pointer_action.setText("Pointeur")
    _assign_icon(w.pan_action,     "pan");     w.pan_action.setText("Pan")
    tool_grp.addAction(w.pointer_action)
    tool_grp.addAction(w.pan_action)
    w.pointer_action.setChecked(True)   # actif par défaut au démarrage
    grp_navigation = _group("Navigation", [
        _btn(w.pointer_action),
        _btn(w.pan_action),
    ])

    # — Importer —
    _assign_icon(w.import_pdf_action, "import_pdf"); w.import_pdf_action.setText("PDF")
    _assign_icon(w.open_action,       "open");       w.open_action.setText("Image")
    grp_import = _group("Importer", [
        _btn(w.import_pdf_action), _btn(w.open_action),
    ])

    # — Historique (Annuler / Refaire) —
    _assign_icon(w.undo_action, "undo")
    _assign_icon(w.redo_action, "redo")
    w.undo_action.setText("Annuler")
    w.redo_action.setText("Refaire")
    grp_historique = _group("Historique", [
        _btn(w.undo_action), _btn(w.redo_action),
    ])

    # — Mesure (Échelle + Distance) —
    _assign_icon(w.scale_action,    "scale");    w.scale_action.setText("Échelle")
    _assign_icon(w.distance_action, "distance"); w.distance_action.setText("Distance")
    tool_grp.addAction(w.scale_action)
    tool_grp.addAction(w.distance_action)
    grp_mesure = _group("Mesure", [
        _btn(w.scale_action), _btn(w.distance_action),
    ])

    # — Dessiner (Surface, Périmètre, Compteur) —
    _assign_icon(w.surface_action,   "surface");   w.surface_action.setText("Surface")
    _assign_icon(w.perimeter_action, "perimeter"); w.perimeter_action.setText("Périmètre")
    _assign_icon(w.counter_action,   "counter");   w.counter_action.setText("Compteur")
    _assign_icon(w.opening_action,   "opening");   w.opening_action.setText("Ouverture")
    _assign_icon(w.ortho_action,     "ortho");     w.ortho_action.setText("Ortho")
    for a in [w.surface_action, w.perimeter_action, w.counter_action, w.opening_action]:
        tool_grp.addAction(a)
    grp_dessiner = _group("Dessiner", [
        _btn(w.surface_action), _btn(w.perimeter_action),
        _btn(w.counter_action), _btn(w.opening_action),
        _btn(w.ortho_action),
    ])

    w.tool_actions = [
        w.pointer_action, w.pan_action,
        w.scale_action, w.distance_action,
        w.surface_action, w.perimeter_action,
        w.counter_action, w.opening_action,
    ]

    # Outils bloqués tant que l'échelle n'est pas calibrée (scale_action exclu)
    # La désactivation est appliquée dynamiquement via _update_tools_for_scale_state()
    # appelé lors du chargement de chaque page — PAS ici pour éviter les conflits
    # avec le QActionGroup exclusif qui bloquerait même scale_action.
    w._measurement_actions = [
        w.distance_action,
        w.surface_action, w.perimeter_action,
        w.counter_action, w.opening_action,
    ]

    # — Zoom —
    _assign_icon(w.zoom_in_action,     "zoom_in");     w.zoom_in_action.setText("Zoom +")
    _assign_icon(w.zoom_out_action,    "zoom_out");    w.zoom_out_action.setText("Zoom −")
    _assign_icon(w.zoom_select_action, "zoom_select"); w.zoom_select_action.setText("Sélection")
    _assign_icon(w.zoom_100_action,    "zoom_100");    w.zoom_100_action.setText("100 %")

    btn_zoom_100 = QToolButton()
    btn_zoom_100.setDefaultAction(w.zoom_100_action)
    btn_zoom_100.setPopupMode(QToolButton.MenuButtonPopup)
    btn_zoom_100.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    zoom_menu = QMenu(btn_zoom_100)
    for pct in [100, 75, 50, 25]:
        act = QAction(f"{pct} %", btn_zoom_100)
        act.triggered.connect(
            (lambda p: lambda: w.canvas_view.zoom_to_percent(p)
             if hasattr(w, 'canvas_view') else None)(pct))
        zoom_menu.addAction(act)
    btn_zoom_100.setMenu(zoom_menu)

    grp_zoom = _group("Zoom", [
        _btn(w.zoom_in_action),
        _btn(w.zoom_out_action),
        _btn(w.zoom_select_action),
        btn_zoom_100,
    ])

    # — Annotation —
    _assign_icon(w.marker_action, "marker"); w.marker_action.setText("Marqueur")
    _assign_icon(w.note_action,   "note");   w.note_action.setText("Note")
    tool_grp.addAction(w.marker_action)
    tool_grp.addAction(w.note_action)
    grp_annotation = _group("Annotation", [
        _btn(w.marker_action), _btn(w.note_action),
    ])

    # — Impression —
    _assign_icon(w.print_action, "print"); w.print_action.setText("Imprimer")
    grp_print = _group("Impression", [_btn(w.print_action)])

    # — Info labels à droite —
    w.toolbar_selection_label = QLabel("Sélection : aucune")
    w.toolbar_selection_label.setObjectName("toolbarSelection")
    w.toolbar_summary_label = QLabel("Total : 0,00 m²")
    w.toolbar_summary_label.setObjectName("toolbarSummary")

    info_w = QWidget()
    info_w.setStyleSheet("background: transparent;")
    iv = QVBoxLayout(info_w)
    iv.setContentsMargins(10, 4, 10, 4)
    iv.setSpacing(2)
    iv.addWidget(w.toolbar_selection_label)
    iv.addWidget(w.toolbar_summary_label)

    # Assemblage
    tab_w = QWidget()
    tab_w.setStyleSheet("background: #e8ecf2;")
    h = QHBoxLayout(tab_w)
    h.setSpacing(0)
    h.setContentsMargins(8, 2, 8, 0)
    h.setAlignment(Qt.AlignLeft)
    for g in [grp_import, grp_historique, grp_navigation, grp_mesure, grp_dessiner, grp_annotation, grp_zoom, grp_print]:
        h.addWidget(g)
        h.addWidget(_vline())
    h.addStretch()
    h.addWidget(info_w)

    w.update_toolbar_selection(None)
    w.update_toolbar_summary()
    return tab_w


def _build_page(window) -> QWidget:
    w = window

    # — Rotation —
    _assign_icon(w.rotate_left_action,  "rotate_left");  w.rotate_left_action.setText("Gauche")
    _assign_icon(w.rotate_right_action, "rotate_right"); w.rotate_right_action.setText("Droite")
    _assign_icon(w.rotate_180_action,   "rotate_180");   w.rotate_180_action.setText("180°")
    grp_rot = _group("Rotation", [
        _btn(w.rotate_left_action),
        _btn(w.rotate_right_action),
        _btn(w.rotate_180_action),
    ])

    # — Retournement —
    _assign_icon(w.flip_h_action, "flip_h"); w.flip_h_action.setText("Horizontal")
    _assign_icon(w.flip_v_action, "flip_v"); w.flip_v_action.setText("Vertical")
    grp_flip = _group("Retournement", [_btn(w.flip_h_action), _btn(w.flip_v_action)])

    # — Ajustements —
    _assign_icon(w.brightness_action, "brightness"); w.brightness_action.setText("Luminosité")
    _assign_icon(w.crop_page_action,  "crop_page");  w.crop_page_action.setText("Rogner")
    grp_adj = _group("Ajustements", [_btn(w.brightness_action), _btn(w.crop_page_action)])

    return _tab_row(grp_rot, grp_flip, grp_adj)


def _build_devis(window) -> QWidget:
    """Onglet Devis : boutons de pilotage du panneau bibliothèque de devis."""
    from PyQt5.QtWidgets import QToolButton
    tab_w = QWidget()
    tab_w.setStyleSheet("background: #e8ecf2;")
    h = QHBoxLayout(tab_w)
    h.setContentsMargins(16, 6, 16, 6)
    h.setSpacing(6)

    btn_qss = """
    QToolButton {
        border: 1px solid #b0c4de; border-radius: 5px;
        padding: 5px 10px; font-size: 11px;
        color: #2a3a5a; background: #eef2fa; min-width: 70px;
    }
    QToolButton:hover   { background: #d0e4ff; border-color: #1976d2; }
    QToolButton:pressed { background: #bbdefb; }
    """

    def _make_btn(text, tooltip, cb):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(btn_qss)
        btn.clicked.connect(cb)
        return btn

    def _show_devis():
        dock = getattr(window, "devis_dock", None)
        if dock:
            dock.setVisible(True)
            dock.raise_()

    def _import_excel():
        panel = getattr(window, "devis_library_panel", None)
        if panel:
            panel._import_excel()

    def _save_model():
        panel = getattr(window, "devis_library_panel", None)
        if panel:
            panel._save_model()

    def _export_model():
        panel = getattr(window, "devis_library_panel", None)
        if panel:
            panel._export_model()

    def _load_model():
        panel = getattr(window, "devis_library_panel", None)
        if panel:
            panel._load_model()

    h.addWidget(_make_btn("📂\nImport Excel",
                          "Importer des lots/items depuis Excel", _import_excel))
    h.addWidget(_make_btn("📁\nCharger",
                          "Charger un modèle de devis (.devis)", _load_model))
    h.addWidget(_make_btn("💾\nEnregistrer",
                          "Enregistrer comme modèle par défaut", _save_model))
    h.addWidget(_make_btn("📤\nExporter",
                          "Exporter la bibliothèque en fichier .devis", _export_model))

    info = QLabel("Bibliothèque de devis — lots et items personnalisables")
    info.setStyleSheet("font-size:11px; color:#607080; padding-left:20px;")
    h.addWidget(info)
    h.addStretch()
    return tab_w


def _build_rapport(window) -> QWidget:
    """Onglet Rapport : boutons de pilotage du panneau de rapport."""
    tab_w = QWidget()
    tab_w.setStyleSheet("background: #e8ecf2;")
    h = QHBoxLayout(tab_w)
    h.setContentsMargins(16, 6, 16, 6)
    h.setSpacing(6)

    btn_qss = """
    QToolButton {
        border: 1px solid #b0c4de; border-radius: 5px;
        padding: 5px 10px; font-size: 11px;
        color: #2a3a5a; background: #eef2fa;
        min-width: 64px;
    }
    QToolButton:hover   { background: #d0e4ff; border-color: #1976d2; }
    QToolButton:pressed { background: #bbdefb; }
    """

    from PyQt5.QtWidgets import QToolButton

    def _make_btn(text: str, tooltip: str, callback) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(btn_qss)
        btn.clicked.connect(callback)
        return btn

    def _refresh():
        panel = getattr(window, "report_panel", None)
        if panel:
            panel.refresh()
            panel.setVisible(True)
            # Montrer le dock si existant
            dock = getattr(window, "report_dock", None)
            if dock:
                dock.setVisible(True)

    def _print():
        panel = getattr(window, "report_panel", None)
        if panel:
            panel._print_report()

    def _export():
        panel = getattr(window, "report_panel", None)
        if panel:
            panel._export_pdf()

    def _export_devis_xl():
        panel = getattr(window, "report_panel", None)
        if panel:
            panel._export_devis_excel()

    def _export_att_xl():
        panel = getattr(window, "report_panel", None)
        if panel:
            panel._export_attachment_excel()

    h.addWidget(_make_btn("🔄\nActualiser", "Recalculer le rapport", _refresh))

    sep1 = QFrame()
    sep1.setFrameShape(QFrame.VLine)
    sep1.setStyleSheet("color:#b0c4de; max-width:1px;")
    h.addWidget(sep1)

    h.addWidget(_make_btn("🖨\nImprimer",    "Imprimer le rapport de quantités", _print))
    h.addWidget(_make_btn("📄\nExport PDF",  "Exporter le rapport en PDF",      _export))

    sep2 = QFrame()
    sep2.setFrameShape(QFrame.VLine)
    sep2.setStyleSheet("color:#b0c4de; max-width:1px;")
    h.addWidget(sep2)

    h.addWidget(_make_btn("📊\nDevis Excel",      "Exporter le Devis en Excel",       _export_devis_xl))
    h.addWidget(_make_btn("📊\nAttach. Excel",    "Exporter l'Attachement en Excel",  _export_att_xl))

    h.addStretch()

    info = QLabel("Rapport de quantités — toutes pages")
    info.setStyleSheet("color:#607080; font-size:11px; font-style:italic;")
    h.addWidget(info)

    return tab_w


# ── Widget ruban principal ────────────────────────────────────────────────────

class RibbonWidget(QWidget):
    """Ruban à onglets : tab bar + zone de contenu."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Tab bar ──────────────────────────────────────────────────────
        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setStyleSheet("""
            QTabBar { background: #dde3ee; border-bottom: none; }
            QTabBar::tab {
                padding: 6px 24px 5px 24px;
                font-size: 12px;
                font-weight: bold;
                color: #5a7090;
                border: none;
                border-bottom: 2px solid transparent;
                background: transparent;
                margin-right: 1px;
            }
            QTabBar::tab:selected {
                color: #1976d2;
                background: #e8ecf2;
                border-bottom: 2px solid #1976d2;
            }
            QTabBar::tab:hover:!selected {
                color: #1a3a70;
                background: #d8e4f4;
            }
        """)
        self.tab_bar.addTab("  Fichier  ")
        self.tab_bar.addTab("  Accueil  ")
        self.tab_bar.addTab("  Page  ")
        self.tab_bar.addTab("  Devis  ")
        self.tab_bar.addTab("  Rapport  ")

        # ── Zone de contenu ──────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setFixedHeight(_TAB_H)
        self.stack.setStyleSheet("background: #e8ecf2; border: none;")

        # ── Séparateur bas ───────────────────────────────────────────────
        border = QFrame()
        border.setFrameShape(QFrame.HLine)
        border.setFixedHeight(2)
        border.setStyleSheet("background: #1976d2; border: none;")

        layout.addWidget(self.tab_bar)
        layout.addWidget(self.stack)
        layout.addWidget(border)

        # L'index 0 (Fichier) n'affiche pas de contenu, il ouvre un menu
        self._last_tab = 1
        self.tab_bar.currentChanged.connect(self._on_tab_changed_internal)
        self.tab_bar.tabBarClicked.connect(self._on_tab_clicked)

        # Construire le contenu de chaque onglet
        self.stack.addWidget(_build_fichier(self._window))   # index 0 (vide)
        self.stack.addWidget(_build_accueil(self._window))   # index 1
        self.stack.addWidget(_build_page(self._window))      # index 2
        self.stack.addWidget(_build_devis(self._window))     # index 3
        self.stack.addWidget(_build_rapport(self._window))   # index 4

        # Démarrer sur Accueil
        self.tab_bar.setCurrentIndex(1)
        self.stack.setCurrentIndex(1)


    def _on_tab_changed_internal(self, index: int):
        """Met à jour le stack et mémorise l'onglet actif (hors Fichier)."""
        self.stack.setCurrentIndex(index)
        if index != 0:
            self._last_tab = index

    def _on_tab_clicked(self, index: int):
        """Clic sur l'onglet Fichier → menu déroulant, retour à l'onglet précédent."""
        if index != 0:
            return
        # Revenir immédiatement à l'onglet précédent
        self.tab_bar.setCurrentIndex(self._last_tab)

        w = self._window
        menu = QMenu(self)
        menu.addAction(w.new_project_action)
        menu.addAction(w.load_project_action)
        recent = getattr(w, "_recent_menu", None)
        if recent:
            menu.addMenu(recent)
        menu.addSeparator()
        menu.addAction(w.save_project_action)
        menu.addAction(w.save_project_as_action)
        menu.addSeparator()
        menu.addAction(w.close_project_action)
        menu.addSeparator()
        menu.addAction(w.help_action)
        menu.addAction(w.tutorial_action)
        menu.addSeparator()
        menu.addAction(w.about_action)
        menu.addAction(w.deactivate_action)
        menu.addSeparator()
        menu.addAction(w.quit_action)

        pos = self.tab_bar.tabRect(0).bottomLeft()
        menu.exec_(self.tab_bar.mapToGlobal(pos))


# ── Point d'entrée ────────────────────────────────────────────────────────────

def build_main_toolbar(window) -> QToolBar:
    """Crée et attache le QToolBar hosting le RibbonWidget."""
    toolbar = QToolBar("Ruban")
    toolbar.setObjectName("mainToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setStyleSheet(
        "QToolBar { border: none; padding: 0; margin: 0; background: #dde3ee; }"
    )
    toolbar.setContentsMargins(0, 0, 0, 0)

    ribbon = RibbonWidget(window, toolbar)
    ribbon.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    toolbar.addWidget(ribbon)

    # Stocker la référence directe à la tab_bar du ruban pour la connexion
    window.ribbon_tab_bar = ribbon.tab_bar

    window.addToolBar(Qt.TopToolBarArea, toolbar)
    return toolbar
