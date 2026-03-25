"""
Scoped read-only API keys for integrations (HTTP pull).

Secrets are stored as SHA-256 hashes only. Full token is shown once on create.
Entitlement: Professional webhooks (integrations bundle); enforced on management and on each data call.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "ple_read_"
COLLECTION = "client_read_api_keys"
DEFAULT_SCOPES = ["read:properties", "read:requirements", "read:tasks", "read:compliance"]
MAX_KEYS_PER_CLIENT = 10

SCOPE_PROPERTIES = "read:properties"
SCOPE_REQUIREMENTS = "read:requirements"
SCOPE_TASKS = "read:tasks"
SCOPE_COMPLIANCE = "read:compliance"


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def key_hint_from_token(plaintext: str) -> str:
    if not plaintext.startswith(TOKEN_PREFIX):
        return "****"
    tail = plaintext[len(TOKEN_PREFIX) :][-6:]
    return f"...{tail}"


async def create_key(
    client_id: str,
    portal_user_id: str,
    name: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    db = database.get_db()
    n = await db[COLLECTION].count_documents({"client_id": client_id, "revoked_at": None})
    if n >= MAX_KEYS_PER_CLIENT:
        raise ValueError("MAX_KEYS")
    raw = generate_token()
    th = hash_token(raw)
    key_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc: Dict[str, Any] = {
        "key_id": key_id,
        "client_id": client_id,
        "token_hash": th,
        "key_hint": key_hint_from_token(raw),
        "name": (name or "").strip() or "Read API key",
        "scopes": list(DEFAULT_SCOPES),
        "created_at": now,
        "created_by": portal_user_id,
        "last_used_at": None,
        "revoked_at": None,
    }
    await db[COLLECTION].insert_one(doc)
    safe = {k: v for k, v in doc.items() if k != "token_hash"}
    return raw, safe


async def list_keys(client_id: str) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = db[COLLECTION].find(
        {"client_id": client_id, "revoked_at": None},
        {"_id": 0, "token_hash": 0},
    ).sort("created_at", -1)
    return await cursor.to_list(50)


async def revoke_key(client_id: str, key_id: str) -> bool:
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    res = await db[COLLECTION].update_one(
        {"key_id": key_id, "client_id": client_id, "revoked_at": None},
        {"$set": {"revoked_at": now}},
    )
    return res.modified_count > 0


async def resolve_token(plaintext: str) -> Optional[Dict[str, Any]]:
    if not plaintext or not plaintext.startswith(TOKEN_PREFIX):
        return None
    th = hash_token(plaintext)
    db = database.get_db()
    doc = await db[COLLECTION].find_one({"token_hash": th})
    if not doc or doc.get("revoked_at"):
        return None
    now = datetime.now(timezone.utc).isoformat()
    await db[COLLECTION].update_one(
        {"key_id": doc["key_id"]},
        {"$set": {"last_used_at": now}},
    )
    scopes = doc.get("scopes") or list(DEFAULT_SCOPES)
    return {
        "client_id": doc["client_id"],
        "key_id": doc["key_id"],
        "scopes": scopes,
    }


def has_scope(ctx: Dict[str, Any], scope: str) -> bool:
    scopes = ctx.get("scopes") or []
    return scope in scopes
