"""
G1 preflight: Tier-0 manifest capture + T1 baseline registry (read-only).

Does not connect to MongoDB. Does not execute staging surveillance.
Does not mutate upstream B–F audit artefacts.

  python -m scripts.g1_preflight_capture --slug-suffix 6fd5ac4c_d35a58ae --out-dir docs/audit
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
    build_launch_baseline_manifest,
    build_t1_scope_registry_baseline,
    enumerate_tier0_entries,
    inventory_critical_authoritative,
    resolve_surveillance_posture,
    validate_manifest_t1,
    write_json_readonly_emit,
)

DEFAULT_SLUG = "6fd5ac4c_d35a58ae"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="G1 preflight capture (read-only, T1 only)")
    parser.add_argument("--slug-suffix", default=DEFAULT_SLUG)
    parser.add_argument("--out-dir", default="docs/audit")
    parser.add_argument("--manifest-version", type=int, default=1)
    return parser.parse_args()


def _tier0_hash_snapshot(audit_dir: Path, slug: str) -> Dict[str, str]:
    return {row["path"]: row["sha256"] for row in enumerate_tier0_entries(audit_dir, slug)}


def main() -> None:
    args = _parse_args()
    slug = args.slug_suffix.strip()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    audit_dir = out_dir
    run_at = datetime.now(timezone.utc).isoformat()
    tier0_before = _tier0_hash_snapshot(audit_dir, slug)

    manifest = build_launch_baseline_manifest(
        audit_dir=audit_dir,
        slug=slug,
        manifest_version=args.manifest_version,
    )
    manifest["captured_at_utc"] = run_at
    manifest["capture_phase"] = "G1_T1_PREFLIGHT"
    manifest_validation = validate_manifest_t1(manifest)

    manifest_name = f"launch_baseline_manifest_{slug}_v{args.manifest_version}.json"
    write_json_readonly_emit(
        audit_dir / manifest_name,
        manifest,
        tier0_hashes_before=tier0_before,
        tier0_hashes_after=tier0_before,
    )

    scope_baseline = build_t1_scope_registry_baseline(slug=slug)
    scope_baseline["captured_at_utc"] = run_at
    scope_baseline["baseline_manifest_ref"] = manifest_name

    posture = resolve_surveillance_posture(
        audit_dir=audit_dir,
        slug=slug,
        baseline_manifest=manifest,
        baseline_scope=scope_baseline,
    )
    upstream = assemble_t1_upstream_integrity(slug=slug, manifest=manifest, posture=posture)
    upstream["captured_at_utc"] = run_at
    upstream["manifest_validation"] = manifest_validation
    upstream["critical_inventory_at_capture"] = inventory_critical_authoritative(audit_dir, slug)

    scope_registry = assemble_t1_launch_scope_registry(slug=slug, posture=posture)
    scope_registry["captured_at_utc"] = run_at
    scope_registry["baseline_manifest_ref"] = manifest_name

    readiness = assemble_t1_readiness(
        slug=slug,
        posture=posture,
        artifacts=[upstream, scope_registry],
        scaffold_only=True,
    )
    readiness["captured_at_utc"] = run_at
    readiness["preflight_capture"] = True

    tier0_after = _tier0_hash_snapshot(audit_dir, slug)
    write_json_readonly_emit(
        audit_dir / f"g1_upstream_integrity_{slug}.json",
        upstream,
        tier0_hashes_before=tier0_before,
        tier0_hashes_after=tier0_after,
    )
    write_json_readonly_emit(
        audit_dir / f"g1_launch_scope_registry_{slug}.json",
        scope_registry,
        tier0_hashes_before=tier0_before,
        tier0_hashes_after=tier0_after,
    )
    write_json_readonly_emit(
        audit_dir / f"g1_launch_readiness_{slug}.json",
        readiness,
        tier0_hashes_before=tier0_before,
        tier0_hashes_after=tier0_after,
    )

    summary: Dict[str, Any] = {
        "implementation_scope": IMPLEMENTATION_SCOPE,
        "read_only_surveillance_only": READ_ONLY_SURVEILLANCE_ONLY,
        "staging_surveillance_executed": False,
        "constitutional_authority_level": readiness.get(
            "constitutional_authority_level",
            CONSTITUTIONAL_AUTHORITY_SCAFFOLD_ONLY,
        ),
        "scaffold_legitimacy_prohibition_pass": readiness.get("scaffold_legitimacy_prohibition_pass"),
        "manifest": manifest_name,
        "manifest_t1_valid": manifest_validation.get("manifest_t1_valid"),
        "manifest_assertion_scan_pass": manifest_validation.get("manifest_assertion_scan_pass"),
        "tier0_entry_count": len(manifest.get("tier0_entries") or []),
        "missing_critical": posture["critical"]["missing_critical_authoritative_artifacts"],
        "surveillance_mode": posture["surveillance_mode"],
        "g1_pass": readiness["g1_pass"],
        "verified_eligible": readiness["verified_eligible"],
        "done_eligible": readiness["done_eligible"],
        "primary_rc": readiness["primary_rc"],
        "readonly_preservation": tier0_before == tier0_after,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
