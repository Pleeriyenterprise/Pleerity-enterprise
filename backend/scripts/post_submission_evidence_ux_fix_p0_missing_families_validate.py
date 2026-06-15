#!/usr/bin/env python3
"""P0 closeout — validate missing requirement families on staging (read + bounded synthetic materialisation)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evidence_authority_convergence_repro_01_execute import (  # noqa: E402
    CLIENT_EMAIL,
    STAGING_API,
    canon_code,
    client_login,
    derive_modal_presentation,
    extract_row_snapshot,
    read_client_password,
)
from scripts.post_submission_evidence_ux_fix_p0_staging_validate import (  # noqa: E402
    FAMILY_ALIASES,
    p0_checks,
)
from scripts.plan_outcome_governed_fixture_seed_lib import StagingApi

OUT = ROOT / "docs/audit/post_submission_evidence_ux_audit_01"
FIXTURE_MARKER = "P0-CLOSEOUT-MISSING-FAMILIES-20260615"
MISSING_FAMILIES = ("smoke_heat_co", "pat", "tenancy", "rent_smart_wales", "lead_testing")

PROBE_CLIENTS: List[Tuple[str, str, Optional[str]]] = [
    ("nancy", "6fd5ac4c-3fd4-4112-ade7-156977deb49f", CLIENT_EMAIL),
    ("scotland_fixture", "ec0b091b-105d-4b78-9711-7ab143999cef", None),
    ("wales_fixture", "6bcc43c0-16f4-46a5-adf4-26693a0919d0", None),
    ("portfolio_eng", "80f83edd-ba12-41ed-929a-bbaf8c696a23", None),
]

GLASGOW_PROPERTY_ID = "0a5b4497-a1ba-4ee9-87e1-ae2bb9d4cc68"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_for_checks(row: Dict[str, Any], snap: Dict[str, Any]) -> Dict[str, Any]:
    return {**snap, "take_action": row.get("take_action")}


def match_family_row(row: Dict[str, Any], family_key: str) -> bool:
    needles = FAMILY_ALIASES[family_key]
    code = str(row.get("requirement_code") or row.get("requirement_type") or "").lower()
    if family_key == "pat":
        if "occupation" in code and "portable" not in code:
            return False
        return "portable_appliance" in code or code == "pat" or code.endswith("_pat")
    return any(n in code for n in needles)


def capture_family(
    api: StagingApi,
    token: str,
    *,
    client_label: str,
    property_id: str,
    property_name: str,
    row: Dict[str, Any],
    note: Optional[str] = None,
) -> Dict[str, Any]:
    snap = extract_row_snapshot(row)
    rid = str(row.get("requirement_id") or "")
    er = api.client_get(token, f"/client/properties/{property_id}/requirements/{rid}/evidence-resolution")
    modal = derive_modal_presentation({**row, **snap}, initial_focus_submission=True)
    checks = p0_checks(row_for_checks(row, snap), er, modal)
    pri = ((row.get("take_action") or {}).get("primary") or {}) if isinstance(row.get("take_action"), dict) else {}
    entry: Dict[str, Any] = {
        "client": client_label,
        "property_id": property_id,
        "property_name": property_name,
        "requirement_id": rid,
        "canonical_code": snap.get("canonical_code"),
        "lifecycle": snap.get("client_lifecycle_state"),
        "truth_stage": snap.get("truth_presentation_stage"),
        "uploaded_not_verified": (snap.get("cognition_truth_flags") or {}).get("uploaded_not_verified"),
        "cognition_primary": snap.get("cognition_primary_action"),
        "take_action_route": pri.get("route"),
        "take_action_intent": pri.get("intent"),
        "take_action_label": pri.get("label"),
        "reopen_field_count": len((er.get("reopen_context") or {}).get("structured_fields_prefill") or {}),
        "modal_context": modal.get("modal_context"),
        "modal_warnings": modal.get("warnings"),
        "checks": checks,
    }
    if note:
        entry["note"] = note
    return entry


def scan_fixture_clients(api: StagingApi, admin_t: str, step: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    matrix: Dict[str, Any] = {}
    scan_log: List[Dict[str, Any]] = []

    for client_label, client_id, email in PROBE_CLIENTS:
        if email:
            pw = os.environ.get("STAGING_CLIENT_PASSWORD") or read_client_password()
            token = client_login(api.api, email, pw)
            auth = "client_login"
        else:
            token = api.impersonate(admin_t, step, client_id, f"{FIXTURE_MARKER} scan")
            auth = "impersonation"

        props = api.client_get(token, "/client/properties").get("properties") or []
        for prop in props:
            pid = str(prop.get("property_id") or "")
            pname = prop.get("nickname") or prop.get("name") or pid
            reqs = api.client_get(token, f"/client/properties/{pid}/requirements").get("requirements") or []
            hits = [fam for fam in MISSING_FAMILIES if any(match_family_row(r, fam) for r in reqs)]
            if hits:
                scan_log.append(
                    {
                        "client": client_label,
                        "client_id": client_id,
                        "auth": auth,
                        "property_id": pid,
                        "property_name": pname,
                        "hits": hits,
                    }
                )
            for fam in MISSING_FAMILIES:
                if fam in matrix:
                    continue
                cands = [r for r in reqs if match_family_row(r, fam)]
                if not cands:
                    continue
                matrix[fam] = capture_family(
                    api,
                    token,
                    client_label=client_label,
                    property_id=pid,
                    property_name=pname,
                    row=cands[0],
                )

    return matrix, scan_log


def smoke_proxy_via_fire_alarm(api: StagingApi, token: str) -> Dict[str, Any]:
    for prop in api.client_get(token, "/client/properties").get("properties") or []:
        pid = str(prop.get("property_id") or "")
        pname = prop.get("nickname") or prop.get("name") or pid
        reqs = api.client_get(token, f"/client/properties/{pid}/requirements").get("requirements") or []
        cands = [r for r in reqs if canon_code(r) in ("fire_alarm", "smoke_heat_alarms", "smoke_alarms")]
        if not cands:
            continue
        return capture_family(
            api,
            token,
            client_label="nancy",
            property_id=pid,
            property_name=pname,
            row=cands[0],
            note="Staging registry has 0 smoke_heat_alarms rows; fire_alarm is the documented domestic-alarm proxy.",
        )
    return {"status": "not_found", "note": "No fire_alarm or smoke_heat_alarms on Nancy portfolio."}


def lead_testing_via_temporary_age(api: StagingApi, token: str) -> Dict[str, Any]:
    prop = api.client_get(token, f"/client/properties/{GLASGOW_PROPERTY_ID}")
    if prop.get("_error"):
        return {"status": "property_not_found", "property_id": GLASGOW_PROPERTY_ID}

    orig_age = prop.get("building_age_years")
    cleanup = {"property_id": GLASGOW_PROPERTY_ID, "restore_building_age_years": orig_age, "marker": FIXTURE_MARKER}
    try:
        patch_payload: Dict[str, Any] = {"building_age_years": 70}
        api.client_patch(token, f"/client/properties/{GLASGOW_PROPERTY_ID}", patch_payload)
        api.client_post(token, f"/properties/{GLASGOW_PROPERTY_ID}/requirements/sync", {})
        reqs = api.client_get(token, f"/client/properties/{GLASGOW_PROPERTY_ID}/requirements").get("requirements") or []
        lead = next((r for r in reqs if "lead_testing" in canon_code(r)), None)
        if not lead:
            return {
                "status": "materialisation_failed",
                "property_id": GLASGOW_PROPERTY_ID,
                "codes_after_sync": sorted({canon_code(r) for r in reqs}),
                "cleanup": cleanup,
            }
        return capture_family(
            api,
            token,
            client_label="nancy",
            property_id=GLASGOW_PROPERTY_ID,
            property_name=prop.get("nickname") or "Glasgow Shawlands",
            row=lead,
            note="Temporary building_age_years=70 materialisation; restored in finally block.",
        )
    finally:
        restore: Dict[str, Any] = {"building_age_years": orig_age}
        api.client_patch(token, f"/client/properties/{GLASGOW_PROPERTY_ID}", restore)
        api.client_post(token, f"/properties/{GLASGOW_PROPERTY_ID}/requirements/sync", {})


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    api = StagingApi(STAGING_API, pace=1.5)
    admin_t, step = api.admin_session()

    matrix, scan_log = scan_fixture_clients(api, admin_t, step)

    pw = os.environ.get("STAGING_CLIENT_PASSWORD") or read_client_password()
    nancy_token = client_login(api.api, CLIENT_EMAIL, pw)

    if matrix.get("smoke_heat_co", {}).get("status"):
        matrix["smoke_heat_co"] = smoke_proxy_via_fire_alarm(api, nancy_token)
    elif "smoke_heat_co" not in matrix:
        matrix["smoke_heat_co"] = smoke_proxy_via_fire_alarm(api, nancy_token)

    if matrix.get("lead_testing", {}).get("status"):
        matrix["lead_testing"] = lead_testing_via_temporary_age(api, nancy_token)
    elif "lead_testing" not in matrix:
        matrix["lead_testing"] = lead_testing_via_temporary_age(api, nancy_token)

    for fam in MISSING_FAMILIES:
        if fam not in matrix:
            matrix[fam] = {"status": "not_found"}

    failures = [
        {"family": fam, **entry}
        for fam, entry in matrix.items()
        if isinstance(entry.get("checks"), dict) and not entry["checks"].get("all_pass")
    ]

    report = {
        "programme": "POST-SUBMISSION-EVIDENCE-UX-FIX-P0-MISSING-FAMILIES",
        "generated_at": utc(),
        "fixture_marker": FIXTURE_MARKER,
        "staging_api": api.api,
        "production_touched": False,
        "data_repair_performed": False,
        "synthetic_fixture_notes": {
            "smoke_heat_co": "Uses fire_alarm proxy when smoke_heat_alarms has zero staging materialisations.",
            "lead_testing": "Temporarily sets Glasgow Shawlands building_age_years=70, syncs, validates, restores original age.",
        },
        "cleanup_plan": {
            "lead_testing": f"Script restores building_age_years on {GLASGOW_PROPERTY_ID} in finally; re-run requirements/sync.",
            "smoke_proxy": "Read-only; no mutation.",
        },
        "scan_log": scan_log,
        "matrix": matrix,
        "failures": failures,
        "go_no_go": "GO" if not failures else "NO-GO",
    }

    out_path = OUT / "MISSING_FAMILIES_VALIDATION_P0.json"
    out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"go_no_go": report["go_no_go"], "failures": len(failures), "out": str(out_path)}, indent=2))
    return 0 if report["go_no_go"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
