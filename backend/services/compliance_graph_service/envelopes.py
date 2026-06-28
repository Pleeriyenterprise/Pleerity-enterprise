"""Graph Service response envelopes — AI-ready structured outputs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.compliance_evidence_graph.constants import SERVICE_VERSION


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def base_envelope(
    *,
    service: str,
    request: Dict[str, Any],
    payload: Dict[str, Any],
    insufficient_evidence: bool = False,
    authoritative_references: Optional[Dict[str, Any]] = None,
    evidence_lineage: Optional[List[Dict[str, Any]]] = None,
    decision_lineage: Optional[Dict[str, Any]] = None,
    confidence_metadata: Optional[Dict[str, Any]] = None,
    applicable_legislation: Optional[List[Dict[str, Any]]] = None,
    applicable_rules: Optional[List[Dict[str, Any]]] = None,
    historical_references: Optional[Dict[str, Any]] = None,
    operational_references: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "service": service,
        "service_version": SERVICE_VERSION,
        "generated_at": _utc(),
        "request": request,
        "authoritative_references": authoritative_references or {},
        "evidence_lineage": evidence_lineage or [],
        "decision_lineage": decision_lineage or {},
        "confidence_metadata": confidence_metadata or {},
        "applicable_legislation": applicable_legislation or [],
        "applicable_rules": applicable_rules or [],
        "historical_references": historical_references or {},
        "operational_references": operational_references or {},
        "insufficient_evidence": insufficient_evidence,
        "payload": payload,
    }


def insufficient(service: str, request: Dict[str, Any], reason: str = "Insufficient evidence available.") -> Dict[str, Any]:
    return base_envelope(
        service=service,
        request=request,
        insufficient_evidence=True,
        payload={"executive_summary": reason, "reason": reason},
    )
