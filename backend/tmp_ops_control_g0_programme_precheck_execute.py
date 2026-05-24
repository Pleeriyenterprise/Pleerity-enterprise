"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G0 programme precheck harness (infrastructure).

Default: --scaffold-only (no staging API calls, no G0 execution classification).
Use --execute-runtime only when explicitly running G0 verification (not enabled by default).

Local harness only — do not commit passwords or screenshots.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ops_runtime_verify_02.artifact_writer import ArtifactWriter, utc_now_iso
from services.ops_runtime_verify_02.classification_helpers import (
    ClassificationAggregator,
    implementation_classification,
)
from services.ops_runtime_verify_02.constants import (
    EXECUTION_STATUS_NOT_EXECUTED,
    PROGRAMME_ID,
    VERIFY_01_FAMILY_SLUGS,
    Verify02Family,
)
from services.ops_runtime_verify_02.control_plane_circularity_service import (
    ControlPlaneCircularityService,
)
from services.ops_runtime_verify_02.operational_orphan_service import OperationalOrphanService
from services.ops_runtime_verify_02.projection_resolution_service import ProjectionResolutionService
from services.ops_runtime_verify_02.route_authority_registry import RouteAuthorityRegistry

PROGRAMME = PROGRAMME_ID
FAMILY = Verify02Family.G0.value


def _slug(client_id: str, property_id: str) -> str:
    return f"{client_id.split('-')[0]}_{property_id.split('-')[0]}"


def _bundle_dir(client_id: str, property_id: str) -> Path:
    slug = _slug(client_id, property_id)
    return ROOT / "docs" / "audit" / f"ops_control_g0_programme_precheck_{slug}"


def _audit_root() -> Path:
    return ROOT / "docs" / "audit" / "ops_control_verify_02"


def _verify_01_lineage(slug: str) -> Dict[str, Any]:
    audit = ROOT / "docs" / "audit"
    rows: List[Dict[str, Any]] = []
    for fam in VERIFY_01_FAMILY_SLUGS:
        bundle_name = f"{fam}_{slug}"
        path = audit / bundle_name / "07_classification.json"
        row = {
            "family": fam,
            "bundle_path": f"{bundle_name}/07_classification.json",
            "present_on_disk": path.is_file(),
            "classification": None,
        }
        if path.is_file():
            try:
                row["classification"] = json.loads(path.read_text(encoding="utf-8")).get("classification")
            except json.JSONDecodeError:
                row["classification"] = "UNREADABLE"
        rows.append(row)
    return {
        "programme": "PRELAUNCH-OPS-RUNTIME-VERIFY-01",
        "pilot_slug": slug,
        "families": rows,
        "all_verified_operationally": all(r.get("classification") == "VERIFIED_OPERATIONALLY" for r in rows if r["present_on_disk"]),
    }


def _deployment_continuity() -> Dict[str, Any]:
    return {
        "checked_at": utc_now_iso(),
        "origin_main_sha": os.environ.get("OPS_VERIFY_ORIGIN_SHA", "unknown"),
        "staging_api": os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com/api"),
        "frontend_url": os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk"),
        "version_endpoint_attestation": "deferred_until_execute_runtime",
        "note": "Scaffold phase — deploy continuity probe not executed",
    }


def _baseline_projection_snapshot(*, execute_runtime: bool) -> Dict[str, Any]:
    if not execute_runtime:
        return {
            "dry_run": True,
            "note": "Baseline API snapshot deferred until G0 --execute-runtime",
            "snapshots": {},
        }
    return {"dry_run": False, "snapshots": {}, "note": "Populate in execute-runtime mode"}


def _operational_surface_inventory(registry: RouteAuthorityRegistry) -> Dict[str, Any]:
    return {
        "surfaces": [
            {
                "route": e.route,
                "family": e.authoritative_family_owner,
                "domain": e.operational_domain,
                "status": "NOT_EXECUTED",
            }
            for e in registry.entries
        ],
        "surface_count": len(registry.entries),
    }


def run_g0_scaffold(client_id: str, property_id: str, *, execute_runtime: bool = False) -> Path:
    slug = _slug(client_id, property_id)
    bundle = _bundle_dir(client_id, property_id)
    writer = ArtifactWriter(bundle, dry_run=not execute_runtime)

    registry = RouteAuthorityRegistry()
    circularity = ControlPlaneCircularityService(registry)
    projection = ProjectionResolutionService()
    orphan_svc = OperationalOrphanService(registry)

    writer.write_json("pilot_lock.json", {
        "programme": PROGRAMME,
        "client_id": client_id,
        "property_id": property_id,
        "pilot_slug": slug,
        "role": "client",
    })
    writer.write_json("deployment_continuity.json", _deployment_continuity())
    writer.write_json("verify_01_lineage.json", _verify_01_lineage(slug))
    writer.write_json("active_routes_snapshot.json", {"routes": registry.routes})
    writer.write_json("route_authority_map.json", registry.route_authority_map())
    writer.write_json("control_plane_circularity.json", circularity.build_artifact())
    writer.write_json("projection_resolution_order.json", projection.build_artifact())
    writer.write_json(
        "operational_orphan_audit.json",
        orphan_svc.audit_entities([], entry_surfaces=["/today", "/command-center", "/properties"]),
    )
    writer.write_json("operational_surface_inventory.json", _operational_surface_inventory(registry))
    writer.write_json("baseline_projection_snapshot.json", _baseline_projection_snapshot(execute_runtime=execute_runtime))
    writer.write_json("feature_flag_snapshot.json", {"note": "deferred_until_execute_runtime"})
    writer.write_json("entitlement_snapshot.json", {"note": "deferred_until_execute_runtime"})
    writer.write_json("surface_availability.json", {"note": "deferred_until_execute_runtime"})
    writer.write_json("cta_inventory_baseline.json", {"ctas": [], "note": "Populate at G0 execute-runtime"})

    agg = ClassificationAggregator(FAMILY)
    classification = agg.finalize(execution_completed=False)
    writer.write_json("07_classification.json", {
        **classification.to_dict(),
        "execution_status": EXECUTION_STATUS_NOT_EXECUTED,
        "implementation_phase": True,
        "scaffold_only": not execute_runtime,
    })
    writer.write_json("classifications.json", {"classifications": [classification.to_dict()]})

    writer.write_report_md(
        f"# G0 Programme Precheck — {slug}\n\n"
        f"**Programme:** `{PROGRAMME}`\n\n"
        f"**Status:** `{EXECUTION_STATUS_NOT_EXECUTED}`\n\n"
        f"**Mode:** `{'execute-runtime' if execute_runtime else 'scaffold-only'}`\n\n"
        "Framework artifacts generated. No operational verification executed.\n"
    )

    _write_programme_scaffold(slug)
    return bundle


def _write_programme_scaffold(slug: str) -> None:
    root = _audit_root()
    root.mkdir(parents=True, exist_ok=True)
    status = {
        "programme": PROGRAMME,
        "pilot_slug": slug,
        "families": {
            Verify02Family.G0.value: EXECUTION_STATUS_NOT_EXECUTED,
            Verify02Family.G1.value: EXECUTION_STATUS_NOT_EXECUTED,
            Verify02Family.G2.value: EXECUTION_STATUS_NOT_EXECUTED,
            Verify02Family.G3.value: EXECUTION_STATUS_NOT_EXECUTED,
            Verify02Family.G4.value: EXECUTION_STATUS_NOT_EXECUTED,
            Verify02Family.G5.value: EXECUTION_STATUS_NOT_EXECUTED,
            Verify02Family.G6.value: EXECUTION_STATUS_NOT_EXECUTED,
            Verify02Family.G7.value: EXECUTION_STATUS_NOT_EXECUTED,
        },
        "implementation_classification": implementation_classification(True),
    }
    (root / "PROGRAMME_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="VERIFY-02 G0 harness")
    parser.add_argument("--client-id", default=os.environ.get("OPS_VERIFY_CLIENT_ID", ""))
    parser.add_argument("--property-id", default=os.environ.get("OPS_VERIFY_PROPERTY_ID", ""))
    parser.add_argument(
        "--execute-runtime",
        action="store_true",
        help="Run G0 runtime probes (staging API). Default is scaffold-only.",
    )
    args = parser.parse_args()
    execute_runtime = bool(args.execute_runtime)
    client_id = args.client_id or "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
    property_id = args.property_id or "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
    if execute_runtime and (not args.client_id or not args.property_id):
        print("execute-runtime requires explicit --client-id and --property-id", file=sys.stderr)
        return 2

    bundle = run_g0_scaffold(client_id, property_id, execute_runtime=execute_runtime)
    print(json.dumps({"bundle_dir": str(bundle), "execute_runtime": execute_runtime}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
