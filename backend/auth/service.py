"""
backend/auth/service.py
=======================
Cryptographic hashing, user account registration, password verification,
secure session lifecycle management, and password resets using bcrypt.
"""

from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import bcrypt

from backend.auth.db import get_db_connection, init_auth_db
from backend.auth.models import UserResponse

logger = logging.getLogger("privsight.auth")


class AuthService:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path
        init_auth_db(self.db_path)

    def _conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    # -------------------------------------------------------------------------
    # Password Hashing & Verification via Bcrypt
    # -------------------------------------------------------------------------
    @staticmethod
    def hash_password(password: str) -> str:
        """Hashes password using bcrypt with salt rounds = 12."""
        salt = bcrypt.gensalt(rounds=12)
        hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed_bytes.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verifies plain password against stored bcrypt hash."""
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception as e:
            logger.warning("Password verification error: %s", e)
            return False

    # -------------------------------------------------------------------------
    # User Registration & Retrieval
    # -------------------------------------------------------------------------
    def register_user(self, full_name: str, email: str, password: str) -> UserResponse:
        """
        Registers a new user with verified email uniqueness and bcrypt password hash.
        Raises ValueError if user already exists or inputs fail validation.
        """
        clean_email = email.strip().lower()
        clean_name = full_name.strip()

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        conn = self._conn()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (clean_email,))
                if cursor.fetchone() is not None:
                    raise ValueError("An account with this email address already exists.")

                pwd_hash = self.hash_password(password)
                now_iso = datetime.now(timezone.utc).isoformat()

                cursor.execute(
                    """
                    INSERT INTO users (email, full_name, password_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (clean_email, clean_name, pwd_hash, now_iso, now_iso),
                )
                user_id = cursor.lastrowid
                return UserResponse(
                    id=user_id,
                    email=clean_email,
                    full_name=clean_name,
                    created_at=now_iso,
                )
        finally:
            conn.close()

    def authenticate_user(self, email: str, password: str) -> Optional[UserResponse]:
        """
        Verifies user credentials.
        Returns UserResponse on success, or None on invalid credentials.
        """
        clean_email = email.strip().lower()
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, email, full_name, password_hash, created_at FROM users WHERE email = ? COLLATE NOCASE",
                (clean_email,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            user_id = row["id"]
            db_email = row["email"]
            name = row["full_name"]
            pwd_hash = row["password_hash"]
            created_at = row["created_at"]

            if not self.verify_password(password, pwd_hash):
                return None

            return UserResponse(
                id=user_id,
                email=db_email,
                full_name=name,
                created_at=created_at,
            )
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Secure Session Management
    # -------------------------------------------------------------------------
    def create_session(
        self,
        user_id: int,
        remember_me: bool = False,
        old_token: Optional[str] = None,
    ) -> Tuple[str, datetime, int]:
        """
        Creates a persistent session token with session regeneration.
        Token is a 32-byte cryptographically secure URL-safe string.
        Invalidates any previous session token passed as old_token.
        Returns: (token, expiry_datetime, max_age_seconds)
        """
        token = secrets.token_urlsafe(32)
        duration_days = 30 if remember_me else 1
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=duration_days)
        max_age_seconds = duration_days * 86400

        conn = self._conn()
        try:
            with conn:
                if old_token:
                    conn.execute("DELETE FROM sessions WHERE token = ?", (old_token,))
                conn.execute(
                    """
                    INSERT INTO sessions (token, user_id, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (token, user_id, now.isoformat(), expires_at.isoformat()),
                )
            return token, expires_at, max_age_seconds
        finally:
            conn.close()

    def get_user_by_session(self, token: Optional[str]) -> Optional[UserResponse]:
        """
        Validates session token. If valid and unexpired, returns UserResponse.
        Otherwise removes expired session and returns None.
        """
        if not token:
            return None

        conn = self._conn()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT u.id, u.email, u.full_name, u.created_at, s.expires_at
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ?
                """,
                (token,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            if row["expires_at"] <= now_iso:
                # Session has expired, clean up lazily
                with conn:
                    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                return None

            return UserResponse(
                id=row["id"],
                email=row["email"],
                full_name=row["full_name"],
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def destroy_session(self, token: Optional[str]) -> bool:
        """Invalidates a session token upon logout."""
        if not token:
            return False

        conn = self._conn()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Password Reset Flow with SMTP Support
    # -------------------------------------------------------------------------
    def create_password_reset(self, email: str) -> Tuple[Optional[str], bool]:
        """
        Generates a 1-hour valid password reset token for the given account.
        Dispatches email if SMTP credentials are provided, otherwise logs securely.
        Returns: (token_or_none, email_delivered_bool)
        """
        clean_email = email.strip().lower()
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (clean_email,))
            row = cursor.fetchone()
            if not row:
                return None, False

            user_id = row["id"]
            token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(hours=1)

            with conn:
                conn.execute(
                    """
                    INSERT INTO password_resets (token, user_id, created_at, expires_at, used)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (token, user_id, now.isoformat(), expires_at.isoformat()),
                )

            # Check if SMTP is configured
            smtp_host = os.getenv("SMTP_HOST")
            email_sent = False
            if smtp_host:
                try:
                    import smtplib
                    from email.message import EmailMessage

                    smtp_port = int(os.getenv("SMTP_PORT", "587"))
                    smtp_user = os.getenv("SMTP_USER", "")
                    smtp_pass = os.getenv("SMTP_PASSWORD", "")
                    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user or "security@privsight.io")
                    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

                    msg = EmailMessage()
                    msg["Subject"] = "PrivSight Password Reset Request"
                    msg["From"] = from_email
                    msg["To"] = clean_email
                    msg.set_content(
                        f"Hello,\n\nA password reset request was received for your PrivSight account.\n\n"
                        f"Your single-use password reset token is:\n{token}\n\n"
                        f"This token is valid for 1 hour. If you did not request this, please ignore this email.\n\n"
                        f"— PrivSight Security Team"
                    )

                    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                        if use_tls:
                            server.starttls()
                        if smtp_user and smtp_pass:
                            server.login(smtp_user, smtp_pass)
                        server.send_message(msg)
                    email_sent = True
                    logger.info("Password reset email delivered to %s", clean_email)
                except Exception as mail_err:
                    logger.error("SMTP delivery failed for %s: %s", clean_email, mail_err)
                    email_sent = False
            else:
                logger.info(
                    "Password reset token generated for user_id=%s. (Local dev mode: token=%s)",
                    user_id,
                    token,
                )

            return token, email_sent
        finally:
            conn.close()

    def reset_password(self, token: str, new_password: str) -> bool:
        """
        Resets user password if token is valid, unused, and not expired.
        Clears all active sessions for that user for security.
        """
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters long.")

        conn = self._conn()
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, expires_at, used
                FROM password_resets
                WHERE token = ?
                """,
                (token,),
            )
            row = cursor.fetchone()
            if not row or row["used"] == 1 or row["expires_at"] <= now_iso:
                return False

            user_id = row["user_id"]
            pwd_hash = self.hash_password(new_password)
            updated_at = now_iso

            with conn:
                cursor.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (pwd_hash, updated_at, user_id),
                )
                cursor.execute(
                    "UPDATE password_resets SET used = 1 WHERE token = ?",
                    (token,),
                )
                # Invalidate existing sessions for security
                cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            return True
        finally:
            conn.close()
