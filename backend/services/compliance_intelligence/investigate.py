"""Investigate orchestrator — Graph Service first, optional Tier 2 narration (Phase 5)."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from services.compliance_graph_service.access import ActorContext
from services.compliance_intelligence.config import intelligence_enabled, intelligence_narration_enabled
from services.compliance_intelligence.graph_dispatch import dispatch_graph_method
from services.compliance_intelligence.hashing import envelope_hash
from services.compliance_intelligence.narrations import store_narration
from services.compliance_intelligence.post_validator import validate_and_strip_narration
from services.compliance_intelligence.prompts import SYSTEM_PROMPT, build_user_prompt
from services.compliance_intelligence.schema import empty_narration, parse_narration_payload


def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def investigate(
    *,
    method: str,
    params: Dict[str, Any],
    actor: ActorContext,
    client_id: Optional[str] = None,
    question: Optional[str] = None,
    narrate: bool = False,
) -> Dict[str, Any]:
    """
    Tier 1: Graph Service envelope (deterministic).
    Tier 2: optional LLM narration when explicitly enabled and narrate=true.
    """
    if not intelligence_enabled():
        return {
            "enabled": False,
            "insufficient_evidence": True,
            "reason": "Compliance intelligence requires COMPLIANCE_EVIDENCE_GRAPH_MODE=enabled.",
            "tier1": None,
            "tier2": None,
        }

    envelope = await dispatch_graph_method(
        method=method, params=params, actor=actor, client_id=client_id
    )
    response_hash = envelope_hash(envelope)
    cid = client_id or params.get("client_id") or actor.client_id

    result: Dict[str, Any] = {
        "enabled": True,
        "graph_method": method,
        "graph_service_response_hash": response_hash,
        "tier1": envelope,
        "tier2": None,
        "narration_id": None,
        "insufficient_evidence": bool(envelope.get("insufficient_evidence")),
    }

    if envelope.get("insufficient_evidence"):
        result["tier2"] = empty_narration(graph_service_response_hash=response_hash, insufficient=True)
        return result

    if not narrate or not intelligence_narration_enabled():
        return result

    from utils import ai_config
    from utils.llm_chat import chat_openai

    user_prompt = build_user_prompt(envelope=envelope, question=question)
    raw_answer = await chat_openai(system_prompt=SYSTEM_PROMPT, user_text=user_prompt)
    parsed = parse_narration_payload(
        _parse_llm_json(raw_answer), graph_service_response_hash=response_hash
    )
    if not parsed:
        result["tier2"] = empty_narration(graph_service_response_hash=response_hash, insufficient=True)
        result["narration_error"] = "invalid_llm_schema"
        return result

    validated = validate_and_strip_narration(parsed, envelope)
    result["tier2"] = validated
    result["insufficient_evidence"] = bool(validated.get("insufficient_evidence"))

    narration_id = await store_narration(
        client_id=cid,
        graph_method=method,
        graph_service_response_hash=response_hash,
        envelope=envelope,
        narration=validated,
        question=question,
        model_id=ai_config.AI_MODEL,
        actor_admin=actor.is_admin,
        actor_portal_user_id=actor.portal_user_id,
    )
    result["narration_id"] = narration_id
    return result
