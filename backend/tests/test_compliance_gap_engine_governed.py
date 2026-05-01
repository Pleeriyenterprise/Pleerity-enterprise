"""Governed compliance gap engine: authority-first inference, CTAs, sync, dedupe hooks."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import AuditAction
from services.compliance_gap_engine import (
    ComplianceGap,
    GAP_EVIDENCE_UPLOADED_UNCONFIRMED,
    GAP_EXPIRED,
    GAP_EXPIRING_SOON,
    GAP_MISSING_EVIDENCE,
    GAP_MISMATCHED_EVIDENCE,
    GAP_TENANT_DELIVERY_PROOF_MISSING,
    gaps_to_priority_actions,
    infer_compliance_gaps_for_requirement,
    stable_gap_key,
)
from services.compliance_gap_operational_bridge import apply_gap_operational_bridge
from services.compliance_gap_sync import aggregate_gap_counts_for_client, sync_compliance_gaps_for_requirement
from services.requirement_evidence_authority import (
    AUTHORITY_VERSION,
    EA_MISSING,
    EA_MISMATCH_FLAGGED,
    EA_UPLOADED_UNCONFIRMED,
    EA_VERIFIED_CURRENT,
    EA_VERIFIED_EXPIRED,
)


def _synced_req(**kwargs):
    base = {
        "client_id": "c-gap",
        "property_id": "p-gap",
        "requirement_id": "r-gap",
        "requirement_code": "EPC",
        "requirement_type": "EPC",
        "title": "EPC",
        "evidence_authority_synced_at": "2026-01-10T12:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": EA_MISSING},
        "updated_at": "2026-01-10T12:00:00+00:00",
    }
    base.update(kwargs)
    if "evidence_authority" in kwargs and isinstance(kwargs["evidence_authority"], dict):
        ea = dict(base["evidence_authority"])
        ea.update(kwargs["evidence_authority"])
        base["evidence_authority"] = ea
    return base


def test_stable_gap_key_is_stable():
    k = stable_gap_key("c1", "p1", "r1", "MISSING_EVIDENCE")
    assert k == "c1:p1:r1:MISSING_EVIDENCE"
    assert stable_gap_key("c1", "p1", "r1", "EXPIRED") != k


def test_infer_missing_evidence_when_authority_missing():
    r = _synced_req(evidence_authority={"version": AUTHORITY_VERSION, "state": EA_MISSING})
    gaps = infer_compliance_gaps_for_requirement(r, property_doc=None)
    kinds = [g.gap_kind for g in gaps]
    assert GAP_MISSING_EVIDENCE in kinds


def test_infer_expired_gap_verified_expired():
    past = "2025-06-01T00:00:00+00:00"
    now = datetime(2026, 1, 15, tzinfo=timezone.utc)
    r = _synced_req(
        evidence_authority={
            "version": AUTHORITY_VERSION,
            "state": EA_VERIFIED_EXPIRED,
            "effective_expiry_date": past,
        }
    )
    gaps = infer_compliance_gaps_for_requirement(r, property_doc=None, now=now)
    assert any(g.gap_kind == GAP_EXPIRED for g in gaps)


def test_infer_expiring_soon_within_window():
    now = datetime(2026, 1, 20, tzinfo=timezone.utc)
    eff = "2026-02-05T00:00:00+00:00"
    r = _synced_req(
        evidence_authority={
            "version": AUTHORITY_VERSION,
            "state": EA_VERIFIED_CURRENT,
            "effective_expiry_date": eff,
        }
    )
    with patch("services.compliance_gap_engine.resolve_expiring_soon_days_for_requirement", return_value=60):
        gaps = infer_compliance_gaps_for_requirement(r, property_doc=None, now=now)
    assert any(g.gap_kind == GAP_EXPIRING_SOON for g in gaps)


def test_infer_mismatch_gap():
    r = _synced_req(
        evidence_authority={
            "version": AUTHORITY_VERSION,
            "state": EA_MISMATCH_FLAGGED,
            "mismatch_reason": "Document type does not match obligation",
        }
    )
    gaps = infer_compliance_gaps_for_requirement(r, property_doc=None)
    assert any(g.gap_kind == GAP_MISMATCHED_EVIDENCE for g in gaps)


def test_infer_uploaded_unconfirmed():
    r = _synced_req(
        evidence_authority={"version": AUTHORITY_VERSION, "state": EA_UPLOADED_UNCONFIRMED},
    )
    gaps = infer_compliance_gaps_for_requirement(r, property_doc=None)
    assert any(g.gap_kind == GAP_EVIDENCE_UPLOADED_UNCONFIRMED for g in gaps)


def test_infer_tenant_delivery_proof_missing_when_policy_requires():
    eff = "2027-06-01T00:00:00+00:00"
    r = _synced_req(
        tenant_delivery_required=True,
        tenant_delivery_proof_status="",
        evidence_authority={
            "version": AUTHORITY_VERSION,
            "state": EA_VERIFIED_CURRENT,
            "effective_expiry_date": eff,
        },
    )
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    with patch("services.compliance_gap_engine.resolve_expiring_soon_days_for_requirement", return_value=60):
        gaps = infer_compliance_gaps_for_requirement(r, property_doc=None, now=now)
    kinds = [g.gap_kind for g in gaps]
    assert GAP_TENANT_DELIVERY_PROOF_MISSING in kinds


def test_no_tenant_delivery_gap_when_proof_recorded():
    eff = "2027-06-01T00:00:00+00:00"
    r = _synced_req(
        tenant_delivery_required=True,
        tenant_delivery_proof_status="DELIVERED",
        evidence_authority={
            "version": AUTHORITY_VERSION,
            "state": EA_VERIFIED_CURRENT,
            "effective_expiry_date": eff,
        },
    )
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    with patch("services.compliance_gap_engine.resolve_expiring_soon_days_for_requirement", return_value=60):
        gaps = infer_compliance_gaps_for_requirement(r, property_doc=None, now=now)
    kinds = [g.gap_kind for g in gaps]
    assert GAP_TENANT_DELIVERY_PROOF_MISSING not in kinds


def test_no_gap_when_verified_current_and_not_expiring():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    eff = "2027-06-01T00:00:00+00:00"
    r = _synced_req(
        evidence_authority={
            "version": AUTHORITY_VERSION,
            "state": EA_VERIFIED_CURRENT,
            "effective_expiry_date": eff,
        }
    )
    with patch("services.compliance_gap_engine.resolve_expiring_soon_days_for_requirement", return_value=60):
        gaps = infer_compliance_gaps_for_requirement(r, property_doc=None, now=now)
    assert gaps == []


def _minimal_gap_wrong_url() -> ComplianceGap:
    return ComplianceGap(
        gap_kind=GAP_MISSING_EVIDENCE,
        severity="HIGH",
        title="Missing evidence",
        description="d",
        why_matters="w",
        recommended_action_detail="detail",
        priority_score=40,
        action_type="missing_document",
        recommended_url="/wrong-from-gap-template",
        recommended_action_label="Wrong gap label",
    )


def test_gaps_to_priority_actions_suppresses_gap_url_when_canonical_primary_has_no_route():
    """Stream D B1: navigable primary route absent — do not keep raw gap recommended_url."""
    g = _minimal_gap_wrong_url()
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "gas_safety",
        "jurisdiction": "England",
        "take_action": {
            "primary": {
                "label": "Upload Gas Safety",
                "kind": "navigate",
                "handler": "navigate",
            },
            "contract": "requirement_take_action_v1",
        },
    }
    rows = gaps_to_priority_actions([g], req)
    assert len(rows) == 1
    assert rows[0]["recommended_url"] == ""
    assert rows[0]["diagnostic_gap_recommended_url"] == "/wrong-from-gap-template"
    assert rows[0]["recommended_action_label"] == "Upload Gas Safety"


def test_gaps_to_priority_actions_guided_primary_keeps_empty_url_not_gap():
    g = _minimal_gap_wrong_url()
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "smoke_heat_alarms",
        "jurisdiction": "England",
        "take_action": {
            "primary": {
                "label": "Resolve requirement",
                "route": None,
                "kind": "guided_evidence_resolution",
                "handler": "guided_evidence",
                "property_id": "p1",
                "requirement_id": "r1",
            },
            "contract": "requirement_take_action_v1",
        },
    }
    rows = gaps_to_priority_actions([g], req)
    assert rows[0]["recommended_url"] == ""
    assert rows[0]["diagnostic_gap_recommended_url"] == "/wrong-from-gap-template"


def test_gaps_to_priority_actions_direct_evidence_primary_keeps_empty_url_not_gap():
    g = _minimal_gap_wrong_url()
    req = {
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "requirement_code": "declaration_only",
        "jurisdiction": "England",
        "take_action": {
            "primary": {
                "label": "Submit declaration",
                "kind": "direct_evidence_action",
                "handler": "direct_evidence",
                "property_id": "p1",
                "requirement_id": "r1",
            },
            "contract": "requirement_take_action_v1",
        },
    }
    rows = gaps_to_priority_actions([g], req)
    assert rows[0]["recommended_url"] == ""
    assert rows[0]["diagnostic_gap_recommended_url"] == "/wrong-from-gap-template"


def test_gaps_to_priority_action_types():
    r = _synced_req()
    gaps = infer_compliance_gaps_for_requirement(
        _synced_req(
            evidence_authority={
                "version": AUTHORITY_VERSION,
                "state": EA_VERIFIED_EXPIRED,
                "effective_expiry_date": "2020-01-01T00:00:00+00:00",
            }
        ),
        property_doc=None,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    actions = gaps_to_priority_actions(gaps, r)
    assert actions
    exp = next(a for a in actions if a.get("gap_kind") == GAP_EXPIRED)
    assert exp["action_type"] == "overdue_compliance"
    with patch("services.compliance_gap_engine.resolve_expiring_soon_days_for_requirement", return_value=30):
        soon_gaps = infer_compliance_gaps_for_requirement(
            _synced_req(
                evidence_authority={
                    "version": AUTHORITY_VERSION,
                    "state": EA_VERIFIED_CURRENT,
                    "effective_expiry_date": "2026-01-15T00:00:00+00:00",
                }
            ),
            property_doc=None,
            now=datetime(2026, 1, 10, tzinfo=timezone.utc),
        )
    act2 = gaps_to_priority_actions(soon_gaps, r)
    ex2 = next(a for a in act2 if a.get("gap_kind") == GAP_EXPIRING_SOON)
    assert ex2["action_type"] == "certificate_expiring_soon"


@pytest.mark.asyncio
async def test_aggregate_gap_counts_for_client():
    db = MagicMock()
    db.compliance_gaps.aggregate = MagicMock(return_value=MagicMock())
    db.compliance_gaps.aggregate.return_value.to_list = AsyncMock(
        return_value=[
            {"_id": {"kind": "MISSING_EVIDENCE", "sev": "HIGH"}, "c": 2},
            {"_id": {"kind": "EXPIRED", "sev": "CRITICAL"}, "c": 1},
        ]
    )
    out = await aggregate_gap_counts_for_client(db, "c1", property_id="p1")
    assert out["total_open"] == 3
    assert out["by_kind"]["MISSING_EVIDENCE"] == 2
    assert out["by_kind"]["EXPIRED"] == 1
    call = db.compliance_gaps.aggregate.call_args[0][0]
    assert call[0]["$match"]["property_id"] == "p1"


@pytest.mark.asyncio
async def test_sync_compliance_gaps_upsert_and_resolve_audits():
    requirement = _synced_req(
        evidence_authority={"version": AUTHORITY_VERSION, "state": EA_MISSING},
        requirement_id="r-audit",
    )
    gaps = infer_compliance_gaps_for_requirement(requirement, property_doc=None)
    assert gaps

    class UR:
        def __init__(self, upserted=False):
            self.upserted_id = object() if upserted else None
            self.modified_count = 1 if not upserted else 0

    db = MagicMock()
    db.properties = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p-gap",
            "client_id": "c-gap",
            "jurisdiction": "England",
            "property_type": "residential",
            "tenancy_active": True,
        }
    )
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c-gap", "default_jurisdiction": "England"})
    db.compliance_gaps.update_one = AsyncMock(return_value=UR(upserted=True))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(
        return_value=[{"gap_key": "old:k", "gap_kind": "EXPIRED"}]
    )
    db.compliance_gaps.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

    with patch("services.compliance_gap_sync.apply_gap_operational_bridge", new=AsyncMock()) as bridge, patch(
        "services.compliance_gap_sync.create_audit_log", new=AsyncMock()
    ) as audit:
        await sync_compliance_gaps_for_requirement(db, requirement, property_doc=None)

    assert db.compliance_gaps.update_one.await_count == 1
    assert bridge.await_count == 1
    opened = [c for c in audit.await_args_list if (c.kwargs.get("action") == AuditAction.COMPLIANCE_GAP_OPENED)]
    resolved = [c for c in audit.await_args_list if (c.kwargs.get("action") == AuditAction.COMPLIANCE_GAP_RESOLVED)]
    assert len(opened) >= 1
    assert len(resolved) >= 1


@pytest.mark.asyncio
async def test_operational_automation_skips_when_gap_engine_materialised():
    from services.operational_automation_service import evaluate_compliance_driven_issues
    from services.ops_compliance_feature_flags import MAINTENANCE_WORKFLOWS

    req = {
        "requirement_id": "r1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_code": "GAS_SAFETY",
        "title": "Gas safety",
        "status": "EXPIRED",
    }
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=MagicMock())
    db.requirements.find.return_value.to_list = AsyncMock(return_value=[req])
    db.properties.find_one = AsyncMock(return_value={"property_id": "p1"})
    db.clients.find_one = AsyncMock(return_value={})
    db.compliance_gaps.count_documents = AsyncMock(return_value=1)
    db.maintenance_issues = MagicMock()
    db.operational_automation_suppress_audit = MagicMock()
    db.operational_automation_suppress_audit.update_one = AsyncMock(return_value=MagicMock(upserted_id=object()))

    with patch("services.operational_automation_service.database.get_db", return_value=db), patch(
        "services.operational_automation_service.filter_requirement_rows_for_client_runtime_surfaces",
        new=AsyncMock(side_effect=lambda db, **kw: kw.get("requirements") or []),
    ), patch(
        "services.operational_automation_service._flags_for_property",
        new=AsyncMock(return_value=({MAINTENANCE_WORKFLOWS: True}, None)),
    ), patch(
        "services.operational_automation_service.maintenance_issues_service.create_issue", new=AsyncMock()
    ) as create_issue, patch("services.operational_automation_service.create_audit_log", new=AsyncMock()):
        await evaluate_compliance_driven_issues("c1", "p1")

    create_issue.assert_not_called()


@pytest.mark.asyncio
async def test_reminder_evaluation_includes_gap_engine():
    from services import reminder_truth_service as rts

    req = {
        "requirement_id": "r1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_code": "EPC",
        "applicability": "REQUIRED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": EA_MISSING},
        "due_date": "2026-12-31T00:00:00+00:00",
    }
    db = MagicMock()
    db.properties = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "England",
            "property_type": "residential",
            "tenancy_active": True,
        }
    )
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "default_jurisdiction": "England"})
    db.requirements.find_one = AsyncMock(return_value=req)
    db.reminder_item_state.find_one = AsyncMock(return_value=None)
    db.reminder_item_state.update_one = AsyncMock()
    db.reminder_evaluation_log.insert_one = AsyncMock()

    with patch("services.reminder_truth_service.is_included_for_calendar", return_value=True), patch(
        "services.reminder_truth_service.get_effective_expiry_date",
        return_value=datetime(2026, 6, 1, tzinfo=timezone.utc),
    ):
        out = await rts.evaluate_requirement_for_daily_reminder(
            db, req, reminder_days=30, cooldown_hours=0, reminder_type="DAILY_COMPLIANCE_EXPIRY_EMAIL"
        )

    assert "gap_engine" in out
    assert GAP_MISSING_EVIDENCE in (out["gap_engine"].get("gap_kinds") or [])


@pytest.mark.asyncio
async def test_gap_operational_bridge_idempotent_when_issue_exists():
    requirement = _synced_req(requirement_id="r-bridge")
    row = infer_compliance_gaps_for_requirement(requirement, property_doc=None)[0].to_mongo(
        client_id="c-gap",
        property_id="p-gap",
        requirement_id="r-bridge",
        requirement_code="EPC",
    )
    row["status"] = "open"
    row["policy"] = {"create_issue_if_open": True}
    db = MagicMock()
    db.maintenance_issues.count_documents = AsyncMock(return_value=1)
    with patch("services.compliance_gap_operational_bridge.create_audit_log", new=AsyncMock()) as audit:
        await apply_gap_operational_bridge(db, [row], requirement)
    audit.assert_not_called()


@pytest.mark.asyncio
async def test_command_center_merges_gap_engine_counts():
    from services.command_center_service import get_command_center_bundle

    with patch(
        "services.command_center_service.get_unified_tasks_for_client",
        new=AsyncMock(return_value={"tasks": {"urgent": [], "in_progress": []}}),
    ), patch(
        "services.command_center_service.get_unified_tasks_digest",
        new=AsyncMock(return_value={"summary": {}, "freshness": {}, "activity_feed": []}),
    ), patch(
        "services.command_center_service.risk_signal_service.get_risk_signals_for_client",
        new=AsyncMock(return_value={"signals": []}),
    ), patch(
        "services.compliance_score.calculate_compliance_score",
        new=AsyncMock(return_value={"score": 80, "grade": "B", "message": "ok", "stats": {}}),
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new=AsyncMock(return_value={"by_kind": {"EXPIRED": 1}, "by_severity": {"HIGH": 1}, "total_open": 1}),
    ):
        bundle = await get_command_center_bundle("cc-client", predictive_enabled=False)

    assert bundle["compliance_status_summary"]["gap_engine"]["total_open"] == 1
    assert bundle["compliance_status_summary"]["gap_engine"]["by_kind"]["EXPIRED"] == 1


def test_gap_to_mongo_includes_policy_snapshot_fields():
    requirement = _synced_req(requirement_id="r-policy")
    requirement["applicability_state"] = "REQUIRED"
    requirement["is_mandatory"] = True
    requirement["policy_criticality"] = "HIGH"
    gaps = infer_compliance_gaps_for_requirement(requirement, property_doc=None)
    row = gaps[0].to_mongo(
        client_id="c-gap",
        property_id="p-gap",
        requirement_id="r-policy",
        requirement_code="EPC",
        requirement_row=requirement,
    )
    assert row["requirement_code_normalized"] == "epc"
    assert row["applicability_state"] in ("REQUIRED", "UNKNOWN")
    assert isinstance(row["is_mandatory"], bool)
    assert row["policy_criticality"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert "policy_classification_version" in row
    assert "policy_reason_codes" in row
