#!/usr/bin/env python3
"""TODAY-WORKFLOW-RESIDUE-CONVERGENCE-01 — post-fix staging verification."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/workflow_residue_convergence_01"
PROGRAMME = "TODAY-WORKFLOW-RESIDUE-CONVERGENCE-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

_spec = importlib.util.spec_from_file_location("_fc", ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py")
_fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fc)
API, FRONTEND = _fc.API, _fc.FRONTEND

CLIENTS = {
    "sophie_calm": {"id": "10b2ddba-e952-4484-91d1-a8f0299d0824", "label": "Sophie Walker (all satisfied)"},
    "partial_b": {"id": "616258a5-51a6-4def-aa00-baa1598b2557", "label": "Partial operational B"},
    "nancy_ops": {"id": "6fd5ac4c-3fd4-4112-ade7-156977deb49f", "label": "Nancy maintenance-heavy"},
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def write(name: str, data: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    return p


def impersonate(cid: str, reason: str) -> Tuple[str, dict]:
    admin_t, _, step, err = _fc.admin_session()
    if err:
        raise RuntimeError(err)
    tok, ierr = _fc.impersonate(admin_t, step, cid, reason)
    if ierr:
        raise RuntimeError(ierr)
    me = httpx.get(f"{API}/auth/me", headers=hdr(tok), timeout=60)
    user = me.json() if me.status_code == 200 else {"client_id": cid}
    return tok, user


def lineage_key(task: dict) -> str | None:
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    rsid = str(meta.get("related_risk_signal_id") or "").strip()
    if rsid:
        return f"risk_signal:{rsid}"
    root = str(meta.get("operational_root_key") or meta.get("gap_key") or "").strip()
    if root:
        return f"root:{root}"
    src = str(task.get("source_type") or "").lower()
    if src == "work_order":
        wid = str(meta.get("related_work_order_id") or task.get("source_entity_id") or "").strip()
        if wid:
            return f"work_order:{wid}"
    if src == "issue":
        iid = str(meta.get("related_issue_id") or task.get("source_entity_id") or "").strip()
        if iid:
            return f"issue:{iid}"
    return None


def collect_tasks(unified: dict) -> List[dict]:
    root = unified.get("tasks") or {}
    out: List[dict] = []
    for bucket in ("urgent", "upcoming", "in_progress"):
        for t in root.get(bucket) or []:
            out.append({**t, "_api_bucket": bucket})
    return out


def probe_client(key: str, spec: dict) -> dict:
    tok, _user = impersonate(spec["id"], f"{PROGRAMME} {key}")
    today = httpx.get(
        f"{API}/today/items",
        headers=hdr(tok),
        params={"bypass_cache": "true"},
        timeout=120,
    ).json()
    unified = httpx.get(
        f"{API}/client/tasks",
        headers=hdr(tok),
        params={"bypass_cache": "true"},
        timeout=120,
    ).json()
    risks = httpx.get(f"{API}/client/risk-signals", headers=hdr(tok), timeout=120).json()
    score = httpx.get(f"{API}/client/compliance-score", headers=hdr(tok), timeout=120).json()
    summary = today.get("summary") or {}
    tasks = collect_tasks(unified)
    lineage_keys = [lineage_key(t) for t in tasks if lineage_key(t)]
    dup_groups = {k: v for k, v in Counter(lineage_keys).items() if v > 1}
    churn_titles = [
        t.get("title")
        for t in tasks
        if "compliance churn" in str(t.get("title") or "").lower()
    ]
    internal_leak = [
        t.get("title")
        for t in tasks
        if any(
            x in str(t.get("title") or "").lower()
            for x in ("compliance churn risk review", "review issue", "review gap")
        )
    ]
    traces = []
    for t in tasks[:20]:
        meta = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
        traces.append(
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "source_type": t.get("source_type"),
                "section": t.get("section"),
                "api_bucket": t.get("_api_bucket"),
                "lineage_key": lineage_key(t),
                "related_risk_signal_id": meta.get("related_risk_signal_id"),
                "related_issue_id": meta.get("related_issue_id"),
                "related_work_order_id": meta.get("related_work_order_id"),
                "operational_root_key": meta.get("operational_root_key") or meta.get("gap_key"),
            }
        )
    stats = score.get("stats") or {}
    active_risks = [
        s
        for s in (risks.get("signals") or [])
        if str(s.get("status") or "").lower() in ("active", "acknowledged")
    ]
    return {
        "client_key": key,
        "label": spec["label"],
        "client_id": spec["id"],
        "summary": {
            "urgent_count": summary.get("urgent_count"),
            "in_progress_count": summary.get("in_progress_count"),
            "unified_urgent": len(unified.get("tasks", {}).get("urgent") or []),
            "unified_in_progress": len(unified.get("tasks", {}).get("in_progress") or []),
            "all_satisfied": stats.get("satisfied") == stats.get("total_requirements")
            and bool(stats.get("total_requirements")),
            "score": score.get("score"),
            "active_risk_signals": len(active_risks),
        },
        "duplicate_lineage_groups": dup_groups,
        "churn_titles": churn_titles,
        "internal_language_leaks": internal_leak,
        "task_titles": [t.get("title") for t in tasks],
        "lineage_traces": traces,
    }


def browser_capture(cid: str, label: str, shot_name: str) -> dict:
    if not sync_playwright:
        return {"pass": False, "error": "playwright_missing"}
    tok, user = impersonate(cid, f"{PROGRAMME} browser {label}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / shot_name
    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120000)
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [tok, user],
        )
        page.goto(f"{FRONTEND}/today", wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(5000)
        body = page.inner_text("body")
        churn_count = body.lower().count("compliance churn")
        page.screenshot(path=str(path), full_page=True)
        return {
            "pass": True,
            "screenshot": str(path.relative_to(ROOT.parent)),
            "compliance_churn_mentions": churn_count,
            "in_progress_visible": "In progress" in body,
            "body_excerpt": body[:1200],
        }


def run_regression() -> dict:
    tests = [
        "tests/test_unified_tasks_operational_convergence.py",
        "tests/test_today_projection_quality.py",
        "tests/test_customer_operational_language_service.py",
        "tests/test_phase21_priority_unification.py",
        "tests/test_risk_signal_regen_governance.py",
    ]
    out: dict = {}
    for t in tests:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", t, "-q", "--tb=no"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        out[t] = {"exit_code": proc.returncode, "tail": (proc.stdout or "")[-400:]}
    out["pass"] = all(v["exit_code"] == 0 for v in out.values() if isinstance(v, dict) and "exit_code" in v)
    return out


def classify_verdict(results: dict) -> dict:
    sophie = results.get("client_probes", {}).get("sophie_calm", {})
    partial = results.get("client_probes", {}).get("partial_b", {})
    nancy = results.get("client_probes", {}).get("nancy_ops", {})
    s_sum = sophie.get("summary") or {}
    classifications: List[str] = []

    sophie_ok = (
        not sophie.get("error")
        and (s_sum.get("urgent_count") or 0) == 0
        and (s_sum.get("in_progress_count") or 0) == 0
        and not sophie.get("duplicate_lineage_groups")
        and not sophie.get("churn_titles")
    )
    if sophie_ok:
        classifications.append("VERIFIED_OPERATIONALLY")
    else:
        classifications.append("OPERATIONAL_SUPPRESSION_DRIFT")

    if not sophie.get("duplicate_lineage_groups") and not partial.get("duplicate_lineage_groups"):
        classifications.append("WORKFLOW_RESIDUE_CONVERGED")
    else:
        classifications.append("DEDUPE_DRIFT")

    if not sophie.get("churn_titles") and not sophie.get("internal_language_leaks"):
        classifications.append("RISK_RESIDUE_DRIFT" if sophie.get("churn_titles") else "WORKFLOW_RESIDUE_CONVERGED")
    elif sophie.get("churn_titles"):
        classifications.append("RISK_RESIDUE_DRIFT")

    nancy_sum = nancy.get("summary") or {}
    nancy_has_ops = (nancy_sum.get("unified_in_progress") or 0) > 0 or (nancy_sum.get("active_risk_signals") or 0) > 0
    if nancy.get("error"):
        classifications.append("OPERATIONAL_SUPPRESSION_DRIFT")
    elif nancy_has_ops:
        classifications.append("VERIFIED_OPERATIONALLY")
    else:
        classifications.append("OPERATIONAL_SUPPRESSION_DRIFT")

    partial_has_work = (partial.get("summary") or {}).get("urgent_count", 0) or (partial.get("summary") or {}).get(
        "in_progress_count", 0
    )
    if partial.get("error"):
        pass
    elif partial_has_work:
        classifications.append("VERIFIED_OPERATIONALLY")
    elif partial.get("summary", {}).get("all_satisfied"):
        classifications.append("VERIFIED_OPERATIONALLY")

    return {
        "classifications": sorted(set(classifications)),
        "sophie_calm_ok": sophie_ok,
        "partial_has_genuine_work": bool(partial_has_work),
        "nancy_predictive_preserved": nancy_has_ops and not nancy.get("duplicate_lineage_groups"),
    }


def main() -> int:
    results: dict = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "generated_at_utc": utc(),
        "implementation_summary": {
            "risk_linked_stale_suppression": "unified_tasks_operational_convergence.suppress_stale_operational_residue_tasks",
            "lineage_dedupe": "unified_tasks_operational_convergence.dedupe_operational_lineage_tasks",
            "customer_language": "customer_operational_language_service._RISK_TYPE_ISSUE_SUMMARIES",
            "churn_lifecycle": "risk_signal_service._rule_compliance_churn current_bad_count==0 decay",
            "regen_governance": "risk_signal_regen_governance.collect_operational_debt_signal_ids skips stale residue",
        },
        "client_probes": {},
        "browser_proof": {},
        "regression": {},
        "before_after": {
            "audit_reference": "docs/audit/today_in_progress_source_trace_audit_01/TODAY_INPROGRESS_SOURCE_TRACE_FINAL.json",
            "expected_delta": [
                "risk-linked stale issues suppressed when compliance recovered",
                "duplicate risk_signal lineage collapsed to single highest-actionability card",
                "compliance churn risk titles replaced with landlord-readable summaries",
                "churn rule returns [] when current_bad_count==0 and no open WO/issues",
            ],
        },
    }
    for key, spec in CLIENTS.items():
        try:
            results["client_probes"][key] = probe_client(key, spec)
        except Exception as exc:
            results["client_probes"][key] = {"error": str(exc)[:400]}

    for key, shot in [
        ("sophie_calm", f"browser_sophie_{RUN_TAG}.png"),
        ("partial_b", f"browser_partial_b_{RUN_TAG}.png"),
        ("nancy_ops", f"browser_nancy_{RUN_TAG}.png"),
    ]:
        try:
            results["browser_proof"][key] = browser_capture(CLIENTS[key]["id"], key, shot)
        except Exception as exc:
            results["browser_proof"][key] = {"pass": False, "error": str(exc)[:300]}

    results["regression"] = run_regression()
    results["verdict"] = classify_verdict(results)

    final_path = write(f"WORKFLOW_RESIDUE_CONVERGENCE_FINAL_{RUN_TAG}.json", results)
    print(json.dumps({"final": str(final_path), "verdict": results["verdict"]}, indent=2))
    return 0 if results["regression"].get("pass") and results["verdict"].get("sophie_calm_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
