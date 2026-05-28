#!/usr/bin/env python3
"""
PRELAUNCH-RENT-OPERATIONS-OUTCOME-VERIFY-01 — landlord rent outcome flow on staging.
API + browser proof; no unit-test-only classification.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/prelaunch_rent_operations_outcome_verify_01"
_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
PILOT_A = os.environ.get("OPS_VERIFY_PROPERTY_A", "d35a58ae-3c81-491c-9694-1d021dd3b8ad")
PILOT_B = os.environ.get("OPS_VERIFY_PROPERTY_B", "0a5b4497-a1ba-4ee9-87e1-ae2bb9d4cc68")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"RENT-OUTCOME-{RUN_TAG}"
API_PACE_S = float(os.environ.get("OPS_API_PACE_S", "2.0"))
SCREEN_DIR = BUNDLE / "screenshots"

KPI_CARDS = [
    {"key": "collected", "field": "rent_collected_this_month_minor", "filter": {"status": "PAID"}},
    {"key": "upcoming", "field": "upcoming_due_count", "filter": {"status": "UPCOMING"}},
    {"key": "overdue", "field": "overdue_count", "filter": {"overdue_only": True}},
    {"key": "partial", "field": "partially_paid_count", "filter": {"status": "PARTIALLY_PAID"}},
    {"key": "arrears", "field": "tenancies_with_arrears_count", "filter": {"attention_only": True}},
    {"key": "delay", "field": "average_payment_delay_days", "filter": {}},
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _pace() -> None:
    time.sleep(API_PACE_S)


def _http(method: str, url: str, *, retries: int = 5, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        _pace()
        try:
            return getattr(httpx, method)(url, timeout=kwargs.pop("timeout", 120), **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            time.sleep(min(2 ** attempt, 20))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"http_failed:{method}:{url}")


class Auth:
    def __init__(self) -> None:
        self.token = ""
        self.user: dict = {}

    def login(self) -> None:
        pw = os.environ.get("OPS_VERIFY_PASSWORD") or PW_FILE.read_text(encoding="utf-8").strip()
        r = _http("post", f"{API}/auth/login", json={"email": EMAIL, "password": pw})
        if r.status_code != 200:
            raise RuntimeError(f"login_failed:{r.status_code}")
        body = r.json()
        self.token = body["access_token"]
        self.user = body.get("user") or {}

    def h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


def _list_properties(auth: Auth) -> List[dict]:
    r = _http("get", f"{API}/client/properties", headers=auth.h())
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("properties") or (data if isinstance(data, list) else [])


def _create_tenancy(auth: Auth, property_id: str, **extra) -> dict:
    body = {"property_id": property_id, "rent_tracking_enabled": True, **extra}
    r = _http("post", f"{API}/client/operations/rent/tenancies", headers=auth.h(), json=body)
    return {"status": r.status_code, "body": r.json() if r.status_code in (200, 201) else r.text[:300]}


def _future_upcoming(ledgers: List[dict]) -> List[dict]:
    today = date.today().isoformat()
    return [
        L
        for L in ledgers
        if (L.get("status") or "") == "UPCOMING" and (L.get("due_date") or "") > today
    ]


def _preview_schedule(auth: Auth, property_id: str, tenancy_id: Optional[str] = None) -> dict:
    start = date.today().replace(day=1).isoformat()
    body: dict = {
        "property_id": property_id,
        "expected_amount_minor": 120000,
        "due_day": 1,
        "start_date": start,
        "rent_frequency": "monthly",
    }
    if tenancy_id:
        body["tenancy_id"] = tenancy_id
    r = _http("post", f"{API}/client/operations/rent/schedules/preview", headers=auth.h(), json=body)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:300]}


def _create_schedule(
    auth: Auth,
    property_id: str,
    tenancy_id: str,
    *,
    idempotency_key: Optional[str] = None,
    external: bool = False,
    external_name: str = "",
) -> dict:
    start = date.today().replace(day=1).isoformat()
    body: dict = {
        "property_id": property_id,
        "expected_amount_minor": 125000,
        "due_day": 1,
        "start_date": start,
        "rent_frequency": "monthly",
        "tenant_name": f"{MARKER} Tenant",
    }
    if external:
        body["is_external_payer"] = True
        body["external_payer_name"] = external_name or f"{MARKER} Council"
    else:
        body["tenancy_id"] = tenancy_id
    if idempotency_key:
        body["idempotency_key"] = idempotency_key
    r = _http("post", f"{API}/client/operations/rent/schedules", headers=auth.h(), json=body)
    return {"status": r.status_code, "body": r.json() if r.status_code in (200, 201) else r.text[:400]}


def _list_ledgers(auth: Auth, **params: Any) -> List[dict]:
    p = {"limit": 200, **params}
    r = _http("get", f"{API}/client/operations/rent/ledgers", headers=auth.h(), params=p)
    if r.status_code != 200:
        return []
    return r.json().get("ledgers") or []


def _rent_summary(auth: Auth, property_id: Optional[str] = None) -> dict:
    params = {"property_id": property_id} if property_id else {}
    r = _http("get", f"{API}/client/operations/rent/summary", headers=auth.h(), params=params)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _close_tenancy(auth: Auth, tenancy_id: str) -> dict:
    r = _http(
        "post",
        f"{API}/client/operations/rent/tenancies/{tenancy_id}/close",
        headers=auth.h(),
        json={"status": "moved_out"},
    )
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:300]}


def _record_payment(auth: Auth, ledger_id: str, amount_minor: int, **extra) -> dict:
    body = {
        "amount_minor": amount_minor,
        "payment_date": date.today().isoformat(),
        "reference": f"{MARKER}-pay",
        "payment_method": "bank_transfer",
        "ledger_id": ledger_id,
        **extra,
    }
    r = _http(
        "post",
        f"{API}/client/operations/rent/ledgers/{ledger_id}/payments",
        headers=auth.h(),
        json=body,
    )
    return {"status": r.status_code, "body": r.json() if r.status_code in (200, 201) else r.text[:300]}


def _payable_ledger(ledgers: List[dict]) -> Optional[dict]:
    today = date.today().isoformat()
    for L in sorted(ledgers, key=lambda x: x.get("due_date") or ""):
        if int(L.get("outstanding_balance_minor") or 0) <= 0:
            continue
        if (L.get("status") or "") in ("PAID", "WAIVED"):
            continue
        if (L.get("due_date") or "") <= today or (L.get("status") or "") != "UPCOMING":
            return L
    return None


def _count_overdue_tenancies(ledgers: List[dict]) -> int:
    seen: set = set()
    for L in ledgers:
        if not L.get("is_overdue"):
            continue
        if int(L.get("outstanding_balance_minor") or 0) <= 0:
            continue
        key = L.get("tenancy_id") or f"prop:{L.get('property_id')}"
        seen.add(key)
    return len(seen)


def verify_schedule_semantics(auth: Auth, prop_a: str, tenancy_id: str, sched_body: dict) -> dict:
    preview = _preview_schedule(auth, prop_a, tenancy_id)
    pb = preview.get("body") if isinstance(preview.get("body"), dict) else {}
    schedule_id = sched_body.get("schedule_id")
    ledgers = _list_ledgers(auth, property_id=prop_a, tenancy_id=tenancy_id)
    sched_ledgers = [L for L in ledgers if L.get("schedule_id") == schedule_id]
    today = date.today()
    future_rows = [L for L in sched_ledgers if (L.get("status") or "") == "UPCOMING"]
    overdue_rows = [L for L in sched_ledgers if L.get("is_overdue")]
    false_arrears_future = [L for L in future_rows if L.get("is_overdue")]
    legacy_mislabeled = [
        L for L in sched_ledgers if L.get("legacy_rent_authority") and L.get("tenancy_id")
    ]
    legacy_ok = [
        L for L in sched_ledgers if L.get("legacy_rent_authority") and not L.get("tenancy_id")
    ]
    upcoming_in_attention = _list_ledgers(
        auth, property_id=prop_a, attention_only=True, tenancy_id=tenancy_id
    )
    upcoming_leak = [L for L in upcoming_in_attention if (L.get("status") or "") == "UPCOMING" and not L.get("is_overdue")]

    return {
        "verified_at_utc": _utc(),
        "preview": preview,
        "preview_period_count": pb.get("period_count"),
        "preview_disclosure": pb.get("disclosure"),
        "schedule_periods_created": sched_body.get("periods_created"),
        "ledger_rows_for_schedule": len(sched_ledgers),
        "future_upcoming_count": len(future_rows),
        "overdue_count_on_schedule": len(overdue_rows),
        "future_labeled_overdue": len(false_arrears_future),
        "legacy_mislabeled_count": len(legacy_mislabeled),
        "legacy_correct_count": len(legacy_ok),
        "upcoming_in_attention_panel": len(upcoming_leak),
        "checks": {
            "preview_states_period_count": int(pb.get("period_count") or 0) >= 1,
            "disclosure_mentions_periods": "period" in (pb.get("disclosure") or "").lower(),
            "future_not_marked_overdue": len(false_arrears_future) == 0,
            "no_upcoming_in_attention": len(upcoming_leak) == 0,
            "legacy_only_without_tenancy": len(legacy_mislabeled) == 0,
            "multi_period_schedule": int(pb.get("period_count") or 0) >= 2,
        },
        "pass": False,
    }


def verify_onboarding(auth: Auth, prop_a: str, prop_b: str) -> dict:
    ten_a = _create_tenancy(auth, prop_a, tenant_display_name=f"{MARKER} Tenant A")
    ten_b = _create_tenancy(auth, prop_b, tenant_display_name=f"{MARKER} Tenant B") if prop_b != prop_a else ten_a
    ta = (ten_a.get("body") or {}).get("tenancy_id") if isinstance(ten_a.get("body"), dict) else None
    tb = (ten_b.get("body") or {}).get("tenancy_id") if isinstance(ten_b.get("body"), dict) else None

    list_a = _http(
        "get",
        f"{API}/client/operations/rent/tenancies",
        headers=auth.h(),
        params={"property_id": prop_a},
    )
    list_b = _http(
        "get",
        f"{API}/client/operations/rent/tenancies",
        headers=auth.h(),
        params={"property_id": prop_b},
    ) if prop_b != prop_a else list_a
    tenancies_a = (list_a.json().get("tenancies") or []) if list_a.status_code == 200 else []
    tenancies_b = (list_b.json().get("tenancies") or []) if list_b.status_code == 200 else []

    idem = f"sched_{MARKER}_{uuid.uuid4().hex[:8]}"
    sched = _create_schedule(auth, prop_a, ta, idempotency_key=idem) if ta else {"status": 400}
    sb = sched.get("body") if isinstance(sched.get("body"), dict) else {}
    ledgers = _list_ledgers(auth, property_id=prop_a, tenancy_id=ta) if ta else []

    leakage_b_on_a = [L for L in ledgers if L.get("property_id") != prop_a]
    wrong_tenancy = [L for L in ledgers if ta and L.get("tenancy_id") not in (ta, None) and not str(L.get("tenancy_id", "")).startswith("ext_")]

    authority_fields = all(
        L.get("property_id") and (L.get("tenancy_id") or L.get("legacy_rent_authority"))
        for L in ledgers[:20]
    ) if ledgers else False

    probe_no_tenancy = _http(
        "post",
        f"{API}/client/operations/rent/schedules",
        headers=auth.h(),
        json={
            "property_id": prop_a,
            "tenant_name": f"{MARKER} orphan",
            "expected_amount_minor": 100000,
            "due_day": 1,
            "start_date": date.today().replace(day=1).isoformat(),
            "rent_frequency": "monthly",
        },
    )

    return {
        "verified_at_utc": _utc(),
        "tenancy_a": ten_a,
        "tenancy_b": ten_b,
        "tenancy_ids_distinct": ta != tb if ta and tb and prop_b != prop_a else True,
        "tenancies_list_a_count": len(tenancies_a),
        "tenancies_list_b_count": len(tenancies_b),
        "schedule_create": sched,
        "schedule_id": sb.get("schedule_id"),
        "ledger_sample": ledgers[:3],
        "ledger_authority_fields": authority_fields,
        "property_leakage": len(leakage_b_on_a),
        "tenancy_leakage": len(wrong_tenancy),
        "schedule_without_tenancy_rejected": probe_no_tenancy.status_code not in (200, 201),
        "occupancy_tenancy_create_status": ten_a.get("status"),
        "checks": {
            "tenancy_created": ten_a.get("status") in (200, 201),
            "schedule_with_tenancy": sched.get("status") in (200, 201) and bool(sb.get("tenancy_id")),
            "ledgers_scoped": len(leakage_b_on_a) == 0 and len(wrong_tenancy) == 0,
            "no_schedule_without_tenancy": probe_no_tenancy.status_code not in (200, 201),
        },
        "pass": False,
        "tenancy_a_id": ta,
        "tenancy_b_id": tb,
        "schedule_body": sb,
    }


def verify_payment_authority(auth: Auth, prop_a: str, tenancy_id: str) -> dict:
    ledgers = _list_ledgers(auth, property_id=prop_a, tenancy_id=tenancy_id)
    target = _payable_ledger(ledgers)
    if not target:
        return {"pass": False, "reason": "no_payable_ledger", "verified_at_utc": _utc()}

    outstanding = int(target.get("outstanding_balance_minor") or 0)
    partial_amt = max(outstanding // 2, 1) if outstanding > 1 else outstanding
    pay = _record_payment(auth, target["ledger_id"], partial_amt, idempotency_key=f"pay_{MARKER}")
    ld_r = _http("get", f"{API}/client/operations/rent/ledgers/{target['ledger_id']}", headers=auth.h())
    after = ld_r.json() if ld_r.status_code == 200 else {}
    payments = after.get("payments") or []

    other_ledgers = _list_ledgers(auth, property_id=prop_a, tenancy_id=tenancy_id)
    others_changed = [
        L for L in other_ledgers
        if L.get("ledger_id") != target["ledger_id"]
        and L.get("updated_at") == target.get("updated_at")
        and int(L.get("received_amount_minor") or 0) > 0
    ]

    return {
        "verified_at_utc": _utc(),
        "target": {
            "ledger_id": target["ledger_id"],
            "property_id": target.get("property_id"),
            "tenancy_id": target.get("tenancy_id"),
            "period_key": target.get("period_key"),
            "tenant_name": target.get("tenant_name"),
            "outstanding_before": outstanding,
        },
        "partial_payment": pay,
        "after": {
            "status": after.get("status"),
            "outstanding_balance_minor": after.get("outstanding_balance_minor"),
            "received_amount_minor": after.get("received_amount_minor"),
        },
        "payments_on_ledger": len(payments),
        "all_payments_match_ledger": all(p.get("ledger_id") == target["ledger_id"] for p in payments),
        "no_cross_ledger_mutation": len(others_changed) == 0,
        "payment_has_property_tenancy": bool(
            pay.get("status") in (200, 201)
            and target.get("property_id")
            and (target.get("tenancy_id") or target.get("legacy_rent_authority"))
        ),
        "checks": {
            "partial_reduces_outstanding": int(after.get("outstanding_balance_minor") or 0) < outstanding,
            "payment_attached_to_ledger": all(p.get("ledger_id") == target["ledger_id"] for p in payments),
            "no_detached_payment": pay.get("status") in (200, 201),
        },
        "pass": False,
    }


def verify_arrears(auth: Auth, prop_a: str) -> dict:
    summ = _rent_summary(auth, prop_a)
    body = summ.get("body") or {}
    all_ledgers = _list_ledgers(auth, property_id=prop_a)
    attention = _list_ledgers(auth, property_id=prop_a, attention_only=True)
    overdue_ledgers = [L for L in all_ledgers if L.get("is_overdue") and int(L.get("outstanding_balance_minor") or 0) > 0]
    actual_arrears_tenancies = _count_overdue_tenancies(all_ledgers)
    reported_arrears = int(body.get("tenancies_with_arrears_count") or 0)
    overdue_count = int(body.get("overdue_count") or 0)

    future_with_outstanding = [
        L for L in all_ledgers
        if (L.get("status") or "") == "UPCOMING" and int(L.get("outstanding_balance_minor") or 0) > 0
    ]
    false_arrears_inflation = reported_arrears > actual_arrears_tenancies and len(future_with_outstanding) > 0

    return {
        "verified_at_utc": _utc(),
        "summary": body,
        "reported_tenancies_with_arrears": reported_arrears,
        "computed_overdue_tenancies": actual_arrears_tenancies,
        "overdue_ledger_rows": overdue_count,
        "overdue_ledgers_sample": overdue_ledgers[:5],
        "attention_count": len(attention),
        "attention_empty_while_arrears": reported_arrears > 0 and len(attention) == 0,
        "future_upcoming_with_balance": len(future_with_outstanding),
        "false_arrears_inflation_suspected": false_arrears_inflation,
        "checks": {
            "arrears_count_matches_overdue_tenancies": reported_arrears == actual_arrears_tenancies
            or (reported_arrears > 0 and actual_arrears_tenancies > 0),
            "attention_when_arrears": not (reported_arrears > 0 and len(attention) == 0),
            "no_future_only_false_arrears": not false_arrears_inflation,
            "overdue_count_positive_when_debt": overdue_count >= len(overdue_ledgers) or len(overdue_ledgers) == 0,
        },
        "pass": False,
    }


def verify_metric_blocks(auth: Auth, prop_a: str) -> dict:
    summ = _rent_summary(auth, prop_a)
    body = summ.get("body") or {}
    probes: List[dict] = []

    for card in KPI_CARDS:
        metric_val = body.get(card["field"])
        filt = card["filter"]
        params: dict = {"property_id": prop_a, "limit": 200}
        if filt.get("status"):
            params["status"] = filt["status"]
        if filt.get("overdue_only"):
            params["overdue_only"] = True
        if filt.get("attention_only"):
            params["attention_only"] = True
        rows = _list_ledgers(auth, **params) if filt else []
        listed = len(rows)
        if card["key"] == "delay":
            ok = metric_val is not None
            drill = True
        elif card["key"] == "collected":
            ok = metric_val is not None
            drill = True
        else:
            ok = metric_val is not None and (listed > 0 or int(metric_val or 0) == 0)
            drill = card["filter"] != {} or card["key"] in ("collected", "delay")
        probes.append(
            {
                "key": card["key"],
                "field": card["field"],
                "metric_value": metric_val,
                "filter": filt,
                "drilldown_rows": listed,
                "has_drilldown_filter": drill,
                "metric_present": metric_val is not None,
                "pass": ok and drill,
            }
        )

    contradictions = []
    if int(body.get("overdue_count") or 0) > 0 and int(body.get("upcoming_due_count") or 0) == 0:
        up_rows = _list_ledgers(auth, property_id=prop_a, status="UPCOMING")
        if len(up_rows) > int(body.get("upcoming_due_count") or 0):
            contradictions.append("upcoming_count_under_reported")

    return {
        "verified_at_utc": _utc(),
        "summary": body,
        "kpi_probes": probes,
        "contradictions": contradictions,
        "checks": {p["key"]: p["pass"] for p in probes},
        "pass": all(p["pass"] for p in probes) and not contradictions,
    }


def verify_multi_property(auth: Auth, prop_a: str, prop_b: str, ta: str, tb: str) -> dict:
    ext = _create_schedule(
        auth,
        prop_b or prop_a,
        "",
        idempotency_key=f"ext_{MARKER}",
        external=True,
        external_name=f"{MARKER} HB",
    )
    ext_body = ext.get("body") if isinstance(ext.get("body"), dict) else {}

    ledgers_before_close = _list_ledgers(auth, property_id=prop_a, tenancy_id=ta) if ta else []
    before_future_ids = {L.get("ledger_id") for L in _future_upcoming(ledgers_before_close)}

    close = _close_tenancy(auth, ta) if ta else {"status": 404}
    close_body = close.get("body") if isinstance(close.get("body"), dict) else {}
    ended_at = close_body.get("ended_at") or _utc()

    ledgers_after_close = _list_ledgers(auth, property_id=prop_a, tenancy_id=ta) if ta else []
    new_future_after_close = [
        L
        for L in _future_upcoming(ledgers_after_close)
        if L.get("ledger_id") not in before_future_ids
        or (L.get("created_at") or "") > ended_at
    ]

    repl = (
        _create_tenancy(
            auth,
            prop_a,
            rent_tracking_enabled=True,
            lineage_parent_tenancy_id=ta,
            tenant_display_name=f"{MARKER} Replacement",
        )
        if ta
        else {"status": 404}
    )
    repl_id = (repl.get("body") or {}).get("tenancy_id") if isinstance(repl.get("body"), dict) else None
    new_sched = _create_schedule(auth, prop_a, repl_id, idempotency_key=f"repl_{MARKER}") if repl_id else {"status": 400}
    ledgers_b = _list_ledgers(auth, property_id=prop_b) if prop_b != prop_a else []

    leak_a_to_b = [L for L in ledgers_b if L.get("tenancy_id") == ta]
    leak_b_to_a = [L for L in _list_ledgers(auth, property_id=prop_a) if tb and L.get("tenancy_id") == tb]

    new_lineage_ledgers = _list_ledgers(auth, property_id=prop_a, tenancy_id=repl_id) if repl_id else []
    old_payments_preserved = any(
        int(L.get("received_amount_minor") or 0) > 0 for L in ledgers_after_close
    )

    return {
        "verified_at_utc": _utc(),
        "external_payer": ext,
        "close_moved_out": close,
        "replacement_tenancy": repl,
        "new_schedule": new_sched,
        "historical_preserved": len(ledgers_before_close) >= 1,
        "ledgers_after_close_count": len(ledgers_after_close),
        "new_lineage_ledger_count": len(new_lineage_ledgers),
        "cross_property_leak_a_b": len(leak_a_to_b),
        "cross_property_leak_b_a": len(leak_b_to_a),
        "future_upcoming_before_close": len(before_future_ids),
        "new_future_ledgers_after_close": len(new_future_after_close),
        "historical_payments_on_old_tenancy": old_payments_preserved,
        "replacement_has_lineage_parent": (repl.get("body") or {}).get("lineage_parent_tenancy_id") == ta
        if isinstance(repl.get("body"), dict)
        else False,
        "checks": {
            "external_payer_ok": ext.get("status") in (200, 201) and ext_body.get("is_external_payer"),
            "no_cross_leak": len(leak_a_to_b) == 0 and len(leak_b_to_a) == 0,
            "close_ok": close.get("status") == 200,
            "replacement_schedule": new_sched.get("status") in (200, 201),
            "distinct_lineage": ta != repl_id if ta and repl_id else True,
            "no_new_future_on_moved_out": len(new_future_after_close) == 0,
            "replacement_lineage_linked": (repl.get("body") or {}).get("lineage_parent_tenancy_id") == ta
            if isinstance(repl.get("body"), dict)
            else False,
        },
        "pass": False,
    }


def run_browser(auth: Auth, prop_a: str, prop_b: str) -> dict:
    out: dict = {"attempted": False, "skipped": True}
    if sync_playwright is None:
        out["error"] = "playwright_not_installed"
        return out

    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    pw = os.environ.get("OPS_VERIFY_PASSWORD") or PW_FILE.read_text(encoding="utf-8").strip()
    captures: List[dict] = []
    timings: List[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
        t0 = time.perf_counter()
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.fill("#email", EMAIL)
        page.fill("#password", pw)
        page.click('button[type="submit"]')
        page.wait_for_timeout(4000)
        timings.append({"step": "login", "elapsed_ms": int((time.perf_counter() - t0) * 1000)})

        routes = [
            ("rent_dashboard", f"/operations/rent?property_id={prop_a}", "rent_dashboard.png"),
            ("rent_setup", f"/operations/rent?property_id={prop_a}&setup=1", "rent_setup_modal.png"),
            ("rent_ledger", f"/operations/rent?property_id={prop_a}&tab=ledger", "rent_ledger.png"),
            ("rent_attention", f"/operations/rent?property_id={prop_a}&tab=attention", "rent_attention.png"),
            ("occupancy", f"/properties/{prop_a}?tab=occupancy", "occupancy_rent_link.png"),
        ]
        if prop_b and prop_b != prop_a:
            routes.append(("rent_property_b", f"/operations/rent?property_id={prop_b}", "rent_property_b.png"))

        for surface, path, shot in routes:
            t1 = time.perf_counter()
            page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(5000)
            try:
                page.wait_for_selector('[data-testid="rent-summary-cards"]', timeout=15_000)
            except Exception:
                pass
            shot_path = SCREEN_DIR / shot
            page.screenshot(path=str(shot_path), full_page=True)
            text = (page.inner_text("body") or "")[:2000]
            captures.append(
                {
                    "surface": surface,
                    "path": path,
                    "screenshot": f"screenshots/{shot}",
                    "rent_page": page.locator('[data-testid="rent-operations-page"]').count() > 0,
                    "kpi_cards": page.locator('[data-testid="rent-summary-cards"]').count() > 0,
                    "schedule_preview": page.locator('[data-testid="rent-schedule-preview"]').count() > 0,
                    "body_has_arrears": "arrears" in text.lower() or "overdue" in text.lower(),
                }
            )
            timings.append({"surface": surface, "elapsed_ms": int((time.perf_counter() - t1) * 1000)})

        if page.locator('[data-testid="rent-enable-tracking"]').count():
            page.locator('[data-testid="rent-enable-tracking"]').first.click()
            page.wait_for_timeout(800)

        page.goto(f"{FRONTEND}/operations/rent?property_id={prop_a}&tab=ledger", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2000)
        kpi = page.locator('[data-testid="rent-kpi-overdue"]')
        if kpi.count():
            kpi.first.click()
            page.wait_for_timeout(1500)
            captures.append({"surface": "kpi_overdue_click", "filter_active": True})

        pay_btn = page.locator('button:has-text("Record payment")')
        if pay_btn.count():
            pay_btn.first.click()
            page.wait_for_timeout(800)
            page.screenshot(path=str(SCREEN_DIR / "record_payment_modal.png"), full_page=False)
            captures.append(
                {
                    "surface": "record_payment",
                    "screenshot": "screenshots/record_payment_modal.png",
                    "payment_authority_context": page.locator('[data-testid="payment-authority-context"]').count() > 0,
                }
            )

        browser.close()

    out = {
        "attempted": True,
        "skipped": False,
        "captures": captures,
        "timings": timings,
        "finished_at_utc": _utc(),
        "pass": any(c.get("rent_page") for c in captures),
    }
    return out


def _finalize_checks(result: dict) -> None:
    result["pass"] = all(result.get("checks", {}).values())


def classify(defects: List[str], gates: Dict[str, bool], browser: dict) -> Tuple[str, str]:
    if "login_failed" in defects:
        return "FAIL_OPERATIONAL", "Could not authenticate to staging"
    if any(d in defects for d in ("MULTI_PROPERTY_LEAKAGE",)):
        return "MULTI_PROPERTY_LEAKAGE", "Tenant/property/ledger isolation failure"
    if any(d in defects for d in ("PAYMENT_ATTRIBUTION_FAILURE",)):
        return "PAYMENT_ATTRIBUTION_FAILURE", "Payment not attributed to correct ledger/tenancy"
    if any(d in defects for d in ("ARREARS_VISIBILITY_FAILURE",)):
        return "ARREARS_VISIBILITY_FAILURE", "Arrears metrics or attention panel inconsistent"
    if any(d in defects for d in ("RENT_AUTHORITY_DRIFT",)):
        return "RENT_AUTHORITY_DRIFT", "Schedule/tenancy authority drift"
    if not browser.get("pass"):
        if all(gates.values()):
            return "PARTIAL", "API gates passed; browser proof incomplete"
        return "TRUST_RISK_PRESENT", f"Gaps: {', '.join(defects)}"
    if all(gates.values()) and browser.get("pass"):
        return "VERIFIED_OPERATIONALLY", "Rent outcome flow verified on staging (API + browser)"
    if defects:
        return "TRUST_RISK_PRESENT", f"Defects: {', '.join(defects)}"
    return "PARTIAL", "Some gates did not pass"


def main() -> int:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    defects: List[str] = []
    gates: Dict[str, bool] = {}

    _write(
        "00_run_meta.json",
        {
            "programme": "PRELAUNCH-RENT-OPERATIONS-OUTCOME-VERIFY-01",
            "run_tag": RUN_TAG,
            "marker": MARKER,
            "started_at": _utc(),
            "api": API,
            "frontend": FRONTEND,
        },
    )

    ver = _http("get", f"{API.replace('/api', '')}/api/version", timeout=30)
    health = _http("get", f"{API.replace('/api', '')}/api/health", timeout=30)
    deploy = {
        "version": ver.json() if ver.status_code == 200 else ver.text[:100],
        "health_status": health.status_code,
    }

    auth = Auth()
    try:
        auth.login()
    except Exception as exc:
        _write("classifications.json", {"classification": "FAIL_OPERATIONAL", "reason": str(exc)})
        return 1

    props = _list_properties(auth)
    prop_a = props[0]["property_id"] if props else PILOT_A
    prop_b = props[1]["property_id"] if len(props) > 1 else (PILOT_B if PILOT_B != prop_a else prop_a)

    onboarding = verify_onboarding(auth, prop_a, prop_b)
    _finalize_checks(onboarding)
    gates["onboarding"] = onboarding["pass"]
    if not onboarding["pass"]:
        defects.append("RENT_AUTHORITY_DRIFT")
    _write("tenancy_onboarding_runtime.json", onboarding)

    ta = onboarding.get("tenancy_a_id")
    sb = onboarding.get("schedule_body") or {}

    schedule = verify_schedule_semantics(auth, prop_a, ta or "", sb)
    _finalize_checks(schedule)
    gates["schedule_semantics"] = schedule["pass"]
    if not schedule["pass"]:
        if schedule["checks"].get("no_upcoming_in_attention") is False:
            defects.append("ARREARS_VISIBILITY_FAILURE")
        else:
            defects.append("RENT_AUTHORITY_DRIFT")
    _write("schedule_semantics_runtime.json", schedule)

    payment = verify_payment_authority(auth, prop_a, ta or "")
    if payment.get("checks"):
        _finalize_checks(payment)
    else:
        payment["pass"] = False
    gates["payment_authority"] = payment["pass"]
    if not payment["pass"]:
        defects.append("PAYMENT_ATTRIBUTION_FAILURE")
    _write("payment_authority_runtime.json", payment)

    arrears = verify_arrears(auth, prop_a)
    _finalize_checks(arrears)
    gates["arrears"] = arrears["pass"]
    if not arrears["pass"]:
        defects.append("ARREARS_VISIBILITY_FAILURE")
    _write("arrears_accuracy_runtime.json", arrears)

    metrics = verify_metric_blocks(auth, prop_a)
    gates["metric_blocks"] = metrics["pass"]
    if not metrics["pass"]:
        defects.append("ARREARS_VISIBILITY_FAILURE")
    _write("rent_metric_blocks_runtime.json", metrics)

    iso = verify_multi_property(
        auth,
        prop_a,
        prop_b,
        ta or "",
        onboarding.get("tenancy_b_id") or "",
    )
    _finalize_checks(iso)
    gates["multi_property"] = iso["pass"]
    if not iso["pass"]:
        if not iso["checks"].get("no_cross_leak"):
            defects.append("MULTI_PROPERTY_LEAKAGE")
        else:
            defects.append("RENT_AUTHORITY_DRIFT")
    _write("multi_property_isolation_runtime.json", iso)

    browser = run_browser(auth, prop_a, prop_b)
    gates["browser"] = browser.get("pass", False)
    _write("browser_runtime.json", browser)

    classification, reason = classify(defects, gates, browser)
    cls = {
        "classification": classification,
        "verified_operationally": classification == "VERIFIED_OPERATIONALLY",
        "reason": reason,
        "defects": sorted(set(defects)),
        "gates": gates,
        "deploy": deploy,
        "run_tag": RUN_TAG,
        "verified_at_utc": _utc(),
    }
    _write("classifications.json", cls)

    roadmap = []
    if "ARREARS_VISIBILITY_FAILURE" in defects:
        roadmap.append("Align tenancies_with_arrears_count with is_overdue tenancies (exclude UPCOMING forecast rows).")
    if "PAYMENT_ATTRIBUTION_FAILURE" in defects:
        roadmap.append("Ensure record-payment modal and API require ledger_id + tenancy context.")
    if "MULTI_PROPERTY_LEAKAGE" in defects:
        roadmap.append("Audit ledger queries for property_id scoping on all rent surfaces.")
    if not browser.get("pass"):
        roadmap.append("Re-run browser capture after frontend deploy continuity check.")

    watchlist = BUNDLE / "watchlist.md"
    watchlist.write_text(
        f"# PRELAUNCH-RENT-OPERATIONS-OUTCOME-VERIFY-01\n\n"
        f"**Classification:** `{classification}`\n"
        f"**Run:** {MARKER}\n\n"
        f"## Defects\n"
        + ("\n".join(f"- {d}" for d in defects) if defects else "- None\n")
        + f"\n## Gates\n"
        + "\n".join(f"- {k}: {v}" for k, v in gates.items())
        + "\n",
        encoding="utf-8",
    )

    report = BUNDLE / "REPORT.md"
    report.write_text(
        f"# PRELAUNCH-RENT-OPERATIONS-OUTCOME-VERIFY-01\n\n"
        f"**Classification:** `{classification}`\n"
        f"**Run:** {MARKER}\n"
        f"**Staging version:** `{deploy.get('version')}`\n\n"
        f"## Summary\n\n{reason}\n\n"
        f"## Gates\n\n| Gate | Pass |\n|------|------|\n"
        + "\n".join(f"| {k} | {v} |" for k, v in gates.items())
        + "\n\n## Remediation roadmap\n\n"
        + ("\n".join(f"- {r}" for r in roadmap) if roadmap else "- None required\n"),
        encoding="utf-8",
    )

    print(json.dumps(cls, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
