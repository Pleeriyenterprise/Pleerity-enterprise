"""Canonical client email identity (single source for duplicate checks and persistence).

Business rule: one ``clients`` row per logical email address. MongoDB's default unique
index on ``email`` is case-sensitive; we enforce the rule in application code by
canonicalising on write and matching legacy rows with case/whitespace-tolerant lookup.
"""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

DuplicateKind = Literal["email", "customer_reference", "client_id", "other"]

# Intake + live check UX: single user-facing string for duplicate identity (matches submit + check-email).
INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE = "An account with this email already exists"


def canonical_client_email(email: str | None) -> str:
    """Normalise email for storage and duplicate detection: strip outer whitespace, lower()."""
    if email is None:
        return ""
    return str(email).strip().lower()


async def client_email_taken(db: Any, email: str | None) -> bool:
    """True if any client document is the same logical email as ``email`` (canonical rule)."""
    canonical = canonical_client_email(email)
    if not canonical:
        return False
    if await db.clients.find_one({"email": canonical}, {"_id": 1}):
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
        {"_id": 1},
    )
    return existing is not None


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
