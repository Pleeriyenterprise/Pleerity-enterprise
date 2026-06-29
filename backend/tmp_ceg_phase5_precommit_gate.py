"""CEG Phase 5 AI Intelligence pre-commit validation gate (do not commit until PHASE_5_COMMIT_READY)."""
from __future__ import annotations

import ast
import asyncio
import inspect
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv

load_dotenv()
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]

BACKEND = Path(__file__).resolve().parent
OUT = BACKEND / "docs/audit/compliance_evidence_graph_and_explainable_intelligence_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

APPROVED_GRAPH_METHODS = {
    "explain_decision",
    "replay_decision",
    "compare_decision",
    "compare_decision_snapshots",
    "find_historical_decision",
    "trace_evidence",
    "trace_requirement",
    "find_decision_dependencies",
    "find_affected_properties",
    "find_affected_requirements",
    "find_missing_evidence",
    "find_superseded_evidence",
    "trace_operational_impact",
    "list_decisions",
}

SAMPLE_ENVELOPE = {
    "service": "explain_decision",
    "insufficient_evidence": False,
    "authoritative_references": {"decision_id": "dec_p5_gate", "snapshot_id": "snap_p5_gate", "node_ids": ["n1"]},
    "payload": {
        "executive_summary": "Gate test",
        "decision": {"decision_id": "dec_p5_gate", "decision_outcome": "VALID"},
    },
}

FORBIDDEN_AUTHORITY_KEYS = {
    "new_score",
    "score_after",
    "requirement_status",
    "decision_outcome_override",
    "recommended_action",
    "rule_override",
}


def _run_pytest(paths: List[str]) -> dict:
    cmd = [sys.executable, "-m", "pytest", *paths, "-q", "--tb=line"]
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) passed", out)
    passed = int(m.group(1)) if m else 0
    m_fail = re.search(r"(\d+) failed", out)
    failed = int(m_fail.group(1)) if m_fail else 0
    return {"exit_code": proc.returncode, "passed": passed, "failed": failed, "output_tail": out[-4000:]}


def _pkg_storage_violations() -> List[str]:
    pkg = BACKEND / "services" / "compliance_intelligence"
    violations = []
    for py in pkg.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "compliance_evidence_graph.storage" in text:
            violations.append(py.name)
    return violations


def _dispatch_methods_from_source() -> Set[str]:
    src = (BACKEND / "services" / "compliance_intelligence" / "graph_dispatch.py").read_text(encoding="utf-8")
    return set(re.findall(r'if m == "([a-z_]+)"', src))


async def main() -> int:
    from fastapi import HTTPException

    from services.compliance_evidence_graph.config import graph_consumers_enabled, graph_mode
    from services.compliance_graph_service.access import ActorContext
    from services.compliance_intelligence.config import intelligence_enabled, intelligence_narration_enabled
    from services.compliance_intelligence.graph_dispatch import dispatch_graph_method
    from services.compliance_intelligence.hashing import envelope_hash
    from services.compliance_intelligence.investigate import investigate
    from services.compliance_intelligence.post_validator import validate_and_strip_narration
    from services.compliance_intelligence.prompts import SYSTEM_PROMPT
    from services.compliance_intelligence import narrations as narrations_module

    report: Dict[str, Any] = {
        "programme": "CEG-PHASE-5-AI-INTELLIGENCE-PRE-COMMIT-VALIDATION-GATE",
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

    # --- Architecture / access boundary ---
    storage_violations = _pkg_storage_violations()
    add("intelligence_no_storage_imports", len(storage_violations) == 0, violations=storage_violations)

    dispatch_src = (BACKEND / "services" / "compliance_intelligence" / "graph_dispatch.py").read_text(encoding="utf-8")
    add(
        "graph_dispatch_graph_service_only",
        "compliance_graph_service import service" in dispatch_src
        and "compliance_evidence_graph.storage" not in dispatch_src,
    )
    dispatch_methods = _dispatch_methods_from_source()
    add(
        "graph_dispatch_approved_methods_only",
        dispatch_methods.issubset(APPROVED_GRAPH_METHODS) and len(dispatch_methods) >= 10,
        methods=sorted(dispatch_methods),
    )

    intel_route = (BACKEND / "routes" / "compliance_intelligence.py").read_text(encoding="utf-8")
    add(
        "admin_intelligence_route_guarded",
        "admin_route_guard" in intel_route
        and "/api/admin/compliance/intelligence/investigate" in intel_route
        and "compliance_evidence_graph.storage" not in intel_route,
    )

    # No customer-facing intelligence routes in frontend
    app_js = (BACKEND.parent / "frontend" / "src" / "App.js").read_text(encoding="utf-8")
    add(
        "no_customer_intelligence_ui",
        "compliance/intelligence" not in app_js and "Intelligence" not in app_js.split("AdminCompliance")[0],
    )

    # --- Feature flag matrix ---
    flag_matrix = {}
    for mode in ("disabled", "shadow", "enabled"):
        os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = mode
        os.environ["AI_ENABLED"] = "true"
        os.environ["OPENAI_API_KEY"] = "test-key"
        os.environ["COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED"] = "true"
        flag_matrix[mode] = {
            "graph_mode": graph_mode(),
            "tier1": intelligence_enabled(),
            "tier2": intelligence_narration_enabled(),
        }
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "enabled"
    os.environ["AI_ENABLED"] = "false"
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("COMPLIANCE_INTELLIGENCE_NARRATION_ENABLED", None)
    flag_matrix["enabled_no_ai"] = {
        "tier1": intelligence_enabled(),
        "tier2": intelligence_narration_enabled(),
    }
    report["sections"]["feature_flag_matrix"] = flag_matrix

    add(
        "feature_flag_disabled_tier1_off",
        not flag_matrix["disabled"]["tier1"] and not flag_matrix["disabled"]["tier2"],
    )
    add(
        "feature_flag_shadow_tier1_off",
        not flag_matrix["shadow"]["tier1"] and not flag_matrix["shadow"]["tier2"],
    )
    add(
        "feature_flag_enabled_tier1_on",
        flag_matrix["enabled"]["tier1"] is True,
    )
    add(
        "feature_flag_tier2_requires_both_flags",
        flag_matrix["enabled"]["tier2"] is True and flag_matrix["enabled_no_ai"]["tier2"] is False,
    )

    # --- Tier behaviour ---
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "disabled"
    disabled = await investigate(
        method="explain_decision",
        params={"decision_id": "dec_x"},
        actor=ActorContext(is_admin=True),
    )
    add(
        "investigate_disabled_safe_response",
        disabled.get("enabled") is False and disabled.get("insufficient_evidence") is True and disabled.get("tier1") is None,
    )

    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "enabled"
    with patch(
        "services.compliance_intelligence.investigate.dispatch_graph_method",
        new_callable=AsyncMock,
        return_value={**SAMPLE_ENVELOPE, "insufficient_evidence": True, "payload": {"reason": "missing"}},
    ):
        insuf = await investigate(
            method="explain_decision",
            params={"decision_id": "dec_missing"},
            actor=ActorContext(is_admin=True),
            narrate=True,
        )
    add(
        "tier2_blocked_on_insufficient_tier1",
        insuf["tier1"]["insufficient_evidence"] is True
        and insuf["tier2"]["insufficient_evidence"] is True
        and insuf["tier2"]["paragraphs"] == [],
    )

    llm_json = json.dumps(
        {
            "paragraphs": [
                {
                    "text": "Valid cited fact.",
                    "authoritative_references": {"decision_id": "dec_p5_gate"},
                    "confidence": 90,
                },
                {
                    "text": "Invented uncited claim.",
                    "authoritative_references": {"decision_id": "dec_other_tenant"},
                    "confidence": 50,
                },
            ],
            "insufficient_evidence": False,
        }
    )
    with patch(
        "services.compliance_intelligence.investigate.dispatch_graph_method",
        new_callable=AsyncMock,
        return_value=SAMPLE_ENVELOPE,
    ), patch(
        "services.compliance_intelligence.investigate.intelligence_narration_enabled",
        return_value=True,
    ), patch("utils.llm_chat.chat_openai", new_callable=AsyncMock, return_value=llm_json), patch(
        "services.compliance_intelligence.investigate.store_narration",
        new_callable=AsyncMock,
        return_value="nar_gate",
    ):
        narrated = await investigate(
            method="explain_decision",
            params={"decision_id": "dec_p5_gate", "client_id": "client-a"},
            actor=ActorContext(is_admin=True, client_id="client-a"),
            client_id="client-a",
            narrate=True,
        )
    tier1_hash_before = envelope_hash(SAMPLE_ENVELOPE)
    tier1_hash_after = envelope_hash(narrated["tier1"])
    add(
        "tier1_unchanged_by_tier2",
        tier1_hash_before == tier1_hash_after and narrated["tier1"] == SAMPLE_ENVELOPE,
    )
    add(
        "citation_strips_uncited_paragraphs",
        len(narrated["tier2"]["paragraphs"]) == 1
        and narrated["tier2"]["paragraphs"][0]["authoritative_references"]["decision_id"] == "dec_p5_gate",
    )

    stripped_all = validate_and_strip_narration(
        {
            "paragraphs": [{"text": "bad", "authoritative_references": {"decision_id": "dec_fake"}}],
            "insufficient_evidence": False,
            "graph_service_response_hash": "sha256:x",
        },
        SAMPLE_ENVELOPE,
    )
    add(
        "citation_prefers_empty_over_unsupported",
        stripped_all["paragraphs"] == [] and stripped_all["insufficient_evidence"] is True,
    )

    node_cited = validate_and_strip_narration(
        {
            "paragraphs": [
                {"text": "node ok", "authoritative_references": {"node_ids": ["n1"]}},
                {"text": "node bad", "authoritative_references": {"node_ids": ["n999"]}},
            ],
            "insufficient_evidence": False,
            "graph_service_response_hash": "sha256:x",
        },
        SAMPLE_ENVELOPE,
    )
    add(
        "citation_node_ids_validated_against_envelope",
        len(node_cited["paragraphs"]) == 1 and node_cited["paragraphs"][0]["text"] == "node ok",
    )

    narration_blob = json.dumps(narrated.get("tier2") or {})
    add(
        "narration_no_authority_mutations",
        not any(k in narration_blob for k in FORBIDDEN_AUTHORITY_KEYS),
    )

    # --- Prompt safety ---
    prompt_checks = {
        "uses_envelope_only": "GRAPH_SERVICE_RESPONSE" in SYSTEM_PROMPT or "present in GRAPH_SERVICE_RESPONSE" in SYSTEM_PROMPT,
        "no_invent_legislation": "Never invent legislation" in SYSTEM_PROMPT,
        "no_invent_timelines": "timelines" in SYSTEM_PROMPT.lower(),
        "no_invent_customer_actions": "customer actions" in SYSTEM_PROMPT.lower(),
        "no_invent_operational_causes": "operational causes" in SYSTEM_PROMPT.lower(),
        "insufficient_evidence_instruction": "insufficient_evidence" in SYSTEM_PROMPT,
        "no_legal_advice_beyond_platform": "legal advice" in SYSTEM_PROMPT.lower(),
        "distinguish_missing_evidence": "missing" in SYSTEM_PROMPT.lower() or "insufficient" in SYSTEM_PROMPT.lower(),
    }
    report["sections"]["prompt_safety"] = prompt_checks
    add("prompt_safety_contract", all(prompt_checks.values()))

    # --- Storage schema (static) ---
    store_sig = inspect.signature(narrations_module.store_narration)
    store_src = inspect.getsource(narrations_module.store_narration)
    required_fields = [
        "narration_id",
        "client_id",
        "graph_service_response_hash",
        "citation_references",
        "prompt_version",
        "model_id",
        "actor_portal_user_id",
    ]
    add(
        "storage_record_fields",
        all(f in store_src for f in required_fields),
        required_fields=required_fields,
        params=list(store_sig.parameters.keys()),
    )
    add(
        "storage_no_secrets_in_record",
        "OPENAI_API_KEY" not in store_src and "api_key" not in store_src.lower(),
    )

    # --- Tenant isolation ---
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value={
            "decision_id": "dec_p5_gate",
            "client_id": "client-a",
            "snapshot_id": "snap_p5_gate",
            "summary": "x",
        },
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value={"snapshot_id": "snap_p5_gate", "decision_reasoning_inputs": {}},
    ):
        try:
            await dispatch_graph_method(
                method="explain_decision",
                params={"decision_id": "dec_p5_gate"},
                actor=ActorContext(is_admin=False, client_id="client-b"),
            )
            cross_blocked = False
        except HTTPException as e:
            cross_blocked = e.status_code == 403

    add("tenant_cross_client_blocked", cross_blocked)

    # --- Regression pytest ---
    regression_paths = [
        "tests/test_compliance_intelligence_phase5.py",
        "tests/test_graph_service_access_boundary.py",
        "tests/test_compliance_graph_service.py",
        "tests/test_compliance_graph_service_phase3.py",
        "tests/test_compliance_graph_health.py",
        "tests/test_graph_integrity_validator.py",
        "tests/test_ceg_producer_registry.py",
        "tests/test_ceg_decision_quality.py",
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

    # --- Runtime (optional DB, narrate=false first) ---
    runtime: Dict[str, Any] = {"connected": False, "checks": [], "narration_runtime": {}}
    sample_decision_id = None
    sample_client_id = None
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "enabled"

    try:
        from database import database
        from services.compliance_graph_service import service as graph_service

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
                    ok = isinstance(result, dict) and result.get("enabled") is True and result.get("tier1")
                    runtime["checks"].append(
                        {
                            "name": name,
                            "passed": ok,
                            "insufficient": (result.get("tier1") or {}).get("insufficient_evidence"),
                            "hash": result.get("graph_service_response_hash"),
                        }
                    )
                    return result
                except Exception as e:
                    runtime["checks"].append({"name": name, "passed": False, "error": str(e)})
                    return None

            for method, params in [
                ("explain_decision", {"decision_id": sample_decision_id}),
                ("replay_decision", {"decision_id": sample_decision_id}),
                ("compare_decision", {"left": sample_decision_id, "right": sample_decision_id}),
                (
                    "trace_evidence",
                    {"anchor_type": "decision", "anchor_id": sample_decision_id, "client_id": sample_client_id},
                ),
                ("trace_operational_impact", {"decision_id": sample_decision_id}),
            ]:
                await rt(
                    f"investigate_{method}",
                    investigate(
                        method=method,
                        params=params,
                        actor=actor,
                        client_id=sample_client_id,
                        narrate=False,
                    ),
                )
            rid = sample.get("requirement_id")
            if rid:
                await rt(
                    "investigate_trace_requirement",
                    investigate(
                        method="trace_requirement",
                        params={"requirement_id": rid, "client_id": sample_client_id},
                        actor=actor,
                        client_id=sample_client_id,
                        narrate=False,
                    ),
                )

            other = ActorContext(is_admin=False, client_id="cross-tenant-probe-999")
            try:
                await investigate(
                    method="explain_decision",
                    params={"decision_id": sample_decision_id},
                    actor=other,
                    client_id="cross-tenant-probe-999",
                    narrate=False,
                )
                runtime["checks"].append({"name": "runtime_cross_tenant_blocked", "passed": False})
            except HTTPException as e:
                runtime["checks"].append(
                    {"name": "runtime_cross_tenant_blocked", "passed": e.status_code == 403}
                )

            # Controlled narrate=true (mocked LLM)
            mock_llm = json.dumps(
                {
                    "paragraphs": [
                        {
                            "text": "Runtime cited summary.",
                            "authoritative_references": {"decision_id": sample_decision_id},
                        }
                    ],
                    "insufficient_evidence": False,
                }
            )
            with patch("utils.llm_chat.chat_openai", new_callable=AsyncMock, return_value=mock_llm), patch(
                "services.compliance_intelligence.investigate.intelligence_narration_enabled",
                return_value=True,
            ):
                narr = await investigate(
                    method="explain_decision",
                    params={"decision_id": sample_decision_id},
                    actor=actor,
                    client_id=sample_client_id,
                    narrate=True,
                )
            runtime["narration_runtime"] = {
                "passed": bool(narr.get("narration_id"))
                and len((narr.get("tier2") or {}).get("paragraphs") or []) >= 1
                and narr.get("graph_service_response_hash", "").startswith("sha256:"),
                "narration_id": narr.get("narration_id"),
                "paragraphs_kept": len((narr.get("tier2") or {}).get("paragraphs") or []),
            }
        else:
            runtime["checks"].append({"name": "sample_decisions", "passed": True, "note": "no DB decisions"})
            runtime["narration_runtime"] = {"passed": True, "note": "skipped — no sample decision"}
    except Exception as e:
        runtime["error"] = str(e)
        runtime["checks"].append({"name": "db_connect", "passed": False, "error": str(e)})
        runtime["narration_runtime"] = {"passed": True, "note": "skipped — DB unavailable"}

    report["sections"]["runtime"] = runtime
    runtime_ok = all(c.get("passed") for c in runtime["checks"]) if runtime["checks"] else True
    narration_ok = runtime["narration_runtime"].get("passed", True)
    add(
        "runtime_tier1_investigate_smoke",
        runtime_ok,
        connected=runtime["connected"],
        checks=len(runtime["checks"]),
    )
    narration_meta = dict(runtime["narration_runtime"])
    narration_meta.pop("passed", None)
    add("runtime_narration_controlled", narration_ok, **narration_meta)

    report["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)

    critical = [
        "intelligence_no_storage_imports",
        "graph_dispatch_graph_service_only",
        "graph_dispatch_approved_methods_only",
        "admin_intelligence_route_guarded",
        "no_customer_intelligence_ui",
        "feature_flag_disabled_tier1_off",
        "feature_flag_shadow_tier1_off",
        "feature_flag_enabled_tier1_on",
        "feature_flag_tier2_requires_both_flags",
        "investigate_disabled_safe_response",
        "tier2_blocked_on_insufficient_tier1",
        "tier1_unchanged_by_tier2",
        "citation_strips_uncited_paragraphs",
        "citation_prefers_empty_over_unsupported",
        "citation_node_ids_validated_against_envelope",
        "narration_no_authority_mutations",
        "prompt_safety_contract",
        "storage_record_fields",
        "storage_no_secrets_in_record",
        "tenant_cross_client_blocked",
        "regression_pytest_suite",
        "runtime_tier1_investigate_smoke",
        "runtime_narration_controlled",
    ]
    passed_map = {c["name"]: c["passed"] for c in report["checks"]}
    failed_critical = [n for n in critical if not passed_map.get(n)]
    report["critical_checks"] = critical
    report["failed_critical"] = failed_critical
    report["acceptance"] = "PHASE_5_COMMIT_READY" if not failed_critical else "NOT_COMMIT_READY"

    report["sections"]["access_boundary"] = {
        "storage_import_violations": storage_violations,
        "dispatch_methods": sorted(dispatch_methods),
        "tenant_cross_client_blocked": passed_map.get("tenant_cross_client_blocked"),
    }
    report["sections"]["citation_gating"] = {
        "strips_uncited": passed_map.get("citation_strips_uncited_paragraphs"),
        "prefers_empty": passed_map.get("citation_prefers_empty_over_unsupported"),
        "node_validation": passed_map.get("citation_node_ids_validated_against_envelope"),
    }
    report["sections"]["narration_safety"] = {
        "tier2_blocked_on_insufficient": passed_map.get("tier2_blocked_on_insufficient_tier1"),
        "tier1_immutable": passed_map.get("tier1_unchanged_by_tier2"),
        "no_authority_keys": passed_map.get("narration_no_authority_mutations"),
    }
    report["sections"]["storage_validation"] = {
        "record_fields": passed_map.get("storage_record_fields"),
        "no_secrets": passed_map.get("storage_no_secrets_in_record"),
    }
    report["sections"]["remaining_risks"] = [
        "Tier 2 narration quality depends on LLM adherence; post-validator is the safety backstop.",
        "Runtime validation uses staging/local DB decisions when connected.",
        "Frontend intelligence UI intentionally not implemented (Phase 5 slice).",
        "Customer-facing intelligence remains Phase 7 — not enabled.",
        "Production COMPLIANCE_EVIDENCE_GRAPH_MODE and narration flags must remain unchanged until staging sign-off.",
    ]

    out_json = OUT / "PHASE_5_PRE_COMMIT_VALIDATION.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = [
        "# Phase 5 Pre-Commit Validation Report",
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
        "## Access boundary",
        "",
        f"- Intelligence package storage imports: {storage_violations or 'none'}",
        f"- Graph dispatch methods: {len(dispatch_methods)} approved",
        f"- Cross-tenant blocked (403): {passed_map.get('tenant_cross_client_blocked')}",
        "",
        "## Citation gating",
        "",
        f"- Uncited paragraphs stripped: {passed_map.get('citation_strips_uncited_paragraphs')}",
        f"- Empty preferred over unsupported: {passed_map.get('citation_prefers_empty_over_unsupported')}",
        f"- Node ID validation: {passed_map.get('citation_node_ids_validated_against_envelope')}",
        "",
        "## Feature flag matrix",
        "",
        "| Mode | Tier 1 | Tier 2 |",
        "|------|--------|--------|",
    ]
    for mode in ("disabled", "shadow", "enabled"):
        row = flag_matrix[mode]
        md.append(f"| {mode} | {row['tier1']} | {row['tier2']} |")
    md.extend(
        [
            "",
            "## Narration safety",
            "",
            f"- Tier 2 blocked when Tier 1 insufficient: {passed_map.get('tier2_blocked_on_insufficient_tier1')}",
            f"- Tier 1 immutable after narration: {passed_map.get('tier1_unchanged_by_tier2')}",
            f"- No authority mutation keys in narration: {passed_map.get('narration_no_authority_mutations')}",
            "",
            "## Storage validation",
            "",
            f"- Required audit fields present: {passed_map.get('storage_record_fields')}",
            f"- No secrets in record schema: {passed_map.get('storage_no_secrets_in_record')}",
            "",
            "## Regression",
            "",
            f"- Pytest: {regression['passed']} passed, {regression['failed']} failed",
            "",
            "## Runtime",
            "",
            f"- DB connected: {runtime['connected']}",
        ]
    )
    if sample_decision_id:
        md.append(f"- Sample decision: `{sample_decision_id}` (client `{sample_client_id}`)")
    for c in runtime["checks"]:
        md.append(f"- {c['name']}: {'pass' if c.get('passed') else 'fail'}")
    md.append(f"- Controlled narration: {runtime['narration_runtime']}")
    md.extend(["", "## Remaining risks", ""])
    for r in report["sections"]["remaining_risks"]:
        md.append(f"- {r}")
    md.extend(
        [
            "",
            "## Commit readiness",
            "",
            f"**Recommendation:** `{report['acceptance']}`",
        ]
    )
    (OUT / "PHASE_5_PRE_COMMIT_VALIDATION_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({"acceptance": report["acceptance"], "failed_critical": failed_critical}, indent=2))
    return 0 if report["acceptance"] == "PHASE_5_COMMIT_READY" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
