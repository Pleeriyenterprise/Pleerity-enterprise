"""
Authoritative pilot invite / promo code generation and normalization.

Frontend must not generate final codes — call admin generate API or create with auto_generate=True.
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Unambiguous charset (no O/0, I/1/l)
_SAFE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_SAFE_DIGITS = "23456789"
_SAFE_ALPHANUM = _SAFE_LETTERS + _SAFE_DIGITS

_RESERVED_PREFIXES = frozenset(
    {"ADMIN", "SYSTEM", "STRIPE", "TEST", "INTERNAL", "ROOT"}
)

_CODE_TYPE_PRIVATE = "private_invite"
_CODE_TYPE_PUBLIC = "public_promo"
_CODE_TYPE_REFERRAL = "referral"
_CODE_TYPE_PARTNER = "partner"
_CODE_TYPE_INTERNAL = "internal_test"

_VALID_CODE_TYPES = frozenset(
    {
        _CODE_TYPE_PRIVATE,
        _CODE_TYPE_PUBLIC,
        _CODE_TYPE_REFERRAL,
        _CODE_TYPE_PARTNER,
        _CODE_TYPE_INTERNAL,
    }
)

_MAX_GENERATION_ATTEMPTS = 16
_CODE_MAX_LEN = 64
_CODE_MIN_LEN = 4


class InviteCodeValidationError(ValueError):
    """Raised when a manual code fails governance rules."""

    def __init__(self, message: str, *, error_code: str = "PILOT_INVITE_CODE_INVALID"):
        self.error_code = error_code
        super().__init__(message)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _random_token(length: int) -> str:
    return "".join(secrets.choice(_SAFE_ALPHANUM) for _ in range(max(1, length)))


def _slug_alnum(raw: str, *, max_len: int = 24) -> str:
    """Uppercase alphanumeric slug from human text (campaign names, variants)."""
    s = re.sub(r"[^A-Za-z0-9]+", "", (raw or "").strip().upper())
    return (s or "PROMO")[:max_len]


def reserved_prefix_hit(code: str) -> Optional[str]:
    """Return matched reserved prefix segment if code starts with one."""
    normalized = normalize_invite_code(raw=code, strict=False)
    if not normalized:
        return None
    head = normalized.split("-", 1)[0]
    if head in _RESERVED_PREFIXES:
        return head
    # Also block codes that equal reserved word exactly
    if normalized in _RESERVED_PREFIXES:
        return normalized
    return None


def assert_manual_code_allowed(code: str) -> str:
    """Validate and normalize a manually entered code; raise InviteCodeValidationError."""
    normalized = normalize_invite_code(raw=code, strict=True)
    if len(normalized) < _CODE_MIN_LEN:
        raise InviteCodeValidationError(
            f"Code must be at least {_CODE_MIN_LEN} characters after normalization.",
            error_code="PILOT_INVITE_CODE_TOO_SHORT",
        )
    if len(normalized) > _CODE_MAX_LEN:
        raise InviteCodeValidationError(
            "Code is too long.",
            error_code="PILOT_INVITE_CODE_TOO_LONG",
        )
    reserved = reserved_prefix_hit(normalized)
    if reserved:
        raise InviteCodeValidationError(
            f"Code cannot use reserved prefix '{reserved}'.",
            error_code="PILOT_INVITE_RESERVED_PREFIX",
        )
    return normalized


def normalize_invite_code(*, raw: str, strict: bool = True) -> str:
    """
    Normalize invite/promo codes for storage and lookup.

    strict=True: strip unsupported symbols, uppercase, remove interior spaces.
    strict=False: legacy-compatible (whitespace strip only) for existing records.
    """
    if not raw:
        return ""
    s = (raw or "").strip().upper()
    if strict:
        # Allow hyphen as separator; map other punctuation to hyphen then collapse
        s = re.sub(r"[^A-Z0-9-]+", "-", s)
        s = re.sub(r"-+", "-", s).strip("-")
    else:
        s = re.sub(r"\s+", "", s)
    return s


def default_prefix_for_code_type(code_type: str) -> str:
    ct = (code_type or _CODE_TYPE_PRIVATE).strip().lower()
    if ct == _CODE_TYPE_PUBLIC:
        return "LAUNCH"
    if ct == _CODE_TYPE_REFERRAL:
        return "REF"
    if ct == _CODE_TYPE_PARTNER:
        return "PARTNER"
    if ct == _CODE_TYPE_INTERNAL:
        return "PILOTINT"
    return "FOUNDING"


def _pattern_private(*, prefix: str, variant: str) -> str:
    base = _slug_alnum(prefix or "FOUNDING", max_len=12)
    if variant:
        var = _slug_alnum(variant, max_len=8)
        return f"{base}-{var}-{_random_token(4)}"
    return f"{base}-{_random_token(4)}"


def _pattern_public(*, prefix: str, campaign_name: str, variant: str) -> str:
    year = str(_utc_now().year)
    if campaign_name:
        slug = _slug_alnum(campaign_name, max_len=20)
        if variant:
            return f"{slug}-{_slug_alnum(variant, max_len=8)}"
        # Human-readable: LAUNCH2026 style when slug is short enough
        if len(slug) <= 12:
            return f"{slug}{year}"
        return f"{slug}-{_random_token(4)}"
    base = _slug_alnum(prefix or "LAUNCH", max_len=12)
    return f"{base}{year}"


def _pattern_referral(*, prefix: str, variant: str) -> str:
    base = _slug_alnum(prefix or "REF", max_len=8)
    slug = _slug_alnum(variant or "USER", max_len=12)
    return f"{base}-{slug}-{_random_token(3)}"


def _pattern_partner(*, prefix: str, variant: str) -> str:
    base = _slug_alnum(prefix or "PARTNER", max_len=12)
    slug = _slug_alnum(variant or "ORG", max_len=10)
    return f"{base}-{slug}-{_random_token(3)}"


def _pattern_internal(*, variant: str) -> str:
    slug = _slug_alnum(variant or "QA", max_len=8)
    return f"PILOTINT-{slug}-{_random_token(4)}"


def generate_code_candidate(
    *,
    code_type: str,
    prefix: str = "",
    variant: str = "",
    campaign_name: str = "",
) -> str:
    """Single generation attempt (not uniqueness-checked)."""
    ct = (code_type or _CODE_TYPE_PRIVATE).strip().lower()
    if ct not in _VALID_CODE_TYPES:
        ct = _CODE_TYPE_PRIVATE
    if ct == _CODE_TYPE_PUBLIC:
        raw = _pattern_public(prefix=prefix, campaign_name=campaign_name, variant=variant)
    elif ct == _CODE_TYPE_REFERRAL:
        raw = _pattern_referral(prefix=prefix, variant=variant)
    elif ct == _CODE_TYPE_PARTNER:
        raw = _pattern_partner(prefix=prefix, variant=variant)
    elif ct == _CODE_TYPE_INTERNAL:
        raw = _pattern_internal(variant=variant or prefix)
    else:
        raw = _pattern_private(prefix=prefix or default_prefix_for_code_type(ct), variant=variant)
    return assert_manual_code_allowed(raw) if raw else ""


async def code_exists(db, code: str) -> bool:
    from services.pilot_invite_service import COL_CODES

    normalized = normalize_invite_code(raw=code, strict=False)
    if not normalized:
        return False
    doc = await db[COL_CODES].find_one({"code": normalized}, {"_id": 1})
    return bool(doc)


async def generate_unique_invite_code(
    db,
    *,
    code_type: str = _CODE_TYPE_PRIVATE,
    prefix: str = "",
    variant: str = "",
    campaign_name: str = "",
) -> str:
    """Generate a unique code with collision retries (authoritative)."""
    last = ""
    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        candidate = generate_code_candidate(
            code_type=code_type,
            prefix=prefix,
            variant=variant,
            campaign_name=campaign_name,
        )
        last = candidate
        if not await code_exists(db, candidate):
            return candidate
        logger.info(
            "pilot invite code collision attempt=%s type=%s candidate=%s",
            attempt + 1,
            code_type,
            candidate[:8] + "***",
        )
    raise InviteCodeValidationError(
        "Could not allocate a unique invite code. Try again or enter a manual code.",
        error_code="PILOT_INVITE_CODE_GENERATION_FAILED",
    )


def generation_profile_for_type(code_type: str) -> Dict[str, Any]:
    """Describe generation strategy for admin UI."""
    ct = (code_type or _CODE_TYPE_PRIVATE).strip().lower()
    profiles = {
        _CODE_TYPE_PRIVATE: {
            "pattern": "PREFIX-XXXX (secure suffix)",
            "example": "FOUNDING-8K4D",
            "human_readable": False,
        },
        _CODE_TYPE_PUBLIC: {
            "pattern": "CAMPAIGNYYYY or CAMPAIGN-XXXX",
            "example": "LAUNCH2026",
            "human_readable": True,
        },
        _CODE_TYPE_REFERRAL: {
            "pattern": "REF-NAME-XXX",
            "example": "REF-MIKE-4K9P",
            "human_readable": True,
        },
        _CODE_TYPE_PARTNER: {
            "pattern": "PARTNER-ORG-XXX",
            "example": "PARTNER-ABC-82Q",
            "human_readable": True,
        },
        _CODE_TYPE_INTERNAL: {
            "pattern": "PILOTINT-SLUG-XXXX",
            "example": "PILOTINT-QA-7H2M",
            "human_readable": False,
        },
    }
    return profiles.get(ct, profiles[_CODE_TYPE_PRIVATE])
