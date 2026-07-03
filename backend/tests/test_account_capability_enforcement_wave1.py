"""ILP-4 Phase 2B Wave 1 — capability enforcement for evidence, reports, documents."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from database import database as db_singleton
from middleware import client_route_guard as middleware_client_route_guard
from routes import client_compliance_evidence as evidence_routes
from routes import documents as documents_routes
from routes import reports as reports_routes
from server import app
from services.account_capability_enforcement import (
    CapabilityEnforcementService,
    CapabilityReasonCode,
)
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)

WAVE1_CLIENT_ID = "c-wave1-cap-1"


def _client(**overrides):
    base = {
        "client_id": WAVE1_CLIENT_ID,
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": WAVE1_CLIENT_ID,
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    base.update(overrides)
    return base


def _portal_user():
    return {
        "client_id": WAVE1_CLIENT_ID,
        "portal_user_id": "pu-wave1-1",
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


class _AsyncIter:
    def __init__(self, items):
        self._items = list(items)
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


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


def _mock_documents_list_db():
    mock_db = MagicMock()
    doc_cursor = MagicMock()
    doc_cursor.to_list = AsyncMock(return_value=[])
    mock_db.documents.find = MagicMock(return_value=MagicMock(sort=MagicMock(return_value=doc_cursor)))
    return mock_db


def _mock_reports_list_db():
    mock_db = MagicMock()
    report_cursor = _AsyncIter([])
    mock_db.reports.find = MagicMock(
        return_value=MagicMock(sort=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=report_cursor))))
    )
    return mock_db


def _mock_evidence_list_db():
    mock_db = MagicMock()
    mock_db.requirements.find_one = AsyncMock(return_value=None)
    return mock_db


def _mock_analyze_db(*, document_present: bool = False):
    mock_db = MagicMock()
    if document_present:
        mock_db.documents.find_one = AsyncMock(
            return_value={
                "document_id": "doc-missing",
                "client_id": WAVE1_CLIENT_ID,
                "file_path": "x.pdf",
                "mime_type": "application/pdf",
            }
        )
    else:
        mock_db.documents.find_one = AsyncMock(return_value=None)
    return mock_db


@pytest.fixture
def wave1_user():
    return _portal_user()


@pytest.fixture
def override_guard(wave1_user):
    async def _fake_guard(request: Request):
        return wave1_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestWave1EvidenceLifecycle:
    def test_evidence_read_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_EVIDENCE_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with (
            patch.object(db_singleton, "get_db", return_value=_mock_evidence_list_db()),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.get(
                "/api/client/properties/p-1/requirements/r-1/compliance-evidence"
            )

        if allowed:
            assert not _is_capability_denied(res)
            assert res.status_code == 404
        else:
            _assert_capability_denied(res, cap)

    def test_evidence_write_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REQ_RESOLVE"
        allowed = _expected_allowed(contract, cap, "write")

        with (
            patch.object(db_singleton, "get_db", return_value=_mock_evidence_list_db()),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.post(
                "/api/client/properties/p-1/requirements/r-1/compliance-evidence",
                json={"evidence_mode": "structured_declaration", "payload": {}},
            )

        if allowed:
            assert not _is_capability_denied(res)
            assert res.status_code == 404
        else:
            _assert_capability_denied(res, cap)


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestWave1ReportsLifecycle:
    def test_reports_view_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REPORT_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with (
            patch.object(db_singleton, "get_db", return_value=_mock_reports_list_db()),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.get("/api/reports/list")

        if allowed:
            assert res.status_code == 200
            assert "reports" in res.json()
        else:
            _assert_capability_denied(res, cap)

    def test_reports_csv_write_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REPORT_GENERATE_CSV"
        allowed = _expected_allowed(contract, cap, "write")

        mock_db = MagicMock()
        mock_db.clients.find_one = AsyncMock(return_value={"customer_reference": "CRN-1"})

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
            patch("routes.reports._enforce_report_export_rate", new=AsyncMock()),
            patch(
                "routes.reports.calculate_compliance_score",
                new=AsyncMock(return_value={"drivers": [], "score_status": "OK"}),
            ),
        ):
            res = client.get("/api/reports/score-drivers.csv")

        if allowed:
            assert not _is_capability_denied(res)
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_reports_schedule_read_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REPORT_SCHEDULE"
        allowed = _expected_allowed(contract, cap, "read")

        mock_db = MagicMock()
        sched_cursor = MagicMock()
        sched_cursor.to_list = AsyncMock(return_value=[])
        mock_db.report_schedules.find = MagicMock(return_value=sched_cursor)

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.get("/api/reports/schedules")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_reports_audit_log_read_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_AUDIT_LOG_EXPORT"
        allowed = _expected_allowed(contract, cap, "read")

        with (
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
            patch("routes.reports._enforce_report_export_rate", new=AsyncMock()),
            patch(
                "services.professional_reports.professional_report_generator.generate_audit_log_pdf",
                new=AsyncMock(return_value=iter([b"%PDF-1.4"])),
            ),
            patch("routes.reports.create_audit_log", new=AsyncMock()),
        ):
            res = client.get("/api/reports/professional/audit-log")

        if allowed:
            assert not _is_capability_denied(res)
        else:
            _assert_capability_denied(res, cap)


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestWave1DocumentsLifecycle:
    def test_documents_list_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_DOC_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with (
            patch.object(db_singleton, "get_db", return_value=_mock_documents_list_db()),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.get("/api/documents")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_documents_delete_write_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_DOC_UPLOAD"
        allowed = _expected_allowed(contract, cap, "write")

        mock_db = MagicMock()
        mock_db.documents.find_one = AsyncMock(return_value=None)

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.delete("/api/documents/doc-missing")

        if allowed:
            assert res.status_code == 404
        else:
            _assert_capability_denied(res, cap)

    def test_documents_details_read_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_DOC_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        mock_db = MagicMock()
        mock_db.documents.find_one = AsyncMock(return_value=None)

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.get("/api/documents/doc-missing/details")

        if allowed:
            assert res.status_code == 404
        else:
            _assert_capability_denied(res, cap)

    def test_documents_analyze_advanced_governed(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        view_allowed = _expected_allowed(contract, "CAP_DOC_VIEW", "read")
        advanced_allowed = _expected_allowed(contract, "CAP_AI_EXTRACTION_ADVANCED", "write")

        mock_db = _mock_analyze_db(document_present=view_allowed)
        if view_allowed:
            mock_db.clients.find_one = AsyncMock(return_value={"billing_plan": "PLAN_3_PRO"})

        with ExitStack() as stack:
            stack.enter_context(patch.object(db_singleton, "get_db", return_value=mock_db))
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if view_allowed and advanced_allowed:
                stack.enter_context(
                    patch(
                        "services.document_analysis.document_analysis_service.analyze_document",
                        new=AsyncMock(return_value={"success": False, "error": "test_skip"}),
                    )
                )
            res = client.post("/api/documents/analyze/doc-missing?return_advanced=true")

        if not view_allowed:
            _assert_capability_denied(res, "CAP_DOC_VIEW")
        elif not advanced_allowed:
            _assert_capability_denied(res, "CAP_AI_EXTRACTION_ADVANCED")
        else:
            assert not _is_capability_denied(res)


class TestWave1PlanGatedViaRuntimeContract:
    def test_solo_plan_blocks_csv_on_active(self, client, override_guard):
        contract = _contract(_client(billing_plan="PLAN_1_SOLO"), _billing())
        assert _expected_allowed(contract, "CAP_REPORT_GENERATE_CSV", "write") is False

        with patch(
            "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
            new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
        ):
            res = client.get("/api/reports/score-drivers.csv")
        _assert_capability_denied(res, "CAP_REPORT_GENERATE_CSV")
        assert res.json()["detail"]["error_code"] == CapabilityReasonCode.DENIED.value

    def test_solo_plan_blocks_advanced_analyze_on_active(self, client, override_guard):
        contract = _contract(_client(billing_plan="PLAN_1_SOLO"), _billing())
        mock_db = MagicMock()
        mock_db.documents.find_one = AsyncMock(
            return_value={
                "document_id": "doc-1",
                "client_id": WAVE1_CLIENT_ID,
                "file_path": "/tmp/x",
            }
        )

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
            ),
        ):
            res = client.post("/api/documents/analyze/doc-1?return_advanced=true")
        _assert_capability_denied(res, "CAP_AI_EXTRACTION_ADVANCED")


class TestWave1NoLegacyEnforcementInMigratedModules:
    def test_wave1_modules_have_no_enforce_feature(self):
        import inspect

        for module in (evidence_routes, reports_routes, documents_routes):
            source = inspect.getsource(module)
            assert "enforce_feature" not in source
            assert "require_feature" not in source

    def test_report_download_does_not_call_enforce_feature(self, client, override_guard):
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
            patch("routes.reports._enforce_report_export_rate", new=AsyncMock()),
        ):
            res = client.get("/api/reports/507f1f77bcf86cd799439011/download")
        mock_ef.assert_not_called()
        assert res.status_code == 404
