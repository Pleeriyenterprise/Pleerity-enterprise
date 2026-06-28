"""
PR4: internal operator commands for applicability override (MARK_REQUIRED / MARK_NOT_REQUIRED / REVOKE).

- Never mutates pipeline_applicability_state (reads current pipeline snapshot only).
- Selector + flat mirrors via ``build_provenance_mongo_set``.
- Append-only audit for every successful command.
- After a successful requirement write, refreshes persisted ``compliance_gaps`` policy snapshots
  via ``sync_compliance_gaps_for_requirement`` (quiet lifecycle + no operational bridge) so HIUA
  reads current effective applicability without waiting for batch reconciliation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Optional

from services.applicability_operator_resolution_reasons import validate_operator_resolution_reason_code
from services.applicability_provenance_backfill import pipeline_from_legacy_requirement
from services.applicability_provenance_constants import normalize_applicability_tri_state
from services.applicability_provenance_selector import build_provenance_mongo_set
from services.applicability_resolution_audit import append_applicability_resolution_audit
from services.compliance_gap_sync import sync_compliance_gaps_for_requirement

logger = logging.getLogger(__name__)

MARK_REQUIRED = "MARK_REQUIRED"
MARK_NOT_REQUIRED = "MARK_NOT_REQUIRED"
REVOKE_OVERRIDE = "REVOKE_OVERRIDE"
OPERATOR_COMMANDS = frozenset({MARK_REQUIRED, MARK_NOT_REQUIRED, REVOKE_OVERRIDE})


class ApplicabilityOperatorActionError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _pipeline_snapshot_only(row: Dict[str, Any]) -> str:
    """Pipeline truth only — never derived from operator override or effective."""
    if row.get("pipeline_applicability_state"):
        return normalize_applicability_tri_state(row["pipeline_applicability_state"])
    nested = row.get("applicability_provenance")
    if isinstance(nested, dict) and nested.get("pipeline_applicability_state"):
        return normalize_applicability_tri_state(nested.get("pipeline_applicability_state"))
    return pipeline_from_legacy_requirement(row)


def _validate_actor(actor: Mapping[str, Any]) -> None:
    if not isinstance(actor, dict):
        raise ApplicabilityOperatorActionError("actor must be a dict", status_code=400)
    at = str(actor.get("type") or "").strip().lower()
    if at not in ("system", "user", "service"):
        raise ApplicabilityOperatorActionError("actor.type must be system, user, or service", status_code=400)
    if at in ("user", "service") and not str(actor.get("id") or "").strip():
        raise ApplicabilityOperatorActionError("actor.id is required for user/service actors", status_code=400)


def _event_type_for_command(command: str) -> str:
    if command == MARK_REQUIRED:
        return "OPERATOR_MARK_REQUIRED"
    if command == MARK_NOT_REQUIRED:
        return "OPERATOR_MARK_NOT_REQUIRED"
    if command == REVOKE_OVERRIDE:
        return "OPERATOR_REVOKE_OVERRIDE"
    raise ApplicabilityOperatorActionError(f"unknown command: {command}", status_code=400)


async def execute_applicability_operator_command(
    db: Any,
    *,
    client_id: str,
    requirement_id: str,
    command: str,
    resolution_reason_code: str,
    actor: Mapping[str, Any],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tenant-scoped operator applicability command. Updates provenance + legacy mirror; refreshes
    open gap snapshots for the requirement; appends applicability resolution audit.

    Raises ApplicabilityOperatorActionError on validation / not-found.
    """
    cmd = str(command or "").strip().upper()
    if cmd not in OPERATOR_COMMANDS:
        raise ApplicabilityOperatorActionError(f"invalid command: {command}", status_code=400)
    try:
        validate_operator_resolution_reason_code(resolution_reason_code)
    except ValueError as exc:
        raise ApplicabilityOperatorActionError(str(exc), status_code=400) from exc
    _validate_actor(actor)

    req = await db.requirements.find_one(
        {"client_id": str(client_id).strip(), "requirement_id": str(requirement_id).strip()},
        {"_id": 0},
    )
    if not req:
        raise ApplicabilityOperatorActionError("requirement not found", status_code=404)

    pipeline_only = _pipeline_snapshot_only(req)
    if cmd == MARK_REQUIRED:
        ov_active, ov_state = True, "REQUIRED"
    elif cmd == MARK_NOT_REQUIRED:
        ov_active, ov_state = True, "NOT_REQUIRED"
    else:
        ov_active, ov_state = False, None

    patch = build_provenance_mongo_set(
        pipeline_applicability_state=pipeline_only,
        operator_override_active=ov_active,
        operator_override_applicability_state=ov_state,
    )
    patch["applicability_state"] = patch["effective_applicability_state"]
    if cmd != REVOKE_OVERRIDE:
        ov = patch["applicability_provenance"]["operator_override"]
        if ov_active:
            ov["resolution_reason_code"] = str(resolution_reason_code).strip().upper()
            if notes and str(notes).strip():
                ov["resolution_notes"] = str(notes).strip()
            ov["actor"] = dict(actor)

    cid_s = str(client_id).strip()
    rid_s = str(requirement_id).strip()
    await db.requirements.update_one(
        {"client_id": cid_s, "requirement_id": rid_s},
        {"$set": patch},
    )
    refreshed = await db.requirements.find_one(
        {"client_id": cid_s, "requirement_id": rid_s},
        {"_id": 0},
    )
    if refreshed:
        prop_doc = None
        pid = str(refreshed.get("property_id") or "").strip()
        if pid:
            prop_doc = await db.properties.find_one(
                {"client_id": cid_s, "property_id": pid},
                {"_id": 0},
            )
        try:
            sync_out = await sync_compliance_gaps_for_requirement(
                db,
                refreshed,
                property_doc=prop_doc,
                audit_lifecycle=False,
                run_operational_bridge=False,
            )
            if sync_out.get("errors"):
                logger.warning(
                    "sync_compliance_gaps_for_requirement after applicability operator command "
                    "client_id=%s requirement_id=%s: %s",
                    cid_s,
                    rid_s,
                    sync_out["errors"],
                )
        except Exception as gap_exc:
            logger.warning(
                "sync_compliance_gaps_for_requirement failed after applicability operator command "
                "client_id=%s requirement_id=%s: %s",
                cid_s,
                rid_s,
                gap_exc,
            )
    else:
        logger.warning(
            "requirements.find_one returned no row after applicability operator update client_id=%s requirement_id=%s",
            cid_s,
            rid_s,
        )

    await append_applicability_resolution_audit(
        db,
        client_id=str(client_id).strip(),
        property_id=req.get("property_id"),
        requirement_id=str(requirement_id).strip(),
        event_type=_event_type_for_command(cmd),
        pipeline_applicability_state=patch["pipeline_applicability_state"],
        effective_applicability_state=patch["effective_applicability_state"],
        applicability_resolution_source=patch["applicability_resolution_source"],
        actor=dict(actor),
        resolution_reason_code=str(resolution_reason_code).strip().upper(),
        notes=str(notes).strip() if notes else None,
    )
    await _dispatch_applicability_operator_producer(
        client_id=cid_s,
        requirement_id=rid_s,
        command=cmd,
        patch=patch,
        resolution_reason_code=str(resolution_reason_code).strip().upper(),
        actor=actor,
        requirement=req,
    )
    return {
        "ok": True,
        "client_id": client_id,
        "requirement_id": requirement_id,
        "command": cmd,
        "pipeline_applicability_state": patch["pipeline_applicability_state"],
        "effective_applicability_state": patch["effective_applicability_state"],
        "applicability_resolution_source": patch["applicability_resolution_source"],
    }


async def _dispatch_applicability_operator_producer(
    *,
    client_id: str,
    requirement_id: str,
    command: str,
    patch: Dict[str, Any],
    resolution_reason_code: str,
    actor: Mapping[str, Any],
    requirement: Dict[str, Any],
) -> None:
    try:
        from services.compliance_evidence_graph.producers.hooks import dispatch_p1_producer
        from services.compliance_evidence_graph.producers.registry import ProducerContext

        await dispatch_p1_producer(
            ProducerContext(
                mutation_kind="applicability_operator",
                client_id=str(client_id).strip(),
                source_collection="requirements",
                source_id=str(requirement_id).strip(),
                property_id=requirement.get("property_id"),
                requirement_id=str(requirement_id).strip(),
                authoritative_payload={
                    "command": command,
                    "pipeline_applicability_state": patch.get("pipeline_applicability_state"),
                    "effective_applicability_state": patch.get("effective_applicability_state"),
                    "resolution_reason_code": resolution_reason_code,
                    "requirement": requirement,
                    "actor_type": str(actor.get("type") or "user"),
                    "actor_id": str(actor.get("id") or ""),
                    "authority_service": "applicability_operator_actions",
                    "authority_component": "execute_applicability_operator_command",
                },
            )
        )
    except Exception:
        pass


__all__ = [
    "ApplicabilityOperatorActionError",
    "MARK_NOT_REQUIRED",
    "MARK_REQUIRED",
    "REVOKE_OVERRIDE",
    "execute_applicability_operator_command",
]
