#!/usr/bin/env python3
"""COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04 — Phase 1 read-only Stripe integrity.

Does not mutate billing records. Does not call admin billing snapshot (that can Stripe-refresh-write).
Masks Stripe identifiers in the written audit JSON.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audit" / "commercial_controls_stripe_integrity_04.json"
TOKEN_FILE = ROOT / ".cc_preflight_token.txt"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
PROD_API = os.getenv("PRODUCTION_API", "https://pleerity-api-production.onrender.com/api").rstrip("/")
MARKER = "COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04"
KNOWN_MISSING_SUBS = {
    "sub_1TI77MCF0O5oqdUzdouAN0BF",
    "sub_1T53ojCF0O5oqdUzhvp5mqmm",
    "sub_1T3HvDCF0O5oqdUzlZ7xCpOv",
    "sub_1T2ThSCF0O5oqdUzXBOJTUdS",
}
CUTOFF_RECENT = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask(value: Any, keep: int = 8) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) <= keep:
        return raw
    return f"{raw[:keep]}…"


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _req(method: str, path: str, token: str = "", **kw) -> Dict[str, Any]:
    timeout = kw.pop("timeout", 90)
    headers = _headers(token) if token else {"Content-Type": "application/json"}
    r = httpx.request(method, f"{API}{path}", headers=headers, timeout=timeout, **kw)
    try:
        body = r.json()
    except Exception:
        body = (r.text or "")[:1500]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _login(email: str, password: str) -> Dict[str, Any]:
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": password}, timeout=90)
    try:
        body = r.json()
    except Exception:
        body = {"raw": (r.text or "")[:300]}
    token = body.get("access_token") if isinstance(body, dict) else None
    user = (body.get("user") or {}) if isinstance(body, dict) else {}
    return {
        "status": r.status_code,
        "ok": r.status_code == 200 and bool(token),
        "token": token,
        "role": user.get("role"),
        "email": user.get("email") or user.get("auth_email"),
    }


def _page_clients(token: str, *, subscription_status: str, skip: int, limit: int = 100) -> Dict[str, Any]:
    return _req(
        "GET",
        f"/admin/clients?subscription_status={subscription_status}&lifecycle_bucket=all&limit={limit}&skip={skip}",
        token,
        timeout=120,
    )


def _collect_status(token: str, status: str, cap: int = 400) -> Tuple[List[Dict[str, Any]], int]:
    rows: List[Dict[str, Any]] = []
    total = 0
    skip = 0
    limit = 100
    while skip < cap:
        page = _page_clients(token, subscription_status=status, skip=skip, limit=limit)
        body = page.get("body") if isinstance(page.get("body"), dict) else {}
        if not page.get("ok"):
            break
        total = int(body.get("total") or 0)
        items = body.get("clients") or []
        rows.extend(items)
        if skip + len(items) >= total or not items:
            break
        skip += limit
    return rows, total


def _classify_row(row: Dict[str, Any], sub_counts: Counter) -> str:
    cust = str(row.get("stripe_customer_id") or "").strip()
    sub = str(row.get("stripe_subscription_id") or "").strip()
    period = _parse_dt(row.get("current_period_end"))
    created = _parse_dt(row.get("created_at"))
    if sub and sub_counts.get(sub, 0) > 1:
        return "DUPLICATE_REFERENCE"
    if not cust and not sub:
        return "MISSING_STRIPE_CUSTOMER"
    if cust and not sub:
        return "MISSING_STRIPE_SUBSCRIPTION"
    if sub and sub in KNOWN_MISSING_SUBS:
        return "STALE_STAGING_FIXTURE"
    if period and period < CUTOFF_RECENT:
        return "STALE_STAGING_FIXTURE"
    if created and created < CUTOFF_RECENT and (not period or period < datetime.now(timezone.utc)):
        return "STALE_STAGING_FIXTURE"
    if period and period >= datetime.now(timezone.utc):
        return "UNKNOWN"
    return "UNKNOWN"


def _stripe_exists_hint(sub: str, drift: str) -> str:
    if sub in KNOWN_MISSING_SUBS:
        return "no_live_retrieve_03"
    if drift == "STALE_STAGING_FIXTURE":
        return "not_retrieved_this_window_historic"
    return "not_retrieved_this_window"


def main() -> int:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or "").strip()
    password = (os.getenv("STAGING_ADMIN_PASSWORD") or "").strip()
    token = ""
    auth_source = ""
    if TOKEN_FILE.is_file():
        candidate = TOKEN_FILE.read_text(encoding="utf-8").strip()
        probe = _req("GET", "/admin/clients?limit=1", candidate)
        if probe.get("ok"):
            token = candidate
            auth_source = "reused_preflight_token"
    login_meta: Dict[str, Any] = {"auth_source": auth_source}
    if not token:
        if not email or not password:
            print(json.dumps({"ok": False, "error": "missing token and STAGING_ADMIN_EMAIL / STAGING_ADMIN_PASSWORD"}))
            return 2
        login = _login(email, password)
        login_meta["login_status"] = login["status"]
        login_meta["role"] = login.get("role")
        if not login["ok"]:
            print(json.dumps({"ok": False, "login": login_meta}, indent=2))
            return 3
        token = login["token"]
        TOKEN_FILE.write_text(token, encoding="utf-8")
        auth_source = "one_login"
        login_meta["auth_source"] = auth_source

    st = _req("GET", "/version")
    pr = httpx.get(f"{PROD_API}/version", timeout=30)
    try:
        pr_body = pr.json()
    except Exception:
        pr_body = {"raw": (pr.text or "")[:200]}

    active_rows, active_total = _collect_status(token, "ACTIVE")
    trial_rows, trial_total = _collect_status(token, "TRIALING")
    billable = active_rows + trial_rows

    sub_counts: Counter = Counter()
    for row in billable:
        sub = str(row.get("stripe_subscription_id") or "").strip()
        if sub:
            sub_counts[sub] += 1

    matrix: List[Dict[str, Any]] = []
    for row in billable:
        sub = str(row.get("stripe_subscription_id") or "").strip()
        cust = str(row.get("stripe_customer_id") or "").strip()
        drift = _classify_row(row, sub_counts)
        period = _parse_dt(row.get("current_period_end"))
        created = _parse_dt(row.get("created_at"))
        now = datetime.now(timezone.utc)
        matrix.append(
            {
                "client_id": row.get("client_id"),
                "email": row.get("email"),
                "platform_subscription_status": row.get("subscription_status"),
                "plan": row.get("billing_plan") or row.get("plan_code"),
                "stripe_customer": _mask(cust),
                "stripe_subscription": _mask(sub),
                "exists": _stripe_exists_hint(sub, drift),
                "platform_period_end": period.isoformat() if period else None,
                "period_in_future": bool(period and period >= now),
                "created_at": created.isoformat() if created else None,
                "created_after_cutoff": bool(created and created >= CUTOFF_RECENT),
                "is_test_like": bool(row.get("is_test_like")),
                "drift_class": drift,
            }
        )

    class_counts = Counter(r["drift_class"] for r in matrix)
    future_period = [r for r in matrix if r.get("period_in_future")]
    recent_created = [r for r in matrix if r.get("created_after_cutoff")]
    unknown_current = [r for r in matrix if r["drift_class"] == "UNKNOWN"]
    duplicate = [r for r in matrix if r["drift_class"] == "DUPLICATE_REFERENCE"]

    isolated = (
        not future_period
        and not unknown_current
        and class_counts.get("STALE_STAGING_FIXTURE", 0) == len(matrix)
        and not duplicate
    )
    if matrix and class_counts.get("STALE_STAGING_FIXTURE", 0) + class_counts.get("MISSING_STRIPE_SUBSCRIPTION", 0) + class_counts.get("MISSING_STRIPE_CUSTOMER", 0) == len(matrix) and not future_period:
        isolated = True
        if class_counts.get("MISSING_STRIPE_SUBSCRIPTION") or class_counts.get("MISSING_STRIPE_CUSTOMER"):
            isolated = not recent_created

    systemic = bool(future_period or (recent_created and unknown_current))
    if isolated:
        decision = "ISOLATED_STALE_STAGING_FIXTURES"
        stop_code = None
    elif systemic:
        decision = "SYSTEMIC_OR_UNVERIFIED_CURRENT"
        stop_code = "BLOCKED_BY_STAGING_STRIPE_RECONCILIATION_DRIFT"
    else:
        decision = "NEEDS_LIVE_STRIPE_FOR_CURRENT_ROWS"
        stop_code = None

    results = {
        "programme": MARKER,
        "at_utc": _utc(),
        "phase": "1_read_only_integrity",
        "mutation": "none",
        "stripe_api_called_from_this_script": False,
        "admin_billing_snapshot_avoided": True,
        "auth_source": auth_source,
        "staging_version": st.get("body") if st.get("ok") else {"status": st.get("status")},
        "production_version": pr_body,
        "totals": {
            "active_total": active_total,
            "trialing_total": trial_total,
            "rows_in_matrix": len(matrix),
        },
        "class_counts": dict(class_counts),
        "future_period_count": len(future_period),
        "recent_created_count": len(recent_created),
        "duplicate_count": len(duplicate),
        "decision": decision,
        "stop_code": stop_code,
        "known_missing_from_03_count": sum(1 for r in matrix if str(r.get("exists")) == "no_live_retrieve_03"),
        "matrix": matrix,
    }
    OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "decision": decision,
                "stop_code": stop_code,
                "class_counts": dict(class_counts),
                "rows": len(matrix),
                "future_period_count": len(future_period),
                "recent_created_count": len(recent_created),
                "wrote": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
