"""
Deterministic validation for evidence review (no OCR/AI in this module).
Consumes optional structured data from document_metadata / ai_extraction.data / related fields only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional

from models.evidence_review import EvidenceReviewState


# Requirement types / codes that are typically expiry-driven in UK compliance vaults
_EXPIRY_EXPECTED_CODES = frozenset(
    {
        "GAS_SAFETY",
        "GAS_SAFETY_CERTIFICATE",
        "EICR",
        "EPC",
        "HMO_LICENCE",
        "HMO_LICENSE",
        "PAT",
        "PAT_TEST",
        "FIRE_ALARM",
        "SMOKE_ALARM",
    }
)

_EICR_FAIL_OUTCOMES = frozenset(
    {
        "UNSATISFACTORY",
        "C1",
        "C2",
        "FI",
        "FAIL",
    }
)


@dataclass
class ValidationContext:
    requirement_code: str
    requirement_type: str
    jurisdiction: Optional[str]
    document: Dict[str, Any]
    property_doc: Optional[Dict[str, Any]]
    extracted_fields: Dict[str, Any] = field(default_factory=dict)


def _parse_date_val(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    s = str(v).strip()
    if not s:
        return None
    try:
        s2 = s.replace("Z", "+00:00")
        if "T" in s2:
            return datetime.fromisoformat(s2).date()
        return datetime.fromisoformat(s2[:10]).date()
    except (TypeError, ValueError):
        return None


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def document_calendar_expiry_date(document: Dict[str, Any]) -> Optional[date]:
    """Earliest known certificate/document expiry from top-level fields and optional structured blobs (no OCR)."""
    extracted = _gather_extracted(document)
    for key in ("expiry_date", "next_inspection_date"):
        d = _parse_date_val(document.get(key)) or _parse_date_val(extracted.get(key))
        if d:
            return d
    return None


def document_is_expired_calendrically(document: Dict[str, Any]) -> bool:
    d = document_calendar_expiry_date(document)
    if d is None:
        return False
    return d < _today_utc()


def _normalize_req_code(requirement: Dict[str, Any]) -> str:
    raw = (requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip()
    return raw.upper().replace("-", "_")


def _gather_extracted(document: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    meta = document.get("document_metadata") if isinstance(document.get("document_metadata"), dict) else {}
    out.update(meta)
    ai = document.get("ai_extraction") if isinstance(document.get("ai_extraction"), dict) else {}
    data = ai.get("data") if isinstance(ai.get("data"), dict) else {}
    out.update(data)
    alt = document.get("ai_extracted_data") if isinstance(document.get("ai_extracted_data"), dict) else {}
    out.update(alt)
    ai_assist = document.get("ai_assistance") if isinstance(document.get("ai_assistance"), dict) else {}
    ef = ai_assist.get("extracted_fields") if isinstance(ai_assist.get("extracted_fields"), dict) else {}
    out.update(ef)
    return out


def build_validation_context(
    *,
    requirement: Optional[Dict[str, Any]],
    document: Dict[str, Any],
    property_doc: Optional[Dict[str, Any]],
) -> ValidationContext:
    req = requirement or {}
    code = _normalize_req_code(req)
    rtype = str(req.get("requirement_type") or "").strip().upper()
    jur = None
    if isinstance(document.get("validation_result"), dict):
        jur = document["validation_result"].get("jurisdiction") or document["validation_result"].get("scoring_jurisdiction")
    extracted = _gather_extracted(document)
    return ValidationContext(
        requirement_code=code or rtype or "UNKNOWN",
        requirement_type=rtype or code or "UNKNOWN",
        jurisdiction=str(jur).strip() if jur else None,
        document=document,
        property_doc=property_doc,
        extracted_fields=extracted,
    )


class EvidenceValidationEngine:
    """Contract implementation for Evidence Review V2."""

    def evaluate(self, ctx: ValidationContext) -> Dict[str, Any]:
        warnings: List[str] = []
        failures: List[str] = []
        missing_required: List[str] = []
        extracted = dict(ctx.extracted_fields)
        ai_assistance = ctx.document.get("ai_assistance") if isinstance(ctx.document.get("ai_assistance"), dict) else {}
        ai_flags = ai_assistance.get("ai_flags") if isinstance(ai_assistance.get("ai_flags"), list) else []
        ai_warnings = ai_assistance.get("extraction_warnings") if isinstance(ai_assistance.get("extraction_warnings"), list) else []
        anomaly_flags = ai_assistance.get("anomaly_flags") if isinstance(ai_assistance.get("anomaly_flags"), list) else []
        anomaly_risk = float(ai_assistance.get("anomaly_risk_score") or 0.0)

        doc_expiry = (
            _parse_date_val(ctx.document.get("expiry_date"))
            or _parse_date_val(extracted.get("expiry_date"))
            or _parse_date_val(extracted.get("next_inspection_date"))
        )
        issue_dt = _parse_date_val(ctx.document.get("issue_date")) or _parse_date_val(extracted.get("issue_date"))

        today = _today_utc()
        if doc_expiry and doc_expiry < today:
            failures.append("DOCUMENT_EXPIRED")
            return self._result(
                "FAIL",
                warnings,
                failures,
                missing_required,
                extracted,
                EvidenceReviewState.REJECTED.value,
            )

        code = ctx.requirement_code
        expects_expiry = code in _EXPIRY_EXPECTED_CODES or any(
            x in code for x in ("GAS", "EICR", "EPC", "HMO", "PAT")
        )
        if expects_expiry and doc_expiry is None:
            warnings.append("MISSING_EXPIRY_DATE")
        if "LOW_EXTRACTION_CONFIDENCE" in ai_warnings:
            warnings.append("AI_LOW_CONFIDENCE_EXTRACTION")

        prop_line = None
        if ctx.property_doc:
            addr = ctx.property_doc.get("address") if isinstance(ctx.property_doc.get("address"), dict) else {}
            prop_line = (
                (addr.get("line1") or addr.get("line_1") or "")
                if isinstance(addr, dict)
                else None
            )
            if not prop_line:
                prop_line = ctx.property_doc.get("address_line_1") or ctx.property_doc.get("display_address")

        doc_addr = (
            extracted.get("property_address")
            or extracted.get("premises_address")
            or extracted.get("installation_address")
            or extracted.get("address")
        )
        if isinstance(doc_addr, dict):
            doc_addr = doc_addr.get("line1") or doc_addr.get("line_1") or ""
        doc_addr_s = str(doc_addr).strip().lower() if doc_addr else ""
        prop_s = str(prop_line).strip().lower() if prop_line else ""

        if doc_addr_s and prop_s:
            if doc_addr_s not in prop_s and prop_s not in doc_addr_s:
                norm_doc = "".join(ch for ch in doc_addr_s if ch.isalnum())
                norm_prop = "".join(ch for ch in prop_s if ch.isalnum())
                if norm_doc and norm_prop and norm_doc != norm_prop:
                    failures.append("PROPERTY_ADDRESS_MISMATCH")
        if "POSSIBLE_ADDRESS_MISMATCH" in ai_flags and "PROPERTY_ADDRESS_MISMATCH" not in failures:
            warnings.append("AI_ADDRESS_MISMATCH_SIGNAL")

        # EICR outcomes — only enforce when outcome signals exist (no fabrication)
        if "EICR" in code or ctx.requirement_type == "EICR":
            outcome_raw = extracted.get("overall_result") or extracted.get("outcome") or extracted.get("eicr_outcome")
            if outcome_raw is None and isinstance(extracted.get("result_summary"), dict):
                outcome_raw = extracted["result_summary"].get("overall_result")
            outcome = str(outcome_raw or "").strip().upper()
            if outcome:
                tokens = set()
                for part in outcome.replace(",", " ").replace("/", " ").split():
                    tokens.add(part.upper())
                if tokens & _EICR_FAIL_OUTCOMES or outcome.upper() in _EICR_FAIL_OUTCOMES:
                    failures.append("EICR_UNSATISFACTORY_OR_DEFECT_CODE")
        if "EICR_CONTAINS_SERIOUS_OBSERVATIONS" in ai_flags and "EICR_UNSATISFACTORY_OR_DEFECT_CODE" not in failures:
            warnings.append("AI_EICR_SERIOUS_OBSERVATIONS")
        if anomaly_risk >= 0.65:
            warnings.append("AI_HIGH_ANOMALY_RISK")

        validation_status = "PASS"
        if failures:
            validation_status = "FAIL"
        elif warnings:
            validation_status = "WARN"
        elif not extracted and expects_expiry:
            validation_status = "NOT_RUN"
        elif not extracted:
            validation_status = "NOT_RUN"

        suggested = EvidenceReviewState.ACCEPTED_UNVERIFIED.value
        if validation_status == "FAIL":
            suggested = EvidenceReviewState.NEEDS_INFORMATION.value

        conf = 0.85 if validation_status == "PASS" else (0.55 if validation_status == "WARN" else 0.35)
        if validation_status == "NOT_RUN":
            conf = 0.25

        return self._result(
            validation_status,
            warnings,
            failures,
            missing_required,
            extracted,
            suggested,
            confidence_score=conf,
            ai_assistance_summary={
                "ai_flags": ai_flags,
                "ai_warnings": ai_warnings,
                "anomaly_flags": anomaly_flags,
                "anomaly_risk_score": anomaly_risk,
            },
        )

    def _result(
        self,
        validation_status: str,
        warnings: List[str],
        failures: List[str],
        missing_required: List[str],
        extracted_fields: Dict[str, Any],
        suggested_review_outcome: str,
        *,
        confidence_score: float = 0.0,
        ai_assistance_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "validation_status": validation_status,
            "warnings": warnings,
            "failures": failures,
            "required_fields_missing": missing_required,
            "extracted_fields": extracted_fields,
            "confidence_score": confidence_score,
            "suggested_review_outcome": suggested_review_outcome,
            "ai_assistance_summary": ai_assistance_summary or {},
        }


def evaluate_document_validation_from_db_rows(
    *,
    requirement: Optional[Dict[str, Any]],
    document: Dict[str, Any],
    property_doc: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ctx = build_validation_context(requirement=requirement, document=document, property_doc=property_doc)
    return EvidenceValidationEngine().evaluate(ctx)
