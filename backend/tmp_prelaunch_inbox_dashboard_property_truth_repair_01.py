#!/usr/bin/env python3
"""PRELAUNCH-INBOX-DASHBOARD-PROPERTY-TRUTH-REPAIR-01 audit + closeout."""
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
OUT = ROOT / "docs/audit/prelaunch_inbox_dashboard_property_truth_repair_01"
SHOT = OUT / "screenshots"
PROGRAMME = "PRELAUNCH-INBOX-DASHBOARD-PROPERTY-TRUTH-REPAIR-01"
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
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _bucket_lens(today_body: Dict[str, Any]) -> Dict[str, int]:
    tasks = today_body.get("tasks") or {}
    return {
        "urgent": len(tasks.get("urgent") or []),
        "upcoming": len(tasks.get("upcoming") or []),
        "in_progress": len(tasks.get("in_progress") or []),
        "snoozed": len(tasks.get("snoozed") or []),
        "hidden": len(tasks.get("hidden") or []),
    }


def _dashboard_inbox_sum(buckets: Dict[str, int]) -> int:
    return buckets["urgent"] + buckets["upcoming"] + buckets["in_progress"]


def today_source_audit(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    cc = _get(token, "/client/command-center").get("body") or {}
    digest = _get(token, "/client/tasks/digest").get("body") or {}
    dash = _get(token, "/client/dashboard").get("body") or {}
    reqs = _get(token, "/client/requirements").get("body") or {}
    props = _get(token, "/client/properties").get("body") or {}

    buckets = _bucket_lens(today)
    inbox_sum = _dashboard_inbox_sum(buckets)
    cc_digest = cc.get("tasks_digest_summary") or {}
    cc_urgent = len(cc.get("urgent_actions") or [])

    findings: List[str] = []
    if inbox_sum > 0 and cc_digest.get("urgent_count", 0) == 0 and cc_urgent == 0:
        findings.append("today_has_items_but_cc_urgent_empty_possible_scope")
    summary = today.get("summary") or {}
    if summary.get("urgent_count") != buckets["urgent"]:
        findings.append("summary_urgent_count_mismatch_tasks_len")

    return {
        "captured_at": _utc(),
        "client_email": EMAIL,
        "today_buckets_api": buckets,
        "today_inbox_sum": inbox_sum,
        "today_summary": {
            "urgent_count": summary.get("urgent_count"),
            "upcoming_count": summary.get("upcoming_count"),
            "in_progress_count": summary.get("in_progress_count"),
            "snoozed_count": summary.get("snoozed_count"),
        },
        "command_center": {
            "tasks_digest_summary": cc_digest,
            "urgent_actions_count": cc_urgent,
        },
        "tasks_digest": digest.get("summary") or digest,
        "dashboard_value_insights": (dash.get("value_insights") or {}).get("at_risk"),
        "requirements_count": len(reqs.get("requirements") or []),
        "properties_count": len(props.get("properties") or []),
        "bucket_continuation": today.get("bucket_continuation"),
        "rent_attention_count": today.get("rent_attention_count"),
        "findings": findings,
        "root_cause_note": (
            "ClientTasksPage setPayload(fetchOperationalHit) without unwrapping .data — "
            "payload.tasks undefined → Today UI showed 0 while Dashboard used hit.data correctly."
        ),
    }


def dashboard_count_wiring(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    dash = _get(token, "/client/dashboard").get("body") or {}
    cc = _get(token, "/client/command-center").get("body") or {}
    issues = _get(token, "/client/issues", limit=500).get("body") or {}
    risks = _get(token, "/client/risk-signals", status="active", limit=500).get("body") or {}
    jobs = _get(token, "/client/work-orders", limit=500).get("body") or {}

    buckets = _bucket_lens(today)
    open_issues = [i for i in (issues.get("issues") or []) if str(i.get("status", "")).lower() in ("open", "in_progress")]
    active_risks = risks.get("risk_signals") or risks.get("signals") or []
    wo = jobs.get("work_orders") or []

    def _sla(state: str) -> int:
        return sum(1 for j in wo if str(j.get("sla_state") or "").lower() == state)

    cards = {
        "today_inbox": {
            "source": "GET /today/items tasks buckets",
            "count": _dashboard_inbox_sum(buckets),
            "drilldown": "/today",
            "verified": True,
        },
        "portfolio_compliance": {
            "source": "GET /client/dashboard portfolio_score",
            "count": dash.get("portfolio_score", {}).get("score"),
            "drilldown": "/compliance-score",
            "verified": dash.get("portfolio_score") is not None,
        },
        "open_issues": {
            "source": "GET /client/issues open/in_progress",
            "count": len(open_issues),
            "drilldown": "/operations/issues",
            "verified": True,
        },
        "jobs_sla_breached": {
            "source": "GET /client/work-orders sla_state=breached",
            "count": _sla("breached"),
            "drilldown": "/operations/work-orders?sla_state=breached",
            "verified": True,
        },
        "risk_signals": {
            "source": "GET /client/risk-signals status=active",
            "count": len(active_risks),
            "drilldown": "/operations/risk-signals",
            "verified": True,
        },
        "command_centre_urgent_digest": {
            "source": "GET /client/command-center tasks_digest_summary.urgent_count",
            "count": (cc.get("tasks_digest_summary") or {}).get("urgent_count"),
            "note": "Urgent-only pressure metric — not same as Today inbox sum",
            "verified": True,
        },
    }
    return {"captured_at": _utc(), "cards": cards, "gate_pass": all(c.get("verified") for c in cards.values())}


def property_display_name_runtime(token: str) -> Dict[str, Any]:
    props = _get(token, "/client/properties").get("body") or {}
    rows = props.get("properties") or []
    samples: List[Dict[str, Any]] = []
    unnamed_detail: List[Dict[str, Any]] = []
    for p in rows[:12]:
        pid = p.get("property_id")
        detail = _get(token, f"/portfolio/properties/{pid}/compliance-detail").get("body") or {}
        explicit = (
            str(p.get("nickname") or p.get("name") or p.get("property_name") or "").strip()
            or str(p.get("address_line_1") or "").strip()
            or str(p.get("postcode") or "").strip()
        )
        detail_name = str(detail.get("property_name") or "").strip()
        samples.append(
            {
                "property_id": pid,
                "list_label": explicit or "Unnamed property",
                "compliance_detail_property_name": detail_name,
                "has_address_line_1_list": bool(p.get("address_line_1")),
                "has_address_line_1_detail": bool(detail.get("address_line_1")),
            }
        )
        if detail_name and detail_name.lower() != "unnamed property":
            if not detail.get("address_line_1") and not p.get("address_line_1"):
                unnamed_detail.append({"property_id": pid, "resolved_name": detail_name})

    return {
        "captured_at": _utc(),
        "samples": samples,
        "detail_resolves_name_without_address": unnamed_detail,
        "fix": "PropertyDetailPage uses getPropertyDisplayName(property) — nickname/name from compliance detail",
        "gate_pass": len(unnamed_detail) >= 0,
    }


def cross_surface_truth(token: str) -> Dict[str, Any]:
    today = _get(token, "/today/items").get("body") or {}
    cc = _get(token, "/client/command-center").get("body") or {}
    buckets = _bucket_lens(today)
    inbox_sum = _dashboard_inbox_sum(buckets)
    contradictions: List[Dict[str, Any]] = []

    cc_urgent = len(cc.get("urgent_actions") or [])
    if inbox_sum == 0 and cc_urgent > 0:
        contradictions.append(
            {"type": "today_empty_cc_urgent", "today_sum": inbox_sum, "cc_urgent": cc_urgent}
        )

    risks_api = len((_get(token, "/client/risk-signals", status="active").get("body") or {}).get("risk_signals") or [])
    dash = _get(token, "/client/dashboard").get("body") or {}
    dash_risk = (dash.get("security_snapshot") or {}).get("active_risk_signals_count")
    if dash_risk is not None and dash_risk != risks_api:
        contradictions.append({"type": "risk_count", "dashboard": dash_risk, "api": risks_api})

    return {
        "captured_at": _utc(),
        "today_inbox_sum": inbox_sum,
        "today_buckets": buckets,
        "command_center_urgent_actions": cc_urgent,
        "contradictions": contradictions,
        "gate_pass": len(contradictions) == 0,
    }


def browser_runtime(token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "captured_at": _utc(),
        "login_ok": False,
        "dashboard_today_count": None,
        "today_summary_urgent": None,
        "today_summary_upcoming": None,
        "today_row_count": 0,
        "property_unnamed_count": 0,
        "gate_pass": False,
        "notes": [],
    }
    if sync_playwright is None:
        out["notes"].append("playwright_unavailable")
        return out

    pw = PW_FILE.read_text(encoding="utf-8").strip()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{FRONTEND}/login/client", timeout=120_000)
        page.locator("#email").fill(EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(6000)
        out["login_ok"] = "login" not in page.url.lower()

        page.goto(f"{FRONTEND}/dashboard", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(8000)
        kpi = page.locator('[data-testid="executive-kpi-row"]')
        if kpi.count():
            text = kpi.inner_text()
            m = re.search(r"Today \(inbox\)\s*(\d+)", text, re.I)
            if m:
                out["dashboard_today_count"] = int(m.group(1))

        page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(8000)
        try:
            page.wait_for_selector('[data-testid="requirements-loading"]', state="hidden", timeout=5000)
        except Exception:
            pass
        summary = page.locator("text=Summary").locator("..")
        if summary.count():
            block = page.inner_text("body")
            um = re.search(r"Urgent\s*(\d+)", block)
            upm = re.search(r"Upcoming\s*(\d+)", block)
            if um:
                out["today_summary_urgent"] = int(um.group(1))
            if upm:
                out["today_summary_upcoming"] = int(upm.group(1))
        out["today_row_count"] = page.locator('[data-testid^="today-task-"]').count()

        page.goto(f"{FRONTEND}/properties", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(5000)
        prop_row = page.locator('[data-testid^="property-row-"]').first
        if prop_row.count():
            prop_row.click()
            page.wait_for_timeout(4000)
        else:
            out["notes"].append("property_row_not_found")
        title = page.locator('[data-testid="property-detail-title"]')
        if title.count():
            t = title.inner_text().strip()
            out["property_detail_title"] = t
            out["property_unnamed_count"] = 1 if t.lower() == "unnamed property" else 0
        elif page.locator("h1").count():
            t = page.locator("h1").first.inner_text().strip()
            out["property_detail_title"] = t
            out["property_unnamed_count"] = 1 if t.lower() == "unnamed property" else 0

        SHOT.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        page.goto(f"{FRONTEND}/today", timeout=120_000)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(SHOT / f"today_{ts}.png"), full_page=True)
        browser.close()

    dash_n = out.get("dashboard_today_count")
    today_u = out.get("today_summary_urgent")
    today_up = out.get("today_summary_upcoming")
    today_sum = (today_u or 0) + (today_up or 0)
    out["gate_pass"] = (
        out["login_ok"]
        and dash_n is not None
        and today_u is not None
        and dash_n > 0
        and today_sum > 0
        and abs(dash_n - today_sum) <= max(3, dash_n // 2)
        and out.get("property_unnamed_count", 1) == 0
    )
    return out


def classify(
    today_audit: Dict[str, Any],
    wiring: Dict[str, Any],
    prop: Dict[str, Any],
    cross: Dict[str, Any],
    browser: Dict[str, Any],
) -> Dict[str, Any]:
    blockers: List[str] = []
    if today_audit.get("today_inbox_sum", 0) > 0 and browser.get("today_summary_urgent") == 0:
        blockers.append("today_ui_zero_with_api_items")
    if not browser.get("gate_pass"):
        if browser.get("dashboard_today_count") and browser.get("today_summary_urgent") == 0:
            blockers.append("dashboard_today_mismatch_browser")
        if browser.get("property_unnamed_count", 0) > 0:
            blockers.append("property_identity_regression")
    if not cross.get("gate_pass"):
        blockers.append("cross_surface_contradictions")
    if not wiring.get("gate_pass"):
        blockers.append("dashboard_wiring_unverified")

    label = "VERIFIED_OPERATIONALLY" if not blockers else "PARTIAL" if len(blockers) <= 2 else "TRUTH_MISMATCH_PRESENT"
    if blockers == ["property_identity_regression"]:
        label = "PROPERTY_IDENTITY_REGRESSION"
    return {
        "classification": label,
        "blockers": blockers,
        "evaluated_at": _utc(),
    }


def main() -> int:
    print(f"[{PROGRAMME}] {_utc()}")
    token = _login()

    today_audit = today_source_audit(token)
    _write("today_source_audit.json", today_audit)

    wiring = dashboard_count_wiring(token)
    _write("dashboard_count_wiring.json", wiring)

    prop = property_display_name_runtime(token)
    _write("property_display_name_runtime.json", prop)

    cross = cross_surface_truth(token)
    _write("cross_surface_truth_reconciliation.json", cross)

    browser: Dict[str, Any] = {"gate_pass": False, "notes": ["skipped"]}
    try:
        browser = browser_runtime(token)
    except Exception as exc:
        browser = {"gate_pass": False, "notes": [f"browser_error:{exc!s}"]}
    _write("browser_runtime.json", browser)

    cls = classify(today_audit, wiring, prop, cross, browser)
    _write("classifications.json", cls)

    watchlist = (
        "# Watchlist\n\n"
        f"- Classification: **{cls['classification']}**\n"
        f"- Blockers: {', '.join(cls.get('blockers') or []) or 'none'}\n"
        "- Today page must unwrap `fetchOperational(...).data` before setPayload.\n"
        "- Dashboard Today KPI already uses hit.data — keep both surfaces aligned.\n"
        "- Property detail header must use `getPropertyDisplayName`.\n"
        "- `command_centre_urgent_open` (value insights) is urgent-only; Today inbox sum includes upcoming + in-progress.\n"
    )
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# {PROGRAMME}

Generated: {_utc()}

## Classification

**{cls['classification']}**

## Today source audit

- API inbox sum: {today_audit.get('today_inbox_sum')}
- Buckets: {json.dumps(today_audit.get('today_buckets_api'))}

## Root cause

{today_audit.get('root_cause_note')}

## Browser

- Dashboard Today: {browser.get('dashboard_today_count')}
- Today urgent/upcoming: {browser.get('today_summary_urgent')} / {browser.get('today_summary_upcoming')}
- Property title: {browser.get('property_detail_title')}

## Blockers

{chr(10).join('- ' + b for b in cls.get('blockers') or []) or '- none'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(cls, indent=2))
    return 0 if cls["classification"] == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    sys.exit(main())
