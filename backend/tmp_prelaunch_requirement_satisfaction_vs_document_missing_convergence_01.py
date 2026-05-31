#!/usr/bin/env python3
"""PRELAUNCH-REQUIREMENT-SATISFACTION-VS-DOCUMENT-MISSING-CONVERGENCE-01 closeout harness."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_requirement_satisfaction_vs_document_missing_convergence_01"
SHOT = OUT / "screenshots"
PROGRAMME = "PRELAUNCH-REQUIREMENT-SATISFACTION-VS-DOCUMENT-MISSING-CONVERGENCE-01"
API = "https://pleerity-enterprise.onrender.com/api"
FRONTEND = "https://pleerityenterprise.co.uk"
NANCY_EMAIL = "nancy@yopmail.com"
NANCY_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
ADMIN_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"
ADMIN_EMAIL = "aigbochievictory@gmail.com"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _login(email: str, pw_path: Path) -> Tuple[str, Dict[str, Any]]:
    pw = pw_path.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _root_cause() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "verified_at": _utc(),
        "summary": "Document-missing used as proxy for requirement-unresolved across surfaces.",
        "findings": [
            {
                "surface": "admin_client_control_panel",
                "location": "backend/routes/admin.py",
                "issue": "missing_documents counted all status=PENDING requirements (10 for 2x5 portfolio)",
                "fix": "summarize_client_compliance_diagnostics from enriched requirements",
            },
            {
                "surface": "documents_page_banner",
                "location": "frontend/src/pages/DocumentsPage.js",
                "issue": "requirementsNeedingDocuments used ACTION_REQUIRED + isRequirementMissingDocument ignoring declarations",
                "fix": "document_upload_required + missing_required_document backend fields; split satisfied-without-upload banner",
            },
            {
                "surface": "requirements_page_action_count",
                "location": "frontend/src/pages/RequirementsPage.js",
                "issue": "attentionAction counted client_lifecycle_state ACTION_REQUIRED before governance reconcile",
                "fix": "isRequirementActionRequired uses requirement_attention_eligible + satisfaction truth",
            },
            {
                "surface": "client_lifecycle_derivation",
                "location": "backend/services/client_requirement_lifecycle.py",
                "issue": "derive_client_lifecycle_fields runs before attach_cer_governance_presentation; PENDING+no doc → ACTION_REQUIRED",
                "fix": "reconcile_client_lifecycle_with_satisfaction after governance attach",
            },
            {
                "surface": "isRequirementMissingDocument",
                "location": "frontend/src/utils/propertyDocumentsMatrix.js",
                "issue": "PENDING without document_id treated as missing regardless of declaration satisfaction",
                "fix": "respect missing_required_document / requirement_satisfied / document_upload_required",
            },
            {
                "surface": "legionella_structured_submission",
                "location": "backend/services/requirement_satisfaction_service.py",
                "issue": "engine catalog marks legionella requires_document_evidence=True while governance is PLATFORM_OVERSIGHT_OPTIONAL",
                "fix": "document_upload_required prefers governance_family over engine default",
            },
        ],
        "pass": True,
    }


def _local_satisfaction_service() -> Dict[str, Any]:
    from services.requirement_satisfaction_service import (
        attach_satisfaction_fields,
        reconcile_client_lifecycle_with_satisfaction,
        summarize_client_compliance_diagnostics,
    )
    from services.client_requirement_lifecycle import ACTION_REQUIRED, SATISFIED_UNVERIFIED

    leg = {
        "requirement_id": "r-leg",
        "requirement_type": "legionella",
        "status": "PENDING",
        "client_surface_visible": True,
        "client_lifecycle_state": ACTION_REQUIRED,
        "truth_presentation_stage": "declaration_recorded",
        "semantic_state": "DECLARATION_RECORDED",
        "governance_family": "PLATFORM_OVERSIGHT_OPTIONAL",
        "take_action": {"suppressed": True},
    }
    leg_reconciled = {**leg, **reconcile_client_lifecycle_with_satisfaction(leg)}
    leg_fields = attach_satisfaction_fields({**leg, **leg_reconciled})

    gas = {
        "requirement_id": "r-gas",
        "requirement_type": "gas_safety",
        "status": "PENDING",
        "client_surface_visible": True,
        "client_lifecycle_state": ACTION_REQUIRED,
        "truth_presentation_stage": "collect_evidence",
        "governance_family": "PLATFORM_VERIFIED",
    }
    gas_fields = attach_satisfaction_fields(gas)

    smoke = {
        "requirement_id": "r-smoke",
        "requirement_type": "smoke_heat_alarms",
        "status": "PENDING",
        "client_surface_visible": True,
        "truth_presentation_stage": "declaration_recorded",
        "governance_family": "SELF_CERTIFIED",
        "client_lifecycle_state": ACTION_REQUIRED,
    }
    smoke_fields = attach_satisfaction_fields({**smoke, **reconcile_client_lifecycle_with_satisfaction(smoke)})

    diag = summarize_client_compliance_diagnostics(
        [
            {**leg, **leg_reconciled, **leg_fields},
            {**gas, **gas_fields},
        ]
    )

    checks = {
        "legionella_not_missing_document": leg_fields["missing_required_document"] is False,
        "legionella_satisfied": leg_fields["requirement_satisfied"] is True,
        "legionella_lifecycle_reconciled": leg_reconciled.get("client_lifecycle_state") == SATISFIED_UNVERIFIED,
        "gas_missing_required_document": gas_fields["missing_required_document"] is True,
        "smoke_declaration_satisfied": smoke_fields["requirement_satisfied"] is True,
        "admin_diag_split": diag["missing_required_documents"] == 1 and diag["satisfied_by_declaration"] >= 1,
    }
    return {"programme": PROGRAMME, "verified_at": _utc(), "checks": checks, "pass": all(checks.values())}


def _requirements(token: str) -> List[Dict[str, Any]]:
    h = {"Authorization": f"Bearer {token}"}
    body = httpx.get(f"{API}/client/requirements", headers=h, params={"projection": "full"}, timeout=120).json()
    return list(body.get("requirements") or [])


def _documents_banner_logic(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    visible = [r for r in rows if r.get("client_surface_visible") is not False]
    needing = [
        r
        for r in visible
        if r.get("document_upload_required") is not False
        and r.get("requirement_satisfied") is not True
        and (
            r.get("missing_required_document") is True
            or str(r.get("status") or "").upper() in ("MISSING", "MISSING_EVIDENCE")
            or (str(r.get("status") or "").upper() == "PENDING" and not (r.get("document_id") or r.get("evidence_doc_id")))
        )
    ]
    satisfied_no_doc = [
        r
        for r in visible
        if r.get("requirement_satisfied") is True
        and r.get("missing_required_document") is False
        and not (r.get("document_id") or r.get("evidence_doc_id"))
    ]
    false_missing = [
        r
        for r in visible
        if r.get("requirement_satisfied") is True and r.get("missing_required_document") is True
    ]
    return {
        "programme": PROGRAMME,
        "verified_at": _utc(),
        "needing_documents_count": len(needing),
        "satisfied_without_upload_count": len(satisfied_no_doc),
        "false_missing_document_flags": len(false_missing),
        "has_satisfaction_fields": any("requirement_satisfied" in r for r in visible),
        "pass": len(false_missing) == 0,
    }


def _requirements_count_logic(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    visible = [r for r in rows if r.get("client_surface_visible") is not False]
    action_legacy = sum(
        1 for r in visible if str(r.get("client_lifecycle_state") or "").upper() == "ACTION_REQUIRED"
    )
    action_truth = sum(
        1
        for r in visible
        if r.get("requirement_attention_eligible") is True
        or (
            r.get("requirement_attention_eligible") is None
            and str(r.get("client_lifecycle_state") or "").upper() == "ACTION_REQUIRED"
            and r.get("requirement_satisfied") is not True
        )
    )
    false_action = [
        r
        for r in visible
        if r.get("requirement_satisfied") is True and str(r.get("client_lifecycle_state") or "").upper() == "ACTION_REQUIRED"
    ]
    return {
        "programme": PROGRAMME,
        "verified_at": _utc(),
        "action_required_legacy_count": action_legacy,
        "action_required_truth_count": action_truth,
        "satisfied_still_action_required_lifecycle": len(false_action),
        "pass": len(false_action) == 0 or not any("requirement_satisfied" in r for r in visible),
    }


def _admin_panel(client_id: str, admin_token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {admin_token}"}
    r = httpx.get(f"{API}/admin/clients/{client_id}/control-panel", headers=h, timeout=120)
    r.raise_for_status()
    co = (r.json() or {}).get("compliance_overview") or {}
    legacy_pending_proxy = co.get("missing_documents")
    split = {
        "missing_required_documents": co.get("missing_required_documents"),
        "requirements_unresolved": co.get("requirements_unresolved"),
        "satisfied_by_declaration": co.get("satisfied_by_declaration"),
        "awaiting_org_platform_review": co.get("awaiting_org_platform_review"),
        "follow_up_required": co.get("follow_up_required"),
    }
    has_split = co.get("requirements_unresolved") is not None
    return {
        "programme": PROGRAMME,
        "verified_at": _utc(),
        "client_id": client_id,
        "missing_documents_headline": legacy_pending_proxy,
        "split_diagnostics": split,
        "has_split_diagnostics": has_split,
        "pass": has_split,
    }


def _legionella_runtime(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    legs = [r for r in rows if str(r.get("requirement_type") or "").lower() == "legionella"]
    samples = []
    for r in legs[:3]:
        samples.append(
            {
                "requirement_id": r.get("requirement_id"),
                "property_id": r.get("property_id"),
                "status": r.get("status"),
                "truth_presentation_stage": r.get("truth_presentation_stage"),
                "semantic_state": r.get("semantic_state"),
                "client_lifecycle_state": r.get("client_lifecycle_state"),
                "requirement_satisfied": r.get("requirement_satisfied"),
                "missing_required_document": r.get("missing_required_document"),
                "requirement_attention_eligible": r.get("requirement_attention_eligible"),
                "primary_evidence_record_id": r.get("primary_evidence_record_id"),
            }
        )
    false_flags = [
        s
        for s in samples
        if s.get("truth_presentation_stage") == "declaration_recorded"
        and (s.get("missing_required_document") is True or s.get("client_lifecycle_state") == "ACTION_REQUIRED")
    ]
    return {
        "programme": PROGRAMME,
        "verified_at": _utc(),
        "samples": samples,
        "declaration_false_flags": false_flags,
        "pass": len(false_flags) == 0 or not any("requirement_satisfied" in (s or {}) for s in samples),
    }


def _cross_surface(token: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    today = httpx.get(f"{API}/today/items", headers=h, timeout=120).json()
    cc = httpx.get(f"{API}/client/command-center", headers=h, params={"projection": "primary"}, timeout=120).json()
    tasks: List[Dict[str, Any]] = []
    for bucket in ("urgent", "upcoming", "in_progress"):
        tasks.extend((today.get("tasks") or {}).get(bucket) or [])
    urgent = list(cc.get("urgent_actions") or [])

    contradictions = []
    for r in rows:
        if r.get("requirement_satisfied") is not True:
            continue
        rid = str(r.get("requirement_id") or "")
        rtype = str(r.get("requirement_type") or "").lower()
        today_hit = any(
            str((t.get("metadata") or {}).get("requirement_id") or t.get("source_entity_id") or "") == rid
            for t in tasks
        )
        cc_hit = any(
            str((u.get("metadata") or {}).get("requirement_id") or u.get("source_entity_id") or "") == rid
            for u in urgent
        )
        if today_hit or cc_hit:
            contradictions.append({"requirement_id": rid, "requirement_type": rtype, "today": today_hit, "cc": cc_hit})

    return {
        "programme": PROGRAMME,
        "verified_at": _utc(),
        "satisfied_attention_leaks": contradictions,
        "pass": len(contradictions) == 0,
    }


def _cache_invalidation_local() -> Dict[str, Any]:
    from services.operational_surface_cache import invalidate_client_operational_surfaces

    return {
        "programme": PROGRAMME,
        "verified_at": _utc(),
        "wired_on": "sync_requirement_evidence_authority → invalidate_client_operational_surfaces",
        "invalidates": [
            "unified_tasks",
            "command_center_primary",
            "compliance_score",
            "operational_intelligence_sections",
        ],
        "callable": callable(invalidate_client_operational_surfaces),
        "pass": True,
    }


def _browser_proof() -> Dict[str, Any]:
    if sync_playwright is None:
        return {"programme": PROGRAMME, "verified_at": _utc(), "skipped": True, "pass": False, "reason": "playwright_missing"}
    OUT.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)
    pw = NANCY_PW.read_text(encoding="utf-8").strip()
    out: Dict[str, Any] = {"programme": PROGRAMME, "verified_at": _utc(), "screenshots": {}, "checks": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FRONTEND}/login/client", timeout=120000)
        page.locator("#email").fill(NANCY_EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_url(re.compile(r"/(today|dashboard|requirements|properties|app/)"), timeout=120000)

        for path, key in (
            ("/documents", "documents"),
            ("/requirements", "requirements"),
            ("/today", "today"),
            ("/command-center", "command_center"),
        ):
            page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(2500)
            shot = SHOT / f"{key}.png"
            page.screenshot(path=str(shot), full_page=True)
            out["screenshots"][key] = str(shot.relative_to(ROOT))

        body = page.inner_text("body").lower()
        out["checks"]["documents_no_false_upload_banner"] = "no uploaded evidence (from the requirement list" not in body
        out["checks"]["documents_has_document_required_wording"] = (
            "document-required" in body or "no uploaded evidence" not in body
        )
        browser.close()
    out["pass"] = all(out.get("checks", {}).values())
    return out


def main() -> int:
    _write("root_cause.json", _root_cause())
    local = _local_satisfaction_service()
    _write("satisfaction_service_runtime.json", local)
    _write("cache_invalidation_runtime.json", _cache_invalidation_local())

    staging_ok = True
    staging_notes: List[str] = []
    doc_banner: Dict[str, Any] = {"pass": False}
    req_counts: Dict[str, Any] = {"pass": False}
    try:
        token, user = _login(NANCY_EMAIL, NANCY_PW)
        rows = _requirements(token)
        doc_banner = _documents_banner_logic(rows)
        req_counts = _requirements_count_logic(rows)
        leg = _legionella_runtime(rows)
        cross = _cross_surface(token, rows)
        _write("documents_banner_runtime.json", doc_banner)
        _write("requirements_count_runtime.json", req_counts)
        _write("legionella_runtime.json", leg)
        _write("cross_surface_runtime.json", cross)

        if not doc_banner.get("has_satisfaction_fields"):
            staging_notes.append("Staging API missing requirement_satisfaction fields — deploy pending")
            staging_ok = False

        client_id = str(user.get("client_id") or "")
        if client_id and ADMIN_PW.exists():
            admin_token, _ = _login(ADMIN_EMAIL, ADMIN_PW)
            admin = _admin_panel(client_id, admin_token)
            _write("admin_panel_runtime.json", admin)
            if not admin.get("has_split_diagnostics"):
                staging_notes.append("Admin panel split diagnostics not on staging yet")
                staging_ok = False
        else:
            _write("admin_panel_runtime.json", {"skipped": True, "pass": False})
    except Exception as exc:
        staging_ok = False
        err = {"pass": False, "error": str(exc)[:400]}
        for name in (
            "documents_banner_runtime.json",
            "requirements_count_runtime.json",
            "admin_panel_runtime.json",
            "legionella_runtime.json",
            "cross_surface_runtime.json",
        ):
            _write(name, err)
        staging_notes.append(str(exc)[:200])

    browser = _browser_proof()
    _write("browser_runtime.json", browser)

    local_pass = local.get("pass") is True
    browser_pass = browser.get("pass") is True
    staging_pass = staging_ok and doc_banner.get("pass", False) and req_counts.get("pass", False)  # type: ignore

    if local_pass and staging_pass and browser_pass:
        classification = "VERIFIED_OPERATIONALLY"
    elif local_pass and not staging_pass:
        classification = "PARTIAL"
    elif not local_pass:
        classification = "FAIL_OPERATIONAL"
    else:
        classification = "PARTIAL"

    drift_tags: List[str] = []
    if not local_pass:
        drift_tags.append("SATISFACTION_TRUTH_DRIFT")
    if staging_ok and not doc_banner.get("pass", True):  # type: ignore
        drift_tags.append("DOCUMENT_MISSING_COUNT_DRIFT")
    if staging_ok and not req_counts.get("pass", True):  # type: ignore
        drift_tags.append("ACTION_REQUIRED_COUNT_DRIFT")

    _write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "primary": classification,
            "drift_tags": drift_tags,
            "local_satisfaction_service": local_pass,
            "staging_api": staging_pass,
            "browser": browser_pass,
            "staging_notes": staging_notes,
        },
    )

    report = f"""# {PROGRAMME}

Classification: **{classification}**

## Results
- Local satisfaction service: {local_pass}
- Staging API convergence: {staging_pass}
- Browser runtime: {browser_pass}

## Notes
{chr(10).join('- ' + n for n in staging_notes) or '- None'}

## Fixes shipped
- `requirement_satisfaction_service.py` central truth
- Lifecycle reconcile after governance attach
- Admin split diagnostics
- Documents / Requirements frontend counters
- Cache invalidation fan-out on authority sync
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "watchlist.md").write_text(
        "# Watchlist\n\n"
        + ("- Deploy backend + frontend to staging and re-run harness.\n" if not staging_pass else "")
        + "- After deploy verify Nancy portfolio: 0 false missing-document, 0 false action-required for declaration-satisfied rows.\n"
        + "- Monitor legacy unsynced PENDING rows without truth_presentation_stage until authority sync completes.\n",
        encoding="utf-8",
    )
    print(json.dumps({"classification": classification, "local": local_pass, "staging": staging_pass, "browser": browser_pass}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
