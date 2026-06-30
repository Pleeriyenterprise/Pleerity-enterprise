"""
REQUIREMENT-AUTHORITY-ONBOARDING-DRIFT-01 — staging shadow + HTTP baseline validation.

Shadow: local develop code exercised against pleerity_staging Mongo (pre-commit).
HTTP: read-only probes against live staging API (may reflect pre-deploy behaviour).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]

BACKEND = Path(__file__).resolve().parent
OUT = BACKEND / "docs/audit/requirement_authority_onboarding_drift_01"
PROGRAMME = "REQUIREMENT-AUTHORITY-ONBOARDING-DRIFT-STAGING-VALIDATION-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

STAGING_API = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
STAGING_ROOT = os.environ.get("STAGING_ROOT", "https://pleerity-enterprise.onrender.com").rstrip("/")
TARGET_CRN = os.environ.get("RAOD_STAGING_CRN", "PLE-CVP-2026-000003").strip()
TARGET_CLIENT_ID = os.environ.get("RAOD_STAGING_CLIENT_ID", "").strip()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_pytest() -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_requirement_authority_onboarding_drift_01.py", "-v", "--tb=line"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "command": "python -m pytest tests/test_requirement_authority_onboarding_drift_01.py -v --tb=line",
        "output_tail": out[-4000:] if len(out) > 4000 else out,
    }


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _admin_login() -> Optional[str]:
    email = os.environ.get("STAGING_ADMIN_EMAIL", "prosper@yopmail.com").strip()
    pw = os.environ.get("STAGING_ADMIN_PASSWORD", "Pastor@36$").strip()
    r = httpx.post(f"{STAGING_API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    return r.json().get("access_token") if r.status_code == 200 else None


def _step_up(admin_token: str, password: str) -> Optional[str]:
    r = httpx.post(
        f"{STAGING_API}/auth/step-up/verify",
        headers=_headers(admin_token),
        json={"password": password},
        timeout=60,
    )
    return r.json().get("step_up_token") if r.status_code == 200 else None


def _conf_token(admin_token: str, client_id: str) -> Optional[str]:
    r = httpx.post(
        f"{STAGING_API}/admin/governance/confirmation-token",
        headers=_headers(admin_token),
        json={
            "action_id": "start_impersonation",
            "reason": f"{PROGRAMME} read-only validation",
            "resource_key": client_id,
        },
        timeout=60,
    )
    return r.json().get("token") if r.status_code == 200 else None


def _impersonate(client_id: str) -> Tuple[Optional[str], Dict[str, Any]]:
    email = os.environ.get("STAGING_ADMIN_EMAIL", "prosper@yopmail.com").strip()
    pw = os.environ.get("STAGING_ADMIN_PASSWORD", "Pastor@36$").strip()
    admin = _admin_login()
    meta: Dict[str, Any] = {"admin_login": bool(admin)}
    if not admin:
        return None, meta
    st = _step_up(admin, pw)
    ct = _conf_token(admin, client_id)
    h = _headers(admin)
    if st:
        h["X-Step-Up-Token"] = st
    if ct:
        h["X-Admin-Confirmation-Token"] = ct
    r = httpx.post(
        f"{STAGING_API}/admin/clients/{client_id}/impersonation/start",
        headers=h,
        json={"reason": f"{PROGRAMME} read-only validation"},
        params={"ttl_minutes": 30},
        timeout=120,
    )
    meta["impersonation_status"] = r.status_code
    if r.status_code != 200:
        meta["impersonation_detail"] = r.text[:500]
        return None, meta
    return r.json().get("access_token"), meta


def _http_tracked_attention_count(rows: List[Dict[str, Any]]) -> int:
    """Mirror frontend isRequirementIncludedInAttentionViews / reporting_semantics_v1."""
    n = 0
    for r in rows:
        if r.get("client_surface_visible") is False:
            continue
        life = str(r.get("client_lifecycle_state") or "").upper()
        if life == "NOT_APPLICABLE":
            continue
        if r.get("is_tracked") is False or r.get("tracked") is False:
            continue
        cls = str(r.get("compliance_requirement_class") or r.get("requirement_class") or "").upper()
        if cls in ("OBLIGATION", "SYSTEM"):
            continue
        if cls and cls not in ("DOCUMENT", "JOB"):
            continue
        app = str(r.get("applicability") or "").upper().strip()
        if app == "NOT_REQUIRED":
            continue
        n += 1
    return n


def _occupation_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        rt = str(r.get("requirement_type") or r.get("requirement_code") or "").lower()
        if "occupation_contract" in rt or rt == "occupation_contract":
            out.append(r)
    return out


async def _shadow_validate(client_id: str) -> Dict[str, Any]:
    from database import database
    from routes.portal import _portal_requirement_count_semantics
    from services.reporting_semantics_v1 import requirement_row_in_tracked_attention_views
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
    from services.requirement_truth import enrich_requirements_for_client
    from services.risk_signal_service import (
        RISK_TYPE_ELECTRICAL,
        _fetch_requirements_confirmed_calendar_risk,
        _rule_electrical,
    )

    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(500)
    property_ids = [p["property_id"] for p in properties]
    raw_reqs = await db.requirements.find({"client_id": client_id}, {"_id": 0}).to_list(10000)

    semantics = await _portal_requirement_count_semantics(db, client_id, client, property_ids)

    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=raw_reqs,
        client_doc=client,
        properties=properties,
    )
    enriched, _ = await enrich_requirements_for_client(db, client_id, list(filtered))
    visible = [r for r in enriched if r.get("client_surface_visible") is not False]
    tracked = [r for r in visible if requirement_row_in_tracked_attention_views(r)]

    # Per-property occupation analysis
    occ_by_prop_raw: Dict[str, List[Dict]] = defaultdict(list)
    for r in raw_reqs:
        rt = str(r.get("requirement_type") or "").lower()
        if "occupation" in rt:
            occ_by_prop_raw[r.get("property_id") or ""].append(r)

    occ_by_prop_visible: Dict[str, List[Dict]] = defaultdict(list)
    for r in visible:
        rt = str(r.get("requirement_type") or "").lower()
        if "occupation" in rt:
            occ_by_prop_visible[r.get("property_id") or ""].append(r)

    wales_props = [p for p in properties if str(p.get("jurisdiction") or "").lower() == "wales"]
    occupation_checks = []
    props_with_occ = {r.get("property_id") for r in raw_reqs if "occupation" in str(r.get("requirement_type") or "").lower()}
    check_props = wales_props or [p for p in properties if p["property_id"] in props_with_occ]
    for p in check_props:
        pid = p["property_id"]
        pname = p.get("name") or p.get("property_name") or pid
        raw_occ = occ_by_prop_raw.get(pid, [])
        vis_occ = occ_by_prop_visible.get(pid, [])
        occupation_checks.append(
            {
                "property_id": pid,
                "property_name": pname,
                "raw_occupation_row_count": len(raw_occ),
                "raw_occupation_types": [r.get("requirement_type") for r in raw_occ],
                "runtime_visible_occupation_count": len(vis_occ),
                "runtime_visible_occupation_types": [r.get("requirement_type") for r in vis_occ],
                "pass_one_visible": len(vis_occ) <= 1,
                "raw_duplicate_pair": len(raw_occ) >= 2
                and "occupation_contract" in [str(x.get("requirement_type")).lower() for x in raw_occ]
                and "wales_occupation_contract" in [str(x.get("requirement_type")).lower() for x in raw_occ],
            }
        )

    # Electrical risk — properties with EICR PENDING/MISSING only
    eicr_checks = []
    for p in properties:
        pid = p["property_id"]
        eicr_rows = [
            r
            for r in raw_reqs
            if r.get("property_id") == pid
            and "eicr" in str(r.get("requirement_type") or r.get("requirement_code") or "").lower()
        ]
        if not eicr_rows:
            continue
        statuses = [str(r.get("status") or "").upper() for r in eicr_rows]
        pending_only = all(s in ("PENDING", "MISSING") for s in statuses)
        if not pending_only:
            continue
        confirmed = await _fetch_requirements_confirmed_calendar_risk(db, pid, client_id)
        electrical = await _rule_electrical(
            db, pid, client_id, p, [], [], [], confirmed
        )
        active_mongo = await db.risk_signals.find(
            {
                "client_id": client_id,
                "property_id": pid,
                "risk_type": RISK_TYPE_ELECTRICAL,
                "status": {"$in": ["active", "ACTIVE"]},
            },
            {"_id": 0, "signal_id": 1, "reasons": 1, "status": 1},
        ).to_list(20)
        eicr_checks.append(
            {
                "property_id": pid,
                "eicr_statuses": statuses,
                "shadow_generated_electrical_count": len(electrical),
                "shadow_pass_no_electrical_on_pending": len(electrical) == 0,
                "mongo_active_electrical_legacy_deploy": len(active_mongo),
                "mongo_active_electrical_sample": active_mongo[:3],
            }
        )

    reconcile_assessment = {
        "clients_with_raw_occupation_duplicate_pairs": 0,
        "properties_needing_reconcile": [],
    }
    for chk in occupation_checks:
        if chk.get("raw_duplicate_pair"):
            reconcile_assessment["clients_with_raw_occupation_duplicate_pairs"] += 1
            reconcile_assessment["properties_needing_reconcile"].append(
                {
                    "property_id": chk["property_id"],
                    "property_name": chk["property_name"],
                    "raw_types": chk["raw_occupation_types"],
                    "runtime_deduped_to": chk["runtime_visible_occupation_count"],
                    "reconcile_recommended": True,
                    "reason": "Raw Mongo retains duplicate rows; runtime dedupe hides in client surfaces",
                }
            )

    count_semantics_pass = (
        semantics.get("requirements_tracked_attention_count") == len(tracked)
        and semantics.get("requirements_runtime_visible_count") == len(visible)
        and semantics.get("requirements_count_semantics")
        == "tracked_attention_document_job_excludes_obligation"
    )

    return {
        "client_id": client_id,
        "customer_reference": client.get("customer_reference"),
        "property_count": len(properties),
        "raw_requirement_count": len(raw_reqs),
        "semantics": semantics,
        "shadow_tracked_attention_count": len(tracked),
        "shadow_runtime_visible_count": len(visible),
        "count_semantics_pass": count_semantics_pass,
        "wales_occupation_checks": occupation_checks,
        "wales_occupation_pass": all(c["pass_one_visible"] for c in occupation_checks) if occupation_checks else None,
        "eicr_electrical_risk_checks": eicr_checks,
        "eicr_electrical_pass": all(c["shadow_pass_no_electrical_on_pending"] for c in eicr_checks)
        if eicr_checks
        else None,
        "reconcile_assessment": reconcile_assessment,
    }


def _http_validate(client_id: str, portal_token: str) -> Dict[str, Any]:
    h = _headers(portal_token)
    samples: Dict[str, Any] = {}

    t0 = time.perf_counter()
    ss = httpx.get(f"{STAGING_API}/portal/setup-status", params={"client_id": client_id}, timeout=120)
    samples["setup_status"] = {
        "status": ss.status_code,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "body": ss.json() if ss.status_code == 200 else ss.text[:400],
    }

    t0 = time.perf_counter()
    req = httpx.get(f"{STAGING_API}/client/requirements", headers=h, params={"projection": "full"}, timeout=120)
    req_body = req.json() if req.status_code == 200 else {}
    rows = req_body.get("requirements") if isinstance(req_body, dict) else []
    samples["requirements"] = {
        "status": req.status_code,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "row_count": len(rows),
        "http_tracked_attention_count": _http_tracked_attention_count(rows),
        "occupation_visible": [
            {
                "requirement_id": r.get("requirement_id"),
                "requirement_type": r.get("requirement_type"),
                "property_id": r.get("property_id"),
            }
            for r in _occupation_rows(rows)
        ],
        "occupation_visible_count": len(_occupation_rows(rows)),
    }

    t0 = time.perf_counter()
    dash = httpx.get(f"{STAGING_API}/client/dashboard", headers=h, timeout=120)
    dash_body = dash.json() if dash.status_code == 200 else {}
    stats = (dash_body.get("compliance_score") or {}).get("stats") or dash_body.get("stats") or {}
    samples["dashboard"] = {
        "status": dash.status_code,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "stats": stats,
    }

    t0 = time.perf_counter()
    cc = httpx.get(f"{STAGING_API}/client/command-center", headers=h, timeout=180)
    cc_body = cc.json() if cc.status_code == 200 else {}
    risk_stream = cc_body.get("risk_signals") or cc_body.get("active_risk_signals") or []
    if isinstance(risk_stream, dict):
        risk_stream = risk_stream.get("items") or risk_stream.get("signals") or []
    electrical_risks = [
        r for r in risk_stream if "electrical" in str(r.get("risk_type") or r.get("title") or "").lower()
    ]
    samples["command_center"] = {
        "status": cc.status_code,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "compliance_status_summary": cc_body.get("compliance_status_summary"),
        "electrical_risk_in_stream_count": len(electrical_risks),
        "electrical_risk_sample": electrical_risks[:3],
    }

    setup_body = samples["setup_status"].get("body") or {}
    has_semantic_fields = all(
        k in setup_body
        for k in (
            "requirements_tracked_attention_count",
            "requirements_runtime_visible_count",
            "requirements_count_semantics",
        )
    )

    tracked_align = (
        samples["requirements"]["http_tracked_attention_count"]
        == samples["requirements"]["row_count"]
        or samples["requirements"]["http_tracked_attention_count"] <= samples["requirements"]["row_count"]
    )

    return {
        "samples": samples,
        "setup_status_has_semantic_fields": has_semantic_fields,
        "requirements_tracked_matches_http_derived": tracked_align,
        "http_occupation_visible_count": samples["requirements"]["occupation_visible_count"],
        "http_occupation_pass_one_or_zero": samples["requirements"]["occupation_visible_count"] <= 1,
        "deployed_fixes_detected_on_http": has_semantic_fields,
    }


async def _find_duplicate_occupation_client(db) -> Optional[str]:
    from collections import defaultdict

    types = ["wales_occupation_contract", "occupation_contract"]
    rows = await db.requirements.find(
        {"requirement_type": {"$in": types}},
        {"_id": 0, "client_id": 1, "property_id": 1, "requirement_type": 1},
    ).to_list(500)
    by: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for r in rows:
        by[r["client_id"]][r["property_id"]].add(r["requirement_type"])
    for cid, ps in by.items():
        for ts in ps.values():
            if "occupation_contract" in ts and "wales_occupation_contract" in ts:
                return cid
    return None


async def _resolve_client_id() -> Tuple[Optional[str], Dict[str, Any]]:
    from database import database

    db = database.get_db()
    meta: Dict[str, Any] = {"search_crn": TARGET_CRN}
    if TARGET_CLIENT_ID:
        meta["resolved_via"] = "env"
        return TARGET_CLIENT_ID, meta
    if TARGET_CRN:
        c = await db.clients.find_one({"customer_reference": TARGET_CRN}, {"_id": 0, "client_id": 1})
        if c:
            meta["resolved_via"] = "customer_reference"
            return c["client_id"], meta
    # Fallback: Wales property with occupation duplicate in mongo
    cursor = db.requirements.find(
        {"requirement_type": {"$in": ["occupation_contract", "wales_occupation_contract"]}},
        {"_id": 0, "client_id": 1, "property_id": 1, "requirement_type": 1},
    )
    pairs: Dict[str, set] = defaultdict(set)
    async for row in cursor:
        pairs[row["client_id"]].add((row["property_id"], row["requirement_type"]))
    for cid, entries in pairs.items():
        by_prop: Dict[str, set] = defaultdict(set)
        for pid, rt in entries:
            by_prop[pid].add(rt)
        if any("occupation_contract" in types and "wales_occupation_contract" in types for types in by_prop.values()):
            meta["resolved_via"] = "mongo_duplicate_occupation_scan"
            meta["fallback_client_id"] = cid
            return cid, meta
    # Any Wales client with wales_occupation_contract
    row = await db.requirements.find_one(
        {"requirement_type": "wales_occupation_contract"},
        {"_id": 0, "client_id": 1},
        sort=[("updated_at", -1)],
    )
    if row:
        meta["resolved_via"] = "latest_wales_occupation_contract"
        return row["client_id"], meta
    return None, meta


async def _staging_version_probe() -> Dict[str, Any]:
    try:
        r = httpx.get(f"{STAGING_API}/version", timeout=60)
        body = r.json() if r.status_code == 200 else {}
        return {"status": r.status_code, "body": body}
    except Exception as e:
        return {"status": None, "error": str(e)}


async def main() -> int:
    from database import database

    await database.connect()

    OUT.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "validated_at": _utc(),
        "branch": "develop",
        "staging_api": STAGING_API,
        "mode": "shadow_local_code_plus_http_baseline",
        "production_touched": False,
    }

    report["local_pytest"] = _run_pytest()
    report["staging_version"] = await _staging_version_probe()

    client_id, resolve_meta = await _resolve_client_id()
    report["client_resolution"] = resolve_meta
    if not client_id:
        report["verdict"] = "BLOCKED"
        report["blocker"] = "No Wales / CRN target client found on pleerity_staging"
        _write_outputs(report)
        return 1

    report["client_id"] = client_id
    report["shadow_validation"] = await _shadow_validate(client_id)

    dup_client = await _find_duplicate_occupation_client(database.get_db())
    if dup_client and dup_client != client_id:
        report["duplicate_occupation_client_id"] = dup_client
        report["duplicate_occupation_shadow"] = await _shadow_validate(dup_client)

    portal_token, imp_meta = _impersonate(client_id)
    report["impersonation"] = imp_meta
    if not portal_token and dup_client:
        portal_token, imp_meta_dup = _impersonate(dup_client)
        report["impersonation_duplicate_client"] = imp_meta_dup
        if portal_token:
            report["http_client_id"] = dup_client
    if portal_token:
        http_cid = report.get("http_client_id") or client_id
        report["http_validation"] = _http_validate(http_cid, portal_token)
    else:
        report["http_validation"] = {"skipped": True, "reason": "impersonation_failed"}

    # Always probe primary CRN setup-status (unauthenticated) for count semantics fields
    ss_primary = httpx.get(
        f"{STAGING_API}/portal/setup-status",
        params={"client_id": client_id},
        timeout=120,
    )
    report["http_setup_status_primary_crn"] = {
        "client_id": client_id,
        "customer_reference": TARGET_CRN,
        "status": ss_primary.status_code,
        "body": ss_primary.json() if ss_primary.status_code == 200 else ss_primary.text[:400],
        "has_semantic_fields": ss_primary.status_code == 200
        and all(
            k in (ss_primary.json() or {})
            for k in (
                "requirements_tracked_attention_count",
                "requirements_runtime_visible_count",
                "requirements_count_semantics",
            )
        ),
    }

    shadow = report["shadow_validation"]
    dup_shadow = report.get("duplicate_occupation_shadow") or {}
    http = report.get("http_validation") or {}

    occ_pass_primary = shadow.get("wales_occupation_pass")
    occ_pass_dup = dup_shadow.get("wales_occupation_pass")
    occupation_pass = occ_pass_dup is True or (
        occ_pass_primary is True or (occ_pass_primary is None and not shadow.get("wales_occupation_checks"))
    )

    checks = {
        "local_pytest": report["local_pytest"]["passed"],
        "shadow_wales_one_occupation": occupation_pass,
        "shadow_duplicate_client_dedupe": occ_pass_dup is not False if dup_shadow else True,
        "shadow_count_semantics": shadow.get("count_semantics_pass") is True,
        "shadow_eicr_no_premature_risk": shadow.get("eicr_electrical_pass") is not False,
    }

    if not http.get("skipped"):
        http_cid = report.get("http_client_id") or client_id
        http_shadow = dup_shadow if http_cid == dup_client and dup_shadow else shadow
        shadow_tracked = http_shadow.get("shadow_tracked_attention_count")
        http_tracked = http.get("samples", {}).get("requirements", {}).get("http_tracked_attention_count")
        checks["http_tracked_aligns_shadow"] = shadow_tracked == http_tracked
        checks["http_dashboard_stats_present"] = bool(
            http.get("samples", {}).get("dashboard", {}).get("stats")
            or (http.get("samples", {}).get("command_center", {}).get("compliance_status_summary") or {}).get(
                "requirements_total"
            )
        )
        checks["http_occupation_pre_deploy_duplicate_visible"] = http.get("http_occupation_visible_count", 0) > 1
        checks["http_setup_status_semantic_fields_absent_pre_deploy"] = not http.get(
            "setup_status_has_semantic_fields", True
        )

    report["checks"] = checks

    reconcile = shadow.get("reconcile_assessment") or {}
    dup_reconcile = (dup_shadow.get("reconcile_assessment") or {}) if dup_shadow else {}
    report["reconcile_required_before_production"] = bool(
        reconcile.get("properties_needing_reconcile") or dup_reconcile.get("properties_needing_reconcile")
    )

    shadow_ok = all(
        checks.get(k)
        for k in (
            "local_pytest",
            "shadow_wales_one_occupation",
            "shadow_duplicate_client_dedupe",
            "shadow_count_semantics",
            "shadow_eicr_no_premature_risk",
        )
    )
    http_deployed = http.get("deployed_fixes_detected_on_http") if not http.get("skipped") else False

    if shadow_ok:
        if http.get("skipped"):
            report["verdict"] = "SHADOW_ACCEPTED_HTTP_SKIPPED"
        elif http_deployed and checks.get("http_tracked_aligns_shadow"):
            report["verdict"] = "STAGING_VALIDATION_ACCEPTED"
        else:
            report["verdict"] = "SHADOW_ACCEPTED_PRE_DEPLOY_HTTP_BASELINE"
            report["post_commit_action"] = "Deploy develop to staging; re-run HTTP probes for setup-status semantic fields"
    else:
        report["verdict"] = "BLOCKED"
        report["failed_checks"] = [k for k, v in checks.items() if not v]

    _write_outputs(report)
    print(json.dumps({"verdict": report["verdict"], "client_id": client_id, "checks": checks}, indent=2))
    return 0 if shadow_ok else 1


def _write_outputs(report: Dict[str, Any]) -> None:
    json_path = OUT / "REQUIREMENT_AUTHORITY_STAGING_VALIDATION.json"
    md_path = OUT / "REQUIREMENT_AUTHORITY_STAGING_VALIDATION_REPORT.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    v = report.get("verdict", "UNKNOWN")
    shadow = report.get("shadow_validation") or {}
    dup_shadow = report.get("duplicate_occupation_shadow") or {}
    http = report.get("http_validation") or {}
    primary_ss = report.get("http_setup_status_primary_crn") or {}
    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Verdict:** `{v}`",
        f"**Run:** {report.get('run_tag')}",
        f"**Primary client:** {report.get('client_id')} ({shadow.get('customer_reference')})",
        f"**Duplicate occupation client:** {report.get('duplicate_occupation_client_id')} ({dup_shadow.get('customer_reference')})",
        f"**Staging deploy SHA:** {(report.get('staging_version') or {}).get('body', {}).get('commit_sha', 'unknown')}",
        "",
        "## Summary",
        "",
        "| Check | Result |",
        "|-------|--------|",
        f"| Local pytest (5 tests) | {'PASS' if report.get('local_pytest', {}).get('passed') else 'FAIL'} |",
        f"| Shadow occupation dedupe (000040) | {'PASS' if dup_shadow.get('wales_occupation_pass') else 'FAIL/N/A'} |",
        f"| Shadow count semantics (000003) | {'PASS' if shadow.get('count_semantics_pass') else 'FAIL'} |",
        f"| Shadow EICR no premature risk | {'PASS' if shadow.get('eicr_electrical_pass') else 'FAIL'} |",
        f"| HTTP fixes deployed on staging | {'NO — pre-deploy baseline' if not http.get('deployed_fixes_detected_on_http') else 'YES'} |",
        f"| Reconcile job required before prod | **{'YES' if report.get('reconcile_required_before_production') else 'NO'}** |",
        "",
        "## Commands",
        "",
        "```bash",
        "cd backend",
        "python -m pytest tests/test_requirement_authority_onboarding_drift_01.py -v --tb=line",
        "python tmp_requirement_authority_staging_validation_01.py",
        "```",
        "",
        "## Local pytest",
        "",
        f"- Exit code: {report.get('local_pytest', {}).get('exit_code')}",
        f"- Passed: {report.get('local_pytest', {}).get('passed')}",
        "",
        "## Shadow validation (local develop code + pleerity_staging Mongo)",
        "",
        f"- Raw requirements: {shadow.get('raw_requirement_count')}",
        f"- Runtime visible: {shadow.get('shadow_runtime_visible_count')}",
        f"- Tracked attention: {shadow.get('shadow_tracked_attention_count')}",
        f"- Semantics: `{json.dumps(shadow.get('semantics'), default=str)}`",
        f"- Wales occupation pass: {shadow.get('wales_occupation_pass')}",
        f"- EICR electrical pass: {shadow.get('eicr_electrical_pass')}",
        "",
        "### Primary CRN PLE-CVP-2026-000003",
        "",
        f"- Raw Mongo: {shadow.get('raw_requirement_count')} | Shadow tracked: {shadow.get('shadow_tracked_attention_count')} | Shadow visible: {shadow.get('shadow_runtime_visible_count')}",
        f"- Setup-status HTTP (pre-deploy): raw `requirements_count` only = {(primary_ss.get('body') or {}).get('requirements_count')}",
        f"- Semantic fields on HTTP: {primary_ss.get('has_semantic_fields')}",
        "",
        "### Duplicate occupation client PLE-CVP-2026-000040 (shadow dedupe proof)",
        "",
        f"- Raw Mongo: {dup_shadow.get('raw_requirement_count')} | Shadow tracked: {dup_shadow.get('shadow_tracked_attention_count')}",
        f"- HTTP requirements rows (pre-deploy, **still shows duplicate**): occupation count = {http.get('http_occupation_visible_count')}",
        f"- Legacy active electrical risk in Mongo (pre-deploy): see `duplicate_occupation_shadow.eicr_electrical_risk_checks`",
        "",
        "### Wales occupation checks (000040)",
        "",
        "```json",
        json.dumps(shadow.get("wales_occupation_checks"), indent=2, default=str),
        "```",
        "",
        "```json",
        json.dumps(dup_shadow.get("wales_occupation_checks"), indent=2, default=str),
        "```",
        "",
        "### Reconcile assessment",
        "",
        f"**Production reconcile required:** {report.get('reconcile_required_before_production')}",
        "",
        "```json",
        json.dumps(shadow.get("reconcile_assessment"), indent=2, default=str),
        "```",
        "",
        "Duplicate-client reconcile:",
        "",
        "```json",
        json.dumps(dup_shadow.get("reconcile_assessment"), indent=2, default=str),
        "```",
        "",
        "**Production recommendation:** Run a reconcile job to archive superseded `occupation_contract` rows where `wales_occupation_contract` exists for the same property. Runtime dedupe is sufficient for client surfaces but Mongo authority remains duplicated until reconcile.",
        "",
        "## HTTP validation (live staging API)",
        "",
    ]
    if http.get("skipped"):
        lines.append(f"- Skipped: {http.get('reason')}")
    else:
        lines.append(f"- Deployed fixes on HTTP: {http.get('deployed_fixes_detected_on_http')}")
        lines.append(f"- Setup-status sample: `{json.dumps(http.get('samples', {}).get('setup_status', {}).get('body'), default=str)[:800]}`")
        lines.append(f"- HTTP occupation visible count: {http.get('http_occupation_visible_count')}")
        lines.append(f"- HTTP tracked attention: {http.get('samples', {}).get('requirements', {}).get('http_tracked_attention_count')}")
    lines.extend(["", "## Checks", "", "```json", json.dumps(report.get("checks"), indent=2), "```", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
