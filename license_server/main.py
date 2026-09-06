"""
Serveur de licences Métraplan — FastAPI + SQLite
================================================
Démarrage : uvicorn main:app --host 0.0.0.0 --port 8765 --reload

Variables d'environnement :
  ADMIN_API_KEY  — clé secrète pour les routes admin (défaut : changez-moi !)
  JWT_SECRET     — secret pour signer les tokens JWT  (défaut : changez-moi !)
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Charger le fichier .env si présent (développement local)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import jwt
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import database as db
import license_gen as lg

# ── Configuration ─────────────────────────────────────────────────────────────
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "metraplan-admin-secret-2026")
JWT_SECRET    = os.environ.get("JWT_SECRET",    "metraplan-jwt-secret-2026")
JWT_ALGO        = "HS256"
TOKEN_TTL_DAYS  = 365  # durée de vie du token JWT côté client logiciel (1 an)
SESSION_TTL_H   = 8    # durée de la session admin (heures)
SESSION_COOKIE  = "admin_session"

app = FastAPI(title="Métraplan License Server", version="1.0.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ── Diagnostic de démarrage ────────────────────────────────────────────────────
import logging
_startup_log = logging.getLogger("metraplan.startup")
logging.basicConfig(level=logging.INFO)

_db_url = (os.environ.get("DATABASE_URL", "")
           or os.environ.get("DATABASE_PUBLIC_URL", "")
           or os.environ.get("POSTGRES_URL", ""))
if _db_url:
    _masked = _db_url[:15] + "****" + _db_url[-10:] if len(_db_url) > 25 else "****"
    _startup_log.info(f"DB URL détectée : {_masked}")
    _startup_log.info(f"Backend : {'PostgreSQL' if _db_url.startswith('postgres') else 'SQLite (fallback)'}")
else:
    _startup_log.warning("Aucune DB URL trouvée → SQLite local")

# Initialiser la BDD au démarrage
try:
    db.init_db()
    _startup_log.info("Base de données initialisée avec succès")
except Exception as _e:
    _startup_log.error(f"Erreur initialisation BDD : {_e}")
    raise


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_admin(x_admin_key: str = Header(None)):
    """Protection des routes API admin (clé dans le header)."""
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Clé admin invalide")


def _make_session_token() -> str:
    """Génère un JWT de session admin (TTL SESSION_TTL_H heures)."""
    payload = {
        "role": "admin",
        "exp":  datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_H),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _check_session(admin_session: Optional[str] = Cookie(None)) -> bool:
    """Vérifie le cookie de session admin. Retourne True si valide."""
    if not admin_session:
        return False
    try:
        payload = jwt.decode(admin_session, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload.get("role") == "admin"
    except jwt.PyJWTError:
        return False


def _require_session(request: Request,
                     admin_session: Optional[str] = Cookie(None)):
    """Dépendance FastAPI : redirige vers /login si session invalide."""
    if not _check_session(admin_session):
        raise HTTPException(status_code=302, headers={"Location": "/login"})


def _make_token(license_key: str, machine_id: str,
                expires_at: str, type_: str) -> str:
    """Génère un JWT signé à retourner au client."""
    payload = {
        "license_key": license_key,
        "machine_id":  machine_id,
        "expires_at":  expires_at,
        "type":        type_,
        "iat":         datetime.now(timezone.utc).isoformat(),
        "exp":         datetime.now(timezone.utc) + timedelta(days=TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class GenerateLicenseRequest(BaseModel):
    client_name:   str
    client_email:  str  = ""
    type:          str  = "standard"   # standard | pro | trial
    duration_days: int  = 365
    notes:         str  = ""


class ActivateRequest(BaseModel):
    license_key: str
    machine_id:  str


class VerifyRequest(BaseModel):
    license_key: str
    machine_id:  str
    token:       str


class BlockRequest(BaseModel):
    license_key: str
    action:      str = "block"   # block | unblock


class UpdateLicenseRequest(BaseModel):
    client_name:  str
    client_email: str  = ""
    type:         str  = "standard"
    expires_at:   str  = ""   # ISO date, ex: "2027-06-01"
    notes:        str  = ""


class TransferRequest(BaseModel):
    license_key: str


# ── Routes Admin ──────────────────────────────────────────────────────────────

@app.post("/generate_license", dependencies=[Depends(_require_admin)])
def generate_license(req: GenerateLicenseRequest):
    """Génère une nouvelle clé de licence et l'enregistre en base."""
    key = lg.generate_key()
    now = _now_iso()
    expires = (datetime.now(timezone.utc) +
               timedelta(days=req.duration_days)).isoformat()

    db.insert_license(
        key=key,
        client_name=req.client_name,
        client_email=req.client_email,
        type_=req.type,
        duration_days=req.duration_days,
        created_at=now,
        expires_at=expires,
        notes=req.notes,
    )
    return {
        "license_key":   key,
        "client_name":   req.client_name,
        "client_email":  req.client_email,
        "type":          req.type,
        "duration_days": req.duration_days,
        "expires_at":    expires,
        "status":        "inactive",
    }


@app.get("/licenses", dependencies=[Depends(_require_admin)])
def list_licenses():
    """Retourne toutes les licences (admin uniquement)."""
    return db.get_all_licenses()


@app.post("/block_license", dependencies=[Depends(_require_admin)])
def block_license(req: BlockRequest):
    """Bloque ou débloque une licence."""
    row = db.get_license(req.license_key)
    if not row:
        raise HTTPException(status_code=404, detail="Licence introuvable")
    new_status = "blocked" if req.action == "block" else "inactive"
    db.set_status(req.license_key, new_status)
    return {"license_key": req.license_key, "status": new_status}


@app.put("/licenses/{license_key}", dependencies=[Depends(_require_admin)])
def update_license(license_key: str, req: UpdateLicenseRequest):
    """Modifie les informations d'une licence (nom, email, type, expiration, notes)."""
    key = lg.normalize_key(license_key)
    row = db.get_license(key)
    if not row:
        raise HTTPException(status_code=404, detail="Licence introuvable")

    # Calcul de la nouvelle date d'expiration
    if req.expires_at:
        try:
            from datetime import datetime
            # Accepter date ISO courte (2027-06-01) ou complète
            exp_str = req.expires_at if "T" in req.expires_at else req.expires_at + "T00:00:00+00:00"
            datetime.fromisoformat(exp_str)   # validation
            expires_at = exp_str
        except Exception:
            raise HTTPException(status_code=400, detail="Format de date invalide (attendu : YYYY-MM-DD)")
    else:
        expires_at = row["expires_at"]

    db.update_license(key, req.client_name, req.client_email,
                      req.type, expires_at, req.notes)
    return {"license_key": key, "status": "updated"}


@app.post("/transfer_license", dependencies=[Depends(_require_admin)])
def transfer_license(req: TransferRequest):
    """Réinitialise le machine_id pour permettre l'activation sur un autre PC."""
    key = lg.normalize_key(req.license_key)
    row = db.get_license(key)
    if not row:
        raise HTTPException(status_code=404, detail="Licence introuvable")
    db.reset_machine_id(key)
    return {"license_key": key, "status": "transferred",
            "message": "Machine ID réinitialisé — le client peut s'activer sur un nouveau PC"}


@app.get("/licenses/{license_key}/history", dependencies=[Depends(_require_admin)])
def get_history(license_key: str, limit: int = 50):
    """Retourne l'historique des vérifications pour une licence."""
    key = lg.normalize_key(license_key)
    row = db.get_license(key)
    if not row:
        raise HTTPException(status_code=404, detail="Licence introuvable")
    return db.get_check_history(key, limit)


# ── Routes Client ─────────────────────────────────────────────────────────────

@app.post("/activate")
def activate(req: ActivateRequest):
    """
    Activation d'une clé par le logiciel client.
    Règles :
      - Clé doit exister, ne pas être bloquée/expirée
      - Si déjà activée sur un autre PC → refus
      - Si même PC (ou non encore activée) → succès + token JWT
    """
    key = lg.normalize_key(req.license_key)

    if not lg.is_valid_format(key):
        raise HTTPException(status_code=400, detail="Format de clé invalide")

    row = db.get_license(key)
    if not row:
        raise HTTPException(status_code=404, detail="Clé de licence introuvable")

    if row["status"] == "blocked":
        raise HTTPException(status_code=403, detail="Cette licence a été bloquée")

    if db.is_expired(row["expires_at"]):
        db.set_status(key, "expired")
        raise HTTPException(status_code=403, detail="Cette licence a expiré")

    # Vérifier si déjà activée sur un autre PC
    if row["machine_id"] and row["machine_id"] != req.machine_id:
        raise HTTPException(
            status_code=409,
            detail="Cette clé est déjà activée sur un autre ordinateur. "
                   "Contactez le support pour transférer votre licence."
        )

    # Activer (ou reconfirmer l'activation)
    db.activate_license(key, req.machine_id, _now_iso())

    token = _make_token(key, req.machine_id, row["expires_at"], row["type"])
    return {
        "status":      "activated",
        "license_key": key,
        "type":        row["type"],
        "expires_at":  row["expires_at"],
        "client_name": row["client_name"],
        "token":       token,
    }


@app.post("/verify")
def verify(req: VerifyRequest):
    """
    Vérification périodique du token (appelée au démarrage du logiciel).
    Renouvelle le token si valide.

    Politique de tolérance :
    - Si le JWT est valide → vérification normale
    - Si le JWT est expiré ou invalide (ex: redéploiement serveur avec nouveau secret)
      → fallback sur vérification BDD via license_key + machine_id
      → si la licence est valide en BDD → émet un nouveau token (auto-renewal)
    """
    key = lg.normalize_key(req.license_key)

    # Vérifier le JWT — tolérant aux expirations et tokens invalides
    jwt_machine_id = None
    try:
        payload = jwt.decode(req.token, JWT_SECRET, algorithms=[JWT_ALGO])
        jwt_machine_id = payload.get("machine_id")
        # JWT valide : vérifier que le machine_id correspond
        if jwt_machine_id and jwt_machine_id != req.machine_id:
            raise HTTPException(status_code=403, detail="Token lié à un autre PC")
    except jwt.ExpiredSignatureError:
        # Token expiré → fallback BDD (ne pas rejeter, renouveler si licence OK)
        pass
    except jwt.InvalidTokenError:
        # Token invalide (ex: JWT_SECRET changé après redéploiement) → fallback BDD
        pass

    # Vérifier la BDD (source de vérité ultime)
    row = db.get_license(key)
    if not row:
        raise HTTPException(status_code=404, detail="Licence introuvable")
    if row["status"] == "blocked":
        raise HTTPException(status_code=403, detail="Licence bloquée")
    if db.is_expired(row["expires_at"]):
        db.set_status(key, "expired")
        raise HTTPException(status_code=403, detail="Licence expirée")

    # Vérifier que le machine_id correspond à celui enregistré en BDD
    # (protection contre réutilisation d'une clé sur un autre PC)
    if row.get("machine_id") and row["machine_id"] != req.machine_id:
        raise HTTPException(status_code=403, detail="Licence activée sur un autre PC")

    now = _now_iso()
    db.update_last_check(key, now)
    db.add_check_history(key, req.machine_id, now, "valid")
    # Émet toujours un nouveau token frais (renouvellement automatique)
    new_token = _make_token(key, req.machine_id, row["expires_at"], row["type"])
    return {
        "status":      "valid",
        "license_key": key,
        "type":        row["type"],
        "expires_at":  row["expires_at"],
        "client_name": row.get("client_name", ""),
        "token":       new_token,
    }


# ── Authentification Admin ────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    """Page de connexion admin."""
    # Si déjà connecté → rediriger vers le dashboard
    session = request.cookies.get(SESSION_COOKIE)
    if _check_session(session):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html",
                                      {"request": request, "error": error})


@app.post("/login")
def login_submit(request: Request, password: str = Form(...)):
    """Vérifie le mot de passe admin et crée la session."""
    if password != ADMIN_API_KEY:
        return templates.TemplateResponse(
            "login.html",
            {"request": request,
             "error": "Mot de passe incorrect. Réessayez."},
            status_code=401,
        )
    token = _make_session_token()
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,          # inaccessible depuis JavaScript
        samesite="lax",
        max_age=SESSION_TTL_H * 3600,
    )
    return response


@app.get("/logout")
def logout():
    """Déconnexion : supprime le cookie de session."""
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ── Dashboard Admin (HTML) ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request,
              admin_session: Optional[str] = Cookie(None)):
    """Sert le dashboard admin (session obligatoire)."""
    if not _check_session(admin_session):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("dashboard.html",
                                      {"request": request,
                                       "admin_key": ADMIN_API_KEY})


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    db_url = (os.environ.get("DATABASE_URL", "")
              or os.environ.get("DATABASE_PUBLIC_URL", "")
              or os.environ.get("POSTGRES_URL", ""))
    return {
        "status":     "ok",
        "version":    "1.0.0",
        "db_backend": "postgresql" if db_url.startswith("postgres") else "sqlite",
        "db_url_set": bool(db_url),
        "db_url_prefix": db_url[:20] + "..." if db_url else "non définie",
        "env_vars_pg": [k for k in ("DATABASE_URL","DATABASE_PUBLIC_URL","POSTGRES_URL")
                        if os.environ.get(k)],
    }
