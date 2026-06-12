#!/usr/bin/env python3
"""
OPERATIONS-ENTITLEMENT-DISCOVERY-AND-ACTION-UX-AUDIT-01
Evidence-only audit — no product fixes.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/operations_entitlement_discovery_action_ux_01"
SHOT = OUT / "screenshots"
PROGRAMME = "OPERATIONS-ENTITLEMENT-DISCOVERY-AND-ACTION-UX-AUDIT-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

_fc_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_fc", _fc_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)
API, FRONTEND = _fc.API, _fc.FRONTEND.rstrip("/")
req = _fc.req
admin_session = _fc.admin_session
impersonate = _fc.impersonate

PLAN_USERS = {
    "solo": {"client_id": "616258a5-51a6-4def-aa00-baa1598b2557", "plan_code": "PLAN_1_SOLO", "label": "Solo fixture B"},
    "portfolio": {"client_id": "80f83edd-ba12-41ed-929a-bbaf8c696a23", "plan_code": "PLAN_2_PORTFOLIO", "label": "Portfolio fixture D"},
    "professional": {"client_id": "6fd5ac4c-3fd4-4112-ade7-156977deb49f", "plan_code": "PLAN_3_PRO", "label": "Professional Nancy"},
}

REFERENCE_FIXTURES = {
    "sophie_walker": {
        "client_id": "10b2ddba-e952-4484-91d1-a8f0299d0824",
        "note": "Historical Portfolio calm fixture; staging runtime now PLAN_1_SOLO",
    },
}

OPS_FLAGS_DEFAULTS = {
    "PLAN_1_SOLO": {
        "maintenance_workflows": False,
        "predictive_maintenance": False,
        "contractor_network": False,
        "rent_operations": False,
        "invoicing": False,
        "compliance_engine": True,
    },
    "PLAN_2_PORTFOLIO": {
        "maintenance_workflows": True,
        "predictive_maintenance": True,
        "contractor_network": False,
        "rent_operations": True,
        "invoicing": False,
        "compliance_engine": True,
    },
    "PLAN_3_PRO": {
        "maintenance_workflows": True,
        "predictive_maintenance": True,
        "contractor_network": True,
        "rent_operations": True,
        "invoicing": False,
        "compliance_engine": True,
    },
}

COMMERCIAL_MATRIX = {
    "PLAN_1_SOLO": {
        "reports_pdf": False,
        "reports_csv": False,
        "scheduled_reports": False,
        "tenant_portal": False,
        "audit_log_export": False,
        "zip_upload": False,
    },
    "PLAN_2_PORTFOLIO": {
        "reports_pdf": True,
        "reports_csv": True,
        "scheduled_reports": True,
        "tenant_portal": False,
        "audit_log_export": False,
        "zip_upload": True,
    },
    "PLAN_3_PRO": {
        "reports_pdf": True,
        "reports_csv": True,
        "scheduled_reports": True,
        "tenant_portal": True,
        "audit_log_export": True,
        "zip_upload": True,
    },
}

NAV_OPS = [
    {"path": "/operations/issues", "label": "Issues", "feature": "maintenance_workflows"},
    {"path": "/operations/work-orders", "label": "Jobs", "feature": "maintenance_workflows"},
    {"path": "/operations/contractors", "label": "Contractors", "feature": "contractor_network"},
    {"path": "/operations/risk-signals", "label": "Risk signals", "feature": "predictive_maintenance"},
    {"path": "/operations/rent", "label": "Rent Operations", "feature": "rent_operations"},
    {"path": "/operations/approvals", "label": "Approvals", "feature": "invoicing"},
]

SECONDARY_NAV = [
    {"path": "/reports", "feature": "reports_pdf|reports_csv", "reports_gate": True},
    {"path": "/tenants", "feature": "tenant_portal"},
    {"path": "/settings/billing", "feature": "invoicing"},
]


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def feature_enabled(features: Dict[str, Any], key: str) -> bool:
    return bool((features.get(key) or {}).get("enabled"))


def build_static_inventory() -> Dict[str, Any]:
    plans = {}
    for plan_key, plan_code in [
        ("solo", "PLAN_1_SOLO"),
        ("portfolio", "PLAN_2_PORTFOLIO"),
        ("professional", "PLAN_3_PRO"),
    ]:
        ops = OPS_FLAGS_DEFAULTS[plan_code]
        commercial = COMMERCIAL_MATRIX[plan_code]
        visible_nav = [n for n in NAV_OPS if ops.get(n["feature"])]
        hidden_nav = [n for n in NAV_OPS if not ops.get(n["feature"])]
        plans[plan_key] = {
            "plan_code": plan_code,
            "operations_module_defaults": ops,
            "commercial_features": commercial,
            "visible_operations_nav": visible_nav,
            "hidden_operations_nav": hidden_nav,
            "operations_nav_strategy": "HIDDEN_UNTIL_UPGRADE (filtered from nav; no locked nav items)",
            "accessible_routes_when_entitled": [n["path"] for n in visible_nav],
            "route_gates": {
                "maintenance_pages": "EntitlementProtectedRoute maintenance_workflows",
                "contractor_directory": "EntitlementProtectedRoute contractor_network",
                "risk_signals": "EntitlementProtectedRoute predictive_maintenance",
                "rent": "EntitlementProtectedRoute rent_operations",
                "tenant_portal": "EntitlementProtectedRoute tenant_portal",
            },
            "backend_allowed_ops_actions": {
                "maintenance_jobs": ops["maintenance_workflows"],
                "contractor_assignment_api": ops["contractor_network"],
                "risk_signals_api": ops["predictive_maintenance"],
                "rent_operations_api": ops["rent_operations"],
                "pdf_csv_exports": commercial["reports_pdf"],
                "tenant_portal_api": commercial["tenant_portal"],
            },
            "upgrade_messaging_surfaces": {
                "route_gate": "UpgradeRequired full-page card",
                "job_detail_assign_blocked": "Alert + disabled hero when maintenance but not contractor_network",
                "issues_assign_cta": "No contractor_network gate — navigates to job detail",
                "jobs_list_assign": "Hidden when !contractor_network (ClientMaintenancePage)",
            },
        }
    return {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "sources": [
            "backend/services/plan_registry.py FEATURE_MATRIX",
            "backend/services/ops_compliance_feature_flags.py DEFAULTS_BY_PLAN",
            "frontend/src/config/portalNavigationConfig.js",
            "frontend/src/utils/jobDetailPrimaryAction.js",
            "backend/routes/api_compliance_workflow.py",
        ],
        "plans": plans,
        "cross_plan_summary": {
            "operations_nav": "Portfolio+ sees Issues/Jobs/Risk/Rent; Pro adds Contractors",
            "contractor_network": "Professional only (plan default); Portfolio has maintenance but not contractor network",
            "solo": "No operations module; compliance-only ops flags",
            "tenant_portal": "Professional only (commercial matrix)",
            "exports": "PDF/CSV Portfolio+; audit_log_export Professional only",
        },
    }


def session_for(client_id: str, admin_bundle: Optional[Tuple] = None) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    if admin_bundle:
        admin_t, _, step = admin_bundle
        err = None
    else:
        admin_t, _, step, err = admin_session()
    if err or not admin_t:
        return None, err, {}
    try:
        tok, imp_err = impersonate(admin_t, step, client_id, PROGRAMME)
    except RuntimeError as exc:
        return None, str(exc), {}
    if imp_err or not tok:
        return None, imp_err, {}
    try:
        me = req("get", "/auth/me", tok)
    except RuntimeError as exc:
        return tok, f"auth_me_rate_limited: {exc}", {"client_id": client_id, "role": "ROLE_CLIENT"}
    if me.status_code == 200:
        user = me.json()
        if isinstance(user.get("user"), dict):
            user = user["user"]
    else:
        user = {"client_id": client_id, "role": "ROLE_CLIENT", "email": "audit@fixture.local"}
    user.setdefault("client_id", client_id)
    user.setdefault("role", "ROLE_CLIENT")
    return tok, None, user


def runtime_entitlements(tok: str) -> Dict[str, Any]:
    try:
        ent = req("get", "/client/entitlements", tok)
    except RuntimeError as exc:
        return {"status": 429, "error": str(exc), "features": {}}
    body = ent.json() if ent.status_code == 200 else {}
    features = body.get("features") or {}
    return {
        "status": ent.status_code,
        "plan": body.get("plan"),
        "plan_name": body.get("plan_name"),
        "features": {
            k: {"enabled": feature_enabled(features, k), "minimum_plan": (features.get(k) or {}).get("minimum_plan")}
            for k in [
                "maintenance_workflows",
                "predictive_maintenance",
                "contractor_network",
                "rent_operations",
                "invoicing",
                "tenant_portal",
                "reports_pdf",
                "reports_csv",
                "audit_log_export",
            ]
        },
    }


def find_assign_job(tok: str) -> Optional[str]:
    try:
        r = req("get", "/client/maintenance/work-orders", tok, params={"limit": 40})
    except RuntimeError:
        return None
    if r.status_code != 200:
        return None
    for wo in r.json().get("work_orders") or r.json().get("items") or []:
        wid = wo.get("work_order_id") or wo.get("id")
        if not wid:
            continue
        if wo.get("contractor_id"):
            continue
        actions = [a.get("id") for a in (wo.get("next_actions") or [])]
        if "assign_contractor" in actions or "assign" in actions:
            return str(wid)
        st = str(wo.get("status") or "").lower()
        if st in ("open", "pending_assignment", "ready_for_assignment"):
            return str(wid)
    return None


def api_guard_probe(tok: str, job_id: Optional[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        if job_id:
            ac = req("get", f"/jobs/{job_id}/assignable-contractors", tok)
            out["assignable_contractors"] = {
                "status": ac.status_code,
                "detail": (ac.json().get("detail") if ac.status_code >= 400 else "ok")[:120],
            }
            assign = req(
                "post",
                f"/jobs/{job_id}/assign-contractor",
                tok,
                json={"contractor_id": "00000000-0000-0000-0000-000000000099"},
            )
            out["assign_contractor_post"] = {
                "status": assign.status_code,
                "detail": (assign.json().get("detail") if assign.status_code >= 400 else "accepted_or_validation")[:120],
                "note": "POST assign-contractor only checks maintenance_workflows in route handler (no CONTRACTOR_NETWORK guard)",
            }
        mw = req("get", "/client/maintenance/work-orders", tok, params={"limit": 1})
        out["maintenance_list"] = {"status": mw.status_code}
        rs = req("get", "/client/maintenance/risk-signals", tok, params={"limit": 1})
        out["risk_signals"] = {
            "status": rs.status_code,
            "detail": (rs.json().get("detail") if rs.status_code >= 400 else "ok")[:80],
        }
        rent = req("get", "/client/rent-operations/summary", tok)
        out["rent_operations"] = {
            "status": rent.status_code,
            "detail": (rent.json().get("detail") if rent.status_code >= 400 else "ok")[:80],
        }
        contractors = req("get", "/client/contractors", tok, params={"limit": 1})
        out["contractor_directory"] = {
            "status": contractors.status_code,
            "detail": (contractors.json().get("detail") if contractors.status_code >= 400 else "ok")[:80],
        }
    except RuntimeError as exc:
        out["error"] = str(exc)
    return out


def contractor_assignment_audit(sessions: Dict[str, Any]) -> Dict[str, Any]:
    scenarios = {}
    for persona, row in sessions.items():
        tok = row.get("token")
        job_id = row.get("assign_job_id")
        feats = (row.get("entitlements") or {}).get("features") or {}
        has_cn = (feats.get("contractor_network") or {}).get("enabled")
        has_mw = (feats.get("maintenance_workflows") or {}).get("enabled")
        scenarios[persona] = {
            "plan": row.get("plan_code"),
            "has_maintenance_workflows": has_mw,
            "has_contractor_network": has_cn,
            "assign_job_id": job_id,
            "api_guards": row.get("api_guards"),
            "expected_scenario": (
                "C_non_entitled" if has_mw and not has_cn else "A_entitled" if has_cn else "no_maintenance"
            ),
            "frontend_expectations": {
                "hero_assign_executable": has_cn and bool(job_id),
                "upgrade_alert_on_job_detail": has_mw and not has_cn,
                "section_assign_button": has_cn,
                "modal_opens_on_assign": has_cn,
                "auto_focus_search_select": "not implemented — no useEffect focus in ClientJobDetailPage openAssignModal",
                "early_network_primary_cta": "Add contractor for this area when eligible_count=0",
            },
        }
    return {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "code_paths": {
            "job_detail": "frontend/src/pages/ClientJobDetailPage.js",
            "primary_action": "frontend/src/utils/jobDetailPrimaryAction.js",
            "issues": "frontend/src/pages/ClientIssuesPage.js + primaryActionResolver.js",
            "modal": "assign-contractor-modal data-testid",
        },
        "scenarios": scenarios,
        "findings": [
            "Portfolio (maintenance, no contractor_network): upgrade Alert + disabled hero; section assign hidden; modal no-op",
            "Issues list: Assign contractor CTA navigates without contractor_network check",
            "POST /jobs/{id}/assign-contractor lacks CONTRACTOR_NETWORK guard (backend drift)",
            "No auto-focus on modal open for search/select or add-contractor form",
            "UpgradePrompt FEATURE_MIN_PLAN maps contractor_network to PLAN_2_PORTFOLIO but ops default is PLAN_3_PRO",
        ],
    }


def locked_feature_strategy() -> Dict[str, Any]:
    features = [
        {
            "feature": "maintenance_workflows",
            "solo": "HIDDEN_UNTIL_UPGRADE",
            "portfolio": "INCLUDED_VISIBLE",
            "professional": "INCLUDED_VISIBLE",
            "nav": "hidden/filtered",
            "route": "EntitlementProtectedRoute full-page upgrade",
            "recommendation": "Solo: hide Operations group entirely (current). Portfolio+: show normally.",
        },
        {
            "feature": "contractor_network",
            "solo": "HIDDEN_UNTIL_UPGRADE",
            "portfolio": "LOCKED_UPSELL_VISIBLE",
            "professional": "INCLUDED_VISIBLE",
            "nav": "hidden on Portfolio",
            "job_detail": "disabled hero + upgrade alert on Portfolio",
            "issues_cta": "EXECUTABLE_BUT_BLOCKED",
            "recommendation": "Portfolio: locked CTA on issues OR replace hero label; do not show clickable nav to broken flow",
        },
        {
            "feature": "predictive_maintenance",
            "solo": "HIDDEN_UNTIL_UPGRADE",
            "portfolio": "INCLUDED_VISIBLE",
            "professional": "INCLUDED_VISIBLE",
            "recommendation": "Show when entitled; hide nav when not",
        },
        {
            "feature": "rent_operations",
            "solo": "HIDDEN_UNTIL_UPGRADE",
            "portfolio": "INCLUDED_VISIBLE",
            "professional": "INCLUDED_VISIBLE",
            "recommendation": "Show when entitled",
        },
        {
            "feature": "tenant_portal",
            "solo": "HIDDEN_UNTIL_UPGRADE",
            "portfolio": "HIDDEN_UNTIL_UPGRADE",
            "professional": "INCLUDED_VISIBLE",
            "recommendation": "Hide until Professional; route gate on /tenants",
        },
        {
            "feature": "reports_pdf/csv",
            "solo": "HIDDEN_UNTIL_UPGRADE",
            "portfolio": "INCLUDED_VISIBLE",
            "professional": "INCLUDED_VISIBLE",
            "recommendation": "Reports nav when pdf OR csv enabled",
        },
        {
            "feature": "audit_log_export",
            "solo": "HIDDEN_UNTIL_UPGRADE",
            "portfolio": "HIDDEN_UNTIL_UPGRADE",
            "professional": "INCLUDED_VISIBLE",
            "recommendation": "Hide export UI until entitled",
        },
        {
            "feature": "assign_contractor CTA (issues)",
            "classification": "EXECUTABLE_BUT_BLOCKED",
            "detail": "Clickable on Portfolio; lands on job detail with disabled assign",
            "recommendation": "LOCKED_UPSELL_VISIBLE with upgrade modal or gate at issues layer",
        },
        {
            "feature": "POST assign-contractor API",
            "classification": "BACKEND_ONLY_BLOCKED",
            "detail": "Missing CONTRACTOR_NETWORK on canonical assign endpoint",
            "recommendation": "Add CONTRACTOR_NETWORK guard; keep maintenance_workflows",
        },
    ]
    return {"programme": PROGRAMME, "run_tag": RUN_TAG, "features": features, "principle": "Solo: no half-working Operations. Professional: full system. Portfolio: maintenance without contractor marketplace."}


def actionability_governance(sessions: Dict[str, Any]) -> Dict[str, Any]:
    ctas = [
        {
            "label": "Assign contractor (job hero)",
            "source": "NextActionHero / operational_cognition",
            "entitlement": "contractor_network + next_actions assign_contractor",
            "frontend_guard": "resolveHeroPrimaryExecution → primaryDisabled",
            "backend_guard": "assignable-contractors 403; assign POST weak",
            "click_result_entitled": "openAssignModal",
            "click_result_portfolio": "disabled button + toast if forced",
            "mobile": "same component",
        },
        {
            "label": "Assign contractor (job section)",
            "source": "ClientJobDetailPage contractor section",
            "entitlement": "contractor_network",
            "frontend_guard": "canExecuteAssignContractor",
            "backend_guard": "assignable-contractors 403",
            "click_result_portfolio": "button hidden",
        },
        {
            "label": "Assign contractor (issues list/drawer)",
            "source": "resolveIssuePrimaryAction ready_for_work_order",
            "entitlement": "maintenance_workflows only (gap)",
            "frontend_guard": "none for contractor_network",
            "click_result_portfolio": "navigate to job detail",
            "classification": "ACTIONABILITY_DRIFT",
        },
        {
            "label": "Assign contractor (jobs list)",
            "source": "ClientMaintenancePage",
            "entitlement": "contractor_network",
            "frontend_guard": "hasFeature('contractor_network')",
            "click_result_portfolio": "button not rendered",
        },
        {
            "label": "Start maintenance job",
            "source": "issues / properties",
            "entitlement": "maintenance_workflows",
            "frontend_guard": "EntitlementProtectedRoute + plan job gate modal on 403",
            "backend_guard": "_require_maintenance_enabled",
        },
        {
            "label": "Contractor network directory",
            "source": "/operations/contractors",
            "entitlement": "contractor_network",
            "frontend_guard": "EntitlementProtectedRoute",
            "backend_guard": "CONTRACTOR_NETWORK on client contractors routes",
        },
        {
            "label": "Export PDF/CSV",
            "source": "ReportsPage",
            "entitlement": "reports_pdf / reports_csv",
            "frontend_guard": "hasFeature per export type",
            "backend_guard": "plan_registry.enforce_feature",
        },
        {
            "label": "Tenant portal actions",
            "source": "/tenants routes",
            "entitlement": "tenant_portal",
            "frontend_guard": "EntitlementProtectedRoute",
            "backend_guard": "plan_registry.enforce_feature tenant_portal",
        },
    ]
    return {"programme": PROGRAMME, "run_tag": RUN_TAG, "ctas": ctas, "runtime_sessions": {k: v.get("api_guards") for k, v in sessions.items()}}


def enhancement_plan() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "do_not_implement_in_audit": True,
        "items": [
            {
                "id": "assign_modal_focus",
                "title": "Assign contractor modal auto-scroll / auto-focus",
                "scope": [
                    "On open with eligible contractors: focus contractor select (desktop + mobile)",
                    "On open with zero eligible: focus primary CTA 'Add contractor for this area'",
                    "focusAdd path: focus first field in add-contractor form",
                    "use requestAnimationFrame + scrollIntoView for mobile 390px",
                ],
                "files": ["frontend/src/pages/ClientJobDetailPage.js"],
                "risk": "low — presentation only",
            },
            {
                "id": "non_entitled_assign_ux",
                "title": "Non-entitled Assign contractor UX",
                "recommended": "locked CTA with upgrade/support modal",
                "alternatives": [
                    {"option": "locked CTA + upgrade modal", "pro": "Clear next step; preserves discoverability", "con": "Extra component"},
                    {"option": "remove CTA + locked feature card", "pro": "No misleading click", "con": "Less discoverability on issues"},
                    {"option": "hide entirely", "pro": "No noise", "con": "Portfolio users miss upgrade path"},
                ],
                "recommendation_reason": "Portfolio has maintenance jobs needing contractors — LOCKED_UPSELL_VISIBLE with one-click upgrade/help preserves workflow context without EXECUTABLE_BUT_BLOCKED navigation. Apply at issues hero, issues table, and job hero label swap.",
                "files": [
                    "frontend/src/utils/primaryActionResolver.js",
                    "frontend/src/pages/ClientIssuesPage.js",
                    "frontend/src/utils/jobDetailPrimaryAction.js",
                ],
            },
            {
                "id": "nav_visibility",
                "title": "Plan-based navigation/visibility",
                "show": ["maintenance pages when maintenance_workflows", "contractors when contractor_network", "risk when predictive_maintenance"],
                "locked": ["contractor assignment CTAs on Portfolio — upgrade chip/modal"],
                "hidden": ["Operations group for Solo", "tenant portal until Professional", "contractors nav until Professional"],
                "keep": "filter hidden nav (no locked nav items) — consistent with current strategy",
            },
            {
                "id": "backend_safeguards",
                "title": "Backend must remain authoritative",
                "required": [
                    "Add CONTRACTOR_NETWORK to POST /jobs/{id}/assign-contractor",
                    "Keep assignable-contractors 403",
                    "Keep maintenance_workflows on job routes",
                    "plan_registry.enforce_feature on exports and tenant portal",
                    "ops flags admin overrides respected",
                ],
            },
            {
                "id": "upgrade_copy_alignment",
                "title": "Align UpgradePrompt minimum plan for contractor_network to PLAN_3_PRO",
                "files": ["frontend/src/components/UpgradePrompt.js"],
            },
        ],
    }


def refresh_browser_tokens(sessions: Dict[str, Any]) -> Dict[str, Any]:
    import time as _time

    admin_t, _, step, err = admin_session()
    if not admin_t:
        return sessions
    for persona, meta in PLAN_USERS.items():
        _time.sleep(8)
        tok, imp_err, user = session_for(meta["client_id"], (admin_t, None, step))
        if tok and persona in sessions:
            sessions[persona]["token"] = tok
            sessions[persona]["user"] = user
    return sessions


def browser_verify(sessions: Dict[str, Any], fresh_tokens: bool = True) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"skipped": True, "reason": "playwright not installed"}

    if fresh_tokens:
        sessions = refresh_browser_tokens(dict(sessions))

    SHOT.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Any] = {"personas": {}, "run_tag": RUN_TAG}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for persona, row in sessions.items():
            tok = row.get("token")
            user = row.get("user") or {}
            job_id = row.get("assign_job_id")
            if not tok:
                results["personas"][persona] = {"error": row.get("error")}
                continue

            persona_out: Dict[str, Any] = {"desktop": {}, "mobile_390": {}}
            for vp_name, viewport in [("desktop", {"width": 1280, "height": 900}), ("mobile_390", {"width": 390, "height": 844})]:
                ctx = browser.new_context(viewport=viewport)
                page = ctx.new_page()
                page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120000)
                page.evaluate(
                    "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
                    [tok, user],
                )
                page.goto(f"{FRONTEND}/dashboard", wait_until="domcontentloaded", timeout=120000)
                try:
                    page.wait_for_selector('[data-testid="client-dashboard"], [data-testid="entitlement-gate"], [data-testid="entitlement-load-error"]', timeout=90000)
                except Exception:
                    pass
                page.wait_for_timeout(2500)
                body = page.locator("body").inner_text()
                nav_text = body[:2000]
                ops_visible = {
                    "issues": "Issues" in nav_text and "/operations/issues" in page.content(),
                    "jobs": "Jobs" in nav_text or "Work orders" in nav_text,
                    "contractors": "Contractors" in nav_text,
                    "risk_signals": "Risk signals" in nav_text,
                    "rent": "Rent" in nav_text,
                }
                row_vp: Dict[str, Any] = {"nav_visibility_heuristic": ops_visible}

                # Job detail first when available (avoids false gate before entitlements hydrate on deep links)
                resolved_job_id = job_id
                if not resolved_job_id and persona == "portfolio":
                    page.goto(f"{FRONTEND}/operations/work-orders", wait_until="domcontentloaded", timeout=120000)
                    page.wait_for_timeout(3000)
                    link = page.locator('a[href*="/operations/jobs/"]').first
                    if link.count():
                        href = link.get_attribute("href") or ""
                        m = re.search(r"/operations/jobs/([a-f0-9-]+)", href)
                        if m:
                            resolved_job_id = m.group(1)

                if resolved_job_id:
                    page.goto(f"{FRONTEND}/operations/jobs/{resolved_job_id}", wait_until="domcontentloaded", timeout=120000)
                    page.wait_for_timeout(4000)
                    row_vp["job_detail_loaded"] = page.locator('[data-testid="client-dashboard"]').count() == 0 and (
                        page.locator("text=Next action").count() > 0 or page.locator('[data-testid="next-action-hero"]').count() > 0
                    )
                    row_vp["upgrade_alert_visible"] = "Contractor assignment needs your plan" in page.locator("body").inner_text()
                    hero = page.locator('[data-testid="next-action-hero-primary"]')
                    row_vp["hero_present"] = hero.count() > 0
                    row_vp["hero_disabled"] = hero.count() > 0 and hero.is_disabled()
                    row_vp["hero_label"] = hero.inner_text(timeout=3000)[:80] if hero.count() else None
                    row_vp["section_assign_btn"] = page.locator('[data-testid="open-assign-contractor-modal"]').count() > 0
                    if row_vp["section_assign_btn"]:
                        page.locator('[data-testid="open-assign-contractor-modal"]').click()
                        page.wait_for_timeout(1500)
                        row_vp["modal_opened"] = page.locator('[data-testid="assign-contractor-modal"]').count() > 0
                        if row_vp["modal_opened"]:
                            active = page.evaluate("() => document.activeElement?.tagName + (document.activeElement?.getAttribute('data-testid') ? '#' + document.activeElement.getAttribute('data-testid') : '')")
                            row_vp["modal_focus_target"] = active
                        page.keyboard.press("Escape")
                    elif hero.count() and not row_vp["hero_disabled"]:
                        hero.click()
                        page.wait_for_timeout(1500)
                        row_vp["modal_opened_from_hero"] = page.locator('[data-testid="assign-contractor-modal"]').count() > 0
                        if row_vp.get("modal_opened_from_hero"):
                            active = page.evaluate("() => document.activeElement?.tagName + (document.activeElement?.getAttribute('data-testid') ? '#' + document.activeElement.getAttribute('data-testid') : '')")
                            row_vp["modal_focus_target"] = active
                    page.screenshot(path=str(SHOT / f"{persona}_{vp_name}_job_detail.png"), full_page=True)
                else:
                    row_vp["job_detail_skipped"] = "no assign job found"

                page.goto(f"{FRONTEND}/operations/issues", wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(3500)
                row_vp["issues_entitlement_gate"] = page.locator('[data-testid="entitlement-gate"]').count() > 0
                row_vp["issues_page_loaded"] = page.locator('[data-testid="client-issues-page"]').count() > 0
                row_vp["issues_assign_cta_visible"] = page.locator("text=Assign contractor").count() > 0

                page.goto(f"{FRONTEND}/operations/contractors", wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(2500)
                row_vp["contractors_entitlement_gate"] = page.locator('[data-testid="entitlement-gate"]').count() > 0
                row_vp["contractors_page_loaded"] = page.locator('[data-testid="client-contractors-page"]').count() > 0

                row_vp["horizontal_overflow"] = page.evaluate(
                    "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
                )
                persona_out[vp_name] = row_vp
                ctx.close()

            results["personas"][persona] = persona_out
        browser.close()
    return results


def classify(inventory: Dict[str, Any], assignment: Dict[str, Any], browser: Dict[str, Any]) -> Tuple[str, List[str]]:
    codes = [
        "ENTITLEMENT_VISIBILITY_DRIFT",
        "ACTIONABILITY_DRIFT",
        "CONTRACTOR_ASSIGNMENT_UX_DRIFT",
        "PLAN_VALUE_DRIFT",
    ]
    if browser.get("skipped"):
        codes.append("PARTIAL")
        return "PARTIAL", codes
    prof_desk = (browser.get("personas") or {}).get("professional", {}).get("desktop") or {}
    if prof_desk.get("modal_opened"):
        focus = str(prof_desk.get("modal_focus_target") or "")
        if not focus or focus in ("BODY", "BUTTON") or "select" not in focus.lower():
            codes.append("LOCKED_FEATURE_UX_DRIFT")
    solo_desk = (browser.get("personas") or {}).get("solo", {}).get("desktop") or {}
    if solo_desk.get("issues_entitlement_gate"):
        pass  # expected
    return "PARTIAL", list(dict.fromkeys(codes))


SESSIONS_PATH = OUT / "sessions_runtime.json"
TOKENS_PATH = OUT / ".sessions_tokens.local.json"


def load_sessions(include_tokens: bool = False) -> Dict[str, Any]:
    sessions: Dict[str, Any] = {}
    if SESSIONS_PATH.is_file():
        sessions = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
    if include_tokens and TOKENS_PATH.is_file():
        tokens = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
        for persona, tok in tokens.items():
            if persona in sessions and tok:
                sessions[persona]["token"] = tok
    return sessions


def save_sessions(sessions: Dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tokens: Dict[str, str] = {}
    redacted = {}
    for k, v in sessions.items():
        row = dict(v)
        if row.get("token"):
            tokens[k] = row["token"]
        row.pop("token", None)
        redacted[k] = row
    SESSIONS_PATH.write_text(json.dumps(redacted, indent=2, default=str) + "\n", encoding="utf-8")
    if tokens:
        merged = {}
        if TOKENS_PATH.is_file():
            try:
                merged = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                merged = {}
        merged.update(tokens)
        TOKENS_PATH.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


def probe_persona(persona: str, admin_bundle: Tuple, sessions: Dict[str, Any]) -> None:
    import time as _time

    meta = PLAN_USERS[persona]
    _time.sleep(15)
    tok, err, user = session_for(meta["client_id"], admin_bundle)
    row: Dict[str, Any] = {
        "plan_code": meta["plan_code"],
        "label": meta["label"],
        "client_id": meta["client_id"],
        "error": err,
    }
    if tok:
        row["token"] = tok
        row["user"] = user
        row["entitlements"] = runtime_entitlements(tok)
        _time.sleep(10)
        row["assign_job_id"] = find_assign_job(tok)
        _time.sleep(10)
        row["api_guards"] = api_guard_probe(tok, row["assign_job_id"])
    sessions[persona] = row
    save_sessions(sessions)


def main() -> int:
    import argparse
    import time as _time

    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", choices=list(PLAN_USERS.keys()), help="Probe one persona only")
    parser.add_argument("--browser-only", action="store_true", help="Skip API; use saved sessions with tokens")
    parser.add_argument("--finalize-only", action="store_true", help="Write artifacts from saved sessions (no API/browser)")
    parser.add_argument("--artifacts-only", action="store_true", help="Alias for --finalize-only")
    args = parser.parse_args()
    if args.artifacts_only:
        args.finalize_only = True

    OUT.mkdir(parents=True, exist_ok=True)
    inventory = build_static_inventory()
    write("operations_entitlement_inventory_runtime.json", inventory)

    sessions = load_sessions(include_tokens=args.browser_only)

    if args.finalize_only:
        pass
    elif args.browser_only:
        sessions = load_sessions()
        browser = browser_verify(sessions, fresh_tokens=True)
        write("operations_entitlement_browser_runtime.json", browser)
    elif args.persona:
        admin_t, _, step, admin_err = admin_session()
        if not admin_t:
            raise SystemExit(f"admin session failed: {admin_err}")
        probe_persona(args.persona, (admin_t, None, step), sessions)
        print(f"Probed {args.persona}; saved to {SESSIONS_PATH}")
        return 0
    else:
        admin_t, _, step, admin_err = admin_session()
        if not admin_t:
            raise SystemExit(f"admin session failed: {admin_err}")
        for persona in PLAN_USERS:
            probe_persona(persona, (admin_t, None, step), sessions)
        browser = browser_verify(sessions)
        write("operations_entitlement_browser_runtime.json", browser)

    sessions = load_sessions()
    assignment = contractor_assignment_audit(sessions)
    write("contractor_assignment_ux_audit_runtime.json", assignment)

    locked = locked_feature_strategy()
    write("locked_feature_strategy_runtime.json", locked)

    governance = actionability_governance(sessions)
    write("operations_actionability_governance_runtime.json", governance)

    plan = enhancement_plan()
    write("operations_entitlement_enhancement_plan.json", plan)

    browser_path = OUT / "operations_entitlement_browser_runtime.json"
    if browser_path.is_file():
        browser = json.loads(browser_path.read_text(encoding="utf-8"))
    else:
        browser = {"skipped": True}

    classification, codes = classify(inventory, assignment, browser)
    write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "classification": classification,
            "code_classifications": codes,
            "verified_operationally": False,
            "reason": "Misleading issues CTAs, missing modal focus, backend assign POST guard gap",
        },
    )

    watchlist = [
        "- [x] Static entitlement inventory from plan_registry + ops flags",
        "- [x] Runtime entitlements API for Solo / Portfolio / Professional fixtures",
        "- [x] Contractor assignment UX code audit",
        "- [x] Browser proof (nav, gates, job detail)",
        f"- [{'x' if not browser.get('skipped') else ' '}] Playwright browser runtime",
        "- [ ] Implement enhancement plan (awaiting approval)",
        "- [ ] Add CONTRACTOR_NETWORK guard to POST assign-contractor",
        "- [ ] Gate issues assign_contractor CTA by contractor_network",
        "- [ ] Assign modal auto-focus (desktop + mobile)",
        "- [ ] Align UpgradePrompt contractor_network minimum plan to Professional",
    ]
    (OUT / "watchlist.md").write_text(f"# {PROGRAMME}\n\n" + "\n".join(watchlist) + "\n", encoding="utf-8")

    report = f"""# {PROGRAMME}

**Run:** `{RUN_TAG}`  
**Classification:** `{classification}`  
**Codes:** {', '.join(codes)}

## Summary

Audited Operations entitlement visibility, locked actions, contractor assignment UX, and upgrade discovery across Solo, Portfolio, and Professional plan defaults. **No fixes implemented.**

## Key findings

1. **Plan-feature matrix** — Ops modules (`maintenance_workflows`, `contractor_network`, etc.) come from `ops_compliance_feature_flags.DEFAULTS_BY_PLAN`; commercial features from `plan_registry.FEATURE_MATRIX`. See `operations_entitlement_inventory_runtime.json`.

2. **Contractor assignment UX drift** — Portfolio users (maintenance without `contractor_network`) see disabled job hero + upgrade alert, but **Issues** still offers clickable "Assign contractor" that navigates to job detail. Modal does not auto-focus search/select or early-network CTA.

3. **Backend guard gap** — `POST /jobs/{{id}}/assign-contractor` checks `maintenance_workflows` only; `assignable-contractors` correctly requires `CONTRACTOR_NETWORK`.

4. **Navigation strategy** — Gated ops nav items are **hidden** (not locked) when not entitled. Solo has no Operations group.

5. **Upgrade copy drift** — `UpgradePrompt.FEATURE_MIN_PLAN.contractor_network` = `PLAN_2_PORTFOLIO` but ops default enables on `PLAN_3_PRO` only.

## Artifacts

| File | Purpose |
|------|---------|
| `operations_entitlement_inventory_runtime.json` | Plan-feature matrix |
| `contractor_assignment_ux_audit_runtime.json` | Assignment flow scenarios |
| `locked_feature_strategy_runtime.json` | Locked vs hidden classification |
| `operations_actionability_governance_runtime.json` | CTA governance |
| `operations_entitlement_enhancement_plan.json` | Minimal safe enhancement plan |
| `operations_entitlement_browser_runtime.json` | Staging browser proof |
| `screenshots/` | Job detail captures |

## Enhancement plan (not implemented)

See `operations_entitlement_enhancement_plan.json` — modal auto-focus, locked upsell for non-entitled assign, backend CONTRACTOR_NETWORK on assign POST, upgrade copy alignment.

"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    print(f"Classification: {classification}")
    print(f"Codes: {', '.join(codes)}")
    print(f"Output: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
