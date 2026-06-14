"""
JURISDICTION-COVERAGE-S1 staging proof — LEAD_TESTING|SCOTLAND lifecycle on existing staging property.

Read/write: pleerity_staging only. Restores original building_age_years on exit.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

OUT_DIR = ROOT / "docs" / "audit" / "jurisdiction_coverage_s1_lead_testing_scotland"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def _lead_row(db, client_id: str, property_id: str) -> Optional[Dict[str, Any]]:
    return await db.requirements.find_one(
        {
            "client_id": client_id,
            "property_id": property_id,
            "$or": [
                {"requirement_type": "lead_testing"},
                {"requirement_code": "lead_testing"},
            ],
        },
        {"_id": 0},
    )


async def _set_age(db, client_id: str, property_id: str, age: Optional[int]) -> None:
    await db.properties.update_one(
        {"client_id": client_id, "property_id": property_id},
        {"$set": {"building_age_years": age, "updated_at": _utc()}},
    )


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient
    from database import database
    from services.catalog_compliance import get_property_compliance_detail
    from services.compliance_evidence_record_service import (
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
        create_compliance_evidence_record,
        validate_lead_testing_structured_declaration_fields,
    )
    from services.compliance_scoring_service import recalculate_and_persist
    from services.requirement_materialization_service import materialize_requirements_for_property
    from services.requirement_truth import enrich_requirements_for_client
    from services.compliance_scoring_v2 import compute_property_score_v2

    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    if not uri:
        print(json.dumps({"error": "MONGO_URI not set"}))
        return 1

    mc = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=30000)
    db = mc["pleerity_staging"]
    database.db = db
    await db.command("ping")

    prop = await db.properties.find_one(
        {
            "jurisdiction": {"$regex": "^Scotland$", "$options": "i"},
            "tenancy_active": True,
            "property_type": {"$nin": ["commercial", "COMMERCIAL"]},
        },
        {"_id": 0},
    )
    if not prop:
        prop = await db.properties.find_one(
            {"jurisdiction": {"$regex": "^Scotland$", "$options": "i"}},
            {"_id": 0},
        )
    if not prop:
        print(json.dumps({"error": "no_staging_scotland_property"}))
        mc.close()
        return 2

    cid = prop["client_id"]
    pid = prop["property_id"]
    original_age = prop.get("building_age_years")
    report: Dict[str, Any] = {
        "wave": "JURISDICTION-COVERAGE-S1-REMEDIATION",
        "started_at": _utc(),
        "staging_property": {
            "client_id": cid,
            "property_id": pid,
            "jurisdiction": prop.get("jurisdiction"),
            "tenancy_active": prop.get("tenancy_active"),
            "original_building_age_years": original_age,
        },
        "steps": [],
    }

    async def step(name: str, age: Optional[int]) -> Dict[str, Any]:
        await _set_age(db, cid, pid, age)
        mat = await materialize_requirements_for_property(cid, pid, reconcile_obsolete=True)
        row = await _lead_row(db, cid, pid)
        prop_doc = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0})
        detail = await get_property_compliance_detail(cid, pid)
        matrix_codes = [m.get("requirement_code") for m in (detail or {}).get("matrix") or []]
        editorial = None
        if row:
            enriched, _ = await enrich_requirements_for_client(db, cid, [row])
            editorial = (enriched[0].get("why_it_matters_short") if enriched else None)
        score_before = await recalculate_and_persist(property_id=pid, reason="S1_STAGING_PROOF")
        reqs = [row] if row else []
        v2 = compute_property_score_v2(
            property_doc=prop_doc or {},
            client_doc=await db.clients.find_one({"client_id": cid}, {"_id": 0}),
            requirements=reqs,
            documents=[],
            open_issues_count=0,
            overdue_work_orders_count=0,
            open_risks_count=0,
        )
        lt_breakdown = [
            b for b in (v2.get("requirement_breakdown") or []) if b.get("requirement_code") == "LEAD_TESTING"
        ]
        return {
            "step": name,
            "building_age_years": age,
            "materialisation": mat,
            "lead_row": {
                "present": row is not None,
                "requirement_id": (row or {}).get("requirement_id"),
                "status": (row or {}).get("status"),
                "applicability": (row or {}).get("applicability"),
                "client_surface_visible": (row or {}).get("client_surface_visible"),
            },
            "matrix_includes_lead_testing": "lead_testing" in matrix_codes,
            "matrix_codes": matrix_codes,
            "editorial_why_short": editorial,
            "recalc_score": (score_before or {}).get("score_0_100") if isinstance(score_before, dict) else score_before,
            "scoring_lead_testing": lt_breakdown[0] if lt_breakdown else None,
        }

    try:
        s1 = await step("age_70_materialise", 70)
        report["steps"].append(s1)

        cer_evidence = None
        row = await _lead_row(db, cid, pid)
        if row:
            structured = {
                "assessment_completed": {"answer": True},
                "assessment_date": {"answer": "2026-01-15"},
                "assessment_type": {"answer": "full_assessment"},
                "risk_level": {"answer": "low"},
                "lead_present": {"answer": False},
                "actions_required": {"answer": False},
                "declaration_confirmed": {"answer": True},
            }
            val_err = validate_lead_testing_structured_declaration_fields(structured)
            cer_evidence = {"validation_error": val_err}
            if not val_err:
                try:
                    cer = await create_compliance_evidence_record(
                        db,
                        requirement=row,
                        evidence_mode=EVIDENCE_MODE_STRUCTURED_DECLARATION,
                        created_by_user_id="s1_staging_proof",
                        evidence_payload={
                            "declaration_statement": "Lead risk assessment record (S1 staging proof)",
                            "structured_fields": structured,
                        },
                        verification_status="VERIFIED",
                    )
                    cer_evidence["created"] = True
                    cer_evidence["evidence_record_id"] = cer.get("evidence_record_id")
                except Exception as exc:
                    cer_evidence["created"] = False
                    cer_evidence["error"] = str(exc)
            row_after_cer = await _lead_row(db, cid, pid)
            cer_evidence["requirement_status_after"] = (row_after_cer or {}).get("status")
        report["cer_submission"] = cer_evidence

        s2 = await step("age_30_reconcile", 30)
        report["steps"].append(s2)

        s3 = await step("age_70_reopen", 70)
        report["steps"].append(s3)

        report["gates"] = {
            "age_70_materialised": s1["lead_row"]["present"],
            "matrix_visible_at_70": s1["matrix_includes_lead_testing"],
            "scoring_applies_at_70": (s1.get("scoring_lead_testing") or {}).get("applies_if") is True,
            "age_30_reconciled": s2["lead_row"].get("applicability") == "NOT_REQUIRED"
            or s2["lead_row"].get("status") == "NOT_REQUIRED"
            or not s2["lead_row"]["present"],
            "age_70_reopened": s3["lead_row"]["present"]
            and (s3["lead_row"].get("applicability") or "").upper() != "NOT_REQUIRED",
        }
    finally:
        await _set_age(db, cid, pid, original_age)
        await materialize_requirements_for_property(cid, pid, reconcile_obsolete=True)
        report["restored_building_age_years"] = original_age
        report["completed_at"] = _utc()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "staging_proof_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    mc.close()
    return 0 if all(report.get("gates", {}).values()) else 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
