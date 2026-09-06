"""
Dialogue d'activation de licence — Métraplan (PyQt5)
=====================================================
Affiché au démarrage si aucune licence valide n'est trouvée.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QProgressBar,
    QMessageBox, QSizePolicy,
)

from core.license_manager import LicenseManager, LicenseStatus, LicenseInfo


# ── Worker thread pour ne pas geler l'UI ─────────────────────────────────────

class _ActivateWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, lm: LicenseManager, key: str):
        super().__init__()
        self._lm  = lm
        self._key = key

    def run(self):
        ok, msg = self._lm.activate(self._key)
        self.finished.emit(ok, msg)


# ── Dialogue principal ────────────────────────────────────────────────────────

class ActivationDialog(QDialog):
    """
    Fenêtre d'activation de licence.
    Retourne QDialog.Accepted si la licence est valide/activée avec succès.
    """

    def __init__(self, parent=None,
                 initial_status: LicenseInfo | None = None):
        super().__init__(parent)
        self._lm = LicenseManager()
        self._initial_status = initial_status
        self._worker: _ActivateWorker | None = None
        self._setup_ui()
        if initial_status:
            self._show_status_message(initial_status)

    # ── Construction de l'interface ───────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle("Activation de licence — Métraplan")
        self.setFixedWidth(480)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet("""
            QDialog  { background: #f0f4f8; }
            QLabel   { color: #263238; }
            QLineEdit {
                padding: 10px 14px; border: 1px solid #b0bec5;
                border-radius: 5px; font-size: 14px;
                background: white; color: #1a2a3a;
                letter-spacing: 2px; font-family: 'Courier New', monospace;
            }
            QLineEdit:focus { border-color: #1976d2; }
            QPushButton {
                padding: 10px 24px; border: none; border-radius: 5px;
                font-size: 13px; font-weight: 700; cursor: pointer;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(0)

        # En-tête
        header = QLabel("Métraplan")
        header.setFont(QFont("Segoe UI", 22, QFont.Bold))
        header.setStyleSheet("color: #1976d2; margin-bottom: 2px;")
        header.setAlignment(Qt.AlignCenter)
        root.addWidget(header)

        sub = QLabel("Logiciel de métré et de prise de quantités")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #78909c; font-size: 11px; margin-bottom: 20px;")
        root.addWidget(sub)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #cfd8dc;")
        root.addWidget(sep)
        root.addSpacing(18)

        # Titre section
        title = QLabel("Activation de la licence")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet("color: #263238; margin-bottom: 6px;")
        root.addWidget(title)

        desc = QLabel(
            "Entrez votre clé de licence pour activer ce logiciel.\n"
            "Format : MTR-XXXX-XXXX-XXXX-XXXX"
        )
        desc.setStyleSheet("color: #607d8b; font-size: 11px; margin-bottom: 14px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # Champ clé
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("MTR-XXXX-XXXX-XXXX-XXXX")
        self._key_input.setMaxLength(24)
        self._key_input.textChanged.connect(self._on_key_changed)
        self._key_input.returnPressed.connect(self._on_activate)
        root.addWidget(self._key_input)
        root.addSpacing(6)

        # Machine ID (info)
        mid = self._lm.get_machine_id()
        mid_label = QLabel(f"ID de cet ordinateur : <code>{mid[:20]}…</code>")
        mid_label.setStyleSheet("color: #90a4ae; font-size: 10px;")
        mid_label.setTextFormat(Qt.RichText)
        root.addWidget(mid_label)
        root.addSpacing(14)

        # Bouton + progress
        btn_row = QHBoxLayout()
        self._btn_activate = QPushButton("Activer")
        self._btn_activate.setStyleSheet(
            "background: #1976d2; color: white;"
            "QPushButton:hover { background: #1565c0; }"
            "QPushButton:disabled { background: #b0bec5; }"
        )
        self._btn_activate.setEnabled(False)
        self._btn_activate.clicked.connect(self._on_activate)
        btn_row.addWidget(self._btn_activate)

        self._btn_cancel = QPushButton("Quitter")
        self._btn_cancel.setStyleSheet("background: #eceff1; color: #546e7a;")
        self._btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_cancel)
        root.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # mode indéterminé
        self._progress.setVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setStyleSheet("QProgressBar { border: none; background: #e0e0e0; }"
                                     "QProgressBar::chunk { background: #1976d2; }")
        root.addSpacing(6)
        root.addWidget(self._progress)

        # Message de statut
        self._msg_label = QLabel("")
        self._msg_label.setWordWrap(True)
        self._msg_label.setStyleSheet("font-size: 11px; margin-top: 10px;")
        self._msg_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self._msg_label)

        # Footer
        root.addSpacing(12)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #eceff1;")
        root.addWidget(sep2)
        root.addSpacing(8)
        footer = QLabel("© 2026 Métraplan — support@metraplan.com")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #b0bec5; font-size: 10px;")
        root.addWidget(footer)

    # ── Logique ───────────────────────────────────────────────────────────

    def _on_key_changed(self, text: str):
        """Auto-formate la clé et active le bouton si le format est correct."""
        from core.license_manager import _is_valid_format

        upper = text.upper().replace(" ", "")

        # Supprimer le préfixe MTR- s'il est déjà présent pour travailler
        # uniquement sur les 4 groupes de données (16 caractères alphanumériques)
        if upper.startswith("MTR-"):
            data = upper[4:].replace("-", "")
        else:
            data = upper.replace("-", "")

        # Garder au maximum 16 caractères de données
        data = data[:16]

        # Reconstruire les groupes de 4 caractères
        parts = [data[i:i+4] for i in range(0, len(data), 4)]
        if parts:
            formatted = "MTR-" + "-".join(parts)
        else:
            formatted = "MTR-"

        # Limiter à la longueur maximale complète : MTR-XXXX-XXXX-XXXX-XXXX = 19 chars
        if text.upper() != formatted:
            cur = self._key_input.cursorPosition()
            self._key_input.blockSignals(True)
            self._key_input.setText(formatted)
            self._key_input.setCursorPosition(min(cur + 1, len(formatted)))
            self._key_input.blockSignals(False)

        self._btn_activate.setEnabled(_is_valid_format(self._key_input.text()))

    def _on_activate(self):
        key = self._key_input.text().strip()
        self._set_loading(True)
        self._msg_label.setText("Connexion au serveur de licences…")
        self._msg_label.setStyleSheet("color: #607d8b; font-size: 11px;")

        self._worker = _ActivateWorker(self._lm, key)
        self._worker.finished.connect(self._on_activation_result)
        self._worker.start()

    def _on_activation_result(self, ok: bool, message: str):
        self._set_loading(False)
        if ok:
            self._msg_label.setText("✅ " + message.replace("\n", "  "))
            self._msg_label.setStyleSheet("color: #2e7d32; font-size: 11px;")
            # Fermer automatiquement après 1.5s
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(1500, self.accept)
        else:
            self._msg_label.setText("❌ " + message)
            self._msg_label.setStyleSheet("color: #c62828; font-size: 11px;")

    def _set_loading(self, loading: bool):
        self._progress.setVisible(loading)
        self._btn_activate.setEnabled(not loading)
        self._btn_cancel.setEnabled(not loading)
        self._key_input.setEnabled(not loading)

    def _show_status_message(self, info: LicenseInfo):
        """Affiche le message de statut initial (ex: licence expirée)."""
        msgs = {
            LicenseStatus.EXPIRED:  ("⚠ Votre licence a expiré. Renouvelez-la.", "#e65100"),
            LicenseStatus.BLOCKED:  ("🔒 Cette licence a été révoquée.", "#c62828"),
            LicenseStatus.INVALID:  ("❌ Licence invalide.", "#c62828"),
            LicenseStatus.ERROR:    ("⚠ Erreur de vérification. Activez à nouveau.", "#e65100"),
            LicenseStatus.NOT_FOUND:("ℹ Aucune licence activée sur cet ordinateur.", "#1976d2"),
        }
        if info.status in msgs:
            txt, color = msgs[info.status]
            self._msg_label.setText(txt)
            self._msg_label.setStyleSheet(f"color: {color}; font-size: 11px;")


# ── Fonction utilitaire ───────────────────────────────────────────────────────

def check_and_show_activation(parent=None, precomputed: LicenseInfo | None = None) -> bool:
    """
    Vérifie la licence et affiche le dialogue d'activation si nécessaire.
    Retourne True si le logiciel peut démarrer, False si l'utilisateur a annulé.

    Paramètre :
        precomputed : résultat déjà calculé par main.py avec force=True.
                      Si fourni, on l'utilise directement (évite un 2e appel
                      avec force=False qui ignorerait le cache et masquerait
                      un blocage dashboard).

    Usage dans main.py :
        _lm_check = LicenseManager().check(force=True)
        if not check_and_show_activation(precomputed=_lm_check):
            sys.exit(0)
    """
    if precomputed is not None:
        status = precomputed
    else:
        # Fallback : vérification directe avec force=True pour toujours
        # contacter le serveur (jamais de cache masquant un blocage)
        lm     = LicenseManager()
        status = lm.check(force=True)

    # Statuts qui permettent de continuer sans dialogue
    # Les avertissements (hors-ligne, expiration proche) sont affichés
    # dans main.py APRÈS la fermeture du splash pour ne pas être bloqués.
    if status.status in (LicenseStatus.VALID, LicenseStatus.OFFLINE):
        return True

    # Afficher le dialogue d'activation
    dlg = ActivationDialog(parent, initial_status=status)
    return dlg.exec_() == QDialog.Accepted
