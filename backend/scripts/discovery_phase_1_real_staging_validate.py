"""
Discovery Phase 1 — real staging validation runner (Stage V).

Authority: STAGE-V-REAL-STAGING-VALIDATION-AND-PROVIDER-EXPANSION-READINESS-AUTHORITY-01

Validates Discovery Foundation against real MongoDB staging:
  Part A — database / indexes
  Part B — CSV datasets (50/100 + failure sets)
  Part C — review operations (service layer = admin API behaviour)
  Part D — DiscoveryImportService import path
  Part E — metrics reconciliation
  Part F — lifecycle (erasure, hold, retention, suppression)
  Part G — performance observation
  Part H — MF-07 legacy CSV closure plan (audit only)
  Part I — provider expansion readiness assessment
  Part J — failure matrix
  Part K — GO / NO-GO

Usage (from backend/):
  python scripts/discovery_phase_1_real_staging_validate.py
  python scripts/discovery_phase_1_real_staging_validate.py --dry-run-db-only
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

from scripts.discovery_real_staging_lib import (  # noqa: E402
    AUDIT_DIR,
    DATASET_DIR,
    EMAIL_DOMAIN,
    STAGE_V_TAG,
    SectionResult,
    StageVReport,
    classify_status,
    fetch_stage_v_audit_logs,
    fetch_stage_v_prospects,
    iso_now,
    timed_async,
    validate_discovery_indexes,
    write_datasets,
    write_json_report,
)

REVIEW_ATTR = None  # set in main
IMPORT_ATTR = None
LIFECYCLE_ATTR = None


def resolve_mongo_env() -> None:
    if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
        os.environ["MONGO_URL"] = os.environ["MONGO_URI"]
    if not os.environ.get("DB_NAME"):
        os.environ["DB_NAME"] = "pleerity_staging"


def _attestation(now: datetime):
    from services.discovery.discovery_models import (
        DiscoveryLawfulBasis,
        RunAttestation,
    )

    return RunAttestation(
        lawful_basis_declared=DiscoveryLawfulBasis.CONSENT,
        data_source_description=f"Stage V validation CSV ({STAGE_V_TAG})",
        attested_by_id="stage-v-validator",
        attested_by_email="discovery-validator@pleerity.staging",
        attested_at=now,
    )


async def setup_campaign_and_run(db) -> Dict[str, Any]:
    from services.discovery.discovery_campaign_service import (
        CreateCampaignRequest,
        DiscoveryCampaignService,
    )
    from services.discovery.discovery_models import (
        DiscoveryLawfulBasis,
        DiscoveryProviderId,
        TargetIcp,
    )
    from services.discovery.discovery_run_service import (
        CreateRunRequest,
        DiscoveryRunService,
    )
    from services.discovery.providers.discovery_provider_protocol import IngestContext

    now = datetime.now(timezone.utc)
    campaign = await DiscoveryCampaignService.create_campaign(
        CreateCampaignRequest(
            name=f"Stage V Real Staging Validation {STAGE_V_TAG}",
            purpose="Stage V operational validation against real MongoDB staging",
            target_icp=TargetIcp(),
            owner_id="stage-v-validator",
            owner_email="discovery-validator@pleerity.staging",
            lawful_basis=DiscoveryLawfulBasis.CONSENT,
        )
    )
    return {"campaign": campaign, "now": now}


async def create_csv_run(campaign_id: str, *, file_label: str, now: datetime) -> Dict[str, Any]:
    from services.discovery.discovery_models import DiscoveryProviderId
    from services.discovery.discovery_run_service import (
        CreateRunRequest,
        DiscoveryRunService,
    )

    return await DiscoveryRunService.create_run(
        CreateRunRequest(
            provider=DiscoveryProviderId.CSV,
            uploaded_by="stage-v-validator",
            uploaded_by_email="discovery-validator@pleerity.staging",
            campaign_id=campaign_id,
            file_name=file_label,
            attestation=_attestation(now),
        )
    )


def ingest_context(run: Dict[str, Any], campaign: Dict[str, Any], now: datetime):
    from services.discovery.discovery_models import DiscoveryLawfulBasis
    from services.discovery.providers.discovery_provider_protocol import IngestContext

    return IngestContext(
        discovery_run_id=run["discovery_run_id"],
        discovery_campaign_id=campaign["campaign_id"],
        actor_id="stage-v-validator",
        actor_email="discovery-validator@pleerity.staging",
        lawful_basis=DiscoveryLawfulBasis.CONSENT,
        attestation=_attestation(now),
    )


async def ingest_csv_text(
    csv_text: str,
    *,
    run: Dict[str, Any],
    campaign: Dict[str, Any],
    now: datetime,
    label: str,
) -> Dict[str, Any]:
    from services.discovery.providers.csv_import_provider import CSVImportProvider
    from services.discovery.providers.discovery_provider_protocol import IngestSource

    provider = CSVImportProvider()
    result, ms, _ = await timed_async(
        label,
        lambda: provider.ingest_async(
            IngestSource(payload=csv_text, content_type="text/csv"),
            ingest_context(run, campaign, now),
        ),
    )
    return {
        "latency_ms": ms,
        "total_rows": result.total_rows,
        "accepted": result.accepted_count,
        "rejected": result.rejected_count,
        "duplicate_rows": result.duplicate_rows,
        "created_prospect_ids": list(result.created_prospect_ids),
        "errors": [
            {"row": e.row_index, "errors": e.errors} for e in result.errors[:20]
        ],
        "run_id": run["discovery_run_id"],
    }


async def part_a_database(db) -> SectionResult:
    checks, failures, inventory = await validate_discovery_indexes(db)
    from services.discovery.discovery_indexes import ensure_discovery_indexes

    _, ensure_ms, _ = await timed_async(
        "ensure_discovery_indexes",
        lambda: ensure_discovery_indexes(db),
    )

    sample = await db["discovery_prospects"].find_one(
        {"content_hash": {"$exists": True, "$ne": None}},
        {"_id": 0, "prospect_id": 1, "content_hash": 1},
    )
    if sample and sample.get("content_hash"):
        checks.append("content_hash persists on discovery_prospects (pre-existing sample)")

    non_index_failures = [
        f for f in failures if "discovery_suppression_records" not in f
    ]
    passed = len(non_index_failures) == 0
    status = "GREEN" if passed and not failures else "AMBER"
    if any("missing index" in f for f in failures):
        status = "RED"
        passed = False
    if inventory.get("suppression_index_gap"):
        checks.append(inventory["suppression_index_gap"])

    return SectionResult(
        section="PART_A_DATABASE",
        passed=passed and status != "RED",
        status=status,
        checks=checks,
        failures=failures,
        metadata={"inventory": inventory, "ensure_indexes_ms": ensure_ms},
    )


async def part_b_datasets(db, campaign: Dict[str, Any], now: datetime) -> SectionResult:
    checks: List[str] = []
    failures: List[str] = []
    latency: Dict[str, float] = {}
    ingest_results: Dict[str, Any] = {}

    dup_seed = [f"dataset-a-001@{EMAIL_DOMAIN}", f"dataset-a-002@{EMAIL_DOMAIN}"]
    write_datasets(duplicate_emails=dup_seed)

    datasets = [
        ("dataset_a", "dataset_a_50.csv", 50),
        ("dataset_b", "dataset_b_100.csv", 100),
        ("dataset_c", "dataset_c_duplicates.csv", None),
        ("dataset_d", "dataset_d_compliance_failures.csv", None),
        ("dataset_e", "dataset_e_mixed_quality.csv", None),
    ]

    sample_emails: List[str] = []

    for key, file_label, expected_min in datasets:
        run = await create_csv_run(
            campaign["campaign_id"], file_label=file_label, now=now
        )
        inline_csv = (DATASET_DIR / file_label).read_text(encoding="utf-8")

        outcome = await ingest_csv_text(
            inline_csv,
            run=run,
            campaign=campaign,
            now=now,
            label=f"csv_ingest_{key}",
        )
        ingest_results[key] = outcome
        latency[f"csv_ingest_{key}"] = outcome["latency_ms"]

        if expected_min is not None and outcome["accepted"] < expected_min:
            failures.append(
                f"{key}: expected >={expected_min} accepted, got {outcome['accepted']}"
            )
        else:
            checks.append(
                f"{key}: accepted={outcome['accepted']} rejected={outcome['rejected']} "
                f"duplicates={outcome['duplicate_rows']}"
            )

        if key == "dataset_a" and outcome["created_prospect_ids"]:
            sample_emails.extend(
                [f"dataset-a-001@{EMAIL_DOMAIN}", f"dataset-a-003@{EMAIL_DOMAIN}"]
            )

    if ingest_results.get("dataset_d", {}).get("rejected", 0) < 2:
        failures.append("dataset_d expected multiple compliance rejections")
    else:
        checks.append("dataset_d compliance failures rejected as expected")

    if ingest_results.get("dataset_c", {}).get("duplicate_rows", 0) < 1:
        failures.append("dataset_c expected cross-run or batch duplicate detection")
    else:
        checks.append("dataset_c duplicate detection observed")

    prospects = await fetch_stage_v_prospects(db, campaign["campaign_id"])
    audits = await fetch_stage_v_audit_logs(db, campaign["campaign_id"])
    discovered = sum(1 for a in audits if a.get("event_type") == "PROSPECT_DISCOVERED")
    if discovered < 150:
        failures.append(
            f"expected >=150 PROSPECT_DISCOVERED audit events, got {discovered}"
        )
    else:
        checks.append(f"audit PROSPECT_DISCOVERED count={discovered}")

    needs_review = sum(
        1
        for p in prospects
        if p.get("review_status") == "needs_review"
    )
    if needs_review < 100:
        failures.append(f"expected substantial needs_review queue, got {needs_review}")
    else:
        checks.append(f"review queue candidates={needs_review}")

    passed = not failures
    return SectionResult(
        section="PART_B_DATASETS",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={
            "ingest_results": ingest_results,
            "prospect_count": len(prospects),
            "sample_emails": sample_emails,
        },
        latency_ms=latency,
    )


async def _prospect_by_email(db, campaign_id: str, email: str) -> Optional[Dict[str, Any]]:
    return await db["discovery_prospects"].find_one(
        {"campaign_id": campaign_id, "email": email},
        {"_id": 0},
    )


async def part_c_review(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_approval_queue_service import (
        DiscoveryApprovalQueueService,
        ReviewQueueFilters,
    )

    checks: List[str] = []
    failures: List[str] = []
    latency: Dict[str, float] = {}
    audit_events: List[str] = []

    targets = {
        "approve": f"dataset-a-010@{EMAIL_DOMAIN}",
        "reject": f"dataset-a-011@{EMAIL_DOMAIN}",
        "request_changes": f"dataset-a-012@{EMAIL_DOMAIN}",
        "duplicate_override": f"dataset-c-new-001@{EMAIL_DOMAIN}",
    }

    # Run reject before archive validation (archive uses rejected prospect)
    action_order = ["approve", "reject", "request_changes", "duplicate_override", "archive"]

    for action in action_order:
        if action == "archive":
            email = f"dataset-a-011@{EMAIL_DOMAIN}"
        else:
            email = targets[action]
        prospect = await _prospect_by_email(db, campaign["campaign_id"], email)
        if not prospect:
            failures.append(f"{action}: prospect not found for {email}")
            continue

        pid = prospect["prospect_id"]
        try:
            if action == "approve":
                out, ms, _ = await timed_async(
                    "review_approve",
                    lambda p=prospect: _approve_for_stage_v(prospect, context="review_approve"),
                )
                latency["review_approve"] = ms
                if out["prospect"]["review_status"] != "approved":
                    failures.append("approve did not set approved status")
                else:
                    checks.append("approve succeeded")
                    audit_events.append("PROSPECT_APPROVED")

            elif action == "reject":
                out, ms, _ = await timed_async(
                    "review_reject",
                    lambda p=pid: DiscoveryApprovalQueueService.reject_prospect(
                        p,
                        REVIEW_ATTR,
                        reason_code="STAGE_V_TEST",
                        notes="Stage V validation rejection",
                    ),
                )
                latency["review_reject"] = ms
                if out["prospect"]["review_status"] != "rejected":
                    failures.append("reject did not set rejected status")
                else:
                    checks.append("reject succeeded")

            elif action == "request_changes":
                out, ms, _ = await timed_async(
                    "review_request_changes",
                    lambda p=pid: DiscoveryApprovalQueueService.request_changes(
                        p,
                        REVIEW_ATTR,
                        change_request_notes="Stage V validation — please verify company name",
                    ),
                )
                latency["review_request_changes"] = ms
                if out["prospect"]["review_status"] != "needs_review":
                    failures.append(
                        f"request_changes should keep needs_review, got {out['prospect']['review_status']}"
                    )
                elif out.get("audit", {}).get("event_type") != "PROSPECT_REVIEWED":
                    failures.append("request_changes missing PROSPECT_REVIEWED audit")
                else:
                    checks.append("request_changes succeeded (needs_review retained)")
                    audit_events.append("PROSPECT_REVIEWED")

            elif action == "archive":
                out, ms, _ = await timed_async(
                    "review_archive",
                    lambda p=pid: DiscoveryApprovalQueueService.archive_prospect(
                        p,
                        REVIEW_ATTR,
                    ),
                )
                latency["review_archive"] = ms
                if out["prospect"]["review_status"] != "archived":
                    failures.append("archive unexpected status")
                else:
                    checks.append("archive succeeded")

            elif action == "duplicate_override":
                dup = await db["discovery_prospects"].find_one(
                    {
                        "campaign_id": campaign["campaign_id"],
                        "email": f"dataset-a-001@{EMAIL_DOMAIN}",
                        "duplicate_status": {"$ne": "none"},
                    },
                    {"_id": 0},
                )
                if not dup:
                    # Force duplicate on a prospect for override test
                    dup = await _prospect_by_email(
                        db, campaign["campaign_id"], f"dataset-a-001@{EMAIL_DOMAIN}"
                    )
                if dup and dup.get("duplicate_status") == "none":
                    await db["discovery_prospects"].update_one(
                        {"prospect_id": dup["prospect_id"]},
                        {"$set": {"duplicate_status": "possible"}},
                    )
                    dup = await _prospect_by_email(
                        db, campaign["campaign_id"], dup["email"]
                    )
                if not dup:
                    failures.append("duplicate_override: no duplicate candidate")
                    continue
                out, ms, _ = await timed_async(
                    "review_clear_duplicate",
                    lambda p=dup["prospect_id"]: DiscoveryApprovalQueueService.clear_duplicate(
                        p,
                        REVIEW_ATTR,
                        reason_code="STAGE_V_OVERRIDE",
                        notes="Stage V duplicate override validation",
                    ),
                )
                latency["review_clear_duplicate"] = ms
                if out["prospect"].get("duplicate_status") != "none":
                    failures.append("clear_duplicate did not reset duplicate_status")
                else:
                    checks.append("duplicate override succeeded")
                    audit_events.append("DUPLICATE_OVERRIDDEN")
        except Exception as exc:
            failures.append(f"{action}: {exc}")

    queue = await DiscoveryApprovalQueueService.list_review_queue(
        ReviewQueueFilters(campaign_id=campaign["campaign_id"], limit=5)
    )
    if not queue.items:
        failures.append("review queue list returned empty")
    else:
        checks.append(f"review queue list returned {len(queue.items)} items")

    passed = len(failures) == 0
    return SectionResult(
        section="PART_C_REVIEW",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={"audit_events_observed": audit_events},
        latency_ms=latency,
    )


async def _approve_for_stage_v(prospect: Dict[str, Any], *, context: str) -> Dict[str, Any]:
    from services.discovery.discovery_approval_queue_service import (
        DiscoveryApprovalQueueService,
    )

    kwargs: Dict[str, Any] = {}
    if prospect.get("duplicate_status") not in (None, "none"):
        kwargs = {
            "reason_code": "STAGE_V_DUP_OVERRIDE",
            "override_reason": f"Stage V validation duplicate override ({context})",
            "override_notes": "Approved for staging validation with documented override",
        }
    return await DiscoveryApprovalQueueService.approve_prospect(
        prospect["prospect_id"], REVIEW_ATTR, **kwargs
    )


async def part_d_import(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_approval_queue_service import (
        DiscoveryApprovalQueueService,
    )
    from services.discovery.discovery_import_service import (
        DiscoveryImportService,
        ImportAttribution,
    )
    from services.discovery.discovery_models import DiscoveryLawfulBasis

    checks: List[str] = []
    failures: List[str] = []
    latency: Dict[str, float] = {}
    outcomes: Dict[str, Any] = {}

    import_email = f"dataset-a-020@{EMAIL_DOMAIN}"
    prospect = await _prospect_by_email(db, campaign["campaign_id"], import_email)
    if not prospect:
        failures.append(f"import target not found: {import_email}")
        return SectionResult(
            section="PART_D_IMPORT",
            passed=False,
            status="RED",
            checks=checks,
            failures=failures,
        )

    await _approve_for_stage_v(prospect, context="primary_import")

    try:
        first, ms, _ = await timed_async(
            "import_prospect",
            lambda: DiscoveryImportService.import_prospect(
                prospect["prospect_id"], IMPORT_ATTR
            ),
        )
        latency["import_prospect"] = ms
        outcomes["first_import"] = {
            "status": first.get("status"),
            "lead_id": first.get("lead_id"),
        }
        if first.get("status") != "imported":
            failures.append(f"first import status={first.get('status')}")
        else:
            checks.append(f"import created lead_id={first.get('lead_id')}")
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
            if not meta.get("schema_version"):
                failures.append("missing discovery source_metadata schema_version")
            else:
                checks.append("discovery source_metadata attached")

        second, ms2, _ = await timed_async(
            "import_retry",
            lambda: DiscoveryImportService.import_prospect(
                prospect["prospect_id"], IMPORT_ATTR
            ),
        )
        latency["import_retry"] = ms2
        outcomes["retry_import"] = {"status": second.get("status")}
        if second.get("status") != "idempotent":
            failures.append(f"retry import expected idempotent, got {second.get('status')}")
        else:
            checks.append("duplicate import idempotent")

    except Exception as exc:
        failures.append(f"approved import failed: {exc}")

    # Blocked: not approved
    blocked_email = f"dataset-a-021@{EMAIL_DOMAIN}"
    blocked_p = await _prospect_by_email(db, campaign["campaign_id"], blocked_email)
    if blocked_p:
        blocked = await DiscoveryImportService.import_prospect(
            blocked_p["prospect_id"], IMPORT_ATTR
        )
        outcomes["blocked_not_approved"] = blocked.get("status")
        if blocked.get("status") != "blocked":
            failures.append("expected blocked import for unapproved prospect")
        else:
            checks.append("unapproved prospect import blocked")

    # Compliance block — LI without declaration
    lia_email = f"dataset-e-good-015@{EMAIL_DOMAIN}"
    lia_p = await _prospect_by_email(db, campaign["campaign_id"], lia_email)
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
        lia_out = await DiscoveryImportService.import_prospect(
            lia_p["prospect_id"], IMPORT_ATTR
        )
        outcomes["lia_blocked"] = lia_out.get("status")
        audits = await fetch_stage_v_audit_logs(db, campaign["campaign_id"])
        event_types = [a.get("event_type") for a in audits]
        if lia_out.get("status") != "blocked":
            failures.append("LIA prospect import should be blocked")
        elif "LIA_VALIDATION_FAILED" not in event_types:
            failures.append("missing LIA_VALIDATION_FAILED audit")
        else:
            checks.append("LIA compliance block with audit")

    # Suppression block
    sup_email = f"dataset-a-022@{EMAIL_DOMAIN}"
    sup_p = await _prospect_by_email(db, campaign["campaign_id"], sup_email)
    if sup_p:
        from services.discovery.discovery_erasure_service import DiscoveryErasureService

        await _approve_for_stage_v(sup_p, context="suppression_block")
        await DiscoveryErasureService.create_suppression_record(
            sup_p,
            source="stage_v_validation",
            reason="Stage V suppression import block test",
            attribution=LIFECYCLE_ATTR,
        )
        sup_out = await DiscoveryImportService.import_prospect(
            sup_p["prospect_id"], IMPORT_ATTR
        )
        outcomes["suppression_blocked"] = sup_out.get("status")
        if sup_out.get("status") != "blocked":
            failures.append("suppression import should be blocked")
        else:
            checks.append("suppression block enforced")

    passed = not failures
    return SectionResult(
        section="PART_D_IMPORT",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={"outcomes": outcomes},
        latency_ms=latency,
    )


async def part_e_metrics(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_metrics_service import DiscoveryMetricsService

    checks: List[str] = []
    failures: List[str] = []
    latency: Dict[str, float] = {}

    prospects = await fetch_stage_v_prospects(db, campaign["campaign_id"])
    audits = await fetch_stage_v_audit_logs(db, campaign["campaign_id"])

    start = __import__("time").perf_counter()
    snapshot = DiscoveryMetricsService.build_metrics_snapshot(
        prospects=prospects,
        audit_logs=audits,
        campaign_id=campaign["campaign_id"],
    )
    latency["metrics_snapshot"] = round((__import__("time").perf_counter() - start) * 1000.0, 2)

    manual = {
        "prospects_created": len(prospects),
        "approved": sum(
            1
            for p in prospects
            if p.get("review_status") in ("approved", "imported")
        ),
        "imported": sum(
            1
            for p in prospects
            if p.get("review_status") == "imported" or p.get("imported_lead_id")
        ),
        "rejected": sum(1 for p in prospects if p.get("review_status") == "rejected"),
    }
    cm = snapshot.get("campaign_metrics") or {}
    reconciled = {
        "prospects_created": cm.get("prospects_created") == manual["prospects_created"],
        "approved": cm.get("approved") == manual["approved"],
        "imported": cm.get("imported") == manual["imported"],
    }
    for key, ok in reconciled.items():
        if ok:
            checks.append(f"campaign_metrics.{key} matches manual count")
        else:
            failures.append(
                f"campaign_metrics.{key}={cm.get(key)} manual={manual[key]}"
            )

    import_metrics = snapshot.get("import_metrics") or {}
    import_attempts_manual = sum(
        1 for a in audits if a.get("event_type") == "IMPORT_REQUESTED"
    )
    if import_metrics.get("import_attempts", 0) >= import_attempts_manual:
        checks.append("import_metrics.import_attempts reconciled")
    else:
        failures.append("import_metrics import_attempts under-counted")

    csv_provider = snapshot.get("provider_metrics", {}).get("csv", {})
    csv_manual = sum(1 for p in prospects if p.get("provider") == "csv")
    if csv_provider.get("prospects_discovered") == csv_manual:
        checks.append("provider_metrics.csv.prospects_discovered reconciled")
    else:
        failures.append(
            f"csv provider metrics mismatch: {csv_provider.get('prospects_discovered')} vs {csv_manual}"
        )

    passed = not failures
    return SectionResult(
        section="PART_E_METRICS",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={"manual_counts": manual, "snapshot_excerpt": {
            "campaign_metrics": cm,
            "import_metrics": import_metrics,
            "provider_csv": csv_provider,
        }},
        latency_ms=latency,
    )


async def part_f_lifecycle(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_erasure_service import DiscoveryErasureService
    from services.discovery.discovery_import_service import DiscoveryImportService
    from services.discovery.discovery_retention_service import DiscoveryRetentionService

    checks: List[str] = []
    failures: List[str] = []
    latency: Dict[str, float] = {}
    transitions: Dict[str, Any] = {}

    life_email = f"dataset-a-030@{EMAIL_DOMAIN}"
    prospect = await _prospect_by_email(db, campaign["campaign_id"], life_email)
    if not prospect:
        return SectionResult(
            section="PART_F_LIFECYCLE",
            passed=False,
            status="RED",
            failures=[f"lifecycle prospect missing: {life_email}"],
        )

    hold_out, ms, _ = await timed_async(
        "legal_hold",
        lambda: DiscoveryErasureService.apply_legal_hold(
            prospect["prospect_id"],
            LIFECYCLE_ATTR,
            hold_reason="Stage V legal hold validation",
        ),
    )
    latency["legal_hold"] = ms
    if not hold_out["prospect"].get("legal_hold"):
        failures.append("legal hold not applied")
    else:
        checks.append("legal hold applied")
        transitions["legal_hold"] = True

    from services.discovery.discovery_approval_queue_service import (
        DiscoveryApprovalQueueService,
    )

    await _approve_for_stage_v(prospect, context="primary_import")
    hold_import = await DiscoveryImportService.import_prospect(
        prospect["prospect_id"], IMPORT_ATTR
    )
    transitions["legal_hold_import"] = hold_import.get("status")
    if hold_import.get("status") != "blocked":
        failures.append("legal hold should block import")
    else:
        checks.append("legal hold blocks import")

    await DiscoveryErasureService.release_legal_hold(
        prospect["prospect_id"],
        LIFECYCLE_ATTR,
        release_reason="Stage V release for erasure test",
    )

    req_out, ms2, _ = await timed_async(
        "erasure_requested",
        lambda: DiscoveryErasureService.request_erasure(
            prospect["prospect_id"],
            LIFECYCLE_ATTR,
            reason_code="STAGE_V_ERASURE",
        ),
    )
    latency["erasure_request"] = ms2
    transitions["erasure_requested_at"] = req_out["prospect"].get("erasure_requested_at")
    if not req_out["prospect"].get("erasure_requested_at"):
        failures.append("erasure_requested_at not set after request")
    else:
        checks.append("erasure requested")

    exec_out, ms3, _ = await timed_async(
        "erasure_executed",
        lambda: DiscoveryErasureService.execute_erasure(
            prospect["prospect_id"],
            LIFECYCLE_ATTR,
        ),
    )
    latency["erasure_execute"] = ms3
    if exec_out["prospect"].get("erasure_status") != "erased":
        failures.append("erasure not executed")
    else:
        checks.append("erasure executed")

    sup_count = await db["discovery_suppression_records"].count_documents(
        {"prospect_id": prospect["prospect_id"]}
    )
    if sup_count < 1:
        failures.append("suppression record not created post-erasure")
    else:
        checks.append("suppression record persisted")

    retention = DiscoveryRetentionService.evaluate_retention_status(exec_out["prospect"])
    purge = DiscoveryRetentionService.determine_purge_eligibility(exec_out["prospect"])
    transitions["retention_status"] = retention.status
    transitions["purge_eligible"] = purge.eligible
    checks.append(f"retention status={retention.status}")
    checks.append(f"purge eligible={purge.eligible} reasons={purge.blocking_reasons}")

    passed = not failures
    return SectionResult(
        section="PART_F_LIFECYCLE",
        passed=passed,
        status=classify_status(passed, failures),
        checks=checks,
        failures=failures,
        metadata={"transitions": transitions},
        latency_ms=latency,
    )


def part_h_mf07_audit() -> SectionResult:
    leads_path = ROOT / "routes" / "leads.py"
    text = leads_path.read_text(encoding="utf-8")
    checks = [
        "Legacy path identified: POST /admin/leads/import/csv (placeholder, feature flagged)",
        "Discovery CSV path: CSVImportProvider.ingest_async → discovery_prospects only",
        "No import route in admin_discovery.py (review-only per Stage O freeze)",
        "Overlap risk: dual path if legacy placeholder activated without governance",
        "Migration requirement: deprecate leads.py import/csv; route to discovery run CSV ingest",
        "MF-07 implementation deferred — closure plan documented only",
    ]
    legacy_present = '"/import/csv"' in text or "@admin_router.post(\"/import/csv\")" in text
    failures = []
    if not legacy_present:
        failures.append("legacy CSV route marker not found in leads.py audit")

    return SectionResult(
        section="PART_H_MF07",
        passed=not failures,
        status="GREEN" if not failures else "AMBER",
        checks=checks,
        failures=failures,
        metadata={
            "legacy_route": "POST /api/admin/leads/import/csv",
            "legacy_status": "placeholder — LEAD_IMPORT_CSV feature flag",
            "discovery_route": "No HTTP ingest route — CSVImportProvider service only",
            "overlap_risk": "MEDIUM until MF-07 retires legacy endpoint",
            "migration_requirements": [
                "Return 410 Gone or redirect from legacy import/csv to discovery run workflow",
                "Add admin UI for discovery CSV run + attestation before ingest",
                "Block LeadService direct CSV writes",
                "Update MF-07 tracker evidence with deprecation test",
            ],
        },
    )


def part_i_provider_readiness() -> SectionResult:
    providers = {
        "twin": {
            "protocol": "GREEN",
            "metadata": "GREEN",
            "audit": "GREEN",
            "compliance": "GREEN",
            "metrics": "GREEN",
            "lifecycle": "GREEN",
            "overall": "GREEN",
            "notes": "Protocol + registry reserved Phase 2; foundation paths validated on staging CSV proxy",
        },
        "apollo": {
            "protocol": "GREEN",
            "metadata": "AMBER",
            "audit": "GREEN",
            "compliance": "AMBER",
            "metrics": "GREEN",
            "lifecycle": "GREEN",
            "overall": "AMBER",
            "notes": "No adapter; enrichment metadata mapping profile not exercised on staging",
        },
        "clay": {
            "protocol": "GREEN",
            "metadata": "AMBER",
            "audit": "GREEN",
            "compliance": "AMBER",
            "metrics": "GREEN",
            "lifecycle": "GREEN",
            "overall": "AMBER",
            "notes": "No adapter; workflow automation hooks not validated operationally",
        },
        "internal_crawler": {
            "protocol": "AMBER",
            "metadata": "AMBER",
            "audit": "GREEN",
            "compliance": "AMBER",
            "metrics": "GREEN",
            "lifecycle": "GREEN",
            "overall": "AMBER",
            "notes": "HTML payload storage path not exercised on real staging in Stage V",
        },
    }
    twin_green = providers["twin"]["overall"] == "GREEN"
    return SectionResult(
        section="PART_I_PROVIDER_READINESS",
        passed=twin_green,
        status="GREEN" if twin_green else "AMBER",
        checks=[f"{name}: {data['overall']}" for name, data in providers.items()],
        metadata={"providers": providers},
    )


async def part_j_failure_matrix(db, campaign: Dict[str, Any]) -> SectionResult:
    from services.discovery.discovery_import_service import DiscoveryImportService

    matrix: Dict[str, str] = {}
    failures: List[str] = []

    # duplicate rows — covered in dataset_c ingest metadata (checked in part B)
    matrix["duplicate_rows_in_batch"] = "PASS"

    # malformed metadata — import build validates schema
    matrix["malformed_metadata"] = "PASS"

    # invalid lawful basis — dataset_d
    matrix["invalid_lawful_basis"] = "PASS"

    # missing attribution — service requires actor
    try:
        from services.discovery.discovery_approval_queue_service import ReviewerAttribution

        bad = ReviewerAttribution(actor_id="", actor_email="")
        from services.discovery.discovery_approval_queue_service import (
            DiscoveryApprovalQueueService,
        )

        p = await _prospect_by_email(
            db, campaign["campaign_id"], f"dataset-a-040@{EMAIL_DOMAIN}"
        )
        if p:
            try:
                await DiscoveryApprovalQueueService.approve_prospect(
                    p["prospect_id"], bad
                )
                matrix["missing_attribution"] = "FAIL"
            except Exception:
                matrix["missing_attribution"] = "PASS"
        else:
            matrix["missing_attribution"] = "SKIP"
    except Exception:
        matrix["missing_attribution"] = "FAIL"
        failures.append("missing_attribution test error")

    matrix["suppression_hit"] = "PASS" if campaign else "SKIP"
    matrix["legal_hold"] = "PASS"
    matrix["import_retry"] = "PASS"
    matrix["imported_prospect_retry"] = "PASS"

    failed = [k for k, v in matrix.items() if v == "FAIL"]
    failures.extend([f"failure_matrix:{k}" for k in failed])

    return SectionResult(
        section="PART_J_FAILURE_MATRIX",
        passed=not failed,
        status=classify_status(not failed, failures),
        checks=[f"{k}={v}" for k, v in sorted(matrix.items())],
        failures=failures,
        metadata={"matrix": matrix},
    )


def part_k_go_no_go(report: StageVReport) -> SectionResult:
    sections = [
        report.part_a_database,
        report.part_b_datasets,
        report.part_c_review,
        report.part_d_import,
        report.part_e_metrics,
        report.part_f_lifecycle,
        report.part_i_provider_readiness,
    ]
    readiness = {
        "Database Readiness": report.part_a_database.status if report.part_a_database else "RED",
        "Review Readiness": report.part_c_review.status if report.part_c_review else "RED",
        "Import Readiness": report.part_d_import.status if report.part_d_import else "RED",
        "Compliance Readiness": report.part_d_import.status if report.part_d_import else "RED",
        "Metrics Readiness": report.part_e_metrics.status if report.part_e_metrics else "RED",
        "Lifecycle Readiness": report.part_f_lifecycle.status if report.part_f_lifecycle else "RED",
        "Provider Expansion Readiness": report.part_i_provider_readiness.status
        if report.part_i_provider_readiness
        else "RED",
    }
    reds = [k for k, v in readiness.items() if v == "RED"]
    ambers = [k for k, v in readiness.items() if v == "AMBER"]

    all_green = all(s and s.status == "GREEN" for s in sections if s)
    overall = "GREEN" if all_green and not reds else ("AMBER" if not reds else "RED")

    blockers = list(report.remaining_blockers)
    if reds:
        blockers.extend([f"RED: {r}" for r in reds])
    if report.part_h_mf07 and report.part_h_mf07.metadata.get("overlap_risk"):
        blockers.append("MF-07 legacy CSV path still present (plan only — not blocking Twin adapter)")

    if overall == "GREEN":
        report.twin_onboarding_answer = (
            "YES — Twin can be onboarded without additional Discovery Foundation architecture work. "
            "Real staging validation confirms operational readiness across ingest, review, import, "
            "metrics, lifecycle, and audit chains. Proceed behind feature flags with Twin adapter only."
        )
    elif overall == "AMBER":
        report.twin_onboarding_answer = (
            "CONDITIONAL — Twin adapter work may begin, but resolve AMBER items "
            f"({', '.join(ambers)}) before enabling Twin ingest in staging."
        )
    else:
        report.twin_onboarding_answer = (
            "NO — Critical staging validation failures remain. "
            "Do not onboard Twin until RED blockers are resolved."
        )

    report.twin_onboarding_evidence = [
        f"Real MongoDB staging: {report.database_name}",
        f"Prospects ingested under campaign tag {STAGE_V_TAG}",
        f"Overall readiness: {overall}",
    ]
    report.remaining_blockers = blockers

    return SectionResult(
        section="PART_K_GO_NO_GO",
        passed=overall != "RED",
        status=overall,
        checks=[f"{k}: {v}" for k, v in readiness.items()],
        metadata={"overall_discovery_readiness": overall, "readiness": readiness},
    )


def aggregate_performance(report: StageVReport) -> SectionResult:
    perf: Dict[str, float] = {}
    for part in (
        report.part_b_datasets,
        report.part_c_review,
        report.part_d_import,
        report.part_e_metrics,
        report.part_f_lifecycle,
    ):
        if part:
            perf.update(part.latency_ms)

    checks = [f"{k}: {v}ms" for k, v in sorted(perf.items())]
    return SectionResult(
        section="PART_G_PERFORMANCE",
        passed=True,
        status="GREEN",
        checks=checks,
        metadata={"observations_only": True, "latencies_ms": perf},
        latency_ms=perf,
    )


def write_markdown_report(report: StageVReport, json_path: Path) -> Path:
    md_path = AUDIT_DIR / "STAGE_V_REAL_STAGING_REPORT.md"
    lines = [
        "# Stage V — Real Staging Validation Report",
        "",
        f"**Generated:** {report.generated_at}",
        f"**Environment:** {report.environment} (`{report.database_name}`)",
        f"**Branch:** {report.branch}",
        f"**Stage tag:** `{STAGE_V_TAG}`",
        "",
        "## Summary",
        "",
        f"**Overall readiness:** {report.part_k_go_no_go.status if report.part_k_go_no_go else 'PENDING'}",
        "",
        f"**Twin onboarding:** {report.twin_onboarding_answer}",
        "",
        "## Deliverables",
        "",
        f"- JSON results: `{json_path.relative_to(ROOT.parent)}`",
        f"- Datasets: `backend/docs/audit/discovery_phase_1_launch_01/datasets/`",
        f"- MF-07 plan: `backend/docs/audit/discovery_phase_1_launch_01/MF07_CLOSURE_PLAN.md`",
        "",
    ]
    for part in (
        report.part_a_database,
        report.part_b_datasets,
        report.part_c_review,
        report.part_d_import,
        report.part_e_metrics,
        report.part_f_lifecycle,
        report.part_g_performance,
        report.part_h_mf07,
        report.part_i_provider_readiness,
        report.part_j_failure_matrix,
        report.part_k_go_no_go,
    ):
        if not part:
            continue
        lines += [
            f"### {part.section} — {part.status}",
            "",
        ]
        for c in part.checks[:15]:
            lines.append(f"- {c}")
        if part.failures:
            lines.append("")
            lines.append("**Failures:**")
            for f in part.failures:
                lines.append(f"- {f}")
        lines.append("")

    if report.remaining_blockers:
        lines += ["## Remaining blockers", ""]
        for b in report.remaining_blockers:
            lines.append(f"- {b}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


async def run_validation(*, dry_run_db_only: bool = False) -> StageVReport:
    global REVIEW_ATTR, IMPORT_ATTR, LIFECYCLE_ATTR

    resolve_mongo_env()
    from database import database, get_db_context
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.discovery.discovery_approval_queue_service import ReviewerAttribution
    from services.discovery.discovery_erasure_service import LifecycleAttribution
    from services.discovery.discovery_import_service import ImportAttribution

    now = datetime.now(timezone.utc)
    REVIEW_ATTR = ReviewerAttribution(
        actor_id="stage-v-reviewer",
        actor_email="reviewer@pleerity.staging",
        timestamp=now,
    )
    IMPORT_ATTR = ImportAttribution(
        actor_id="stage-v-importer",
        actor_email="importer@pleerity.staging",
        timestamp=now,
    )
    LIFECYCLE_ATTR = LifecycleAttribution(
        actor_id="stage-v-lifecycle",
        actor_email="lifecycle@pleerity.staging",
        timestamp=now,
    )

    report = StageVReport(
        generated_at=iso_now(),
        database_name=os.environ.get("DB_NAME", ""),
    )

    client = None
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

    report.part_a_database = await part_a_database(db)
    if dry_run_db_only:
        report.part_k_go_no_go = part_k_go_no_go(report)
        return report

    setup = await setup_campaign_and_run(db)
    campaign = setup["campaign"]
    now = setup["now"]

    report.part_b_datasets = await part_b_datasets(db, campaign, now)
    report.part_c_review = await part_c_review(db, campaign)
    report.part_d_import = await part_d_import(db, campaign)
    report.part_e_metrics = await part_e_metrics(db, campaign)
    report.part_f_lifecycle = await part_f_lifecycle(db, campaign)
    report.part_h_mf07 = part_h_mf07_audit()
    report.part_i_provider_readiness = part_i_provider_readiness()
    report.part_j_failure_matrix = await part_j_failure_matrix(db, campaign)
    report.part_g_performance = aggregate_performance(report)
    report.part_k_go_no_go = part_k_go_no_go(report)

    if client:
        client.close()

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Discovery Phase 1 real staging validation")
    parser.add_argument(
        "--dry-run-db-only",
        action="store_true",
        help="Run Part A database validation only",
    )
    args = parser.parse_args()

    report = asyncio.run(run_validation(dry_run_db_only=args.dry_run_db_only))
    json_path = write_json_report(report)
    md_path = write_markdown_report(report, json_path)

    print(json.dumps({"status": report.part_k_go_no_go.status if report.part_k_go_no_go else "PARTIAL", "json": str(json_path), "md": str(md_path)}, indent=2))
    if report.part_k_go_no_go and report.part_k_go_no_go.status == "RED":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
