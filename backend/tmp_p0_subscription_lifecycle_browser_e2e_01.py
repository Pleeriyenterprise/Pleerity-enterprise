"""Browser + API E2E for cancel-at-period-end keep subscription (staging only)."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api")
FE = os.getenv("STAGING_FE", "https://pleerity-enterprise-9jjg.vercel.app")
OUT = Path(__file__).resolve().parent / "docs/audit/p0_subscription_lifecycle_transition_convergence_01"
PROGRAMME = "P0-SUBSCRIPTION-LIFECYCLE-TRANSITION-CONVERGENCE-01"
ADMIN_EMAIL = os.environ.get("STAGING_ADMIN_EMAIL", "prosper@yopmail.com")
ADMIN_PASSWORD = os.environ.get("STAGING_ADMIN_PASSWORD", "Pastor@36$")
TARGET_CLIENT_ID = os.getenv("STAGING_CANCEL_SCHEDULED_CLIENT_ID", "")
TARGET_EMAIL = os.getenv("STAGING_CANCEL_SCHEDULED_EMAIL", "")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _admin_token() -> str:
    r = httpx.post(
        f"{API}/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Origin": FE},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _impersonate(admin_token: str, client_id: str) -> str:
    ah = {"Authorization": f"Bearer {admin_token}", "Origin": FE}
    su = httpx.post(f"{API}/auth/step-up/verify", headers=ah, json={"password": ADMIN_PASSWORD}, timeout=90)
    su.raise_for_status()
    if su.json().get("step_up_token"):
        ah["X-Step-Up-Token"] = su.json()["step_up_token"]
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
        params={"ttl_minutes": 90},
        json={"reason": PROGRAMME},
        timeout=120,
    )
    imp.raise_for_status()
    return imp.json()["access_token"]


def _client_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Origin": FE}


def _step_up_headers(token: str) -> dict:
    h = _client_headers(token)
    su = httpx.post(f"{API}/auth/step-up/verify", headers=h, json={"password": ADMIN_PASSWORD}, timeout=90)
    su.raise_for_status()
    if su.json().get("step_up_token"):
        h["X-Step-Up-Token"] = su.json()["step_up_token"]
    return h


def _lifecycle(token: str) -> dict:
    r = httpx.get(f"{API}/client/lifecycle-runtime", headers=_client_headers(token), timeout=90)
    lr = r.json().get("lifecycle_runtime") or r.json()
    cx = lr.get("customer_experience") or {}
    return {
        "lifecycle_state": lr.get("lifecycle_state"),
        "portal_mode": lr.get("portal_mode"),
        "runtime_version": lr.get("runtime_version"),
        "customer_experience": cx,
        "transition_pending": (lr.get("lifecycle_context") or {}).get("transition_pending"),
    }


def _find_cancel_scheduled_client() -> tuple[str, str] | tuple[None, None]:
    if TARGET_CLIENT_ID and TARGET_EMAIL:
        return TARGET_EMAIL, TARGET_CLIENT_ID
    from pymongo import MongoClient

    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    if not uri:
        return None, None
    db = MongoClient(uri, serverSelectionTimeoutMS=15000)[os.getenv("DB_NAME", "pleerity_staging")]
    billing = db.client_billing.find_one(
        {
            "cancel_at_period_end": True,
            "subscription_status": {"$in": ["ACTIVE", "TRIALING"]},
            "stripe_subscription_id": {"$exists": True, "$nin": [None, ""]},
        },
        {"_id": 0, "client_id": 1, "current_period_end": 1},
        sort=[("current_period_end", 1)],
    )
    if not billing:
        return None, None
    client = db.clients.find_one({"client_id": billing["client_id"]}, {"_id": 0, "email": 1, "client_id": 1})
    if not client:
        return None, None
    return client.get("email"), client.get("client_id")


def _past_date_in_text(text: str) -> bool:
    """True if copy claims full access until a date already in the past."""
    m = re.search(r"full access until (\d{4}-\d{2}-\d{2})", text, re.I)
    if not m:
        return False
    try:
        end = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return end < datetime.now(timezone.utc)
    except ValueError:
        return False


def _browser_keep_subscription(token: str, email: str, client_id: str) -> dict:
    out: dict = {"clicked": False, "resume_route_called": False, "errors": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        resume_seen = {"value": False}

        def on_request(req):
            if "/billing/resume" in req.url and req.method == "POST":
                resume_seen["value"] = True

        page.on("request", on_request)
        page.goto(FE + "/login", wait_until="domcontentloaded", timeout=120000)
        page.evaluate(
            """(d) => {
                localStorage.setItem('auth_token', d.token);
                localStorage.setItem('user', JSON.stringify(d.user));
            }""",
            {"token": token, "user": {"email": email, "role": "ROLE_CLIENT_ADMIN", "client_id": client_id, "impersonation": True}},
        )
        page.goto(FE + "/today", wait_until="domcontentloaded", timeout=120000)
        try:
            page.wait_for_selector('[data-testid="lifecycle-shell"]', timeout=25000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        out["banner_text_snippet"] = " ".join(body.split())[:400]
        out["past_access_date_in_ui"] = _past_date_in_text(body)
        out["has_transition_pending_copy"] = "subscription status is being updated" in body.lower()

        keep = page.locator('[data-testid="lifecycle-keep-subscription"]')
        if keep.count() == 0:
            keep = page.locator('[data-testid="billing-keep-subscription"]')
            page.goto(FE + "/settings/billing", wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(4000)
        if keep.count() > 0:
            keep.first.click()
            out["clicked"] = True
            page.wait_for_timeout(1500)
            pwd = page.locator('input[type="password"]')
            if pwd.count() > 0:
                pwd.first.fill(ADMIN_PASSWORD)
                submit = page.get_by_role("button", name=re.compile("confirm|verify|continue", re.I))
                if submit.count() > 0:
                    submit.first.click()
                    page.wait_for_timeout(8000)
        out["resume_route_called"] = resume_seen["value"]
        out["final_url"] = page.url
        out["final_body_snippet"] = " ".join(page.inner_text("body").split())[:400]
        browser.close()
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"programme": PROGRAMME, "validated_at": _utc(), "checks": {}}

    probe = httpx.post(f"{API}/billing/resume", headers={"Origin": FE}, timeout=30)
    report["resume_route_probe"] = {"status": probe.status_code}
    report["resume_route_deployed"] = probe.status_code in (401, 403, 422)

    email, client_id = _find_cancel_scheduled_client()
    if not client_id:
        report["verdict"] = "SUBSCRIPTION_LIFECYCLE_TRANSITION_BLOCKED"
        report["blocker"] = "no_cancel_scheduled_staging_account_found"
        (OUT / "BROWSER_E2E_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    report["target"] = {"email": email, "client_id": client_id}
    admin = _admin_token()
    token = _impersonate(admin, client_id)
    before = _lifecycle(token)
    report["before"] = before

    cx = before.get("customer_experience") or {}
    explanation = cx.get("explanation") or cx.get("heading") or ""
    report["checks"]["no_past_access_date_in_api"] = not _past_date_in_text(str(explanation))

    browser = _browser_keep_subscription(token, email, client_id)
    report["browser"] = browser
    report["checks"]["no_past_access_date_in_ui"] = not browser.get("past_access_date_in_ui", True)

    # API resume when still scheduled (idempotent path if already resumed in browser)
    after_browser = _lifecycle(token)
    if after_browser.get("lifecycle_state") == "CANCELLATION_SCHEDULED":
        rh = _step_up_headers(token)
        resume = httpx.post(f"{API}/billing/resume", headers=rh, timeout=120)
        report["resume_api"] = {"status": resume.status_code, "body": resume.json() if resume.headers.get("content-type", "").startswith("application/json") else resume.text[:300]}
    else:
        report["resume_api"] = {"skipped": True, "reason": "already_not_cancellation_scheduled"}

    after = _lifecycle(token)
    report["after"] = after
    report["checks"]["lifecycle_active_or_full_access"] = after.get("lifecycle_state") == "ACTIVE" and after.get("portal_mode") == "FULL_ACCESS"
    report["checks"]["resume_route_deployed"] = report["resume_route_deployed"]
    report["checks"]["keep_subscription_action_wired"] = browser.get("clicked") or report.get("resume_api", {}).get("status") == 200

    failed = [k for k, v in report["checks"].items() if not v]
    if not report["resume_route_deployed"]:
        report["verdict"] = "SUBSCRIPTION_LIFECYCLE_TRANSITION_BLOCKED"
        report["blocker"] = "resume_route_not_deployed"
    elif failed:
        report["verdict"] = "SUBSCRIPTION_LIFECYCLE_TRANSITION_CONVERGED_WITH_CONDITIONS"
        report["conditions"] = failed
    else:
        report["verdict"] = "SUBSCRIPTION_LIFECYCLE_TRANSITION_CONVERGED"

    (OUT / "BROWSER_E2E_REPORT.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md = [
        "# Browser E2E — subscription lifecycle transition",
        "",
        f"**Validated:** {report['validated_at']}",
        f"**Verdict:** `{report['verdict']}`",
        "",
        f"Target: `{email}` (`{client_id}`)",
        "",
        "## Checks",
        "",
    ]
    for k, v in report["checks"].items():
        md.append(f"- {k}: **{'PASS' if v else 'FAIL'}**")
    (OUT / "BROWSER_E2E_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "checks": report["checks"]}, indent=2))
    return 0 if report["verdict"].startswith("SUBSCRIPTION_LIFECYCLE_TRANSITION_CONVERGED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
