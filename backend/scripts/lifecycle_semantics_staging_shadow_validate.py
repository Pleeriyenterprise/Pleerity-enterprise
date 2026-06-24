#!/usr/bin/env python3
"""
LIFECYCLE-SEMANTICS-PHASE1-STAGING-SHADOW-VALIDATION-01

Read-only staging Mongo validation: resolve lifecycle semantics on real requirement rows
using local Phase 1 code with LIFECYCLE_SEMANTICS_MODE=shadow.

Does NOT write to Mongo, send reminders, recalculate scores, or modify staging API env.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

OUT_PATH = (
    ROOT
    / "docs"
    / "audit"
    / "LIFECYCLE_SEMANTICS_PHASE1_STAGING_SHADOW_VALIDATION.json"
)

SCENARIOS = [
    ("S1", "gas_safety", "EXPIRY_BASED"),
    ("S2", "eicr", "EXPIRY_BASED"),
    ("S3", "epc", "EXPIRY_BASED"),
    ("S4", "hmo_license", "EXPIRY_BASED"),
    ("S5", "legionella", "REVIEW_BASED"),
    ("S6", "deposit_pi", "DECLARATION_BASED"),
    ("S7", "right_to_rent", "OCCUPANCY_LIFECYCLE"),
    ("S8", "tenancy_agreement", "TENANCY_LIFECYCLE"),
    ("S9", "smoke_heat_alarms", "EVENT_BASED"),
    ("S10", "fitness_for_human_habitation", "OPERATIONAL"),
]

STAGING_DB_NAME = "pleerity_staging"
STAGING_API_BASE = os.getenv(
    "STAGE_Y_CVP_BASE_URL", "https://pleerity-enterprise.onrender.com"
).rstrip("/")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def _find_sample_requirement(db, slug: str) -> Optional[Dict[str, Any]]:
    or_clauses = [
        {"requirement_code": slug},
        {"requirement_type": slug},
        {"code": slug},
    ]
    return await db.requirements.find_one(
        {"$or": or_clauses},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )


async def _staging_api_health() -> Dict[str, Any]:
    import httpx

    out: Dict[str, Any] = {"base_url": STAGING_API_BASE}
    for path in ("/api/health", "/health", "/"):
        url = f"{STAGING_API_BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
            out["health_path"] = path
            out["http_status"] = resp.status_code
            out["reachable"] = resp.status_code < 500
            if resp.status_code == 200 and len(resp.text) < 2000:
                try:
                    out["body"] = resp.json()
                except Exception:
                    out["body_preview"] = resp.text[:300]
            break
        except Exception as exc:
            out["last_error"] = str(exc)
    return out


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    from services.lifecycle_semantics_config import get_lifecycle_semantics_mode
    from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
    from services.lifecycle_semantics_shadow import build_shadow_payload
    from services.requirement_client_runtime_surface import project_requirement_row_client_runtime

    os.environ["LIFECYCLE_SEMANTICS_MODE"] = "shadow"
    mode = get_lifecycle_semantics_mode()

    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    report: Dict[str, Any] = {
        "authority": "LIFECYCLE-SEMANTICS-PHASE1-STAGING-SHADOW-VALIDATION-01",
        "generated_at": _utc(),
        "local_commit": "99cfea46",
        "local_branch": "feature/lifecycle-semantics-phase1",
        "lifecycle_semantics_mode": mode,
        "active_mode_blocked": get_lifecycle_semantics_mode.__module__,
        "staging_database": STAGING_DB_NAME,
        "staging_api": await _staging_api_health(),
        "deploy_note": (
            "Shadow logs on Render require deploy of feature/lifecycle-semantics-phase1 "
            "with LIFECYCLE_SEMANTICS_MODE=shadow. This script validates resolver against "
            "staging Mongo rows using local Phase 1 code (read-only)."
        ),
        "scenarios": [],
        "unresolved": [],
        "conflicts": [],
        "parity_checks": [],
    }

    if mode != "shadow":
        report["error"] = f"expected shadow mode, got {mode}"
        OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    if not uri or "pleerity_staging" not in uri:
        report["error"] = "MONGO_URI must be pleerity_staging cluster user (read-only guard)"
        OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    mc = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=30000)
    db = mc[STAGING_DB_NAME]
    await db.command("ping")
    report["mongo_ping"] = "ok"

    for sid, slug, expected_semantics in SCENARIOS:
        row = await _find_sample_requirement(db, slug)
        entry: Dict[str, Any] = {
            "scenario_id": sid,
            "slug": slug,
            "expected_semantics": expected_semantics,
            "sample_found": row is not None,
        }
        if not row:
            report["unresolved"].append({"scenario": sid, "reason": "no_staging_sample_row"})
            entry["status"] = "NO_SAMPLE"
            report["scenarios"].append(entry)
            continue

        resolved = resolve_lifecycle_semantics(row)
        shadow = build_shadow_payload(row)
        entry["requirement_id"] = resolved.requirement_id
        entry["lifecycle_semantics"] = resolved.lifecycle_semantics
        entry["attention_kind"] = resolved.attention_kind
        entry["canonical_dates"] = resolved.canonical_dates.to_dict()
        entry["resolution_source"] = resolved.resolution_source
        entry["validation_issues"] = list(resolved.validation_issues)
        entry["shadow_divergence"] = shadow.get("divergence")

        if resolved.lifecycle_semantics != expected_semantics:
            entry["status"] = "SEMANTICS_MISMATCH"
            report["conflicts"].append(
                {
                    "scenario": sid,
                    "expected": expected_semantics,
                    "actual": resolved.lifecycle_semantics,
                }
            )
        elif resolved.validation_issues:
            conflicts = [i for i in resolved.validation_issues if i.startswith("conflict_")]
            if conflicts:
                entry["status"] = "CONFLICT"
                report["conflicts"].append({"scenario": sid, "issues": conflicts})
            else:
                entry["status"] = "PASS_WITH_NOTES"
        else:
            entry["status"] = "PASS"

        # Behaviour parity: projection unchanged by shadow hook
        os.environ["LIFECYCLE_SEMANTICS_MODE"] = "disabled"
        proj_disabled = project_requirement_row_client_runtime(dict(row))
        os.environ["LIFECYCLE_SEMANTICS_MODE"] = "shadow"
        proj_shadow = project_requirement_row_client_runtime(dict(row))
        parity_fields = ("status", "due_date", "evidence_state")
        parity_ok = all(proj_disabled.get(k) == proj_shadow.get(k) for k in parity_fields)
        entry["runtime_projection_parity"] = parity_ok
        if not parity_ok:
            entry["parity_diff"] = {
                k: {"disabled": proj_disabled.get(k), "shadow": proj_shadow.get(k)}
                for k in parity_fields
                if proj_disabled.get(k) != proj_shadow.get(k)
            }
        report["parity_checks"].append(
            {"scenario": sid, "projection_parity": parity_ok}
        )

        # Read-only score snapshot (no recalc)
        pid = row.get("property_id")
        cid = row.get("client_id")
        if pid and cid:
            score_doc = await db.property_compliance_scores.find_one(
                {"client_id": cid, "property_id": pid},
                {"_id": 0, "score": 1, "updated_at": 1},
            )
            entry["property_score_snapshot"] = score_doc

        report["scenarios"].append(entry)

    mc.close()

    # Active mode block check
    os.environ["LIFECYCLE_SEMANTICS_MODE"] = "active"
    from services.lifecycle_semantics_config import get_lifecycle_semantics_mode as _mode

    report["active_mode_resolves_to"] = _mode()

    passed = sum(1 for s in report["scenarios"] if s.get("status", "").startswith("PASS"))
    report["summary"] = {
        "scenarios_total": len(SCENARIOS),
        "scenarios_pass_or_pass_with_notes": passed,
        "unresolved_count": len(report["unresolved"]),
        "conflict_count": len(report["conflicts"]),
        "projection_parity_all": all(p["projection_parity"] for p in report["parity_checks"]),
    }

    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    ok = (
        report["summary"]["unresolved_count"] == 0
        and report["summary"]["projection_parity_all"]
        and report["active_mode_resolves_to"] == "disabled"
        and passed == len(SCENARIOS)
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
