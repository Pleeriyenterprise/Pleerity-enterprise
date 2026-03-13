"""
Retrieval for website support chat: score user message (and context) against structured KB.
Returns best match with confidence; used to answer direct questions without LLM when above threshold.
"""
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from services.support_chatbot_knowledge import get_structured_qa

logger = logging.getLogger(__name__)

# Minimum confidence to return a KB answer (avoid hallucination when no strong match)
RETRIEVAL_CONFIDENCE_THRESHOLD = 0.35

# When best score is below threshold but above this, we may show a clarifying question
CLARIFYING_THRESHOLD = 0.18


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for matching."""
    if not text:
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _keyword_overlap_score(query_norm: str, keywords: List[str], title: str, category: str) -> float:
    """
    Score how well the query matches an entry.
    - Query words in keywords: weight 1.0 per word (max 1.0 for keyword match).
    - Query words in title: weight 0.8.
    - Query words in category: weight 0.6.
    Returns a value in [0, 1] (can exceed 1 if multiple matches; we cap later).
    """
    if not query_norm.strip():
        return 0.0
    query_words = set(query_norm.split())
    if not query_words:
        return 0.0
    score = 0.0
    # Keywords: strongest signal
    keywords_norm = _normalize(" ".join(keywords))
    kw_set = set(keywords_norm.split())
    for w in query_words:
        if w in kw_set:
            score += 1.0
    # Title
    title_norm = _normalize(title)
    for w in query_words:
        if len(w) > 2 and w in title_norm:
            score += 0.8
    # Category (e.g. "cvp", "document_packs")
    cat_norm = _normalize(category)
    for w in query_words:
        if len(w) > 2 and w in cat_norm:
            score += 0.6
    # Normalize by query length so we don't over-penalize long queries
    return score / max(len(query_words), 1)


def _context_boost(entry_category: str, context_topic: Optional[str]) -> float:
    """Boost score when conversation context topic aligns with entry category."""
    if not context_topic:
        return 1.0
    topic = (context_topic or "").lower()
    cat = (entry_category or "").lower()
    # Map intent/topic to category
    if topic in ("compliance_vault_pro", "cvp") and cat == "cvp":
        return 1.25
    if topic == "document_packs" and cat == "document_packs":
        return 1.25
    if topic == "automation" and cat == "automation":
        return 1.25
    if topic == "market_research" and cat == "market_research":
        return 1.25
    if topic in ("account_support", "login") and cat == "login":
        return 1.25
    if topic == "pricing" and cat == "cvp":
        return 1.2
    return 1.0


def retrieve(
    message: str,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], float, List[Dict[str, Any]]]:
    """
    Search structured KB by keywords/title/category; apply context boost.
    Returns:
      - best_entry: the top-scoring entry or None
      - best_score: its score (after boost, may be > 1)
      - all_scored: list of (entry, score) for optional clarifying (e.g. top 3)
    """
    message = (message or "").strip()
    if not message:
        return None, 0.0, []
    qa = get_structured_qa()
    if not qa:
        return None, 0.0, []
    query_norm = _normalize(message)
    context_topic = None
    if conversation_context:
        context_topic = conversation_context.get("intent") or conversation_context.get("topic")
    scored: List[Tuple[Dict[str, Any], float]] = []
    for entry in qa:
        raw = _keyword_overlap_score(
            query_norm,
            entry.get("keywords") or [],
            entry.get("title") or "",
            entry.get("category") or "",
        )
        boost = _context_boost(entry.get("category"), context_topic)
        final = raw * boost
        scored.append((entry, final))
    scored.sort(key=lambda x: -x[1])
    if not scored:
        return None, 0.0, []
    best_entry, best_score = scored[0]
    return best_entry, best_score, scored[:5]


def get_actions_from_entry(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return actions as [{ label, url }] for API; url is None for in-chat-only actions."""
    out: List[Dict[str, Any]] = []
    for action in entry.get("actions") or []:
        if isinstance(action, (list, tuple)):
            label = action[0] if action else ""
            url = action[1] if len(action) > 1 else None
        else:
            label, url = str(action), None
        out.append({"label": label, "url": url})
    return out


def build_response_from_entry(entry: Dict[str, Any]) -> str:
    """
    Format a KB entry as: short intro (answer) + optional bullets + next action choices.
    Matches the style of build_guided_response in support_chatbot.
    """
    lines = []
    answer = (entry.get("answer") or "").strip()
    if answer:
        lines.append(answer)
    lines.append("")
    actions = entry.get("actions") or []
    if actions:
        lines.append("What would you like to do?")
        for i, action in enumerate(actions, 1):
            if isinstance(action, (list, tuple)):
                label, url = action[0], action[1] if len(action) > 1 else None
            else:
                label, url = action, None
            if url:
                lines.append(f"{i}. {label}: {url}")
            else:
                lines.append(f"{i}. {label}")
    return "\n".join(lines).strip()


def get_clarifying_message(scored: List[Tuple[Dict[str, Any], float]]) -> Optional[str]:
    """
    When retrieval has weak matches, suggest clarifying options (e.g. top 2 topics).
    Returns None if not enough signal to clarify.
    """
    if not scored or len(scored) < 2:
        return None
    top = [e for e, s in scored[:3] if s >= CLARIFYING_THRESHOLD]
    if len(top) < 2:
        return None
    titles = [e.get("title") or e.get("id") for e in top[:2]]
    return "I'm not sure which of these you mean. Are you asking about:\n\n• **" + titles[0] + "**\n• **" + titles[1] + "**\n\nOr type your question again and I'll try to help."
