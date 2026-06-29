"""Governed Graph Service read adapter — CIE-1 stub only."""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.compliance_graph_service.access import ActorContext


async def fetch_graph_envelope(
    *,
    method: str,
    params: Dict[str, Any],
    actor: ActorContext,
    client_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Reserved for CIE-2+; CIE-1 does not perform live graph reads."""
    return None
