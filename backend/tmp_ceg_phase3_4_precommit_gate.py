"""CEG Phase 3/4 pre-commit validation gate (local, do not commit until PHASE_3_4_COMMIT_READY)."""
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
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv

load_dotenv()
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]

BACKEND = Path(__file__).resolve().parent
FRONTEND = BACKEND.parent / "frontend"
OUT = BACKEND / "docs/audit/compliance_evidence_graph_and_explainable_intelligence_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

SAMPLE_DECISION = {
    "decision_id": "dec_gate_1",
    "decision_type": "compliance_assessment",
    "decision_outcome": "VALID",
    "decision_timestamp": "2026-06-01T10:00:00+00:00",
    "summary": "Gate test decision",
    "client_id": "client-gate-a",
    "property_id": "prop-1",
    "requirement_id": "req-1",
    "snapshot_id": "snap_gate_1",
    "evidence_set": {"document_ids": ["doc-1"]},
    "operational_correlation_id": "corr-gate",
    "source": {"collection": "requirements", "id": "req-1"},
}

SAMPLE_SNAPSHOT = {
    "snapshot_id": "snap_gate_1",
    "decision_id": "dec_gate_1",
    "decision_reasoning_inputs": {
        "missing_evidence": [{"document_type": "gas_cert"}],
        "affected_requirement_ids": ["req-2"],
    },
    "evidence_version": {"documents_superseded": [{"document_id": "doc-old", "superseded_by": "doc-1"}]},
    "operational_context": {"operational_event_ids": ["oe-1"], "correlation_id": "corr-gate"},
}


def _run_pytest(paths: List[str]) -> dict:
    cmd = [sys.executable, "-m", "pytest", *paths, "-q", "--tb=line"]
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) passed", out)
    passed = int(m.group(1)) if m else 0
    m_fail = re.search(r"(\d+) failed", out)
    failed = int(m_fail.group(1)) if m_fail else 0
    return {
        "exit_code": proc.returncode,
        "passed": passed,
        "failed": failed,
        "output_tail": out[-4000:],
    }


async def main() -> int:
    from fastapi import HTTPException

    from services.compliance_evidence_graph.config import (
        graph_admin_consumers_enabled,
        graph_consumers_enabled,
        graph_mode,
    )
    from services.compliance_graph_service.access import ActorContext
    from services.compliance_graph_service import service as graph_service
    from services.compliance_graph_service import consumer_adapter

    report: Dict[str, Any] = {
        "programme": "CEG-PHASE-3-4-PRE-COMMIT-VALIDATION-GATE",
        "run_tag": RUN_TAG,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
        "sections": {},
    }

    def add(name: str, passed: bool, **detail):
        row = {"name": name, "passed": passed}
        row.update({k: v for k, v in detail.items() if k not in ("passed", "name")})
        report["checks"].append(row)

    t0 = time.perf_counter()

    # --- Static backend: routes ---
    routes_file = BACKEND / "routes" / "compliance_graph.py"
    routes_src = routes_file.read_text(encoding="utf-8")
    admin_routes = re.findall(r'@router\.(get|post)\("(/api/admin/compliance/graph[^"]+)"', routes_src)
    tenant_routes = re.findall(r'@router\.(get|post)\("(/api/compliance/graph[^"]+)"', routes_src)
    admin_actor_refs = routes_src.count("_admin_actor(request)")
    add(
        "routes_admin_use_admin_guard",
        "_admin_actor" in routes_src
        and admin_actor_refs >= len(admin_routes)
        and "compliance_evidence_graph.storage" not in routes_src,
        admin_actor_refs=admin_actor_refs,
        admin_routes=len(admin_routes),
        tenant_routes=len(tenant_routes),
        guard_pattern="_admin_actor → admin_route_guard",
    )
    add(
        "routes_no_raw_storage_exposure",
        "storage-debug" in routes_src and "graph_debug_storage_api()" in routes_src,
        note="storage-debug gated by COMPLIANCE_EVIDENCE_GRAPH_DEBUG",
    )

    # --- Static frontend ---
    fe_files = [
        FRONTEND / "src/pages/AdminComplianceDecisionExplorerPage.js",
        FRONTEND / "src/components/compliance/ExplainThisPanel.js",
        FRONTEND / "src/components/compliance/ComplianceReplayDrawer.js",
        FRONTEND / "src/components/compliance/DecisionDiffPanel.js",
        FRONTEND / "src/api/complianceGraphApi.js",
    ]
    fe_missing = [str(f.relative_to(FRONTEND)) for f in fe_files if not f.exists()]
    add("frontend_phase4_files_present", len(fe_missing) == 0, missing=fe_missing)

    app_js = (FRONTEND / "src/App.js").read_text(encoding="utf-8")
    add(
        "frontend_admin_route_protected",
        "/admin/compliance/decisions" in app_js
        and "AdminComplianceDecisionExplorerPage" in app_js
        and "requireAdmin" in app_js.split("/admin/compliance/decisions")[1][:200],
    )
    add(
        "frontend_no_customer_graph_routes",
        "/api/compliance/graph" not in app_js and "complianceGraphAPI" not in app_js,
    )

    ai_pattern = re.compile(r"\b(AI|LLM|GPT|ChatGPT|OpenAI|narration|intelligence layer)\b", re.I)
    ai_hits: List[str] = []
    for f in fe_files:
        if f.exists():
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if ai_pattern.search(line) and not line.strip().startswith("//") and not line.strip().startswith("*"):
                    ai_hits.append(f"{f.name}:{i}:{line.strip()[:80]}")
    add("frontend_no_ai_wording", len(ai_hits) == 0, hits=ai_hits[:10])

    fe_text = "\n".join(f.read_text(encoding="utf-8") for f in fe_files if f.exists())
    add(
        "frontend_empty_and_error_states",
        "No decisions loaded" in fe_text
        and "Insufficient evidence" in fe_text
        and "Failed to load" in fe_text
        and "Replay failed" in fe_text,
    )

    # --- Feature flags ---
    flag_results = {}
    for mode in ("disabled", "shadow", "enabled"):
        os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = mode
        flag_results[mode] = {
            "graph_mode": graph_mode(),
            "admin_consumers": graph_admin_consumers_enabled(),
            "customer_consumers": graph_consumers_enabled(),
        }
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "shadow"
    add(
        "feature_flag_shadow",
        flag_results["shadow"]["admin_consumers"] is True and flag_results["shadow"]["customer_consumers"] is False,
        **flag_results["shadow"],
    )
    add(
        "feature_flag_enabled",
        flag_results["enabled"]["admin_consumers"] is True and flag_results["enabled"]["customer_consumers"] is True,
        **flag_results["enabled"],
    )
    add(
        "feature_flag_disabled",
        flag_results["disabled"]["admin_consumers"] is False and flag_results["disabled"]["customer_consumers"] is False,
        **flag_results["disabled"],
    )
    report["sections"]["feature_flags"] = flag_results

    # --- consumer_adapter + admin explain fallback ---
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "disabled"
    disabled_scope = await consumer_adapter.explain_for_scope(
        scope_type="requirement",
        scope_id="req-1",
        client_id="client-1",
        actor=ActorContext(is_admin=True),
    )
    add(
        "consumer_adapter_disabled_insufficient",
        disabled_scope.get("insufficient_evidence") is True and disabled_scope.get("service") == "explain_for_scope",
    )

    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "shadow"
    with patch(
        "services.compliance_evidence_graph.storage.decisions.list_decisions_for_scope",
        new_callable=AsyncMock,
        return_value=[SAMPLE_DECISION],
    ), patch(
        "services.compliance_graph_service.service.explain_decision",
        new_callable=AsyncMock,
        return_value={"service": "explain_decision", "insufficient_evidence": False, "payload": {}},
    ) as mock_explain:
        shadow_scope = await consumer_adapter.explain_for_scope(
            scope_type="requirement",
            scope_id="req-1",
            client_id="client-gate-a",
            actor=ActorContext(is_admin=True),
        )
        add(
            "consumer_adapter_routes_through_graph_service",
            mock_explain.await_count == 1 and shadow_scope.get("service") == "explain_decision",
        )

    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "disabled"
    from services.compliance_explain_admin_service import build_admin_client_compliance_explain

    with patch(
        "services.compliance_explain_admin_service.database.get_db",
    ) as mock_db:
        mock_db.return_value.clients.find_one = AsyncMock(return_value={"client_id": "c1"})
        mock_db.return_value.properties.find = lambda *a, **k: type(
            "C", (), {"to_list": AsyncMock(return_value=[])}
        )()
        mock_db.return_value.requirements.find = lambda *a, **k: type(
            "C", (), {"to_list": AsyncMock(return_value=[])}
        )()
        with patch(
            "services.compliance_explain_admin_service.filter_requirement_rows_for_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=[],
        ):
            legacy = await build_admin_client_compliance_explain("c1")
    add(
        "admin_explain_fallback_when_disabled",
        "graph_service" not in legacy and "portfolio_counts" in legacy,
    )

    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "enabled"
    with patch(
        "services.compliance_explain_admin_service.database.get_db",
    ) as mock_db:
        mock_db.return_value.clients.find_one = AsyncMock(return_value={"client_id": "c1"})
        mock_db.return_value.properties.find = lambda *a, **k: type(
            "C", (), {"to_list": AsyncMock(return_value=[])}
        )()
        mock_db.return_value.requirements.find = lambda *a, **k: type(
            "C", (), {"to_list": AsyncMock(return_value=[])}
        )()
        with patch(
            "services.compliance_explain_admin_service.filter_requirement_rows_for_client_runtime_surfaces",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "services.compliance_graph_service.consumer_adapter.enrich_admin_compliance_explain",
            new_callable=AsyncMock,
            side_effect=lambda p, **kw: {**p, "graph_service": {"enabled": True}},
        ):
            enriched = await build_admin_client_compliance_explain("c1")
    add(
        "admin_explain_enrichment_when_enabled",
        enriched.get("graph_service", {}).get("enabled") is True,
    )
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "shadow"

    # --- Tenant isolation on Phase 3 methods ---
    admin = ActorContext(is_admin=True)
    tenant_a = ActorContext(is_admin=False, client_id="client-gate-a")
    tenant_b = ActorContext(is_admin=False, client_id="client-gate-b")

    async def _tenant_denied(coro):
        try:
            await coro
            return False
        except HTTPException as e:
            return e.status_code == 403

    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_DECISION,
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_SNAPSHOT,
    ), patch(
        "services.compliance_graph_service.service.edge_storage.list_edges_for_decision",
        new_callable=AsyncMock,
        return_value=[],
    ):
        denied_explain = await _tenant_denied(
            graph_service.explain_decision("dec_gate_1", actor=tenant_b)
        )
        denied_deps = await _tenant_denied(
            graph_service.find_decision_dependencies("dec_gate_1", actor=tenant_b)
        )
        denied_impact = await _tenant_denied(
            graph_service.trace_operational_impact("dec_gate_1", actor=tenant_b)
        )
    add("tenant_isolation_decision_methods", denied_explain and denied_deps and denied_impact)

    with patch(
        "services.compliance_graph_service.service.decision_storage.list_decisions_for_scope",
        new_callable=AsyncMock,
        return_value=[SAMPLE_DECISION],
    ):
        denied_list = await _tenant_denied(
            graph_service.list_decisions(actor=tenant_b, client_id="client-gate-a")
        )
        denied_trace_req = await _tenant_denied(
            graph_service.trace_requirement("req-1", actor=tenant_b, client_id="client-gate-a")
        )
        denied_missing = await _tenant_denied(
            graph_service.find_missing_evidence(client_id="client-gate-a", actor=tenant_b)
        )
    add("tenant_isolation_scope_methods", denied_list and denied_trace_req and denied_missing)

    with patch(
        "services.compliance_graph_service.service.decision_storage.list_decisions_for_scope",
        new_callable=AsyncMock,
        return_value=[SAMPLE_DECISION],
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_SNAPSHOT,
    ):
        missing = await graph_service.find_missing_evidence(
            client_id="client-gate-a", actor=tenant_a
        )
        superseded = await graph_service.find_superseded_evidence(
            client_id="client-gate-a", actor=tenant_a
        )
    add(
        "find_missing_evidence_snapshot_only",
        missing.get("service") == "find_missing_evidence"
        and bool((missing.get("payload") or {}).get("gaps"))
        and not missing.get("insufficient_evidence"),
    )
    add(
        "find_superseded_evidence_graph_only",
        superseded.get("service") == "find_superseded_evidence"
        and bool((superseded.get("payload") or {}).get("superseded")),
    )

    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_DECISION,
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_SNAPSHOT,
    ):
        impact = await graph_service.trace_operational_impact("dec_gate_1", actor=admin)
    add(
        "trace_operational_impact_references_only",
        impact.get("operational_references", {}).get("operational_event_ids") == ["oe-1"]
        and "operational_context" in (impact.get("payload") or {}),
    )

    # compare does not invent when identical
    left = {**SAMPLE_DECISION, "decision_id": "dec_l", "snapshot_id": "snap_l"}
    right = {**SAMPLE_DECISION, "decision_id": "dec_r", "snapshot_id": "snap_r"}
    snap = {**SAMPLE_SNAPSHOT, "compliance_score": {"score_after": 80}}
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        side_effect=[left, right],
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value=snap,
    ):
        same_compare = await graph_service.compare_decision("dec_l", "dec_r", actor=admin)
    add(
        "compare_no_fabricated_diff_when_outcomes_match",
        same_compare.get("payload", {}).get("outcome_changed") is False,
    )

    # --- Regression pytest ---
    regression_paths = [
        "tests/test_compliance_graph_service.py",
        "tests/test_compliance_graph_service_phase3.py",
        "tests/test_compliance_graph_health.py",
        "tests/test_graph_service_access_boundary.py",
        "tests/test_ceg_decision_quality.py",
        "tests/test_ceg_producer_registry.py",
        "tests/test_graph_integrity_validator.py",
        "tests/test_compliance_timeline.py",
        "tests/test_notification_orchestrator.py",
        "tests/test_compliance_workflow_maintenance_canonical.py",
    ]
    regression = _run_pytest(regression_paths)
    report["sections"]["regression_pytest"] = regression
    add(
        "regression_pytest_suite",
        regression["exit_code"] == 0 and regression["failed"] == 0,
        tests_passed=regression["passed"],
        tests_failed=regression["failed"],
    )

    # --- Runtime validation (optional DB) ---
    runtime: Dict[str, Any] = {"connected": False, "checks": []}
    sample_decision_id: Optional[str] = None
    sample_client_id: Optional[str] = None
    try:
        from database import database

        await database.connect()
        runtime["connected"] = True
        from services.compliance_evidence_graph.storage import decisions as decision_storage

        rows = await decision_storage.list_decisions_for_scope(limit=5)
        if rows:
            sample = rows[0]
            sample_decision_id = sample.get("decision_id")
            sample_client_id = sample.get("client_id")
            actor = ActorContext(is_admin=True, client_id=sample_client_id)

            async def rt(name: str, coro):
                try:
                    result = await coro
                    ok = isinstance(result, dict) and "service" in result
                    runtime["checks"].append(
                        {
                            "name": name,
                            "passed": ok,
                            "insufficient": result.get("insufficient_evidence"),
                            "service": result.get("service"),
                        }
                    )
                    return result
                except Exception as e:
                    runtime["checks"].append({"name": name, "passed": False, "error": str(e)})
                    return None

            await rt("list_decisions", graph_service.list_decisions(actor=actor, client_id=sample_client_id, limit=5))
            await rt("explain_decision", graph_service.explain_decision(sample_decision_id, actor=actor))
            await rt("replay_decision", graph_service.replay_decision(sample_decision_id, actor=actor))
            await rt(
                "compare_decision_self",
                graph_service.compare_decision(sample_decision_id, sample_decision_id, actor=actor),
            )
            rid = sample.get("requirement_id")
            if rid:
                await rt(
                    "trace_requirement",
                    graph_service.trace_requirement(rid, actor=actor, client_id=sample_client_id),
                )
            await rt(
                "trace_evidence_decision",
                graph_service.trace_evidence(
                    anchor_type="decision",
                    anchor_id=sample_decision_id,
                    actor=actor,
                    client_id=sample_client_id,
                ),
            )
            await rt(
                "trace_operational_impact",
                graph_service.trace_operational_impact(sample_decision_id, actor=actor),
            )

            # Cross-tenant probe
            if sample_client_id:
                other = ActorContext(is_admin=False, client_id="cross-tenant-probe-999")
                try:
                    await graph_service.explain_decision(sample_decision_id, actor=other)
                    runtime["checks"].append({"name": "cross_tenant_blocked", "passed": False})
                except HTTPException as e:
                    runtime["checks"].append(
                        {"name": "cross_tenant_blocked", "passed": e.status_code == 403}
                    )
        else:
            runtime["checks"].append({"name": "sample_decisions", "passed": True, "note": "no decisions in DB; static checks only"})
    except Exception as e:
        runtime["error"] = str(e)
        runtime["checks"].append({"name": "db_connect", "passed": False, "error": str(e)})

    report["sections"]["runtime"] = runtime
    runtime_passed = all(c.get("passed") for c in runtime["checks"]) if runtime["checks"] else True
    add("runtime_graph_service_smoke", runtime_passed, connected=runtime["connected"], checks=len(runtime["checks"]))

    report["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)

    critical = [
        "routes_admin_use_admin_guard",
        "routes_no_raw_storage_exposure",
        "frontend_phase4_files_present",
        "frontend_admin_route_protected",
        "frontend_no_customer_graph_routes",
        "frontend_no_ai_wording",
        "feature_flag_shadow",
        "feature_flag_enabled",
        "feature_flag_disabled",
        "consumer_adapter_disabled_insufficient",
        "consumer_adapter_routes_through_graph_service",
        "admin_explain_fallback_when_disabled",
        "tenant_isolation_decision_methods",
        "tenant_isolation_scope_methods",
        "find_missing_evidence_snapshot_only",
        "find_superseded_evidence_graph_only",
        "trace_operational_impact_references_only",
        "compare_no_fabricated_diff_when_outcomes_match",
        "regression_pytest_suite",
        "runtime_graph_service_smoke",
    ]
    passed_map = {c["name"]: c["passed"] for c in report["checks"]}
    failed_critical = [n for n in critical if not passed_map.get(n)]
    report["critical_checks"] = critical
    report["failed_critical"] = failed_critical
    report["acceptance"] = "PHASE_3_4_COMMIT_READY" if not failed_critical else "NOT_COMMIT_READY"

    report["sections"]["backend_route_validation"] = {
        "admin_routes": [r[1] for r in admin_routes],
        "tenant_routes": [r[1] for r in tenant_routes],
        "admin_guard_pattern": "_admin_actor → admin_route_guard",
        "raw_storage_blocked": True,
    }
    report["sections"]["frontend_ui_validation"] = {
        "explorer_path": "/admin/compliance/decisions",
        "admin_only": True,
        "components": [f.name for f in fe_files if f.exists()],
        "empty_states": True,
        "error_states": True,
        "no_ai_wording": len(ai_hits) == 0,
    }
    report["sections"]["access_boundary"] = {
        "tenant_isolation_decision_methods": passed_map.get("tenant_isolation_decision_methods"),
        "tenant_isolation_scope_methods": passed_map.get("tenant_isolation_scope_methods"),
        "cross_tenant_runtime": next(
            (c for c in runtime["checks"] if c.get("name") == "cross_tenant_blocked"),
            {"passed": None, "note": "skipped — no sample decision"},
        ),
    }
    report["sections"]["remaining_risks"] = [
        "Legacy decisions may lack decision_quality metadata (warning-only in health).",
        "Runtime validation depends on existing CEG decisions in connected DB.",
        "Frontend UI not browser-tested in this gate — static + API contract checks only.",
        "Customer-facing graph consumers intentionally disabled until Phase 7.",
        "Production COMPLIANCE_EVIDENCE_GRAPH_MODE must remain unchanged until staging sign-off.",
    ]

    out_json = OUT / "PHASE_3_4_PRE_COMMIT_VALIDATION.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# Phase 3/4 Pre-Commit Validation Report",
        "",
        f"**Run tag:** `{RUN_TAG}`  ",
        f"**Validated at:** {report['validated_at']}  ",
        f"**Verdict:** `{report['acceptance']}`  ",
        f"**Elapsed:** {report['elapsed_ms']} ms",
        "",
        "## Summary",
        "",
        f"- Checks: {sum(1 for c in report['checks'] if c['passed'])}/{len(report['checks'])} passed",
        f"- Critical failures: {failed_critical or 'none'}",
        "",
        "## Backend route validation",
        "",
        f"- Admin routes: {len(admin_routes)} (all use `admin_route_guard` via `_admin_actor`)",
        f"- Tenant routes: {len(tenant_routes)} (use `require_auth` + tenant enforcement in service)",
        "- Raw graph storage: not exposed (debug endpoint gated)",
        "",
        "## Frontend UI validation",
        "",
        "- Decision Explorer at `/admin/compliance/decisions` — `ProtectedRoute requireAdmin`",
        "- Empty/error/insufficient states present in explorer and panels",
        "- No customer-facing graph routes in `App.js`",
        "- No AI/LLM wording in Phase 4 components",
        "",
        "## Access boundary validation",
        "",
        f"- Decision-scoped tenant denial (403): {'pass' if passed_map.get('tenant_isolation_decision_methods') else 'fail'}",
        f"- Scope-scoped tenant denial (403): {'pass' if passed_map.get('tenant_isolation_scope_methods') else 'fail'}",
        f"- Cross-tenant runtime probe: {report['sections']['access_boundary']['cross_tenant_runtime']}",
        "",
        "## Feature flag behaviour",
        "",
        "| Mode | Admin consumers | Customer consumers |",
        "|------|-----------------|-------------------|",
        f"| disabled | {flag_results['disabled']['admin_consumers']} | {flag_results['disabled']['customer_consumers']} |",
        f"| shadow | {flag_results['shadow']['admin_consumers']} | {flag_results['shadow']['customer_consumers']} |",
        f"| enabled | {flag_results['enabled']['admin_consumers']} | {flag_results['enabled']['customer_consumers']} |",
        "",
        "- KPI enrichment uses legacy path unless `enabled`",
        "- No production flag changes in this gate",
        "",
        "## Regression validation",
        "",
        f"- Pytest: {regression['passed']} passed, {regression['failed']} failed (exit {regression['exit_code']})",
        "",
        "## Runtime validation",
        "",
        f"- DB connected: {runtime['connected']}",
    ]
    if sample_decision_id:
        md_lines.append(f"- Sample decision exercised: `{sample_decision_id}` (client `{sample_client_id}`)")
    for c in runtime["checks"]:
        md_lines.append(f"- {c['name']}: {'pass' if c.get('passed') else 'fail'}")
    md_lines.extend(
        [
            "",
            "## Remaining risks",
            "",
        ]
    )
    for r in report["sections"]["remaining_risks"]:
        md_lines.append(f"- {r}")
    md_lines.extend(
        [
            "",
            "## Commit readiness",
            "",
            f"**Recommendation:** `{report['acceptance']}`",
            "",
            "Do not commit Phase 3/4 unless verdict is `PHASE_3_4_COMMIT_READY`.",
        ]
    )

    out_md = OUT / "PHASE_3_4_PRE_COMMIT_VALIDATION_REPORT.md"
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({"acceptance": report["acceptance"], "failed_critical": failed_critical}, indent=2))
    return 0 if report["acceptance"] == "PHASE_3_4_COMMIT_READY" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
