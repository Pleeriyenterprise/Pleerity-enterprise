"""
Requirement-aware evidence / document classification and matching (Compliance Vault Pro).

Layered model:
1) User intent: requirement_id, declared document_type, upload_route_context
2) Filename / title hints
3) Extracted structured fields / OCR traits (document_type, issuer, certificate numbers, headings)
4) Plausibility vs expected families for the requirement + cross-family blockers

Results are explainable (reason codes + detection_signals), auditable, and persisted on documents.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from services.evidence_document_taxonomy import (
    ALL_CANONICAL_FAMILIES,
    CANONICAL_DEPOSIT_PROTECTION,
    CANONICAL_EICR,
    CANONICAL_EPC,
    CANONICAL_FIRE_ALARM_INSPECTION,
    CANONICAL_FIRE_RISK_ASSESSMENT,
    CANONICAL_GAS_SAFETY,
    CANONICAL_HMO_LICENCE,
    CANONICAL_LANDLORD_REGISTRATION,
    CANONICAL_LEGIONELLA_RISK_ASSESSMENT,
    CANONICAL_OCCUPATION_CONTRACT,
    CANONICAL_PAT_TEST,
    CANONICAL_RIGHT_TO_RENT_EVIDENCE,
    CANONICAL_SMOKE_CO_ALARM_EVIDENCE,
    CANONICAL_TENANCY_AGREEMENT,
    CANONICAL_UNKNOWN,
    MATCH_OUTCOME_MATCH_CONFIRMED,
    MATCH_OUTCOME_MATCH_LIKELY,
    MATCH_OUTCOME_MISMATCH_SUSPECTED,
    MATCH_OUTCOME_NEEDS_ADMIN_REVIEW,
    MATCH_OUTCOME_UNKNOWN_TYPE,
    POLICY_ACCEPT_CONFIRMED,
    POLICY_ACCEPT_PENDING,
    POLICY_BLOCK_UPLOAD,
    POLICY_QUARANTINE,
    REASON_CODE_ADMIN_OVERRIDE_MATCH,
    REASON_CODE_DECLARED_TYPE_MISMATCH,
    REASON_CODE_EXTRACTION_AMBIGUOUS,
    REASON_CODE_EXTRACTION_FAMILY_MISMATCH,
    REASON_CODE_FILENAME_HINT_MISMATCH,
    REASON_CODE_LOW_SIGNAL,
    REASON_CODE_NONE,
    REASON_CODE_NO_REQUIREMENT_LINK,
    REASON_CODE_STRONG_FAMILY_MISMATCH,
    expected_canonical_families_for_requirement,
)

_STRONG = 0.82
_LIKELY = 0.62
_WEAK = 0.38

# (canonical_family, positive_patterns, anti_patterns_for_other_families_hint)
_FAMILY_RULES: List[Tuple[str, Tuple[str, ...], Tuple[str, ...]]] = [
    (
        CANONICAL_EPC,
        ("energy performance certificate", "epc rating", " epc ", "asset rating", "sap rating", "energy efficiency"),
        ("eicr", "electrical installation", "gas safe", "cp12"),
    ),
    (
        CANONICAL_EICR,
        (
            "eicr",
            "electrical installation condition report",
            "periodic inspection report",
            "fixed electrical installation",
            "bs7671",
            "niceic",
            "electrical safety standards",
        ),
        ("energy performance", " epc ", "gas safe", "cp12", "landlord gas"),
    ),
    (
        CANONICAL_GAS_SAFETY,
        (
            "gas safety",
            "cp12",
            "cp17",
            "landlord gas safety record",
            "gas safe register",
            "gas installation",
            "flue test",
        ),
        ("eicr", "electrical installation condition", "energy performance certificate", " epc "),
    ),
    (
        CANONICAL_FIRE_ALARM_INSPECTION,
        ("fire alarm test", "fire detection", "fire alarm certificate", "weekly fire alarm", "l5 fire"),
        ("energy performance", " epc ", "gas safe", "eicr"),
    ),
    (
        CANONICAL_LEGIONELLA_RISK_ASSESSMENT,
        ("legionella", "l8 assessment", "water systems risk", "acop l8"),
        ("gas safe", "eicr", "epc"),
    ),
    (
        CANONICAL_RIGHT_TO_RENT_EVIDENCE,
        ("right to rent", "immigration act", "acceptable documents", "time limited right to rent"),
        ("gas safe", "eicr", "epc", "electrical installation condition"),
    ),
    (
        CANONICAL_SMOKE_CO_ALARM_EVIDENCE,
        ("smoke alarm", "carbon monoxide alarm", "co alarm", "heat alarm", "interlinked"),
        ("eicr", "epc", "gas safe certificate"),
    ),
    (
        CANONICAL_FIRE_RISK_ASSESSMENT,
        ("fire risk assessment", "fra template", "hmo fire risk", "five steps to risk assessment"),
        ("gas safe", "eicr"),
    ),
    (
        CANONICAL_PAT_TEST,
        ("portable appliance", "pat test", "pat label", "inspection & testing of electrical equipment"),
        ("eicr", "epc", "gas safe"),
    ),
    (
        CANONICAL_HMO_LICENCE,
        ("hmo licence", "hmo license", "licence conditions", "local housing authority"),
        (),
    ),
    (
        CANONICAL_LANDLORD_REGISTRATION,
        ("landlord registration", "registered landlord", "landlord reg no"),
        (),
    ),
    (
        CANONICAL_DEPOSIT_PROTECTION,
        ("deposit protection", "custodial scheme", "insured scheme", "dps", "mydeposits", "tenancy deposit"),
        (),
    ),
    (
        CANONICAL_TENANCY_AGREEMENT,
        ("assured shorthold tenancy", "tenancy agreement", "ast agreement", "tenant agreement"),
        ("gas safe", "eicr", "epc certificate"),
    ),
    (
        CANONICAL_OCCUPATION_CONTRACT,
        ("occupation contract", "written statement of information", "contract-holder", "rent smart wales"),
        (),
    ),
]


def _flatten_text(
    *,
    filename: str,
    user_declared_document_type: Optional[str],
    extracted_data: Optional[Dict[str, Any]],
    original_title: Optional[str] = None,
) -> str:
    parts: List[str] = [filename or "", original_title or "", user_declared_document_type or ""]
    if isinstance(extracted_data, dict):
        for k in (
            "document_type",
            "document_subtype",
            "doc_type",
            "certificate_title",
            "issuer",
            "summary",
            "raw_text_excerpt",
        ):
            v = extracted_data.get(k)
            if v:
                parts.append(str(v))
        nested = extracted_data.get("structured_fields")
        if isinstance(nested, dict):
            for v in nested.values():
                if isinstance(v, (str, int, float)):
                    parts.append(str(v))
    blob = " ".join(parts)
    blob = re.sub(r"\s+", " ", blob).strip().lower()
    return blob


def _score_families(blob: str, filename: str = "") -> Tuple[Dict[str, float], List[str]]:
    """Return per-family scores 0..1 and list of human-readable signal strings."""
    signals: List[str] = []
    scores: Dict[str, float] = {f: 0.0 for f in ALL_CANONICAL_FAMILIES if f != CANONICAL_UNKNOWN}
    if not blob or len(blob) < 3:
        return scores, signals

    for fam, positives, negatives in _FAMILY_RULES:
        pos_hits = sum(1 for p in positives if p in blob)
        neg_hits = sum(1 for n in negatives if n in blob)
        if pos_hits == 0:
            continue
        base = min(1.0, 0.35 + 0.22 * pos_hits)
        penalty = 0.18 * neg_hits
        scores[fam] = max(scores[fam], max(0.0, base - penalty))
        if pos_hits:
            signals.append(f"content_hint:{fam}:{pos_hits}")

    # Filename-only nudges (short blob still gets weak signal)
    fn = (filename or "").lower()
    if fn:
        if "epc" in fn or "energy-performance" in fn:
            scores[CANONICAL_EPC] = max(scores[CANONICAL_EPC], 0.45)
            signals.append("filename_hint:EPC")
        if "eicr" in fn or "electrical" in fn:
            scores[CANONICAL_EICR] = max(scores[CANONICAL_EICR], 0.45)
            signals.append("filename_hint:EICR")
        if "gas" in fn or "cp12" in fn:
            scores[CANONICAL_GAS_SAFETY] = max(scores[CANONICAL_GAS_SAFETY], 0.45)
            signals.append("filename_hint:GAS_SAFETY")
        if "rtr" in fn or "right-to-rent" in fn or "right_to_rent" in fn:
            scores[CANONICAL_RIGHT_TO_RENT_EVIDENCE] = max(scores[CANONICAL_RIGHT_TO_RENT_EVIDENCE], 0.45)
            signals.append("filename_hint:RIGHT_TO_RENT")

    return scores, signals


def _best_family(scores: Dict[str, float]) -> Tuple[str, float, bool]:
    """Return (family, confidence, ambiguous)."""
    if not scores:
        return CANONICAL_UNKNOWN, 0.0, True
    top = max(scores.values()) if scores else 0.0
    if top < 0.2:
        return CANONICAL_UNKNOWN, top, True
    leaders = sorted([f for f, s in scores.items() if s >= top - 0.08 and s >= 0.2], key=lambda f: (-scores[f], f))
    if len(leaders) > 1 and top < _LIKELY:
        return CANONICAL_UNKNOWN, top, True
    fam = leaders[0]
    second = scores.get(sorted([f for f in scores if f != fam], key=lambda f: -scores[f])[0], 0.0) if len(scores) > 1 else 0.0
    ambiguous = (top - second) < 0.12 and second >= 0.35
    return fam, top, ambiguous


def _declared_type_to_canonical(user_declared: Optional[str]) -> Optional[str]:
    if not user_declared or not str(user_declared).strip():
        return None
    t = str(user_declared).strip().lower()
    m = {
        "epc": CANONICAL_EPC,
        "eicr": CANONICAL_EICR,
        "gas": CANONICAL_GAS_SAFETY,
        "gas safety": CANONICAL_GAS_SAFETY,
        "cp12": CANONICAL_GAS_SAFETY,
        "fire alarm": CANONICAL_FIRE_ALARM_INSPECTION,
        "legionella": CANONICAL_LEGIONELLA_RISK_ASSESSMENT,
        "pat": CANONICAL_PAT_TEST,
        "right to rent": CANONICAL_RIGHT_TO_RENT_EVIDENCE,
        "right_to_rent": CANONICAL_RIGHT_TO_RENT_EVIDENCE,
    }
    for k, v in m.items():
        if k in t:
            return v
    return None


def evaluate_document_requirement_match(
    *,
    requirement: Optional[Dict[str, Any]],
    filename: str,
    user_declared_document_type: Optional[str],
    extracted_data: Optional[Dict[str, Any]],
    upload_route_context: str = "unknown",
    original_title: Optional[str] = None,
    reviewed_match_outcome: Optional[str] = None,
    reviewed_match_actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full layered evaluation. Returns a dict safe to merge into Mongo ``documents`` and for APIs.

    Keys: predicted_document_type, predicted_document_subtype, match_outcome, match_confidence,
    mismatch_reason_code, mismatch_reason_text, matched_requirement_family, detection_signals,
    evidence_match_policy, evidence_satisfies_requirement, user_messages (list),
    requirement_evidence_mismatch (legacy bool), manual_review_flag_suggested.
    """
    rid = (requirement or {}).get("requirement_id") if requirement else None
    req_key = ""
    expected: frozenset = frozenset()
    if requirement:
        expected = frozenset(expected_canonical_families_for_requirement(requirement))
        req_key = str(
            requirement.get("requirement_type") or requirement.get("requirement_code") or ""
        ).strip()

    blob = _flatten_text(
        filename=filename or "",
        user_declared_document_type=user_declared_document_type,
        extracted_data=extracted_data,
        original_title=original_title,
    )
    user_messages: List[str] = []
    scores, signals = _score_families(blob, filename=filename or "")
    raw_pred_family, raw_conf, raw_ambiguous = _best_family(scores)
    pred_family, conf, ambiguous = raw_pred_family, raw_conf, raw_ambiguous

    declared_canon = _declared_type_to_canonical(user_declared_document_type)
    if declared_canon:
        signals.append(f"user_declared_type:{declared_canon}")
        pred_family = declared_canon
        conf = max(conf, _LIKELY)

    # Extraction/content strongly contradicts the selected requirement even if the declared type was ticked incorrectly
    if (
        raw_pred_family != CANONICAL_UNKNOWN
        and raw_pred_family not in expected
        and raw_conf >= _STRONG
        and rid
        and expected
    ):
        user_messages.append(
            f"Extracted content looks like {raw_pred_family.replace('_', ' ')} evidence, "
            f"which does not satisfy this obligation (expected: {', '.join(sorted(expected))})."
        )
        return {
            "predicted_document_type": raw_pred_family,
            "predicted_document_subtype": None,
            "match_outcome": MATCH_OUTCOME_MISMATCH_SUSPECTED,
            "match_confidence": round(float(raw_conf), 4),
            "mismatch_reason_code": REASON_CODE_EXTRACTION_FAMILY_MISMATCH,
            "mismatch_reason_text": "Structured / content classification contradicts this requirement family.",
            "matched_requirement_family": req_key or None,
            "detection_signals": {
                "signals": signals + ["raw_prediction_override_declared"],
                "scores": scores,
                "route": upload_route_context,
                "declared_canonical": declared_canon,
            },
            "evidence_match_policy": POLICY_QUARANTINE,
            "evidence_satisfies_requirement": False,
            "user_messages": user_messages,
            "requirement_evidence_mismatch": True,
            "manual_review_flag_suggested": True,
        }

    if reviewed_match_outcome == MATCH_OUTCOME_MATCH_CONFIRMED:
        return {
            "predicted_document_type": pred_family,
            "predicted_document_subtype": None,
            "match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED,
            "match_confidence": 1.0,
            "mismatch_reason_code": REASON_CODE_ADMIN_OVERRIDE_MATCH,
            "mismatch_reason_text": None,
            "matched_requirement_family": req_key or None,
            "detection_signals": {"signals": signals + ["admin_override:confirmed"], "scores": scores, "route": upload_route_context},
            "evidence_match_policy": POLICY_ACCEPT_CONFIRMED,
            "evidence_satisfies_requirement": True,
            "user_messages": [],
            "requirement_evidence_mismatch": False,
            "manual_review_flag_suggested": False,
            "reviewed_match_outcome": reviewed_match_outcome,
            "reviewed_match_actor_id": reviewed_match_actor_id,
        }

    # No requirement link — classification only
    if not rid or not expected:
        outcome = MATCH_OUTCOME_UNKNOWN_TYPE if pred_family == CANONICAL_UNKNOWN or ambiguous else MATCH_OUTCOME_MATCH_LIKELY
        if pred_family == CANONICAL_UNKNOWN:
            outcome = MATCH_OUTCOME_UNKNOWN_TYPE
        policy = POLICY_ACCEPT_PENDING
        if outcome == MATCH_OUTCOME_UNKNOWN_TYPE:
            policy = POLICY_QUARANTINE
        return {
            "predicted_document_type": pred_family,
            "predicted_document_subtype": None,
            "match_outcome": outcome,
            "match_confidence": round(float(conf), 4),
            "mismatch_reason_code": REASON_CODE_NO_REQUIREMENT_LINK if not rid else REASON_CODE_LOW_SIGNAL,
            "mismatch_reason_text": None,
            "matched_requirement_family": None,
            "detection_signals": {"signals": signals, "scores": scores, "route": upload_route_context},
            "evidence_match_policy": policy,
            "evidence_satisfies_requirement": False if rid else None,
            "user_messages": [
                "We could not confidently classify this file against a requirement yet. "
                "Link a requirement or wait for extraction, then confirm details."
            ],
            "requirement_evidence_mismatch": False,
            "manual_review_flag_suggested": pred_family == CANONICAL_UNKNOWN or ambiguous,
        }

    matched_requirement_family = req_key

    in_family = pred_family in expected

    # Declared type incompatible with requirement (belt-and-suspenders vs registry validation)
    if declared_canon and declared_canon not in expected:
        user_messages.append(
            f"This upload was labeled as evidence that looks like {declared_canon.replace('_', ' ')} "
            f"but the selected obligation expects different evidence types."
        )
        return {
            "predicted_document_type": declared_canon,
            "predicted_document_subtype": None,
            "match_outcome": MATCH_OUTCOME_MISMATCH_SUSPECTED,
            "match_confidence": max(conf, _STRONG),
            "mismatch_reason_code": REASON_CODE_DECLARED_TYPE_MISMATCH,
            "mismatch_reason_text": "Declared document type is not in the allowed family for this requirement.",
            "matched_requirement_family": matched_requirement_family,
            "detection_signals": {"signals": signals, "scores": scores, "route": upload_route_context},
            "evidence_match_policy": POLICY_BLOCK_UPLOAD,
            "evidence_satisfies_requirement": False,
            "user_messages": user_messages,
            "requirement_evidence_mismatch": True,
            "manual_review_flag_suggested": True,
        }

    # Strong content/filename mismatch
    if pred_family != CANONICAL_UNKNOWN and not in_family and conf >= _STRONG:
        user_messages.append(
            f"This file looks more like {pred_family.replace('_', ' ')} evidence than what this obligation expects. "
            "If that is wrong, pick another requirement or contact support."
        )
        return {
            "predicted_document_type": pred_family,
            "predicted_document_subtype": None,
            "match_outcome": MATCH_OUTCOME_MISMATCH_SUSPECTED,
            "match_confidence": round(float(conf), 4),
            "mismatch_reason_code": REASON_CODE_STRONG_FAMILY_MISMATCH,
            "mismatch_reason_text": f"Predicted {pred_family} vs expected families {sorted(expected)}",
            "matched_requirement_family": matched_requirement_family,
            "detection_signals": {"signals": signals, "scores": scores, "route": upload_route_context},
            "evidence_match_policy": POLICY_QUARANTINE,
            "evidence_satisfies_requirement": False,
            "user_messages": user_messages,
            "requirement_evidence_mismatch": True,
            "manual_review_flag_suggested": True,
        }

    # Filename-only mismatch at medium confidence (pre-extraction gate)
    if pred_family != CANONICAL_UNKNOWN and not in_family and conf >= _LIKELY and len(blob) < 800:
        user_messages.append(
            "The file name suggests a different certificate type than the selected obligation. "
            "Confirm the file is correct or change the requirement before uploading."
        )
        return {
            "predicted_document_type": pred_family,
            "predicted_document_subtype": None,
            "match_outcome": MATCH_OUTCOME_MISMATCH_SUSPECTED,
            "match_confidence": round(float(conf), 4),
            "mismatch_reason_code": REASON_CODE_FILENAME_HINT_MISMATCH,
            "mismatch_reason_text": "Filename / shallow text hints do not match expected evidence family.",
            "matched_requirement_family": matched_requirement_family,
            "detection_signals": {"signals": signals, "scores": scores, "route": upload_route_context},
            "evidence_match_policy": POLICY_BLOCK_UPLOAD if upload_route_context == "client_upload_pre_analysis" else POLICY_QUARANTINE,
            "evidence_satisfies_requirement": False,
            "user_messages": user_messages,
            "requirement_evidence_mismatch": True,
            "manual_review_flag_suggested": True,
        }

    if ambiguous and pred_family == CANONICAL_UNKNOWN:
        return {
            "predicted_document_type": CANONICAL_UNKNOWN,
            "predicted_document_subtype": None,
            "match_outcome": MATCH_OUTCOME_NEEDS_ADMIN_REVIEW,
            "match_confidence": round(float(conf), 4),
            "mismatch_reason_code": REASON_CODE_EXTRACTION_AMBIGUOUS,
            "mismatch_reason_text": "We need more information before this requirement can be confirmed.",
            "matched_requirement_family": matched_requirement_family,
            "detection_signals": {"signals": signals, "scores": scores, "route": upload_route_context},
            "evidence_match_policy": POLICY_QUARANTINE,
            "evidence_satisfies_requirement": False,
            "user_messages": [
                "We could not confidently match this file to the selected obligation from its contents. "
                "An administrator may need to review it."
            ],
            "requirement_evidence_mismatch": False,
            "manual_review_flag_suggested": True,
        }

    if in_family and conf >= _STRONG:
        user_messages.append(
            "This file appears consistent with the selected obligation. Confirm extracted dates on the next step."
        )
        return {
            "predicted_document_type": pred_family,
            "predicted_document_subtype": None,
            "match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED,
            "match_confidence": round(float(conf), 4),
            "mismatch_reason_code": REASON_CODE_NONE,
            "mismatch_reason_text": None,
            "matched_requirement_family": matched_requirement_family,
            "detection_signals": {"signals": signals, "scores": scores, "route": upload_route_context},
            "evidence_match_policy": POLICY_ACCEPT_CONFIRMED,
            "evidence_satisfies_requirement": True,
            "user_messages": user_messages,
            "requirement_evidence_mismatch": False,
            "manual_review_flag_suggested": False,
        }

    if in_family:
        user_messages.append(
            "This file is plausibly the right evidence type. Review extracted details before treating it as compliant."
        )
        return {
            "predicted_document_type": pred_family,
            "predicted_document_subtype": None,
            "match_outcome": MATCH_OUTCOME_MATCH_LIKELY,
            "match_confidence": round(float(conf), 4),
            "mismatch_reason_code": REASON_CODE_NONE,
            "mismatch_reason_text": None,
            "matched_requirement_family": matched_requirement_family,
            "detection_signals": {"signals": signals, "scores": scores, "route": upload_route_context},
            "evidence_match_policy": POLICY_ACCEPT_PENDING,
            "evidence_satisfies_requirement": True,
            "user_messages": user_messages,
            "requirement_evidence_mismatch": False,
            "manual_review_flag_suggested": conf < _LIKELY,
        }

    # Unknown / low signal with requirement selected
    user_messages.append(
        "We could not confidently classify this file against the selected obligation from available signals. "
        "Wait for extraction or ask an administrator to review."
    )
    return {
        "predicted_document_type": pred_family,
        "predicted_document_subtype": None,
        "match_outcome": MATCH_OUTCOME_UNKNOWN_TYPE,
        "match_confidence": round(float(conf), 4),
        "mismatch_reason_code": REASON_CODE_LOW_SIGNAL,
        "mismatch_reason_text": "Insufficient confident classification for this requirement.",
        "matched_requirement_family": matched_requirement_family,
        "detection_signals": {"signals": signals, "scores": scores, "route": upload_route_context},
        "evidence_match_policy": POLICY_QUARANTINE,
        "evidence_satisfies_requirement": False,
        "user_messages": user_messages,
        "requirement_evidence_mismatch": False,
        "manual_review_flag_suggested": True,
    }


def match_evaluation_to_persisted_document_fields(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """Subset for Mongo $set on documents collection."""
    keys = (
        "predicted_document_type",
        "predicted_document_subtype",
        "match_outcome",
        "match_confidence",
        "mismatch_reason_code",
        "mismatch_reason_text",
        "matched_requirement_family",
        "detection_signals",
        "evidence_match_policy",
        "evidence_satisfies_requirement",
        "evidence_match_user_messages",
        "requirement_evidence_mismatch",
        "reviewed_match_outcome",
        "reviewed_match_actor_id",
        "reviewed_match_at",
    )
    out: Dict[str, Any] = {}
    for k in keys:
        if k in evaluation and evaluation[k] is not None:
            out[k] = evaluation[k]
    if "user_messages" in evaluation:
        out["evidence_match_user_messages"] = evaluation["user_messages"]
    return out


async def persist_document_evidence_match_after_extraction(db: Any, document_id: str) -> None:
    """
    Recompute and persist match fields after AI extraction (document_analysis and similar paths).
    Keeps parity with ``routes.documents._run_analysis_after_upload``.
    """
    from services.requirement_evidence_authority import sync_for_documents_touching

    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        return
    req = None
    rid = doc.get("requirement_id")
    cid = doc.get("client_id")
    if rid and cid:
        req = await db.requirements.find_one({"requirement_id": rid, "client_id": cid}, {"_id": 0})
    ai = doc.get("ai_extraction") if isinstance(doc.get("ai_extraction"), dict) else {}
    extracted = ai.get("data") if isinstance(ai.get("data"), dict) else None
    if extracted is None and isinstance(doc.get("ai_extracted_data"), dict):
        extracted = doc.get("ai_extracted_data")
    if not isinstance(extracted, dict):
        extracted = {}
    mev = evaluate_document_requirement_match(
        requirement=req,
        filename=str(doc.get("file_name") or ""),
        user_declared_document_type=doc.get("document_type"),
        extracted_data=extracted or None,
        upload_route_context="document_analysis_service",
    )
    patch = match_evaluation_to_persisted_document_fields(mev)
    if mev.get("manual_review_flag_suggested"):
        patch["manual_review_flag"] = True
    if patch:
        await db.documents.update_one({"document_id": document_id}, {"$set": patch})
    await sync_for_documents_touching(db, document_id=document_id)


def document_blocks_verified_satisfaction(doc: Dict[str, Any]) -> bool:
    """True when this document must not be used to mark a requirement compliant while unresolved."""
    if doc.get("evidence_satisfies_requirement") is False:
        return True
    mo = str(doc.get("match_outcome") or "").strip()
    if mo in (MATCH_OUTCOME_MISMATCH_SUSPECTED, MATCH_OUTCOME_NEEDS_ADMIN_REVIEW, MATCH_OUTCOME_UNKNOWN_TYPE):
        return True
    if doc.get("requirement_evidence_mismatch") is True:
        return True
    return False
