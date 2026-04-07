"""Jurisdiction-aware contractor assignment (service_regions vs job jurisdiction)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.compliance_rules_registry import canonicalize_uk_portfolio_label
from services.contractor_service import (
    contractor_service_regions_allow_jurisdiction,
    normalize_contractor_service_regions_list,
)


def test_canonicalize_uk_portfolio_label():
    assert canonicalize_uk_portfolio_label("scotland") == "Scotland"
    assert canonicalize_uk_portfolio_label("England") == "England"
    assert canonicalize_uk_portfolio_label("  Wales ") == "Wales"
    assert canonicalize_uk_portfolio_label("EU") is None


def test_normalize_contractor_service_regions_list_drops_invalid():
    assert normalize_contractor_service_regions_list(["Scotland", "nope", "england"]) == ["Scotland", "England"]


def test_contractor_unrestricted_when_no_service_regions():
    assert contractor_service_regions_allow_jurisdiction({}, "Scotland") is True
    assert contractor_service_regions_allow_jurisdiction({"service_regions": []}, "Scotland") is True


def test_contractor_regions_must_cover_job():
    c = {"service_regions": ["England", "Wales"]}
    assert contractor_service_regions_allow_jurisdiction(c, "England") is True
    assert contractor_service_regions_allow_jurisdiction(c, "Scotland") is False


@pytest.mark.asyncio
async def test_resolve_effective_work_order_jurisdiction_from_wo_field():
    from services.contractor_service import resolve_effective_work_order_jurisdiction

    db = MagicMock()
    db.requirements.find_one = AsyncMock()
    db.properties.find_one = AsyncMock()
    db.clients.find_one = AsyncMock()
    wo = {"jurisdiction": "wales", "property_id": "p1", "linked_property_requirement_id": None}
    j = await resolve_effective_work_order_jurisdiction(db, wo, "c1")
    assert j == "Wales"
    db.requirements.find_one.assert_not_called()
