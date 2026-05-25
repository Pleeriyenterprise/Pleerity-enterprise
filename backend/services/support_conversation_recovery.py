"""
Deterministic recovery when users signal confusion, correction, or frustration.

Runs before the support AI planner so we do not repeat stale pricing dumps or miss
the underlying question (e.g. plan comparisons).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

_FRUSTRATION_RE = re.compile(
    r"(?:"
    r"\b(?:you(?:'re| are)|that(?:'s| is)|this is)\s+(?:wrong|confus|incorrect|not right)\b"
    r"|\bnot what i (?:asked|meant|wanted)\b"
    r"|\b(?:stop|quit)\s+repeat"
    r"|\byou (?:keep|already)\s+(?:said|saying|told)\b"
    r"|\bdo you understand\b"
    r"|\bare you (?:ok|okay|confus)\b"
    r"|\bi(?:'m| am)\s+(?:confus|frustrat|annoy)\b"
    r"|\byou(?:'re| are)\s+not\s+answer"
    r"|\bthat did(?:n't| not) help\b"
    r")",
    re.I,
)

_PLAN_PAIR_PATTERNS: List[Tuple[re.Pattern, Tuple[str, str]]] = [
    (re.compile(r"\bprofessional\b.*\bportfolio\b|\bportfolio\b.*\bprofessional\b", re.I), ("professional", "portfolio")),
    (re.compile(r"\bsolo\b.*\bportfolio\b|\bportfolio\b.*\bsolo\b", re.I), ("solo", "portfolio")),
    (re.compile(r"\bsolo\b.*\bprofessional\b|\bprofessional\b.*\bsolo\b", re.I), ("solo", "professional")),
]


def is_frustration_or_correction_message(message: str) -> bool:
    return bool(_FRUSTRATION_RE.search((message or "").strip()))


def detect_plan_comparison_pair(text: str) -> Optional[Tuple[str, str]]:
    raw = (text or "").strip()
    if not raw:
        return None
    for pattern, pair in _PLAN_PAIR_PATTERNS:
        if pattern.search(raw):
            return pair
    return None


def _plan_code_for_alias(alias: str) -> Optional[str]:
    key = (alias or "").strip().lower()
    mapping = {
        "solo": "PLAN_1_SOLO",
        "portfolio": "PLAN_2_PORTFOLIO",
        "professional": "PLAN_3_PRO",
    }
    return mapping.get(key)


def _feature_delta_labels(code_a: str, code_b: str) -> List[str]:
    """Registry-only feature differences (b has, a lacks)."""
    try:
        from services.plan_registry import FEATURE_MATRIX, FEATURE_METADATA, PlanCode
    except Exception:
        return []

    codes = {
        "PLAN_1_SOLO": PlanCode.PLAN_1_SOLO,
        "PLAN_2_PORTFOLIO": PlanCode.PLAN_2_PORTFOLIO,
        "PLAN_3_PRO": PlanCode.PLAN_3_PRO,
    }
    pa = codes.get(code_a)
    pb = codes.get(code_b)
    if not pa or not pb:
        return []
    ma = FEATURE_MATRIX.get(pa, {}) or {}
    mb = FEATURE_MATRIX.get(pb, {}) or {}
    deltas: List[str] = []
    for fk, on_b in sorted(mb.items()):
        if not on_b or ma.get(fk):
            continue
        meta = FEATURE_METADATA.get(fk, {}) or {}
        label = (meta.get("name") or fk).strip()
        if label:
            deltas.append(label)
    return deltas[:8]


def build_registry_plan_comparison_reply(pair: Tuple[str, str]) -> Optional[str]:
    """Grounded Solo/Portfolio/Professional comparison from plan_registry."""
    try:
        from services.plan_registry import PLAN_DEFINITIONS, PlanCode
    except Exception:
        return None

    alias_a, alias_b = pair
    code_a = _plan_code_for_alias(alias_a)
    code_b = _plan_code_for_alias(alias_b)
    if not code_a or not code_b:
        return None

    enum_map = {
        "PLAN_1_SOLO": PlanCode.PLAN_1_SOLO,
        "PLAN_2_PORTFOLIO": PlanCode.PLAN_2_PORTFOLIO,
        "PLAN_3_PRO": PlanCode.PLAN_3_PRO,
    }
    pa = PLAN_DEFINITIONS.get(enum_map[code_a], {}) or {}
    pb = PLAN_DEFINITIONS.get(enum_map[code_b], {}) or {}
    if not pa or not pb:
        return None

    name_a = pa.get("name") or alias_a.title()
    name_b = pb.get("name") or alias_b.title()
    lines = [
        f"Sorry if my last reply missed what you needed — here is a direct **{name_a} vs {name_b}** comparison from our current plans:",
        "",
        f"**{name_a}** — up to **{pa.get('max_properties')}** properties, "
        f"**£{float(pa.get('monthly_price', 0)):.0f}/month** + **£{float(pa.get('onboarding_fee', 0)):.0f}** onboarding.",
        f"**{name_b}** — up to **{pb.get('max_properties')}** properties, "
        f"**£{float(pb.get('monthly_price', 0)):.0f}/month** + **£{float(pb.get('onboarding_fee', 0)):.0f}** onboarding.",
        "",
    ]
    extra_b = _feature_delta_labels(code_a, code_b)
    extra_a = _feature_delta_labels(code_b, code_a)
    if extra_b:
        lines.append(f"**{name_b}** also includes (not on **{name_a}**): {', '.join(extra_b)}.")
    if extra_a:
        lines.append(f"**{name_a}** includes (not on **{name_b}**): {', '.join(extra_a)}.")
    lines.append("")
    lines.append("Prices are from our live plan registry. Want help choosing based on how many properties you manage?")
    return "\n".join(lines)


def _underlying_user_messages(
    message: str,
    ctx: Dict[str, Any],
    conversation_history: List[Dict[str, Any]],
) -> List[str]:
    out: List[str] = []
    for turn in conversation_history or []:
        role = (turn.get("role") or turn.get("sender") or "").lower()
        if role in ("user", "customer", "visitor"):
            body = (turn.get("content") or turn.get("message") or "").strip()
            if body and body != message.strip():
                out.append(body)
    recent = ctx.get("recent_entities") or []
    if isinstance(recent, list):
        for item in recent:
            s = str(item).strip()
            if s and s != message.strip() and s not in out:
                out.append(s)
    return out


def try_frustration_recovery_turn(
    message: str,
    ctx: Dict[str, Any],
    conversation_history: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Return a handler dict when the user is correcting/frustrated and we can answer
    the underlying plan comparison from registry facts.
    """
    if not is_frustration_or_correction_message(message):
        return None

    prior_messages = list(reversed(_underlying_user_messages(message, ctx, conversation_history)))
    pair: Optional[Tuple[str, str]] = None
    underlying: Optional[str] = None
    for prior in prior_messages:
        detected = detect_plan_comparison_pair(prior)
        if detected:
            pair = detected
            underlying = prior
            break

    if pair:
        reply = build_registry_plan_comparison_reply(pair)
        if reply:
            from services.support_conversational_orchestrator import touch_session_memory

            touch_session_memory(message, ctx)
            ctx["active_topic"] = "pricing"
            ctx["last_support_area"] = "plan_comparison"
            return {
                "response": reply,
                "action": "respond",
                "metadata": {
                    "conversation_recovery": True,
                    "recovery_kind": "plan_comparison",
                    "plan_comparison_pair": list(pair),
                    "underlying_question": (underlying or "")[:300],
                    "frustration_detected": True,
                },
                "conversation_context": ctx,
            }

    from services.support_conversational_orchestrator import touch_session_memory

    touch_session_memory(message, ctx)
    clarify = (
        "Sorry — I may have misunderstood you. I won't repeat the last answer. "
        "What were you trying to find out — plan comparison, pricing, sign-up, billing, or speaking to someone on the team?"
    )
    if prior_messages:
        snippet = prior_messages[0][:120]
        clarify = (
            f"Sorry — I may have misunderstood. Your earlier question looked like: “{snippet}”. "
            "Tell me in one line what you want compared or fixed, and I'll answer that directly."
        )
    return {
        "response": clarify,
        "action": "respond",
        "metadata": {
            "conversation_recovery": True,
            "recovery_kind": "clarify_after_frustration",
            "frustration_detected": True,
        },
        "conversation_context": ctx,
    }
