"""Tests for Email Presentation Authority (EMAIL-PRESENTATION-AUTHORITY-01)."""

from __future__ import annotations

import re

import pytest

from email_presentation.authority import EmailPresentationAuthority
from email_presentation.constants import RAG_AMBER_HEX, RAG_GREEN_HEX, RAG_RED_HEX
from email_presentation.context import enrich_presentation_context
from email_presentation.cta import CTA_OPEN_PORTAL, CTA_REVIEW_ISSUE, cta_label
from email_presentation.greeting import resolve_greeting, strip_embedded_greetings
from email_presentation.registry import AUTHORITY_VERSION, get_registry_entry, registry_as_list
from email_presentation.status_colors import color_for_rag, enrich_affected_properties, rag_status_chip_html
from email_presentation.shell import render_fragment_email, render_lead_sequence_email
from services.email_service import EmailService
from models import EmailTemplateAlias


class TestGreetingAuthority:
    def test_named_customer(self):
        assert resolve_greeting("Pleasant Aigbochie") == "Hello Pleasant,"

    def test_missing_name(self):
        assert resolve_greeting(None) == "Hello,"
        assert resolve_greeting("") == "Hello,"
        assert resolve_greeting("there") == "Hello,"

    def test_never_hello_there(self):
        assert "there" not in resolve_greeting("there").lower() or resolve_greeting("there") == "Hello,"

    def test_strip_embedded_greeting(self):
        frag = "<p>Hi ,</p><p>Your document has been verified.</p>"
        out = strip_embedded_greetings(frag)
        assert "Hi ," not in out
        assert "verified" in out

    def test_no_double_greeting_fragment_email(self):
        html = render_fragment_email(
            {},
            body_html="<p>Hi ,</p><h2>Document Verified</h2><p>Content</p>",
            client_name="Pleasant Aigbochie",
            header_title="Compliance Vault Pro",
        )
        assert html.count("Hello Pleasant,") == 1
        assert "Hi ," not in html


class TestStatusColourAuthority:
    def test_rag_colours(self):
        assert color_for_rag("GREEN") == RAG_GREEN_HEX
        assert color_for_rag("AMBER") == RAG_AMBER_HEX
        assert color_for_rag("RED") == RAG_RED_HEX

    def test_amber_not_red_default(self):
        row = enrich_affected_properties(
            [{"previous_status": "GREEN", "new_status": "AMBER", "address": "1 Test St"}]
        )[0]
        assert row["new_color"] == RAG_AMBER_HEX
        assert RAG_RED_HEX not in rag_status_chip_html("AMBER")

    def test_compliance_alert_table_amber(self):
        svc = EmailService()
        html = svc._build_html_body(
            EmailTemplateAlias.COMPLIANCE_ALERT,
            {
                "client_name": "Pleasant Aigbochie",
                "affected_properties": [
                    {
                        "address": "45 Lichfield Street",
                        "previous_status": "GREEN",
                        "new_status": "AMBER",
                        "reason": "Requirements expiring soon",
                    }
                ],
                "portal_link": "https://pleerityenterprise.co.uk/dashboard",
            },
        )
        assert f'color: {RAG_AMBER_HEX}' in html
        assert "Needs review" in html


class TestBrandingAndDomain:
    def test_brand_website_not_pleerity_com(self):
        brand = EmailPresentationAuthority.get_brand()
        assert "pleerity.com" not in brand.website_url
        assert brand.website_url.startswith("https://")

    def test_lead_sequence_no_hardcoded_pleerity_com(self):
        html = render_lead_sequence_email(
            None,
            display_name="Pleasant",
            body_text="Gap detected",
            header_title="Compliance gap",
            cta_url="https://pleerityenterprise.co.uk/dashboard",
            cta_key="review_issue",
            why_received="test",
        )
        assert "https://pleerity.com" not in html
        assert "pleerityenterprise.co.uk" in html

    def test_cta_governed_labels(self):
        assert cta_label("open_portal") == CTA_OPEN_PORTAL
        assert cta_label("review_issue") == CTA_REVIEW_ISSUE


class TestComplianceAlertAndEnablement:
    def test_compliance_alert_portal_authority_copy(self):
        svc = EmailService()
        html = svc._build_html_body(
            EmailTemplateAlias.COMPLIANCE_ALERT,
            {
                "client_name": "Pleasant",
                "affected_properties": [
                    {"address": "A", "previous_status": "AMBER", "new_status": "RED", "reason": "Overdue"}
                ],
                "portal_link": "#",
            },
        )
        assert "portal remains authoritative" in html.lower()

    def test_admin_manual_fragment_single_greeting(self):
        svc = EmailService()
        html = svc._build_html_body(
            EmailTemplateAlias.ADMIN_MANUAL,
            {
                "message": "<h2>Document Verified</h2><p>Verified content</p>",
                "client_name": "Pleasant Aigbochie",
            },
        )
        assert html.count("Hello Pleasant,") == 1
        assert "Hello there" not in html


class TestPresentationContext:
    def test_enrich_injects_colours(self):
        ctx = enrich_presentation_context(
            {"affected_properties": [{"previous_status": "AMBER", "new_status": "RED"}]}
        )
        assert ctx["affected_properties"][0]["prev_color"] == RAG_AMBER_HEX
        assert ctx["affected_properties"][0]["new_color"] == RAG_RED_HEX


class TestRegistry:
    def test_registry_covers_compliance_alert(self):
        entry = get_registry_entry("COMPLIANCE_ALERT")
        assert entry is not None
        assert entry["authority_version"] == AUTHORITY_VERSION
        assert entry["presentation_family"] == "compliance_status"

    def test_registry_all_email_templates(self):
        rows = registry_as_list()
        assert len(rows) >= 80
        assert all(r["template_key"] for r in rows)

    def test_no_production_pleerity_com_in_customer_shell_footer(self):
        html = EmailPresentationAuthority.render_customer_email(
            {},
            greeting="Hello,",
            body_html="<p>Test</p>",
            header_title="Test",
        )
        assert "pleerity.com" not in html
