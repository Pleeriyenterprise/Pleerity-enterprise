"""Governed staging fixture seed helpers — PLAN-OUTCOME-GOVERNED-STAGING-FIXTURE-SEEDING-01."""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/plan_based_business_outcome_runtime_audit_01"
PROGRAMME = "PLAN-OUTCOME-GOVERNED-STAGING-FIXTURE-SEEDING-01"
FIXTURE_MARKER = "PLAN-OUTCOME-GOVERNED-FIXTURE-20260602"
ALLOWED_API_HOSTS = frozenset(
    {
        "pleerity-enterprise.onrender.com",
        "localhost",
        "127.0.0.1",
    }
)
FORBIDDEN_MONGO_HOST_MARKERS = frozenset({"prod", "production", "pleerity-prod"})

FIXTURE_PLAN: Dict[str, Dict[str, Any]] = {
    "A": {
        "label": "Solo exact — 1 property, 1 jurisdiction, all satisfied, Today calm",
        "plan_code": "PLAN_1_SOLO",
        "base_client_id": "10b2ddba-e952-4484-91d1-a8f0299d0824",
        "keep_property_id": "6b33492c-5e24-453b-bcde-49844fd4aede",
        "property_count": 1,
        "jurisdictions": ["England"],
        "mixed_jurisdiction": False,
        "evidence_method": "existing_satisfied_reference; archive surplus property",
        "assurance": "verified_documents + declarations already satisfied",
        "score_range": "85-95",
        "today": "calm",
        "reports": "no unresolved operational obligations",
        "cleanup": "reactivate archived property only with governed marker audit",
        "actions": ["archive_surplus_properties"],
    },
    "D": {
        "label": "Portfolio 5 same jurisdiction all satisfied",
        "plan_code": "PLAN_2_PORTFOLIO",
        "base_client_id": "80f83edd-ba12-41ed-929a-bbaf8c696a23",
        "property_count": 5,
        "jurisdictions": ["England"],
        "mixed_jurisdiction": False,
        "evidence_method": "property_create + requirements_sync + governed declaration/document seed",
        "assurance": "HUMAN_ACCEPTED documents + structured declarations",
        "score_range": "80-95",
        "today": "calm",
        "reports": "no unresolved operational obligations",
        "cleanup": "archive seeded properties tagged with marker",
        "actions": ["ensure_property_count", "sync_requirements", "satisfy_all_requirements"],
    },
    "E": {
        "label": "Portfolio 5-10 mixed jurisdiction all satisfied",
        "plan_code": "PLAN_2_PORTFOLIO",
        "base_client_id": "6bcc43c0-16f4-46a5-adf4-26693a0919d0",
        "property_count": 6,
        "jurisdictions": ["England", "Wales", "Scotland"],
        "mixed_jurisdiction": True,
        "evidence_method": "property_create + jurisdiction patch + requirements_sync + governed seed",
        "assurance": "mixed-jurisdiction registry obligations satisfied via valid paths",
        "score_range": "75-92",
        "today": "calm",
        "reports": "no unresolved operational obligations",
        "cleanup": "archive seeded properties tagged with marker",
        "actions": ["ensure_property_count", "assign_mixed_jurisdictions", "sync_requirements", "satisfy_all_requirements"],
    },
    "G": {
        "label": "Professional 3-5 same jurisdiction all satisfied",
        "plan_code": "PLAN_3_PRO",
        "base_client_id": "f68d4f4b-8007-43c6-84cb-a20c4ab69891",
        "property_count": 4,
        "jurisdictions": ["Wales"],
        "mixed_jurisdiction": False,
        "plan_override_note": "commercial entitlement upgrade to PLAN_3_PRO if base is portfolio",
        "evidence_method": "plan upgrade + property focus + governed seed",
        "assurance": "Wales same-jurisdiction professional obligations",
        "score_range": "80-94",
        "today": "calm",
        "reports": "no unresolved operational obligations",
        "cleanup": "revert plan only via governed commercial entitlement",
        "actions": ["ensure_pro_plan", "ensure_property_count", "align_jurisdiction", "sync_requirements", "satisfy_all_requirements"],
    },
    "H": {
        "label": "Professional 5-10 mixed jurisdiction all satisfied",
        "plan_code": "PLAN_3_PRO",
        "base_client_id": "6fd5ac4c-3fd4-4112-ade7-156977deb49f",
        "property_count": 7,
        "jurisdictions": ["England", "Wales", "Scotland"],
        "mixed_jurisdiction": True,
        "evidence_method": "retain mixed portfolio + governed bulk satisfaction",
        "assurance": "mixed professional portfolio all satisfied",
        "score_range": "75-93",
        "today": "calm",
        "reports": "no unresolved operational obligations",
        "cleanup": "do not delete pilot data; satisfaction reversible via audit",
        "actions": ["sync_requirements", "satisfy_all_requirements"],
    },
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_mongo_url(explicit: str = "", url_file: str = "") -> Tuple[Optional[str], Optional[str]]:
    if explicit:
        return explicit.strip(), os.getenv("DB_NAME", "pleerity_staging")
    if url_file:
        p = Path(url_file)
        if p.is_file():
            raw = p.read_text(encoding="utf-8").strip()
            for line in raw.splitlines():
                if line.startswith("MONGO_URL="):
                    return line.split("=", 1)[1].strip(), os.getenv("DB_NAME", "pleerity_staging")
            if raw.startswith("mongodb"):
                return raw, os.getenv("DB_NAME", "pleerity_staging")
    for key in ("STAGING_MONGO_URL", "MONGO_URL", "DATABASE_URL"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val, os.getenv("DB_NAME", "pleerity_staging")
    return None, None


def check_safety_guards(
    *,
    api_base: str,
    dry_run: bool,
    confirm_write: bool,
    mongo_url: Optional[str],
) -> Dict[str, Any]:
    host = api_base.replace("https://", "").replace("http://", "").split("/")[0].lower()
    env_ok = any(h in host for h in ALLOWED_API_HOSTS)
    mongo_ok = True
    mongo_note = "api_only_mode"
    if mongo_url:
        lower = mongo_url.lower()
        mongo_ok = not any(m in lower for m in FORBIDDEN_MONGO_HOST_MARKERS)
        mongo_note = "staging_mongo_configured" if mongo_ok else "production_mongo_rejected"
    write_allowed = (not dry_run) and confirm_write and env_ok and mongo_ok
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": FIXTURE_MARKER,
        "environment_guard": env_ok,
        "api_host": host,
        "dry_run": dry_run,
        "confirm_write": confirm_write,
        "write_allowed": write_allowed,
        "production_db_access": False,
        "real_customer_mutation": False,
        "staging_only": env_ok,
        "mongo_url_present": bool(mongo_url),
        "mongo_safety": mongo_note,
        "idempotency_marker": FIXTURE_MARKER,
        "cleanup_notes": "Archive or marker-tagged properties; satisfaction via authority sync + recalc queue",
        "audit_rows": "clients/properties/requirements/evidence/audit_logs tagged with fixture marker",
        "pass": env_ok and (dry_run or write_allowed or (not confirm_write and not dry_run)),
    }


def build_seed_plan() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": FIXTURE_MARKER,
        "fixtures": FIXTURE_PLAN,
        "pass": True,
    }


def read_admin_password() -> str:
    if os.environ.get("STAGING_ADMIN_PASSWORD"):
        return os.environ["STAGING_ADMIN_PASSWORD"].strip()
    p = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


class StagingApi:
    def __init__(self, api: str, pace: float = 5.0) -> None:
        self.api = api.rstrip("/")
        if not self.api.endswith("/api"):
            self.api = f"{self.api}/api"
        self.pace = pace

    def _sleep(self) -> None:
        time.sleep(self.pace)

    def admin_session(self) -> Tuple[str, str]:
        email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
        pw = read_admin_password()
        self._sleep()
        r = httpx.post(f"{self.api}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
        r.raise_for_status()
        t = r.json()["access_token"]
        self._sleep()
        su = httpx.post(
            f"{self.api}/auth/step-up/verify",
            headers={"Authorization": f"Bearer {t}"},
            json={"password": pw},
            timeout=90,
        )
        step = su.json().get("step_up_token", "") if su.status_code == 200 else ""
        return t, step

    def impersonate(self, admin_t: str, step: str, client_id: str, reason: str) -> str:
        headers = {"Authorization": f"Bearer {admin_t}"}
        if step:
            headers["X-Step-Up-Token"] = step
        self._sleep()
        r = httpx.post(
            f"{self.api}/admin/clients/{client_id}/impersonation/start",
            headers=headers,
            params={"ttl_minutes": 15},
            json={"reason": reason},
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["access_token"]

    def client_get(self, token: str, path: str) -> Dict[str, Any]:
        self._sleep()
        r = httpx.get(f"{self.api}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=120)
        if r.status_code != 200:
            return {"_error": r.status_code, "_text": r.text[:200]}
        return r.json()

    def client_post(self, token: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._sleep()
        r = httpx.post(
            f"{self.api}{path}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=300,
        )
        try:
            body = r.json()
        except Exception:
            body = {"text": r.text[:300]}
        return {"status": r.status_code, "body": body}

    def client_patch(self, token: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._sleep()
        r = httpx.patch(
            f"{self.api}{path}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=120,
        )
        try:
            body = r.json()
        except Exception:
            body = {"text": r.text[:300]}
        return {"status": r.status_code, "body": body}

    def probe(self, token: str) -> Dict[str, Any]:
        dash = self.client_get(token, "/client/dashboard")
        score = self.client_get(token, "/client/compliance-score")
        props = self.client_get(token, "/client/properties")
        today = self.client_get(token, "/today/items")
        ent = self.client_get(token, "/client/entitlements")
        properties = props.get("properties") or []
        active_properties = [p for p in properties if p.get("is_active", True) is not False]
        stats = score.get("stats") or dash.get("compliance_summary") or {}
        tasks = today.get("tasks") or {}
        urgent = list(tasks.get("urgent") or [])
        in_prog = list(tasks.get("in_progress") or [])
        total = int(stats.get("total_requirements") or 0)
        satisfied = int(stats.get("satisfied") or stats.get("compliant") or 0)
        jurisdictions: List[str] = []
        for p in properties:
            j = (p.get("jurisdiction") or "").strip()
            if j and j not in jurisdictions:
                jurisdictions.append(j)
        rag = {"GREEN": 0, "AMBER": 0, "RED": 0}
        for p in properties:
            st = (p.get("compliance_status") or "").upper()
            if st in rag:
                rag[st] += 1
        sc = score.get("score_confidence") or {}
        return {
            "score": score.get("score"),
            "property_count": len(active_properties),
            "jurisdictions": jurisdictions,
            "requirement_total": total,
            "requirement_satisfied": satisfied,
            "requirement_unsatisfied": max(0, total - satisfied),
            "overdue": int(stats.get("overdue") or 0),
            "property_rag": rag,
            "today_urgent_count": len(urgent),
            "today_in_progress_count": len(in_prog),
            "today_calm": len(urgent) == 0 and len(in_prog) == 0,
            "all_satisfied": total > 0 and satisfied >= total and int(stats.get("overdue") or 0) == 0,
            "properties_valid": rag["AMBER"] == 0 and rag["RED"] == 0,
            "score_confidence_present": bool(sc.get("headline")),
            "entitlements_plan": ent.get("plan"),
        }


def archive_surplus_properties(api: StagingApi, token: str, *, keep_property_id: str, marker: str) -> Dict[str, Any]:
    props = api.client_get(token, "/client/properties").get("properties") or []
    archived: List[Dict[str, Any]] = []
    for p in props:
        pid = p.get("property_id")
        if not pid or pid == keep_property_id:
            continue
        if p.get("is_active") is False:
            archived.append({"property_id": pid, "action": "already_archived"})
            continue
        res = api.client_patch(
            token,
            f"/properties/{pid}",
            {"is_active": False, "nickname": f"{marker}-archived-{pid[:8]}"},
        )
        archived.append({"property_id": pid, "status": res.get("status"), "action": "archived"})
    return {"archived": archived, "kept": keep_property_id, "pass": True}


def ensure_properties(
    api: StagingApi,
    token: str,
    *,
    target_count: int,
    marker: str,
    jurisdiction: str = "England",
    mixed_jurisdictions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    props = api.client_get(token, "/client/properties").get("properties") or []
    active = [p for p in props if p.get("is_active", True) is not False]
    created: List[Dict[str, Any]] = []
    jurisdictions = mixed_jurisdictions or [jurisdiction]
    idx = 0
    while len(active) + len(created) < target_count:
        j = jurisdictions[idx % len(jurisdictions)]
        payload = {
            "nickname": f"{marker}-prop-{len(active)+len(created)+1}",
            "address_line_1": f"{marker} Fixture Street {len(active)+len(created)+1}",
            "city": "Cardiff" if j == "Wales" else ("Edinburgh" if j == "Scotland" else "London"),
            "postcode": "CF10 1AA" if j == "Wales" else ("EH1 1AA" if j == "Scotland" else "SW1A 1AA"),
            "property_type": "residential",
            "number_of_units": 1,
            "jurisdiction": j,
        }
        res = api.client_post(token, "/properties/create", payload)
        created.append({"jurisdiction": j, "status": res.get("status"), "body": res.get("body")})
        if res.get("status") not in (200, 201):
            break
        idx += 1
    props = api.client_get(token, "/client/properties").get("properties") or []
    active = [p for p in props if p.get("is_active", True) is not False]
    patched: List[Dict[str, Any]] = []
    if mixed_jurisdictions and len(mixed_jurisdictions) > 1:
        for i, p in enumerate(active):
            j = jurisdictions[i % len(jurisdictions)]
            if (p.get("jurisdiction") or "") != j:
                res = api.client_patch(token, f"/properties/{p['property_id']}", {"jurisdiction": j})
                patched.append({"property_id": p["property_id"], "jurisdiction": j, "status": res.get("status")})
    sync_rows: List[Dict[str, Any]] = []
    for p in active:
        pid = p.get("property_id")
        if not pid:
            continue
        res = api.client_post(token, f"/properties/{pid}/requirements/sync", {})
        sync_rows.append({"property_id": pid, "status": res.get("status")})
    return {
        "target_count": target_count,
        "active_count": len(active),
        "created": created,
        "patched": patched,
        "sync": sync_rows,
        "pass": len(active) >= target_count,
    }


def satisfy_requirements_via_api(api: StagingApi, token: str, property_id: str, marker: str) -> Dict[str, Any]:
    reqs = api.client_get(token, f"/client/properties/{property_id}/requirements").get("requirements") or []
    rows: List[Dict[str, Any]] = []
    for req in reqs:
        if req.get("requirement_satisfied"):
            rows.append({"requirement_id": req.get("requirement_id"), "action": "already_satisfied"})
            continue
        rid = req.get("requirement_id")
        if not rid:
            continue
        meta = req.get("registry_metadata") or {}
        modes = ((meta.get("evidence_resolution") or {}).get("allowed_evidence_modes")) or []
        if modes and "STRUCTURED_DECLARATION" not in modes:
            rows.append(
                {
                    "requirement_id": rid,
                    "requirement_type": req.get("requirement_type"),
                    "action": "document_required_mongo_seed",
                }
            )
            continue
        payload = {
            "evidence_mode": "STRUCTURED_DECLARATION",
            "structured_declaration": {
                "declaration_statement": (
                    f"Governed staging fixture declaration ({marker}) — obligation recorded for plan outcome verification."
                ),
                "structured_fields": {"governed_fixture": True, "marker": marker},
            },
        }
        res = api.client_post(
            token,
            f"/client/properties/{property_id}/requirements/{rid}/compliance-evidence",
            payload,
        )
        rows.append(
            {
                "requirement_id": rid,
                "requirement_type": req.get("requirement_type"),
                "status": res.get("status"),
                "action": "structured_declaration",
            }
        )
    api.client_post(token, f"/properties/{property_id}/requirements/sync", {})
    return {"property_id": property_id, "rows": rows, "attempted": len(rows)}


async def satisfy_requirements_via_db(
    client_id: str,
    property_ids: List[str],
    marker: str,
) -> Dict[str, Any]:
    from database import database
    from models.core import DocumentStatus
    from services.requirement_evidence_authority import sync_requirement_evidence_authority
    from services.compliance_evidence_record_service import (
        create_compliance_evidence_record,
        effective_evidence_resolution,
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
    )
    from services.compliance_recalc_queue import enqueue_compliance_recalc, ACTOR_SYSTEM, TRIGGER_LAZY_BACKFILL

    await database.connect()
    db = database.get_db()
    now = datetime.now(timezone.utc)
    rows: List[Dict[str, Any]] = []
    for pid in property_ids:
        reqs = await db.requirements.find(
            {"client_id": client_id, "property_id": pid, "status": {"$nin": ["NOT_REQUIRED"]}},
            {"_id": 0},
        ).to_list(500)
        for req in reqs:
            from services.requirement_satisfaction_service import attach_satisfaction_fields, is_requirement_satisfied

            enriched = attach_satisfaction_fields(req)
            if is_requirement_satisfied(enriched):
                rows.append({"requirement_id": req.get("requirement_id"), "property_id": pid, "action": "already_satisfied"})
                continue
            rid = str(req["requirement_id"])
            policy = effective_evidence_resolution(req)
            modes = policy.get("allowed_evidence_modes") or []
            action = "skipped"
            try:
                if EVIDENCE_MODE_STRUCTURED_DECLARATION in modes:
                    from services.compliance_evidence_record_service import VERIFICATION_VERIFIED

                    await create_compliance_evidence_record(
                        db,
                        requirement=req,
                        evidence_mode=EVIDENCE_MODE_STRUCTURED_DECLARATION,
                        created_by_user_id="governed_fixture_seed",
                        evidence_payload={
                            "declaration_statement": f"Governed fixture ({marker})",
                            "structured_fields": {"governed_fixture": True, "marker": marker},
                        },
                        verification_status=VERIFICATION_VERIFIED,
                    )
                    action = "structured_declaration_service"
                else:
                    document_id = str(uuid.uuid4())
                    rtype = str(req.get("requirement_type") or "evidence")
                    expiry = (now + timedelta(days=365)).date().isoformat()
                    issue = (now - timedelta(days=30)).date().isoformat()
                    doc = {
                        "document_id": document_id,
                        "client_id": client_id,
                        "property_id": pid,
                        "evidence_scope_type": "PROPERTY",
                        "evidence_scope_id": pid,
                        "authoritative_property_id": pid,
                        "requirement_id": rid,
                        "file_name": f"{marker}_{rtype}.pdf",
                        "file_path": f"{client_id}/{marker}/{document_id}.pdf",
                        "file_size": 1024,
                        "mime_type": "application/pdf",
                        "status": DocumentStatus.VERIFIED.value,
                        "uploaded_by": "GOVERNED_FIXTURE_SEED",
                        "uploaded_at": now.isoformat(),
                        "document_type": rtype,
                        "source": "governed_fixture_seed",
                        "staging_verification_fixture": marker,
                        "evidence_review_state": "ACCEPTED_UNVERIFIED",
                        "assurance_tier": "HUMAN_ACCEPTED",
                        "evidence_satisfies_requirement": True,
                        "match_outcome": "MATCH_CONFIRMED",
                        "expiry_date": expiry,
                        "issue_date": issue,
                        "verified_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                    }
                    await db.documents.update_one({"document_id": document_id}, {"$set": doc}, upsert=True)
                    await sync_requirement_evidence_authority(db, rid, property_id_hint=pid)
                    action = "governed_document_seed"
                await db.audit_logs.insert_one(
                    {
                        "audit_id": str(uuid.uuid4()),
                        "action": "UPDATE",
                        "actor_id": "governed_fixture_seed",
                        "client_id": client_id,
                        "property_id": pid,
                        "resource_type": "requirement",
                        "resource_id": rid,
                        "event_type": "GOVERNED_FIXTURE_SEED",
                        "metadata": {"fixture_marker": marker, "action": action},
                        "timestamp": now,
                    }
                )
            except Exception as exc:
                action = f"error:{exc.__class__.__name__}"
            rows.append({"requirement_id": rid, "property_id": pid, "action": action})
        await enqueue_compliance_recalc(
            client_id,
            property_id=pid,
            trigger=TRIGGER_LAZY_BACKFILL,
            actor=ACTOR_SYSTEM,
            reason=f"{marker} governed fixture satisfaction",
        )
    return {"client_id": client_id, "rows": rows, "pass": bool(rows)}


def run_db_satisfy(client_id: str, property_ids: List[str], marker: str) -> Dict[str, Any]:
    return asyncio.run(satisfy_requirements_via_db(client_id, property_ids, marker))


def create_fixture(
    api: StagingApi,
    sid: str,
    spec: Dict[str, Any],
    *,
    dry_run: bool,
    write_allowed: bool,
    mongo_url: Optional[str],
) -> Dict[str, Any]:
    base = spec["base_client_id"]
    entry: Dict[str, Any] = {
        "scenario": sid,
        "base_client_id": base,
        "marker": FIXTURE_MARKER,
        "dry_run": dry_run,
        "actions": [],
    }
    if dry_run or not write_allowed:
        entry["status"] = "dry_run_or_blocked"
        entry["pass"] = False
        return entry

    admin_t, step = api.admin_session()
    token = api.impersonate(admin_t, step, base, f"{PROGRAMME} seed {sid}")
    entry_probe_before = api.probe(token)

    if sid == "A":
        keep = spec.get("keep_property_id")
        arch = archive_surplus_properties(api, token, keep_property_id=keep, marker=FIXTURE_MARKER)
        entry["actions"].append(arch)
        admin_t, step = api.admin_session()
        token = api.impersonate(admin_t, step, base, f"{PROGRAMME} verify {sid}")
        entry_probe_after = api.probe(token)
        entry["probe_before"] = entry_probe_before
        entry["probe_after"] = entry_probe_after
        entry["client_id"] = base
        entry["pass"] = (
            entry_probe_after.get("property_count") == 1
            and entry_probe_after.get("all_satisfied")
            and entry_probe_after.get("today_calm")
        )
        entry["status"] = "seeded" if entry["pass"] else "partial"
        return entry

    prop_result = None
    if "ensure_property_count" in spec.get("actions", []) or sid in ("D", "E", "G"):
        target = int(spec.get("property_count") or 5)
        mixed = spec.get("mixed_jurisdiction")
        jurs = spec.get("jurisdictions") or ["England"]
        prop_result = ensure_properties(
            api,
            token,
            target_count=target,
            marker=FIXTURE_MARKER,
            jurisdiction=jurs[0],
            mixed_jurisdictions=jurs if mixed else None,
        )
        entry["actions"].append(prop_result)

    admin_t, step = api.admin_session()
    token = api.impersonate(admin_t, step, base, f"{PROGRAMME} satisfy {sid}")
    props = api.client_get(token, "/client/properties").get("properties") or []
    active_ids = [p["property_id"] for p in props if p.get("is_active", True) is not False and p.get("property_id")]

    sat_rows: List[Dict[str, Any]] = []
    if mongo_url:
        os.environ["MONGO_URL"] = mongo_url
        sat_rows.append(run_db_satisfy(base, active_ids, FIXTURE_MARKER))
    else:
        for pid in active_ids:
            sat_rows.append(satisfy_requirements_via_api(api, token, pid, FIXTURE_MARKER))
    entry["actions"].append({"satisfaction": sat_rows})

    admin_t, step = api.admin_session()
    token = api.impersonate(admin_t, step, base, f"{PROGRAMME} final probe {sid}")
    entry_probe_after = api.probe(token)
    entry["probe_after"] = entry_probe_after
    entry["client_id"] = base
    entry["pass"] = bool(entry_probe_after.get("all_satisfied") and entry_probe_after.get("today_calm"))
    entry["status"] = "seeded" if entry["pass"] else "partial"
    return entry


def write_registry_override(results: Dict[str, Dict[str, Any]]) -> None:
    fixtures = {}
    for sid, row in results.items():
        if row.get("client_id"):
            fixtures[sid] = {
                "client_id": row["client_id"],
                "marker": FIXTURE_MARKER,
                "seeded_at": utc(),
                "pass": row.get("pass"),
            }
    payload = {"programme": PROGRAMME, "generated_at": utc(), "marker": FIXTURE_MARKER, "fixtures": fixtures}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "governed_fixture_registry_runtime.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
