"""
Couche base de données — Métraplan License Server
==================================================
Supporte deux backends selon la variable DATABASE_URL :

  • SQLite   (défaut, Railway, développement local)
      → DATABASE_URL absent ou vide
  • PostgreSQL (Render free tier, tout service managé)
      → DATABASE_URL=postgresql://user:pass@host:5432/dbname

Le reste du code est identique ; seuls les connecteurs et
les marqueurs de paramètre (?  vs  %s) changent.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, List, Optional

# ── Détection du backend ──────────────────────────────────────────────────────

import logging as _logging
_db_log = _logging.getLogger("metraplan.database")

# Essayer DATABASE_URL puis DATABASE_PUBLIC_URL (Railway interne vs externe)
DATABASE_URL: str = (
    os.environ.get("DATABASE_URL", "")
    or os.environ.get("DATABASE_PUBLIC_URL", "")
    or os.environ.get("POSTGRES_URL", "")
)
_IS_PG: bool = DATABASE_URL.startswith("postgres")
_P: str = "%s" if _IS_PG else "?"          # marqueur de paramètre SQL
_SQLITE_PATH = Path(__file__).parent / "licenses.db"

_db_log.info(f"database.py chargé — backend={'PostgreSQL' if _IS_PG else 'SQLite'} — URL présente={bool(DATABASE_URL)}")

# ── DDL ───────────────────────────────────────────────────────────────────────

_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS licenses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key   TEXT    NOT NULL UNIQUE,
    client_name   TEXT    NOT NULL,
    client_email  TEXT    DEFAULT '',
    type          TEXT    NOT NULL DEFAULT 'standard',
    duration_days INTEGER NOT NULL DEFAULT 365,
    created_at    TEXT    NOT NULL,
    expires_at    TEXT    NOT NULL,
    machine_id    TEXT    DEFAULT NULL,
    status        TEXT    NOT NULL DEFAULT 'inactive',
    last_check    TEXT    DEFAULT NULL,
    notes         TEXT    DEFAULT ''
);
"""

_DDL_HISTORY_SQLITE = """
CREATE TABLE IF NOT EXISTS check_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key   TEXT    NOT NULL,
    checked_at    TEXT    NOT NULL,
    machine_id    TEXT    DEFAULT NULL,
    result        TEXT    NOT NULL DEFAULT 'valid',
    FOREIGN KEY (license_key) REFERENCES licenses(license_key)
);
"""

_DDL_PG = """
CREATE TABLE IF NOT EXISTS licenses (
    id            SERIAL PRIMARY KEY,
    license_key   TEXT    NOT NULL UNIQUE,
    client_name   TEXT    NOT NULL,
    client_email  TEXT    DEFAULT '',
    type          TEXT    NOT NULL DEFAULT 'standard',
    duration_days INTEGER NOT NULL DEFAULT 365,
    created_at    TEXT    NOT NULL,
    expires_at    TEXT    NOT NULL,
    machine_id    TEXT    DEFAULT NULL,
    status        TEXT    NOT NULL DEFAULT 'inactive',
    last_check    TEXT    DEFAULT NULL,
    notes         TEXT    DEFAULT ''
);
"""

_DDL_HISTORY_PG = """
CREATE TABLE IF NOT EXISTS check_history (
    id            SERIAL PRIMARY KEY,
    license_key   TEXT    NOT NULL,
    checked_at    TEXT    NOT NULL,
    machine_id    TEXT    DEFAULT NULL,
    result        TEXT    NOT NULL DEFAULT 'valid'
);
"""


# ── Connexion ─────────────────────────────────────────────────────────────────

@contextmanager
def get_db() -> Generator[Any, None, None]:
    """Fournit une connexion transactionnelle (SQLite ou PostgreSQL)."""
    if _IS_PG:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(str(_SQLITE_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _exec(conn, sql: str, params: tuple = ()) -> Any:
    """Exécute une requête et retourne le curseur."""
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def _row_to_dict(row) -> Optional[dict]:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)                 # psycopg2 RealDictRow
    return dict(row)                     # sqlite3.Row


# ── Initialisation ────────────────────────────────────────────────────────────

def init_db() -> None:
    """Crée les tables si elles n'existent pas encore."""
    ddl         = _DDL_PG          if _IS_PG else _DDL_SQLITE
    ddl_history = _DDL_HISTORY_PG  if _IS_PG else _DDL_HISTORY_SQLITE
    with get_db() as conn:
        _exec(conn, ddl)
        _exec(conn, ddl_history)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def insert_license(key: str, client_name: str, client_email: str,
                   type_: str, duration_days: int,
                   created_at: str, expires_at: str,
                   notes: str = "") -> int:
    sql = f"""
        INSERT INTO licenses
            (license_key, client_name, client_email, type, duration_days,
             created_at, expires_at, status, notes)
        VALUES ({_P},{_P},{_P},{_P},{_P},{_P},{_P},'inactive',{_P})
    """
    params = (key, client_name, client_email, type_, duration_days,
              created_at, expires_at, notes)
    with get_db() as conn:
        if _IS_PG:
            cur = _exec(conn, sql + " RETURNING id", params)
            row = cur.fetchone()
            return row["id"] if row else -1
        else:
            cur = _exec(conn, sql, params)
            return cur.lastrowid


def get_license(key: str) -> Optional[dict]:
    with get_db() as conn:
        cur = _exec(conn, f"SELECT * FROM licenses WHERE license_key = {_P}", (key,))
        return _row_to_dict(cur.fetchone())


def activate_license(key: str, machine_id: str, last_check: str) -> None:
    sql = (f"UPDATE licenses "
           f"SET machine_id={_P}, status='active', last_check={_P} "
           f"WHERE license_key={_P}")
    with get_db() as conn:
        _exec(conn, sql, (machine_id, last_check, key))


def update_last_check(key: str, last_check: str) -> None:
    with get_db() as conn:
        _exec(conn, f"UPDATE licenses SET last_check={_P} WHERE license_key={_P}",
              (last_check, key))


def set_status(key: str, status: str) -> None:
    with get_db() as conn:
        _exec(conn, f"UPDATE licenses SET status={_P} WHERE license_key={_P}",
              (status, key))


def get_all_licenses() -> List[dict]:
    with get_db() as conn:
        cur = _exec(conn, "SELECT * FROM licenses ORDER BY created_at DESC")
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]


def is_expired(expires_at: str) -> bool:
    try:
        exp = datetime.fromisoformat(expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp
    except Exception:
        return True


def update_license(key: str, client_name: str, client_email: str,
                   type_: str, expires_at: str, notes: str) -> None:
    """Modifie les informations d'une licence existante."""
    sql = (f"UPDATE licenses "
           f"SET client_name={_P}, client_email={_P}, type={_P}, "
           f"    expires_at={_P}, notes={_P} "
           f"WHERE license_key={_P}")
    with get_db() as conn:
        _exec(conn, sql, (client_name, client_email, type_, expires_at, notes, key))


def reset_machine_id(key: str) -> None:
    """Réinitialise le machine_id pour permettre l'activation sur un autre PC."""
    sql = (f"UPDATE licenses "
           f"SET machine_id=NULL, status='inactive' "
           f"WHERE license_key={_P}")
    with get_db() as conn:
        _exec(conn, sql, (key,))


def add_check_history(key: str, machine_id: str, checked_at: str,
                      result: str = "valid") -> None:
    """Enregistre une vérification dans l'historique."""
    sql = (f"INSERT INTO check_history (license_key, machine_id, checked_at, result) "
           f"VALUES ({_P},{_P},{_P},{_P})")
    with get_db() as conn:
        _exec(conn, sql, (key, machine_id, checked_at, result))


def get_check_history(key: str, limit: int = 50) -> List[dict]:
    """Retourne les N dernières vérifications pour une clé donnée."""
    sql = (f"SELECT * FROM check_history WHERE license_key={_P} "
           f"ORDER BY checked_at DESC LIMIT {_P}")
    with get_db() as conn:
        cur = _exec(conn, sql, (key, limit))
        return [_row_to_dict(r) for r in cur.fetchall()]
