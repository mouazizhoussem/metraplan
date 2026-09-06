# core/formula_engine.py
"""
Moteur d'évaluation des formules de devis Metraplan.

Une formule est une expression textuelle simple qui combine des variables
extraites des mesures d'un groupe d'entités, par exemple :

    "surface_nette"
    "surface_nette × 2"
    "longueur_nette × hauteur"
    "surface_brute × 0.10"
    "nombre"

Variables disponibles selon le type d'entité :
  Surface  (polygon)  : surface_brute, surface_nette, perimetre_surface,
                        perimetre_ouvertures, deduction_ouvertures,
                        epaisseur, volume
  Périmètre           : longueur_brute, longueur_nette, surface_brute,
                        surface_nette, volume, hauteur, epaisseur,
                        perimetre_ouvertures, surface_deduction_ouvertures
  Compteur (point)    : nombre, longueur_unitaire, hauteur, epaisseur,
                        surface_compteur, volume_compteur

  Alias rétro-compatibles (anciens noms, toujours calculés) :
    volume_dalle, volume_mur, surface_brute_mur, surface_nette_mur, surface_laterale

Opérateurs supportés : + - × * / ( )
Le symbole × (U+00D7) est remplacé par * avant évaluation.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional, Tuple

from core.precision import P as _P

# Précisions de stockage par type de grandeur physique
_P_LEN = 2   # longueurs (ml)
_P_SRF = 2   # surfaces  (m²)
_P_VOL = 3   # volumes   (m³)


def _r(x: float, n: int = _P_SRF) -> float:
    """Arrondit x à n décimales (Decimal ROUND_HALF_UP)."""
    return _P.round(x, n)


def _rl(x: float) -> float:
    """Arrondit une longueur (m) à la précision affichée."""
    return _P.round(x, _P_LEN)


def _rs(x: float) -> float:
    """Arrondit une surface (m²) à la précision affichée."""
    return _P.round(x, _P_SRF)


def _rv(x: float) -> float:
    """Arrondit un volume (m³) à la précision affichée."""
    return _P.round(x, _P_VOL)


# ── Variables disponibles ─────────────────────────────────────────────────────

def _resolve_group_root(entity):
    """
    Remonte toujours au parent du groupe, quelle que soit l'entité sélectionnée.
    L'affectation BPU porte sur l'estimé TOTAL du groupe, pas sur un membre seul.

    Cas possibles :
      - entity est le parent  → retourner entity
      - entity est un enfant  → remonter via parent_entity
      - entity est seul (pas de groupe) → retourner entity
    """
    parent = getattr(entity, "parent_entity", None)
    if parent is not None:
        # C'est un enfant → on prend le parent
        return parent
    # C'est déjà le parent (ou une entité sans groupe)
    return entity


def build_variables(entity) -> Dict[str, float]:
    """
    Construit le dictionnaire de variables à partir d'un groupe d'entités.

    IMPORTANT : remonte TOUJOURS au parent du groupe avant de calculer,
    même si l'entité passée est un enfant. Cela garantit que les affectations
    BPU reflètent le total du groupe complet, pas seulement un membre isolé.
    """
    # Résoudre la racine du groupe
    entity   = _resolve_group_root(entity)

    etype    = getattr(entity, "entity_type", "")
    # Arrondir à 2 décimales pour éliminer les erreurs de représentation flottante
    # (ex: hauteur entrée comme "5" stockée en 5.001 via QDoubleSpinBox)
    height   = _P.round(float(getattr(entity, "height",    0.0) or 0.0), 2)
    thick    = _P.round(float(getattr(entity, "thickness", 0.0) or 0.0), 2)
    is_grp   = getattr(entity, "is_group_parent", False)
    children = getattr(entity, "child_entities",  []) or []
    # Toujours inclure parent + tous les enfants
    members  = [entity] + list(children) if children else [entity]

    vars_: Dict[str, float] = {
        # Génériques
        "hauteur":   height,
        "epaisseur": thick,
        # Surface (polygon)
        "surface_brute":                 0.0,
        "surface_nette":                 0.0,
        "perimetre_surface":             0.0,
        "perimetre_ouvertures":          0.0,
        "deduction_ouvertures":          0.0,
        "volume":                        0.0,
        # Périmètre (mur)
        "longueur_brute":                0.0,
        "longueur_nette":                0.0,
        "surface_deduction_ouvertures":  0.0,
        # Aliases rétro-compatibles (anciens noms)
        "surface_laterale":              0.0,
        "volume_mur":                    0.0,
        "surface_brute_mur":             0.0,
        "surface_nette_mur":             0.0,
        # Compteur (point)
        "nombre":                        0.0,
        "longueur_unitaire":             0.0,
    }

    # ── Surfaces ─────────────────────────────────────────────────────────────
    if etype in ("polygon", "surface"):
        brute = nette = perim_surf = perim_ouv = deduct = 0.0
        for m in members:
            try:
                b = m.calculate_area() if hasattr(m, "calculate_area") else 0.0
            except Exception:
                b = 0.0

            # Périmètre du contour
            try:
                perim_surf += (m.calculate_perimeter_length()
                               if hasattr(m, "calculate_perimeter_length") else 0.0)
            except Exception:
                pass

            ppm_m = float(getattr(m, "pixels_per_meter", 1.0) or 1.0)
            if ppm_m <= 0:
                ppm_m = 1.0

            live_openings   = getattr(m, "openings",               []) or []
            pending_openings = getattr(m, "_pending_openings_data", []) or []

            if live_openings:
                # ── Mode canvas : OpeningEntity avec QPointF ──────────────────
                op_area = 0.0
                for op in live_openings:
                    try:
                        pts    = getattr(op, "points", []) or []
                        ppm_op = float(getattr(op, "pixels_per_meter", ppm_m) or ppm_m)
                        if ppm_op <= 0:
                            ppm_op = ppm_m
                        np_ = len(pts)
                        if np_ >= 2:
                            perim_px = sum(
                                math.hypot(pts[(i+1)%np_].x() - pts[i].x(),
                                           pts[(i+1)%np_].y() - pts[i].y())
                                for i in range(np_)
                            )
                            perim_ouv = _P.add(perim_ouv, perim_px / ppm_op, 2)
                        if np_ >= 3:
                            # Aire de l'ouverture (Shoelace)
                            a = 0.0
                            for i in range(np_):
                                j = (i + 1) % np_
                                a += pts[i].x() * pts[j].y()
                                a -= pts[j].x() * pts[i].y()
                            op_area = _P.add(op_area, abs(a) / 2.0 / (ppm_op ** 2), _P_SRF)
                    except Exception:
                        pass
                n_net = _P.round(max(0.0, b - op_area), _P_SRF)

            elif pending_openings:
                # ── Mode rapport : dicts avec tuples (x, y) ──────────────────
                op_area = 0.0
                for op_d in pending_openings:
                    try:
                        pts_raw = op_d.get("points", []) or []
                        ppm_op  = float(op_d.get("pixels_per_meter", ppm_m) or ppm_m)
                        if ppm_op <= 0:
                            ppm_op = ppm_m
                        np_ = len(pts_raw)
                        if np_ >= 2:
                            perim_px = sum(
                                math.hypot(pts_raw[(i+1)%np_][0] - pts_raw[i][0],
                                           pts_raw[(i+1)%np_][1] - pts_raw[i][1])
                                for i in range(np_)
                            )
                            perim_ouv = _P.add(perim_ouv, perim_px / ppm_op, 2)
                        if np_ >= 3:
                            a = 0.0
                            for i in range(np_):
                                j = (i + 1) % np_
                                a += pts_raw[i][0] * pts_raw[j][1]
                                a -= pts_raw[j][0] * pts_raw[i][1]
                            op_area = _P.add(op_area, abs(a) / 2.0 / (ppm_op ** 2), _P_SRF)
                    except Exception:
                        pass
                n_net = _P.round(max(0.0, b - op_area), _P_SRF)

            else:
                # Aucune ouverture
                n_net = b

            brute  = _P.add(brute,  b,         _P_SRF)
            nette  = _P.add(nette,  n_net,      _P_SRF)
            deduct = _P.add(deduct, b - n_net,  _P_SRF)

        vol_dalle = _rv(_P.mul(nette, thick, _P_VOL)) if thick > 0 else 0.0
        vars_.update({
            "surface_brute":        _rs(brute),
            "surface_nette":        _rs(nette),
            "perimetre_surface":    _rl(perim_surf),
            "perimetre_ouvertures": _rl(perim_ouv),
            "deduction_ouvertures": _rs(deduct),
            "volume":               vol_dalle,   # surface_nette × epaisseur
            "volume_dalle":         vol_dalle,   # alias rétro-compatible
        })

    # ── Périmètres ───────────────────────────────────────────────────────────
    elif etype in ("perimeter", "line"):
        long_brute = long_nette = surf_lat = vol_mur = perim_ouv = 0.0
        surf_ded_ouv = 0.0   # Σ(largeur_ouv × hauteur_ouv)

        for m in members:
            ppm_m = float(getattr(m, "pixels_per_meter", 1.0) or 1.0)
            if ppm_m <= 0:
                ppm_m = 1.0

            # ── Longueur BRUTE : tous les segments (y compris ceux des ouvertures)
            # On préfère calculate_gross_perimeter_length_m() (méthode publique).
            # Fallback : calculer manuellement depuis self.points
            try:
                if hasattr(m, "calculate_gross_perimeter_length_m"):
                    lb = float(m.calculate_gross_perimeter_length_m())
                elif hasattr(m, "_calculate_gross_perimeter_length_m"):
                    lb = float(m._calculate_gross_perimeter_length_m())
                elif hasattr(m, "points") and len(getattr(m, "points", [])) >= 2:
                    import math as _math
                    pts = m.points
                    lb = sum(
                        _math.hypot(pts[i+1].x() - pts[i].x(),
                                    pts[i+1].y() - pts[i].y())
                        for i in range(len(pts) - 1)
                    ) / ppm_m
                else:
                    lb = 0.0
            except Exception:
                lb = 0.0

            # ── Longueur NETTE : longueur brute moins les largeurs d'ouvertures
            # calculate_perimeter_length() EXCLUT déjà les segments d'ouverture
            # → c'est bien la longueur nette liniaire.
            try:
                if hasattr(m, "calculate_perimeter_length"):
                    ln = float(m.calculate_perimeter_length())
                else:
                    ln = lb   # pas d'ouvertures connues → nette = brute
            except Exception:
                ln = lb

            long_brute += lb
            long_nette += ln

            # ── Surface latérale : utiliser calculate_surface_laterale() en priorité
            # Cette méthode fait : gross_length × wall_height − Σ(ouv_w × ouv_h)
            # ce qui est plus précis que net_length × wall_height
            # (net_length × wall_height surerait wall_height pour chaque ouverture,
            #  pas leur vraie hauteur individuelle)
            try:
                if hasattr(m, "calculate_surface_laterale") and height > 0:
                    sl = float(m.calculate_surface_laterale())
                else:
                    sl = ln * height if height > 0 else 0.0
            except Exception:
                sl = ln * height if height > 0 else 0.0
            surf_lat += sl

            # ── Volume mur : utiliser calculate_volume() en priorité
            try:
                if hasattr(m, "calculate_volume") and height > 0 and thick > 0:
                    vm = float(m.calculate_volume())
                else:
                    vm = sl * thick if thick > 0 else 0.0
            except Exception:
                vm = sl * thick if thick > 0 else 0.0
            vol_mur += vm

            # ── Ouvertures linéaires (fenêtres, portes)
            for op in getattr(m, "linear_openings", []) or []:
                try:
                    op_w = _P.round(float(op.get("length_m", 0.0) or 0.0), 2)
                    op_h = _P.round(float(op.get("height",   0.0) or 0.0), 2)
                    perim_ouv    = _P.add(perim_ouv,    _P.mul(2.0, _P.add(op_w, op_h)), 2)
                    if op_w > 0 and op_h > 0:
                        surf_ded_ouv = _P.add(surf_ded_ouv, _P.surface(op_w, op_h))
                except Exception:
                    pass

        surf_brute_mur = _rs(_P.surface(_rl(long_brute), height)) if height > 0 else 0.0
        surf_ded_ouv   = _rs(surf_ded_ouv)
        surf_nette_mur = _rs(max(0.0, _P.sub(surf_brute_mur, surf_ded_ouv)))

        vars_.update({
            "longueur_brute":               _rl(long_brute),
            "longueur_nette":               _rl(long_nette),
            "perimetre_ouvertures":         _rl(perim_ouv),
            "surface_deduction_ouvertures": surf_ded_ouv,
            # Noms unifiés (même sémantique que polygone, adaptés au périmètre)
            "surface_brute":                surf_brute_mur,   # longueur_brute × hauteur
            "surface_nette":                surf_nette_mur,   # surface_brute − Σouvertures
            "volume":                       _rv(vol_mur),     # surface_nette × epaisseur
            # Aliases rétro-compatibles (anciens noms)
            "surface_laterale":             _rs(surf_lat),
            "volume_mur":                   _rv(vol_mur),
            "surface_brute_mur":            surf_brute_mur,
            "surface_nette_mur":            surf_nette_mur,
        })

    # ── Compteurs ─────────────────────────────────────────────────────────────
    elif etype == "point":
        # ── Résoudre tous les membres du groupe ──────────────────────────────
        # child_entities est rempli par :
        #   • _rebuild_group_links()       → chargement de projet / génération rapport
        #   • _refresh_point_group_links() → ajout/suppression live (counter_tool.py)
        # Si child_entities est vide malgré un group_id valide (cas exceptionnel),
        # on tente un fallback via _entity_manager stocké sur l'entité.
        if not children:
            gid = getattr(entity, "group_id", None)
            em  = getattr(entity, "_entity_manager", None)
            if gid and em is not None:
                try:
                    peers = [p for p in em.get_points_by_group(gid)
                             if p is not entity]
                    if peers:
                        children = peers
                        members  = [entity] + children
                except Exception:
                    pass

        count     = len(members)
        unit_len  = _rl(float(getattr(entity, "length", 0.0) or 0.0))
        total_len = _rl(unit_len * count)
        surf_cpt  = _rs(total_len * height) if height > 0 else 0.0
        vol_cpt   = _rv(surf_cpt  * thick)  if (height > 0 and thick > 0) else 0.0
        vars_.update({
            "nombre":             float(count),
            "longueur_unitaire":  unit_len,
            "surface_compteur":   surf_cpt,
            "volume_compteur":    vol_cpt,
            # Alias : "volume" renvoie volume_compteur pour les compteurs,
            # cohérent avec polygon ("volume" = surface_nette × épaisseur)
            # et perimeter ("volume" = surface_nette × épaisseur).
            "volume":             vol_cpt,
        })

    return vars_


# ── Évaluateur de formule ─────────────────────────────────────────────────────

# Caractères autorisés dans une formule (sécurité)
_SAFE_PATTERN = re.compile(
    r'^[\w\s\.\+\-\*/\(\)×÷]+$'
)
_ALLOWED_NAMES = {
    "surface_brute", "surface_nette", "perimetre_surface",
    "perimetre_ouvertures", "deduction_ouvertures", "volume", "volume_dalle",
    "longueur_brute", "longueur_nette", "surface_laterale", "volume_mur",
    "surface_brute_mur", "surface_deduction_ouvertures", "surface_nette_mur",
    "hauteur", "epaisseur", "nombre", "longueur_unitaire",
    "surface_compteur", "volume_compteur",
}


def evaluate_formula(formula_expr: str,
                     variables: Dict[str, float],
                     coefficient: float = 1.0) -> Tuple[float, str]:
    """
    Évalue une formule et retourne (quantité, message_erreur).
    En cas de succès, message_erreur est "".
    En cas d'erreur, quantité est 0.0.

    Exemples :
        evaluate_formula("surface_nette", vars)         → (38.20, "")
        evaluate_formula("surface_nette × 2", vars)     → (76.40, "")
        evaluate_formula("longueur_nette × hauteur", v) → (35.00, "")
    """
    if not formula_expr or not formula_expr.strip():
        return 0.0, "Formule vide"

    # Normalisation : × → *,  ÷ → /
    expr = formula_expr.strip().replace("×", "*").replace("÷", "/")

    # Vérification des caractères autorisés
    if not _SAFE_PATTERN.match(expr):
        return 0.0, f"Formule invalide : caractères non autorisés dans « {formula_expr} »"

    # Injecter les variables dans l'espace de noms
    local_ns = {k: v for k, v in variables.items() if k in _ALLOWED_NAMES}
    # Interdire l'accès à builtins
    global_ns = {"__builtins__": {}}

    try:
        result = eval(expr, global_ns, local_ns)  # noqa: S307
        qty = _P.mul(float(result), coefficient, 3)   # 3 déc. pour couvrir m³
        return qty, ""
    except ZeroDivisionError:
        return 0.0, "Division par zéro"
    except NameError as e:
        return 0.0, f"Variable inconnue : {e}"
    except Exception as e:
        return 0.0, f"Erreur de calcul : {e}"


def _unit_decimals(unit: str) -> int:
    """Nombre de décimales d'affichage selon l'unité (identique à l'UI)."""
    u = (unit or "").strip().lower()
    if u in ("m³", "m3"):
        return 3
    return 2   # m², ml, m, U et tout le reste


def compute_assignment_item(entity, assigned_item) -> Tuple[float, float, str]:
    """
    Calcule la quantité et le total pour un AssignedItem lié à un groupe.

    La quantité est arrondie selon l'unité AVANT le calcul du total, ce qui
    garantit que : total affiché = qty affichée × PU (cohérence BTP).

    Retourne (qty, total, error_message).
    """
    from core.devis_manager import AssignedItem  # import local pour éviter cycles
    vars_ = build_variables(entity)
    qty, err = evaluate_formula(
        assigned_item.formula_expr,
        vars_,
        assigned_item.coefficient,
    )
    nd    = _unit_decimals(getattr(assigned_item, "unit", ""))
    qty   = _P.round(qty, nd)
    total = _P.mul(qty, assigned_item.prix_unitaire, 2)
    return qty, total, err


def compute_assignment_item_with_vars(
        entity, assigned_item) -> Tuple[float, float, str, Dict[str, float]]:
    """
    Identique à compute_assignment_item mais retourne aussi le dict de variables.

    Retourne (qty, total, error_message, variables_dict).
    """
    vars_ = build_variables(entity)
    qty, err = evaluate_formula(
        assigned_item.formula_expr,
        vars_,
        assigned_item.coefficient,
    )
    nd    = _unit_decimals(getattr(assigned_item, "unit", ""))
    qty   = _P.round(qty, nd)
    total = _P.mul(qty, assigned_item.prix_unitaire, 2)
    return qty, total, err, vars_


def preview_formula(formula_expr: str, entity) -> str:
    """
    Retourne une chaîne lisible montrant le calcul en détail.
    Utilisé dans l'interface pour l'aperçu en temps réel.

    Ex: "surface_nette × 2  →  38.20 × 2 = 76.40 m²"
    """
    vars_ = build_variables(entity)
    expr_norm = formula_expr.strip().replace("×", "*").replace("÷", "/")

    # Remplacer les noms de variables par leurs valeurs pour l'affichage
    display = formula_expr.strip()
    for name in sorted(_ALLOWED_NAMES, key=len, reverse=True):
        if name in vars_:
            display = display.replace(name, f"{vars_[name]:.2f}")

    qty, err = evaluate_formula(formula_expr, vars_)
    if err:
        return f"{formula_expr}  →  ⚠ {err}"
    return f"{display} = {qty:.2f}"


# ── Helpers : liste des variables pour affichage dans l'UI ───────────────────

VARIABLE_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "surface_brute": {
        "label": "Surface brute",
        "unit":  "m²",
        "types": "polygon perimeter",
        "desc":  "Polygone : aire brute  |  Périmètre : longueur_brute × hauteur",
    },
    "surface_nette": {
        "label": "Surface nette",
        "unit":  "m²",
        "types": "polygon perimeter",
        "desc":  "Polygone : aire − ouvertures  |  Périmètre : surface_brute − Σouvertures",
    },
    "perimetre_surface": {
        "label": "Périmètre du contour",
        "unit":  "ml",
        "types": "polygon",
        "desc":  "Longueur du périmètre de la surface",
    },
    "perimetre_ouvertures": {
        "label": "Périmètre des ouvertures",
        "unit":  "ml",
        "types": "polygon perimeter",
        "desc":  "Σ 2×(largeur + hauteur) de chaque ouverture — utile pour jambages, linteaux",
    },
    "deduction_ouvertures": {
        "label": "Déduction ouvertures",
        "unit":  "m²",
        "types": "polygon",
        "desc":  "Surface totale déduite (ouvertures)",
    },
    "volume": {
        "label": "Volume",
        "unit":  "m³",
        "types": "polygon perimeter point",
        "desc":  "surface_nette × épaisseur (surface/périmètre) — a × b × h × nombre (compteur)",
    },
    "longueur_brute": {
        "label": "Longueur brute",
        "unit":  "ml",
        "types": "perimeter",
        "desc":  "Longueur totale sans déduction",
    },
    "longueur_nette": {
        "label": "Longueur nette",
        "unit":  "ml",
        "types": "perimeter",
        "desc":  "Longueur après déduction des ouvertures linéaires",
    },
    "surface_deduction_ouvertures": {
        "label": "Surface des ouvertures (déduction)",
        "unit":  "m²",
        "types": "perimeter",
        "desc":  "Σ (largeur × hauteur) de chaque ouverture tracée sur le plan",
    },
    "hauteur": {
        "label": "Hauteur  h",
        "unit":  "m",
        "types": "perimeter, point",
        "desc":  "Hauteur h — hauteur du mur (périmètre) ou hauteur de l'élément (compteur)",
    },
    "epaisseur": {
        "label": "Épaisseur  e",
        "unit":  "m",
        "types": "polygon, perimeter, point",
        "desc":  "Épaisseur e (surface/périmètre) — Côté b de la section (compteur)",
    },
    "nombre": {
        "label": "Nombre",
        "unit":  "U",
        "types": "point",
        "desc":  "Nombre d'éléments dans le groupe",
    },
    "longueur_unitaire": {
        "label": "Côté  a (section)",
        "unit":  "ml",
        "types": "point",
        "desc":  "Premier côté de la section transversale (a) — volume unitaire : a × b × h",
    },
    "surface_compteur": {
        "label": "Surface totale",
        "unit":  "m²",
        "types": "point",
        "desc":  "a × h × nombre  (si hauteur h > 0)",
    },
    "volume_compteur": {
        "label": "Volume total",
        "unit":  "m³",
        "types": "point",
        "desc":  "a × b × h × nombre  (si h > 0 et b > 0)",
    },
}


def get_available_variables(entity_type: str) -> List[Dict[str, str]]:
    """
    Retourne la liste des variables disponibles pour un type d'entité donné.
    Utilisé pour peupler la liste dans l'interface de construction de formule.
    """
    result = []
    for var_name, info in VARIABLE_DESCRIPTIONS.items():
        if entity_type in info["types"]:
            result.append({
                "name":  var_name,
                "label": info["label"],
                "unit":  info["unit"],
                "desc":  info["desc"],
            })
    return result
