"""Tests for Lifecycle Communication Authority (LIFECYCLE-COMMUNICATION-AUTHORITY-01)."""

from __future__ import annotations

import pytest

from lifecycle_communication import (
    AUTHORITY_VERSION,
    LifecycleCommunicationAuthority,
    resolve_customer_communication,
    registry_as_list,
)
from lifecycle_communication.constants import LIFECYCLE_FAMILIES
from lifecycle_communication.headings import heading_for_reminder_group
from lifecycle_communication.verbs import GOVERNED_VERBS
from models import EmailTemplateAlias
from services.email_service import EmailService
from services.lifecycle_reminder_template_registry import lifecycle_reminder_spec


def _row(**kwargs):
    base = {
        "requirement_code": "gas_safety",
        "requirement_name": "Gas Safety Certificate",
        "status": "EXPIRING_SOON",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "client_lifecycle_label": "Renewal due",
    }
    base.update(kwargs)
    return base


class TestRegistry:
    def test_all_families_registered(self):
        families = {e["lifecycle_family"] for e in registry_as_list()}
        assert families == set(LIFECYCLE_FAMILIES)

    def test_authority_version(self):
        assert AUTHORITY_VERSION == "lifecycle_communication_v1"
        assert LifecycleCommunicationAuthority.version == AUTHORITY_VERSION


class TestLifecycleFamilies:
    @pytest.mark.parametrize(
        "row,expected_family,expected_verb",
        [
            (_row(lifecycle_semantics="EXPIRY_BASED"), "EXPIRY_BASED", "Renew"),
            (_row(requirement_code="hmo_license", lifecycle_attention_kind="CERTIFICATE_EXPIRING"), "LICENSING", "Renew"),
            (
                _row(requirement_code="scotland_landlord_registration", lifecycle_attention_kind="CERTIFICATE_EXPIRING"),
                "REGISTRATION",
                "Renew",
            ),
            (_row(lifecycle_semantics="DECLARATION_BASED"), "DECLARATION_BASED", "Complete"),
            (_row(lifecycle_semantics="TENANCY_LIFECYCLE", lifecycle_attention_kind="TENANCY_TERM_ENDING"), "TENANCY_LIFECYCLE", "Upload"),
            (_row(lifecycle_semantics="OCCUPANCY_LIFECYCLE", lifecycle_attention_kind="OCCUPANCY_REVIEW_DUE"), "OCCUPANCY_LIFECYCLE", "Record"),
            (_row(lifecycle_attention_kind="REVIEW_DUE"), "REVIEW_BASED", "Review"),
            (_row(lifecycle_attention_kind="EVENT_ACTION_REQUIRED"), "EVENT_BASED", "Record"),
            (_row(lifecycle_attention_kind="OPERATIONAL_ACTION_REQUIRED"), "OPERATIONAL", "Resolve"),
            (_row(workflow_class="GUIDED_DECLARATION"), "DECLARATION_BASED", "Complete"),
            (_row(workflow_class="EXTERNAL_ASSESSMENT_EVIDENCE"), "ASSESSMENT", "Complete"),
            (_row(allowed_evidence_modes=["INSPECTION_CHECKLIST"]), "INSPECTION", "Arrange"),
        ],
    )
    def test_family_and_verb(self, row, expected_family, expected_verb):
        comm = resolve_customer_communication(row, surface="portal_detail")
        assert comm["lifecycle_family"] == expected_family
        assert comm["lifecycle_verb"] == expected_verb
        assert GOVERNED_VERBS[expected_family] == expected_verb


class TestCommunicationStructure:
    def test_answers_why_what_when_how_next(self):
        comm = resolve_customer_communication(
            _row(due_date="2026-08-01"),
            surface="portal_detail",
            due_date="2026-08-01",
        )
        assert comm["reason"]
        assert comm["primary_action"]
        assert comm["when_text"]
        assert comm["how_text"]
        assert comm["next_step"]
        assert "expiry" not in comm["reason"].lower() or comm["lifecycle_family"] in (
            "EXPIRY_BASED",
            "LICENSING",
            "REGISTRATION",
        )

    def test_no_generic_action_required_reason(self):
        comm = resolve_customer_communication(
            _row(lifecycle_semantics="DECLARATION_BASED", requirement_code="legionella_declaration"),
            surface="portal_detail",
        )
        assert comm["reason"]
        assert comm["reason"].lower() not in ("action required.", "compliance action required.")
        assert "declaration" in comm["reason"].lower()


class TestNoLeakage:
    def test_review_not_renewal(self):
        comm = resolve_customer_communication(
            _row(lifecycle_attention_kind="REVIEW_DUE"),
            surface="digest",
            is_overdue=True,
        )
        sv = comm["surface_variants"]
        assert "renewal" not in sv.get("digest_label", "").lower()

    def test_declaration_not_expiry(self):
        comm = resolve_customer_communication(
            _row(lifecycle_semantics="DECLARATION_BASED"),
            surface="enablement",
            due_date="2026-08-01",
        )
        assert "expires" not in comm["reason"].lower()
        assert "renewal" not in comm["primary_action"].lower()

    def test_operational_not_certificate(self):
        comm = resolve_customer_communication(
            {
                "lifecycle_attention_kind": "OPERATIONAL_ACTION_REQUIRED",
                "requirement_name": "Extractor fan repair",
                "client_lifecycle_label": "Follow-up required",
            },
            surface="portal_detail",
        )
        assert "renewal" not in comm["reason"].lower()
        assert comm["lifecycle_verb"] == "Resolve"


class TestHeadings:
    def test_group_headings_not_misleading(self):
        assert "Certificates & Expiring Evidence" not in heading_for_reminder_group("certificate_reminders")
        assert "Other Compliance Actions" not in heading_for_reminder_group("other_reminders")
        assert "licences" in heading_for_reminder_group("certificate_reminders").lower()


class TestReminderIntegration:
    def test_review_due_spec_avoids_expiry_language(self):
        spec = lifecycle_reminder_spec("REVIEW_DUE")
        assert "expiry" not in spec["header_title"].lower()
        assert "review" in spec["intro_html"].lower()

    def test_lifecycle_reminder_email_uses_governed_copy(self):
        svc = EmailService()
        html = svc._build_html_body(
            EmailTemplateAlias.LIFECYCLE_REMINDER_REVIEW_DUE,
            {
                "client_name": "Test",
                "requirement_name": "Legionella",
                "property_address": "1 Test Street",
                "due_date": "2026-07-01",
                "lifecycle_attention_kind": "REVIEW_DUE",
            },
        )
        assert "review due on" in html.lower()
        assert "renewal" not in html.lower()


class TestTakeActionEnrichment:
    def test_customer_communication_attached(self):
        from services.requirement_action_resolver import (
            enrich_take_action_envelope_for_client,
            resolve_take_action_envelope,
        )

        row = _row(property_id="prop-1", workflow_class="DOCUMENT_UPLOAD")
        env = enrich_take_action_envelope_for_client(resolve_take_action_envelope(row, property_id="prop-1"), row)
        assert "customer_communication" in env
        assert env["customer_communication"]["authority_version"] == AUTHORITY_VERSION


class TestRiskCopy:
    def test_electrical_not_certificate_only(self):
        from lifecycle_communication.copy import risk_recommended_action

        text = risk_recommended_action("ELECTRICAL")
        assert "electrical safety obligation" in text.lower()
        assert "certificate and arrange" not in text.lower()
