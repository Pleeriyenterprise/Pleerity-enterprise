"""Minimal policy hooks for promotion decisions under Evidence Review V2."""

from __future__ import annotations

from typing import Any, Dict


def promotions_allowed_for_accept_unverified(
    *,
    validation_snapshot: Dict[str, Any],
    validation_override_reason: str,
) -> bool:
    """
    Requirement-level COMPLIANT promotion when accepting human-evidence.

    FAIL blocks promotion unless an explicit override reason was captured at verify time.
    """
    vs = str(validation_snapshot.get("validation_status") or "").upper()
    override = bool(str(validation_override_reason or "").strip())
    if vs == "FAIL":
        return override
    return True
