"""
Compliance Timeline — deterministic current-truth projection per requirement.

Single calculator for obligation dates (Phase 1 Date Architecture Correction).
Does not persist dates; does not implement an event ledger.

Authority hierarchy (highest wins):
  1. Verified document expiry (evidence_authority)
  2. Structured CER date
  3. User confirmed expiry
  4. AI extracted expiry
  5. System estimate (warning_days materialization placeholder — low confidence)
  6. Null / unknown
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.lifecycle_semantics_fallback_map import (
    fallback_entry_for_canonical_code,
    fallback_entry_for_storage_slug,
)
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_types import FieldContract, LifecycleSemantics
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_evidence_authority import (
    EA_VERIFIED_CURRENT,
    EA_VERIFIED_EXPIRED,
)
from services.requirement_truth import DATE_SOURCE_SYSTEM_ESTIMATED

TIMELINE_VERSION = "v1"

AUTHORITY_VERIFIED_DOCUMENT = "verified_document"
AUTHORITY_STRUCTURED_CER = "structured_cer"
AUTHORITY_USER_CONFIRMED = "user_confirmed"
AUTHORITY_AI_EXTRACTED = "ai_extracted"
AUTHORITY_SYSTEM_ESTIMATE = "system_estimate"
AUTHORITY_UNKNOWN = "unknown"

CONFIDENCE_VERIFIED = "VERIFIED"
CONFIDENCE_PARTIAL = "PARTIALLY_CONFIRMED"
CONFIDENCE_ESTIMATED = "ESTIMATED"
CONFIDENCE_UNKNOWN = "UNKNOWN"


@dataclass
class CalculatedDateField:
    calculated_date: Optional[str]
    calculation_rule: str
    authority_source: str
    confidence: str
    is_estimated: bool
    is_verified: bool
    is_customer_supplied: bool
    is_ai_extracted: bool
    source_field: Optional[str]
    source_record_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FamilyTimelineRules:
    timeline_category: str
    primary_concept: str
    fallback_concept: Optional[str]
    expects_expiry: bool
    expects_review: bool
    allows_estimate: bool
    allows_customer_supplied: bool
    allows_ai_extracted: bool


_FAMILY_RULES: Dict[str, FamilyTimelineRules] = {
    "gas_safety": FamilyTimelineRules(
        "certificate_lifecycle", "certificate_expiry", None, True, False, True, True, True
    ),
    "epc": FamilyTimelineRules(
        "certificate_lifecycle", "certificate_expiry", None, True, False, True, True, True
    ),
    "eicr": FamilyTimelineRules(
        "certificate_lifecycle", "certificate_expiry", None, True, False, True, True, True
    ),
    "portable_appliance_test": FamilyTimelineRules(
        "certificate_lifecycle", "certificate_expiry", None, True, False, True, True, True
    ),
    "hmo_license": FamilyTimelineRules(
        "certificate_lifecycle", "certificate_expiry", None, True, False, True, True, True
    ),
    "selective_license": FamilyTimelineRules(
        "certificate_lifecycle", "certificate_expiry", None, True, False, True, True, True
    ),
    "property_licence": FamilyTimelineRules(
        "certificate_lifecycle", "certificate_expiry", None, True, False, True, True, True
    ),
    "legionella": FamilyTimelineRules(
        "assessment_lifecycle", "next_assessment_due", "assessment_date", False, True, False, True, False
    ),
    "lead_testing": FamilyTimelineRules(
        "assessment_lifecycle", "next_assessment_due", "assessment_date", False, True, False, True, False
    ),
    "how_to_rent": FamilyTimelineRules(
        "declaration_lifecycle", "delivery_date", None, False, False, False, True, False
    ),
    "deposit_pi": FamilyTimelineRules(
        "declaration_lifecycle", "declaration_date", None, False, False, False, True, False
    ),
    "tenancy_agreement": FamilyTimelineRules(
        "tenancy_lifecycle", "tenancy_start", "tenancy_end", False, False, False, True, False
    ),
    "rent_smart_wales": FamilyTimelineRules(
        "registration_lifecycle", "registration_date", "next_review_due", False, True, False, True, False
    ),
    "landlord_registration": FamilyTimelineRules(
        "registration_lifecycle", "registration_date", "next_review_due", False, True, False, True, False
    ),
    "scotland_landlord_registration": FamilyTimelineRules(
        "registration_lifecycle", "registration_date", "next_review_due", False, True, False, True, False
    ),
    "landlord_registration_ni": FamilyTimelineRules(
        "registration_lifecycle", "registration_date", "next_review_due", False, True, False, True, False
    ),
    "smoke_heat_alarms": FamilyTimelineRules(
        "event_lifecycle", "event_date", None, False, False, False, True, False
    ),
    "hmo_fire_risk": FamilyTimelineRules(
        "hybrid_lifecycle", "certificate_expiry", "next_review_due", True, True, True, True, True
    ),
    "hmo_fire_risk_evidence": FamilyTimelineRules(
        "hybrid_lifecycle", "certificate_expiry", "next_review_due", True, True, True, True, True
    ),
    "fire_risk_assessment": FamilyTimelineRules(
        "hybrid_lifecycle", "certificate_expiry", "next_review_due", True, True, True, True, True
    ),
}

_CONCEPT_LABELS: Dict[str, str] = {
    "certificate_expiry": "Certificate expires",
    "next_assessment_due": "Next assessment due",
    "assessment_date": "Assessment date",
    "declaration_date": "Declaration date",
    "delivery_date": "Guide delivery date",
    "tenancy_start": "Tenancy start",
    "tenancy_end": "Tenancy term ends",
    "registration_date": "Registration date",
    "next_review_due": "Next review due",
    "event_date": "Evidence recorded",
    "estimated_compliance_date": "Estimated compliance date",
    "missing": "No date on file",
}


def _parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = (value.replace("Z", "+00:00") if isinstance(value, str) else str(value)).strip()
        if not s:
            return None
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (TypeError, ValueError):
        return None


def _iso_date(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.date().isoformat()


def _format_gb_label(concept: str, iso: Optional[str]) -> str:
    if not iso:
        return _CONCEPT_LABELS.get("missing", "No date on file")
    try:
        d = datetime.fromisoformat(iso).date()
        months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        formatted = f"{d.day} {months[d.month - 1]} {d.year}"
    except ValueError:
        formatted = iso
    label_prefix = _CONCEPT_LABELS.get(concept, concept.replace("_", " ").title())
    return f"{label_prefix}: {formatted}"


def _storage_slug(requirement: Dict[str, Any]) -> str:
    for key in ("requirement_code", "requirement_type", "code", "type"):
        raw = requirement.get(key)
        if raw:
            normalized = normalize_requirement_code(str(raw))
            if normalized:
                return normalized
            return str(raw).strip().lower().replace(" ", "_")
    return ""


def _structured_declaration(requirement: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("structured_declaration", "structured_payload", "declaration_payload"):
        val = requirement.get(key)
        if isinstance(val, dict):
            return val
    return {}


def _active_cer_records(
    records: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if not records:
        return []
    out: List[Dict[str, Any]] = []
    for rec in records:
        if rec.get("archived") is True:
            continue
        if rec.get("included_in_active_compliance") is False:
            continue
        out.append(rec)
    return out


def _cer_structured_fields(rec: Dict[str, Any]) -> Dict[str, Any]:
    payload = rec.get("evidence_payload") if isinstance(rec.get("evidence_payload"), dict) else {}
    sf = payload.get("structured_fields")
    if isinstance(sf, dict):
        flat: Dict[str, Any] = {}
        for k, v in sf.items():
            if isinstance(v, dict) and "answer" in v:
                flat[k] = v.get("answer")
            else:
                flat[k] = v
        return flat
    if isinstance(payload, dict):
        return {k: v for k, v in payload.items() if k != "structured_fields"}
    return {}


def _pick_cer_field(
    records: Optional[List[Dict[str, Any]]],
    structured: Dict[str, Any],
    *field_names: str,
) -> Tuple[Optional[datetime], Optional[str], Optional[str]]:
    for name in field_names:
        dt = _parse_date(structured.get(name))
        if dt:
            return dt, f"structured_declaration.{name}", None
    for rec in _active_cer_records(records):
        fields = _cer_structured_fields(rec)
        for name in field_names:
            dt = _parse_date(fields.get(name))
            if dt:
                rid = str(rec.get("evidence_record_id") or "") or None
                return dt, f"cer.{name}", rid
    return None, None, None


def _verified_document_expiry(requirement: Dict[str, Any]) -> Optional[CalculatedDateField]:
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    synced = bool(requirement.get("evidence_authority_synced_at")) and int(ea.get("version") or 0) >= 1
    if not synced:
        return None
    state = str(ea.get("state") or "").upper()
    if state not in (EA_VERIFIED_CURRENT, EA_VERIFIED_EXPIRED):
        return None
    if ea.get("effective_expiry_is_null") is True:
        return None
    eff = _parse_date(ea.get("effective_expiry_date"))
    if eff is None:
        return None
    doc_id = str(ea.get("effective_verified_document_id") or requirement.get("document_id") or "") or None
    return CalculatedDateField(
        calculated_date=_iso_date(eff),
        calculation_rule="verified_document_expiry_from_evidence_authority",
        authority_source=AUTHORITY_VERIFIED_DOCUMENT,
        confidence=CONFIDENCE_VERIFIED,
        is_estimated=False,
        is_verified=True,
        is_customer_supplied=False,
        is_ai_extracted=False,
        source_field="evidence_authority.effective_expiry_date",
        source_record_id=doc_id,
    )


def _user_confirmed_expiry(requirement: Dict[str, Any]) -> Optional[CalculatedDateField]:
    confirmed = _parse_date(requirement.get("confirmed_expiry_date"))
    if confirmed is None:
        return None
    expiry_source = str(requirement.get("expiry_source") or "").upper()
    if expiry_source == "EXTRACTED":
        return None
    return CalculatedDateField(
        calculated_date=_iso_date(confirmed),
        calculation_rule="user_confirmed_expiry_on_requirement",
        authority_source=AUTHORITY_USER_CONFIRMED,
        confidence=CONFIDENCE_PARTIAL,
        is_estimated=False,
        is_verified=False,
        is_customer_supplied=True,
        is_ai_extracted=False,
        source_field="confirmed_expiry_date",
        source_record_id=str(requirement.get("requirement_id") or "") or None,
    )


def _ai_extracted_expiry(requirement: Dict[str, Any]) -> Optional[CalculatedDateField]:
    extracted = _parse_date(requirement.get("extracted_expiry_date"))
    if extracted is None:
        return None
    return CalculatedDateField(
        calculated_date=_iso_date(extracted),
        calculation_rule="ai_extracted_expiry_on_requirement",
        authority_source=AUTHORITY_AI_EXTRACTED,
        confidence=CONFIDENCE_PARTIAL,
        is_estimated=False,
        is_verified=False,
        is_customer_supplied=False,
        is_ai_extracted=True,
        source_field="extracted_expiry_date",
        source_record_id=str(requirement.get("document_id") or "") or None,
    )


def _system_estimate_due_date(requirement: Dict[str, Any]) -> Optional[CalculatedDateField]:
    due = _parse_date(requirement.get("due_date"))
    if due is None:
        return None
    stored_source = str(requirement.get("date_source") or "").upper()
    has_higher = bool(
        requirement.get("confirmed_expiry_date") or requirement.get("extracted_expiry_date")
    )
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    if bool(requirement.get("evidence_authority_synced_at")) and ea.get("effective_expiry_date"):
        return None
    if has_higher and stored_source != DATE_SOURCE_SYSTEM_ESTIMATED:
        return None
    if stored_source and stored_source != DATE_SOURCE_SYSTEM_ESTIMATED:
        return None
    return CalculatedDateField(
        calculated_date=_iso_date(due),
        calculation_rule="system_estimate_warning_days_materialization",
        authority_source=AUTHORITY_SYSTEM_ESTIMATE,
        confidence=CONFIDENCE_ESTIMATED,
        is_estimated=True,
        is_verified=False,
        is_customer_supplied=False,
        is_ai_extracted=False,
        source_field="due_date",
        source_record_id=str(requirement.get("requirement_id") or "") or None,
    )


def _cer_expiry_from_records(
    records: Optional[List[Dict[str, Any]]],
    structured: Dict[str, Any],
) -> Optional[CalculatedDateField]:
    dt, field, rid = _pick_cer_field(
        records,
        structured,
        "expiry_date",
        "certificate_expiry_date",
        "valid_until",
    )
    if dt is None:
        return None
    verified = any(
        str(r.get("verification_status") or "").upper() == "VERIFIED"
        for r in _active_cer_records(records)
    )
    return CalculatedDateField(
        calculated_date=_iso_date(dt),
        calculation_rule="structured_cer_expiry_field",
        authority_source=AUTHORITY_STRUCTURED_CER,
        confidence=CONFIDENCE_VERIFIED if verified else CONFIDENCE_PARTIAL,
        is_estimated=False,
        is_verified=verified,
        is_customer_supplied=True,
        is_ai_extracted=False,
        source_field=field,
        source_record_id=rid,
    )


def _resolve_expiry_hierarchy(
    requirement: Dict[str, Any],
    *,
    records: Optional[List[Dict[str, Any]]],
    structured: Dict[str, Any],
    allows_estimate: bool,
) -> Optional[CalculatedDateField]:
    for resolver in (
        lambda: _verified_document_expiry(requirement),
        lambda: _cer_expiry_from_records(records, structured),
        lambda: _user_confirmed_expiry(requirement),
        lambda: _ai_extracted_expiry(requirement),
        lambda: _system_estimate_due_date(requirement) if allows_estimate else None,
    ):
        result = resolver()
        if result is not None:
            return result
    return None


def _resolve_cer_date_field(
    records: Optional[List[Dict[str, Any]]],
    structured: Dict[str, Any],
    *field_names: str,
    rule_prefix: str,
    verified_records: bool = False,
) -> Optional[CalculatedDateField]:
    dt, field, rid = _pick_cer_field(records, structured, *field_names)
    if dt is None:
        return None
    verified = verified_records or any(
        str(r.get("verification_status") or "").upper() == "VERIFIED"
        for r in _active_cer_records(records)
    )
    return CalculatedDateField(
        calculated_date=_iso_date(dt),
        calculation_rule=f"{rule_prefix}_{field_names[0]}",
        authority_source=AUTHORITY_STRUCTURED_CER,
        confidence=CONFIDENCE_VERIFIED if verified else CONFIDENCE_PARTIAL,
        is_estimated=False,
        is_verified=verified,
        is_customer_supplied=True,
        is_ai_extracted=False,
        source_field=field,
        source_record_id=rid,
    )


def _family_rules_for_requirement(
    requirement: Dict[str, Any],
    semantics: LifecycleSemantics,
    field_contract: FieldContract,
) -> FamilyTimelineRules:
    slug = _storage_slug(requirement)
    if slug in _FAMILY_RULES:
        return _FAMILY_RULES[slug]
    canonical = (normalize_requirement_code(slug) or "").upper() if slug else ""
    if canonical:
        mapped = fallback_entry_for_canonical_code(canonical)
        if mapped and slug:
            pass
    if semantics == "EXPIRY_BASED":
        return FamilyTimelineRules(
            "certificate_lifecycle", "certificate_expiry", None, True, False, True, True, True
        )
    if semantics == "REVIEW_BASED":
        return FamilyTimelineRules(
            "assessment_lifecycle", "next_assessment_due", "assessment_date", False, True, False, True, False
        )
    if semantics == "DECLARATION_BASED":
        return FamilyTimelineRules(
            "declaration_lifecycle", "declaration_date", None, False, False, False, True, False
        )
    if semantics == "TENANCY_LIFECYCLE":
        return FamilyTimelineRules(
            "tenancy_lifecycle", "tenancy_start", "tenancy_end", False, False, False, True, False
        )
    if semantics == "OCCUPANCY_LIFECYCLE":
        return FamilyTimelineRules(
            "occupancy_lifecycle", "occupancy_check", "occupancy_follow_up", False, True, False, True, False
        )
    return FamilyTimelineRules(
        "event_lifecycle", "event_date", None, False, False, False, True, False
    )


def _compute_timeline_dates(
    requirement: Dict[str, Any],
    *,
    semantics: LifecycleSemantics,
    field_contract: FieldContract,
    family: FamilyTimelineRules,
    records: Optional[List[Dict[str, Any]]],
    structured: Dict[str, Any],
) -> Dict[str, Optional[CalculatedDateField]]:
    out: Dict[str, Optional[CalculatedDateField]] = {
        "expiry_date": None,
        "review_date": None,
        "assessment_date": None,
        "inspection_date": None,
        "declaration_date": None,
        "tenancy_start_date": None,
        "tenancy_end_date": None,
        "registration_date": None,
        "event_date": None,
        "next_review_date": None,
    }

    if family.expects_expiry or semantics == "EXPIRY_BASED":
        out["expiry_date"] = _resolve_expiry_hierarchy(
            requirement,
            records=records,
            structured=structured,
            allows_estimate=family.allows_estimate,
        )

    out["assessment_date"] = _resolve_cer_date_field(
        records,
        structured,
        "assessment_date",
        "review_date",
        rule_prefix="assessment",
    )
    out["next_review_date"] = _resolve_cer_date_field(
        records,
        structured,
        "next_review_date",
        "follow_up_date",
        "follow_up_check_date",
        rule_prefix="next_review",
    )
    if out["next_review_date"] is None and family.expects_review:
        nr = _parse_date(requirement.get("next_review_date"))
        if nr:
            out["next_review_date"] = CalculatedDateField(
                calculated_date=_iso_date(nr),
                calculation_rule="requirement_row_next_review_date",
                authority_source=AUTHORITY_STRUCTURED_CER,
                confidence=CONFIDENCE_PARTIAL,
                is_estimated=False,
                is_verified=False,
                is_customer_supplied=True,
                is_ai_extracted=False,
                source_field="next_review_date",
                source_record_id=str(requirement.get("requirement_id") or "") or None,
            )

    out["declaration_date"] = _resolve_cer_date_field(
        records,
        structured,
        "protection_date",
        "deposit_received_date",
        "declaration_date",
        rule_prefix="declaration",
    )
    delivery = _resolve_cer_date_field(
        records,
        structured,
        "delivery_date",
        "served_date",
        "guide_version_date",
        rule_prefix="delivery",
    )
    if delivery:
        out["declaration_date"] = delivery

    out["tenancy_start_date"] = _resolve_cer_date_field(
        records,
        structured,
        "tenancy_start_date",
        rule_prefix="tenancy_start",
    )
    out["tenancy_end_date"] = _resolve_cer_date_field(
        records,
        structured,
        "fixed_term_end_date",
        "tenancy_end_date",
        rule_prefix="tenancy_end",
    )

    out["registration_date"] = _resolve_cer_date_field(
        records,
        structured,
        "registration_date",
        "issue_date",
        "registration_issued_date",
        rule_prefix="registration",
    )

    out["event_date"] = _resolve_cer_date_field(
        records,
        structured,
        "event_date",
        "completion_date",
        "inspection_date",
        rule_prefix="event",
    )
    out["inspection_date"] = _resolve_cer_date_field(
        records,
        structured,
        "inspection_date",
        "completion_date",
        rule_prefix="inspection",
    )

    if semantics in ("EVENT_BASED", "DECLARATION_BASED") and not family.expects_expiry:
        out["expiry_date"] = None

    if field_contract.does_not_expire and semantics != "EXPIRY_BASED":
        if not family.expects_expiry:
            out["expiry_date"] = None

    review_src = out["next_review_date"] or out["assessment_date"]
    out["review_date"] = review_src

    return out


def _select_primary_date(
    family: FamilyTimelineRules,
    dates: Dict[str, Optional[CalculatedDateField]],
) -> Tuple[Optional[CalculatedDateField], str]:
    cat = family.timeline_category

    if cat == "certificate_lifecycle":
        primary = dates.get("expiry_date")
        if primary and primary.calculated_date:
            concept = "estimated_compliance_date" if primary.is_estimated else "certificate_expiry"
            return primary, concept

    if cat == "hybrid_lifecycle":
        primary = dates.get("expiry_date")
        if primary and primary.calculated_date:
            concept = "estimated_compliance_date" if primary.is_estimated else "certificate_expiry"
            return primary, concept
        fallback = dates.get("next_review_date") or dates.get("review_date")
        if fallback and fallback.calculated_date:
            return fallback, "next_review_due"

    if cat == "assessment_lifecycle":
        if dates.get("next_review_date") and dates["next_review_date"].calculated_date:
            return dates["next_review_date"], "next_assessment_due"
        if dates.get("assessment_date") and dates["assessment_date"].calculated_date:
            return dates["assessment_date"], "assessment_date"

    if cat == "declaration_lifecycle":
        primary = dates.get("declaration_date")
        if primary and primary.calculated_date:
            concept = family.primary_concept if family.primary_concept in _CONCEPT_LABELS else "declaration_date"
            return primary, concept

    if cat == "tenancy_lifecycle":
        if dates.get("tenancy_start_date") and dates["tenancy_start_date"].calculated_date:
            return dates["tenancy_start_date"], "tenancy_start"
        if dates.get("tenancy_end_date") and dates["tenancy_end_date"].calculated_date:
            return dates["tenancy_end_date"], "tenancy_end"

    if cat == "registration_lifecycle":
        if dates.get("registration_date") and dates["registration_date"].calculated_date:
            return dates["registration_date"], "registration_date"
        if dates.get("next_review_date") and dates["next_review_date"].calculated_date:
            return dates["next_review_date"], "next_review_due"

    if cat == "event_lifecycle":
        primary = dates.get("event_date") or dates.get("declaration_date")
        if primary and primary.calculated_date:
            return primary, "event_date"

    if family.allows_estimate:
        est = dates.get("expiry_date")
        if est and est.is_estimated and est.calculated_date:
            return est, "estimated_compliance_date"

    return None, "missing"


def _reminder_start_date(
    primary_iso: Optional[str],
    reminder_window_days: Optional[int],
) -> Optional[str]:
    if not primary_iso or reminder_window_days is None or reminder_window_days <= 0:
        return None
    primary_dt = _parse_date(primary_iso)
    if primary_dt is None:
        return None
    start = primary_dt - timedelta(days=int(reminder_window_days))
    return _iso_date(start)


def _effective_attention_date(
    semantics: LifecycleSemantics,
    dates: Dict[str, Optional[CalculatedDateField]],
    primary: Optional[CalculatedDateField],
) -> Optional[str]:
    if primary and primary.calculated_date and not primary.is_estimated:
        return primary.calculated_date
    if semantics == "EXPIRY_BASED":
        exp = dates.get("expiry_date")
        return exp.calculated_date if exp else None
    if semantics == "REVIEW_BASED":
        nr = dates.get("next_review_date") or dates.get("assessment_date")
        return nr.calculated_date if nr else None
    if semantics == "TENANCY_LIFECYCLE":
        end = dates.get("tenancy_end_date")
        return end.calculated_date if end else None
    return primary.calculated_date if primary else None


def calculate_compliance_timeline(
    requirement: Dict[str, Any],
    *,
    compliance_evidence_records: Optional[List[Dict[str, Any]]] = None,
    reminder_days_before: Optional[int] = 30,
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Deterministic Compliance Timeline Calculator.
    Callable without background jobs or database access.
    """
    _ = as_of
    resolved = resolve_lifecycle_semantics(requirement)
    semantics = resolved.lifecycle_semantics
    field_contract = resolved.field_contract
    slug = _storage_slug(requirement)
    if slug in _FAMILY_RULES:
        family = _FAMILY_RULES[slug]
    else:
        family = _family_rules_for_requirement(requirement, semantics, field_contract)
    structured = _structured_declaration(requirement)

    date_fields = _compute_timeline_dates(
        requirement,
        semantics=semantics,
        field_contract=field_contract,
        family=family,
        records=compliance_evidence_records,
        structured=structured,
    )

    primary_field, primary_concept = _select_primary_date(family, date_fields)
    if primary_field is None and family.allows_estimate:
        est = _system_estimate_due_date(requirement)
        if est:
            primary_field = est
            primary_concept = "estimated_compliance_date"
            if date_fields.get("expiry_date") is None and family.expects_expiry:
                date_fields["expiry_date"] = est

    primary_iso = primary_field.calculated_date if primary_field else None
    if primary_field and primary_field.is_estimated:
        primary_concept = "estimated_compliance_date"

    reminder_window = reminder_days_before
    reminder_start = _reminder_start_date(primary_iso, reminder_window)

    attention_iso = _effective_attention_date(semantics, date_fields, primary_field)

    def _field_iso(key: str) -> Optional[str]:
        f = date_fields.get(key)
        return f.calculated_date if f else None

    timeline_reason = primary_field.calculation_rule if primary_field else "no_authoritative_date"

    return {
        "primary_date": primary_iso,
        "primary_date_label": _format_gb_label(primary_concept, primary_iso),
        "primary_date_concept": primary_concept,
        "primary_date_confidence": primary_field.confidence if primary_field else CONFIDENCE_UNKNOWN,
        "primary_date_source": primary_field.authority_source if primary_field else AUTHORITY_UNKNOWN,
        "primary_date_authority": primary_field.authority_source if primary_field else AUTHORITY_UNKNOWN,
        "is_estimated": bool(primary_field.is_estimated) if primary_field else False,
        "is_verified": bool(primary_field.is_verified) if primary_field else False,
        "is_customer_supplied": bool(primary_field.is_customer_supplied) if primary_field else False,
        "is_ai_extracted": bool(primary_field.is_ai_extracted) if primary_field else False,
        "reminder_window_days": reminder_window,
        "reminder_start_date": reminder_start,
        "expiry_date": _field_iso("expiry_date"),
        "review_date": _field_iso("review_date"),
        "assessment_date": _field_iso("assessment_date"),
        "inspection_date": _field_iso("inspection_date"),
        "declaration_date": _field_iso("declaration_date"),
        "tenancy_start_date": _field_iso("tenancy_start_date"),
        "tenancy_end_date": _field_iso("tenancy_end_date"),
        "registration_date": _field_iso("registration_date"),
        "event_date": _field_iso("event_date"),
        "next_review_date": _field_iso("next_review_date"),
        "effective_attention_date": attention_iso,
        "timeline_reason": timeline_reason,
        "timeline_version": TIMELINE_VERSION,
        "timeline_category": family.timeline_category,
        "lifecycle_semantics": semantics,
        "calculated_fields": {
            k: v.to_dict() if v else None for k, v in date_fields.items()
        },
        "family_rules": asdict(family),
    }


def build_compliance_timeline(
    requirement: Dict[str, Any],
    *,
    compliance_evidence_records: Optional[List[Dict[str, Any]]] = None,
    reminder_days_before: Optional[int] = 30,
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Public entry point — alias for calculate_compliance_timeline."""
    return calculate_compliance_timeline(
        requirement,
        compliance_evidence_records=compliance_evidence_records,
        reminder_days_before=reminder_days_before,
        as_of=as_of,
    )
