import sys
import logging
import os
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor, QIcon
from ui.main_window import MainWindow
from core.app_logger import setup_logging, get_logger
from version import APP_VERSION, APP_NAME, APP_COPYRIGHT

# Configurer le logging — fichier dans %APPDATA%\Metraplan\ (pas dans le dossier d'installation)
_appdata = Path(os.environ.get("APPDATA", Path.home())) / "Metraplan"
_appdata.mkdir(parents=True, exist_ok=True)
setup_logging(level=logging.WARNING,
              log_file=_appdata / "metraplan.log")
_log = get_logger(__name__)


def _load_stylesheet(app: QApplication):
    """Charge le stylesheet QSS depuis assets/style/app.qss."""
    qss_path = Path(__file__).parent / "assets" / "style" / "app.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    else:
        _log.warning("Stylesheet introuvable : %s", qss_path)


def _create_splash():
    """Crée et affiche le splash screen avec textes superposés."""
    splash_path = Path(__file__).parent / "assets" / "images" / "splash.png"
    if not splash_path.exists():
        _log.warning("Image splash introuvable : %s", splash_path)
        return None

    pixmap = QPixmap(str(splash_path))
    if pixmap.isNull():
        _log.warning("Impossible de charger l'image splash.")
        return None

    # Redimensionner à 900 px de large (image 16:9, ratio conservé)
    pixmap = pixmap.scaledToWidth(900, Qt.SmoothTransformation)

    # Peindre numéro de version et crédit en bas de l'image
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    from PyQt5.QtCore import QRect
    w = pixmap.width()
    h = pixmap.height()

    def _draw_text_shadow(painter, text, font, color, align, rect):
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0, 130))
        painter.drawText(rect.translated(1, 1), align, text)
        painter.setPen(color)
        painter.drawText(rect, align, text)

    # Version centrée en bas
    font_ver = QFont("Segoe UI", 9, QFont.Bold)
    _draw_text_shadow(painter, f"Version {APP_VERSION}",
                      font_ver, QColor(255, 255, 255),
                      Qt.AlignCenter, QRect(10, h - 32, w - 20, 20))

    # Copyright bas droite (le crédit "created by" est déjà intégré à l'image)
    font_credit = QFont("Segoe UI", 7, QFont.Normal)
    font_credit.setItalic(True)
    _draw_text_shadow(painter, APP_COPYRIGHT,
                      font_credit, QColor(200, 200, 200),
                      Qt.AlignRight | Qt.AlignVCenter, QRect(10, h - 16, w - 14, 14))

    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlags(Qt.SplashScreen)
    return splash


def _install_excepthook(log_path: Path) -> None:
    """
    Remplace sys.excepthook pour intercepter toutes les exceptions non gérées :
    - Loggue le traceback complet dans metraplan.log
    - Affiche un dialogue convivial à l'utilisateur
    - Evite une fermeture silencieuse du programme
    """
    import traceback

    def _handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _log.critical("Exception non gérée :\n%s", tb_text)
        try:
            from PyQt5.QtWidgets import QMessageBox, QApplication as _QApp
            app_ = _QApp.instance()
            if app_:
                box = QMessageBox()
                box.setWindowTitle("Erreur inattendue — Métraplan")
                box.setIcon(QMessageBox.Critical)
                box.setText(
                    "<b>Une erreur inattendue s'est produite.</b><br><br>"
                    "Le programme va tenter de continuer, mais nous vous recommandons "
                    "de sauvegarder votre travail immédiatement.<br><br>"
                    f"<i>Détail enregistré dans :<br>{log_path}</i>"
                )
                box.setDetailedText(tb_text)
                box.exec_()
        except Exception:
            pass

    sys.excepthook = _handle_exception


if __name__ == "__main__":
    # Désactiver le scaling HiDPI automatique pour éviter un affichage trop grand
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, False)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    _install_excepthook(_appdata / "metraplan.log")
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Metraplan")

    _load_stylesheet(app)

    # Icône de l'application
    _icon_path = Path(__file__).parent / "assets" / "icons" / "metraplan.ico"
    if _icon_path.exists():
        app.setWindowIcon(QIcon(str(_icon_path)))

    # Afficher le splash screen (minimum 3 secondes)
    splash = _create_splash()
    if splash:
        splash.show()
        app.processEvents()

    # ── Vérification de la licence ────────────────────────────────────────
    # force=True : ignore le cache local, contacte toujours le serveur au démarrage
    # → blocage dashboard effectif immédiatement au prochain lancement
    from core.license_manager import LicenseManager, LicenseStatus
    _lm_check = LicenseManager().check(force=True)
    _needs_dialog = _lm_check.status not in (LicenseStatus.VALID, LicenseStatus.OFFLINE)

    # Cacher le splash seulement si la fenêtre d'activation doit s'afficher
    if _needs_dialog and splash:
        splash.hide()
        app.processEvents()

    from ui.activation_dialog import check_and_show_activation
    if not check_and_show_activation(precomputed=_lm_check):
        sys.exit(0)

    # Réafficher le splash après l'activation si on l'avait caché
    if _needs_dialog and splash:
        splash.show()
        app.processEvents()

    window = MainWindow()

    # ── Vérification périodique (toutes les 24h pendant la session) ───────
    # Vérification forcée toutes les heures : force=True garantit le contact
    # serveur à chaque fois → un blocage dashboard prend effet dans l'heure
    # même si le programme reste ouvert en continu.
    def _periodic_license_check():
        from core.license_manager import LicenseManager, LicenseStatus
        from PyQt5.QtWidgets import QMessageBox
        lm = LicenseManager()
        info = lm.check(force=True)
        if info.status in (LicenseStatus.EXPIRED, LicenseStatus.BLOCKED,
                           LicenseStatus.INVALID, LicenseStatus.ERROR):
            QMessageBox.critical(
                window, "Licence expirée ou révoquée",
                f"Votre licence n'est plus valide.\n\n{info.message}\n\n"
                "Le logiciel va se fermer.",
            )
            sys.exit(1)
        elif info.status == LicenseStatus.OFFLINE:
            QMessageBox.warning(
                window, "Mode hors-ligne",
                info.message,
            )

    _license_timer = QTimer()
    _license_timer.timeout.connect(_periodic_license_check)
    _license_timer.start(1 * 60 * 60 * 1000)   # toutes les 1 h (blocage max 1h si session ouverte)
    # Restaurer la géométrie de la dernière session
    geom = window._settings.value("geometry")
    if geom:
        window.restoreGeometry(geom)
    state = window._settings.value("windowState")
    if state:
        window.restoreState(state)

    def _show_main():
        window.show()
        if splash:
            splash.finish(window)
        # Avertissement expiration affiché APRÈS la fermeture du splash
        if _lm_check.status == LicenseStatus.OFFLINE:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                window, "Mode hors-ligne", _lm_check.message)
        elif _lm_check.days_left > 0 and _lm_check.days_left <= 14:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                window, "Renouvellement de licence",
                f"Votre licence expire dans {_lm_check.days_left} jour(s).\n"
                "Contactez le support pour la renouveler.",
            )

    # Fermer le splash après 5 secondes minimum
    QTimer.singleShot(5000, _show_main)

    sys.exit(app.exec_())