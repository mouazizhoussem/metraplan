# ui/main_window.py
import sys
from PyQt5.QtWidgets import (QMainWindow, QAction, QToolBar, QLabel, 
                             QStatusBar, QFileDialog, QMessageBox, QDockWidget, QVBoxLayout, QWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

# Import de la nouvelle vue
from view.canvas_view import CanvasView

# Import des outils
from tools.surface_tool import SurfaceTool
from tools.distance_tool import DistanceTool
from tools.counter_tool import CounterTool
from tools.scale_tool import ScaleTool
from tools.perimeter_tool import PerimeterTool

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Application de Mesure")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialisation de la vue Canvas
        self.canvas_view = CanvasView(self)
        self.setCentralWidget(self.canvas_view)
        
        # Initialisation des outils et connexion à la vue
        self.init_tools()
        
        # Initialisation de l'interface
        self.init_ui()
        
        # Variables d'état
        self.ortho_mode = False
        
    def init_tools(self):
        """Initialise tous les outils et les connecte à la vue"""
        # Création des outils
        self.canvas_view.surface_tool = SurfaceTool(self.canvas_view)
        self.canvas_view.distance_tool = DistanceTool(self.canvas_view)
        self.canvas_view.counter_tool = CounterTool(self.canvas_view)
        self.canvas_view.scale_tool = ScaleTool(self.canvas_view)
        self.canvas_view.perimeter_tool = PerimeterTool(self.canvas_view)
        
        # Configuration des outils (si nécessaire)
        # Exemple: self.canvas_view.surface_tool.set_some_setting(value)
        
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.create_actions()
        self.create_menu()
        self.create_toolbar()
        self.create_statusbar()
        self.create_dock_widgets()
        
    def create_actions(self):
        """Crée les actions de menu"""
        # Action Ouvrir
        self.open_action = QAction(QIcon("icons/open.png"), "Ouvrir", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.setStatusTip("Ouvrir une image")
        self.open_action.triggered.connect(self.open_image)
        
        # Action Quitter
        self.quit_action = QAction(QIcon("icons/quit.png"), "Quitter", self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.setStatusTip("Quitter l'application")
        self.quit_action.triggered.connect(self.close)
        
        # Actions des outils
        self.surface_action = QAction(QIcon("icons/surface.png"), "Surface", self)
        self.surface_action.setCheckable(True)
        self.surface_action.setStatusTip("Mesurer une surface")
        self.surface_action.triggered.connect(self.activate_surface_tool)
        
        self.distance_action = QAction(QIcon("icons/distance.png"), "Distance", self)
        self.distance_action.setCheckable(True)
        self.distance_action.setStatusTip("Mesurer une distance")
        self.distance_action.triggered.connect(self.activate_distance_tool)
        
        self.counter_action = QAction(QIcon("icons/counter.png"), "Compteur", self)
        self.counter_action.setCheckable(True)
        self.counter_action.setStatusTip("Compter des éléments")
        self.counter_action.triggered.connect(self.activate_counter_tool)
        
        self.scale_action = QAction(QIcon("icons/scale.png"), "Échelle", self)
        self.scale_action.setCheckable(True)
        self.scale_action.setStatusTip("Définir l'échelle")
        self.scale_action.triggered.connect(self.activate_scale_tool)
        
        self.perimeter_action = QAction(QIcon("icons/perimeter.png"), "Périmètre", self)
        self.perimeter_action.setCheckable(True)
        self.perimeter_action.setStatusTip("Mesurer un périmètre")
        self.perimeter_action.triggered.connect(self.activate_perimeter_tool)
        
        # Action Mode Ortho
        self.ortho_action = QAction(QIcon("icons/ortho.png"), "Mode Ortho", self)
        self.ortho_action.setCheckable(True)
        self.ortho_action.setShortcut("O")
        self.ortho_action.setStatusTip("Activer/désactiver le mode orthogonal")
        self.ortho_action.triggered.connect(self.toggle_ortho_mode)
        
        # Action Effacer tout
        self.clear_action = QAction(QIcon("icons/clear.png"), "Effacer tout", self)
        self.clear_action.setStatusTip("Effacer toutes les mesures")
        self.clear_action.triggered.connect(self.clear_all)
        
    def create_menu(self):
        """Crée les menus"""
        menu_bar = self.menuBar()
        
        # Menu Fichier
        file_menu = menu_bar.addMenu("Fichier")
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)
        
        # Menu Outils
        tools_menu = menu_bar.addMenu("Outils")
        tools_menu.addAction(self.surface_action)
        tools_menu.addAction(self.distance_action)
        tools_menu.addAction(self.counter_action)
        tools_menu.addAction(self.scale_action)
        tools_menu.addAction(self.perimeter_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.ortho_action)
        tools_menu.addAction(self.clear_action)
        
    def create_toolbar(self):
        """Crée la barre d'outils"""
        toolbar = QToolBar("Outils principaux")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        toolbar.addAction(self.open_action)
        toolbar.addSeparator()
        toolbar.addAction(self.surface_action)
        toolbar.addAction(self.distance_action)
        toolbar.addAction(self.counter_action)
        toolbar.addAction(self.scale_action)
        toolbar.addAction(self.perimeter_action)
        toolbar.addSeparator()
        toolbar.addAction(self.ortho_action)
        toolbar.addAction(self.clear_action)
        
        # Grouper les actions d'outils pour la désélection mutuelle
        self.tool_actions = [
            self.surface_action,
            self.distance_action,
            self.counter_action,
            self.scale_action,
            self.perimeter_action
        ]
        
    def create_statusbar(self):
        """Crée la barre de statut"""
        self.statusBar().showMessage("Prêt")
        
        # Label pour les mesures
        self.measure_label = QLabel("Aucune mesure")
        self.statusBar().addPermanentWidget(self.measure_label)
        
    def create_dock_widgets(self):
        """Crée les widgets ancrables"""
        # Dock widget pour les propriétés (exemple)
        properties_dock = QDockWidget("Propriétés", self)
        properties_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        properties_widget = QWidget()
        properties_layout = QVBoxLayout()
        properties_widget.setLayout(properties_layout)
        
        # Ajouter des contrôles aux propriétés si nécessaire
        # properties_layout.addWidget(QLabel("Options des outils"))
        
        properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, properties_dock)
        
    def open_image(self):
        """Ouvre une image"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir une image", "", 
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        
        if file_path:
            success = self.canvas_view.load_image(file_path)
            if success:
                self.statusBar().showMessage(f"Image chargée: {file_path}")
            else:
                QMessageBox.warning(self, "Erreur", "Impossible de charger l'image")
                
    def activate_surface_tool(self):
        """Active l'outil de surface"""
        self.deselect_other_tools(self.surface_action)
        self.canvas_view.set_mode("polygon")
        
    def activate_distance_tool(self):
        """Active l'outil de distance"""
        self.deselect_other_tools(self.distance_action)
        self.canvas_view.set_mode("distance")
        
    def activate_counter_tool(self):
        """Active l'outil de compteur"""
        self.deselect_other_tools(self.counter_action)
        self.canvas_view.set_mode("counter")
        
    def activate_scale_tool(self):
        """Active l'outil d'échelle"""
        self.deselect_other_tools(self.scale_action)
        self.canvas_view.set_mode("scale")
        
    def activate_perimeter_tool(self):
        """Active l'outil de périmètre"""
        self.deselect_other_tools(self.perimeter_action)
        self.canvas_view.set_mode("perimeter")
        
    def deselect_other_tools(self, current_action):
        """Désélectionne les autres outils"""
        for action in self.tool_actions:
            if action != current_action:
                action.setChecked(False)
                
    def toggle_ortho_mode(self):
        """Active/désactive le mode orthogonal"""
        self.ortho_mode = not self.ortho_mode
        self.ortho_action.setChecked(self.ortho_mode)
        
        # Transmet l'état au canvas_view si nécessaire
        if hasattr(self.canvas_view, 'set_ortho_mode'):
            self.canvas_view.set_ortho_mode(self.ortho_mode)
            
        status = "activé" if self.ortho_mode else "désactivé"
        self.statusBar().showMessage(f"Mode orthogonal {status}")
        
    def clear_all(self):
        """Efface toutes les mesures"""
        reply = QMessageBox.question(
            self, "Confirmation", 
            "Voulez-vous vraiment effacer toutes les mesures?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.canvas_view.clear_scene()
            self.statusBar().showMessage("Toutes les mesures ont été effacées")
            
    def closeEvent(self, event):
        """Gère la fermeture de l'application"""
        reply = QMessageBox.question(
            self, "Quitter", 
            "Voulez-vous vraiment quitter l'application?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()