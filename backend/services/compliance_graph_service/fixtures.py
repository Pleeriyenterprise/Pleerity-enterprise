"""Controlled fixtures for Phase 1 validation — not live producers."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_evidence_graph.constants import DECISION_COMPLIANCE_ASSESSMENT
from services.compliance_evidence_graph.emit_service import emit_compliance_decision


async def seed_fixture_decision(
    *,
    client_id: str = "ceg-fixture-client",
    property_id: str = "ceg-fixture-property",
    requirement_id: str = "ceg-fixture-requirement",
    outcome: str = "VALID",
    dedupe_suffix: str = "v1",
    previous_decision_id: Optional[str] = None,
    decision_timestamp: Optional[str] = None,
) -> Optional[str]:
    """Emit a deterministic fixture decision for service/route validation."""
    dedupe = f"fixture:assessment:{requirement_id}:{dedupe_suffix}"
    snapshot_payload: Dict[str, Any] = {
        "applicable_legislation": [
            {
                "legislation_id": "gas_safety_regs_1998",
                "version": "1998-amendment-2018",
                "title": "Gas Safety (Installation and Use) Regulations 1998",
            }
        ],
        "applicable_jurisdiction": {"jurisdiction": "england", "local_authority": "Westminster"},
        "rules_version": {"governed_rule_version_id": "gov_fixture_v1"},
        "evidence_version": {
            "document_versions": [{"document_id": "doc_fixture_1", "version": 1, "verification_status": "verified"}]
        },
        "ai_extraction_results": [{"document_id": "doc_fixture_1", "extracted_fields": {"expiry_date": "2027-06-28"}}],
        "human_approvals": [{"review_event_id": "rev_fixture_1", "outcome": "approved"}],
        "compliance_score": {"property_id": property_id, "score_before": 70, "score_after": 78},
        "risk_score": {"property_id": property_id, "risk_level_before": "medium", "risk_level_after": "low"},
        "operational_context": {"correlation_id": "corr_fixture_1", "operational_event_ids": []},
        "timeline_references": [],
        "decision_reasoning_inputs": {
            "authority_sync_outcome": {"semantic_state": outcome},
            "missing_dependencies": [],
        },
    }
    return await emit_compliance_decision(
        decision_type=DECISION_COMPLIANCE_ASSESSMENT,
        decision_outcome=outcome,
        summary=f"Fixture assessment: requirement {requirement_id} → {outcome}",
        source_collection="requirements",
        source_id=requirement_id,
        dedupe_key=dedupe,
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        previous_decision_id=previous_decision_id,
        decision_timestamp=decision_timestamp,
        decision_authority={
            "service": "compliance_graph_service.fixtures",
            "component": "seed_fixture_decision",
            "actor_type": "system",
            "actor_id": "phase1_validation",
        },
        snapshot_payload=snapshot_payload,
        document_ids=["doc_fixture_1"],
        operational_correlation_id="corr_fixture_1",
        scope={"object_type": "requirement", "object_id": requirement_id},
        metadata={"fixture": True, "phase": 1},
    )
