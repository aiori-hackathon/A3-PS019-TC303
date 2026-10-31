"""
backend/auth/db.py
==================
Persistent SQLite storage for PrivSight user accounts, active sessions,
and password reset tokens.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_AUTH_DB_PATH = BASE_DIR / "data" / "users.db"


def get_db_path() -> Path:
    env_path = os.getenv("PRIVSIGHT_AUTH_DB")
    if env_path:
        return Path(env_path)
    if os.getenv("VERCEL"):
        # On Vercel serverless, /var/task is read-only; use /tmp
        tmp_db = Path("/tmp") / "users.db"
        if not tmp_db.exists() and DEFAULT_AUTH_DB_PATH.exists():
            import shutil
            try:
                shutil.copy2(DEFAULT_AUTH_DB_PATH, tmp_db)
            except Exception:
                pass
        return tmp_db
    return DEFAULT_AUTH_DB_PATH


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_path or get_db_path()
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        target_path = Path("/tmp") / target_path.name
        target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_auth_db(db_path: Optional[Path] = None) -> None:
    """Initializes tables and indexes for users, sessions, and password resets."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS password_resets (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    token TEXT PRIMARY KEY,
                    revoked_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
                """
            )

            # Auto-seed default production/demo accounts
            default_users = [
                (
                    "compliance@enterprise.com",
                    "Enterprise Compliance Lead",
                    "$2b$12$shP3Ck8lOQdqQ/Z8WFt28etI2Lq3wProZbppbdNjZAIqLBEWxraxm",
                ),
                (
                    "admin@privsight.io",
                    "System Administrator",
                    "$2b$12$shP3Ck8lOQdqQ/Z8WFt28etI2Lq3wProZbppbdNjZAIqLBEWxraxm",
                ),
                (
                    "test@example.com",
                    "Auditor Demo",
                    "$2b$12$shP3Ck8lOQdqQ/Z8WFt28etI2Lq3wProZbppbdNjZAIqLBEWxraxm",
                ),
            ]
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            for email, full_name, pwd_hash in default_users:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        INSERT INTO users (email, full_name, password_hash, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (email, full_name, pwd_hash, now_iso, now_iso),
                    )
    finally:
        conn.close()

