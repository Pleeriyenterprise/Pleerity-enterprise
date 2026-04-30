"""
PR4: Tenant-scoped idempotent policy backfill and gap reconciliation.

Safety controls:
- tenant-scoped only execution
- batch-size caps
- retry with backoff
- resumable checkpoints
- dead-letter tracking
- max writes/sec guard
- progress metrics per tenant
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

from services.compliance_gap_engine import infer_compliance_gaps_for_requirement
from services.policy_field_normalizer import resolve_policy_facts
from services.portfolio_risk_policy import POLICY_CLASSIFICATION_VERSION
from services.requirement_evidence_authority import normalized_evidence_state_for_policy

CHECKPOINT_COLLECTION = "compliance_policy_backfill_checkpoints"
DEAD_LETTER_COLLECTION = "compliance_policy_backfill_dead_letters"
JOB_REQUIREMENT_FIELDS = "requirement_policy_fields"
JOB_GAP_RECONCILIATION = "gap_policy_reconciliation"

MAX_BATCH_SIZE_CAP = 500
DEFAULT_BATCH_SIZE = 200
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_WRITES_PER_SEC = 50.0
DEFAULT_MAX_TENANTS_PER_RUN = 100
PR5_REQ_COVERAGE_GATE_PERCENT = 99.0
PR5_GAP_COVERAGE_GATE_PERCENT = 99.5


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _col(db: Any, name: str) -> Any:
    c = getattr(db, name, None)
    return c if c is not None else db[name]


def _batch_size(n: int) -> int:
    n = int(n or DEFAULT_BATCH_SIZE)
    if n < 1:
        n = 1
    return min(n, MAX_BATCH_SIZE_CAP)


def _policy_defaults_for_requirement(requirement: Dict[str, Any]) -> Dict[str, Any]:
    cls = str(requirement.get("compliance_requirement_class") or "").upper()
    return {
        "is_mandatory": cls in ("DOCUMENT", "JOB", "OBLIGATION"),
        "policy_criticality": "MEDIUM",
    }


async def _retry(
    fn: Callable[[], Awaitable[Any]],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = 0.25,
) -> Any:
    attempt = 0
    while True:
        try:
            return await fn()
        except Exception:
            attempt += 1
            if attempt > max_retries:
                raise
            await asyncio.sleep(backoff_seconds * (2 ** (attempt - 1)))


class _WriteRateLimiter:
    def __init__(self, max_writes_per_sec: float):
        self._interval = 1.0 / max(max_writes_per_sec, 0.1)
        self._last = 0.0

    async def tick(self) -> None:
        now = time.monotonic()
        wait = self._last + self._interval - now
        if wait > 0:
            await asyncio.sleep(wait)
        self._last = time.monotonic()


async def _load_checkpoint(db, *, job_name: str, client_id: str) -> Dict[str, Any]:
    row = await _col(db, CHECKPOINT_COLLECTION).find_one(
        {"job_name": job_name, "client_id": client_id},
        {"_id": 0},
    )
    return row or {
        "job_name": job_name,
        "client_id": client_id,
        "last_requirement_id": "",
        "status": "new",
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "started_at": None,
        "updated_at": None,
        "completed_at": None,
    }


async def _save_checkpoint(
    db,
    *,
    job_name: str,
    client_id: str,
    patch: Dict[str, Any],
) -> None:
    await _col(db, CHECKPOINT_COLLECTION).update_one(
        {"job_name": job_name, "client_id": client_id},
        {"$set": {**patch, "updated_at": _utc_iso()}, "$setOnInsert": {"created_at": _utc_iso()}},
        upsert=True,
    )


async def _dead_letter(
    db,
    *,
    job_name: str,
    client_id: str,
    requirement_id: Optional[str],
    stage: str,
    error: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    await _col(db, DEAD_LETTER_COLLECTION).insert_one(
        {
            "dead_letter_id": f"{job_name}:{client_id}:{requirement_id or 'none'}:{int(time.time() * 1000)}",
            "job_name": job_name,
            "client_id": client_id,
            "requirement_id": requirement_id,
            "stage": stage,
            "error": error,
            "payload": payload or {},
            "created_at": _utc_iso(),
        }
    )


async def _fetch_requirement_batch(
    db,
    *,
    client_id: str,
    after_requirement_id: str,
    batch_size: int,
) -> list:
    q: Dict[str, Any] = {
        "client_id": client_id,
        "requirement_id": {"$exists": True, "$nin": [None, ""]},
    }
    if after_requirement_id:
        q["requirement_id"]["$gt"] = after_requirement_id
    cur = db.requirements.find(q, {"_id": 0}).sort("requirement_id", 1).limit(batch_size)
    return await cur.to_list(batch_size)


def _normalized_requirement_policy_patch(requirement: Dict[str, Any]) -> Dict[str, Any]:
    reg = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    facts = resolve_policy_facts(
        requirement,
        registry_metadata=reg,
        catalog_defaults=_policy_defaults_for_requirement(requirement),
    )
    return {
        "requirement_code_normalized": facts["requirement_code_normalized"],
        "applicability_state": facts["applicability_state"],
        "is_mandatory": bool(facts["is_mandatory"]),
        "policy_criticality": facts["policy_criticality"],
        "evidence_state_normalized": normalized_evidence_state_for_policy(requirement),
        "policy_classification_version": POLICY_CLASSIFICATION_VERSION,
        "policy_last_resolved_at": _utc_iso(),
    }


def _same_policy_fields(requirement: Dict[str, Any], patch: Dict[str, Any]) -> bool:
    for k, v in patch.items():
        if k in ("policy_last_resolved_at",):
            continue
        if requirement.get(k) != v:
            return False
    return True


async def run_tenant_requirement_policy_backfill(
    db,
    *,
    client_id: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = 0.25,
    max_writes_per_sec: float = DEFAULT_MAX_WRITES_PER_SEC,
    limit_requirements: Optional[int] = None,
) -> Dict[str, Any]:
    """Tenant-scoped idempotent backfill for requirement policy fields."""
    bs = _batch_size(batch_size)
    rl = _WriteRateLimiter(max_writes_per_sec=max_writes_per_sec)
    cp = await _load_checkpoint(db, job_name=JOB_REQUIREMENT_FIELDS, client_id=client_id)
    await _save_checkpoint(
        db,
        job_name=JOB_REQUIREMENT_FIELDS,
        client_id=client_id,
        patch={"status": "running", "started_at": cp.get("started_at") or _utc_iso()},
    )

    processed = int(cp.get("processed") or 0)
    updated = int(cp.get("updated") or 0)
    failed = int(cp.get("failed") or 0)
    last_requirement_id = str(cp.get("last_requirement_id") or "")

    while True:
        if limit_requirements is not None and processed >= int(limit_requirements):
            break
        take = bs if limit_requirements is None else min(bs, int(limit_requirements) - processed)
        if take <= 0:
            break
        rows = await _retry(
            lambda: _fetch_requirement_batch(
                db,
                client_id=client_id,
                after_requirement_id=last_requirement_id,
                batch_size=take,
            ),
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        if not rows:
            break
        for req in rows:
            rid = str(req.get("requirement_id") or "")
            if not rid:
                continue
            processed += 1
            last_requirement_id = rid
            try:
                patch = _normalized_requirement_policy_patch(req)
                if not _same_policy_fields(req, patch):
                    await rl.tick()
                    await _retry(
                        lambda: db.requirements.update_one(
                            {"client_id": client_id, "requirement_id": rid},
                            {"$set": patch},
                        ),
                        max_retries=max_retries,
                        backoff_seconds=backoff_seconds,
                    )
                    updated += 1
            except Exception as e:
                failed += 1
                await _dead_letter(
                    db,
                    job_name=JOB_REQUIREMENT_FIELDS,
                    client_id=client_id,
                    requirement_id=rid,
                    stage="requirement_patch",
                    error=str(e),
                    payload={"requirement_id": rid},
                )
            await _save_checkpoint(
                db,
                job_name=JOB_REQUIREMENT_FIELDS,
                client_id=client_id,
                patch={
                    "status": "running",
                    "last_requirement_id": last_requirement_id,
                    "processed": processed,
                    "updated": updated,
                    "failed": failed,
                },
            )

    await _save_checkpoint(
        db,
        job_name=JOB_REQUIREMENT_FIELDS,
        client_id=client_id,
        patch={
            "status": "completed",
            "last_requirement_id": last_requirement_id,
            "processed": processed,
            "updated": updated,
            "failed": failed,
            "completed_at": _utc_iso(),
        },
    )
    return {
        "job_name": JOB_REQUIREMENT_FIELDS,
        "client_id": client_id,
        "processed": processed,
        "updated": updated,
        "failed": failed,
        "last_requirement_id": last_requirement_id,
        "batch_size": bs,
        "max_writes_per_sec": max_writes_per_sec,
    }


def _gap_policy_snapshot_patch(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "requirement_code_normalized": row.get("requirement_code_normalized"),
        "applicability_state": row.get("applicability_state"),
        "is_mandatory": row.get("is_mandatory"),
        "policy_criticality": row.get("policy_criticality"),
        "evidence_state_normalized": row.get("evidence_state_normalized"),
        "days_overdue": row.get("days_overdue"),
        "days_to_expiry": row.get("days_to_expiry"),
        "critical_mandatory_breach": bool(row.get("critical_mandatory_breach")),
        "high_risk_gap": bool(row.get("high_risk_gap")),
        "attention_only_gap": bool(row.get("attention_only_gap")),
        "unknown_or_stale_signal": bool(row.get("unknown_or_stale_signal")),
        "policy_reason_codes": list(row.get("policy_reason_codes") or []),
        "policy_classification_version": row.get("policy_classification_version") or POLICY_CLASSIFICATION_VERSION,
        "policy_snapshot_updated_at": _utc_iso(),
    }


async def run_tenant_gap_policy_reconciliation(
    db,
    *,
    client_id: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = 0.25,
    max_writes_per_sec: float = DEFAULT_MAX_WRITES_PER_SEC,
    limit_requirements: Optional[int] = None,
) -> Dict[str, Any]:
    """Tenant-scoped reconciliation: refresh policy snapshot fields on open gaps."""
    bs = _batch_size(batch_size)
    rl = _WriteRateLimiter(max_writes_per_sec=max_writes_per_sec)
    cp = await _load_checkpoint(db, job_name=JOB_GAP_RECONCILIATION, client_id=client_id)
    await _save_checkpoint(
        db,
        job_name=JOB_GAP_RECONCILIATION,
        client_id=client_id,
        patch={"status": "running", "started_at": cp.get("started_at") or _utc_iso()},
    )
    processed = int(cp.get("processed") or 0)
    updated = int(cp.get("updated") or 0)
    failed = int(cp.get("failed") or 0)
    last_requirement_id = str(cp.get("last_requirement_id") or "")

    while True:
        if limit_requirements is not None and processed >= int(limit_requirements):
            break
        take = bs if limit_requirements is None else min(bs, int(limit_requirements) - processed)
        if take <= 0:
            break
        rows = await _retry(
            lambda: _fetch_requirement_batch(
                db,
                client_id=client_id,
                after_requirement_id=last_requirement_id,
                batch_size=take,
            ),
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        if not rows:
            break
        for req in rows:
            rid = str(req.get("requirement_id") or "")
            pid = str(req.get("property_id") or "")
            if not rid:
                continue
            processed += 1
            last_requirement_id = rid
            try:
                property_doc = await _retry(
                    lambda: db.properties.find_one(
                        {"client_id": client_id, "property_id": pid},
                        {"_id": 0},
                    ),
                    max_retries=max_retries,
                    backoff_seconds=backoff_seconds,
                )
                inferred = infer_compliance_gaps_for_requirement(req, property_doc=property_doc)
                inferred_rows: Dict[str, Dict[str, Any]] = {}
                req_code = str(req.get("requirement_code") or req.get("code") or req.get("requirement_type") or "")
                for g in inferred:
                    row = g.to_mongo(
                        client_id=client_id,
                        property_id=pid,
                        requirement_id=rid,
                        requirement_code=req_code,
                        requirement_row=req,
                    )
                    inferred_rows[str(row.get("gap_key") or "")] = row
                open_rows = await _retry(
                    lambda: db.compliance_gaps.find(
                        {"client_id": client_id, "requirement_id": rid, "status": "open"},
                        {"_id": 0, "gap_key": 1},
                    ).to_list(1000),
                    max_retries=max_retries,
                    backoff_seconds=backoff_seconds,
                )
                for gr in open_rows:
                    gap_key = str(gr.get("gap_key") or "")
                    if not gap_key:
                        continue
                    src = inferred_rows.get(gap_key)
                    if not src:
                        # Keep current open gap; just dead-letter for manual inspection.
                        failed += 1
                        await _dead_letter(
                            db,
                            job_name=JOB_GAP_RECONCILIATION,
                            client_id=client_id,
                            requirement_id=rid,
                            stage="gap_not_inferred",
                            error="open_gap_not_in_current_inference",
                            payload={"gap_key": gap_key},
                        )
                        continue
                    await rl.tick()
                    await _retry(
                        lambda: db.compliance_gaps.update_one(
                            {"client_id": client_id, "gap_key": gap_key, "status": "open"},
                            {"$set": _gap_policy_snapshot_patch(src)},
                        ),
                        max_retries=max_retries,
                        backoff_seconds=backoff_seconds,
                    )
                    updated += 1
            except Exception as e:
                failed += 1
                await _dead_letter(
                    db,
                    job_name=JOB_GAP_RECONCILIATION,
                    client_id=client_id,
                    requirement_id=rid,
                    stage="gap_reconcile",
                    error=str(e),
                    payload={"requirement_id": rid},
                )
            await _save_checkpoint(
                db,
                job_name=JOB_GAP_RECONCILIATION,
                client_id=client_id,
                patch={
                    "status": "running",
                    "last_requirement_id": last_requirement_id,
                    "processed": processed,
                    "updated": updated,
                    "failed": failed,
                },
            )
    await _save_checkpoint(
        db,
        job_name=JOB_GAP_RECONCILIATION,
        client_id=client_id,
        patch={
            "status": "completed",
            "last_requirement_id": last_requirement_id,
            "processed": processed,
            "updated": updated,
            "failed": failed,
            "completed_at": _utc_iso(),
        },
    )
    return {
        "job_name": JOB_GAP_RECONCILIATION,
        "client_id": client_id,
        "processed": processed,
        "updated": updated,
        "failed": failed,
        "last_requirement_id": last_requirement_id,
        "batch_size": bs,
        "max_writes_per_sec": max_writes_per_sec,
    }


async def run_policy_backfill_for_tenants(
    db,
    *,
    tenant_ids: list[str],
    tenant_concurrency_limit: int = 2,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = 0.25,
    max_writes_per_sec: float = DEFAULT_MAX_WRITES_PER_SEC,
    force: bool = False,
    dry_run: bool = False,
    max_tenants: int = DEFAULT_MAX_TENANTS_PER_RUN,
) -> Dict[str, Any]:
    """Tenant-concurrency orchestrator for PR4 jobs."""
    sem = asyncio.Semaphore(max(1, int(tenant_concurrency_limit)))
    bounded_tenants = [str(t).strip() for t in tenant_ids if str(t).strip()][: max(1, int(max_tenants))]
    out: Dict[str, Any] = {
        "tenant_results": {},
        "tenant_concurrency_limit": max(1, int(tenant_concurrency_limit)),
        "max_tenants": max(1, int(max_tenants)),
        "tenants_requested": len(tenant_ids),
        "tenants_selected": len(bounded_tenants),
        "dry_run": bool(dry_run),
    }

    async def _one(tid: str) -> Tuple[str, Dict[str, Any]]:
        async with sem:
            status = await get_tenant_policy_convergence_status(db, client_id=tid)
            if dry_run:
                return tid, {
                    "mode": "dry_run",
                    "status": status,
                    "eligible_for_pr5": bool(status.get("eligible_for_pr5")),
                }
            if (not force) and bool(status.get("eligible_for_pr5")):
                return tid, {
                    "mode": "skipped_converged",
                    "status": status,
                    "eligible_for_pr5": True,
                }
            req = await run_tenant_requirement_policy_backfill(
                db,
                client_id=tid,
                batch_size=batch_size,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
                max_writes_per_sec=max_writes_per_sec,
            )
            gap = await run_tenant_gap_policy_reconciliation(
                db,
                client_id=tid,
                batch_size=batch_size,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
                max_writes_per_sec=max_writes_per_sec,
            )
            post = await get_tenant_policy_convergence_status(db, client_id=tid)
            return tid, {
                "mode": "executed",
                "requirement_backfill": req,
                "gap_reconciliation": gap,
                "status_before": status,
                "status_after": post,
                "eligible_for_pr5": bool(post.get("eligible_for_pr5")),
            }

    rows = await asyncio.gather(*[_one(t) for t in bounded_tenants])
    for tid, r in rows:
        out["tenant_results"][tid] = r
    return out


async def discover_tenant_ids(
    db,
    *,
    client_id: Optional[str] = None,
    all_tenants: bool = False,
    limit: int = DEFAULT_MAX_TENANTS_PER_RUN,
    resume_from: Optional[str] = None,
    include_test_tenants: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Authoritative tenant discovery from clients collection.
    Excludes deleted/suspended/test-like tenants by default.
    """
    if client_id:
        return {
            "source": "clients",
            "filters": {"client_id": client_id},
            "tenant_ids": [str(client_id)],
            "dry_run": bool(dry_run),
            "discovered_count": 1,
        }
    if not all_tenants:
        raise ValueError("Provide client_id or set all_tenants=True")

    lim = max(1, min(int(limit or DEFAULT_MAX_TENANTS_PER_RUN), 1000))
    q: Dict[str, Any] = {
        "client_id": {"$exists": True, "$nin": [None, ""]},
        "is_deleted": {"$ne": True},
    }
    if not include_test_tenants:
        q["is_test_like"] = {"$ne": True}
    # Lifecycle guard: exclude explicit suspended/deleted where present.
    q["client_lifecycle_status"] = {"$nin": ["SUSPENDED", "suspended", "DELETED", "deleted"]}
    if resume_from:
        q["client_id"]["$gt"] = str(resume_from)
    cur = db.clients.find(q, {"_id": 0, "client_id": 1}).sort("client_id", 1).limit(lim)
    rows = await cur.to_list(lim)
    tenant_ids = [str(r.get("client_id") or "").strip() for r in rows if str(r.get("client_id") or "").strip()]
    return {
        "source": "clients",
        "filters": {
            "all_tenants": True,
            "limit": lim,
            "resume_from": resume_from,
            "include_test_tenants": bool(include_test_tenants),
        },
        "tenant_ids": tenant_ids,
        "dry_run": bool(dry_run),
        "discovered_count": len(tenant_ids),
    }


async def get_tenant_policy_convergence_status(db, *, client_id: str) -> Dict[str, Any]:
    req_total = int(await db.requirements.count_documents({"client_id": client_id}))
    req_v1 = int(
        await db.requirements.count_documents(
            {"client_id": client_id, "policy_classification_version": POLICY_CLASSIFICATION_VERSION}
        )
    )
    gap_total = int(await db.compliance_gaps.count_documents({"client_id": client_id, "status": "open"}))
    gap_policy = int(
        await db.compliance_gaps.count_documents(
            {
                "client_id": client_id,
                "status": "open",
                "requirement_code_normalized": {"$nin": [None, ""]},
                "policy_criticality": {"$nin": [None, ""]},
                "applicability_state": {"$nin": [None, ""]},
                "evidence_state_normalized": {"$nin": [None, ""]},
            }
        )
    )
    req_cov = round((req_v1 / req_total) * 100, 2) if req_total > 0 else 100.0
    gap_cov = round((gap_policy / gap_total) * 100, 2) if gap_total > 0 else 100.0
    cp_req = await _load_checkpoint(db, job_name=JOB_REQUIREMENT_FIELDS, client_id=client_id)
    cp_gap = await _load_checkpoint(db, job_name=JOB_GAP_RECONCILIATION, client_id=client_id)
    eligible = (
        req_cov >= PR5_REQ_COVERAGE_GATE_PERCENT
        and gap_cov >= PR5_GAP_COVERAGE_GATE_PERCENT
        and str(cp_req.get("status") or "").lower() == "completed"
        and str(cp_gap.get("status") or "").lower() == "completed"
    )
    return {
        "client_id": client_id,
        "requirement_coverage_percent": req_cov,
        "gap_coverage_percent": gap_cov,
        "requirements_total": req_total,
        "requirements_v1": req_v1,
        "open_gaps_total": gap_total,
        "open_gaps_policy_ready": gap_policy,
        "last_checkpoint_state": {
            "requirement_backfill": {
                "status": cp_req.get("status"),
                "processed": int(cp_req.get("processed") or 0),
                "updated": int(cp_req.get("updated") or 0),
                "failed": int(cp_req.get("failed") or 0),
                "updated_at": cp_req.get("updated_at"),
            },
            "gap_reconciliation": {
                "status": cp_gap.get("status"),
                "processed": int(cp_gap.get("processed") or 0),
                "updated": int(cp_gap.get("updated") or 0),
                "failed": int(cp_gap.get("failed") or 0),
                "updated_at": cp_gap.get("updated_at"),
            },
        },
        "eligible_for_pr5": bool(eligible),
    }
