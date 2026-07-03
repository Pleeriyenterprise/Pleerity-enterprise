"""ILP-4 — evidence pack, analytics, and activity-since capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import client as client_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)

CLIENT_ID = "c-ilp4-epa-1"


def _client(**overrides):
    base = {
        "client_id": CLIENT_ID,
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": CLIENT_ID,
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    base.update(overrides)
    return base


def _portal_user():
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": "pu-ilp4-epa-1",
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


@pytest.fixture
def epa_user():
    return _portal_user()


@pytest.fixture
def override_guard(epa_user):
    async def _fake_guard(request: Request):
        return epa_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=epa_user)):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestEvidencePackAnalyticsSourceGovernance:
    def test_analytics_and_evidence_pack_blocks_no_enforce_feature(self):
        source = open(client_routes.__file__, encoding="utf-8").read()
        analytics_start = source.index('@router.get("/analytics/summary")')
        tasks_start = source.index('@router.post("/tasks/record-intent")')
        block = source[analytics_start:tasks_start]
        assert "enforce_feature" not in block
        assert 'client_require_capability("CAP_COMPLIANCE_ACTIVITY"' in block
        assert 'client_require_capability("CAP_REPORT_AUDIT_PACK"' in block


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestEvidencePackAnalyticsLifecycle:
    def test_analytics_summary_read(self, client, override_guard, lifecycle):
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
                        "services.product_analytics_service.summarize_client_events",
                        new=AsyncMock(return_value={"events": []}),
                    )
                )
            res = client.get("/api/client/analytics/summary")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_activity_since_read(self, client, override_guard, lifecycle):
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
                        "services.portal_activity_service.peek_activity_since_for_portal_user",
                        new=AsyncMock(return_value={"items": []}),
                    )
                )
            res = client.get("/api/client/activity-since")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_activity_since_acknowledge_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_COMPLIANCE_ACTIVITY"
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
                        "services.portal_activity_service.acknowledge_activity_cursor",
                        new=AsyncMock(return_value=NOW.isoformat()),
                    )
                )
            res = client.post("/api/client/activity-since/acknowledge")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_analytics_events_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_COMPLIANCE_ACTIVITY"
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
                        "utils.analytics_event_logger.record_portal_analytics_event",
                        new=AsyncMock(return_value=None),
                    )
                )
            res = client.post(
                "/api/client/analytics/events",
                json={"event": "dashboard_viewed", "path": "/dashboard"},
            )

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_evidence_pack_create_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REPORT_AUDIT_PACK"
        allowed = _expected_allowed(contract, cap, "write")

        mock_db = MagicMock()
        mock_db.compliance_evidence_pack_jobs.count_documents = AsyncMock(return_value=0)
        mock_db.clients.find_one = AsyncMock(return_value={"customer_reference": "CRN-1"})

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                from database import database as db_singleton

                stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
                stack.enter_context(
                    patch(
                        "services.evidence_pack_service.create_evidence_pack_job",
                        new=AsyncMock(return_value={"job_id": "job-1", "status": "completed"}),
                    )
                )
                stack.enter_context(
                    patch("utils.audit.create_audit_log", new=AsyncMock(return_value=None))
                )
            res = client.post("/api/client/evidence-pack/jobs", json={})

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_evidence_pack_list_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REPORT_AUDIT_PACK"
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
                        "services.evidence_pack_service.recent_jobs",
                        new=AsyncMock(return_value=[]),
                    )
                )
            res = client.get("/api/client/evidence-pack/jobs")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)

    def test_evidence_pack_download_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REPORT_AUDIT_PACK"
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
                        "services.evidence_pack_service.get_job",
                        new=AsyncMock(
                            return_value={
                                "status": "completed",
                                "gridfs_id": "gid-1",
                                "filename": "pack.zip",
                            }
                        ),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.evidence_pack_service.read_pack_bytes",
                        new=AsyncMock(return_value=b"PK"),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.product_analytics_service.record_event",
                        new=AsyncMock(return_value=None),
                    )
                )
            res = client.get("/api/client/evidence-pack/jobs/job-1/file")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)
