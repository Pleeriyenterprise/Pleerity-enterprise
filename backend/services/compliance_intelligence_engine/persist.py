"""Atomic artefact + provenance persistence."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from services.compliance_intelligence_engine.storage import artefacts as artefact_storage
from services.compliance_intelligence_engine.storage import provenance as provenance_storage


async def persist_artefact_with_provenance(
    *, artefact: Dict[str, Any], provenance: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if artefact.get("provenance_id") != provenance.get("provenance_id"):
        raise ValueError("provenance_id_mismatch")
    if artefact.get("artefact_id") != provenance.get("artefact_id"):
        raise ValueError("artefact_id_mismatch")
    await provenance_storage.insert_provenance(provenance)
    await artefact_storage.insert_artefact(artefact)
    return artefact, provenance
