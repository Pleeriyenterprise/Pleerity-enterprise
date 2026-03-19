"""
Unified document-generation LLM calls with OpenAI ↔ Gemini failover.

Primary default: OpenAI. Secondary: Gemini.

Failover triggers: 429, quota / rate limit signals, timeouts, Google ResourceExhausted.
Also fails over if the preferred provider is not configured (missing key) so the other may work.

Logs: primary provider, whether fallback ran, and reason.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = float(os.environ.get("DOCUMENT_LLM_TIMEOUT_SECONDS", "120") or "120")
DEFAULT_PREFERRED = (os.environ.get("DOCUMENT_LLM_PREFERRED_PROVIDER", "openai") or "openai").strip().lower()


@dataclass
class UnifiedLLMResult:
    """Successful generation outcome."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    provider_used: str  # "openai" | "gemini"
    model_used: str
    fallback_used: bool
    primary_provider: str
    fallback_reason: Optional[str] = None


def _error_summary(exc: BaseException) -> str:
    parts = [type(exc).__name__]
    msg = str(exc).strip()
    if msg:
        parts.append(msg[:200])
    try:
        import openai

        if isinstance(exc, openai.APIStatusError):
            parts.append(f"status={getattr(exc, 'status_code', '')}")
    except ImportError:
        pass
    return ":".join(parts)


def should_attempt_failover(exc: BaseException) -> bool:
    """
    True if we should try the alternate provider (transient / capacity / missing config).
    """
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    msg = str(exc).lower()

    try:
        import openai

        if isinstance(exc, openai.RateLimitError):
            return True
        if isinstance(exc, openai.APITimeoutError):
            return True
        if isinstance(exc, openai.APIConnectionError):
            return True
        if isinstance(exc, openai.APIStatusError) and getattr(exc, "status_code", None) == 429:
            return True
    except ImportError:
        pass

    try:
        from google.api_core import exceptions as gexc

        if isinstance(exc, (gexc.ResourceExhausted, gexc.TooManyRequests)):
            return True
        if isinstance(exc, gexc.DeadlineExceeded):
            return True
    except ImportError:
        pass

    if "429" in msg or "rate limit" in msg or "quota" in msg or "resource exhausted" in msg:
        return True
    if "timeout" in msg or "timed out" in msg or "deadline exceeded" in msg:
        return True

    # No API key / not configured → try other provider
    if isinstance(exc, ValueError):
        if any(
            x in msg
            for x in (
                "not set",
                "not found in environment",
                "not configured",
                "not installed",
                "api_key",
            )
        ):
            return True
    return False


async def _call_openai(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    model: str,
    timeout_s: float,
) -> Tuple[str, int, int]:
    import os as _os

    from utils import ai_config

    api_key = getattr(ai_config, "get_openai_api_key", lambda: None)() or _os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set (required for OpenAI provider)")
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise ValueError("openai package not installed. pip install openai")
    client = AsyncOpenAI(api_key=api_key, timeout=timeout_s)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=min(max(temperature, 0.0), 2.0),
        max_tokens=max_tokens,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise ValueError("Empty response from OpenAI")
    usage = getattr(response, "usage", None)
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    return text, int(pt), int(ct)


async def _call_gemini(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
    timeout_s: float,
) -> Tuple[str, int, int]:
    from utils.llm_chat import _get_api_key

    if not _get_api_key():
        raise ValueError("LLM_API_KEY not found in environment")
    loop = asyncio.get_event_loop()

    def _sync() -> str:
        import google.generativeai as genai

        api_key = _get_api_key()
        genai.configure(api_key=api_key)
        model_name = model if model and "gemini" in model else "gemini-2.0-flash"
        gemini = genai.GenerativeModel(model_name, system_instruction=system_prompt)
        response = gemini.generate_content(user_prompt)
        if not response or not response.text:
            raise ValueError("Empty response from LLM")
        return response.text

    try:
        text = await asyncio.wait_for(loop.run_in_executor(None, _sync), timeout=timeout_s)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(f"Gemini generation exceeded {timeout_s}s") from None
    # Token counts not consistently exposed from sync SDK; approximate for metrics
    pt = len(system_prompt.split()) + len(user_prompt.split())
    ct = len(text.split()) if text else 0
    return text.strip(), pt, ct


def _normalize_preferred(preferred: Optional[str]) -> str:
    p = (preferred or DEFAULT_PREFERRED or "openai").strip().lower()
    if p not in ("openai", "gemini"):
        logger.warning("Invalid DOCUMENT_LLM_PREFERRED_PROVIDER=%s; using openai", p)
        return "openai"
    return p


async def generate_with_failover(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    preferred_provider: Optional[str] = None,
    openai_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> UnifiedLLMResult:
    """
    Try preferred provider first; on failover-eligible errors, try the other.
    Raises last exception if both fail or second fails.
    """
    from utils import ai_config

    primary = _normalize_preferred(preferred_provider)
    secondary = "gemini" if primary == "openai" else "openai"
    timeout_s = float(timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_S)

    oa_model = openai_model or getattr(ai_config, "AI_MODEL", None) or os.environ.get(
        "OPENAI_DOCUMENT_MODEL", "gpt-4o-mini"
    )
    gm_model = gemini_model or os.environ.get("DOCUMENT_GEMINI_MODEL", "gemini-2.0-flash")

    order = [(primary, primary), (secondary, secondary)]
    fallback_reason: Optional[str] = None
    last_exc: Optional[BaseException] = None
    primary_failure: Optional[BaseException] = None

    for attempt, (prov, _) in enumerate(order):
        try:
            if prov == "openai":
                text, pt, ct = await _call_openai(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=oa_model,
                    timeout_s=timeout_s,
                )
                model_used = oa_model
            else:
                text, pt, ct = await _call_gemini(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=gm_model,
                    timeout_s=timeout_s,
                )
                model_used = gm_model

            fb = attempt > 0
            logger.info(
                "document_llm_ok provider_used=%s model=%s fallback_used=%s primary_attempted=%s fallback_reason=%s",
                prov,
                model_used,
                fb,
                primary,
                fallback_reason or "-",
            )
            return UnifiedLLMResult(
                text=text,
                prompt_tokens=pt,
                completion_tokens=ct,
                provider_used=prov,
                model_used=model_used,
                fallback_used=fb,
                primary_provider=primary,
                fallback_reason=fallback_reason,
            )
        except BaseException as e:
            last_exc = e
            summary = _error_summary(e)
            if attempt == 0 and should_attempt_failover(e):
                primary_failure = e
                fallback_reason = f"{primary}_failed:{summary}"
                logger.warning(
                    "document_llm_failover primary=%s error=%s; trying secondary=%s",
                    primary,
                    summary,
                    secondary,
                )
                continue
            logger.error("document_llm_failed provider=%s error=%s", prov, summary)
            if attempt == 1 and primary_failure is not None:
                raise RuntimeError(
                    f"Both LLM providers failed after failover. "
                    f"Primary ({primary}): {_error_summary(primary_failure)}; "
                    f"Secondary ({secondary}): {summary}"
                ) from e
            raise

    logger.error("document_llm_exhausted_providers primary=%s", primary)
    if last_exc:
        raise last_exc
    raise RuntimeError("document_llm: no provider attempted")


def get_default_preferred_provider() -> str:
    return _normalize_preferred(None)
