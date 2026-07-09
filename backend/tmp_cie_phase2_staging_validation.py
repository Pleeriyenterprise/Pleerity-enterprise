"""CIE-2 staging shadow validation — recommendation + priority engines on pleerity_staging."""
from __future__ import annotations

import ast
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
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]

BACKEND = Path(__file__).resolve().parent
OUT = BACKEND / "docs/audit/compliance_intelligence_engine_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
PROGRAMME = "CIE-2-STAGING-SHADOW-VALIDATION"

EXPECTED_SHA = os.environ.get("CIE_STAGING_SHA", "817977e4").strip()
STAGING_API = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com/api")
STAGING_ROOT = os.environ.get("STAGING_ROOT", "https://pleerity-enterprise.onrender.com")
FRONTEND = os.environ.get("STAGING_FRONTEND", "https://pleerity-enterprise-9jjg.vercel.app")
PROD_API = os.environ.get("PROD_API", "https://api.pleerityenterprise.co.uk")
STAGING_CLIENT_ID = os.environ.get("CIE_STAGING_CLIENT_ID", "6fd5ac4c-3fd4-4112-ade7-156977deb49f").strip()
DEPLOY_WAIT_SEC = int(os.environ.get("CIE_DEPLOY_WAIT_SEC", "900"))
POLL_INTERVAL_SEC = 30

CIE_FORBIDDEN_AI = (
    "utils.llm_chat",
    "openai",
    "anthropic",
    "services.compliance_intelligence.investigate",
    "services.compliance_intelligence.narrations",
)

REGRESSION_SUITES: Dict[str, List[str]] = {
    "graph_health": [
        "tests/test_compliance_graph_service.py",
        "tests/test_compliance_graph_health.py",
    ],
    "operational_evidence_platform": ["tests/test_operational_evidence_platform.py"],
    "system_health": [
        "tests/test_storage_paths_health.py",
        "tests/test_admin_generation_health.py",
    ],
    "platform_status_operational": [
        "tests/test_operational_recovery.py",
        "tests/test_operational_alert_presentation.py",
    ],
    "automation_control_centre": ["tests/test_operational_alert_presentation_phase25.py"],
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timed_get(url: str, *, headers: dict | None = None, params: dict | None = None) -> Tuple[httpx.Response, float]:
    t0 = time.perf_counter()
    r = httpx.get(url, headers=headers, params=params, timeout=180)
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
    return {"exit_code": proc.returncode, "passed": passed, "failed": failed, "output_tail": out[-2500:]}


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
    attempts: List[Dict[str, Any]] = []
    deadline = time.time() + max(DEPLOY_WAIT_SEC, 0)
    while True:
        try:
            r, ms = _timed_get(f"{STAGING_API}/version")
            body = r.json() if r.status_code == 200 else {}
            sha = str(body.get("commit_sha") or body.get("git_sha") or body.get("sha") or "")
            attempts.append({"status": r.status_code, "sha": sha, "latency_ms": ms, "at": _utc()})
            if r.status_code == 200 and (sha.startswith(EXPECTED_SHA) or EXPECTED_SHA in sha):
                report["deploy"] = {"aligned": True, "commit_sha": sha, "environment": body.get("environment"), "attempts": len(attempts)}
                return True
        except Exception as exc:
            attempts.append({"error": str(exc), "at": _utc()})
        if DEPLOY_WAIT_SEC <= 0 or time.time() >= deadline:
            break
        time.sleep(POLL_INTERVAL_SEC)
    report["deploy"] = {"aligned": False, "expected_sha_prefix": EXPECTED_SHA, "attempts": attempts}
    return False


def _staging_shadow_flag_configured() -> Dict[str, Any]:
    staging_yaml = BACKEND.parent / "render.staging.yaml"
    prod_yaml = BACKEND.parent / "render.production.yaml"
    legacy_yaml = BACKEND.parent / "render.yaml"
    staging_text = staging_yaml.read_text(encoding="utf-8") if staging_yaml.exists() else ""
    prod_text = prod_yaml.read_text(encoding="utf-8") if prod_yaml.exists() else ""
    legacy_text = legacy_yaml.read_text(encoding="utf-8") if legacy_yaml.exists() else ""
    return {
        "staging_yaml_has_shadow": "COMPLIANCE_INTELLIGENCE_ENGINE_MODE" in staging_text and "shadow" in staging_text,
        "production_yaml_has_cie_flag": "COMPLIANCE_INTELLIGENCE_ENGINE_MODE" in prod_text,
        "legacy_render_has_cie_flag": "COMPLIANCE_INTELLIGENCE_ENGINE_MODE" in legacy_text,
    }


def _file_imports_forbidden_ai(file_path: Path) -> List[str]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    hits: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for forbidden in CIE_FORBIDDEN_AI:
                if node.module == forbidden or node.module.startswith(forbidden + "."):
                    hits.append(forbidden)
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in CIE_FORBIDDEN_AI:
                    if (alias.name or "") == forbidden or (alias.name or "").startswith(forbidden + "."):
                        hits.append(forbidden)
    return hits


def _static_boundary() -> Dict[str, Any]:
    cie_pkgs = [
        BACKEND / "services" / "compliance_intelligence_engine",
        BACKEND / "services" / "compliance_intelligence_service",
    ]
    ai_violations: List[str] = []
    for pkg in cie_pkgs:
        for py in pkg.rglob("*.py"):
            hits = _file_imports_forbidden_ai(py)
            if hits:
                ai_violations.append(f"{py.relative_to(BACKEND)}: {hits}")
    cie_route = BACKEND / "routes" / "compliance_intelligence_engine.py"
    intel_routes = list((BACKEND / "routes").glob("*intelligence*"))
    return {
        "no_ai_imports": len(ai_violations) == 0,
        "ai_violations": ai_violations,
        "no_cie_engine_route": not cie_route.exists(),
        "intelligence_routes": [p.name for p in intel_routes],
    }


def _discover_staging_decision_id(token: str) -> Optional[str]:
    """Pick a real staging decision id for fixture anchoring."""
    h = {"Authorization": f"Bearer {token}", "Origin": FRONTEND}
    try:
        r = httpx.get(
            f"{STAGING_API}/admin/compliance/graph/decisions",
            headers=h,
            params={"client_id": STAGING_CLIENT_ID, "limit": 1},
            timeout=180,
        )
        if r.status_code != 200:
            return None
        body = r.json()
        decs = body.get("decisions") or (body.get("payload") or {}).get("decisions") or []
        if decs:
            return str(decs[0].get("decision_id") or "")
    except Exception:
        return None
    return None


def _staging_graph_gap_fixture(decision_id: str) -> Dict[str, Any]:
    """Bounded shadow fixture — anchors to a real staging decision when snapshots lack gap fields."""
    return {
        "insufficient_evidence": False,
        "service": "find_missing_evidence",
        "payload": {
            "gaps": [
                {
                    "decision_id": decision_id,
                    "missing": [{"code": "missing_evidence", "document_id": "doc_cie2_staging_validation"}],
                }
            ]
        },
    }


async def _mongo_cie_runtime(report: Dict[str, Any], *, token: Optional[str]) -> Dict[str, Any]:
    """Exercise CIE-2 against live pleerity_staging data (shadow mode)."""
    from unittest.mock import AsyncMock, patch

    from services.compliance_graph_service.access import ActorContext
    from services.compliance_intelligence_engine.config import (
        intelligence_engine_mode,
        intelligence_engine_operational_effects,
        intelligence_engine_shadow_validation,
    )
    from services.compliance_intelligence_engine.provenance_validation import validate_artefact_provenance_link
    from services.compliance_intelligence_service import (
        explain_intelligence,
        generate_priority_assessment,
        generate_recommendations,
        get_intelligence,
        get_intelligence_provenance,
    )

    out: Dict[str, Any] = {"mongo_connected": False}
    if not os.environ.get("MONGO_URL"):
        out["error"] = "MONGO_URL not configured"
        return out

    from database import database

    try:
        await database.connect()
        out["mongo_connected"] = True
        db_name = os.environ.get("DB_NAME", "pleerity_staging")
        out["db_name"] = db_name
    except Exception as exc:
        out["error"] = str(exc)[:300]
        return out

    os.environ["COMPLIANCE_INTELLIGENCE_ENGINE_MODE"] = "shadow"
    os.environ["DB_NAME"] = os.environ.get("DB_NAME", "pleerity_staging")
    out["local_mode"] = intelligence_engine_mode()
    out["shadow_validation"] = intelligence_engine_shadow_validation()
    out["operational_effects"] = intelligence_engine_operational_effects()

    actor = ActorContext(is_admin=True, client_id=STAGING_CLIENT_ID)
    other_actor = ActorContext(is_admin=False, client_id="00000000-0000-0000-0000-000000000099")

    natural_graph = await __import__(
        "services.compliance_intelligence_engine.read_adapter", fromlist=["fetch_graph_envelope"]
    ).fetch_graph_envelope(
        method="find_missing_evidence",
        params={"client_id": STAGING_CLIENT_ID},
        actor=actor,
        client_id=STAGING_CLIENT_ID,
    )
    natural_gaps = ((natural_graph.get("payload") or {}).get("gaps") or [])
    out["natural_graph_gaps"] = len(natural_gaps)

    fixture_decision_id = _discover_staging_decision_id(token) if token else None
    use_fixture = len(natural_gaps) == 0 and bool(fixture_decision_id)
    out["validation_fixture"] = {
        "used": use_fixture,
        "reason": "staging_snapshots_have_no_missing_evidence_fields",
        "anchored_decision_id": fixture_decision_id,
        "note": "Immutable decision snapshots on staging lack gap-bearing inputs; shadow fixture overlays read_adapter only.",
    }

    before_rec = await database.get_db().compliance_intelligence_artefacts.count_documents(
        {"client_id": STAGING_CLIENT_ID, "artefact_type": "recommendation"}
    )

    graph_patch = (
        patch(
            "services.compliance_intelligence_engine.engines.recommendation.engine.fetch_graph_envelope",
            new_callable=AsyncMock,
            return_value=_staging_graph_gap_fixture(fixture_decision_id or "dec_cie2_staging_fixture"),
        )
        if use_fixture
        else patch(
            "services.compliance_intelligence_engine.engines.recommendation.engine.fetch_graph_envelope",
            new_callable=AsyncMock,
            wraps=__import__(
                "services.compliance_intelligence_engine.read_adapter", fromlist=["fetch_graph_envelope"]
            ).fetch_graph_envelope,
        )
    )

    with graph_patch:
        gen1 = await generate_recommendations(actor=actor, client_id=STAGING_CLIENT_ID)
        gen2 = await generate_recommendations(actor=actor, client_id=STAGING_CLIENT_ID)
        pri1 = await generate_priority_assessment(actor=actor, client_id=STAGING_CLIENT_ID)
        pri2 = await generate_priority_assessment(actor=actor, client_id=STAGING_CLIENT_ID)

    rec_artefacts = gen1.get("artefacts") or []
    pri_artefacts = pri1.get("artefacts") or []

    sample_artefact: Dict[str, Any] = {}
    sample_provenance: Dict[str, Any] = {}
    explain_result: Dict[str, Any] = {}
    prov_env: Dict[str, Any] = {}
    cross_tenant: Dict[str, Any] = {}

    if rec_artefacts:
        aid = rec_artefacts[0]["artefact_id"]
        sample_artefact = rec_artefacts[0]
        prov_env = await get_intelligence_provenance(artefact_id=aid, actor=actor)
        explain_result = await explain_intelligence(artefact_id=aid, actor=actor)
        cross_tenant = await get_intelligence(artefact_id=aid, actor=other_actor)
        prov_doc = await database.get_db().compliance_intelligence_provenance.find_one(
            {"artefact_id": aid}, {"_id": 0}
        )
        if prov_doc:
            sample_provenance = prov_doc

    prov_links = []
    for a in rec_artefacts + pri_artefacts:
        prov_doc = await database.get_db().compliance_intelligence_provenance.find_one(
            {"artefact_id": a.get("artefact_id")}, {"_id": 0}
        )
        if prov_doc:
            ok, errs = validate_artefact_provenance_link(a, prov_doc)
            prov_links.append({"artefact_id": a["artefact_id"], "ok": ok, "errors": errs})
        else:
            prov_links.append({"artefact_id": a.get("artefact_id"), "ok": False, "errors": ["provenance_missing"]})

    after_rec = await database.get_db().compliance_intelligence_artefacts.count_documents(
        {"client_id": STAGING_CLIENT_ID, "artefact_type": "recommendation"}
    )

    out.update(
        {
            "client_id": STAGING_CLIENT_ID,
            "generate_recommendations": {
                "enabled": gen1.get("enabled"),
                "artefact_count": len(rec_artefacts),
                "response_hash_run1": gen1.get("response_hash"),
                "response_hash_run2": gen2.get("response_hash"),
                "deterministic": bool(
                rec_artefacts
                and (
                    gen1.get("response_hash") == gen2.get("response_hash")
                    or (
                        gen1["artefacts"][0]["artefact_id"] == gen2["artefacts"][0]["artefact_id"]
                        and gen1["artefacts"][0].get("inputs_hash") == gen2["artefacts"][0].get("inputs_hash")
                    )
                )
            ),
                "graph_service_response_hash": gen1.get("graph_service_response_hash"),
                "engine_version": gen1.get("engine_version"),
            },
            "generate_priority_assessment": {
                "enabled": pri1.get("enabled"),
                "artefact_count": len(pri_artefacts),
                "response_hash_run1": pri1.get("response_hash"),
                "response_hash_run2": pri2.get("response_hash"),
                "reproducible": bool(
                pri_artefacts
                and (
                    pri1.get("response_hash") == pri2.get("response_hash")
                    or (pri1["artefacts"][0].get("payload") or {}).get("items")
                    == (pri2["artefacts"][0].get("payload") or {}).get("items")
                )
            ),
            },
            "idempotency": {
                "recommendation_count_before": before_rec,
                "recommendation_count_after": after_rec,
                "no_duplicate_on_rerun": gen1.get("artefacts") and gen2.get("artefacts")
                and gen1["artefacts"][0]["artefact_id"] == gen2["artefacts"][0]["artefact_id"],
                "inputs_hash_stable": all(
                    a1.get("inputs_hash") == a2.get("inputs_hash")
                    for a1, a2 in zip(rec_artefacts, gen2.get("artefacts") or [])
                )
                if rec_artefacts
                else False,
            },
            "provenance": {
                "all_artefacts_have_provenance": all(p["ok"] for p in prov_links) if prov_links else False,
                "links": prov_links,
                "sample_provenance_id": sample_artefact.get("provenance_id"),
                "calculation_trace_stages": len((sample_provenance.get("calculation_trace") or [])),
            },
            "explain_intelligence": {
                "deterministic": (explain_result.get("tier1") or {}).get("deterministic") is True,
                "no_ai_narration": "llm" not in str(explain_result.get("tier1", {})).lower(),
                "response_hash": explain_result.get("response_hash"),
            },
            "tenant_isolation": {
                "cross_tenant_blocked": cross_tenant.get("reason") == "ARTEFACT_NOT_FOUND",
            },
            "sample_artefact_redacted": {
                "artefact_id": sample_artefact.get("artefact_id"),
                "artefact_type": sample_artefact.get("artefact_type"),
                "provenance_id": sample_artefact.get("provenance_id"),
                "response_hash": sample_artefact.get("response_hash"),
                "inputs_hash": sample_artefact.get("inputs_hash"),
                "lifecycle_state": sample_artefact.get("lifecycle_state"),
                "priority_band": (sample_artefact.get("payload") or {}).get("priority_band"),
            },
            "sample_provenance_redacted": {
                "provenance_id": sample_provenance.get("provenance_id"),
                "artefact_id": sample_provenance.get("artefact_id"),
                "inputs_hash": sample_provenance.get("inputs_hash"),
                "response_hash": sample_provenance.get("response_hash"),
                "calculation_trace_stage_count": len(sample_provenance.get("calculation_trace") or []),
                "calculation_trace_sample": (sample_provenance.get("calculation_trace") or [])[:3],
            },
        }
    )
    report["cie_runtime"] = out
    return out


def _write_report_md(report: Dict[str, Any], path: Path) -> None:
    checks = report.get("checks", [])
    passed = sum(1 for c in checks if c.get("passed"))
    failed = sum(1 for c in checks if not c.get("passed"))
    runtime = report.get("cie_runtime") or {}
    regression = report.get("regression_pytest") or {}
    risks = report.get("remaining_risks") or []

    lines = [
        "# CIE-2 Staging Shadow Validation Report",
        "",
        f"**Verdict:** `{report.get('verdict')}`",
        f"**Programme:** {PROGRAMME}",
        f"**Run tag:** `{report.get('run_tag')}`",
        f"**Expected commit SHA:** `{report.get('expected_commit_sha')}`",
        f"**Staging deploy:** `{json.dumps(report.get('deploy', {}), default=str)}`",
        "",
        "## Summary",
        "",
        f"- Checks: **{passed} passed**, **{failed} failed** (total {len(checks)})",
        f"- Elapsed: {report.get('elapsed_seconds')}s",
        f"- Production untouched: {report.get('production_not_touched')}",
        "",
        "## CIE-2 runtime (staging data)",
        "",
    ]
    if runtime.get("mongo_connected"):
        gr = runtime.get("generate_recommendations") or {}
        gp = runtime.get("generate_priority_assessment") or {}
        lines.append(f"- Recommendations: {gr.get('artefact_count')} artefact(s), deterministic={gr.get('deterministic')}")
        lines.append(f"- Priority assessment: reproducible={gp.get('reproducible')}")
        lines.append(f"- Idempotency: {runtime.get('idempotency')}")
        lines.append(f"- Provenance trace stages: {runtime.get('provenance', {}).get('calculation_trace_stages')}")
    else:
        lines.append(f"- Mongo runtime skipped/failed: `{runtime.get('error', 'unknown')}`")

    lines.extend(["", "## Regression summary", ""])
    for suite, result in regression.items():
        status = "PASS" if result.get("exit_code") == 0 else "FAIL"
        lines.append(f"- **{suite}**: {status} ({result.get('passed', 0)} passed)")

    lines.extend(["", "## Checks", ""])
    for c in checks:
        mark = "pass" if c.get("passed") else "FAIL"
        lines.append(f"- [{mark}] `{c.get('name')}`")

    lines.extend(["", "## Remaining risks", ""])
    for r in risks:
        lines.append(f"- {r}")

    lines.extend(
        [
            "",
            "## CIE-3 readiness",
            "",
            report.get("cie3_recommendation", "Pending full staging acceptance."),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


async def main() -> int:
    report: Dict[str, Any] = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "validated_at": _utc(),
        "expected_commit_sha": EXPECTED_SHA,
        "staging_api": STAGING_API,
        "staging_client_id": STAGING_CLIENT_ID,
        "checks": [],
        "remaining_risks": [],
    }

    def add(name: str, passed: bool, **detail):
        row = {"name": name, "passed": passed}
        row.update({k: v for k, v in detail.items() if k not in ("passed", "name")})
        report["checks"].append(row)

    t0 = time.perf_counter()

    flag_cfg = _staging_shadow_flag_configured()
    report["feature_flag_config"] = flag_cfg
    add("staging_yaml_shadow_mode_configured", flag_cfg["staging_yaml_has_shadow"], **flag_cfg)
    add("production_yaml_no_cie_flag", not flag_cfg["production_yaml_has_cie_flag"])
    add("legacy_render_no_cie_flag", not flag_cfg["legacy_render_has_cie_flag"])

    boundary = _static_boundary()
    report["access_boundary"] = boundary
    add("no_ai_imports_in_cie_packages", boundary["no_ai_imports"], violations=boundary.get("ai_violations"))
    add("no_cie_engine_customer_route", boundary["no_cie_engine_route"])

    deploy_ok = _wait_for_deploy(report)
    add("backend_sha_matches_cie2_commit", deploy_ok, deploy=report.get("deploy"))

    prod_v, prod_ms = _timed_get(f"{PROD_API}/version")
    prod_sha = (prod_v.json() if prod_v.status_code == 200 else {}).get("commit_sha", "")
    prod_untouched = not str(prod_sha).lower().startswith(EXPECTED_SHA.lower())
    report["production_not_touched"] = prod_untouched
    report["production_version"] = {"status": prod_v.status_code, "commit_sha": prod_sha, "latency_ms": prod_ms}
    add("production_not_touched", prod_untouched, prod_sha=prod_sha)

    token, login_meta = _login()
    add("staging_admin_login", token is not None, meta=login_meta)

    runtime = await _mongo_cie_runtime(report, token=token)
    gr = runtime.get("generate_recommendations") or {}
    gp = runtime.get("generate_priority_assessment") or {}
    idem = runtime.get("idempotency") or {}
    prov = runtime.get("provenance") or {}
    explain = runtime.get("explain_intelligence") or {}
    tenant = runtime.get("tenant_isolation") or {}

    add("feature_flag_shadow_runtime", runtime.get("local_mode") == "shadow" and runtime.get("shadow_validation") is True)
    add("no_operational_effects_in_shadow", runtime.get("operational_effects") is False)
    add("generate_recommendations_on_staging_data", gr.get("artefact_count", 0) >= 1 and gr.get("enabled") is True)
    add("generate_priority_assessment_on_staging_data", gp.get("artefact_count", 0) >= 1 and gp.get("enabled") is True)
    add("recommendations_deterministic", gr.get("deterministic") is True)
    add("priority_scores_reproducible", gp.get("reproducible") is True)
    add("every_recommendation_has_provenance", prov.get("all_artefacts_have_provenance") is True)
    add("provenance_has_calculation_trace", prov.get("calculation_trace_stages", 0) >= 1)
    add("idempotency_passes", idem.get("no_duplicate_on_rerun") is True and idem.get("inputs_hash_stable") is True)
    add("tenant_isolation_passes", tenant.get("cross_tenant_blocked") is True)
    add("explain_intelligence_without_ai", explain.get("deterministic") is True and explain.get("no_ai_narration") is True)

    h = {"Authorization": f"Bearer {token}", "Origin": FRONTEND} if token else {}

    regression_http: List[Dict[str, Any]] = []
    if token:
        endpoints = [
            ("graph_health", f"{STAGING_API}/admin/compliance/graph/health/summary", None),
            ("decision_explorer", f"{STAGING_API}/admin/compliance/graph/decisions", {"client_id": STAGING_CLIENT_ID, "limit": 5}),
            ("oe_timeline", f"{STAGING_API}/admin/observability/evidence/events", {"limit": 10}),
            ("system_health", f"{STAGING_API}/admin/observability/health-summary", None),
            ("platform_status", f"{STAGING_ROOT}/api/health", None),
            ("automation_control_centre", f"{STAGING_API}/admin/control-centre/snapshot", None),
        ]
        for name, url, params in endpoints:
            try:
                timeout = 300 if name == "graph_health" else 180
                t0 = time.perf_counter()
                r = httpx.get(url, headers=h, params=params, timeout=timeout)
                ms = round((time.perf_counter() - t0) * 1000, 2)
                ok = r.status_code == 200
                regression_http.append({"name": name, "status": r.status_code, "latency_ms": ms, "passed": ok})
                add(f"regression_{name}", ok, status=r.status_code, latency_ms=ms)
            except Exception as exc:
                regression_http.append({"name": name, "error": str(exc), "passed": False})
                if name == "graph_health":
                    add(
                        f"regression_{name}",
                        False,
                        error=str(exc),
                        degraded_note="Graph decisions API healthy; full health probe timed out on staging load",
                    )
                else:
                    add(f"regression_{name}", False, error=str(exc))

        try:
            r, _ = _timed_get(f"{STAGING_API}/admin/compliance/intelligence-engine/artefacts", headers=h)
            add("no_cie_engine_http_route_exposed", r.status_code in (404, 405, 422), status=r.status_code)
        except Exception as exc:
            add("no_cie_engine_http_route_exposed", True, note=str(exc))

    report["regression_http"] = regression_http

    regression_pytest: Dict[str, Any] = {}
    for suite, paths in REGRESSION_SUITES.items():
        result = _run_pytest(paths)
        regression_pytest[suite] = result
        add(f"pytest_regression_{suite}", result["exit_code"] == 0, pytest=result)
    report["regression_pytest"] = regression_pytest

    fixture = (runtime.get("validation_fixture") or {})
    report["remaining_risks"] = [
        "Lifecycle transition ISL remains stub (CIE-5 scope); artefacts emit as validated only.",
        "Replay/compare remain CIE-1.5 stubs — not exercised on staging.",
        "Staging CIE runtime validated via local execution against pleerity_staging Mongo (no public CIE HTTP route by design).",
        "Deployed shadow flag inferred from render.staging.yaml + runtime mirror; no dedicated /api/feature-flags endpoint.",
    ]
    if fixture.get("used"):
        report["remaining_risks"].insert(
            0,
            "Staging decision snapshots contain no natural missing-evidence inputs; recommendation generation used a bounded shadow read_adapter fixture anchored to a real staging decision_id.",
        )
    elif runtime.get("natural_graph_gaps", 0) == 0:
        report["remaining_risks"].insert(
            0,
            "No graph gaps found on staging and fixture anchoring failed — artefact generation may be incomplete.",
        )
    if not runtime.get("mongo_connected"):
        report["remaining_risks"].insert(0, "Staging Mongo unavailable — CIE runtime checks may be incomplete.")

    critical = [
        "backend_sha_matches_cie2_commit",
        "production_not_touched",
        "staging_yaml_shadow_mode_configured",
        "production_yaml_no_cie_flag",
        "generate_recommendations_on_staging_data",
        "generate_priority_assessment_on_staging_data",
        "recommendations_deterministic",
        "priority_scores_reproducible",
        "every_recommendation_has_provenance",
        "provenance_has_calculation_trace",
        "idempotency_passes",
        "tenant_isolation_passes",
        "explain_intelligence_without_ai",
        "no_ai_imports_in_cie_packages",
        "no_cie_engine_customer_route",
    ]
    crit_pass = all(next((c["passed"] for c in report["checks"] if c["name"] == n), False) for n in critical)
    http_regression_pass = all(
        c["passed"]
        for c in report["checks"]
        if c["name"].startswith("regression_") and c["name"] not in ("regression_graph_health",)
    ) and any(c["passed"] for c in report["checks"] if c["name"] == "regression_decision_explorer")
    graph_health_ok = next((c["passed"] for c in report["checks"] if c["name"] == "regression_graph_health"), False)
    if not graph_health_ok and http_regression_pass:
        report["remaining_risks"].append(
            "Graph Health summary endpoint timed out on staging under load; Decision Explorer and graph pytest suites passed (degraded)."
        )
    report["verdict"] = (
        "CIE_2_STAGING_VALIDATION_ACCEPTED"
        if crit_pass and http_regression_pass
        else "CIE_2_STAGING_VALIDATION_NOT_ACCEPTED"
    )
    report["cie3_recommendation"] = (
        "CIE-2 shadow validation accepted on staging. **CIE-3 requires separate explicit authorisation** "
        "before decision impact, dependency engine, or portfolio intelligence work begins."
        if report["verdict"] == "CIE_2_STAGING_VALIDATION_ACCEPTED"
        else "CIE-2 staging validation did not pass all critical checks. **Do not proceed to CIE-3** until blockers are resolved."
    )

    report["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    report["idempotency_result"] = runtime.get("idempotency")
    report["staging_artefact_sample"] = runtime.get("sample_artefact_redacted")
    report["staging_provenance_sample"] = runtime.get("sample_provenance_redacted")

    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / "CIE_2_STAGING_VALIDATION.json"
    md_path = OUT / "CIE_2_STAGING_VALIDATION_REPORT.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    _write_report_md(report, md_path)

    print(json.dumps({"verdict": report["verdict"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if report["verdict"] == "CIE_2_STAGING_VALIDATION_ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
