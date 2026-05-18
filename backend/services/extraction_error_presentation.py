"""User-safe extraction error messages — no raw provider errors in UI."""
from __future__ import annotations

import re
from typing import Optional

_USER_MESSAGES = {
    "AI_NOT_CONFIGURED": "Extraction unavailable — manual review required.",
    "AI_EXTRACTION_UNAVAILABLE": "Extraction unavailable — manual review required.",
    "NO_TEXT": "Could not read text from this file — enter data manually or try a clearer scan.",
    "NO_TEXT_OCR_FAILED": "Could not read text from this file — enter data manually or try a clearer scan.",
    "PARSE_ERROR": "Extraction failed — review manually.",
    "AI_ERROR": "Extraction failed — review manually.",
    "RATE_LIMITED": "Extraction temporarily unavailable — try again later or enter data manually.",
}

_PROVIDER_LEAK_PATTERNS = re.compile(
    r"generativelanguage|googleapis\.com|openai\.com|sk-[a-z]+-|"
    r"quota exceeded|free_tier|resource_exhausted|api[_ ]key",
    re.I,
)


def user_facing_extraction_message(
    error_code: Optional[str],
    raw_message: Optional[str] = None,
) -> str:
    code = (error_code or "AI_ERROR").strip().upper()
    if code in _USER_MESSAGES:
        return _USER_MESSAGES[code]
    if raw_message and _PROVIDER_LEAK_PATTERNS.search(raw_message):
        return _USER_MESSAGES["AI_ERROR"]
    if raw_message and len(raw_message) < 120 and not _looks_like_stack(raw_message):
        return raw_message
    return _USER_MESSAGES["AI_ERROR"]


def _looks_like_stack(msg: str) -> bool:
    return "Traceback" in msg or "File \"" in msg or " at 0x" in msg
