"""PostgreSQL helpers for the Smart Waste-Bin project.

Two database roles are used:
  waste_admin : owns the database (full control). Used only for setup and by you in pgAdmin/psql.
  waste_app   : used by the Streamlit app. Can read waste_readings, and read/add rows in app_users.
App users (admin / viewer) live in the app_users table with salted PBKDF2 password hashes.
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from pathlib import Path

import psycopg

ITERATIONS = 200_000
ROLES = ("viewer", "admin")        # viewer first: it is the default choice in the app


def load_env(path=None):
    """Read KEY=VALUE lines from .env into os.environ (existing variables are not overwritten)."""
    path = Path(path or Path(__file__).parent / ".env")
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()


def load_streamlit_secrets():
    """On Streamlit Community Cloud the settings come from the app's Secrets, not from a .env file."""
    try:
        import streamlit as st
        for key, value in st.secrets.items():
            if isinstance(value, str):
                os.environ.setdefault(key, value)
    except Exception:
        pass


load_streamlit_secrets()


SQLITE_PATH = Path(__file__).parent / "artifacts" / "waste_bin.db"
_status_cache = {"at": 0.0, "value": None}


def hosted():
    """True when one DATABASE_URL (a cloud database) is used instead of local roles."""
    return bool(os.environ.get("DATABASE_URL"))


def connect(who="app", dbname=None):
    """who = 'app' | 'admin' | 'super' (super is only for setup_db.py)."""
    env = os.environ
    if hosted() and who != "super":
        return psycopg.connect(env["DATABASE_URL"], connect_timeout=10)
    if who == "super":
        user, password, name = env.get("PG_SUPERUSER", "postgres"), env.get("PG_SUPERPASS", ""), dbname or "postgres"
    elif who == "admin":
        user, password, name = env.get("DB_ADMIN_USER", "waste_admin"), env.get("DB_ADMIN_PASSWORD", ""), dbname or env.get("DB_NAME", "waste_bin")
    else:
        user, password, name = env.get("DB_APP_USER", "waste_app"), env.get("DB_APP_PASSWORD", ""), dbname or env.get("DB_NAME", "waste_bin")
    return psycopg.connect(host=env.get("DB_HOST", "localhost"), port=int(env.get("DB_PORT", "5432")),
                           dbname=name, user=user, password=password, connect_timeout=5)


# ---------- which database are we using? ----------
def _explain(exc):
    """A short, safe message for visitors. Never includes host names, addresses or passwords."""
    text = str(exc).lower()
    if "password authentication failed" in text or "authentication failed" in text:
        return "the database refused the user name or password."
    if "ssl" in text:
        return "the database requires SSL. Add ?sslmode=require to DATABASE_URL."
    if "does not exist" in text:
        return "the database name in the connection string does not exist."
    return "the database server could not be reached."


def status():
    """Return {'mode': 'postgres' | 'sqlite' | 'error', 'message': str}. Cached for 30 seconds.

    postgres : PostgreSQL works (DATABASE_URL in the cloud, or the local server on your PC)
    sqlite   : no PostgreSQL available, so the bundled read-only copy artifacts/waste_bin.db is used (demo mode)
    error    : a cloud DATABASE_URL is set but does not work (we do not hide that by falling back)
    """
    now = time.time()
    if _status_cache["value"] is not None and now - _status_cache["at"] < 30:
        return _status_cache["value"]
    try:
        connect("app").close()
        result = {"mode": "postgres", "message": ""}
    except Exception as exc:
        if hosted():
            result = {"mode": "error", "message": _explain(exc)}
        elif SQLITE_PATH.exists():
            result = {"mode": "sqlite", "message": ""}
        else:
            result = {"mode": "error", "message": "PostgreSQL is not running and artifacts/waste_bin.db was not found."}
    _status_cache.update(at=now, value=result)
    return result


def demo_login_configured():
    return bool(os.environ.get("APP_ADMIN_USER") and os.environ.get("APP_ADMIN_PASSWORD"))


def _sqlite():
    return sqlite3.connect(SQLITE_PATH.resolve().as_uri() + "?mode=ro", uri=True)      # read-only


# ---------- passwords ----------
def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


# ---------- app users ----------
def authenticate(username, password):
    """Return the user's role if the credentials are right, otherwise None."""
    if status()["mode"] == "sqlite":                      # demo mode: one admin login from Secrets / .env
        expected_user = os.environ.get("APP_ADMIN_USER", "")
        expected_pw = os.environ.get("APP_ADMIN_PASSWORD", "")
        ok_user = hmac.compare_digest(username.encode(), expected_user.encode())
        ok_pw = hmac.compare_digest(password.encode(), expected_pw.encode())
        return "admin" if (expected_user and expected_pw and ok_user and ok_pw) else None
    with connect("app") as con:
        row = con.execute("SELECT password_hash, role FROM app_users WHERE username = %s", (username,)).fetchone()
    if row is None:
        hash_password(password)           # similar work for unknown users
        return None
    return row[1] if verify_password(password, row[0]) else None


def create_user(username, password, role="viewer"):
    if status()["mode"] != "postgres":
        raise ValueError("Creating users needs PostgreSQL (not available in demo mode).")
    if role not in ROLES:
        raise ValueError("Role must be 'admin' or 'viewer'.")
    if len(username) < 3 or len(password) < 8:
        raise ValueError("Username needs 3+ characters and the password 8+ characters.")
    try:
        with connect("app") as con:
            con.execute("INSERT INTO app_users (username, password_hash, role) VALUES (%s, %s, %s)",
                        (username, hash_password(password), role))
    except psycopg.errors.UniqueViolation:
        raise ValueError(f"The username '{username}' already exists.") from None


def list_users():
    if status()["mode"] != "postgres":
        return []
    with connect("app") as con:
        return con.execute("SELECT username, role, created_at FROM app_users ORDER BY id").fetchall()


# ---------- readings ----------
READING_COLUMNS = ["sensor_id", "ts", "fill_pct", "weight_kg", "hours_since_collection",
                   "avg_fill_rate", "hour", "is_weekend", "hours_to_full"]


def count_readings():
    if status()["mode"] == "sqlite":
        with _sqlite() as con:
            return con.execute("SELECT COUNT(*) FROM waste_readings").fetchone()[0]
    with connect("app") as con:
        return con.execute("SELECT COUNT(*) FROM waste_readings").fetchone()[0]


def fetch_readings(limit=None):
    if status()["mode"] == "sqlite":
        sql = ("SELECT Sensor_ID AS sensor_id, Timestamp AS ts, fill_pct, weight_kg, hours_since_collection, "
               "avg_fill_rate, hour, is_weekend, hours_to_full FROM waste_readings ORDER BY Timestamp")
        params = ()
        if limit:
            sql += " LIMIT ?"
            params = (int(limit),)
        with _sqlite() as con:
            return con.execute(sql, params).fetchall()
    sql = f"SELECT {', '.join(READING_COLUMNS)} FROM waste_readings ORDER BY ts"
    params = ()
    if limit:
        sql += " LIMIT %s"
        params = (int(limit),)
    with connect("app") as con:
        return con.execute(sql, params).fetchall()
