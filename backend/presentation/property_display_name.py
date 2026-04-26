"""Shared property display-name resolver for client-facing text."""

from __future__ import annotations

from typing import Any, Dict


def get_property_display_name(property_row: Dict[str, Any] | None) -> str:
    row = property_row or {}
    explicit = str(
        row.get("nickname")
        or row.get("name")
        or row.get("property_name")
        or row.get("property_label")
        or ""
    ).strip()
    if explicit:
        return explicit

    line1 = str(row.get("address_line_1") or "").strip()
    city = str(row.get("city") or row.get("town") or "").strip()
    postcode = str(row.get("postcode") or "").strip()

    if line1 and city:
        return f"{line1}, {city}"
    if line1 and postcode:
        return f"{line1}, {postcode}"
    if line1:
        return line1
    if postcode:
        return postcode
    return "Unnamed property"

