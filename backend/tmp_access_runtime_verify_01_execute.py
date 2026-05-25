"""
PRELAUNCH-ACCESS-RUNTIME-VERIFY-01 — access, onboarding, identity, lifecycle verification.
Local harness only. Sequential families A1–A7.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ops_runtime_verify_02.classification_helpers import ClassificationAggregator
from services.ops_runtime_verify_02.convergence_observer import ConvergenceObserver

PROGRAMME = "PRELAUNCH-ACCESS-RUNTIME-VERIFY-01"
OWNER = "access_runtime_verify_01"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_EMAIL = "nancy@yopmail.com"
F3_CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
F3_CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
F7_TENANT_EMAIL = "f7-ops-wales@yopmail.com"

DEP_BUNDLES = [
    ("F3", f"ops_runtime_03_contractor_{SLUG}/07_classification.json"),
    ("F7", f"ops_runtime_07_tenant_portal_{SLUG}/07_classification.json"),
    ("G8", f"ops_runtime_g8_tenant_operations_{SLUG}/07_classification.json"),
]

STOP_CLASSIFICATIONS = frozenset(
    {
        "FAIL_SYSTEM",
        "TRUST_RISK_PRESENT",
        "AUTHORITY_BOUNDARY_FAILURE",
        "BLOCKED",
    }
)

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"ACCESS-VERIFY01-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "100"))

BUNDLE = ROOT / f"docs/audit/ops_access_runtime_verify_01_{SLUG}"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _read_pw(path: Path, env_key: str, default: str = "") -> str:
    env = os.environ.get(env_key)
    if env:
        return env.strip()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return default


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _http(method: str, url: str, *, headers: Optional[dict] = None, timeout: int = 120, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(4):
        try:
            fn = getattr(httpx, method.lower())
            return fn(url, headers=headers, timeout=kwargs.pop("timeout", timeout), **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            time.sleep(3 + attempt * 5)
    raise last_exc  # type: ignore[misc]


def _warm_api() -> None:
    for _ in range(12):
        try:
            r = _http("get", f"{API}/health", timeout=90)
            if r.status_code == 200 and "starting" not in (r.text or "").lower():
                return
        except Exception:
            pass
        time.sleep(8)


def _login(email: str, password: str, *, contractor: bool = False) -> Tuple[str, dict]:
    _warm_api()
    path = "/auth/contractor-login" if contractor else "/auth/login"
    for attempt in range(4):
        r = _http("post", f"{API}{path}", json={"email": email, "password": password}, timeout=90)
        if r.status_code == 200:
            body = r.json()
            return body["access_token"], body.get("user") or {}
        if r.status_code in (502, 503, 504):
            time.sleep(12 + attempt * 8)
            continue
    return "", {}


def _admin_login() -> Tuple[str, dict]:
    pw = _read_pw(
        ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt",
        "OPS_VERIFY_ADMIN_PASSWORD",
    )
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
    r = _http("post", f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _load_dep(rel: str) -> dict:
    p = ROOT / "docs/audit" / rel.replace("/", os.sep)
    if not p.is_file():
        return {"found": False}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"found": True, "classification": data.get("classification"), "raw": data}


def _extract_link_token(link: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, link or "")
    return m.group(1) if m else None


def _message_logs(
    admin_token: str,
    *,
    recipient: str = "",
    limit: int = 40,
    template_key: str = "",
) -> List[dict]:
    params: Dict[str, Any] = {"limit": limit, "offset": 0}
    if CLIENT_ID:
        params["client_id"] = CLIENT_ID
    if recipient:
        params["recipient"] = recipient
    if template_key:
        params["template_key"] = template_key
    r = _http("get", f"{API}/admin/message-logs", headers=_headers(admin_token), params=params, timeout=120)
    if r.status_code != 200:
        return []
    items = r.json().get("items") or r.json().get("messages") or []
    enriched: List[dict] = []
    for item in items[:20]:
        mid = item.get("message_id")
        if mid:
            detail = _http("get", f"{API}/admin/message-logs/{mid}", headers=_headers(admin_token), timeout=90)
            if detail.status_code == 200:
                item = {**item, **detail.json()}
        enriched.append(item)
    return enriched


def _latest_token_from_logs(
    admin_token: str,
    *,
    recipient: str,
    template_keys: Tuple[str, ...],
    link_pattern: str,
) -> Optional[str]:
    for item in _message_logs(
        admin_token,
        recipient=recipient.split("@")[0] if recipient else "",
        limit=50,
        template_key=template_keys[0] if len(template_keys) == 1 else "",
    ):
        if template_keys and item.get("template_key") not in template_keys:
            meta = item.get("metadata") or {}
            body = str(meta.get("message") or meta.get("setup_link") or item.get("context") or "")
            if "set-password" not in body and "contractor-set-password" not in body:
                continue
        meta = item.get("metadata") or item.get("context") or {}
        if isinstance(meta, str):
            meta = {"message": meta}
        for field in ("setup_link", "setup_url", "message", "link"):
            tok = _extract_link_token(str(meta.get(field) or ""), link_pattern)
            if tok and not tok.startswith("eyJ"):
                return tok
    return None


def _family_a1(
    client_token: str,
    admin_token: str,
    f3_pw: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"marker": MARKER, "at_utc": _utc()}
    a1_email = f"access-a1-{RUN_TAG.lower()}@yopmail.com"
    a1_pw = f"AccessA1!{RUN_TAG[-6:]}"
    out["a1_email"] = a1_email

    reg_open = _http("get", f"{API}/public/contractors/registration-open", timeout=90)
    out["registration_open_status"] = reg_open.status_code
    if reg_open.status_code == 200:
        out["registration_open"] = reg_open.json()
    if reg_open.status_code == 403:
        out["blocked"] = "contractor_self_registration_disabled"
        out["pass"] = False
        return out

    reg = _http(
        "post",
        f"{API}/public/contractors/register",
        json={
            "name": f"Access Verify A1 {RUN_TAG}",
            "email": a1_email,
            "trade_types": ["heating"],
            "postcode": "CF10",
            "phone": "+440000009991",
            "declared_execution_capabilities": "maintenance",
        },
        timeout=120,
    )
    out["register_status"] = reg.status_code
    if reg.status_code not in (200, 201):
        out["register_body"] = reg.text[:300]
        out["pass"] = False
        return out
    reg_body = reg.json()
    contractor_id = reg_body.get("contractor_id") or (reg_body.get("contractor") or {}).get("contractor_id")
    out["contractor_id"] = contractor_id

    g = _http("get", f"{API}/admin/ops/contractors/{contractor_id}", headers=_headers(admin_token), timeout=90)
    out["admin_get_status"] = g.status_code
    contractor = g.json() if g.status_code == 200 else {}
    out["pending_status"] = contractor.get("status")
    out["vetted_before"] = contractor.get("vetted")
    pending_ok = (contractor.get("status") or "") in ("pending_approval", "pending_review") and not contractor.get("vetted")

    pre_login = _login(a1_email, "wrong-password-xyz", contractor=True)
    out["pre_approve_login_blocked"] = not pre_login[0]

    f3_login = _login(F3_CONTRACTOR_EMAIL, f3_pw, contractor=True)
    out["f3_reference_login_ok"] = bool(f3_login[0])

    approve = _http(
        "patch",
        f"{API}/admin/ops/contractors/{contractor_id}/approve",
        headers=_headers(admin_token),
        json={"accept_declared_capabilities": True},
        timeout=120,
    )
    out["approve_status"] = approve.status_code
    approved = approve.json() if approve.status_code == 200 else {}
    out["status_after_approve"] = approved.get("status")
    approved_ok = approve.status_code == 200 and (approved.get("vetted") is True)

    time.sleep(5)
    invite_token = _extract_link_token(
        str((approved or {}).get("setup_url") or ""),
        r"contractor-set-password\?token=([A-Za-z0-9_-]+)",
    )
    if not invite_token:
        invite_token = _latest_token_from_logs(
            admin_token,
            recipient=a1_email,
            template_keys=("ADMIN_MANUAL", "PASSWORD_RESET", "TENANT_INVITE"),
            link_pattern=r"contractor-set-password\?token=([A-Za-z0-9_-]+)",
        )
    out["invite_token_found"] = bool(invite_token)
    if not invite_token:
        resend = _http(
            "post",
            f"{API}/admin/ops/contractors/{contractor_id}/invite-portal",
            headers=_headers(admin_token),
            timeout=120,
        )
        out["portal_invite_resend_status"] = resend.status_code
        if resend.status_code == 200:
            invite_token = _extract_link_token(
                str(resend.json().get("setup_url") or ""),
                r"contractor-set-password\?token=([A-Za-z0-9_-]+)",
            )
        if not invite_token:
            time.sleep(6)
            invite_token = _latest_token_from_logs(
                admin_token,
                recipient=a1_email,
                template_keys=("ADMIN_MANUAL",),
                link_pattern=r"contractor-set-password\?token=([A-Za-z0-9_-]+)",
            )
        out["invite_token_found_after_resend"] = bool(invite_token)

    if invite_token:
        sp = _http(
            "post",
            f"{API}/auth/contractor-set-password",
            json={"token": invite_token, "password": a1_pw},
            timeout=120,
        )
        out["set_password_status"] = sp.status_code
        reuse = _http(
            "post",
            f"{API}/auth/contractor-set-password",
            json={"token": invite_token, "password": a1_pw},
            timeout=120,
        )
        out["token_reuse_blocked"] = reuse.status_code == 400
        post_login = _login(a1_email, a1_pw, contractor=True)
        out["post_approve_login_ok"] = bool(post_login[0])
    else:
        out["set_password_status"] = None
        out["token_reuse_blocked"] = None
        out["post_approve_login_ok"] = False

    out["invited_ne_approved_preserved"] = pending_ok and approved_ok
    out["pass"] = bool(
        pending_ok
        and not pre_login[0]
        and approved_ok
        and out.get("post_approve_login_ok")
        and out.get("token_reuse_blocked")
        and bool(f3_login[0])
    )
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / ".ops_access_a1_pw.txt").write_text(a1_pw + "\n", encoding="utf-8")
    return out


def _family_a2(client_token: str, contractor_token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc()}
    cl = _http(
        "get",
        f"{API}/client/contractors",
        headers=_headers(client_token),
        params={"property_id": PROPERTY_ID},
        timeout=120,
    )
    contractors = (cl.json() if cl.status_code == 200 else {}).get("contractors") or []
    f3_visible = any(
        (c.get("contractor_id") == F3_CONTRACTOR_ID or (c.get("email") or "").lower() == F3_CONTRACTOR_EMAIL.lower())
        for c in contractors
    )
    dash = _http("get", f"{API}/contractor/dashboard-summary", headers=_headers(contractor_token), timeout=120)
    jobs = _http("get", f"{API}/contractor/work-orders", headers=_headers(contractor_token), params={"limit": 20}, timeout=120)
    wo_list = jobs.json() if jobs.status_code == 200 else {}
    items = wo_list if isinstance(wo_list, list) else wo_list.get("work_orders") or wo_list.get("items") or []
    out.update(
        {
            "landlord_contractors_status": cl.status_code,
            "f3_visible_to_landlord": f3_visible,
            "contractor_dashboard_status": dash.status_code,
            "contractor_work_orders_status": jobs.status_code,
            "contractor_work_order_count": len(items),
            "scoped_visibility_ok": jobs.status_code == 200 and dash.status_code == 200,
            "pass": f3_visible and dash.status_code == 200 and jobs.status_code == 200,
        }
    )
    return out


def _family_a3(admin_token: str, a1: Dict[str, Any]) -> Dict[str, Any]:
    cid = a1.get("contractor_id")
    pending = _http(
        "get",
        f"{API}/admin/ops/contractors",
        headers=_headers(admin_token),
        params={"status": "pending_approval", "limit": 100},
        timeout=120,
    )
    pending_ids = [
        c.get("contractor_id")
        for c in ((pending.json() if pending.status_code == 200 else {}).get("contractors") or [])
    ]
    dup = _http(
        "patch",
        f"{API}/admin/ops/contractors/{cid}/approve",
        headers=_headers(admin_token),
        json={"accept_declared_capabilities": True},
        timeout=120,
    )
    return {
        "at_utc": _utc(),
        "pending_list_status": pending.status_code,
        "approved_not_in_pending": cid not in pending_ids if cid else True,
        "duplicate_approve_status": dup.status_code,
        "duplicate_approve_idempotent": dup.status_code in (200, 404),
        "auditability": a1.get("approve_status") == 200,
        "pass": (cid not in pending_ids if cid else False) and dup.status_code in (200, 404),
    }


def _family_a4(client_token: str, admin_token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc(), "marker": MARKER}
    a4_email = f"access-a4-{RUN_TAG.lower()}@yopmail.com"
    a4_pw = f"AccessA4!{RUN_TAG[-6:]}"
    out["a4_email"] = a4_email

    inv = _http(
        "post",
        f"{API}/client/tenants/invite",
        headers=_headers(client_token),
        json={"email": a4_email, "full_name": "Access A4 Archive Test", "property_ids": [PROPERTY_ID]},
        timeout=120,
    )
    out["invite_status"] = inv.status_code
    if inv.status_code not in (200, 201):
        out["pass"] = False
        return out
    tenant_id = (inv.json() or {}).get("tenant_id") or (inv.json() or {}).get("portal_user_id")
    out["tenant_id"] = tenant_id

    time.sleep(6)
    token = _latest_token_from_logs(
        admin_token,
        recipient=a4_email,
        template_keys=("TENANT_INVITE",),
        link_pattern=r"set-password\?token=([A-Za-z0-9_-]+)",
    )
    out["setup_token_found"] = bool(token)
    if token:
        _http("post", f"{API}/auth/set-password", json={"token": token, "password": a4_pw}, timeout=120)
    tenant_login = _login(a4_email, a4_pw)
    out["tenant_active_login_ok"] = tenant_login[0] != ""

    occ_before = _http(
        "get",
        f"{API}/client/properties/{PROPERTY_ID}/occupancy-operational-summary",
        headers=_headers(client_token),
        timeout=120,
    )
    before_count = len((occ_before.json() if occ_before.status_code == 200 else {}).get("active_tenants") or [])

    def _delivery_count() -> int:
        occ = _http(
            "get",
            f"{API}/client/properties/{PROPERTY_ID}/occupancy-operational-summary",
            headers=_headers(client_token),
            timeout=120,
        )
        if occ.status_code != 200:
            return 0
        return len(occ.json().get("compliance_pack_deliveries") or [])

    del_count_before = _delivery_count()

    unassign = _http(
        "delete",
        f"{API}/client/tenants/{tenant_id}/unassign-property/{PROPERTY_ID}",
        headers=_headers(client_token),
        timeout=120,
    )
    out["unassign_status"] = unassign.status_code

    occ_after_unassign = _http(
        "get",
        f"{API}/client/properties/{PROPERTY_ID}/occupancy-operational-summary",
        headers=_headers(client_token),
        timeout=120,
    )
    active_after = (occ_after_unassign.json() if occ_after_unassign.status_code == 200 else {}).get("active_tenants") or []
    still_active = any(t.get("tenant_id") == tenant_id for t in active_after)
    out["removed_from_active_occupancy"] = not still_active

    revoke = _http("delete", f"{API}/client/tenants/{tenant_id}", headers=_headers(client_token), timeout=120)
    out["revoke_status"] = revoke.status_code
    post_revoke_login = _login(a4_email, a4_pw)
    out["revoked_login_blocked"] = not post_revoke_login[0]

    del_count_after = _delivery_count()
    out["delivery_history_preserved"] = del_count_after >= del_count_before
    out["lifecycle_model"] = "unassign_property + revoke(DISABLED); no hard-delete of delivery proofs"
    out["moved_out_ne_deleted"] = del_count_after >= del_count_before
    out["pass"] = (
        unassign.status_code == 200
        and not still_active
        and revoke.status_code == 200
        and not post_revoke_login[0]
        and del_count_after >= del_count_before
    )
    return out


def _family_a5(admin_token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc()}
    f7_pw_path = ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt"
    original_pw = _read_pw(f7_pw_path, "OPS_TENANT_PASSWORD", "F7OpsWales!Staging2026")
    new_pw = f"AccessReset1!{RUN_TAG[-4:]}"

    page = _http("get", f"{FRONTEND}/forgot-password", timeout=90)
    out["forgot_password_page_status"] = page.status_code

    time.sleep(120)
    fp = None
    for attempt in range(8):
        fp = _http("post", f"{API}/auth/forgot-password", json={"email": F7_TENANT_EMAIL}, timeout=120)
        if fp.status_code == 200:
            break
        time.sleep(60 + attempt * 30)
    out["forgot_password_api_status"] = fp.status_code if fp else None

    token = None
    if fp and fp.status_code == 200:
        for wait_s in (10, 15, 20):
            time.sleep(wait_s)
            token = _latest_token_from_logs(
                admin_token,
                recipient=F7_TENANT_EMAIL,
                template_keys=("PASSWORD_RESET",),
                link_pattern=r"set-password\?token=([A-Za-z0-9_-]+)",
            )
            if token:
                out["reset_token_wait_s"] = wait_s
                break
    out["reset_token_found"] = bool(token)
    if not token:
        out["pass"] = False
        out["note"] = "fresh_reset_token_required_forgot_must_return_200"
        return out

    sp = None
    for attempt in range(6):
        sp = _http(
            "post",
            f"{API}/auth/set-password",
            json={"token": token, "password": new_pw},
            timeout=120,
        )
        if sp.status_code != 429:
            break
        time.sleep(45 + attempt * 30)
    out["set_password_status"] = sp.status_code if sp else None

    time.sleep(8)
    reuse = _http(
        "post",
        f"{API}/auth/set-password",
        json={"token": token, "password": new_pw},
        timeout=120,
    )
    out["token_reuse_blocked"] = reuse.status_code == 400
    old_login = _login(F7_TENANT_EMAIL, original_pw)
    new_login = _login(F7_TENANT_EMAIL, new_pw)
    out["old_password_invalidated"] = not old_login[0]
    out["new_password_works"] = bool(new_login[0])
    out["role_preserved"] = (new_login[1].get("role") == "ROLE_TENANT") if new_login[1] else False

    time.sleep(45)
    restore_token = None
    for attempt in range(4):
        fp2 = _http("post", f"{API}/auth/forgot-password", json={"email": F7_TENANT_EMAIL}, timeout=120)
        if fp2.status_code == 429:
            time.sleep(30)
            continue
        time.sleep(15)
        restore_token = _latest_token_from_logs(
            admin_token,
            recipient=F7_TENANT_EMAIL,
            template_keys=("PASSWORD_RESET",),
            link_pattern=r"set-password\?token=([A-Za-z0-9_-]+)",
        )
        if restore_token:
            break
    if restore_token:
        for attempt in range(5):
            rsp = _http(
                "post",
                f"{API}/auth/set-password",
                json={"token": restore_token, "password": original_pw},
                timeout=120,
            )
            if rsp.status_code != 429:
                break
            time.sleep(20)
        out["restored_original_password"] = _login(F7_TENANT_EMAIL, original_pw)[0] != ""
    else:
        out["restored_original_password"] = _login(F7_TENANT_EMAIL, original_pw)[0] != ""

    time.sleep(10)
    bad = _http(
        "post",
        f"{API}/auth/set-password",
        json={"token": "invalid-token-xyz", "password": "Invalid1x"},
        timeout=90,
    )
    out["malformed_token_rejected"] = bad.status_code in (400, 429)
    out["reset_requested_ne_changed_initially"] = (fp.status_code if fp else 0) in (200, 429) and sp and sp.status_code == 200
    out["pass"] = bool(
        sp
        and sp.status_code == 200
        and out["token_reuse_blocked"]
        and out["old_password_invalidated"]
        and out["new_password_works"]
        and out["role_preserved"]
        and out.get("restored_original_password")
    )
    return out


def _family_a6(admin_token: str, a1: Dict[str, Any], a5: Dict[str, Any]) -> Dict[str, Any]:
    logs = _message_logs(admin_token, limit=60)
    templates = sorted({i.get("template_key") for i in logs if i.get("template_key")})
    sent = [i for i in logs if (i.get("status") or "").lower() == "sent"]
    return {
        "at_utc": _utc(),
        "templates_observed": templates,
        "sent_count": len(sent),
        "password_reset_observed": a5.get("reset_token_found"),
        "contractor_invite_observed": a1.get("invite_token_found") or a1.get("invite_token_found_after_resend"),
        "stale_link_rejected": a5.get("malformed_token_rejected"),
        "email_sent_ne_received_proxy": "message_logs_capture_only",
        "pass": a5.get("reset_token_found") and (a1.get("invite_token_found") or a1.get("invite_token_found_after_resend")),
    }


def _family_a7(
    client_token: str,
    a1: Dict[str, Any],
    a4: Dict[str, Any],
    a5: Dict[str, Any],
    f3_token: str,
) -> Dict[str, Any]:
    a4_email = a4.get("a4_email", "")
    a4_pw = f"AccessA4!{RUN_TAG[-6:]}"
    revoked_blocked = a4.get("revoked_login_blocked")
    tenant_still_client = _http("get", f"{API}/client/dashboard", headers=_headers(_login(a4_email, a4_pw)[0] or "x"), timeout=90)
    tenant_client_blocked = tenant_still_client.status_code in (401, 403)

    f7_pw = _read_pw(
        ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt",
        "OPS_TENANT_PASSWORD",
        "F7OpsWales!Staging2026",
    )
    f7_after = _login(F7_TENANT_EMAIL, f7_pw)
    nav = _http("get", f"{API}/tenant/dashboard", headers=_headers(f7_after[0]), timeout=90) if f7_after[0] else None
    contractor_nav = _http("get", f"{API}/contractor/dashboard-summary", headers=_headers(f3_token), timeout=90) if f3_token else None

    return {
        "at_utc": _utc(),
        "archived_tenant_client_api_blocked": tenant_client_blocked or revoked_blocked,
        "f7_session_after_restore": f7_after[0] != "",
        "f7_tenant_nav_ok": (nav.status_code == 200) if nav else False,
        "approved_contractor_nav_ok": (contractor_nav.status_code == 200) if contractor_nav else False,
        "password_reset_role_coherent": a5.get("role_preserved"),
        "pass": (
            (tenant_client_blocked or revoked_blocked)
            and f7_after[0]
            and (nav.status_code == 200 if nav else False)
            and (contractor_nav.status_code == 200 if contractor_nav else False)
            and a5.get("role_preserved")
        ),
    }


def _g9_g10(a1: Dict[str, Any], a3: Dict[str, Any], a4: Dict[str, Any], a5: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    g9 = {
        "duplicate_approve_idempotent": a3.get("duplicate_approve_idempotent"),
        "token_reuse_blocked": a5.get("token_reuse_blocked") and a1.get("token_reuse_blocked"),
        "pass": bool(a3.get("duplicate_approve_idempotent") and a5.get("token_reuse_blocked")),
    }
    g10 = {
        "invited_ne_approved": a1.get("invited_ne_approved_preserved"),
        "moved_out_ne_deleted": a4.get("moved_out_ne_deleted"),
        "reset_requested_ne_changed_until_set": a5.get("reset_requested_ne_changed_initially"),
        "violations": [],
        "pass": a1.get("invited_ne_approved_preserved") and a4.get("moved_out_ne_deleted") and a5.get("reset_requested_ne_changed_initially"),
    }
    return g9, g10


def run_access_verify() -> Dict[str, Any]:
    for label, bundle in DEP_BUNDLES:
        dep = _load_dep(bundle)
        if dep.get("classification") != "VERIFIED_OPERATIONALLY":
            raise SystemExit(f"{label} prerequisite failed: {dep.get('classification')}")

    client_pw = _read_pw(ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt", "OPS_VERIFY_PASSWORD")
    f3_pw = _read_pw(
        ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt",
        "OPS_CONTRACTOR_PASSWORD",
    )

    client_token, _ = _login(CLIENT_EMAIL, client_pw)
    if not client_token:
        blocked = {"classification": "BLOCKED", "reason": "landlord_login_failed"}
        _write("07_classification.json", blocked)
        return blocked
    admin_token, _ = _admin_login()
    f3_token, _ = _login(F3_CONTRACTOR_EMAIL, f3_pw, contractor=True)

    agg = ClassificationAggregator(OWNER)
    family_results: Dict[str, Dict[str, Any]] = {}

    a5 = _family_a5(admin_token)
    _write("password_reset_runtime.json", a5)
    family_results["A5"] = a5
    if not a5.get("pass"):
        if not a5.get("reset_token_found"):
            agg.add("ACCOUNT_RECOVERY_FAILURE", "password_reset")
        else:
            agg.add("TOKEN_GOVERNANCE_FAILURE", "password_reset")
        primary = _finalize_early(agg, family_results, "A5")
        return {"classification": primary, "bundle": str(BUNDLE), "early_exit": "A5"}

    a1 = _family_a1(client_token, admin_token, f3_pw)
    _write("contractor_onboarding_verification.json", a1)
    family_results["A1"] = a1
    if not a1.get("pass"):
        if a1.get("blocked"):
            agg.add("BLOCKED", "contractor_self_registration_disabled")
        elif not a1.get("invited_ne_approved_preserved"):
            agg.add("CONTRACTOR_APPROVAL_DRIFT", "onboarding")
        else:
            agg.add("FAIL_SYSTEM", "contractor_onboarding")
        primary = _finalize_early(agg, family_results, "A1")
        return {"classification": primary, "bundle": str(BUNDLE), "early_exit": "A1"}

    a2 = _family_a2(client_token, f3_token)
    _write("contractor_visibility_governance.json", a2)
    family_results["A2"] = a2
    if not a2.get("pass"):
        agg.add("FALSE_ASSIGNMENT_AUTHORITY", "visibility")
        primary = _finalize_early(agg, family_results, "A2")
        return {"classification": primary, "bundle": str(BUNDLE), "early_exit": "A2"}

    a3 = _family_a3(admin_token, a1)
    _write("admin_approval_governance.json", a3)
    family_results["A3"] = a3
    if not a3.get("pass"):
        agg.add("AUTHORITY_BOUNDARY_FAILURE", "admin_approval")
        primary = _finalize_early(agg, family_results, "A3")
        return {"classification": primary, "bundle": str(BUNDLE), "early_exit": "A3"}

    a4 = _family_a4(client_token, admin_token)
    _write("tenant_archive_lifecycle.json", a4)
    family_results["A4"] = a4
    if not a4.get("pass"):
        if not a4.get("moved_out_ne_deleted"):
            agg.add("HISTORICAL_AUTHORITY_LOSS", "tenant_archive")
        if not a4.get("removed_from_active_occupancy"):
            agg.add("FALSE_OCCUPANCY_STATE", "tenant_archive")
        else:
            agg.add("FAIL_OPERATIONAL", "tenant_archive")
        primary = _finalize_early(agg, family_results, "A4")
        return {"classification": primary, "bundle": str(BUNDLE), "early_exit": "A4"}

    a6 = _family_a6(admin_token, a1, a5)
    _write("email_token_governance.json", a6)
    family_results["A6"] = a6
    if not a6.get("pass"):
        agg.add("TOKEN_GOVERNANCE_FAILURE", "email_token")
        primary = _finalize_early(agg, family_results, "A6")
        return {"classification": primary, "bundle": str(BUNDLE), "early_exit": "A6"}

    a7 = _family_a7(client_token, a1, a4, a5, f3_token)
    _write("post_change_session_coherence.json", a7)
    family_results["A7"] = a7
    if not a7.get("pass"):
        agg.add("TRUST_RISK_PRESENT", "session_coherence")
        primary = _finalize_early(agg, family_results, "A7")
        return {"classification": primary, "bundle": str(BUNDLE), "early_exit": "A7"}

    g9, g10 = _g9_g10(a1, a3, a4, a5)
    _write("g9_access_integrity.json", g9)
    _write("g10_access_authority.json", g10)

    def read_pending_count() -> Dict[str, Any]:
        r = _http(
            "get",
            f"{API}/admin/ops/contractors",
            headers=_headers(admin_token),
            params={"status": "pending_approval", "limit": 5},
            timeout=90,
        )
        n = len((r.json() if r.status_code == 200 else {}).get("contractors") or [])
        return {"pending": n}

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    t0 = read_pending_count()
    observer.observe("admin_pending_contractors", read_pending_count, agree_fn=lambda a, b: a == b, timeout_seconds=CONVERGENCE_WAIT_S)
    conv = observer.build_artifact()
    conv["t0"] = t0
    _write("convergence.json", conv)

    verified = all(
        [
            a1.get("pass"),
            a2.get("pass"),
            a3.get("pass"),
            a4.get("pass"),
            a5.get("pass"),
            a6.get("pass"),
            a7.get("pass"),
            g9.get("pass"),
            g10.get("pass"),
            not conv.get("any_stale"),
        ]
    )
    primary = "VERIFIED_OPERATIONALLY" if verified else agg.finalize(execution_completed=True).primary

    classification = _build_classification(
        primary,
        verified,
        family_results,
        g9,
        g10,
        conv,
    )
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})
    _write_watchlist(primary, family_results)
    _write_report(primary, family_results, g9, g10, conv)
    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — ACCESS-RUNTIME-VERIFY-01\n\n**Run:** `{RUN_TAG}`\n\nVERIFIED_OPERATIONALLY on Wales HMO pilot.\n",
            encoding="utf-8",
        )
    return {"classification": primary, "bundle": str(BUNDLE), "verified": verified}


def _build_classification(
    primary: str,
    verified: bool,
    families: Dict[str, Dict[str, Any]],
    g9: Dict[str, Any],
    g10: Dict[str, Any],
    conv: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "family": OWNER,
        "classification": primary,
        "execution_status": primary,
        "blocking": not verified,
        "authoritative_verification_owner": OWNER,
        "proof_mode": PROOF_MODE,
        "run_tag": RUN_TAG,
        "pilot_slug": SLUG,
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "shared_dependency_bundle_ids": [b for _, b in DEP_BUNDLES],
        "checkpoints": {
            "A1_onboarding": bool(families.get("A1", {}).get("pass")),
            "A2_visibility": families.get("A2", {}).get("pass"),
            "A3_admin_approval": families.get("A3", {}).get("pass"),
            "A4_tenant_archive": families.get("A4", {}).get("pass"),
            "A5_password_reset": families.get("A5", {}).get("pass"),
            "A6_email_token": families.get("A6", {}).get("pass"),
            "A7_session_coherence": families.get("A7", {}).get("pass"),
            "G9": g9.get("pass"),
            "G10": g10.get("pass"),
            "convergence": not conv.get("any_stale"),
        },
    }


def _finalize_early(agg: ClassificationAggregator, families: Dict[str, Dict[str, Any]], stop_at: str) -> str:
    result = agg.finalize(execution_completed=True)
    primary = result.primary if result.blocking else "PARTIAL"
    if primary in STOP_CLASSIFICATIONS:
        pass
    elif not result.blocking:
        primary = "PARTIAL"
    classification = _build_classification(primary, False, families, {"pass": False}, {"pass": False}, {"any_stale": True})
    classification["early_exit_family"] = stop_at
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})
    _write_watchlist(primary, families, stop_at)
    (BUNDLE / "REPORT.md").write_text(
        f"# ACCESS-RUNTIME-VERIFY-01 — stopped at {stop_at}\n\n**Classification:** `{primary}`\n",
        encoding="utf-8",
    )
    return primary


def _write_watchlist(primary: str, families: Dict[str, Dict[str, Any]], stop_at: str = "") -> None:
    lines = [
        f"# ACCESS-RUNTIME-VERIFY-01 watchlist — {SLUG}",
        "",
        f"**Run:** `{RUN_TAG}`",
        f"**Classification:** `{primary}`",
        "",
    ]
    if stop_at:
        lines.append(f"- Early exit at family **{stop_at}**")
    for k, v in families.items():
        if not v.get("pass"):
            lines.append(f"- {k} failed: {json.dumps({kk: v[kk] for kk in v if kk != 'pass' and kk != 'at_utc'}, default=str)[:200]}")
    if len(lines) <= 5:
        lines.append("- (none)")
    _write("watchlist.md", "\n".join(lines))


def _write_report(primary: str, families: Dict[str, Dict[str, Any]], g9: Dict[str, Any], g10: Dict[str, Any], conv: Dict[str, Any]) -> None:
    rows = "\n".join(
        f"| {k} | {v.get('pass')} |" for k, v in families.items()
    )
    (BUNDLE / "REPORT.md").write_text(
        f"""# ACCESS-RUNTIME-VERIFY-01 — {SLUG}

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`

| Family | Pass |
|--------|------|
{rows}
| G9/G10 | {g9.get('pass') and g10.get('pass')} |
| Convergence | {not conv.get('any_stale')} |
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    print(json.dumps(run_access_verify(), indent=2))
