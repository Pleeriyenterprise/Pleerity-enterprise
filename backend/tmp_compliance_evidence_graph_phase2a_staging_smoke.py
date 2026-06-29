"""
COMPLIANCE-EVIDENCE-GRAPH-PHASE-2A-STAGING-SMOKE

Post-deploy staging validation for Phase 2A Graph Health infrastructure.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

PROGRAMME = "COMPLIANCE-EVIDENCE-GRAPH-PHASE-2A-STAGING-SMOKE"
EXPECTED_SHA_PREFIX = os.environ.get("CEG_PHASE2A_SHA_PREFIX", "eb502862")
STAGING_API = "https://pleerity-enterprise.onrender.com/api"
STAGING_ROOT = "https://pleerity-enterprise.onrender.com"
FRONTEND = "https://pleerity-enterprise-9jjg.vercel.app"
PROD_API = "https://api.pleerityenterprise.co.uk"
OUT_DIR = Path(__file__).resolve().parent / "docs/audit/compliance_evidence_graph_and_explainable_intelligence_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
DEPLOY_WAIT_SEC = int(os.environ.get("CEG_DEPLOY_WAIT_SEC", "900"))
POLL_INTERVAL_SEC = 30


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _login() -> Tuple[Optional[str], str]:
    email = os.environ.get("STAGING_ADMIN_EMAIL", "prosper@yopmail.com").strip()
    pw = os.environ.get("STAGING_ADMIN_PASSWORD", "Pastor@36$").strip()
    r = httpx.post(
        f"{STAGING_API}/auth/admin/login",
        json={"email": email, "password": pw},
        headers={"Origin": FRONTEND},
        timeout=120,
    )
    if r.status_code == 200:
        return r.json().get("access_token"), email[:3] + "***"
    return None, f"login_failed_{r.status_code}"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Origin": FRONTEND}


def _timed_get(url: str, *, headers: dict | None = None, params: dict | None = None) -> Tuple[httpx.Response, float]:
    t0 = time.perf_counter()
    r = httpx.get(url, headers=headers, params=params, timeout=120)
    return r, round((time.perf_counter() - t0) * 1000, 2)


def _wait_for_deploy(report: Dict[str, Any]) -> bool:
    deadline = time.time() + max(DEPLOY_WAIT_SEC, 1)
    attempts: List[Dict[str, Any]] = []
    while time.time() < deadline:
        r, ms = _timed_get(f"{STAGING_API}/version")
        body = r.json() if r.status_code == 200 else {}
        sha = str(body.get("commit_sha") or body.get("git_sha") or body.get("sha") or "")
        attempts.append({"status": r.status_code, "sha": sha, "latency_ms": ms, "at": _utc()})
        if r.status_code == 200 and sha.lower().startswith(EXPECTED_SHA_PREFIX.lower()):
            report["deploy"] = {"aligned": True, "commit_sha": sha, "attempts": len(attempts)}
            return True
        if DEPLOY_WAIT_SEC <= 0:
            break
        time.sleep(POLL_INTERVAL_SEC)
    report["deploy"] = {"aligned": False, "expected_prefix": EXPECTED_SHA_PREFIX, "attempts": attempts}
    return False


def main() -> int:
    report: Dict[str, Any] = {
        "programme": PROGRAMME,
        "validated_at": _utc(),
        "run_tag": RUN_TAG,
        "expected_sha_prefix": EXPECTED_SHA_PREFIX,
        "staging_api": STAGING_API,
        "checks": [],
    }

    def add(name: str, passed: bool, **detail):
        report["checks"].append({"name": name, "passed": passed, **detail})

    # Deploy alignment
    deployed = _wait_for_deploy(report)
    add("backend_version_aligned", deployed, **(report.get("deploy") or {}))

    # Production untouched
    prod_v, prod_ms = _timed_get(f"{PROD_API}/version")
    prod_sha = (prod_v.json() if prod_v.status_code == 200 else {}).get("commit_sha", "")
    prod_aligned = not str(prod_sha).lower().startswith(EXPECTED_SHA_PREFIX.lower())
    add(
        "production_not_touched",
        prod_aligned,
        prod_status=prod_v.status_code,
        prod_sha=prod_sha,
        latency_ms=prod_ms,
    )

    token, login_note = _login()
    add("admin_login", bool(token), note=login_note)
    if not token:
        report["verdict"] = "STAGING_SMOKE_BLOCKED"
        _write_report(report)
        return 1

    h = _headers(token)

    # Graph Health endpoints
    gh_r, gh_ms = _timed_get(f"{STAGING_API}/admin/compliance/graph/health", headers=h)
    gh_body = gh_r.json() if gh_r.status_code == 200 else {"error": gh_r.text[:300]}
    report["graph_health_sample"] = gh_body if gh_r.status_code == 200 else {"status": gh_r.status_code, "error": gh_body}
    add(
        "graph_health_api",
        gh_r.status_code == 200,
        status=gh_r.status_code,
        latency_ms=gh_ms,
        overall_status=gh_body.get("overall_status") if gh_r.status_code == 200 else None,
    )

    reg_r, reg_ms = _timed_get(f"{STAGING_API}/admin/compliance/graph/producers/registry", headers=h)
    reg_body = reg_r.json() if reg_r.status_code == 200 else {}
    report["producer_registry_sample"] = reg_body
    live_emit = (reg_body.get("entries") or [])
    live_count = sum(1 for e in live_emit if e.get("live_emit_active"))
    add(
        "producer_registry_api",
        reg_r.status_code == 200 and len(live_emit) >= 10,
        status=reg_r.status_code,
        latency_ms=reg_ms,
        entry_count=len(live_emit),
        live_emit_active_count=live_count,
    )
    add("no_live_producers", live_count == 0 and reg_body.get("live_emit_active") is False, live_emit_active_count=live_count)

    if gh_r.status_code == 200:
        pr = gh_body.get("producer_registry") or {}
        add(
            "graph_health_status_acceptable",
            gh_body.get("overall_status") in ("healthy", "degraded"),
            overall_status=gh_body.get("overall_status"),
            integrity_failures=(gh_body.get("summary") or {}).get("integrity_failure_count"),
        )
        add(
            "health_live_emit_zero",
            pr.get("live_emit_active_count", 1) == 0,
            live_emit_active_count=pr.get("live_emit_active_count"),
        )

    # Regression surfaces
    regression: Dict[str, Any] = {}
    for name, url, params in [
        ("system_health", f"{STAGING_API}/admin/observability/health-summary", None),
        ("control_centre", f"{STAGING_API}/admin/control-centre/snapshot", None),
        ("oe_timeline", f"{STAGING_API}/admin/observability/evidence/events", {"limit": 20}),
        ("graph_health_summary", f"{STAGING_API}/admin/compliance/graph/health/summary", None),
    ]:
        r, ms = _timed_get(url, headers=h, params=params)
        regression[name] = {"status": r.status_code, "latency_ms": ms, "ok": r.status_code == 200}
        add(f"regression_{name}", r.status_code == 200, status=r.status_code, latency_ms=ms)

    cc = regression.get("control_centre") or {}
    if cc.get("ok"):
        cc_r, _ = _timed_get(f"{STAGING_API}/admin/control-centre/snapshot", headers=h)
        cc_body = cc_r.json() if cc_r.status_code == 200 else {}
        platform_status = (cc_body.get("system") or {}).get("status")
        regression["platform_status"] = {"status": cc_r.status_code, "platform_status": platform_status}
        add("regression_platform_status", cc_r.status_code == 200, platform_status=platform_status)

    report["regression_summary"] = regression

    # Feature flag note — cannot read env from API; infer from registry behaviour
    report["feature_flag_inference"] = {
        "live_emit_active_count": live_count,
        "inferred_mode": "disabled_or_shadow_without_emit",
        "note": "Producers registered but emit_implemented=false; no live graph decisions",
    }
    add("feature_flag_safe", live_count == 0, inferred="disabled_or_shadow_without_emit")

    passed = sum(1 for c in report["checks"] if c["passed"])
    total = len(report["checks"])
    blockers = [c["name"] for c in report["checks"] if not c["passed"]]
    report["summary"] = {
        "passed": passed,
        "total": total,
        "blockers": blockers,
        "verdict": "PHASE_2A_STAGING_SMOKE_PASSED" if passed == total else "PHASE_2A_STAGING_SMOKE_FAILED",
        "phase_2b_ready_recommendation": passed == total,
    }
    _write_report(report)
    print(json.dumps(report["summary"], indent=2))
    return 0 if passed == total else 1


def _write_report(report: Dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "PHASE_2A_STAGING_SMOKE.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path = OUT_DIR / "PHASE_2A_STAGING_SMOKE_REPORT.md"
    md_path.write_text(_render_md(report), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


def _render_md(report: Dict[str, Any]) -> str:
    s = report.get("summary") or {}
    lines = [
        "# Phase 2A Staging Smoke Report",
        "",
        f"**Programme:** {PROGRAMME}",
        f"**Validated at:** {report.get('validated_at')}",
        f"**Verdict:** `{s.get('verdict')}`",
        "",
        "## Deploy",
        "",
        f"- Expected SHA prefix: `{report.get('expected_sha_prefix')}`",
        f"- Aligned: {(report.get('deploy') or {}).get('aligned')}",
        f"- Staging SHA: {(report.get('deploy') or {}).get('commit_sha', 'n/a')}",
        "",
        "## API summary",
        "",
        "| Check | Pass |",
        "|-------|------|",
    ]
    for c in report.get("checks") or []:
        lines.append(f"| {c['name']} | {'✓' if c['passed'] else '✗'} |")
    lines.extend(["", "## Graph Health sample", "", "```json", json.dumps(report.get("graph_health_sample") or {}, indent=2)[:4000], "```"])
    lines.extend(["", "## Regression", "", "```json", json.dumps(report.get("regression_summary") or {}, indent=2), "```"])
    lines.extend(["", "## Remaining risks", "", "- Phase 1 fixtures may warn on missing decision_quality until 2B", "- Platform Status derived from Control Centre snapshot", ""])
    rec = "PHASE_2B_READY (await explicit approval)" if s.get("phase_2b_ready_recommendation") else "Resolve blockers before 2B"
    lines.extend(["", f"## Recommendation: {rec}", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
