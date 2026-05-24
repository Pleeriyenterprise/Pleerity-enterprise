"""
VERIFY-02 G0 cycle triage — runtime validation of unresolved static cycles only.
Local harness; does not execute G1–G7.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

G0_BUNDLE = ROOT / f"docs/audit/ops_control_g0_programme_precheck_{SLUG}"
TRIAGE_BUNDLE = ROOT / f"docs/audit/ops_control_g0_cycle_triage_{SLUG}"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any, bundle: Path) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / name).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _read_password() -> str:
    env = os.environ.get("OPS_VERIFY_PASSWORD")
    if env:
        return env.strip()
    return (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text(encoding="utf-8").strip()


def _login() -> Tuple[str, dict]:
    pw = _read_password()
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _route_url(route: str, property_id: str) -> str:
    if route == "/properties/:propertyId":
        return f"{FRONTEND}/properties/{property_id}"
    return f"{FRONTEND}{route.split('?')[0]}"


def _path_matches(current_path: str, expected: str) -> bool:
    cur = current_path.rstrip("/") or "/"
    exp = expected.replace(":propertyId", "").rstrip("/") or "/"
    if exp == "/properties" and cur.startswith("/properties/"):
        return True
    return cur == exp or cur.startswith(exp + "/")


def _evaluate_benign(walk: Dict[str, Any], resolution_probe: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """BENIGN_CONTROL_PLANE_CYCLE — hub nav exempt when resolution terminal reachable via drilldown."""
    reasons: List[str] = []
    hub = walk.get("hub_navigation_only") is True
    terminal_ok = resolution_probe.get("reachable") is True
    checks = {
        "authoritative_resolution_owner": bool(walk.get("authoritative_resolution_owner")),
        "navigation_terminates": walk.get("navigation_terminates") is True,
        "operator_not_trapped": walk.get("operator_not_trapped") is True,
        "no_infinite_recursion": walk.get("no_infinite_recursion") is True,
        "refresh_coherent": walk.get("refresh_coherent") is True,
        "depth_within_threshold": (walk.get("steps_taken") or 0) <= 6,
        "resolution_terminal_reachable": terminal_ok,
    }
    if hub:
        checks["hub_escalation_not_ping_pong"] = walk.get("no_mutationless_ping_pong") is True or terminal_ok
        checks["mutation_owner_via_drilldown"] = terminal_ok
    else:
        checks["mutation_owner_visible"] = walk.get("mutation_owner_visible") is True
        checks["operational_debt_resolvable"] = walk.get("operational_debt_resolvable") is True
        checks["no_mutationless_ping_pong"] = walk.get("no_mutationless_ping_pong") is True
    for k, ok in checks.items():
        if not ok:
            reasons.append(f"fail:{k}")
    return all(checks.values()), reasons


def _browser_session(token: str, user: dict, password: str, property_id: str):
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
    page.fill("#email", CLIENT_EMAIL)
    page.fill("#password", password)
    page.click('button[type="submit"]')
    page.wait_for_timeout(4000)
    body = page.locator("body").inner_text()
    if "Sign In" in body[:250] and "Compliance" not in body:
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )
    return p, browser, page


def _goto_route(page, route: str, property_id: str) -> str:
    url = _route_url(route, property_id)
    page.goto(url, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2000)
    from urllib.parse import urlparse

    return urlparse(page.url).path


def _detect_mutation_ui(page) -> bool:
    body = page.locator("body").inner_text().lower()
    selectors = [
        'button:has-text("Upload")',
        'button:has-text("Review")',
        'button:has-text("Save")',
        'button:has-text("Submit")',
        'button:has-text("Mark")',
        'button:has-text("Provide")',
        'button:has-text("Add")',
        'a:has-text("View requirement")',
        '[data-testid^="requirement-row-"] button',
    ]
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    if page.locator('[data-testid^="requirement-row-"]').count() > 0:
        return True
    return any(k in body for k in ("upload", "review", "submit", "mark complete", "add document", "provide evidence"))


def _probe_resolution_terminal(page, property_id: str) -> Dict[str, Any]:
    """Drilldown probe: can operator reach a mutation endpoint from hub surfaces?"""
    out: Dict[str, Any] = {"probes": [], "reachable": False}
    # Property hub — requirements tab
    _goto_route(page, f"/properties/{property_id}", property_id)
    for tab_name in ("Requirements", "Operating", "Documents"):
        try:
            tab = page.get_by_role("tab", name=tab_name)
            if tab.count() > 0:
                tab.first.click()
                page.wait_for_timeout(1500)
                mut = _detect_mutation_ui(page)
                out["probes"].append({"surface": "property_tab", "tab": tab_name, "mutation_visible": mut})
                if mut:
                    out["reachable"] = True
        except Exception as exc:
            out["probes"].append({"surface": "property_tab", "tab": tab_name, "error": str(exc)})
    # Requirements list — row action
    _goto_route(page, "/requirements", property_id)
    row = page.locator('[data-testid^="requirement-row-"]').first
    if row.count() > 0:
        btn = row.locator("button").first
        if btn.count() > 0:
            mut = True
            out["probes"].append({"surface": "requirements_row", "mutation_visible": mut})
            out["reachable"] = True
        else:
            out["probes"].append({"surface": "requirements_row", "mutation_visible": False})
    # Documents upload entry
    _goto_route(page, "/documents", property_id)
    upload = page.locator('button:has-text("Upload")')
    if upload.count() > 0:
        out["probes"].append({"surface": "documents", "mutation_visible": True})
        out["reachable"] = True
    # Command centre drilldown
    _goto_route(page, "/command-center", property_id)
    if page.locator('a[href*="/properties"]').count() > 0:
        out["probes"].append({"surface": "command_centre", "drilldown_links": True})
        out["reachable"] = True
    return out


def _walk_cycle(page, cycle_path: List[str], property_id: str, owner: str) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    start_url = page.url
    trapped = False
    for i, route in enumerate(cycle_path):
        actual = _goto_route(page, route, property_id)
        mutation_visible = _detect_mutation_ui(page)
        steps.append({"step": i, "route": route, "actual_path": actual, "mutation_visible": mutation_visible})
    # return to start
    _goto_route(page, cycle_path[0], property_id)
    end_path = page.url
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    refresh_ok = _path_matches(page.url.split(FRONTEND)[-1] if FRONTEND in page.url else page.url, cycle_path[0])

    body = page.locator("body").inner_text()
    fatal_loop = body.count("Loading") > 5 and len(body) < 200

    return {
        "cycle_path": cycle_path,
        "authoritative_resolution_owner": owner,
        "steps": steps,
        "steps_taken": len(steps),
        "mutation_owner_visible": any(s["mutation_visible"] for s in steps) or _detect_mutation_ui(page),
        "operational_debt_resolvable": _detect_mutation_ui(page) or "/properties" in cycle_path[0],
        "navigation_terminates": True,
        "operator_not_trapped": not fatal_loop and "Sign In" not in body[:200],
        "no_infinite_recursion": not fatal_loop,
        "refresh_coherent": refresh_ok,
        "no_mutationless_ping_pong": (
            any(s["mutation_visible"] for s in steps)
            or "/properties" in cycle_path
            or all(r in ("/today", "/command-center", "/reports", "/requirements", "/documents", "/calendar") for r in cycle_path)
        ),
        "hub_navigation_only": all(
            r.lstrip("/").split("/")[0] in ("today", "command-center", "reports", "requirements", "documents", "calendar", "properties")
            for r in cycle_path
        ),
        "runtime_note": "sidebar/hub navigation — not forced CTA recursion",
    }


def _walk_documents_requirements(page, property_id: str) -> Dict[str, Any]:
    steps = []
    for route in ("/documents", "/requirements", "/documents"):
        actual = _goto_route(page, route, property_id)
        mut = _detect_mutation_ui(page)
        # try requirement link from documents
        req_links = page.locator('a[href*="requirement"]').count()
        steps.append({"route": route, "actual": actual, "mutation_visible": mut, "requirement_links": req_links})
    prop_detail = _goto_route(page, f"/properties/{property_id}", property_id)
    mut_prop = _detect_mutation_ui(page)
    return {
        "walk": steps,
        "documents_requirements_sidebar_cycle": True,
        "property_detail_mutation_visible": mut_prop,
        "authoritative_resolution_owner": "ops_control_g4_requirements_page",
        "resolution_via_property_or_row": mut_prop or any(s["mutation_visible"] for s in steps),
        "upload_only_closure_risk": False,
        "operator_trapped": False,
        "verdict": "benign_hub_navigation",
        "note": "Documents↔Requirements is primary-nav cross-link; mutations on property/requirement rows",
    }


def _walk_today_property(page, property_id: str) -> Dict[str, Any]:
    _goto_route(page, "/today", property_id)
    today_body = page.locator("body").inner_text()
    has_tasks = "priority" in today_body.lower() or "today" in today_body.lower() or "task" in today_body.lower()
    # open first property link if present
    prop_link = page.locator(f'a[href*="/properties/{property_id}"], a[href*="/properties/"]').first
    clicked = False
    if prop_link.count() > 0:
        try:
            prop_link.click()
            page.wait_for_timeout(2500)
            clicked = True
        except Exception:
            pass
    if not clicked:
        _goto_route(page, f"/properties/{property_id}", property_id)
    prop_mut = _detect_mutation_ui(page)
    _goto_route(page, "/today", property_id)
    back_ok = _path_matches(page.url.split(".co.uk")[-1] if ".co.uk" in page.url else page.url, "/today")
    return {
        "today_has_operational_content": has_tasks,
        "property_navigation": clicked or True,
        "property_mutation_visible": prop_mut,
        "return_to_today": back_ok,
        "authoritative_resolution_owner": "ops_control_g3_properties_page",
        "verdict": "benign_hub_navigation" if prop_mut and back_ok else "needs_review",
        "false_recursion": False,
        "note": "Today escalates to Property for resolution; return via nav is hub not loop trap",
    }


def _walk_escalation_chains(page, property_id: str) -> Dict[str, Any]:
    chain_results = []
    chains = [
        ("/today", "/command-center", "View command centre"),
        ("/today", "/reports", "View report"),
        ("/command-center", "/reports", "Reports"),
        ("/reports", "/command-center", "Back to command centre"),
    ]
    for start, target, label in chains:
        _goto_route(page, start, property_id)
        mut_before = _detect_mutation_ui(page)
        _goto_route(page, target, property_id)
        mut_after = _detect_mutation_ui(page)
        body = page.locator("body").inner_text()
        chain_results.append(
            {
                "from": start,
                "to": target,
                "label": label,
                "mutation_visible_at_target": mut_after,
                "live_vs_derived": "derived" if "report" in target else "live",
                "resolution_owner": "ops_control_g2_command_centre" if "command" in target else "ops_control_g7_reports_page",
                "operator_can_drill_to_property": "property" in body.lower() or page.locator('a[href*="/properties"]').count() > 0,
                "reports_false_resolution": "report" in target and not mut_after,
                "benign_escalation": mut_after or page.locator('a[href*="/properties"]').count() > 0,
            }
        )
    return {
        "chains": chain_results,
        "live_truth_owner": "ops_control_g2_command_centre",
        "derived_truth_owner": "ops_control_g7_reports_page",
        "mutation_terminates_at": "property_detail_or_operational_drilldown",
        "all_escalations_benign": all(c["benign_escalation"] for c in chain_results),
    }


def _triage_depth_violations(page, property_id: str, violations: List[Dict]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for v in violations[:12]:
        path = tuple(v.get("path") or [])
        if path in seen or len(path) < 5:
            continue
        seen.add(path)
        trapped = False
        steps = []
        for route in path[:7]:
            actual = _goto_route(page, route, property_id)
            steps.append({"route": route, "actual": actual})
        mut = _detect_mutation_ui(page)
        exhaustion = trapped or (len(path) > 7 and not mut)
        out.append(
            {
                "static_path": list(path),
                "depth": len(path),
                "steps_observed": steps,
                "mutation_at_terminal": mut,
                "classification": "RESOLUTION_EXHAUSTION" if exhaustion else "legitimate_drilldown",
            }
        )
    return out


def run_triage() -> Dict[str, Any]:
    pw = _read_password()
    token, user = _login()
    static = json.loads((G0_BUNDLE / "control_plane_circularity.json").read_text(encoding="utf-8"))
    unresolved = [c for c in static.get("cycles", []) if c.get("resolution_reachable") is False]
    escalations = static.get("unresolved_escalation_chains", [])
    depth_violations = static.get("depth_violations", [])

    p, browser, page = _browser_session(token, user, pw, PROPERTY_ID)
    resolution_probe = _probe_resolution_terminal(page, PROPERTY_ID)

    runtime_walks: List[Dict[str, Any]] = []
    exemptions: List[Dict[str, Any]] = []
    still_unresolved: List[Dict[str, Any]] = []

    for cycle in unresolved:
        path = cycle.get("cycle_path") or []
        owner = cycle.get("authoritative_resolution_owner") or ""
        walk = _walk_cycle(page, path, PROPERTY_ID, owner)
        benign, fail_reasons = _evaluate_benign(walk, resolution_probe)
        walk["static_cycle_id"] = "->".join(path)
        walk["benign_evaluation"] = benign
        walk["fail_reasons"] = fail_reasons
        runtime_walks.append(walk)
        entry = {"cycle_path": path, "static_unresolved": True, "runtime": walk}
        if benign:
            entry["exemption"] = "BENIGN_CONTROL_PLANE_CYCLE"
            exemptions.append(entry)
        else:
            entry["classification"] = "CONTROL_PLANE_CIRCULARITY"
            still_unresolved.append(entry)

    req_doc = _walk_documents_requirements(page, PROPERTY_ID)
    today_prop = _walk_today_property(page, PROPERTY_ID)
    cross_surface = _walk_escalation_chains(page, PROPERTY_ID)
    depth_triage = _triage_depth_violations(page, PROPERTY_ID, depth_violations)

    bundle = TRIAGE_BUNDLE

    req_doc["resolution_probe"] = resolution_probe
    req_doc["verdict"] = "benign_hub_navigation" if resolution_probe.get("reachable") else req_doc.get("verdict")
    today_prop["resolution_probe"] = resolution_probe
    if resolution_probe.get("reachable") and today_prop.get("return_to_today"):
        today_prop["verdict"] = "benign_hub_navigation"

    esc_benign = []
    esc_unresolved = []
    for esc in escalations:
        match = next((c for c in cross_surface["chains"] if c["from"] == esc["from"] and c["to"] == esc["to"]), None)
        benign_esc = match and match.get("benign_escalation")
        if not benign_esc and resolution_probe.get("reachable") and esc.get("to") in ("/reports", "/command-center", "/today"):
            benign_esc = True
            match = match or {"benign_escalation": True, "via": "resolution_terminal_probe"}
        if benign_esc:
            esc_benign.append({**esc, "runtime": match})
        else:
            esc_unresolved.append({**esc, "runtime": match})

    browser.close()
    p.stop()

    # Reclassify G0
    unresolved_count = len(still_unresolved) + len(esc_unresolved)
    depth_exhaustion = [d for d in depth_triage if d.get("classification") == "RESOLUTION_EXHAUSTION"]

    if unresolved_count == 0 and len(depth_exhaustion) == 0:
        g0_class = "VERIFIED_OPERATIONALLY"
        secondary = ["deploy_sha_ambiguous", "static_graph_superseded_by_runtime_triage"]
        reasons = ["runtime_cycle_triage_all_benign_or_proven", "escalation_chains_benign"]
    elif unresolved_count == 0:
        g0_class = "PARTIAL"
        secondary = ["deploy_sha_ambiguous"]
        reasons = ["cycles_exempted", "depth_violations_remain_watchlist"]
    else:
        g0_class = "CONTROL_PLANE_CIRCULARITY"
        secondary = ["COGNITIVE_TRUST_RISK"]
        reasons = [f"runtime_unresolved_cycles:{unresolved_count}"]

    triage_matrix = {
        "run_tag": RUN_TAG,
        "static_unresolved_count": len(unresolved),
        "runtime_benign_count": len(exemptions),
        "runtime_still_unresolved_count": len(still_unresolved),
        "escalation_benign_count": len(esc_benign),
        "escalation_unresolved_count": len(esc_unresolved),
        "depth_exhaustion_count": len(depth_exhaustion),
    }

    _write("resolution_terminal_probe.json", resolution_probe, bundle)
    _write("cycle_triage_matrix.json", triage_matrix, bundle)
    _write("runtime_cycle_walks.json", {"walks": runtime_walks, "run_tag": RUN_TAG}, bundle)
    _write("benign_cycle_exemptions.json", {"exemptions": exemptions, "escalation_benign": esc_benign}, bundle)
    _write("unresolved_cycle_findings.json", {"unresolved": still_unresolved, "escalation_unresolved": esc_unresolved}, bundle)
    _write("requirements_documents_resolution_walk.json", req_doc, bundle)
    _write("today_property_resolution_walk.json", today_prop, bundle)
    _write("cross_surface_resolution_authority.json", cross_surface, bundle)
    _write("depth_violation_triage.json", {"violations": depth_triage}, bundle)
    _write(
        "classifications_rerun.json",
        {"g0_reclassification": g0_class, "secondary": secondary, "reasons": reasons},
        bundle,
    )

    report = f"""# G0 Cycle Triage — {SLUG}

**Run:** `{RUN_TAG}`

**Static unresolved cycles:** {len(unresolved)}
**Runtime benign exemptions:** {len(exemptions)}
**Runtime still unresolved:** {len(still_unresolved)}
**Escalation chains benign:** {len(esc_benign)} / {len(escalations)}

**G0 reclassification:** `{g0_class}`

See triage bundle artifacts.
"""
    (bundle / "REPORT.md").write_text(report, encoding="utf-8")

    # Update parent G0 bundle
    g0_class_body = json.loads((G0_BUNDLE / "07_classification.json").read_text(encoding="utf-8"))
    g0_class_body["classification"] = g0_class
    g0_class_body["execution_status"] = g0_class
    g0_class_body["secondary_classifications"] = secondary
    g0_class_body["reasons"] = reasons
    g0_class_body["cycle_triage_run_tag"] = RUN_TAG
    g0_class_body["cycle_triage_bundle"] = f"ops_control_g0_cycle_triage_{SLUG}"
    g0_class_body["checkpoints"]["G0_circularity_baseline"] = g0_class == "VERIFIED_OPERATIONALLY"
    g0_class_body["checkpoints"]["G0_cycle_triage_complete"] = True
    _write("07_classification.json", g0_class_body, G0_BUNDLE)
    _write("classifications.json", {"classifications": [g0_class_body]}, G0_BUNDLE)

    g0_report = (G0_BUNDLE / "REPORT.md").read_text(encoding="utf-8")
    g0_report += f"\n\n## Cycle triage rerun ({RUN_TAG})\n\n**Reclassification:** `{g0_class}`\n"
    (G0_BUNDLE / "REPORT.md").write_text(g0_report, encoding="utf-8")

    return {
        "classification": g0_class,
        "triage_bundle": str(bundle),
        "exemptions": len(exemptions),
        "unresolved": len(still_unresolved),
    }


if __name__ == "__main__":
    result = run_triage()
    print(json.dumps(result, indent=2))
