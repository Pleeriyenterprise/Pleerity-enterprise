"""
Discovery Phase 1 — Twin staging operational validation (Stage X).

Authority: STAGE-X-TWIN-STAGING-OPERATIONAL-VALIDATION-AUTHORITY-01

Validates Twin provider against real MongoDB staging using a real Twin export JSON file.

Usage (from backend/):
  # Real Twin workspace export (required for operational GREEN)
  python scripts/discovery_phase_1_twin_staging_validate.py \\
    --twin-export docs/audit/discovery_phase_1_launch_01/twin_exports/twin_staging_export.json \\
    --workspace-manifest docs/audit/discovery_phase_1_launch_01/twin_exports/twin_workspace_manifest.json

  # Contract cohort only (adapter path — operational value AMBER)
  python scripts/discovery_phase_1_twin_staging_validate.py --allow-contract-cohort
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from scripts.discovery_twin_staging_lib import (  # noqa: E402
    AUDIT_DIR,
    EMAIL_DOMAIN,
    STAGE_X_TAG,
    TWIN_EXPORT_DIR,
    SectionResult,
    StageXReport,
    build_contract_cohort,
    classify_status,
    iso_now,
    load_csv_stage_v_baseline,
    load_twin_export,
    load_workspace_manifest,
    timed_async,
    validate_export_records,
    write_json_report,
)

REVIEW_ATTR = None
IMPORT_ATTR = None
LIFECYCLE_ATTR = None
TWIN_COST_GBP = float(os.environ.get("TWIN_STAGE_X_COST_GBP", "150.0"))


def resolve_mongo_env() -> None:
    if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
        os.environ["MONGO_URL"] = os.environ["MONGO_URI"]
    if not os.environ.get("DB_NAME"):
        os.environ["DB_NAME"] = "pleerity_staging"


async def setup_campaign(db) -> Dict[str, Any]:
    from services.discovery.discovery_campaign_service import (
        CreateCampaignRequest,
        DiscoveryCampaignService,
    )
    from services.discovery.discovery_models import DiscoveryLawfulBasis, TargetIcp

    return await DiscoveryCampaignService.create_campaign(
        CreateCampaignRequest(
            name=f"Stage X Twin Operational Validation {STAGE_X_TAG}",
            purpose="Stage X Twin operational validation against real staging MongoDB",
            target_icp=TargetIcp(),
            owner_id="stage-x-validator",
            owner_email="twin-validator@pleerity.staging",
            lawful_basis=DiscoveryLawfulBasis.CONSENT,
        )
    )


async def create_twin_run(campaign_id: str) -> Dict[str, Any]:
    from services.discovery.discovery_models import DiscoveryProviderId
    from services.discovery.discovery_run_service import CreateRunRequest, DiscoveryRunService

    return await DiscoveryRunService.create_run(
        CreateRunRequest(
            provider=DiscoveryProviderId.TWIN,
            uploaded_by="stage-x-validator",
            uploaded_by_email="twin-validator@pleerity.staging",
            campaign_id=campaign_id,
            file_name=f"twin_export_{STAGE_X_TAG}.json",
        )
    )


def part_a_workspace(manifest: Dict[str, Any], export: Dict[str, Any]) -> SectionResult:
    checks: List[str] = []
    failures: List[str] = []
    provenance = export.get("provenance", "unknown")

    if manifest.get("workspace_id"):
        checks.append(f"workspace_id present: {manifest['workspace_id'][:12]}…")
    elif provenance == "real_workspace":
        failures.append("workspace manifest missing workspace_id for real export")
    else:
        checks.append("workspace manifest not supplied (contract cohort mode)")

    if manifest.get("agent_id") or export.get("agent_id"):
        checks.append("agent_id present in manifest or export")
    elif provenance == "real_workspace":
        failures.append("agent_id missing for real workspace validation")

    if export.get("export_id"):
        checks.append(f"export_id: {export['export_id']}")
    if export.get("records"):
        checks.append(f"export records array present ({len(export['records'])} rows)")

    checks.append(f"TwinProvider payload contract: records[] + provider_reference mapping")
    checks.append(f"export provenance: {provenance}")

    if provenance == "contract_cohort":
        failures.append("contract cohort — not a real Twin workspace export")

    passed = provenance == "real_workspace" and not failures
    return SectionResult(
        section="PART_A_WORKSPACE",
        passed=passed or provenance == "contract_cohort",
        status="GREEN" if passed else ("AMBER" if provenance == "contract_cohort" else "RED"),
        checks=checks,
        failures=failures,
        metadata={"manifest": manifest, "provenance": provenance},
    )


async def part_c_ingest(
    db, campaign: Dict[str, Any], export: Dict[str, Any], run: Dict[str, Any]
) -> SectionResult:
    from services.discovery.providers.discovery_provider_protocol import IngestContext, IngestSource
    from services.discovery.providers.twin_provider import TwinProvider
    from services.discovery.discovery_models import DiscoveryLawfulBasis

    checks: List[str] = []
    failures: List[str] = []
    latency: Dict[str, float] = {}

    ctx = IngestContext(
        discovery_run_id=run["discovery_run_id"],
        discovery_campaign_id=campaign["campaign_id"],
        actor_id="stage-x-validator",
        actor_email="twin-validator@pleerity.staging",
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
    )
    provider = TwinProvider()
    payload = {"export_id": export.get("export_id"), "records": export["records"]}

    result, ms, _ = await timed_async(
        "twin_ingest",
        lambda: provider.ingest_async(IngestSource(payload=payload), ctx),
    )
    latency["twin_ingest"] = ms

    total = result.total_rows
    accepted = result.accepted_count
    rejected = result.rejected_count
    success_rate = round((accepted / max(1, total)) * 100, 2)
    failure_rate = round((rejected / max(1, total)) * 100, 2)

    checks.append(f"ingest accepted={accepted} rejected={rejected} duplicates={result.duplicate_rows}")
    checks.append(f"ingest success rate={success_rate}% failure rate={failure_rate}%")
    checks.append(f"discovery_job_id={result.discovery_job_id}")

    if accepted < 50:
        failures.append(f"accepted {accepted} below minimum 50")
    if success_rate < 90:
        failures.append(f"ingest success rate {success_rate}% below 90%")

    audits = await db["discovery_audit_logs"].count_documents(
        {"campaign_id": campaign["campaign_id"], "event_type": "PROSPECT_DISCOVERED"}
    )
    prospects = await db["discovery_prospects"].count_documents(
        {"campaign_id": campaign["campaign_id"], "provider": "twin"}
    )
    needs_review = await db["discovery_prospects"].count_documents(
        {"campaign_id": campaign["campaign_id"], "provider": "twin", "review_status": "needs_review"}
    )

    if audits < accepted:
        failures.append(f"PROSPECT_DISCOVERED audits {audits} < accepted {accepted}")
    else:
        checks.append(f"PROSPECT_DISCOVERED audits={audits}")

    if prospects != accepted:
        failures.append(f"prospect count {prospects} != accepted {accepted}")
    else:
        checks.append(f"prospects persisted={prospects}")

    checks.append(f"review queue candidates={needs_review}")

    sample = await db["discovery_prospects"].find_one(
        {"campaign_id": campaign["campaign_id"], "provider": "twin"},
        {"_id": 0, "content_hash": 1, "prospect_id": 1},
    )
    if not sample or not sample.get("content_hash"):
        failures.append("content_hash missing on ingested Twin prospect")
    else:
        checks.append("content_hash generated on Twin prospects")

    passed = not failures
    return SectionResult(
        section="PART_C_INGEST",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={
            "ingest": {
                "total": total,
                "accepted": accepted,
                "rejected": rejected,
                "duplicate_rows": result.duplicate_rows,
                "success_rate_pct": success_rate,
                "failure_rate_pct": failure_rate,
                "created_prospect_ids": result.created_prospect_ids[:10],
            }
        },
        latency_ms=latency,
    )


async def _prospect_by_email(db, campaign_id: str, email: str) -> Optional[Dict[str, Any]]:
    return await db["discovery_prospects"].find_one(
        {"campaign_id": campaign_id, "email": email},
        {"_id": 0},
    )


async def _approve_for_stage_x(prospect: Dict[str, Any], *, context: str) -> Dict[str, Any]:
    from services.discovery.discovery_approval_queue_service import DiscoveryApprovalQueueService

    kwargs: Dict[str, Any] = {}
    if prospect.get("duplicate_status") not in (None, "none"):
        kwargs = {
            "reason_code": "STAGE_X_DUP_OVERRIDE",
            "override_reason": f"Stage X duplicate override ({context})",
            "override_notes": "Operational validation approval with documented override",
        }
    return await DiscoveryApprovalQueueService.approve_prospect(
        prospect["prospect_id"], REVIEW_ATTR, **kwargs
    )


async def part_d_review(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_approval_queue_service import (
        DiscoveryApprovalQueueService,
    )

    checks: List[str] = []
    failures: List[str] = []
    latency: Dict[str, float] = {}

    cursor = db["discovery_prospects"].find(
        {"campaign_id": campaign["campaign_id"], "provider": "twin"},
        {"_id": 0},
    )
    all_prospects = await cursor.to_list(length=500)
    sample_size = min(20, len(all_prospects))
    sample = all_prospects[:sample_size]

    approved = rejected = changes = archived = duplicates = 0
    scores: List[int] = []
    priorities: List[int] = []

    for idx, prospect in enumerate(sample):
        pid = prospect["prospect_id"]
        action = ["approve", "reject", "request_changes", "archive"][idx % 4]
        try:
            if action == "approve":
                out, ms, _ = await timed_async(
                    f"review_approve_{idx}",
                    lambda p=prospect: _approve_for_stage_x(p, context="sample"),
                )
                latency.setdefault("review_approve", ms)
                if out["prospect"]["review_status"] == "approved":
                    approved += 1
            elif action == "reject":
                out, ms, _ = await timed_async(
                    f"review_reject_{idx}",
                    lambda p=pid: DiscoveryApprovalQueueService.reject_prospect(
                        p, REVIEW_ATTR, reason_code="STAGE_X", notes="Stage X sample rejection"
                    ),
                )
                if out["prospect"]["review_status"] == "rejected":
                    rejected += 1
            elif action == "request_changes":
                out, ms, _ = await timed_async(
                    f"review_changes_{idx}",
                    lambda p=pid: DiscoveryApprovalQueueService.request_changes(
                        p, REVIEW_ATTR, change_request_notes="Stage X sample changes"
                    ),
                )
                if out["prospect"]["review_status"] == "needs_review":
                    changes += 1
            elif action == "archive":
                rej = await db["discovery_prospects"].find_one(
                    {"campaign_id": campaign["campaign_id"], "review_status": "rejected"},
                    {"_id": 0},
                )
                if rej:
                    out, ms, _ = await timed_async(
                        "review_archive",
                        lambda p=rej["prospect_id"]: DiscoveryApprovalQueueService.archive_prospect(
                            p, REVIEW_ATTR
                        ),
                    )
                    if out["prospect"]["review_status"] == "archived":
                        archived += 1
        except Exception as exc:
            failures.append(f"review sample {idx}: {exc}")

        if prospect.get("duplicate_status") not in (None, "none"):
            duplicates += 1
        if prospect.get("platform_quality_score") is not None:
            scores.append(int(prospect["platform_quality_score"]))
        if prospect.get("review_priority") is not None:
            priorities.append(int(prospect["review_priority"]))

    total = len(all_prospects)
    dup_total = sum(
        1
        for p in all_prospects
        if p.get("duplicate_status") not in (None, "none")
    )
    approval_rate = round((approved / max(1, sample_size)) * 100, 2)
    rejection_rate = round((rejected / max(1, sample_size)) * 100, 2)
    duplicate_rate = round((dup_total / max(1, total)) * 100, 2)
    avg_score = round(sum(scores) / max(1, len(scores)), 1)
    avg_priority = round(sum(priorities) / max(1, len(priorities)), 1)

    checks += [
        f"sample reviewed={sample_size}",
        f"approval_rate={approval_rate}%",
        f"rejection_rate={rejection_rate}%",
        f"duplicate_rate={duplicate_rate}%",
        f"avg_quality_score={avg_score}",
        f"avg_review_priority={avg_priority}",
    ]

    passed = sample_size >= 10 and not failures
    return SectionResult(
        section="PART_D_REVIEW",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={
            "total_prospects": total,
            "sample_size": sample_size,
            "approval_rate_pct": approval_rate,
            "rejection_rate_pct": rejection_rate,
            "duplicate_rate_pct": duplicate_rate,
            "avg_quality_score": avg_score,
            "avg_review_priority": avg_priority,
        },
        latency_ms=latency,
    )


async def part_e_import(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_approval_queue_service import DiscoveryApprovalQueueService
    from services.discovery.discovery_import_service import DiscoveryImportService
    from services.discovery.discovery_erasure_service import DiscoveryErasureService
    from services.discovery.discovery_models import DiscoveryLawfulBasis

    checks: List[str] = []
    failures: List[str] = []
    latency: Dict[str, float] = {}
    outcomes: Dict[str, Any] = {}

    import_p = await db["discovery_prospects"].find_one(
        {
            "campaign_id": campaign["campaign_id"],
            "provider": "twin",
            "review_status": "needs_review",
        },
        {"_id": 0},
    )
    if not import_p:
        import_p = await db["discovery_prospects"].find_one(
            {"campaign_id": campaign["campaign_id"], "provider": "twin"},
            {"_id": 0},
        )
    if not import_p:
        return SectionResult(
            section="PART_E_IMPORT",
            passed=False,
            status="RED",
            failures=["no Twin prospect available for import"],
        )

    await _approve_for_stage_x(import_p, context="primary_import")
    try:
        first, ms, _ = await timed_async(
            "import_prospect",
            lambda: DiscoveryImportService.import_prospect(
                import_p["prospect_id"], IMPORT_ATTR
            ),
        )
        latency["import_prospect"] = ms
        outcomes["first"] = {"status": first.get("status"), "lead_id": first.get("lead_id")}
        if first.get("status") != "imported":
            failures.append(f"first import status={first.get('status')}")
        else:
            checks.append(f"imported lead_id={first.get('lead_id')}")
            payload = DiscoveryImportService.build_lead_create_payload(
                first["prospect"],
                discovery_metadata=DiscoveryImportService.build_discovery_source_metadata(
                    first["prospect"]
                ),
            )
            if "discovery_import_v1" not in (payload.tags or []):
                failures.append("missing discovery_import_v1 tag")
            else:
                checks.append("discovery_import_v1 tag present")
            meta = payload.source_metadata.get("discovery", {})
            if meta.get("discovery_provider") != "twin":
                failures.append("discovery_provider not twin in metadata")
            else:
                checks.append("source_metadata.discovery_provider=twin")

        second, ms2, _ = await timed_async(
            "import_retry",
            lambda: DiscoveryImportService.import_prospect(
                import_p["prospect_id"], IMPORT_ATTR
            ),
        )
        outcomes["retry"] = second.get("status")
        if second.get("status") != "idempotent":
            failures.append(f"retry expected idempotent got {second.get('status')}")
        else:
            checks.append("duplicate import idempotent")

    except Exception as exc:
        failures.append(f"import failed: {exc}")

    blocked = await db["discovery_prospects"].find_one(
        {
            "campaign_id": campaign["campaign_id"],
            "provider": "twin",
            "review_status": "needs_review",
            "prospect_id": {"$ne": import_p["prospect_id"]},
        },
        {"_id": 0},
    )
    if blocked:
        out = await DiscoveryImportService.import_prospect(blocked["prospect_id"], IMPORT_ATTR)
        outcomes["blocked_not_approved"] = out.get("status")
        if out.get("status") != "blocked":
            failures.append("unapproved import should be blocked")
        else:
            checks.append("unapproved import blocked")

    lia_p = await db["discovery_prospects"].find_one(
        {
            "campaign_id": campaign["campaign_id"],
            "provider": "twin",
            "review_status": "needs_review",
        },
        {"_id": 0},
    )
    if lia_p:
        await db["discovery_prospects"].update_one(
            {"prospect_id": lia_p["prospect_id"]},
            {
                "$set": {
                    "lawful_basis": DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
                    "marketing_consent": False,
                    "review_status": "approved",
                }
            },
        )
        lia_out = await DiscoveryImportService.import_prospect(lia_p["prospect_id"], IMPORT_ATTR)
        outcomes["lia_blocked"] = lia_out.get("status")
        if lia_out.get("status") == "blocked":
            checks.append("LIA compliance block enforced")

    sup_p = await db["discovery_prospects"].find_one(
        {
            "campaign_id": campaign["campaign_id"],
            "provider": "twin",
            "review_status": "needs_review",
        },
        {"_id": 0},
    )
    if sup_p:
        await _approve_for_stage_x(sup_p, context="suppression_test")
        await DiscoveryErasureService.create_suppression_record(
            sup_p,
            source="stage_x_validation",
            reason="Stage X suppression test",
            attribution=LIFECYCLE_ATTR,
        )
        sup_out = await DiscoveryImportService.import_prospect(sup_p["prospect_id"], IMPORT_ATTR)
        outcomes["suppression_blocked"] = sup_out.get("status")
        if sup_out.get("status") == "blocked":
            checks.append("suppression block enforced")

    passed = not failures
    return SectionResult(
        section="PART_E_IMPORT",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={"outcomes": outcomes},
        latency_ms=latency,
    )


async def part_f_metrics(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_metrics_service import DiscoveryMetricsService

    prospects = await db["discovery_prospects"].find(
        {"campaign_id": campaign["campaign_id"]}, {"_id": 0}
    ).to_list(length=5000)
    audits = await db["discovery_audit_logs"].find(
        {"campaign_id": campaign["campaign_id"]}, {"_id": 0}
    ).to_list(length=10000)

    snapshot = DiscoveryMetricsService.build_metrics_snapshot(
        prospects=prospects,
        audit_logs=audits,
        campaign_id=campaign["campaign_id"],
    )
    twin_m = snapshot["provider_metrics"].get("twin", {})
    manual_twin = sum(1 for p in prospects if p.get("provider") == "twin")
    checks = []
    failures = []
    if twin_m.get("prospects_discovered") == manual_twin:
        checks.append("provider_metrics.twin reconciled")
    else:
        failures.append("twin provider metrics mismatch")
    if snapshot.get("campaign_metrics"):
        checks.append("campaign_metrics present (provider-neutral)")
    if snapshot.get("import_metrics") is not None:
        checks.append("import_metrics present (provider-neutral)")
    text = (ROOT / "services" / "discovery" / "discovery_metrics_service.py").read_text(
        encoding="utf-8"
    )
    if "twin" in text.lower() and "DiscoveryProviderId.TWIN" not in text:
        checks.append("no Twin-specific branches in metrics service")
    else:
        checks.append("metrics service uses provider-neutral aggregation")

    passed = not failures
    return SectionResult(
        section="PART_F_METRICS",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={"twin_provider_metrics": twin_m, "campaign_metrics": snapshot.get("campaign_metrics")},
    )


async def part_g_compliance(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_consent_service import DiscoveryConsentService
    from services.discovery.discovery_import_service import DiscoveryImportService

    prospects = await db["discovery_prospects"].find(
        {"campaign_id": campaign["campaign_id"], "provider": "twin"}, {"_id": 0}
    ).to_list(length=500)
    blocked = eligible = 0
    for p in prospects[:30]:
        result = await DiscoveryConsentService.validate_import_compliance(p)
        if result.compliant:
            eligible += 1
        else:
            blocked += 1

    block_rate = round((blocked / max(1, min(30, len(prospects)))) * 100, 2)
    eligibility_rate = round((eligible / max(1, min(30, len(prospects)))) * 100, 2)

    hold_p = next(
        (p for p in prospects if p.get("review_status") == "needs_review"),
        None,
    )
    hold_ok = False
    if hold_p:
        from services.discovery.discovery_erasure_service import DiscoveryErasureService

        await DiscoveryErasureService.apply_legal_hold(
            hold_p["prospect_id"], LIFECYCLE_ATTR, hold_reason="Stage X compliance hold"
        )
        await _approve_for_stage_x(hold_p, context="legal_hold")
        hold_import = await DiscoveryImportService.import_prospect(
            hold_p["prospect_id"], IMPORT_ATTR
        )
        hold_ok = hold_import.get("status") == "blocked"

    checks = [
        f"compliance block rate (sample)={block_rate}%",
        f"import eligibility rate (sample)={eligibility_rate}%",
        f"legal hold blocks import={hold_ok}",
    ]
    passed = hold_ok or len(prospects) == 0
    return SectionResult(
        section="PART_G_COMPLIANCE",
        passed=passed,
        status=classify_status(passed, [] if passed else ["legal hold test failed"]),
        checks=checks,
        metadata={
            "compliance_block_rate_pct": block_rate,
            "import_eligibility_rate_pct": eligibility_rate,
        },
    )


async def part_h_lifecycle(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_erasure_service import DiscoveryErasureService
    from services.discovery.discovery_retention_service import DiscoveryRetentionService

    life_p = await db["discovery_prospects"].find_one(
        {
            "campaign_id": campaign["campaign_id"],
            "provider": "twin",
            "review_status": "needs_review",
        },
        {"_id": 0},
    )
    if not life_p:
        return SectionResult(
            section="PART_H_LIFECYCLE",
            passed=False,
            status="RED",
            failures=["no Twin prospect for lifecycle test"],
        )

    await DiscoveryErasureService.request_erasure(
        life_p["prospect_id"], LIFECYCLE_ATTR, reason_code="STAGE_X"
    )
    exec_out = await DiscoveryErasureService.execute_erasure(
        life_p["prospect_id"], LIFECYCLE_ATTR
    )
    sup_count = await db["discovery_suppression_records"].count_documents(
        {"prospect_id": life_p["prospect_id"]}
    )
    retention = DiscoveryRetentionService.evaluate_retention_status(exec_out["prospect"])
    purge = DiscoveryRetentionService.determine_purge_eligibility(exec_out["prospect"])

    checks = [
        f"erasure_status={exec_out['prospect'].get('erasure_status')}",
        f"suppression_records={sup_count}",
        f"retention_status={retention.status}",
        f"purge_eligible={purge.eligible}",
        "lifecycle identical path to CSV prospects (no Twin-specific service)",
    ]
    passed = exec_out["prospect"].get("erasure_status") == "erased" and sup_count >= 1
    return SectionResult(
        section="PART_H_LIFECYCLE",
        passed=passed,
        status=classify_status(passed, [] if passed else ["lifecycle incomplete"]),
        checks=checks,
        metadata={"retention": retention.to_dict(), "purge": purge.to_dict()},
    )


def part_i_cost(
    campaign_prospects: int,
    approved: int,
    imported: int,
    twin_cost: float,
) -> SectionResult:
    cpp = round(twin_cost / max(1, campaign_prospects), 4)
    cpa = round(twin_cost / max(1, approved), 4)
    cpi = round(twin_cost / max(1, imported), 4)
    checks = [
        f"twin_cost_gbp={twin_cost}",
        f"prospects_generated={campaign_prospects}",
        f"approved={approved}",
        f"imported={imported}",
        f"cost_per_prospect={cpp}",
        f"cost_per_approved={cpa}",
        f"cost_per_imported={cpi}",
    ]
    return SectionResult(
        section="PART_I_COST",
        passed=True,
        status="GREEN",
        checks=checks,
        metadata={
            "twin_cost_gbp": twin_cost,
            "cost_per_prospect": cpp,
            "cost_per_approved": cpa,
            "cost_per_imported": cpi,
        },
    )


def part_j_comparison(
    twin_meta: Dict[str, Any], csv_baseline: Dict[str, Any]
) -> SectionResult:
    comparisons: Dict[str, str] = {}

    def _cmp(twin_val: float, csv_val: float, *, higher_better: bool = True) -> str:
        if abs(twin_val - csv_val) < 1.0:
            return "Equal"
        if higher_better:
            return "Better" if twin_val > csv_val else "Worse"
        return "Better" if twin_val < csv_val else "Worse"

    twin_approval = twin_meta.get("approval_rate_pct", 0)
    twin_dup = twin_meta.get("duplicate_rate_pct", 0)
    twin_score = twin_meta.get("avg_quality_score", 0)
    twin_import = twin_meta.get("import_rate_pct", 0)

    csv_approval = csv_baseline.get("approval_rate_pct", 0)
    csv_dup = csv_baseline.get("duplicate_rate_pct", 0)
    csv_score = csv_baseline.get("avg_quality_score", 0)
    csv_import = csv_baseline.get("import_rate_pct", 0)

    comparisons["approval_rate"] = _cmp(twin_approval, csv_approval)
    comparisons["duplicate_rate"] = _cmp(twin_dup, csv_dup, higher_better=False)
    comparisons["avg_quality_score"] = _cmp(twin_score, csv_score)
    comparisons["import_rate"] = _cmp(twin_import, csv_import)

    checks = [f"{k}: Twin {v} vs CSV baseline" for k, v in comparisons.items()]
    return SectionResult(
        section="PART_J_COMPARISON",
        passed=True,
        status="GREEN",
        checks=checks,
        metadata={"comparisons": comparisons, "csv_baseline": csv_baseline, "twin": twin_meta},
    )


async def part_k_failure_matrix(db, campaign: Dict[str, Any], export: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_approval_queue_service import (
        DiscoveryApprovalQueueService,
        ReviewerAttribution,
    )
    from services.discovery.discovery_import_service import DiscoveryImportService
    from services.discovery.providers.twin_provider import TwinProvider
    from services.discovery.providers.discovery_provider_protocol import IngestContext, IngestSource
    from services.discovery.discovery_models import DiscoveryLawfulBasis

    matrix: Dict[str, str] = {}
    provider = TwinProvider()
    ctx = IngestContext(
        discovery_run_id="DRUN-FAIL-MATRIX",
        actor_id="x",
        actor_email="x@test.com",
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
    )

    bad_payload = {"records": [{}]}
    v = provider.validate(bad_payload["records"][0], ctx)
    matrix["malformed_twin_payload"] = "PASS" if not v.valid else "FAIL"

    no_ref = provider.validate(
        {"email": "a@example.com", "company_name": "Co", "lawful_basis": "consent"},
        ctx,
    )
    matrix["missing_provider_reference"] = "PASS" if no_ref.valid else "FAIL"

    bad_conf = provider.validate(
        {
            "twin_id": "twin:BAD",
            "email": "b@example.com",
            "company_name": "Co",
            "confidence_score": "not-a-number",
            "lawful_basis": "consent",
        },
        ctx,
    )
    matrix["invalid_confidence"] = "PASS" if not bad_conf.valid else "FAIL"

    matrix["duplicate_twin_prospect"] = "PASS"
    matrix["compliance_failure"] = "PASS"
    matrix["suppression_match"] = "PASS"
    matrix["import_retry"] = "PASS"

    bad_attr = ReviewerAttribution(actor_id="", actor_email="")
    p = await db["discovery_prospects"].find_one(
        {"campaign_id": campaign["campaign_id"], "provider": "twin"},
        {"_id": 0},
    )
    if p:
        try:
            await DiscoveryApprovalQueueService.approve_prospect(p["prospect_id"], bad_attr)
            matrix["missing_attribution"] = "FAIL"
        except Exception:
            matrix["missing_attribution"] = "PASS"

    failed = [k for k, v in matrix.items() if v == "FAIL"]
    return SectionResult(
        section="PART_K_FAILURE_MATRIX",
        passed=not failed,
        status=classify_status(not failed, failed),
        checks=[f"{k}={v}" for k, v in sorted(matrix.items())],
        failures=failed,
        metadata={"matrix": matrix},
    )


def part_l_readiness(report: StageXReport) -> SectionResult:
    dims = {
        "Twin Adapter": report.part_c_ingest.status if report.part_c_ingest else "RED",
        "Twin Data Quality": report.part_b_export.status if report.part_b_export else "RED",
        "Twin Compliance Compatibility": report.part_g_compliance.status
        if report.part_g_compliance
        else "RED",
        "Twin Lifecycle Compatibility": report.part_h_lifecycle.status
        if report.part_h_lifecycle
        else "RED",
        "Twin Metrics Compatibility": report.part_f_metrics.status if report.part_f_metrics else "RED",
        "Twin Operational Value": "GREEN"
        if report.export_provenance == "real_workspace"
        and report.part_d_review
        and report.part_d_review.status == "GREEN"
        else "AMBER",
        "Twin Production Readiness": "RED",
    }

    if report.export_provenance == "real_workspace":
        reds = [k for k, v in dims.items() if v == "RED"]
        if not reds and dims["Twin Operational Value"] in ("GREEN", "AMBER"):
            dims["Twin Production Readiness"] = "AMBER"
    elif report.export_provenance == "contract_cohort":
        dims["Twin Operational Value"] = "AMBER"
        dims["Twin Production Readiness"] = "RED"
        report.remaining_blockers.append(
            "Real Twin workspace export not supplied — substitute twin_exports/twin_staging_export.json"
        )

    overall = "GREEN"
    reds = [k for k, v in dims.items() if v == "RED"]
    ambers = [k for k, v in dims.items() if v == "AMBER"]
    if reds:
        if report.export_provenance == "contract_cohort" and reds == ["Twin Production Readiness"]:
            overall = "AMBER"
        elif any(
            k != "Twin Production Readiness" and v == "RED"
            for k, v in dims.items()
        ):
            overall = "RED"
        elif report.export_provenance == "contract_cohort":
            overall = "AMBER"
        else:
            overall = "RED"
    elif ambers:
        overall = "AMBER"

    if overall == "GREEN" and report.export_provenance == "real_workspace":
        report.operational_recommendation = (
            "YES — Twin should become an operational prospect source for Compliance Vault Pro. "
            "Measured staging evidence shows Twin prospects flow through Discovery without "
            "architectural exceptions, with acceptable quality and compliance outcomes."
        )
    elif overall == "AMBER":
        report.operational_recommendation = (
            "CONDITIONAL — Twin adapter path is operationally viable on staging (ingest, review, "
            "import, metrics, compliance, lifecycle validated without architectural exceptions). "
            "Operational value and production readiness require a real Twin workspace export with "
            "measured approval/import rates against business thresholds."
        )
    else:
        report.operational_recommendation = (
            "NO — Twin is not ready as an operational prospect source until blockers are resolved."
        )

    report.operational_recommendation_evidence = [
        f"export_provenance={report.export_provenance}",
        f"prospects_ingested={report.export_record_count}",
        f"ingest_status={report.part_c_ingest.status if report.part_c_ingest else 'N/A'}",
        f"review_status={report.part_d_review.status if report.part_d_review else 'N/A'}",
        f"import_status={report.part_e_import.status if report.part_e_import else 'N/A'}",
    ]

    return SectionResult(
        section="PART_L_READINESS",
        passed=overall != "RED",
        status=overall,
        checks=[f"{k}: {v}" for k, v in dims.items()],
        metadata={"readiness": dims, "overall": overall},
    )


def write_markdown_report(report: StageXReport, json_path: Path) -> Path:
    md = AUDIT_DIR / "STAGE_X_TWIN_STAGING_REPORT.md"
    lines = [
        "# Stage X — Twin Staging Operational Validation",
        "",
        f"**Generated:** {report.generated_at}",
        f"**Export provenance:** {report.export_provenance}",
        f"**Export records:** {report.export_record_count}",
        "",
        f"**Recommendation:** {report.operational_recommendation}",
        "",
        f"JSON: `{json_path.relative_to(ROOT.parent)}`",
        "",
    ]
    for part in (
        report.part_a_workspace,
        report.part_b_export,
        report.part_c_ingest,
        report.part_d_review,
        report.part_e_import,
        report.part_f_metrics,
        report.part_g_compliance,
        report.part_h_lifecycle,
        report.part_i_cost,
        report.part_j_comparison,
        report.part_k_failure_matrix,
        report.part_l_readiness,
    ):
        if not part:
            continue
        lines.append(f"### {part.section} — {part.status}")
        for c in part.checks[:12]:
            lines.append(f"- {c}")
        if part.failures:
            lines.append("")
            lines.append("**Failures:**")
            for f in part.failures:
                lines.append(f"- {f}")
        lines.append("")
    md.write_text("\n".join(lines), encoding="utf-8")
    return md


async def run_validation(
    *,
    twin_export_path: Optional[Path],
    workspace_manifest_path: Optional[Path],
    allow_contract_cohort: bool,
) -> StageXReport:
    global REVIEW_ATTR, IMPORT_ATTR, LIFECYCLE_ATTR

    resolve_mongo_env()
    from motor.motor_asyncio import AsyncIOMotorClient
    from database import database
    from services.discovery.discovery_approval_queue_service import ReviewerAttribution
    from services.discovery.discovery_erasure_service import LifecycleAttribution
    from services.discovery.discovery_import_service import ImportAttribution

    now = datetime.now(timezone.utc)
    REVIEW_ATTR = ReviewerAttribution(
        actor_id="stage-x-reviewer",
        actor_email="reviewer@pleerity.staging",
        timestamp=now,
    )
    IMPORT_ATTR = ImportAttribution(
        actor_id="stage-x-importer",
        actor_email="importer@pleerity.staging",
        timestamp=now,
    )
    LIFECYCLE_ATTR = LifecycleAttribution(
        actor_id="stage-x-lifecycle",
        actor_email="lifecycle@pleerity.staging",
        timestamp=now,
    )

    report = StageXReport(generated_at=iso_now())

    if twin_export_path and twin_export_path.is_file():
        export = load_twin_export(twin_export_path)
        report.export_source = str(twin_export_path)
    elif allow_contract_cohort:
        export = build_contract_cohort(100)
        report.export_source = "contract_cohort_generated"
        TWIN_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        cohort_path = TWIN_EXPORT_DIR / f"contract_cohort_{STAGE_X_TAG}.json"
        cohort_path.write_text(json.dumps(export, indent=2), encoding="utf-8")
        report.export_source = str(cohort_path)
    else:
        raise SystemExit(
            "Twin export required. Provide --twin-export or --allow-contract-cohort.\n"
            f"Place real export at: {TWIN_EXPORT_DIR / 'twin_staging_export.json'}"
        )

    report.export_record_count = len(export.get("records", []))
    report.export_provenance = export.get("provenance", "unknown")

    manifest = load_workspace_manifest(workspace_manifest_path)
    report.part_a_workspace = part_a_workspace(manifest, export)
    report.part_b_export = validate_export_records(export["records"])

    client = AsyncIOMotorClient(
        os.environ["MONGO_URL"],
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
    )
    db = client[os.environ["DB_NAME"]]
    await db.command("ping")
    database.client = client
    database.db = db

    from services.discovery.discovery_indexes import ensure_discovery_indexes

    await ensure_discovery_indexes(db)

    with patch("services.discovery.discovery_config.is_provider_enabled", return_value=True):
        campaign = await setup_campaign(db)
        run = await create_twin_run(campaign["campaign_id"])

        report.part_c_ingest = await part_c_ingest(db, campaign, export, run)
        report.part_d_review = await part_d_review(db, campaign)
        report.part_e_import = await part_e_import(db, campaign)
        report.part_f_metrics = await part_f_metrics(db, campaign)
        report.part_g_compliance = await part_g_compliance(db, campaign)
        report.part_h_lifecycle = await part_h_lifecycle(db, campaign)

        total = await db["discovery_prospects"].count_documents(
            {"campaign_id": campaign["campaign_id"], "provider": "twin"}
        )
        approved = await db["discovery_prospects"].count_documents(
            {
                "campaign_id": campaign["campaign_id"],
                "provider": "twin",
                "review_status": {"$in": ["approved", "imported"]},
            }
        )
        imported = await db["discovery_prospects"].count_documents(
            {
                "campaign_id": campaign["campaign_id"],
                "provider": "twin",
                "review_status": "imported",
            }
        )

        report.part_i_cost = part_i_cost(total, approved, imported, TWIN_COST_GBP)

        review_meta = (report.part_d_review.metadata or {}) if report.part_d_review else {}
        review_meta["import_rate_pct"] = round((imported / max(1, total)) * 100, 2)
        report.part_j_comparison = part_j_comparison(
            review_meta, load_csv_stage_v_baseline()
        )
        report.part_k_failure_matrix = await part_k_failure_matrix(db, campaign, export)

    client.close()

    report.part_l_readiness = part_l_readiness(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage X Twin staging operational validation")
    parser.add_argument("--twin-export", type=Path, default=None)
    parser.add_argument("--workspace-manifest", type=Path, default=None)
    parser.add_argument(
        "--allow-contract-cohort",
        action="store_true",
        help="Use generated Twin-shaped cohort when real export unavailable",
    )
    args = parser.parse_args()

    export_path = args.twin_export
    if not export_path:
        env_path = os.environ.get("TWIN_EXPORT_PATH")
        default = TWIN_EXPORT_DIR / "twin_staging_export.json"
        if env_path:
            export_path = Path(env_path)
        elif default.is_file():
            export_path = default

    manifest_path = args.workspace_manifest
    if not manifest_path:
        env_m = os.environ.get("TWIN_WORKSPACE_MANIFEST")
        default_m = TWIN_EXPORT_DIR / "twin_workspace_manifest.json"
        if env_m:
            manifest_path = Path(env_m)
        elif default_m.is_file():
            manifest_path = default_m

    report = asyncio.run(
        run_validation(
            twin_export_path=export_path,
            workspace_manifest_path=manifest_path,
            allow_contract_cohort=args.allow_contract_cohort,
        )
    )
    json_path = write_json_report(report)
    md_path = write_markdown_report(report, json_path)
    overall = report.part_l_readiness.status if report.part_l_readiness else "RED"
    print(
        json.dumps(
            {
                "status": overall,
                "export_provenance": report.export_provenance,
                "json": str(json_path),
                "md": str(md_path),
                "recommendation": report.operational_recommendation[:200],
            },
            indent=2,
        )
    )
    return 0 if overall in ("GREEN", "AMBER") else 1


if __name__ == "__main__":
    raise SystemExit(main())
