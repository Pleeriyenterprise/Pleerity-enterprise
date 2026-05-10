"""
Client-safe propagation notices (L-009) when RST core backbone gates defer work.

Additive only — does not change authority, queue, or activation decisions.
See ``docs/launch/LAUNCH_AUTHORITY_TRACKER.md`` L-009 and ``merge_rst_core_backbone_activation_into_fanout``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

# Stable codes for clients / integrators (not internal activation_reason strings).
NOTICE_AUTHORITY_SYNC_DEFERRED = "COMPLIANCE_PROPAGATION_DEFERRED_AUTHORITY_SYNC"
NOTICE_RECALC_ENQUEUE_DEFERRED = "COMPLIANCE_PROPAGATION_DEFERRED_SCORE_RECALC"


def _message_for_authority_sync_blocked() -> str:
    return (
        "Linked requirement evidence was not fully synchronised yet because compliance processing "
        "is temporarily limited by platform settings. Scores and obligation views will catch up when processing resumes."
    )


def _message_for_recalc_enqueue_blocked() -> str:
    return (
        "A background compliance score refresh was not queued because compliance processing is temporarily "
        "limited by platform settings. Your headline score may update later when processing resumes."
    )


def _fanout_has_recalc_enqueue_blocked_by_backbone(fanout: Dict[str, Any]) -> bool:
    targets = fanout.get("downstream_trigger_targets") or fanout.get("downstream_propagation") or []
    if not isinstance(targets, list):
        return False
    for row in targets:
        if not isinstance(row, dict):
            continue
        tgt = str(row.get("downstream_target") or "")
        stage = str(row.get("propagation_stage") or "")
        if "compliance_recalc_queue.enqueue_compliance_recalc" not in tgt:
            continue
        if "rst_core_backbone_blocked_skip_enqueue" in stage:
            return True
    return False


def merge_propagation_notice_from_ordered_transition_fanouts(
    ordered_fanouts: Sequence[Optional[Dict[str, Any]]],
) -> Optional[Dict[str, str]]:
    """
    Merge client-safe notices from multiple transition fanouts (e.g. admin requirement relink).

    * **Order:** ``ordered_fanouts`` is caller-defined — for relink use **prior requirement fanout,
      then new requirement fanout** when both exist.
    * **Precedence:** ``NOTICE_AUTHORITY_SYNC_DEFERRED`` wins over ``NOTICE_RECALC_ENQUEUE_DEFERRED``.
      Within the same code, the **first** matching fanout in order wins.
    """
    first_recalc: Optional[Dict[str, str]] = None
    for fo in ordered_fanouts:
        if not fo:
            continue
        n = build_propagation_notice_from_transition_fanout(fo)
        if not n:
            continue
        code = n.get("code")
        if code == NOTICE_AUTHORITY_SYNC_DEFERRED:
            return n
        if code == NOTICE_RECALC_ENQUEUE_DEFERRED and first_recalc is None:
            first_recalc = n
    return first_recalc


def build_propagation_notice_from_transition_fanout(
    transition_fanout: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """
    Return a small notice dict for API responses, or None when propagation was not deferred
    by backbone visibility rules on this fanout.
    """
    if not transition_fanout or not isinstance(transition_fanout, dict):
        return None
    act = transition_fanout.get("rst_core_backbone_activation")
    if isinstance(act, dict) and act.get("permitted") is False:
        return {"code": NOTICE_AUTHORITY_SYNC_DEFERRED, "message": _message_for_authority_sync_blocked()}
    if _fanout_has_recalc_enqueue_blocked_by_backbone(transition_fanout):
        return {"code": NOTICE_RECALC_ENQUEUE_DEFERRED, "message": _message_for_recalc_enqueue_blocked()}
    return None
