#!/usr/bin/env python3
"""PRELAUNCH-CUSTOMER-OPERATIONAL-LANGUAGE-GOVERNANCE-01 — audit harness."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_customer_operational_language_governance_01"
SHOT = OUT / "screenshots"
PROGRAMME = "PRELAUNCH-CUSTOMER-OPERATIONAL-LANGUAGE-GOVERNANCE-01"
API = "https://pleerity-enterprise.onrender.com/api"
FRONTEND = "https://pleerityenterprise.co.uk"
NANCY_EMAIL = "nancy@yopmail.com"
NANCY_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"

FORBIDDEN_PATTERNS = [
    re.compile(r"\bMISMATCHED_EVIDENCE\b"),
    re.compile(r"\bMISSING_EVIDENCE\b"),
    re.compile(r"\bGap:\s*[A-Z_]+", re.I),
    re.compile(r"\bKey:\s*[0-9a-f:\-]+", re.I),
    re.compile(r"\(\s*(HIGH|MEDIUM|LOW|CRITICAL)\s*\)", re.I),
    re.compile(r"classification signal", re.I),
    re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}.*MISMATCHED", re.I),
]

BACKEND_MARKERS = [
    "customer_operational_language_service",
    "sanitize_task_for_customer",
    "is_customer_safe_maintenance_escalation",
    "derive_customer_safe_issue_summary",
    "translate_internal_operational_message",
]

ROOT_CAUSE_FILES = [
    "services/compliance_gap_operational_bridge.py",
    "services/client_priority_stream.py",
    "services/unified_tasks_service.py",
    "services/today_projection_service.py",
    "services/operational_cognition_service.py",
    "services/command_center_service.py",
]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _git_short() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT.parent, text=True).strip()
    except Exception:
        return "unknown"


def _scan_text_for_leaks(text: str) -> List[str]:
    hits: List[str] = []
    for pat in FORBIDDEN_PATTERNS:
        if pat.search(text or ""):
            hits.append(pat.pattern)
    return hits


def _collect_task_strings(obj: Any, acc: List[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in (
                "title",
                "description",
                "customer_safe_title",
                "customer_safe_description",
                "why_matters",
                "recommended_action",
                "user_safe_summary",
                "primary_action_label",
            ) and isinstance(v, str):
                acc.append(v)
            _collect_task_strings(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _collect_task_strings(item, acc)


def _run_pytest() -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "pytest", "tests/test_customer_operational_language_service.py", "-q"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
    return {
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _login_client(retries: int = 4) -> Tuple[str, Dict[str, Any]]:
    pw = NANCY_PW.read_text(encoding="utf-8").strip()
    last_err = None
    for _ in range(retries):
        try:
            r = httpx.post(f"{API}/auth/login", json={"email": NANCY_EMAIL, "password": pw}, timeout=120)
            if r.status_code == 503:
                time.sleep(12)
                continue
            r.raise_for_status()
            body = r.json()
            return body["access_token"], body.get("user") or {}
        except Exception as exc:
            last_err = exc
            time.sleep(6)
    raise RuntimeError(f"client login failed: {last_err}")


def _api_surface_scan(token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    surfaces: Dict[str, Any] = {}
    endpoints = {
        "today_tasks": f"{API}/client/tasks",
        "command_center_bundle": f"{API}/client/command-center",
    }
    for name, url in endpoints.items():
        entry: Dict[str, Any] = {"url": url, "status": None, "leaks": [], "maintenance_cta_drift": []}
        try:
            r = httpx.get(url, headers=headers, timeout=120)
            entry["status"] = r.status_code
            if r.status_code == 200:
                body = r.json()
                texts: List[str] = []
                _collect_task_strings(body, texts)
                for t in texts:
                    entry["leaks"].extend(_scan_text_for_leaks(t))
                    if re.search(r"maintenance job", t, re.I) and re.search(
                        r"match|evidence|certificate|document", t, re.I
                    ):
                        entry["maintenance_cta_drift"].append(t[:200])
                entry["leaks"] = sorted(set(entry["leaks"]))
                entry["maintenance_cta_drift"] = entry["maintenance_cta_drift"][:8]
                entry["passed"] = not entry["leaks"] and not entry["maintenance_cta_drift"]
            else:
                entry["passed"] = False
                entry["error"] = r.text[:500]
        except Exception as exc:
            entry["passed"] = False
            entry["error"] = str(exc)
        surfaces[name] = entry
    return surfaces


def _browser_today_capture() -> Dict[str, Any]:
    if sync_playwright is None:
        return {"skipped": True, "reason": "playwright not installed", "passed": False}
    SHOT.mkdir(parents=True, exist_ok=True)
    result: Dict[str, Any] = {"screenshots": [], "page_leaks": [], "forbidden_phrases": [], "passed": False}
    pw = NANCY_PW.read_text(encoding="utf-8").strip()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FRONTEND}/login/client", timeout=120000)
        page.locator("#email").fill(NANCY_EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_url(re.compile(r"/(today|dashboard|requirements|properties|app/)"), timeout=120000)
        for path, fname in (("/today", "today.png"), ("/command-center", "command_centre.png")):
            page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(3000)
            shot = SHOT / fname
            page.screenshot(path=str(shot), full_page=True)
            result["screenshots"].append(str(shot.relative_to(ROOT)))
        body_text = page.inner_text("body")
        result["page_leaks"] = _scan_text_for_leaks(body_text)
        forbidden_ui = [
            "Gap:",
            "Key:",
            "MISMATCHED_EVIDENCE",
            "MISSING_EVIDENCE",
            "classification signal",
            "Ambiguous classification",
        ]
        result["forbidden_phrases"] = [p for p in forbidden_ui if p.lower() in body_text.lower()]
        result["passed"] = not result["page_leaks"] and not result["forbidden_phrases"]
        browser.close()
    return result


def main() -> int:
    ts = _utc()
    commit = _git_short()
    OUT.mkdir(parents=True, exist_ok=True)

    from services.customer_operational_language_service import translation_matrix_export

    bridge_src = (ROOT / "services/compliance_gap_operational_bridge.py").read_text(encoding="utf-8")
    root_cause = {
        "programme": PROGRAMME,
        "timestamp": ts,
        "commit": commit,
        "primary_leak_vectors": [
            {
                "file": "services/compliance_gap_operational_bridge.py",
                "issue": "Appended Gap/Key diagnostic suffix to maintenance issue descriptions",
                "fixed": "Gap: {gap_kind}" not in bridge_src,
            },
            {
                "file": "services/client_priority_stream.py",
                "issue": "Raw issue.description used as task title/text",
                "fixed": "derive_customer_safe_issue_summary wired",
            },
            {
                "file": "frontend/src/pages/ClientTasksPage.js",
                "issue": "Issue description used as card title",
                "fixed": "customer_safe_title preferred; Gap: rejected",
            },
            {
                "file": "services/today_projection_service.py",
                "issue": "Create maintenance job business action for all issues",
                "fixed": "is_customer_safe_maintenance_escalation gates CTA",
            },
            {
                "file": "services/command_center_service.py",
                "issue": "Degraded fallback used raw issue.description as title",
                "fixed": "language service + sanitize on slim tasks",
            },
        ],
        "screenshot_symptoms": [
            "Ambiguous classification signals. Gap: MISMATCHED_EVIDENCE (HIGH). Key: …",
            "Start maintenance job on evidence-gap cards",
        ],
    }
    _write("root_cause.json", root_cause)

    language_governance = {
        "programme": PROGRAMME,
        "timestamp": ts,
        "commit": commit,
        "architecture": [
            "Raw engine state",
            "Operational interpretation",
            "Governance truth",
            "Customer-safe semantic translation",
            "Role-aware action language",
            "UI presentation",
        ],
        "canonical_service": "services/customer_operational_language_service.py",
        "mandatory_call_sites": [
            "unified_tasks_service.get_unified_tasks_for_client (pre-return sanitize)",
            "today_projection_service.compact_task_for_today_list",
            "command_center_service._slim_task / _priority_action_to_slim_urgent",
            "client_priority_stream issue actions",
            "operational_cognition_service.build_envelope_for_issue",
            "compliance_gap_operational_bridge issue create",
        ],
        "forbidden_on_customer_surfaces": [
            "internal enums",
            "UUIDs / evidence keys",
            "Gap:/Key: diagnostics",
            "HIGH/MEDIUM/LOW engine flags",
            "classifier / reconciliation jargon",
        ],
    }
    _write("language_governance.json", language_governance)
    _write("translation_matrix.json", translation_matrix_export())

    pytest_result = _run_pytest()
    regression = {
        "programme": PROGRAMME,
        "timestamp": ts,
        "commit": commit,
        "pytest_customer_operational_language": pytest_result,
        "backend_markers_present": {
            m: (ROOT / "services/customer_operational_language_service.py").read_text(encoding="utf-8").find(m) >= 0
            for m in BACKEND_MARKERS
        },
        "bridge_no_gap_append": "Gap: {gap_kind}" not in bridge_src,
        "passed": pytest_result.get("passed") and "Gap: {gap_kind}" not in bridge_src,
    }
    _write("regression_runtime.json", regression)

    runtime = {"programme": PROGRAMME, "timestamp": ts, "commit": commit, "staging_api": None, "passed": False}
    browser = {"programme": PROGRAMME, "timestamp": ts, "commit": commit, "passed": False}
    try:
        token, _user = _login_client()
        runtime["staging_api"] = _api_surface_scan(token)
        runtime["passed"] = all(v.get("passed") for v in runtime["staging_api"].values())
    except Exception as exc:
        runtime["error"] = str(exc)
    try:
        browser = _browser_today_capture()
        browser["programme"] = PROGRAMME
        browser["timestamp"] = ts
        browser["commit"] = commit
    except Exception as exc:
        browser = {
            "programme": PROGRAMME,
            "timestamp": ts,
            "commit": commit,
            "passed": False,
            "error": str(exc),
        }
    _write("runtime_verification.json", runtime)
    _write("browser_runtime.json", browser)

    all_pass = (
        regression.get("passed")
        and runtime.get("passed")
        and browser.get("passed")
    )
    classification = {
        "programme": PROGRAMME,
        "timestamp": ts,
        "commit": commit,
        "classification": "VERIFIED_OPERATIONALLY" if all_pass else "IMPLEMENTED_PENDING_RUNTIME",
        "deploy_commit": commit,
        "gates": {
            "unit_regression": regression.get("passed"),
            "staging_api_no_leaks": runtime.get("passed"),
            "browser_today_no_leaks": browser.get("passed"),
        },
        "blocking_if_not_verified": [
            "Deploy language layer to staging",
            "Re-run harness after deploy",
            "Confirm Today cards show customer-safe copy only",
        ],
    }
    _write("classifications.json", classification)

    watchlist = OUT / "watchlist.md"
    watchlist.write_text(
        "\n".join(
            [
                "# Watchlist — customer operational language governance",
                "",
                f"- **Programme:** {PROGRAMME}",
                f"- **Commit (local):** `{commit}`",
                f"- **Classification:** {classification['classification']}",
                "",
                "## Post-deploy checks",
                "- Today / Command Centre API payloads: zero `Gap:` / `Key:` / internal enums",
                "- Evidence-gap issues: CTA must not be `Start maintenance job`",
                "- Legacy DB issue rows: sanitization must override stored diagnostic descriptions",
                "",
                "## Residual surfaces (monitor)",
                "- Admin diagnostics and audit logs (internal — exempt)",
                "- Upload pre-analysis API may still return `mismatch_reason_code` internally; ensure customer `user_messages` only on UI",
                "- Contractor / tenant portals: re-run cross-role harness after deploy",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = OUT / "REPORT.md"
    report.write_text(
        "\n".join(
            [
                f"# {PROGRAMME}",
                "",
                f"**Classification:** {classification['classification']}",
                "",
                f"**Local commit:** `{commit}`",
                f"**Harness timestamp:** {ts}",
                "",
                "## Summary",
                "",
                "Implemented canonical `customer_operational_language_service` and wired sanitisation into",
                "unified tasks, Today projection, Command Centre, priority stream, cognition envelopes,",
                "and compliance gap issue creation. Removed Gap/Key append from gap operational bridge.",
                "",
                "## Gate results",
                "",
                f"| Gate | Result |",
                f"|------|--------|",
                f"| Unit regression (`test_customer_operational_language_service`) | {'PASS' if regression.get('passed') else 'FAIL'} |",
                f"| Staging API leak scan | {'PASS' if runtime.get('passed') else 'PENDING/FAIL'} |",
                f"| Browser Today capture | {'PASS' if browser.get('passed') else 'PENDING/FAIL'} |",
                "",
                "## Root cause",
                "",
                "Internal gap diagnostics (`Gap: MISMATCHED_EVIDENCE (HIGH). Key: …`) were written into",
                "maintenance issue descriptions and surfaced verbatim on Today cards as titles and primary CTAs.",
                "",
                "## Next step",
                "",
                "Deploy to staging and re-run this harness for `VERIFIED_OPERATIONALLY`.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps({"classification": classification["classification"], "regression": regression.get("passed"), "runtime": runtime.get("passed"), "browser": browser.get("passed")}, indent=2))
    return 0 if regression.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
