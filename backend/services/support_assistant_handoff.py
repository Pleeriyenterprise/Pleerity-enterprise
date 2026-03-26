"""
Structured handoff summary for support tickets and human escalation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.support_assistant_intent import SupportAssistantIntent


def build_handoff_summary(
    *,
    conversation_id: str,
    user_message: str,
    router_intent: SupportAssistantIntent,
    intent_confidence: float,
    conversation_history: List[Dict[str, Any]],
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Plain-text block pasted into ticket description by the widget."""
    lines = [
        "[Pleerity Support Assistant — structured handoff]",
        f"Conversation ID: {conversation_id}",
        f"Router intent: {router_intent.value} (confidence {intent_confidence:.2f})",
        "",
        "--- Latest customer message ---",
        user_message.strip(),
        "",
        "--- Recent transcript (newest last) ---",
    ]
    tail = list(conversation_history or [])[-8:]
    for msg in tail:
        sender = msg.get("sender") or msg.get("role")
        text = msg.get("message_text") or msg.get("text") or ""
        who = "Customer" if sender in ("user", "USER") else "Assistant"
        lines.append(f"{who}: {(text or '')[:500]}")
    if extra:
        lines.append("")
        lines.append("--- Context ---")
        for k, v in extra.items():
            lines.append(f"{k}: {v}")
    return "\n".join(lines).strip()
