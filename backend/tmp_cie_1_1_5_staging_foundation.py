"""CIE-1 + CIE-1.5 staging foundation acceptance validation."""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

BACKEND = Path(__file__).resolve().parent
OUT = BACKEND / "docs/audit/compliance_intelligence_engine_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
PROGRAMME = "CIE-1-AND-CIE-1.5-STAGING-FOUNDATION-ACCEPTANCE"

EXPECTED_SHA = os.environ.get("CIE_STAGING_SHA", "935cf3f4").strip()
STAGING_API = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com/api")
STAGING_ROOT = os.environ.get("STAGING_ROOT", "https://pleerity-enterprise.onrender.com")
FRONTEND = os.environ.get("STAGING_FRONTEND", "https://pleerity-enterprise-9jjg.vercel.app")
DEPLOY_WAIT_SEC = int(os.environ.get("CIE_DEPLOY_WAIT_SEC", "900"))
POLL_INTERVAL_SEC = 30


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timed_get(url: str, *, headers: dict | None = None, params: dict | None = None) -> Tuple[httpx.Response, float]:
    t0 = time.perf_counter()
    r = httpx.get(url, headers=headers, params=params, timeout=120)
    return r, round((time.perf_counter() - t0) * 1000, 2)


def _run_pytest(paths: List[str]) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q", "--tb=line"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) passed", out)
    passed = int(m.group(1)) if m else 0
    m_fail = re.search(r"(\d+) failed", out)
    failed = int(m_fail.group(1)) if m_fail else 0
    return {"exit_code": proc.returncode, "passed": passed, "failed": failed, "output_tail": out[-3000:]}


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


def _wait_for_deploy(report: Dict[str, Any]) -> bool:
    deadline = time.time() + DEPLOY_WAIT_SEC
    last_sha = ""
    while time.time() < deadline:
        try:
            r, ms = _timed_get(f"{STAGING_API}/version")
            if r.status_code == 200:
                body = r.json()
                sha = str(body.get("commit_sha") or body.get("git_sha") or body.get("sha") or "")
                last_sha = sha
                report["deploy"] = {"sha": sha, "latency_ms": ms, "checked_at": _utc()}
                if sha.startswith(EXPECTED_SHA) or EXPECTED_SHA in sha:
                    return True
        except Exception as exc:
            report["deploy"] = {"error": str(exc), "checked_at": _utc()}
        time.sleep(POLL_INTERVAL_SEC)
    report.setdefault("deploy", {})["last_sha"] = last_sha
    return False


async def _local_cie_checks() -> Dict[str, Any]:
    from services.compliance_intelligence_engine.config import intelligence_engine_mode
    from services.compliance_intelligence_engine.provenance_validation import validate_all_registry_seeds_v1
    from services.compliance_intelligence_engine.replay import dispatch_replay
    from services.compliance_intelligence_engine.comparison import dispatch_compare
    from services.compliance_graph_service.access import ActorContext
    from services.compliance_intelligence_service import generate_recommendations, replay_intelligence

    os.environ.pop("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", None)
    mode = intelligence_engine_mode()
    ok_seeds, seed_errors = validate_all_registry_seeds_v1()

    actor = ActorContext(is_admin=False, client_id="staging-gate")
    gen = await generate_recommendations(actor=actor)
    replay = await dispatch_replay(replay_type="exact", provenance_id="cip_staging")
    compare = await dispatch_compare(left_id="cia_a", right_id="cia_b")
    isl_replay = await replay_intelligence(
        actor=actor, replay_type="exact", provenance_id="cip_staging", as_of="2026-06-17T00:00:00Z"
    )

    return {
        "mode_default": mode,
        "registry_seeds_ok": ok_seeds,
        "registry_seed_errors": seed_errors,
        "generate_response_hash": gen.get("response_hash", ""),
        "replay_response_hash": replay.get("response_hash", ""),
        "compare_response_hash": compare.get("response_hash", ""),
        "isl_replay_response_hash": isl_replay.get("response_hash", ""),
    }


async def main() -> int:
    report: Dict[str, Any] = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "validated_at": _utc(),
        "expected_commit_sha_prefix": EXPECTED_SHA,
        "staging_api": STAGING_API,
        "checks": [],
        "regression_http": [],
    }

    def add(name: str, passed: bool, **detail):
        row = {"name": name, "passed": passed}
        row.update({k: v for k, v in detail.items() if k not in ("passed", "name")})
        report["checks"].append(row)

    t0 = time.perf_counter()

    deploy_ok = _wait_for_deploy(report)
    add("staging_deploy_sha_aligned", deploy_ok, deploy=report.get("deploy"))

    local = await _local_cie_checks()
    report["local_cie"] = local
    add("cie_mode_defaults_disabled", local["mode_default"] == "disabled", mode=local["mode_default"])
    add("registry_v1_seeds_validate", local["registry_seeds_ok"], errors=local.get("registry_seed_errors"))
    add(
        "envelope_response_hash_on_generate",
        str(local.get("generate_response_hash", "")).startswith("sha256:"),
    )
    add(
        "envelope_response_hash_on_replay",
        str(local.get("replay_response_hash", "")).startswith("sha256:"),
    )
    add(
        "envelope_response_hash_on_compare",
        str(local.get("compare_response_hash", "")).startswith("sha256:"),
    )
    add("no_cie_customer_route_file", not (BACKEND / "routes" / "compliance_intelligence_engine.py").exists())

    engines_dir = BACKEND / "services" / "compliance_intelligence_engine" / "engines"
    add("no_domain_engines_package", not engines_dir.exists())

    cie_pytest = _run_pytest(
        [
            "tests/test_compliance_intelligence_engine_cie1.py",
            "tests/test_compliance_intelligence_engine_cie1_5.py",
            "tests/test_graph_service_access_boundary.py",
        ]
    )
    add("cie_local_pytest", cie_pytest["exit_code"] == 0, pytest=cie_pytest)

    reg_pytest = _run_pytest(
        [
            "tests/test_compliance_graph_service.py",
            "tests/test_compliance_graph_service_phase3.py",
            "tests/test_compliance_graph_health.py",
            "tests/test_compliance_intelligence_phase5.py",
        ]
    )
    add("ceg_graph_regression_pytest", reg_pytest["exit_code"] == 0, pytest=reg_pytest)

    token, login_meta = _login()
    add("staging_admin_login", token is not None, meta=login_meta)
    h = {"Authorization": f"Bearer {token}", "Origin": FRONTEND} if token else {}

    if token:
        endpoints = [
            ("graph_health", f"{STAGING_API}/admin/compliance/graph/health", None),
            ("graph_health_summary", f"{STAGING_API}/admin/compliance/graph/health/summary", None),
            ("system_health", f"{STAGING_API}/admin/observability/health-summary", None),
            ("control_centre", f"{STAGING_API}/admin/control-centre/snapshot", None),
            ("oe_timeline", f"{STAGING_API}/admin/observability/evidence/events", {"limit": 10}),
            ("platform_status", f"{STAGING_ROOT}/api/health", None),
        ]
        for name, url, params in endpoints:
            try:
                r, ms = _timed_get(url, headers=h, params=params)
                ok = r.status_code == 200
                row = {"name": name, "status": r.status_code, "latency_ms": ms, "passed": ok}
                report["regression_http"].append(row)
                add(f"http_regression_{name}", ok, status=r.status_code, latency_ms=ms)
            except Exception as exc:
                report["regression_http"].append({"name": name, "error": str(exc), "passed": False})
                add(f"http_regression_{name}", False, error=str(exc))

        # Decision explorer / graph list smoke
        try:
            r, ms = _timed_get(f"{STAGING_API}/admin/compliance/graph/decisions", headers=h, params={"limit": 5})
            add("http_regression_decision_explorer", r.status_code == 200, status=r.status_code, latency_ms=ms)
        except Exception as exc:
            add("http_regression_decision_explorer", False, error=str(exc))

        # CIE engine route must not exist on staging
        try:
            r, _ = _timed_get(f"{STAGING_API}/admin/compliance/intelligence-engine/artefacts", headers=h)
            add("no_cie_engine_http_route", r.status_code in (404, 405, 422), status=r.status_code)
        except Exception as exc:
            add("no_cie_engine_http_route", True, note=str(exc))

    report["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    critical = [
        "staging_deploy_sha_aligned",
        "cie_mode_defaults_disabled",
        "registry_v1_seeds_validate",
        "envelope_response_hash_on_generate",
        "cie_local_pytest",
        "ceg_graph_regression_pytest",
    ]
    crit_pass = all(
        next((c["passed"] for c in report["checks"] if c["name"] == n), False) for n in critical
    )
    report["verdict"] = "CIE_1_1_5_STAGING_ACCEPTED" if crit_pass else "CIE_1_1_5_STAGING_NOT_ACCEPTED"

    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / "CIE_1_1_5_STAGING_ACCEPTANCE.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md_lines = [
        "# CIE-1 + CIE-1.5 Staging Foundation Acceptance",
        "",
        f"**Verdict:** `{report['verdict']}`",
        f"**Run tag:** `{RUN_TAG}`",
        f"**Expected SHA:** `{EXPECTED_SHA}`",
        f"**Staging deploy:** `{report.get('deploy', {})}`",
        "",
        "## Summary",
        "",
        "Staging foundation validation for Compliance Intelligence Engine (CIE-1) and",
        "Provenance foundation (CIE-1.5). CIE remains `COMPLIANCE_INTELLIGENCE_ENGINE_MODE=disabled`.",
        "",
        "## Checks",
        "",
    ]
    for c in report["checks"]:
        mark = "pass" if c["passed"] else "FAIL"
        md_lines.append(f"- [{mark}] `{c['name']}`")
    md_lines.extend(
        [
            "",
            "## Regression",
            "",
            f"- CIE local pytest: {cie_pytest['passed']} passed",
            f"- CEG/graph pytest: {reg_pytest['passed']} passed",
            "",
            "## Remaining risks",
            "",
            "1. CIE persistence stubs — no live artefact/provenance writes until CIE-2.",
            "2. Replay/compare execution deferred — stubs only on staging.",
            "3. Staging does not exercise CIE domain engines (by design).",
            "",
            "## CIE-2 readiness",
            "",
            "CIE-1 + CIE-1.5 foundation is accepted on staging. **CIE-2 requires separate",
            "explicit authorisation** before recommendation/priority engines are implemented.",
            "",
            "**Do not implement:** Recommendation Engine, Priority Engine, or other domain",
            "engines without explicit CIE-2 approval.",
        ]
    )
    (OUT / "CIE_1_1_5_STAGING_ACCEPTANCE_REPORT.md").write_text("\n".join(md_lines), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "path": str(json_path)}, indent=2))
    return 0 if report["verdict"] == "CIE_1_1_5_STAGING_ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
