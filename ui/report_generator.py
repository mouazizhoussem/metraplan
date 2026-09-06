# ui/report_generator.py
"""
Générateur de données pour le rapport de quantités Metraplan.

Parcourt toutes les pages de _all_pages, reconstruit les entités,
applique la même logique _smart_qty que le panneau Pages & Mesures,
et retourne un dict structuré prêt à être affiché ou imprimé.

Intègre également les affectations BPU (DevisManager) pour générer
le rapport quantitatif et financier complet.
"""
from __future__ import annotations

import datetime
import math as _math
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.precision import P as _P

if TYPE_CHECKING:
    from ui.main_window import MainWindow


# ── Types exportés ────────────────────────────────────────────────────────────

class BpuLotRow:
    """Ligne du récapitulatif BPU par lot."""
    def __init__(self, lot_id: str, lot_label: str,
                 item_id: str, item_label: str, unit: str):
        self.lot_id    = lot_id
        self.lot_label = lot_label
        self.item_id   = item_id
        self.item_label = item_label
        self.unit      = unit
        self.qty_total: float = 0.0
        self.prix_unitaire: float = 0.0

    @property
    def total(self) -> float:
        return _P.mul(self.qty_total, self.prix_unitaire, 2)


class BpuReport:
    """Rapport BPU complet (récapitulatif financier)."""
    def __init__(self, tva_rate: float = 19.0):
        self.tva_rate = tva_rate
        # (lot_id, item_id) → BpuLotRow
        self._rows: Dict[tuple, BpuLotRow] = {}

    def add(self, lot_id: str, lot_label: str,
            item_id: str, item_label: str,
            unit: str, qty: float, pu: float):
        key = (lot_id, item_id)
        if key not in self._rows:
            self._rows[key] = BpuLotRow(lot_id, lot_label, item_id, item_label, unit)
        row = self._rows[key]
        # Accumuler avec la même précision que l'affichage pour cohérence BTP :
        # qty est déjà arrondie par compute_assignment_item(_with_vars).
        nd = 3 if (unit or "").strip().lower() in ("m³", "m3") else 2
        row.qty_total = _P.add(row.qty_total, qty, nd)
        if pu > 0:
            row.prix_unitaire = pu   # dernier PU saisi (cohérence)

    @property
    def rows(self) -> List[BpuLotRow]:
        return sorted(self._rows.values(), key=lambda r: (r.lot_id, r.item_id))

    @property
    def lots(self) -> List[str]:
        seen, out = set(), []
        for r in self.rows:
            if r.lot_id not in seen:
                seen.add(r.lot_id); out.append(r.lot_id)
        return out

    def rows_for_lot(self, lot_id: str) -> List[BpuLotRow]:
        return [r for r in self.rows if r.lot_id == lot_id]

    def subtotal_lot(self, lot_id: str) -> float:
        rows = self.rows_for_lot(lot_id)
        return _P.somme(*[r.total for r in rows], decimals=2) if rows else 0.0

    @property
    def total_ht(self) -> float:
        rows = self.rows
        return _P.somme(*[r.total for r in rows], decimals=2) if rows else 0.0

    @property
    def tva_amount(self) -> float:
        return _P.mul(self.total_ht, self.tva_rate / 100.0, 2)

    @property
    def total_ttc(self) -> float:
        return _P.add(self.total_ht, self.tva_amount, 2)


def _detect_rect_dims(points, pixels_per_meter: float,
                      tol: float = 0.02) -> Optional[Tuple[float, float]]:
    """
    Détecte si un polygone est un rectangle (ou carré) et retourne
    (longueur_m, largeur_m) triées en ordre décroissant.

    Critères : exactement 4 points, 4 angles à 90° (cosinus ≤ tol ≈ 2%).
    Fonctionne pour les rectangles droits ET inclinés.
    Retourne None si la forme n'est pas un rectangle.
    """
    if len(points) != 4:
        return None
    if pixels_per_meter <= 0:
        return None

    # Vecteurs des 4 côtés
    vecs = []
    for i in range(4):
        p1 = points[i]
        p2 = points[(i + 1) % 4]
        # Compatibilité QPointF (attributs .x()/.y()) et tuples (x, y)
        if hasattr(p1, "x"):
            dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
        else:
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        vecs.append((dx, dy))

    # Vérifier que chaque angle est à 90°
    for i in range(4):
        v1 = vecs[i]
        v2 = vecs[(i + 1) % 4]
        dot  = v1[0] * v2[0] + v1[1] * v2[1]
        n1   = _math.hypot(*v1)
        n2   = _math.hypot(*v2)
        if n1 < 1e-6 or n2 < 1e-6:
            return None
        if abs(dot) / (n1 * n2) > tol:
            return None

    # Longueurs des côtés en mètres (moyenne des deux paires opposées)
    side_lens = [_math.hypot(*v) / pixels_per_meter for v in vecs]
    L = round((side_lens[0] + side_lens[2]) / 2.0, 2)
    l = round((side_lens[1] + side_lens[3]) / 2.0, 2)
    return (max(L, l), min(L, l))


class GroupBpuItem:
    """Item affecté à un groupe, avec quantité calculée."""
    def __init__(self, lot_id: str, lot_label: str,
                 item_id: str, item_label: str, unit: str,
                 formula_expr: str, qty: float,
                 prix_unitaire: float, total: float, error: str = "",
                 page_name: str = "", group_name: str = "",
                 variables: Optional[Dict[str, float]] = None,
                 group_type: str = "",
                 openings_detail: Optional[List[Dict]] = None,
                 dims_brute: Optional[Tuple[float, float]] = None,
                 members_detail: Optional[List[Dict]] = None,
                 coefficient: float = 1.0):
        self.lot_id          = lot_id
        self.lot_label       = lot_label
        self.item_id         = item_id
        self.item_label      = item_label
        self.unit            = unit
        self.formula_expr    = formula_expr
        self.qty             = qty
        self.prix_unitaire   = prix_unitaire
        self.total           = total
        self.error           = error
        self.page_name       = page_name
        self.group_name      = group_name
        self.variables: Dict[str, float] = variables or {}
        self.group_type      = group_type   # "polygon"/"perimeter"/"point"
        # Détail des ouvertures/déductions pour le justificatif d'attachement
        # Liste de dicts : {"label": str, "length_m": float, "height": float, "area": float}
        self.openings_detail: List[Dict] = openings_detail or []
        # Dimensions L × l (m) si le groupe est un rectangle/carré unique, sinon None
        self.dims_brute: Optional[Tuple[float, float]] = dims_brute
        # Détail par membre pour les groupes multi-surfaces
        # Liste de dicts : {"label", "dims", "area_brute", "area_nette", "openings"}
        self.members_detail: List[Dict] = members_detail or []
        # Coefficient multiplicateur (champ "× nombre" du panneau d'affectation)
        self.coefficient: float = coefficient


class PageReport:
    """Quantités mesurées pour une page."""
    def __init__(self, page_index: int, page_name: str):
        self.page_index = page_index
        self.page_name  = page_name
        # liste de dicts {name, type, qty, unit, count, bpu_items}
        self.items: List[Dict[str, Any]] = []


class GlobalRow:
    """Ligne de synthèse globale (même désignation sur plusieurs pages)."""
    def __init__(self, name: str, etype: str, unit: str):
        self.name   = name
        self.etype  = etype
        self.unit   = unit
        # {page_name: qty}
        self.by_page: Dict[str, float] = {}
        self.total: float = 0.0


class ReportData:
    """Structure complète produite par generate_report()."""
    def __init__(self):
        self.metadata: Dict[str, str] = {}
        self.tva_rate: float = 19.0
        self.page_reports: List[PageReport] = []
        # clé : (name, etype, unit) → GlobalRow
        self._global: Dict[tuple, GlobalRow] = {}
        # Rapport BPU (affectations de devis)
        self.bpu: Optional[BpuReport] = None

    @property
    def global_rows(self) -> List[GlobalRow]:
        return sorted(self._global.values(), key=lambda r: (r.etype, r.name))

    def all_page_names(self) -> List[str]:
        seen, out = set(), []
        for pr in self.page_reports:
            if pr.page_name not in seen:
                seen.add(pr.page_name)
                out.append(pr.page_name)
        return out


# ── Fonction principale ───────────────────────────────────────────────────────

def generate_report(main_window: "MainWindow") -> ReportData:
    """
    Collecte toutes les mesures de toutes les pages et retourne un ReportData.
    Réutilise _smart_qty pour garantir la cohérence avec Pages & Mesures.
    """
    from models.pdf_document import create_entity_from_dict
    from ui.pdf_measurements_panel import _smart_qty

    rd = ReportData()

    # ── Métadonnées projet ────────────────────────────────────────────────────
    meta = getattr(main_window, "project_metadata", {}) or {}
    rd.metadata = {
        "name":         meta.get("name", "Projet sans nom"),
        "number":       meta.get("number", ""),
        "owner":        meta.get("owner", ""),
        "architect":    meta.get("architect", ""),
        "company":      meta.get("company", ""),
        "date":         meta.get("created_date", "")
                        or datetime.date.today().strftime("%d/%m/%Y"),
    }

    # TVA depuis les métadonnées projet (modifiable par l'utilisateur)
    rd.tva_rate = float(meta.get("tva_rate", 19.0))
    rd.bpu = BpuReport(tva_rate=rd.tva_rate)

    pages = getattr(main_window, "_all_pages", None) or []
    if not pages:
        return rd

    # Sauvegarder la page active pour que ses entités soient à jour
    if hasattr(main_window, "_save_current_page_entities"):
        try:
            main_window._save_current_page_entities()
        except Exception:
            pass

    # ── Types à exclure du rapport ────────────────────────────────────────────
    EXCLUDED_TYPES = {"opening", "line", "scale", "marker", "distance"}

    for page_idx, page in enumerate(pages):
        if page is None:
            continue
        entities_data = getattr(page, "entities_data", None) or []
        if not entities_data:
            continue

        page_name = getattr(page, "name", None) or f"Page {page_idx + 1}"
        pr = PageReport(page_idx, page_name)

        # 1) Reconstruire les entités
        entities = []
        for d in entities_data:
            ent = create_entity_from_dict(d)
            if ent is not None:
                entities.append(ent)

        # 2) Rétablir les liens de groupe (parent / enfants)
        if hasattr(main_window, "_rebuild_group_links"):
            main_window._rebuild_group_links(entities)

        # 3) Filtrer : garder uniquement les racines (pas les enfants de groupe)
        root_entities = [
            e for e in entities
            if getattr(e, "entity_type", "") not in EXCLUDED_TYPES
            and getattr(e, "parent_entity", None) is None
        ]

        # 4) Dédoublonner par group_id (ne garder que le parent)
        seen_groups: set = set()
        for ent in root_entities:
            # group_id persistant → entity_id stable (périmètres sans groupe) → None
            gid = (getattr(ent, "group_id", None)
                   or getattr(ent, "entity_id", None))
            if gid:
                if gid in seen_groups:
                    continue
                seen_groups.add(gid)

            # 5) Calculer la quantité
            try:
                qty, unit = _smart_qty(ent)
            except Exception:
                qty, unit = 0.0, ""

            count = 1 + len(getattr(ent, "child_entities", []) or [])
            name  = getattr(ent, "name", "") or "Sans nom"
            etype = getattr(ent, "entity_type", "")

            # 6a) Extraire le détail des ouvertures par membre (pour l'attachement)
            openings_detail: List[Dict] = []   # liste plate (tous membres confondus)
            _member_data:    List[Dict] = []   # par membre (pour members_detail)
            try:
                members_ent = [ent] + list(getattr(ent, "child_entities", []) or [])
                is_poly = etype in ("polygon", "surface")

                ouv_global = 1   # compteur global d'ouvertures (continu sur tous les membres)
                for midx, m in enumerate(members_ent):
                    m_ppm    = float(getattr(m, "pixels_per_meter", 1.0) or 1.0)
                    m_opngs: List[Dict] = []   # ouvertures de CE membre uniquement

                    # ── Aire brute du membre ──────────────────────────────────
                    try:
                        m_area_brute = _P.round(
                            float(m.calculate_area()
                                  if hasattr(m, "calculate_area") else 0.0), 2)
                    except Exception:
                        m_area_brute = 0.0

                    # ── Dimensions rectangle du membre ────────────────────────
                    m_pts  = getattr(m, "points", []) or []
                    m_dims = _detect_rect_dims(m_pts, m_ppm) if is_poly else None

                    # ── Périmètre : ouvertures linéaires (portes/fenêtres) ────
                    for op in (getattr(m, "linear_openings", []) or []):
                        lm = _P.round(float(op.get("length_m", 0.0) or 0.0), 2)
                        oh = _P.round(float(op.get("height",   0.0) or 0.0), 2)
                        if lm > 0 and oh > 0:
                            lbl_g = f"Ouv.{ouv_global}"
                            ouv_global += 1
                            entry = {
                                "label":    lbl_g,
                                "length_m": lm,
                                "height":   oh,
                                "area":     _P.surface(lm, oh),
                            }
                            openings_detail.append(entry)
                            m_opngs.append(dict(entry))

                    # ── Surface : ouvertures polygonales ──────────────────────
                    live_opngs    = getattr(m, "openings",               []) or []
                    pending_opngs = getattr(m, "_pending_openings_data", []) or []

                    # Mode canvas : OpeningEntity avec QPointF
                    for op in live_opngs:
                        try:
                            pts    = getattr(op, "points", []) or []
                            ppm_op = float(getattr(op, "pixels_per_meter", m_ppm) or m_ppm)
                            if len(pts) >= 3 and ppm_op > 0:
                                n = len(pts)
                                area_px = abs(sum(
                                    pts[i].x() * pts[(i+1) % n].y() -
                                    pts[(i+1) % n].x() * pts[i].y()
                                    for i in range(n)
                                )) / 2.0
                                area_m   = _P.round(area_px / (ppm_op ** 2), 2)
                                rect_ouv = _detect_rect_dims(pts, ppm_op)
                                lbl_g    = f"Ouv.{ouv_global}"
                                ouv_global += 1
                                entry = {
                                    "label":    lbl_g,
                                    "length_m": rect_ouv[0] if rect_ouv else 0.0,
                                    "height":   rect_ouv[1] if rect_ouv else 0.0,
                                    "area":     area_m,
                                }
                                openings_detail.append(entry)
                                m_opngs.append(dict(entry))
                        except Exception:
                            pass

                    # Mode rapport : dicts avec tuples (x, y)
                    for op_d in pending_opngs:
                        try:
                            pts_raw = op_d.get("points", []) or []
                            ppm_op  = float(op_d.get("pixels_per_meter", m_ppm) or m_ppm)
                            if len(pts_raw) >= 3 and ppm_op > 0:
                                np_ = len(pts_raw)
                                a = 0.0
                                for i in range(np_):
                                    j = (i + 1) % np_
                                    a += pts_raw[i][0] * pts_raw[j][1]
                                    a -= pts_raw[j][0] * pts_raw[i][1]
                                area_m   = _P.round(abs(a) / 2.0 / (ppm_op ** 2), 2)
                                rect_ouv = _detect_rect_dims(pts_raw, ppm_op)
                                lbl_g    = f"Ouv.{ouv_global}"
                                ouv_global += 1
                                entry = {
                                    "label":    lbl_g,
                                    "length_m": rect_ouv[0] if rect_ouv else 0.0,
                                    "height":   rect_ouv[1] if rect_ouv else 0.0,
                                    "area":     area_m,
                                }
                                openings_detail.append(entry)
                                m_opngs.append(dict(entry))
                        except Exception:
                            pass

                    # ── Accumuler les données de ce membre ────────────────────
                    m_area_ded   = _P.somme_surfaces(*[op["area"] for op in m_opngs]) if m_opngs else 0.0
                    m_area_nette = _P.surface_nette(m_area_brute, m_area_ded)
                    # Label séquentiel : "Surface 1", "Surface 2"... indépendant du nom entité
                    m_label = f"Surface {midx+1}"
                    _member_data.append({
                        "label":      m_label,
                        "dims":       m_dims,
                        "area_brute": m_area_brute,
                        "area_nette": m_area_nette,
                        "openings":   m_opngs,
                    })
            except Exception:
                pass

            # 6b) Dériver dims_brute et members_detail depuis _member_data
            dims_brute:     Optional[Tuple[float, float]] = None
            members_detail: List[Dict]                    = []
            if etype in ("polygon", "surface"):
                if len(_member_data) == 1:
                    # Surface unique → dims_brute pour le format actuel
                    dims_brute = _member_data[0].get("dims")
                elif len(_member_data) > 1:
                    # Groupe multi-surfaces → détail par membre
                    members_detail = _member_data

            # 6c) Récupérer les items de devis affectés à ce groupe
            bpu_items: List[GroupBpuItem] = []
            if gid:
                try:
                    from core.devis_manager import DevisManager
                    from core.formula_engine import compute_assignment_item_with_vars
                    dm = DevisManager.instance()
                    ga = dm.get_assignment(gid)
                    if ga:
                        for ai in ga.items:
                            ai_qty, ai_total, ai_err, ai_vars = \
                                compute_assignment_item_with_vars(ent, ai)
                            lot_obj    = dm.get_lot(ai.lot_id)
                            lot_label  = f"{ai.lot_id} – {lot_obj.label}" if lot_obj else ai.lot_id
                            item_label = dm.get_item_label(ai.lot_id, ai.item_id)
                            item_unit  = dm.get_item_unit(ai.lot_id, ai.item_id)
                            bpu_items.append(GroupBpuItem(
                                lot_id          = ai.lot_id,
                                lot_label       = lot_label,
                                item_id         = ai.item_id,
                                item_label      = item_label,
                                unit            = item_unit,
                                formula_expr    = ai.formula_expr,
                                qty             = ai_qty,
                                prix_unitaire   = ai.prix_unitaire,
                                total           = ai_total,
                                error           = ai_err,
                                page_name       = page_name,
                                group_name      = name,
                                variables       = ai_vars,
                                group_type      = etype,
                                openings_detail = openings_detail,
                                dims_brute      = dims_brute,
                                members_detail  = members_detail,
                                coefficient     = float(getattr(ai, "coefficient", 1.0)),
                            ))
                            # Accumulation BPU
                            if rd.bpu:
                                rd.bpu.add(
                                    ai.lot_id, lot_label,
                                    ai.item_id, item_label,
                                    item_unit, ai_qty, ai.prix_unitaire,
                                )
                except Exception:
                    pass

            pr.items.append({
                "name":      name,
                "type":      etype,
                "qty":       qty,
                "unit":      unit,
                "count":     count,
                "bpu_items": bpu_items,
            })

            # 7) Accumulation globale (par désignation + type + unité)
            key = (name, etype, unit)
            if key not in rd._global:
                rd._global[key] = GlobalRow(name, etype, unit)
            grow = rd._global[key]
            _nd = 3 if (unit or "").strip().lower() in ("m³", "m3") else 2
            grow.by_page[page_name] = _P.add(
                grow.by_page.get(page_name, 0.0), qty, _nd)
            grow.total = _P.add(grow.total, qty, _nd)

        rd.page_reports.append(pr)

    return rd


# ── Helpers de formatage ──────────────────────────────────────────────────────

def _decimals_for_unit(unit: str) -> int:
    """Retourne le nombre de décimales selon l'unité physique."""
    u = (unit or "").strip()
    if u in ("m³", "m3"):
        return 3          # volumes béton/maçonnerie : 3 décimales
    if u in ("m²", "m2", "ml", "m", "km"):
        return 2          # surfaces et longueurs : 2 décimales
    if u in ("u.", "u", "ens.", "forfait"):
        return 0          # compteurs : entier
    return 3              # défaut sécuritaire : 3 décimales


def fmt_qty(value: float, unit: str) -> str:
    """Formate une quantité avec son unité (précision selon l'unité)."""
    u = (unit or "").strip()
    n = _decimals_for_unit(u)
    if n == 0:
        return f"{int(round(value))} {u}" if u else str(int(round(value)))
    return f"{value:.{n}f} {u}".strip()


def type_label(etype: str) -> str:
    """Libellé lisible pour un type d'entité."""
    return {
        "polygon":   "Surface",
        "perimeter": "Périmètre",
        "point":     "Compteur",
    }.get(etype, etype.capitalize())


# ── Helpers HTML partagés ────────────────────────────────────────────────────

def _rh_th(label: str, align: str = "left", width: str = "") -> str:
    """Cellule d'en-tête de tableau (thème bleu)."""
    w = f"width:{width};" if width else ""
    return (f"<th style='background:#1565c0;color:#ffffff;padding:7pt 9pt;"
            f"font-size:9pt;font-weight:bold;border:1px solid #0d47a1;"
            f"text-align:{align};{w}'>{label}</th>")


def _rh_th_green(label: str, align: str = "left", width: str = "") -> str:
    """Cellule d'en-tête de tableau (thème vert)."""
    w = f"width:{width};" if width else ""
    return (f"<th style='background:#2e7d32;color:#ffffff;padding:7pt 9pt;"
            f"font-size:9pt;font-weight:bold;border:1px solid #1b5e20;"
            f"text-align:{align};{w}'>{label}</th>")


def _rh_td(content: str, align: str = "left", bold: bool = False,
           color: str = "#1a1a2e", bg: str = "#ffffff",
           size: str = "9pt", italic: bool = False,
           border: str = "1px solid #cfd8dc") -> str:
    """Cellule de données avec style inline."""
    fw  = "bold" if bold else "normal"
    fst = "italic" if italic else "normal"
    return (f"<td style='border:{border};padding:5pt 8pt;"
            f"font-size:{size};font-weight:{fw};font-style:{fst};"
            f"color:{color};background:{bg};text-align:{align}'>"
            f"{content}</td>")


def _rh_h2(title: str, color: str = "#0d47a1",
           bg: str = "#e3f2fd", accent: str = "#1565c0",
           page_break: bool = False) -> str:
    """Titre de section h2 avec bannière colorée."""
    pb = "page-break-before:always;" if page_break else ""
    return (f"<h2 style='font-size:13pt;color:{color};font-weight:bold;"
            f"margin:28px 0 10px 0;padding:8px 14px;"
            f"background:{bg};border-left:5px solid {accent};{pb}'>"
            f"{title}</h2>")


def _rh_h3(title: str) -> str:
    """Titre de sous-section h3 avec bannière bleue."""
    return (f"<h3 style='font-size:11pt;color:#1565c0;font-weight:bold;"
            f"margin:18px 0 6px 0;padding:5px 10px;"
            f"background:#e8f0fe;border-left:4px solid #1565c0'>"
            f"&#128196;&nbsp;{title}</h3>")


def _rh_fmt_da(amount: float) -> str:
    return f"{amount:,.0f}&nbsp;DA".replace(",", "\u202f")


_HTML_BASE_STYLE = """
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: #1a1a2e;
    line-height: 1.5;
    margin: 0;
  }
  p, td, th { font-family: 'Segoe UI', Arial, sans-serif; }
  @media print {
    h2 { page-break-before: always; }
    h3 { page-break-before: auto; }
    tr { page-break-inside: avoid; }
  }
"""


def _rh_wrap(body: str, extra_style: str = "") -> str:
    """Enveloppe le corps HTML dans un document complet."""
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            f"<style>{_HTML_BASE_STYLE}{extra_style}</style></head>"
            f"<body>{body}</body></html>")


def build_html_header(meta: dict, today: str) -> str:
    """Génère le bloc d'en-tête projet commun à tous les rapports."""
    meta_rows = ""
    for label, key in [
        ("Projet",            "name"),
        ("N° de projet",      "number"),
        ("Maître d'ouvrage",  "owner"),
        ("Maître d'œuvre",    "architect"),
        ("Entreprise",        "company"),
        ("Date",              "date"),
    ]:
        val = meta.get(key, "")
        if val:
            meta_rows += (
                f"<tr>"
                f"<td style='border:none;color:#546e7a;font-size:9pt;"
                f"width:170px;padding:3pt 10pt;vertical-align:top'>{label}</td>"
                f"<td style='border:none;font-weight:bold;font-size:10pt;"
                f"padding:3pt 10pt'>{val}</td>"
                f"</tr>"
            )
    return f"""
<table width="100%" style="border-collapse:collapse;margin-bottom:6px">
  <tr><td style="border:none;padding:0 0 4px 0">
    <p style="font-size:18pt;font-weight:bold;color:#0d47a1;margin:0 0 2px 0">
      Devis Quantitatif et Estimatif
    </p>
    <p style="font-size:9pt;color:#78909c;margin:0">
      Métraplan &mdash; Généré le {today}
    </p>
  </td></tr>
</table>
<table style="border-collapse:collapse;margin-bottom:16px;
              border-left:5px solid #1565c0;background:#f8fbff;width:60%">
  {meta_rows}
</table>
<hr style="border:none;border-top:2px solid #1565c0;margin:0 0 20px 0"/>"""


def build_html_pages_section(rd: ReportData) -> str:
    """HTML de la section relevé quantitatif par page."""
    pages_html = ""
    for pr in rd.page_reports:
        if not pr.items:
            continue
        rows = ""
        alt  = False
        for item in pr.items:
            icon      = {"polygon": "■", "perimeter": "╱", "point": "●"}.get(item["type"], "•")
            count_lbl = f"&nbsp;×&nbsp;{item['count']}" if item["count"] > 1 else ""
            bg_group  = "#eef4ff" if not alt else "#f4f7ff"
            alt       = not alt
            rows += (
                f"<tr style='background:{bg_group}'>"
                + _rh_td(f"<span style='font-size:11pt'>{icon}</span>",
                         align="center", color="#546e7a", bg=bg_group, border="1px solid #cfd8dc")
                + _rh_td(f"<b>{item['name']}{count_lbl}</b>",
                         size="10pt", bg=bg_group, border="1px solid #cfd8dc")
                + _rh_td(type_label(item["type"]),
                         color="#607080", bg=bg_group, border="1px solid #cfd8dc")
                + _rh_td(fmt_qty(item["qty"], item["unit"]),
                         align="right", bold=True, color="#1565c0",
                         size="10pt", bg=bg_group, border="1px solid #cfd8dc")
                + _rh_td("", bg=bg_group, border="1px solid #cfd8dc")
                + _rh_td("", bg=bg_group, border="1px solid #cfd8dc")
                + "</tr>"
            )
            for bi in item.get("bpu_items", []):
                err_str = (f"&nbsp;<span style='color:#e53935'>⚠ {bi.error}</span>"
                           if bi.error else "")
                qty_str = _fmt_money_num(bi.qty, bi.unit)
                pu_str  = _rh_fmt_da(bi.prix_unitaire) if bi.prix_unitaire else "—"
                tot_str = _rh_fmt_da(bi.total)         if bi.total        else "—"
                rows += (
                    "<tr>"
                    + _rh_td("&nbsp;&nbsp;└", align="center", color="#bbb",
                             size="8pt", border="1px solid #e0e0e0")
                    + _rh_td(f"&nbsp;&nbsp;&nbsp;{bi.item_id}&nbsp;—&nbsp;"
                             f"{bi.item_label}{err_str}",
                             color="#37474f", border="1px solid #e0e0e0")
                    + _rh_td(bi.formula_expr, color="#90a4ae", italic=True,
                             size="8pt", border="1px solid #e0e0e0")
                    + _rh_td(qty_str, align="right", border="1px solid #e0e0e0")
                    + _rh_td(pu_str,  align="right", color="#546e7a",
                             border="1px solid #e0e0e0")
                    + _rh_td(tot_str, align="right", bold=True, color="#1b5e20",
                             border="1px solid #e0e0e0")
                    + "</tr>"
                )
        pages_html += f"""
{_rh_h3(pr.page_name)}
<table width="100%" style="border-collapse:collapse;margin-bottom:18px">
  <thead><tr>
    {_rh_th("", width="28px")}
    {_rh_th("Groupe / Désignation")}
    {_rh_th("Formule")}
    {_rh_th("Quantité",   align="right", width="95px")}
    {_rh_th("P.U. (DA)",  align="right", width="110px")}
    {_rh_th("Montant (DA)", align="right", width="120px")}
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""
    return pages_html


def build_html_global_section(rd: ReportData) -> str:
    """HTML de la section synthèse globale des mesures."""
    if not rd.global_rows:
        return ""
    global_rows_html = ""
    alt = False
    for row in rd.global_rows:
        icon = {"polygon": "■", "perimeter": "╱", "point": "●"}.get(row.etype, "•")
        bg   = "#f5f8ff" if alt else "#ffffff"
        alt  = not alt
        global_rows_html += (
            "<tr>"
            + _rh_td(f"<span style='font-size:11pt'>{icon}</span>",
                     align="center", color="#546e7a", bg=bg)
            + _rh_td(row.name, size="10pt", bg=bg)
            + _rh_td(type_label(row.etype), color="#607080", bg=bg)
            + _rh_td(fmt_qty(row.total, row.unit),
                     align="right", bold=True, color="#1565c0", size="10pt", bg=bg)
            + "</tr>"
        )
    return f"""
{_rh_h2("Synthèse des mesures — toutes pages")}
<table width="100%" style="border-collapse:collapse;margin-bottom:18px">
  <thead><tr>
    {_rh_th("", width="28px")}
    {_rh_th("Désignation")}
    {_rh_th("Type")}
    {_rh_th("Total", align="right", width="120px")}
  </tr></thead>
  <tbody>{global_rows_html}</tbody>
</table>"""


def build_html_bpu_recap_section(rd: ReportData, page_break: bool = True) -> str:
    """HTML de la section récapitulatif BPU financier."""
    bpu = rd.bpu
    if not bpu or not bpu.rows:
        return ""

    lots_html = ""
    for lot_id in bpu.lots:
        lot_rows      = bpu.rows_for_lot(lot_id)
        lot_label_str = lot_rows[0].lot_label if lot_rows else lot_id
        lot_rows_html = ""
        alt = False
        for r in lot_rows:
            pu_str  = _rh_fmt_da(r.prix_unitaire) if r.prix_unitaire else "—"
            tot_str = _rh_fmt_da(r.total)
            bg      = "#ffffff" if alt else "#f9fef9"
            alt     = not alt
            lot_rows_html += (
                "<tr>"
                + _rh_td(r.item_id,    bg=bg, border="1px solid #c8e6c9")
                + _rh_td(r.item_label, bg=bg, border="1px solid #c8e6c9")
                + _rh_td(r.unit, align="center", bg=bg, border="1px solid #c8e6c9")
                + _rh_td(f"{r.qty_total:.3f}", align="right", bg=bg,
                         border="1px solid #c8e6c9")
                + _rh_td(pu_str,  align="right", bg=bg, border="1px solid #c8e6c9")
                + _rh_td(tot_str, align="right", bold=True, color="#1b5e20",
                         bg=bg, border="1px solid #c8e6c9")
                + "</tr>"
            )
        sub     = bpu.subtotal_lot(lot_id)
        sub_str = _rh_fmt_da(sub)
        lots_html += f"""
<tr style="background:#2e7d32">
  <td colspan="6" style="border:1px solid #1b5e20;padding:7pt 12pt;
      font-weight:bold;color:#ffffff;font-size:10pt">
    LOT {lot_id} &mdash; {lot_label_str}
  </td>
</tr>
{lot_rows_html}
<tr style="background:#e8f5e9">
  <td colspan="5" style="border:1px solid #a5d6a7;padding:5pt 10pt;
      text-align:right;font-weight:bold;color:#2e7d32;font-size:9pt">
    Sous-total LOT {lot_id}
  </td>
  <td style="border:2px solid #2e7d32;padding:5pt 10pt;text-align:right;
      font-weight:bold;color:#1b5e20;font-size:10pt">{sub_str}</td>
</tr>
<tr><td colspan="6" style="border:none;padding:6pt"></td></tr>"""

    ht_str      = _rh_fmt_da(bpu.total_ht)
    tva_str     = _rh_fmt_da(bpu.tva_amount)
    ttc_str     = _rh_fmt_da(bpu.total_ttc)
    ttc_lettres = _number_to_words_fr(int(round(bpu.total_ttc)))

    return f"""
{_rh_h2("BORDEREAU DES PRIX UNITAIRES — RÉCAPITULATIF",
         color="#1b5e20", bg="#e8f5e9", accent="#2e7d32",
         page_break=page_break)}
<table width="100%" style="border-collapse:collapse;margin-bottom:20px">
  <thead><tr>
    {_rh_th_green("N°",          width="60px")}
    {_rh_th_green("Désignation")}
    {_rh_th_green("U.",          align="center", width="42px")}
    {_rh_th_green("Quantité",    align="right",  width="80px")}
    {_rh_th_green("P.U. (DA)",   align="right",  width="115px")}
    {_rh_th_green("Montant (DA)", align="right", width="125px")}
  </tr></thead>
  <tbody>{lots_html}</tbody>
</table>
<table width="50%" style="margin-left:50%;border-collapse:collapse;
       margin-top:16px;font-size:10pt">
  <tr>
    <td style="border:1px solid #bdbdbd;padding:6pt 14pt;color:#37474f;width:200px">
        MONTANT TOTAL H.T.</td>
    <td style="border:1px solid #bdbdbd;padding:6pt 14pt;
        text-align:right;font-weight:bold">{ht_str}</td>
  </tr>
  <tr style="background:#f5f5f5">
    <td style="border:1px solid #bdbdbd;padding:6pt 14pt;color:#37474f">
        TVA {bpu.tva_rate:.0f}&nbsp;%</td>
    <td style="border:1px solid #bdbdbd;padding:6pt 14pt;text-align:right">{tva_str}</td>
  </tr>
  <tr style="background:#e8f5e9">
    <td style="border:2px solid #2e7d32;padding:8pt 14pt;
        font-weight:bold;color:#1b5e20;font-size:11pt">
        MONTANT TOTAL T.T.C.</td>
    <td style="border:2px solid #2e7d32;padding:8pt 14pt;text-align:right;
        font-weight:bold;font-size:12pt;color:#1b5e20">{ttc_str}</td>
  </tr>
</table>
<p style="margin-top:18px;font-style:italic;color:#37474f;font-size:10pt;
          border-top:1px solid #ccc;padding-top:14px">
  <b>Arrêté le présent devis à la somme de&nbsp;:</b><br/>
  {ttc_lettres} dinars algériens (T.T.C.)
</p>"""


def build_html_report(rd: ReportData) -> str:
    """
    Génère le rapport complet (toutes sections) en HTML.
    Peut être passé à QTextDocument.setHtml() pour l'impression / export PDF.
    """
    today  = datetime.date.today().strftime("%d/%m/%Y")
    header = build_html_header(rd.metadata, today)
    pages  = build_html_pages_section(rd)
    glob   = build_html_global_section(rd)
    bpu    = build_html_bpu_recap_section(rd, page_break=True)
    return _rh_wrap(f"{header}{pages}{glob}{bpu}")


def _fmt_money_num(qty: float, unit: str) -> str:
    if unit in ("m²", "m³"):
        return f"{qty:.2f} {unit}"
    if unit in ("ml", "m"):
        return f"{qty:.2f} {unit}"
    if unit == "U":
        return f"{int(round(qty))} U"
    return f"{qty:.2f}"


def _number_to_words_fr(n: int) -> str:
    """Convertit un entier en lettres françaises (simplifié pour DA)."""
    try:
        from num2words import num2words
        return num2words(n, lang="fr").capitalize()
    except ImportError:
        pass
    # Fallback minimaliste si num2words non installé
    if n == 0:
        return "Zéro"
    units = ["", "un", "deux", "trois", "quatre", "cinq", "six", "sept",
             "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze",
             "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
    tens  = ["", "", "vingt", "trente", "quarante", "cinquante",
             "soixante", "soixante-dix", "quatre-vingt", "quatre-vingt-dix"]

    def _below_1000(x):
        if x == 0: return ""
        if x < 20: return units[x]
        if x < 100:
            t, u = divmod(x, 10)
            return tens[t] + ("-" + units[u] if u else "")
        c, r = divmod(x, 100)
        prefix = ("cent" if c == 1 else units[c] + " cent")
        return prefix + (" " + _below_1000(r) if r else "")

    parts = []
    if n >= 1_000_000:
        m, n = divmod(n, 1_000_000)
        parts.append(_below_1000(m) + " million" + ("s" if m > 1 else ""))
    if n >= 1_000:
        k, n = divmod(n, 1_000)
        parts.append(("mille" if k == 1 else _below_1000(k) + " mille"))
    if n > 0:
        parts.append(_below_1000(n))
    return " ".join(p for p in parts if p).capitalize()
