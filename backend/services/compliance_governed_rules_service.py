"""
Governed, versioned compliance rule definitions (admin-managed) with publish/rollback.

Engine (generation, scoring formulas, workflows) stays in code. Editable *data* lives in Mongo:
- ``compliance_governed_rule_versions``: immutable version documents + governance metadata.
- Publish syncs the active payload into ``requirement_rules`` (``governed=true``) for provisioning.

No arbitrary expressions: applicability uses a fixed set of boolean/list predicates only.
"""
from __future__ import annotations

import copy
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from models import AuditAction, PropertyTypeApplicability, RequirementStatus, RuleCategory
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

COL_VERSIONS = "compliance_governed_rule_versions"

# Lifecycle: draft → pending approval → approved → published (supersedes prior published)
STATUS_DRAFT = "DRAFT"
STATUS_PENDING_APPROVAL = "PENDING_APPROVAL"
STATUS_APPROVED = "APPROVED"
STATUS_PUBLISHED = "PUBLISHED"
STATUS_SUPERSEDED = "SUPERSEDED"
STATUS_ARCHIVED = "ARCHIVED"

REQUIREMENT_CLASS_VALUES = frozenset({"DOCUMENT", "JOB", "OBLIGATION", "SYSTEM"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_upper(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def _bool_match(cond: Optional[bool], actual: Optional[bool]) -> bool:
    """None condition = wildcard."""
    if cond is None:
        return True
    if actual is None:
        return False
    return bool(cond) == bool(actual)


def property_matches_governed_applicability(
    property_doc: Dict[str, Any],
    conditions: Optional[Dict[str, Any]],
) -> bool:
    """
    Evaluate fixed applicability predicates against a property document.
    ``conditions`` may be None or empty = match all properties (subject to jurisdictions elsewhere).
    Supported keys: is_hmo, has_gas_supply, tenancy_active, furnished (bool | null);
    local_authority_in: non-empty list of uppercase tokens → property.local_authority must be in set.
    """
    if not conditions:
        return True

    def _pb(key: str, default: Optional[bool] = None) -> Optional[bool]:
        v = property_doc.get(key)
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        s = str(v).strip().upper()
        if s in ("YES", "TRUE", "1"):
            return True
        if s in ("NO", "FALSE", "0", ""):
            return False
        return bool(v)

    if "is_hmo" in conditions and conditions["is_hmo"] is not None:
        pt = (property_doc.get("property_type") or "").strip().upper()
        is_hmo = bool(property_doc.get("is_hmo")) or pt == "HMO"
        if not _bool_match(bool(conditions["is_hmo"]), is_hmo):
            return False

    if "has_gas_supply" in conditions and conditions["has_gas_supply"] is not None:
        has_gas = _pb("has_gas_supply", True)
        if has_gas is None:
            has_gas = True
        if not _bool_match(bool(conditions["has_gas_supply"]), has_gas):
            return False

    if "tenancy_active" in conditions and conditions["tenancy_active"] is not None:
        ta = _pb("tenancy_active", None)
        if not _bool_match(bool(conditions["tenancy_active"]), ta):
            return False

    if "furnished" in conditions and conditions["furnished"] is not None:
        fu = _pb("furnished", None)
        if not _bool_match(bool(conditions["furnished"]), fu):
            return False

    la_list = conditions.get("local_authority_in")
    if la_list:
        if not isinstance(la_list, (list, tuple)):
            la_list = [la_list]
        allowed = {_norm_upper(x) for x in la_list if x}
        prop_la = _norm_upper(property_doc.get("local_authority"))
        if allowed and prop_la not in allowed:
            return False

    return True


def _default_payload(rule_type: str) -> Dict[str, Any]:
    rt = (rule_type or "").strip().lower()
    return {
        "title": rt.replace("_", " ").title(),
        "description": "",
        "jurisdictions": None,
        "frequency_days": 365,
        "warning_days": 30,
        "compliance_requirement_class": "DOCUMENT",
        "risk_weight": 3,
        "client_surface_visible": None,
        "is_mandatory": True,
        "category": RuleCategory.OTHER.value,
        "applicable_to": PropertyTypeApplicability.ALL.value,
        "applicability_conditions": {},
        "regulatory_reference": None,
        # Lifecycle (payload mirrors runtime row; publish copies into requirement_rules)
        "is_active": True,
        "deprecated": False,
        "effective_from": None,
        "effective_to": None,
    }


def _validate_payload(payload: Dict[str, Any]) -> None:
    cls_ = (payload.get("compliance_requirement_class") or "DOCUMENT").strip().upper()
    if cls_ not in REQUIREMENT_CLASS_VALUES:
        raise ValueError(f"compliance_requirement_class must be one of {sorted(REQUIREMENT_CLASS_VALUES)}")
    rw = int(payload.get("risk_weight", 3))
    if rw < 1 or rw > 5:
        raise ValueError("risk_weight must be 1–5")
    freq = int(payload.get("frequency_days", 365))
    if freq < 1 or freq > 36500:
        raise ValueError("frequency_days out of allowed range")
    warn = int(payload.get("warning_days", 30))
    if warn < 0 or warn > 3650:
        raise ValueError("warning_days out of allowed range")
    cond = payload.get("applicability_conditions")
    if cond is not None and not isinstance(cond, dict):
        raise ValueError("applicability_conditions must be an object")
    allowed_cond_keys = {"is_hmo", "has_gas_supply", "tenancy_active", "furnished", "local_authority_in"}
    if cond:
        for k in cond:
            if k not in allowed_cond_keys:
                raise ValueError(f"Unknown applicability key: {k}")

    if "is_active" in payload and not isinstance(payload["is_active"], bool):
        raise ValueError("is_active must be a boolean")
    if "deprecated" in payload and not isinstance(payload["deprecated"], bool):
        raise ValueError("deprecated must be a boolean")
    for ek in ("effective_from", "effective_to"):
        v = payload.get(ek)
        if v is not None and (not isinstance(v, str) or not str(v).strip()):
            raise ValueError(f"{ek} must be a non-empty ISO-8601 string or null")
    eff_a = payload.get("effective_from")
    eff_b = payload.get("effective_to")
    for ek, ev in (("effective_from", eff_a), ("effective_to", eff_b)):
        if ev:
            try:
                datetime.fromisoformat(str(ev).replace("Z", "+00:00"))
            except ValueError as ex:
                raise ValueError(f"{ek} must be a valid ISO-8601 timestamp") from ex
    if eff_a and eff_b:
        ta = datetime.fromisoformat(str(eff_a).replace("Z", "+00:00"))
        tb = datetime.fromisoformat(str(eff_b).replace("Z", "+00:00"))
        if ta > tb:
            raise ValueError("effective_from must be before or equal to effective_to")


async def _next_version_seq(db, rule_type: str) -> int:
    last = await db[COL_VERSIONS].find_one(
        {"rule_type": rule_type},
        sort=[("version_seq", -1)],
        projection={"version_seq": 1},
    )
    return int((last or {}).get("version_seq") or 0) + 1


def payload_to_requirement_rule_row(
    rule_type: str,
    version_id: str,
    version_seq: int,
    payload: Dict[str, Any],
    *,
    governed_effective_from_iso: Optional[str] = None,
) -> Dict[str, Any]:
    """Map governed payload to ``requirement_rules`` document shape."""
    jurisdictions = payload.get("jurisdictions")
    if jurisdictions is not None and not isinstance(jurisdictions, list):
        jurisdictions = [jurisdictions]
    csv = payload.get("client_surface_visible")
    cls_ = (payload.get("compliance_requirement_class") or "DOCUMENT").strip().upper()
    if csv is None:
        csv = cls_ != "SYSTEM"
    eff_from_row = governed_effective_from_iso or payload.get("effective_from")
    eff_to_row = payload.get("effective_to")
    is_active = bool(payload.get("is_active", True))
    deprecated = bool(payload.get("deprecated", False))
    return {
        "rule_id": str(uuid.uuid4()),
        "rule_type": rule_type.strip().lower(),
        "name": payload.get("title") or rule_type,
        "description": payload.get("description") or "",
        "category": payload.get("category") or RuleCategory.OTHER.value,
        "frequency_days": int(payload.get("frequency_days", 365)),
        "warning_days": int(payload.get("warning_days", 30)),
        "applicable_to": payload.get("applicable_to") or PropertyTypeApplicability.ALL.value,
        "is_mandatory": bool(payload.get("is_mandatory", True)),
        "is_active": is_active,
        "risk_weight": int(payload.get("risk_weight", 3)),
        "regulatory_reference": payload.get("regulatory_reference"),
        "notes": payload.get("notes"),
        "jurisdictions": jurisdictions,
        "governed": True,
        "governed_version_id": version_id,
        "governed_version_seq": version_seq,
        "compliance_requirement_class": cls_,
        "client_surface_visible": csv,
        "governed_applicability": payload.get("applicability_conditions") or {},
        "governed_deprecated": deprecated,
        "governed_effective_from": eff_from_row,
        "governed_effective_to": eff_to_row,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "created_by": "GOVERNED_RULES",
    }


async def create_draft(
    rule_type: str,
    actor: Dict[str, Any],
    *,
    clone_from_version_id: Optional[str] = None,
    initial_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    rt = rule_type.strip().lower()
    if not rt:
        raise ValueError("rule_type required")

    payload: Dict[str, Any]
    if clone_from_version_id:
        src = await db[COL_VERSIONS].find_one({"version_id": clone_from_version_id}, {"_id": 0})
        if not src:
            raise ValueError("Source version not found")
        payload = copy.deepcopy(src.get("payload") or {})
    elif initial_payload:
        payload = copy.deepcopy(initial_payload)
    else:
        published = await db[COL_VERSIONS].find_one(
            {"rule_type": rt, "status": STATUS_PUBLISHED},
            {"_id": 0, "payload": 1},
            sort=[("version_seq", -1)],
        )
        payload = copy.deepcopy((published or {}).get("payload") or _default_payload(rt))

    _validate_payload(payload)

    version_id = str(uuid.uuid4())
    version_seq = await _next_version_seq(db, rt)
    doc = {
        "version_id": version_id,
        "rule_type": rt,
        "version_seq": version_seq,
        "status": STATUS_DRAFT,
        "payload": payload,
        "change_reason": None,
        "effective_from": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "created_by": actor.get("portal_user_id"),
        "submitted_at": None,
        "submitted_by": None,
        "approved_at": None,
        "approved_by": None,
        "published_at": None,
        "published_by": None,
        "supersedes_version_id": None,
        "effective_to": None,
    }
    await db[COL_VERSIONS].insert_one(doc)
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=actor.get("portal_user_id"),
        metadata={"action": "governed_rule_draft_created", "version_id": version_id, "rule_type": rt},
    )
    doc.pop("_id", None)
    return doc


async def update_draft(version_id: str, actor: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    db = database.get_db()
    cur = await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})
    if not cur:
        raise ValueError("Version not found")
    if cur.get("status") != STATUS_DRAFT:
        raise ValueError("Only DRAFT versions can be edited")

    if patch.get("rule_type") is not None:
        raise ValueError("rule_type is immutable for a version document")
    pl0 = patch.get("payload")
    if isinstance(pl0, dict) and pl0.get("rule_type") is not None:
        raise ValueError("payload.rule_type is immutable; create a new governed rule for a new requirement code")

    payload = copy.deepcopy(cur.get("payload") or {})
    if "payload" in patch and isinstance(patch["payload"], dict):
        payload.update(patch["payload"])
    new_reason = patch["change_reason"] if "change_reason" in patch else cur.get("change_reason")
    new_eff = patch["effective_from"] if "effective_from" in patch else cur.get("effective_from")

    _validate_payload(payload)
    await db[COL_VERSIONS].update_one(
        {"version_id": version_id},
        {
            "$set": {
                "payload": payload,
                "change_reason": new_reason,
                "effective_from": new_eff,
                "updated_at": _now_iso(),
            }
        },
    )
    out = await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=actor.get("portal_user_id"),
        metadata={"action": "governed_rule_draft_updated", "version_id": version_id},
    )
    return out


async def submit_for_approval(version_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    db = database.get_db()
    cur = await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})
    if not cur or cur.get("status") != STATUS_DRAFT:
        raise ValueError("Only DRAFT can be submitted")
    if not (cur.get("change_reason") or "").strip():
        raise ValueError("change_reason is required before submit")

    await db[COL_VERSIONS].update_one(
        {"version_id": version_id},
        {
            "$set": {
                "status": STATUS_PENDING_APPROVAL,
                "submitted_at": _now_iso(),
                "submitted_by": actor.get("portal_user_id"),
                "updated_at": _now_iso(),
            }
        },
    )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=actor.get("portal_user_id"),
        metadata={"action": "governed_rule_submitted", "version_id": version_id},
    )
    return await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})


async def approve_version(version_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    db = database.get_db()
    cur = await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})
    if not cur or cur.get("status") != STATUS_PENDING_APPROVAL:
        raise ValueError("Only PENDING_APPROVAL can be approved")

    await db[COL_VERSIONS].update_one(
        {"version_id": version_id},
        {
            "$set": {
                "status": STATUS_APPROVED,
                "approved_at": _now_iso(),
                "approved_by": actor.get("portal_user_id"),
                "updated_at": _now_iso(),
            }
        },
    )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=actor.get("portal_user_id"),
        metadata={"action": "governed_rule_approved", "version_id": version_id},
    )
    return await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})


async def reconcile_obsolete_governed_db_rule_requirements(
    rule_type: str,
    rule_row: Dict[str, Any],
    *,
    actor_id: Optional[str] = None,
    enqueue_recalc: bool = True,
    recalc_max_enqueues: int = 5000,
) -> Dict[str, Any]:
    """
    Soft-retire ``requirements`` rows sourced from governed ``requirement_rules`` when the
    published rule no longer covers the property (jurisdiction, applicability, lifecycle window,
    inactive, or deprecated). Never deletes rows; preserves evidence-bearing rows.
    """
    from services.compliance_rules_registry import governed_requirement_rule_covers_property
    from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE

    if not rule_row.get("governed"):
        return {"reconciled": 0, "skipped": 0, "recalc_enqueued": 0}

    db = database.get_db()
    rt = rule_type.strip().lower()
    reconciled = 0
    skipped = 0
    enq = 0
    now = datetime.now(timezone.utc)

    cursor = db.requirements.find(
        {
            "requirement_type": rt,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        },
        {"_id": 0},
    )
    async for row in cursor:
        if row.get("evidence_doc_id"):
            skipped += 1
            continue
        st = (row.get("status") or "").upper()
        if st in ("COMPLIANT", "VERIFIED"):
            skipped += 1
            continue
        prop = await db.properties.find_one({"property_id": row.get("property_id")}, {"_id": 0})
        if not prop:
            skipped += 1
            continue
        client = await db.clients.find_one({"client_id": row.get("client_id")}, {"_id": 0, "default_jurisdiction": 1}) or {}
        ptype = (prop.get("property_type") or "residential").upper()
        if governed_requirement_rule_covers_property(rule_row, ptype, prop, client):
            continue

        if (row.get("applicability") or "").upper() == "NOT_REQUIRED" and row.get("not_required_reason"):
            meta0 = row.get("registry_metadata") or {}
            if meta0.get("governed_reconciled"):
                skipped += 1
                continue

        await db.requirements.update_one(
            {"requirement_id": row.get("requirement_id")},
            {
                "$set": {
                    "applicability": "NOT_REQUIRED",
                    "status": RequirementStatus.NOT_REQUIRED.value,
                    "not_required_reason": "not_applicable",
                    "is_tracked": False,
                    "client_surface_visible": False,
                    "requires_document": False,
                    "requires_job": False,
                    "updated_at": now.isoformat(),
                    "registry_metadata": {
                        **(row.get("registry_metadata") or {}),
                        "governed_reconciled": True,
                        "governed_reconciled_at": now.isoformat(),
                    },
                }
            },
        )
        reconciled += 1
        if enqueue_recalc and enq < recalc_max_enqueues:
            try:
                from services.compliance_recalc_queue import (
                    ACTOR_SYSTEM,
                    TRIGGER_PROPERTY_UPDATED,
                )
                from services.compliance_recalc_lifecycle_transition import (
                    enqueue_governed_compliance_recalc as enqueue_compliance_recalc,
                )

                await enqueue_compliance_recalc(
                    property_id=row["property_id"],
                    client_id=row["client_id"],
                    trigger_reason=TRIGGER_PROPERTY_UPDATED,
                    actor_type=ACTOR_SYSTEM,
                    actor_id=None,
                    correlation_id=f"GOVERNED_RULE_RECONCILE:{rt}:{row['property_id']}",
                )
                enq += 1
            except Exception as ex:
                logger.warning("reconcile enqueue skip property_id=%s: %s", row.get("property_id"), ex)

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=actor_id,
        metadata={
            "action": "governed_rule_requirements_reconciled",
            "rule_type": rt,
            "reconciled": reconciled,
            "skipped": skipped,
        },
    )
    return {"reconciled": reconciled, "skipped": skipped, "recalc_enqueued": enq}


async def _collect_publish_property_targets(
    db,
    rule_type: str,
    jurisdictions: Optional[Any],
    *,
    recalc_max_properties: int,
) -> List[Dict[str, Any]]:
    """Union of properties matching jurisdiction filter and properties with DB-rule rows for this type."""
    pairs: List[Dict[str, Any]] = []
    seen: set = set()
    max_total = max(1, int(recalc_max_properties)) * 2

    q: Dict[str, Any] = {"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]}
    jurs = jurisdictions
    if jurs:
        if not isinstance(jurs, list):
            jurs = [jurs]
        q["jurisdiction"] = {"$in": [str(j) for j in jurs if j]}
    cursor = db.properties.find(q, {"property_id": 1, "client_id": 1}).limit(recalc_max_properties)
    async for p in cursor:
        if len(pairs) >= max_total:
            break
        key = (p.get("client_id"), p.get("property_id"))
        if key[0] and key[1] and key not in seen:
            seen.add(key)
            pairs.append({"client_id": key[0], "property_id": key[1]})

    from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE

    rt = rule_type.strip().lower()
    req_cursor = db.requirements.find(
        {"requirement_type": rt, "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE},
        {"client_id": 1, "property_id": 1, "_id": 0},
    ).limit(recalc_max_properties)
    async for r in req_cursor:
        if len(pairs) >= max_total:
            break
        key = (r.get("client_id"), r.get("property_id"))
        if key[0] and key[1] and key not in seen:
            seen.add(key)
            pairs.append({"client_id": key[0], "property_id": key[1]})

    return pairs


async def publish_version(
    version_id: str,
    actor: Dict[str, Any],
    *,
    enqueue_property_recalc: bool = True,
    recalc_max_properties: int = 2000,
) -> Dict[str, Any]:
    """Publish APPROVED version: sync requirement_rules, supersede prior published, optional recalc queue."""
    db = database.get_db()
    cur = await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})
    if not cur or cur.get("status") != STATUS_APPROVED:
        raise ValueError("Only APPROVED versions can be published")

    rt = cur["rule_type"]
    payload = cur["payload"]
    version_seq = int(cur["version_seq"])

    prev_latest = await db[COL_VERSIONS].find_one(
        {"rule_type": rt, "status": STATUS_PUBLISHED},
        {"_id": 0, "version_id": 1},
        sort=[("version_seq", -1)],
    )
    now = _now_iso()
    await db[COL_VERSIONS].update_many(
        {"rule_type": rt, "status": STATUS_PUBLISHED},
        {"$set": {"status": STATUS_SUPERSEDED, "updated_at": now, "effective_to": now}},
    )

    eff_publish = cur.get("effective_from") or now
    row = payload_to_requirement_rule_row(
        rt, version_id, version_seq, payload, governed_effective_from_iso=eff_publish
    )
    existing = await db.requirement_rules.find_one({"rule_type": rt, "governed": True})
    if existing:
        rid = existing["rule_id"]
        row["rule_id"] = rid
        row["created_at"] = existing.get("created_at", row["created_at"])
        await db.requirement_rules.replace_one({"rule_id": rid}, row)
    else:
        ungoverned = await db.requirement_rules.find_one({"rule_type": rt, "governed": {"$ne": True}})
        if ungoverned:
            raise ValueError(
                f"rule_type {rt} already exists as non-governed requirement_rules row; resolve manually"
            )
        await db.requirement_rules.insert_one(row)

    await db[COL_VERSIONS].update_one(
        {"version_id": version_id},
        {
            "$set": {
                "status": STATUS_PUBLISHED,
                "published_at": now,
                "published_by": actor.get("portal_user_id"),
                "effective_from": eff_publish,
                "supersedes_version_id": (prev_latest or {}).get("version_id"),
                "updated_at": now,
            }
        },
    )

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=actor.get("portal_user_id"),
        metadata={
            "action": "governed_rule_published",
            "version_id": version_id,
            "rule_type": rt,
            "version_seq": version_seq,
        },
    )

    affected_estimate = 0
    enqueued = 0
    rematerialized = 0
    reconcile_stats: Dict[str, Any] = {"reconciled": 0, "skipped": 0, "recalc_enqueued": 0}
    if enqueue_property_recalc:
        from services.compliance_recalc_queue import (
            ACTOR_SYSTEM,
            TRIGGER_PROPERTY_UPDATED,
        )
        from services.compliance_recalc_lifecycle_transition import (
            enqueue_governed_compliance_recalc as enqueue_compliance_recalc,
        )
        from services.provisioning import provisioning_service

        targets = await _collect_publish_property_targets(
            db, rt, payload.get("jurisdictions"), recalc_max_properties=recalc_max_properties
        )
        affected_estimate = len(targets)
        for p in targets:
            try:
                await provisioning_service._generate_requirements(p["client_id"], p["property_id"])
                rematerialized += 1
            except Exception as ex:
                logger.warning("generate_requirements skip property_id=%s: %s", p.get("property_id"), ex)
            try:
                await enqueue_compliance_recalc(
                    property_id=p["property_id"],
                    client_id=p["client_id"],
                    trigger_reason=TRIGGER_PROPERTY_UPDATED,
                    actor_type=ACTOR_SYSTEM,
                    actor_id=None,
                    correlation_id=f"GOVERNED_RULE_PUBLISH:{version_id}:{p['property_id']}",
                )
                enqueued += 1
            except Exception as ex:
                logger.warning("enqueue recalc skip property_id=%s: %s", p.get("property_id"), ex)

        reconcile_stats = await reconcile_obsolete_governed_db_rule_requirements(
            rt, row, actor_id=actor.get("portal_user_id"), enqueue_recalc=True
        )
        enqueued += int(reconcile_stats.get("recalc_enqueued") or 0)

    return {
        "version_id": version_id,
        "rule_type": rt,
        "status": STATUS_PUBLISHED,
        "requirement_rule_id": row["rule_id"],
        "affected_properties_estimate": affected_estimate,
        "properties_regenerated": rematerialized,
        "properties_rematerialized": rematerialized,
        "recalc_jobs_enqueued": enqueued,
        "governed_requirements_reconciled": reconcile_stats.get("reconciled", 0),
        "governed_reconcile_skipped": reconcile_stats.get("skipped", 0),
    }


async def rollback_published(rule_type: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Point ``requirement_rules`` back at the prior version's payload (by version_seq)."""
    db = database.get_db()
    rt = rule_type.strip().lower()
    current = await db[COL_VERSIONS].find_one(
        {"rule_type": rt, "status": STATUS_PUBLISHED},
        {"_id": 0},
        sort=[("version_seq", -1)],
    )
    if not current:
        raise ValueError("Nothing published for this rule_type")

    target = await db[COL_VERSIONS].find_one(
        {"rule_type": rt, "version_seq": {"$lt": current["version_seq"]}},
        {"_id": 0},
        sort=[("version_seq", -1)],
    )
    if not target:
        raise ValueError("No prior version to roll back to")

    rb_now = _now_iso()
    await db[COL_VERSIONS].update_one(
        {"version_id": current["version_id"]},
        {"$set": {"status": STATUS_SUPERSEDED, "updated_at": rb_now, "effective_to": rb_now}},
    )
    payload = target.get("payload") or {}
    _validate_payload(payload)
    tvid = target["version_id"]
    tseq = int(target["version_seq"])
    eff_restore = target.get("effective_from") or rb_now
    row = payload_to_requirement_rule_row(
        rt, tvid, tseq, payload, governed_effective_from_iso=eff_restore
    )
    existing = await db.requirement_rules.find_one({"rule_type": rt, "governed": True})
    if existing:
        row["rule_id"] = existing["rule_id"]
        row["created_at"] = existing.get("created_at", row["created_at"])
        await db.requirement_rules.replace_one({"rule_id": existing["rule_id"]}, row)

    await db[COL_VERSIONS].update_one(
        {"version_id": tvid},
        {
            "$set": {
                "status": STATUS_PUBLISHED,
                "published_at": rb_now,
                "published_by": actor.get("portal_user_id"),
                "updated_at": rb_now,
            }
        },
    )

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=actor.get("portal_user_id"),
        metadata={"action": "governed_rule_rollback", "rule_type": rt, "restored_version_id": tvid},
    )

    affected_estimate = 0
    enqueued = 0
    rematerialized = 0
    reconcile_stats: Dict[str, Any] = {"reconciled": 0, "skipped": 0, "recalc_enqueued": 0}
    from services.compliance_recalc_queue import (
        ACTOR_SYSTEM,
        TRIGGER_PROPERTY_UPDATED,
    )
    from services.compliance_recalc_lifecycle_transition import (
        enqueue_governed_compliance_recalc as enqueue_compliance_recalc,
    )
    from services.provisioning import provisioning_service

    targets = await _collect_publish_property_targets(
        db, rt, payload.get("jurisdictions"), recalc_max_properties=2000
    )
    affected_estimate = len(targets)
    for p in targets:
        try:
            await provisioning_service._generate_requirements(p["client_id"], p["property_id"])
            rematerialized += 1
        except Exception as ex:
            logger.warning("rollback generate_requirements skip property_id=%s: %s", p.get("property_id"), ex)
        try:
            await enqueue_compliance_recalc(
                property_id=p["property_id"],
                client_id=p["client_id"],
                trigger_reason=TRIGGER_PROPERTY_UPDATED,
                actor_type=ACTOR_SYSTEM,
                actor_id=None,
                correlation_id=f"GOVERNED_RULE_ROLLBACK:{tvid}:{p['property_id']}",
            )
            enqueued += 1
        except Exception as ex:
            logger.warning("rollback enqueue skip property_id=%s: %s", p.get("property_id"), ex)

    reconcile_stats = await reconcile_obsolete_governed_db_rule_requirements(
        rt, row, actor_id=actor.get("portal_user_id"), enqueue_recalc=True
    )
    enqueued += int(reconcile_stats.get("recalc_enqueued") or 0)

    return {
        "version_id": tvid,
        "rule_type": rt,
        "status": STATUS_PUBLISHED,
        "requirement_rule_id": row.get("rule_id"),
        "affected_properties_estimate": affected_estimate,
        "properties_regenerated": rematerialized,
        "properties_rematerialized": rematerialized,
        "recalc_jobs_enqueued": enqueued,
        "governed_requirements_reconciled": reconcile_stats.get("reconciled", 0),
        "governed_reconcile_skipped": reconcile_stats.get("skipped", 0),
    }


async def preview_publish_impact(version_id: str) -> Dict[str, Any]:
    """Read-only impact summary for staging (no writes)."""
    db = database.get_db()
    cur = await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})
    if not cur:
        raise ValueError("Version not found")
    payload = cur.get("payload") or {}
    rt = cur["rule_type"]
    jurs = payload.get("jurisdictions")
    if jurs and not isinstance(jurs, list):
        jurs = [jurs]

    prev_pub = await db[COL_VERSIONS].find_one(
        {"rule_type": rt, "status": STATUS_PUBLISHED},
        {"_id": 0, "payload": 1, "version_id": 1, "version_seq": 1},
        sort=[("version_seq", -1)],
    )
    if prev_pub and prev_pub.get("version_id") == version_id:
        prev_pub = await db[COL_VERSIONS].find_one(
            {"rule_type": rt, "status": STATUS_SUPERSEDED},
            {"_id": 0, "payload": 1, "version_id": 1, "version_seq": 1},
            sort=[("version_seq", -1)],
        )

    q: Dict[str, Any] = {"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]}
    if jurs:
        q["jurisdiction"] = {"$in": [str(j) for j in jurs if j]}
    prop_count = await db.properties.count_documents(q)

    diff_keys: set = set()
    if prev_pub:
        oldp = prev_pub.get("payload") or {}
        for k in set(oldp.keys()) | set(payload.keys()):
            if oldp.get(k) != payload.get(k):
                diff_keys.add(k)

    return {
        "rule_type": rt,
        "version_id": version_id,
        "version_seq": cur.get("version_seq"),
        "status": cur.get("status"),
        "affected_jurisdictions": jurs or ["ALL (no jurisdiction filter on properties query)"],
        "matching_active_property_count": prop_count,
        "payload_field_changes_vs_latest_published": sorted(diff_keys),
        "portal_visibility_note": "client_surface_visible on governed row flows to materialised requirements when DB rule arm applies.",
        "previous_published_version_id": (prev_pub or {}).get("version_id"),
    }


async def list_versions(rule_type: Optional[str], limit: int = 50) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {}
    if rule_type:
        q["rule_type"] = rule_type.strip().lower()
    cur = db[COL_VERSIONS].find(q, {"_id": 0}).sort([("rule_type", 1), ("version_seq", -1)]).limit(limit)
    return await cur.to_list(limit)


async def get_version(version_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})


async def runtime_row_diff(version_id: str) -> Dict[str, Any]:
    """Compare payload-derived ``requirement_rules`` shape vs current governed row in Mongo (read-only)."""
    db = database.get_db()
    cur = await db[COL_VERSIONS].find_one({"version_id": version_id}, {"_id": 0})
    if not cur:
        raise ValueError("Version not found")
    rt = cur["rule_type"]
    payload = cur.get("payload") or {}
    eff_prev = cur.get("effective_from") or _now_iso()
    synthetic = payload_to_requirement_rule_row(
        rt, version_id, int(cur.get("version_seq", 0)), payload, governed_effective_from_iso=eff_prev
    )
    keys = (
        "name",
        "description",
        "frequency_days",
        "warning_days",
        "jurisdictions",
        "compliance_requirement_class",
        "client_surface_visible",
        "risk_weight",
        "governed_applicability",
        "applicable_to",
        "is_active",
        "governed_deprecated",
        "governed_effective_from",
        "governed_effective_to",
    )
    live = await db.requirement_rules.find_one({"rule_type": rt, "governed": True}, {"_id": 0})
    differences = []
    if not live:
        return {
            "rule_type": rt,
            "version_id": version_id,
            "live_row_exists": False,
            "synthetic_preview": {k: synthetic.get(k) for k in keys},
            "field_differences": [],
        }
    for k in keys:
        if synthetic.get(k) != live.get(k):
            differences.append({"field": k, "from_version": synthetic.get(k), "in_requirement_rules": live.get(k)})
    return {
        "rule_type": rt,
        "version_id": version_id,
        "live_row_exists": True,
        "live_governed_version_id": live.get("governed_version_id"),
        "field_differences": differences,
    }
