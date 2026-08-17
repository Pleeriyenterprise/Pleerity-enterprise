#!/usr/bin/env python3
"""Follow-up 03: cleanup leftover grace; find a live Stripe subscription; PLAN_UNRESOLVED scan."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audit" / "commercial_controls_e2e_followup_03.json"
TOKEN_FILE = ROOT / ".cc_preflight_token.txt"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
REASON = "COMMERCIAL-CONTROLS-E2E-03 follow-up governed certification"
RUNTIME_SHA = "7c77391a5ee65f0a85372d9c462448c270b6b066"
CLEANUP_CLIENT = "ec0b091b-105d-4b78-9711-7ab143999cef"
CANDIDATES = [
    "6fd5ac4c-3fd4-4112-ade7-156977deb49f",  # nancy@yopmail.com
    "33017032-afec-48cc-8102-30761bf49f75",  # extra active
    "b3c0c6d0",  # placeholder skipped
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mask(v: Any, n: int = 8) -> Optional[str]:
    s = str(v or "").strip()
    if not s:
        return None
    return s if len(s) <= n else f"{s[:n]}…"


def _ecode(body: Any) -> Optional[str]:
    if isinstance(body, dict) and isinstance(body.get("detail"), dict):
        return body["detail"].get("error_code")
    return None


def _headers(token: str, step_up: str = "", confirmation: str = "") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    if confirmation:
        h["X-Admin-Confirmation-Token"] = confirmation
    return h


def _req(method: str, path: str, token: str, **kw) -> Dict[str, Any]:
    step_up = kw.pop("step_up", "")
    confirmation = kw.pop("confirmation", "")
    timeout = kw.pop("timeout", 120)
    r = httpx.request(
        method,
        f"{API}{path}",
        headers=_headers(token, step_up, confirmation),
        timeout=timeout,
        **kw,
    )
    try:
        body = r.json()
    except Exception:
        body = (r.text or "")[:1500]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _login() -> str:
    if TOKEN_FILE.is_file():
        tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
        probe = _req("GET", "/admin/clients?limit=1", tok)
        if probe.get("ok"):
            return tok
    email = (os.getenv("STAGING_ADMIN_EMAIL") or "").strip()
    password = (os.getenv("STAGING_ADMIN_PASSWORD") or "").strip()
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": password}, timeout=90)
    if r.status_code in (401, 423):
        raise SystemExit(json.dumps({"blocked": r.status_code}))
    r.raise_for_status()
    tok = r.json()["access_token"]
    TOKEN_FILE.write_text(tok, encoding="utf-8")
    return tok


def _step(token: str) -> str:
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or "").strip()
    r = httpx.post(f"{API}/auth/step-up/verify", json={"password": pw}, headers=_headers(token), timeout=60)
    r.raise_for_status()
    return r.json()["step_up_token"]


def _confirm(token: str, resource: str, action_id: str = "commercial_entitlement_execute") -> str:
    r = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        json={"action_id": action_id, "reason": REASON, "resource_key": resource},
        headers=_headers(token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["token"]


def _exec(token: str, step: str, cid: str, action: str, extra: Dict[str, Any], send_email: bool = False) -> Dict[str, Any]:
    started = time.perf_counter()
    out = _req(
        "POST",
        f"/admin/clients/{cid}/commercial-entitlement/execute",
        token,
        json={"action": action, "reason": REASON, "send_customer_email": send_email, **extra},
        step_up=step,
        confirmation=_confirm(token, cid),
        timeout=90,
    )
    out["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return out


def _assess(token: str, cid: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/clients/{cid}/commercial-entitlement/assessment", token)


def _bill(token: str, cid: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/billing/clients/{cid}", token, timeout=90)


def _obs(token: str, cid: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/clients/{cid}/commercial-entitlement/observability", token)


def _msgs(token: str, cid: str) -> Dict[str, Any]:
    return _req("GET", f"/admin/message-logs?client_id={cid}&limit=8", token)


def _msg_rows(body: Any) -> List[Dict[str, Any]]:
    if not isinstance(body, dict):
        return []
    rows = body.get("items") or body.get("messages") or body.get("logs") or []
    out: List[Dict[str, Any]] = []
    for m in rows[:8]:
        if isinstance(m, dict):
            out.append(
                {
                    "message_id_prefix": _mask(m.get("message_id")),
                    "status": m.get("status"),
                    "template_key": m.get("template_key"),
                    "recipient": m.get("recipient"),
                    "created_at": str(m.get("created_at") or "")[:25],
                }
            )
    return out


def _revoke(token: str, step: str, cid: str) -> Dict[str, Any]:
    a = _assess(token, cid).get("body") or {}
    if not isinstance(a, dict) or not a.get("has_active_exception"):
        return {"revoked": False}
    return {"revoked": True, "exe": _exec(token, step, cid, "revoke_commercial_exception", {})}


def _access(body: Any) -> Dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    acc = body.get("access") or {}
    gov = body.get("active_governance") or {}
    return {
        "canonical": acc.get("canonical_entitlement_state"),
        "underlying": acc.get("underlying_canonical_entitlement_state"),
        "effective": acc.get("effective_entitlement_state"),
        "plan": acc.get("restored_plan_code"),
        "exception": body.get("has_active_exception"),
        "gov": (gov or {}).get("exception_type") if isinstance(gov, dict) else None,
        "expiry": (gov or {}).get("entitlement_expiry_at") if isinstance(gov, dict) else None,
        "notify": (gov or {}).get("customer_notification_status") if isinstance(gov, dict) else None,
        "stripe_recon": (gov or {}).get("stripe_reconciliation_status") if isinstance(gov, dict) else None,
    }


def main() -> int:
    token = _login()
    step = _step(token)
    out: Dict[str, Any] = {"at_utc": _utc(), "runtime_sha": RUNTIME_SHA, "cleanup": {}, "probe": [], "suspend_active": {}, "plan_unresolved": {}, "expiry": {}}

    out["cleanup"]["drjpane_before"] = _access(_assess(token, CLEANUP_CLIENT).get("body"))
    out["cleanup"]["revoke"] = _revoke(token, step, CLEANUP_CLIENT)
    out["cleanup"]["drjpane_after"] = _access(_assess(token, CLEANUP_CLIENT).get("body"))

    # Expand ACTIVE candidates from client list
    ids: List[str] = [
        "6fd5ac4c-3fd4-4112-ade7-156977deb49f",
        "33017032-afec-48cc-8102-30761bf49f75",
    ]
    for skip in (0, 50, 100):
        listing = _req("GET", f"/admin/clients?lifecycle_bucket=all&limit=50&skip={skip}", token, timeout=90)
        body = listing.get("body") if isinstance(listing.get("body"), dict) else {}
        for row in body.get("clients") or []:
            cid = row.get("client_id")
            st = str(row.get("subscription_status") or "").upper()
            if cid and st == "ACTIVE" and cid not in ids:
                ids.append(cid)
        # plan-less hunt
        for row in body.get("clients") or []:
            plan = row.get("billing_plan") or row.get("plan_code")
            if row.get("client_id") and not plan:
                out.setdefault("planless_rows", []).append(
                    {"client_id": row.get("client_id"), "email": row.get("email"), "status": row.get("subscription_status")}
                )

    now = datetime.now(timezone.utc)
    chosen = None
    for cid in ids[:12]:
        a = _assess(token, cid)
        b = _bill(token, cid)
        ab = a.get("body") if isinstance(a.get("body"), dict) else {}
        bb = b.get("body") if isinstance(b.get("body"), dict) else {}
        acc = ab.get("access") or {}
        period = str(bb.get("current_period_end") or "")
        future = False
        try:
            raw = period.replace("Z", "+00:00")
            if raw:
                future = datetime.fromisoformat(raw) > now
        except Exception:
            future = False
        probe = {
            "client_id": cid,
            "email": bb.get("contact_email"),
            "canonical": (acc.get("underlying_canonical_entitlement_state") or acc.get("canonical_entitlement_state")),
            "plan": acc.get("restored_plan_code"),
            "exception": ab.get("has_active_exception"),
            "sub_prefix": _mask(bb.get("stripe_subscription_id")),
            "period_end": period[:40] if period else None,
            "period_in_future": future,
            "has_subscription": (bb.get("subscription_lifecycle") or {}).get("has_subscription"),
            "subscription_status": bb.get("subscription_status"),
        }
        out["probe"].append(probe)
        if (
            chosen is None
            and (acc.get("underlying_canonical_entitlement_state") or acc.get("canonical_entitlement_state") or "").upper() == "ENABLED"
            and not ab.get("has_active_exception")
            and bb.get("stripe_subscription_id")
        ):
            # Prefer future period; otherwise still try yopmail nancy first
            if future or cid == "6fd5ac4c-3fd4-4112-ade7-156977deb49f":
                chosen = cid

    if chosen is None:
        for p in out["probe"]:
            if p.get("canonical") == "ENABLED" and not p.get("exception") and p.get("sub_prefix"):
                chosen = p["client_id"]
                break

    out["chosen_active"] = chosen
    if chosen:
        _revoke(token, step, chosen)
        before = _access(_assess(token, chosen).get("body"))
        before_bill = _bill(token, chosen)
        expiry = _iso_z(datetime.now(timezone.utc) + timedelta(seconds=95))
        exe = _exec(token, step, chosen, "suspend_billing", {"duration_days": 14, "entitlement_expiry_at": expiry}, send_email=True)
        if exe.get("status") == 403:
            step = _step(token)
            exe = _exec(token, step, chosen, "suspend_billing", {"duration_days": 14, "entitlement_expiry_at": expiry}, send_email=True)
        after = _access(_assess(token, chosen).get("body"))
        after_bill = _bill(token, chosen)
        exe_body = exe.get("body") if isinstance(exe.get("body"), dict) else {}
        stripe_pause = exe_body.get("stripe_pause")
        out["suspend_active"] = {
            "client_id": chosen,
            "runtime_sha": RUNTIME_SHA,
            "before": before,
            "after": after,
            "api_status": exe.get("status"),
            "elapsed_ms": exe.get("elapsed_ms"),
            "error_code": _ecode(exe_body),
            "error_message": (exe_body.get("detail") or {}).get("message") if isinstance(exe_body.get("detail"), dict) else None,
            "stripe_pause": {
                "mutation": (stripe_pause or {}).get("mutation") if isinstance(stripe_pause, dict) else None,
                "behavior": (stripe_pause or {}).get("behavior") if isinstance(stripe_pause, dict) else None,
                "reconciliation_status": (stripe_pause or {}).get("reconciliation_status") if isinstance(stripe_pause, dict) else None,
                "subscription_status": (stripe_pause or {}).get("subscription_status") if isinstance(stripe_pause, dict) else None,
                "subscription_id_prefix": _mask((stripe_pause or {}).get("subscription_id")) if isinstance(stripe_pause, dict) else None,
            },
            "email_result": exe_body.get("email_result"),
            "preview": exe_body.get("impact_preview"),
            "messages": _msg_rows(_msgs(token, chosen).get("body")),
            "before_period_end": str((before_bill.get("body") or {}).get("current_period_end") or "")[:40],
            "after_period_end": str((after_bill.get("body") or {}).get("current_period_end") or "")[:40],
            "audit": [
                {"event_type": e.get("event_type"), "created_at": str(e.get("created_at") or "")[:25]}
                for e in ((_obs(token, chosen).get("body") or {}).get("audit_events") or [])[:6]
                if isinstance(e, dict)
            ],
        }
        mutation = (out["suspend_active"]["stripe_pause"] or {}).get("mutation")
        if exe.get("ok") and after.get("exception") and mutation in ("pause_collection", "already_paused"):
            out["suspend_active"]["verdict"] = "PASS"
            dup = _exec(token, step, chosen, "grant_grace_period", {"duration_days": 7})
            out["duplicate"] = {
                "status": dup.get("status"),
                "error_code": _ecode(dup.get("body")),
                "pass": not dup.get("ok"),
            }
            time.sleep(100)
            conf = _confirm(token, "commercial_entitlement_expiry:global", "run_portfolio_wide_job")
            job = _req(
                "POST",
                "/admin/jobs/run",
                token,
                json={"job": "commercial_entitlement_expiry", "reason": REASON, "portfolio_wide": True, "portfolio_wide_confirmed": True},
                confirmation=conf,
                timeout=180,
            )
            after_exp = _access(_assess(token, chosen).get("body"))
            after_bill_exp = _bill(token, chosen)
            jb = job.get("body") if isinstance(job.get("body"), dict) else {}
            out["expiry"] = {
                "job_ok": job.get("ok"),
                "result": jb.get("result"),
                "after": after_exp,
                "period_end": str((after_bill_exp.get("body") or {}).get("current_period_end") or "")[:40],
                "pass": not after_exp.get("exception") and (after_exp.get("underlying") or after_exp.get("canonical") or "").upper() == "ENABLED",
                "runtime_sha": RUNTIME_SHA,
            }
        else:
            out["suspend_active"]["verdict"] = "FAIL_OR_STALE_STRIPE"
            # If Stripe missing sub, try next candidate once more (max 2 additional)
            extra_attempts = []
            for p in out["probe"]:
                cid = p["client_id"]
                if cid == chosen:
                    continue
                if p.get("canonical") != "ENABLED" or p.get("exception"):
                    continue
                _revoke(token, step, cid)
                exe2 = _exec(token, step, cid, "suspend_billing", {"duration_days": 14}, send_email=False)
                extra_attempts.append(
                    {
                        "client_id": cid,
                        "email": p.get("email"),
                        "status": exe2.get("status"),
                        "error_code": _ecode(exe2.get("body")),
                        "message": ((exe2.get("body") or {}).get("detail") or {}).get("message")
                        if isinstance((exe2.get("body") or {}).get("detail"), dict)
                        else None,
                        "stripe_pause": (exe2.get("body") or {}).get("stripe_pause") if isinstance(exe2.get("body"), dict) else None,
                    }
                )
                if exe2.get("ok"):
                    _revoke(token, step, cid)
                    break
                if len(extra_attempts) >= 3:
                    break
            out["additional_stripe_attempts"] = extra_attempts

    # PLAN_UNRESOLVED: try suspend on clients whose assessment restored_plan_code is empty
    unresolved = None
    for skip in (0, 50, 100, 150):
        listing = _req("GET", f"/admin/clients?lifecycle_bucket=all&limit=50&skip={skip}", token, timeout=90)
        body = listing.get("body") if isinstance(listing.get("body"), dict) else {}
        for row in body.get("clients") or []:
            cid = row.get("client_id")
            if not cid:
                continue
            a = _assess(token, cid)
            ab = a.get("body") if isinstance(a.get("body"), dict) else {}
            plan = (ab.get("access") or {}).get("restored_plan_code")
            if ab.get("found") and not plan and not ab.get("has_active_exception"):
                unresolved = {"client_id": cid, "email": row.get("email"), "canonical": (ab.get("access") or {}).get("canonical_entitlement_state")}
                break
        if unresolved:
            break
    out["plan_unresolved_candidate"] = unresolved
    if unresolved:
        exe = _exec(token, step, unresolved["client_id"], "suspend_billing", {"duration_days": 14})
        out["plan_unresolved"] = {
            "client_id": unresolved["client_id"],
            "status": exe.get("status"),
            "error_code": _ecode(exe.get("body")),
            "message": ((exe.get("body") or {}).get("detail") or {}).get("message")
            if isinstance((exe.get("body") or {}).get("detail"), dict)
            else None,
            "pass": _ecode(exe.get("body")) == "PLAN_UNRESOLVED",
            "runtime_sha": RUNTIME_SHA,
        }

    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "cleanup": out["cleanup"].get("drjpane_after"),
        "chosen": chosen,
        "suspend_verdict": (out.get("suspend_active") or {}).get("verdict"),
        "stripe": (out.get("suspend_active") or {}).get("stripe_pause"),
        "error": (out.get("suspend_active") or {}).get("error_code"),
        "plan_unresolved": out.get("plan_unresolved") or out.get("plan_unresolved_candidate"),
        "expiry": (out.get("expiry") or {}).get("pass"),
        "wrote": str(OUT),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
