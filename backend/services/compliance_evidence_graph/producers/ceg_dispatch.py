"""Non-blocking CEG P2 dispatch helpers for authority services."""
from __future__ import annotations

from typing import Any, Dict, Optional


async def try_dispatch_p2(
    *,
    mutation_kind: str,
    client_id: str,
    source_collection: str,
    source_id: str,
    property_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    mutation_timestamp: Optional[str] = None,
    authoritative_payload: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from services.compliance_evidence_graph.producers.hooks import dispatch_p2_producer
        from services.compliance_evidence_graph.producers.registry import ProducerContext

        await dispatch_p2_producer(
            ProducerContext(
                mutation_kind=mutation_kind,
                client_id=client_id,
                source_collection=source_collection,
                source_id=source_id,
                property_id=property_id,
                correlation_id=correlation_id,
                mutation_timestamp=mutation_timestamp,
                authoritative_payload=authoritative_payload or {},
            )
        )
    except Exception:
        pass
