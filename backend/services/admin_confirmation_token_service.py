"""Short-lived, action-bound admin confirmation tokens (non-reusable)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status

from database import database

COLLECTION = "admin_confirmation_tokens"
TTL_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_admin_confirmation_token(
    user_id: str,
    action_id: str,
    *,
    resource_key: Optional[str] = None,
    reason: str = "",
) -> str:
    db = database.get_db()
    token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(seconds=TTL_SECONDS)
    await db[COLLECTION].insert_one(
        {
            "token_hash": _hash_token(token),
            "user_id": user_id,
            "action_id": action_id,
            "resource_key": (resource_key or "").strip() or None,
            "reason": (reason or "").strip() or None,
            "expires_at": expires_at,
            "consumed_at": None,
            "created_at": _now(),
        }
    )
    return token


async def consume_admin_confirmation_token(
    token: str,
    user_id: str,
    action_id: str,
    *,
    resource_key: Optional[str] = None,
) -> None:
    trimmed = (token or "").strip()
    if not trimmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin confirmation token required for this action.",
        )
    db = database.get_db()
    doc = await db[COLLECTION].find_one({"token_hash": _hash_token(trimmed), "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired admin confirmation token.",
        )
    if doc.get("action_id") != action_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirmation token is not valid for this action.",
        )
    expected_resource = (resource_key or "").strip() or None
    stored_resource = doc.get("resource_key")
    if stored_resource and expected_resource and stored_resource != expected_resource:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirmation token is not valid for this resource.",
        )
    expires_at = doc.get("expires_at")
    if expires_at and isinstance(expires_at, datetime):
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if exp < _now():
            await db[COLLECTION].delete_one({"token_hash": _hash_token(trimmed)})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin confirmation token expired.",
            )
    if doc.get("consumed_at"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin confirmation token already used.",
        )
    await db[COLLECTION].update_one(
        {"token_hash": _hash_token(trimmed)},
        {"$set": {"consumed_at": _now()}},
    )
