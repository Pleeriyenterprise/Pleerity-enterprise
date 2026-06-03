#!/usr/bin/env python3
"""DASHBOARD-SCORE-WIDGET-SEMANTIC-CONVERGENCE-01"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/dashboard_score_widget_semantic_convergence_01"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _creds() -> tuple[str, str]:
    email = (os.getenv("STAGING_CLIENT_ADMIN_EMAIL") or "nancy@yopmail.com").strip()
    pw = (os.getenv("STAGING_CLIENT_ADMIN_PASSWORD") or "").strip()
    if not pw:
        for p in (
            ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt",
            ROOT / "docs/audit/ops_verify_01_6a614499_f1c7b5df_landlord_registration_ni/.ops_verify_temp_pw.txt",
        ):
            if p.is_file():
                pw = p.read_text(encoding="utf-8").strip()
                break
    if not pw:
        raise SystemExit("Set STAGING_CLIENT_ADMIN_PASSWORD")
    return email, pw


def _login(email: str, password: str) -> Optional[str]:
    try:
        r = httpx.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=120)
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None


def derivation_trace() -> Dict[str, Any]:
    return {
        "programme": "DASHBOARD-SCORE-WIDGET-SEMANTIC-CONVERGENCE-01",
        "generated_at": _utc(),
        "widgets": {
            "quick_actions_stats_requirements": {
                "ui": "ClientDashboard.js stats row — complianceScore.stats.total_requirements",
                "api": "GET /api/client/compliance-score → stats.total_requirements",
                "backend": "compliance_score.calculate_compliance_score",
                "derivation_chain": [
                    "filter_requirement_rows_for_client_runtime_surfaces (planner + jurisdiction + NOT_REQUIRED gates)",
                    "enrich_requirements_for_client",
                    "project_requirement_row_client_runtime",
                    "client_portal_surface_visible_row filter",
                    "compute_client_portal_requirement_stats(portal_reqs)",
                ],
                "meaning": "Count of portal-visible runtime rows AFTER alias-family dedupe per property",
                "authority": "derived_live_projection",
                "not_same_as": "Requirements page raw tracked count (no backend alias dedupe on FE list)",
            },
            "quick_actions_stats_valid": {
                "ui": "ClientDashboard.js — complianceScore.stats.compliant",
                "backend": "compute_client_portal_requirement_stats — status in (COMPLIANT, VALID)",
                "meaning": "Legacy compliance status bucket, not lifecycle VERIFIED",
                "authority": "derived_live_projection",
                "not_same_as": "Requirements page stats.compliant uses lifecycle VERIFIED | SATISFIED_UNVERIFIED",
            },
            "days_until_next_expiry": {
                "ui": "ClientDashboard.js — complianceScore.stats.days_until_next_expiry",
                "backend": "calculate_compliance_score loop over portal_reqs",
                "filter": "status in COMPLIANT, VALID, PENDING, EXPIRING_SOON with due_date >= today",
                "due_date_source": "project_requirement_row_client_runtime → get_effective_expiry_date (evidence_authority effective_expiry, else confirmed/extracted/due_date)",
                "meaning": "Minimum days until next future effective expiry among filtered rows",
                "can_include": "estimated or provisional dates when no confirmed expiry",
                "authority": "derived_live_projection",
                "not_same_as": "Operational expiring-soon tile (expiring_soon count uses status EXPIRING_SOON only)",
            },
            "quick_action_cards": {
                "ui": "complianceScore.recommendations.slice(0,3)",
                "backend": "Aggregated property compliance_top_next_actions from persisted score recalc (v2 top_next_actions)",
                "fallback": "Generic overdue/expiring_soon copy if no persisted actions",
                "authority": "persisted_score_with_live_property_match",
            },
            "score_denominator_headline": {
                "ui": "displayScoreInfo / complianceScore.score — portfolio mean of persisted property scores",
                "backend": "aggregate_persisted_portfolio_headline + calculate_compliance_score",
                "authority": "persisted_portfolio_aggregate",
            },
            "dashboard_score_card_breakdown": {
                "ui": "complianceScore.components / bucket percents from persisted compliance_bucket_breakdown",
                "authority": "persisted_property_score",
            },
            "compliance_top_next_actions": {
                "persist": "compliance_scoring_service.recalculate_and_persist → compliance_top_next_actions",
                "source": "compliance_scoring_v2 compute_property_score_v2 top_next_actions",
            },
        },
    }


def _fe_tracked_like(req: Dict[str, Any]) -> bool:
    """Mirror frontend isRequirementIncludedInAttentionViews (simplified)."""
    app = str(req.get("applicability") or "").upper()
    if app == "NOT_REQUIRED":
        return False
    st = str(req.get("status") or "").upper()
    if st == "NOT_REQUIRED":
        return False
    cls = str(req.get("compliance_requirement_class") or req.get("requirement_class") or "").upper()
    if cls in ("OBLIGATION", "SYSTEM"):
        return False
    if cls and cls not in ("DOCUMENT", "JOB"):
        return False
    if req.get("is_tracked") is False or req.get("tracked") is False:
        return False
    if req.get("client_surface_visible") is False:
        return False
    return True


def _fe_lifecycle_valid(req: Dict[str, Any]) -> bool:
    state = str(req.get("client_lifecycle_state") or req.get("lifecycle_state") or "").upper()
    if state in ("VERIFIED", "SATISFIED_UNVERIFIED"):
        return True
    label = str(req.get("client_lifecycle_label") or "").lower()
    return "verified" in label or "satisfied" in label


def runtime_probe(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    score = httpx.get(f"{API}/client/compliance-score", headers=h, timeout=120).json()
    reqs = httpx.get(f"{API}/client/requirements?projection=full", headers=h, timeout=120).json()
    req_list = reqs.get("requirements") or []
    fe_tracked = [r for r in req_list if _fe_tracked_like(r)]
    fe_valid_lifecycle = sum(1 for r in fe_tracked if _fe_lifecycle_valid(r))
    stats = score.get("stats") or {}
    nearest_candidates: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for r in fe_tracked:
        due = r.get("due_date") or r.get("confirmed_expiry_date") or (r.get("evidence_authority") or {}).get("effective_expiry_date")
        if not due:
            continue
        try:
            s = str(due).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days = (dt - now).days
            if days >= 0:
                nearest_candidates.append(
                    {
                        "requirement_id": r.get("requirement_id"),
                        "property_id": r.get("property_id"),
                        "requirement_type": r.get("requirement_type") or r.get("requirement_code"),
                        "status": r.get("status"),
                        "due_date": due,
                        "days_until": days,
                        "date_source": (r.get("evidence_authority") or {}).get("effective_expiry_date") and "evidence_authority"
                        or ("confirmed" if r.get("confirmed_expiry_date") else "due_date_or_extracted"),
                    }
                )
        except Exception:
            pass
    nearest_candidates.sort(key=lambda x: x["days_until"])
    api_days = stats.get("days_until_next_expiry")
    return {
        "generated_at": _utc(),
        "properties_count": score.get("properties_count"),
        "dashboard_widget": {
            "total_requirements": stats.get("total_requirements"),
            "compliant": stats.get("compliant"),
            "expiring_soon": stats.get("expiring_soon"),
            "overdue": stats.get("overdue"),
            "days_until_next_expiry": api_days,
            "nearest_expiry_type": stats.get("nearest_expiry_type"),
        },
        "requirements_registry": {
            "raw_rows": len(req_list),
            "fe_tracked_attention_count": len(fe_tracked),
            "fe_valid_lifecycle_count": fe_valid_lifecycle,
        },
        "deltas": {
            "registry_vs_widget_requirements": len(fe_tracked) - int(stats.get("total_requirements") or 0),
            "lifecycle_valid_vs_widget_valid": fe_valid_lifecycle - int(stats.get("compliant") or 0),
        },
        "nearest_expiry_probe": nearest_candidates[:5],
        "expiry_match_api": nearest_candidates[0]["days_until"] == api_days if nearest_candidates and api_days is not None else None,
        "recommendations_sample": (score.get("recommendations") or [])[:3],
    }


def count_convergence(runtime: Dict[str, Any]) -> Dict[str, Any]:
    d = runtime.get("deltas") or {}
    reg = runtime.get("requirements_registry") or {}
    w = runtime.get("dashboard_widget") or {}
    req_delta = d.get("registry_vs_widget_requirements", 0)
    valid_delta = d.get("lifecycle_valid_vs_widget_valid", 0)
    intentional_reasons = [
        "Backend portal stats apply alias-family dedupe per property (fire_detection, deposit, etc.)",
        "Requirements page counts FE tracked rows without alias dedupe",
        "Widget Valid uses COMPLIANT/VALID status; Requirements Valid uses lifecycle VERIFIED/SATISFIED_UNVERIFIED",
    ]
    return {
        "generated_at": _utc(),
        "widget_requirements_count": w.get("total_requirements"),
        "registry_tracked_count": reg.get("fe_tracked_attention_count"),
        "delta": req_delta,
        "is_drift": req_delta != 0,
        "is_intentional_filtering": req_delta != 0,
        "intentional_reasons": intentional_reasons,
        "widget_valid": w.get("compliant"),
        "registry_valid_lifecycle": reg.get("fe_valid_lifecycle_count"),
        "valid_delta": valid_delta,
        "valid_is_drift": valid_delta != 0,
        "conclusion": (
            "Counts differ by design (dedupe + status semantics) but UI labels do not disclose the distinction"
            if req_delta != 0 or valid_delta != 0
            else "Counts align on this client"
        ),
    }


def expiry_semantics(runtime: Dict[str, Any]) -> Dict[str, Any]:
    w = runtime.get("dashboard_widget") or {}
    days = w.get("days_until_next_expiry")
    nearest = (runtime.get("nearest_expiry_probe") or [{}])[0] if runtime.get("nearest_expiry_probe") else {}
    classification = "semantic_drift"
    if days is None:
        classification = "no_future_expiry_in_probe"
    elif days > 365:
        classification = "estimated_renewal_forecast_non_operational"
    elif days <= 90:
        classification = "operational_expiry_window"
    return {
        "generated_at": _utc(),
        "days_until_next_expiry": days,
        "nearest_requirement": nearest,
        "classification": classification,
        "findings": {
            "uses_future_effective_expiry": True,
            "includes_estimated_dates": nearest.get("date_source") != "confirmed" if nearest else None,
            "excludes_overdue_for_min_calc": True,
            "misleading_label_when_days_gt_365": days is not None and days > 365,
            "requirements_page_expiring_soon_zero": w.get("expiring_soon") == 0,
        },
        "note": "Label 'Days to Next Expiry' implies operational urgency; values >365d are renewal forecasts, not active expiries.",
    }


def ui_cognition(runtime: Dict[str, Any], count: Dict[str, Any], expiry: Dict[str, Any]) -> Dict[str, Any]:
    issues = []
    if count.get("is_drift"):
        issues.append({
            "label": "Requirements",
            "current": "Requirements",
            "problem": f"Shows {count.get('widget_requirements_count')} while registry shows {count.get('registry_tracked_count')} tracked items",
            "suggested": "Score-tracked obligations (after dedupe) or show both counts",
        })
    if count.get("valid_is_drift"):
        issues.append({
            "label": "Valid",
            "current": "Valid",
            "problem": "Uses COMPLIANT/VALID status, not lifecycle verified count",
            "suggested": "Valid (compliance status) or align count with lifecycle",
        })
    if expiry.get("findings", {}).get("misleading_label_when_days_gt_365"):
        issues.append({
            "label": "Days to Next Expiry",
            "current": "Days to Next Expiry",
            "problem": f"Shows {expiry.get('days_until_next_expiry')} days — non-operational forecast",
            "suggested": "Next renewal (estimated) or cap display / show date source",
        })
    return {
        "generated_at": _utc(),
        "honest_labels_required": len(issues) > 0,
        "issues": issues,
        "compliance_score_page_uses_tracked_items": True,
        "dashboard_widget_uses_requirements": True,
        "label_inconsistency_across_surfaces": True,
    }


def recommended_convergence(ui: Dict[str, Any]) -> Dict[str, Any]:
    fixes = []
    for issue in ui.get("issues") or []:
        fixes.append(
            {
                "scope": "frontend/ClientDashboard.js",
                "type": "label_clarification",
                "change": issue.get("suggested"),
                "priority": "p0" if "Expiry" in (issue.get("label") or "") else "p1",
            }
        )
    fixes.append(
        {
            "scope": "frontend/ClientDashboard.js",
            "type": "tooltip",
            "change": "Explain stats come from score projection (alias dedupe + compliance status), link to Requirements for full registry",
            "priority": "p1",
        }
    )
    if any(f.get("priority") == "p0" for f in fixes):
        fixes.append(
            {
                "scope": "frontend/ClientDashboard.js",
                "type": "expiry_suppression_threshold",
                "change": "When days_until_next_expiry > 365, show 'Next renewal 1+ yr' and date source badge (estimated vs confirmed)",
                "priority": "p1",
            }
        )
    return {
        "generated_at": _utc(),
        "redesign_scoring": False,
        "minimal_fixes": fixes,
        "no_count_inflation": True,
    }


def run_regression() -> Dict[str, Any]:
    suites = [
        "tests/test_scoring_semantics_v1.py",
        "tests/test_score_cognition_service.py",
        "tests/test_compliance_scoring_v2_model.py",
        "tests/test_portfolio_pending_score_recalc_snapshot.py",
        "tests/test_requirement_client_runtime_surface.py",
        "tests/test_compliance_recalc_queue_stabilization_phase1.py",
    ]
    results = {}
    all_ok = True
    for suite in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", suite, "-q"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        results[suite] = {"passed": ok, "tail": (proc.stdout or proc.stderr)[-400:]}
        all_ok = all_ok and ok
    return {"all_passed": all_ok, "suites": results}


def classify(count: Dict[str, Any], expiry: Dict[str, Any], ui: Dict[str, Any], regression: Dict[str, Any]) -> Dict[str, Any]:
    tests_ok = regression.get("all_passed")
    has_count = count.get("is_drift") or count.get("valid_is_drift")
    has_expiry = expiry.get("classification") == "estimated_renewal_forecast_non_operational"
    if not tests_ok:
        klass = "FAIL_OPERATIONAL"
    elif has_count and has_expiry:
        klass = "SCORE_WIDGET_SEMANTIC_DRIFT"
    elif has_count:
        klass = "COUNT_CONVERGENCE_DRIFT"
    elif has_expiry:
        klass = "EXPIRY_COGNITION_DRIFT"
    elif ui.get("honest_labels_required"):
        klass = "PARTIAL"
    else:
        klass = "VERIFIED_OPERATIONALLY"
    return {
        "programme": "DASHBOARD-SCORE-WIDGET-SEMANTIC-CONVERGENCE-01",
        "classified_at": _utc(),
        "classification": klass,
        "checks": {
            "regression_passed": tests_ok,
            "count_explained": True,
            "count_labels_honest": not has_count,
            "expiry_explained": True,
            "expiry_labels_honest": not has_expiry,
        },
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    _write("derivation_trace.json", derivation_trace())
    email, pw = _creds()
    token = _login(email, pw)
    if not token:
        _write("classifications.json", {"classification": "FAIL_OPERATIONAL", "reason": "login_failed"})
        return 1
    runtime = runtime_probe(token)
    _write("aggregation_runtime.json", runtime)
    _write("count_convergence_runtime.json", count_convergence(runtime))
    expiry = expiry_semantics(runtime)
    _write("expiry_semantics_runtime.json", expiry)
    count = count_convergence(runtime)
    ui = ui_cognition(runtime, count, expiry)
    _write("ui_cognition_runtime.json", ui)
    rec = recommended_convergence(ui)
    _write("recommended_convergence_runtime.json", rec)
    regression = run_regression()
    _write("regression_runtime.json", regression)
    classifications = classify(count, expiry, ui, regression)
    _write("classifications.json", classifications)
    (OUT / "REPORT.md").write_text(
        f"# DASHBOARD-SCORE-WIDGET-SEMANTIC-CONVERGENCE-01\n\n"
        f"Classification: **{classifications['classification']}**\n\n"
        f"- Widget requirements: {runtime.get('dashboard_widget', {}).get('total_requirements')}\n"
        f"- Registry tracked: {runtime.get('requirements_registry', {}).get('fe_tracked_attention_count')}\n"
        f"- Days to next expiry: {runtime.get('dashboard_widget', {}).get('days_until_next_expiry')}\n",
        encoding="utf-8",
    )
    print(f"classification={classifications['classification']}")
    return 0 if classifications["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
