"""
Phase 2 S5-extract — profile-aware document extraction (shadow observe / active authoritative).

Does not modify confirmation enforcement (LIFECYCLE_AWARE_CONFIRM).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from services.lifecycle_aware_extraction_config import (
    get_effective_extraction_mode,
    is_lifecycle_aware_extraction_off,
)
from services.lifecycle_extraction_profile_resolver import (
    ResolvedExtractionProfile,
    resolve_extraction_profile,
)
from services.lifecycle_extraction_profiles import ExtractionProfile, get_extraction_profile

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.85

ExtractionJobStatus = str  # EXTRACTED | NEEDS_REVIEW


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def resolve_profile_for_extraction(
    requirement: Optional[Dict[str, Any]],
    *,
    document: Optional[Dict[str, Any]] = None,
    registry_row: Optional[Dict[str, Any]] = None,
) -> ResolvedExtractionProfile:
    req = requirement if isinstance(requirement, dict) else {}
    return resolve_extraction_profile(req, registry_row=registry_row, document=document)


def log_profile_selected(
    resolved: ResolvedExtractionProfile,
    *,
    document_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
) -> None:
    if is_lifecycle_aware_extraction_off():
        return
    logger.info(
        "lifecycle_extract_profile_selected",
        extra={
            "extraction_profile_id": resolved.profile_id,
            "lifecycle_semantics": resolved.lifecycle_semantics,
            "resolution_source": resolved.resolution_source,
            "requirement_code": resolved.requirement_code,
            "document_id": document_id,
            "requirement_id": requirement_id,
        },
    )
    if resolved.profile_id == "supporting_document_v1" or resolved.resolution_source == "default":
        logger.info(
            "lifecycle_extract_profile_fallback",
            extra={
                "extraction_profile_id": resolved.profile_id,
                "resolution_source": resolved.resolution_source,
                "requirement_code": resolved.requirement_code,
                "document_id": document_id,
            },
        )


def _confidence_block(parsed: Dict[str, Any]) -> Dict[str, float]:
    confidence = parsed.get("confidence") if isinstance(parsed.get("confidence"), dict) else {}
    out: Dict[str, float] = {}
    for key in ("overall", "dates", "fields", "doc_type"):
        raw = confidence.get(key)
        if raw is None:
            continue
        try:
            out[key] = max(0.0, min(1.0, float(raw)))
        except (TypeError, ValueError):
            out[key] = 0.0
    if "overall" not in out:
        out["overall"] = 0.5
    return out


def _normalize_date_field(value: Any) -> Optional[str]:
    if not _is_present(value):
        return None
    raw = str(value).strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    return None


def normalize_profile_extraction(
    parsed: Dict[str, Any],
    profile: ExtractionProfile,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"confidence": _confidence_block(parsed)}
    allowed = set(profile.extracted_fields)
    for field in profile.extracted_fields:
        if field == "confidence":
            continue
        value = parsed.get(field)
        if field.endswith("_date") or field in ("check_date", "completion_date", "document_date"):
            out[field] = _normalize_date_field(value)
        elif value is None or value == "":
            out[field] = None
        else:
            out[field] = value
    if "doc_type" in allowed and parsed.get("doc_type"):
        out["doc_type"] = str(parsed.get("doc_type")).upper().replace(" ", "_")
    return out


def build_profile_json_schema(profile: ExtractionProfile) -> str:
    props: List[str] = []
    for field in profile.extracted_fields:
        if field == "confidence":
            continue
        if field.endswith("_date") or field in ("check_date", "completion_date", "document_date"):
            props.append(f'  "{field}": null or "YYYY-MM-DD"')
        else:
            props.append(f'  "{field}": null or string')
    props.append(
        '  "confidence": {"overall": 0.0 to 1.0, "dates": 0.0 to 1.0, "fields": 0.0 to 1.0}'
    )
    inner = ",\n".join(props)
    return f"{{\n{inner}\n}}"


def build_profile_system_prompt(profile: ExtractionProfile) -> str:
    required = ", ".join(profile.required_fields) or "(none)"
    optional = ", ".join(profile.optional_fields) or "(none)"
    forbidden = ", ".join(profile.forbidden_fields) or "(none)"
    schema = build_profile_json_schema(profile)
    return f"""You extract structured fields from UK property compliance document text only.
Profile: {profile.profile_id} ({profile.lifecycle_semantics}).
{profile.description}

Output MUST be valid JSON matching this schema exactly. Return ONLY the JSON object.

Schema:
{schema}

RULES:
1. Extract only fields visible in the document text; do not infer legal conclusions.
2. Required fields for this profile: {required}.
3. Optional fields: {optional}.
4. Do NOT populate forbidden fields: {forbidden}.
5. Dates must be YYYY-MM-DD or null.
6. confidence.overall must be between 0 and 1.
"""


def validate_profile_extraction_json(raw: str, profile: ExtractionProfile) -> bool:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    return "confidence" in parsed or any(f in parsed for f in profile.extracted_fields)


def legacy_extraction_status(extracted: Dict[str, Any]) -> ExtractionJobStatus:
    confidence = extracted.get("confidence") or {}
    overall = float(confidence.get("overall") or 0)
    expiry_date = extracted.get("expiry_date")
    if overall >= CONFIDENCE_THRESHOLD and _is_present(expiry_date):
        return "EXTRACTED"
    return "NEEDS_REVIEW"


def profile_extraction_status(
    profile: ExtractionProfile,
    extracted: Dict[str, Any],
) -> ExtractionJobStatus:
    confidence = extracted.get("confidence") or {}
    overall = float(confidence.get("overall") or 0)
    if overall < CONFIDENCE_THRESHOLD:
        return "NEEDS_REVIEW"
    for field in profile.required_fields:
        if not _is_present(extracted.get(field)):
            return "NEEDS_REVIEW"
    for field in profile.forbidden_fields:
        if _is_present(extracted.get(field)):
            return "NEEDS_REVIEW"
    return "EXTRACTED"


def profile_field_present(extracted: Dict[str, Any], field: str) -> bool:
    return _is_present(extracted.get(field))


def observe_extraction_shadow(
    *,
    legacy_extracted: Dict[str, Any],
    profile_extracted: Optional[Dict[str, Any]],
    profile: ExtractionProfile,
    resolved: ResolvedExtractionProfile,
    document_id: Optional[str] = None,
    extraction_id: Optional[str] = None,
) -> None:
    """
    Shadow-only: compare legacy vs profile extraction outcomes; log divergence. No mutation.
    """
    mode = get_effective_extraction_mode()
    if mode == "off" or profile_extracted is None:
        return

    legacy_status = legacy_extraction_status(legacy_extracted)
    profile_status = profile_extraction_status(profile, profile_extracted)
    extra = {
        "extraction_profile_id": profile.profile_id,
        "lifecycle_semantics": profile.lifecycle_semantics,
        "resolution_source": resolved.resolution_source,
        "document_id": document_id,
        "extraction_id": extraction_id,
        "legacy_status": legacy_status,
        "profile_status": profile_status,
        "legacy_has_expiry_date": _is_present(legacy_extracted.get("expiry_date")),
        "profile_required_fields": list(profile.required_fields),
        "profile_required_present": {
            f: profile_field_present(profile_extracted, f) for f in profile.required_fields
        },
    }
    if profile_status == "EXTRACTED":
        logger.info("lifecycle_extract_shadow_complete", extra=extra)
    else:
        logger.info("lifecycle_extract_shadow_incomplete", extra=extra)
    if legacy_status != profile_status:
        extra["status_divergence"] = True
        logger.info("lifecycle_extract_shadow_status_divergence", extra=extra)


def merge_profile_into_legacy_storage(
    legacy_extracted: Dict[str, Any],
    profile_extracted: Dict[str, Any],
    profile: ExtractionProfile,
) -> Dict[str, Any]:
    """Active mode: use profile fields while preserving legacy cert keys when present."""
    merged = dict(legacy_extracted)
    for field in profile.extracted_fields:
        if field == "confidence":
            continue
        val = profile_extracted.get(field)
        if _is_present(val):
            merged[field] = val
    conf = profile_extracted.get("confidence")
    if isinstance(conf, dict) and conf.get("overall") is not None:
        merged["confidence"] = conf
    return merged


def build_storage_payload_from_legacy(
    extracted: Dict[str, Any],
    overall: float,
) -> Dict[str, Any]:
    """Legacy cert-centric extracted_documents.extracted shape."""
    return {
        "doc_type": extracted.get("doc_type") or "UNKNOWN",
        "certificate_number": extracted.get("certificate_number"),
        "issue_date": extracted.get("issue_date"),
        "expiry_date": extracted.get("expiry_date"),
        "inspector_company": extracted.get("inspector_company"),
        "inspector_id": extracted.get("inspector_id"),
        "address_line_1": extracted.get("address_line_1"),
        "postcode": extracted.get("postcode"),
        "property_match_confidence": overall,
        "overall_confidence": overall,
        "notes": extracted.get("notes"),
    }


def build_storage_payload_from_profile(
    profile: ExtractionProfile,
    extracted: Dict[str, Any],
    overall: float,
) -> Dict[str, Any]:
    """Active mode storage — profile fields plus compatibility keys."""
    payload: Dict[str, Any] = {
        "doc_type": extracted.get("doc_type") or "UNKNOWN",
        "property_match_confidence": overall,
        "overall_confidence": overall,
        "notes": extracted.get("notes"),
        "extraction_profile_id": profile.profile_id,
        "lifecycle_semantics": profile.lifecycle_semantics,
    }
    for field in profile.extracted_fields:
        if field == "confidence":
            continue
        if _is_present(extracted.get(field)):
            payload[field] = extracted.get(field)
    if profile.lifecycle_semantics == "EXPIRY_BASED":
        payload["certificate_number"] = extracted.get("certificate_number") or extracted.get(
            "licence_number"
        )
        payload["issue_date"] = extracted.get("issue_date")
        payload["expiry_date"] = extracted.get("expiry_date")
        payload["inspector_company"] = extracted.get("inspector_company")
        payload["inspector_id"] = extracted.get("inspector_id")
    return payload


def determine_authoritative_extraction_status(
    *,
    mode: str,
    legacy_extracted: Dict[str, Any],
    profile_extracted: Optional[Dict[str, Any]],
    profile: ExtractionProfile,
) -> ExtractionJobStatus:
    if mode == "active" and profile_extracted is not None:
        return profile_extraction_status(profile, profile_extracted)
    return legacy_extraction_status(legacy_extracted)


async def maybe_run_profile_extraction_observe(
    text: str,
    file_name: str,
    *,
    legacy_extracted: Dict[str, Any],
    requirement: Optional[Dict[str, Any]] = None,
    document: Optional[Dict[str, Any]] = None,
    registry_row: Optional[Dict[str, Any]] = None,
    document_id: Optional[str] = None,
    extraction_id: Optional[str] = None,
    hints: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[ResolvedExtractionProfile]]:
    """
    When extraction mode is shadow or active: resolve profile, run profile LLM, log comparison.
    Returns (profile_extracted, resolved) — caller uses legacy response in shadow/off.
    """
    mode = get_effective_extraction_mode()
    if mode == "off":
        return None, None

    resolved = resolve_profile_for_extraction(
        requirement,
        document=document,
        registry_row=registry_row,
    )
    log_profile_selected(
        resolved,
        document_id=document_id,
        requirement_id=(requirement or {}).get("requirement_id"),
    )

    from services.ai_provider import extract_profile_aware_fields_async

    profile_result = await extract_profile_aware_fields_async(
        text,
        file_name,
        resolved.profile,
        hints=hints,
    )
    profile_extracted = (
        profile_result.get("extracted") if profile_result.get("success") else None
    )
    observe_extraction_shadow(
        legacy_extracted=legacy_extracted,
        profile_extracted=profile_extracted,
        profile=resolved.profile,
        resolved=resolved,
        document_id=document_id,
        extraction_id=extraction_id,
    )
    return profile_extracted, resolved
