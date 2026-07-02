"""Greeting authority — one governed salutation pattern for customer emails."""

from __future__ import annotations

import re
from typing import Optional

_INVALID_NAME_TOKENS = frozenset(
    {
        "",
        "there",
        "customer",
        "valued customer",
        "client",
        "user",
        "recipient",
    }
)

# Patterns stripped from HTML fragments to prevent double greetings.
_EMBEDDED_GREETING_PATTERNS = (
    re.compile(r"<p>\s*Hi\s*,?\s*</p>", re.I),
    re.compile(r"<p>\s*Hi\s+[^<]{0,80},?\s*</p>", re.I),
    re.compile(r"<p>\s*Hello\s+there\s*,?\s*</p>", re.I),
    re.compile(r"<p>\s*Hello\s+[^<]{0,80},?\s*</p>", re.I),
    re.compile(r"^\s*Hi\s*,?\s*\n", re.I | re.M),
    re.compile(r"^\s*Hello\s+[^\n,]{0,80},?\s*\n", re.I | re.M),
)


def _normalize_name_token(name: Optional[str]) -> str:
    return (name or "").strip()


def _first_name_from_display(name: str) -> Optional[str]:
    token = name.split()[0].strip() if name else ""
    if not token or token.lower() in _INVALID_NAME_TOKENS:
        return None
    return token


def resolve_greeting(
    display_name: Optional[str] = None,
    *,
    first_name: Optional[str] = None,
    client_name: Optional[str] = None,
) -> str:
    """
  Governed greeting:
  - Named customer → ``Hello {First},``
  - Missing / invalid → ``Hello,``
  Never ``Hello there,``, ``Hi ,``, or ``Valued Customer``.
    """
    candidates = [first_name, display_name, client_name]
    for raw in candidates:
        name = _normalize_name_token(raw)
        if not name or name.lower() in _INVALID_NAME_TOKENS:
            continue
        first = _first_name_from_display(name)
        if first:
            return f"Hello {first},"
    return "Hello,"


def strip_embedded_greetings(html_or_text: str) -> str:
    """Remove leading greeting lines/paragraphs from template fragments."""
    out = html_or_text or ""
    for pat in _EMBEDDED_GREETING_PATTERNS:
        out = pat.sub("", out, count=1)
    return out.strip()
