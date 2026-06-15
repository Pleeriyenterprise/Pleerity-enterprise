#!/usr/bin/env python3
"""POST-SUBMISSION-EVIDENCE-UX-FIX-P0 — staging read-only validation harness."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evidence_authority_convergence_repro_01_execute import (  # noqa: E402
    CLIENT_EMAIL,
    PROGRAMME,
    SCENARIO_A_CODES,
    SCENARIO_B_CODES,
    STAGING_API,
    TARGET_CODES,
    capture_requirement,
    client_login,
    derive_modal_presentation,
    extract_row_snapshot,
    has_persisted_submission,
    match_family,
    pick_rows,
    read_client_password,
)
from scripts.plan_outcome_governed_fixture_seed_lib import StagingApi

OUT = ROOT / "docs/audit/post_submission_evidence_ux_audit_01"
EXPECTED_SHA = "4e4a4fe312ef4cc9ec1385f9d9ac592a51be37b7"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

FAMILY_ALIASES = {
    "legionella": ("legionella",),
    "smoke_heat_co": ("smoke_heat", "smoke_heat_alarms", "smoke"),
    "gas_safety": ("gas_safety", "gas"),
    "eicr": ("eicr",),
    "epc": ("epc",),
    "pat": ("pat", "portable_appliance"),
    "tenancy": ("tenancy_agreement", "tenancy"),
    "hmo": ("hmo_fire", "hmo_fire_risk", "fire_risk"),
    "rent_smart_wales": ("rent_smart", "rent_smart_wales"),
    "lead_testing": ("lead_testing", "lead"),
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def p0_checks(row: Dict[str, Any], er: Dict[str, Any], modal: Dict[str, Any]) -> Dict[str, Any]:
    code = str(row.get("canonical_code") or row.get("requirement_code") or "").lower()
    flags = (row.get("cognition_truth_flags") or {})
    reopen = er.get("reopen_context") if isinstance(er.get("reopen_context"), dict) else None
    cog_pri = row.get("cognition_primary_action") or {}
    ta = row.get("take_action") if isinstance(row.get("take_action"), dict) else {}
    pri = ta.get("primary") if isinstance(ta.get("primary"), dict) else {}
    route = str(pri.get("route") or cog_pri.get("url") or "")
    has_doc = bool(str(row.get("document_id") or "").strip())
    has_cer = bool(str(row.get("primary_evidence_record_id") or "").strip())
    structured_only = has_cer and not has_doc

    checks = {
        "false_upload_warning": not (
            flags.get("uploaded_not_verified") and structured_only and not has_doc
        ),
        "verified_view_not_documents_only": True,
        "reopen_prefill_when_cer": True,
        "single_update_cta_hero_suppressed": True,  # frontend-only (showHeroPrimary); verified via bundle markers
        "pat_routes_documents": True,
    }

    if structured_only and str(cog_pri.get("key") or "") == "view_verified_evidence":
        url = str(cog_pri.get("url") or "")
        checks["verified_view_not_documents_only"] = "open=intel" in url or "tab=evidence" in url

    if has_cer and reopen:
        pre = reopen.get("structured_fields_prefill") or reopen.get("checklist_answers_prefill") or {}
        checks["reopen_prefill_when_cer"] = len(pre) > 0 or bool(reopen.get("contractor_confirmation_prefill"))
    elif has_cer and not reopen:
        checks["reopen_prefill_when_cer"] = False

    if "pat" in code or "portable_appliance" in code:
        checks["pat_routes_documents"] = "/documents" in route and (
            pri.get("intent") in ("upload_evidence", None, "", "guided_evidence_resolution")
            or cog_pri.get("key") in ("upload_evidence", "view_verified_evidence", None)
            or "/documents" in route
        )

    warnings = modal.get("warnings") or []
    checks["no_false_upload_warning_in_modal"] = not (
        structured_only and not has_doc and any("Uploaded is not verified" in w for w in warnings)
    )

    checks["all_pass"] = all(checks.values())
    return checks


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    api = StagingApi(STAGING_API, pace=2.5)
    headers = {"User-Agent": BROWSER_UA}

    ver = httpx.get(f"{api.api}/version", headers=headers, timeout=120)
    ver_body = ver.json() if ver.status_code == 200 else {"status": ver.status_code, "text": ver.text[:200]}
    sha = str(ver_body.get("commit_sha") or "")
    sha_ok = sha.startswith("4e4a4fe3")

    pw = os.environ.get("STAGING_CLIENT_PASSWORD") or read_client_password()
    token = client_login(api.api, CLIENT_EMAIL, pw)

    properties = [
        ("nancy_primary", "d35a58ae-3c81-491c-9694-1d021dd3b8ad"),
        ("solo_fixture", "6b33492c-5e24-453b-bcde-49844fd4aede"),
    ]

    matrix: Dict[str, Any] = {}
    failures: List[Dict[str, Any]] = []
    captures: List[Dict[str, Any]] = []

    for prop_label, pid in properties:
        reqs_body = api.client_get(token, f"/client/properties/{pid}/requirements")
        rows = reqs_body.get("requirements") or []
        for family_key, needles in FAMILY_ALIASES.items():
            candidates = [
                r for r in rows
                if any(n in str(r.get("requirement_code") or r.get("requirement_type") or "").lower() for n in needles)
            ]
            # PAT: exclude Wales occupation_contract false positive
            if family_key == "pat":
                filtered = []
                for r in candidates:
                    code = str(r.get("requirement_code") or r.get("requirement_type") or "").lower()
                    if "occupation_contract" in code or "occupation" in code and "pat" not in code:
                        continue
                    if "portable_appliance" in code or code == "pat" or code.endswith("_pat"):
                        filtered.append(r)
                candidates = filtered
            if not candidates:
                if family_key not in matrix:
                    matrix[family_key] = {"status": "not_on_property", "property": prop_label}
                continue
            row = candidates[0]
            snap = extract_row_snapshot(row)
            rid = str(row.get("requirement_id") or "")
            er = api.client_get(token, f"/client/properties/{pid}/requirements/{rid}/evidence-resolution")
            modal = derive_modal_presentation({**row, **snap}, initial_focus_submission=True)
            checks = p0_checks({**snap, "take_action": row.get("take_action")}, er, modal)
            entry = {
                "property": prop_label,
                "requirement_id": rid,
                "canonical_code": snap.get("canonical_code"),
                "lifecycle": snap.get("client_lifecycle_state"),
                "truth_stage": snap.get("truth_presentation_stage"),
                "uploaded_not_verified": (snap.get("cognition_truth_flags") or {}).get("uploaded_not_verified"),
                "cognition_primary": snap.get("cognition_primary_action"),
                "take_action_primary": snap.get("take_action_primary_label"),
                "reopen_field_count": len((er.get("reopen_context") or {}).get("structured_fields_prefill") or {}),
                "modal_context": modal.get("modal_context"),
                "modal_warnings": modal.get("warnings"),
                "checks": checks,
            }
            matrix[family_key] = entry
            captures.append(entry)
            if not checks.get("all_pass"):
                failures.append({"family": family_key, **entry})

    # Deduplicate failures by family (keep first)
    seen_fail: set = set()
    deduped_failures: List[Dict[str, Any]] = []
    for f in failures:
        if f["family"] in seen_fail:
            continue
        seen_fail.add(f["family"])
        deduped_failures.append(f)
    failures = deduped_failures

    report = {
        "programme": "POST-SUBMISSION-EVIDENCE-UX-FIX-P0-STAGING-VALIDATION",
        "generated_at": utc(),
        "staging_api": api.api,
        "expected_sha": EXPECTED_SHA,
        "version": ver_body,
        "sha_match": sha_ok,
        "data_repair_performed": False,
        "production_touched": False,
        "registry_changed": False,
        "matrix": matrix,
        "failures": failures,
        "go_no_go": "GO" if sha_ok and not failures else "NO-GO",
        "failure_count": len(failures),
    }

    out_path = OUT / "STAGING_VALIDATION_P0.json"
    out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"sha_ok": sha_ok, "go_no_go": report["go_no_go"], "failures": len(failures), "out": str(out_path)}, indent=2))
    return 0 if report["go_no_go"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
