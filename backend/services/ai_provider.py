"""
AI provider for compliance document field extraction only.
Input: extracted text (no raw binary). Output: strict JSON schema only.
No legal advice; no compliance verdicts. If uncertain, return nulls and lower confidence.
"""
import json
import os
import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Env (task spec)
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_MODEL_EXTRACTION = os.getenv("AI_MODEL_EXTRACTION", "gpt-4o-mini")
AI_EXTRACTION_PROMPT_VERSION = os.getenv("AI_EXTRACTION_PROMPT_VERSION", "v1")
AI_EXTRACTION_ENABLED = os.getenv("AI_EXTRACTION_ENABLED", "true").lower() in ("true", "1", "yes")

# Allowed doc_type values (task enum)
DOC_TYPES = {"GAS_SAFETY", "EICR", "EPC", "HMO_LICENCE", "TENANCY", "INSURANCE", "UNKNOWN"}

# Required JSON output schema (task)
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


def _call_openai(text: str, file_name: str, hints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call OpenAI API for extraction. Returns parsed JSON or raises."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=OPENAI_API_KEY)
    hint_str = ""
    if hints:
        hint_str = f" Hints: {json.dumps(hints)}."
    user_content = f"Document filename: {file_name}.{hint_str}\n\nExtract fields from this document text:\n\n{text}"
    response = client.chat.completions.create(
        model=AI_MODEL_EXTRACTION,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content[:30000]},
        ],
        temperature=0.1,
    )
    raw_text = (response.choices[0].message.content or "").strip()
    # Strip markdown code block if present
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
    return json.loads(raw_text), raw_text, getattr(response, "usage", None)


def extract_compliance_fields(
    text: str,
    file_name: str,
    hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract compliance fields from document text only. No legal advice; output is suggested only.
    Returns dict with: extracted payload (normalized), raw_response_json, model, prompt_version,
    tokens_in, tokens_out (if available). On failure raises or returns error payload.
    """
    if not AI_EXTRACTION_ENABLED:
        return {
            "success": False,
            "error_code": "AI_NOT_CONFIGURED",
            "error_message": "AI extraction is disabled (AI_EXTRACTION_ENABLED=false).",
            "extracted": None,
            "raw_response_json": None,
            "model": AI_MODEL_EXTRACTION,
            "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
            "tokens_in": None,
            "tokens_out": None,
        }
    if not text or not text.strip():
        return {
            "success": False,
            "error_code": "NO_TEXT",
            "error_message": "No text provided for extraction.",
            "extracted": None,
            "raw_response_json": None,
            "model": AI_MODEL_EXTRACTION,
            "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
            "tokens_in": None,
            "tokens_out": None,
        }
    if AI_PROVIDER != "openai":
        return {
            "success": False,
            "error_code": "AI_NOT_CONFIGURED",
            "error_message": f"AI_PROVIDER={AI_PROVIDER} not supported; use openai.",
            "extracted": None,
            "raw_response_json": None,
            "model": AI_MODEL_EXTRACTION,
            "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
            "tokens_in": None,
            "tokens_out": None,
        }
    try:
        parsed, raw_text, usage = _call_openai(text, file_name, hints)
    except json.JSONDecodeError as e:
        logger.warning("AI extraction JSON decode error: %s", e)
        return {
            "success": False,
            "error_code": "PARSE_ERROR",
            "error_message": str(e),
            "extracted": None,
            "raw_response_json": raw_text if "raw_text" in dir() else None,
            "model": AI_MODEL_EXTRACTION,
            "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
            "tokens_in": None,
            "tokens_out": None,
        }
    except Exception as e:
        logger.exception("AI extraction call failed: %s", e)
        return {
            "success": False,
            "error_code": "AI_ERROR",
            "error_message": str(e),
            "extracted": None,
            "raw_response_json": None,
            "model": AI_MODEL_EXTRACTION,
            "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
            "tokens_in": None,
            "tokens_out": None,
        }
    # Normalize and validate
    extracted = _normalize_extraction(parsed)
    tokens_in = usage.input_tokens if usage else None
    tokens_out = usage.output_tokens if usage else None
    return {
        "success": True,
        "error_code": None,
        "error_message": None,
        "extracted": extracted,
        "raw_response_json": raw_text,
        "model": AI_MODEL_EXTRACTION,
        "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }


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
    # Normalize dates to YYYY-MM-DD or null
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
