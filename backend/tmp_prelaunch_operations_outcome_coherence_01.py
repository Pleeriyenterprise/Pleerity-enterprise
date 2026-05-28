#!/usr/bin/env python3
"""
PRELAUNCH-OPERATIONS-OUTCOME-COHERENCE-01 — baseline runtime coherence audit.

Stability gate + cross-surface CTA contradiction matrix + invariant mapping.
No remediation — audit artifacts only.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
PROGRAMME = "PRELAUNCH-OPERATIONS-OUTCOME-COHERENCE-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-COHERENCE-01-{RUN_TAG}"

DEFAULT_CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
DEFAULT_PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"
CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
CLIENT_EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
PW_PATH = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_temp_pw.txt"
CONTRACTOR_PW_PATH = ROOT / f"docs/audit/ops_runtime_03_contractor_{DEFAULT_SLUG}/.ops_contractor_temp_pw.txt"
TENANT_PW_PATH = ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{DEFAULT_SLUG}/.ops_tenant_temp_pw.txt"

OUT = ROOT / "docs" / "audit" / "prelaunch_operations_outcome_coherence_01"
SHOT = OUT / "screenshots"

ISSUE_TERMINAL = frozenset({"closed", "cancelled", "resolved"})
WO_TERMINAL = frozenset({"COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"})

START_CTA_PATTERNS = re.compile(
    r"(start|create|log|schedule|arrange|new)\s+(inspection|maintenance|job|issue|work)",
    re.I,
)
CONTINUATION_PATTERNS = re.compile(
    r"(view|continue|awaiting|already|in progress|assigned|quote|verify|review|contact|open)",
    re.I,
)


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def load_inventory(
    path: str,
    token: str,
    *,
    list_key: str,
    params: Optional[dict] = None,
    retries: int = 3,
) -> Tuple[List[dict], int, List[Dict[str, Any]]]:
    """Load paginated list with retries; returns rows, total, attempt log."""
    attempts: List[Dict[str, Any]] = []
    params = dict(params or {})
    params["limit"] = min(int(params.get("limit") or 200), 200)
    for n in range(retries):
        row = call("GET", path, token, params=params, timeout=90.0)
        attempts.append({"attempt": n + 1, "status": row["status"], "ok": row["ok"], "elapsed_ms": row["elapsed_ms"]})
        if row["ok"] and isinstance(row.get("body"), dict):
            body = row["body"]
            items = body.get(list_key) or []
            total = int(body.get("total") or len(items))
            if items or total == 0:
                return items, total, attempts
        time.sleep(1.5)
    return [], 0, attempts


def call(
    method: str,
    path: str,
    token: Optional[str] = None,
    *,
    params: Optional[dict] = None,
    body: Optional[dict] = None,
    timeout: float = 45.0,
) -> Dict[str, Any]:
    headers = h(token) if token else {}
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.request(
                method,
                f"{API}{path}",
                headers=headers,
                params=params,
                json=body,
            )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        try:
            parsed = r.json()
        except Exception:
            parsed = (r.text or "")[:800]
        return {
            "method": method,
            "path": path,
            "status": r.status_code,
            "ok": 200 <= r.status_code < 300,
            "elapsed_ms": elapsed_ms,
            "body": parsed,
        }
    except httpx.TimeoutException as exc:
        return {
            "method": method,
            "path": path,
            "status": 599,
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            "body": f"timeout: {exc}",
        }


def login(email: str, password: str, contractor: bool = False) -> str:
    path = "/auth/contractor-login" if contractor else "/auth/login"
    r = httpx.post(f"{API}{path}", json={"email": email, "password": password}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def read_pw(path: Path, env_key: str, fallback: str) -> str:
    if os.environ.get(env_key):
        return os.environ[env_key]
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return fallback


# --- Frontend parity: risk signal primary key (primaryActionResolver.js) ---


def resolve_risk_signal_primary_key(
    signal: dict,
    *,
    has_maintenance_workflows: bool = True,
    has_compliance_engine: bool = True,
) -> Dict[str, str]:
    cont = signal.get("operational_continuation") or {}
    if cont.get("has_active_lineage") and cont.get("continuation_cta"):
        cta = cont["continuation_cta"]
        return {
            "key": cta.get("key") or "view_workflow",
            "label": cta.get("label") or "View workflow",
            "continuation": True,
        }
    actions = signal.get("suggested_actions") or ["create_issue", "create_work_order"]
    if not isinstance(actions, list):
        actions = ["create_issue", "create_work_order"]
    want_inspection = "schedule_inspection" in actions and has_maintenance_workflows
    if want_inspection and has_compliance_engine:
        return {"key": "compliance_inspection", "label": "Start inspection job"}
    if want_inspection and not has_compliance_engine:
        return {"key": "log_inspection_issue", "label": "Log maintenance issue"}
    if "create_work_order" in actions:
        return {"key": "maintenance_job", "label": "Start maintenance job"}
    if "create_issue" in actions:
        return {"key": "maintenance_issue", "label": "Log maintenance issue"}
    return {"key": "review", "label": "Review risk signal"}


def classify_cta_intent(label: str) -> str:
    if not label:
        return "unknown"
    if START_CTA_PATTERNS.search(label):
        return "start_create"
    if CONTINUATION_PATTERNS.search(label):
        return "continuation"
    return "other"


def normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip().lower())


# --- Stability gate ---


def stability_gate() -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": utc(), "checks": [], "pass": False}
    health_runs = []
    for i in range(3):
        row = call("GET", "/health")
        health_runs.append({"attempt": i + 1, "status": row["status"], "elapsed_ms": row["elapsed_ms"]})
        time.sleep(0.8)
    version = call("GET", "/version")
    ver_body = version.get("body") if isinstance(version.get("body"), dict) else {}
    commit = ver_body.get("commit") or ver_body.get("git_commit") or ver_body.get("version")
    auth_probe = call("POST", "/auth/login", body={"email": "probe@invalid.local", "password": "x"})
    auth_reachable = auth_probe["status"] in (400, 401, 422, 403)
    try:
        client_pw = read_pw(PW_PATH, "OPS_VERIFY_PASSWORD", "OpsVerify01!StagingWalk")
        login(CLIENT_EMAIL, client_pw)
        client_login_ok = True
    except Exception as exc:
        client_login_ok = False
        client_login_err = str(exc)
    else:
        client_login_err = None

    health_ok = all(r["status"] == 200 for r in health_runs)
    out["health_runs"] = health_runs
    out["version"] = {"status": version["status"], "commit": commit, "body": ver_body}
    out["auth_endpoint"] = {"status": auth_probe["status"], "reachable_without_502_503": auth_probe["status"] not in (502, 503)}
    out["client_login"] = {"ok": client_login_ok, "error": client_login_err}
    out["pass"] = health_ok and version["status"] == 200 and auth_reachable and client_login_ok
    out["checks"] = [
        {"name": "health_200_x3", "pass": health_ok},
        {"name": "version_200", "pass": version["status"] == 200},
        {"name": "auth_reachable", "pass": auth_reachable},
        {"name": "client_login", "pass": client_login_ok},
    ]
    return out


# --- Cross-surface projections ---


def load_entitlements(client_tok: str) -> Dict[str, bool]:
    ent = call("GET", "/client/entitlements", client_tok)
    feats = (ent.get("body") or {}).get("features") or {} if ent["ok"] else {}
    return {
        "maintenance_workflows": bool((feats.get("maintenance_workflows") or {}).get("enabled")),
        "predictive_maintenance": bool((feats.get("predictive_maintenance") or {}).get("enabled")),
        "compliance_engine": bool((feats.get("compliance_engine") or feats.get("compliance_workflows") or {}).get("enabled")),
    }


def build_lineage_graph(
    signals: List[dict],
    issues: List[dict],
    work_orders: List[dict],
    *,
    pilot_property_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    issues_by_signal: Dict[str, List[dict]] = {}
    wos_by_signal: Dict[str, List[dict]] = {}
    issues_by_id: Dict[str, dict] = {}
    wos_by_id: Dict[str, dict] = {}

    for i in issues:
        issues_by_id[str(i.get("issue_id") or "")] = i
        sid = (i.get("risk_signal_id") or "").strip()
        if sid:
            issues_by_signal.setdefault(sid, []).append(i)
    for wo in work_orders:
        wos_by_id[str(wo.get("work_order_id") or "")] = wo
        sid = (wo.get("risk_signal_id") or "").strip()
        if sid:
            wos_by_signal.setdefault(sid, []).append(wo)

    clusters: List[Dict[str, Any]] = []
    seen_signal_ids: Set[str] = set()

    def active_issue(i: dict) -> bool:
        return (i.get("status") or "").lower() not in ISSUE_TERMINAL

    def active_wo(w: dict) -> bool:
        return (w.get("status") or "").upper() not in WO_TERMINAL

    for s in signals:
        sid = s.get("signal_id")
        if not sid:
            continue
        seen_signal_ids.add(sid)
        linked_issues = issues_by_signal.get(sid, [])
        linked_wos = wos_by_signal.get(sid, [])
        active_issues = [i for i in linked_issues if active_issue(i)]
        active_wos = [w for w in linked_wos if active_wo(w)]
        clusters.append(
            {
                "signal_id": sid,
                "risk_type": s.get("risk_type"),
                "signal_status": s.get("status"),
                "property_id": s.get("property_id"),
                "suggested_actions": s.get("suggested_actions"),
                "recommended_action": s.get("recommended_action"),
                "propagation": s.get("propagation"),
                "linked_issue_ids": [i.get("issue_id") for i in linked_issues],
                "linked_work_order_ids": [w.get("work_order_id") for w in linked_wos],
                "active_issue_ids": [i.get("issue_id") for i in active_issues],
                "active_work_order_ids": [w.get("work_order_id") for w in active_wos],
                "has_active_lineage": bool(active_issues or active_wos),
            }
        )

    # Orphan issues / wos without signal in list
    for i in issues:
        if not i.get("risk_signal_id") and active_issue(i):
            clusters.append(
                {
                    "signal_id": None,
                    "orphan_issue_id": i.get("issue_id"),
                    "has_active_lineage": bool(i.get("linked_work_order_id") or i.get("work_order_id")),
                    "active_issue_ids": [i.get("issue_id")],
                    "active_work_order_ids": [
                        x
                        for x in [i.get("linked_work_order_id"), i.get("work_order_id")]
                        if x
                    ],
                }
            )
    return clusters


def project_cluster_surfaces(
    cluster: dict,
    client_tok: str,
    contractor_tok: str,
    tenant_tok: str,
    entitlements: Dict[str, bool],
    cc_urgent: List[dict],
    signals_by_id: Dict[str, dict],
) -> Dict[str, Any]:
    surfaces: Dict[str, Any] = {}
    sid = cluster.get("signal_id")
    signal = signals_by_id.get(sid) if sid else None

    if signal:
        primary = resolve_risk_signal_primary_key(
            signal,
            has_maintenance_workflows=entitlements.get("maintenance_workflows", True),
            has_compliance_engine=entitlements.get("compliance_engine", True),
        )
        sug = call("GET", f"/client/maintenance/risk-signals/{sid}/suggested-actions", client_tok)
        surfaces["risk_signals"] = {
            "primary_cta": primary,
            "primary_intent": classify_cta_intent(primary["label"]),
            "suggested_actions_api": sug.get("body"),
            "signal_status": signal.get("status"),
            "recommended_action_stored": signal.get("recommended_action"),
        }

    for iid in cluster.get("active_issue_ids") or []:
        ir = call("GET", f"/client/maintenance/issues/{iid}", client_tok)
        body = ir.get("body") if isinstance(ir.get("body"), dict) else {}
        wo_id = body.get("linked_work_order_id") or body.get("work_order_id")
        cont = body.get("operational_continuation") or {}
        issue_ctas = []
        if cont.get("has_active_lineage") and cont.get("continuation_cta"):
            cta = cont["continuation_cta"]
            issue_ctas.append(
                {
                    "id": cta.get("key") or "view_workflow",
                    "label": cta.get("label") or "View workflow",
                    "intent": "continuation",
                }
            )
        elif (body.get("status") or "").lower() not in ISSUE_TERMINAL and not wo_id:
            issue_ctas.append({"id": "create_work_order", "label": "Create work order", "intent": "start_create"})
        elif wo_id:
            issue_ctas.append({"id": "view_linked_job", "label": f"View job {wo_id}", "intent": "continuation"})
        surfaces.setdefault("issues", []).append(
            {
                "issue_id": iid,
                "status": body.get("status"),
                "linked_work_order_id": wo_id,
                "ctas": issue_ctas,
                "issue_resolution_hint": body.get("issue_resolution_hint"),
            }
        )

    for wid in cluster.get("active_work_order_ids") or []:
        # Maintenance list projection
        wr = call("GET", f"/client/maintenance/work-orders/{wid}", client_tok)
        wbody = wr.get("body") if isinstance(wr.get("body"), dict) else {}
        # Canonical job projection with next_actions
        jr = call("GET", f"/jobs/{wid}", client_tok)
        jbody = jr.get("body") if isinstance(jr.get("body"), dict) else {}
        next_actions = jbody.get("next_actions") or []
        surfaces.setdefault("jobs", []).append(
            {
                "work_order_id": wid,
                "status": wbody.get("status") or jbody.get("status"),
                "canonical_status": jbody.get("job_status") or jbody.get("canonical_status"),
                "contractor_id": wbody.get("contractor_id") or jbody.get("contractor_id"),
                "operational_exception": wbody.get("operational_exception") or jbody.get("operational_exception"),
                "next_actions": [
                    {"id": a.get("id"), "label": a.get("label"), "intent": classify_cta_intent(a.get("label") or "")}
                    for a in next_actions
                    if isinstance(a, dict)
                ],
                "maintenance_list_cta": "View job" if wid else None,
            }
        )
        cr = call("GET", f"/contractor/work-orders/{wid}", contractor_tok)
        cbody = cr.get("body") if isinstance(cr.get("body"), dict) else {}
        c_next = cbody.get("next_actions") or []
        surfaces.setdefault("contractor", []).append(
            {
                "work_order_id": wid,
                "next_actions": [
                    {"id": a.get("id"), "label": a.get("label"), "intent": classify_cta_intent(a.get("label") or "")}
                    for a in c_next
                    if isinstance(a, dict)
                ],
            }
        )

    # Command centre rows referencing this cluster
    refs = set()
    for x in cluster.get("active_work_order_ids") or []:
        refs.add(str(x))
    for x in cluster.get("active_issue_ids") or []:
        refs.add(str(x))
    if sid:
        refs.add(str(sid))
    cc_rows = []
    for row in cc_urgent:
        blob = json.dumps(row, default=str)
        if any(r and r in blob for r in refs):
            cc_rows.append(
                {
                    "title": row.get("title") or row.get("headline"),
                    "primary_action_label": row.get("primary_action_label") or row.get("recommended_action_label"),
                    "primary_action_url": row.get("primary_action_url") or row.get("recommended_url"),
                    "intent": classify_cta_intent(
                        row.get("primary_action_label") or row.get("recommended_action_label") or ""
                    ),
                }
            )
    surfaces["command_centre"] = cc_rows

    # Tenant surface: issues/requests mentioning property
    tr = call("GET", "/tenant/requests", tenant_tok, params={"limit": 50})
    treqs = (tr.get("body") or {}).get("requests") or [] if tr["ok"] else []
    tenant_rows = [
        r
        for r in treqs
        if isinstance(r, dict)
        and (
            r.get("property_id") == DEFAULT_PID
            or any(
                str(x) in json.dumps(r, default=str)
                for x in (cluster.get("active_issue_ids") or []) + (cluster.get("active_work_order_ids") or [])
            )
        )
    ]
    surfaces["tenant"] = [
        {
            "request_id": r.get("request_id") or r.get("id"),
            "type": r.get("type") or r.get("request_type"),
            "status": r.get("status"),
        }
        for r in tenant_rows[:5]
    ]

    return surfaces


def probe_backend_rejection(cluster: dict, client_tok: str) -> List[Dict[str, Any]]:
    """Class 4: encouraged start action that backend rejects."""
    probes: List[Dict[str, Any]] = []
    sid = cluster.get("signal_id")
    if sid and cluster.get("has_active_lineage"):
        for action, path_tpl in (
            ("create_work_order", f"/client/maintenance/risk-signals/{sid}/create-work-order"),
            ("create_issue", f"/client/maintenance/risk-signals/{sid}/create-issue"),
        ):
            r = call("POST", path_tpl, client_tok, body={})
            body = r.get("body") if isinstance(r.get("body"), dict) else {}
            replay = bool(body.get("idempotent_replay") or body.get("operational_continuation", {}).get("has_active_lineage"))
            duplicate_mint = (
                r["status"] == 200
                and not replay
                and body.get("work_order_id")
                and body.get("work_order_id") not in (cluster.get("active_work_order_ids") or [])
            )
            probes.append(
                {
                    "probe": f"risk_signal_{action}",
                    "path": path_tpl,
                    "status": r["status"],
                    "rejected": r["status"] in (400, 409, 422),
                    "idempotent_replay": replay,
                    "duplicate_mint": duplicate_mint,
                    "body_excerpt": str(r.get("body"))[:400],
                }
            )
    for iid in cluster.get("active_issue_ids") or []:
        r = call("POST", f"/client/maintenance/issues/{iid}/create-work-order", client_tok)
        probes.append(
            {
                "probe": "issue_create_work_order",
                "issue_id": iid,
                "status": r["status"],
                "rejected": r["status"] in (400, 409, 422),
                "idempotent_replay": r["status"] == 200 and isinstance(r.get("body"), dict) and r["body"].get("work_order_id"),
                "body_excerpt": str(r.get("body"))[:400],
            }
        )
    return probes


def detect_contradictions(
    cluster: dict,
    surfaces: dict,
    backend_probes: List[dict],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    has_active = cluster.get("has_active_lineage")
    risk = surfaces.get("risk_signals") or {}
    risk_primary = risk.get("primary_cta") or {}
    risk_intent = risk.get("primary_intent") or classify_cta_intent(risk_primary.get("label", ""))

    # Class 1 & 2: duplicate invitation / continuation blindness
    if has_active and risk_intent == "start_create":
        findings.append(
            {
                "class": "duplicate_workflow_invitation",
                "severity": "high",
                "detail": "Risk signal primary CTA is start/create while active lineage exists",
                "risk_primary": risk_primary,
                "active_work_order_ids": cluster.get("active_work_order_ids"),
                "active_issue_ids": cluster.get("active_issue_ids"),
                "lineage_via_property_overlap": cluster.get("lineage_via_property_overlap"),
            }
        )
    if cluster.get("lineage_via_property_overlap") and risk_intent == "start_create":
        findings.append(
            {
                "class": "duplicate_workflow_invitation",
                "severity": "high",
                "detail": "Property has active operational work but risk signal still offers fresh-start CTA (lineage not propagated)",
                "risk_type": cluster.get("risk_type"),
                "property_active_work_order_ids": cluster.get("property_active_work_order_ids"),
            }
        )
    if has_active and risk_intent == "start_create":
        findings.append(
            {
                "class": "continuation_blindness",
                "severity": "high",
                "detail": "Active workflow exists but risk surface behaves as fresh start",
                "signal_status": cluster.get("signal_status"),
            }
        )

    # Class 3: cross-surface disagreement
    labels: List[Tuple[str, str]] = []
    if risk_primary.get("label"):
        labels.append(("risk_signals", risk_primary["label"]))
    for row in surfaces.get("issues") or []:
        for c in row.get("ctas") or []:
            labels.append(("issues", c.get("label", "")))
    for row in surfaces.get("jobs") or []:
        for c in row.get("next_actions") or []:
            labels.append(("jobs", c.get("label", "")))
    for row in surfaces.get("command_centre") or []:
        labels.append(("command_centre", row.get("primary_action_label", "")))
    intents = {src: classify_cta_intent(lbl) for src, lbl in labels if lbl}
    start_sources = [s for s, i in intents.items() if i == "start_create"]
    cont_sources = [s for s, i in intents.items() if i == "continuation"]
    if start_sources and cont_sources:
        findings.append(
            {
                "class": "cross_surface_disagreement",
                "severity": "medium",
                "detail": "Mixed start/create vs continuation CTAs on same operational object",
                "labels": labels,
                "start_sources": start_sources,
                "continuation_sources": cont_sources,
            }
        )

    # Class 4: backend rejection after encouraged CTA
    for p in backend_probes:
        if p.get("rejected") and has_active:
            findings.append(
                {
                    "class": "backend_rejection_after_encouraged_cta",
                    "severity": "critical",
                    "detail": "Backend rejected action while active lineage exists",
                    "probe": p,
                }
            )

    # Class 6: orphan operational state
    if cluster.get("orphan_issue_id") and not cluster.get("active_work_order_ids"):
        issue_rows = surfaces.get("issues") or []
        if issue_rows and not (issue_rows[0].get("ctas") or []):
            findings.append(
                {
                    "class": "orphan_operational_state",
                    "severity": "medium",
                    "detail": "Open issue without visible operational path",
                    "issue_id": cluster.get("orphan_issue_id"),
                }
            )
    if (cluster.get("signal_status") or "") == "remediation_in_progress" and not cluster.get("active_work_order_ids"):
        if not cluster.get("propagation"):
            findings.append(
                {
                    "class": "orphan_operational_state",
                    "severity": "medium",
                    "detail": "Signal remediation_in_progress without active WO and no propagation meta",
                    "signal_id": cluster.get("signal_id"),
                }
            )

    # Class 7: dead-end flow
    for row in surfaces.get("jobs") or []:
        st = (row.get("status") or "").upper()
        if st not in WO_TERMINAL and not row.get("next_actions"):
            findings.append(
                {
                    "class": "dead_end_operational_flow",
                    "severity": "high",
                    "detail": "Non-terminal job with empty next_actions",
                    "work_order_id": row.get("work_order_id"),
                    "status": st,
                }
            )

    return findings


def command_centre_alignment(client_tok: str, issues: List[dict], work_orders: List[dict]) -> Dict[str, Any]:
    primary = call("GET", "/client/command-center", client_tok, params={"projection": "primary"})
    body = primary.get("body") if isinstance(primary.get("body"), dict) else {}
    urgent = body.get("urgent_actions") or body.get("pressure_urgent_rows") or []
    urgent_count = body.get("pressure_urgent_count") or body.get("urgent_open_total") or len(urgent)
    pressure_degraded = body.get("pressure_degraded")
    pressure_status = body.get("pressure_status")

    open_issues = sum(1 for i in issues if (i.get("status") or "").lower() not in ISSUE_TERMINAL)
    open_wos = sum(1 for w in work_orders if (w.get("status") or "").upper() not in WO_TERMINAL)
    breached = sum(
        1
        for w in work_orders
        if (w.get("sla_state") or "").lower() == "breached"
        or (w.get("operational_exception") or "") == "NO_ACCESS"
    )
    operational_debt = open_issues + open_wos + breached

    calm_degraded = False
    if operational_debt > 0 and (urgent_count == 0 or len(urgent) == 0):
        if pressure_degraded or pressure_status == "degraded" or primary["status"] == 599:
            calm_degraded = True

    return {
        "primary_status": primary["status"],
        "elapsed_ms": primary["elapsed_ms"],
        "pressure_degraded": pressure_degraded,
        "pressure_status": pressure_status,
        "pressure_fallback_reason": body.get("pressure_fallback_reason"),
        "pressure_user_message": body.get("pressure_user_message") or body.get("user_message"),
        "urgent_count": urgent_count,
        "urgent_rows_sample": urgent[:8],
        "operational_debt_estimate": operational_debt,
        "open_issues": open_issues,
        "open_work_orders": open_wos,
        "calm_looking_degraded": calm_degraded,
        "checks": {
            "primary_returns_200": primary["status"] == 200,
            "degraded_disclosed_when_degraded": not pressure_degraded or bool(body.get("pressure_fallback_reason")),
            "no_false_calm_when_debt": not calm_degraded,
        },
    }


def browser_coherence_capture(client_pw: str) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"skipped": True, "reason": "playwright_not_installed"}

    SHOT.mkdir(parents=True, exist_ok=True)
    timings: List[Dict[str, Any]] = []
    paths = [
        ("/operations/risk-signals", "risk_signals"),
        ("/operations/issues", "issues"),
        ("/operations/work-orders", "jobs_list"),
        ("/command-center", "command_centre"),
        ("/operations/contractors", "contractors"),
    ]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            t_login = time.perf_counter()
            page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120000)
            page.fill("#email", CLIENT_EMAIL)
            page.fill("#password", client_pw)
            page.locator('button[type="submit"]').first.click()
            page.wait_for_timeout(5000)
            timings.append({"step": "login", "elapsed_ms": round((time.perf_counter() - t_login) * 1000, 1)})

            captures = []
            for path, name in paths:
                t0 = time.perf_counter()
                page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(3000)
                shot = SHOT / f"{name}.png"
                page.screenshot(path=str(shot), full_page=True)
                text = (page.inner_text("body") or "")[:6000]
                start_hits = len(START_CTA_PATTERNS.findall(text))
                cont_hits = len(CONTINUATION_PATTERNS.findall(text))
                elapsed = round((time.perf_counter() - t0) * 1000, 1)
                timings.append({"surface": name, "path": path, "elapsed_ms": elapsed})
                captures.append(
                    {
                        "surface": name,
                        "screenshot": str(shot.relative_to(ROOT)).replace("\\", "/"),
                        "start_cta_text_hits": start_hits,
                        "continuation_text_hits": cont_hits,
                    }
                )
            browser.close()
        return {"captures": captures, "timings": timings, "skipped": False}
    except Exception as exc:
        return {"skipped": True, "reason": "browser_capture_failed", "error": str(exc), "timings": timings}


def build_invariant_map() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "principle": "Every operational CTA must answer the single most operationally correct next step right now.",
        "invariants": [
            {
                "id": "INV-OC-001",
                "name": "no_duplicate_workflow_invitation",
                "rule": "If active issue/job/contractor/quote/inspection exists for lineage, suppress start/create CTAs.",
                "authority": ["risk_signal_service", "primaryActionResolver.js", "ClientIssuesPage", "compliance_workflow_service"],
                "contradiction_class": "duplicate_workflow_invitation",
            },
            {
                "id": "INV-OC-002",
                "name": "continuation_when_active",
                "rule": "Active workflows must surface continuation CTAs with ownership context, not fresh-start verbs.",
                "authority": ["compliance_workflow_service.next_job_actions", "ClientJobDetailPage", "ClientRiskSignalsPage"],
                "contradiction_class": "continuation_blindness",
            },
            {
                "id": "INV-OC-003",
                "name": "cross_surface_next_step_parity",
                "rule": "Risk/Issues/Jobs/CommandCentre/Contractor/Tenant must agree on operational phase for same object.",
                "authority": ["command_center_service", "client_priority_stream", "unified_tasks_service", "primaryActionResolver.js"],
                "contradiction_class": "cross_surface_disagreement",
            },
            {
                "id": "INV-OC-004",
                "name": "no_backend_rejection_after_encouraged_cta",
                "rule": "Encouraged UI/API CTAs must not 4xx when lineage already satisfies objective.",
                "authority": ["risk_signal_issue_idempotency", "maintenance_wo_from_issue_idempotency", "client_maintenance routes"],
                "contradiction_class": "backend_rejection_after_encouraged_cta",
            },
            {
                "id": "INV-OC-005",
                "name": "truthful_degraded_pressure",
                "rule": "Degraded orchestration must disclose degradation and preserve urgent continuation visibility.",
                "authority": ["command_center_service.get_command_center_primary_bundle"],
                "contradiction_class": "calm_looking_degraded_state",
            },
            {
                "id": "INV-OC-006",
                "name": "no_orphan_operational_state",
                "rule": "Open issues/signals must expose owner path (linked job, assign, escalate, or explicit blocked reason).",
                "authority": ["maintenance_issues_service", "risk_signal_regen_governance"],
                "contradiction_class": "orphan_operational_state",
            },
            {
                "id": "INV-OC-007",
                "name": "no_dead_end_non_terminal",
                "rule": "Non-terminal jobs/issues must expose at least one meaningful next action or blocked-state explanation.",
                "authority": ["compliance_workflow_service.next_job_actions"],
                "contradiction_class": "dead_end_operational_flow",
            },
        ],
        "remediation_policy": {
            "forbidden": ["hide_button_without_explanation", "suppress_urgent_debt_for_visual_calm"],
            "required_replacement": [
                "continuation_cta",
                "blocked_state_explanation",
                "ownership_context",
                "current_workflow_status",
                "escalation_path",
            ],
        },
    }


def classify_programme(
    stability: dict,
    contradictions: List[dict],
    cc: dict,
    *,
    audit_meta: dict,
) -> str:
    if not stability.get("pass"):
        return "BLOCKED"
    if audit_meta.get("inventory_incomplete"):
        return "FAIL_OPERATIONAL"
    if audit_meta.get("clusters_audited", 0) == 0 and audit_meta.get("signals_total", 0) > 0:
        return "FAIL_OPERATIONAL"
    critical = [c for c in contradictions if c.get("severity") == "critical"]
    high = [c for c in contradictions if c.get("severity") == "high"]
    if critical:
        return "TRUST_RISK_PRESENT"
    if cc.get("calm_looking_degraded"):
        return "TRUST_RISK_PRESENT"
    if len(high) >= 3 or len(contradictions) >= 8:
        return "OPERATIONAL_CONFUSION_RISK"
    if contradictions:
        return "PARTIAL"
    return "VERIFIED_OPERATIONALLY"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "marker": MARKER,
        "started_at": utc(),
        "api": API,
        "frontend": FRONTEND,
        "pilot": {"client_id": DEFAULT_CID, "property_id": DEFAULT_PID},
    }
    write("00_run_meta.json", meta)

    # Part 0: stability gate
    stability = stability_gate()
    write("stability_gate.json", stability)
    if not stability.get("pass"):
        write(
            "classifications.json",
            {"classification": "BLOCKED", "reason": "staging_stability_gate_failed", "stability_gate": stability},
        )
        (OUT / "REPORT.md").write_text(
            "# PRELAUNCH-OPERATIONS-OUTCOME-COHERENCE-01\n\n**Classification:** BLOCKED\n\nStaging stability gate failed. Baseline coherence audit not executed.\n",
            encoding="utf-8",
        )
        (OUT / "watchlist.md").write_text("- Resolve staging stability before coherence audit rerun.\n", encoding="utf-8")
        return 2

    client_pw = read_pw(PW_PATH, "OPS_VERIFY_PASSWORD", "OpsVerify01!StagingWalk")
    contractor_pw = read_pw(CONTRACTOR_PW_PATH, "OPS_CONTRACTOR_PASSWORD", "")
    tenant_pw = read_pw(TENANT_PW_PATH, "OPS_TENANT_PASSWORD", "F7OpsWales!Staging2026")

    client_tok = login(CLIENT_EMAIL, client_pw)
    contractor_tok = login(CONTRACTOR_EMAIL, contractor_pw, contractor=True)
    tenant_tok = login(TENANT_EMAIL, tenant_pw)

    ent = load_entitlements(client_tok)

    signals, signals_total, signals_attempts = load_inventory(
        "/client/maintenance/risk-signals", client_tok, list_key="signals", params={"limit": 500}
    )
    issues, issues_total, issues_attempts = load_inventory(
        "/client/maintenance/issues",
        client_tok,
        list_key="issues",
        params={"property_id": DEFAULT_PID, "limit": 300},
    )
    work_orders, wos_total, wos_attempts = load_inventory(
        "/client/maintenance/work-orders",
        client_tok,
        list_key="work_orders",
        params={"property_id": DEFAULT_PID, "limit": 300},
    )
    inventory_incomplete = signals_total == 0 or (issues_total == 0 and wos_total == 0)
    inventory_log = {
        "signals": {"total": signals_total, "loaded": len(signals), "attempts": signals_attempts},
        "issues": {"total": issues_total, "loaded": len(issues), "attempts": issues_attempts},
        "work_orders": {"total": wos_total, "loaded": len(work_orders), "attempts": wos_attempts},
        "pilot_property_id": DEFAULT_PID,
        "inventory_incomplete": inventory_incomplete,
    }
    write("inventory_load.json", inventory_log)

    cc_primary = command_centre_alignment(client_tok, issues, work_orders)
    cc_urgent = cc_primary.get("urgent_rows_sample") or []

    clusters = build_lineage_graph(signals, issues, work_orders, pilot_property_id=DEFAULT_PID)
    signals_by_id = {s["signal_id"]: s for s in signals if s.get("signal_id")}

    # Focus audit on clusters with active lineage, property overlap, or high-risk signal types
    recurring_types = ("recurring_repairs", "maintenance_frequency", "repeated_repairs", "sla_breach")
    audit_targets = [
        c
        for c in clusters
        if c.get("has_active_lineage")
        or c.get("lineage_via_property_overlap")
        or (c.get("risk_type") or "").lower() in recurring_types
        or c.get("orphan_issue_id")
    ][:40]

    cross_surface_rows: List[Dict[str, Any]] = []
    all_contradictions: List[Dict[str, Any]] = []
    duplicate_prevention: List[Dict[str, Any]] = []
    cta_conflicts: List[Dict[str, Any]] = []
    backend_probes_all: List[Dict[str, Any]] = []

    for cluster in audit_targets:
        surfaces = project_cluster_surfaces(
            cluster, client_tok, contractor_tok, tenant_tok, ent, cc_urgent, signals_by_id
        )
        probes = probe_backend_rejection(cluster, client_tok)
        backend_probes_all.extend(probes)
        findings = detect_contradictions(cluster, surfaces, probes)
        row = {
            "cluster": cluster,
            "surfaces": surfaces,
            "backend_probes": probes,
            "contradictions": findings,
        }
        cross_surface_rows.append(row)
        all_contradictions.extend(findings)
        for f in findings:
            cta_conflicts.append({**f, "signal_id": cluster.get("signal_id"), "cluster": cluster})
        if cluster.get("has_active_lineage") and any(
            f["class"] == "duplicate_workflow_invitation" for f in findings
        ):
            duplicate_prevention.append(
                {
                    "signal_id": cluster.get("signal_id"),
                    "active_work_order_ids": cluster.get("active_work_order_ids"),
                    "risk_primary": (surfaces.get("risk_signals") or {}).get("primary_cta"),
                    "detail": "Active lineage exists but start/create still primary on risk surface",
                }
            )

    # Tenant duplicate governance spot-check
    dup_probe = call(
        "POST",
        "/tenant/report-issue",
        tenant_tok,
        body={
            "property_id": DEFAULT_PID,
            "description": f"{MARKER} duplicate governance probe",
            "category": "general",
        },
    )
    tenant_dup = {
        "probe": dup_probe,
        "duplicate_governance": dup_probe["status"] == 409
        or (
            isinstance(dup_probe.get("body"), dict)
            and "duplicate" in json.dumps(dup_probe["body"], default=str).lower()
        ),
    }

    browser = browser_coherence_capture(client_pw)

    issues_runtime = {
        "captured_at": utc(),
        "inventory": {
            "total": len(issues),
            "by_status": {},
            "with_linked_wo": sum(1 for i in issues if i.get("linked_work_order_id") or i.get("work_order_id")),
            "with_risk_signal": sum(1 for i in issues if i.get("risk_signal_id")),
        },
        "tenant_duplicate_governance": tenant_dup,
        "audit_clusters": [r for r in cross_surface_rows if r["cluster"].get("active_issue_ids")],
    }
    jobs_runtime = {
        "captured_at": utc(),
        "inventory": {
            "total": len(work_orders),
            "by_status": {},
            "with_next_actions_sampled": 0,
        },
        "audit_clusters": [r for r in cross_surface_rows if r["cluster"].get("active_work_order_ids")],
    }
    risk_runtime = {
        "captured_at": utc(),
        "inventory": {
            "total": signals_total,
            "pilot_clusters": len(clusters),
            "with_active_lineage": sum(1 for c in clusters if c.get("has_active_lineage")),
            "with_property_overlap": sum(1 for c in clusters if c.get("lineage_via_property_overlap")),
        },
        "audit_targets": audit_targets[:15],
        "duplicate_invitation_cases": duplicate_prevention,
    }

    write("issues_runtime.json", issues_runtime)
    write("jobs_runtime.json", jobs_runtime)
    write("risk_signals_runtime.json", risk_runtime)
    write(
        "cross_surface_coherence.json",
        {
            "captured_at": utc(),
            "entitlements": ent,
            "clusters_audited": len(audit_targets),
            "rows": cross_surface_rows,
        },
    )
    write("duplicate_workflow_prevention.json", {"cases": duplicate_prevention, "backend_probes": backend_probes_all})
    write("cta_conflict_detection.json", {"conflicts": cta_conflicts, "by_class": _group_by_class(cta_conflicts)})
    write("command_centre_operational_alignment.json", cc_primary)
    write("browser_navigation_timings.json", browser)
    write("invariant_mapping.json", build_invariant_map())

    audit_meta = {
        "clusters_audited": len(audit_targets),
        "signals_total": signals_total,
        "issues_total": issues_total,
        "work_orders_total": wos_total,
        "inventory_incomplete": inventory_incomplete,
    }
    classification = classify_programme(stability, all_contradictions, cc_primary, audit_meta=audit_meta)
    write(
        "classifications.json",
        {
            "classification": classification,
            "contradiction_count": len(all_contradictions),
            "contradiction_by_class": _group_by_class(all_contradictions),
            "stability_gate": stability.get("pass"),
            "command_centre_calm_degraded": cc_primary.get("calm_looking_degraded"),
            "duplicate_invitation_cases": len(duplicate_prevention),
            "audit_meta": audit_meta,
            "inventory_load": inventory_log,
        },
    )

    _write_report(
        classification, stability, all_contradictions, cc_primary, duplicate_prevention, browser, audit_meta
    )
    _write_watchlist(classification, all_contradictions, cc_primary)

    print(json.dumps({"classification": classification, "contradictions": len(all_contradictions)}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


def _group_by_class(rows: List[dict]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        cls = r.get("class") or "unknown"
        out[cls] = out.get(cls, 0) + 1
    return out


def _write_report(
    classification: str,
    stability: dict,
    contradictions: List[dict],
    cc: dict,
    dup_cases: List[dict],
    browser: dict,
    audit_meta: dict,
) -> None:
    by_class = _group_by_class(contradictions)
    lines = [
        "# PRELAUNCH-OPERATIONS-OUTCOME-COHERENCE-01",
        "",
        f"**Classification:** `{classification}`",
        f"**Run tag:** `{RUN_TAG}`",
        "",
        "## Stability gate",
        f"- Pass: **{stability.get('pass')}**",
        f"- Version commit: `{((stability.get('version') or {}).get('commit'))}`",
        "",
        "## Baseline coherence audit (pre-remediation)",
        "",
        "This run maps cross-surface CTA truth for the same operational objects across Risk Signals, Issues, Jobs, Command Centre, Contractor, and Tenant.",
        "",
        "### Contradiction summary",
        "",
    ]
    for cls, count in sorted(by_class.items(), key=lambda x: -x[1]):
        lines.append(f"- `{cls}`: {count}")
    lines.extend(
        [
            "",
            "### Command Centre alignment",
            f"- Primary status: {cc.get('primary_status')}",
            f"- Urgent count: {cc.get('urgent_count')}",
            f"- Calm-looking degraded: **{cc.get('calm_looking_degraded')}**",
            "",
            "### Audit coverage",
            f"- Clusters audited: **{audit_meta.get('clusters_audited', 0)}**",
            f"- Pilot signals/issues/work_orders totals: {audit_meta.get('signals_total')}/{audit_meta.get('issues_total')}/{audit_meta.get('work_orders_total')}",
            f"- Inventory incomplete: **{audit_meta.get('inventory_incomplete')}**",
            "",
            "### Duplicate workflow invitation cases",
            f"- Count: **{len(dup_cases)}**",
            "",
            "### Browser evidence",
            f"- Skipped: {browser.get('skipped', False)}",
        ]
    )
    if browser.get("captures"):
        for c in browser["captures"]:
            lines.append(f"- `{c['surface']}`: {c['screenshot']}")
    lines.extend(
        [
            "",
            "## Next step",
            "Remediation must replace invalid CTAs with continuation/blocked-state explanations — not hide buttons.",
            "",
            "See `invariant_mapping.json` and `cta_conflict_detection.json` for authoritative contradiction register.",
        ]
    )
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_watchlist(classification: str, contradictions: List[dict], cc: dict) -> None:
    lines = ["# Watchlist — operations outcome coherence\n"]
    if classification != "VERIFIED_OPERATIONALLY":
        lines.append(f"- Programme classification: **{classification}** (baseline audit)\n")
    by_class = _group_by_class(contradictions)
    for cls, n in sorted(by_class.items(), key=lambda x: -x[1]):
        lines.append(f"- [{cls}] {n} finding(s) — requires targeted remediation with explicit continuation copy\n")
    if cc.get("calm_looking_degraded"):
        lines.append("- Command Centre degraded path may present calm surface despite operational debt\n")
    lines.append("- Do not remediate by silent button suppression\n")
    (OUT / "watchlist.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
