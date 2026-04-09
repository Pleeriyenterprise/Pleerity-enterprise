"""Unit tests for portfolio jurisdiction resolution and jurisdiction_compliance_notice payloads."""
from unittest.mock import AsyncMock, patch

import pytest

from services.compliance_rules_registry import (
    COMPLIANCE_BASIS_CLIENT_DEFAULT,
    COMPLIANCE_BASIS_DEFAULT_FALLBACK,
    COMPLIANCE_BASIS_PROPERTY_EXPLICIT,
    COMPLIANCE_CONFIDENCE_EXPLICIT,
    COMPLIANCE_CONFIDENCE_FALLBACK,
    build_jurisdiction_compliance_notice,
    build_portfolio_jurisdiction_attestation,
    jurisdiction_attribution_for_property,
    property_jurisdiction_requirement_flags,
    resolve_portfolio_jurisdiction,
)
from presentation.jurisdiction_reporting import unique_property_jurisdictions
from services.command_center_service import get_command_center_bundle


def test_resolve_portfolio_jurisdiction_property_explicit():
    r = resolve_portfolio_jurisdiction({"jurisdiction": "Scotland"}, {"default_jurisdiction": "England"})
    assert r.effective_label == "Scotland"
    assert r.compliance_basis == COMPLIANCE_BASIS_PROPERTY_EXPLICIT


def test_resolve_portfolio_jurisdiction_client_default_when_property_missing():
    r = resolve_portfolio_jurisdiction({}, {"default_jurisdiction": "Wales"})
    assert r.effective_label == "Wales"
    assert r.compliance_basis == COMPLIANCE_BASIS_CLIENT_DEFAULT


def test_resolve_portfolio_jurisdiction_client_default_case_insensitive():
    r = resolve_portfolio_jurisdiction({}, {"default_jurisdiction": "  england  "})
    assert r.effective_label == "England"
    assert r.compliance_basis == COMPLIANCE_BASIS_CLIENT_DEFAULT


def test_resolve_portfolio_jurisdiction_client_default_invalid_property_value():
    r = resolve_portfolio_jurisdiction({"jurisdiction": "  eu  "}, {"default_jurisdiction": "Northern Ireland"})
    assert r.effective_label == "Northern Ireland"
    assert r.compliance_basis == COMPLIANCE_BASIS_CLIENT_DEFAULT


def test_resolve_portfolio_jurisdiction_default_fallback_no_valid_labels():
    r = resolve_portfolio_jurisdiction({}, {})
    assert r.effective_label == "England"
    assert r.compliance_basis == COMPLIANCE_BASIS_DEFAULT_FALLBACK


def test_resolve_portfolio_jurisdiction_default_fallback_invalid_client_only():
    r = resolve_portfolio_jurisdiction({"jurisdiction": ""}, {"default_jurisdiction": "InvalidLand"})
    assert r.effective_label == "England"
    assert r.compliance_basis == COMPLIANCE_BASIS_DEFAULT_FALLBACK


def test_resolve_strips_whitespace_property():
    r = resolve_portfolio_jurisdiction({"jurisdiction": "  England  "}, None)
    assert r.effective_label == "England"
    assert r.compliance_basis == COMPLIANCE_BASIS_PROPERTY_EXPLICIT


def test_property_jurisdiction_requirement_flags_explicit_vs_missing():
    f_ok = property_jurisdiction_requirement_flags({"jurisdiction": "Wales"})
    assert f_ok["jurisdiction_required"] is False
    assert f_ok["compliance_confidence"] == COMPLIANCE_CONFIDENCE_EXPLICIT
    f_miss = property_jurisdiction_requirement_flags({})
    assert f_miss["jurisdiction_required"] is True
    assert f_miss["compliance_confidence"] == COMPLIANCE_CONFIDENCE_FALLBACK


def test_build_portfolio_jurisdiction_attestation_counts_ids():
    att = build_portfolio_jurisdiction_attestation(
        {},
        [{"property_id": "a", "jurisdiction": "Scotland"}, {"property_id": "b"}],
    )
    assert att["jurisdiction_required"] is True
    assert att["compliance_confidence"] == COMPLIANCE_CONFIDENCE_FALLBACK
    assert att["jurisdiction_required_property_ids"] == ["b"]
    assert att["jurisdiction_required_property_count"] == 1


def test_build_jurisdiction_compliance_notice_empty_properties():
    n = build_jurisdiction_compliance_notice({"default_jurisdiction": "Scotland"}, [])
    assert n["active"] is False
    assert n["compliance_basis"] is None
    assert n["affected_property_ids"] == []
    assert n["affected_property_count"] == 0


def test_build_jurisdiction_compliance_notice_all_explicit():
    client = {"default_jurisdiction": "England"}
    props = [
        {"property_id": "p1", "jurisdiction": "Scotland"},
        {"property_id": "p2", "jurisdiction": "Wales"},
    ]
    n = build_jurisdiction_compliance_notice(client, props)
    assert n["active"] is False
    assert n["affected_property_count"] == 0


def test_build_jurisdiction_compliance_notice_all_client_default_no_notice():
    """Properties without explicit jurisdiction still resolve via client default — not fallback."""
    client = {"default_jurisdiction": "Wales"}
    props = [{"property_id": "a"}, {"property_id": "b"}]
    n = build_jurisdiction_compliance_notice(client, props)
    assert n["active"] is False
    assert n["affected_property_ids"] == []


def test_build_jurisdiction_compliance_notice_mixed_explicit_and_client_default_no_fallback():
    client = {"default_jurisdiction": "Wales"}
    props = [
        {"property_id": "p1", "jurisdiction": "Scotland"},
        {"property_id": "p2"},
    ]
    n = build_jurisdiction_compliance_notice(client, props)
    assert n["active"] is False


def test_build_jurisdiction_compliance_notice_mixed_affected_ids_and_count():
    client = {}
    props = [
        {"property_id": "ok", "jurisdiction": "England"},
        {"property_id": "fb1"},
        {"property_id": "fb2", "jurisdiction": "not-a-uk-label"},
    ]
    n = build_jurisdiction_compliance_notice(client, props)
    assert n["active"] is True
    assert n["compliance_basis"] == COMPLIANCE_BASIS_DEFAULT_FALLBACK
    assert set(n["affected_property_ids"]) == {"fb1", "fb2"}
    assert n["affected_property_count"] == 2


def test_build_jurisdiction_compliance_notice_skips_rows_without_property_id():
    client = {}
    props = [{"jurisdiction": None}, {"property_id": "p1"}]
    n = build_jurisdiction_compliance_notice(client, props)
    assert n["affected_property_ids"] == ["p1"]
    assert n["affected_property_count"] == 1


def test_build_fallback_when_only_client_default_applies_to_address_only_props():
    """Properties with no jurisdiction still resolve via client default — no notice."""
    client = {"default_jurisdiction": "Scotland"}
    props = [{"property_id": "p1", "address_line_1": "1 Main St"}]
    n = build_jurisdiction_compliance_notice(client, props)
    assert n["active"] is False


@pytest.mark.asyncio
async def test_command_center_scopes_jurisdiction_notice_to_property_filter():
    """When property_id_filter is set, only that id remains in affected_property_ids if it was fallback."""
    cs = {
        "score": 70,
        "grade": "C",
        "message": "ok",
        "stats": {"overdue": 1},
        "jurisdiction_required": True,
        "compliance_confidence": "fallback",
        "jurisdiction_required_property_ids": ["scoped-p", "other-p"],
        "jurisdiction_required_property_count": 2,
        "jurisdiction_fallback_acknowledged": False,
        "jurisdiction_compliance_notice": {
            "active": True,
            "compliance_basis": "default_fallback",
            "affected_property_ids": ["scoped-p", "other-p"],
            "affected_property_count": 2,
        },
    }
    with patch(
        "services.command_center_service.get_unified_tasks_digest",
        new=AsyncMock(return_value={"summary": {}, "freshness": {}, "activity_feed": []}),
    ), patch(
        "services.command_center_service.get_unified_tasks_for_client",
        new=AsyncMock(return_value={"tasks": {"urgent": [], "in_progress": []}}),
    ), patch(
        "services.command_center_service.risk_signal_service.get_risk_signals_for_client",
        new=AsyncMock(return_value={"signals": []}),
    ), patch(
        "services.compliance_score.calculate_compliance_score",
        new=AsyncMock(return_value=cs),
    ):
        bundle = await get_command_center_bundle(
            "c1",
            predictive_enabled=False,
            property_id_filter="scoped-p",
        )
    notice = bundle["compliance_status_summary"]["jurisdiction_compliance_notice"]
    assert notice["active"] is True
    assert notice["compliance_basis"] == "default_fallback"
    assert notice["affected_property_ids"] == ["scoped-p"]
    assert notice["affected_property_count"] == 1
    summ = bundle["compliance_status_summary"]
    assert summ["jurisdiction_required"] is True
    assert summ["compliance_confidence"] == "fallback"


@pytest.mark.asyncio
async def test_command_center_scoped_filter_hides_notice_when_property_not_affected():
    cs = {
        "score": 70,
        "grade": "C",
        "message": "ok",
        "stats": {},
        "jurisdiction_required": True,
        "compliance_confidence": "fallback",
        "jurisdiction_required_property_ids": ["other-p"],
        "jurisdiction_required_property_count": 1,
        "jurisdiction_fallback_acknowledged": False,
        "jurisdiction_compliance_notice": {
            "active": True,
            "compliance_basis": "default_fallback",
            "affected_property_ids": ["other-p"],
            "affected_property_count": 1,
        },
    }
    with patch(
        "services.command_center_service.get_unified_tasks_digest",
        new=AsyncMock(return_value={"summary": {}, "freshness": {}, "activity_feed": []}),
    ), patch(
        "services.command_center_service.get_unified_tasks_for_client",
        new=AsyncMock(return_value={"tasks": {"urgent": [], "in_progress": []}}),
    ), patch(
        "services.command_center_service.risk_signal_service.get_risk_signals_for_client",
        new=AsyncMock(return_value={"signals": []}),
    ), patch(
        "services.compliance_score.calculate_compliance_score",
        new=AsyncMock(return_value=cs),
    ):
        bundle = await get_command_center_bundle(
            "c1",
            predictive_enabled=False,
            property_id_filter="scoped-p",
        )
    notice = bundle["compliance_status_summary"]["jurisdiction_compliance_notice"]
    assert notice["active"] is False
    assert notice["compliance_basis"] is None
    assert notice["affected_property_ids"] == []
    summ = bundle["compliance_status_summary"]
    assert summ["jurisdiction_required"] is False
    assert summ["compliance_confidence"] == "explicit"


def test_jurisdiction_attribution_property_record():
    att = jurisdiction_attribution_for_property(
        {"jurisdiction": "Wales"}, {"default_jurisdiction": "Scotland"}
    )
    assert att["jurisdiction_source"] == "property_record"
    assert att["effective_jurisdiction_label"] == "Wales"
    assert att["compliance_basis"] == COMPLIANCE_BASIS_PROPERTY_EXPLICIT


def test_jurisdiction_attribution_account_default():
    att = jurisdiction_attribution_for_property({}, {"default_jurisdiction": "England"})
    assert att["jurisdiction_source"] == "account_default"
    assert att["effective_jurisdiction_label"] == "England"
    assert att["compliance_basis"] == COMPLIANCE_BASIS_CLIENT_DEFAULT


def test_jurisdiction_attribution_system_default():
    att = jurisdiction_attribution_for_property({}, {})
    assert att["jurisdiction_source"] == "system_default"
    assert att["compliance_basis"] == COMPLIANCE_BASIS_DEFAULT_FALLBACK


def test_jurisdiction_attribution_reuses_resolution():
    """When callers already resolved jurisdiction, attribution must honour _resolution (no double resolve)."""
    r = resolve_portfolio_jurisdiction({"jurisdiction": "Northern Ireland"}, {"default_jurisdiction": "Wales"})
    att = jurisdiction_attribution_for_property({}, {}, _resolution=r)
    assert att["jurisdiction_source"] == "property_record"
    assert att["effective_jurisdiction_label"] == "Northern Ireland"


def test_mixed_portfolio_properties_resolve_independently():
    client = {"default_jurisdiction": "England"}
    props = [
        {"property_id": "a", "jurisdiction": "Wales"},
        {"property_id": "b", "jurisdiction": "Scotland"},
        {"property_id": "c"},
    ]
    a = jurisdiction_attribution_for_property(props[0], client)
    b = jurisdiction_attribution_for_property(props[1], client)
    c = jurisdiction_attribution_for_property(props[2], client)
    assert a["effective_jurisdiction_label"] == "Wales"
    assert b["effective_jurisdiction_label"] == "Scotland"
    assert c["effective_jurisdiction_label"] == "England"
    assert a["jurisdiction_source"] == "property_record"
    assert b["jurisdiction_source"] == "property_record"
    assert c["jurisdiction_source"] == "account_default"


def test_dashboard_hard_notice_inactive_when_portfolio_only_uses_account_default():
    """Hard portfolio warning (default_fallback) must not activate when client default covers all properties."""
    client = {"default_jurisdiction": "Wales"}
    props = [{"property_id": "p1"}, {"property_id": "p2"}]
    n = build_jurisdiction_compliance_notice(client, props)
    assert n["active"] is False
    assert n.get("compliance_basis") != COMPLIANCE_BASIS_DEFAULT_FALLBACK


def test_onboarding_attestation_still_pressures_explicit_jurisdiction_despite_account_default():
    """Onboarding gate: any property without explicit jurisdiction on record stays flagged, even if account default exists."""
    att = build_portfolio_jurisdiction_attestation(
        {"default_jurisdiction": "Scotland"},
        [{"property_id": "needs_explicit"}, {"property_id": "ok", "jurisdiction": "England"}],
    )
    assert att["jurisdiction_required"] is True
    assert att["compliance_confidence"] == COMPLIANCE_CONFIDENCE_FALLBACK
    assert att["jurisdiction_required_property_ids"] == ["needs_explicit"]


def test_legacy_scotland_scoring_bucket_on_property_resolves_to_portfolio_scotland():
    r = resolve_portfolio_jurisdiction({"jurisdiction": "SCOTLAND"}, {"default_jurisdiction": "England"})
    assert r.effective_label == "Scotland"
    assert r.compliance_basis == COMPLIANCE_BASIS_PROPERTY_EXPLICIT


def test_legacy_england_wales_bucket_does_not_override_client_default():
    """ENGLAND_WALES on the property field is ambiguous; treat like missing label for resolution."""
    r = resolve_portfolio_jurisdiction({"jurisdiction": "ENGLAND_WALES"}, {"default_jurisdiction": "Wales"})
    assert r.effective_label == "Wales"
    assert r.compliance_basis == COMPLIANCE_BASIS_CLIENT_DEFAULT


def test_legacy_england_wales_bucket_still_flags_jurisdiction_required():
    f = property_jurisdiction_requirement_flags({"jurisdiction": "ENGLAND_WALES"})
    assert f["jurisdiction_required"] is True
    assert f["compliance_confidence"] == COMPLIANCE_CONFIDENCE_FALLBACK


def test_unique_property_jurisdictions_skips_england_wales_bucket_string():
    labels = unique_property_jurisdictions(
        [
            {"jurisdiction": "England"},
            {"jurisdiction": "ENGLAND_WALES"},
            {"jurisdiction": "SCOTLAND"},
        ]
    )
    assert labels == ["England", "Scotland"]


def test_legacy_england_wales_property_triggers_portfolio_default_fallback_notice():
    """Ambiguous legacy bucket without client default should surface default_fallback (same as unset)."""
    n = build_jurisdiction_compliance_notice(None, [{"property_id": "p1", "jurisdiction": "ENGLAND_WALES"}])
    assert n["active"] is True
    assert n["affected_property_ids"] == ["p1"]
