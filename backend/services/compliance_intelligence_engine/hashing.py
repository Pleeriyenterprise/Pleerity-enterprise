"""Deterministic hashing for intelligence artefacts and envelopes."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Optional


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_digest(payload: Any) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def inputs_hash(
    *,
    artefact_type: str,
    scope: Dict[str, Any],
    source_decision_ids: Iterable[str],
    source_snapshot_ids: Iterable[str],
    template_version: str,
    deterministic_version: str,
    engine_version: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    body = {
        "artefact_type": artefact_type,
        "scope": scope,
        "source_decision_ids": sorted(source_decision_ids),
        "source_snapshot_ids": sorted(source_snapshot_ids),
        "template_version": template_version,
        "deterministic_version": deterministic_version,
        "engine_version": engine_version,
    }
    if extra:
        body["extra"] = extra
    return sha256_digest(body)


def artefact_response_hash(artefact_body: Dict[str, Any]) -> str:
    """Hash artefact excluding volatile identity/timing fields."""
    excluded = {"artefact_id", "generated_at", "_id"}
    filtered = {k: v for k, v in artefact_body.items() if k not in excluded}
    return sha256_digest(filtered)


def envelope_hash(envelope: Dict[str, Any]) -> str:
    return sha256_digest(envelope)


def trace_hash(calculation_trace: Any) -> str:
    return sha256_digest(calculation_trace)


def provenance_record_hash(provenance_body: Dict[str, Any]) -> str:
    excluded = {"provenance_id", "generated_at", "_id"}
    filtered = {k: v for k, v in provenance_body.items() if k not in excluded}
    return sha256_digest(filtered)
