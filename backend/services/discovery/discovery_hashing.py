"""
Discovery content hashing, idempotency keys, and lineage validation — Stage H.

Deterministic canonical hashing with volatile-field exclusion.
No storage, routes, or provider ingest.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from services.discovery.discovery_models import (
    OriginLineageEntry,
    normalise_email,
    normalise_phone,
)

# Stable field order for canonical content hash (do not reorder without migration).
CANONICAL_HASH_FIELD_ORDER: tuple[str, ...] = (
    "provider",
    "provider_reference",
    "source_url",
    "company_name",
    "contact_name",
    "email",
    "phone",
    "website",
    "location",
    "business_type",
    "landlord_type",
    "campaign_id",
    "discovery_run_id",
)

# Backward-compatible export for tests/docs referencing identity subset.
CONTENT_HASH_FIELDS: tuple[str, ...] = tuple(
    f
    for f in CANONICAL_HASH_FIELD_ORDER
    if f
    in {
        "company_name",
        "contact_name",
        "email",
        "phone",
        "website",
        "business_type",
        "landlord_type",
        "source_url",
        "provider",
        "provider_reference",
        "campaign_id",
        "discovery_run_id",
        "location",
    }
)

VOLATILE_HASH_FIELDS = frozenset(
    {
        "created_at",
        "updated_at",
        "review_status",
        "reviewer_id",
        "reviewer_email",
        "review_timestamp",
        "review_priority",
        "provider_confidence",
        "platform_quality_score",
        "raw_payload_reference",
        "audit_id",
        "audit_fields",
        "duplicate_status",
        "duplicate_lead_id",
        "duplicate_override_reason",
        "merged_into_prospect_id",
        "imported_lead_id",
        "imported_timestamp",
        "erasure_status",
        "erasure_requested_at",
        "erased_at",
        "risk_flags",
        "legal_hold",
        "marketing_consent",
        "lawful_basis",
        "prospect_id",
        "discovery_job_id",
        "email_hash",
        "phone_hash",
        "tenant_id",
        "origin_lineage",
        "source_type",
    }
)

CONTENT_HASH_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*:[^:@\s]{1,128}:[a-f0-9]{64}$"
)
PROVIDER_REFERENCE_MAX_LEN = 256
EMAIL_IN_REFERENCE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _strip_volatile_fields(data: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if k not in VOLATILE_HASH_FIELDS}


def _normalise_location(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts = [
            str(value.get("city") or "").strip().lower(),
            str(value.get("region") or "").strip().lower(),
            str(value.get("postcode") or "").strip().lower(),
            str(value.get("country") or "").strip().lower(),
        ]
        return "|".join(parts)
    return str(value).strip().lower()


def _normalise_canonical_value(field: str, value: Any) -> str:
    if value is None:
        return ""
    if field == "email":
        return normalise_email(str(value)) or ""
    if field == "phone":
        return normalise_phone(str(value)) or ""
    if field == "location":
        return _normalise_location(value)
    if field in ("provider", "business_type", "landlord_type"):
        return str(value).strip().lower()
    return str(value).strip().lower()


def compute_canonical_content_hash(data: Mapping[str, Any]) -> str:
    """
    Deterministic SHA-256 over canonical prospect content.

    Ignores volatile fields (timestamps, scores, review state, audit, etc.).
    """
    clean = _strip_volatile_fields(data)
    parts: List[str] = []
    for field in CANONICAL_HASH_FIELD_ORDER:
        parts.append(_normalise_canonical_value(field, clean.get(field)))
    payload = "\x1f".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_content_hash(fields: Mapping[str, Any]) -> str:
    """Alias for canonical hash — single authoritative implementation."""
    return compute_canonical_content_hash(fields)


def validate_content_hash_hex(content_hash: str) -> List[str]:
    errors: List[str] = []
    if not content_hash or not str(content_hash).strip():
        errors.append("content_hash is required")
    elif not CONTENT_HASH_HEX_PATTERN.match(str(content_hash).strip().lower()):
        errors.append("content_hash must be 64-character lowercase hex SHA-256")
    return errors


def normalize_provider_reference(
    provider: str,
    provider_reference: Optional[str],
) -> str:
    """
    Normalize provider reference for safe storage and idempotency.

    Namespaces as `{provider}:{token}` when no namespace present.
    Sanitizes control characters; bounds length.
    """
    provider_id = str(provider).strip().lower()
    if not provider_reference or not str(provider_reference).strip():
        return f"{provider_id}:-"

    ref = str(provider_reference).strip()
    ref = re.sub(r"[\x00-\x1f\x7f]", "", ref)
    if len(ref) > PROVIDER_REFERENCE_MAX_LEN:
        ref = ref[:PROVIDER_REFERENCE_MAX_LEN]

    if ":" in ref:
        prefix, _rest = ref.split(":", 1)
        if prefix == provider_id:
            return ref
    combined = f"{provider_id}:{ref}"
    if len(combined) > PROVIDER_REFERENCE_MAX_LEN:
        combined = combined[:PROVIDER_REFERENCE_MAX_LEN]
    return combined


def _idempotency_reference_segment(normalized_reference: str) -> str:
    """Segment safe for idempotency key — no raw email/PII."""
    if EMAIL_IN_REFERENCE.search(normalized_reference):
        return hashlib.sha256(normalized_reference.encode("utf-8")).hexdigest()[:16]
    return normalized_reference.replace(":", "_")[:128]


def build_discovery_idempotency_key(
    provider: str,
    provider_reference: Optional[str],
    content_hash: str,
) -> str:
    """
    Provider-neutral idempotency key. No timestamps. No raw PII in key material.
    """
    hash_errors = validate_content_hash_hex(content_hash)
    if hash_errors:
        raise ValueError(hash_errors[0])

    provider_id = str(provider).strip().lower()
    norm_ref = normalize_provider_reference(provider_id, provider_reference)
    ref_seg = _idempotency_reference_segment(norm_ref)
    return f"{provider_id}:{ref_seg}:{content_hash.strip().lower()}"


def validate_discovery_idempotency_key(key: str) -> List[str]:
    errors: List[str] = []
    if not key or not str(key).strip():
        errors.append("idempotency key is required")
        return errors
    normalised = str(key).strip().lower()
    if not IDEMPOTENCY_KEY_PATTERN.match(normalised):
        errors.append("idempotency key format invalid")
        return errors
    if "@" in normalised:
        errors.append("idempotency key must not contain raw email")
    parts = normalised.split(":")
    if len(parts) != 3:
        errors.append("idempotency key must have provider:reference:content_hash form")
    elif not CONTENT_HASH_HEX_PATTERN.match(parts[2]):
        errors.append("idempotency key content_hash segment invalid")
    return errors


def _entry_as_dict(
    entry: Union[OriginLineageEntry, Mapping[str, Any]],
) -> Dict[str, Any]:
    if isinstance(entry, OriginLineageEntry):
        return entry.model_dump(mode="json")
    return dict(entry)


def validate_origin_lineage_entry(
    entry: Union[OriginLineageEntry, Mapping[str, Any]],
) -> List[str]:
    errors: List[str] = []
    data = _entry_as_dict(entry)

    if not data.get("provider") or not str(data["provider"]).strip():
        errors.append("origin_lineage entry requires provider")

    if not data.get("discovery_run_id") or not str(data["discovery_run_id"]).strip():
        errors.append("origin_lineage entry requires discovery_run_id")

    ch = data.get("content_hash")
    if not ch:
        errors.append("origin_lineage entry requires content_hash")
    else:
        errors.extend(validate_content_hash_hex(str(ch)))

    discovered = data.get("discovered_at") or data.get("ingested_at")
    if not discovered:
        errors.append("origin_lineage entry requires discovered_at or ingested_at")

    pref = data.get("provider_reference")
    if pref is not None and str(pref).strip():
        norm = normalize_provider_reference(str(data["provider"]), str(pref))
        if len(norm) > PROVIDER_REFERENCE_MAX_LEN:
            errors.append("origin_lineage provider_reference too long")

    return errors


def validate_origin_lineage(
    entries: Sequence[Union[OriginLineageEntry, Mapping[str, Any]]],
    *,
    previous: Optional[Sequence[Union[OriginLineageEntry, Mapping[str, Any]]]] = None,
) -> List[str]:
    """
    Validate lineage list. When previous is set, enforces append-only semantics.
    """
    errors: List[str] = []
    if not entries:
        errors.append("origin_lineage must contain at least one entry")
        return errors

    for idx, entry in enumerate(entries):
        entry_errors = validate_origin_lineage_entry(entry)
        errors.extend(f"entry[{idx}]: {e}" for e in entry_errors)

    if previous is not None:
        if len(entries) < len(previous):
            errors.append("origin_lineage cannot shrink — append-only")
        for i, prev in enumerate(previous):
            if i >= len(entries):
                break
            prev_d = _entry_as_dict(prev)
            cur_d = _entry_as_dict(entries[i])
            for key in ("provider", "provider_reference", "discovery_run_id", "content_hash"):
                if prev_d.get(key) != cur_d.get(key):
                    errors.append(f"origin_lineage entry[{i}].{key} cannot be mutated")
                    break

    return errors


def content_hash_exposes_pii(content_hash: str) -> bool:
    """Content hash is SHA-256 hex — never contains @ or readable PII."""
    return "@" in content_hash or " " in content_hash
