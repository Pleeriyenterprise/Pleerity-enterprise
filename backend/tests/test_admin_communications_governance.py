"""Governance unit tests for admin communications broadcast pipeline."""
from __future__ import annotations

import pytest

from services import admin_communications_service as acs


def test_sanitize_admin_html_strips_script():
    dirty = '<p>Hello</p><script>alert(1)</script><p>World</p>'
    clean = acs.sanitize_admin_html(dirty)
    assert "script" not in clean.lower()
    assert "Hello" in clean
    assert "World" in clean


def test_apply_template_variables_substitutes_and_strips_unknown():
    out = acs.apply_template_variables("Hi {{company_name}} — {{missing_token}}", {"company_name": "Acme"})
    assert out == "Hi Acme — "
    assert "{{" not in out


def test_preview_checksum_stable_for_same_payload():
    payload = {
        "message_type": "SERVICE_UPDATE",
        "severity": "info",
        "target_scope": "SINGLE",
        "target_filters": {"client_id": "c1"},
        "subject": "Test",
        "body_html": "<p>x</p>",
        "body_text": "",
        "in_app_title": "",
        "in_app_body": "",
        "banner_title": "",
        "banner_message": "",
        "channels": ["in_app"],
    }
    assert acs.compute_preview_checksum(payload) == acs.compute_preview_checksum(dict(payload))


def test_high_risk_ack_required_for_all_clients_and_incident():
    assert acs.requires_high_risk_acknowledgement("ALL_CLIENTS", "SERVICE_UPDATE") is True
    assert acs.requires_high_risk_acknowledgement("SINGLE", "INCIDENT") is True
    assert acs.requires_high_risk_acknowledgement("SINGLE", "SERVICE_UPDATE") is False


@pytest.mark.asyncio
async def test_send_blocks_without_confirm_send():
    with pytest.raises(ValueError, match="confirm_send"):
        await acs.send_communication(
            admin_user={"portal_user_id": "admin-1"},
            message_type="SERVICE_UPDATE",
            severity="info",
            target_scope="SINGLE",
            target_filters={"client_id": "c1"},
            subject="S",
            body_html="<p>x</p>",
            body_text="",
            in_app_title="T",
            in_app_body="B",
            banner_title="",
            banner_message="",
            channels=["in_app"],
            template_id=None,
            preview_checksum="deadbeef",
            expected_recipient_count=1,
            confirm_send=False,
            acknowledge_high_risk=False,
        )
