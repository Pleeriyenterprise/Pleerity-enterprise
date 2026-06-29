"""CIE orchestrator stub — domain engines deferred to CIE-2+."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_intelligence_engine.config import intelligence_engine_enabled
from services.compliance_intelligence_engine.envelopes import build_stub_envelope
from services.compliance_intelligence_engine.schema import IntelligenceScope


def unavailable_envelope(
    *,
    service: str,
    reason: str = "COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED",
    artefact_type: Optional[str] = None,
) -> Dict[str, Any]:
    return build_stub_envelope(
        service=service,
        enabled=False,
        insufficient_evidence=True,
        reason=reason,
        artefact_type=artefact_type,
    )


def not_implemented_envelope(
    *,
    service: str,
    artefact_type: Optional[str] = None,
) -> Dict[str, Any]:
    return build_stub_envelope(
        service=service,
        enabled=True,
        insufficient_evidence=True,
        reason="CIE_DOMAIN_ENGINE_NOT_IMPLEMENTED",
        artefact_type=artefact_type,
    )


async def dispatch_generate(
    *,
    service: str,
    artefact_type: Optional[str],
    scope: IntelligenceScope,
) -> Dict[str, Any]:
    if not intelligence_engine_enabled():
        return unavailable_envelope(service=service, artefact_type=artefact_type)
    return not_implemented_envelope(service=service, artefact_type=artefact_type)
