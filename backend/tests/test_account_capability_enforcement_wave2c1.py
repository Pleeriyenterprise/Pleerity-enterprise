"""ILP-4 Phase 2C-1 — capability enforcement for properties, portfolio, client score/requirement subset."""
from __future__ import annotations

import inspect
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from database import database as db_singleton
from middleware import client_route_guard as middleware_client_route_guard
from routes import client as client_routes
from routes import portfolio as portfolio_routes
from routes import properties as properties_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)

WAVE2C1_CLIENT_ID = "c-wave2c1-1"


def _client(**overrides):
    base = {
        "client_id": WAVE2C1_CLIENT_ID,
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": WAVE2C1_CLIENT_ID,
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    base.update(overrides)
    return base


def _portal_user():
    return {
        "client_id": WAVE2C1_CLIENT_ID,
        "portal_user_id": "pu-wave2c1-1",
        "role": "ROLE_CLIENT",
    }


def _contract(client=None, billing=None, **kwargs):
    return build_runtime_contract(
        client=client or _client(),
        billing=billing or _billing(),
        now=NOW,
        **kwargs,
    )


LIFECYCLE_PRESETS = {
    "ACTIVE": (_client(), _billing()),
    "TRIAL": (_client(), _billing(subscription_status="TRIALING")),
    "GRACE_PERIOD": (
        _client(),
        _billing(
            subscription_status="PAST_DUE",
            billing_lifecycle_state="grace_period",
            grace_period_ends_at=GRACE_END.isoformat(),
        ),
    ),
    "CANCELLATION_SCHEDULED": (
        _client(),
        _billing(
            subscription_status="ACTIVE",
            billing_lifecycle_state="cancel_at_period_end",
            cancel_at_period_end=True,
            current_period_end=PERIOD_END.isoformat(),
        ),
    ),
    "READ_ONLY": (
        _client(),
        _billing(
            subscription_status="UNPAID",
            billing_lifecycle_state="expired",
            read_only_retention=True,
        ),
    ),
    "CANCELLED_IMMEDIATE": (
        _client(),
        _billing(subscription_status="CANCELED", billing_lifecycle_state="cancelled"),
    ),
    "SUBSCRIPTION_EXPIRED": (
        _client(),
        _billing(
            subscription_status="UNPAID",
            billing_lifecycle_state="expired",
            canonical_entitlement_state="SUSPENDED",
        ),
    ),
    "SUSPENDED": (
        _client(client_lifecycle_status="SUSPENDED"),
        _billing(),
    ),
    "ARCHIVED": (
        _client(is_deleted=True, client_lifecycle_status="ARCHIVED"),
        _billing(),
    ),
    "UNKNOWN": (
        _client(),
        _billing(subscription_status="WEIRD", billing_lifecycle_state="active"),
    ),
}


def _mock_evaluate_contract(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


def _svc():
    return CapabilityEnforcementService(db=None)


def _expected_allowed(contract, cap_id: str, action: str) -> bool:
    return _svc().evaluate_from_contract(contract, cap_id, action).allowed


def _is_capability_denied(res) -> bool:
    if res.status_code != 403:
        return False
    detail = res.json().get("detail")
    return isinstance(detail, dict) and detail.get("error") == "capability_denied"


def _assert_capability_denied(res, cap_id: str):
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "capability_denied"
    assert detail["capability_id"] == cap_id


def _mock_properties_list_db():
    mock_db = MagicMock()
    prop_cursor = MagicMock()
    prop_cursor.to_list = AsyncMock(return_value=[])
    mock_db.properties.find = MagicMock(return_value=prop_cursor)
    req_cursor = MagicMock()
    req_cursor.to_list = AsyncMock(return_value=[])
    mock_db.requirements.find = MagicMock(return_value=req_cursor)
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": WAVE2C1_CLIENT_ID})
    return mock_db


def _mock_property_exists_db():
    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        return_value={"property_id": "p-1", "client_id": WAVE2C1_CLIENT_ID, "jurisdiction": "England"}
    )
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": WAVE2C1_CLIENT_ID})
    return mock_db


def _mock_score_history_db():
    mock_db = _mock_property_exists_db()
    hist_cursor = MagicMock()
    hist_cursor.to_list = AsyncMock(return_value=[])
    mock_db.score_change_log.find = MagicMock(
        return_value=MagicMock(sort=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=hist_cursor))))
    )
    return mock_db


def _mock_audit_timeline_db():
    mock_db = MagicMock()
    log_cursor = MagicMock()
    log_cursor.to_list = AsyncMock(return_value=[])
    mock_db.audit_logs.find = MagicMock(
        return_value=MagicMock(sort=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=log_cursor))))
    )
    return mock_db


@pytest.fixture
def wave2c1_user():
    return _portal_user()


@pytest.fixture
def override_guard(wave2c1_user):
    async def _fake_guard(request: Request):
        return wave2c1_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=wave2c1_user)):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestWave2C1RuntimeMatrixExtensions:
    def test_new_capabilities_present_in_contract(self):
        contract = _contract()
        caps = contract["capabilities"]
        for cap in (
            "CAP_PROP_ARCHIVE",
            "CAP_PROP_DELETE",
            "CAP_PROP_IMPORT",
            "CAP_REQ_MARK_N_A",
            "CAP_REQ_COMPLETE",
            "CAP_SCORE_EXPLAIN",
            "CAP_SCORE_TREND",
            "CAP_SCORE_SNAPSHOT",
            "CAP_COMPLIANCE_ACTIVITY",
        ):
            assert cap in caps, cap

    def test_mark_not_applicable_distinct_from_resolve(self):
        contract = _contract()
        na = _svc().evaluate_from_contract(contract, "CAP_REQ_MARK_N_A", "write")
        resolve = _svc().evaluate_from_contract(contract, "CAP_REQ_RESOLVE", "write")
        assert na.capability_id != resolve.capability_id
        assert na.allowed is True
        assert resolve.allowed is True


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestWave2C1PropertiesLifecycle:
    def test_prop_list_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_PROP_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(patch.object(db_singleton, "get_db", return_value=_mock_properties_list_db()))
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            stack.enter_context(
                patch(
                    "routes.properties.filter_requirement_rows_for_client_runtime_surfaces",
                    new=AsyncMock(side_effect=lambda _db, **kw: kw["requirements"]),
                )
            )
            res = client.get("/api/properties/list")

        if allowed:
            assert res.status_code == 200
            assert "properties" in res.json()
        else:
            _assert_capability_denied(res, cap)

    def test_prop_create_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_PROP_CREATE"
        allowed = _expected_allowed(contract, cap, "write")

        mock_db = MagicMock()
        mock_db.clients.find_one = AsyncMock(
            return_value={
                "client_id": WAVE2C1_CLIENT_ID,
                "onboarding_status": "PROVISIONED",
                "default_jurisdiction": "England",
            }
        )
        mock_db.properties.count_documents = AsyncMock(return_value=0)

        with ExitStack() as stack:
            stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.plan_registry.plan_registry.enforce_property_limit",
                        new=AsyncMock(return_value=(True, None, None)),
                    )
                )
                stack.enter_context(patch("routes.properties.create_audit_log", new=AsyncMock()))
                stack.enter_context(
                    patch(
                        "services.compliance_rules_registry.canonicalize_uk_portfolio_label",
                        return_value="England",
                    )
                )
                stack.enter_context(patch("routes.properties.Property", MagicMock()))
                stack.enter_context(patch.object(mock_db.properties, "insert_one", new=AsyncMock()))
            res = client.post(
                "/api/properties/create",
                json={
                    "address_line_1": "1 Test St",
                    "city": "London",
                    "postcode": "SW1A 1AA",
                },
            )

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_prop_edit_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_PROP_EDIT"
        allowed = _expected_allowed(contract, cap, "write")

        mock_db = MagicMock()
        mock_db.properties.find_one = AsyncMock(
            return_value={
                "property_id": "p-1",
                "client_id": WAVE2C1_CLIENT_ID,
                "is_active": True,
            }
        )
        mock_db.properties.update_one = AsyncMock()

        with ExitStack() as stack:
            stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.provisioning_status_hook.update_provisioning_status_for_property",
                        new=AsyncMock(),
                    )
                )
            res = client.patch("/api/properties/p-1", json={"nickname": "Updated"})

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_prop_archive_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        edit_cap = "CAP_PROP_EDIT"
        archive_cap = "CAP_PROP_ARCHIVE"
        edit_allowed = _expected_allowed(contract, edit_cap, "write")
        archive_allowed = _expected_allowed(contract, archive_cap, "write")

        mock_db = MagicMock()
        mock_db.properties.find_one = AsyncMock(
            return_value={
                "property_id": "p-1",
                "client_id": WAVE2C1_CLIENT_ID,
                "is_active": True,
            }
        )
        mock_db.properties.update_one = AsyncMock()

        with ExitStack() as stack:
            stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if edit_allowed and archive_allowed:
                stack.enter_context(
                    patch(
                        "services.provisioning_status_hook.update_provisioning_status_for_property",
                        new=AsyncMock(),
                    )
                )
            res = client.patch("/api/properties/p-1", json={"is_active": False})

        if not edit_allowed:
            _assert_capability_denied(res, edit_cap)
        elif not archive_allowed:
            _assert_capability_denied(res, archive_cap)
        else:
            assert not _is_capability_denied(res)

    def test_prop_import_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_PROP_IMPORT"
        allowed = _expected_allowed(contract, cap, "write")

        mock_db = MagicMock()
        mock_db.clients.find_one = AsyncMock(
            return_value={"client_id": WAVE2C1_CLIENT_ID, "onboarding_status": "PROVISIONED"}
        )
        mock_db.properties.count_documents = AsyncMock(return_value=0)

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.post(
                "/api/properties/bulk-import",
                json={
                    "properties": [
                        {
                            "address_line_1": "2 Test St",
                            "city": "London",
                            "postcode": "SW1A 2AA",
                        }
                    ]
                },
            )

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_req_view_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REQ_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        mock_db = _mock_property_exists_db()
        req_cursor = MagicMock()
        req_cursor.to_list = AsyncMock(return_value=[])
        mock_db.requirements.find = MagicMock(return_value=req_cursor)

        with ExitStack() as stack:
            stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            stack.enter_context(
                patch(
                    "routes.properties.filter_requirement_rows_for_client_runtime_surfaces",
                    new=AsyncMock(side_effect=lambda _db, **kw: kw["requirements"]),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.requirement_truth.enrich_requirements_for_client",
                        new=AsyncMock(return_value=([], {})),
                    )
                )
            res = client.get("/api/properties/p-1/requirements")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_req_mark_na_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REQ_MARK_N_A"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(patch.object(db_singleton, "get_db", return_value=_mock_property_exists_db()))
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.requirement_mark_not_applicable_catalog.mark_catalog_requirement_not_applicable_for_property",
                        new=AsyncMock(return_value=("r-1", "gas_safety", True)),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.requirement_mark_not_applicable_catalog.sync_audit_enqueue_after_catalog_not_applicable",
                        new=AsyncMock(),
                    )
                )
            res = client.post(
                "/api/properties/p-1/requirements/mark-not-applicable",
                json={"requirement_code": "gas_safety", "not_required_reason": "not_applicable"},
            )

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_req_resolve_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REQ_RESOLVE"
        allowed = _expected_allowed(contract, cap, "write")

        mock_db = MagicMock()
        mock_db.properties.find_one = AsyncMock(
            return_value={"property_id": "p-1", "client_id": WAVE2C1_CLIENT_ID}
        )
        mock_db.requirements.find_one = AsyncMock(return_value=None)

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.patch(
                "/api/properties/p-1/requirements/r-1",
                json={"confirmed_expiry_date": "2027-01-01"},
            )

        if allowed:
            assert res.status_code == 404
        else:
            _assert_capability_denied(res, cap)


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestWave2C1ClientScoreAndActivityLifecycle:
    def test_score_view_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_SCORE_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.client.calculate_compliance_score",
                        new=AsyncMock(return_value={"score": 80}),
                    )
                )
            res = client.get("/api/client/compliance-score")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_score_explain_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_SCORE_EXPLAIN"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.compliance_trending.get_score_change_explanation",
                        new=AsyncMock(return_value={"explanation": "ok"}),
                    )
                )
            res = client.get("/api/client/compliance-score/explanation")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_score_trend_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_SCORE_TREND"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.compliance_trending.get_score_trend",
                        new=AsyncMock(return_value={"points": []}),
                    )
                )
            res = client.get("/api/client/compliance-score/trend")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_score_snapshot_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_SCORE_SNAPSHOT"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.compliance_trending.capture_daily_snapshot",
                        new=AsyncMock(return_value={"captured": True}),
                    )
                )
            res = client.post("/api/client/compliance-score/snapshot")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_compliance_activity_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_COMPLIANCE_ACTIVITY"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.compliance_outcome_engine.list_activity",
                        new=AsyncMock(return_value={"items": []}),
                    )
                )
            res = client.get("/api/client/compliance/activity")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_client_mark_not_applicable_uses_cap_req_mark_n_a(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REQ_MARK_N_A"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(patch.object(db_singleton, "get_db", return_value=_mock_property_exists_db()))
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "services.requirement_mark_not_applicable_catalog.mark_catalog_requirement_not_applicable_for_property",
                        new=AsyncMock(return_value=("r-1", "gas_safety", True)),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.requirement_mark_not_applicable_catalog.sync_audit_enqueue_after_catalog_not_applicable",
                        new=AsyncMock(),
                    )
                )
            res = client.post(
                "/api/client/properties/p-1/requirements/mark-not-applicable",
                json={"requirement_code": "gas_safety", "not_required_reason": "not_applicable"},
            )

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestWave2C1PortfolioLifecycle:
    def test_score_history_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_SCORE_TREND"
        allowed = _expected_allowed(contract, cap, "read")

        with (
            patch.object(db_singleton, "get_db", return_value=_mock_score_history_db()),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.get("/api/portfolio/properties/p-1/score-history")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_audit_timeline_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_COMPLIANCE_ACTIVITY"
        allowed = _expected_allowed(contract, cap, "read")

        with (
            patch.object(db_singleton, "get_db", return_value=_mock_audit_timeline_db()),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.get("/api/portfolio/audit-timeline")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_compliance_summary_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_SCORE_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        headline = {
            "portfolio_score": 80,
            "risk_level": "LOW",
            "properties": [],
            "properties_by_id": {},
            "score_status": "OK",
        }

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(patch.object(db_singleton, "get_db", return_value=MagicMock()))
                stack.enter_context(
                    patch(
                        "routes.portfolio.get_persisted_portfolio_headline_for_summary",
                        new=AsyncMock(return_value=headline),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
                        new=AsyncMock(
                            return_value={
                                "by_kind": {},
                                "by_severity": {},
                                "total_open": 0,
                                "policy": {"total_open": 0},
                            }
                        ),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.portfolio.get_portfolio_compliance_from_catalog",
                        new=AsyncMock(return_value=None),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.portfolio.build_portfolio_override_outputs",
                        new=AsyncMock(
                            return_value={
                                "effective_override_output": {
                                    "effective_portfolio_risk_state": "LOW",
                                    "base_portfolio_risk_state": "LOW",
                                    "risk_override_reasons": [],
                                    "critical_property_count": 0,
                                    "high_risk_gap_count": 0,
                                    "unknown_or_stale_property_count": 0,
                                    "attention_required": False,
                                    "critical_property_escalation": False,
                                    "suppress_positive_headline": False,
                                },
                                "legacy_override_output": {},
                                "policy_override_output": {},
                            }
                        ),
                    )
                )
            res = client.get("/api/portfolio/compliance-summary")

        if allowed:
            assert not _is_capability_denied(res)
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)


class TestWave2C1NoLegacyEnforcementInMigratedModules:
    def test_properties_and_portfolio_have_no_enforce_feature(self):
        for module in (properties_routes, portfolio_routes):
            source = inspect.getsource(module)
            assert "enforce_feature" not in source
            assert "require_feature" not in source
            assert "client_route_guard" not in source

    def test_migrated_client_routes_use_capability_deps(self):
        source = inspect.getsource(client_routes)
        assert 'client_require_capability("CAP_REQ_MARK_N_A"' in source
        assert 'client_require_capability("CAP_SCORE_EXPLAIN"' in source
        assert 'client_require_capability("CAP_SCORE_SNAPSHOT"' in source
        assert 'client_require_capability("CAP_COMPLIANCE_ACTIVITY"' in source
