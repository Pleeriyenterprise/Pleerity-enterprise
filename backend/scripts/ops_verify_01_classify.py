"""
OPS-VERIFY-01 journey classification from evidence bundles (read-only).

Never auto-assigns VERIFIED_OPERATIONALLY without bundle completeness + browser attestation.

  python -m scripts.ops_verify_01_classify --slug-suffix 6fd5ac4c_d35a58ae --out-dir docs/audit
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops_verify_01_manifest import (  # noqa: E402
    CHECKPOINTS,
    CLASSIFICATIONS,
    DEFAULT_SLUG,
    JOURNEY_A,
    JOURNEY_B,
    JOURNEY_C,
    JOURNEY_D,
    JOURNEYS,
    UNIT_ID,
    assess_bundle_completeness,
    bundle_dir,
    bundle_paths,
    read_json_if_exists,
    write_json,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OPS-VERIFY-01 classify journeys from bundle")
    p.add_argument("--slug-suffix", default=DEFAULT_SLUG)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--journeys", default="", help="Comma-separated journey keys; default all four")
    return p.parse_args()


def _ui_attestation(manifest: Dict[str, Any], journey: str) -> Dict[str, Any]:
    raw = manifest.get("ui_attestations") or {}
    if isinstance(raw.get(journey), dict):
        return raw[journey]
    return {}


def _checkpoint_results(manifest: Dict[str, Any], journey: str) -> Dict[str, bool]:
    raw = manifest.get("checkpoint_results") or {}
    journey_map = raw.get(journey) if isinstance(raw.get(journey), dict) else {}
    out: Dict[str, bool] = {}
    for cp in CHECKPOINTS.get(journey, ()):
        out[cp] = bool(journey_map.get(cp))
    return out


def _failed_checkpoints(checks: Dict[str, bool]) -> List[str]:
    return [k for k, v in checks.items() if not v]


def _classify_journey_a(
    *,
    completeness: Dict[str, Any],
    manifest: Dict[str, Any],
    baseline: Optional[Dict[str, Any]],
    post: Optional[Dict[str, Any]],
    convergence: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ui = _ui_attestation(manifest, JOURNEY_A)
    cps = _checkpoint_results(manifest, JOURNEY_A)
    failed = _failed_checkpoints(cps)
    reasons: List[str] = []

    if str(manifest.get("proof_mode")) in ("replay", "fixture") or manifest.get("replay_or_fixture_driver"):
        return _result(JOURNEY_A, "VERIFIED_REPLAY_ONLY", failed, reasons + ["replay_or_fixture_driver"])

    if not completeness.get("operational_evidence_ready"):
        return _result(
            JOURNEY_A,
            "IMPLEMENTED_NOT_VERIFIED",
            failed,
            reasons + ["bundle_incomplete_or_browser_not_attested"],
        )

    cer_delta = int((post or {}).get("cer_count_delta_from_baseline") or 0)
    if cer_delta <= 0 and not (post or {}).get("cer_rows"):
        reasons.append("no_cer_persistence_observed")
    if not (post or {}).get("authority_changed_from_baseline"):
        reasons.append("authority_unchanged_or_unobserved")

    if ui.get("user_visible_gap"):
        return _result(JOURNEY_A, "USER_VISIBLE_GAP", failed, reasons + ["ui_attestation_user_visible_gap"])

    conv = convergence or {}
    partial = conv.get("async_convergence_partial_signals") or {}
    if partial.get("pending_flag") or partial.get("queue_pending_or_running"):
        if cer_delta > 0 or (post or {}).get("cer_rows"):
            return _result(JOURNEY_A, "ASYNC_CONVERGENCE_PARTIAL", failed, reasons)

    if ui.get("trust_risk"):
        return _result(JOURNEY_A, "TRUST_RISK_PRESENT", failed, reasons)

    if reasons:
        if any("authority" in r or "cer" in r for r in reasons):
            return _result(JOURNEY_A, "SYSTEM_OUTCOME_UNPROVEN", failed, reasons)
        return _result(JOURNEY_A, "IMPLEMENTED_NOT_VERIFIED", failed, reasons)

    if failed:
        return _result(JOURNEY_A, "IMPLEMENTED_NOT_VERIFIED", failed, ["checkpoints_incomplete"])

    if all(cps.values()) and ui.get("submission_visible") and ui.get("refresh_persisted"):
        return _result(JOURNEY_A, "VERIFIED_OPERATIONALLY", failed, [])

    return _result(JOURNEY_A, "IMPLEMENTED_NOT_VERIFIED", failed, ["manual_checkpoints_or_ui_not_confirmed"])


def _classify_journey_b(
    *,
    completeness: Dict[str, Any],
    manifest: Dict[str, Any],
    baseline: Optional[Dict[str, Any]],
    post: Optional[Dict[str, Any]],
    convergence: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ui = _ui_attestation(manifest, JOURNEY_B)
    cps = _checkpoint_results(manifest, JOURNEY_B)
    failed = _failed_checkpoints(cps)
    reasons: List[str] = []

    if str(manifest.get("proof_mode")) in ("replay", "fixture") or manifest.get("replay_or_fixture_driver"):
        return _result(JOURNEY_B, "VERIFIED_REPLAY_ONLY", failed, ["replay_or_fixture_driver"])

    if not completeness.get("operational_evidence_ready"):
        return _result(JOURNEY_B, "IMPLEMENTED_NOT_VERIFIED", failed, ["bundle_incomplete_or_browser_not_attested"])

    docs = (post or {}).get("documents") or []
    if not docs:
        reasons.append("no_documents_observed")
    supporting_only = all(str(d.get("source") or "") == "supporting_evidence_attachment" for d in docs if docs)
    if supporting_only and docs:
        reasons.append("documents_are_supporting_only_not_primary_path")

    if ui.get("user_visible_gap"):
        return _result(JOURNEY_B, "USER_VISIBLE_GAP", failed, reasons)

    conv = convergence or {}
    partial = conv.get("async_convergence_partial_signals") or {}
    if partial.get("pending_flag") or partial.get("queue_pending_or_running"):
        if docs:
            return _result(JOURNEY_B, "ASYNC_CONVERGENCE_PARTIAL", failed, reasons)

    if reasons:
        return _result(JOURNEY_B, "SYSTEM_OUTCOME_UNPROVEN", failed, reasons)

    if failed:
        return _result(JOURNEY_B, "IMPLEMENTED_NOT_VERIFIED", failed, ["checkpoints_incomplete"])

    if all(cps.values()) and ui.get("document_visible"):
        return _result(JOURNEY_B, "VERIFIED_OPERATIONALLY", failed, [])

    return _result(JOURNEY_B, "IMPLEMENTED_NOT_VERIFIED", failed, ["manual_checkpoints_or_ui_not_confirmed"])


def _classify_journey_c(
    *,
    completeness: Dict[str, Any],
    manifest: Dict[str, Any],
    baseline: Optional[Dict[str, Any]],
    post: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ui = _ui_attestation(manifest, JOURNEY_C)
    cps = _checkpoint_results(manifest, JOURNEY_C)
    failed = _failed_checkpoints(cps)
    reasons: List[str] = []

    if str(manifest.get("proof_mode")) in ("replay", "fixture") or manifest.get("replay_or_fixture_driver"):
        return _result(JOURNEY_C, "VERIFIED_REPLAY_ONLY", failed, ["replay_or_fixture_driver"])

    if not completeness.get("browser_walkthrough_completed"):
        return _result(JOURNEY_C, "IMPLEMENTED_NOT_VERIFIED", failed, ["browser_walkthrough_not_attested"])

    cer_delta = int((post or {}).get("cer_count_delta_from_baseline") or 0)
    if cer_delta > 0:
        reasons.append("cer_created_on_supporting_only_path")

    if ui.get("false_completion_implied"):
        return _result(JOURNEY_C, "TRUST_RISK_PRESENT", failed, reasons + ["false_completion_implied"])

    if ui.get("user_visible_gap"):
        return _result(JOURNEY_C, "USER_VISIBLE_GAP", failed, reasons)

    if cer_delta > 0:
        return _result(JOURNEY_C, "TRUST_RISK_PRESENT", failed, reasons)

    if failed:
        return _result(JOURNEY_C, "IMPLEMENTED_NOT_VERIFIED", failed, ["checkpoints_incomplete"])

    if ui.get("supporting_only_copy_truthful") and ui.get("no_false_submission_panel"):
        if all(cps.values()):
            return _result(JOURNEY_C, "VERIFIED_OPERATIONALLY", failed, [])
        return _result(JOURNEY_C, "IMPLEMENTED_NOT_VERIFIED", failed, ["checkpoints_incomplete"])

    return _result(JOURNEY_C, "IMPLEMENTED_NOT_VERIFIED", failed, ["ui_attestations_incomplete"])


def _classify_journey_d(
    *,
    completeness: Dict[str, Any],
    manifest: Dict[str, Any],
    post: Optional[Dict[str, Any]],
    convergence: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if JOURNEY_D not in (manifest.get("journeys_executed") or []):
        return _result(JOURNEY_D, "IMPLEMENTED_NOT_VERIFIED", [], ["journey_not_executed_optional"])

    ui = _ui_attestation(manifest, JOURNEY_D)
    cps = _checkpoint_results(manifest, JOURNEY_D)
    failed = _failed_checkpoints(cps)

    if str(manifest.get("proof_mode")) in ("replay", "fixture"):
        return _result(JOURNEY_D, "VERIFIED_REPLAY_ONLY", failed, [])

    if not completeness.get("operational_evidence_ready"):
        return _result(JOURNEY_D, "IMPLEMENTED_NOT_VERIFIED", failed, ["bundle_incomplete"])

    cer_rows = (post or {}).get("cer_rows") or []
    verified = any(str(r.get("verification_status") or "").upper() in ("VERIFIED", "REJECTED") for r in cer_rows)
    if not verified:
        return _result(JOURNEY_D, "SYSTEM_OUTCOME_UNPROVEN", failed, ["verification_state_not_observed"])

    if ui.get("user_visible_gap"):
        return _result(JOURNEY_D, "USER_VISIBLE_GAP", failed, [])

    if all(cps.values()) and ui.get("labels_match_db"):
        return _result(JOURNEY_D, "VERIFIED_OPERATIONALLY", failed, [])

    return _result(JOURNEY_D, "IMPLEMENTED_NOT_VERIFIED", failed, ["checkpoints_or_ui_incomplete"])


def _result(journey: str, classification: str, failed: List[str], reasons: List[str]) -> Dict[str, Any]:
    if classification not in CLASSIFICATIONS:
        classification = "IMPLEMENTED_NOT_VERIFIED"
    return {
        "journey": journey,
        "classification": classification,
        "failed_checkpoints": failed,
        "reasons": reasons,
    }


def classify_bundle(
    bundle: Path,
    slug: str,
    *,
    journeys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    paths = bundle_paths(bundle, slug)
    manifest = read_json_if_exists(paths["manifest"]) or {}
    baseline = read_json_if_exists(paths["baseline"])
    post = read_json_if_exists(paths["post_submit"])
    convergence = read_json_if_exists(paths["convergence"])
    completeness = assess_bundle_completeness(
        bundle,
        slug,
        journeys=journeys or list(manifest.get("journeys_executed") or []) or None,
    )

    selected = journeys or list(JOURNEYS)
    results: List[Dict[str, Any]] = []
    for journey in selected:
        if journey == JOURNEY_A:
            results.append(
                _classify_journey_a(
                    completeness=completeness,
                    manifest=manifest,
                    baseline=baseline,
                    post=post,
                    convergence=convergence,
                )
            )
        elif journey == JOURNEY_B:
            results.append(
                _classify_journey_b(
                    completeness=completeness,
                    manifest=manifest,
                    baseline=baseline,
                    post=post,
                    convergence=convergence,
                )
            )
        elif journey == JOURNEY_C:
            results.append(
                _classify_journey_c(
                    completeness=completeness,
                    manifest=manifest,
                    baseline=baseline,
                    post=post,
                )
            )
        elif journey == JOURNEY_D:
            results.append(
                _classify_journey_d(
                    completeness=completeness,
                    manifest=manifest,
                    post=post,
                    convergence=convergence,
                )
            )

    payload = {
        "unit_id": UNIT_ID,
        "slug": slug,
        "bundle_completeness": completeness,
        "classifications": results,
        "rules": {
            "never_infer_from_replay": True,
            "never_infer_from_route_existence": True,
            "never_infer_from_enqueue_alone": True,
            "never_infer_from_optimistic_ui": True,
            "verified_operationally_requires": [
                "operational_evidence_ready",
                "all_mandatory_checkpoints_pass",
                "journey_specific_ui_attestations",
            ],
        },
    }
    write_json(paths["classifications"], payload)
    return payload


def main() -> None:
    args = _parse_args()
    audit_root = Path(args.out_dir)
    if not audit_root.is_absolute():
        audit_root = ROOT / audit_root
    slug = args.slug_suffix.strip()
    bundle = bundle_dir(audit_root, slug)
    journeys = [j.strip() for j in args.journeys.split(",") if j.strip()] or None
    payload = classify_bundle(bundle, slug, journeys=journeys)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
