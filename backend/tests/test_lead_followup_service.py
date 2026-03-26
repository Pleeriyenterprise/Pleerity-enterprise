"""
Tests for lead follow-up service: default day-based nurture sequence and risk-check transactional.
"""
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from services.lead_models import (
    FOLLOWUP_SEQUENCE,
    DEFAULT_DAY_NURTURE_SEQUENCE,
)
from services.lead_followup_service import LeadFollowUpService


class TestDefaultDayNurtureSequence:
    """Default day-based nurture sequence (0, 2, 4, 6, 8, 12, 15) from lead_models."""

    def test_default_day_nurture_has_seven_steps(self):
        assert len(DEFAULT_DAY_NURTURE_SEQUENCE) == 7

    def test_default_day_nurture_delay_days_match_spec(self):
        days = [s["delay_days"] for s in DEFAULT_DAY_NURTURE_SEQUENCE]
        assert days == [0, 2, 4, 6, 8, 12, 15]

    def test_default_day_nurture_has_expected_template_ids(self):
        ids = [s["template_id"] for s in DEFAULT_DAY_NURTURE_SEQUENCE]
        assert ids[0] == "nurture_day0_welcome"
        assert ids[-1] == "nurture_day15_conversion_cta"
        assert "nurture_day2_compliance_education" in ids
        assert "nurture_day8_document_pack" in ids

    def test_followup_sequence_unchanged_three_steps(self):
        """Hour-based default sequence still exists for backward compatibility."""
        assert len(FOLLOWUP_SEQUENCE) == 3
        assert all("delay_hours" in s for s in FOLLOWUP_SEQUENCE)


class TestNurtureTemplatesRender:
    """New day-based nurture templates render without error."""

    def test_nurture_day0_welcome_renders(self):
        lead = {"lead_id": "LEAD-1", "email": "a@b.co", "name": "Test"}
        subject, body = LeadFollowUpService.render_template("nurture_day0_welcome", lead)
        assert "Welcome" in subject
        assert "Test" in body or "there" in body
        assert "LEAD-1" in body

    def test_risk_check_transactional_template_renders_with_risk_context(self):
        lead = {
            "lead_id": "LEAD-1",
            "email": "a@b.co",
            "name": "Test",
            "risk_score": 65,
            "risk_band": "MODERATE",
            "activation_url": "https://app.example.com/intake/start?lead_token=abc",
        }
        subject, body = LeadFollowUpService.render_template(
            "lead_transactional_risk_check_completed", lead
        )
        assert "Compliance Risk Snapshot" in subject or "Risk" in subject
        assert "65" in body
        assert "Activate Compliance Monitoring" in body
        assert "lead_token=abc" in body or "app.example.com" in body

    def test_transactional_risk_builder_does_not_expose_lead_id(self):
        from services.lead_followup_service import _build_transactional_risk_check_html

        lead = {
            "lead_id": "LEAD-INTERNAL-ONLY",
            "email": "a@b.co",
            "name": "Test",
            "risk_score": 92,
        }
        subject, body = _build_transactional_risk_check_html(lead, "https://app.example.com/intake/start")
        assert "Compliance Risk Snapshot" in subject
        assert "Low Risk" in body
        assert "LEAD-INTERNAL-ONLY" not in body


class TestSendRiskCheckCompletedTransactional:
    """send_risk_check_completed_transactional calls orchestrator and logs audit."""

    def test_send_risk_check_completed_returns_true_when_sent(self):
        lead = {
            "lead_id": "LEAD-rc1",
            "email": "risk@example.com",
            "name": "Risk",
            "risk_score": 50,
            "risk_band": "HIGH",
        }
        activation_url = "https://app.example.com/intake/start?lead_token=xyz"

        async def run():
            with patch(
                "services.notification_orchestrator.notification_orchestrator.send",
                new_callable=AsyncMock,
                return_value=MagicMock(outcome="sent"),
            ), patch(
                "services.lead_service.LeadService.log_audit",
                new_callable=AsyncMock,
            ):
                return await LeadFollowUpService.send_risk_check_completed_transactional(
                    lead, activation_url
                )

        result = asyncio.run(run())
        assert result is True

    def test_send_risk_check_completed_returns_false_when_no_email(self):
        lead = {"lead_id": "LEAD-rc1", "email": ""}

        async def run():
            return await LeadFollowUpService.send_risk_check_completed_transactional(
                lead, "https://app.example.com"
            )

        result = asyncio.run(run())
        assert result is False
