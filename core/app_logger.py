"""
Configuration centralisée du logging pour Metraplan.

Usage dans n'importe quel module :
    from core.app_logger import get_logger
    log = get_logger(__name__)
    log.debug("message de débogage")
    log.warning("avertissement")
    log.error("erreur critique")
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(level: int = logging.WARNING,
                  log_file: Path | None = None) -> None:
    """
    Configure le logging global de l'application.
    - En production  : niveau WARNING → seuls les avertissements et erreurs sont affichés.
    - En développement : appeler setup_logging(logging.DEBUG) pour tout voir.
    """
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt,
                        handlers=handlers, force=True)

    # Réduire le bruit des bibliothèques tierces
    for noisy in ("PIL", "urllib3", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.ERROR)


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger nommé pour le module appelant."""
    return logging.getLogger(name)
