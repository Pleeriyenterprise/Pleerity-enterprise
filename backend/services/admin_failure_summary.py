"""
Admin-safe summarization of generation / LLM failures.

Never intended to forward raw provider stack traces to the admin UI by default.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


def classify_generation_error(
    error_message: Optional[str],
    *,
    error_code: Optional[str] = None,
    both_providers_exhausted: bool = False,
) -> Tuple[str, bool]:
    """
    Returns (error_type, retryable).

    error_type is a stable machine key for analytics (not user-facing prose).
    """
    msg = (error_message or "").lower()
    code = (error_code or "").upper()

    if code in ("LLM_INVALID_JSON", "EMPTY_OUTPUT"):
        return "schema_error", False

    if "not valid json" in msg or ("json" in msg and "parse" in msg):
        return "schema_error", False
    if "schema" in msg or "validation" in msg and "output" in msg:
        return "schema_error", False

    if (
        "quota" in msg
        or "insufficient_quota" in msg
        or "billing" in msg
        or "exceeded your current quota" in msg
    ):
        return "quota_exceeded", True

    if (
        "429" in msg
        or "rate limit" in msg
        or "too many requests" in msg
        or "resource exhausted" in msg
        or "resourceexhausted" in msg
    ):
        return "rate_limit", True

    if "timeout" in msg or "timed out" in msg or "deadline exceeded" in msg:
        return "timeout", True

    if (
        "api_key" in msg
        or "authentication" in msg
        or "401" in msg
        or "403" in msg
        or "invalid api key" in msg
        or "permission denied" in msg
    ):
        return "invalid_api_key", False

    if both_providers_exhausted or "both llm providers failed" in msg:
        # Transient if message suggests rate/quota/timeout inside primary/secondary errors
        if any(x in msg for x in ("429", "quota", "rate", "timeout", "resource exhausted", "deadline")):
            return "provider_exhausted_transient", True
        return "provider_exhausted", False

    if "prompt" in msg and "build" in msg:
        return "prompt_template_error", False

    if "ai service unavailable" in msg or "llm_api_key" in msg:
        return "configuration_error", False

    return "unknown", False


def summarize_generation_failure(
    error_type: str,
    error_message: Optional[str],
) -> Dict[str, Any]:
    """
    Admin-facing short summary. error_message may be raw; we only use it for light context, truncated.
    """
    safe_snippet = re.sub(r"\s+", " ", (error_message or "").strip())[:180]

    catalog = {
        "quota_exceeded": (
            "AI provider quota reached",
            "AI provider quota or billing limit was hit.",
            "Check provider billing and quotas, or retry later.",
        ),
        "rate_limit": (
            "AI rate limit",
            "The AI provider temporarily throttled requests.",
            "Wait and retry, or spread load; consider failover if configured.",
        ),
        "timeout": (
            "Temporary provider timeout",
            "The AI provider did not respond in time.",
            "Retry shortly; if persistent, check provider status and timeouts.",
        ),
        "schema_error": (
            "Generated output failed validation",
            "Model output could not be parsed or did not match the expected structure.",
            "Review prompt/schema alignment and test prompt in Prompt Manager.",
        ),
        "invalid_api_key": (
            "Provider authentication error",
            "API credentials may be missing, revoked, or lack permissions.",
            "Verify OPENAI_API_KEY / Gemini configuration in deployment secrets.",
        ),
        "provider_exhausted_transient": (
            "Providers exhausted (transient)",
            "Both configured providers failed; errors look transient.",
            "Retry after a short delay or switch preferred provider manually.",
        ),
        "provider_exhausted": (
            "Providers exhausted",
            "Both configured providers failed for this generation.",
            "Review error pattern in analytics; may need prompt or data fixes.",
        ),
        "prompt_template_error": (
            "Prompt or template issue",
            "Prompt could not be built from the template and intake data.",
            "Check prompt template variables and intake schema.",
        ),
        "configuration_error": (
            "AI configuration error",
            "Generation blocked by missing or invalid AI configuration.",
            "Fix environment configuration before retrying.",
        ),
        "unknown": (
            "Generation failed",
            "An unexpected error occurred during generation.",
            "Review workflow timeline and generation runs; escalate if recurring.",
        ),
    }

    title, short, action = catalog.get(
        error_type,
        catalog["unknown"],
    )

    inferred_type, retryable_from_msg = classify_generation_error(
        error_message,
        error_code=None,
        both_providers_exhausted=("provider_exhausted" in error_type),
    )
    # Prefer classifier when it agrees with bucket; else fall back to type-based defaults
    retryable_by_type = {
        "quota_exceeded": True,
        "rate_limit": True,
        "timeout": True,
        "schema_error": False,
        "invalid_api_key": False,
        "provider_exhausted_transient": True,
        "provider_exhausted": False,
        "prompt_template_error": False,
        "configuration_error": False,
        "unknown": False,
    }
    retryable = retryable_from_msg if inferred_type == error_type else retryable_by_type.get(error_type, False)

    return {
        "title": title,
        "short_message": short if not safe_snippet else f"{short} ({safe_snippet})".strip()[:300],
        "recommended_action": action,
        "retryable": retryable,
    }


def order_failure_fields_from_message(
    error_message: Optional[str],
    *,
    error_code: Optional[str] = None,
    both_providers_exhausted: bool = False,
) -> Dict[str, Any]:
    """Persistable subset for orders collection."""
    et, retryable = classify_generation_error(
        error_message,
        error_code=error_code,
        both_providers_exhausted=both_providers_exhausted,
    )
    summary = summarize_generation_failure(et, error_message)
    return {
        "last_generation_error_type": et,
        "last_generation_error_short": summary["short_message"][:500],
        "retryable_failure": retryable,
    }
