"""
Server-side governance for pilot invite / public promo codes (abuse + visibility).

Used by pilot_invite_service.validate_invite_for_checkout. Stripe coupons remain the billing mechanism only.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

COL_ATTEMPTS = "pilot_invite_validation_attempts"

_VALID_CODE_TYPES = frozenset(
    {"private_invite", "public_promo", "referral", "partner", "internal_test"}
)


def invite_code_type(doc: Dict[str, Any]) -> str:
    raw = str(doc.get("code_type") or "private_invite").strip().lower()
    if raw not in _VALID_CODE_TYPES:
        logger.warning("Unknown pilot code_type %r on invite %s — coercing to private_invite", raw, doc.get("code"))
        return "private_invite"
    return raw


def is_public_promo_family(code_type: str) -> bool:
    return code_type in ("public_promo", "referral", "partner")


def is_internal_test(code_type: str) -> bool:
    return code_type == "internal_test"


def campaign_status_value(doc: Dict[str, Any]) -> str:
    return str(doc.get("campaign_status") or "not_applicable").strip().lower()


def campaign_state_value(doc: Dict[str, Any]) -> str:
    state = str(doc.get("campaign_state") or "").strip().lower()
    if state in ("draft", "active", "paused", "expired", "archived"):
        return state
    legacy = campaign_status_value(doc)
    if legacy == "ended":
        return "expired"
    if legacy in ("draft", "active", "paused"):
        return legacy
    return "draft"


def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def email_domain(email: Optional[str]) -> Optional[str]:
    em = normalize_email(email)
    if not em or "@" not in em:
        return None
    return em.rsplit("@", 1)[-1].strip().lower()


def _parse_domain_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip().lower().lstrip("@") for x in val if str(x).strip()]
    s = str(val).strip()
    if not s:
        return []
    return [p.strip().lower().lstrip("@") for p in re.split(r"[\s,;]+", s) if p.strip()]


def assert_public_entry_and_campaign(
    doc: Dict[str, Any],
    *,
    entry_channel: str,
) -> None:
    """Raise PilotInvitePublicError when public promo family rules block this request."""
    from models.pilot_invite import PilotInvitePublicError

    ct = invite_code_type(doc)
    ec = (entry_channel or "manual").strip().lower()
    if ec not in ("manual", "link"):
        ec = "manual"

    if is_internal_test(ct):
        cs = campaign_state_value(doc)
        if cs in ("paused", "expired", "archived"):
            raise PilotInvitePublicError(
                "PILOT_INVITE_CAMPAIGN_INACTIVE",
                "This internal test code is not active.",
            )
        if bool(doc.get("public_entry_enabled")) or bool(doc.get("is_publicly_enterable")):
            raise PilotInvitePublicError(
                "PILOT_INVITE_PUBLIC_ENTRY_DISABLED",
                "This internal test code is not available for public entry.",
            )
        if ec == "manual":
            raise PilotInvitePublicError(
                "PILOT_INVITE_PUBLIC_ENTRY_DISABLED",
                "This internal test code requires the controlled test link.",
            )
        return

    if not is_public_promo_family(ct):
        return

    if not bool(doc.get("public_entry_enabled", False)):
        raise PilotInvitePublicError(
            "PILOT_INVITE_PUBLIC_ENTRY_DISABLED",
            "This promotion code is not available right now.",
        )

    cs = campaign_state_value(doc)
    if cs in ("draft", "expired", "archived"):
        raise PilotInvitePublicError(
            "PILOT_INVITE_CAMPAIGN_INACTIVE",
            "This promotion is not active.",
        )
    if cs == "paused":
        raise PilotInvitePublicError(
            "PILOT_INVITE_CAMPAIGN_PAUSED",
            "This promotion is paused. Please try again later.",
        )
    if cs != "active":
        raise PilotInvitePublicError(
            "PILOT_INVITE_CAMPAIGN_INACTIVE",
            "This promotion is not active.",
        )

    if ec == "manual" and not bool(doc.get("is_publicly_enterable", False)):
        raise PilotInvitePublicError(
            "PILOT_INVITE_PUBLIC_ENTRY_DISABLED",
            "This code cannot be entered manually. Use the link you were given, or contact support.",
        )


async def assert_abuse_rules(
    db,
    doc: Dict[str, Any],
    *,
    email: Optional[str],
    client_id: Optional[str],
    stripe_payment_method_id: Optional[str] = None,
) -> None:
    """Raise PilotInvitePublicError when abuse / eligibility rules fail."""
    from models.pilot_invite import PilotInvitePublicError

    invite_code_id = str(doc.get("invite_code_id") or "")
    em = normalize_email(email)
    dom = email_domain(em)

    if bool(doc.get("first_time_customer_only")) and em:
        existing = await db["clients"].find_one(
            {
                "$or": [{"email": em}, {"contact_email": em}],
            },
            {"_id": 1},
        )
        if existing:
            raise PilotInvitePublicError(
                "PILOT_INVITE_NOT_FIRST_TIME_CUSTOMER",
                "This offer is only available to first-time customers.",
            )

    allowed = _parse_domain_list(doc.get("allowed_email_domains"))
    if allowed and dom and dom not in allowed:
        raise PilotInvitePublicError(
            "PILOT_INVITE_EMAIL_DOMAIN_NOT_ALLOWED",
            "This offer is not available for your email domain.",
        )
    blocked = _parse_domain_list(doc.get("blocked_email_domains"))
    if blocked and dom and dom in blocked:
        raise PilotInvitePublicError(
            "PILOT_INVITE_EMAIL_DOMAIN_NOT_ALLOWED",
            "This offer is not available for your email domain.",
        )

    if bool(doc.get("one_redemption_per_email")) and em and invite_code_id:
        or_clauses: List[Dict[str, Any]] = [{"redemption_email": em}]
        async for c in db["clients"].find({"$or": [{"email": em}, {"contact_email": em}]}, {"client_id": 1}):
            cid = c.get("client_id")
            if cid:
                or_clauses.append({"client_id": cid})
        filt: Dict[str, Any] = {
            "invite_code_id": invite_code_id,
            "status": {"$in": ["pending", "completed"]},
        }
        if len(or_clauses) == 1:
            filt.update(or_clauses[0])
        else:
            filt["$or"] = or_clauses
        dup = await db["pilot_invite_redemptions"].count_documents(filt)
        if dup > 0:
            raise PilotInvitePublicError(
                "PILOT_INVITE_ALREADY_REDEEMED_EMAIL",
                "This code has already been used with this email address.",
            )

    if bool(doc.get("one_redemption_per_customer")) and client_id and invite_code_id:
        dup_c = await db["pilot_invite_redemptions"].count_documents(
            {
                "invite_code_id": invite_code_id,
                "client_id": client_id,
                "status": {"$in": ["pending", "completed"]},
            }
        )
        if dup_c > 0:
            raise PilotInvitePublicError(
                "PILOT_INVITE_ALREADY_REDEEMED_CUSTOMER",
                "This code has already been used on this account.",
            )

    per_account = doc.get("max_uses_per_account")
    if per_account is not None and client_id and invite_code_id:
        try:
            account_cap = int(per_account)
        except (TypeError, ValueError):
            account_cap = 0
        if account_cap > 0:
            account_uses = await db["pilot_invite_redemptions"].count_documents(
                {
                    "invite_code_id": invite_code_id,
                    "client_id": client_id,
                    "status": {"$in": ["pending", "completed"]},
                }
            )
            if account_uses >= account_cap:
                raise PilotInvitePublicError(
                    "PILOT_INVITE_ACCOUNT_LIMIT_EXCEEDED",
                    "This code has reached its usage limit for this account.",
                )

    pm = (stripe_payment_method_id or "").strip()
    if bool(doc.get("one_redemption_per_payment_method")) and pm and invite_code_id:
        dup_pm = await db["pilot_invite_redemptions"].count_documents(
            {
                "invite_code_id": invite_code_id,
                "stripe_payment_method_id": pm,
                "status": {"$in": ["pending", "completed"]},
            }
        )
        if dup_pm > 0:
            raise PilotInvitePublicError(
                "PILOT_INVITE_ALREADY_REDEEMED_PAYMENT_METHOD",
                "This code has already been used with this payment method.",
            )

    max_day = doc.get("max_uses_per_day")
    if max_day is not None and invite_code_id:
        try:
            cap = int(max_day)
        except (TypeError, ValueError):
            cap = 0
        if cap > 0:
            start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            used_today = await db["pilot_invite_redemptions"].count_documents(
                {
                    "invite_code_id": invite_code_id,
                    "created_at": {"$gte": start},
                    "status": {"$in": ["pending", "completed"]},
                }
            )
            if used_today >= cap:
                raise PilotInvitePublicError(
                    "PILOT_INVITE_DAILY_LIMIT_EXCEEDED",
                    "This code has reached its daily usage limit. Try again tomorrow.",
                )


async def record_validation_attempt(
    db,
    *,
    code_normalized: str,
    invite_code_id: Optional[str],
    outcome: str,
    reason_code: Optional[str],
    entry_channel: str,
    email: Optional[str],
    client_id: Optional[str] = None,
) -> None:
    """Persist validation attempt for admin review (best-effort)."""
    now = datetime.now(timezone.utc)
    doc = {
        "attempt_id": str(uuid.uuid4()),
        "code": code_normalized,
        "invite_code_id": invite_code_id,
        "outcome": outcome,
        "reason_code": reason_code,
        "entry_channel": (entry_channel or "manual").strip().lower(),
        "email": normalize_email(email) if email else None,
        "client_id": client_id,
        "created_at": now,
    }
    try:
        await db[COL_ATTEMPTS].insert_one(doc)
    except Exception as exc:
        logger.warning("pilot_invite_validation_attempt insert failed: %s", exc)
