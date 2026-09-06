def init_ui(self):
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
    from core.canvas_view import CanvasView  # Import correct
    from core.ortho_manager import OrthoManager  # Import correct

    central = QWidget(self)
    self.setCentralWidget(central)
    vbox = QVBoxLayout(central)

    # Première ligne - Outils principaux
    hbox1 = QHBoxLayout()
    # ... (ajout des boutons comme avant) ...
    vbox.addLayout(hbox1)

    # Deuxième ligne - Outils auxiliaires
    hbox2 = QHBoxLayout()
    # ... (ajout des boutons comme avant) ...
    vbox.addLayout(hbox2)

    # Zone de dessin (canvas) - CORRECTION ICI
    self.canvas_view = CanvasView(self)  # ← Nom correct
    vbox.addWidget(self.canvas_view)
    self.canvas_view.ortho_manager = OrthoManager()  # ← Correction ici

    # Panneau d'informations sur les entités
    entity_info_layout = QHBoxLayout()
    # ... (ajout des labels et boutons) ...
    vbox.addLayout(entity_info_layout)

    # Labels d'information
    self.measure_label = QLabel("Mesure : -")
    vbox.addWidget(self.measure_label)
    self.counter_label = QLabel("Compteur : -")
    vbox.addWidget(self.counter_label)
    self.ortho_label = QLabel("Mode Ortho : Désactivé")
    vbox.addWidget(self.ortho_label)

    # Connexions des signaux - CORRECTION ICI
    # Utilisez canvas_view au lieu de canvas
    self.canvas_view.entity_manager.entity_added.connect(
        self.update_entity_stats)
    self.canvas_view.entity_manager.entity_removed.connect(
        self.update_entity_stats)
