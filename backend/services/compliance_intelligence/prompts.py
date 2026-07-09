"""LLM prompt contract for grounded compliance narration (Phase 5)."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from services.compliance_intelligence.schema import PROMPT_VERSION

SYSTEM_PROMPT = """You are an evidence interpreter for Pleerity compliance decisions.
Only state facts present in GRAPH_SERVICE_RESPONSE.
Every claim must map to authoritative_references in your JSON output.
If uncertain or data is missing, set insufficient_evidence to true and return empty paragraphs.
Never invent legislation, legal certainty, scores, timelines, customer actions, or operational causes.
Do not give legal advice beyond platform-supported explanation from the envelope.
Distinguish verified facts in the envelope from missing or insufficient evidence.
Respond with JSON only (no markdown fences):
{
  "paragraphs": [
    {
      "text": "...",
      "authoritative_references": { "decision_id": "...", "snapshot_fields": [] },
      "confidence": 90
    }
  ],
  "insufficient_evidence": false
}"""


def build_user_prompt(*, envelope: Dict[str, Any], question: Optional[str]) -> str:
    payload = {
        "prompt_version": PROMPT_VERSION,
        "GRAPH_SERVICE_RESPONSE": envelope,
        "USER_QUESTION": question or "Summarise this compliance decision for an admin reviewer.",
    }
    return json.dumps(payload, default=str)
