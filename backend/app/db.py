
import sqlite3
from contextlib import contextmanager
from threading import local
from .config import DB_PATH

_local = local()

# Migration guards — only nullable columns or columns with defaults are safe for ALTER TABLE ADD COLUMN
_USER_NEW_COLUMNS = [
    ("phone",                      "TEXT"),
    ("designation",                "TEXT"),
    ("region",                     "TEXT"),
    ("city",                       "TEXT"),
    ("is_active",                  "INTEGER DEFAULT 1"),
    ("total_interactions_logged",  "INTEGER DEFAULT 0"),
    ("last_active_at",             "TIMESTAMP"),
    ("updated_at",                 "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
]

_INTERACTION_NEW_COLUMNS = [
    ("user_id",             "INTEGER"),
    ("interaction_type",    "TEXT DEFAULT 'call'"),   # NOT NULL removed — invalid in ALTER TABLE
    ("interaction_channel", "TEXT"),
    ("interaction_date",    "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("raw_input",           "TEXT"),
    ("ai_summary",          "TEXT"),
    ("ai_entities",         "TEXT"),
    ("sentiment",           "TEXT"),
    ("product_discussed",   "TEXT"),
    ("outcome",             "TEXT"),
    ("follow_up_required",  "INTEGER DEFAULT 0"),
    ("follow_up_date",      "TIMESTAMP"),
    ("updated_at",          "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
]

_HCP_NEW_COLUMNS = [
    ("specialty",             "TEXT"),
    ("sub_specialty",         "TEXT"),
    ("qualification",         "TEXT"),
    ("organization",          "TEXT"),
    ("department",            "TEXT"),
    ("phone",                 "TEXT"),
    ("email",                 "TEXT"),
    ("city",                  "TEXT"),
    ("state",                 "TEXT"),
    ("country",               "TEXT DEFAULT 'India'"),
    ("normalized_name",       "TEXT"),
    ("engagement_score",      "REAL DEFAULT 0"),
    ("total_interactions",    "INTEGER DEFAULT 0"),
    ("last_interaction_date", "TIMESTAMP"),
    ("priority",              "TEXT DEFAULT 'medium'"),
    ("status",                "TEXT DEFAULT 'active'"),
    ("created_by",            "TEXT"),
    ("updated_at",            "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
]


def _new_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_connection() as conn:
        # Run migration guards FIRST so existing tables get new columns
        # before any CREATE INDEX statements reference them
        for table, columns in [
            ("users",        _USER_NEW_COLUMNS),
            ("hcps",         _HCP_NEW_COLUMNS),
            ("interactions", _INTERACTION_NEW_COLUMNS),
        ]:
            # Table may not exist yet on first run — PRAGMA returns empty, that's fine
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for col, col_type in columns:
                if col not in existing and existing:  # only ALTER if table exists
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        conn.commit()

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                name                      TEXT    NOT NULL,
                email                     TEXT    NOT NULL UNIQUE,
                phone                     TEXT,
                role                      TEXT    NOT NULL DEFAULT 'sales_rep',
                designation               TEXT,
                region                    TEXT,
                city                      TEXT,
                password_hash             TEXT,
                is_active                 INTEGER DEFAULT 1,
                total_interactions_logged INTEGER DEFAULT 0,
                last_active_at            TIMESTAMP,
                created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
                ON users(email COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_users_role   ON users(role);
            CREATE INDEX IF NOT EXISTS idx_users_region ON users(region);

            CREATE TABLE IF NOT EXISTS hcps (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                name                  TEXT    NOT NULL COLLATE NOCASE,
                specialty             TEXT,
                sub_specialty         TEXT,
                qualification         TEXT,
                organization          TEXT,
                department            TEXT,
                phone                 TEXT,
                email                 TEXT    UNIQUE,
                city                  TEXT,
                state                 TEXT,
                country               TEXT    DEFAULT 'India',
                normalized_name       TEXT    UNIQUE,
                engagement_score      REAL    DEFAULT 0,
                total_interactions    INTEGER DEFAULT 0,
                last_interaction_date TIMESTAMP,
                priority              TEXT    DEFAULT 'medium',
                status                TEXT    DEFAULT 'active',
                created_by            TEXT,
                created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_hcps_name
                ON hcps(name COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS interactions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                hcp_id              INTEGER   NOT NULL,
                user_id             INTEGER,
                interaction_type    TEXT      NOT NULL DEFAULT 'call',
                interaction_channel TEXT,
                interaction_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes               TEXT      NOT NULL,
                raw_input           TEXT,
                ai_summary          TEXT,
                ai_entities         TEXT,
                sentiment           TEXT,
                product_discussed   TEXT,
                outcome             TEXT,
                follow_up_required  INTEGER   DEFAULT 0,
                follow_up_date      TIMESTAMP,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(hcp_id)  REFERENCES hcps(id)  ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_interactions_hcp_id  ON interactions(hcp_id);
            CREATE INDEX IF NOT EXISTS idx_interactions_user_id ON interactions(user_id);
            CREATE INDEX IF NOT EXISTS idx_interactions_date    ON interactions(interaction_date);
            CREATE INDEX IF NOT EXISTS idx_interactions_followup ON interactions(follow_up_required, follow_up_date);

            CREATE TABLE IF NOT EXISTS interaction_metadata (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                interaction_id   INTEGER NOT NULL,
                key              TEXT    NOT NULL,
                value            TEXT,
                value_type       TEXT    DEFAULT 'string',
                source           TEXT    DEFAULT 'llm',
                confidence_score REAL,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(interaction_id) REFERENCES interactions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_metadata_interaction_id ON interaction_metadata(interaction_id);
            CREATE INDEX IF NOT EXISTS idx_metadata_key            ON interaction_metadata(key);
            CREATE INDEX IF NOT EXISTS idx_metadata_source         ON interaction_metadata(source);

            CREATE TABLE IF NOT EXISTS tags (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                category    TEXT,
                description TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_name     ON tags(name COLLATE NOCASE);
            CREATE INDEX        IF NOT EXISTS idx_tags_category ON tags(category);

            CREATE TABLE IF NOT EXISTS hcp_tags (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                hcp_id           INTEGER NOT NULL,
                tag_id           INTEGER NOT NULL,
                confidence_score REAL,
                source           TEXT    DEFAULT 'llm',
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(hcp_id) REFERENCES hcps(id) ON DELETE CASCADE,
                FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                UNIQUE(hcp_id, tag_id)
            );

            CREATE INDEX IF NOT EXISTS idx_hcp_tags_hcp_id ON hcp_tags(hcp_id);
            CREATE INDEX IF NOT EXISTS idx_hcp_tags_tag_id ON hcp_tags(tag_id);

            CREATE TABLE IF NOT EXISTS appointments (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                hcp_id         INTEGER NOT NULL,
                date           TEXT    NOT NULL,
                time           TEXT    NOT NULL,
                status         TEXT    DEFAULT 'scheduled',
                notes          TEXT,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(hcp_id) REFERENCES hcps(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_appointments_hcp_date ON appointments(hcp_id, date);
        """)

        # Second pass: add any columns still missing after table creation
        for table, columns in [
            ("users",        _USER_NEW_COLUMNS),
            ("hcps",         _HCP_NEW_COLUMNS),
            ("interactions", _INTERACTION_NEW_COLUMNS),
        ]:
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for col, col_type in columns:
                if col not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        conn.commit()


@contextmanager
def get_connection() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _new_connection()
        _local.conn = conn
    else:
        try:
            conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            conn = _new_connection()
            _local.conn = conn
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise

# init_db() is NOT called here — called once via lifespan in main.py
# Calling it at import time causes race conditions with multiple gunicorn workers
