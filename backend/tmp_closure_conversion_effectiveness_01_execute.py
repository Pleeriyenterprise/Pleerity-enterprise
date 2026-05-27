#!/usr/bin/env python3
"""
CLOSURE-CONVERSION-EFFECTIVENESS-01

Validates OPERATIONAL-CLOSURE-CONVERSION-01 runtime surfaces on staging:
closure scoring, deadlock reduction, momentum prioritisation, verification throughput.
Read-only.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
PROGRAMME = "CLOSURE-CONVERSION-EFFECTIVENESS-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

DEFAULT_CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
CLIENT_EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
PW_PATH = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_temp_pw.txt"
CLIENT_PW = os.environ.get("OPS_VERIFY_PASSWORD") or (
    PW_PATH.read_text(encoding="utf-8").strip() if PW_PATH.is_file() else "OpsVerify01!StagingWalk"
)

OUT = ROOT / "docs" / "audit" / "closure_conversion_effectiveness_01"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def login_client() -> str:
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PW}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def get_json(url: str, token: str, *, params: Optional[dict] = None) -> Tuple[int, Any]:
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=120)
    if "application/json" in (r.headers.get("content-type") or "").lower():
        return r.status_code, r.json()
    return r.status_code, r.text


def classify_closure(
    closure: Dict[str, Any],
    snap: Dict[str, Any],
    urgent_has_momentum: bool,
) -> Tuple[str, Dict[str, Any]]:
    if not closure.get("available", True) and closure.get("error"):
        return "STALLED_OPERATIONAL_SYSTEM", {"reason": "closure_bundle_unavailable", "error": closure.get("error")}

    deadlock = closure.get("deadlock_reduction_v1") or {}
    verification = closure.get("verification_throughput_v1") or {}
    scores = closure.get("closure_conversion_scores_v1") or {}
    kpis = closure.get("closure_momentum_kpis_v1") or {}
    confidence = closure.get("landlord_decision_confidence_v1") or {}

    groups = deadlock.get("groups") or []
    has_deadlock = len(groups) >= 1
    has_scores = (scores.get("likely_to_stall_count") or 0) >= 0
    has_verification = verification.get("verification_queue_count") is not None
    has_kpis = bool(kpis.get("closure_conversion_rate") is not None or kpis.get("operational_momentum_trend"))
    momentum_actions = closure.get("momentum_priority_actions") or []

    fleet_deadlock = (snap.get("jobs_no_contractor") or 0) + (snap.get("jobs_completed_unverified") or 0)
    conf_score = confidence.get("decision_confidence_score") or 0

    signals_ok = has_deadlock and has_scores and has_verification and has_kpis
    surfaces_momentum = urgent_has_momentum or len(momentum_actions) > 0

    fake_chains = scores.get("fake_progress_chain_count") or 0
    if signals_ok and surfaces_momentum and conf_score >= 0.5 and fleet_deadlock < 15 and fake_chains < 5:
        return "VERIFIED_CLOSURE_CONVERSION", {
            "deadlock_groups": len(groups),
            "momentum_actions": len(momentum_actions),
            "confidence": conf_score,
        }
    if signals_ok and (surfaces_momentum or len(groups) >= 2) and fake_chains <= 15:
        return "PARTIAL_CLOSURE_CONVERSION", {
            "deadlock_groups": len(groups),
            "fleet_deadlock_units": fleet_deadlock,
            "verification_queue": verification.get("verification_queue_count"),
            "fake_progress_chains": scores.get("fake_progress_chain_count"),
            "confidence": conf_score,
        }
    if signals_ok:
        return "WORKFLOW_WITHOUT_CLOSURE_RISK", {
            "note": "Closure data present but momentum/urgent merge weak or fleet still blocked",
            "fleet_deadlock_units": fleet_deadlock,
        }
    return "STALLED_OPERATIONAL_SYSTEM", {"reason": "missing_closure_signals"}


def closure_snapshot(token: str) -> Dict[str, Any]:
    st, cc = get_json(f"{API}/client/command-center", token, params={"projection": "primary"})
    snap: Dict[str, Any] = {"command_center_status": st, "captured_at": utc()}
    if st != 200 or not isinstance(cc, dict):
        return snap

    ov = cc.get("operational_value_v1") or {}
    closure = ov.get("closure_conversion_v1") or {}
    snap["closure_available"] = closure.get("available", True) and not closure.get("error")
    snap["deadlock_groups"] = len((closure.get("deadlock_reduction_v1") or {}).get("groups") or [])
    snap["verification_queue"] = (closure.get("verification_throughput_v1") or {}).get("verification_queue_count")
    snap["likely_to_stall"] = (closure.get("closure_conversion_scores_v1") or {}).get("likely_to_stall_count")
    snap["fake_progress_chains"] = (closure.get("closure_conversion_scores_v1") or {}).get("fake_progress_chain_count")
    snap["what_clears_most_pressure"] = closure.get("what_clears_most_pressure")
    snap["decision_confidence"] = (closure.get("landlord_decision_confidence_v1") or {}).get("decision_confidence_score")

    urgent = cc.get("urgent_actions") or []
    snap["urgent_rows"] = len(urgent)
    snap["urgent_closure_momentum"] = sum(
        1
        for u in urgent
        if ((u.get("metadata") or {}).get("closure_momentum_action"))
        or str((u.get("metadata") or {}).get("action_type") or "").startswith("closure_")
    )

    st2, wos_body = get_json(f"{API}/client/maintenance/work-orders", token, params={"limit": 200})
    wos = (wos_body or {}).get("work_orders") or [] if st2 == 200 else []
    snap["jobs_no_contractor"] = sum(
        1
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id")
    )
    snap["jobs_completed_unverified"] = sum(
        1 for w in wos if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
    )

    snap["_closure_bundle"] = closure
    snap["_urgent_has_momentum"] = snap["urgent_closure_momentum"] > 0
    return snap


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    write("programme.json", {"programme": PROGRAMME, "run_tag": RUN_TAG, "api": API, "client_id": DEFAULT_CID})

    token = login_client()
    snap = closure_snapshot(token)
    closure = snap.pop("_closure_bundle", {})
    urgent_has_momentum = snap.pop("_urgent_has_momentum", False)
    write("closure_snapshot.json", snap)

    classification, detail = classify_closure(closure, snap, urgent_has_momentum)
    write("07_classification.json", {
        "programme": PROGRAMME,
        "classification": classification,
        "detail": detail,
        "verified_at_utc": utc(),
    })

    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{classification}`",
        f"**Verified at:** {utc()}",
        "",
        "## Snapshot",
        "",
        json.dumps(snap, indent=2),
        "",
        "## Detail",
        "",
        json.dumps(detail, indent=2),
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"programme": PROGRAMME, "classification": classification, "detail": detail}, indent=2))
    return 0 if classification in ("VERIFIED_CLOSURE_CONVERSION", "PARTIAL_CLOSURE_CONVERSION") else 1


if __name__ == "__main__":
    raise SystemExit(main())
