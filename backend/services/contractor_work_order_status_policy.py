"""
Strict work-order status transitions a contractor may apply via PATCH (portal JWT or job link).

OPEN / ASSIGNED are handled by accept/decline endpoints, not PATCH.
Terminal states (COMPLETED, CANCELLED, CLOSED, VERIFIED) are not mutable by contractor PATCH.
"""
from __future__ import annotations

from typing import Optional, Tuple

from services import maintenance_service as ms

# Forward-only operational path: scheduled → work underway / parts wait → complete.
_CONTRACTOR_PATCH_TRANSITIONS = {
    ms.STATUS_SCHEDULED: (ms.STATUS_IN_PROGRESS, ms.STATUS_AWAITING_PARTS),
    ms.STATUS_IN_PROGRESS: (ms.STATUS_AWAITING_PARTS, ms.STATUS_COMPLETED),
    ms.STATUS_AWAITING_PARTS: (ms.STATUS_IN_PROGRESS, ms.STATUS_COMPLETED),
}

_CONTRACTOR_PATCH_TARGET_STATUSES = frozenset(
    {
        ms.STATUS_SCHEDULED,
        ms.STATUS_IN_PROGRESS,
        ms.STATUS_AWAITING_PARTS,
        ms.STATUS_COMPLETED,
    }
)


def validate_contractor_status_patch(current: Optional[str], new: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Returns (ok, error_message). ``new`` None means no status change in the PATCH body.
    Same current→current is allowed (idempotent).
    """
    if not new or not str(new).strip():
        return True, None
    nxt = str(new).strip().upper()
    if nxt not in _CONTRACTOR_PATCH_TARGET_STATUSES:
        return False, "Contractors may only set status to SCHEDULED, IN_PROGRESS, AWAITING_PARTS, or COMPLETED."

    cur = (current or "").strip().upper()
    if cur == nxt:
        return True, None

    targets = _CONTRACTOR_PATCH_TRANSITIONS.get(cur)
    if targets is None:
        return False, (
            f"Cannot change status from {cur or 'UNKNOWN'} here. "
            "If the job is still assigned to you and shows OPEN or ASSIGNED, use Accept or Decline first."
        )

    if nxt not in targets:
        allowed = ", ".join(targets)
        return False, f"From {cur}, the next allowed step is one of: {allowed}."

    return True, None
