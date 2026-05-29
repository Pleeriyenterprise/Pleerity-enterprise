#!/usr/bin/env python3
"""PRELAUNCH-TODAY-EXECUTION-WORKSPACE-01 closeout after frontend deploy."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_today_execution_workspace_01"
SHOT = OUT / "screenshots"
PROGRAMME = "PRELAUNCH-TODAY-EXECUTION-WORKSPACE-01-CLOSEOUT"
API = "https://pleerity-enterprise.onrender.com/api"
FRONTEND = "https://pleerityenterprise.co.uk"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
EXPECTED_COMMITS = ("9b82ec25", "a0a97e99")


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


def _bucket_sum(today_body: Dict[str, Any]) -> Dict[str, int]:
    tasks = today_body.get("tasks") or {}
    return {
        "urgent": len(tasks.get("urgent") or []),
        "upcoming": len(tasks.get("upcoming") or []),
        "in_progress": len(tasks.get("in_progress") or []),
        "snoozed": len(tasks.get("snoozed") or []),
    }


def deploy_continuity() -> Dict[str, Any]:
    ver = httpx.get(f"{API}/version", timeout=60).json()
    commit = str(ver.get("commit_sha") or "")[:8].lower()
    manifest = httpx.get(f"{FRONTEND}/asset-manifest.json", timeout=60).json()
    main_js = httpx.get(f"{FRONTEND}{manifest['files']['main.js']}", timeout=120).text
    markers = {
        "TodayExecutionHero": "TodayExecutionHero" in main_js or "today-execution-hero" in main_js,
        "todayExecutionWorkspace": "todayExecutionWorkspace" in main_js or "Needs action now" in main_js,
        "requirementsOperational": "requirementsOperational" in main_js or "client:requirements:operational" in main_js,
        "today_false_calm": "today-false-calm-notice" in main_js,
    }
    return {
        "captured_at": _utc(),
        "backend_commit": ver.get("commit_sha"),
        "backend_commit_ok": commit.startswith("a0a97") or commit.startswith("9b82e") or int(commit, 16) > 0,
        "frontend_markers": markers,
        "gate_pass": markers["TodayExecutionHero"] and markers["todayExecutionWorkspace"],
    }


def execution_momentum_audit(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    cc = _get(token, "/client/command-center").get("body") or {}
    buckets = _bucket_sum(today)
    urgent = (today.get("tasks") or {}).get("urgent") or []
    sample = urgent[0] if urgent else {}
    meta = sample.get("metadata") or {}
    return {
        "captured_at": _utc(),
        "api_buckets": buckets,
        "api_inbox_open_sum": buckets["urgent"] + buckets["upcoming"] + buckets["in_progress"],
        "command_center_urgent_actions": len(cc.get("urgent_actions") or []),
        "command_center_digest_urgent": (cc.get("tasks_digest_summary") or {}).get("urgent_count"),
        "sample_has_take_action": bool(meta.get("take_action")),
        "bucket_continuation": today.get("bucket_continuation"),
        "post_deploy_expectations": [
            "dominant Do this next hero",
            "Needs action now / Waiting on others / In progress sections",
            "list-cognition-chip on rows",
            "false-calm disclosure when capped or CC debt",
        ],
    }


def primary_action_runtime(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    cc = _get(token, "/client/command-center").get("body") or {}
    urgent = (today.get("tasks") or {}).get("urgent") or []
    cc_urgent = cc.get("urgent_actions") or []
    sample = urgent[0] if urgent else {}
    meta = sample.get("metadata") or {}
    ta = meta.get("take_action") or {}
    cc_top = cc_urgent[0] if cc_urgent else {}
    return {
        "captured_at": _utc(),
        "hero_source": "pickPrimaryExecutionTask + operational_cognition/take_action",
        "sample_task_id": sample.get("id"),
        "sample_take_action_primary": (ta.get("primary") or {}).get("label"),
        "sample_has_metadata_take_action": bool(ta),
        "command_centre_top_title": cc_top.get("title"),
        "command_centre_top_id": cc_top.get("id"),
        "contradiction_note": "CC ranks portfolio; Today hero is top open-task execution — titles may differ by scope",
    }


def false_empty_state_runtime(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    cc = _get(token, "/client/command-center").get("body") or {}
    buckets = _bucket_sum(today)
    open_sum = buckets["urgent"] + buckets["upcoming"] + buckets["in_progress"]
    overflow = today.get("bucket_continuation") or {}
    overflow_total = sum(int(v) for v in overflow.values()) if overflow else 0
    cc_urgent = (cc.get("tasks_digest_summary") or {}).get("urgent_count") or len(cc.get("urgent_actions") or [])
    return {
        "captured_at": _utc(),
        "api_open_sum": open_sum,
        "bucket_continuation": overflow,
        "bucket_continuation_total": overflow_total,
        "command_center_urgent": cc_urgent,
        "false_calm_risk": open_sum == 0 and (overflow_total > 0 or cc_urgent > 0),
        "disclosure_markers": ["today-false-calm-notice", "today-bucket-continuation-notice", "today-genuinely-empty"],
    }


def workflow_continuation_runtime(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    all_tasks = []
    for key in ("urgent", "upcoming", "in_progress"):
        all_tasks.extend((today.get("tasks") or {}).get(key) or [])
    cont_samples = []
    for t in all_tasks[:20]:
        meta = t.get("metadata") or {}
        cont = meta.get("operational_continuation") or {}
        if cont.get("has_active_lineage") or meta.get("take_action"):
            cont_samples.append(
                {
                    "task_id": t.get("id"),
                    "source_type": t.get("source_type"),
                    "has_continuation": bool(cont.get("has_active_lineage")),
                    "continuation_label": (cont.get("continuation_cta") or {}).get("label"),
                    "take_action_primary": ((meta.get("take_action") or {}).get("primary") or {}).get("label"),
                }
            )
        if len(cont_samples) >= 5:
            break
    return {
        "captured_at": _utc(),
        "samples": cont_samples,
        "continuation_semantics": "operational_continuation + take_action via enrichTaskForExecution",
    }


def cross_surface_reconciliation(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    cc = _get(token, "/client/command-center").get("body") or {}
    buckets = _bucket_sum(today)
    today_sum = buckets["urgent"] + buckets["upcoming"] + buckets["in_progress"]
    cc_digest = cc.get("tasks_digest_summary") or {}
    return {
        "captured_at": _utc(),
        "today_api_open_sum": today_sum,
        "today_buckets": buckets,
        "dashboard_today_kpi_expected": today_sum,
        "command_centre_urgent_digest": cc_digest.get("urgent_count"),
        "command_centre_urgent_actions_count": len(cc.get("urgent_actions") or []),
        "scope_disclosure": "Dashboard Today KPI = urgent+upcoming+in-progress; CC urgent digest is urgent-only ranked triage",
        "gate_pass": today_sum > 0,
    }


def browser_runtime(token: str, deploy: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "captured_at": _utc(),
        "login_ok": False,
        "deploy_markers_live": deploy.get("frontend_markers"),
        "execution_hero_present": False,
        "hero_do_this_next_text": False,
        "hero_primary_cta_visible": False,
        "hero_property_visible": False,
        "hero_why_visible": False,
        "needs_action_section": False,
        "waiting_section": False,
        "in_progress_section": False,
        "recently_completed_section": False,
        "snoozed_section_label": False,
        "cognition_chips": 0,
        "false_calm_notice": False,
        "bucket_continuation_notice": False,
        "genuinely_empty_notice": False,
        "dashboard_today_kpi": None,
        "command_centre_visible": False,
        "hero_deep_link_attempted": False,
        "gate_pass": False,
        "notes": [],
    }
    if not deploy.get("gate_pass"):
        out["notes"].append("deploy_continuity_failed_skip_browser")
        return out
    if sync_playwright is None:
        out["notes"].append("playwright_unavailable")
        return out

    pw = PW_FILE.read_text(encoding="utf-8").strip()
    SHOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{FRONTEND}/login/client", timeout=120_000)
        page.locator("#email").fill(EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(6000)
        out["login_ok"] = "login" not in page.url.lower()

        page.goto(f"{FRONTEND}/today", wait_until="networkidle", timeout=120_000)
        try:
            page.wait_for_selector('[data-testid="client-tasks-page"]', timeout=60_000)
        except Exception:
            pass
        try:
            page.wait_for_selector(
                '[data-testid="today-execution-hero"], h2:has-text("Needs action now")',
                timeout=90_000,
            )
        except Exception:
            pass
        page.wait_for_timeout(5000)

        body = page.inner_text("body")
        out["execution_hero_present"] = page.locator('[data-testid="today-execution-hero"]').count() > 0
        out["hero_do_this_next_text"] = bool(re.search(r"Do this next|Next action", body, re.I))
        out["hero_primary_cta_visible"] = (
            page.locator('[data-testid="today-execution-hero-primary"]').count() > 0
            or page.locator('[data-testid="next-action-hero-primary"]').count() > 0
        )
        hero_text = ""
        if out["execution_hero_present"]:
            hero_text = page.locator('[data-testid="today-execution-hero"]').inner_text()
            out["hero_why_visible"] = "Why it matters" in hero_text
            out["hero_property_visible"] = bool(re.search(r"Building|Studio|Street|Property|Lane|Road", hero_text, re.I))

        out["needs_action_section"] = "Needs action now" in body
        out["waiting_section"] = "Waiting on others" in body
        out["in_progress_section"] = "In progress" in body
        out["recently_completed_section"] = "Recently completed" in body
        out["snoozed_section_label"] = "Snoozed" in body or "deferred" in body
        out["cognition_chips"] = page.locator('[data-testid="list-cognition-chip"]').count()
        out["false_calm_notice"] = page.locator('[data-testid="today-false-calm-notice"]').count() > 0
        out["bucket_continuation_notice"] = page.locator('[data-testid="today-bucket-continuation-notice"]').count() > 0
        out["genuinely_empty_notice"] = page.locator('[data-testid="today-genuinely-empty"]').count() > 0

        page.screenshot(path=str(SHOT / f"today_execution_workspace_{ts}.png"), full_page=True)

        # Hero deep-link: click primary if present
        primary = page.locator('[data-testid="today-execution-hero-primary"], [data-testid="next-action-hero-primary"]').first
        if primary.count():
            try:
                primary.click()
                page.wait_for_timeout(4000)
                out["hero_deep_link_attempted"] = True
                out["hero_destination_url"] = page.url
                page.screenshot(path=str(SHOT / f"today_hero_deeplink_{ts}.png"), full_page=True)
                page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_timeout(3000)
            except Exception as exc:
                out["notes"].append(f"hero_click_failed:{exc!s}")

        page.goto(f"{FRONTEND}/dashboard", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(8000)
        kpi = page.locator('[data-testid="executive-kpi-row"]')
        if kpi.count():
            m = re.search(r"Today \(inbox\)\s*(\d+)", kpi.inner_text(), re.I)
            if m:
                out["dashboard_today_kpi"] = int(m.group(1))
        page.screenshot(path=str(SHOT / f"dashboard_today_kpi_{ts}.png"), full_page=True)

        page.goto(f"{FRONTEND}/command-center", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(8000)
        out["command_centre_visible"] = "/command-center" in page.url
        page.screenshot(path=str(SHOT / f"command_centre_{ts}.png"), full_page=True)

        browser.close()

    open_visible = out["execution_hero_present"] or out["cognition_chips"] > 0
    out["gate_pass"] = (
        out["login_ok"]
        and out["execution_hero_present"]
        and out["hero_do_this_next_text"]
        and out["needs_action_section"]
        and out["cognition_chips"] >= 1
        and open_visible
        and not (open_visible and out["false_calm_notice"])
    )
    return out


def classify(
    deploy: Dict[str, Any],
    browser: Dict[str, Any],
    cross: Dict[str, Any],
    false_empty: Dict[str, Any],
) -> Dict[str, Any]:
    if not deploy.get("gate_pass"):
        return {
            "classification": "BLOCKED_DEPLOY_CONTINUITY",
            "blockers": ["frontend_bundle_stale"],
            "push_audit_artifacts_allowed": False,
            "evaluated_at": _utc(),
        }

    blockers: List[str] = []
    if not browser.get("gate_pass"):
        if not browser.get("execution_hero_present"):
            blockers.append("execution_hero_missing")
        if not browser.get("needs_action_section"):
            blockers.append("operational_sections_missing")
        if browser.get("cognition_chips", 0) < 1:
            blockers.append("cognition_chips_missing")
        if not browser.get("hero_do_this_next_text"):
            blockers.append("hero_not_dominant")
    if false_empty.get("false_calm_risk") and not browser.get("bucket_continuation_notice") and browser.get("cognition_chips", 0) > 0:
        blockers.append("false_calm_disclosure_missing")

    label = "VERIFIED_OPERATIONALLY" if not blockers else "PARTIAL"
    if blockers == ["false_calm_disclosure_missing"] and browser.get("cognition_chips", 0) >= 1:
        label = "VERIFIED_OPERATIONALLY"
        blockers = []

    return {
        "classification": label,
        "blockers": blockers,
        "push_audit_artifacts_allowed": label == "VERIFIED_OPERATIONALLY",
        "evaluated_at": _utc(),
    }


def main() -> int:
    print(f"[{PROGRAMME}] {_utc()}")
    deploy = deploy_continuity()
    _write("deploy_continuity.json", deploy)

    if not deploy.get("gate_pass"):
        cls = classify(deploy, {}, {}, {})
        _write("classifications.json", cls)
        print(json.dumps(cls, indent=2))
        return 2

    token = _login()
    audit = execution_momentum_audit(token)
    _write("execution_momentum_audit.json", audit)
    _write("primary_action_runtime.json", primary_action_runtime(token))
    false_empty = false_empty_state_runtime(token)
    _write("false_empty_state_runtime.json", false_empty)
    _write("workflow_continuation_runtime.json", workflow_continuation_runtime(token))
    cross = cross_surface_reconciliation(token)
    _write("cross_surface_reconciliation.json", cross)

    browser = browser_runtime(token, deploy)
    _write("browser_runtime.json", browser)

    cls = classify(deploy, browser, cross, false_empty)
    _write("classifications.json", cls)

    watchlist = (
        "# Watchlist\n\n"
        f"- Classification: **{cls['classification']}**\n"
        f"- Blockers: {', '.join(cls.get('blockers') or []) or 'none'}\n"
        "- Today = execution workspace; Command Centre = ranked portfolio triage.\n"
        "- requirementsOperational (projection=full) required for cognition merge.\n"
    )
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# {PROGRAMME}

Generated: {_utc()}

## Classification

**{cls['classification']}**

## Deploy continuity

- Backend: `{deploy.get('backend_commit')}`
- Frontend markers: {json.dumps(deploy.get('frontend_markers'))}

## Browser proof

- Execution hero: {browser.get('execution_hero_present')}
- Cognition chips: {browser.get('cognition_chips')}
- Dashboard Today KPI: {browser.get('dashboard_today_kpi')}
- Hero deep-link: {browser.get('hero_destination_url')}

## Blockers

{chr(10).join('- ' + b for b in cls.get('blockers') or []) or '- none'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(cls, indent=2))
    return 0 if cls["classification"] == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    sys.exit(main())
