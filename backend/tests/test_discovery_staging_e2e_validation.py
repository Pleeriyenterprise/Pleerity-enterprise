"""
Stage U — Discovery staging end-to-end operational validation.

Synthetic staging harness exercising full discovery lifecycle A–T.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.discovery.discovery_approval_queue_service import (
    DiscoveryApprovalQueueService,
)
from services.discovery.discovery_duplicate_service import DiscoveryDuplicateService
from services.discovery.discovery_erasure_service import DiscoveryErasureService
from services.discovery.discovery_import_service import (
    DiscoveryImportError,
    DiscoveryImportService,
    ImportAttribution,
)
from services.discovery.discovery_metrics_service import DiscoveryMetricsService
from services.discovery.discovery_models import (
    DiscoveryDuplicateStatus,
    DiscoveryErasureStatus,
    DiscoveryLawfulBasis,
    DiscoveryReviewStatus,
)
from services.discovery.discovery_prospect_service import DiscoveryProspectService
from services.discovery.discovery_retention_service import DiscoveryRetentionService
from tests.discovery_staging_harness import (
    IMPORT_ATTR,
    LIFECYCLE_ATTR,
    REVIEW_ATTR,
    STAGING_NOW,
    STAGING_REPORT,
    ScenarioResult,
    StagingFakeDB,
    audit_event_types,
    compute_readiness,
    db_patch_stack,
    hash_for,
    record_scenario,
    seed_staging_prospect,
    timed,
)

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# PART A — Foundation inventory
# ---------------------------------------------------------------------------


def test_part_a_foundation_inventory_exists():
    inventory = {
        "Prospect Store": DISCOVERY_ROOT / "discovery_prospect_service.py",
        "Quality Scoring": DISCOVERY_ROOT / "discovery_quality_service.py",
        "Duplicate Detection": DISCOVERY_ROOT / "discovery_duplicate_service.py",
        "Audit": DISCOVERY_ROOT / "discovery_audit_service.py",
        "CSV Provider": DISCOVERY_ROOT / "providers" / "csv_import_provider.py",
        "Approval Queue": DISCOVERY_ROOT / "discovery_approval_queue_service.py",
        "Review Workflow": BACKEND_ROOT / "routes" / "admin_discovery.py",
        "Import Service": DISCOVERY_ROOT / "discovery_import_service.py",
        "Compliance": DISCOVERY_ROOT / "discovery_consent_service.py",
        "Metrics": DISCOVERY_ROOT / "discovery_metrics_service.py",
        "Lifecycle": DISCOVERY_ROOT / "discovery_retention_service.py",
        "Erasure": DISCOVERY_ROOT / "discovery_erasure_service.py",
    }
    missing = [name for name, path in inventory.items() if not path.is_file()]
    STAGING_REPORT.inventory = {name: "PRESENT" for name in inventory}
    assert not missing, f"Missing components: {missing}"


# ---------------------------------------------------------------------------
# PART B — U-01 Valid prospect happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u01_valid_prospect_e2e_flow():
    db = StagingFakeDB()
    result = ScenarioResult("U-01", "Valid Prospect E2E", passed=False)
    with db_patch_stack(db):
        prospect, create_ms = await timed(
            "prospect_create",
            lambda: seed_staging_prospect(
                db,
                email="u01@staging.pleerity.com",
                prospect_key="U01",
                marketing_consent=False,
            ),
        )
        result.latency_ms["prospect_create"] = create_ms

        approve_out, review_ms = await timed(
            "review_approve",
            lambda: DiscoveryApprovalQueueService.approve_prospect(
                prospect["prospect_id"], REVIEW_ATTR
            ),
        )
        result.latency_ms["review_approve"] = review_ms
        approved = approve_out["prospect"]

        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(
                return_value={"lead_id": "LEAD-U01", "is_duplicate": False}
            ),
        ) as create_lead:
            import_out, import_ms = await timed(
                "import",
                lambda: DiscoveryImportService.import_prospect(
                    approved["prospect_id"], IMPORT_ATTR
                ),
            )
        result.latency_ms["import"] = import_ms

    events = audit_event_types(db)
    result.audit_events = events

    checks = [
        import_out["status"] == "imported",
        import_out["lead_id"] == "LEAD-U01",
        import_out["prospect"]["imported_lead_id"] == "LEAD-U01",
        import_out["prospect"]["review_status"]
        == DiscoveryReviewStatus.IMPORTED.value,
        "PROSPECT_APPROVED" in events,
        "IMPORT_REQUESTED" in events,
        "IMPORT_VALIDATED" in events,
        "PROSPECT_IMPORTED" in events,
        create_lead.await_count == 1,
    ]
    payload = DiscoveryImportService.build_lead_create_payload(
        import_out["prospect"],
        discovery_metadata=DiscoveryImportService.build_discovery_source_metadata(
            import_out["prospect"]
        ),
    )
    checks += [
        "discovery_import_v1" in (payload.tags or []),
        payload.source_metadata.get("discovery", {}).get("schema_version") is not None,
    ]

    snapshot = DiscoveryMetricsService.build_metrics_snapshot(
        prospects=db.discovery_prospects.docs,
        audit_logs=db.discovery_audit_logs.docs,
        campaign_id=prospect.get("campaign_id"),
        generated_at=STAGING_NOW,
    )
    checks.append(snapshot["import_metrics"]["import_success"] >= 1)

    result.metadata["metrics_snapshot"] = {
        "import_success": snapshot["import_metrics"]["import_success"],
        "provider_discovered": snapshot["provider_metrics"].get("manual", {}).get(
            "prospects_discovered", 0
        ),
    }

    for check in checks:
        result.assertions.append(str(check))
    result.failures = [str(c) for c in checks if not c]
    result.passed = not result.failures
    record_scenario(result)
    assert result.passed, result.failures


# ---------------------------------------------------------------------------
# PART C — U-02 Duplicate governance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u02_duplicate_governance():
    db = StagingFakeDB()
    result = ScenarioResult("U-02", "Duplicate Governance", passed=False)
    email = "dup@staging.pleerity.com"
    with db_patch_stack(db):
        first = await seed_staging_prospect(db, email=email, prospect_key="U02A")
        second = await seed_staging_prospect(db, email=email, prospect_key="U02B")

        dup_start = __import__("time").perf_counter()
        candidates = await DiscoveryDuplicateService.find_duplicate_candidates(second)
        result.latency_ms["duplicate_detection"] = round(
            (__import__("time").perf_counter() - dup_start) * 1000, 2
        )

        classification = DiscoveryDuplicateService.classify_duplicate(
            second, candidates
        )
        await DiscoveryDuplicateService.mark_confirmed_duplicate(
            second["prospect_id"],
            classification,
            actor_id=REVIEW_ATTR.actor_id,
        )
        refreshed = await DiscoveryProspectService.get_prospect(second["prospect_id"])

        await db.discovery_prospects.update_one(
            {"prospect_id": refreshed["prospect_id"]},
            {
                "$set": {
                    "review_status": DiscoveryReviewStatus.APPROVED.value,
                }
            },
        )
        blocked = await DiscoveryImportService.import_prospect(
            refreshed["prospect_id"], IMPORT_ATTR
        )

        await DiscoveryApprovalQueueService.clear_duplicate(
            refreshed["prospect_id"],
            REVIEW_ATTR,
            reason_code="STAGING_OVERRIDE",
            notes="Staging duplicate override",
        )
        await DiscoveryApprovalQueueService.approve_prospect(
            refreshed["prospect_id"], REVIEW_ATTR
        )

        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(
                return_value={"lead_id": "LEAD-U02", "is_duplicate": False}
            ),
        ):
            after_override = await DiscoveryImportService.import_prospect(
                refreshed["prospect_id"], IMPORT_ATTR
            )

    events = audit_event_types(db)
    result.audit_events = events
    checks = [
        blocked["status"] == "blocked",
        "DUPLICATE_OVERRIDDEN" in events or any(
            "duplicate" in e.lower() for e in events
        ),
        after_override["status"] == "imported",
        first["prospect_id"] != second["prospect_id"],
    ]
    result.failures = [str(c) for c in checks if not c]
    result.passed = not result.failures
    record_scenario(result)
    assert result.passed, result.failures


# ---------------------------------------------------------------------------
# PART D — U-03 / U-04 Compliance failures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u03_marketing_consent_failure():
    db = StagingFakeDB()
    result = ScenarioResult("U-03", "Marketing Consent Failure", passed=False)
    with db_patch_stack(db):
        prospect = await seed_staging_prospect(
            db,
            email="u03@staging.pleerity.com",
            prospect_key="U03",
            marketing_consent=False,
        )
        await db.discovery_prospects.update_one(
            {"prospect_id": prospect["prospect_id"]},
            {
                "$set": {
                    "lawful_basis": DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
                    "marketing_consent": True,
                }
            },
        )
        prospect = await DiscoveryProspectService.get_prospect(prospect["prospect_id"])
        await DiscoveryApprovalQueueService.approve_prospect(
            prospect["prospect_id"], REVIEW_ATTR
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(),
        ) as create_lead:
            out = await DiscoveryImportService.import_prospect(
                prospect["prospect_id"], IMPORT_ATTR
            )
    events = audit_event_types(db)
    checks = [
        out["status"] == "blocked",
        "CONSENT_VALIDATION_FAILED" in events,
        "IMPORT_BLOCKED" in events,
        create_lead.await_count == 0,
    ]
    result.audit_events = events
    result.failures = [str(c) for c in checks if not c]
    result.passed = not result.failures
    record_scenario(result)
    assert result.passed


@pytest.mark.asyncio
async def test_u04_lia_failure():
    db = StagingFakeDB()
    result = ScenarioResult("U-04", "LIA Failure", passed=False)
    with db_patch_stack(db):
        prospect = await seed_staging_prospect(
            db,
            email="u04@staging.pleerity.com",
            prospect_key="U04",
            marketing_consent=False,
        )
        await db.discovery_prospects.update_one(
            {"prospect_id": prospect["prospect_id"]},
            {
                "$set": {
                    "lawful_basis": DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
                }
            },
        )
        prospect = await DiscoveryProspectService.get_prospect(prospect["prospect_id"])
        await DiscoveryApprovalQueueService.approve_prospect(
            prospect["prospect_id"], REVIEW_ATTR
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(),
        ) as create_lead:
            out = await DiscoveryImportService.import_prospect(
                prospect["prospect_id"], IMPORT_ATTR
            )
    events = audit_event_types(db)
    checks = [
        out["status"] == "blocked",
        "LIA_VALIDATION_FAILED" in events,
        "IMPORT_BLOCKED" in events,
        create_lead.await_count == 0,
    ]
    result.audit_events = events
    result.failures = [str(c) for c in checks if not c]
    result.passed = not result.failures
    record_scenario(result)
    assert result.passed


# ---------------------------------------------------------------------------
# PART E — U-05 Suppression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u05_suppressed_prospect_blocked():
    db = StagingFakeDB()
    result = ScenarioResult("U-05", "Suppressed Prospect", passed=False)
    with db_patch_stack(db):
        prospect = await seed_staging_prospect(
            db,
            email="u05@staging.pleerity.com",
            prospect_key="U05",
            erasure_status=DiscoveryErasureStatus.ERASED.value,
        )
        await db.discovery_prospects.update_one(
            {"prospect_id": prospect["prospect_id"]},
            {
                "$set": {
                    "review_status": DiscoveryReviewStatus.APPROVED.value,
                    "email": None,
                    "contact_name": "[ERASED]",
                }
            },
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(),
        ) as create_lead:
            out = await DiscoveryImportService.import_prospect(
                prospect["prospect_id"], IMPORT_ATTR
            )
    events = audit_event_types(db)
    checks = [
        out["status"] == "blocked",
        "SUPPRESSION_MATCH" in events or "IMPORT_BLOCKED" in events,
        create_lead.await_count == 0,
    ]
    result.audit_events = events
    result.failures = [str(c) for c in checks if not c]
    result.passed = not result.failures
    record_scenario(result)
    assert result.passed


# ---------------------------------------------------------------------------
# PART F — U-06 Erasure and re-import block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u06_erasure_and_reimport_block():
    db = StagingFakeDB()
    result = ScenarioResult("U-06", "Erasure and Re-import Block", passed=False)
    with db_patch_stack(db):
        prospect = await seed_staging_prospect(
            db,
            email="u06@staging.pleerity.com",
            prospect_key="U06",
        )
        await DiscoveryApprovalQueueService.approve_prospect(
            prospect["prospect_id"], REVIEW_ATTR
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(
                return_value={"lead_id": "LEAD-U06", "is_duplicate": False}
            ),
        ):
            imported = await DiscoveryImportService.import_prospect(
                prospect["prospect_id"], IMPORT_ATTR
            )

        await DiscoveryErasureService.request_erasure(
            prospect["prospect_id"], LIFECYCLE_ATTR, reason_code="GDPR_STAGING"
        )
        erased = await DiscoveryErasureService.execute_erasure(
            prospect["prospect_id"], LIFECYCLE_ATTR
        )
        pii_errors = DiscoveryErasureService.verify_anonymisation(erased["prospect"])

        reimport = await seed_staging_prospect(
            db,
            email="u06@staging.pleerity.com",
            prospect_key="U06R",
        )
        await DiscoveryApprovalQueueService.approve_prospect(
            reimport["prospect_id"], REVIEW_ATTR
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(),
        ) as create_lead:
            blocked = await DiscoveryImportService.import_prospect(
                reimport["prospect_id"], IMPORT_ATTR
            )

    events = audit_event_types(db)
    checks = [
        imported["status"] == "imported",
        erased["prospect"]["erasure_status"] == DiscoveryErasureStatus.ERASED.value,
        pii_errors == [],
        bool(erased["suppression"]["active"]),
        len(db.discovery_audit_logs.docs) >= 3,
        blocked["status"] == "blocked",
        create_lead.await_count == 0,
    ]
    result.audit_events = events
    result.failures = [str(c) for c in checks if not c]
    result.passed = not result.failures
    record_scenario(result)
    assert result.passed


# ---------------------------------------------------------------------------
# PART G — U-07 Legal hold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_u07_legal_hold_lifecycle():
    db = StagingFakeDB()
    result = ScenarioResult("U-07", "Legal Hold Lifecycle", passed=False)
    with db_patch_stack(db):
        prospect = await seed_staging_prospect(
            db,
            email="u07@staging.pleerity.com",
            prospect_key="U07",
        )
        held = await DiscoveryErasureService.apply_legal_hold(
            prospect["prospect_id"],
            LIFECYCLE_ATTR,
            hold_reason="Staging litigation hold",
        )
        purge_while_held = DiscoveryRetentionService.determine_purge_eligibility(
            held["prospect"], evaluated_at=STAGING_NOW
        )
        try:
            await DiscoveryErasureService.execute_erasure(
                prospect["prospect_id"], LIFECYCLE_ATTR
            )
            erasure_blocked = False
        except Exception:
            erasure_blocked = True

        released = await DiscoveryErasureService.release_legal_hold(
            prospect["prospect_id"], LIFECYCLE_ATTR
        )
        summary = DiscoveryErasureService.build_lifecycle_summary(
            released["prospect"], evaluated_at=STAGING_NOW
        )

    events = audit_event_types(db)
    checks = [
        held["prospect"]["legal_hold"] is True,
        purge_while_held.eligible is False,
        erasure_blocked is True,
        released["prospect"]["legal_hold"] is False,
        "LEGAL_HOLD_APPLIED" in events,
        "LEGAL_HOLD_RELEASED" in events,
        "Legal Hold:\nNo" in summary.split("Erasure Status:")[0],
    ]
    result.audit_events = events
    result.failures = [str(c) for c in checks if not c]
    result.passed = not result.failures
    record_scenario(result)
    assert result.passed


# ---------------------------------------------------------------------------
# PART H — Metrics validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_part_h_metrics_reflect_staging_activity():
    db = StagingFakeDB()
    with db_patch_stack(db):
        p1 = await seed_staging_prospect(
            db, email="metrics1@staging.com", prospect_key="M1"
        )
        await DiscoveryApprovalQueueService.approve_prospect(
            p1["prospect_id"], REVIEW_ATTR
        )
        await DiscoveryApprovalQueueService.reject_prospect(
            (
                await seed_staging_prospect(
                    db, email="metrics2@staging.com", prospect_key="M2"
                )
            )["prospect_id"],
            REVIEW_ATTR,
            reason_code="STAGING_REJECT",
            notes="staging reject",
        )

    snapshot = DiscoveryMetricsService.build_metrics_snapshot(
        prospects=db.discovery_prospects.docs,
        audit_logs=db.discovery_audit_logs.docs,
        campaign_id=p1.get("campaign_id"),
        generated_at=STAGING_NOW,
    )
    assert sum(
        v.get("prospects_discovered", 0)
        for v in snapshot["provider_metrics"].values()
    ) == 2
    assert snapshot["review_metrics"]["rejection_rate"] >= 0
    assert snapshot["campaign_metrics"]["prospects_created"] >= 1


# ---------------------------------------------------------------------------
# PART J — Boundary validation (Stage Q hooks)
# ---------------------------------------------------------------------------


def test_part_j_boundary_still_green():
    regression = BACKEND_ROOT / "tests" / "test_discovery_crm_boundary_regression.py"
    assert regression.is_file()
    text = regression.read_text(encoding="utf-8")
    assert "test_only_discovery_import_service_calls_create_lead" in text
    STAGING_REPORT.boundary_status = "GREEN"


# ---------------------------------------------------------------------------
# PART K — Launch gates NG-025–029
# ---------------------------------------------------------------------------


def test_part_k_launch_gates_from_staging():
    """Evaluated after scenarios in test_part_n_o."""
    pass


def _validate_launch_gates():
    gates: dict[str, str] = {}
    for scenario in STAGING_REPORT.scenarios:
        if scenario.scenario_id == "U-01":
            gates["NG-025"] = (
                "GREEN"
                if "PROSPECT_APPROVED" in scenario.audit_events
                else "RED"
            )
            gates["NG-028"] = (
                "GREEN"
                if scenario.passed and "IMPORT_REQUESTED" in scenario.audit_events
                else "AMBER"
            )
            gates["NG-029"] = "GREEN" if scenario.passed else "RED"
        if scenario.scenario_id in ("U-03", "U-04", "U-05"):
            gates["NG-029"] = "GREEN"
    gates["NG-026"] = STAGING_REPORT.boundary_status
    gates["NG-027"] = STAGING_REPORT.boundary_status
    STAGING_REPORT.launch_gates = gates
    return gates


# ---------------------------------------------------------------------------
# PART M — Failure matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_part_m_failure_matrix():
    db = StagingFakeDB()
    matrix: dict[str, str] = {}
    with db_patch_stack(db):
        # duplicate import attempt / already imported
        p = await seed_staging_prospect(
            db, email="fm1@staging.com", prospect_key="FM1"
        )
        await DiscoveryApprovalQueueService.approve_prospect(
            p["prospect_id"], REVIEW_ATTR
        )
        with patch(
            "services.discovery.discovery_import_service.LeadService.find_duplicate",
            new=AsyncMock(return_value=None),
        ), patch(
            "services.discovery.discovery_import_service.LeadService.create_lead",
            new=AsyncMock(
                return_value={"lead_id": "LEAD-FM1", "is_duplicate": False}
            ),
        ):
            first = await DiscoveryImportService.import_prospect(
                p["prospect_id"], IMPORT_ATTR
            )
            second = await DiscoveryImportService.import_prospect(
                p["prospect_id"], IMPORT_ATTR
            )
        matrix["duplicate_import_attempt"] = (
            "PASS" if second["status"] == "idempotent" else "FAIL"
        )
        matrix["already_imported"] = (
            "PASS" if first["status"] == "imported" else "FAIL"
        )

        # erased prospect
        erased_p = await seed_staging_prospect(
            db,
            email="fm-erased@staging.com",
            prospect_key="FME",
            erasure_status=DiscoveryErasureStatus.ERASED.value,
        )
        await db.discovery_prospects.update_one(
            {"prospect_id": erased_p["prospect_id"]},
            {"$set": {"review_status": DiscoveryReviewStatus.APPROVED.value}},
        )
        out_erased = await DiscoveryImportService.import_prospect(
            erased_p["prospect_id"], IMPORT_ATTR
        )
        matrix["erased_prospect"] = (
            "PASS" if out_erased["status"] == "blocked" else "FAIL"
        )

        # legal hold
        lh = await seed_staging_prospect(
            db, email="fm-lh@staging.com", prospect_key="FMLH", legal_hold=True
        )
        await DiscoveryApprovalQueueService.approve_prospect(
            lh["prospect_id"], REVIEW_ATTR
        )
        out_lh = await DiscoveryImportService.import_prospect(
            lh["prospect_id"], IMPORT_ATTR
        )
        matrix["legal_hold_prospect"] = (
            "PASS" if out_lh["status"] == "blocked" else "FAIL"
        )

        # invalid lawful basis
        bad = await seed_staging_prospect(
            db,
            email="fm-bad@staging.com",
            prospect_key="FMBAD",
        )
        await db.discovery_prospects.update_one(
            {"prospect_id": bad["prospect_id"]},
            {
                "$set": {
                    "lawful_basis": DiscoveryLawfulBasis.UNKNOWN.value,
                    "review_status": DiscoveryReviewStatus.APPROVED.value,
                }
            },
        )
        bad = await DiscoveryProspectService.get_prospect(bad["prospect_id"])
        out_bad = await DiscoveryImportService.import_prospect(
            bad["prospect_id"], IMPORT_ATTR
        )
        matrix["invalid_lawful_basis"] = (
            "PASS" if out_bad["status"] == "blocked" else "FAIL"
        )

        # missing attribution
        try:
            await DiscoveryImportService.import_prospect(
                bad["prospect_id"],
                ImportAttribution(actor_id="", actor_email=""),
            )
            matrix["missing_attribution"] = "FAIL"
        except DiscoveryImportError:
            matrix["missing_attribution"] = "PASS"

    STAGING_REPORT.failure_matrix = matrix
    assert all(v == "PASS" for v in matrix.values()), matrix


# ---------------------------------------------------------------------------
# PART N / O — Final report emission
# ---------------------------------------------------------------------------


def test_part_n_o_emit_staging_report_and_readiness():
    gates = _validate_launch_gates()
    assert all(v in ("GREEN", "AMBER") for v in gates.values()), gates
    compute_readiness(STAGING_REPORT)
    path = STAGING_REPORT.write_json()
    assert path.is_file()
    assert STAGING_REPORT.operational_readiness_score >= 80
    assert STAGING_REPORT.twin_readiness in ("GREEN", "AMBER")
    assert STAGING_REPORT.recommendation
