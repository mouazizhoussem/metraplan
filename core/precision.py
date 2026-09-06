# core/precision.py
"""
Utilitaire de précision arithmétique pour Métraplan.

Utilise decimal.Decimal (base 10) au lieu des float IEEE-754 (base 2)
pour éliminer les erreurs d'arrondi dans les calculs BTP :
  • 3.86 × 3.57  → float: 13.780200000000001  / Decimal: 13.78  ✓
  • round(2.675, 2) → float: 2.67 (bug)        / Decimal: 2.68  ✓
  • 0.1 + 0.2    → float: 0.30000000000000004  / Decimal: 0.30  ✓

Usage :
    from core.precision import P

    brute  = P.surface(3.86, 3.57)           # 13.78
    ouv    = P.surface(2.53, 1.57)           # 3.97
    nette  = P.surface_nette(brute, ouv)     # 9.81
    vol    = P.volume(nette, 0.16)           # 1.570 m³
    _log.info(P.fmt_surface(nette))              # "9.81"
    _log.info(P.fmt_volume(vol))                 # "1.570"
"""
from __future__ import annotations
from core.app_logger import get_logger
_log = get_logger(__name__)

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Union

Number = Union[int, float, str, Decimal]


class _Precision:
    """
    Singleton de précision arithmétique Decimal.
    Toutes les méthodes retournent des float Python standard pour
    une intégration transparente avec le reste du code.
    """

    # ── Helpers internes ──────────────────────────────────────────────────────

    @staticmethod
    def _d(value: Number) -> Decimal:
        """
        Convertit en Decimal de manière fiable.
        Passer par str() évite l'erreur classique :
            Decimal(0.1) → Decimal('0.1000000000000000055511151...')
            Decimal('0.1') → Decimal('0.1')  ✓
        """
        try:
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @staticmethod
    def _q(decimals: int) -> Decimal:
        """Quantum d'arrondi : decimals=2 → Decimal('0.01')."""
        return Decimal("1e-" + str(decimals)) if decimals > 0 else Decimal("1")

    def _r(self, d: Decimal, decimals: int) -> float:
        """Arrondit un Decimal et retourne un float."""
        return float(d.quantize(self._q(decimals), rounding=ROUND_HALF_UP))

    # ── Opérations arithmétiques de base ─────────────────────────────────────

    def round(self, value: Number, decimals: int = 2) -> float:
        """Arrondi ROUND_HALF_UP (arrondi scolaire, pas bancaire)."""
        return self._r(self._d(value), decimals)

    def add(self, a: Number, b: Number, decimals: int = 2) -> float:
        return self._r(self._d(a) + self._d(b), decimals)

    def sub(self, a: Number, b: Number, decimals: int = 2) -> float:
        return self._r(self._d(a) - self._d(b), decimals)

    def mul(self, a: Number, b: Number, decimals: int = 2) -> float:
        return self._r(self._d(a) * self._d(b), decimals)

    def div(self, a: Number, b: Number, decimals: int = 2) -> float:
        db = self._d(b)
        if db == Decimal("0"):
            return 0.0
        return self._r(self._d(a) / db, decimals)

    # ── Opérations métier BTP ─────────────────────────────────────────────────

    def surface(self, longueur: Number, largeur: Number) -> float:
        """L × l → m² arrondi à 2 décimales."""
        return self.mul(longueur, largeur, 2)

    def volume(self, surface: Number, epaisseur: Number) -> float:
        """S × e → m³ arrondi à 3 décimales."""
        return self.mul(surface, epaisseur, 3)

    def surface_nette(self, brute: Number, *deductions: Number) -> float:
        """
        surface_brute − Σ(ouvertures) → m² (2 décimales, jamais négatif).
        Accepte n'importe quel nombre de déductions :
            P.surface_nette(14.22, 3.97)          # une ouverture
            P.surface_nette(14.22, 2.10, 1.87)    # deux ouvertures
        """
        total_ded = sum(self._d(d) for d in deductions)
        nette = self._d(brute) - total_ded
        return self._r(max(Decimal("0"), nette), 2)

    def longueur_nette(self, brute: Number, *deductions: Number) -> float:
        """longueur_brute − Σ(ouvertures linéaires) → ml (2 décimales)."""
        total_ded = sum(self._d(d) for d in deductions)
        nette = self._d(brute) - total_ded
        return self._r(max(Decimal("0"), nette), 2)

    def somme(self, *values: Number, decimals: int = 2) -> float:
        """Somme précise d'un nombre quelconque de valeurs."""
        total = sum(self._d(v) for v in values)
        return self._r(total, decimals)

    def somme_surfaces(self, *surfaces: Number) -> float:
        """Somme de surfaces m² (2 décimales)."""
        return self.somme(*surfaces, decimals=2)

    def somme_volumes(self, *volumes: Number) -> float:
        """Somme de volumes m³ (3 décimales)."""
        return self.somme(*volumes, decimals=3)

    # ── Formatage cohérent affichage ↔ PDF ───────────────────────────────────

    def fmt(self, value: Number, decimals: int = 2, unit: str = "") -> str:
        """
        Formate un nombre avec séparateur milliers (espace fine).
        Identique entre l'interface et les rapports PDF.
        """
        rounded   = self.round(value, decimals)
        formatted = f"{rounded:,.{decimals}f}".replace(",", "\u202f")
        return f"{formatted} {unit}".strip() if unit else formatted

    def fmt_surface(self, value: Number) -> str:
        """Formate une surface m² (2 décimales)."""
        return self.fmt(value, 2)

    def fmt_volume(self, value: Number) -> str:
        """Formate un volume m³ (3 décimales)."""
        return self.fmt(value, 3)

    def fmt_longueur(self, value: Number) -> str:
        """Formate une longueur ml (2 décimales)."""
        return self.fmt(value, 2)

    def fmt_unite(self, value: Number) -> str:
        """Formate un comptage entier."""
        return str(int(self.round(value, 0)))

    def fmt_qty(self, value: Number, unit: str) -> str:
        """Formate une quantité selon son unité (même règle partout)."""
        unit = (unit or "").strip()
        if unit in ("m³", "m3"):
            return self.fmt(value, 3, unit)
        if unit in ("m²", "m2", "ml", "m"):
            return self.fmt(value, 2, unit)
        if unit.upper() == "U":
            return f"{int(self.round(value, 0))} U"
        return self.fmt(value, 2, unit)

    # ── Vérificateur de cohérence (aide au débogage) ─────────────────────────

    def check(self, label: str, computed: Number, expected: Number,
              decimals: int = 2, tolerance: float | None = None) -> bool:
        """
        Vérifie que `computed` correspond à `expected` à `decimals` près.
        Affiche un avertissement si un écart est détecté.
        Retourne True (OK) ou False (écart).
        """
        tol = tolerance if tolerance is not None else 0.5 * 10 ** (-decimals)
        diff = abs(float(self._d(computed) - self._d(expected)))
        if diff > tol:
            _log.info(
                f"[PRECISION ⚠] {label} : "
                f"calculé={self.fmt(computed, decimals)}, "
                f"attendu={self.fmt(expected, decimals)}, "
                f"écart={diff:.{decimals + 3}f}"
            )
            return False
        return True


# ── Singleton global ──────────────────────────────────────────────────────────
# Importer P dans tous les modules qui font des calculs numériques.
P = _Precision()