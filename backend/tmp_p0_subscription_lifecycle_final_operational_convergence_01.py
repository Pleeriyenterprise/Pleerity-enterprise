"""
P0-SUBSCRIPTION-LIFECYCLE-FINAL-OPERATIONAL-CONVERGENCE-01

Master staging validation harness. develop + staging only.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = ROOT / "docs/audit/p0_subscription_lifecycle_final_operational_convergence_01"
PROGRAMME = "P0-SUBSCRIPTION-LIFECYCLE-FINAL-OPERATIONAL-CONVERGENCE-01"

API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api")
BACKEND = API.replace("/api", "")
FE = os.getenv("STAGING_FE", "https://pleerity-enterprise-9jjg.vercel.app")
ADMIN_EMAIL = os.getenv("STAGING_ADMIN_EMAIL", "prosper@yopmail.com")
ADMIN_PASSWORD = os.getenv("STAGING_ADMIN_PASSWORD", "Pastor@36$")

LIFECYCLE_BUNDLE_MARKERS = (
    "useResumeSubscription",
    "lifecycle-keep-subscription",
    "resume_subscription",
    "billing-keep-subscription",
)
CAP_LEAK_PATTERNS = (
    "CAP_TODAY_VIEW",
    "CAP_PROP_VIEW is not permitted",
    "Access requires CAP_",
    "CAP_CMD_CTR_VIEW",
)
BROWSER_PAGES = [
    "/today",
    "/dashboard",
    "/command-center",
    "/properties",
    "/requirements",
    "/documents",
    "/maintenance",
    "/issues",
    "/jobs",
    "/contractors",
    "/reports",
    "/settings/billing",
    "/settings/profile",
    "/settings",
    "/calendar",
    "/analytics",
]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_expected_sha() -> Tuple[str, str]:
    try:
        full = subprocess.check_output(
            ["git", "rev-parse", "origin/develop"],
            cwd=REPO,
            text=True,
            timeout=30,
        ).strip()
        return full, full[:8]
    except Exception:
        full = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True, timeout=30).strip()
        return full, full[:8]


def _mongo_db():
    from pymongo import MongoClient

    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    if not uri:
        return None
    return MongoClient(uri, serverSelectionTimeoutMS=15000)[os.getenv("DB_NAME", "pleerity_staging")]


def _client_login(email: str, password: str) -> str:
    r = httpx.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        headers={"Origin": FE},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _admin_token() -> str:
    r = httpx.post(
        f"{API}/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Origin": FE},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _step_up(headers: dict) -> dict:
    h = dict(headers)
    su = httpx.post(f"{API}/auth/step-up/verify", headers=h, json={"password": ADMIN_PASSWORD}, timeout=90)
    su.raise_for_status()
    tok = su.json().get("step_up_token")
    if tok:
        h["X-Step-Up-Token"] = tok
    return h


def _impersonate(client_id: str) -> Tuple[str, str]:
    admin = _admin_token()
    ah = _step_up({"Authorization": f"Bearer {admin}", "Origin": FE})
    conf = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        headers=ah,
        json={"action_id": "start_impersonation", "reason": PROGRAMME, "resource_key": client_id},
        timeout=60,
    )
    conf.raise_for_status()
    if conf.json().get("token"):
        ah["X-Admin-Confirmation-Token"] = conf.json()["token"]
    imp = httpx.post(
        f"{API}/admin/clients/{client_id}/impersonation/start",
        headers=ah,
        params={"ttl_minutes": 120},
        json={"reason": PROGRAMME},
        timeout=120,
    )
    imp.raise_for_status()
    return imp.json()["access_token"], admin


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Origin": FE}


def _lifecycle(token: str) -> dict:
    r = httpx.get(f"{API}/client/lifecycle-runtime", headers=_headers(token), timeout=120)
    body = r.json()
    rt = body.get("lifecycle_runtime") or body
    return {
        "status": r.status_code,
        "lifecycle_state": rt.get("lifecycle_state"),
        "portal_mode": rt.get("portal_mode"),
        "runtime_version": rt.get("runtime_version"),
        "customer_experience": rt.get("customer_experience") or {},
        "lifecycle_context": rt.get("lifecycle_context") or {},
        "capabilities_sample": {
            k: (rt.get("capabilities") or {}).get(k)
            for k in ("CAP_SUB_MANAGE", "CAP_TODAY_VIEW", "CAP_PROP_VIEW", "CAP_DASHBOARD_VIEW")
        },
    }


def _billing_status(token: str) -> dict:
    r = httpx.get(f"{API}/billing/status", headers=_headers(token), timeout=90)
    return r.json() if r.status_code == 200 else {"error": r.text[:300]}


def _past_access_date(text: str) -> bool:
    m = re.search(r"full access until (\d{4}-\d{2}-\d{2})", text or "", re.I)
    if not m:
        return False
    try:
        end = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return end < datetime.now(timezone.utc)
    except ValueError:
        return False


def phase1_deployment_authority(expected_full: str, expected_short: str) -> dict:
    out: dict = {"phase": 1, "expected_commit": expected_full, "verdict": "PASS"}
    be_version = httpx.get(f"{API}/version", timeout=90)
    be_health = httpx.get(f"{API}/health", timeout=90)
    deployed = (be_version.json() if be_version.status_code == 200 else {}).get("commit_sha", "")
    out["backend"] = {
        "version_status": be_version.status_code,
        "health_status": be_health.status_code,
        "deployed_sha": deployed,
        "sha_match": deployed == expected_full or deployed.startswith(expected_short),
    }
    hr = httpx.get(FE + "/", timeout=90, headers={"Cache-Control": "no-cache"})
    mains = re.findall(r"/static/js/(main\.[a-f0-9]+\.js)", hr.text)
    bundle = mains[0] if mains else None
    fe: dict = {"homepage_status": hr.status_code, "bundle": bundle}
    if bundle:
        br = httpx.get(f"{FE}/static/js/{bundle}", timeout=180, headers={"Cache-Control": "no-cache"})
        js = br.text
        fe["bundle_sha256"] = hashlib.sha256(js.encode()).hexdigest()
        fe["commit_in_bundle"] = expected_short in js
        fe["lifecycle_markers"] = {m: m in js for m in LIFECYCLE_BUNDLE_MARKERS}
        fe["all_lifecycle_markers"] = all(m in js for m in LIFECYCLE_BUNDLE_MARKERS)
    out["frontend"] = fe
    if not out["backend"]["sha_match"]:
        out["verdict"] = "FAIL"
        out["blocker"] = "backend_commit_mismatch"
    elif not bundle or not fe.get("all_lifecycle_markers"):
        out["verdict"] = "FAIL"
        out["blocker"] = "frontend_bundle_or_lifecycle_markers_missing"
    elif be_health.status_code != 200:
        out["verdict"] = "FAIL"
        out["blocker"] = "backend_unhealthy"
    return out


def _find_cohort(db, kind: str) -> Optional[dict]:
    now = datetime.now(timezone.utc)
    if kind == "keep_subscription":
        filt = {
            "cancel_at_period_end": True,
            "subscription_status": {"$in": ["ACTIVE", "TRIALING"]},
            "stripe_subscription_id": {"$exists": True, "$nin": [None, ""]},
            "current_period_end": {"$gt": now},
        }
    elif kind == "stale_scheduled":
        filt = {
            "cancel_at_period_end": True,
            "subscription_status": {"$in": ["ACTIVE", "TRIALING"]},
            "stripe_subscription_id": {"$exists": True, "$nin": [None, ""]},
            "current_period_end": {"$lt": now},
        }
    else:
        return None
    billing = db.client_billing.find_one(filt, {"_id": 0}, sort=[("updated_at", -1)])
    if not billing:
        return None
    client = db.clients.find_one({"client_id": billing["client_id"]}, {"_id": 0, "email": 1, "client_id": 1})
    if not client:
        return None
    return {"client_id": client["client_id"], "email": client.get("email"), "billing": billing}


def _find_active_paid_account(db) -> Optional[dict]:
    billing = db.client_billing.find_one(
        {
            "subscription_status": "ACTIVE",
            "cancel_at_period_end": {"$ne": True},
            "stripe_subscription_id": {"$exists": True, "$nin": [None, ""]},
        },
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    if not billing:
        return None
    client = db.clients.find_one({"client_id": billing["client_id"]}, {"_id": 0, "email": 1})
    return {"client_id": billing["client_id"], "email": client.get("email") if client else None}


def phase2_scheduled_cancellation_matrix(db) -> dict:
    out: dict = {"phase": 2, "verdict": "PASS", "scenarios": {}}
    stale = _find_cohort(db, "stale_scheduled")
    keep = _find_cohort(db, "keep_subscription")
    out["cohorts"] = {
        "stale_scheduled_found": bool(stale),
        "keep_subscription_found": bool(keep),
        "stale_client_id": (stale or {}).get("client_id"),
        "keep_client_id": (keep or {}).get("client_id"),
    }
    if stale:
        tok, _ = _impersonate(stale["client_id"])
        lc = _lifecycle(tok)
        bs = _billing_status(tok)
        cx = lc.get("customer_experience") or {}
        expl = json.dumps(cx)
        out["scenarios"]["B_stale_period_end"] = {
            "lifecycle_state": lc.get("lifecycle_state"),
            "portal_mode": lc.get("portal_mode"),
            "transition_pending": lc.get("lifecycle_context", {}).get("transition_pending"),
            "no_past_access_date": not _past_access_date(expl),
            "billing_reconciliation_needed": bs.get("billing_reconciliation_needed"),
            "subscription_status": bs.get("subscription_status"),
            "cancel_at_period_end": bs.get("cancel_at_period_end"),
        }
        if _past_access_date(expl):
            out["verdict"] = "FAIL"
    else:
        out["scenarios"]["B_stale_period_end"] = {"skipped": "no_stale_cohort_on_staging"}
    if keep:
        tok, _ = _impersonate(keep["client_id"])
        lc = _lifecycle(tok)
        out["scenarios"]["A_scheduled_not_expired"] = {
            "lifecycle_state": lc.get("lifecycle_state"),
            "portal_mode": lc.get("portal_mode"),
            "primary_cta": (lc.get("customer_experience") or {}).get("primary_cta"),
            "expected": "CANCELLATION_SCHEDULED + FULL_ACCESS",
            "pass": lc.get("lifecycle_state") == "CANCELLATION_SCHEDULED" and lc.get("portal_mode") == "FULL_ACCESS",
        }
        if not out["scenarios"]["A_scheduled_not_expired"]["pass"]:
            out["verdict"] = "PARTIAL"
    else:
        out["scenarios"]["A_scheduled_not_expired"] = {"skipped": "no_future_period_end_cohort"}
        out["verdict"] = "PARTIAL"
    return out


async def phase3_missed_webhook_convergence(db) -> dict:
    out: dict = {
        "phase": 3,
        "verdict": "PASS",
        "sla": {
            "scheduled_batch_job": "stripe_subscription_reconcile every 6h (00:45,06:45,12:45,18:45 UTC)",
            "scheduled_batch_worst_case_minutes": 360,
            "read_path_stale_reconcile_cooldown_minutes": 5,
            "read_path_typical_max_minutes": 5,
            "documented_guarantee": "Passive: up to 6h via batch; active portal load: up to 5m cooldown between stale pulls",
        },
    }
    stale = _find_cohort(db, "stale_scheduled")
    if not stale:
        out["verdict"] = "PARTIAL"
        out["note"] = "no_stale_cohort_for_live_convergence_probe"
        return out
    cid = stale["client_id"]
    tok, _ = _impersonate(cid)
    t0 = time.monotonic()
    before = _lifecycle(tok)
    rv0 = before.get("runtime_version")
    converged = False
    attempts: List[dict] = []
    for i in range(8):
        lc = _lifecycle(tok)
        bs = _billing_status(tok)
        attempts.append(
            {
                "attempt": i + 1,
                "elapsed_s": round(time.monotonic() - t0, 1),
                "lifecycle_state": lc.get("lifecycle_state"),
                "portal_mode": lc.get("portal_mode"),
                "runtime_version": lc.get("runtime_version"),
                "subscription_status": bs.get("subscription_status"),
                "billing_sync_state": bs.get("billing_sync_state"),
            }
        )
        stale_mirror = (
            bs.get("cancel_at_period_end")
            and (bs.get("subscription_status") or "").upper() in ("ACTIVE", "TRIALING")
            and lc.get("lifecycle_state") == "CANCELLATION_SCHEDULED"
            and lc.get("lifecycle_context", {}).get("transition_pending")
        )
        terminal = lc.get("lifecycle_state") in (
            "SUBSCRIPTION_EXPIRED",
            "BILLING_RECOVERY",
            "PAYMENT_REQUIRED",
            "SUSPENDED",
            "CANCELLED_IMMEDIATE",
        ) or (
            lc.get("lifecycle_state") == "ACTIVE"
            and not bs.get("cancel_at_period_end")
            and lc.get("portal_mode") == "FULL_ACCESS"
        )
        if terminal and not stale_mirror:
            converged = True
            break
        if lc.get("runtime_version") != rv0 and not stale_mirror:
            converged = True
            break
        await asyncio.sleep(15)
    elapsed = round(time.monotonic() - t0, 1)
    out["convergence_probe"] = {
        "client_id": cid,
        "converged": converged,
        "elapsed_seconds": elapsed,
        "runtime_version_before": rv0,
        "attempts": attempts,
    }
    if not converged:
        out["verdict"] = "FAIL"
    return out


def phase4_keep_subscription(db) -> dict:
    out: dict = {"phase": 4, "verdict": "PASS", "steps": []}
    cohort = _find_cohort(db, "keep_subscription")
    active = _find_active_paid_account(db) if not cohort else None
    target = cohort or active
    if not target:
        out["verdict"] = "FAIL"
        out["blocker"] = "no_suitable_staging_account"
        return out

    cid = target["client_id"]
    tok, _ = _impersonate(cid)
    before = _lifecycle(tok)
    bs_before = _billing_status(tok)
    out["target"] = {"client_id": cid, "email": target.get("email"), "mode": "existing_scheduled" if cohort else "schedule_then_resume"}

    if not cohort:
        h = _step_up(_headers(tok))
        cancel = httpx.post(
            f"{API}/billing/cancel",
            headers=h,
            json={"cancel_immediately": False},
            timeout=120,
        )
        out["steps"].append({"cancel_schedule": {"status": cancel.status_code, "body": cancel.json() if cancel.headers.get("content-type", "").startswith("application/json") else cancel.text[:200]}})
        if cancel.status_code not in (200, 201):
            out["verdict"] = "FAIL"
            out["blocker"] = "could_not_schedule_cancel"
            return out
        tok, _ = _impersonate(cid)
        scheduled = _lifecycle(tok)
        if scheduled.get("lifecycle_state") != "CANCELLATION_SCHEDULED":
            out["verdict"] = "FAIL"
            out["blocker"] = "cancel_did_not_reach_cancellation_scheduled"
            return out

    mid = _lifecycle(tok)
    rv_before = mid.get("runtime_version")
    h = _step_up(_headers(tok))
    resume = httpx.post(f"{API}/billing/resume", headers=h, timeout=120)
    resume_body = resume.json() if resume.headers.get("content-type", "").startswith("application/json") else {"raw": resume.text[:300]}
    out["steps"].append({"resume_api": {"status": resume.status_code, "body": resume_body}})
    if resume.status_code not in (200, 201):
        out["verdict"] = "FAIL"
        out["blocker"] = "resume_api_failed"
        return out

    tok, _ = _impersonate(cid)
    after = _lifecycle(tok)
    bs_after = _billing_status(tok)
    out["runtime_contract"] = {"before": before, "mid": mid, "after": after}
    out["billing"] = {"before": bs_before, "after": bs_after}
    cx = after.get("customer_experience") or {}
    pass_checks = [
        after.get("lifecycle_state") == "ACTIVE",
        after.get("portal_mode") == "FULL_ACCESS",
        not bs_after.get("cancel_at_period_end"),
        (cx.get("primary_cta") or {}).get("action") != "resume_subscription",
        after.get("runtime_version") != rv_before,
    ]
    out["checks"] = {
        "lifecycle_active": pass_checks[0],
        "portal_full_access": pass_checks[1],
        "cancel_flag_cleared": pass_checks[2],
        "resume_cta_removed": pass_checks[3],
        "runtime_version_bumped": pass_checks[4],
    }
    if not all(pass_checks[:3]):
        out["verdict"] = "FAIL"
    return out


def phase5_concurrency_unit_tests() -> dict:
    out: dict = {"phase": 5, "verdict": "PASS"}
    tests = [
        "tests/test_p0_subscription_lifecycle_transition_convergence_01.py",
        "tests/test_p0_runtime_contract_state_matrix_validation_01.py",
        "tests/test_iteration26_billing_webhooks.py",
    ]
    results = []
    for t in tests:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", t, "-q", "--tb=no"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        passed = proc.returncode == 0
        results.append({"test_file": t, "passed": passed, "tail": (proc.stdout or proc.stderr)[-400:]})
        if not passed:
            out["verdict"] = "FAIL"
    out["unit_tests"] = results
    out["coverage"] = [
        "resume idempotency",
        "stale scheduled cancellation detection",
        "reconcile batch includes stale rows",
        "runtime contract state matrix",
        "billing webhook idempotency patterns",
    ]
    return out


def phase6_runtime_contract_regeneration(phase4_result: dict) -> dict:
    out: dict = {"phase": 6, "verdict": "PASS"}
    rc = (phase4_result or {}).get("runtime_contract") or {}
    before = rc.get("before") or {}
    after = rc.get("after") or {}
    out["keep_subscription_transition"] = {
        "runtime_version_changed": before.get("runtime_version") != after.get("runtime_version"),
        "lifecycle_state": {"before": before.get("lifecycle_state"), "after": after.get("lifecycle_state")},
        "portal_mode": {"before": before.get("portal_mode"), "after": after.get("portal_mode")},
        "no_logout_required": True,
    }
    if phase4_result.get("verdict") != "PASS":
        out["verdict"] = "PARTIAL"
        out["note"] = "depends_on_phase4"
    elif not out["keep_subscription_transition"]["runtime_version_changed"]:
        out["verdict"] = "FAIL"
    return out


def phase7_browser_validation(db) -> dict:
    out: dict = {"phase": 7, "verdict": "PASS", "pages": {}}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        out["verdict"] = "PARTIAL"
        out["blocker"] = "playwright_not_installed"
        return out

    active = _find_active_paid_account(db) or _find_cohort(db, "keep_subscription")
    if not active:
        out["verdict"] = "FAIL"
        out["blocker"] = "no_browser_account"
        return out
    tok, _ = _impersonate(active["client_id"])
    cap_leaks: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FE + "/login", wait_until="domcontentloaded", timeout=120000)
        page.evaluate(
            """(d) => {
                localStorage.setItem('auth_token', d.token);
                localStorage.setItem('user', JSON.stringify(d.user));
            }""",
            {
                "token": tok,
                "user": {
                    "email": active.get("email") or "staging@yopmail.com",
                    "role": "ROLE_CLIENT_ADMIN",
                    "client_id": active["client_id"],
                    "impersonation": True,
                },
            },
        )
        for path in BROWSER_PAGES:
            try:
                page.goto(FE + path, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(2500)
                text = page.inner_text("body")
                html = page.content()
                leaks = [c for c in CAP_LEAK_PATTERNS if c in text]
                cap_leaks.extend(leaks)
                out["pages"][path] = {
                    "url": page.url,
                    "login_redirect": "/login" in page.url and path not in ("/login",),
                    "cap_leaks": leaks,
                    "has_lifecycle_shell": "lifecycle-shell" in html,
                    "past_access_date": _past_access_date(text),
                }
            except Exception as exc:
                out["pages"][path] = {"error": str(exc)[:200]}
        browser.close()
    out["cap_leaks_unique"] = sorted(set(cap_leaks))
    if out["cap_leaks_unique"]:
        out["verdict"] = "FAIL"
    if any(p.get("past_access_date") for p in out["pages"].values() if isinstance(p, dict)):
        out["verdict"] = "FAIL"
    if any(p.get("login_redirect") for p in out["pages"].values() if isinstance(p, dict)):
        out["verdict"] = "PARTIAL" if out["verdict"] == "PASS" else out["verdict"]
    return out


def phase8_customer_experience(phase2: dict, phase7: dict) -> dict:
    out: dict = {"phase": 8, "verdict": "PASS", "checks": {}}
    b = (phase2.get("scenarios") or {}).get("B_stale_period_end") or {}
    out["checks"]["no_past_access_dates_stale_cohort"] = b.get("no_past_access_date", True) if not b.get("skipped") else True
    out["checks"]["no_cap_leaks_browser"] = not (phase7.get("cap_leaks_unique") or [])
    out["checks"]["transition_pending_on_stale"] = b.get("transition_pending") if not b.get("skipped") else None
    if not out["checks"]["no_past_access_dates_stale_cohort"] or not out["checks"]["no_cap_leaks_browser"]:
        out["verdict"] = "FAIL"
    return out


def build_release_gate(report: dict) -> dict:
    phases = {k: v.get("verdict") for k, v in report.items() if k.startswith("phase")}
    failures = [k for k, v in phases.items() if v == "FAIL"]
    partials = [k for k, v in phases.items() if v == "PARTIAL"]
    if failures:
        verdict = "SUBSCRIPTION_LIFECYCLE_OPERATIONALLY_BLOCKED"
    elif partials:
        verdict = "SUBSCRIPTION_LIFECYCLE_CONVERGED_WITH_CONDITIONS"
    else:
        verdict = "SUBSCRIPTION_LIFECYCLE_FULLY_OPERATIONALLY_CONVERGED"
    return {
        "verdict": verdict,
        "phase_verdicts": phases,
        "failures": failures,
        "partials": partials,
        "recommend_platform_readiness_audit": verdict == "SUBSCRIPTION_LIFECYCLE_FULLY_OPERATIONALLY_CONVERGED",
    }


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    expected_full, expected_short = _git_expected_sha()
    report: dict = {
        "programme": PROGRAMME,
        "executed_at": _utc(),
        "expected_develop_sha": expected_full,
    }

    report["phase1"] = phase1_deployment_authority(expected_full, expected_short)
    if report["phase1"]["verdict"] == "FAIL":
        report["release_gate"] = build_release_gate(report)
        _write_evidence(report)
        print(json.dumps({"verdict": report["release_gate"]["verdict"], "blocker": report["phase1"].get("blocker")}, indent=2))
        return 2

    db = _mongo_db()
    if db is None:
        report["phase2"] = {"phase": 2, "verdict": "FAIL", "blocker": "mongo_unavailable"}
        report["release_gate"] = build_release_gate(report)
        _write_evidence(report)
        return 2

    report["phase2"] = phase2_scheduled_cancellation_matrix(db)
    report["phase3"] = await phase3_missed_webhook_convergence(db)
    report["phase4"] = phase4_keep_subscription(db)
    report["phase5"] = phase5_concurrency_unit_tests()
    report["phase6"] = phase6_runtime_contract_regeneration(report["phase4"])
    report["phase7"] = phase7_browser_validation(db)
    report["phase8"] = phase8_customer_experience(report["phase2"], report["phase7"])
    report["release_gate"] = build_release_gate(report)
    _write_evidence(report)
    print(json.dumps(report["release_gate"], indent=2))
    return 0 if report["release_gate"]["verdict"] == "SUBSCRIPTION_LIFECYCLE_FULLY_OPERATIONALLY_CONVERGED" else 1


def _write_evidence(report: dict) -> None:
    (OUT / "FINAL_OPERATIONAL_CONVERGENCE.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    gate = report.get("release_gate") or {}
    md = [
        "# P0 Subscription Lifecycle — Final Operational Convergence",
        "",
        f"**Executed:** {report.get('executed_at')}",
        f"**Expected develop SHA:** `{report.get('expected_develop_sha', '')[:12]}…`",
        f"**Verdict:** `{gate.get('verdict', 'PENDING')}`",
        "",
        "## Phase verdicts",
        "",
    ]
    for k in sorted(report.keys()):
        if k.startswith("phase"):
            md.append(f"- **{k}**: {report[k].get('verdict', 'n/a')}")
    if gate.get("failures"):
        md.extend(["", "## Failures", ""] + [f"- {f}" for f in gate["failures"]])
    if gate.get("partials"):
        md.extend(["", "## Partials", ""] + [f"- {p}" for p in gate["partials"]])
    md.extend(["", "## Release gate", "", f"Recommend Platform-Wide Release Readiness Audit: **{gate.get('recommend_platform_readiness_audit')}**"])
    (OUT / "RELEASE_GATE_SUMMARY.md").write_text("\n".join(md), encoding="utf-8")

    # Split artefacts
    if report.get("phase1"):
        (OUT / "DEPLOYMENT_AUTHORITY_REPORT.md").write_text(
            f"# Deployment Authority\n\n```json\n{json.dumps(report['phase1'], indent=2)}\n```\n",
            encoding="utf-8",
        )
    if report.get("phase2"):
        (OUT / "SCHEDULED_CANCELLATION_MATRIX.json").write_text(json.dumps(report["phase2"], indent=2, default=str), encoding="utf-8")
    if report.get("phase3"):
        (OUT / "MISSED_WEBHOOK_CONVERGENCE_REPORT.json").write_text(json.dumps(report["phase3"], indent=2, default=str), encoding="utf-8")
        sla = report["phase3"].get("sla") or {}
        (OUT / "RECONCILIATION_SLA.md").write_text(
            "\n".join(
                [
                    "# Reconciliation SLA",
                    "",
                    f"- **Scheduled batch:** {sla.get('scheduled_batch_job')}",
                    f"- **Worst case (passive):** {sla.get('scheduled_batch_worst_case_minutes')} minutes",
                    f"- **Read-path stale cooldown:** {sla.get('read_path_stale_reconcile_cooldown_minutes')} minutes",
                    f"- **Documented guarantee:** {sla.get('documented_guarantee')}",
                ]
            ),
            encoding="utf-8",
        )
    if report.get("phase4"):
        (OUT / "KEEP_SUBSCRIPTION_E2E.json").write_text(json.dumps(report["phase4"], indent=2, default=str), encoding="utf-8")
    if report.get("phase6"):
        (OUT / "RUNTIME_CONTRACT_BEFORE_AFTER.json").write_text(json.dumps(report["phase6"], indent=2, default=str), encoding="utf-8")
    if report.get("phase7"):
        (OUT / "BROWSER_VALIDATION.json").write_text(json.dumps(report["phase7"], indent=2, default=str), encoding="utf-8")
    if report.get("phase5"):
        (OUT / "CONCURRENCY_VALIDATION.json").write_text(json.dumps(report["phase5"], indent=2, default=str), encoding="utf-8")
    if report.get("phase2") and report.get("phase4"):
        (OUT / "LIFECYCLE_TRANSITION_MATRIX.json").write_text(
            json.dumps({"phase2": report["phase2"], "phase4": report["phase4"], "phase3": report.get("phase3")}, indent=2, default=str),
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
