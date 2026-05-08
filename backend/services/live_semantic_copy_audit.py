from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from services.reporting_semantic_copy_contract import (
    CLIENT_STATUS_CHIP,
    NO_DISCLOSURE_REQUIRED,
    PORTFOLIO_SCORE,
    REPORT_EXPORT,
    build_semantic_copy_contract_row,
    semantic_wording_contract_base,
)
from services.trigger_propagation_audit import SEMANTIC_TRANSITIONS

# --- Violation classifications ---
PROHIBITED_WORDING_VIOLATION = "PROHIBITED_WORDING_VIOLATION"
MISSING_REQUIRED_DISCLOSURE = "MISSING_REQUIRED_DISCLOSURE"
UNSAFE_SIMPLIFICATION = "UNSAFE_SIMPLIFICATION"
SEMANTIC_COLLAPSE_RISK = "SEMANTIC_COLLAPSE_RISK"
CURRENTNESS_COLLAPSE = "CURRENTNESS_COLLAPSE"
VERIFICATION_COLLAPSE = "VERIFICATION_COLLAPSE"
FOLLOWUP_SUPPRESSION = "FOLLOWUP_SUPPRESSION"
EXPIRY_VALIDITY_COLLAPSE = "EXPIRY_VALIDITY_COLLAPSE"
OPERATIONAL_CLOSURE_COLLAPSE = "OPERATIONAL_CLOSURE_COLLAPSE"
CONTEXT_MISSING = "CONTEXT_MISSING"
DISCLOSURE_MISMATCH = "DISCLOSURE_MISMATCH"
UNKNOWN_SEMANTIC_MAPPING = "UNKNOWN_SEMANTIC_MAPPING"

SEVERITY_LOW = "LOW"
SEVERITY_MODERATE = "MODERATE"
SEVERITY_HIGH = "HIGH"
SEVERITY_CRITICAL = "CRITICAL"

_WORDING_TYPE_BADGE = "BADGE"
_WORDING_TYPE_CTA = "CTA"
_WORDING_TYPE_HEADLINE = "HEADLINE"
_WORDING_TYPE_BODY = "BODY"
_WORDING_TYPE_TABLE = "TABLE_HEADING"
_WORDING_TYPE_MODAL = "MODAL_SUMMARY"
_WORDING_TYPE_NOTIFICATION = "NOTIFICATION"

_STATE_MODEL_LIMITATION = (
    "Static scan of repository strings does not observe runtime semantic_state per record; "
    "associated_semantic_state is heuristic only."
)
_RUNTIME_CONVERGENCE_LIMITATION = (
    "Copy audit cannot prove which backend semantic transition applies to a UI label at runtime."
)

_DISCLOSURE_LEXICON = (
    "not independently verified",
    "not verified",
    "self-declared",
    "declaration",
    "pending review",
    "awaiting confirmation",
    "uploaded pending",
    "expiry review",
    "review required",
    "operationally open",
    "follow-up",
    "follow up",
    "outstanding",
    "partially complete",
    "incomplete",
    "additional evidence",
    "may still be required",
    "no submission",
    "not recorded",
)

_SKIP_PATH_SUBSTRINGS = (
    "node_modules",
    "/dist/",
    "\\dist\\",
    ".min.js",
    "/build/",
    "\\build\\",
    "/coverage/",
    "package-lock.json",
)

_SKIP_FILE_SUFFIXES = (
    ".test.js",
    ".test.jsx",
    ".test.ts",
    ".test.tsx",
    ".spec.js",
    ".spec.jsx",
    ".snap",
    ".map",
)

_SCAN_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

_PATH_TO_CONSUMER: Tuple[Tuple[str, str], ...] = (
    ("clientcommandcenter", "COMMAND_CENTER"),
    ("commandcenter", "COMMAND_CENTER"),
    ("compliancescore", "PORTFOLIO_SCORE"),
    ("scoredriver", "PORTFOLIO_SCORE"),
    ("complianceoverview", "PORTFOLIO_SCORE"),
    ("scorebucket", "PORTFOLIO_SCORE"),
    ("requirement", "REQUIREMENT_LIST"),
    ("resolvedrequirement", "REQUIREMENT_LIST"),
    ("propertydetail", "PROPERTY_SUMMARY"),
    ("propertysummary", "PROPERTY_SUMMARY"),
    ("evidencestatus", "CLIENT_STATUS_CHIP"),
    ("urgencydisplay", "CLIENT_STATUS_CHIP"),
    ("presentdomain", "CLIENT_STATUS_CHIP"),
    ("notification", "NOTIFICATION_EMAIL_PATHS"),
    ("emailpath", "NOTIFICATION_EMAIL_PATHS"),
    ("reminder", "REMINDER_ENGINE"),
    ("sla", "REMINDER_ENGINE"),
    ("escalation", "REMINDER_ENGINE"),
    ("export", "REPORT_EXPORT"),
    ("pdf", "REPORT_EXPORT"),
    ("report", "REPORT_EXPORT"),
    ("admin", "COMMAND_CENTER"),
)


def _repo_root_default() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_path_key(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _should_skip_file(path: Path) -> bool:
    s = str(path).lower()
    for sub in _SKIP_PATH_SUBSTRINGS:
        if sub.lower() in s:
            return True
    for suf in _SKIP_FILE_SUFFIXES:
        if s.endswith(suf):
            return True
    return path.suffix.lower() not in _SCAN_EXTENSIONS


def _unescape_js_string(inner: str) -> str:
    return (
        inner.replace("\\\\", "\\")
        .replace('\\"', '"')
        .replace("\\'", "'")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "")
    )


def _extract_quoted_strings(content: str) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for quote in ('"', "'"):
        pattern = re.compile(rf"{quote}((?:[^\\{quote}]|\\.)*){quote}")
        for m in pattern.finditer(content):
            raw = m.group(1)
            text = _unescape_js_string(raw).strip()
            if len(text) < 4 or len(text) > 400:
                continue
            if not re.search(r"[a-zA-Z]{3,}", text):
                continue
            out.append((m.start(), text))
    return out


_COMPLIANCE_HINT = re.compile(
    r"\b(compliant|compliance|verified|verify|current|valid|complete|completed|resolved|passed|"
    r"pending|expired|expiry|follow[- ]?up|declaration|partial|uploaded|assessment|certificate|"
    r"operationally|outstanding|renewal|review required|not recorded|missing|score|evidence)\b",
    re.IGNORECASE,
)


def _is_compliance_relevant(text: str) -> bool:
    return bool(_COMPLIANCE_HINT.search(text))


def _infer_source_surface(rel_path: str) -> str:
    lower = rel_path.lower()
    if "modal" in lower:
        return _WORDING_TYPE_MODAL
    if "notification" in lower or "email" in lower:
        return _WORDING_TYPE_NOTIFICATION
    if "command" in lower and "center" in lower:
        return "COMMAND_CENTER_SUMMARY"
    if "score" in lower or "compliance" in lower:
        return "COMPLIANCE_SCORE_SUMMARY"
    if "requirement" in lower:
        return "REQUIREMENT_CARD"
    if "property" in lower:
        return "PROPERTY_SUMMARY_SURFACE"
    if "evidence" in lower or "chip" in lower or "badge" in lower:
        return "EVIDENCE_CHIP_OR_BADGE"
    if "urgency" in lower:
        return "URGENCY_CHIP"
    return "GENERAL_UI_COPY"


def _infer_wording_type(rel_path: str, text: str) -> str:
    lower = rel_path.lower()
    tl = text.lower()
    if any(x in tl for x in ("submit", "continue", "view ", "open ", "complete action", "upload")):
        return _WORDING_TYPE_CTA
    if len(text) < 36 and "\n" not in text:
        return _WORDING_TYPE_BADGE
    if "heading" in lower or "column" in lower or "header" in lower:
        return _WORDING_TYPE_TABLE
    if "modal" in lower:
        return _WORDING_TYPE_MODAL
    if len(text) > 120:
        return _WORDING_TYPE_BODY
    return _WORDING_TYPE_HEADLINE


def _infer_consumer(rel_path: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "", rel_path.lower())
    for needle, consumer in _PATH_TO_CONSUMER:
        if needle in compact:
            return consumer
    return "REQUIREMENT_LIST"


def _infer_associated_semantic_state(text: str) -> str:
    tl = text.lower()
    if any(x in tl for x in ("expiry review", "review required", "renewal", "validity requires")):
        return "EXPIRY_REVIEW_REQUIRED"
    if "verified current" in tl:
        return "VERIFIED_CURRENT"
    if any(x in tl for x in ("expired", "past validity", "past validity window")):
        return "VERIFIED_EXPIRED"
    if any(x in tl for x in ("operationally open", "work in progress", "not closed operationally")):
        return "OPERATIONALLY_OPEN"
    if any(x in tl for x in ("follow-up", "follow up", "followup", "remediation may still")):
        return "ASSESSMENT_FOLLOWUP_REQUIRED"
    if any(x in tl for x in ("partially complete", "additional evidence", "incomplete submission")):
        return "PARTIALLY_COMPLETE"
    if any(x in tl for x in ("self-declared", "declaration on file")):
        return "DECLARATION_RECORDED"
    if "declaration" in tl and "not" not in tl[:30]:
        return "DECLARATION_RECORDED"
    if any(x in tl for x in ("uploaded pending", "awaiting confirmation", "not yet attested")):
        return "UPLOADED_UNCONFIRMED"
    if any(x in tl for x in ("not recorded", "no submission", "awaiting record")):
        return "MISSING"
    if any(x in tl for x in ("completeness pending", "awaiting further evidence")):
        return "COMPLETENESS_PENDING"
    return "UNKNOWN_MAPPED"


def _disclosure_present(text: str) -> bool:
    tl = text.lower()
    return any(phrase in tl for phrase in _DISCLOSURE_LEXICON)


def _simplified_representation_detected(text: str, wording_type: str) -> bool:
    if wording_type == _WORDING_TYPE_BADGE and len(text) < 48:
        return True
    if len(text) < 28 and "\n" not in text:
        return True
    return False


def map_audit_consumer_to_contract_consumer(consumer: str) -> str:
    """Map inventory consumer labels to Phase 2 contract consumers (deterministic)."""
    c = consumer.upper()
    if c == "COMMAND_CENTER":
        return CLIENT_STATUS_CHIP
    if c == "REQUIREMENT_LIST":
        return REPORT_EXPORT
    if c in (CLIENT_STATUS_CHIP, REPORT_EXPORT, PORTFOLIO_SCORE):
        return c
    if c == "PROPERTY_SUMMARY":
        return CLIENT_STATUS_CHIP
    if c == "NOTIFICATION_EMAIL_PATHS":
        return REPORT_EXPORT
    if c == "REMINDER_ENGINE":
        return REPORT_EXPORT
    return REPORT_EXPORT


def extract_live_semantic_strings(
    repo_root: Optional[Path] = None,
    scan_roots: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    root = repo_root or _repo_root_default()
    roots = list(scan_roots or ("frontend/src", "backend"))
    extractions: List[Dict[str, Any]] = []
    for rel in roots:
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if _should_skip_file(path):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel_key = _normalize_path_key(path, root)
            for offset, text in _extract_quoted_strings(content):
                if not _is_compliance_relevant(text):
                    continue
                extractions.append(
                    {
                        "source_file": rel_key,
                        "byte_offset": offset,
                        "extracted_text": text,
                    }
                )
    extractions.sort(key=lambda x: (x["source_file"], x["byte_offset"], x["extracted_text"]))
    return extractions


def build_semantic_copy_inventory(
    extractions: Sequence[Dict[str, Any]],
    repo_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    root = repo_root or _repo_root_default()
    rows: List[Dict[str, Any]] = []
    for ex in extractions:
        rel_path = str(ex.get("source_file") or "")
        text = str(ex.get("extracted_text") or "")
        consumer = _infer_consumer(rel_path)
        wording_type = _infer_wording_type(rel_path, text)
        state_guess = _infer_associated_semantic_state(text)
        contract = semantic_wording_contract_base(state_guess if state_guess != "UNKNOWN_MAPPED" else "MISSING")
        disc = _disclosure_present(text)
        simp = _simplified_representation_detected(text, wording_type)
        reference = f"{state_guess if state_guess != 'UNKNOWN_MAPPED' else 'MISSING'}:{consumer}"
        rows.append(
            {
                "source_surface": _infer_source_surface(rel_path),
                "source_file": rel_path,
                "semantic_context": wording_type,
                "detected_wording": text,
                "wording_type": wording_type,
                "associated_semantic_state": state_guess,
                "consumer": consumer,
                "simplified_representation_detected": simp,
                "disclosure_present": disc,
                "governance_contract_reference": reference,
                "base_contract_prohibited_sample": contract["prohibited_wording"][:8],
            }
        )
    rows.sort(key=lambda r: (r["source_file"], r["detected_wording"], r["consumer"]))
    _ = root
    return rows


def _severity_for_violation(violation_type: str, consumer: str, text: str) -> str:
    c = consumer.upper()
    high_surface = c in (CLIENT_STATUS_CHIP, REPORT_EXPORT, "COMMAND_CENTER")
    tl = text.lower()
    if violation_type == PROHIBITED_WORDING_VIOLATION:
        if high_surface or ("compliant" in tl and c == "PORTFOLIO_SCORE"):
            return SEVERITY_CRITICAL if c in (CLIENT_STATUS_CHIP, REPORT_EXPORT) else SEVERITY_HIGH
        return SEVERITY_HIGH if high_surface else SEVERITY_MODERATE
    if violation_type == MISSING_REQUIRED_DISCLOSURE:
        return SEVERITY_HIGH if high_surface else SEVERITY_MODERATE
    if violation_type == UNSAFE_SIMPLIFICATION:
        return SEVERITY_CRITICAL if c == CLIENT_STATUS_CHIP else SEVERITY_HIGH
    if violation_type == UNKNOWN_SEMANTIC_MAPPING:
        return SEVERITY_LOW
    return SEVERITY_MODERATE


def evaluate_inventory_violations(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    text = row["detected_wording"]
    tl = text.lower()
    consumer = row["consumer"]
    state_raw = row["associated_semantic_state"]
    state = state_raw if state_raw != "UNKNOWN_MAPPED" else "MISSING"

    contract_consumer = map_audit_consumer_to_contract_consumer(consumer)
    contract_row = build_semantic_copy_contract_row(state, contract_consumer)

    base = semantic_wording_contract_base(state)
    prohibited = [p.lower() for p in base.get("prohibited_wording") or []]
    required_disclosures = list(base.get("required_disclosures") or [])

    violations: List[Dict[str, Any]] = []

    for token in prohibited:
        if len(token) >= 3 and token in tl:
            violations.append(
                {
                    "violation_type": PROHIBITED_WORDING_VIOLATION,
                    "severity": _severity_for_violation(PROHIBITED_WORDING_VIOLATION, consumer, text),
                    "detail": f"contains prohibited token '{token}' for inferred_state={state}",
                    "consumer": consumer,
                    "source_file": row["source_file"],
                    "detected_wording": text,
                    "associated_semantic_state": state_raw,
                    "governance_contract_reference": row["governance_contract_reference"],
                }
            )

    if "compliant" in tl and state != "VERIFIED_CURRENT":
        if not any(v["violation_type"] == PROHIBITED_WORDING_VIOLATION for v in violations):
            violations.append(
                {
                    "violation_type": SEMANTIC_COLLAPSE_RISK,
                    "severity": SEVERITY_HIGH,
                    "detail": "'compliant' language with inferred_state != VERIFIED_CURRENT",
                    "consumer": consumer,
                    "source_file": row["source_file"],
                    "detected_wording": text,
                    "associated_semantic_state": state_raw,
                    "governance_contract_reference": row["governance_contract_reference"],
                }
            )

    if any(x in tl for x in ("current", "valid", "up to date")) and state in ("EXPIRY_REVIEW_REQUIRED", "VERIFIED_EXPIRED"):
        violations.append(
            {
                "violation_type": CURRENTNESS_COLLAPSE,
                "severity": SEVERITY_HIGH,
                "detail": "currentness language under expiry-sensitive inferred state",
                "consumer": consumer,
                "source_file": row["source_file"],
                "detected_wording": text,
                "associated_semantic_state": state_raw,
                "governance_contract_reference": row["governance_contract_reference"],
            }
        )

    if any(x in tl for x in ("resolved", "closed", "complete")) and state in (
        "OPERATIONALLY_OPEN",
        "ASSESSMENT_FOLLOWUP_REQUIRED",
        "FOLLOWUP_REQUIRED",
    ):
        if "partial" not in tl:
            violations.append(
                {
                    "violation_type": OPERATIONAL_CLOSURE_COLLAPSE,
                    "severity": SEVERITY_HIGH,
                    "detail": "closure language while inferred state suggests open follow-up",
                    "consumer": consumer,
                    "source_file": row["source_file"],
                    "detected_wording": text,
                    "associated_semantic_state": state_raw,
                    "governance_contract_reference": row["governance_contract_reference"],
                }
            )

    if ("verified" in tl) and state in ("DECLARATION_RECORDED", "UPLOADED_UNCONFIRMED"):
        if "not " not in tl[:48]:
            violations.append(
                {
                    "violation_type": VERIFICATION_COLLAPSE,
                    "severity": SEVERITY_MODERATE,
                    "detail": "verification language without explicit negation for declaration/uploaded-unconfirmed context",
                    "consumer": consumer,
                    "source_file": row["source_file"],
                    "detected_wording": text,
                    "associated_semantic_state": state_raw,
                    "governance_contract_reference": row["governance_contract_reference"],
                }
            )

    needs_disc = any(str(d) != NO_DISCLOSURE_REQUIRED for d in required_disclosures)
    if needs_disc and not row["disclosure_present"] and len(text) > 12:
        violations.append(
            {
                "violation_type": MISSING_REQUIRED_DISCLOSURE,
                "severity": _severity_for_violation(MISSING_REQUIRED_DISCLOSURE, consumer, text),
                "detail": f"missing disclosure markers for required_disclosures={required_disclosures}",
                "consumer": consumer,
                "source_file": row["source_file"],
                "detected_wording": text,
                "associated_semantic_state": state_raw,
                "governance_contract_reference": row["governance_contract_reference"],
            }
        )

    if row["simplified_representation_detected"] and contract_row["representation_safety"] in (
        "UNSAFE_FOR_SIMPLIFIED_REPORTING",
        "SAFE_WITH_DISCLAIMER",
        "UNSAFE_FOR_COMPLIANT_LANGUAGE",
    ):
        if not row["disclosure_present"]:
            violations.append(
                {
                    "violation_type": UNSAFE_SIMPLIFICATION,
                    "severity": _severity_for_violation(UNSAFE_SIMPLIFICATION, consumer, text),
                    "detail": "compressed wording without disclosure under elevated representation risk",
                    "consumer": consumer,
                    "source_file": row["source_file"],
                    "detected_wording": text,
                    "associated_semantic_state": state_raw,
                    "governance_contract_reference": row["governance_contract_reference"],
                }
            )

    if state_raw == "UNKNOWN_MAPPED" and _is_compliance_relevant(text):
        violations.append(
            {
                "violation_type": UNKNOWN_SEMANTIC_MAPPING,
                "severity": SEVERITY_LOW,
                "detail": "compliance-adjacent copy could not be mapped to a semantic_transition",
                "consumer": consumer,
                "source_file": row["source_file"],
                "detected_wording": text,
                "associated_semantic_state": state_raw,
                "governance_contract_reference": row["governance_contract_reference"],
            }
        )

    seen: Set[Tuple[str, str, str, str]] = set()
    unique: List[Dict[str, Any]] = []
    for v in violations:
        key = (v["violation_type"], v["detail"], v["source_file"], v["detected_wording"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(v)
    return sorted(unique, key=lambda x: (x["severity"], x["violation_type"], x["source_file"], x["detected_wording"]))


def audit_reporting_wording_contract_compare(row: Dict[str, Any]) -> Dict[str, Any]:
    state = row["associated_semantic_state"]
    st = state if state != "UNKNOWN_MAPPED" else "MISSING"
    cc = build_semantic_copy_contract_row(st, map_audit_consumer_to_contract_consumer(row["consumer"]))
    return {
        "inventory_source_file": row["source_file"],
        "contract_representation_safety": cc["representation_safety"],
        "contract_export_readiness": cc["export_readiness"],
        "contract_prohibited": cc["prohibited_wording"],
    }


# Spec alias (same behavior as compare helper)
audit_reporting_wording_contract = audit_reporting_wording_contract_compare


def audit_reporting_disclosure_contract(row: Dict[str, Any]) -> Dict[str, Any]:
    state = row["associated_semantic_state"]
    st = state if state != "UNKNOWN_MAPPED" else "MISSING"
    cc = build_semantic_copy_contract_row(st, map_audit_consumer_to_contract_consumer(row["consumer"]))
    return {
        "inventory_source_file": row["source_file"],
        "required_disclosures": cc["required_disclosures"],
        "disclosure_present_in_string": row["disclosure_present"],
    }


def audit_reporting_representation_risk(row: Dict[str, Any]) -> Dict[str, Any]:
    vlist = evaluate_inventory_violations(row)
    return {
        "inventory_source_file": row["source_file"],
        "violations": vlist,
        "violation_count": len(vlist),
    }


def audit_reporting_export_readiness(row: Dict[str, Any]) -> Dict[str, Any]:
    state = row["associated_semantic_state"]
    st = state if state != "UNKNOWN_MAPPED" else "MISSING"
    cc = build_semantic_copy_contract_row(st, map_audit_consumer_to_contract_consumer(row["consumer"]))
    return {
        "inventory_source_file": row["source_file"],
        "export_readiness": cc["export_readiness"],
        "trust_risk": cc["trust_risk"],
    }


def _build_consumer_audit_views(
    violations: Sequence[Dict[str, Any]],
    inventory: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    targets = (
        CLIENT_STATUS_CHIP,
        REPORT_EXPORT,
        PORTFOLIO_SCORE,
        "COMMAND_CENTER",
        "REQUIREMENT_LIST",
        "REMINDER_ENGINE",
        "NOTIFICATION_EMAIL_PATHS",
    )
    views: Dict[str, Any] = {}
    for consumer in targets:
        cv = [v for v in violations if v["consumer"] == consumer]
        top_v = sorted(cv, key=lambda x: (x["severity"], x["violation_type"]))[:25]
        high_risk = sorted(
            {v["detected_wording"] for v in cv if v["severity"] in (SEVERITY_CRITICAL, SEVERITY_HIGH)}
        )[:20]
        simpl = sorted({v["detected_wording"] for v in cv if v["violation_type"] == UNSAFE_SIMPLIFICATION})[:20]
        missing_d = sorted({v["source_file"] for v in cv if v["violation_type"] == MISSING_REQUIRED_DISCLOSURE})[:20]
        prohibited_n = sum(1 for v in cv if v["violation_type"] == PROHIBITED_WORDING_VIOLATION)
        freq_simp: Dict[str, int] = {}
        for r in inventory:
            if r["consumer"] != consumer:
                continue
            if r["simplified_representation_detected"]:
                freq_simp[r["detected_wording"]] = freq_simp.get(r["detected_wording"], 0) + 1
        most_simp = dict(sorted(freq_simp.items(), key=lambda x: (-x[1], x[0]))[:15])
        views[consumer] = {
            "violation_count": len(cv),
            "top_violations": top_v,
            "highest_risk_wording": high_risk,
            "unsafe_simplification_strings": simpl,
            "missing_disclosure_sources": missing_d,
            "prohibited_wording_exposure_count": prohibited_n,
            "most_frequent_simplified_strings": most_simp,
        }
    return views


def _unsafe_wording_exposure_summary(violations: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    acc: Dict[str, int] = {}
    for v in violations:
        vt = v["violation_type"]
        acc[vt] = acc.get(vt, 0) + 1
    return dict(sorted(acc.items()))


def build_live_semantic_copy_audit_phase3_snapshot(
    repo_root: Optional[Path] = None,
    scan_roots: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    root = repo_root or _repo_root_default()
    extractions = extract_live_semantic_strings(root, scan_roots)
    inventory = build_semantic_copy_inventory(extractions, root)

    violation_lists = [evaluate_inventory_violations(r) for r in inventory]
    row_has_violation = [len(v) > 0 for v in violation_lists]
    all_violations: List[Dict[str, Any]] = []
    for vl in violation_lists:
        all_violations.extend(vl)

    by_severity: Dict[str, int] = {}
    for v in all_violations:
        by_severity[v["severity"]] = by_severity.get(v["severity"], 0) + 1
    by_severity = dict(sorted(by_severity.items()))

    by_consumer: Dict[str, int] = {}
    for v in all_violations:
        by_consumer[v["consumer"]] = by_consumer.get(v["consumer"], 0) + 1
    by_consumer = dict(sorted(by_consumer.items()))

    prohibited_matrix: Dict[str, int] = {}
    for v in all_violations:
        if v["violation_type"] == PROHIBITED_WORDING_VIOLATION:
            prohibited_matrix[v["source_file"]] = prohibited_matrix.get(v["source_file"], 0) + 1
    prohibited_matrix = dict(sorted(prohibited_matrix.items(), key=lambda x: (-x[1], x[0]))[:80])

    missing_disc_matrix: Dict[str, int] = {}
    for v in all_violations:
        if v["violation_type"] == MISSING_REQUIRED_DISCLOSURE:
            missing_disc_matrix[v["source_file"]] = missing_disc_matrix.get(v["source_file"], 0) + 1
    missing_disc_matrix = dict(sorted(missing_disc_matrix.items(), key=lambda x: (-x[1], x[0]))[:80])

    critical_violations = [v for v in all_violations if v["severity"] == SEVERITY_CRITICAL]
    highest_risk_surfaces = sorted({v["source_file"] for v in critical_violations})[:40]

    safest_surfaces = sorted(
        {
            inventory[i]["source_file"]
            for i, has_v in enumerate(row_has_violation)
            if not has_v and inventory[i]["disclosure_present"]
        }
    )[:40]

    collapse_hotspots: Dict[str, int] = {}
    for v in all_violations:
        if v["violation_type"] in (SEMANTIC_COLLAPSE_RISK, CURRENTNESS_COLLAPSE, VERIFICATION_COLLAPSE):
            collapse_hotspots[v["source_file"]] = collapse_hotspots.get(v["source_file"], 0) + 1
    collapse_hotspots = dict(sorted(collapse_hotspots.items(), key=lambda x: (-x[1], x[0]))[:40])

    gaps_unresolved = sorted(
        {r["source_file"] for r in inventory if r["associated_semantic_state"] == "UNKNOWN_MAPPED"}
    )[:60]

    consumer_views = _build_consumer_audit_views(all_violations, inventory)

    exposure_summary = _unsafe_wording_exposure_summary(all_violations)

    _trust_order = (
        "CRITICAL_TRUST_RISK",
        "HIGH_TRUST_RISK",
        "MODERATE_TRUST_RISK",
        "LOW_TRUST_RISK",
    )
    trust_rankings = sorted(
        [
            {
                "source_file": r["source_file"],
                "consumer": r["consumer"],
                "trust_risk": audit_reporting_export_readiness(r)["trust_risk"],
                "wording_excerpt": r["detected_wording"][:120],
            }
            for r in inventory
        ],
        key=lambda x: (
            _trust_order.index(x["trust_risk"]) if x["trust_risk"] in _trust_order else 9,
            x["consumer"],
            x["source_file"],
        ),
    )[:150]

    return {
        "phase": "Live Semantic Copy Inventory & Violation Audit Phase 3",
        "scope": "read-only repository scan vs reporting semantic copy contracts",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "non_blocking": True,
        "repo_root": str(root),
        "semantic_transitions_reference": list(SEMANTIC_TRANSITIONS),
        "inventory_total_extractions": len(extractions),
        "inventory_total_rows": len(inventory),
        "violations_total": len(all_violations),
        "violations_by_severity": by_severity,
        "violations_by_consumer": by_consumer,
        "prohibited_wording_matrix": prohibited_matrix,
        "missing_disclosure_matrix": missing_disc_matrix,
        "highest_risk_wording_surfaces": highest_risk_surfaces,
        "safest_wording_surfaces": safest_surfaces,
        "semantic_collapse_hotspots": collapse_hotspots,
        "unresolved_semantic_mapping_surfaces": gaps_unresolved,
        "unsafe_wording_exposure_summary": exposure_summary,
        "trust_risk_rankings": trust_rankings,
        "violations_sample": all_violations[:200],
        "consumer_audit_views": consumer_views,
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
    }


def write_live_semantic_copy_audit_phase3_json(
    target_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
) -> Path:
    snap = build_live_semantic_copy_audit_phase3_snapshot(repo_root)
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "LIVE_SEMANTIC_COPY_AUDIT_PHASE3.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path