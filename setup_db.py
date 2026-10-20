"""Set up PostgreSQL for the Smart Waste-Bin project.

    python setup_db.py              # first time: roles, database, tables, permissions, data, first app admin
    python setup_db.py --reload     # only reload waste_readings from artifacts/waste_bin.db (after re-running the notebook)

Needs a .env file (copy .env.example) and artifacts/waste_bin.db created by the notebook.
"""
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql

import db

SQLITE_PATH = Path(__file__).parent / "artifacts" / "waste_bin.db"


def need(name):
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"Missing {name} in .env (see .env.example).")
    return value


def create_roles_and_database():
    dbname = os.environ.get("DB_NAME", "waste_bin")
    admin_user, admin_pw = os.environ.get("DB_ADMIN_USER", "waste_admin"), need("DB_ADMIN_PASSWORD")
    app_user, app_pw = os.environ.get("DB_APP_USER", "waste_app"), need("DB_APP_PASSWORD")

    with db.connect("super") as con:
        con.autocommit = True
        for name, pw in ((admin_user, admin_pw), (app_user, app_pw)):
            exists = con.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            con.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(name), sql.Literal(pw)))
            print(f"{'Updated' if exists else 'Created'} role {name}")
        if not con.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone():
            con.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(dbname), sql.Identifier(admin_user)))
            print(f"Created database {dbname} (owner {admin_user})")
        else:
            print(f"Database {dbname} already exists")
        con.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(dbname)))
        con.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname), sql.Identifier(app_user)))
    return dbname, admin_user, app_user


def create_tables_and_permissions(dbname, admin_user, app_user):
    with db.connect("super", dbname) as con:
        con.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(app_user)))
        con.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(admin_user)))      # tables are owned by waste_admin
        con.execute("""
            CREATE TABLE IF NOT EXISTS waste_readings (
                id BIGSERIAL PRIMARY KEY,
                sensor_id TEXT NOT NULL,
                ts TIMESTAMP NOT NULL,
                fill_pct DOUBLE PRECISION,
                weight_kg DOUBLE PRECISION,
                hours_since_collection DOUBLE PRECISION,
                avg_fill_rate DOUBLE PRECISION,
                hour SMALLINT,
                is_weekend SMALLINT,
                hours_to_full DOUBLE PRECISION)""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_waste_readings_ts ON waste_readings (ts)")
        con.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'viewer')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
        app = sql.Identifier(app_user)
        con.execute(sql.SQL("GRANT SELECT ON waste_readings TO {}").format(app))
        con.execute(sql.SQL("GRANT SELECT, INSERT ON app_users TO {}").format(app))
        con.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE app_users_id_seq TO {}").format(app))
    print("Tables and permissions ready")


def load_readings():
    if not SQLITE_PATH.exists():
        sys.exit("artifacts/waste_bin.db not found. Run the notebook first.")
    with sqlite3.connect(SQLITE_PATH) as lite:
        df = pd.read_sql("SELECT * FROM waste_readings", lite)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    rows = [(r.Sensor_ID, r.Timestamp.to_pydatetime(), float(r.fill_pct), float(r.weight_kg),
             float(r.hours_since_collection), float(r.avg_fill_rate), int(r.hour), int(r.is_weekend),
             float(r.hours_to_full)) for r in df.itertuples()]
    with db.connect("admin") as con:
        con.execute("TRUNCATE waste_readings RESTART IDENTITY")
        with con.cursor() as cur:
            cur.executemany("""INSERT INTO waste_readings (sensor_id, ts, fill_pct, weight_kg, hours_since_collection,
                               avg_fill_rate, hour, is_weekend, hours_to_full)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", rows)
        n = con.execute("SELECT COUNT(*) FROM waste_readings").fetchone()[0]
    print(f"Loaded {n} rows into waste_readings")


def create_first_admin():
    user, pw = need("APP_ADMIN_USER"), need("APP_ADMIN_PASSWORD")
    if len(pw) < 8:
        sys.exit("APP_ADMIN_PASSWORD must have at least 8 characters.")
    with db.connect("admin") as con:
        con.execute("""INSERT INTO app_users (username, password_hash, role) VALUES (%s, %s, 'admin')
                       ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash, role = 'admin'""",
                    (user, db.hash_password(pw)))
    print(f"App admin user '{user}' ready")


if __name__ == "__main__":
    try:
        if "--reload" in sys.argv:
            load_readings()
        else:
            names = create_roles_and_database()
            create_tables_and_permissions(*names)
            load_readings()
            create_first_admin()
            print("\nDone. Start the app with: streamlit run app.py")
    except psycopg.OperationalError as exc:
        sys.exit(f"Could not connect to PostgreSQL: {exc}\nIs the service running, and are the .env values right?")
