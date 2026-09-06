"""
Gestionnaire de licences côté client — Métraplan
=================================================
Responsabilités :
  - Calculer le machine_id unique du PC
  - Stocker le token JWT dans le registre Windows (+ fallback fichier)
  - Vérifier la validité de la licence au démarrage
  - Envoyer les requêtes /activate et /verify au serveur

Politique de vérification :
  - Vérification serveur FORCÉE à chaque démarrage (force=True).
  - Vérification serveur obligatoire toutes les heures en session (timer).
  - Si le serveur est injoignable, tolérance OFFLINE_GRACE_DAYS (7 jours).
  - Au-delà de 7 jours sans connexion → logiciel bloqué.
  - Blocage dashboard → effectif au prochain démarrage ou dans l'heure.

Usage :
    from core.license_manager import LicenseManager
    lm = LicenseManager()
    status = lm.check(force=True)  # démarrage : ignore cache
    status = lm.check()            # vérif périodique (timer)
    ok, msg = lm.activate(key)     # activation manuelle
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple
import urllib.request
import urllib.error

# ── Configuration ──────────────────────────────────────────────────────────────

def _load_server_url() -> str:
    """
    Lit l'URL du serveur dans l'ordre de priorité :
      1. Variable d'environnement METRAPLAN_LICENSE_URL (tests / CI)
      2. Fichier config.ini à côté du .exe
      3. Valeur par défaut compilée
    """
    env = os.environ.get("METRAPLAN_LICENSE_URL")
    if env:
        return env.rstrip("/")

    import configparser
    for candidate in (
        Path(__file__).parent.parent / "config.ini",
        Path(sys.executable).parent / "config.ini",
    ):
        if candidate.exists():
            cfg = configparser.ConfigParser()
            cfg.read(str(candidate), encoding="utf-8")
            url = cfg.get("license", "server_url", fallback=None)
            if url:
                return url.rstrip("/")

    return "https://licences.metraplan.com"


LICENSE_SERVER_URL = _load_server_url()
VERIFY_ENDPOINT    = f"{LICENSE_SERVER_URL}/verify"
ACTIVATE_ENDPOINT  = f"{LICENSE_SERVER_URL}/activate"

# Vérification serveur obligatoire tous les 7 jours (même si JWT encore valide)
PERIODIC_CHECK_DAYS = 7

# Tolérance hors-ligne : blocage après 7 jours sans connexion au serveur
OFFLINE_GRACE_DAYS  = 7

_REG_KEY_PATH = r"Software\Metraplan"
_REG_VALUE    = "LicenseData"


# ── Statuts et types de données ───────────────────────────────────────────────

class LicenseStatus(Enum):
    VALID      = "valid"
    NOT_FOUND  = "not_found"    # Aucune activation locale
    EXPIRED    = "expired"
    BLOCKED    = "blocked"
    INVALID    = "invalid"
    OFFLINE    = "offline"      # Serveur injoignable, token local encore valide
    ERROR      = "error"


@dataclass
class LicenseInfo:
    status:      LicenseStatus
    message:     str = ""
    license_key: str = ""
    client_name: str = ""
    type:        str = ""
    expires_at:  str = ""
    days_left:   int = 0


# ── Machine ID ────────────────────────────────────────────────────────────────

def get_machine_id() -> str:
    """
    Hash stable du PC : UUID BIOS + hostname + disque.
    Résiste aux changements mineurs (mise à jour OS, ajout RAM…).
    """
    parts = []

    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["wmic", "csproduct", "get", "uuid"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode(errors="ignore")
            uuid_lines = [l.strip() for l in out.splitlines()
                          if l.strip() and "UUID" not in l]
            if uuid_lines:
                parts.append(uuid_lines[0])
        except Exception:
            pass

    parts.append(socket.gethostname())
    parts.append(platform.node())
    parts.append(platform.machine())

    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["wmic", "diskdrive", "get", "serialnumber"],
                stderr=subprocess.DEVNULL, timeout=5
            ).decode(errors="ignore")
            serials = [l.strip() for l in out.splitlines()
                       if l.strip() and "SerialNumber" not in l]
            parts.extend(serials[:2])
        except Exception:
            pass

    raw = "|".join(filter(None, parts))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ── Stockage local (Registre Windows + fallback fichier) ─────────────────────

def _reg_write(data: dict) -> None:
    if sys.platform == "win32":
        import winreg
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_KEY_PATH)
            winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_SZ,
                              json.dumps(data, ensure_ascii=False))
            winreg.CloseKey(key)
            return
        except Exception:
            pass
    _file_path().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _reg_read() -> Optional[dict]:
    if sys.platform == "win32":
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY_PATH,
                                 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, _REG_VALUE)
            winreg.CloseKey(key)
            return json.loads(val)
        except FileNotFoundError:
            return None
        except Exception:
            pass
    p = _file_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _reg_delete() -> None:
    if sys.platform == "win32":
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY_PATH,
                                 0, winreg.KEY_WRITE)
            winreg.DeleteValue(key, _REG_VALUE)
            winreg.CloseKey(key)
        except Exception:
            pass
    p = _file_path()
    if p.exists():
        p.unlink(missing_ok=True)


def _file_path() -> Path:
    appdata = Path(os.environ.get("APPDATA", str(Path.home()))) / "Metraplan"
    appdata.mkdir(parents=True, exist_ok=True)
    return appdata / "license.dat"


# ── Requêtes HTTP (stdlib uniquement) ─────────────────────────────────────────

def _post(url: str, payload: dict, timeout: int = 10) -> Tuple[int, dict]:
    """POST JSON → (status_code, body_dict). Lève ConnectionError si réseau KO."""
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"detail": str(e)}
        return e.code, body
    except Exception as exc:
        raise ConnectionError(str(exc)) from exc


# ── Helpers internes ──────────────────────────────────────────────────────────

def _days_since(iso_str: str) -> Optional[int]:
    """Nombre de jours écoulés depuis une date ISO. None si invalide."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


def _days_until(iso_str: str) -> int:
    """Nombre de jours restants avant expiration (0 si expiré)."""
    try:
        exp = datetime.fromisoformat(iso_str)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return max(0, (exp - datetime.now(timezone.utc)).days)
    except Exception:
        return 0


def _is_locally_expired(expires_at: str) -> bool:
    return _days_until(expires_at) == 0 and bool(expires_at)


# ── LicenseManager ────────────────────────────────────────────────────────────

class LicenseManager:
    """Point d'entrée unique pour toutes les opérations de licence."""

    def __init__(self):
        self._machine_id = get_machine_id()

    # ── Vérification au démarrage ──────────────────────────────────────────

    def check(self, force: bool = False) -> LicenseInfo:
        """
        Algorithme :
          1. Lire données locales → si absent : NOT_FOUND
          2. Détecter manipulation d'horloge (date système < last_check)
          3. Vérifier expiration locale immédiate
          4. Si force=False ET dernier check < PERIODIC_CHECK_DAYS → VALID (cache)
             Si force=True → ignorer le cache, toujours contacter le serveur
          5. Contacter serveur /verify → mettre à jour le token
          6. Si serveur KO → tolérance OFFLINE_GRACE_DAYS

        Utilisation :
          - force=True  : au démarrage de l'app (blocage immédiat si clé révoquée)
          - force=False : vérifications périodiques internes
        """
        stored = _reg_read()
        if not stored:
            return LicenseInfo(LicenseStatus.NOT_FOUND,
                               "Aucune licence activée sur cet ordinateur.")

        license_key = stored.get("license_key", "")
        token       = stored.get("token", "")
        expires_at  = stored.get("expires_at", "")
        last_check  = stored.get("last_check", "")

        # 1. Détection de manipulation d'horloge
        #    Si l'heure actuelle est AVANT la date du dernier check connu
        #    → l'horloge a été reculée → forcer vérification serveur immédiate
        clock_tampered = False
        if last_check:
            try:
                lc_dt = datetime.fromisoformat(last_check)
                if lc_dt.tzinfo is None:
                    lc_dt = lc_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < lc_dt:
                    clock_tampered = True
            except Exception:
                pass

        # 2. Expiration locale (évite un aller-serveur inutile)
        if not clock_tampered and not force and _is_locally_expired(expires_at):
            return LicenseInfo(LicenseStatus.EXPIRED,
                               "Votre licence a expiré. Contactez le support pour la renouveler.",
                               license_key=license_key, expires_at=expires_at)

        # 3. Cache local : si force=False ET check récent (< 7 jours) ET licence
        #    non expirée ET horloge non manipulée → pas besoin de contacter serveur
        days_since_check = _days_since(last_check)
        days_left_local  = _days_until(expires_at)
        if (not force
                and not clock_tampered
                and days_since_check is not None
                and days_since_check < PERIODIC_CHECK_DAYS
                and days_left_local > 0):
            return LicenseInfo(
                status=LicenseStatus.VALID,
                message="Licence valide (cache local).",
                license_key=license_key,
                client_name=stored.get("client_name", ""),
                type=stored.get("type", ""),
                expires_at=expires_at,
                days_left=days_left_local,
            )

        # 3. Vérification serveur obligatoire (7+ jours depuis le dernier check)
        try:
            code, body = _post(VERIFY_ENDPOINT, {
                "license_key": license_key,
                "machine_id":  self._machine_id,
                "token":       token,
            })

            if code == 200:
                stored.update({
                    "token":       body["token"],
                    "expires_at":  body["expires_at"],
                    "type":        body["type"],
                    "last_check":  datetime.now(timezone.utc).isoformat(),
                })
                _reg_write(stored)
                return self._build_info(LicenseStatus.VALID, body)

            elif code in (401, 403):
                detail = body.get("detail", "")
                if "expir" in detail.lower():
                    return LicenseInfo(LicenseStatus.EXPIRED, detail,
                                       license_key=license_key)
                if "bloqu" in detail.lower() or "block" in detail.lower() or "révoqu" in detail.lower():
                    return LicenseInfo(LicenseStatus.BLOCKED, detail,
                                       license_key=license_key)
                return LicenseInfo(LicenseStatus.INVALID, detail,
                                   license_key=license_key)
            else:
                return LicenseInfo(LicenseStatus.INVALID,
                                   body.get("detail", "Licence invalide."),
                                   license_key=license_key)

        except ConnectionError:
            return self._offline_check(stored)

    def _offline_check(self, stored: dict) -> LicenseInfo:
        """
        Serveur injoignable.
        Autorise jusqu'à OFFLINE_GRACE_DAYS jours depuis le dernier check réussi.
        Au-delà → ERROR (blocage).
        """
        last_check = stored.get("last_check", "")
        expires_at = stored.get("expires_at", "")
        license_key = stored.get("license_key", "")

        if _is_locally_expired(expires_at):
            return LicenseInfo(LicenseStatus.EXPIRED,
                               "Votre licence a expiré.",
                               license_key=license_key, expires_at=expires_at)

        days_since = _days_since(last_check)
        if days_since is not None and days_since <= OFFLINE_GRACE_DAYS:
            remaining = OFFLINE_GRACE_DAYS - days_since
            return LicenseInfo(
                LicenseStatus.OFFLINE,
                f"Serveur de licences injoignable.\n"
                f"Mode hors-ligne autorisé encore {remaining} jour(s).\n"
                f"Connectez-vous à internet pour revalider votre licence.",
                license_key=license_key,
                type=stored.get("type", ""),
                expires_at=expires_at,
                days_left=_days_until(expires_at),
            )

        return LicenseInfo(
            LicenseStatus.ERROR,
            f"Licence non vérifiable depuis plus de {OFFLINE_GRACE_DAYS} jours.\n\n"
            "Connectez-vous à internet et relancez le logiciel.\n"
            "Si le problème persiste, contactez le support.",
            license_key=license_key,
        )

    # ── Activation ─────────────────────────────────────────────────────────

    def activate(self, license_key: str) -> Tuple[bool, str]:
        """
        Active une clé de licence sur ce PC.
        Retourne (True, message_succès) ou (False, message_erreur).
        """
        key = _normalize_key(license_key)

        if not _is_valid_format(key):
            return False, "Format de clé invalide.\nFormat attendu : MTR-XXXX-XXXX-XXXX-XXXX"

        try:
            code, body = _post(ACTIVATE_ENDPOINT, {
                "license_key": key,
                "machine_id":  self._machine_id,
            })
        except ConnectionError:
            return False, (
                "Impossible de contacter le serveur de licences.\n\n"
                f"Vérifiez votre connexion et que le serveur est accessible :\n{LICENSE_SERVER_URL}"
            )

        if code == 200:
            _reg_write({
                "license_key": key,
                "token":       body["token"],
                "expires_at":  body["expires_at"],
                "type":        body["type"],
                "client_name": body.get("client_name", ""),
                "last_check":  datetime.now(timezone.utc).isoformat(),
            })
            exp = body["expires_at"][:10]
            return True, (
                f"Licence activée avec succès !\n\n"
                f"Type       : {body['type']}\n"
                f"Expiration : {exp}\n"
                f"Client     : {body.get('client_name', '')}"
            )

        detail = body.get("detail", "Erreur inconnue")
        # Messages utilisateur plus clairs selon le code HTTP
        if code == 409:
            detail = (
                "Cette clé est déjà activée sur un autre ordinateur.\n\n"
                "Pour transférer votre licence, désactivez d'abord l'ancien PC\n"
                "ou contactez le support."
            )
        elif code == 403 and "bloqu" in detail.lower():
            detail = "Cette licence a été révoquée.\nContactez le support."
        elif code == 404:
            detail = "Clé de licence introuvable.\nVérifiez que vous avez saisi la bonne clé."
        return False, detail

    # ── Désactivation ──────────────────────────────────────────────────────

    def deactivate(self) -> None:
        """Supprime les données de licence locales (permet réactivation sur autre PC)."""
        _reg_delete()

    # ── Informations ───────────────────────────────────────────────────────

    def get_stored_info(self) -> Optional[dict]:
        return _reg_read()

    def get_machine_id(self) -> str:
        return self._machine_id

    def needs_periodic_check(self) -> bool:
        """True si un appel serveur est nécessaire (dernière vérif > 7 jours)."""
        stored = _reg_read()
        if not stored:
            return False
        days = _days_since(stored.get("last_check", ""))
        return days is None or days >= PERIODIC_CHECK_DAYS

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _build_info(status: LicenseStatus, body: dict) -> LicenseInfo:
        expires_at = body.get("expires_at", "")
        return LicenseInfo(
            status=status,
            message="Licence valide.",
            license_key=body.get("license_key", ""),
            client_name=body.get("client_name", ""),
            type=body.get("type", ""),
            expires_at=expires_at,
            days_left=_days_until(expires_at),
        )


# ── Fonctions utilitaires publiques ───────────────────────────────────────────

def _normalize_key(key: str) -> str:
    return key.strip().upper().replace(" ", "").replace("–", "-")


def _is_valid_format(key: str) -> bool:
    import string
    parts = key.split("-")
    if len(parts) != 5 or parts[0] != "MTR":
        return False
    alphabet = string.ascii_uppercase + string.digits
    return all(len(p) == 4 and all(c in alphabet for c in p) for p in parts[1:])
