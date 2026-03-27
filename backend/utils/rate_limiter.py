"""Route-scoped rate limiting (in-memory). Use Redis for multi-instance parity."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self) -> None:
        self.attempts: Dict[str, List[datetime]] = {}
        self._lock = asyncio.Lock()

    def _prune(self, key: str, window_minutes: int) -> None:
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=window_minutes)
        if key not in self.attempts:
            self.attempts[key] = []
            return
        self.attempts[key] = [ts for ts in self.attempts[key] if now - ts < window]

    async def peek_blocked(
        self,
        key: str,
        max_attempts: int,
        window_minutes: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Return (blocked, error_message) without recording a new hit.
        blocked=True means limit already reached.
        """
        async with self._lock:
            self._prune(key, window_minutes)
            now = datetime.now(timezone.utc)
            window = timedelta(minutes=window_minutes)
            bucket = self.attempts.get(key, [])
            if len(bucket) >= max_attempts:
                oldest = min(bucket)
                wait_until = oldest + window
                wait_seconds = max(0, int((wait_until - now).total_seconds()))
                return True, f"Rate limit exceeded. Try again in {wait_seconds} seconds."
            return False, None

    async def record_hit(self, key: str, window_minutes: int) -> None:
        """Record one consumption against key (e.g. failed login)."""
        async with self._lock:
            self._prune(key, window_minutes)
            if key not in self.attempts:
                self.attempts[key] = []
            self.attempts[key].append(datetime.now(timezone.utc))

    async def clear_key(self, key: str) -> None:
        """Clear tracked attempts for a single key."""
        async with self._lock:
            self.attempts.pop(key, None)

    async def check_rate_limit(
        self,
        key: str,
        max_attempts: int,
        window_minutes: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Classic check: if under cap, record one hit and allow; else deny.
        Use for endpoints where each call should count (forgot-password, forms).
        """
        async with self._lock:
            self._prune(key, window_minutes)
            now = datetime.now(timezone.utc)
            window = timedelta(minutes=window_minutes)
            bucket = self.attempts.setdefault(key, [])
            if len(bucket) >= max_attempts:
                oldest = min(bucket)
                wait_until = oldest + window
                wait_seconds = max(0, int((wait_until - now).total_seconds()))
                return False, f"Rate limit exceeded. Try again in {wait_seconds} seconds."
            bucket.append(now)
            return True, None

    async def check_rate_limit_daily(
        self,
        key: str,
        max_attempts: int,
    ) -> Tuple[bool, Optional[str]]:
        """Per-day rate limit. Window = 24 hours."""
        return await self.check_rate_limit(
            key=key,
            max_attempts=max_attempts,
            window_minutes=24 * 60,
        )


rate_limiter = RateLimiter()


def log_rate_limit_event(scope: str, key_suffix: str, ip: Optional[str] = None) -> None:
    """Structured log for observability (SIEM-friendly)."""
    logger.warning(
        "security.rate_limit scope=%s key_suffix=%s ip=%s",
        scope,
        key_suffix,
        ip or "-",
    )
