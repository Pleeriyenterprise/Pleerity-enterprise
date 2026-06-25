"""Phase 4 S4.2 + S4.3 — lifecycle-aware reminder shadow telemetry and active gates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.lifecycle_aware_reminders_config import get_effective_reminder_mode
from services.lifecycle_reminder_gates import (
    build_reminder_lifecycle_context,
    classify_reminder_timing,
    evaluate_lifecycle_certificate_expiry_reminder,
    lifecycle_certificate_expiry_pipeline_allowed,
    resolve_lifecycle_reminder_template_key,
)


def _iso_in_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _mock_db(req: dict) -> MagicMock:
    db = MagicMock()
    db.properties = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": req.get("property_id"),
            "client_id": req.get("client_id"),
            "jurisdiction": "England",
            "property_type": "residential",
            "tenancy_active": True,
        }
    )
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={"client_id": req.get("client_id"), "default_jurisdiction": "England"}
    )
    db.requirements.find_one = AsyncMock(return_value=req)
    db.reminder_item_state.find_one = AsyncMock(return_value=None)
    db.reminder_item_state.update_one = AsyncMock()
    db.reminder_evaluation_log.insert_one = AsyncMock()
    return db


class TestLifecycleReminderGatesUnit:
    def test_certificate_pipeline_blocks_review_based_when_gated(self):
        ctx = build_reminder_lifecycle_context(
            {"requirement_code": "legionella", "due_date": _iso_in_days(10)},
        )
        assert ctx.lifecycle_semantics == "REVIEW_BASED"
        allowed = lifecycle_certificate_expiry_pipeline_allowed(
            "DAILY_COMPLIANCE_EXPIRY_EMAIL",
            apply_lifecycle_gates=True,
            lifecycle_semantics=ctx.lifecycle_semantics,
            requires_expiry_date=ctx.requires_expiry_date,
        )
        assert allowed is False

    def test_template_resolver_off_returns_legacy(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_REMINDERS", raising=False)
        assert resolve_lifecycle_reminder_template_key("REVIEW_DUE", channel="EMAIL") == (
            "COMPLIANCE_EXPIRY_REMINDER"
        )


class TestLifecycleReminderShadow:
    @pytest.mark.asyncio
    async def test_shadow_logs_divergence_for_review_based_due_date(self, monkeypatch, caplog):
        from services import reminder_truth_service as rts

        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        req = {
            "requirement_id": "r-leg",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_code": "legionella",
            "requirement_type": "legionella",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "due_date": _iso_in_days(10),
            "client_surface_visible": True,
        }
        db = _mock_db(req)
        with patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new=AsyncMock(return_value=True),
        ):
            out = await rts.evaluate_requirement_for_daily_reminder(
                db,
                req,
                reminder_days=30,
                cooldown_hours=0,
                reminder_type="DAILY_COMPLIANCE_EXPIRY_EMAIL",
            )
        assert get_effective_reminder_mode() == "shadow"
        assert out["eligible"] is True
        assert "lifecycle_reminder_shadow_complete" in caplog.text
        assert "lifecycle_reminder_shadow_divergence" in caplog.text

    @pytest.mark.asyncio
    async def test_shadow_keeps_legacy_eligibility_authoritative(self, monkeypatch):
        from services import reminder_truth_service as rts

        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        req = {
            "requirement_id": "r-leg",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_code": "legionella",
            "requirement_type": "legionella",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "due_date": _iso_in_days(10),
            "client_surface_visible": True,
        }
        db = _mock_db(req)
        with patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new=AsyncMock(return_value=True),
        ):
            shadow_out = await rts.evaluate_requirement_for_daily_reminder(
                db,
                req,
                reminder_days=30,
                cooldown_hours=0,
                reminder_type="DAILY_COMPLIANCE_EXPIRY_EMAIL",
            )
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "off")
        db2 = _mock_db(req)
        with patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new=AsyncMock(return_value=True),
        ):
            off_out = await rts.evaluate_requirement_for_daily_reminder(
                db2,
                req,
                reminder_days=30,
                cooldown_hours=0,
                reminder_type="DAILY_COMPLIANCE_EXPIRY_EMAIL",
            )
        assert shadow_out["eligible"] == off_out["eligible"] is True


class TestLifecycleReminderActiveGates:
    def _active_preview(self, monkeypatch) -> None:
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")

    @pytest.mark.asyncio
    async def test_active_suppresses_review_based_due_date(self, monkeypatch):
        from services import reminder_truth_service as rts

        self._active_preview(monkeypatch)
        req = {
            "requirement_id": "r-leg",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_code": "legionella",
            "requirement_type": "legionella",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "due_date": _iso_in_days(10),
            "client_surface_visible": True,
        }
        db = _mock_db(req)
        with patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new=AsyncMock(return_value=True),
        ):
            out = await rts.evaluate_requirement_for_daily_reminder(
                db,
                req,
                reminder_days=30,
                cooldown_hours=0,
                reminder_type="DAILY_COMPLIANCE_EXPIRY_EMAIL",
            )
        assert out["eligible"] is False
        assert out["suppression_reason"] == "NOT_RELEVANT"

    @pytest.mark.asyncio
    async def test_active_allows_expiry_based_certificate(self, monkeypatch):
        from services import reminder_truth_service as rts

        self._active_preview(monkeypatch)
        req = {
            "requirement_id": "r-gas",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_code": "gas_safety",
            "requirement_type": "gas_safety",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "due_date": _iso_in_days(10),
            "client_surface_visible": True,
        }
        db = _mock_db(req)
        with patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new=AsyncMock(return_value=True),
        ):
            out = await rts.evaluate_requirement_for_daily_reminder(
                db,
                req,
                reminder_days=30,
                cooldown_hours=0,
                reminder_type="DAILY_COMPLIANCE_EXPIRY_EMAIL",
            )
        assert out["eligible"] is True
        assert out["classification"] == "expiring"
        assert out.get("lifecycle_attention_kind") == "CERTIFICATE_EXPIRING"

    def test_active_gate_evaluator_blocks_non_expiry_semantics(self, monkeypatch):
        self._active_preview(monkeypatch)
        now = datetime.now(timezone.utc)
        ctx = build_reminder_lifecycle_context(
            {"requirement_code": "legionella", "due_date": _iso_in_days(10)},
            as_of=now,
        )
        eligible, classification, reason = evaluate_lifecycle_certificate_expiry_reminder(
            ctx,
            reminder_type="DAILY_COMPLIANCE_EXPIRY_EMAIL",
            now=now,
            reminder_days=30,
            legacy_due_date=now + timedelta(days=10),
            apply_lifecycle_gates=True,
        )
        assert eligible is False
        assert classification is None
        assert reason == "NOT_RELEVANT"


class TestLifecycleReminderTemplateRouting:
    def test_shadow_logs_planned_template_routing(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        key = resolve_lifecycle_reminder_template_key("REVIEW_DUE", channel="EMAIL")
        assert key == "COMPLIANCE_EXPIRY_REMINDER"
        assert "lifecycle_reminder_shadow_template_routing" in caplog.text

    def test_active_returns_planned_template_mapping(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        assert resolve_lifecycle_reminder_template_key("CERTIFICATE_EXPIRING") == (
            "COMPLIANCE_EXPIRY_REMINDER"
        )

    def test_classify_reminder_timing_overdue(self):
        now = datetime.now(timezone.utc)
        eligible, classification, reason = classify_reminder_timing(
            now - timedelta(days=3),
            now=now,
            reminder_days=30,
        )
        assert eligible is True
        assert classification == "overdue"
        assert reason is None
