"""Focused tests: DOCUMENT_UPLOAD / gas_safety client upload success → backbone observability (bounded slice)."""
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from database import database as db_singleton
from routes import documents as documents_routes
from server import app
from services.compliance_recalc_queue import EnqueueComplianceRecalcResult
from services.evidence_document_taxonomy import POLICY_QUARANTINE


@pytest.fixture
def client_http():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _ignore_unawaited_analysis_coroutine():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        yield


def _match_eval_ok():
    return {
        "evidence_match_policy": POLICY_QUARANTINE,
        "match_outcome": "MATCH_CONFIRMED",
        "match_confidence": 0.95,
        "predicted_document_type": "gas_safety_certificate",
        "mismatch_reason_code": None,
        "mismatch_reason_text": None,
        "user_messages": [],
        "evidence_satisfies_requirement": True,
        "manual_review_flag_suggested": False,
    }


def test_workflow_activation_observability_filters_disallowed_targets():
    from routes.documents import _workflow_activation_observability_for_gas_safety_client_upload

    fanout = {
        "transition_id": "tr:test",
        "correlation_id": "corr:test",
        "transition_outcome": "TRANSITION_APPLIED",
        "rst_core_backbone_activation": {"permitted": True, "activation_family": "REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE"},
        "downstream_trigger_targets": [
            {"downstream_target": "notifications.send_digest", "enqueue_outcome": "ENQUEUE_ACCEPTED"},
            {
                "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                "enqueue_outcome": "ENQUEUE_ACCEPTED",
                "downstream_correlation_id": "corr:test",
            },
        ],
    }
    out = _workflow_activation_observability_for_gas_safety_client_upload(
        fanout,
        document_upload_correlation_id="DOC_UPLOADED:doc1",
    )
    assert out["workflow_class"] == "DOCUMENT_UPLOAD"
    assert out["obligation_slice"] == "gas_safety"
    assert out["document_upload_correlation_id"] == "DOC_UPLOADED:doc1"
    assert len(out["approved_downstream_observations"]) == 1
    assert out["approved_downstream_observations"][0]["downstream_target"] == "compliance_recalc_queue.enqueue_compliance_recalc"


@pytest.mark.parametrize(
    "req_code,req_type,expected_slice",
    [
        ("gas_safety", "gas_safety", "gas_safety"),
        ("GAS_SAFETY", "cp12", "gas_safety"),
        ("pat", "portable_appliance_test", None),
    ],
)
def test_gas_safety_bounded_slice_resolution(req_code, req_type, expected_slice):
    from routes.documents import _resolve_bound_document_upload_activation_obligation_slice

    req = {"requirement_id": "r1", "requirement_code": req_code, "requirement_type": req_type}
    assert _resolve_bound_document_upload_activation_obligation_slice(req) == expected_slice


def test_gas_safety_client_upload_success_response_shape_and_observability(client_http, tmp_path):
    user = {"client_id": "cli-gs", "portal_user_id": "pu-gs", "role": "ROLE_CLIENT_ADMIN"}
    pid, rid = "prop-gs", "req-gs"
    prop = {"property_id": pid, "client_id": user["client_id"], "is_active": True}
    req = {
        "requirement_id": rid,
        "client_id": user["client_id"],
        "property_id": pid,
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "applicability": "REQUIRED",
    }

    async def guard(request):
        return user

    mock_db = MagicMock()

    async def find_one(filter_q, *args, **kwargs):
        if "property_id" in filter_q and filter_q.get("property_id") == pid:
            return prop
        if "requirement_id" in filter_q and filter_q.get("requirement_id") == rid:
            return req
        if filter_q.get("client_id") == user["client_id"] and "default_jurisdiction" in str(kwargs):
            return {}
        return None

    mock_db.properties.find_one = AsyncMock(side_effect=find_one)
    mock_db.clients.find_one = AsyncMock(return_value={})
    mock_db.requirements.find_one = AsyncMock(side_effect=find_one)
    mock_db.documents.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))

    enqueue_calls = []

    async def fake_sync(
        db,
        requirement_id,
        property_id_hint=None,
        correlation_id=None,
        transition_origin=None,
        transition_observability_out=None,
    ):
        if transition_observability_out is not None:
            transition_observability_out.clear()
            transition_observability_out.update(
                {
                    "transition_id": "tr:synthetic",
                    "correlation_id": correlation_id or "",
                    "transition_origin": transition_origin or "",
                    "requirement_id": requirement_id,
                    "property_id": property_id_hint,
                    "client_id": user["client_id"],
                    "downstream_trigger_targets": [
                        {
                            "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
                            "trigger_mode": "sync",
                            "enqueue_attempted": True,
                            "enqueue_succeeded": True,
                            "propagation_stage": "gap_sync",
                        }
                    ],
                    "transition_outcome": "TRANSITION_APPLIED",
                }
            )
            transition_observability_out["downstream_propagation"] = transition_observability_out["downstream_trigger_targets"]
        return {"state": "UPLOADED_UNCONFIRMED", "version": 2}

    async def capture_enqueue(**kwargs):
        enqueue_calls.append(kwargs)
        cid = kwargs.get("correlation_id") or ""
        return EnqueueComplianceRecalcResult(
            enqueued=True,
            correlation_id=cid,
            regeneration_requeued=True,
            regeneration_error=None,
        )

    with (
        patch.object(documents_routes, "DOCUMENT_STORAGE_PATH", tmp_path),
        patch.object(documents_routes, "client_route_guard", guard),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "services.compliance_rules_registry.validate_document_upload_for_requirement",
            return_value={"valid": True},
        ),
        patch.object(documents_routes, "evaluate_document_requirement_match", return_value=_match_eval_ok()),
        patch("utils.rate_limiter.rate_limiter.check_rate_limit", new_callable=AsyncMock, return_value=(True, None)),
        patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(documents_routes, "_validate_optional_work_order_document_link", new_callable=AsyncMock, return_value=None),
        patch.object(
            documents_routes,
            "safe_upsert_document_upload_evidence_for_linked_document",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("services.authority_mutation_fanout.sync_requirement_evidence_authority", side_effect=fake_sync),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock, side_effect=capture_enqueue),
        patch("services.provisioning.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("routes.documents.create_audit_log", new_callable=AsyncMock),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
        patch("services.analytics_service.log_event", new_callable=AsyncMock),
        patch("services.analytics_service.log_first_doc_uploaded_once", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
        patch.object(documents_routes.asyncio, "create_task", return_value=MagicMock()),
    ):
        res = client_http.post(
            "/api/documents/upload",
            files={"file": ("gas_cert.pdf", b"%PDF-1.4 cert", "application/pdf")},
            data={
                "property_id": pid,
                "requirement_id": rid,
                "document_type": "Gas safety certificate",
            },
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("message") == "Document uploaded successfully"
    assert body.get("document_id")
    assert "evidence_match" in body
    assert "outcome" in body

    obs = body.get("workflow_activation_observability")
    assert obs is not None
    assert obs.get("workflow_class") == "DOCUMENT_UPLOAD"
    assert obs.get("obligation_slice") == "gas_safety"
    doc_id = body["document_id"]
    assert obs.get("document_upload_correlation_id") == f"DOC_UPLOADED:{doc_id}"

    targets = [r.get("downstream_target") for r in (obs.get("approved_downstream_observations") or [])]
    assert "compliance_gap_sync.sync_compliance_gaps_for_requirement" in targets
    assert "compliance_recalc_queue.enqueue_compliance_recalc" in targets
    forbidden = ("notification", "unified_task", "command_centre", "portfolio", "report_export", "cache_invalidation")
    raw = str(obs).lower()
    for f in forbidden:
        assert f not in raw

    assert enqueue_calls, "enqueue_compliance_recalc should run on success path"
    assert enqueue_calls[0].get("correlation_id") == f"DOC_UPLOADED:{doc_id}"

    bb = obs.get("rst_core_backbone_activation") or {}
    assert "activation_family" in bb
    assert bb.get("permitted") is True

    regen_rows = [
        r
        for r in (obs.get("approved_downstream_observations") or [])
        if r.get("downstream_target") == "risk_signal_regen_queue.enqueue_risk_signal_regen"
    ]
    assert regen_rows, "gated REGENERATION_RECALC delegate row expected when recalc reports regeneration_requeued"
    assert regen_rows[0].get("enqueue_succeeded") is True


def test_non_bounded_slice_client_upload_omits_workflow_activation_observability(client_http, tmp_path):
    """PAT is DOCUMENT_UPLOAD class but not in the bounded gas_safety/eicr observability slices."""
    user = {"client_id": "cli-pat", "portal_user_id": "pu-pat", "role": "ROLE_CLIENT_ADMIN"}
    pid, rid = "prop-pat", "req-pat"
    prop = {"property_id": pid, "client_id": user["client_id"], "is_active": True}
    req = {
        "requirement_id": rid,
        "client_id": user["client_id"],
        "property_id": pid,
        "requirement_type": "portable_appliance_test",
        "requirement_code": "portable_appliance_test",
        "applicability": "REQUIRED",
    }

    async def guard(request):
        return user

    mock_db = MagicMock()

    async def find_one(filter_q, *args, **kwargs):
        if "property_id" in filter_q and filter_q.get("property_id") == pid:
            return prop
        if "requirement_id" in filter_q and filter_q.get("requirement_id") == rid:
            return req
        if filter_q.get("client_id") == user["client_id"] and "default_jurisdiction" in str(kwargs):
            return {}
        return None

    mock_db.properties.find_one = AsyncMock(side_effect=find_one)
    mock_db.clients.find_one = AsyncMock(return_value={})
    mock_db.requirements.find_one = AsyncMock(side_effect=find_one)
    mock_db.documents.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))

    async def fake_sync(
        db,
        requirement_id,
        property_id_hint=None,
        correlation_id=None,
        transition_origin=None,
        transition_observability_out=None,
    ):
        if transition_observability_out is not None:
            transition_observability_out.clear()
            transition_observability_out.update(
                {
                    "transition_id": "tr:pat",
                    "correlation_id": correlation_id or "",
                    "requirement_id": requirement_id,
                    "downstream_trigger_targets": [],
                    "transition_outcome": "TRANSITION_APPLIED",
                }
            )
        return {"state": "MISSING", "version": 2}

    with (
        patch.object(documents_routes, "DOCUMENT_STORAGE_PATH", tmp_path),
        patch.object(documents_routes, "client_route_guard", guard),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "services.compliance_rules_registry.validate_document_upload_for_requirement",
            return_value={"valid": True},
        ),
        patch.object(documents_routes, "evaluate_document_requirement_match", return_value=_match_eval_ok()),
        patch("utils.rate_limiter.rate_limiter.check_rate_limit", new_callable=AsyncMock, return_value=(True, None)),
        patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(documents_routes, "_validate_optional_work_order_document_link", new_callable=AsyncMock, return_value=None),
        patch.object(
            documents_routes,
            "safe_upsert_document_upload_evidence_for_linked_document",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("services.authority_mutation_fanout.sync_requirement_evidence_authority", side_effect=fake_sync),
        patch(
            "services.compliance_recalc_queue.enqueue_compliance_recalc",
            new_callable=AsyncMock,
            return_value=EnqueueComplianceRecalcResult(enqueued=True, correlation_id="x"),
        ),
        patch("services.provisioning.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("routes.documents.create_audit_log", new_callable=AsyncMock),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
        patch("services.analytics_service.log_event", new_callable=AsyncMock),
        patch("services.analytics_service.log_first_doc_uploaded_once", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
        patch.object(documents_routes.asyncio, "create_task", return_value=MagicMock()),
    ):
        res = client_http.post(
            "/api/documents/upload",
            files={"file": ("pat.pdf", b"%PDF-1.4", "application/pdf")},
            data={"property_id": pid, "requirement_id": rid, "document_type": "PAT certificate"},
        )

    assert res.status_code == 200, res.text
    assert "workflow_activation_observability" not in res.json()


def test_gas_safety_rst_backbone_blocked_shows_skip_observability(client_http, tmp_path):
    """When backbone gate blocks, authority_sync skip row remains visible on the gas_safety observability slice."""
    user = {"client_id": "cli-bk", "portal_user_id": "pu-bk", "role": "ROLE_CLIENT_ADMIN"}
    pid, rid = "prop-bk", "req-bk"
    prop = {"property_id": pid, "client_id": user["client_id"], "is_active": True}
    req_row = {
        "requirement_id": rid,
        "client_id": user["client_id"],
        "property_id": pid,
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
    }

    async def guard(request):
        return user

    blocked_gate = {
        "activation_family": "REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE",
        "activation_governance_version": "workflow_runtime_activation_registry_v3",
        "activation_guard_result": "GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY",
        "activation_reason": "rst_core_backbone_registry_ceiling_observe_only",
        "activation_scope": "requirement_state_transition_core_backbone_only",
        "activation_state": "ACTIVATION_OBSERVE_ONLY",
        "child_compliance_recalc_gate": {"permitted": False},
        "child_regeneration_recalc_gate": {"permitted": False},
        "permitted": False,
        "registry_ceiling": "ACTIVATION_OBSERVE_ONLY",
    }

    mock_db = MagicMock()

    async def find_one(filter_q, *args, **kwargs):
        if "property_id" in filter_q and filter_q.get("property_id") == pid:
            return prop
        if "requirement_id" in filter_q and filter_q.get("requirement_id") == rid:
            return req_row
        if filter_q.get("client_id") == user["client_id"] and "default_jurisdiction" in str(kwargs):
            return {}
        return None

    mock_db.properties.find_one = AsyncMock(side_effect=find_one)
    mock_db.clients.find_one = AsyncMock(return_value={})
    mock_db.requirements.find_one = AsyncMock(side_effect=find_one)
    mock_db.documents.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))

    async def sync_must_not_run(*args, **kwargs):
        raise AssertionError("sync_requirement_evidence_authority must not run when backbone gate blocks")

    enqueue_calls = []

    async def enqueue_should_not_run(**kwargs):
        enqueue_calls.append(kwargs)
        return EnqueueComplianceRecalcResult(enqueued=False, correlation_id="")

    with (
        patch.object(documents_routes, "DOCUMENT_STORAGE_PATH", tmp_path),
        patch.object(documents_routes, "client_route_guard", guard),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "services.compliance_rules_registry.validate_document_upload_for_requirement",
            return_value={"valid": True},
        ),
        patch.object(documents_routes, "evaluate_document_requirement_match", return_value=_match_eval_ok()),
        patch("utils.rate_limiter.rate_limiter.check_rate_limit", new_callable=AsyncMock, return_value=(True, None)),
        patch(
            "services.requirement_client_runtime_surface.requirement_row_eligible_on_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(documents_routes, "_validate_optional_work_order_document_link", new_callable=AsyncMock, return_value=None),
        patch.object(
            documents_routes,
            "safe_upsert_document_upload_evidence_for_linked_document",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.authority_mutation_fanout.resolve_requirement_state_transition_core_backbone_gate",
            return_value=blocked_gate,
        ),
        patch(
            "services.authority_mutation_fanout.sync_requirement_evidence_authority",
            side_effect=sync_must_not_run,
        ),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock, side_effect=enqueue_should_not_run),
        patch("services.provisioning.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch("routes.documents.create_audit_log", new_callable=AsyncMock),
        patch("services.score_events_service.write_score_event", new_callable=AsyncMock),
        patch("services.analytics_service.log_event", new_callable=AsyncMock),
        patch("services.analytics_service.log_first_doc_uploaded_once", new_callable=AsyncMock),
        patch("services.compliance_outcome_engine.apply_action_outcome", new_callable=AsyncMock, return_value=None),
        patch.object(documents_routes.asyncio, "create_task", return_value=MagicMock()),
    ):
        res = client_http.post(
            "/api/documents/upload",
            files={"file": ("gas.pdf", b"%PDF-1.4", "application/pdf")},
            data={"property_id": pid, "requirement_id": rid, "document_type": "Gas safety certificate"},
        )

    assert res.status_code == 200, res.text
    assert enqueue_calls == [], "recalc enqueue must not run when backbone gate blocks"

    obs = res.json().get("workflow_activation_observability")
    assert obs is not None
    bb = obs.get("rst_core_backbone_activation") or {}
    assert bb.get("permitted") is False
    targets = [r.get("downstream_target") for r in (obs.get("approved_downstream_observations") or [])]
    assert "requirement_state_transition.core_backbone.authority_sync" in targets
    skip_row = next(
        r
        for r in (obs.get("approved_downstream_observations") or [])
        if r.get("downstream_target") == "requirement_state_transition.core_backbone.authority_sync"
    )
    assert skip_row.get("enqueue_attempted") is False
