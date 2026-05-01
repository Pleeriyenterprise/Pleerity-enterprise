"""
Stream C — remediation correlation view v1 (service + route).

Run: pytest Pleerity-enterprise/backend/tests/test_remediation_correlation_view_v1.py -v --tb=short
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request

import routes.support as support_routes
from middleware import require_support_or_above
from server import app
from services import remediation_correlation_view as rcv


@pytest.fixture
def support_auth():
    """Bypass portal login; endpoint still requires support-or-above dependency."""

    async def _fake(request: Request):
        return {"email": "support@test.com", "portal_user_id": "test-support", "role": "ROLE_SUPPORT"}

    app.dependency_overrides[require_support_or_above] = _fake
    yield
    app.dependency_overrides.pop(require_support_or_above, None)


def _cursor(items):
    m = MagicMock()
    m.sort.return_value = m
    m.limit.return_value = m
    m.to_list = AsyncMock(return_value=items)
    return m


def test_feature_flag_env(monkeypatch):
    monkeypatch.delenv(rcv.FEATURE_ENV, raising=False)
    assert rcv.is_remediation_correlation_view_v1_enabled() is False
    monkeypatch.setenv(rcv.FEATURE_ENV, "1")
    assert rcv.is_remediation_correlation_view_v1_enabled() is True


@pytest.mark.asyncio
async def test_build_gap_anchor():
    db = MagicMock()
    gap = {
        "gap_key": "gk_test",
        "client_id": "cid1",
        "property_id": "pid1",
        "status": "open",
        "requirement_id": "req1",
        "gap_kind": "MISSING",
        "severity": "high",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
    db.compliance_gaps.find_one = AsyncMock(return_value=gap)
    db.maintenance_issues.find = MagicMock(return_value=_cursor([]))
    db.work_orders.find = MagicMock(return_value=_cursor([]))
    db.audit_logs.find = MagicMock(return_value=_cursor([]))
    db.property_compliance_score_history.find = MagicMock(return_value=_cursor([]))
    db.score_change_log.find = MagicMock(return_value=_cursor([]))

    out = await rcv.build_remediation_correlation_view(
        db,
        client_id="cid1",
        property_id="pid1",
        entry_kind="gap_key",
        entry_value="gk_test",
        window_half_days=7,
    )
    assert out["client_id"] == "cid1"
    assert out["property_id"] == "pid1"
    assert out["entry"] == {"kind": "gap_key", "value": "gk_test"}
    assert out["disclaimer"] == rcv.DISCLAIMER
    assert out.get("non_authoritative") is True
    assert len(out["rows"]) == 1
    row = out["rows"][0]
    assert row["remediation_key"] == "gk_test"
    assert row["source_system"] == "gap"
    assert row["linked_entities"]["gap_key"] == "gk_test"
    assert row["closure_semantics"]["inbox_visibility"] is False
    assert row["closure_semantics"]["compliance"] is False
    assert "supporting_reads" in out


@pytest.mark.asyncio
async def test_build_issue_bridge_gap_missing_flag():
    db = MagicMock()
    issue = {
        "issue_id": "iss1",
        "client_id": "cid1",
        "property_id": "pid1",
        "status": "open",
        "operational_root_key": "missing_gap_key",
        "created_at": "2026-01-01T00:00:00Z",
    }
    db.maintenance_issues.find_one = AsyncMock(return_value=issue)
    db.compliance_gaps.find_one = AsyncMock(return_value=None)
    db.work_orders.find = MagicMock(return_value=_cursor([]))
    db.audit_logs.find = MagicMock(return_value=_cursor([]))
    db.property_compliance_score_history.find = MagicMock(return_value=_cursor([]))
    db.score_change_log.find = MagicMock(return_value=_cursor([]))

    out = await rcv.build_remediation_correlation_view(
        db,
        client_id="cid1",
        property_id="pid1",
        entry_kind="issue_id",
        entry_value="iss1",
    )
    row = out["rows"][0]
    assert row["remediation_key"] == "issue:iss1"
    assert "bridge_gap_missing" in row["diagnostic_flags"]
    assert out.get("non_authoritative") is True


@pytest.mark.asyncio
async def test_score_change_log_advisory_only_when_mapping_signal():
    db = MagicMock()
    gap = {
        "gap_key": "gk2",
        "client_id": "cid1",
        "property_id": "pid1",
        "status": "open",
        "requirement_id": "req1",
        "gap_kind": "MISSING",
        "severity": "high",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
    db.compliance_gaps.find_one = AsyncMock(return_value=gap)
    db.maintenance_issues.find = MagicMock(return_value=_cursor([]))
    db.work_orders.find = MagicMock(return_value=_cursor([]))
    db.audit_logs.find = MagicMock(return_value=_cursor([]))
    db.property_compliance_score_history.find = MagicMock(return_value=_cursor([]))
    # Rows exist but no requirement-level mapping payload → no advisory
    db.score_change_log.find = MagicMock(
        return_value=_cursor([{"new_score": 80, "previous_score": 79, "created_at": "2026-01-05T00:00:00Z"}])
    )

    out = await rcv.build_remediation_correlation_view(
        db,
        client_id="cid1",
        property_id="pid1",
        entry_kind="gap_key",
        entry_value="gk2",
    )
    assert "score_change_log_present_mapping_advisory" not in out["rows"][0]["diagnostic_flags"]

    db.score_change_log.find = MagicMock(
        return_value=_cursor(
            [
                {
                    "changed_requirements": [{"requirement_key": "k1", "previous_status": "x", "new_status": "y"}],
                    "created_at": "2026-01-05T00:00:00Z",
                }
            ]
        )
    )
    out2 = await rcv.build_remediation_correlation_view(
        db,
        client_id="cid1",
        property_id="pid1",
        entry_kind="gap_key",
        entry_value="gk2",
    )
    assert "score_change_log_present_mapping_advisory" in out2["rows"][0]["diagnostic_flags"]


@pytest.mark.asyncio
async def test_build_lookup_error():
    db = MagicMock()
    db.compliance_gaps.find_one = AsyncMock(return_value=None)
    with pytest.raises(LookupError):
        await rcv.build_remediation_correlation_view(
            db,
            client_id="cid1",
            property_id="pid1",
            entry_kind="gap_key",
            entry_value="nope",
        )


@pytest.mark.asyncio
async def test_build_value_error_kind():
    db = MagicMock()
    with pytest.raises(ValueError):
        await rcv.build_remediation_correlation_view(
            db,
            client_id="cid1",
            property_id="pid1",
            entry_kind="requirement_id",
            entry_value="x",
        )


def test_http_disabled_without_flag(client, support_auth, monkeypatch):
    monkeypatch.delenv(rcv.FEATURE_ENV, raising=False)
    r = client.post(
        "/api/admin/support/remediation-correlation-view",
        json={
            "client_id": "client_corr_test",
            "property_id": "property_corr_test",
            "entry": {"kind": "gap_key", "value": "gap_corr_test"},
        },
    )
    assert r.status_code == 404


def test_http_requires_auth(client, monkeypatch):
    monkeypatch.setenv(rcv.FEATURE_ENV, "1")
    r = client.post(
        "/api/admin/support/remediation-correlation-view",
        json={
            "client_id": "client_corr_test",
            "property_id": "property_corr_test",
            "entry": {"kind": "gap_key", "value": "gap_corr_test"},
        },
    )
    assert r.status_code in (401, 403)


def test_http_validation(client, support_auth, monkeypatch):
    monkeypatch.setenv(rcv.FEATURE_ENV, "1")
    r = client.post(
        "/api/admin/support/remediation-correlation-view",
        json={"client_id": "", "property_id": "p", "entry": {"kind": "gap_key", "value": "g"}},
    )
    assert r.status_code == 422


def test_http_enabled_anchor_not_found(client, support_auth, monkeypatch):
    monkeypatch.setenv(rcv.FEATURE_ENV, "1")
    db = MagicMock()
    db.compliance_gaps.find_one = AsyncMock(return_value=None)
    with patch.object(support_routes.database, "get_db", return_value=db):
        r = client.post(
            "/api/admin/support/remediation-correlation-view",
            json={
                "client_id": "client_corr_anchor",
                "property_id": "property_corr_anchor",
                "entry": {"kind": "gap_key", "value": "gap_missing_xyz"},
            },
        )
    assert r.status_code == 404
