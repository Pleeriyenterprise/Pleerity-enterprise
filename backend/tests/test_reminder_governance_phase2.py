from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from services.email_service import EmailService, EmailTemplateAlias
from services.jobs import (
    _build_grouped_reminder_context,
    _infer_reminder_workflow_bucket,
    _reminder_item_label_from_req,
    _requirement_detail_label_from_req,
    _workflow_aware_reminder_line,
)
from services.governance_validation_engine import (
    validate_reminder_generation_semantics,
    validate_reminder_narrative_groups,
)


def test_reminder_display_prefers_requirement_display_short_and_canonical_names():
    req = {
        "requirement_type": "gas_safety",
        "requirement_display": {
            "short_name": "Gas Safety",
            "canonical_name": "Gas Safety Certificate",
        },
    }
    assert _reminder_item_label_from_req(req) == "Gas Safety"
    assert _requirement_detail_label_from_req(req) == "Gas Safety Certificate"


def test_reminder_workflow_bucket_fallback_order_prefers_primary_resolution_then_modes_then_code_family():
    req_primary = {"primary_resolution_workflow": "GUIDED_DECLARATION"}
    assert _infer_reminder_workflow_bucket(req_primary) == "GUIDED_DECLARATION"

    req_modes = {"allowed_evidence_modes": ["STRUCTURED_DECLARATION"]}
    assert _infer_reminder_workflow_bucket(req_modes) == "GUIDED_DECLARATION"

    req_code = {"requirement_code": "fitness_for_human_habitation"}
    assert _infer_reminder_workflow_bucket(req_code) == "CONDITION_STANDARD"


def test_reminder_semantics_are_workflow_aware_and_non_forbidden():
    guided_line = _workflow_aware_reminder_line({"workflow_class": "GUIDED_DECLARATION"}, classification="expiring", days_until_due=9)
    assess_line = _workflow_aware_reminder_line(
        {"workflow_class": "EXTERNAL_ASSESSMENT_EVIDENCE"}, classification="overdue", days_until_due=-2
    )
    cond_line = _workflow_aware_reminder_line({"workflow_class": "CONDITION_STANDARD"}, classification="expiring", days_until_due=12)
    doc_line = _workflow_aware_reminder_line({"workflow_class": "DOCUMENT_UPLOAD"}, classification="expiring", days_until_due=5)

    assert "declaration" in guided_line.lower()
    assert "assessment" in assess_line.lower()
    assert "condition" in cond_line.lower()
    assert "action is due soon" in doc_line.lower()

    all_text = " ".join([guided_line, assess_line, cond_line, doc_line]).lower()
    assert "blocking compliance" not in all_text
    assert "operationally safe" not in all_text
    assert "verification passed" not in all_text
    assert "upload complete" not in all_text


def test_validate_reminder_generation_semantics_flags_forbidden_and_missing_contracts():
    out = validate_reminder_generation_semantics(
        [
            {
                "source_type": "requirement",
                "type": "Tenancy agreement",
                "semantic_line": "Declaration verified and blocking compliance",
                "metadata": {"workflow_class": "GUIDED_DECLARATION"},
            }
        ]
    )
    assert out["summary"] == "FAIL"
    ids = set(out["results"][0]["violations"])
    assert any("missing_requirement_display" in x for x in ids)
    assert any("forbidden_generic_blocking_copy" in x for x in ids)
    assert any("declaration_presented_as_verified" in x for x in ids)


def test_validate_reminder_generation_semantics_warns_on_workflow_semantic_mismatch():
    out = validate_reminder_generation_semantics(
        [
            {
                "source_type": "requirement",
                "type": "Legionella",
                "semantic_line": "Evidence required before expiry",
                "metadata": {
                    "workflow_class": "EXTERNAL_ASSESSMENT_EVIDENCE",
                    "requirement_display": {"short_name": "Legionella", "canonical_name": "Legionella Assessment"},
                },
            }
        ]
    )
    assert out["summary"] == "WARN"
    warns = set(out["results"][0]["warnings"])
    assert any("reminder_semantics_inconsistent_with_workflow" in x for x in warns)


def test_grouped_reminder_context_builds_expected_semantic_groups_and_preserves_legacy_inputs():
    expiring = [
        {
            "type": "Gas Safety",
            "detail_type": "Gas Safety Certificate",
            "semantic_line": "Evidence required before expiry",
            "workflow_semantics_bucket": "DOCUMENT_UPLOAD",
            "days_remaining": 9,
        },
        {
            "type": "Deposit Protection",
            "detail_type": "Deposit Protection Record",
            "semantic_line": "Declaration has not been recorded — action required",
            "workflow_semantics_bucket": "GUIDED_DECLARATION",
            "days_remaining": 6,
        },
    ]
    overdue = [
        {
            "type": "Legionella",
            "detail_type": "Legionella Assessment",
            "semantic_line": "Assessment review is overdue — follow-up actions may remain unresolved",
            "workflow_semantics_bucket": "EXTERNAL_ASSESSMENT_EVIDENCE",
            "days_overdue": 2,
        },
        {
            "type": "Fitness for Human Habitation",
            "detail_type": "Fitness for Human Habitation Standard",
            "semantic_line": "Property condition issues require review — outstanding remediation activity detected",
            "workflow_semantics_bucket": "CONDITION_STANDARD",
            "days_overdue": 4,
        },
    ]
    grouped = _build_grouped_reminder_context(expiring, overdue)
    assert len(grouped["certificate_reminders"]) == 1
    assert len(grouped["declaration_reminders"]) == 1
    assert len(grouped["assessment_reminders"]) == 1
    assert len(grouped["condition_reminders"]) == 1
    assert len(grouped["other_reminders"]) == 0
    # Compatibility: builder does not mutate existing arrays.
    assert expiring[0]["type"] == "Gas Safety"
    assert overdue[0]["type"] == "Legionella"


def test_validate_reminder_narrative_groups_flags_forbidden_wording_and_wrong_placement():
    payload = {
        "certificate_reminders": [
            {
                "type": "Fitness for Human Habitation",
                "detail_type": "Fitness for Human Habitation Standard",
                "semantic_line": "Upload complete and blocking compliance",
                "workflow_semantics_bucket": "CONDITION_STANDARD",
            }
        ],
        "declaration_reminders": [
            {
                "type": "Tenancy Agreement",
                "detail_type": "Tenancy Agreement Record",
                "semantic_line": "Declaration verified and certified",
                "workflow_semantics_bucket": "GUIDED_DECLARATION",
            }
        ],
        "assessment_reminders": [
            {
                "type": "Legionella",
                "detail_type": "Legionella Assessment",
                "semantic_line": "Assessment is remediation complete and operationally safe",
                "workflow_semantics_bucket": "EXTERNAL_ASSESSMENT_EVIDENCE",
            }
        ],
        "condition_reminders": [],
        "other_reminders": [],
    }
    out = validate_reminder_narrative_groups(payload)
    assert out["summary"] == "FAIL"
    violations = set(out["results"][0]["violations"])
    assert any("condition_standard_in_certificate_group" in x for x in violations)
    assert any("forbidden_blocking_compliance_wording" in x for x in violations)
    assert any("declaration_framed_as_verified" in x for x in violations)
    assert any("assessment_framed_as_resolved_or_safe" in x for x in violations)


def test_send_reminder_email_includes_grouped_arrays_and_preserves_legacy_contract():
    async def _run():
        from services.jobs import JobScheduler

        with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
            scheduler = JobScheduler()
        scheduler.db = MagicMock()
        scheduler.db.audit_logs.insert_one = AsyncMock()

        captured = {}

        async def _fake_send(*, template_key, client_id, context, idempotency_key, event_type):
            captured["template_key"] = template_key
            captured["client_id"] = client_id
            captured["context"] = context
            captured["event_type"] = event_type
            return SimpleNamespace(outcome="sent")

        with patch("services.notification_orchestrator.notification_orchestrator.send", new=AsyncMock(side_effect=_fake_send)):
            ok = await scheduler._send_reminder_email(
                {"client_id": "c-1", "email": "a@test.com", "full_name": "Client"},
                expiring=[
                    {
                        "type": "Gas Safety",
                        "detail_type": "Gas Safety Certificate",
                        "semantic_line": "Evidence required before expiry",
                        "workflow_semantics_bucket": "DOCUMENT_UPLOAD",
                        "days_remaining": 6,
                        "due_date": "01 June 2026",
                        "property_address": "1 Test St",
                    }
                ],
                overdue=[],
                recipient_email="a@test.com",
            )
        assert ok is True
        assert captured["template_key"] == "COMPLIANCE_EXPIRY_REMINDER"
        ctx = captured["context"]
        # Legacy compatibility fields preserved.
        assert "expiring_count" in ctx and "overdue_count" in ctx
        assert "requirement_name" in ctx and "subject" in ctx
        # Phase 2B grouped fields added.
        assert isinstance(ctx["certificate_reminders"], list)
        assert isinstance(ctx["declaration_reminders"], list)
        assert isinstance(ctx["assessment_reminders"], list)
        assert isinstance(ctx["condition_reminders"], list)
        assert isinstance(ctx["other_reminders"], list)
        assert "certificate_reminders_json" in ctx

    asyncio.run(_run())


def test_reminder_template_renders_grouped_sections_when_present():
    svc = EmailService()
    html = svc._build_html_body(
        EmailTemplateAlias.REMINDER,
        {
            "client_name": "Client",
            "portal_link": "https://example.test/dashboard",
            "requirement_name": "Gas Safety",
            "property_address": "1 Test St",
            "due_date": "01 June 2026",
            "days_remaining": 5,
            "certificate_reminders": [
                {"type": "Gas Safety", "semantic_line": "Evidence required before expiry"},
            ],
            "declaration_reminders": [
                {"type": "Tenancy Agreement", "semantic_line": "Declaration verified and certified"},
            ],
            "assessment_reminders": [
                {"type": "Legionella", "semantic_line": "Assessment is operationally safe"},
            ],
            "condition_reminders": [
                {"type": "Fitness", "semantic_line": "Upload complete"},
            ],
            "other_reminders": [{"type": "General", "semantic_line": "Action required"}],
        },
    )
    text = svc._build_text_body(
        EmailTemplateAlias.REMINDER,
        {
            "client_name": "Client",
            "portal_link": "https://example.test/dashboard",
            "requirement_name": "Gas Safety",
            "property_address": "1 Test St",
            "due_date": "01 June 2026",
            "days_remaining": 5,
            "certificate_reminders": [{"type": "Gas Safety", "semantic_line": "Evidence required before expiry"}],
            "declaration_reminders": [{"type": "Tenancy Agreement", "semantic_line": "Declaration certified"}],
            "assessment_reminders": [{"type": "Legionella", "semantic_line": "Assessment remediated"}],
            "condition_reminders": [{"type": "Fitness", "semantic_line": "Document complete"}],
            "other_reminders": [],
        },
    )
    assert "Certificates, licences and registrations" in html
    assert "Declarations and tenancy records" in html
    assert "Assessments and reviews" in html
    assert "Property conditions and remediation" in html
    assert "Outstanding compliance obligations" in html
    assert "Certificates, licences and registrations:" in text
    assert "Declarations and tenancy records:" in text
    assert "Assessments and reviews:" in text
    assert "Property conditions and remediation:" in text
    lower_all = (html + "\n" + text).lower()
    assert "blocking compliance" not in lower_all
    assert "declaration verified" not in lower_all
    assert "declaration certified" not in lower_all
    assert "operationally safe" not in lower_all
    assert "remediated" not in lower_all
    assert "upload complete" not in lower_all
    assert "document complete" not in lower_all


def test_reminder_template_legacy_rendering_works_when_grouped_arrays_missing():
    svc = EmailService()
    html = svc._build_html_body(
        EmailTemplateAlias.REMINDER,
        {
            "client_name": "Client",
            "portal_link": "https://example.test/dashboard",
            "requirement_name": "Gas Safety",
            "property_address": "1 Test St",
            "due_date": "01 June 2026",
            "days_remaining": 3,
        },
    )
    text = svc._build_text_body(
        EmailTemplateAlias.REMINDER,
        {
            "client_name": "Client",
            "portal_link": "https://example.test/dashboard",
            "requirement_name": "Gas Safety",
            "property_address": "1 Test St",
            "due_date": "01 June 2026",
            "days_remaining": 3,
        },
    )
    assert "This is a reminder about" in html
    assert "This is a reminder about" in text
    assert "Certificates, licences and registrations" not in html
    assert "Certificates, licences and registrations:" not in text
