# core/devis_manager.py
"""
Gestionnaire de la bibliothèque de devis Metraplan.

Responsabilités :
  - Charger le modèle de devis depuis data/devis_model.json
  - Gérer les items/lots personnalisés (CRUD)
  - Exposer les lots et items sous forme d'objets simples
  - Charger/sauvegarder les affectations (group_assignments) du projet
  - Émettre devis_structure_changed quand la bibliothèque est modifiée
"""
from __future__ import annotations
from core.app_logger import get_logger
_log = get_logger(__name__)

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal


# ── Chemin par défaut de la bibliothèque ──────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_LIBRARY = os.path.join(_HERE, "..", "data", "devis_model.json")


# ── Modèles de données ────────────────────────────────────────────────────────

@dataclass
class DevisItem:
    """Un poste du devis (ligne BPU)."""
    id: str                        # ex: "04.02"
    label: str                     # ex: "Maçonnerie en brique 20cm"
    unit: str                      # "m²" | "m³" | "ml" | "U"
    default_formula: str = ""      # ex: "surface_nette"
    is_custom: bool = False        # True = ajouté par l'utilisateur


@dataclass
class DevisLot:
    """Un lot de travaux (regroupement d'items)."""
    id: str                        # ex: "04"
    label: str                     # ex: "Maçonnerie"
    items: List[DevisItem] = field(default_factory=list)
    is_custom: bool = False        # True = ajouté par l'utilisateur

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":        self.id,
            "label":     self.label,
            "is_custom": self.is_custom,
            "items": [
                {
                    "id":              it.id,
                    "label":           it.label,
                    "unit":            it.unit,
                    "default_formula": it.default_formula,
                    "is_custom":       it.is_custom,
                }
                for it in self.items
            ],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DevisLot":
        lot = cls(
            id=d["id"], label=d["label"],
            is_custom=d.get("is_custom", False)
        )
        for item_data in d.get("items", []):
            lot.items.append(DevisItem(
                id              = item_data["id"],
                label           = item_data["label"],
                unit            = item_data.get("unit", ""),
                default_formula = item_data.get("default_formula", ""),
                is_custom       = item_data.get("is_custom", False),
            ))
        return lot


@dataclass
class AssignedItem:
    """Affectation d'un item de devis à un groupe de mesure."""
    lot_id: str
    item_id: str
    formula_expr: str
    coefficient: float = 1.0
    prix_unitaire: float = 0.0
    qty_computed: float = 0.0
    total_computed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lot_id":        self.lot_id,
            "item_id":       self.item_id,
            "formula_expr":  self.formula_expr,
            "coefficient":   self.coefficient,
            "prix_unitaire": self.prix_unitaire,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AssignedItem":
        return cls(
            lot_id        = d.get("lot_id", ""),
            item_id       = d.get("item_id", ""),
            formula_expr  = d.get("formula_expr", ""),
            coefficient   = float(d.get("coefficient", 1.0)),
            prix_unitaire = float(d.get("prix_unitaire", 0.0)),
        )


@dataclass
class GroupAssignment:
    """Toutes les affectations pour un groupe de mesure."""
    group_id: str
    group_name: str
    group_type: str
    page_name: str
    items: List[AssignedItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id":   self.group_id,
            "group_name": self.group_name,
            "group_type": self.group_type,
            "page_name":  self.page_name,
            "items":      [it.to_dict() for it in self.items],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GroupAssignment":
        ga = cls(
            group_id   = d.get("group_id", ""),
            group_name = d.get("group_name", ""),
            group_type = d.get("group_type", ""),
            page_name  = d.get("page_name", ""),
        )
        ga.items = [AssignedItem.from_dict(i) for i in d.get("items", [])]
        return ga


# ── Gestionnaire principal ────────────────────────────────────────────────────

class DevisManager(QObject):
    """
    Singleton gestionnaire de la bibliothèque de devis.
    Hérite de QObject pour exposer le signal devis_structure_changed.
    Accès global via DevisManager.instance().
    """

    # Émis quand la structure lots/items est modifiée (CRUD, import…)
    devis_structure_changed = pyqtSignal()

    _instance: Optional["DevisManager"] = None

    def __init__(self, library_path: str = _DEFAULT_LIBRARY):
        super().__init__()
        self._library_path = library_path
        self._lots: List[DevisLot] = []
        self._assignments: Dict[str, GroupAssignment] = {}
        self._custom_items: List[Dict[str, Any]] = []   # rétrocompat
        self._load_library()

    @classmethod
    def instance(cls) -> "DevisManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    # ── Chargement / sauvegarde de la bibliothèque ────────────────────────────

    def _load_library(self):
        """Charge data/devis_model.json."""
        path = os.path.normpath(self._library_path)
        if not os.path.exists(path):
            _log.warning(f"[DevisManager] Bibliothèque introuvable : {path}")
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._lots = []
            for lot_data in data.get("lots", []):
                self._lots.append(DevisLot.from_dict(lot_data))
            _log.info(f"[DevisManager] {len(self._lots)} lots chargés "
                  f"({sum(len(l.items) for l in self._lots)} items)")
        except Exception as exc:
            _log.warning(f"[DevisManager] Erreur chargement bibliothèque : {exc}")

    def reload_library(self):
        """Recharge la bibliothèque depuis le fichier JSON."""
        self._load_library()
        self._apply_custom_items()
        self.devis_structure_changed.emit()

    def save_library(self, path: str = "") -> bool:
        """
        Sauvegarde la bibliothèque complète (lots + items) dans un fichier JSON.
        Si path est vide, écrase le fichier par défaut.
        """
        target = os.path.normpath(path or self._library_path)
        try:
            data = {
                "version":     "1.0",
                "title":       "Bibliothèque de devis Metraplan",
                "description": "Modèle personnalisé",
                "lots":        [lot.to_dict() for lot in self._lots],
            }
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            _log.info(f"[DevisManager] Bibliothèque sauvegardée : {target}")
            return True
        except Exception as exc:
            _log.warning(f"[DevisManager] Erreur sauvegarde : {exc}")
            return False

    def load_library_from_file(self, path: str) -> bool:
        """Charge une bibliothèque depuis un fichier .devis ou .json."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._lots = [DevisLot.from_dict(d) for d in data.get("lots", [])]
            self.devis_structure_changed.emit()
            return True
        except Exception as exc:
            _log.warning(f"[DevisManager] Erreur chargement fichier : {exc}")
            return False

    def import_from_excel(self, path: str) -> tuple:
        """
        Importe des lots/items depuis un fichier Excel (.xlsx / .xlsm).

        Détection intelligente et universelle :
        ─ Auto-détection de la ligne d'en-tête (ignorée).
        ─ Auto-détection des colonnes N°, Désignation, Unité, P.U.
        ─ Reconnaissance des lots par :
            • numéros entiers   : 1, 01, 17
            • préfixe LOT       : "LOT 01", "Lot I"
            • chiffres romains  : I, II, III, IV … (jusqu'à XX)
            • lettre unique     : A, B, C …
        ─ Reconnaissance des items par :
            • séparateur point  : 01.01, 17.03
            • séparateur tiret  : 01-01  (normalisé en 01.01)
            • séparateur slash  : 01/01  (normalisé en 01.01)
            • présence d'unité  quand le N° n'est pas identifiable seul
        ─ Gestion des cellules fusionnées (la valeur est reportée).
        ─ Feuilles multiples  : première feuille non vide utilisée.
        ─ Lignes totalement vides ignorées.
        ─ Prix unitaires (P.U.) récupérés s'ils existent dans le fichier.

        Retourne (lots_importés: List[DevisLot], message: str).
        """
        import re

        ext = os.path.splitext(path)[1].lower()

        # ── Ouvrir le classeur selon l'extension ──────────────────────────────
        all_rows: List[tuple] = []
        # row_colors[i] = True si la ligne i a un fond coloré (= probable LOT)
        row_colors: List[bool] = []

        if ext in (".xlsx", ".xlsm", ".xlam", ".xltx", ".xltm"):
            # Format moderne — openpyxl
            try:
                import openpyxl
            except ImportError:
                return [], "openpyxl non installé. Exécutez : python -m pip install openpyxl"
            try:
                # Charger SANS data_only=True pour accéder aux styles de cellule
                wb_styled = openpyxl.load_workbook(path, data_only=False)
                wb        = openpyxl.load_workbook(path, data_only=True)
            except Exception as exc:
                return [], f"Impossible d'ouvrir le fichier : {exc}"

            ws = None
            ws_styled = None
            for sheet_name in wb.sheetnames:
                candidate = wb[sheet_name]
                if candidate.max_row and candidate.max_row > 1:
                    ws        = candidate
                    ws_styled = wb_styled[sheet_name]
                    break
            if ws is None:
                return [], "Aucune feuille non vide trouvée dans le classeur."

            # Construire la liste des valeurs ET des couleurs de fond
            def _cell_has_color(cell) -> bool:
                """True si la cellule a un fond non blanc / non transparent."""
                try:
                    fill = cell.fill
                    if fill is None or fill.fill_type in (None, "none"):
                        return False
                    fg = fill.fgColor
                    if fg is None:
                        return False
                    # Type "rgb" : couleur explicite
                    if fg.type == "rgb":
                        rgb = fg.rgb or "00000000"
                        # Blanc = FFFFFFFF ou 00000000 (transparent)
                        return rgb not in ("FFFFFFFF", "00000000", "00FFFFFF",
                                           "FFFFFF", "000000")
                    # Type "indexed" : index 64 = pas de couleur
                    if fg.type == "indexed":
                        return fg.indexed not in (64, 0)
                    # Type "theme" : presque toujours coloré
                    if fg.type == "theme":
                        return True
                except Exception:
                    pass
                return False

            rows_styled = list(ws_styled.iter_rows())
            for row_cells in rows_styled:
                vals = tuple(
                    cell.value for cell in row_cells)
                all_rows.append(vals)
                # La ligne est colorée si AU MOINS UNE des 4 premières
                # cellules a un fond non blanc
                colored = any(_cell_has_color(c)
                              for c in row_cells[:4] if c is not None)
                row_colors.append(colored)

        elif ext in (".xls",):
            # Ancien format Excel 97-2003 — xlrd
            try:
                import xlrd
            except ImportError:
                return [], ("xlrd non installé (nécessaire pour les fichiers .xls).\n"
                            "Exécutez : python -m pip install xlrd")
            try:
                wb_xls = xlrd.open_workbook(path)
            except Exception as exc:
                return [], f"Impossible d'ouvrir le fichier .xls : {exc}"

            # Choisir la première feuille non vide
            ws_xls = None
            for i in range(wb_xls.nsheets):
                s = wb_xls.sheet_by_index(i)
                if s.nrows > 1:
                    ws_xls = s
                    break
            if ws_xls is None:
                return [], "Aucune feuille non vide trouvée dans le classeur .xls."

            # Convertir en tuples comme openpyxl
            for r in range(ws_xls.nrows):
                row_vals = []
                for c in range(ws_xls.ncols):
                    cell = ws_xls.cell(r, c)
                    # xlrd type : 0=empty,1=text,2=number,3=date,4=bool,5=error
                    if cell.ctype == 0:
                        row_vals.append(None)
                    elif cell.ctype == 2:
                        # Nombre : enlever le .0 si entier
                        v = cell.value
                        row_vals.append(str(int(v)) if v == int(v) else str(v))
                    else:
                        row_vals.append(str(cell.value) if cell.value != "" else None)
                all_rows.append(tuple(row_vals))

        else:
            return [], (f"Format de fichier « {ext} » non supporté.\n"
                        "Formats acceptés : .xlsx, .xls, .xlsm")

        # ── Helpers ───────────────────────────────────────────────────────────

        _ROMAN = {
            "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
            "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
            "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
            "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
        }
        _UNITS_KNOWN = {
            "m²", "m2", "m³", "m3", "ml", "ml.", "m", "u", "u.", "ens",
            "ens.", "forfait", "fft", "kg", "t", "l", "h", "j",
        }

        def _is_unit(val: str) -> bool:
            return val.lower().strip().rstrip(".") in {
                u.lower().rstrip(".") for u in _UNITS_KNOWN}

        def _clean_num(raw: str) -> str:
            """Normalise le séparateur d'un ID item (- ou / → .)."""
            return re.sub(r"[-/]", ".", raw.strip())

        def _is_lot_id(raw: str) -> Optional[str]:
            """
            Reconnaît un identifiant de LOT et retourne l'ID normalisé,
            ou None si ce n'est pas un lot.
            Formats : 1, 01, 17, LOT 01, Lot I, I, II, A, B …
            """
            s = raw.strip()
            # Préfixe "LOT " ou "Lot "
            m = re.match(r"^[Ll][Oo][Tt]\s*(\S+)$", s)
            if m:
                s = m.group(1)
            # Chiffre entier pur (sans point, sans lettre mélangée)
            if re.match(r"^\d+$", s):
                return str(int(s)).zfill(2)
            # Chiffre romain
            if s.upper() in _ROMAN:
                return str(_ROMAN[s.upper()]).zfill(2)
            # Lettre unique A-Z (sans suffixe / ou ) → seulement si pas sous-item)
            if re.match(r"^[A-Z]$", s.upper()):
                return s.upper()
            return None

        def _is_item_id(raw: str) -> Optional[str]:
            """
            Reconnaît un identifiant d'ITEM (contient un séparateur).
            Retourne l'ID normalisé, ou None.
            """
            s = _clean_num(raw.strip())
            # xx.yy ou xx.yy.zz (numérique)
            if re.match(r"^\d+\.\d+(\.\d+)?$", s):
                return s
            # Lettre.numéro  : A.01, B.3
            if re.match(r"^[A-Z]\.\d+$", s.upper()):
                return s.upper()
            return None

        def _is_subitem_letter(raw: str) -> Optional[str]:
            """
            Reconnaît un sous-article alphabétique lié à l'article courant.
            Formats acceptés : a/, b/, a), b), a., b., a-, b-  ou lettre seule.
            Retourne la lettre minuscule normalisée, ou None.
            """
            s = raw.strip()
            # Lettre suivie d'un séparateur : a/, a), a., a-
            m = re.match(r"^([a-zA-Z])[/\)\.\-]$", s)
            if m:
                return m.group(1).lower()
            return None

        def _is_header_row(cells: list) -> bool:
            """True si la ligne ressemble à un en-tête (N°, Désignation…)."""
            keywords = {"n°", "num", "numéro", "numero", "désignation",
                        "designation", "intitulé", "libellé", "description",
                        "unité", "unite", "u.", "p.u", "prix", "montant"}
            for c in cells[:5]:
                if c and str(c).strip().lower().rstrip(".") in keywords:
                    return True
            return False

        # ── Détecter les colonnes ─────────────────────────────────────────────
        # On cherche l'en-tête pour savoir dans quelle colonne est quoi.
        col_num   = 0   # indice colonne N°
        col_label = 1   # indice colonne Désignation
        col_unit  = 2   # indice colonne Unité
        col_pu    = -1  # indice colonne P.U. (-1 = absent)

        # Chercher la ligne d'en-tête dans les 10 premières lignes
        header_row_idx = -1
        for i, row in enumerate(all_rows[:10]):
            if _is_header_row(list(row)):
                header_row_idx = i
                for j, cell in enumerate(row):
                    if cell is None:
                        continue
                    c = str(cell).strip().lower()
                    if any(k in c for k in ("n°", "num", "art")):
                        col_num = j
                    elif any(k in c for k in ("désig", "desig", "intitulé",
                                              "libel", "descrip")):
                        col_label = j
                    elif any(k in c for k in ("unité", "unite", "u.")):
                        col_unit = j
                    elif any(k in c for k in ("p.u", "prix unit", "pu ")):
                        col_pu = j
                break

        data_rows = all_rows[header_row_idx + 1:] if header_row_idx >= 0 \
                    else all_rows

        # ── Gérer les cellules fusionnées (résoudre les valeurs manquantes) ──
        # openpyxl ne remplit pas les cellules fusionnées automatiquement,
        # on garde la valeur de la cellule précédente pour la colonne N°.
        last_num_val = None

        # ── Fonction de parsing d'une ligne ──────────────────────────────────

        def _parse_row(row):
            def _get(col: int) -> str:
                if col < 0 or col >= len(row) or row[col] is None:
                    return ""
                return str(row[col]).strip()
            return _get(col_num), _get(col_label), _get(col_unit), \
                   (_get(col_pu) if col_pu >= 0 else "")

        def _skip_line(label: str) -> bool:
            ll = label.lower()
            return any(k in ll for k in (
                "total", "sous-total", "montant", "arrêté", "arrété",
                "t.t.c", "h.t.", "tva", "report", "arrêt",
            ))

        def _parse_pu(pu_raw: str) -> float:
            try:
                return float(
                    pu_raw.replace(" ", "").replace("\xa0", "")
                          .replace(",", ".").replace("DA", "").replace("€", "")
                )
            except ValueError:
                return 0.0

        # ── Passe 0 : détection par couleur de fond (priorité maximale) ─────────
        # Dans les devis algériens, les lots ont toujours un fond coloré (gris,
        # bleu, vert…). C'est le signal le plus fiable et indépendant du format.
        lots: List[DevisLot] = []
        current_lot: Optional[DevisLot] = None
        current_item_id: Optional[str] = None
        n_items      = 0
        lot_counter  = 0
        mode_msg     = ""

        color_based = False
        if row_colors and any(row_colors):
            # Au moins une ligne colorée → on tente la détection couleur
            last_num_val   = None
            header_skipped = False

            for idx, row in enumerate(data_rows):
                if not row:
                    continue
                # Décalage : data_rows commence après header_row_idx
                src_idx = (header_row_idx + 1 + idx) \
                          if header_row_idx >= 0 else idx
                is_colored = row_colors[src_idx] if src_idx < len(row_colors) \
                             else False

                num_raw, label_raw, unit_raw, pu_raw = _parse_row(row)

                sub_letter = _is_subitem_letter(num_raw) if num_raw else None
                if not sub_letter:
                    if not num_raw and last_num_val:
                        num_raw = last_num_val
                    elif num_raw:
                        last_num_val = num_raw

                if not label_raw or _skip_line(label_raw):
                    continue

                prix_u = _parse_pu(pu_raw)

                if is_colored:
                    # ── LIGNE COLORÉE → LOT ──────────────────────────────────
                    lot_counter += 1
                    raw_id   = num_raw or str(lot_counter)
                    clean_id = re.sub(r"[^\d]", "", raw_id) or str(lot_counter)
                    lot_id_s = clean_id.zfill(2)
                    current_lot     = DevisLot(id=lot_id_s, label=label_raw,
                                               is_custom=True)
                    current_item_id = None
                    lots.append(current_lot)

                elif sub_letter and current_item_id and current_lot is not None:
                    # ── SOUS-ARTICLE ALPHABÉTIQUE ────────────────────────────
                    sub_id = f"{current_item_id}.{sub_letter}"
                    item = DevisItem(id=sub_id,
                                     label=f"  {sub_letter.upper()}/ {label_raw}",
                                     unit=unit_raw or "U",
                                     default_formula="", is_custom=True)
                    if prix_u > 0:
                        item.__dict__["_imported_pu"] = prix_u
                    if current_lot:
                        current_lot.items.append(item)
                    n_items += 1

                elif current_lot is not None:
                    # ── ITEM normal (ligne non colorée) ──────────────────────
                    item_id = _is_item_id(num_raw or "") or None
                    if item_id is None:
                        n_auto  = len(current_lot.items) + 1
                        item_id = f"{current_lot.id}.{n_auto:02d}"
                    item = DevisItem(id=item_id, label=label_raw,
                                     unit=unit_raw or "U",
                                     default_formula="", is_custom=True)
                    if prix_u > 0:
                        item.__dict__["_imported_pu"] = prix_u
                    current_lot.items.append(item)
                    current_item_id = item_id
                    n_items += 1

            if lots:
                color_based = True
                mode_msg = " (détection par couleur de fond)"

        # ── Passe 1 : détection stricte par patterns de N° ──────────────────────
        if not color_based:
            lots            = []
            current_lot     = None
            current_item_id = None
            n_items         = 0
            last_num_val    = None

            for row in data_rows:
                if not row:
                    continue
                num_raw, label_raw, unit_raw, pu_raw = _parse_row(row)

                sub_letter = _is_subitem_letter(num_raw) if num_raw else None
                if not sub_letter:
                    if not num_raw and last_num_val:
                        num_raw = last_num_val
                    elif num_raw:
                        last_num_val = num_raw

                if not label_raw or _skip_line(label_raw):
                    continue

                prix_u  = _parse_pu(pu_raw)

                if sub_letter is not None and current_item_id and current_lot is not None:
                    sub_id = f"{current_item_id}.{sub_letter}"
                    item = DevisItem(id=sub_id,
                                     label=f"  {sub_letter.upper()}/ {label_raw}",
                                     unit=unit_raw or "U",
                                     default_formula="", is_custom=True)
                    if prix_u > 0:
                        item.__dict__["_imported_pu"] = prix_u
                    current_lot.items.append(item)
                    n_items += 1
                    continue

                lot_id  = _is_lot_id(num_raw)  if num_raw else None
                item_id = _is_item_id(num_raw) if num_raw else None

                if lot_id is None and item_id is None \
                        and _is_unit(unit_raw) and current_lot is not None:
                    n_auto  = len(current_lot.items) + 1
                    item_id = f"{current_lot.id}.{n_auto:02d}"

                if lot_id is not None:
                    current_lot     = DevisLot(id=lot_id, label=label_raw,
                                               is_custom=True)
                    current_item_id = None
                    lots.append(current_lot)
                elif item_id is not None and current_lot is not None:
                    item = DevisItem(id=item_id, label=label_raw,
                                     unit=unit_raw or "U",
                                     default_formula="", is_custom=True)
                    if prix_u > 0:
                        item.__dict__["_imported_pu"] = prix_u
                    current_lot.items.append(item)
                    current_item_id = item_id
                    n_items += 1

            if lots:
                mode_msg = ""  # détection stricte réussie

        # ── Passe 2 : mode universel (si passe 0 et passe 1 = 0 résultats) ────
        if not lots:
            lots            = []
            current_lot     = None
            current_item_id = None
            n_items         = 0
            lot_counter     = 0
            last_num_val    = None

            for row in data_rows:
                if not row:
                    continue
                num_raw, label_raw, unit_raw, pu_raw = _parse_row(row)

                sub_letter = _is_subitem_letter(num_raw) if num_raw else None
                if not sub_letter:
                    if not num_raw and last_num_val:
                        num_raw = last_num_val
                    elif num_raw:
                        last_num_val = num_raw

                if not label_raw or _skip_line(label_raw):
                    continue

                prix_u   = _parse_pu(pu_raw)
                has_unit = bool(unit_raw and unit_raw.strip())

                if sub_letter and current_item_id and current_lot is not None:
                    sub_id = f"{current_item_id}.{sub_letter}"
                    item = DevisItem(id=sub_id,
                                     label=f"  {sub_letter.upper()}/ {label_raw}",
                                     unit=unit_raw or "U",
                                     default_formula="", is_custom=True)
                    if prix_u > 0:
                        item.__dict__["_imported_pu"] = prix_u
                    current_lot.items.append(item)
                    n_items += 1
                    continue

                if not has_unit:
                    lot_counter += 1
                    raw_id   = num_raw or str(lot_counter)
                    clean_id = re.sub(r"[^\d]", "", raw_id) or str(lot_counter)
                    lot_id_s = clean_id.zfill(2)
                    current_lot     = DevisLot(id=lot_id_s, label=label_raw,
                                               is_custom=True)
                    current_item_id = None
                    lots.append(current_lot)
                else:
                    if current_lot is None:
                        lot_counter += 1
                        current_lot = DevisLot(id=str(lot_counter).zfill(2),
                                               label="Lot général",
                                               is_custom=True)
                        lots.append(current_lot)
                    n_auto  = len(current_lot.items) + 1
                    item_id = _is_item_id(num_raw or "") \
                              or f"{current_lot.id}.{n_auto:02d}"
                    item = DevisItem(id=item_id, label=label_raw,
                                     unit=unit_raw,
                                     default_formula="", is_custom=True)
                    if prix_u > 0:
                        item.__dict__["_imported_pu"] = prix_u
                    current_lot.items.append(item)
                    current_item_id = item_id
                    n_items += 1

            if lots:
                mode_msg = " (mode universel — détection par unité)"

        # ── Diagnostic si toujours vide ───────────────────────────────────────
        if not lots:
            preview = []
            for row in data_rows[:8]:
                if row and any(c is not None for c in row):
                    preview.append(" | ".join(
                        str(c) if c is not None else "" for c in row[:5]))
            preview_str = "\n".join(preview) or "(feuille vide)"
            msg = (
                f"Import impossible : aucun lot ni article détecté.\n\n"
                f"Aperçu des premières lignes du fichier :\n{preview_str}\n\n"
                f"Vérifiez que le fichier contient bien des colonnes "
                f"N° | Désignation | Unité."
            )
            return [], msg

        msg = (f"{len(lots)} lot(s) et {n_items} article(s) importés "
               f"depuis « {os.path.basename(path)} »{mode_msg}.")
        return lots, msg

    def apply_imported_lots(self, lots: List[DevisLot],
                            merge: bool = True):
        """
        Applique les lots importés à la bibliothèque.
        Si merge=True, fusionne avec l'existant.
        Si merge=False, remplace tout.
        """
        if not merge:
            self._lots = lots
        else:
            for new_lot in lots:
                existing = self.get_lot(new_lot.id)
                if existing:
                    # Ajouter seulement les nouveaux items
                    existing_ids = {it.id for it in existing.items}
                    for it in new_lot.items:
                        if it.id not in existing_ids:
                            existing.items.append(it)
                else:
                    self._lots.append(new_lot)
        self.devis_structure_changed.emit()

    # ── CRUD Lots ─────────────────────────────────────────────────────────────

    @property
    def lots(self) -> List[DevisLot]:
        return self._lots

    def get_lot(self, lot_id: str) -> Optional[DevisLot]:
        for lot in self._lots:
            if lot.id == lot_id:
                return lot
        return None

    def add_lot(self, lot_id: str = "", label: str = "Nouveau lot",
                insert_after: str = "") -> DevisLot:
        """
        Ajoute un lot personnalisé.
        insert_after : id d'un lot existant après lequel insérer le nouveau.
                       Si vide ou introuvable, le lot est ajouté en fin.
        """
        if not lot_id:
            existing = {l.id for l in self._lots}
            n = 99
            while str(n).zfill(2) in existing:
                n += 1
            lot_id = str(n).zfill(2)
        lot = DevisLot(id=lot_id, label=label, is_custom=True)
        if insert_after:
            ids = [l.id for l in self._lots]
            if insert_after in ids:
                self._lots.insert(ids.index(insert_after) + 1, lot)
            else:
                self._lots.append(lot)
        else:
            self._lots.append(lot)
        self.devis_structure_changed.emit()
        return lot

    def rename_lot(self, lot_id: str, new_label: str) -> bool:
        lot = self.get_lot(lot_id)
        if not lot:
            return False
        lot.label = new_label
        self.devis_structure_changed.emit()
        return True

    def remove_lot(self, lot_id: str) -> bool:
        """Supprime un lot (custom ou standard)."""
        before = len(self._lots)
        self._lots = [l for l in self._lots if l.id != lot_id]
        if len(self._lots) < before:
            self.devis_structure_changed.emit()
            return True
        return False

    def move_lot(self, lot_id: str, direction: int):
        """Déplace un lot vers le haut (-1) ou le bas (+1)."""
        idx = next((i for i, l in enumerate(self._lots) if l.id == lot_id), -1)
        if idx < 0:
            return
        new_idx = idx + direction
        if 0 <= new_idx < len(self._lots):
            self._lots.insert(new_idx, self._lots.pop(idx))
            self.devis_structure_changed.emit()

    def reorder_lot(self, lot_id: str, dest_index: int):
        """Déplace un lot à la position dest_index (drag & drop)."""
        idx = next((i for i, l in enumerate(self._lots) if l.id == lot_id), -1)
        if idx < 0 or idx == dest_index:
            return
        lot = self._lots.pop(idx)
        # Ajuster l'index si on a retiré un élément avant la destination
        if dest_index > idx:
            dest_index -= 1
        self._lots.insert(dest_index, lot)
        self.devis_structure_changed.emit()

    def move_item_to_lot(self, item_id: str, src_lot_id: str,
                         dest_lot_id: str, dest_index: int = -1) -> bool:
        """
        Déplace un item du lot src_lot_id vers dest_lot_id.
        dest_index = position dans le lot destination (-1 = fin).
        Retourne True si réussi.
        """
        src_lot  = self.get_lot(src_lot_id)
        dest_lot = self.get_lot(dest_lot_id)
        if not src_lot or not dest_lot:
            return False
        item = next((it for it in src_lot.items if it.id == item_id), None)
        if item is None:
            return False
        src_lot.items.remove(item)
        if dest_index < 0 or dest_index >= len(dest_lot.items):
            dest_lot.items.append(item)
        else:
            dest_lot.items.insert(dest_index, item)
        self.devis_structure_changed.emit()
        return True

    # ── CRUD Items ────────────────────────────────────────────────────────────

    def get_item(self, lot_id: str, item_id: str) -> Optional[DevisItem]:
        lot = self.get_lot(lot_id)
        if not lot:
            return None
        for item in lot.items:
            if item.id == item_id:
                return item
        return None

    def get_item_label(self, lot_id: str, item_id: str) -> str:
        item = self.get_item(lot_id, item_id)
        return item.label if item else f"{item_id} (inconnu)"

    def get_item_unit(self, lot_id: str, item_id: str) -> str:
        item = self.get_item(lot_id, item_id)
        return item.unit if item else ""

    def add_item(self, lot_id: str, label: str = "Nouvel item",
                 unit: str = "U", default_formula: str = "",
                 item_id: str = "",
                 insert_after: str = "") -> Optional[DevisItem]:
        """
        Ajoute un item personnalisé à un lot.

        Si item_id est fourni (ex: "17.03"), il est utilisé tel quel.
        Sinon, un ID est auto-généré sous la forme "lot_id.C01".
        insert_after : id d'un item existant après lequel insérer le nouvel
                       item. Si vide ou introuvable, l'item est ajouté en fin.
        """
        lot = self.get_lot(lot_id)
        if not lot:
            return None
        existing_ids = {it.id for it in lot.items}

        if item_id and item_id not in existing_ids:
            new_id = item_id
        else:
            # Auto-générer : lot_id.C01, .C02…
            base = f"{lot_id}.C"
            n = 1
            new_id = f"{base}{n:02d}"
            while new_id in existing_ids:
                n += 1
                new_id = f"{base}{n:02d}"

        item = DevisItem(id=new_id, label=label, unit=unit,
                         default_formula=default_formula, is_custom=True)

        if insert_after:
            ids = [it.id for it in lot.items]
            if insert_after in ids:
                lot.items.insert(ids.index(insert_after) + 1, item)
            else:
                lot.items.append(item)
        else:
            lot.items.append(item)

        self.devis_structure_changed.emit()
        return item

    def rename_item(self, lot_id: str, item_id: str,
                    new_label: str = "", new_unit: str = "") -> bool:
        item = self.get_item(lot_id, item_id)
        if not item:
            return False
        if new_label:
            item.label = new_label
        if new_unit:
            item.unit = new_unit
        self.devis_structure_changed.emit()
        return True

    def remove_item(self, lot_id: str, item_id: str) -> bool:
        lot = self.get_lot(lot_id)
        if not lot:
            return False
        before = len(lot.items)
        lot.items = [it for it in lot.items if it.id != item_id]
        if len(lot.items) < before:
            self.devis_structure_changed.emit()
            return True
        return False

    def move_item(self, lot_id: str, item_id: str, direction: int):
        lot = self.get_lot(lot_id)
        if not lot:
            return
        idx = next((i for i, it in enumerate(lot.items)
                    if it.id == item_id), -1)
        if idx < 0:
            return
        new_idx = idx + direction
        if 0 <= new_idx < len(lot.items):
            lot.items.insert(new_idx, lot.items.pop(idx))
            self.devis_structure_changed.emit()

    # ── Items personnalisés (rétrocompat) ─────────────────────────────────────

    def add_custom_item(self, lot_id: str, label: str, unit: str,
                        default_formula: str = "") -> Optional[DevisItem]:
        return self.add_item(lot_id, label, unit, default_formula)

    def remove_custom_item(self, lot_id: str, item_id: str) -> bool:
        return self.remove_item(lot_id, item_id)

    def _apply_custom_items(self):
        for c in self._custom_items:
            lot = self.get_lot(c["lot_id"])
            if lot and not any(it.id == c["id"] for it in lot.items):
                lot.items.append(DevisItem(
                    id=c["id"], label=c["label"], unit=c["unit"],
                    default_formula=c.get("default_formula", ""),
                    is_custom=True
                ))

    # ── Affectations (group_assignments) ──────────────────────────────────────

    def get_assignment(self, group_id: str) -> Optional[GroupAssignment]:
        return self._assignments.get(group_id)

    def get_or_create_assignment(self, group_id: str, group_name: str,
                                  group_type: str,
                                  page_name: str) -> GroupAssignment:
        if group_id not in self._assignments:
            self._assignments[group_id] = GroupAssignment(
                group_id=group_id, group_name=group_name,
                group_type=group_type, page_name=page_name
            )
        return self._assignments[group_id]

    def add_assignment_item(self, group_id: str, group_name: str,
                             group_type: str, page_name: str,
                             lot_id: str, item_id: str,
                             formula_expr: str, coefficient: float = 1.0,
                             prix_unitaire: float = 0.0) -> AssignedItem:
        ga = self.get_or_create_assignment(
            group_id, group_name, group_type, page_name)
        ai = AssignedItem(
            lot_id=lot_id, item_id=item_id,
            formula_expr=formula_expr,
            coefficient=coefficient,
            prix_unitaire=prix_unitaire,
        )
        ga.items.append(ai)
        return ai

    def remove_assignment_item(self, group_id: str, index: int):
        ga = self._assignments.get(group_id)
        if ga and 0 <= index < len(ga.items):
            ga.items.pop(index)

    def update_assignment_item(self, group_id: str, index: int, **kwargs):
        ga = self._assignments.get(group_id)
        if not ga or not (0 <= index < len(ga.items)):
            return
        ai = ga.items[index]
        for k, v in kwargs.items():
            if hasattr(ai, k):
                setattr(ai, k, v)

    def copy_assignments(self, source_group_id: str, target_group_id: str,
                         target_name: str = "", target_type: str = "",
                         page_name: str = "") -> bool:
        """
        Duplique les affectations de source_group_id vers target_group_id.

        Utilisé lors du copier/coller d'une entité : la copie hérite des
        mêmes items BPU que l'original, avec les mêmes formules et coefficients.
        Ne fait rien si source_group_id est inconnu ou si target_group_id
        possède déjà des affectations.

        Retourne True si la copie a eu lieu, False sinon.
        """
        import copy as _copy
        source_ga = self._assignments.get(source_group_id)
        if not source_ga or not source_ga.items:
            return False
        if target_group_id in self._assignments:
            return False

        new_ga = GroupAssignment(
            group_id=target_group_id,
            group_name=target_name or source_ga.group_name,
            group_type=target_type or source_ga.group_type,
            page_name=page_name or source_ga.page_name,
        )
        for ai in source_ga.items:
            new_ga.items.append(_copy.deepcopy(ai))
        self._assignments[target_group_id] = new_ga
        return True

    def clear_assignments(self):
        self._assignments.clear()
        self._custom_items.clear()

    def all_assignments(self) -> List[GroupAssignment]:
        return list(self._assignments.values())

    # ── Persistance projet (.mtp) ─────────────────────────────────────────────

    def assignments_to_dict(self) -> Dict[str, Any]:
        """Sérialise les affectations ET les lots custom pour le .mtp."""
        custom_lots = [lot.to_dict() for lot in self._lots if lot.is_custom]
        # Items custom dans des lots standard
        custom_items_in_std = []
        for lot in self._lots:
            if not lot.is_custom:
                for it in lot.items:
                    if it.is_custom:
                        custom_items_in_std.append({
                            "lot_id":          lot.id,
                            "id":              it.id,
                            "label":           it.label,
                            "unit":            it.unit,
                            "default_formula": it.default_formula,
                        })
        return {
            "custom_lots":          custom_lots,
            "custom_items":         custom_items_in_std,
            "group_assignments":    {
                gid: ga.to_dict()
                for gid, ga in self._assignments.items()
            },
        }

    def assignments_from_dict(self, data: Dict[str, Any]):
        """Restaure les affectations depuis le .mtp chargé."""
        self._assignments.clear()
        self._custom_items = []

        # Restaurer les lots entièrement custom
        for lot_data in data.get("custom_lots", []):
            if not self.get_lot(lot_data["id"]):
                self._lots.append(DevisLot.from_dict(lot_data))

        # Restaurer les items custom dans des lots standard
        for c in data.get("custom_items", []):
            lot = self.get_lot(c["lot_id"])
            if lot and not any(it.id == c["id"] for it in lot.items):
                lot.items.append(DevisItem(
                    id=c["id"], label=c["label"], unit=c["unit"],
                    default_formula=c.get("default_formula", ""),
                    is_custom=True
                ))

        # Rétrocompat ancien format
        for c in data.get("custom_items_legacy", []):
            self._custom_items.append(c)
        self._apply_custom_items()

        for gid, ga_data in data.get("group_assignments", {}).items():
            self._assignments[gid] = GroupAssignment.from_dict(ga_data)