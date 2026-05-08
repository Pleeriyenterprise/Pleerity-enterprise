from __future__ import annotations

"""
Runtime Convergence Phase 2 audit notes (concise):
- Fully satisfies contract: unified requirement-backed task metadata, command-centre requirement actions,
  score-driver requirement rows (matched canonical rows).
- Partially satisfies: sparse legacy rows where upstream semantic fields are absent.
- Acceptable omissions: EXPECTED_IF_AVAILABLE / EXPECTED_IF_RELEVANT fields on sparse legacy payloads.
- Convergence candidates: remaining producer paths that still emit requirement-shaped rows without
  full semantic enrichment.
- STATE_MODEL_LIMITATION: sparse legacy state remains sparse until upstream canonical state/resolution
  is present; this phase is diagnostic only.
"""

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services import unified_tasks_service as uts
from services.command_center_service import _slim_task
from services.semantic_payload_contract import (
    CANONICAL_REQUIREMENT_ROW,
    COMMAND_CENTRE_REQUIREMENT_ACTION,
    OPERATIONAL_TASK_ROW,
    REQUIREMENT_BACKED_TASK,
    SCORE_DRIVER_REQUIREMENT,
    validate_semantic_payload_contract,
)


def test_unified_requirement_task_emits_converged_semantic_fields():
    action = {
        "action_type": "missing_document",
        "related_property_id": "p1",
        "related_requirement_id": "r1",
        "requirement_code": "gas_safety",
        "title": "Missing gas certificate",
        "description": "Upload missing evidence.",
        "recommended_action_label": "Upload document",
        "recommended_url": "/documents?property_id=p1&requirement_id=r1",
        "severity": "high",
        "priority": 88,
        "canonical_take_action": {"primary": {"kind": "guided_evidence_resolution", "label": "Resolve evidence"}},
        "workflow_class": "MULTI_EVIDENCE",
        "semantic_state": "PARTIALLY_COMPLETE",
        "guidance_target": "evidence_resolution",
        "allowed_evidence_modes": ["document_upload", "declaration"],
        "requirement_display": {"short_name": "Gas Safety"},
        "evidence_authority": {"state": "MISSING"},
        "evidence_completeness": {"is_incomplete": True},
    }
    task = uts._action_to_task(action, {"p1": "Property 1"}, datetime.now(timezone.utc))
    md = task.get("metadata") or {}
    assert task.get("source_type") == "requirement"
    assert md.get("workflow_class") == "MULTI_EVIDENCE"
    assert md.get("semantic_state") == "PARTIALLY_COMPLETE"
    assert isinstance(md.get("take_action"), dict)
    assert isinstance(md.get("requirement_display"), dict)
    assert isinstance(md.get("evidence_authority"), dict)
    assert isinstance(md.get("evidence_completeness"), dict)
    diag = validate_semantic_payload_contract(
        {
            "source_type": task.get("source_type"),
            "requirement_id": md.get("requirement_id"),
            "property_id": task.get("property_id"),
            "workflow_class": md.get("workflow_class"),
            "semantic_state": md.get("semantic_state"),
            "take_action": md.get("take_action"),
            "requirement_display": md.get("requirement_display"),
            "evidence_authority": md.get("evidence_authority"),
            "evidence_completeness": md.get("evidence_completeness"),
            "guidance_target": md.get("guidance_target"),
            "allowed_evidence_modes": md.get("allowed_evidence_modes"),
            "primary_action_type": task.get("primary_action_type"),
            "primary_action_label": task.get("primary_action_label"),
            "primary_action_url": task.get("primary_action_url"),
            "action_context_type": task.get("action_context_type"),
        },
        REQUIREMENT_BACKED_TASK,
    )
    assert diag["severity"] in ("OK", "WARNING")
    assert not diag["missing_required"]
    canon_diag = validate_semantic_payload_contract(
        {
            "requirement_id": md.get("requirement_id"),
            "property_id": task.get("property_id"),
            "workflow_class": md.get("workflow_class"),
            "semantic_state": md.get("semantic_state"),
            "take_action": md.get("take_action"),
            "requirement_display": md.get("requirement_display"),
            "evidence_authority": md.get("evidence_authority"),
            "evidence_completeness": md.get("evidence_completeness"),
            "guidance_target": md.get("guidance_target"),
            "allowed_evidence_modes": md.get("allowed_evidence_modes"),
        },
        CANONICAL_REQUIREMENT_ROW,
    )
    assert canon_diag["severity"] in ("OK", "WARNING")
    assert not canon_diag["missing_required"]


def test_command_center_slim_task_keeps_requirement_semantics_not_operational():
    req = _slim_task(
        {
            "id": "requirement:r1",
            "source_type": "requirement",
            "source_id": "r1",
            "requirement_id": "r1",
            "property_id": "p1",
            "primary_action_type": "upload_evidence",
            "primary_action_label": "Upload document",
            "primary_action_url": "/documents?property_id=p1&requirement_id=r1",
            "metadata": {
                "workflow_class": "MULTI_EVIDENCE",
                "semantic_state": "PARTIALLY_COMPLETE",
                "take_action": {"primary": {"kind": "guided_evidence_resolution"}},
                "requirement_display": {"short_name": "Gas Safety"},
                "evidence_authority": {"state": "MISSING"},
                "evidence_completeness": {"is_incomplete": True},
            },
        }
    )
    assert req.get("workflow_class") == "MULTI_EVIDENCE"
    assert req.get("semantic_state") == "PARTIALLY_COMPLETE"
    assert isinstance(req.get("take_action"), dict)
    req_diag = validate_semantic_payload_contract(
        req,
        COMMAND_CENTRE_REQUIREMENT_ACTION,
    )
    assert req_diag["severity"] in ("OK", "WARNING")
    assert not req_diag["missing_required"]

    op = _slim_task(
        {
            "id": "work_order:w1",
            "source_type": "work_order",
            "source_id": "w1",
            "metadata": {
                "workflow_class": "MULTI_EVIDENCE",
                "take_action": {"primary": {"kind": "guided_evidence_resolution"}},
            },
        }
    )
    assert "workflow_class" not in op
    assert "take_action" not in op
    op_diag = validate_semantic_payload_contract(
        {
            "source_type": op.get("source_type"),
            "property_id": op.get("property_id") or "p-op",
            "primary_action_type": op.get("primary_action_type") or "work_order",
            "primary_action_label": op.get("primary_action_label") or "View details",
            "workflow_class": op.get("workflow_class"),
            "take_action": op.get("take_action"),
            "evidence_authority": op.get("evidence_authority"),
            "evidence_completeness": op.get("evidence_completeness"),
        },
        OPERATIONAL_TASK_ROW,
    )
    assert op_diag["severity"] in ("OK", "WARNING")
    assert not op_diag["unexpected_fields"]


@pytest.mark.asyncio
async def test_compliance_score_driver_rows_include_converged_semantics():
    from services.compliance_score import calculate_compliance_score

    class _Collection:
        def __init__(self, rows):
            self._rows = list(rows)

        def find(self, *_a, **_k):
            return SimpleNamespace(_rows=list(self._rows))

    now = datetime.now(timezone.utc)
    properties = [{"property_id": "p1", "client_id": "c1", "compliance_score": 72, "is_hmo": False}]
    requirements = [
        {
            "requirement_id": "r1",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_type": "gas_safety",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=2)).isoformat(),
            "workflow_class": "MULTI_EVIDENCE",
            "semantic_state": "PARTIALLY_COMPLETE",
            "take_action": {"primary": {"kind": "guided_evidence_resolution"}},
            "requirement_display": {"short_name": "Gas Safety"},
            "evidence_authority": {"state": "MISSING"},
            "evidence_completeness": {"is_incomplete": True},
            "guidance_target": "evidence_resolution",
            "allowed_evidence_modes": ["document_upload", "declaration"],
        }
    ]
    db = SimpleNamespace(
        properties=_Collection(properties),
        requirements=_Collection(requirements),
        documents=_Collection([]),
        clients=SimpleNamespace(find_one=AsyncMock(return_value={"default_jurisdiction": "England"})),
    )

    async def _mongo_find_to_list(cursor, cap=500000):  # noqa: ARG001
        return list(getattr(cursor, "_rows", []))

    _eff = {
        "base_portfolio_risk_state": "Moderate Risk",
        "effective_portfolio_risk_state": "Moderate Risk",
        "risk_override_reasons": [],
        "critical_property_count": 0,
        "high_risk_gap_count": 0,
        "unknown_or_stale_property_count": 0,
        "attention_required": False,
        "critical_property_escalation": False,
        "suppress_positive_headline": False,
    }
    _override_bundle = {
        "legacy_override_output": _eff,
        "policy_override_output": _eff,
        "effective_override_output": _eff,
    }

    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.compliance_score.mongo_find_to_list",
        new=AsyncMock(side_effect=_mongo_find_to_list),
    ), patch(
        "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
        new=AsyncMock(side_effect=lambda *_a, **kw: kw.get("requirements") or []),
    ), patch(
        "services.requirement_truth.enrich_requirements_for_client",
        new=AsyncMock(side_effect=lambda *_a, **_kw: ((_a[2] if len(_a) >= 3 else []), {})),
    ), patch(
        "services.requirement_client_runtime_surface.project_requirement_row_client_runtime",
        side_effect=lambda r: dict(r),
    ), patch(
        "services.requirement_client_runtime_surface.client_portal_surface_visible_row",
        side_effect=lambda _r: True,
    ), patch(
        "services.requirement_client_runtime_surface.compute_client_portal_requirement_stats",
        return_value={
            "total_requirements": 1,
            "compliant": 0,
            "pending": 0,
            "expiring_soon": 0,
            "overdue": 1,
            "missing_evidence": 1,
        },
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new=AsyncMock(return_value={"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": {}}),
    ), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new=AsyncMock(return_value=_override_bundle),
    ), patch(
        "services.compliance_score.get_canonical_requirement_ids_map_for_properties",
        new=AsyncMock(return_value={"p1": {"r1"}}),
    ), patch(
        "services.compliance_score.requirement_has_active_negative_actionability",
        return_value=True,
    ), patch(
        "services.compliance_score.resolve_expiring_soon_days_for_requirement",
        return_value=30,
    ), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new=AsyncMock(return_value=None),
    ):
        out = await calculate_compliance_score("c1")

    drivers = out.get("drivers") or []
    assert len(drivers) == 1
    d = drivers[0]
    assert d.get("workflow_class") == "MULTI_EVIDENCE"
    assert d.get("semantic_state") == "PARTIALLY_COMPLETE"
    assert isinstance(d.get("take_action"), dict)
    assert isinstance(d.get("requirement_display"), dict)
    assert isinstance(d.get("evidence_authority"), dict)
    assert isinstance(d.get("evidence_completeness"), dict)
    driver_diag = validate_semantic_payload_contract(d, SCORE_DRIVER_REQUIREMENT)
    assert driver_diag["severity"] in ("OK", "WARNING")
    assert not driver_diag["missing_required"]
