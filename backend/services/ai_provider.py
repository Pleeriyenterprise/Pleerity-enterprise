"""
AI provider for compliance document field extraction only.
Input: extracted text (no raw binary). Output: strict JSON schema only.

Uses document_extraction_llm_gateway: OpenAI primary, Gemini fallback.
Config: utils.ai_config (AI_ENABLED, OPENAI_API_KEY, etc.).
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from utils import ai_config

from services.document_extraction_llm_gateway import (
    complete_document_extraction_llm,
    is_any_document_extraction_llm_configured,
    validate_extraction_json,
)
from services.extraction_error_presentation import user_facing_extraction_message
from services.lifecycle_extraction_profiles import ExtractionProfile
from services.lifecycle_profile_extraction import (
    build_profile_system_prompt,
    normalize_profile_extraction,
    validate_profile_extraction_json,
)

logger = logging.getLogger(__name__)

AI_EXTRACTION_PROMPT_VERSION = __import__("os").getenv("AI_EXTRACTION_PROMPT_VERSION", "v1")

DOC_TYPES = {"GAS_SAFETY", "EICR", "EPC", "HMO_LICENCE", "TENANCY", "INSURANCE", "UNKNOWN"}

EXTRACTION_SCHEMA = """
{
  "doc_type": "GAS_SAFETY | EICR | EPC | HMO_LICENCE | TENANCY | INSURANCE | UNKNOWN",
  "certificate_number": null or string,
  "issue_date": null or "YYYY-MM-DD",
  "expiry_date": null or "YYYY-MM-DD",
  "inspector_company": null or string,
  "inspector_id": null or string,
  "address_line_1": null or string,
  "postcode": null or string,
  "requirement_key": null or string (e.g. gas_safety, eicr),
  "confidence": {
    "overall": 0.0 to 1.0,
    "dates": 0.0 to 1.0,
    "address": 0.0 to 1.0,
    "doc_type": 0.0 to 1.0
  },
  "notes": null or string
}
"""

SYSTEM_PROMPT = f"""You extract structured fields from UK property compliance document text only.
Output MUST be valid JSON matching this schema exactly. Return ONLY the JSON object, no markdown or explanation.

Schema:
{EXTRACTION_SCHEMA}

RULES (mandatory):
1. Do NOT give legal advice or compliance verdicts. You only extract visible facts.
2. Do NOT infer facts that are not clearly stated in the text.
3. If uncertain about any field, set it to null and use lower confidence (0.0-0.5).
4. Dates must be YYYY-MM-DD. If only partial date visible, use null or the part you know.
5. doc_type must be exactly one of: GAS_SAFETY, EICR, EPC, HMO_LICENCE, TENANCY, INSURANCE, UNKNOWN.
6. requirement_key should match doc_type (e.g. gas_safety for GAS_SAFETY, eicr for EICR).
7. Postcode: UK format only. If not clearly a postcode, set to null.
8. confidence values must be numbers between 0 and 1.
"""


def _base_failure(
    error_code: str,
    *,
    raw_message: Optional[str] = None,
    raw_response_json: Optional[str] = None,
    llm_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "error_code": error_code,
        "error_message": user_facing_extraction_message(error_code, raw_message),
        "extracted": None,
        "raw_response_json": raw_response_json,
        "model": (llm_meta or {}).get("model_used") or ai_config.AI_MODEL,
        "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
        "tokens_in": (llm_meta or {}).get("tokens_in"),
        "tokens_out": (llm_meta or {}).get("tokens_out"),
        "provider_used": (llm_meta or {}).get("provider_used"),
        "fallback_used": (llm_meta or {}).get("fallback_used"),
        "llm_error_class": (llm_meta or {}).get("llm_error_class"),
        "llm_latency_ms": (llm_meta or {}).get("llm_latency_ms"),
        "extraction_attempted_at": (llm_meta or {}).get("extraction_attempted_at"),
    }


def _llm_meta_from_result(result) -> Dict[str, Any]:
    return {
        "provider_used": result.provider_used,
        "model_used": result.model_used,
        "fallback_used": result.fallback_used,
        "llm_error_class": result.llm_error_class,
        "llm_latency_ms": result.llm_latency_ms,
        "extraction_attempted_at": result.extraction_attempted_at,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
    }


async def extract_compliance_fields_async(
    text: str,
    file_name: str,
    hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract compliance fields from document text (async, OpenAI primary / Gemini fallback).
    """
    if not ai_config.AI_ENABLED:
        return _base_failure("AI_NOT_CONFIGURED")

    if not is_any_document_extraction_llm_configured():
        return _base_failure("AI_NOT_CONFIGURED")

    if not text or not text.strip():
        return _base_failure("NO_TEXT")

    hint_str = ""
    if hints:
        hint_str = f" Hints: {json.dumps(hints)}."
    user_content = f"Document filename: {file_name}.{hint_str}\n\nExtract fields from this document text:\n\n{text}"

    llm_result = await complete_document_extraction_llm(
        SYSTEM_PROMPT,
        user_content[:30000],
        validate_output=validate_extraction_json,
        temperature=ai_config.AI_TEMPERATURE,
        max_tokens=ai_config.AI_MAX_OUTPUT_TOKENS,
    )

    if llm_result is None:
        return _base_failure("AI_EXTRACTION_UNAVAILABLE")

    llm_meta = _llm_meta_from_result(llm_result)
    raw_text = llm_result.text

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.warning("AI extraction JSON decode error: %s", e)
        return _base_failure(
            "PARSE_ERROR",
            raw_message=str(e),
            raw_response_json=raw_text,
            llm_meta=llm_meta,
        )

    extracted = _normalize_extraction(parsed)
    return {
        "success": True,
        "error_code": None,
        "error_message": None,
        "extracted": extracted,
        "raw_response_json": raw_text,
        "model": llm_result.model_used,
        "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
        "tokens_in": llm_result.tokens_in,
        "tokens_out": llm_result.tokens_out,
        "provider_used": llm_result.provider_used,
        "fallback_used": llm_result.fallback_used,
        "llm_error_class": llm_result.llm_error_class,
        "llm_latency_ms": llm_result.llm_latency_ms,
        "extraction_attempted_at": llm_result.extraction_attempted_at,
    }


async def extract_profile_aware_fields_async(
    text: str,
    file_name: str,
    profile: ExtractionProfile,
    hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Profile-aware extraction (Phase 2 S5-extract). Uses per-profile schema and prompts.
    """
    if not ai_config.AI_ENABLED:
        return _base_failure("AI_NOT_CONFIGURED")

    if not is_any_document_extraction_llm_configured():
        return _base_failure("AI_NOT_CONFIGURED")

    if not text or not text.strip():
        return _base_failure("NO_TEXT")

    hint_str = ""
    if hints:
        hint_str = f" Hints: {json.dumps(hints)}."
    user_content = (
        f"Document filename: {file_name}.{hint_str}\n\n"
        f"Extract fields from this document text:\n\n{text}"
    )
    system_prompt = build_profile_system_prompt(profile)

    def _validate(raw: str) -> bool:
        return validate_profile_extraction_json(raw, profile)

    llm_result = await complete_document_extraction_llm(
        system_prompt,
        user_content[:30000],
        validate_output=_validate,
        temperature=ai_config.AI_TEMPERATURE,
        max_tokens=ai_config.AI_MAX_OUTPUT_TOKENS,
    )

    if llm_result is None:
        return _base_failure("AI_EXTRACTION_UNAVAILABLE")

    llm_meta = _llm_meta_from_result(llm_result)
    raw_text = llm_result.text

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.warning("Profile AI extraction JSON decode error: %s", e)
        return _base_failure(
            "PARSE_ERROR",
            raw_message=str(e),
            raw_response_json=raw_text,
            llm_meta=llm_meta,
        )

    extracted = normalize_profile_extraction(parsed, profile)
    prompt_version = f"{AI_EXTRACTION_PROMPT_VERSION}:{profile.profile_id}"
    return {
        "success": True,
        "error_code": None,
        "error_message": None,
        "extracted": extracted,
        "raw_response_json": raw_text,
        "model": llm_result.model_used,
        "prompt_version": prompt_version,
        "tokens_in": llm_result.tokens_in,
        "tokens_out": llm_result.tokens_out,
        "provider_used": llm_result.provider_used,
        "fallback_used": llm_result.fallback_used,
        "llm_error_class": llm_result.llm_error_class,
        "llm_latency_ms": llm_result.llm_latency_ms,
        "extraction_attempted_at": llm_result.extraction_attempted_at,
        "extraction_profile_id": profile.profile_id,
    }


def extract_profile_aware_fields(
    text: str,
    file_name: str,
    profile: ExtractionProfile,
    hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sync wrapper for profile-aware extraction."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                extract_profile_aware_fields_async(text, file_name, profile, hints),
            )
            return future.result()
    return asyncio.run(extract_profile_aware_fields_async(text, file_name, profile, hints))


def extract_compliance_fields(
    text: str,
    file_name: str,
    hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sync wrapper for background threads and legacy callers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                extract_compliance_fields_async(text, file_name, hints),
            )
            return future.result()
    return asyncio.run(extract_compliance_fields_async(text, file_name, hints))


def _normalize_extraction(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure doc_type in enum, confidence 0-1, dates YYYY-MM-DD or null."""
    doc_type = (parsed.get("doc_type") or "UNKNOWN").upper().replace(" ", "_")
    if doc_type not in DOC_TYPES:
        doc_type = "UNKNOWN"
    confidence = parsed.get("confidence") or {}
    for k in ("overall", "dates", "address", "doc_type"):
        v = confidence.get(k)
        if v is not None:
            try:
                confidence[k] = max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                confidence[k] = 0.0
    if "overall" not in confidence:
        confidence["overall"] = 0.5
    for key in ("issue_date", "expiry_date"):
        v = parsed.get(key)
        if v is None or v == "":
            parsed = {**parsed, key: None}
        elif isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v):
            parsed = {**parsed, key: v[:10]}
        else:
            parsed = {**parsed, key: None}
    return {
        "doc_type": doc_type,
        "certificate_number": parsed.get("certificate_number") or None,
        "issue_date": parsed.get("issue_date"),
        "expiry_date": parsed.get("expiry_date"),
        "inspector_company": parsed.get("inspector_company") or None,
        "inspector_id": parsed.get("inspector_id") or None,
        "address_line_1": parsed.get("address_line_1") or None,
        "postcode": parsed.get("postcode") or None,
        "requirement_key": parsed.get("requirement_key") or None,
        "confidence": confidence,
        "notes": parsed.get("notes") or None,
    }
