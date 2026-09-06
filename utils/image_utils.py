"""
Fonctions utilitaires pour les images.
"""
from __future__ import annotations

from typing import Optional, Tuple

from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt


def pil_to_pixmap(pil_image) -> Optional[QPixmap]:
    """Conversion PIL.Image -> QPixmap."""
    if pil_image is None:
        return None
    try:
        mode = pil_image.mode
        if mode not in ("RGB", "RGBA"):
            pil_image = pil_image.convert("RGBA")
            mode = "RGBA"

        data = pil_image.tobytes("raw", mode)
        fmt = QImage.Format_RGBA8888 if mode == "RGBA" else QImage.Format_RGB888
        qimg = QImage(data, pil_image.width, pil_image.height, fmt)
        return QPixmap.fromImage(qimg.copy())
    except Exception:
        return None


def optimize_image_for_display(
    pixmap: QPixmap, max_size: Tuple[int, int]
) -> QPixmap:
    """Redimensionnement intelligent."""
    if not pixmap:
        return pixmap
    max_w, max_h = max_size
    if pixmap.width() <= max_w and pixmap.height() <= max_h:
        return pixmap
    return pixmap.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
