"""
Account/campaign-scoped eligibility overrides for pilot promo redemption (separate from campaign truth).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from database import database

logger = logging.getLogger(__name__)

COL_ELIGIBILITY_OVERRIDES = "pilot_redemption_eligibility_overrides"


class EligibilityOverrideScope(str, Enum):
    EMAIL = "email"
    CLIENT_ID = "client_id"
    INVITE_CODE_ID = "invite_code_id"


class EligibilityOverrideType(str, Enum):
    BYPASS_FIRST_TIME = "bypass_first_time"
    ALLOW_PROMO_RETRY = "allow_promo_retry"
    MANUAL_ATTACH_PROMO = "manual_attach_promo"
    RECOVER_ONBOARDING = "recover_onboarding"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _override_active(doc: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    now = now or _utc_now()
    if doc.get("revoked_at"):
        return False
    exp = _parse_dt(doc.get("override_expires_at"))
    if exp and exp <= now:
        return False
    return True


async def find_active_overrides(
    *,
    email: Optional[str] = None,
    client_id: Optional[str] = None,
    invite_code_id: Optional[str] = None,
    override_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    now = _utc_now()
    or_clauses: List[Dict[str, Any]] = []
    em = (email or "").strip().lower()
    if em:
        or_clauses.append({"scope": EligibilityOverrideScope.EMAIL.value, "scope_value": em})
    if client_id:
        or_clauses.append({"scope": EligibilityOverrideScope.CLIENT_ID.value, "scope_value": client_id})
    if invite_code_id:
        or_clauses.append({"scope": EligibilityOverrideScope.INVITE_CODE_ID.value, "scope_value": invite_code_id})
    if not or_clauses:
        return []

    filt: Dict[str, Any] = {
        "$or": or_clauses,
        "revoked_at": None,
        "$and": [
            {
                "$or": [
                    {"override_expires_at": None},
                    {"override_expires_at": {"$gt": now}},
                ]
            }
        ],
    }
    if override_types:
        filt["override_type"] = {"$in": override_types}

    rows = (
        await db[COL_ELIGIBILITY_OVERRIDES]
        .find(filt, {"_id": 0})
        .sort("override_created_at", -1)
        .limit(50)
        .to_list(length=50)
    )
    return [r for r in rows if _override_active(r, now=now)]


async def has_override(
    *,
    email: Optional[str] = None,
    client_id: Optional[str] = None,
    invite_code_id: Optional[str] = None,
    override_type: str,
) -> bool:
    rows = await find_active_overrides(
        email=email,
        client_id=client_id,
        invite_code_id=invite_code_id,
        override_types=[override_type],
    )
    return len(rows) > 0


async def create_eligibility_override(
    *,
    scope: str,
    scope_value: str,
    override_type: str,
    override_reason: str,
    override_actor: Dict[str, Any],
    invite_code: Optional[str] = None,
    invite_code_id: Optional[str] = None,
    override_expires_at: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    now = _utc_now()
    doc = {
        "override_id": str(uuid.uuid4()),
        "scope": scope,
        "scope_value": scope_value.strip(),
        "override_type": override_type,
        "override_reason": override_reason.strip(),
        "override_actor": override_actor,
        "override_created_at": now,
        "override_expires_at": override_expires_at,
        "invite_code": (invite_code or "").strip().upper() or None,
        "invite_code_id": invite_code_id,
        "metadata": metadata or {},
        "revoked_at": None,
        "revoked_by": None,
    }
    if scope == EligibilityOverrideScope.EMAIL.value:
        doc["scope_value"] = doc["scope_value"].lower()
    await db[COL_ELIGIBILITY_OVERRIDES].insert_one(doc)
    doc.pop("_id", None)
    return doc


async def revoke_eligibility_override(
    *,
    override_id: str,
    revoked_by: Dict[str, Any],
) -> bool:
    db = database.get_db()
    now = _utc_now()
    res = await db[COL_ELIGIBILITY_OVERRIDES].update_one(
        {"override_id": override_id, "revoked_at": None},
        {"$set": {"revoked_at": now, "revoked_by": revoked_by, "updated_at": now}},
    )
    return res.modified_count > 0


async def list_overrides_for_invite(
    invite_code_id: str,
    *,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = (
        db[COL_ELIGIBILITY_OVERRIDES]
        .find({"invite_code_id": invite_code_id}, {"_id": 0})
        .sort("override_created_at", -1)
        .limit(limit)
    )
    return [doc async for doc in cursor]


async def list_overrides_for_client(client_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    db = database.get_db()
    or_clauses: List[Dict[str, Any]] = [
        {"scope": EligibilityOverrideScope.CLIENT_ID.value, "scope_value": client_id},
    ]
    client = await db["clients"].find_one({"client_id": client_id}, {"_id": 0, "email": 1, "contact_email": 1})
    if client:
        for field in ("email", "contact_email"):
            em = (client.get(field) or "").strip().lower()
            if em:
                or_clauses.append({"scope": EligibilityOverrideScope.EMAIL.value, "scope_value": em})
    cursor = (
        db[COL_ELIGIBILITY_OVERRIDES]
        .find({"$or": or_clauses}, {"_id": 0})
        .sort("override_created_at", -1)
        .limit(limit)
    )
    return [doc async for doc in cursor]
