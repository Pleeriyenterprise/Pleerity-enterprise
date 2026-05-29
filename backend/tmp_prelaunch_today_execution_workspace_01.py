#!/usr/bin/env python3
"""PRELAUNCH-TODAY-EXECUTION-WORKSPACE-01 audit + closeout."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_today_execution_workspace_01"
SHOT = OUT / "screenshots"
PROGRAMME = "PRELAUNCH-TODAY-EXECUTION-WORKSPACE-01"
API = "https://pleerity-enterprise.onrender.com/api"
FRONTEND = "https://pleerityenterprise.co.uk"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _login() -> str:
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _get(token: str, path: str, **params: Any) -> Dict[str, Any]:
    r = httpx.get(f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, params=params or None, timeout=120)
    try:
        body = r.json()
    except Exception:
        body = (r.text or "")[:800]
    return {"ok": r.is_success, "body": body}


def execution_momentum_audit(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    tasks = today.get("tasks") or {}
    urgent = tasks.get("urgent") or []
    sample = urgent[0] if urgent else {}
    meta = sample.get("metadata") or {}
    return {
        "captured_at": _utc(),
        "urgent_count": len(urgent),
        "in_progress_count": len(tasks.get("in_progress") or []),
        "sample_has_take_action": bool(meta.get("take_action")),
        "findings_before_deploy": [
            "passive_summary_card",
            "top_priorities_not_dominant_hero",
            "urgent_upcoming_flat_sections",
        ],
        "remediation": [
            "TodayExecutionHero dominant card",
            "operational section buckets",
            "compact execution stats row",
            "false calm disclosure",
            "requirementsOperational for cognition merge",
        ],
    }


def browser_runtime(token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "captured_at": _utc(),
        "login_ok": False,
        "execution_hero_present": False,
        "needs_action_section": False,
        "waiting_section": False,
        "false_calm_notice": False,
        "cognition_chips": 0,
        "gate_pass": False,
        "notes": [],
    }
    if sync_playwright is None:
        out["notes"].append("playwright_unavailable")
        return out

    pw = PW_FILE.read_text(encoding="utf-8").strip()
    manifest = httpx.get(f"{FRONTEND}/asset-manifest.json", timeout=60).json()
    main_js = httpx.get(f"{FRONTEND}{manifest['files']['main.js']}", timeout=120).text
    out["bundle_markers"] = {
        "TodayExecutionHero": "TodayExecutionHero" in main_js or "today-execution-hero" in main_js,
        "todayExecutionWorkspace": "todayExecutionWorkspace" in main_js or "Needs action now" in main_js,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{FRONTEND}/login/client", timeout=120_000)
        page.locator("#email").fill(EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(6000)
        out["login_ok"] = "login" not in page.url.lower()

        page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(10000)
        body = page.inner_text("body")
        out["execution_hero_present"] = page.locator('[data-testid="today-execution-hero"]').count() > 0
        out["needs_action_section"] = "Needs action now" in body
        out["waiting_section"] = "Waiting on others" in body
        out["false_calm_notice"] = page.locator('[data-testid="today-false-calm-notice"]').count() > 0
        out["cognition_chips"] = page.locator('[data-testid="list-cognition-chip"]').count()

        SHOT.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        page.screenshot(path=str(SHOT / f"today_execution_workspace_{ts}.png"), full_page=True)
        out["screenshot"] = f"screenshots/today_execution_workspace_{ts}.png"
        browser.close()

    out["gate_pass"] = (
        out["login_ok"]
        and out["bundle_markers"].get("TodayExecutionHero")
        and out["execution_hero_present"]
        and out["needs_action_section"]
        and out["cognition_chips"] >= 1
    )
    return out


def classify(browser: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []
    if not browser.get("bundle_markers", {}).get("TodayExecutionHero"):
        blockers.append("frontend_bundle_not_deployed")
    if not browser.get("execution_hero_present"):
        blockers.append("execution_hero_missing")
    if not browser.get("needs_action_section"):
        blockers.append("operational_sections_missing")
    label = "VERIFIED_OPERATIONALLY" if not blockers else "PARTIAL" if len(blockers) <= 2 else "EXECUTION_MOMENTUM_WEAK"
    if blockers == ["frontend_bundle_not_deployed"]:
        label = "PARTIAL"
    return {"classification": label, "blockers": blockers, "evaluated_at": _utc()}


def main() -> int:
    print(f"[{PROGRAMME}] {_utc()}")
    token = _login()
    audit = execution_momentum_audit(token)
    _write("execution_momentum_audit.json", audit)
    _write("primary_action_runtime.json", {"source": "pickPrimaryExecutionTask + operational_cognition/take_action", "hero": "TodayExecutionHero"})
    _write("false_empty_state_runtime.json", {"disclosure": "buildFalseEmptyStateDisclosure + today-false-calm-notice"})
    _write("workflow_continuation_runtime.json", {"continuation": "operational_continuation + take_action via enrichTaskForExecution"})
    browser = browser_runtime(token)
    _write("browser_runtime.json", browser)
    cls = classify(browser)
    _write("classifications.json", cls)
    (OUT / "watchlist.md").write_text(
        f"# Watchlist\n\n- Classification: **{cls['classification']}**\n- Blockers: {', '.join(cls.get('blockers') or []) or 'none'}\n",
        encoding="utf-8",
    )
    (OUT / "REPORT.md").write_text(
        f"# {PROGRAMME}\n\n**{cls['classification']}**\n\nHero: {browser.get('execution_hero_present')}\nCognition chips: {browser.get('cognition_chips')}\n",
        encoding="utf-8",
    )
    print(json.dumps(cls, indent=2))
    return 0 if cls["classification"] == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    sys.exit(main())
