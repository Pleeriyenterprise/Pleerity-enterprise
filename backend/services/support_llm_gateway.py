"""
LLM gateway for the public support AI brain.

Provider order (configurable, defaults OpenAI → Gemini):
  - Primary: OpenAI (OPENAI_API_KEY, model SUPPORT_AI_OPENAI_MODEL or AI_MODEL)
  - Fallback: Gemini (LLM_API_KEY, model SUPPORT_AI_GEMINI_MODEL)

Does not log prompts or API keys. Returns None when no provider succeeds so the
legacy support stack can handle the turn.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

from services.unified_llm_service import should_attempt_failover

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = float(os.environ.get("SUPPORT_AI_LLM_TIMEOUT_SECONDS", "45") or "45")
DEFAULT_PRIMARY = (os.environ.get("SUPPORT_AI_PRIMARY_PROVIDER", "openai") or "openai").strip().lower()
DEFAULT_FALLBACK = (os.environ.get("SUPPORT_AI_FALLBACK_PROVIDER", "gemini") or "gemini").strip().lower()
DEFAULT_OPENAI_MODEL = (
    os.environ.get("SUPPORT_AI_OPENAI_MODEL")
    or os.environ.get("AI_MODEL")
    or "gpt-4o-mini"
).strip()
DEFAULT_GEMINI_MODEL = (
    os.environ.get("SUPPORT_AI_GEMINI_MODEL")
    or os.environ.get("DOCUMENT_GEMINI_MODEL")
    or "gemini-2.0-flash"
).strip()

ValidateFn = Callable[[str], bool]


@dataclass
class SupportLLMResult:
    text: str
    provider_used: str
    model_used: str
    fallback_used: bool
    llm_latency_ms: int
    primary_provider: str
    llm_error_class: Optional[str] = None  # redacted summary when failover/failure


def _normalize_provider(name: str, default: str) -> str:
    p = (name or default).strip().lower()
    if p not in ("openai", "gemini"):
        logger.warning("Invalid support LLM provider %r; using %s", name, default)
        return default
    return p


def _openai_configured() -> bool:
    try:
        from utils import ai_config

        key = getattr(ai_config, "get_openai_api_key", lambda: None)()
        if key:
            return True
    except Exception:
        pass
    return bool((os.environ.get("OPENAI_API_KEY") or "").strip())


def _gemini_configured() -> bool:
    return bool((os.environ.get("LLM_API_KEY") or "").strip())


def is_any_support_llm_configured() -> bool:
    """True if at least one configured provider can be attempted."""
    return _openai_configured() or _gemini_configured()


def _provider_configured(provider: str) -> bool:
    return _openai_configured() if provider == "openai" else _gemini_configured()


def _redact_error_class(exc: BaseException) -> str:
    """Safe error label for metadata/logs — no message bodies (may contain user text)."""
    return type(exc).__name__


def _error_summary_for_log(exc: BaseException) -> str:
    """Short log-safe summary (truncated, no keys)."""
    parts = [_redact_error_class(exc)]
    msg = str(exc).strip().lower()
    if not msg:
        return parts[0]
    if "api_key" in msg or "api key" in msg:
        parts.append("missing_or_invalid_key")
    elif "timeout" in msg or "timed out" in msg:
        parts.append("timeout")
    elif "429" in msg or "rate limit" in msg or "quota" in msg:
        parts.append("rate_limit")
    elif "empty response" in msg:
        parts.append("empty_response")
    else:
        parts.append("provider_error")
    return ":".join(parts)


async def _invoke_provider(
    provider: str,
    *,
    system_prompt: str,
    user_prompt: str,
    openai_model: str,
    gemini_model: str,
    timeout_s: float,
    temperature: float,
    max_tokens: int,
) -> str:
    from services.unified_llm_service import _call_gemini, _call_openai

    if provider == "openai":
        text, _, _ = await _call_openai(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=openai_model,
            timeout_s=timeout_s,
        )
        return text
    text, _, _ = await _call_gemini(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=gemini_model,
        timeout_s=timeout_s,
    )
    return text


async def complete_support_planner(
    system_prompt: str,
    user_prompt: str,
    *,
    validate_output: Optional[ValidateFn] = None,
    temperature: float = 0.25,
    max_tokens: int = 1200,
    timeout_seconds: Optional[float] = None,
) -> Optional[SupportLLMResult]:
    """
    Run support planner LLM with primary then optional fallback provider.

    If validate_output is set, invalid primary output triggers one fallback attempt
    (without calling fallback when primary output is valid).

    Returns None if no provider is configured or both attempts fail validation.
    """
    if not is_any_support_llm_configured():
        logger.info("support_llm: no provider keys configured; skipping LLM")
        return None

    primary = _normalize_provider(DEFAULT_PRIMARY, "openai")
    fallback = _normalize_provider(DEFAULT_FALLBACK, "gemini")
    if fallback == primary:
        fallback = "gemini" if primary == "openai" else "openai"

    timeout_s = float(timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_S)
    t_start = time.perf_counter()

    last_error_class: Optional[str] = None
    primary_error: Optional[BaseException] = None

    # --- Primary ---
    if _provider_configured(primary):
        try:
            raw = await _invoke_provider(
                primary,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                openai_model=DEFAULT_OPENAI_MODEL,
                gemini_model=DEFAULT_GEMINI_MODEL,
                timeout_s=timeout_s,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            valid = validate_output(raw) if validate_output else bool((raw or "").strip())
            if valid:
                latency = int((time.perf_counter() - t_start) * 1000)
                model_used = DEFAULT_OPENAI_MODEL if primary == "openai" else DEFAULT_GEMINI_MODEL
                logger.info(
                    "support_llm_ok provider=%s model=%s fallback_used=false latency_ms=%s",
                    primary,
                    model_used,
                    latency,
                )
                return SupportLLMResult(
                    text=raw,
                    provider_used=primary,
                    model_used=model_used,
                    fallback_used=False,
                    llm_latency_ms=latency,
                    primary_provider=primary,
                )
            last_error_class = "invalid_planner_json"
            logger.warning(
                "support_llm_invalid_output provider=%s; will try fallback if configured",
                primary,
            )
        except BaseException as e:
            primary_error = e
            last_error_class = _error_summary_for_log(e)
            logger.warning(
                "support_llm_fail provider=%s error=%s",
                primary,
                last_error_class,
            )
    else:
        last_error_class = f"{primary}_not_configured"

    # --- Fallback (once) ---
    if not _provider_configured(fallback):
        logger.warning(
            "support_llm_unavailable primary=%s fallback=%s not_configured last_error=%s",
            primary,
            fallback,
            last_error_class,
        )
        return None

    if primary_error is not None and not should_attempt_failover(primary_error):
        if last_error_class != "invalid_planner_json":
            return None

    try:
        raw = await _invoke_provider(
            fallback,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            openai_model=DEFAULT_OPENAI_MODEL,
            gemini_model=DEFAULT_GEMINI_MODEL,
            timeout_s=timeout_s,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        valid = validate_output(raw) if validate_output else bool((raw or "").strip())
        if not valid:
            logger.warning(
                "support_llm_invalid_output provider=%s fallback=true",
                fallback,
            )
            return None
        latency = int((time.perf_counter() - t_start) * 1000)
        model_used = DEFAULT_OPENAI_MODEL if fallback == "openai" else DEFAULT_GEMINI_MODEL
        logger.info(
            "support_llm_ok provider=%s model=%s fallback_used=true latency_ms=%s",
            fallback,
            model_used,
            latency,
        )
        return SupportLLMResult(
            text=raw,
            provider_used=fallback,
            model_used=model_used,
            fallback_used=True,
            llm_latency_ms=latency,
            primary_provider=primary,
            llm_error_class=last_error_class,
        )
    except BaseException as e:
        logger.warning(
            "support_llm_fail provider=%s fallback=true error=%s",
            fallback,
            _error_summary_for_log(e),
        )
        return None
