"""Canonical client email identity (single source for duplicate checks and persistence).

Business rule: at most one *active* onboarding or provisioned identity per logical email.
Released stranded attempts may retain the email in historical fields and must not block
fresh registration. MongoDB's unique index on ``email`` is case-sensitive; application
code canonicalises on write and matches legacy rows with case/whitespace-tolerant lookup.
"""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

DuplicateKind = Literal["email", "customer_reference", "client_id", "other"]

# Intake + live check UX: single user-facing string for duplicate identity (matches submit + check-email).
INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE = "An account with this email already exists"

ONBOARDING_IDENTITY_ACTIVE = "ACTIVE"
ONBOARDING_IDENTITY_RELEASED = "RELEASED_FOR_RESTART"


def canonical_client_email(email: str | None) -> str:
    """Normalise email for storage and duplicate detection: strip outer whitespace, lower()."""
    if email is None:
        return ""
    return str(email).strip().lower()


def is_released_onboarding_identity(doc: Optional[dict[str, Any]]) -> bool:
    if not doc:
        return False
    status = str(doc.get("onboarding_identity_status") or "").strip().upper()
    return status == ONBOARDING_IDENTITY_RELEASED


def _identity_projection() -> dict[str, int]:
    return {"_id": 1, "client_id": 1, "onboarding_identity_status": 1}


async def client_email_taken(db: Any, email: str | None) -> bool:
    """True if an *active* client or portal identity already uses this canonical email."""
    canonical = canonical_client_email(email)
    if not canonical:
        return False
    doc = await db.clients.find_one({"email": canonical}, _identity_projection())
    if doc and not is_released_onboarding_identity(doc):
        return True
    # Legacy rows where ``email`` was stored without normalisation (case / surrounding spaces).
    existing = await db.clients.find_one(
        {
            "$expr": {
                "$eq": [
                    {"$toLower": {"$trim": {"input": {"$ifNull": ["$email", ""]}}}},
                    canonical,
                ]
            }
        },
        _identity_projection(),
    )
    if existing and not is_released_onboarding_identity(existing):
        return True

    portal_users = getattr(db, "portal_users", None)
    if portal_users is None:
        return False
    pu = await portal_users.find_one(
        {"auth_email": canonical},
        {"_id": 1, "client_id": 1, "is_deleted": 1},
    )
    if not isinstance(pu, dict) or not pu:
        return False
    if pu.get("is_deleted"):
        return False
    client_id = (pu.get("client_id") or "").strip()
    if not client_id:
        return True
    owner = await db.clients.find_one({"client_id": client_id}, _identity_projection())
    return not is_released_onboarding_identity(owner)


async def find_latest_released_attempt_for_email(db: Any, email: str | None) -> Optional[dict[str, Any]]:
    """Most recent released stranded attempt for this email (historical, not uniqueness-blocking)."""
    canonical = canonical_client_email(email)
    if not canonical:
        return None
    query = {
        "onboarding_identity_status": ONBOARDING_IDENTITY_RELEASED,
        "$or": [
            {"released_canonical_email": canonical},
            {"email": canonical},
        ],
    }
    cursor = db.clients.find(query, {"_id": 0, "client_id": 1, "released_at": 1, "released_canonical_email": 1}).sort(
        "released_at", -1
    )
    rows = await cursor.to_list(1)
    return rows[0] if rows else None


def classify_clients_duplicate_key_error(err: BaseException) -> Optional[DuplicateKind]:
    """Classify pymongo DuplicateKeyError from ``clients.insert_one`` (code 11000)."""
    details: dict[str, Any] = getattr(err, "details", None) or {}
    code = details.get("code")
    if code is None and hasattr(err, "code"):
        code = getattr(err, "code", None)
    errmsg = (details.get("errmsg") or str(err)).lower()
    is_dup = code == 11000 or "e11000" in errmsg or "dup key" in errmsg or "duplicate key" in errmsg
    if not is_dup:
        return None
    kp = details.get("keyPattern")
    if isinstance(kp, dict):
        if "email" in kp:
            return "email"
        if "customer_reference" in kp:
            return "customer_reference"
        if "client_id" in kp:
            return "client_id"
    # Driver / server version differences: fall back to errmsg tokens.
    if "index: email" in errmsg or "dup key: { email:" in errmsg or '"email"' in errmsg:
        return "email"
    if "customer_reference" in errmsg:
        return "customer_reference"
    if "client_id" in errmsg:
        return "client_id"
    return "other"
