"""Branding resolver: Pleerity default vs white-label eligibility."""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.account_capability_enforcement import CapabilityDecision
from services.branding_resolver_service import (
    BrandingContext,
    BrandingFallbackReason,
    resolve_branding,
    merge_invoice_branding_overlay,
    pleerity_profile,
)


def _capability_patch(*, allowed=True, reason_code="PLAN_NOT_ELIGIBLE"):
    decision = CapabilityDecision(
        capability_id="CAP_BRANDING_WHITE_LABEL",
        action="read",
        grant="ALLOW" if allowed else "DENY",
        effective_semantic="ALLOW" if allowed else "DENY",
        allowed=allowed,
        source="test",
        reason_code=reason_code if not allowed else "",
        reason="" if allowed else reason_code,
    )
    mock_svc = MagicMock()
    mock_svc.evaluate = AsyncMock(return_value=decision)
    return patch(
        "services.branding_resolver_service.CapabilityEnforcementService",
        return_value=mock_svc,
    )


def test_scenario_a_no_white_label_uses_pleerity_visuals_and_client_doc_name():
    """WL off → Pleerity letterhead keys; document still shows client business name."""
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={
            "company_name": "Acme Lettings",
            "email": "ops@acme.test",
            "phone": "123",
        }
    )
    mock_db.branding_settings.find_one = AsyncMock(
        return_value={"white_label_enabled": False, "primary_color": "#FF0000"}
    )

    async def _run():
        with patch("services.branding_resolver_service.database.get_db", return_value=mock_db):
            with _capability_patch(allowed=True):
                return await resolve_branding("c1", BrandingContext.CLIENT_DOCUMENT_PDF)

    p = asyncio.run(_run())
    assert p.source == "pleerity"
    assert p.company_name.startswith("Pleerity")
    assert "Acme Lettings" in p.to_report_dict()["company_name"]
    assert BrandingFallbackReason.WHITE_LABEL_NOT_ENABLED.value in p.fallback_reasons


def test_scenario_b_white_label_when_complete():
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={"company_name": "Acme", "email": "ops@acme.test"}
    )
    mock_db.branding_settings.find_one = AsyncMock(
        return_value={
            "white_label_enabled": True,
            "company_name": "Acme WL",
            "contact_email": "support@acme.test",
            "logo_upload_ext": ".png",
            "logo_url": "https://api.example/branding/logo",
            "primary_color": "#0B1D3A",
            "include_pleerity_branding": True,
        }
    )

    async def _run():
        with patch("services.branding_resolver_service.database.get_db", return_value=mock_db):
            with _capability_patch(allowed=True):
                with patch(
                    "services.branding_resolver_service._client_logo_file_path",
                    return_value="/tmp/branding_logos/c1.png",
                ):
                    return await resolve_branding("c1", BrandingContext.CLIENT_DOCUMENT_PDF)

    p = asyncio.run(_run())
    assert p.source == "client_white_label"
    assert p.company_name == "Acme WL"
    assert not p.fallback_reasons
    lines = p.to_report_dict()["pdf_attribution_lines"]
    assert any("Powered by" in x for x in lines)


def test_scenario_c_incomplete_logo_falls_back():
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={"company_name": "Acme", "email": "a@a.test"}
    )
    mock_db.branding_settings.find_one = AsyncMock(
        return_value={
            "white_label_enabled": True,
            "company_name": "Acme",
            "contact_email": "a@a.test",
            "primary_color": "#0B1D3A",
        }
    )

    async def _run():
        with patch("services.branding_resolver_service.database.get_db", return_value=mock_db):
            with _capability_patch(allowed=True):
                with patch("services.branding_resolver_service._client_logo_file_path", return_value=None):
                    return await resolve_branding("c1", BrandingContext.CLIENT_DOCUMENT_PDF)

    p = asyncio.run(_run())
    assert p.source == "pleerity"
    assert BrandingFallbackReason.INCOMPLETE_MISSING_LOGO.value in p.fallback_reasons


def test_scenario_d_plan_denies_white_label():
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value={"company_name": "Acme", "email": "a@a.test"})
    mock_db.branding_settings.find_one = AsyncMock(return_value={"white_label_enabled": True})

    async def _run():
        with patch("services.branding_resolver_service.database.get_db", return_value=mock_db):
            with _capability_patch(allowed=False, reason_code="PLAN_NOT_ELIGIBLE"):
                return await resolve_branding("c1", BrandingContext.CLIENT_DOCUMENT_PDF)

    p = asyncio.run(_run())
    assert p.source == "pleerity"
    assert "PLAN_NOT_ELIGIBLE" in p.fallback_reasons


def test_invoice_overlay_empty_for_pleerity():
    p = pleerity_profile()
    assert merge_invoice_branding_overlay(p) == {}
