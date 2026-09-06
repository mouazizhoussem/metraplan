"""
Génération et validation des clés de licence Métraplan.

Format : MTR-XXXX-XXXX-XXXX-XXXX
  MTR  = préfixe produit
  XXXX = 4 groupes de 4 caractères alphanumériques majuscules (Base32 sans padding)

La clé est générée aléatoirement (16 octets de secrets) et ne contient pas
de checksum embarqué — la validation passe toujours par le serveur.
"""
from __future__ import annotations

import secrets
import string

_ALPHABET = string.ascii_uppercase + string.digits   # 36 chars
_GROUP_LEN = 4
_NUM_GROUPS = 4
_PREFIX = "MTR"


def generate_key() -> str:
    """Génère une clé de licence sécurisée au format MTR-XXXX-XXXX-XXXX-XXXX."""
    groups = []
    for _ in range(_NUM_GROUPS):
        group = "".join(secrets.choice(_ALPHABET) for _ in range(_GROUP_LEN))
        groups.append(group)
    return f"{_PREFIX}-" + "-".join(groups)


def is_valid_format(key: str) -> bool:
    """Vérifie uniquement le format de la clé (pas son authenticité)."""
    parts = key.upper().split("-")
    if len(parts) != _NUM_GROUPS + 1:
        return False
    if parts[0] != _PREFIX:
        return False
    for part in parts[1:]:
        if len(part) != _GROUP_LEN:
            return False
        if not all(c in _ALPHABET for c in part):
            return False
    return True


def normalize_key(key: str) -> str:
    """Normalise la clé (majuscules, espaces supprimés)."""
    return key.strip().upper().replace(" ", "").replace("–", "-")
