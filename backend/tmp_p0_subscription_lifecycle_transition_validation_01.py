"""P0-SUBSCRIPTION-LIFECYCLE-TRANSITION-CONVERGENCE-01 staging validation harness."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api")
FE = os.getenv("STAGING_FE", "https://pleerity-enterprise-9jjg.vercel.app")
OUT = Path(__file__).resolve().parent / "docs/audit/p0_subscription_lifecycle_transition_convergence_01"
STAGING_CLIENT_EMAIL = os.getenv("STAGING_CANCEL_SCHEDULED_EMAIL", os.getenv("STAGING_ALLISON_EMAIL", ""))
STAGING_CLIENT_PASSWORD = os.getenv("STAGING_CANCEL_SCHEDULED_PASSWORD", os.getenv("STAGING_ALLISON_PASSWORD", ""))


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _login(email: str, password: str) -> dict:
    r = httpx.post(f"{API}/auth/login", json={"email": email, "password": password}, headers={"Origin": FE}, timeout=90)
    r.raise_for_status()
    return r.json()


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Origin": FE}


async def _mongo_allison(email_or_client_id: str | None):
    from pymongo import MongoClient

    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    if not uri or not email_or_client_id:
        return None, None
    db = MongoClient(uri, serverSelectionTimeoutMS=15000)[os.getenv("DB_NAME", "pleerity_staging")]
    if "@" in email_or_client_id:
        client = db.clients.find_one({"email": email_or_client_id}, {"_id": 0})
    else:
        client = db.clients.find_one({"client_id": email_or_client_id}, {"_id": 0})
    if not client:
        return None, None
    billing = db.client_billing.find_one({"client_id": client["client_id"]}, {"_id": 0})
    return client, billing


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"programme": "P0-SUBSCRIPTION-LIFECYCLE-TRANSITION-CONVERGENCE-01", "validated_at": _utc()}

    # Deployment probe: resume route exists
    probe = httpx.post(f"{API}/billing/resume", headers={"Origin": FE}, timeout=30)
    report["resume_route_probe"] = {"status": probe.status_code, "detail": probe.text[:200]}
    report["resume_route_deployed"] = probe.status_code in (401, 403, 422)  # not 404

    token = None
    if STAGING_CLIENT_PASSWORD and STAGING_CLIENT_EMAIL:
        auth = _login(STAGING_CLIENT_EMAIL, STAGING_CLIENT_PASSWORD)
        token = auth["access_token"]
    else:
        # Governed impersonation path — no account-specific production logic
        admin_email = os.getenv("STAGING_ADMIN_EMAIL", "prosper@yopmail.com")
        admin_password = os.getenv("STAGING_ADMIN_PASSWORD", "Pastor@36$")
        client_id = os.getenv("STAGING_CANCEL_SCHEDULED_CLIENT_ID", "")
        if not client_id and (os.getenv("MONGO_URI") or os.getenv("MONGO_URL")):
            from pymongo import MongoClient

            db = MongoClient(os.getenv("MONGO_URI") or os.getenv("MONGO_URL"), serverSelectionTimeoutMS=15000)[
                os.getenv("DB_NAME", "pleerity_staging")
            ]
            billing = db.client_billing.find_one(
                {
                    "cancel_at_period_end": True,
                    "subscription_status": {"$in": ["ACTIVE", "TRIALING"]},
                    "stripe_subscription_id": {"$exists": True, "$nin": [None, ""]},
                },
                {"_id": 0, "client_id": 1},
            )
            client_id = (billing or {}).get("client_id") or ""
        if not client_id:
            report["verdict"] = "SUBSCRIPTION_LIFECYCLE_TRANSITION_BLOCKED"
            report["blocker"] = "no_staging_cancel_scheduled_account_and_no_password"
            (OUT / "VALIDATION_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 2
        ar = httpx.post(
            f"{API}/auth/admin/login",
            json={"email": admin_email, "password": admin_password},
            headers={"Origin": FE},
            timeout=180,
        )
        ar.raise_for_status()
        admin_token = ar.json()["access_token"]
        ah = {"Authorization": f"Bearer {admin_token}", "Origin": FE}
        su = httpx.post(f"{API}/auth/step-up/verify", headers=ah, json={"password": admin_password}, timeout=90)
        su.raise_for_status()
        if su.json().get("step_up_token"):
            ah["X-Step-Up-Token"] = su.json()["step_up_token"]
        conf = httpx.post(
            f"{API}/admin/governance/confirmation-token",
            headers=ah,
            json={"action_id": "start_impersonation", "reason": "p0_lifecycle_transition_validation", "resource_key": client_id},
            timeout=60,
        )
        conf.raise_for_status()
        if conf.json().get("token"):
            ah["X-Admin-Confirmation-Token"] = conf.json()["token"]
        imp = httpx.post(
            f"{API}/admin/clients/{client_id}/impersonation/start",
            headers=ah,
            params={"ttl_minutes": 90},
            json={"reason": "p0_lifecycle_transition_validation"},
            timeout=120,
        )
        imp.raise_for_status()
        token = imp.json()["access_token"]
        report["auth_mode"] = "admin_impersonation"
        report["impersonated_client_id"] = client_id

    auth = {"access_token": token}
    token = auth["access_token"]
    lr = httpx.get(f"{API}/client/lifecycle-runtime", headers=_headers(token), timeout=90).json()
    rt = lr.get("lifecycle_runtime") or lr
    bs = httpx.get(f"{API}/billing/status", headers=_headers(token), timeout=90).json()
    report["before"] = {
        "lifecycle_state": rt.get("lifecycle_state"),
        "portal_mode": rt.get("portal_mode"),
        "runtime_version": rt.get("runtime_version"),
        "customer_experience": rt.get("customer_experience"),
        "billing": {
            "subscription_status": bs.get("subscription_status"),
            "cancel_at_period_end": bs.get("cancel_at_period_end"),
            "current_period_end": bs.get("current_period_end"),
        },
    }

    client, billing = await _mongo_allison(STAGING_CLIENT_EMAIL or report.get("impersonated_client_id"))
    if billing:
        from services.billing_scheduled_cancellation_authority import (
            is_stale_scheduled_cancellation_mirror,
            reconcile_stale_scheduled_cancellation_if_needed,
        )

        stale = is_stale_scheduled_cancellation_mirror(billing)
        report["stale_scheduled_mirror_before"] = stale
        if stale:
            billing_after, reconciled = await reconcile_stale_scheduled_cancellation_if_needed(
                client["client_id"],
                billing,
                event_source="p0_lifecycle_transition_validation",
            )
            report["stale_reconcile_attempted"] = True
            report["stale_reconcile_success"] = reconciled
            report["billing_after_reconcile"] = {
                k: billing_after.get(k)
                for k in (
                    "subscription_status",
                    "cancel_at_period_end",
                    "current_period_end",
                    "billing_lifecycle_state",
                )
            } if billing_after else None

    # Refresh API after reconcile
    lr2 = httpx.get(f"{API}/client/lifecycle-runtime", headers=_headers(token), timeout=90).json()
    rt2 = lr2.get("lifecycle_runtime") or lr2
    report["after"] = {
        "lifecycle_state": rt2.get("lifecycle_state"),
        "portal_mode": rt2.get("portal_mode"),
        "runtime_version": rt2.get("runtime_version"),
        "customer_experience": rt2.get("customer_experience"),
    }

    cx = report["after"].get("customer_experience") or {}
    explanation = (cx.get("explanation") or "") if isinstance(cx, dict) else ""
    stale_date_ok = "2026-06-16" not in explanation
    converged = rt2.get("lifecycle_state") in ("ACTIVE", "CANCELLED_IMMEDIATE", "SUBSCRIPTION_EXPIRED", "BILLING_RECOVERY")
    not_stale_scheduled = rt2.get("lifecycle_state") != "CANCELLATION_SCHEDULED" or not report.get("stale_scheduled_mirror_before")

    if report.get("resume_route_deployed") and stale_date_ok and (not_stale_scheduled or converged):
        report["verdict"] = "SUBSCRIPTION_LIFECYCLE_TRANSITION_CONVERGED"
    elif report.get("resume_route_deployed") and stale_date_ok:
        report["verdict"] = "SUBSCRIPTION_LIFECYCLE_TRANSITION_CONVERGED_WITH_CONDITIONS"
        report["conditions"] = ["keep_subscription_browser_e2e_not_run", "may_require_fresh_runtime_fetch_after_deploy"]
    else:
        report["verdict"] = "SUBSCRIPTION_LIFECYCLE_TRANSITION_BLOCKED"
        report["blocker"] = "deploy_or_stale_mirror_not_converged"

    (OUT / "VALIDATION_REPORT.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "after": report["after"]}, indent=2, default=str))
    return 0 if report["verdict"].startswith("SUBSCRIPTION_LIFECYCLE_TRANSITION_CONVERGED") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
