"""Phase 4 — billing recovery state machine, orchestration, bulk safety."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from services.billing_recovery_state_machine import (
    STATE_CHECKOUT_REGENERATED,
    STATE_CUSTOMER_PENDING,
    STATE_MODE_UNVERIFIED,
    STATE_RECOVERY_REQUIRED,
    STATE_RECOVERY_RESOLVED,
    BillingRecoveryTransitionError,
    can_transition,
    initial_recovery_state,
    transition_recovery_state,
)
from services.billing_recovery_service import (
    BULK_MAX_BATCH,
    build_recovery_dashboard,
    bulk_resend_continuation,
)


def test_initial_state_mode_unverified():
    assert initial_recovery_state(verification_status="MODE_UNVERIFIED") == STATE_MODE_UNVERIFIED


def test_initial_state_recovery_required():
    assert initial_recovery_state(verification_status=None) == "RECOVERY_REQUIRED"


def test_transition_idempotent():
    new_state, record = transition_recovery_state(
        STATE_MODE_UNVERIFIED,
        STATE_MODE_UNVERIFIED,
        action="noop",
        actor_id="admin@test",
    )
    assert new_state == STATE_MODE_UNVERIFIED
    assert record["idempotent"] is True


def test_transition_allowed_path():
    new_state, record = transition_recovery_state(
        STATE_MODE_UNVERIFIED,
        "RECOVERY_REQUIRED",
        action="open",
        actor_id="admin@test",
    )
    assert new_state == "RECOVERY_REQUIRED"
    assert record["idempotent"] is False


def test_transition_forbidden():
    with pytest.raises(BillingRecoveryTransitionError):
        transition_recovery_state(
            STATE_RECOVERY_RESOLVED,
            STATE_MODE_UNVERIFIED,
            action="illegal",
            actor_id="admin@test",
        )


def test_checkout_regenerated_to_customer_pending():
    assert can_transition(STATE_CHECKOUT_REGENERATED, STATE_CUSTOMER_PENDING)


@pytest.mark.asyncio
async def test_bulk_resend_preview():
    mock_db = MagicMock()
    mock_db.billing_recovery_audit.insert_one = AsyncMock()
    mock_db.billing_recovery_metrics.update_one = AsyncMock()
    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.billing_recovery_service.create_audit_log", new=AsyncMock()):
            result = await bulk_resend_continuation(
                ["c1", "c2"],
                actor_id="admin@test",
                preview=True,
            )
    assert result["preview"] is True
    assert len(result["results"]) == 2
    assert result["results"][0]["preview"] is True


@pytest.mark.asyncio
async def test_bulk_resend_batch_limit():
    ids = [f"c{i}" for i in range(BULK_MAX_BATCH + 1)]
    with pytest.raises(ValueError, match="Batch limit"):
        await bulk_resend_continuation(ids, actor_id="admin@test", preview=True)


@pytest.mark.asyncio
async def test_regenerate_supersedes_pending_checkouts():
    from services.billing_recovery_service import regenerate_checkout_for_recovery

    mock_db = MagicMock()
    mock_db.checkout_sessions.update_many = AsyncMock(return_value=MagicMock(modified_count=2))
    mock_db.billing_recovery_cases.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "recovery_state": STATE_MODE_UNVERIFIED,
            "remediation_code": "MODE_UNVERIFIED",
            "operational_risk": "high",
            "recommended_action": "REGENERATE_CHECKOUT_REQUIRED",
        }
    )
    mock_db.billing_recovery_cases.update_one = AsyncMock()
    mock_db.billing_recovery_cases.insert_one = AsyncMock()
    mock_db.billing_recovery_audit.insert_one = AsyncMock()
    mock_db.billing_recovery_metrics.update_one = AsyncMock()
    mock_db.client_billing.find_one = AsyncMock(
        return_value={"client_id": "c1", "stripe_mode_verification_status": "MODE_UNVERIFIED"}
    )
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "a@b.com"})
    mock_db.stripe_events.find_one = AsyncMock(return_value=None)
    mock_db.checkout_sessions.find_one = AsyncMock(return_value=None)

    mock_stripe = MagicMock()
    mock_stripe.create_checkout_session = AsyncMock(
        return_value={"session_id": "cs_test", "checkout_url": "https://checkout.example"}
    )
    mock_stripe.create_upgrade_session = AsyncMock()

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.billing_recovery_service.create_audit_log", new=AsyncMock()):
            with patch("services.billing_recovery_service.resolve_stripe_context", new=AsyncMock()):
                with patch(
                    "services.billing_recovery_service._get_or_create_case",
                    new=AsyncMock(
                        return_value={
                            "client_id": "c1",
                            "recovery_state": STATE_MODE_UNVERIFIED,
                            "remediation_code": "MODE_UNVERIFIED",
                        }
                    ),
                ):
                    with patch("services.stripe_service.StripeService", return_value=mock_stripe):
                        with patch(
                            "services.billing_recovery_service.transition_case",
                            new=AsyncMock(side_effect=lambda cid, **kw: {"recovery_state": kw["target_state"]}),
                        ):
                            result = await regenerate_checkout_for_recovery(
                                "c1",
                                plan_code="PLAN_2_PORTFOLIO",
                                actor_id="admin@test",
                                origin_url="https://app.example/admin/billing",
                                send_email=False,
                            )
    mock_db.checkout_sessions.update_many.assert_awaited()
    assert result["checkout"]["session_id"] == "cs_test"
    mock_stripe.create_checkout_session.assert_awaited_once()
    mock_stripe.create_upgrade_session.assert_not_awaited()


@pytest.mark.asyncio
async def test_regenerate_prepares_state_before_stripe_side_effects():
    from services.billing_recovery_service import regenerate_checkout_for_recovery

    mock_db = MagicMock()
    mock_db.checkout_sessions.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.billing_recovery_cases.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "recovery_state": STATE_MODE_UNVERIFIED,
            "remediation_code": "MODE_UNVERIFIED",
            "operational_risk": "high",
            "recommended_action": "REGENERATE_CHECKOUT_REQUIRED",
        }
    )
    mock_db.billing_recovery_cases.update_one = AsyncMock()
    mock_db.billing_recovery_cases.insert_one = AsyncMock()
    mock_db.billing_recovery_audit.insert_one = AsyncMock()
    mock_db.billing_recovery_metrics.update_one = AsyncMock()
    mock_db.client_billing.find_one = AsyncMock(
        return_value={"client_id": "c1", "stripe_mode_verification_status": "MODE_UNVERIFIED"}
    )
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "a@b.com"})
    mock_db.stripe_events.find_one = AsyncMock(return_value=None)
    mock_db.checkout_sessions.find_one = AsyncMock(return_value=None)

    mock_stripe = MagicMock()
    mock_stripe.create_checkout_session = AsyncMock(
        return_value={"session_id": "cs_test", "checkout_url": "https://checkout.example"}
    )

    call_states = []

    async def _fake_transition_case(client_id, **kw):
        call_states.append(kw["target_state"])
        return {"recovery_state": kw["target_state"]}

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.billing_recovery_service.create_audit_log", new=AsyncMock()):
            with patch("services.billing_recovery_service.resolve_stripe_context", new=AsyncMock()):
                with patch(
                    "services.billing_recovery_service._get_or_create_case",
                    new=AsyncMock(
                        return_value={
                            "client_id": "c1",
                            "recovery_state": STATE_MODE_UNVERIFIED,
                            "remediation_code": "MODE_UNVERIFIED",
                        }
                    ),
                ):
                    with patch("services.stripe_service.StripeService", return_value=mock_stripe):
                        with patch(
                            "services.billing_recovery_service.transition_case",
                            new=AsyncMock(side_effect=_fake_transition_case),
                        ):
                            await regenerate_checkout_for_recovery(
                                "c1",
                                plan_code="PLAN_2_PORTFOLIO",
                                actor_id="admin@test",
                                origin_url="https://app.example/admin/billing",
                                send_email=False,
                            )

    assert call_states[0] == "RECOVERY_REQUIRED"
    assert call_states[1] == STATE_CHECKOUT_REGENERATED
    assert call_states[2] == STATE_CUSTOMER_PENDING


@pytest.mark.asyncio
async def test_regenerate_mode_unverified_billing_row_uses_deployment_checkout():
    """Reproduces staging 500: upgrade preflight on MODE_UNVERIFIED must use deployment Checkout."""
    from services.billing_recovery_service import regenerate_checkout_for_recovery

    mock_db = MagicMock()
    mock_db.checkout_sessions.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.billing_recovery_cases.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "recovery_state": STATE_RECOVERY_REQUIRED,
            "remediation_code": "MODE_UNVERIFIED",
        }
    )
    mock_db.billing_recovery_cases.update_one = AsyncMock()
    mock_db.billing_recovery_cases.insert_one = AsyncMock()
    mock_db.billing_recovery_audit.insert_one = AsyncMock()
    mock_db.billing_recovery_metrics.update_one = AsyncMock()
    mock_db.client_billing.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "stripe_mode_verification_status": "MODE_UNVERIFIED",
            "stripe_subscription_id": "sub_test_legacy",
            "stripe_customer_id": "cus_test_legacy",
        }
    )
    mock_db.clients.find_one = AsyncMock(
        return_value={"client_id": "c1", "email": "client@example.com", "customer_reference": "CRN-TEST"}
    )

    mock_stripe = MagicMock()
    mock_stripe.create_checkout_session = AsyncMock(
        return_value={"session_id": "cs_recovery", "checkout_url": "https://checkout.example/recovery"}
    )
    mock_stripe.create_upgrade_session = AsyncMock(
        side_effect=Exception("upgrade preflight should not run")
    )

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.billing_recovery_service.create_audit_log", new=AsyncMock()):
            with patch("services.billing_recovery_service.resolve_stripe_context", new=AsyncMock()):
                with patch(
                    "services.billing_recovery_service._get_or_create_case",
                    new=AsyncMock(
                        return_value={
                            "client_id": "c1",
                            "recovery_state": STATE_RECOVERY_REQUIRED,
                            "remediation_code": "MODE_UNVERIFIED",
                        }
                    ),
                ):
                    with patch("services.stripe_service.StripeService", return_value=mock_stripe):
                        with patch(
                            "services.billing_recovery_service.transition_case",
                            new=AsyncMock(side_effect=lambda cid, **kw: {"recovery_state": kw["target_state"]}),
                        ):
                            result = await regenerate_checkout_for_recovery(
                                "c1",
                                plan_code="PLAN_2_PORTFOLIO",
                                actor_id="admin@test",
                                origin_url="https://app.example/admin/billing",
                                send_email=False,
                            )

    mock_stripe.create_checkout_session.assert_awaited_once()
    mock_stripe.create_upgrade_session.assert_not_awaited()
    assert result["checkout"]["session_id"] == "cs_recovery"
    assert result["checkout"]["regeneration_path"] == "deployment_checkout"


@pytest.mark.asyncio
async def test_continuation_email_rate_limit_blocks_at_three():
    from services.billing_recovery_service import _send_continuation_email

    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "client@example.com"})
    mock_audit_collection = MagicMock()
    mock_audit_collection.count_documents = AsyncMock(return_value=3)
    mock_db.__getitem__.return_value = mock_audit_collection

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.notification_orchestrator.notification_orchestrator.send", new=AsyncMock()) as send_mock:
            result = await _send_continuation_email(
                "c1",
                "https://checkout.example",
                actor_id="admin@test",
            )

    assert result["sent"] is False
    assert result["reason"] == "rate_limited"
    send_mock.assert_not_called()


class _AsyncCursor:
    def __init__(self, rows):
        self._rows = rows
        self._limit = None

    def limit(self, n):
        self._limit = n
        return self

    def sort(self, *_args, **_kwargs):
        return self

    def __aiter__(self):
        rows = self._rows[: self._limit] if self._limit is not None else self._rows

        async def _gen():
            for r in rows:
                yield r

        return _gen()


def _wire_recovery_collections(mock_db, *, remediated_rows=None, active_count=0, metrics_doc=None):
    case_col = MagicMock()
    case_col.find.return_value = _AsyncCursor(remediated_rows or [])
    case_col.count_documents = AsyncMock(return_value=active_count)
    metrics_col = MagicMock()
    metrics_col.find_one = AsyncMock(return_value=metrics_doc)
    mapping = {
        "billing_recovery_cases": case_col,
        "billing_recovery_metrics": metrics_col,
    }
    mock_db.__getitem__.side_effect = lambda name: mapping[name]


@pytest.mark.asyncio
async def test_dashboard_empty_data_safe():
    mock_db = MagicMock()
    mock_db.client_billing.find.return_value = _AsyncCursor([])
    _wire_recovery_collections(mock_db, remediated_rows=[], active_count=0, metrics_doc=None)

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_mode_authority.get_stripe_mode", return_value="test"):
            with patch(
                "services.billing_recovery_service.classify_orphaned_checkout_sessions",
                new=AsyncMock(return_value={"summary": {}, "categories": {"requires_regeneration": []}}),
            ):
                payload = await build_recovery_dashboard(limit=20)

    assert payload["summary"]["mode_unverified_clients"] == 0
    assert payload["summary"]["pending_regeneration"] == 0
    assert payload["deployment_mode"] == "test"


@pytest.mark.asyncio
async def test_dashboard_mode_unverified_and_missing_optionals():
    mock_db = MagicMock()
    mock_db.client_billing.find.return_value = _AsyncCursor([{"client_id": "client_12345678"}])
    _wire_recovery_collections(
        mock_db,
        remediated_rows=[],
        active_count=1,
        metrics_doc={"events": {"recovery_started": 2}},
    )

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_mode_authority.get_stripe_mode", return_value="live"):
            with patch(
                "services.billing_recovery_service._get_or_create_case",
                new=AsyncMock(
                    return_value={
                        "client_id": "client_12345678",
                        "recovery_state": "MODE_UNVERIFIED",
                        "remediation_code": "MODE_UNVERIFIED",
                        "operational_risk": "high",
                        "recommended_action": "REGENERATE_CHECKOUT_REQUIRED",
                        "escalation_state": "normal",
                        "last_recovery_action": "case_opened",
                    }
                ),
            ):
                with patch(
                    "services.billing_recovery_service._enrich_case_row",
                    new=AsyncMock(
                        return_value={
                            "client_id": "client_12345678",
                            "client_label": "client_12",
                            "crn": None,
                            "remediation_code": "MODE_UNVERIFIED",
                            "operational_risk": "high",
                            "billing_status": None,
                            "entitlement_status": None,
                            "recommended_action": "REGENERATE_CHECKOUT_REQUIRED",
                            "recovery_state": "MODE_UNVERIFIED",
                            "owner": None,
                            "assigned_at": None,
                            "escalation_state": "normal",
                            "last_checkout": None,
                            "last_webhook": None,
                            "last_recovery_action": "case_opened",
                            "recovery_age_days": 0,
                            "customer_safe_message": "Your billing access needs to be refreshed.",
                        }
                    ),
                ):
                    with patch(
                        "services.billing_recovery_service.classify_orphaned_checkout_sessions",
                        new=AsyncMock(return_value={"summary": {"requires_regeneration": 0}, "categories": {"requires_regeneration": []}}),
                    ):
                        payload = await build_recovery_dashboard(limit=20)

    assert payload["summary"]["mode_unverified_clients"] == 1
    assert payload["summary"]["pending_regeneration"] == 1
    assert payload["sections"]["drift_metrics_summary"][0]["metrics"]["recovery_started"] == 2


@pytest.mark.asyncio
async def test_dashboard_includes_orphaned_checkout_categories():
    mock_db = MagicMock()
    mock_db.client_billing.find.return_value = _AsyncCursor([])
    _wire_recovery_collections(mock_db, remediated_rows=[], active_count=0, metrics_doc=None)

    orphan_rows = [
        {"session_id_redacted": "cs_xxx", "classification": "requires_regeneration"},
        {"session_id_redacted": "cs_yyy", "classification": "requires_regeneration"},
    ]
    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_mode_authority.get_stripe_mode", return_value="test"):
            with patch(
                "services.billing_recovery_service.classify_orphaned_checkout_sessions",
                new=AsyncMock(return_value={"summary": {"requires_regeneration": 2}, "categories": {"requires_regeneration": orphan_rows}}),
            ):
                payload = await build_recovery_dashboard(limit=20)

    assert len(payload["sections"]["orphaned_checkout_sessions"]) == 2
    assert payload["sections"]["drift_metrics_summary"][0]["orphaned_checkout_count"] == 2


@pytest.mark.asyncio
async def test_dashboard_serialization_safety_generated_at_iso():
    mock_db = MagicMock()
    mock_db.client_billing.find.return_value = _AsyncCursor([])
    _wire_recovery_collections(mock_db, remediated_rows=[], active_count=0, metrics_doc=None)
    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_mode_authority.get_stripe_mode", return_value="test"):
            with patch(
                "services.billing_recovery_service.classify_orphaned_checkout_sessions",
                new=AsyncMock(return_value={"summary": {}, "categories": {"requires_regeneration": []}}),
            ):
                payload = await build_recovery_dashboard(limit=20)
    # verify top-level runtime payload remains JSON-safe
    assert "T" in payload["generated_at"]
    assert payload["generated_at"].endswith("+00:00")


@pytest.mark.asyncio
async def test_dashboard_legacy_objectid_client_id_shape_no_500():
    legacy_client_id = ObjectId()
    mock_db = MagicMock()
    mock_db.client_billing.find.return_value = _AsyncCursor([{"client_id": legacy_client_id}])
    _wire_recovery_collections(mock_db, remediated_rows=[], active_count=1, metrics_doc=None)

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_mode_authority.get_stripe_mode", return_value="test"):
            with patch(
                "services.billing_recovery_service._get_or_create_case",
                new=AsyncMock(
                    return_value={
                        "client_id": legacy_client_id,
                        "recovery_state": "MODE_UNVERIFIED",
                        "recommended_action": "REGENERATE_CHECKOUT_REQUIRED",
                    }
                ),
            ):
                mock_db.client_billing.find_one = AsyncMock(
                    return_value={"client_id": legacy_client_id, "stripe_subscription_id": None}
                )
                mock_db.clients.find_one = AsyncMock(return_value={})
                mock_db.stripe_events.find_one = AsyncMock(return_value=None)
                mock_db.checkout_sessions.find_one = AsyncMock(return_value=None)
                with patch(
                    "services.billing_recovery_service.classify_orphaned_checkout_sessions",
                    new=AsyncMock(return_value={"summary": {}, "categories": {"requires_regeneration": []}}),
                ):
                    payload = await build_recovery_dashboard(limit=20)

    row = payload["sections"]["mode_unverified_clients"][0]
    assert isinstance(row["client_id"], str)
    assert len(row["client_label"]) > 0
