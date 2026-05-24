"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G0 programme precheck harness.

Default: scaffold-only (static artifacts, NOT_EXECUTED).
--execute-runtime: first real G0 verification (read-only; no lifecycle mutations).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ops_runtime_verify_02.artifact_writer import ArtifactWriter, utc_now_iso
from services.ops_runtime_verify_02.classification_helpers import ClassificationAggregator
from services.ops_runtime_verify_02.constants import (
    EXECUTION_STATUS_NOT_EXECUTED,
    PROGRAMME_ID,
    VERIFY_01_FAMILY_SLUGS,
    Verify02Family,
)
from services.ops_runtime_verify_02.control_plane_circularity_service import (
    ControlPlaneCircularityService,
)
from services.ops_runtime_verify_02.operational_orphan_service import OperationalOrphanService
from services.ops_runtime_verify_02.projection_resolution_service import ProjectionResolutionService
from services.ops_runtime_verify_02.route_authority_registry import RouteAuthorityRegistry

PROGRAMME = PROGRAMME_ID
FAMILY = Verify02Family.G0.value

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"

G0_SURFACES = [
    ("/today", "ops_control_g1_today_page", "/client/tasks"),
    ("/command-center", "ops_control_g2_command_centre", "/client/command-center"),
    ("/properties", "ops_control_g3_properties_page", "/client/properties"),
    ("/requirements", "ops_control_g4_requirements_page", "/client/requirements"),
    ("/documents", "ops_control_g5_documents_page", "/client/documents"),
    ("/calendar", "ops_control_g6_calendar_page", "/calendar/events"),
    ("/reports", "ops_control_g7_reports_page", "/reports"),
]

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(client_id: str, property_id: str) -> str:
    return f"{client_id.split('-')[0]}_{property_id.split('-')[0]}"


def _bundle_dir(client_id: str, property_id: str) -> Path:
    return ROOT / "docs" / "audit" / f"ops_control_g0_programme_precheck_{_slug(client_id, property_id)}"


def _read_password(slug: str) -> str:
    env = os.environ.get("OPS_VERIFY_PASSWORD")
    if env:
        return env.strip()
    path = ROOT / f"docs/audit/ops_verify_01_{slug}/.ops_verify_temp_pw.txt"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"password not found: {path}")


def _http(method: str, url: str, **kwargs) -> httpx.Response:
    for attempt in range(4):
        try:
            with httpx.Client(timeout=120.0) as client:
                return client.request(method, url, **kwargs)
        except httpx.HTTPError:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"http_failed:{url}")


def _verify_01_lineage(slug: str) -> Dict[str, Any]:
    audit = ROOT / "docs" / "audit"
    rows: List[Dict[str, Any]] = []
    missing: List[str] = []
    not_verified: List[str] = []
    for fam in VERIFY_01_FAMILY_SLUGS:
        bundle_name = f"{fam}_{slug}"
        rel = f"{bundle_name}/07_classification.json"
        path = audit / bundle_name / "07_classification.json"
        row: Dict[str, Any] = {
            "family": fam,
            "bundle_path": rel,
            "present_on_disk": path.is_file(),
            "classification": None,
            "shared_dependency_bundle_ids": [],
            "proof_mode": None,
        }
        if path.is_file():
            try:
                body = json.loads(path.read_text(encoding="utf-8"))
                row["classification"] = body.get("classification")
                row["shared_dependency_bundle_ids"] = body.get("shared_dependency_bundle_ids") or []
                row["proof_mode"] = body.get("proof_mode")
            except json.JSONDecodeError:
                row["classification"] = "UNREADABLE"
        else:
            missing.append(fam)
        if row["classification"] != "VERIFIED_OPERATIONALLY":
            not_verified.append(fam)
        rows.append(row)
    intact = not missing and not not_verified
    return {
        "programme": "PRELAUNCH-OPS-RUNTIME-VERIFY-01",
        "pilot_slug": slug,
        "families": rows,
        "missing_families": missing,
        "not_verified_operationally": not_verified,
        "lineage_intact": intact,
        "all_verified_operationally": intact,
    }


def _origin_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT.parent), text=True
        ).strip()
    except Exception:
        return os.environ.get("OPS_VERIFY_ORIGIN_SHA", "unknown")


def _deployment_continuity(token: Optional[str]) -> Dict[str, Any]:
    probes: List[Dict[str, Any]] = []

    def probe(name: str, method: str, url: str, **kw) -> None:
        try:
            r = _http(method, url, **kw)
            probes.append({"name": name, "url": url, "status": r.status_code, "ok": r.status_code < 500})
        except Exception as exc:
            probes.append({"name": name, "url": url, "status": None, "ok": False, "error": str(exc)})

    probe("api_root", "GET", f"{API}/version")
    version_body: Dict[str, Any] = {}
    try:
        vr = _http("GET", f"{API}/version")
        if vr.status_code == 200:
            version_body = vr.json()
    except Exception:
        pass

    probe("frontend_root", "GET", FRONTEND)
    probe("auth_login", "POST", f"{API}/auth/login", json={"email": "probe@invalid.test", "password": "x"})
    probe("auth_contractor_login", "POST", f"{API}/auth/contractor-login", json={"email": "x@yopmail.com", "password": "x"})
    if token:
        probe("client_dashboard", "GET", f"{API}/client/dashboard", headers={"Authorization": f"Bearer {token}"})
        probe("tenant_route_sample", "GET", f"{API}/tenant/reported-issues", headers={"Authorization": f"Bearer {token}"})

    deploy_sha = version_body.get("commit_sha") or version_body.get("git_sha") or "unknown"
    sha_ambiguous = deploy_sha in ("unknown", "", None)
    api_ok = all(p["ok"] for p in probes if p["name"] in ("api_root", "auth_login"))
    fe_ok = any(p["ok"] for p in probes if p["name"] == "frontend_root")

    return {
        "checked_at": utc_now_iso(),
        "run_tag": RUN_TAG,
        "origin_main_sha": _origin_sha(),
        "staging_api": API,
        "frontend_url": FRONTEND,
        "version_endpoint": version_body,
        "deploy_sha": deploy_sha,
        "deploy_sha_ambiguous": sha_ambiguous,
        "probes": probes,
        "runtime_reachable": api_ok and fe_ok,
        "continuity_acceptable": api_ok and fe_ok,
        "note": "deploy_sha ambiguous — PARTIAL acceptable if runtime coherent" if sha_ambiguous else "",
    }


def _login_landlord(password: str) -> Tuple[str, Dict[str, Any]]:
    r = _http("POST", f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"landlord_login_failed:{r.status_code}:{r.text[:200]}")
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _route_authority_audit(registry: RouteAuthorityRegistry) -> Tuple[Dict[str, Any], List[str], bool]:
    rmap = registry.route_authority_map()
    routes = rmap.get("routes") or []
    conflicts: List[Dict[str, Any]] = []
    by_route: Dict[str, Dict[str, Any]] = {}
    issues: List[str] = []
    required = (
        "authoritative_family_owner",
        "projection_authority_owner",
        "authoritative_resolution_owner",
        "projection_resolution_rank",
        "mutation_owner",
        "primary_cta_owner",
    )
    for entry in routes:
        route = entry.get("route")
        if not route:
            continue
        missing = [k for k in required if not entry.get(k) and entry.get(k) != 0]
        if missing:
            issues.append(f"missing_fields:{route}:{missing}")
        if route in by_route and by_route[route].get("authoritative_family_owner") != entry.get("authoritative_family_owner"):
            conflicts.append({"route": route, "a": by_route[route], "b": entry})
        by_route[route] = entry
    coherent = not conflicts and not issues
    if conflicts:
        issues.append("PROJECTION_RESOLUTION_FAILURE")
    return rmap, issues, coherent


def _api_surface_probe(token: str, api_path: str) -> Dict[str, Any]:
    if api_path.startswith("/calendar"):
        url = f"{API}{api_path}"
    elif api_path.startswith("/reports"):
        url = f"{API}{api_path}"
    else:
        url = f"{API}{api_path}"
    r = _http("GET", url, headers={"Authorization": f"Bearer {token}"})
    return {"api_path": api_path, "status": r.status_code, "ok": r.status_code in (200, 403)}


def _browser_surfaces(token: str, user: dict, password: str, property_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    from playwright.sync_api import sync_playwright

    ctas: List[Dict[str, Any]] = []
    surfaces: List[Dict[str, Any]] = []

    def harvest_ctas(page, source_route: str) -> None:
        anchors = page.locator("a[href]").all()
        for a in anchors[:80]:
            try:
                href = a.get_attribute("href") or ""
                label = (a.inner_text() or "").strip()[:80]
                if not href or href.startswith("#") or href.startswith("javascript"):
                    continue
                ctas.append(
                    {
                        "source_route": source_route,
                        "label": label,
                        "href": href,
                        "mutation_owner": "none",
                    }
                )
            except Exception:
                continue

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.fill("#email", CLIENT_EMAIL)
        page.fill("#password", password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        body0 = page.locator("body").inner_text()
        if "Sign In" in body0[:300] and "Compliance" not in body0:
            page.evaluate(
                "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
                [token, user],
            )
        for route, _family, api_path in G0_SURFACES:
            url = f"{FRONTEND}{route}"
            if route == "/properties":
                url = f"{FRONTEND}/properties/{property_id}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_timeout(2500)
                body = page.locator("body").inner_text()
                fatal = any(x in body.lower() for x in ("application error", "something went wrong", "failed to load"))
                chrome = any(x in body for x in ("Compliance", "Operations", "PLE", "Today", "Properties", "Requirements", "Documents", "Calendar", "Reports", "Command"))
                ok = not fatal and (chrome or len(body) > 100)
                surfaces.append(
                    {
                        "route": route,
                        "url": url,
                        "shell_renders": ok,
                        "fatal_error": fatal,
                        "api_probe": _api_surface_probe(token, api_path),
                        "auth_reachable": True,
                    }
                )
                harvest_ctas(page, route)
            except Exception as exc:
                surfaces.append(
                    {
                        "route": route,
                        "url": url,
                        "shell_renders": False,
                        "error": str(exc),
                        "api_probe": _api_surface_probe(token, api_path),
                    }
                )
        browser.close()

    return {"surfaces": surfaces, "all_reachable": all(s.get("shell_renders") for s in surfaces)}, ctas


def _baseline_entities(token: str, property_id: str) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    headers = {"Authorization": f"Bearer {token}"}

    def add_from_list(items: List[Any], etype: str, route_tpl: str, id_key: str = "id") -> None:
        for it in items[:25]:
            if not isinstance(it, dict):
                continue
            eid = str(it.get(id_key) or it.get("_id") or "")
            if not eid:
                continue
            entities.append(
                {
                    "type": etype,
                    "id": eid,
                    "open": True,
                    "target_route": route_tpl.format(id=eid, property_id=property_id),
                }
            )

    r = _http("GET", f"{API}/client/properties", headers=headers)
    if r.status_code == 200:
        props = r.json()
        plist = props if isinstance(props, list) else props.get("properties") or props.get("items") or []
        add_from_list(plist, "property", "/properties/{id}")

    r = _http("GET", f"{API}/client/requirements", headers=headers)
    if r.status_code == 200:
        data = r.json()
        reqs = data if isinstance(data, list) else data.get("requirements") or data.get("items") or []
        add_from_list(reqs, "requirement", "/requirements")

    r = _http("GET", f"{API}/client/tasks", headers=headers)
    if r.status_code == 200:
        data = r.json()
        tasks_raw = data if isinstance(data, list) else data.get("tasks") or data.get("items") or []
        if isinstance(tasks_raw, dict):
            tasks_raw = tasks_raw.get("items") or tasks_raw.get("tasks") or list(tasks_raw.values())
        if not isinstance(tasks_raw, list):
            tasks_raw = []
        for t in tasks_raw[:25]:
            if not isinstance(t, dict):
                continue
            tid = str(t.get("id") or t.get("task_id") or "")
            deeplink = t.get("deeplink") or t.get("href") or "/today"
            entities.append({"type": "task", "id": tid or deeplink, "open": True, "target_route": str(deeplink)})

    return entities


def _baseline_projection_snapshot(token: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    snaps: Dict[str, Any] = {}
    for name, path in (
        ("command_center", "/client/command-center"),
        ("tasks", "/client/tasks"),
        ("protection_snapshot", "/client/protection-snapshot"),
        ("open_issues_hint", "/client/dashboard"),
    ):
        try:
            r = _http("GET", f"{API}{path}", headers=headers)
            if r.status_code == 200:
                body = r.json()
                if isinstance(body, dict):
                    snaps[name] = {k: body[k] for k in list(body.keys())[:20]}
                else:
                    snaps[name] = {"type": type(body).__name__, "len": len(body) if hasattr(body, "__len__") else None}
            else:
                snaps[name] = {"status": r.status_code}
        except Exception as exc:
            snaps[name] = {"error": str(exc)}
    return {"captured_at": utc_now_iso(), "snapshots": snaps}


def _classify_g0(
    lineage: Dict[str, Any],
    deploy: Dict[str, Any],
    route_ok: bool,
    route_issues: List[str],
    surfaces: Dict[str, Any],
    circularity: Dict[str, Any],
    orphan_audit: Dict[str, Any],
) -> Tuple[str, List[str], List[str]]:
    secondary: List[str] = []
    reasons: List[str] = []

    if not lineage.get("lineage_intact"):
        return "BLOCKED", secondary, ["verify_01_lineage_incomplete"]

    bad_cycles = [
        c
        for c in circularity.get("cycles") or []
        if c.get("loop_detected") and not c.get("resolution_reachable")
    ]
    if bad_cycles:
        secondary.append("CONTROL_PLANE_CIRCULARITY")
        secondary.append("COGNITIVE_TRUST_RISK")
        reasons.append("unresolved_control_plane_cycles")

    if not route_ok:
        secondary.append("PROJECTION_RESOLUTION_FAILURE")
        reasons.extend(route_issues)

    orphan_count = orphan_audit.get("orphan_count") or len(orphan_audit.get("orphans") or [])
    if orphan_count > 0:
        secondary.append("OPERATIONAL_ORPHAN_STATE")
        reasons.append(f"baseline_orphans:{orphan_count}")

    if not deploy.get("runtime_reachable"):
        return "FAIL_SYSTEM", secondary, reasons + ["staging_unreachable"]

    surfaces_ok = surfaces.get("all_reachable", False)
    if not surfaces_ok:
        return "FAIL_SYSTEM", secondary, reasons + ["operational_surfaces_not_reachable"]

    if secondary:
        if "CONTROL_PLANE_CIRCULARITY" in secondary:
            primary_fail = "CONTROL_PLANE_CIRCULARITY"
        elif "PROJECTION_RESOLUTION_FAILURE" in secondary:
            primary_fail = "PROJECTION_RESOLUTION_FAILURE"
        elif "OPERATIONAL_ORPHAN_STATE" in secondary:
            primary_fail = "OPERATIONAL_ORPHAN_STATE"
        else:
            primary_fail = sorted(secondary)[0]
        extras = sorted(set(secondary))
        if deploy.get("deploy_sha_ambiguous"):
            reasons.append("deploy_sha_ambiguous")
        return primary_fail, extras, reasons

    if deploy.get("deploy_sha_ambiguous"):
        return "PARTIAL", ["deploy_sha_ambiguous"], reasons + ["continuity_acceptable_runtime_coherent"]

    return "VERIFIED_OPERATIONALLY", secondary, reasons


def run_g0_execute(client_id: str, property_id: str) -> Path:
    slug = _slug(client_id, property_id)
    bundle = _bundle_dir(client_id, property_id)
    bundle.mkdir(parents=True, exist_ok=True)
    writer = ArtifactWriter(bundle, dry_run=False)
    password = _read_password(slug)

    lineage = _verify_01_lineage(slug)
    if not lineage.get("lineage_intact"):
        writer.write_json("verify_01_lineage.json", lineage)
        writer.write_json(
            "07_classification.json",
            {
                "programme": PROGRAMME,
                "family": FAMILY,
                "classification": "BLOCKED",
                "execution_status": "BLOCKED",
                "run_tag": RUN_TAG,
                "pilot_slug": slug,
                "reasons": ["verify_01_lineage_incomplete"],
            },
        )
        writer.write_report_md(f"# G0 BLOCKED — lineage\n\nMissing or unverified VERIFY-01 families.\n")
        return bundle

    token, user = _login_landlord(password)
    deploy = _deployment_continuity(token)

    registry = RouteAuthorityRegistry()
    rmap, route_issues, route_ok = _route_authority_audit(registry)
    circularity_svc = ControlPlaneCircularityService(registry)
    circularity = circularity_svc.build_artifact()
    projection = ProjectionResolutionService()
    proj_artifact = projection.build_artifact()
    proj_artifact["registration_note"] = "G0 baseline rank 1-5 registration only; no runtime contradiction classification"

    surface_inv, ctas = _browser_surfaces(token, user, password, property_id)
    entities = _baseline_entities(token, property_id)
    orphan_audit = OperationalOrphanService(registry).audit_entities(
        entities, entry_surfaces=["/today", "/command-center", "/properties"]
    )

    primary, secondary, reasons = _classify_g0(
        lineage, deploy, route_ok, route_issues, surface_inv, circularity, orphan_audit
    )

    writer.write_json("pilot_lock.json", {
        "programme": PROGRAMME,
        "client_id": client_id,
        "property_id": property_id,
        "pilot_slug": slug,
        "landlord_email": CLIENT_EMAIL,
        "run_tag": RUN_TAG,
    })
    writer.write_json("verify_01_lineage.json", lineage)
    writer.write_json("deployment_continuity.json", deploy)
    writer.write_json("active_routes_snapshot.json", {"routes": registry.routes})
    writer.write_json("route_authority_map.json", rmap)
    writer.write_json("operational_surface_inventory.json", surface_inv)
    writer.write_json("cta_inventory_baseline.json", {"ctas": ctas, "count": len(ctas), "run_tag": RUN_TAG})
    writer.write_json("control_plane_circularity.json", circularity)
    writer.write_json("operational_orphan_audit.json", orphan_audit)
    writer.write_json("projection_resolution_order.json", proj_artifact)
    writer.write_json("baseline_projection_snapshot.json", _baseline_projection_snapshot(token))
    writer.write_json("surface_availability.json", surface_inv)
    writer.write_json("entitlement_snapshot.json", {"deferred": "G7 deep entitlements at G7 family"})
    writer.write_json("feature_flag_snapshot.json", {"deferred": "feature flags at G0 not blocking"})

    class_body = {
        "programme": PROGRAMME,
        "family": FAMILY,
        "authoritative_verification_owner": FAMILY,
        "proof_mode": "operational_browser",
        "classification": primary,
        "execution_status": primary if primary != "PARTIAL" else "PARTIAL",
        "secondary_classifications": secondary,
        "reasons": reasons,
        "run_tag": RUN_TAG,
        "pilot_slug": slug,
        "shared_dependency_bundle_ids": [r["bundle_path"] for r in lineage["families"]],
        "checkpoints": {
            "G0_lineage": lineage.get("lineage_intact"),
            "G0_deployment": deploy.get("continuity_acceptable"),
            "G0_route_authority": route_ok,
            "G0_surfaces": surface_inv.get("all_reachable"),
            "G0_circularity_baseline": not any(
                c.get("loop_detected") and not c.get("resolution_reachable")
                for c in circularity.get("cycles") or []
            ),
            "G0_orphan_baseline": (orphan_audit.get("orphan_count") or 0) == 0,
        },
    }
    writer.write_json("07_classification.json", class_body)
    writer.write_json("classifications.json", {"classifications": [class_body]})

    watchlist = []
    if deploy.get("deploy_sha_ambiguous"):
        watchlist.append("deploy_sha unknown from /api/version — recorded; PARTIAL acceptable if runtime coherent")
    writer.write_json("watchlist.md", "\n".join(f"- {w}" for w in watchlist) if watchlist else "- none")

    writer.write_report_md(
        f"# G0 Programme Precheck — {slug}\n\n"
        f"**Run:** `{RUN_TAG}`\n\n"
        f"**Classification:** `{primary}`\n\n"
        f"**Reasons:** {', '.join(reasons) or 'none'}\n\n"
        f"**Secondary:** {', '.join(secondary) or 'none'}\n\n"
        "Read-only G0 execution; no lifecycle mutations.\n"
    )

    # programme status
    status_path = ROOT / "docs/audit/ops_control_verify_02/PROGRAMME_STATUS.json"
    if status_path.is_file():
        st = json.loads(status_path.read_text(encoding="utf-8"))
        st["families"][FAMILY] = primary
        st["g0_run_tag"] = RUN_TAG
        status_path.write_text(json.dumps(st, indent=2), encoding="utf-8")

    print(json.dumps({"classification": primary, "bundle": str(bundle)}, indent=2))
    return bundle


def run_g0_scaffold(client_id: str, property_id: str) -> Path:
    """Scaffold-only (not used when --execute-runtime)."""
    slug = _slug(client_id, property_id)
    bundle = _bundle_dir(client_id, property_id)
    writer = ArtifactWriter(bundle, dry_run=True)
    registry = RouteAuthorityRegistry()
    writer.write_json("07_classification.json", {
        "programme": PROGRAMME,
        "family": FAMILY,
        "classification": EXECUTION_STATUS_NOT_EXECUTED,
        "execution_status": EXECUTION_STATUS_NOT_EXECUTED,
    })
    writer.write_report_md(f"# G0 scaffold only — {slug}\n")
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="VERIFY-02 G0 harness")
    parser.add_argument("--client-id", default=CLIENT_ID)
    parser.add_argument("--property-id", default=PROPERTY_ID)
    parser.add_argument("--execute-runtime", action="store_true")
    args = parser.parse_args()
    if args.execute_runtime:
        run_g0_execute(args.client_id, args.property_id)
        return 0
    run_g0_scaffold(args.client_id, args.property_id)
    print("scaffold-only; use --execute-runtime for G0 verification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
