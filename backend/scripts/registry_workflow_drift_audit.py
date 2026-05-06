#!/usr/bin/env python3
"""
Live registry / runtime workflow drift audit (read-only).

Compares effective_evidence_resolution + resolver take_action + workflow reference
against governance expectations. Does not mutate data.

Usage (from backend/):
  python -m scripts.registry_workflow_drift_audit [--json PATH] [--md PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow running as script or module
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.compliance_evidence_record_service import effective_evidence_resolution
from services.compliance_requirement_engine import resolve_engine_payload_from_code
from services.requirement_action_resolver import enrich_take_action_envelope_for_client, resolve_take_action_envelope
from services.requirement_code_registry import CANONICAL_REQUIREMENT_CODES, normalize_requirement_code
from services.governance_coverage_registry import GOVERNANCE_SURFACE_REGISTRY
from services.requirement_workflow_audit import (
    WC_DOCUMENT_UPLOAD,
    WC_EXTERNAL_ASSESSMENT_EVIDENCE,
    WC_GUIDED_DECLARATION,
    WC_GUIDANCE_ONLY,
    WC_MULTI_EVIDENCE,
    WC_REGISTRATION_TRACKING,
    WC_TENANT_DELIVERY,
    WC_UNKNOWN,
    _FALLBACK_REFERENCE_BY_CANONICAL,
    compute_workflow_mismatch_flags,
    describe_runtime_behaviour,
    resolve_workflow_class_reference,
)
JURISDICTIONS = ("england", "scotland", "wales", "northern_ireland")

# Canonical registry union decision-record fallbacks (condition standards, jobs, system rows).
_AUDIT_REQUIREMENT_CODES = sorted(set(CANONICAL_REQUIREMENT_CODES) | set(_FALLBACK_REFERENCE_BY_CANONICAL.keys()))

# workflow audit flag id -> (drift_category, default_severity)
_FLAG_CATEGORY: Dict[str, Tuple[str, str]] = {
    "ALIAS_LEGACY_STORAGE_SLUG": ("CANONICAL_IDENTITY_DRIFT", "LOW"),
    "ALIAS_NOT_NORMALIZED": ("CANONICAL_IDENTITY_DRIFT", "MEDIUM"),
    "REGISTRATION_TRACKING_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "TENANT_DELIVERY_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "RIGHT_TO_RENT_GUIDED_DECLARATION_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "DEPOSIT_GUIDED_DECLARATION_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "WALES_OCCUPATION_CONTRACT_GUIDED_DECLARATION_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "TENANCY_AGREEMENT_GUIDED_DECLARATION_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "LEGIONELLA_EXTERNAL_ASSESSMENT_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "LEAD_TESTING_EXTERNAL_ASSESSMENT_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "LEAD_TESTING_UNSUPPORTED_JURISDICTION": ("JURISDICTION_DRIFT", "HIGH"),
    "CONDITION_STANDARD_UNSUPPORTED_JURISDICTION": ("JURISDICTION_DRIFT", "HIGH"),
    "CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY": ("CTA_DRIFT", "HIGH"),
    "CONDITION_STANDARD_MARKED_COMPLETE_WITHOUT_OPERATIONAL_SIGNALS": ("OPERATIONAL_CONVERGENCE_DRIFT", "HIGH"),
    "CONDITION_STANDARD_DOCUMENT_COMPLETION_VIOLATION": ("OPERATIONAL_CONVERGENCE_DRIFT", "HIGH"),
    "MULTI_EVIDENCE_DOCUMENT_ONLY": ("EVIDENCE_MODE_DRIFT", "MEDIUM"),
    "EVIDENCE_MODE_MISMATCH": ("EVIDENCE_MODE_DRIFT", "MEDIUM"),
    "RESOLVER_CTA_MISMATCH": ("WORKFLOW_CLASS_DRIFT", "HIGH"),
    "WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "GUIDED_DECLARATION_WITHOUT_STRUCTURED_PAYLOAD": ("EVIDENCE_MODE_DRIFT", "HIGH"),
    "CERTIFICATE_WORKFLOW_WITHOUT_DOCUMENT_MODE": ("EVIDENCE_MODE_DRIFT", "MEDIUM"),
    "WORKFLOW_PRIMARY_CTA_GOVERNANCE_VIOLATION": ("CTA_DRIFT", "HIGH"),
    "ASSESSMENT_COMPLETED_WITH_UNRESOLVED_ACTIONS": ("OPERATIONAL_CONVERGENCE_DRIFT", "MEDIUM"),
    "WORKFLOW_SEMANTIC_COLLAPSE_RISK": ("REPORTING_SEMANTIC_DRIFT", "HIGH"),
    "WORKFLOW_REPORTING_SEMANTIC_DRIFT": ("REPORTING_SEMANTIC_DRIFT", "HIGH"),
    "DECLARATION_PRESENTED_AS_VERIFIED_PROOF": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "DECLARATION_REPORTED_AS_EXTERNALLY_VERIFIED": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "CONDITION_STANDARD_DOCUMENT_EQUIVALENCE": ("REPORTING_SEMANTIC_DRIFT", "HIGH"),
    "CONDITION_STANDARD_REPORTED_AS_DOCUMENT_COMPLIANT": ("REPORTING_SEMANTIC_DRIFT", "HIGH"),
    "ASSESSMENT_TREATED_AS_REMEDIATION": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "ASSESSMENT_REPORTED_AS_REMEDIATED": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "WORKFLOW_COMPLETION_SEMANTIC_DRIFT": ("REPORTING_SEMANTIC_DRIFT", "HIGH"),
    "WORKFLOW_SCORE_SEMANTIC_DRIFT": ("SCORE_CONFIDENCE_DRIFT", "MEDIUM"),
    "ASSESSMENT_PRESENTED_AS_REMEDIATED": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "DECLARATION_PRESENTED_AS_EXTERNALLY_VERIFIED": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "CONDITION_STANDARD_PRESENTED_AS_UPLOAD_COMPLETE": ("REPORTING_SEMANTIC_DRIFT", "HIGH"),
    "DOCUMENT_WORKFLOW_MISSING_EXPIRY_SEMANTICS": ("SCORE_CONFIDENCE_DRIFT", "LOW"),
    "FORBIDDEN_COMPLIANCE_REPRESENTATION": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "DECLARATION_PRESENTED_AS_AUDIT_READY": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "UNVERIFIED_WORKFLOW_PRESENTED_AS_VERIFIED": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
    "ASSESSMENT_PRESENTED_AS_OPERATIONALLY_SAFE": ("REPORTING_SEMANTIC_DRIFT", "MEDIUM"),
}


def _build_governance_coverage_analysis(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Static governance coverage summary + drift heuristics from audit findings."""
    surfaces_none = sorted(sid for sid, row in GOVERNANCE_SURFACE_REGISTRY.items() if row.get("enforcement_level") == "NONE")
    surfaces_partial = sorted(sid for sid, row in GOVERNANCE_SURFACE_REGISTRY.items() if row.get("enforcement_level") == "PARTIAL")
    surfaces_strict = sorted(sid for sid, row in GOVERNANCE_SURFACE_REGISTRY.items() if row.get("enforcement_level") == "STRICT")
    fallback = sorted(sid for sid, row in GOVERNANCE_SURFACE_REGISTRY.items() if row.get("uses_local_fallback_logic"))
    noncanonical_surfaces = sorted(sid for sid, row in GOVERNANCE_SURFACE_REGISTRY.items() if row.get("allows_noncanonical_requirement_rows"))
    finding_ids = {str(f.get("finding_id") or "") for f in findings}
    return {
        "surfaces_enforcement_none": surfaces_none,
        "surfaces_enforcement_partial": surfaces_partial,
        "surfaces_enforcement_strict": surfaces_strict,
        "surfaces_with_local_fallback": fallback,
        "surfaces_allowing_noncanonical_rows": noncanonical_surfaces,
        "audit_flags_include_semantic_collapse": "WORKFLOW_SEMANTIC_COLLAPSE_RISK" in finding_ids,
        "audit_flags_include_completion_drift": "WORKFLOW_COMPLETION_SEMANTIC_DRIFT" in finding_ids,
        "notes": (
            "Resolver + requirements surfaces remain PARTIAL: server take_action contract vs client "
            "requirementTakeActionResolver must stay aligned. Reminder generation is NONE until wired."
        ),
    }


def _governance_coverage_markdown_sections(analysis: Dict[str, Any]) -> List[str]:
    return [
        "",
        "## Governance Coverage Gaps",
        "",
        "**Surfaces at enforcement NONE (highest drift risk):** " + ", ".join(analysis.get("surfaces_enforcement_none") or []) + ".",
        "",
        "**Surfaces at PARTIAL enforcement (fallback or duplicate semantics likely):** "
        + ", ".join(analysis.get("surfaces_enforcement_partial") or [])
        + ".",
        "",
        "**STRICT governance surfaces:** " + ", ".join(analysis.get("surfaces_enforcement_strict") or []) + ".",
        "",
        "**Surfaces flagged as using local fallback logic:** " + ", ".join(analysis.get("surfaces_with_local_fallback") or []) + ".",
        "",
        "## Frontend Semantic Drift Risks",
        "",
        "- Client CTA resolver (`frontend/src/utils/requirementTakeActionResolver.js`) duplicates resolver intent mapping — "
        "misalignment produces drift not visible in backend-only audits.",
        "- Dashboard / Command Centre copy uses document-centric language (e.g. “Missing documents”) without workflow-class qualifiers.",
        "",
        "## Duplicate Runtime Semantic Paths",
        "",
        "- Evidence policy: `effective_evidence_resolution` vs published `registry_metadata.evidence_resolution`.",
        "- Workflow reference: decision-record fallbacks vs optional registry `client_workflow_class`.",
        "- Score drivers vs workflow execution semantics (`EXECUTION_SEMANTICS_METADATA`) — not yet unified.",
        "",
        "## Noncanonical Requirement Rendering Risks",
        "",
        "- Surfaces allowing noncanonical rows in registry: "
        + ", ".join(analysis.get("surfaces_allowing_noncanonical_rows") or ["(none)"])
        + ".",
        "- CI guard: `governance_validation_engine.validate_noncanonical_requirement_ids` for synthetic IDs on governed rows.",
        "",
    ]


def _norm_wf(wf: str) -> str:
    u = str(wf or "").strip().upper()
    if u == "LEGACY_DOCUMENT_UPLOAD":
        return WC_DOCUMENT_UPLOAD
    return u


def _policy_fallback_legacy(policy: Dict[str, Any]) -> bool:
    return str(policy.get("primary_resolution_workflow") or "").strip().upper() == "LEGACY_DOCUMENT_UPLOAD"


def _reference_expects_structured_first(ref: str) -> bool:
    return ref in (
        WC_GUIDED_DECLARATION,
        WC_TENANT_DELIVERY,
        WC_REGISTRATION_TRACKING,
        WC_EXTERNAL_ASSESSMENT_EVIDENCE,
    )


def _engine_certificate_like(eng: Dict[str, Any]) -> bool:
    cls = str(eng.get("compliance_requirement_class") or "").strip().upper()
    ful = str(eng.get("fulfillment_mode") or eng.get("engine_fulfillment_mode") or "").strip().lower()
    return cls == "DOCUMENT" or ful == "document"


def run_audit() -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    scenarios: List[Dict[str, Any]] = []

    for code in _AUDIT_REQUIREMENT_CODES:
        for jur in JURISDICTIONS:
            row = _audit_one(code, jur)
            scenarios.append(row["scenario"])
            findings.extend(row["findings"])

    # Dedupe identical findings (same code, jur, category, message signature)
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for f in findings:
        key = (
            f.get("canonical_requirement_code"),
            f.get("jurisdiction"),
            f.get("drift_type"),
            f.get("finding_id"),
            f.get("detail", "")[:200],
        )
        sk = json.dumps(key, sort_keys=True)
        if sk in seen:
            continue
        seen.add(sk)
        unique.append(f)

    by_sev = defaultdict(int)
    for f in unique:
        by_sev[str(f.get("severity", "")).upper()] += 1

    coverage = _build_governance_coverage_analysis(unique)
    return {
        "methodology": (
            "Synthetic requirement rows per canonical code × jurisdiction; "
            "effective_evidence_resolution + resolve_take_action_envelope + enrich_take_action_envelope_for_client; "
            "compute_workflow_mismatch_flags with decision-record reference (no published registry overlay); "
            "explicit policy-vs-reference checks; engine vs external-assessment heuristic for lead_testing."
        ),
        "scenarios_evaluated": len(scenarios),
        "findings_total": len(unique),
        "findings_by_severity": dict(by_sev),
        "findings": sorted(unique, key=lambda x: (x.get("severity", ""), x.get("drift_type", ""), x.get("canonical_requirement_code", ""))),
        "scenarios": scenarios,
        "governance_coverage_analysis": coverage,
    }


def _audit_one(code: str, jurisdiction: str) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    canon = normalize_requirement_code(code) or code
    eng = resolve_engine_payload_from_code(code)
    base: Dict[str, Any] = {
        "requirement_id": "audit_req_static",
        "property_id": "audit_prop_static",
        "requirement_code": code,
        "requirement_type": code,
        "jurisdiction": jurisdiction,
        "property_jurisdiction": jurisdiction,
    }
    base.update(eng)

    policy = effective_evidence_resolution(base)
    env = resolve_take_action_envelope(
        base,
        property_id=base["property_id"],
        property_jurisdiction=jurisdiction,
    )
    merged = {
        **base,
        "take_action": env.get("take_action"),
        "action_type": env.get("action_type"),
    }
    client = enrich_take_action_envelope_for_client(env, merged)
    enriched = {**merged, **client}

    ref, ref_src = resolve_workflow_class_reference(code, published_entry=None)
    runtime_wf = str(enriched.get("workflow_class") or "").strip()
    modes = enriched.get("allowed_evidence_modes") or []

    scenario = {
        "canonical_requirement_code": canon,
        "jurisdiction": jurisdiction,
        "workflow_class_reference": ref,
        "reference_source": ref_src,
        "runtime_workflow_class": runtime_wf,
        "allowed_evidence_modes": modes,
        "primary_resolution_workflow": policy.get("primary_resolution_workflow"),
        "runtime_behaviour": describe_runtime_behaviour(enriched),
        "engine_compliance_class": eng.get("compliance_requirement_class"),
        "engine_fulfillment_mode": eng.get("fulfillment_mode") or eng.get("engine_fulfillment_mode"),
    }

    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=ref,
        reference_source=ref_src,
    )
    for fl in flags:
        fid = str(fl.get("id") or "")
        cat_sev = _FLAG_CATEGORY.get(fid)
        if not cat_sev:
            cat, sev = "WORKFLOW_AUDIT_FLAG", "MEDIUM"
        else:
            cat, sev = cat_sev
        findings.append(
            _finding(
                drift_type=cat,
                severity=sev,
                canon=canon,
                code=code,
                jurisdiction=jurisdiction,
                workflow_class=runtime_wf,
                reference_class=ref,
                modes=modes,
                finding_id=fid,
                detail=str(fl.get("detail") or ""),
                expected=f"governance reference={ref}; see WORKFLOW_BEHAVIOUR_GOVERNANCE.md",
                observed=scenario["runtime_behaviour"],
                surfaces=_surfaces_for_category(cat),
                remediation=_remediation_hint(cat, fid),
                fix_lane=_fix_lane(cat, fid),
            )
        )

    # Explicit policy fallback vs guided/reference mismatch (registry absent).
    if ref != WC_UNKNOWN and _policy_fallback_legacy(policy) and _reference_expects_structured_first(ref):
        findings.append(
            _finding(
                drift_type="EVIDENCE_MODE_DRIFT",
                severity="CRITICAL",
                canon=canon,
                code=code,
                jurisdiction=jurisdiction,
                workflow_class=runtime_wf,
                reference_class=ref,
                modes=modes,
                finding_id="POLICY_FALLBACK_VS_REFERENCE_GUIDED",
                detail=(
                    f"effective_evidence_resolution falls back to LEGACY_DOCUMENT_UPLOAD while decision-record "
                    f"reference is {ref} — structured-first defaults missing for this code/jurisdiction."
                ),
                expected=f"Structured-first evidence_resolution for {ref} (registry or DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE).",
                observed=f"primary_resolution_workflow={policy.get('primary_resolution_workflow')}, modes={modes}",
                surfaces=["Requirements", "Evidence-resolution API", "Compliance tab"],
                remediation="Publish registry evidence_resolution or extend DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE / Wales context rules.",
                fix_lane="registry-only",
            )
        )

    # Engine treats lead_testing as certificate-like default while workflow reference is external assessment.
    if canon == "lead_testing" and _engine_certificate_like(eng) and ref == WC_EXTERNAL_ASSESSMENT_EVIDENCE:
        findings.append(
            _finding(
                drift_type="WORKFLOW_CLASS_DRIFT",
                severity="HIGH",
                canon=canon,
                code=code,
                jurisdiction=jurisdiction,
                workflow_class=runtime_wf,
                reference_class=ref,
                modes=modes,
                finding_id="ENGINE_SPEC_VS_EXTERNAL_ASSESSMENT_REFERENCE",
                detail=(
                    "compliance_requirement_engine defaults lead_testing to certificate-style engine spec; "
                    "workflow reference is EXTERNAL_ASSESSMENT_EVIDENCE — surfaces may present certificate semantics incorrectly."
                ),
                expected="Engine informational/document semantics aligned with assessment workflow where product intends operational posture.",
                observed=f"engine_class={eng.get('compliance_requirement_class')}, fulfillment={eng.get('fulfillment_mode')}",
                surfaces=["Command Centre", "Today", "Compliance score drivers", "Requirements"],
                remediation="Add lead_testing to compliance_requirement_engine._SPECS_BY_STORAGE_SLUG with intentional visibility/fulfillment.",
                fix_lane="policy-only",
            )
        )

    # Reference vs runtime normalized mismatch (family-level), excluding known LEGACY alias.
    nw_ref = _norm_wf(ref)
    nw_rt = _norm_wf(runtime_wf)
    if ref not in (WC_UNKNOWN,) and nw_ref != nw_rt:
        # MULTI_EVIDENCE vs GUIDED_EVIDENCE_RESOLUTION is a known resolver label — downgrade if smoke alarms
        sev = "MEDIUM"
        if canon == "smoke_heat_alarms" and ref == WC_MULTI_EVIDENCE and runtime_wf in ("GUIDED_EVIDENCE_RESOLUTION",):
            sev = "LOW"
        findings.append(
            _finding(
                drift_type="WORKFLOW_CLASS_DRIFT",
                severity=sev,
                canon=canon,
                code=code,
                jurisdiction=jurisdiction,
                workflow_class=runtime_wf,
                reference_class=ref,
                modes=modes,
                finding_id="REFERENCE_VS_RUNTIME_WORKFLOW_CLASS",
                detail=f"reference_class={ref} but enriched workflow_class={runtime_wf} (after LEGACY≈DOCUMENT normalization: {nw_ref} vs {nw_rt}).",
                expected=f"Runtime workflow_class should align with decision-record reference for {canon}.",
                observed=scenario["runtime_behaviour"],
                surfaces=["Requirements", "Today", "take_action exports"],
                remediation="Align enrich_take_action_envelope_for_client mapping or decision-record fallback map.",
                fix_lane="resolver-only",
            )
        )

    return {"scenario": scenario, "findings": findings}


def _surfaces_for_category(cat: str) -> List[str]:
    m = {
        "EVIDENCE_MODE_DRIFT": ["Evidence-resolution API", "Compliance tab", "Guided modal"],
        "CTA_DRIFT": ["Requirements", "Today", "Needs Attention", "take_action"],
        "JURISDICTION_DRIFT": ["Planner", "Requirements", "jurisdiction-gated APIs"],
        "WORKFLOW_CLASS_DRIFT": ["Requirements", "Resolver outputs", "Exports"],
        "REPORTING_SEMANTIC_DRIFT": ["Reports", "Audit exports", "Compliance summary"],
        "OPERATIONAL_CONVERGENCE_DRIFT": ["Operating Hub", "Issues/work orders", "Condition standards"],
        "CANONICAL_IDENTITY_DRIFT": ["All surfaces using requirement_code"],
        "SCORE_CONFIDENCE_DRIFT": ["Compliance score", "Score drivers", "Reports"],
    }
    return m.get(cat, ["Multiple"])


def _remediation_hint(cat: str, fid: str) -> str:
    if fid.startswith("POLICY_FALLBACK"):
        return "Add explicit evidence_resolution defaults or publish registry metadata."
    if cat == "JURISDICTION_DRIFT":
        return "Tighten planner applicability / jurisdiction filters for this obligation."
    if cat == "CTA_DRIFT":
        return "Adjust resolver primary intent or condition-standard branch for upload-primary prohibition."
    if cat == "EVIDENCE_MODE_DRIFT":
        return "Ensure STRUCTURED_DECLARATION + DOCUMENT_UPLOAD published or code defaults updated."
    return "See finding detail and WORKFLOW_BEHAVIOUR_GOVERNANCE.md."


def _fix_lane(cat: str, fid: str) -> str:
    if "POLICY_FALLBACK" in fid:
        return "registry-only"
    if cat == "CTA_DRIFT":
        return "resolver-only"
    if cat == "JURISDICTION_DRIFT":
        return "policy-only"
    if cat == "REPORTING_SEMANTIC_DRIFT" and "GOVERNANCE" in fid:
        return "governance-only"
    if cat == "OPERATIONAL_CONVERGENCE_DRIFT":
        return "operational-convergence"
    if cat == "CANONICAL_IDENTITY_DRIFT":
        return "workflow-authority"
    return "presentation-only"


def _finding(
    *,
    drift_type: str,
    severity: str,
    canon: str,
    code: str,
    jurisdiction: str,
    workflow_class: str,
    reference_class: str,
    modes: Any,
    finding_id: str,
    detail: str,
    expected: str,
    observed: str,
    surfaces: List[str],
    remediation: str,
    fix_lane: str,
) -> Dict[str, Any]:
    return {
        "canonical_requirement_code": canon,
        "affected_aliases": [code] if code != canon else [],
        "workflow_class": workflow_class,
        "reference_class": reference_class,
        "jurisdiction": jurisdiction,
        "drift_type": drift_type,
        "finding_id": finding_id,
        "severity": severity,
        "current_effective_modes": modes,
        "expected_governance_behavior": expected,
        "observed_runtime_behavior": observed,
        "detail": detail,
        "affected_surfaces": surfaces,
        "recommended_remediation": remediation,
        "fix_lane": fix_lane,
    }


def _write_md(report: Dict[str, Any], path: Path) -> None:
    by_type: Dict[str, int] = defaultdict(int)
    for f in report.get("findings", []):
        by_type[str(f.get("drift_type") or "?")] += 1

    lines = [
        "# Live registry / runtime workflow drift audit",
        "",
        f"**Findings (deduped):** {report['findings_total']}",
        f"**Scenarios:** {report['scenarios_evaluated']} (canonical codes × jurisdictions)",
        "",
        "**Scope note:** No published-registry Mongo overlay — uses code defaults + decision-record "
        "`client_workflow_class` fallbacks only. Production drift may differ where registry publishes "
        "`registry_metadata.evidence_resolution`.",
        "",
        "## Methodology",
        "",
        report.get("methodology", ""),
        "",
        "## Counts by drift type",
        "",
    ]
    for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
        lines.append(f"- **{k}:** {v}")
    lines.extend(
        [
            "",
            "## Counts by severity",
            "",
        ]
    )
    for k, v in sorted(report.get("findings_by_severity", {}).items(), key=lambda x: -x[1]):
        lines.append(f"- **{k}:** {v}")
    lines.extend(["", "## Findings by workflow class (runtime)", ""])
    by_wf: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for f in report.get("findings", []):
        by_wf[str(f.get("workflow_class") or "UNKNOWN")].append(f)
    for wf in sorted(by_wf.keys()):
        lines.append(f"### {wf}")
        lines.append("")
        for item in by_wf[wf][:50]:
            lines.append(
                f"- **{item.get('severity')}** [{item.get('drift_type')}] `{item.get('canonical_requirement_code')}` "
                f"({item.get('jurisdiction')}): {item.get('finding_id')} — {item.get('detail', '')[:160]}"
            )
        if len(by_wf[wf]) > 50:
            lines.append(f"- … {len(by_wf[wf]) - 50} more")
        lines.append("")
    cov = report.get("governance_coverage_analysis") or {}
    lines.extend(_governance_coverage_markdown_sections(cov))
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=str, default="", help="Write JSON report path")
    ap.add_argument("--md", type=str, default="", help="Write Markdown summary path")
    args = ap.parse_args()

    report = run_audit()

    out_dir = _BACKEND / "docs" / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(args.json) if args.json else out_dir / "REGISTRY_WORKFLOW_DRIFT_AUDIT.json"
    md_path = Path(args.md) if args.md else out_dir / "REGISTRY_WORKFLOW_DRIFT_AUDIT.md"

    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    _write_md(report, md_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(report["findings_by_severity"], indent=2))


if __name__ == "__main__":
    main()
