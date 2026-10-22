"""
backend/auth/rate_limiter.py
============================
Thread-safe in-memory rate limiter for authentication attempts.
Protects against brute-force and credential stuffing attacks.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Tuple


class LoginRateLimiter:
    """
    Tracks failed authentication attempts by (ip, normalized_email).
    Enforces maximum attempts within a sliding time window.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        # Key: (ip, email) -> List of timestamp floats
        self._attempts: Dict[Tuple[str, str], list[float]] = {}

    def _cleanup_old_attempts(self, now: float, timestamps: list[float]) -> list[float]:
        cutoff = now - self.window_seconds
        return [t for t in timestamps if t > cutoff]

    def is_rate_limited(self, ip: str, email: str) -> Tuple[bool, int]:
        """
        Checks whether the (ip, email) pair is currently rate-limited.
        Returns: (is_limited: bool, retry_after_seconds: int)
        """
        now = time.time()
        key = (ip.strip(), email.strip().lower())

        with self._lock:
            timestamps = self._attempts.get(key, [])
            valid_timestamps = self._cleanup_old_attempts(now, timestamps)
            self._attempts[key] = valid_timestamps

            if len(valid_timestamps) >= self.max_attempts:
                oldest = valid_timestamps[0]
                retry_after = max(1, int(self.window_seconds - (now - oldest)))
                return True, retry_after

            return False, 0

    def record_failure(self, ip: str, email: str) -> None:
        """Records a failed login attempt."""
        now = time.time()
        key = (ip.strip(), email.strip().lower())

        with self._lock:
            timestamps = self._attempts.get(key, [])
            valid_timestamps = self._cleanup_old_attempts(now, timestamps)
            valid_timestamps.append(now)
            self._attempts[key] = valid_timestamps

    def reset(self, ip: str, email: str) -> None:
        """Clears failure records upon successful authentication."""
        key = (ip.strip(), email.strip().lower())
        with self._lock:
            self._attempts.pop(key, None)


# Global rate limiter instance for auth endpoints
login_rate_limiter = LoginRateLimiter(max_attempts=5, window_seconds=300)
