"""
Compliance Graph Health service — aggregates integrity validator output.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.compliance_evidence_graph.producers.registry import list_producer_registry
from services.compliance_evidence_graph.validation.integrity_validator import (
    VALIDATOR_VERSION,
    validate_graph,
)
from services.compliance_graph_health.metrics import (
    SERVICE_VERSION,
    build_metrics_from_validation,
    compute_overall_status,
    sample_ids,
)


def _environment() -> str:
    return (os.getenv("ENVIRONMENT") or os.getenv("DEPLOYMENT_TIER") or "development").strip().lower()


async def run_validation_on_demand(
    *,
    client_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    max_decisions: int = 10_000,
) -> Dict[str, Any]:
    result = await validate_graph(
        client_id=client_id,
        since=since,
        until=until,
        max_decisions=max_decisions,
    )
    return result.to_dict()


async def generate_health_report(
    *,
    client_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    max_decisions: int = 10_000,
) -> Dict[str, Any]:
    validation = await validate_graph(
        client_id=client_id,
        since=since,
        until=until,
        max_decisions=max_decisions,
    )
    vdict = validation.to_dict()
    metrics = build_metrics_from_validation(validation.stats, vdict)
    failure_count = metrics["integrity_failure_count"]
    warning_count = metrics["warning_count"]
    status = compute_overall_status(
        integrity_failure_count=failure_count,
        warning_count=warning_count,
    )

    return {
        "service": "compliance_graph_health",
        "service_version": SERVICE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "client_id": client_id,
            "environment": _environment(),
            "since": since,
            "until": until,
            "max_decisions": max_decisions,
        },
        "overall_status": status,
        "summary": {
            "decisions_examined": validation.stats.get("decisions_examined", 0),
            "checks_passed": validation.checks_run - failure_count,
            "checks_failed": failure_count,
            "warnings": warning_count,
            "integrity_failure_count": failure_count,
        },
        "metrics": metrics,
        "failures": vdict.get("failures") or [],
        "warnings": [
            {
                **w,
                "sample_decision_ids": sample_ids([w]),
            }
            for w in (vdict.get("warnings") or [])
        ],
        "producer_registry": {
            "entries": len(list_producer_registry()),
            "live_emit_active_count": sum(
                1 for e in list_producer_registry() if e.get("live_emit_active")
            ),
        },
        "validator_version": VALIDATOR_VERSION,
        "validation_duration_ms": validation.duration_ms,
    }


async def generate_health_summary(
    *,
    client_id: Optional[str] = None,
    since: Optional[str] = None,
) -> Dict[str, Any]:
    report = await generate_health_report(client_id=client_id, since=since, max_decisions=5000)
    return {
        "service": report["service"],
        "generated_at": report["generated_at"],
        "overall_status": report["overall_status"],
        "summary": report["summary"],
        "metrics": report["metrics"],
    }
