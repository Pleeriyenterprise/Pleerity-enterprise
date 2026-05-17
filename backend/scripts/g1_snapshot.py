"""
G1 Launch Governance Surveillance — Tranche T1 read-only scaffolding.

ANTI_EXPANSION: implementation_scope=T1_ONLY. Observes Tier-0 audit artefacts only;
never mutates production state, never rewrites upstream B–F artefacts, never derives
normative legitimacy, never auto-heals.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from scripts.c2_snapshot import fp, fp32  # noqa: F401

IMPLEMENTATION_SCOPE = "T1_ONLY"
READ_ONLY_SURVEILLANCE_ONLY = True
CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY = "SCAFFOLD_ONLY"

SURVEILLANCE_FULL = "SURVEILLANCE_FULL"
SURVEILLANCE_DEGRADED = "SURVEILLANCE_DEGRADED"
SURVEILLANCE_BLOCKED = "SURVEILLANCE_BLOCKED"

MANIFEST_TIER_CLASSIFICATION = "T1_INDEX_ONLY"
CONSTITUTIONAL_MASS_ACCOUNTING_MODE = "FIELD_PLUS_ELEMENT"
CONSTITUTIONAL_MASS_ELEMENT_BUDGET = 120

T1_APPROVED_PRIMARY_RCS: Tuple[str, ...] = (
    "G1-P1",
    "G1-P2",
    "G1-P5",
    "G1-RC-21",
    "G1-RC-27",
)

T2_T3_BLOCKED_RCS: Tuple[str, ...] = (
    "G1-P3",
    "G1-P4",
    "G1-P6",
    "G1-P7",
    "G1-P8",
    "G1-P9",
    "G1-P10",
    "G1-RC-22",
    "G1-RC-23",
    "G1-RC-24",
    "G1-RC-25",
    "G1-RC-26",
)

MANIFEST_FORBIDDEN_KEYS: Tuple[str, ...] = (
    "g1_pass",
    "legitimacy_decision",
    "governance_assertion",
    "replay_conclusion",
    "constitutional_adequacy",
    "normative_interpretation",
    "product_truth_verdict",
    "verified_eligible",
    "done_eligible",
)

PROHIBITED_NORMATIVE_FIELDS: Tuple[str, ...] = MANIFEST_FORBIDDEN_KEYS + (
    "legitimacy_score",
    "governance_interpretation",
    "semantic_stability_claim",
    "replay_verdict",
    "constitutional_legitimacy",
    "governance_completion",
    "contradiction_resolution",
    "reinterpretation_decision",
)

PROHIBITED_NORMATIVE_VALUE_MARKERS: Tuple[str, ...] = (
    "constitutionally_adequate",
    "launch_legitimate",
    "governance_complete",
    "semantic_stability_proven",
)

REFUSED_CAPABILITY_INVENTORY: Tuple[str, ...] = (
    "T2_PREDICATES",
    "T3_PREDICATES",
    "SEMANTIC_REINTERPRETATION",
    "CONTRADICTION_ARCHAEOLOGY",
    "GOVERNANCE_REPLAYABILITY_INFERENCE",
    "INSTITUTIONAL_SURVIVABILITY_LOGIC",
    "LEGITIMACY_SCORING",
    "GOVERNANCE_AUTHORITY_MODELLING",
    "LIVE_STAGING_SURVEILLANCE",
)

ALLOWED_WRITE_PREFIXES: Tuple[str, ...] = (
    "g1_",
    "launch_baseline_manifest_",
)

PROHIBITED_WRITE_TARGET_PREFIXES: Tuple[str, ...] = (
    "b1_",
    "c1_",
    "c2_",
    "c2a_",
    "d1_",
    "d1b_",
    "e1_",
    "e1b_",
    "f1_",
    "f1a_",
)

RETIRED_ARTIFACT_PREFIXES: Tuple[str, ...] = (
    "g1_governance_legitimacy_",
    "g1_bounded_reinterpretation_",
    "g1_anti_authoritarian_drift_",
    "g1_governance_replayability_",
    "g1_institutional_memory_antifragility_",
    "g1_historical_contradictions_",
    "g1_governance_succession_",
    "g1_partial_knowledge_survivability_",
    "g1_interpretation_drift_",
    "g1_governance_authority_",
)

TIER0_UNIT_PREFIXES: Tuple[str, ...] = (
    "b1_",
    "c1_",
    "c2_",
    "c2a_",
    "d1_",
    "d1b_",
    "e1_",
    "e1b_",
    "f1_",
    "f1a_",
)

CRITICAL_AUTHORITATIVE_SPECS: Tuple[Dict[str, str], ...] = (
    {
        "family": "d1b",
        "filename_pattern": "d1b_verification_report_{slug}.json",
        "authoritative_label": "d1b_authoritative_rerun",
        "pass_field": "d1_pass",
    },
    {
        "family": "e1b",
        "filename_pattern": "e1b_verification_report_{slug}.json",
        "authoritative_label": "e1b_authoritative_rerun",
        "pass_field": "e1b_pass",
    },
    {
        "family": "f1a",
        "filename_pattern": "f1a_verification_report_{slug}.json",
        "authoritative_label": "f1a_authoritative_rerun",
        "pass_field": "f1a_pass",
    },
)

MAX_ALLOWED_ARRAY_ELEMENTS: Dict[str, int] = {
    "tier0_entries": 256,
    "manifest_scope_inventory": 256,
    "manifest_grounding_requirements": 256,
    "normalization_boundary_inventory": 32,
    "critical_authoritative_artifact_inventory": 16,
    "missing_critical_authoritative_artifacts": 16,
    "missing_tier0": 128,
    "deferred_risk_inventory": 64,
    "watchlist_inventory": 64,
    "silently_removed": 64,
    "tier0_link_resolution": 64,
    "unresolved_tracker_claims": 32,
    "secondary_tags": 32,
    "advisory_tag_elevation_attempts": 16,
    "max_allowed_array_elements": 64,
}

DEFAULT_MIN_TIER0_COVERAGE = 0.95

__all__ = [
    "IMPLEMENTATION_SCOPE",
    "READ_ONLY_SURVEILLANCE_ONLY",
    "CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY",
    "SURVEILLANCE_FULL",
    "SURVEILLANCE_DEGRADED",
    "SURVEILLANCE_BLOCKED",
    "MANIFEST_TIER_CLASSIFICATION",
    "CONSTITUTIONAL_MASS_ACCOUNTING_MODE",
    "CONSTITUTIONAL_MASS_ELEMENT_BUDGET",
    "T1_APPROVED_PRIMARY_RCS",
    "T2_T3_BLOCKED_RCS",
    "REFUSED_CAPABILITY_INVENTORY",
    "assemble_t1_readiness",
    "assemble_t1_upstream_integrity",
    "assemble_t1_launch_scope_registry",
    "apply_scaffold_legitimacy_prohibition",
    "attempt_scope_escalation",
    "bind_tracker_claims",
    "build_anti_seepage_envelope",
    "build_incompleteness_doctrine",
    "build_launch_baseline_manifest",
    "build_t1_scope_registry_baseline",
    "compare_manifest_integrity",
    "compare_normalization_boundary",
    "compare_scope_registry",
    "count_constitutional_mass",
    "detect_primary_rc_t1",
    "detect_retired_artifact_usage",
    "enumerate_tier0_entries",
    "evaluate_live_staging_gate",
    "evaluate_pass_prohibition",
    "evaluate_surveillance_mode",
    "inventory_critical_authoritative",
    "is_prohibited_write_target",
    "load_json_if_exists",
    "normalization_boundary_inventory",
    "refuse_capability_activation",
    "refuse_t2_t3_predicate",
    "resolve_surveillance_posture",
    "scan_manifest_normative_assertions",
    "sha256_file",
    "t1_tracker_claims",
    "validate_manifest_t1",
    "verify_readonly_preservation",
    "write_json_readonly_emit",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def refuse_t2_t3_predicate(predicate_name: str) -> Dict[str, Any]:
    t3_predicates = {"G1-P7", "G1-P9", "G1-P10", "G1-RC-22", "G1-RC-23", "G1-RC-25", "G1-RC-26"}
    capability_id = "T3_PREDICATES" if predicate_name in t3_predicates else "T2_PREDICATES"
    refusal = refuse_capability_activation(
        capability_id=capability_id,
        detail=f"predicate:{predicate_name}",
    )
    refusal["predicate"] = predicate_name
    return refusal


def build_anti_seepage_envelope() -> Dict[str, Any]:
    reasons = {
        "T2_PREDICATES": "G1-P3/P4/P6/P8 and G1-RC-24 blocked pending T2 programme approval",
        "T3_PREDICATES": "G1-P7/P9/P10 and G1-RC-22/23/25/26 blocked pending T3 programme approval",
        "SEMANTIC_REINTERPRETATION": "No semantic drift or reinterpretation engines in T1",
        "CONTRADICTION_ARCHAEOLOGY": "No historical contradiction simulation in T1",
        "GOVERNANCE_REPLAYABILITY_INFERENCE": "No governance replayability inference in T1",
        "INSTITUTIONAL_SURVIVABILITY_LOGIC": "No institutional survivability logic in T1",
        "LEGITIMACY_SCORING": "No legitimacy scoring or constitutional adequacy derivation",
        "GOVERNANCE_AUTHORITY_MODELLING": "No governance authority modelling chains",
        "LIVE_STAGING_SURVEILLANCE": "Live staging execution not authorised under T1 signoff",
    }
    return {
        "refused_capability_inventory": list(REFUSED_CAPABILITY_INVENTORY),
        "capability_refusal_reason": [{"capability": k, "reason": v} for k, v in reasons.items()],
        "attempted_scope_escalations": [],
    }


def refuse_capability_activation(*, capability_id: str, detail: str = "") -> Dict[str, Any]:
    if capability_id not in REFUSED_CAPABILITY_INVENTORY:
        capability_id = "UNKNOWN_CAPABILITY"
    return {
        "refused": True,
        "observable_refusal": True,
        "silent_noop": False,
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "capability": capability_id,
        "detail": detail,
        "reason": f"CAPABILITY_REFUSED_UNDER_{IMPLEMENTATION_SCOPE}",
    }


def attempt_scope_escalation(
    envelope: Dict[str, Any],
    *,
    capability_id: str,
    detail: str,
) -> Dict[str, Any]:
    refusal = refuse_capability_activation(capability_id=capability_id, detail=detail)
    envelope["attempted_scope_escalations"].append(
        {
            "capability": capability_id,
            "detail": detail,
            "refused": True,
            "refusal": refusal,
        }
    )
    return refusal


def build_incompleteness_doctrine() -> Dict[str, Any]:
    return {
        "implementation_scope_limitations": [
            "T1 implements G1-P1, G1-P2, G1-P5, G1-RC-21, G1-RC-27 only",
            "No g1_product_surveillance_* or g1_governance_surface_* in T1",
            "No live staging DB surveillance under T1 signoff",
            "Tracker prose binding for F1_DONE_SCOPE remains explicitly unresolved",
        ],
        "intentionally_unimplemented_capabilities": list(REFUSED_CAPABILITY_INVENTORY),
        "anti_expansion_containment_rationale": [
            "Incomplete scope is a containment mechanism, not a defect",
            "T1 harness existence does not imply constitutional legitimacy",
            "Metadata may point to truth; metadata is not truth",
            "Surveillance outputs are Tier-3 observational only",
        ],
    }


def scan_manifest_normative_assertions(payload: Any, *, path: str = "") -> Dict[str, Any]:
    forbidden: List[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_path = f"{path}.{key}" if path else key
            if key in PROHIBITED_NORMATIVE_FIELDS or key in MANIFEST_FORBIDDEN_KEYS:
                forbidden.append(f"prohibited_field:{key_path}")
            if isinstance(value, str):
                lowered = value.lower()
                for marker in PROHIBITED_NORMATIVE_VALUE_MARKERS:
                    if marker in lowered:
                        forbidden.append(f"prohibited_value_marker:{key_path}:{marker}")
            nested = scan_manifest_normative_assertions(value, path=key_path)
            forbidden.extend(nested["forbidden_manifest_assertions"])
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            nested = scan_manifest_normative_assertions(item, path=f"{path}[{index}]")
            forbidden.extend(nested["forbidden_manifest_assertions"])
    return {
        "forbidden_manifest_assertions": forbidden,
        "manifest_assertion_scan_pass": not forbidden,
        "prohibited_normative_fields": list(PROHIBITED_NORMATIVE_FIELDS),
    }


def is_prohibited_write_target(filename: str) -> bool:
    if any(filename.startswith(prefix) for prefix in ALLOWED_WRITE_PREFIXES):
        return False
    return any(filename.startswith(prefix) for prefix in PROHIBITED_WRITE_TARGET_PREFIXES)


def verify_readonly_preservation(
    *,
    path: Path,
    tier0_hashes_before: Optional[Dict[str, str]] = None,
    tier0_hashes_after: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    attempted: List[Dict[str, Any]] = []
    if is_prohibited_write_target(path.name):
        attempted.append({"path": str(path), "action": "write", "blocked": True})
    hash_drift: List[str] = []
    if tier0_hashes_before and tier0_hashes_after:
        for tier0_path, before_hash in tier0_hashes_before.items():
            after_hash = tier0_hashes_after.get(tier0_path)
            if after_hash is not None and after_hash != before_hash:
                hash_drift.append(tier0_path)
                attempted.append({"path": tier0_path, "action": "hash_rewrite", "blocked": True})
    return {
        "readonly_preservation_pass": not attempted and not hash_drift,
        "attempted_upstream_mutations": attempted,
        "prohibited_write_targets": [
            {"prefix": prefix, "policy": "WRITE_FORBIDDEN"} for prefix in PROHIBITED_WRITE_TARGET_PREFIXES
        ],
        "allowed_write_prefixes": list(ALLOWED_WRITE_PREFIXES),
    }


def apply_scaffold_legitimacy_prohibition(
    pass_fields: Dict[str, Any],
    *,
    scaffold_only: bool,
) -> Dict[str, Any]:
    if not scaffold_only:
        return pass_fields
    prohibited = evaluate_pass_prohibition(
        surveillance_mode=SURVEILLANCE_DEGRADED,
        degraded_mode=True,
    )
    prohibited["g1_pass"] = False
    prohibited["verified_eligible"] = False
    prohibited["done_eligible"] = False
    prohibited["constitutional_authority_level"] = CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY
    prohibited["scaffold_legitimacy_prohibition_pass"] = (
        not prohibited["g1_pass"]
        and not prohibited["verified_eligible"]
        and not prohibited["done_eligible"]
    )
    prohibited["scaffold_authority_boundary"] = [
        "Scaffolding existence is never constitutional legitimacy",
        "t1_harness_scaffold_only=true forbids g1_pass regardless of T1 check outcomes",
        "No VERIFIED or DONE eligibility may be inferred from harness artefacts alone",
    ]
    return prohibited


def evaluate_live_staging_gate(
    *,
    explicit_execution_approval: bool,
    implementation_scope: str,
    live_staging_requested: bool,
) -> Dict[str, Any]:
    envelope = build_anti_seepage_envelope()
    if not live_staging_requested:
        return {
            "authorised": False,
            "surveillance_execution_authorised": False,
            "reason": "LIVE_STAGING_NOT_REQUESTED",
            **envelope,
        }
    attempt_scope_escalation(
        envelope,
        capability_id="LIVE_STAGING_SURVEILLANCE",
        detail="live_staging_requested",
    )
    if not explicit_execution_approval:
        return {
            "authorised": False,
            "surveillance_execution_authorised": False,
            "reason": "MISSING_EXPLICIT_EXECUTION_APPROVAL",
            "approval_flag_alone_insufficient": True,
            **envelope,
        }
    if implementation_scope == IMPLEMENTATION_SCOPE:
        return {
            "authorised": False,
            "surveillance_execution_authorised": False,
            "reason": "SCOPE_AUTHORITY_INSUFFICIENT_T1_ONLY",
            "note": "Explicit approval flag alone is insufficient; implementation_scope must exceed T1_ONLY",
            "approval_flag_alone_insufficient": True,
            **envelope,
        }
    return {
        "authorised": False,
        "surveillance_execution_authorised": False,
        "reason": "LIVE_PATH_NOT_IMPLEMENTED",
        **envelope,
    }


def is_retired_artifact_filename(name: str) -> bool:
    base = Path(name).name
    return any(base.startswith(prefix) for prefix in RETIRED_ARTIFACT_PREFIXES)


def detect_retired_artifact_usage(referenced_paths: Iterable[str]) -> List[str]:
    violations: List[str] = []
    for raw in referenced_paths:
        name = Path(raw).name
        if is_retired_artifact_filename(name):
            violations.append(name)
    return violations


def normalization_boundary_inventory() -> List[Dict[str, Any]]:
    from scripts.e1a_snapshot import SEMANTIC_EVIDENCE_AUTHORITY_OMIT_KEYS
    from scripts.f1_snapshot import OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS

    return [
        {
            "boundary_id": "OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS",
            "unit": "F1",
            "omit_keys": list(OBSERVATIONAL_MESSAGE_LOG_OMIT_KEYS),
            "approving_unit_ref": "F1",
            "visibility_only": True,
        },
        {
            "boundary_id": "SEMANTIC_EVIDENCE_AUTHORITY_OMIT_KEYS",
            "unit": "E1b",
            "omit_keys": list(SEMANTIC_EVIDENCE_AUTHORITY_OMIT_KEYS),
            "approving_unit_ref": "E1b",
            "visibility_only": True,
        },
    ]


def enumerate_tier0_entries(audit_dir: Path, slug: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    suffix = f"_{slug}.json"
    for path in sorted(audit_dir.glob(f"*{suffix}")):
        name = path.name
        if not any(name.startswith(prefix) for prefix in TIER0_UNIT_PREFIXES):
            continue
        entries.append(
            {
                "path": str(path.relative_to(audit_dir.parent.parent)).replace("\\", "/"),
                "filename": name,
                "sha256": sha256_file(path),
                "authoritative_label": _authoritative_label_for(name),
                "lineage_reference": name.split("_")[0],
            }
        )
    return entries


def _authoritative_label_for(filename: str) -> str:
    if filename.startswith("d1b_"):
        return "d1b_authoritative"
    if filename.startswith("e1b_"):
        return "e1b_authoritative"
    if filename.startswith("f1a_"):
        return "f1a_authoritative"
    if filename.startswith("d1_"):
        return "d1_historical"
    if filename.startswith("e1_"):
        return "e1_historical"
    if filename.startswith("f1_"):
        return "f1_historical"
    return "tier0_observational"


def manifest_grounding_requirements(entries: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "requirement_id": "T0_PATH_HASH",
            "path": row["path"],
            "sha256": row["sha256"],
            "authoritative_label": row["authoritative_label"],
        }
        for row in entries
    ]


def build_launch_baseline_manifest(
    *,
    audit_dir: Path,
    slug: str,
    manifest_version: int = 1,
) -> Dict[str, Any]:
    entries = enumerate_tier0_entries(audit_dir, slug)
    norm_inventory = normalization_boundary_inventory()
    return {
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "manifest_version": manifest_version,
        "manifest_tier_classification": MANIFEST_TIER_CLASSIFICATION,
        "pilot_slug": slug,
        "manifest_grounding_requirements": manifest_grounding_requirements(entries),
        "manifest_scope_inventory": [
            {
                "path": row["path"],
                "sha256": row["sha256"],
                "lineage_reference": row["lineage_reference"],
            }
            for row in entries
        ],
        "normalization_boundary_inventory": norm_inventory,
        "tier0_entries": entries,
        "read_only_capture": True,
        "anti_expansion_posture": "T1_INDEX_ONLY_NO_NORMATIVE_ASSERTIONS",
    }


def validate_manifest_t1(manifest: Dict[str, Any]) -> Dict[str, Any]:
    violations: List[str] = []
    assertion_scan = scan_manifest_normative_assertions(manifest)
    if manifest.get("manifest_tier_classification") != MANIFEST_TIER_CLASSIFICATION:
        violations.append("manifest_tier_classification_not_T1_INDEX_ONLY")
    for key in MANIFEST_FORBIDDEN_KEYS:
        if key in manifest:
            violations.append(f"forbidden_manifest_key:{key}")
    violations.extend(assertion_scan["forbidden_manifest_assertions"])
    for row in manifest.get("manifest_grounding_requirements") or []:
        if not row.get("path") or not row.get("sha256"):
            violations.append("manifest_grounding_missing_tier0_derivation")
    for row in manifest.get("manifest_scope_inventory") or []:
        if not row.get("path") or not row.get("sha256"):
            violations.append("manifest_scope_row_missing_tier0_derivation")
    for row in manifest.get("tier0_entries") or []:
        for forbidden in MANIFEST_FORBIDDEN_KEYS:
            if forbidden in row:
                violations.append(f"tier0_row_forbidden_key:{forbidden}")
    normative_violation = bool(assertion_scan["forbidden_manifest_assertions"])
    return {
        "manifest_t1_valid": not violations,
        "violations": violations,
        "forbidden_manifest_assertions": assertion_scan["forbidden_manifest_assertions"],
        "manifest_assertion_scan_pass": assertion_scan["manifest_assertion_scan_pass"],
        "prohibited_normative_fields": assertion_scan["prohibited_normative_fields"],
        "metadata_authority_escalation": normative_violation,
        "primary_rc_candidate": "G1-RC-21" if violations else None,
    }


def inventory_critical_authoritative(audit_dir: Path, slug: str) -> Dict[str, Any]:
    inventory: List[Dict[str, Any]] = []
    missing: List[str] = []
    for spec in CRITICAL_AUTHORITATIVE_SPECS:
        filename = spec["filename_pattern"].format(slug=slug)
        path = audit_dir / filename
        present = path.is_file()
        payload = load_json_if_exists(path) if present else None
        pass_field = spec["pass_field"]
        pass_value = payload.get(pass_field) if payload else None
        inventory.append(
            {
                "family": spec["family"],
                "path": f"docs/audit/{filename}" if present else None,
                "sha256": sha256_file(path) if present else None,
                "authoritative_label": spec["authoritative_label"],
                "present": present,
                "pass_field": pass_field,
                "pass_value": pass_value,
            }
        )
        if not present:
            missing.append(filename)
    return {
        "critical_authoritative_artifact_inventory": inventory,
        "missing_critical_authoritative_artifacts": missing,
        "critical_complete": not missing,
    }


def compare_manifest_integrity(
    *,
    baseline: Dict[str, Any],
    current_entries: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    baseline_by_path = {row["path"]: row for row in baseline.get("tier0_entries") or []}
    current_by_path = {row["path"]: row for row in current_entries}
    missing_tier0: List[str] = []
    tamper_detected = False
    hash_mismatches: List[Dict[str, str]] = []
    for path, row in baseline_by_path.items():
        current = current_by_path.get(path)
        if current is None:
            missing_tier0.append(path)
            continue
        if current["sha256"] != row["sha256"]:
            tamper_detected = True
            hash_mismatches.append({"path": path, "baseline_sha256": row["sha256"], "current_sha256": current["sha256"]})
    total = len(baseline_by_path) or 1
    present = total - len(missing_tier0)
    coverage = present / total
    return {
        "tamper_detected": tamper_detected,
        "missing_tier0": missing_tier0,
        "hash_mismatches": hash_mismatches,
        "tier0_coverage_ratio": coverage,
        "retroactive_rewrite_detected": tamper_detected,
    }


def compare_normalization_boundary(
    *,
    baseline_inventory: Sequence[Dict[str, Any]],
    current_inventory: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    baseline_keys: Dict[str, set] = {}
    for row in baseline_inventory:
        baseline_keys[row["boundary_id"]] = set(row.get("omit_keys") or [])
    widened: List[Dict[str, Any]] = []
    for row in current_inventory:
        boundary_id = row["boundary_id"]
        current_keys = set(row.get("omit_keys") or [])
        prior = baseline_keys.get(boundary_id, set())
        added = sorted(current_keys - prior)
        if added and not row.get("approving_unit_ref"):
            widened.append({"boundary_id": boundary_id, "added_keys": added})
        elif added:
            widened.append(
                {
                    "boundary_id": boundary_id,
                    "added_keys": added,
                    "approving_unit_ref": row.get("approving_unit_ref"),
                    "requires_separate_unit": True,
                }
            )
    drift = any(item.get("added_keys") and not item.get("approving_unit_ref") for item in widened)
    return {
        "normalization_drift_detected": drift,
        "normalization_boundary_delta": widened,
        "primary_rc_candidate": "G1-P2" if drift else None,
    }


def build_t1_scope_registry_baseline(*, slug: str) -> Dict[str, Any]:
    return {
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "pilot_slug": slug,
        "proof_context_snapshot": [
            {
                "unit": "F1",
                "status": "DONE",
                "proof_context": "F1-M1 idempotency replay; F1-M8 observe-only",
                "tracker_section": "§ F1 DONE closure",
            },
            {
                "unit": "F1a",
                "status": "IN_PROGRESS",
                "proof_context": "Harness refinement rerun; classification deferred",
                "tracker_section": "§ F1a",
            },
        ],
        "accepted_scope_limitations": [
            "F1-M2–M7 mutation paths not proven in F1 unit",
            "Full notification-path provider ack not in F1 scope",
        ],
        "deferred_risk_inventory": [
            {
                "id": "F1-M2-M7",
                "status": "DEFERRED",
                "rationale": "Separate governed verification units required",
            },
        ],
        "watchlist_inventory": [
            {
                "id": "F1-M2-M7-unproven",
                "source": "LAUNCH_AUTHORITY_TRACKER § F1 DONE watchlist",
                "blocking": False,
            },
            {
                "id": "B1-updated_at-churn",
                "source": "programme watchlist",
                "blocking": False,
            },
            {
                "id": "C2a-volatile-task-ids",
                "source": "programme watchlist",
                "blocking": False,
            },
        ],
        "silently_removed": [],
        "proof_interpretation_constraints": [
            "T3 g1_* outputs are observational only",
            "Manifest is index-only; never normative product truth",
        ],
    }


def compare_scope_registry(
    *,
    baseline: Dict[str, Any],
    current: Dict[str, Any],
) -> Dict[str, Any]:
    def _ids(rows: Sequence[Any]) -> set:
        out: set = set()
        for row in rows:
            if isinstance(row, str):
                out.add(row)
                continue
            if not isinstance(row, dict):
                continue
            ident = row.get("id") or row.get("item") or row.get("rationale")
            if ident:
                out.add(str(ident))
        return out

    removed: List[str] = []
    for section in ("deferred_risk_inventory", "watchlist_inventory", "accepted_scope_limitations"):
        base_ids = _ids(baseline.get(section) or [])
        cur_ids = _ids(current.get(section) or [])
        for ident in sorted(base_ids - cur_ids):
            removed.append(f"{section}:{ident}")
    return {
        "silently_removed": removed,
        "primary_rc_candidate": "G1-P5" if removed else None,
    }


def t1_tracker_claims(*, slug: str) -> List[Dict[str, Any]]:
    return [
        {
            "claim_id": "D1_AUTHORITATIVE_PRESENT",
            "claim": "D1b authoritative verification report exists for pilot",
            "expected_tier0_filename": f"d1b_verification_report_{slug}.json",
            "replay_lineage_ref": "d1b_*",
        },
        {
            "claim_id": "E1_AUTHORITATIVE_PRESENT",
            "claim": "E1b authoritative verification report exists for pilot",
            "expected_tier0_filename": f"e1b_verification_report_{slug}.json",
            "replay_lineage_ref": "e1b_*",
        },
        {
            "claim_id": "F1A_AUTHORITATIVE_PRESENT",
            "claim": "F1a authoritative verification report exists for pilot",
            "expected_tier0_filename": f"f1a_verification_report_{slug}.json",
            "replay_lineage_ref": "f1a_*",
        },
        {
            "claim_id": "F1_DONE_SCOPE",
            "claim": "F1 unit marked DONE with explicit F1-M2–M7 deferral",
            "expected_tier0_filename": None,
            "replay_lineage_ref": None,
            "explicit_unresolved": True,
            "unresolved_reason": "T1 binds prose closure to artefact hash when tracker excerpt capture is T2-blocked",
        },
    ]


def bind_tracker_claims(
    *,
    claims: Sequence[Dict[str, Any]],
    tier0_entries: Sequence[Dict[str, Any]],
    audit_dir: Path,
    slug: str,
) -> Dict[str, Any]:
    by_filename = {Path(row["path"]).name: row for row in tier0_entries}
    resolutions: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    for claim in claims:
        if claim.get("explicit_unresolved"):
            unresolved.append(
                {
                    "claim_id": claim["claim_id"],
                    "claim": claim["claim"],
                    "reason": claim.get("unresolved_reason"),
                }
            )
            continue
        expected = claim.get("expected_tier0_filename")
        if not expected:
            unresolved.append({"claim_id": claim["claim_id"], "claim": claim["claim"], "reason": "no_expected_artifact"})
            continue
        row = by_filename.get(expected)
        path = audit_dir / expected
        if row is None and path.is_file():
            row = {
                "path": f"docs/audit/{expected}",
                "sha256": sha256_file(path),
            }
        if row is None:
            unresolved.append({"claim_id": claim["claim_id"], "claim": claim["claim"], "reason": "tier0_artifact_missing"})
            continue
        resolutions.append(
            {
                "claim_id": claim["claim_id"],
                "tier0_artifact_path": row["path"],
                "tier0_artifact_sha256": row["sha256"],
                "replay_lineage_ref": claim.get("replay_lineage_ref"),
                "normalization_boundary_ref": None,
            }
        )
    return {
        "tier0_link_resolution": resolutions,
        "unresolved_tracker_claims": unresolved,
        "tracker_truth_binding_pass": not unresolved,
    }


def _walk_mass(node: Any, *, in_array: bool) -> Tuple[int, int]:
    if isinstance(node, dict):
        fields = len(node)
        elements = 0
        for value in node.values():
            f, e = _walk_mass(value, in_array=False)
            fields += f
            elements += e
        return fields, elements
    if isinstance(node, list):
        elements = len(node)
        fields = 0
        for item in node:
            f, e = _walk_mass(item, in_array=True)
            fields += f
            elements += e
        return fields, elements
    return (0, 1 if in_array else 1)


def count_constitutional_mass(payloads: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total_fields = 0
    total_elements = 0
    array_violations: List[Dict[str, Any]] = []
    for payload in payloads:
        for key, value in payload.items():
            if isinstance(value, list):
                limit = MAX_ALLOWED_ARRAY_ELEMENTS.get(key)
                if limit is not None and len(value) > limit:
                    array_violations.append({"field": key, "count": len(value), "max_allowed": limit})
        fields, elements = _walk_mass(payload, in_array=False)
        total_fields += fields
        total_elements += elements
    mass_total = total_fields + total_elements
    budget_exceeded = mass_total > CONSTITUTIONAL_MASS_ELEMENT_BUDGET
    return {
        "constitutional_mass_accounting_mode": CONSTITUTIONAL_MASS_ACCOUNTING_MODE,
        "artefact_count": len(payloads),
        "field_count": total_fields,
        "element_count": total_elements,
        "constitutional_mass_element_budget": CONSTITUTIONAL_MASS_ELEMENT_BUDGET,
        "max_allowed_array_elements": [
            {"field": key, "max_allowed": value} for key, value in sorted(MAX_ALLOWED_ARRAY_ELEMENTS.items())
        ],
        "mass_total": mass_total,
        "budget_exceeded": budget_exceeded,
        "array_limit_violations": array_violations,
        "accounting_valid": not budget_exceeded and not array_violations,
    }


def evaluate_surveillance_mode(
    *,
    missing_critical: Sequence[str],
    tier0_coverage_ratio: float,
    manifest_valid: bool,
    min_coverage: float = DEFAULT_MIN_TIER0_COVERAGE,
) -> str:
    if missing_critical:
        return SURVEILLANCE_DEGRADED if tier0_coverage_ratio >= min_coverage else SURVEILLANCE_BLOCKED
    if tier0_coverage_ratio < min_coverage or not manifest_valid:
        return SURVEILLANCE_DEGRADED
    return SURVEILLANCE_FULL


def evaluate_pass_prohibition(*, surveillance_mode: str, degraded_mode: bool) -> Dict[str, bool]:
    allow_pass = surveillance_mode == SURVEILLANCE_FULL and not degraded_mode
    return {
        "g1_pass": allow_pass,
        "verified_eligible": allow_pass,
        "done_eligible": allow_pass,
        "degraded_mode": degraded_mode or surveillance_mode != SURVEILLANCE_FULL,
    }


def detect_primary_rc_t1(state: Dict[str, Any]) -> Optional[str]:
    precedence: Tuple[Tuple[str, str], ...] = (
        ("critical_omission_masking", "G1-RC-27"),
        ("manifest_rc21", "G1-RC-21"),
        ("tamper_or_missing_tier0", "G1-P1"),
        ("normalization_drift", "G1-P2"),
        ("scope_erasure", "G1-P5"),
    )
    for key, rc in precedence:
        if state.get(key):
            if rc in T1_APPROVED_PRIMARY_RCS:
                return rc
    return None


def resolve_surveillance_posture(
    *,
    audit_dir: Path,
    slug: str,
    baseline_manifest: Optional[Dict[str, Any]] = None,
    baseline_scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current_entries = enumerate_tier0_entries(audit_dir, slug)
    critical = inventory_critical_authoritative(audit_dir, slug)
    manifest = baseline_manifest or build_launch_baseline_manifest(audit_dir=audit_dir, slug=slug)
    manifest_validation = validate_manifest_t1(manifest)
    if manifest_validation.get("metadata_authority_escalation"):
        manifest_validation["manifest_t1_valid"] = False
    integrity = (
        compare_manifest_integrity(baseline=manifest, current_entries=current_entries)
        if baseline_manifest
        else {
            "tamper_detected": False,
            "missing_tier0": [],
            "hash_mismatches": [],
            "tier0_coverage_ratio": 1.0,
            "retroactive_rewrite_detected": False,
        }
    )
    norm_compare = compare_normalization_boundary(
        baseline_inventory=manifest.get("normalization_boundary_inventory") or [],
        current_inventory=normalization_boundary_inventory(),
    )
    scope_baseline = baseline_scope or build_t1_scope_registry_baseline(slug=slug)
    scope_current = build_t1_scope_registry_baseline(slug=slug)
    scope_compare = compare_scope_registry(baseline=scope_baseline, current=scope_current)
    binding = bind_tracker_claims(
        claims=t1_tracker_claims(slug=slug),
        tier0_entries=current_entries,
        audit_dir=audit_dir,
        slug=slug,
    )
    surveillance_mode = evaluate_surveillance_mode(
        missing_critical=critical["missing_critical_authoritative_artifacts"],
        tier0_coverage_ratio=float(integrity.get("tier0_coverage_ratio") or 0.0),
        manifest_valid=bool(manifest_validation.get("manifest_t1_valid")),
    )
    rc27 = bool(critical["missing_critical_authoritative_artifacts"]) and surveillance_mode == SURVEILLANCE_FULL
    rc_state = {
        "critical_omission_masking": rc27,
        "manifest_rc21": not manifest_validation.get("manifest_t1_valid")
        or manifest_validation.get("metadata_authority_escalation"),
        "tamper_or_missing_tier0": bool(integrity.get("tamper_detected") or integrity.get("missing_tier0")),
        "normalization_drift": bool(norm_compare.get("normalization_drift_detected")),
        "scope_erasure": bool(scope_compare.get("silently_removed")),
    }
    primary_rc = detect_primary_rc_t1(rc_state)
    degraded_triggers = bool(
        critical["missing_critical_authoritative_artifacts"]
        or surveillance_mode != SURVEILLANCE_FULL
        or primary_rc is not None
    )
    pass_fields = evaluate_pass_prohibition(
        surveillance_mode=surveillance_mode,
        degraded_mode=degraded_triggers,
    )
    retired_violations = detect_retired_artifact_usage(
        [row.get("path") or "" for row in manifest.get("tier0_entries") or []]
    )
    return {
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "surveillance_mode": surveillance_mode,
        "primary_rc": primary_rc,
        "manifest_validation": manifest_validation,
        "integrity": integrity,
        "critical": critical,
        "norm_compare": norm_compare,
        "scope_compare": scope_compare,
        "tracker_binding": binding,
        "retired_violations": retired_violations,
        "pass_fields": pass_fields,
        "current_entries": current_entries,
        "manifest": manifest,
        "scope_baseline": scope_baseline,
    }


def assemble_t1_upstream_integrity(
    *,
    slug: str,
    manifest: Dict[str, Any],
    posture: Dict[str, Any],
) -> Dict[str, Any]:
    critical = posture["critical"]
    integrity = posture["integrity"]
    return {
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "unit": "G1",
        "pilot_slug": slug,
        "manifest_version": manifest.get("manifest_version"),
        "tier0_manifest_ref": f"launch_baseline_manifest_{slug}_v{manifest.get('manifest_version', 1)}.json",
        "manifest_tier_classification": manifest.get("manifest_tier_classification"),
        "manifest_grounding_requirements": manifest.get("manifest_grounding_requirements"),
        "tier0_entries": manifest.get("tier0_entries"),
        "critical_authoritative_artifact_inventory": critical["critical_authoritative_artifact_inventory"],
        "missing_critical_authoritative_artifacts": critical["missing_critical_authoritative_artifacts"],
        "tamper_detected": integrity.get("tamper_detected"),
        "missing_tier0": integrity.get("missing_tier0"),
        "retroactive_rewrite_detected": integrity.get("retroactive_rewrite_detected"),
        "read_only": True,
    }


def assemble_t1_launch_scope_registry(*, slug: str, posture: Dict[str, Any]) -> Dict[str, Any]:
    baseline = posture["scope_baseline"]
    compare = posture["scope_compare"]
    norm = posture["norm_compare"]
    return {
        **baseline,
        "silently_removed": compare.get("silently_removed") or [],
        "normalization_boundary_visibility": {
            "normalization_drift_detected": norm.get("normalization_drift_detected"),
            "normalization_boundary_delta": norm.get("normalization_boundary_delta"),
        },
        "scope_registry_diff_pass": not (compare.get("silently_removed") or []),
    }


def assemble_t1_readiness(
    *,
    slug: str,
    posture: Dict[str, Any],
    artifacts: Sequence[Dict[str, Any]],
    scaffold_only: bool = False,
) -> Dict[str, Any]:
    mass = count_constitutional_mass(artifacts)
    binding = posture["tracker_binding"]
    pass_fields = apply_scaffold_legitimacy_prohibition(
        dict(posture["pass_fields"]),
        scaffold_only=scaffold_only,
    )
    anti_seepage = build_anti_seepage_envelope()
    incompleteness = build_incompleteness_doctrine()
    assertion_scan = scan_manifest_normative_assertions(posture.get("manifest") or {})
    return {
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "unit": "G1",
        "pilot_slug": slug,
        "surveillance_mode": posture["surveillance_mode"],
        "degraded_mode": pass_fields["degraded_mode"],
        "g1_pass": pass_fields["g1_pass"],
        "verified_eligible": pass_fields["verified_eligible"],
        "done_eligible": pass_fields["done_eligible"],
        "constitutional_authority_level": pass_fields.get(
            "constitutional_authority_level",
            "OBSERVATIONAL_T3",
        ),
        "scaffold_legitimacy_prohibition_pass": pass_fields.get(
            "scaffold_legitimacy_prohibition_pass",
            not scaffold_only,
        ),
        "scaffold_authority_boundary": pass_fields.get("scaffold_authority_boundary", []),
        "primary_rc": posture["primary_rc"],
        "secondary_tags": ["TAG_PARTIAL_KNOWLEDGE"] if pass_fields["degraded_mode"] else [],
        "advisory_tag_elevation_attempts": [],
        "tag_governance_boundary_pass": True,
        "tier0_link_resolution": binding["tier0_link_resolution"],
        "unresolved_tracker_claims": binding["unresolved_tracker_claims"],
        "tracker_truth_binding_pass": binding["tracker_truth_binding_pass"],
        "tier0_grounding": [
            {"path": row["path"], "sha256": row["sha256"]}
            for row in posture["current_entries"]
            if not str(row["path"]).startswith("docs/audit/g1_")
        ],
        "predicate_binding_inventory": [
            {"predicate": rc, "scope": "T1_APPROVED"} for rc in T1_APPROVED_PRIMARY_RCS
        ],
        "non_falsifiable_language_inventory": [],
        "advisory_only_governance_language": ["TAG_PARTIAL_KNOWLEDGE"],
        "constitutional_mass": mass,
        "constitutional_mass_accounting_mode": CONSTITUTIONAL_MASS_ACCOUNTING_MODE,
        "challenge_refs": [],
        "artifact_index": [
            {"artefact": f"g1_upstream_integrity_{slug}.json", "tier": "T3", "observational_only": True},
            {"artefact": f"g1_launch_scope_registry_{slug}.json", "tier": "T3", "observational_only": True},
            {"artefact": f"g1_launch_readiness_{slug}.json", "tier": "T3", "observational_only": True},
        ],
        "t2_t3_predicate_refusals": [refuse_t2_t3_predicate(name) for name in ("G1-P3", "G1-RC-24", "G1-P10")],
        "refused_capability_inventory": anti_seepage["refused_capability_inventory"],
        "capability_refusal_reason": anti_seepage["capability_refusal_reason"],
        "attempted_scope_escalations": anti_seepage["attempted_scope_escalations"],
        "forbidden_manifest_assertions": assertion_scan["forbidden_manifest_assertions"],
        "manifest_assertion_scan_pass": assertion_scan["manifest_assertion_scan_pass"],
        "prohibited_normative_fields": assertion_scan["prohibited_normative_fields"],
        "implementation_scope_limitations": incompleteness["implementation_scope_limitations"],
        "intentionally_unimplemented_capabilities": incompleteness["intentionally_unimplemented_capabilities"],
        "anti_expansion_containment_rationale": incompleteness["anti_expansion_containment_rationale"],
        "boundary_reinforcement": [
            "T1 does not authorize legitimacy generation",
            "T1 does not authorize governance interpretation or completion claims",
            "T1 does not authorize semantic replay inference or replay archaeology",
            "T1 does not authorize contradiction resolution or governance centralization",
            "T1 does not authorize self-authorizing surveillance",
        ],
        "anti_expansion_enforced": True,
        "t1_harness_scaffold_only": scaffold_only,
        "read_only": True,
    }


def write_json_readonly_emit(
    path: Path,
    payload: Dict[str, Any],
    *,
    tier0_hashes_before: Optional[Dict[str, str]] = None,
    tier0_hashes_after: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Emit observational JSON; refuses prohibited upstream Tier-0 write targets."""
    preservation = verify_readonly_preservation(
        path=path,
        tier0_hashes_before=tier0_hashes_before,
        tier0_hashes_after=tier0_hashes_after,
    )
    if not preservation["readonly_preservation_pass"]:
        raise RuntimeError(
            "G1_READONLY_PRESERVATION_VIOLATION: "
            f"refused write to {path.name}; attempted={preservation['attempted_upstream_mutations']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return preservation
