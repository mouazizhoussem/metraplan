# ui/scale_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QDoubleSpinBox, QMessageBox,
                             QFormLayout, QGroupBox, QTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal


class ScaleCalibrationDialog(QDialog):
    """Dialogue pour le calibrage automatique de l'échelle"""

    # Signal émis quand une mesure est effectuée
    measurement_received = pyqtSignal(float)  # pixels

    def __init__(self, parent=None, canvas_view=None):
        super().__init__(parent)
        self.canvas_view = canvas_view
        self.distance_pixels = 0.0
        self.real_distance = 0.0
        self._measurement_connected = False

        self.setWindowTitle("Calibrage de l'échelle")
        self.setMinimumWidth(500)
        self.setModal(False)  # Non bloquant

        self.init_ui()
        self.connect_to_canvas()

    def init_ui(self):
        """Initialise l'interface du dialogue"""
        layout = QVBoxLayout()

        # Instructions
        instructions = QGroupBox("Instructions")
        instructions_layout = QVBoxLayout()
        instruction_text = QTextEdit()
        instruction_text.setReadOnly(True)
        instruction_text.setMaximumHeight(140)
        instruction_text.setText("""
<p><b>Pour définir l'échelle :</b></p>
<ol>
<li>L'outil <b>Distance</b> est maintenant actif</li>
<li>Tracez une ligne sur une mesure connue de l'image<br/>
    (ex: une règle, une dimension affichée, une longueur de référence)</li>
<li>La distance mesurée apparaîtra automatiquement ci-dessous</li>
<li>Entrez la valeur réelle correspondante en mètres</li>
<li>Cliquez sur <b>Valider</b> pour appliquer l'échelle</li>
</ol>
<p><i style="color: #666;">Vous pourrez modifier l'échelle plus tard via l'outil Échelle</i></p>
        """)
        instruction_text.setStyleSheet(
            "background-color: #F0F8FF; border: 1px solid #B0C4DE; padding: 10px;")
        instructions_layout.addWidget(instruction_text)
        instructions.setLayout(instructions_layout)
        layout.addWidget(instructions)

        # Informations sur la mesure
        info_group = QGroupBox("Mesure effectuée")
        info_layout = QFormLayout()

        # Distance en pixels (remplie automatiquement depuis la mesure)
        self.pixels_label = QLabel("En attente d'une mesure...")
        self.pixels_label.setStyleSheet(
            "font-weight: bold; color: #666; font-size: 12px; padding: 5px;")
        info_layout.addRow("Distance mesurée:", self.pixels_label)

        # Distance réelle en mètres
        self.distance_input = QDoubleSpinBox()
        self.distance_input.setMinimum(0.001)
        self.distance_input.setMaximum(10000.0)
        self.distance_input.setDecimals(3)
        self.distance_input.setSuffix(" m")
        self.distance_input.setValue(1.0)
        self.distance_input.setSingleStep(0.1)
        # Désactivé jusqu'à ce qu'une mesure soit effectuée
        self.distance_input.setEnabled(False)
        self.distance_input.setToolTip(
            "Entrez la valeur réelle de la mesure en mètres")
        info_layout.addRow("Valeur réelle:", self.distance_input)

        # Aperçu de l'échelle calculée
        self.scale_preview = QLabel("Mesurez d'abord une distance")
        self.scale_preview.setStyleSheet(
            "font-weight: bold; color: #999; font-size: 12px; padding: 5px;")
        info_layout.addRow("Échelle calculée:", self.scale_preview)

        # Mettre à jour l'aperçu lors de la saisie
        self.distance_input.valueChanged.connect(self.update_scale_preview)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Boutons
        buttons_layout = QHBoxLayout()

        self.skip_button = QPushButton("Passer")
        self.skip_button.setToolTip("Utiliser l'échelle par défaut (100 px/m)")
        self.skip_button.clicked.connect(self.accept_skip)
        buttons_layout.addWidget(self.skip_button)

        buttons_layout.addStretch()

        self.validate_button = QPushButton("Valider")
        self.validate_button.setDefault(True)
        # Désactivé jusqu'à ce qu'une mesure soit effectuée
        self.validate_button.setEnabled(False)
        self.validate_button.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.validate_button.clicked.connect(self.validate_scale)
        buttons_layout.addWidget(self.validate_button)

        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def connect_to_canvas(self):
        """Connecte le dialogue au canvas pour détecter les mesures"""
        try:
            if self.canvas_view and hasattr(self.canvas_view, 'entity_manager'):
                # Activer l'outil distance
                if hasattr(self.canvas_view, 'tool_manager'):
                    self.canvas_view.tool_manager.activate_tool('distance')

                # Connecter le signal pour détecter les nouvelles entités (lignes)
                def on_entity_added(entity):
                    if (hasattr(entity, 'entity_type') and
                        entity.entity_type == 'line' and
                            not self._measurement_connected):

                        # Calculer la distance en pixels
                        if hasattr(entity, 'start_point') and hasattr(entity, 'end_point'):
                            dx = entity.end_point.x() - entity.start_point.x()
                            dy = entity.end_point.y() - entity.start_point.y()
                            distance_px = (dx**2 + dy**2) ** 0.5

                            if distance_px > 0:
                                self.set_measured_distance(distance_px)
                                self._measurement_connected = True
                                # Désactiver l'outil distance après la mesure
                                if hasattr(self.canvas_view, 'tool_manager'):
                                    self.canvas_view.tool_manager.deactivate_all_tools()

                self.canvas_view.entity_manager.entity_added.connect(
                    on_entity_added)
        except Exception as e:
            pass

    def set_measured_distance(self, pixels):
        """Définit la distance mesurée en pixels"""
        self.distance_pixels = pixels
        self.pixels_label.setText(
            f"<span style='color: #0066CC; font-weight: bold;'>{pixels:.2f} px</span>")
        self.pixels_label.setStyleSheet(
            "font-weight: bold; color: #0066CC; font-size: 12px; padding: 5px;")

        # Activer le champ de saisie
        self.distance_input.setEnabled(True)
        self.validate_button.setEnabled(True)

        # Mettre à jour l'aperçu
        self.update_scale_preview()

    def update_scale_preview(self):
        """Met à jour l'aperçu de l'échelle calculée"""
        real_dist = self.distance_input.value()
        if real_dist > 0 and self.distance_pixels > 0:
            pixels_per_meter = self.distance_pixels / real_dist
            self.scale_preview.setText(
                f"<span style='color: #00AA00; font-weight: bold;'>1 m = {pixels_per_meter:.2f} px</span>"
            )
            self.scale_preview.setStyleSheet(
                "font-weight: bold; color: #00AA00; font-size: 12px; padding: 5px;")
        else:
            if self.distance_pixels > 0:
                self.scale_preview.setText(
                    "Entrez la valeur réelle pour calculer l'échelle")
                self.scale_preview.setStyleSheet(
                    "font-weight: bold; color: #999; font-size: 12px; padding: 5px;")

    def validate_scale(self):
        """Valide et applique l'échelle"""
        real_dist = self.distance_input.value()

        # Vérifications
        if real_dist <= 0:
            QMessageBox.warning(
                self,
                "Valeur invalide",
                "La distance réelle doit être supérieure à 0.\n\nVeuillez entrer une valeur valide en mètres."
            )
            self.distance_input.setFocus()
            return

        if self.distance_pixels <= 0:
            QMessageBox.warning(
                self,
                "Mesure manquante",
                "Vous devez d'abord mesurer une distance sur l'image.\n\n"
                "Utilisez l'outil Distance (déjà activé) pour tracer une ligne sur une mesure connue."
            )
            return

        # Validation de la plage raisonnable
        pixels_per_meter = self.distance_pixels / real_dist

        if pixels_per_meter < 0.1 or pixels_per_meter > 100000:
            reply = QMessageBox.warning(
                self,
                "Échelle inhabituelle",
                f"L'échelle calculée est : {pixels_per_meter:.2f} px/m\n\n"
                f"Cette valeur semble inhabituelle. Êtes-vous sûr de vos valeurs ?\n\n"
                f"Distance mesurée : {self.distance_pixels:.2f} px\n"
                f"Distance réelle : {real_dist:.3f} m",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Appliquer l'échelle
        if self.canvas_view:
            self.canvas_view.pixels_per_meter = pixels_per_meter

            # Mettre à jour toutes les entités existantes avec la nouvelle échelle
            self.update_existing_entities_scale(pixels_per_meter)

            # Afficher un message de confirmation
            QMessageBox.information(
                self,
                "Échelle définie",
                f"✓ Échelle appliquée avec succès !\n\n"
                f"<b>1 mètre = {pixels_per_meter:.2f} pixels</b>\n\n"
                f"Toutes les nouvelles mesures utiliseront cette échelle.\n\n"
                f"Vous pouvez la modifier plus tard via l'outil <b>Échelle</b>."
            )

        self.accept()

    def update_existing_entities_scale(self, new_pixels_per_meter):
        """Met à jour l'échelle de toutes les entités existantes"""
        try:
            if self.canvas_view and hasattr(self.canvas_view, 'entity_manager'):
                entities = self.canvas_view.entity_manager.get_all_entities()
                for entity in entities:
                    if hasattr(entity, 'pixels_per_meter'):
                        entity.pixels_per_meter = new_pixels_per_meter
                        # Redessiner l'entité avec la nouvelle échelle
                        if hasattr(entity, 'scene_ref') and entity.scene_ref:
                            if hasattr(entity, 'draw_text'):
                                try:
                                    entity.draw_text(entity.scene_ref)
                                except Exception as e:
                                    pass
        except Exception as e:
            pass

    def accept_skip(self):
        """Accepte avec l'échelle par défaut"""
        reply = QMessageBox.question(
            self,
            "Utiliser l'échelle par défaut",
            "Vous allez utiliser l'échelle par défaut (100 px/m).\n\n"
            "Les mesures ne seront pas précises tant que l'échelle n'est pas calibrée.\n\n"
            "Vous pourrez modifier l'échelle plus tard via l'outil <b>Échelle</b>.\n\n"
            "Continuer sans calibrer ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.canvas_view:
                self.canvas_view.pixels_per_meter = 100  # Valeur par défaut
            self.accept()

    def closeEvent(self, event):
        """Gère la fermeture du dialogue"""
        # Désactiver l'outil distance si activé
        if self.canvas_view and hasattr(self.canvas_view, 'tool_manager'):
            self.canvas_view.tool_manager.deactivate_all_tools()
        super().closeEvent(event)
