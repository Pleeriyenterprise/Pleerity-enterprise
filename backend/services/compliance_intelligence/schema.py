"""Citation-required narration response schema (Phase 5)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


PROMPT_VERSION = "ceg-intelligence-v1"


def empty_narration(*, graph_service_response_hash: str, insufficient: bool = True) -> Dict[str, Any]:
    return {
        "paragraphs": [],
        "insufficient_evidence": insufficient,
        "graph_service_response_hash": graph_service_response_hash,
        "prompt_version": PROMPT_VERSION,
    }


def parse_narration_payload(raw: Any, *, graph_service_response_hash: str) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    paragraphs = raw.get("paragraphs")
    if not isinstance(paragraphs, list):
        return None
    normalised: List[Dict[str, Any]] = []
    for item in paragraphs:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        refs = item.get("authoritative_references")
        if not text or not isinstance(refs, dict):
            continue
        normalised.append(
            {
                "text": text,
                "authoritative_references": refs,
                "confidence": item.get("confidence"),
            }
        )
    return {
        "paragraphs": normalised,
        "insufficient_evidence": bool(raw.get("insufficient_evidence")),
        "graph_service_response_hash": graph_service_response_hash,
        "prompt_version": PROMPT_VERSION,
    }
