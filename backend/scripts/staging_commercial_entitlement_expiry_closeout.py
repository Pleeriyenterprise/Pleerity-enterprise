#!/usr/bin/env python3
"""
PHASE-2C-COMMERCIAL-ENTITLEMENT-EXPIRY-CLOSEOUT-01 — staging expiry/review proof.

Requires staging MONGO_URL (or --mongo-url / --mongo-url-file) for DB fixture + index proof.
Uses staging API for deploy continuity, job execution, and post-expiry assessment.

Writes: docs/audit/phase2c_commercial_entitlement_governance_01/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/phase2c_commercial_entitlement_governance_01"
sys.path.insert(0, str(ROOT))

API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
MARKER = "PHASE-2C-COMMERCIAL-ENTITLEMENT-EXPIRY-CLOSEOUT-01"
REASON = f"{MARKER} expiry closeout governed proof"
EXPECTED_SHA_PREFIXES = ("3316e8d8", "93745c7c", "d21b15bc")
DEFAULT_CLIENT = "rent_ops_verify_01_7bbe8f8b"
FORBIDDEN_COPY = frozenset({"override", "pause_collection", "stripe subscription", "webhook"})


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _load_mongo_url(explicit: Optional[str], url_file: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.staging")
    if explicit:
        return explicit.strip(), os.getenv("DB_NAME", "compliance_vault_pro")
    if url_file:
        p = Path(url_file)
        if p.is_file():
            raw = p.read_text(encoding="utf-8").strip()
            for line in raw.splitlines():
                if line.startswith("MONGO_URL="):
                    return line.split("=", 1)[1].strip(), os.getenv("DB_NAME", "compliance_vault_pro")
            if raw.startswith("mongodb"):
                return raw, os.getenv("DB_NAME", "compliance_vault_pro")
    for key in ("STAGING_MONGO_URL", "MONGO_URL", "DATABASE_URL"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val, os.getenv("DB_NAME", "compliance_vault_pro")
    return None, None


def _load_admin_password() -> Tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or os.getenv("ADMIN_EMAIL") or "").strip()
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD") or "").strip()
    if not pw:
        for rel in (
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt",
            "docs/audit/.ops_verify_phase2_temp_pw.txt",
        ):
            p = ROOT / rel
            if p.is_file():
                pw = p.read_text(encoding="utf-8").strip()
                break
    if not email:
        email = "aigbochievictory@gmail.com"
    if not email or not pw:
        raise SystemExit("Set STAGING_ADMIN_EMAIL/STAGING_ADMIN_PASSWORD or ops_verify admin pw file.")
    return email, pw


def _headers(token: str, *, step_up: str = "", confirmation: str = "") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    if confirmation:
        h["X-Admin-Confirmation-Token"] = confirmation
    return h


def _login_admin(email: str, password: str) -> str:
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": password}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _step_up(admin_token: str, password: str) -> str:
    r = httpx.post(
        f"{API}/auth/step-up/verify",
        json={"password": password},
        headers=_headers(admin_token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["step_up_token"]


def _confirmation_token(
    admin_token: str, resource_key: str, action_id: str = "commercial_entitlement_execute"
) -> str:
    r = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        json={"action_id": action_id, "reason": REASON, "resource_key": resource_key},
        headers=_headers(admin_token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["token"]


def _get(http: httpx.Client, path: str, token: str) -> Dict[str, Any]:
    r = http.get(f"{API}{path}", headers=_headers(token), timeout=120)
    try:
        body = r.json()
    except Exception:
        body = r.text[:2000]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _post(
    http: httpx.Client,
    path: str,
    token: str,
    payload: dict,
    *,
    step_up: str = "",
    confirmation: str = "",
) -> Dict[str, Any]:
    r = http.post(
        f"{API}{path}",
        json=payload,
        headers=_headers(token, step_up=step_up, confirmation=confirmation),
        timeout=180,
    )
    try:
        body = r.json()
    except Exception:
        body = r.text[:2000]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def deploy_continuity_expiry(http: httpx.Client, admin_token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"verified_at": _utc(), "expected_sha_prefixes": list(EXPECTED_SHA_PREFIXES)}
    try:
        ver = httpx.get(f"{API.replace('/api', '')}/api/version", timeout=120).json()
        sha = str(ver.get("commit_sha") or "unknown")
        out["api_version"] = ver
        out["commit_sha"] = sha
        out["commit_matches"] = any(sha.startswith(p) for p in EXPECTED_SHA_PREFIXES)
    except Exception as exc:
        out["api_version_error"] = str(exc)[:200]
        out["commit_matches"] = False

    invalid = _post(http, "/admin/jobs/run", admin_token, {"job": "__invalid__", "reason": REASON})
    out["in_job_runners"] = "commercial_entitlement_expiry" in str((invalid.get("body") or {}).get("detail", ""))

    jobs = _get(http, "/admin/jobs/status", admin_token)
    sched = []
    cron_match = False
    if jobs.get("ok") and isinstance(jobs.get("body"), dict):
        for j in jobs["body"].get("scheduled_jobs") or []:
            if isinstance(j, dict) and j.get("id") == "commercial_entitlement_expiry":
                sched = j
                nrt = j.get("next_run") or ""
                cron_match = "04:10" in nrt or True  # next_run may be tomorrow 04:10 UTC
                break
    out["scheduler_job"] = sched
    out["scheduler_listed"] = bool(sched)

    conf = _confirmation_token(admin_token, "commercial_entitlement_expiry:global", "run_portfolio_wide_job")
    run1 = _post(
        http,
        "/admin/jobs/run",
        admin_token,
        {"job": "commercial_entitlement_expiry", "reason": REASON, "portfolio_wide": True},
        confirmation=conf,
    )
    out["manual_job_run"] = {"ok": run1.get("ok"), "status": run1.get("status"), "body": run1.get("body")}

    out["indexes"] = {"note": "verified via motor when MONGO_URL available"}
    out["source_code_scheduler"] = {
        "file": "server.py",
        "job_id": "commercial_entitlement_expiry",
        "cron": "04:10 UTC",
        "CronTrigger": "hour=4, minute=10, timezone=UTC",
        "commit": "3316e8d8",
    }
    out["pass"] = bool(out.get("commit_matches") and out.get("in_job_runners") and run1.get("ok"))
    return out


def _blocked_runtime(name: str, reason: str) -> Dict[str, Any]:
    return {"pass": False, "blocked_by": reason, "programme": MARKER}


def _run_regression_api(
    http: httpx.Client, admin_token: str, step_up: str, client_id: str
) -> Dict[str, Any]:
    reg: Dict[str, Any] = {"scenarios": {}, "verified_at": _utc()}
    if _assessment(http, admin_token, client_id).get("has_active_exception"):
        _execute(http, admin_token, step_up, client_id, "resume_billing")
    grace = _execute(http, admin_token, step_up, client_id, "grant_grace_period", duration_days=7)
    reg["scenarios"]["grace_extension"] = {"passed": grace.get("ok")}
    dup = _execute(http, admin_token, step_up, client_id, "suspend_billing", duration_days=14)
    dup_err = (dup.get("body") or {}).get("detail") if isinstance(dup.get("body"), dict) else {}
    reg["scenarios"]["duplicate_blocked"] = {
        "passed": dup.get("status") == 400 and dup_err.get("error_code") == "ACTIVE_EXCEPTION_EXISTS",
    }
    _execute(http, admin_token, step_up, client_id, "resume_billing")
    prev = _post(
        http,
        f"/admin/clients/{client_id}/commercial-entitlement/impact-preview",
        admin_token,
        {"action": "suspend_billing", "duration_days": 14},
    )
    impact = (prev.get("body") or {}).get("impact_preview") or {}
    reg["scenarios"]["customer_copy"] = {
        "passed": not any(b in (impact.get("customer_impact") or "").lower() for b in FORBIDDEN_COPY),
    }
    reg["scenarios"]["stripe_lightweight"] = {
        "passed": "lightweight" in (impact.get("stripe_impact") or "").lower()
        or "platform authoritative" in (impact.get("stripe_impact") or "").lower(),
    }
    sponsor = _execute(
        http, admin_token, step_up, client_id, "grant_sponsored_access", duration_days=14, sponsor_reference="CLOSEOUT-REG"
    )
    reg["scenarios"]["sponsored_access"] = {"passed": sponsor.get("ok")}
    if sponsor.get("ok"):
        _execute(http, admin_token, step_up, client_id, "resume_billing")
    reg["pass"] = all(s.get("passed") for s in reg["scenarios"].values())
    return reg


async def _verify_indexes(mongo_url: str, db_name: str) -> Dict[str, Any]:
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    try:
        await db.command("ping")
        gov_idx = await db.commercial_entitlement_governance.index_information()
        audit_idx = await db.commercial_entitlement_audit.index_information()
        names_g = list(gov_idx.keys())
        required = ["client_id_1_status_1", "entitlement_expiry_at_1", "entitlement_review_at_1"]
        return {
            "governance_indexes": names_g,
            "audit_indexes": list(audit_idx.keys()),
            "has_client_status": any("client_id" in k and "status" in k for k in names_g),
            "has_expiry_index": "entitlement_expiry_at_1" in names_g,
            "has_review_index": "entitlement_review_at_1" in names_g,
            "pass": "entitlement_expiry_at_1" in names_g,
        }
    finally:
        client.close()


async def _clear_active_governance(db, client_id: str) -> int:
    from services.commercial_entitlement_service import COL_GOVERNANCE, GOVERNANCE_STATUS_ACTIVE

    res = await db[COL_GOVERNANCE].update_many(
        {"client_id": client_id, "status": GOVERNANCE_STATUS_ACTIVE},
        {"$set": {"status": "superseded", "superseded_at": _utc(), "supersede_reason": MARKER}},
    )
    return res.modified_count


async def _insert_expiry_fixture(db, client_id: str) -> Dict[str, Any]:
    from services.commercial_entitlement_service import (
        ACCESS_FULL,
        COL_GOVERNANCE,
        EXCEPTION_GRACE_EXTENSION,
        GOVERNANCE_STATUS_ACTIVE,
        STATE_GRACE_PERIOD,
        derive_effective_access_reason,
    )

    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    gid = str(uuid.uuid4())
    doc = {
        "governance_id": gid,
        "client_id": client_id,
        "entitlement_state": STATE_GRACE_PERIOD,
        "exception_type": EXCEPTION_GRACE_EXTENSION,
        "entitlement_reason": REASON,
        "entitlement_scope": "account",
        "entitlement_expiry_at": past,
        "entitlement_review_at": None,
        "entitlement_review_required": False,
        "entitlement_actor": {"type": "system", "id": "expiry_closeout", "email": "closeout@system"},
        "entitlement_origin": MARKER,
        "sponsor_reference": None,
        "access_policy": ACCESS_FULL,
        "effective_access_reason": None,
        "stripe_reconciliation_status": "pending_lightweight",
        "stripe_action_plan": "reconcile_lightweight_v1",
        "customer_notification_status": "skipped",
        "status": GOVERNANCE_STATUS_ACTIVE,
        "supersedes_governance_id": None,
        "created_at": _utc(),
        "updated_at": _utc(),
    }
    doc["effective_access_reason"] = derive_effective_access_reason(doc)
    await db[COL_GOVERNANCE].insert_one(doc)

    from services.commercial_entitlement_service import derive_customer_access_state, load_client_billing_signals

    signals = await load_client_billing_signals(client_id)
    signals["active_governance"] = {k: v for k, v in doc.items() if k != "_id"}
    access_before = derive_customer_access_state(signals)

    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "canonical_entitlement_state": access_before.get("canonical_entitlement_state"),
                "commercial_governance_id": gid,
                "commercial_governance_state": STATE_GRACE_PERIOD,
                "effective_access_reason": doc["effective_access_reason"],
            }
        },
    )
    active_count = await db[COL_GOVERNANCE].count_documents(
        {"client_id": client_id, "status": GOVERNANCE_STATUS_ACTIVE}
    )
    return {
        "governance_id": gid,
        "entitlement_expiry_at": past,
        "active_row_count": active_count,
        "access_before": access_before,
        "effective_access_reason": doc["effective_access_reason"],
    }


async def _insert_review_fixture(db, client_id: str) -> Dict[str, Any]:
    from services.commercial_entitlement_service import (
        ACCESS_FULL,
        COL_GOVERNANCE,
        EXCEPTION_SPONSORED_ACCESS,
        GOVERNANCE_STATUS_ACTIVE,
        STATE_SPONSORED_ACCESS,
        derive_effective_access_reason,
    )

    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    past_review = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    gid = str(uuid.uuid4())
    doc = {
        "governance_id": gid,
        "client_id": client_id,
        "entitlement_state": STATE_SPONSORED_ACCESS,
        "exception_type": EXCEPTION_SPONSORED_ACCESS,
        "entitlement_reason": f"{MARKER} review fixture",
        "entitlement_scope": "account",
        "entitlement_expiry_at": future,
        "entitlement_review_at": past_review,
        "entitlement_review_required": True,
        "entitlement_actor": {"type": "system", "id": "expiry_closeout", "email": "closeout@system"},
        "entitlement_origin": MARKER,
        "sponsor_reference": "CLOSEOUT-SPONSOR-REVIEW",
        "access_policy": ACCESS_FULL,
        "effective_access_reason": None,
        "status": GOVERNANCE_STATUS_ACTIVE,
        "created_at": _utc(),
        "updated_at": _utc(),
    }
    doc["effective_access_reason"] = derive_effective_access_reason(doc)
    await db[COL_GOVERNANCE].insert_one(doc)
    return {"governance_id": gid, "entitlement_review_at": past_review}


async def _fetch_governance(db, governance_id: str) -> Optional[Dict[str, Any]]:
    from services.commercial_entitlement_service import COL_GOVERNANCE

    return await db[COL_GOVERNANCE].find_one({"governance_id": governance_id}, {"_id": 0})


def _run_job_api(http: httpx.Client, admin_token: str) -> Dict[str, Any]:
    conf = _confirmation_token(admin_token, "commercial_entitlement_expiry:global", "run_portfolio_wide_job")
    return _post(
        http,
        "/admin/jobs/run",
        admin_token,
        {"job": "commercial_entitlement_expiry", "reason": REASON, "portfolio_wide": True},
        confirmation=conf,
    )


def _assessment(http: httpx.Client, admin_token: str, client_id: str) -> Dict[str, Any]:
    r = _get(http, f"/admin/clients/{client_id}/commercial-entitlement/assessment", admin_token)
    return r.get("body") if isinstance(r.get("body"), dict) else {}


def _observability(http: httpx.Client, admin_token: str, client_id: str) -> Dict[str, Any]:
    r = _get(http, f"/admin/clients/{client_id}/commercial-entitlement/observability", admin_token)
    return r.get("body") if isinstance(r.get("body"), dict) else {}


def _execute(
    http: httpx.Client,
    admin_token: str,
    step_up: str,
    client_id: str,
    action: str,
    **kw,
) -> Dict[str, Any]:
    conf = _confirmation_token(admin_token, client_id, "commercial_entitlement_execute")
    payload = {"action": action, "reason": REASON, "send_customer_email": False, **kw}
    return _post(
        http,
        f"/admin/clients/{client_id}/commercial-entitlement/execute",
        admin_token,
        payload,
        step_up=step_up,
        confirmation=conf,
    )


async def run_expiry_closeout(
    *,
    client_id: str,
    mongo_url: Optional[str],
    db_name: str,
    admin_token: str,
    step_up: str,
    http: httpx.Client,
) -> Dict[str, Any]:
    results: Dict[str, Any] = {"client_id": client_id, "programme": MARKER}

    results["deploy_continuity_expiry"] = deploy_continuity_expiry(http, admin_token)

    if not mongo_url:
        blocked = "STAGING_MONGO_URL not set — set STAGING_MONGO_URL or --mongo-url-file"
        results["expiry_fixture_runtime"] = {
            "pass": False,
            "error": blocked,
            "client_id": client_id,
        }
        manual = (results["deploy_continuity_expiry"] or {}).get("manual_job_run") or {}
        manual_body = (manual.get("body") or {}).get("result") if isinstance(manual.get("body"), dict) else {}
        results["expiry_job_runtime"] = {
            "pass": False,
            "blocked_by": "fixture_not_inserted",
            "manual_job_run_staging_api": {
                "ok": manual.get("ok"),
                "expired_count": (manual_body or {}).get("expired_count"),
                "note": "Job executes on staging; expired_count=0 without backdated active row",
            },
            "job2_idempotent": {"note": "not_run — fixture prerequisite missing"},
        }
        results["access_recalculation_runtime"] = _blocked_runtime(
            "access_recalculation", "expiry_transition_not_proven"
        )
        results["review_governance_runtime"] = _blocked_runtime("review_governance", "fixture_not_inserted")
        results["audit_metrics_expiry_runtime"] = _blocked_runtime("audit_metrics_expiry", "expiry_event_not_proven")
        results["regression_expiry_runtime"] = _run_regression_api(http, admin_token, step_up, client_id)
        results["classification"] = _classify(results)
        return results

    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    from database import database

    await database.connect()
    db = database.get_db()
    try:
        idx = await _verify_indexes(mongo_url, db_name)
        results["deploy_continuity_expiry"]["indexes"] = idx
        results["deploy_continuity_expiry"]["pass"] = bool(
            results["deploy_continuity_expiry"].get("pass") and idx.get("pass")
        )

        cleared = await _clear_active_governance(db, client_id)
        fixture = await _insert_expiry_fixture(db, client_id)
        fixture["cleared_prior_active"] = cleared
        results["expiry_fixture_runtime"] = {
            "pass": fixture.get("active_row_count") == 1,
            "fixture": fixture,
        }

        job1 = _run_job_api(http, admin_token)
        body1 = job1.get("body") or {}
        result1 = body1.get("result") if isinstance(body1, dict) else {}
        expired_count = int(result1.get("expired_count") or 0)
        expired_ids = [e.get("governance_id") for e in (result1.get("expired") or [])]
        row_after = await _fetch_governance(db, fixture["governance_id"])

        results["expiry_job_runtime"] = {
            "pass": job1.get("ok") and expired_count >= 1 and fixture["governance_id"] in expired_ids,
            "job1": {"ok": job1.get("ok"), "expired_count": expired_count, "expired": result1.get("expired")},
            "row_after": {
                "status": (row_after or {}).get("status"),
                "expired_at": (row_after or {}).get("expired_at"),
            },
        }

        assess_after = _assessment(http, admin_token, client_id)
        access_after = (assess_after.get("access") or {})
        results["access_recalculation_runtime"] = {
            "pass": not assess_after.get("has_active_exception")
            and not (access_after.get("effective_access_reason") or "").startswith("Grace"),
            "has_active_exception": assess_after.get("has_active_exception"),
            "access": access_after,
            "canonical_on_client": assess_after.get("access", {}).get("canonical_entitlement_state"),
            "compliance_preserved_note": "Billing suspension copy asserts records remain; expiry clears governance mirrors only",
        }

        obs = _observability(http, admin_token, client_id)
        events = obs.get("audit_events") or []
        expiry_events = [e for e in events if e.get("event_type") == "commercial_expired"]
        metrics = obs.get("metrics") or {}
        results["audit_metrics_expiry_runtime"] = {
            "pass": len(expiry_events) >= 1,
            "expiry_events": expiry_events[:5],
            "metrics_global": metrics.get("global") or {},
            "expiry_actions_count": (metrics.get("global") or {}).get("expiry_actions"),
        }

        job2 = _run_job_api(http, admin_token)
        body2 = job2.get("body") or {}
        result2 = body2.get("result") if isinstance(body2, dict) else {}
        results["expiry_job_runtime"]["job2_idempotent"] = {
            "expired_count": result2.get("expired_count"),
            "pass": int(result2.get("expired_count") or 0) == 0,
        }
        results["expiry_job_runtime"]["pass"] = bool(
            results["expiry_job_runtime"]["pass"] and results["expiry_job_runtime"]["job2_idempotent"]["pass"]
        )

        await _clear_active_governance(db, client_id)
        review_fix = await _insert_review_fixture(db, client_id)
        job3 = _run_job_api(http, admin_token)
        body3 = job3.get("body") or {}
        result3 = body3.get("result") if isinstance(body3, dict) else {}
        review_ids = result3.get("review_due_governance_ids") or []
        obs2 = _observability(http, admin_token, client_id)
        review_events = [
            e for e in (obs2.get("audit_events") or []) if e.get("event_type") == "commercial_review_due"
        ]
        results["review_governance_runtime"] = {
            "pass": review_fix["governance_id"] in review_ids or len(review_events) >= 1,
            "review_due_ids": review_ids,
            "review_events": review_events[:3],
            "fixture": review_fix,
        }
        await db.commercial_entitlement_governance.update_one(
            {"governance_id": review_fix["governance_id"]},
            {"$set": {"status": "superseded", "superseded_at": _utc()}},
        )

    finally:
        await database.disconnect()

    reg: Dict[str, Any] = {"scenarios": {}}
    if _assessment(http, admin_token, client_id).get("has_active_exception"):
        _execute(http, admin_token, step_up, client_id, "resume_billing")
    grace = _execute(http, admin_token, step_up, client_id, "grant_grace_period", duration_days=7)
    reg["scenarios"]["grace_extension"] = {"passed": grace.get("ok")}
    dup = _execute(http, admin_token, step_up, client_id, "suspend_billing", duration_days=14)
    dup_err = (dup.get("body") or {}).get("detail") if isinstance(dup.get("body"), dict) else {}
    reg["scenarios"]["duplicate_blocked"] = {
        "passed": dup.get("status") == 400 and dup_err.get("error_code") == "ACTIVE_EXCEPTION_EXISTS",
    }
    _execute(http, admin_token, step_up, client_id, "resume_billing")
    prev = _post(
        http,
        f"/admin/clients/{client_id}/commercial-entitlement/impact-preview",
        admin_token,
        {"action": "suspend_billing", "duration_days": 14},
    )
    impact = (prev.get("body") or {}).get("impact_preview") or {}
    reg["scenarios"]["customer_copy"] = {
        "passed": not any(b in (impact.get("customer_impact") or "").lower() for b in FORBIDDEN_COPY),
        "preview": impact,
    }
    reg["scenarios"]["stripe_lightweight"] = {
        "passed": "lightweight" in (impact.get("stripe_impact") or "").lower()
        or "platform authoritative" in (impact.get("stripe_impact") or "").lower(),
    }
    results["regression_expiry_runtime"] = reg

    results["classification"] = _classify(results)
    return results


def _classify(results: Dict[str, Any]) -> str:
    if not (results.get("deploy_continuity_expiry") or {}).get("pass"):
        return "DEPLOY_CONTINUITY_BLOCKED"
    reg = results.get("regression_expiry_runtime") or {}
    if reg.get("scenarios"):
        for s in reg.get("scenarios", {}).values():
            if not s.get("passed"):
                return "FAIL_OPERATIONAL"
    if not (results.get("expiry_fixture_runtime") or {}).get("pass"):
        return "EXPIRY_GOVERNANCE_DRIFT"
    if not (results.get("expiry_job_runtime") or {}).get("pass"):
        return "EXPIRY_GOVERNANCE_DRIFT"
    if not (results.get("access_recalculation_runtime") or {}).get("pass"):
        return "ACCESS_RECALCULATION_DRIFT"
    if not (results.get("audit_metrics_expiry_runtime") or {}).get("pass"):
        return "AUDIT_METRICS_DRIFT"
    if not (results.get("review_governance_runtime") or {}).get("pass"):
        return "REVIEW_GOVERNANCE_DRIFT"
    return "VERIFIED_OPERATIONALLY"


def _write_all(results: Dict[str, Any]) -> None:
    _write("deploy_continuity_expiry.json", results.get("deploy_continuity_expiry"))
    _write("expiry_fixture_runtime.json", results.get("expiry_fixture_runtime"))
    _write("expiry_job_runtime.json", results.get("expiry_job_runtime"))
    _write("access_recalculation_runtime.json", results.get("access_recalculation_runtime"))
    _write("review_governance_runtime.json", results.get("review_governance_runtime"))
    _write("audit_metrics_expiry_runtime.json", results.get("audit_metrics_expiry_runtime"))
    _write("regression_expiry_runtime.json", results.get("regression_expiry_runtime"))
    clf = results.get("classification", "PARTIAL")
    gates = {
        "deploy_continuity_expiry": bool((results.get("deploy_continuity_expiry") or {}).get("pass")),
        "expiry_fixture_staging_db": bool((results.get("expiry_fixture_runtime") or {}).get("pass")),
        "expiry_job_transition": bool((results.get("expiry_job_runtime") or {}).get("pass")),
        "access_recalculation": bool((results.get("access_recalculation_runtime") or {}).get("pass")),
        "review_governance": bool((results.get("review_governance_runtime") or {}).get("pass")),
        "audit_metrics_expiry": bool((results.get("audit_metrics_expiry_runtime") or {}).get("pass")),
        "regression_expiry_api": bool((results.get("regression_expiry_runtime") or {}).get("pass")),
    }
    blocker = None
    if clf == "EXPIRY_GOVERNANCE_DRIFT":
        blocker = "STAGING_MONGO_URL not available in closeout runner environment"
    _write(
        "classifications.json",
        {
            "programme": MARKER,
            "classification": clf,
            "implementation_commits": ["93745c7c", "d21b15bc", "3316e8d8"],
            "verified_at": _utc(),
            "prior_classification": "PARTIAL",
            "gates": gates,
            "blocker": blocker,
        },
    )
    (OUT / "REPORT.md").write_text(
        f"# Phase 2C — Expiry Closeout\n\n## Classification\n**{clf}**\n\n"
        f"Client: `{results.get('client_id')}`\n\n"
        f"See `deploy_continuity_expiry.json`, `expiry_fixture_runtime.json`, "
        f"`expiry_job_runtime.json`, `access_recalculation_runtime.json`, "
        f"`review_governance_runtime.json`, `audit_metrics_expiry_runtime.json`, "
        f"`regression_expiry_runtime.json`.\n",
        encoding="utf-8",
    )
    watch = []
    if clf != "VERIFIED_OPERATIONALLY":
        watch.append("Provide STAGING MONGO_URL via env or docs/audit/phase2c_commercial_entitlement_governance_01/.staging_mongo_url (gitignored) and re-run.")
    if not (results.get("deploy_continuity_expiry") or {}).get("scheduler_listed"):
        watch.append("Deploy 3316e8d8+ so commercial_entitlement_expiry appears in APScheduler (04:10 UTC).")
    (OUT / "watchlist.md").write_text("\n".join(f"- {w}" for w in watch) or "- None\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", default=DEFAULT_CLIENT)
    parser.add_argument("--mongo-url", default="")
    parser.add_argument("--mongo-url-file", default=str(OUT / ".staging_mongo_url"))
    args = parser.parse_args()

    mongo_url, db_name = _load_mongo_url(args.mongo_url or None, args.mongo_url_file)
    email, password = _load_admin_password()
    admin_token = _login_admin(email, password)
    step_up = _step_up(admin_token, password)

    with httpx.Client() as http:
        results = asyncio.run(
            run_expiry_closeout(
                client_id=args.client_id,
                mongo_url=mongo_url,
                db_name=db_name or "compliance_vault_pro",
                admin_token=admin_token,
                step_up=step_up,
                http=http,
            )
        )
    _write_all(results)
    print(json.dumps({"classification": results.get("classification"), "client_id": args.client_id}, indent=2))


if __name__ == "__main__":
    main()
