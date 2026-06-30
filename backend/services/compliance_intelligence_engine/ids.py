"""Deterministic ID generation for CIE artefacts."""
from __future__ import annotations

import uuid

from services.compliance_intelligence_engine.constants import (
    ARTEFACT_ID_PREFIX,
    PROVENANCE_ID_PREFIX,
    TRANSITION_ID_PREFIX,
)


def new_artefact_id() -> str:
    return f"{ARTEFACT_ID_PREFIX}{uuid.uuid4().hex}"


def new_provenance_id() -> str:
    return f"{PROVENANCE_ID_PREFIX}{uuid.uuid4().hex}"


def new_transition_id() -> str:
    return f"{TRANSITION_ID_PREFIX}{uuid.uuid4().hex}"
