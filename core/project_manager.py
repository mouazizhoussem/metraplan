"""Outils de sauvegarde/chargement de projet (.mtp)."""
from __future__ import annotations
from core.app_logger import get_logger
_log = get_logger(__name__)

import copy
import json
import base64
from typing import Any, Dict, List

from PyQt5.QtCore import QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QPixmap

from models.pdf_document import PDFDocument, PDFPage

PROJECT_EXTENSION = ".mtp"
PROJECT_FILTER = "Projet Metraplan (*.mtp);;Tous les fichiers (*)"
# Version actuelle du format .mtp.
# v1: {"version": 1, "pages":[{"entities_data":[...]}]}
# v2: ajout metadata + normalisation stricte des pages.
PROJECT_VERSION = 2


def ensure_project_extension(file_path: str) -> str:
    if not file_path.lower().endswith(PROJECT_EXTENSION):
        return f"{file_path}{PROJECT_EXTENSION}"
    return file_path


def save_project(main_window, file_path: str) -> bool:
    """Sauvegarde l'état des pages et entités dans un fichier JSON."""
    try:
        _flush_current_page_entities(main_window)
        pages_payload = _collect_pages_payload(main_window)

        # Sérialiser les affectations de devis
        devis_payload: Dict[str, Any] = {}
        try:
            from core.devis_manager import DevisManager
            devis_payload = DevisManager.instance().assignments_to_dict()
        except Exception as exc_devis:
            _log.warning(f"⚠ Affectations non sauvegardées : {exc_devis}")

        payload: Dict[str, Any] = {
            "version": PROJECT_VERSION,
            "metadata": {
                "app": "metraplan",
            },
            "pages": pages_payload,
            "devis": devis_payload,
        }
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        _log.warning(f"❌ Erreur sauvegarde projet: {exc}")
        return False


def load_project(main_window, file_path: str) -> bool:
    """Charge un projet depuis un fichier JSON .mtp."""
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:
        _log.warning(f"❌ Erreur lecture projet: {exc}")
        return False

    payload = _migrate_payload(payload)
    pages_raw = payload.get("pages", [])
    if not isinstance(pages_raw, list) or not pages_raw:
        return False

    try:
        _reset_workspace(main_window)
        pages = _build_pages_from_payload(pages_raw)
        if not pages:
            return False

        # Réinitialiser la liste maîtresse et la peupler avec les pages chargées.
        main_window._all_pages = list(pages)
        main_window._pdf_import_offset = 0

        # Conserver un document synthétique pour la compatibilité (normalize_pages, etc.).
        doc = PDFDocument(file_path=file_path, total_pages=len(pages))
        doc.pages = pages
        main_window.pdf_document = doc
        # IMPORTANT: laisser à None avant le premier affichage,
        # sinon on_pdf_page_selected() appelle _save_current_page_entities()
        # et écrase la page 0 avec une scène encore vide.
        main_window.current_pdf_page_index = None
        main_window._pdf_file_path = file_path

        # Restaurer les affectations de devis
        devis_data = payload.get("devis", {})
        if devis_data:
            try:
                from core.devis_manager import DevisManager
                DevisManager.instance().assignments_from_dict(devis_data)
                _log.info(f"✅ Affectations de devis restaurées")
            except Exception as exc_devis:
                _log.warning(f"⚠ Affectations non restaurées : {exc_devis}")

        if hasattr(main_window, "show_pdf_dock"):
            main_window.show_pdf_dock()
        if hasattr(main_window, "pdf_navigator") and main_window.pdf_navigator:
            main_window.pdf_navigator.set_pages(main_window._all_pages)
            main_window.pdf_navigator.set_current_page(0)
        if hasattr(main_window, "on_pdf_page_selected"):
            main_window.on_pdf_page_selected(0)
        return True
    except Exception as exc:
        _log.warning(f"❌ Erreur chargement projet: {exc}")
        return False


def _flush_current_page_entities(main_window) -> None:
    """Synchronise les entités de la page active avant sauvegarde."""
    # 1) Laisser MainWindow faire sa synchro standard (mode PDF)
    if hasattr(main_window, "_save_current_page_entities"):
        try:
            main_window._save_current_page_entities()
        except Exception as exc:
            _log.warning(f"⚠️ Sync page courante via MainWindow impossible: {exc}")

    # 2) Filet de sécurité: forcer la synchro depuis la scène courante
    # (indispensable en mode image, où pdf_document peut être absent).
    pages = _managed_pages(main_window)
    if not pages:
        return
    current_index = getattr(main_window, "current_pdf_page_index", 0) or 0
    if 0 <= current_index < len(pages):
        page = pages[current_index]
        canvas_view = getattr(main_window, "canvas_view", None)
        em = getattr(canvas_view, "entity_manager", None)
        if page and em and hasattr(page, "save_entities"):
            entities = [
                ent for ent in em.get_all_entities()
                if getattr(ent, "entity_type", "") != "opening"
            ]
            page.save_entities(entities)
            page.pixels_per_meter = getattr(canvas_view, "pixels_per_meter", 100.0) or 100.0


def _collect_pages_payload(main_window) -> List[Dict[str, Any]]:
    pages = _managed_pages(main_window)
    payload: List[Dict[str, Any]] = []
    for idx, page in enumerate(pages):
        if page is None:
            continue
        entities = copy.deepcopy(getattr(page, "entities_data", []) or [])
        payload.append(
            {
                "index": idx,
                "name": getattr(page, "name", "") or f"Page {idx + 1}",
                "pixels_per_meter": float(getattr(page, "pixels_per_meter", 100.0) or 100.0),
                "entities_data": entities,
                "pixmap_png_b64": _pixmap_to_b64(getattr(page, "pixmap", None)),
                "thumbnail_png_b64": _pixmap_to_b64(getattr(page, "thumbnail", None)),
            }
        )
    return payload


def _build_pages_from_payload(pages_raw: List[Dict[str, Any]]) -> List[PDFPage]:
    pages: List[PDFPage] = []
    for idx, raw in enumerate(pages_raw):
        page = PDFPage(
            page_index=idx,
            name=raw.get("name", f"Page {idx + 1}"),
            pixels_per_meter=float(raw.get("pixels_per_meter", 100.0) or 100.0),
        )
        page.entities_data = raw.get("entities_data", []) or []
        page.pixmap = _b64_to_pixmap(raw.get("pixmap_png_b64"))
        page.thumbnail = _b64_to_pixmap(raw.get("thumbnail_png_b64"))
        pages.append(page)
    return pages


def _pixmap_to_b64(pixmap: QPixmap) -> str:
    """Encode un QPixmap en base64 PNG pour stockage JSON."""
    if not pixmap or pixmap.isNull():
        return ""
    arr = QByteArray()
    buf = QBuffer(arr)
    if not buf.open(QIODevice.WriteOnly):
        return ""
    ok = pixmap.save(buf, "PNG")
    buf.close()
    if not ok:
        return ""
    return base64.b64encode(bytes(arr)).decode("ascii")


def _b64_to_pixmap(value: str) -> QPixmap:
    """Decode une chaîne base64 PNG vers QPixmap."""
    if not value:
        return None
    try:
        raw = base64.b64decode(value)
        pm = QPixmap()
        if pm.loadFromData(raw, "PNG"):
            return pm
        return None
    except Exception:
        return None


def _migrate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migre un payload ancien vers PROJECT_VERSION.
    Migration idempotente: relancer n'altère pas le résultat.
    """
    if not isinstance(payload, dict):
        return {"version": PROJECT_VERSION, "metadata": {"app": "metraplan"}, "pages": []}

    raw_version = payload.get("version")
    # Fichiers historiques sans version -> considérer v1.
    if raw_version is None:
        version = 1
    else:
        try:
            version = int(raw_version)
        except Exception:
            version = 1

    migrated = copy.deepcopy(payload)
    while version < PROJECT_VERSION:
        if version == 1:
            migrated = _migrate_v1_to_v2(migrated)
            version = 2
        else:
            # Garde-fou pour versions futures inconnues.
            version = PROJECT_VERSION

    # Normalisation finale défensive.
    if "metadata" not in migrated or not isinstance(migrated["metadata"], dict):
        migrated["metadata"] = {"app": "metraplan"}
    if "pages" not in migrated or not isinstance(migrated["pages"], list):
        migrated["pages"] = []
    migrated["version"] = PROJECT_VERSION
    return migrated


def _migrate_v1_to_v2(payload_v1: Dict[str, Any]) -> Dict[str, Any]:
    """Migration structurelle v1 -> v2."""
    out = copy.deepcopy(payload_v1)
    pages = out.get("pages", [])
    if not isinstance(pages, list):
        pages = []

    normalized_pages: List[Dict[str, Any]] = []
    for idx, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        entities = page.get("entities_data")
        # Compatibilité extra: certains dumps peuvent avoir 'entities' au lieu de 'entities_data'
        if entities is None:
            entities = page.get("entities", [])
        if not isinstance(entities, list):
            entities = []

        normalized_pages.append(
            {
                "index": idx,
                "name": page.get("name", f"Page {idx + 1}"),
                "pixels_per_meter": float(page.get("pixels_per_meter", 100.0) or 100.0),
                "entities_data": entities,
            }
        )

    out["pages"] = normalized_pages
    out["metadata"] = {"app": "metraplan"}
    out["version"] = 2
    return out


def _managed_pages(main_window) -> List[PDFPage]:
    if hasattr(main_window, "_managed_pages"):
        try:
            return list(main_window._managed_pages() or [])
        except Exception:
            pass
    if getattr(main_window, "pdf_document", None):
        return list(getattr(main_window.pdf_document, "pages", []) or [])
    if getattr(main_window, "pdf_navigator", None):
        return list(getattr(main_window.pdf_navigator, "_pages", []) or [])
    return []


def _reset_workspace(main_window) -> None:
    em = getattr(getattr(main_window, "canvas_view", None), "entity_manager", None)
    scene = getattr(getattr(main_window, "canvas_view", None), "scene", None)
    if em and hasattr(em, "clear_all"):
        em.clear_all(scene)
    if scene and hasattr(scene, "clear"):
        scene.clear()
    # Réinitialiser la liste maîtresse des pages
    if hasattr(main_window, "_all_pages"):
        main_window._all_pages = []
    if hasattr(main_window, "_pdf_import_offset"):
        main_window._pdf_import_offset = 0
    main_window.pdf_document = None
    main_window.current_pdf_page_index = None
    # Réinitialiser les affectations et recharger la bibliothèque par défaut
    try:
        from core.devis_manager import DevisManager
        dm = DevisManager.instance()
        dm.clear_assignments()
        dm.reload_library()   # efface les lots custom du projet précédent
    except Exception:
        pass