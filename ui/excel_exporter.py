# ui/excel_exporter.py
"""
Export Excel pour les onglets Devis général et Attachement de Métraplan.
Fidélité maximale à l'affichage écran : couleurs, fusions, polices, formats.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.report_panel import ReportPanel


# ── Palettes (alignées sur report_panel.py) ───────────────────────────────────

_LOT_BG      = "FF1565C0"   # bleu foncé en-tête lot (Devis)
_LOT_FG      = "FFFFFFFF"
_ART_BG      = "FFDDEEFF"   # fond article polygon
_SUB_BG      = "FFF4F8FF"
_TOT_BG      = "FFFFF9C4"   # jaune total
_HT_BG       = "FFE3F2FD"
_TVA_BG      = "FFFFF8E1"
_TTC_BG      = "FFE8F5E9"
_SEP_BG      = "FFC8D4E8"
_HDR_BG_ATT  = "FF0D47A1"   # en-tête colonnes attachement
_LOT_BG_ATT  = "FFDDE8F5"
_LOT_FG_ATT  = "FF0D47A1"
_ART_BG_POLY = "FFDDEEFF"
_ART_BG_PERI = "FFFFEEDD"
_ART_BG_PT   = "FFDDF5E4"
_SUB_BG_ATT  = "FFF4F8FF"
_TOT_BG_ATT  = "FFFFFDE7"

_TYPE_BG = {
    "polygon":   _ART_BG_POLY,
    "perimeter": _ART_BG_PERI,
    "point":     _ART_BG_PT,
    "unknown":   "FFF3E5F5",
}


def _hex(html: str) -> str:
    """Convertit '#rrggbb' ou '#aarrggbb' vers 'AARRGGBB' pour openpyxl."""
    h = html.lstrip("#")
    if len(h) == 6:
        return "FF" + h.upper()
    if len(h) == 8:
        return h.upper()
    return "FF000000"


def _fill(hex_argb: str):
    from openpyxl.styles import PatternFill
    return PatternFill("solid", fgColor=hex_argb)


def _font(bold=False, italic=False, size=10, color="FF000000"):
    from openpyxl.styles import Font
    return Font(bold=bold, italic=italic, size=size, color=color, name="Calibri")


def _align(h="left", v="center", wrap=False):
    from openpyxl.styles import Alignment
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


def _border_thin():
    from openpyxl.styles import Border, Side
    s = Side(style="thin", color="FFB0C0D0")
    return Border(left=s, right=s, top=s, bottom=s)


def _num_fmt(value: float) -> str:
    """Format français : 30 000,00"""
    try:
        f = f"{value:,.2f}"
        int_p, dec_p = f.split(".")
        int_p = int_p.replace(",", "\u00a0")
        return f"{int_p},{dec_p}"
    except Exception:
        return str(value)


# ══════════════════════════════════════════════════════════════════════════════
#  Export — Devis général
# ══════════════════════════════════════════════════════════════════════════════

def export_devis_xlsx(panel: "ReportPanel", path: str) -> None:
    """
    Exporte l'onglet Devis général vers un fichier .xlsx.
    Lit directement self._data.bpu pour être indépendant de l'affichage.
    """
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    data = getattr(panel, "_data", None)
    if not data:
        raise ValueError("Aucune donnée de rapport disponible.")

    bpu = getattr(data, "bpu", None)
    if not bpu or not bpu.rows:
        raise ValueError("Aucun article de devis affecté.")

    wb = Workbook()
    ws = wb.active
    ws.title = "Devis général"

    # ── Largeurs colonnes ────────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 50   # Désignation
    ws.column_dimensions["B"].width = 10   # Unité
    ws.column_dimensions["C"].width = 14   # Quantité
    ws.column_dimensions["D"].width = 18   # P.U. (DA)
    ws.column_dimensions["E"].width = 20   # Total (DA)

    # ── En-tête du tableau ───────────────────────────────────────────────────
    headers = ["Désignation", "Unité", "Quantité", "P.U. (DA)", "Total (DA)"]
    hdr_row = 1
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=hdr_row, column=col, value=h)
        c.fill  = _fill("FF1565C0")
        c.font  = _font(bold=True, color="FFFFFFFF", size=11)
        c.alignment = _align("center")
        c.border = _border_thin()

    row = 2

    # ── Métadonnées projet ───────────────────────────────────────────────────
    meta = getattr(data, "metadata", {}) or {}
    for label, key in [
        ("Projet",           "name"),
        ("N° de projet",     "number"),
        ("Maître d'ouvrage", "owner"),
        ("Maître d'œuvre",   "architect"),
        ("Entreprise",       "company"),
    ]:
        val = meta.get(key, "")
        if val:
            ws.merge_cells(start_row=row, start_column=1,
                           end_row=row, end_column=5)
            c = ws.cell(row=row, column=1,
                        value=f"{label} : {val}")
            c.font = _font(italic=True, size=9, color="FF607080")
            c.alignment = _align("left")
            row += 1

    if row > 2:
        ws.cell(row=row, column=1)
        row += 1

    # ── Lots et articles ─────────────────────────────────────────────────────
    for lot_id in bpu.lots:
        rows_lot = bpu.rows_for_lot(lot_id)
        if not rows_lot:
            continue

        lot_label = rows_lot[0].lot_label

        # Ligne en-tête lot (fusion A-E)
        ws.merge_cells(start_row=row, start_column=1,
                       end_row=row, end_column=5)
        c = ws.cell(row=row, column=1,
                    value=f"  LOT  {lot_label}")
        c.fill  = _fill(_LOT_BG)
        c.font  = _font(bold=True, color=_LOT_FG, size=11)
        c.alignment = _align("left")
        c.border = _border_thin()
        ws.row_dimensions[row].height = 20
        row += 1

        for bpu_row in rows_lot:
            # Ligne article
            desig = f"    {bpu_row.item_id}  {bpu_row.item_label}"
            pu    = bpu_row.prix_unitaire
            total = bpu_row.total
            nd    = 3 if (bpu_row.unit or "").strip().lower() in ("m³", "m3") else 2

            vals = [
                desig,
                bpu_row.unit,
                round(bpu_row.qty_total, nd),
                _num_fmt(pu) if pu > 0 else "",
                _num_fmt(total) if pu > 0 else "—",
            ]
            aligns = ["left", "center", "right", "right", "right"]
            for col, (val, al) in enumerate(zip(vals, aligns), 1):
                c = ws.cell(row=row, column=col, value=val)
                c.fill  = _fill(_ART_BG)
                c.font  = _font(size=10,
                                color="FF0D47A1" if col == 1 else
                                      "FF1B5E20" if col == 5 and pu > 0 else
                                      "FF424242")
                c.alignment = _align(al)
                c.border = _border_thin()
            row += 1

        # Sous-total lot
        st = bpu.subtotal_lot(lot_id)
        for col in range(1, 6):
            c = ws.cell(row=row, column=col)
            c.fill   = _fill("FFF0F4FB")
            c.border = _border_thin()
        c3 = ws.cell(row=row, column=4, value=f"Sous-total {lot_id} :")
        c3.font = _font(bold=True, size=10, color="FF0D47A1")
        c3.alignment = _align("right")
        c4 = ws.cell(row=row, column=5, value=_num_fmt(st) + " DA")
        c4.font = _font(bold=True, size=10, color="FF0D47A1")
        c4.alignment = _align("right")
        row += 1

    # ── Séparateur ────────────────────────────────────────────────────────────
    for col in range(1, 6):
        c = ws.cell(row=row, column=col)
        c.fill = _fill(_SEP_BG)
    row += 1

    # ── Totaux finaux ────────────────────────────────────────────────────────
    tva_rate = getattr(bpu, "tva_rate", 19.0)
    totaux = [
        ("TOTAL HT :",      bpu.total_ht,     _HT_BG,  "FF0D47A1", 12),
        (f"TVA {tva_rate:.0f}% :", bpu.vat_amount if hasattr(bpu, "vat_amount")
                                   else bpu.tva_amount, _TVA_BG, "FF424242", 10),
        ("TOTAL TTC :",     bpu.total_ttc,    _TTC_BG, "FF1B5E20", 13),
    ]
    for label, val, bg, fg, sz in totaux:
        for col in range(1, 6):
            c = ws.cell(row=row, column=col)
            c.fill   = _fill(bg)
            c.border = _border_thin()
        ws.cell(row=row, column=4,
                value=label).font = _font(bold=True, size=sz, color=fg)
        ws.cell(row=row, column=4).alignment = _align("right")
        ws.cell(row=row, column=5,
                value=_num_fmt(val) + " DA").font = _font(bold=True, size=sz, color=fg)
        ws.cell(row=row, column=5).alignment = _align("right")
        ws.row_dimensions[row].height = 18 if sz < 12 else 22
        row += 1

    wb.save(path)


# ══════════════════════════════════════════════════════════════════════════════
#  Export — Attachement
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_etype(raw: str) -> str:
    raw = (raw or "").lower()
    if raw in ("polygon", "surface"):   return "polygon"
    if raw in ("perimeter", "line"):    return "perimeter"
    if raw in ("point", "compteur", "counter"): return "point"
    return "unknown"


def export_attachment_xlsx(panel: "ReportPanel", path: str) -> None:
    """
    Exporte l'onglet Attachement vers un fichier .xlsx.
    Fusions, couleurs par type, ligne Total si plusieurs occurrences.
    """
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    from core.precision import P as _P

    data = getattr(panel, "_data", None)
    if not data:
        raise ValueError("Aucune donnée de rapport disponible.")

    # Reconstruire l'index identique à _populate_attachment
    index      = {}
    lot_labels = {}
    item_labels = {}
    lots_seen   = []

    for pr in data.page_reports:
        for item in pr.items:
            for bi in item.get("bpu_items", []):
                key = (bi.lot_id, bi.item_id)
                index.setdefault(key, []).append(bi)
                lot_labels[bi.lot_id]  = bi.lot_label
                item_labels[key]       = (bi.item_label, bi.unit)
                if bi.lot_id not in lots_seen:
                    lots_seen.append(bi.lot_id)

    if not index:
        raise ValueError("Aucune affectation trouvée dans le rapport.")

    wb = Workbook()
    ws = wb.active
    ws.title = "Attachement"

    # ── Largeurs colonnes ────────────────────────────────────────────────────
    col_widths = [6, 32, 12, 18, 22, 40, 9, 12, 8]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── En-têtes ─────────────────────────────────────────────────────────────
    headers = ["N°", "Désignation", "Page", "Groupe",
               "Formule", "Calcul détaillé", "Nombre", "Quantité", "Unité"]
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.fill  = _fill(_HDR_BG_ATT)
        c.font  = _font(bold=True, color="FFFFFFFF", size=10)
        c.alignment = _align("center")
        c.border = _border_thin()
    ws.row_dimensions[1].height = 18
    ws.freeze_panes = "A2"

    row    = 2
    lineno = 0

    for lot_id in lots_seen:
        # ── En-tête lot ───────────────────────────────────────────────────────
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
        c = ws.cell(row=row, column=1,
                    value=f"  LOT  {lot_labels[lot_id]}")
        c.fill  = _fill(_LOT_BG_ATT)
        c.font  = _font(bold=True, size=11, color=_LOT_FG_ATT)
        c.alignment = _align("left")
        c.border = _border_thin()
        ws.row_dimensions[row].height = 20
        row += 1

        art_keys = sorted(
            [k for k in index if k[0] == lot_id], key=lambda k: k[1])

        for key in art_keys:
            item_id       = key[1]
            ilabel, iunit = item_labels[key]
            occurrences   = index[key]
            n_occ         = len(occurrences)
            qty_total     = _P.somme(*(bi.qty for bi in occurrences))
            lineno       += 1

            # Déterminer le type dominant pour la couleur
            dom_type = "unknown"
            for bi in occurrences:
                t = _normalize_etype(bi.group_type)
                if t != "unknown":
                    dom_type = t
                    break
            art_bg  = _TYPE_BG.get(dom_type, _TYPE_BG["unknown"])
            sub_bg  = "FFF4F8FF"

            first_row_art = row

            # ── Lignes occurrences ────────────────────────────────────────────
            for i, bi in enumerate(occurrences):
                is_first = (i == 0)
                bg = art_bg if is_first else sub_bg

                # Calcul de la colonne "Calcul détaillé" (version simplifiée)
                try:
                    v = bi.variables or {}
                    formula = bi.formula_expr or ""
                    # Tenter d'afficher la valeur numérique brute
                    calcul_str = f"{bi.qty:.2f}" if not bi.error else f"⚠ {bi.error}"
                except Exception:
                    calcul_str = ""

                coef = getattr(bi, "coefficient", 1.0) or 1.0
                nombre_t = "" if abs(coef - 1.0) < 1e-9 else (
                    f"{coef:.0f}" if coef == int(coef) else f"{coef:.3g}")

                nd_u = 3 if (iunit or "").strip().lower() in ("m³", "m3") else 2
                qty_t = f"⚠ {bi.error}" if bi.error else f"{bi.qty:.{nd_u}f}"

                row_vals = [
                    lineno if is_first else "",
                    f"{item_id}  {ilabel}" if is_first else "",
                    bi.page_name,
                    bi.group_name,
                    bi.formula_expr,
                    calcul_str,
                    nombre_t,
                    qty_t,
                    iunit if is_first else "",
                ]
                row_aligns = ["center", "left", "center", "left",
                              "left", "left", "center", "right", "center"]

                for col, (val, al) in enumerate(zip(row_vals, row_aligns), 1):
                    c = ws.cell(row=row, column=col, value=val)
                    c.fill      = _fill(bg)
                    c.alignment = _align(al, wrap=(col == 6))
                    c.border    = _border_thin()
                    if col in (1, 2) and is_first:
                        c.font = _font(bold=True, size=10)
                    elif col == 8:
                        c.font = _font(bold=True, size=10,
                                       color="FFC62828" if bi.error else "FF1565C0")
                    else:
                        c.font = _font(size=9,
                                       color="FF546E7A" if col in (3, 4) else "FF000000")
                row += 1

            # ── Ligne Total (si plusieurs occurrences) ────────────────────────
            if n_occ > 1:
                for col in range(1, 10):
                    c = ws.cell(row=row, column=col)
                    c.fill   = _fill(_TOT_BG_ATT)
                    c.border = _border_thin()
                ws.merge_cells(start_row=row, start_column=3,
                               end_row=row, end_column=7)
                c_lbl = ws.cell(row=row, column=3, value="  ▶  Total")
                c_lbl.font      = _font(bold=True, size=10, color="FFE65100")
                c_lbl.alignment = _align("left")
                nd_u = 3 if (iunit or "").strip().lower() in ("m³", "m3") else 2
                c_tot = ws.cell(row=row, column=8,
                                value=f"{qty_total:.{nd_u}f}")
                c_tot.font      = _font(bold=True, size=10, color="FFE65100")
                c_tot.alignment = _align("right")
                ws.cell(row=row, column=9,
                        value=iunit).font = _font(bold=True, size=10, color="FFE65100")
                row += 1

            # ── Fusion N° et Désignation sur toutes les lignes de cet article ─
            span = n_occ + (1 if n_occ > 1 else 0)
            if span > 1:
                ws.merge_cells(start_row=first_row_art, start_column=1,
                               end_row=first_row_art + span - 1, end_column=1)
                ws.merge_cells(start_row=first_row_art, start_column=2,
                               end_row=first_row_art + span - 1, end_column=2)

    wb.save(path)
