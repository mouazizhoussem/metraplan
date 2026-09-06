"""
Service principal de conversion PDF vers images.
Utilise PyMuPDF (fitz) pour des performances optimales.
"""
from __future__ import annotations

from typing import Optional, Tuple, List

from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot, Qt
from PyQt5.QtGui import QImage

try:
    import fitz  # PyMuPDF
except Exception as exc:  # pragma: no cover - dépendance externe
    fitz = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class PDFConversionWorker(QObject):
    conversion_started = pyqtSignal(int)  # total pages converties
    page_converted = pyqtSignal(int, QImage, QImage)  # index, image, thumb
    conversion_finished = pyqtSignal()
    conversion_error = pyqtSignal(str)

    def __init__(
        self,
        file_path: str,
        dpi: int = 150,
        page_range: Optional[Tuple[int, int]] = None,
        thumb_width: int = 180,
        grayscale: bool = False,
    ):
        super().__init__()
        self.file_path = file_path
        self.dpi = dpi
        self.page_range = page_range
        self.thumb_width = thumb_width
        self.grayscale = grayscale
        self._cancel = False

    def cancel(self):
        self._cancel = True

    @pyqtSlot()
    def run(self):
        if _IMPORT_ERROR is not None:
            self.conversion_error.emit(
                f"PyMuPDF non disponible: {_IMPORT_ERROR}")
            return
        try:
            doc = fitz.open(self.file_path)
            total_pages = doc.page_count

            if self.page_range:
                start, end = self.page_range
                start = max(0, min(start, total_pages - 1))
                end = max(0, min(end, total_pages - 1))
                indices = list(range(start, end + 1))
            else:
                indices = list(range(total_pages))

            self.conversion_started.emit(len(indices))

            zoom = float(self.dpi) / 72.0
            matrix = fitz.Matrix(zoom, zoom)

            for result_idx, page_idx in enumerate(indices):
                if self._cancel:
                    break
                page = doc.load_page(page_idx)
                if self.grayscale:
                    pix = page.get_pixmap(
                        matrix=matrix, alpha=False, colorspace=fitz.csGRAY
                    )
                    fmt = QImage.Format_Grayscale8
                else:
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    fmt = QImage.Format_RGB888

                image = QImage(
                    pix.samples, pix.width, pix.height, pix.stride, fmt
                ).copy()

                thumb = image.scaledToWidth(
                    self.thumb_width, Qt.SmoothTransformation
                )
                self.page_converted.emit(result_idx, image, thumb)

            doc.close()
            self.conversion_finished.emit()
        except Exception as e:
            self.conversion_error.emit(str(e))


class PDFConverter(QObject):
    conversion_started = pyqtSignal(int)
    page_converted = pyqtSignal(int, QImage, QImage)  # index, image, thumb
    conversion_finished = pyqtSignal()
    conversion_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._thread: Optional[QThread] = None
        self._worker: Optional[PDFConversionWorker] = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start_conversion(
        self,
        file_path: str,
        dpi: int = 150,
        page_range: Optional[Tuple[int, int]] = None,
        thumb_width: int = 180,
        grayscale: bool = False,
    ):
        if self.is_running():
            self.cancel()

        self._thread = QThread()
        self._worker = PDFConversionWorker(
            file_path=file_path,
            dpi=dpi,
            page_range=page_range,
            thumb_width=thumb_width,
            grayscale=grayscale,
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.conversion_started.connect(self.conversion_started)
        self._worker.page_converted.connect(self.page_converted)
        self._worker.conversion_finished.connect(self.conversion_finished)
        self._worker.conversion_error.connect(self.conversion_error)

        self._worker.conversion_finished.connect(self._thread.quit)
        self._worker.conversion_error.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)

        self._thread.start()

    def cancel(self):
        if self._worker:
            self._worker.cancel()

    def _cleanup(self):
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
