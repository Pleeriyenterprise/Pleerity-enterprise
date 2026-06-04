#!/usr/bin/env python3
"""Post-run reconcile for OPERATIONS-FAMILY-END-TO-END-RUNTIME-AUDIT-01 harness field fixes."""
from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/operations_family_end_to_end_runtime_audit_01"
API = "https://pleerity-enterprise.onrender.com/api"
SLUG = "6fd5ac4c_d35a58ae"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def load(name: str) -> dict:
    return json.loads((BUNDLE / name).read_text(encoding="utf-8"))


def save(name: str, data: dict) -> None:
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> None:
    pw = (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text(encoding="utf-8").strip()
    tok = httpx.post(f"{API}/auth/login", json={"email": "nancy@yopmail.com", "password": pw}, timeout=120).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    ij = load("issue_job_runtime.json")
    iid = ij.get("issue_id")
    if iid:
        tl = httpx.get(f"{API}/client/maintenance/issues/{iid}/timeline", headers=h, timeout=90)
        items = (tl.json().get("items") or []) if tl.status_code == 200 else []
        for s in ij.get("steps", []):
            if s.get("step") == "timeline_updated":
                s["ok"] = len(items) >= 1
                s["detail"] = f"items={len(items)}"
        ij["pass"] = bool(iid and ij.get("work_order_id")) and all(s["ok"] for s in ij.get("steps", []))
        save("issue_job_runtime.json", ij)

        audit = {
            "issue_id": iid,
            "timeline_status": tl.status_code,
            "event_count": len(items),
            "event_type_sample": sorted({i.get("event_type") for i in items if i.get("event_type")})[:20],
            "events_sample": items[:6],
            "expected_actions": [
                {"keyword": k, "present": k in json.dumps(items, default=str).lower()}
                for k in ("issue", "work_order", "contractor", "quote", "complete", "invoice", "audit")
            ],
            "pass": tl.status_code == 200 and len(items) >= 2,
            "reconciled": True,
        }
        save("operations_audit_trail_runtime.json", audit)

    rs = httpx.get(f"{API}/client/maintenance/properties/{PID}/risk-signals", headers=h, timeout=90)
    signals = rs.json().get("signals") or []
    risk = {
        "property_api_status": rs.status_code,
        "signals": [
            {
                "signal_id": s.get("signal_id"),
                "risk_type": s.get("risk_type"),
                "risk_level": s.get("risk_level"),
                "status": s.get("status"),
                "reasons_sample": (s.get("reasons") or [])[:2],
            }
            for s in signals[:8]
        ],
        "validations": [
            {
                "signal_id": s.get("signal_id"),
                "pass": bool(s.get("signal_id")) and bool(s.get("risk_type")),
            }
            for s in signals[:5]
        ],
        "pass": rs.status_code == 200,
        "reconciled": True,
    }
    if signals:
        risk["pass"] = rs.status_code == 200 and all(
            bool(s.get("signal_id")) and bool(s.get("risk_type")) for s in signals[:3]
        )
    save("risk_signal_runtime.json", risk)

    setup = load("operations_runtime_setup.json")
    inv = load("contractor_invoice_runtime.json")
    clf = load("classifications.json")
    checklist = clf.get("checklist", {})
    checklist["issue_job"] = load("issue_job_runtime.json").get("pass")
    checklist["audit_trail"] = load("operations_audit_trail_runtime.json").get("pass")
    checklist["risk"] = load("risk_signal_runtime.json").get("pass")

    blockers = [k for k, v in checklist.items() if v is False]
    flags = []
    if not setup.get("invoicing"):
        flags.append("INVOICING_ENTITLEMENT_DISABLED")
        blockers = [b for b in blockers if b != "invoice"] + ["invoice_entitlement"]
    classification = "VERIFIED_OPERATIONALLY"
    if blockers:
        classification = "PARTIAL" if len(blockers) <= 2 and checklist.get("contractor_assignment") else "FAIL_OPERATIONAL"
    if "invoice_entitlement" in blockers or not inv.get("pass"):
        classification = "OPERATIONS_FLOW_DRIFT" if classification == "PARTIAL" else classification
        flags.append("RENT_OPERATIONS_DRIFT" if not checklist.get("rent") else "")
    flags = [f for f in flags if f]

    clf.update(
        {
            "classification": classification,
            "blockers": blockers,
            "secondary_flags": sorted(set(flags + clf.get("secondary_flags", []))),
            "checklist": checklist,
            "reconciled_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "notes": [
                "Timeline harness used items[] not events[] — reconciled.",
                "Risk signals use signal_id/risk_type — reconciled.",
                "Landlord INVOICING entitlement false on pilot; contractor invoice submit succeeded but approvals API 403.",
            ],
        }
    )
    save("classifications.json", clf)
    print("reconciled", classification, blockers)


if __name__ == "__main__":
    main()
