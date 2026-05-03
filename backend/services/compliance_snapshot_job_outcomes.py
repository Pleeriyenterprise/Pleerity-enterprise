"""
Maps capture_all_client_snapshots() aggregates to run_instrumented / job_runs outcome contract.

Keeps scoring and snapshot persistence in compliance_trending; this module is classification only.
"""
from __future__ import annotations

from typing import Any, Dict

from services.job_run_service import (
    OUTCOME_CONDITIONAL_NO_OUTPUT,
    OUTCOME_DEGRADED,
    OUTCOME_FAILED,
    OUTCOME_SUCCESS,
)

COMPLIANCE_SCORE_SNAPSHOTS_JOB_ID = "compliance_score_snapshots"


def should_skip_control_centre_no_outcome_flag(job_id: str, detail: Dict[str, Any]) -> bool:
    """
    Control Centre jobs_flagged_no_expected_outcome: intentional no-work for snapshots
    (no ACTIVE clients) is not a misconfiguration.
    """
    if job_id != COMPLIANCE_SCORE_SNAPSHOTS_JOB_ID:
        return False
    if (detail.get("last_outcome_status") or "").strip().lower() != OUTCOME_CONDITIONAL_NO_OUTPUT:
        return False
    om = detail.get("outcome_metrics") or {}
    return om.get("no_clients") is True or om.get("queue_empty") is True


def build_compliance_score_snapshots_run_result(capture: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the dict returned by run_compliance_score_snapshots for run_instrumented.

    ``capture`` is the return value of capture_all_client_snapshots (never the legacy
    outer-failure dict — callers must raise on catastrophic DB failure).
    """
    total = int(capture.get("total_clients") or 0)
    client_ok = int(capture.get("success_count") or capture.get("clients_succeeded") or 0)
    client_fail = int(capture.get("error_count") or capture.get("clients_failed") or 0)
    ps_created = int(capture.get("property_snapshots_created") or 0)
    ps_failed = int(capture.get("property_snapshot_failures") or 0)
    ps_skipped = int(capture.get("property_snapshots_skipped_no_score") or 0)
    prop_enum_fail = int(capture.get("property_enumeration_failures") or 0)

    attempted = total
    operational_failures = client_fail + ps_failed + prop_enum_fail

    outcome_metrics: Dict[str, Any] = {
        "clients_considered": total,
        "clients_succeeded": client_ok,
        "clients_failed": client_fail,
        "property_snapshots_created": ps_created,
        "property_snapshot_failures": ps_failed,
        "property_snapshots_skipped_no_score": ps_skipped,
        "property_enumeration_failures": prop_enum_fail,
        "attempted_count": attempted,
        "success_count": client_ok,
        "failed_count": operational_failures,
        "no_clients": total == 0,
    }

    if total == 0:
        outcome_metrics["outcome_kind"] = "NO_WORK_ELIGIBLE"
        outcome_metrics["queue_empty"] = True
        return {
            "message": "Compliance score snapshots: no ACTIVE clients to snapshot.",
            "count": 0,
            "errors": 0,
            "outcome_status": OUTCOME_CONDITIONAL_NO_OUTPUT,
            "outcome_metrics": outcome_metrics,
        }

    # Catastrophic: every client portfolio snapshot failed (property rows irrelevant).
    if client_ok == 0 and client_fail == total and total > 0:
        outcome_metrics["outcome_kind"] = "FAILED"
        err_tail = (capture.get("errors") or [])[:3]
        return {
            "message": f"Compliance score snapshots: all {total} client snapshot(s) failed.",
            "count": 0,
            "errors": client_fail,
            "outcome_status": OUTCOME_FAILED,
            "outcome_metrics": outcome_metrics,
            "error_code": "COMPLIANCE_SCORE_SNAPSHOTS_ALL_CLIENTS_FAILED",
            "error_message": f"All {total} client(s) failed; first errors: {err_tail}",
            "stack_trace": None,
        }

    partial_client = client_fail > 0
    partial_property = ps_failed > 0 or prop_enum_fail > 0

    if partial_client or partial_property:
        outcome_metrics["outcome_kind"] = "DEGRADED"
        parts = [
            f"{client_ok}/{total} client portfolio snapshot(s) succeeded",
            f"{client_fail} client failure(s)",
            f"{ps_created} property row(s) written",
            f"{ps_failed} property snapshot failure(s)",
        ]
        if prop_enum_fail:
            parts.append(f"{prop_enum_fail} property list enumeration failure(s)")
        msg = "Compliance score snapshots: " + "; ".join(parts) + "."
        return {
            "message": msg,
            "count": client_ok,
            "errors": operational_failures,
            "outcome_status": OUTCOME_DEGRADED,
            "outcome_metrics": outcome_metrics,
            "error_message": (
                f"{client_fail} client failure(s), {ps_failed} property snapshot failure(s)"
                + (f", {prop_enum_fail} enumeration issue(s)" if prop_enum_fail else "")
            ),
        }

    outcome_metrics["outcome_kind"] = "WORK_PERFORMED"
    outcome_metrics["queue_empty"] = False
    return {
        "message": (
            f"Compliance score snapshots: {client_ok}/{total} clients; "
            f"{ps_created} property daily row(s) written"
            + (
                f", {ps_skipped} propert{'y' if ps_skipped == 1 else 'ies'} skipped (no persisted score)"
                if ps_skipped
                else ""
            )
            + "."
        ),
        "count": client_ok,
        "errors": 0,
        "outcome_status": OUTCOME_SUCCESS,
        "outcome_metrics": outcome_metrics,
    }
