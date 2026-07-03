"""ILP-4 Phase 2A — pilot route capability enforcement."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from database import database as db_singleton
from middleware import client_route_guard as middleware_client_route_guard
from middleware.capability_gating import capability_denied_http_detail
from routes import client as client_routes
from routes import documents as documents_routes
from routes import reports as reports_routes
from server import app
from services.account_capability_enforcement import (
    GRANT_DENY,
    GRANT_HIDDEN,
    GRANT_READ,
    CapabilityDecision,
    CapabilityEnforcementService,
    CapabilityReasonCode,
)
from services.account_lifecycle_runtime_contract import build_runtime_contract
from services.capability_compatibility import evaluate_feature_via_capability

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

PILOT_CLIENT_ID = "c-pilot-cap-1"


def _client(**overrides):
    base = {
        "client_id": PILOT_CLIENT_ID,
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": PILOT_CLIENT_ID,
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    base.update(overrides)
    return base


def _portal_user():
    return {
        "client_id": PILOT_CLIENT_ID,
        "portal_user_id": "pu-pilot-1",
        "role": "ROLE_CLIENT",
    }


def _contract(**kwargs):
    return build_runtime_contract(client=_client(), billing=_billing(), now=NOW, **kwargs)


def _decision_from_contract(contract, cap_id: str, action: str, *, allowed: bool | None = None):
    svc = CapabilityEnforcementService(db=None)
    decision = svc.evaluate_from_contract(contract, cap_id, action)
    if allowed is not None:
        assert decision.allowed is allowed, (cap_id, action, decision.reason_code)
    return decision


@pytest.fixture
def pilot_user():
    return _portal_user()


@pytest.fixture
def override_guard(pilot_user):
    async def _fake_guard(request: Request):
        return pilot_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with (
        patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=pilot_user)),
        patch.object(reports_routes, "client_route_guard", new=AsyncMock(return_value=pilot_user)),
        patch.object(documents_routes, "client_route_guard", new=AsyncMock(return_value=pilot_user)),
    ):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


def _mock_evaluate_contract(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


class TestCapabilityDeniedPayload:
    def test_http_detail_is_governed_safe(self):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="UNPAID",
                billing_lifecycle_state="expired",
                read_only_retention=True,
            ),
            now=NOW,
        )
        decision = _decision_from_contract(contract, "CAP_PROP_VIEW", "write", allowed=False)
        detail = capability_denied_http_detail(decision)
        assert detail["error"] == "capability_denied"
        assert detail["error_code"] == CapabilityReasonCode.READ_ONLY_BLOCKED.value
        assert detail["capability_id"] == "CAP_PROP_VIEW"
        assert detail["action"] == "write"
        assert detail["grant"] == GRANT_READ
        assert detail["effective_semantic"] == "READ_ONLY"
        assert "message" in detail
        assert detail["recovery"] is not None
        assert detail["recovery"]["route"] == "/settings/billing"

    def test_hidden_denial_payload(self):
        decision = CapabilityDecision(
            capability_id="CAP_SCORE_EXPLAIN",
            action="read",
            grant=GRANT_HIDDEN,
            effective_semantic=GRANT_HIDDEN,
            allowed=False,
            source="runtime_contract",
            reason_code=CapabilityReasonCode.UNKNOWN_CAPABILITY.value,
            reason="Catalog gap.",
            lifecycle_state="ACTIVE",
            portal_mode="FULL_ACCESS",
        )
        detail = capability_denied_http_detail(decision)
        assert detail["error_code"] == CapabilityReasonCode.UNKNOWN_CAPABILITY.value
        assert detail["grant"] == GRANT_HIDDEN


class TestPilotRouteEnforcement:
    def test_active_properties_read_allowed(self, client, override_guard):
        contract = _contract()
        mock_db = MagicMock()
        prop_cursor = MagicMock()
        prop_cursor.to_list = AsyncMock(return_value=[])
        mock_db.properties.find = MagicMock(return_value=prop_cursor)
        mock_db.clients.find_one = AsyncMock(return_value={"client_id": PILOT_CLIENT_ID})

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
            patch(
                "services.property_compliance_status_service.attach_live_compliance_status_to_properties",
                AsyncMock(side_effect=lambda _db, **kw: kw["properties"]),
            ),
        ):
            res = client.get("/api/client/properties")
        assert res.status_code == 200
        assert "properties" in res.json()

    def test_read_only_blocks_mark_not_applicable(self, client, override_guard):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="UNPAID",
                billing_lifecycle_state="expired",
                read_only_retention=True,
            ),
            now=NOW,
        )
        with patch(
            "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
            new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
        ):
            res = client.post(
                "/api/client/properties/p-1/requirements/mark-not-applicable",
                json={"requirement_code": "gas_safety", "not_required_reason": "not_applicable"},
            )
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert detail["error"] == "capability_denied"
        assert detail["capability_id"] == "CAP_REQ_RESOLVE"
        assert detail["error_code"] == CapabilityReasonCode.DENIED.value

    def test_read_only_allows_properties_list(self, client, override_guard):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="UNPAID",
                billing_lifecycle_state="expired",
                read_only_retention=True,
            ),
            now=NOW,
        )
        mock_db = MagicMock()
        prop_cursor = MagicMock()
        prop_cursor.to_list = AsyncMock(return_value=[])
        mock_db.properties.find = MagicMock(return_value=prop_cursor)
        mock_db.clients.find_one = AsyncMock(return_value={"client_id": PILOT_CLIENT_ID})

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
            patch(
                "services.property_compliance_status_service.attach_live_compliance_status_to_properties",
                AsyncMock(side_effect=lambda _db, **kw: kw["properties"]),
            ),
        ):
            res = client.get("/api/client/properties")
        assert res.status_code == 200

    def test_suspended_blocks_documents_list(self, client, override_guard):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="SUSPENDED",
                billing_lifecycle_state="suspended",
                canonical_entitlement_state="SUSPENDED",
            ),
            now=NOW,
        )
        with patch(
            "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
            new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
        ):
            res = client.get("/api/documents")
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert detail["error"] == "capability_denied"
        assert detail["capability_id"] == "CAP_DOC_VIEW"
        assert detail["error_code"] == CapabilityReasonCode.DENIED.value
        assert detail["grant"] == GRANT_DENY

    def test_cancelled_blocks_mark_not_applicable(self, client, override_guard):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="CANCELED",
                billing_lifecycle_state="cancelled",
            ),
            now=NOW,
        )
        with patch(
            "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
            new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
        ):
            res = client.post(
                "/api/client/properties/p-1/requirements/mark-not-applicable",
                json={"requirement_code": "gas_safety", "not_required_reason": "not_applicable"},
            )
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert detail["capability_id"] == "CAP_REQ_RESOLVE"
        assert detail["error"] == "capability_denied"
        assert detail["lifecycle_state"] == "CANCELLED_IMMEDIATE"

    def test_unknown_capability_returns_hidden_safe_payload(self, client, override_guard):
        svc = CapabilityEnforcementService(db=None)

        async def _doc_unknown(client_id, capability_id, action, *, contract=None):
            if capability_id == "CAP_DOC_VIEW":
                return svc.evaluate_from_contract(_contract(), "CAP_SCORE_EXPLAIN", action)
            return svc.evaluate_from_contract(_contract(), capability_id, action)

        with patch(
            "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
            new=AsyncMock(side_effect=_doc_unknown),
        ):
            res = client.get("/api/documents")
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert detail["error_code"] == CapabilityReasonCode.UNKNOWN_CAPABILITY.value
        assert detail["grant"] == GRANT_HIDDEN


class TestLegacyEnforceFeatureCompatibility:
    @pytest.mark.asyncio
    async def test_non_pilot_route_still_uses_enforce_feature(self):
        contract = build_runtime_contract(
            client=_client(billing_plan="PLAN_1_SOLO"),
            billing=_billing(),
            now=NOW,
        )
        svc = CapabilityEnforcementService(db=None)
        decision = await evaluate_feature_via_capability(
            svc, PILOT_CLIENT_ID, "reports_pdf", "write", contract=contract
        )
        assert decision.allowed is False

    def test_report_download_no_longer_calls_enforce_feature(self, client, override_guard):
        """Pilot download uses CAP_REPORT_DOWNLOAD only — enforce_feature must not gate this path."""
        contract = _contract()
        mock_db = MagicMock()
        mock_db.reports.find_one = AsyncMock(return_value=None)

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
            patch("services.plan_registry.plan_registry.enforce_feature", new=AsyncMock()) as mock_ef,
            patch(
                "routes.reports._enforce_report_export_rate",
                new=AsyncMock(),
            ),
        ):
            res = client.get("/api/reports/507f1f77bcf86cd799439011/download")
        mock_ef.assert_not_called()
        assert res.status_code == 404
