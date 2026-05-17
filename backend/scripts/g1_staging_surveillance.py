"""
G1 staging surveillance driver — T1 read-only skeleton only.

ANTI_EXPANSION:
- implementation_scope=T1_ONLY
- No MongoDB / live staging surveillance without explicit approval AND non-T1 scope
- Default: refuse execution and emit skeleton posture only

Scaffold-only file evaluation (no DB):

  python -m scripts.g1_staging_surveillance --scaffold-only --slug-suffix 6fd5ac4c_d35a58ae

Live staging requires BOTH (future programme gates — never satisfied in T1):
  --explicit-execution-approval
  AND implementation_scope != T1_ONLY

Current T1 refuses live execution even when --explicit-execution-approval is set.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.g1_snapshot import (  # noqa: E402
    CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY,
    IMPLEMENTATION_SCOPE,
    READ_ONLY_SURVEILLANCE_ONLY,
    assemble_t1_launch_scope_registry,
    assemble_t1_readiness,
    assemble_t1_upstream_integrity,
    build_anti_seepage_envelope,
    enumerate_tier0_entries,
    evaluate_live_staging_gate,
    load_json_if_exists,
    resolve_surveillance_posture,
    write_json_readonly_emit,
)

DEFAULT_SLUG = "6fd5ac4c_d35a58ae"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="G1 staging surveillance skeleton (T1 only)")
    parser.add_argument("--slug-suffix", default=DEFAULT_SLUG)
    parser.add_argument("--out-dir", default="docs/audit")
    parser.add_argument("--manifest-version", type=int, default=1)
    parser.add_argument(
        "--scaffold-only",
        action="store_true",
        help="Read-only file-based T1 evaluation (no MongoDB).",
    )
    parser.add_argument(
        "--live-staging",
        action="store_true",
        help="Request live staging DB surveillance (refused under T1).",
    )
    parser.add_argument(
        "--explicit-execution-approval",
        action="store_true",
        help="Programme approval marker — insufficient alone for live staging.",
    )
    parser.add_argument(
        "--implementation-scope",
        default=IMPLEMENTATION_SCOPE,
        help="Scope authority marker; T1_ONLY always refuses live staging.",
    )
    return parser.parse_args()


def _tier0_hash_snapshot(audit_dir: Path, slug: str) -> Dict[str, str]:
    return {row["path"]: row["sha256"] for row in enumerate_tier0_entries(audit_dir, slug)}


def _refusal_payload(*, reason: str, gate: Dict[str, Any], extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "read_only_surveillance_only": READ_ONLY_SURVEILLANCE_ONLY,
        "surveillance_execution_authorised": False,
        "staging_surveillance_executed": False,
        "refusal_reason": reason,
        "live_staging_gate": gate,
    }
    if extra:
        payload.update(extra)
    return payload


def _run_scaffold(*, audit_dir: Path, slug: str, manifest_version: int) -> Dict[str, Any]:
    tier0_before = _tier0_hash_snapshot(audit_dir, slug)
    manifest_name = f"launch_baseline_manifest_{slug}_v{manifest_version}.json"
    manifest_path = audit_dir / manifest_name
    baseline_manifest = load_json_if_exists(manifest_path)
    baseline_scope_path = audit_dir / f"g1_launch_scope_registry_{slug}.json"
    baseline_scope = load_json_if_exists(baseline_scope_path)

    posture = resolve_surveillance_posture(
        audit_dir=audit_dir,
        slug=slug,
        baseline_manifest=baseline_manifest,
        baseline_scope=baseline_scope,
    )
    manifest = baseline_manifest or posture["manifest"]
    upstream = assemble_t1_upstream_integrity(slug=slug, manifest=manifest, posture=posture)
    scope_registry = assemble_t1_launch_scope_registry(slug=slug, posture=posture)
    readiness = assemble_t1_readiness(
        slug=slug,
        posture=posture,
        artifacts=[upstream, scope_registry],
        scaffold_only=True,
    )
    run_at = datetime.now(timezone.utc).isoformat()
    tier0_after = _tier0_hash_snapshot(audit_dir, slug)
    for artefact, name in (
        (upstream, f"g1_upstream_integrity_{slug}.json"),
        (scope_registry, f"g1_launch_scope_registry_{slug}.json"),
        (readiness, f"g1_launch_readiness_{slug}.json"),
    ):
        artefact["captured_at_utc"] = run_at
        artefact["g1_staging_skeleton"] = True
        write_json_readonly_emit(
            audit_dir / name,
            artefact,
            tier0_hashes_before=tier0_before,
            tier0_hashes_after=tier0_after,
        )

    return {
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "mode": "SCAFFOLD_ONLY",
        "surveillance_execution_authorised": False,
        "staging_surveillance_executed": False,
        "constitutional_authority_level": readiness.get(
            "constitutional_authority_level",
            CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY,
        ),
        "scaffold_legitimacy_prohibition_pass": readiness.get("scaffold_legitimacy_prohibition_pass"),
        "manifest_ref": manifest_name if baseline_manifest else "inline_baseline_from_tier0_scan",
        "surveillance_mode": readiness["surveillance_mode"],
        "g1_pass": readiness["g1_pass"],
        "verified_eligible": readiness["verified_eligible"],
        "done_eligible": readiness["done_eligible"],
        "primary_rc": readiness["primary_rc"],
        "missing_critical": posture["critical"]["missing_critical_authoritative_artifacts"],
        "readonly_preservation": tier0_before == tier0_after,
    }


def main() -> None:
    args = _parse_args()
    slug = args.slug_suffix.strip()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    live_gate = evaluate_live_staging_gate(
        explicit_execution_approval=args.explicit_execution_approval,
        implementation_scope=args.implementation_scope.strip(),
        live_staging_requested=args.live_staging,
    )

    if args.live_staging:
        payload = _refusal_payload(
            reason=live_gate["reason"],
            gate=live_gate,
            extra={
                "note": "Approval flag alone is insufficient; scope authority must exceed T1_ONLY.",
            },
        )
        print(json.dumps(payload, indent=2))
        sys.exit(2)

    if not args.scaffold_only:
        envelope = build_anti_seepage_envelope()
        payload = _refusal_payload(
            reason="EXECUTION_REFUSED_USE_SCAFFOLD_ONLY",
            gate=live_gate,
            extra={
                "hint": "Pass --scaffold-only for read-only file evaluation.",
                "attempted_scope_escalations": envelope.get("attempted_scope_escalations"),
            },
        )
        print(json.dumps(payload, indent=2))
        sys.exit(2)

    summary = _run_scaffold(audit_dir=out_dir, slug=slug, manifest_version=args.manifest_version)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
