"""Property Management Routes - Additive Enhancement
Allows clients to create and manage properties.
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from models import Property, ComplianceStatus, AuditAction, UserRole
from utils.expiry_utils import get_effective_expiry_date, get_computed_status, is_included_for_calendar
from utils.audit import create_audit_log
from utils.compliance_fanout_log import compliance_fanout_extra
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

from services.requirement_client_runtime_surface import (
    filter_requirement_rows_for_client_runtime_surfaces,
    project_requirement_row_client_runtime,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/properties", tags=["properties"])

def _validate_building_age_years(value: Optional[int]) -> int:
    """Optional building age in whole years; used for Scotland lead-testing and EICR frequency planning."""
    if value is None:
        raise ValueError("missing")
    try:
        age = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid") from exc
    if age < 0 or age > 500:
        raise ValueError("range")
    return age


class CreatePropertyRequest(BaseModel):
    nickname: Optional[str] = None  # Optional; when set, used to identify the property; otherwise address is used
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    property_type: str = "residential"
    number_of_units: int = 1
    # Optional override; when omitted, new properties use the client's saved default_jurisdiction (canonicalised).
    jurisdiction: Optional[str] = Field(None, description="Scotland | England | Wales | Northern Ireland")
    building_age_years: Optional[int] = Field(
        None,
        ge=0,
        le=500,
        description="Optional building age in years (Scotland lead-testing gate when > 50)",
    )

@router.post("/create")
async def create_property(request: Request, data: CreatePropertyRequest):
    """Create a new property for the authenticated client.
    
    Enforces plan-based property limits.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client with plan info
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not client or client["onboarding_status"] != "PROVISIONED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account must be fully provisioned to add properties"
            )
        
        # Property cap enforcement (plan_registry canonical) – count only active properties
        active_count = await db.properties.count_documents({
            "client_id": user["client_id"],
            "$or": [{"is_active": True}, {"is_active": {"$exists": False}}],
        })
        from services.plan_registry import plan_registry
        allowed, error_msg, error_details = await plan_registry.enforce_property_limit(
            user["client_id"], active_count + 1
        )
        if not allowed:
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole(user["role"]),
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                metadata={
                    "action_type": "PLAN_LIMIT_EXCEEDED",
                    "feature": "property_create",
                    "current_count": active_count,
                    "requested_count": 1,
                    "attempted_address": data.address_line_1,
                },
            )
            detail = dict(error_details or {})
            detail["error_code"] = "PLAN_LIMIT"  # API contract for plan-limit 403
            detail["message"] = detail.get("message") or error_msg
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )
        
        from services.compliance_rules_registry import canonicalize_uk_portfolio_label

        if data.jurisdiction is not None and str(data.jurisdiction).strip():
            prop_jurisdiction = canonicalize_uk_portfolio_label(data.jurisdiction)
            if not prop_jurisdiction:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="jurisdiction must be Scotland, England, Wales, or Northern Ireland",
                )
        else:
            prop_jurisdiction = canonicalize_uk_portfolio_label(client.get("default_jurisdiction"))

        # Create property
        building_age_years = None
        if data.building_age_years is not None:
            try:
                building_age_years = _validate_building_age_years(data.building_age_years)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="building_age_years must be an integer between 0 and 500",
                )

        property_obj = Property(
            client_id=user["client_id"],
            nickname=(data.nickname or "").strip() or None,
            address_line_1=data.address_line_1,
            address_line_2=data.address_line_2,
            city=data.city,
            postcode=data.postcode,
            property_type=data.property_type,
            number_of_units=data.number_of_units,
            compliance_status=ComplianceStatus.RED,
            jurisdiction=prop_jurisdiction,
            building_age_years=building_age_years,
        )
        
        prop_doc = property_obj.model_dump()
        for key in ["created_at", "updated_at"]:
            if prop_doc.get(key):
                prop_doc[key] = prop_doc[key].isoformat()
        
        await db.properties.insert_one(prop_doc)
        
        # Remove MongoDB _id from response
        prop_doc.pop("_id", None)
        
        # Generate requirements using existing logic
        from services.provisioning import provisioning_service
        await provisioning_service._generate_requirements(
            user["client_id"],
            property_obj.property_id
        )
        
        # Update compliance status
        await provisioning_service._update_property_compliance(
            property_obj.property_id
        )
        from services.compliance_recalc_queue import enqueue_compliance_recalc, TRIGGER_PROPERTY_CREATED, ACTOR_ADMIN
        await enqueue_compliance_recalc(
            property_id=property_obj.property_id,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_PROPERTY_CREATED,
            actor_type=ACTOR_ADMIN,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"PROPERTY_CREATED:{property_obj.property_id}",
        )
        from services.provisioning_status_hook import update_provisioning_status_for_property
        await update_provisioning_status_for_property(user["client_id"], property_obj.property_id)
        try:
            from services.score_events_service import write_score_event, EVENT_PROPERTY_ADDED, ACTOR_ROLE_CLIENT
            await write_score_event(
                client_id=user["client_id"],
                event_type=EVENT_PROPERTY_ADDED,
                actor_user_id=user.get("portal_user_id"),
                actor_role=ACTOR_ROLE_CLIENT,
                property_id=property_obj.property_id,
                metadata={"address": f"{data.address_line_1}, {data.city}", "postcode": data.postcode},
            )
        except Exception as ev_err:
            logger.debug("Score event PROPERTY_ADDED skip: %s", ev_err)

        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole(user["role"]),
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="property",
            resource_id=property_obj.property_id,
            metadata={
                "action": "property_created",
                "address": f"{data.address_line_1}, {data.city}",
                "postcode": data.postcode
            }
        )
        
        logger.info(f"Property created by client {user['client_id']}: {property_obj.property_id}")
        
        return {
            "message": "Property created successfully",
            "property_id": property_obj.property_id,
            "property": prop_doc
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Property creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create property"
        )

# Fields that affect compliance score applicability (v1); changing any triggers recalc.
APPLICABILITY_FIELDS = frozenset(
    {
        "is_hmo",
        "bedrooms",
        "occupancy",
        "licence_required",
        "has_gas_supply",
        "has_gas",
        "tenancy_active",
        "furnished",
        "property_type",
        "building_age_years",
    }
)

_MAX_REQUIREMENTS_GAP_SYNC_AFTER_MATERIALIZATION = 500


async def _sync_compliance_gaps_for_property_requirements_after_materialization(
    db,
    *,
    client_id: str,
    property_id: str,
) -> None:
    """
    After requirement materialisation, persist gap rows for each requirement on this property
    (default gap lifecycle + operational bridge). Tenant-scoped: client_id + property_id only.
    """
    from services.compliance_gap_sync import sync_compliance_gaps_for_requirement

    cid = str(client_id or "").strip()
    pid = str(property_id or "").strip()
    if not cid or not pid:
        return
    prop_doc = await db.properties.find_one({"property_id": pid, "client_id": cid}, {"_id": 0})
    rows = await db.requirements.find(
        {"property_id": pid, "client_id": cid},
        {"_id": 0},
    ).to_list(_MAX_REQUIREMENTS_GAP_SYNC_AFTER_MATERIALIZATION)
    for req in rows:
        rid = req.get("requirement_id")
        if not rid:
            continue
        try:
            await sync_compliance_gaps_for_requirement(db, req, property_doc=prop_doc)
        except Exception as exc:
            logger.warning(
                "patch_property: gap sync after materialisation failed client_id=%s property_id=%s requirement_id=%s: %s",
                cid,
                pid,
                rid,
                exc,
                extra=compliance_fanout_extra(
                    op="gap_sync",
                    stage="failed",
                    client_id=cid,
                    property_id=pid,
                    requirement_id=str(rid),
                    exc_type=type(exc).__name__,
                ),
            )


class PatchPropertyRequest(BaseModel):
    """Optional fields for PATCH; only provided keys are updated."""
    nickname: Optional[str] = None
    property_type: Optional[str] = None  # residential, commercial, flat, house, bungalow, etc.; commercial excludes residential-only requirements
    is_hmo: Optional[bool] = None
    bedrooms: Optional[int] = None
    occupancy: Optional[str] = None
    licence_required: Optional[str] = None
    has_gas_supply: Optional[bool] = None
    has_gas: Optional[bool] = None
    tenancy_active: Optional[bool] = None
    furnished: Optional[bool] = None
    is_active: Optional[bool] = None  # False = archived (read-only) when over property limit
    building_age_years: Optional[int] = Field(
        None,
        ge=0,
        le=500,
        description="Optional building age in years; clear with null",
    )
    # Set to Scotland | England | Wales | Northern Ireland, or "" / null to clear the property record (fall back to account default).
    jurisdiction: Optional[str] = None


@router.patch("/{property_id}")
async def patch_property(request: Request, property_id: str, data: PatchPropertyRequest):
    """Update a property. Only provided fields are updated.
    Changing is_hmo, bedrooms, occupancy, licence_required, has_gas_supply, or has_gas triggers compliance score recalc (queued).
    Changing jurisdiction runs an immediate compliance score recalculation for this property.
    Setting is_active=False archives the property (read-only); is_active=True counts toward plan limit.
    """
    user = await client_route_guard(request)
    db = database.get_db()

    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1, "client_id": 1, "property_type": 1, "is_hmo": 1, "bedrooms": 1, "occupancy": 1,
         "licence_required": 1, "has_gas_supply": 1, "has_gas": 1, "tenancy_active": 1, "furnished": 1,
         "building_age_years": 1, "is_active": 1, "jurisdiction": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    update = {}
    jurisdiction_changed = False
    payload = data.model_dump(exclude_none=True)
    from services.compliance_rules_registry import canonicalize_uk_portfolio_label

    if "building_age_years" in data.model_fields_set:
        payload.pop("building_age_years", None)
        raw_age = data.building_age_years
        if raw_age is None:
            update["building_age_years"] = None
        else:
            try:
                update["building_age_years"] = _validate_building_age_years(raw_age)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="building_age_years must be an integer between 0 and 500",
                )

    if "jurisdiction" in data.model_fields_set:
        payload.pop("jurisdiction", None)
        raw_j = data.jurisdiction
        if raw_j is None or (isinstance(raw_j, str) and not raw_j.strip()):
            update["jurisdiction"] = None
        else:
            canon = canonicalize_uk_portfolio_label(raw_j)
            if not canon:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="jurisdiction must be Scotland, England, Wales, or Northern Ireland (or empty to clear)",
                )
            update["jurisdiction"] = canon
        jurisdiction_changed = True

    for key, value in payload.items():
        update[key] = value

    # When activating a property, enforce plan limit (active count cannot exceed allowed)
    if "is_active" in update and update["is_active"] is True:
        from services.plan_registry import plan_registry
        active_count = await db.properties.count_documents({
            "client_id": user["client_id"],
            "property_id": {"$ne": property_id},
            "$or": [{"is_active": True}, {"is_active": {"$exists": False}}],
        })
        allowed, error_msg, error_details = await plan_registry.enforce_property_limit(
            user["client_id"], active_count + 1
        )
        if not allowed:
            detail = error_details or {}
            if "error_code" not in detail:
                detail["error_code"] = "PLAN_LIMIT"
            detail["message"] = detail.get("message") or error_msg
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    if not update:
        return {"message": "No updates", "property_id": property_id}

    applicability_changed = any(
        f in update and prop.get(f) != update[f]
        for f in APPLICABILITY_FIELDS
    )

    now = datetime.now(timezone.utc)
    update["updated_at"] = now.isoformat()
    await db.properties.update_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"$set": update},
    )
    from services.provisioning_status_hook import update_provisioning_status_for_property
    await update_provisioning_status_for_property(user["client_id"], property_id)

    materialization_ok = False
    prev_jurisdiction = prop.get("jurisdiction")
    if jurisdiction_changed or applicability_changed:
        try:
            from services.requirement_materialization_service import materialize_requirements_for_property

            trigger = "property_jurisdiction_patch" if jurisdiction_changed else "property_applicability_patch"
            await materialize_requirements_for_property(
                user["client_id"],
                property_id,
                reconcile_obsolete=True,
                materialization_trigger=trigger,
            )
            materialization_ok = True
            if jurisdiction_changed:
                try:
                    from services.compliance_evidence_graph.producers.hooks import dispatch_p1_producer
                    from services.compliance_evidence_graph.producers.registry import ProducerContext

                    await dispatch_p1_producer(
                        ProducerContext(
                            mutation_kind="property_jurisdiction_materialization",
                            client_id=str(user["client_id"]),
                            source_collection="properties",
                            source_id=property_id,
                            property_id=property_id,
                            mutation_timestamp=now.isoformat(),
                            authoritative_payload={
                                "previous_jurisdiction": prev_jurisdiction,
                                "new_jurisdiction": update.get("jurisdiction"),
                                "applicability_fields_changed": applicability_changed,
                                "jurisdiction": update.get("jurisdiction"),
                            },
                        )
                    )
                except Exception:
                    pass
        except Exception as mat_err:
            logger.exception(
                "patch_property: requirement materialisation failed property_id=%s: %s",
                property_id,
                mat_err,
            )

    if materialization_ok:
        try:
            await _sync_compliance_gaps_for_property_requirements_after_materialization(
                db,
                client_id=str(user["client_id"]),
                property_id=str(property_id),
            )
        except Exception as gap_sweep_err:
            logger.warning(
                "patch_property: post-materialisation gap sync sweep failed property_id=%s: %s",
                property_id,
                gap_sweep_err,
                extra=compliance_fanout_extra(
                    op="gap_sync",
                    stage="failed",
                    client_id=str(user["client_id"]),
                    property_id=str(property_id),
                    exc_type=type(gap_sweep_err).__name__,
                ),
            )

    if jurisdiction_changed:
        from services.compliance_scoring_service import recalculate_and_persist
        from services.compliance_recalc_queue import (
            TRIGGER_PROPERTY_UPDATED,
            ACTOR_CLIENT,
            enqueue_compliance_recalc,
        )

        try:
            await recalculate_and_persist(
                property_id,
                TRIGGER_PROPERTY_UPDATED,
                actor={
                    "id": user.get("portal_user_id"),
                    "role": user.get("role") or "ROLE_CLIENT",
                },
                context={"correlation_id": f"PROPERTY_JURISDICTION_PATCH:{property_id}"},
            )
        except Exception as recalc_err:
            logger.exception(
                "patch_property: synchronous compliance recalc failed after jurisdiction update property_id=%s: %s",
                property_id,
                recalc_err,
            )
            await enqueue_compliance_recalc(
                property_id=property_id,
                client_id=user["client_id"],
                trigger_reason=TRIGGER_PROPERTY_UPDATED,
                actor_type=ACTOR_CLIENT,
                actor_id=user.get("portal_user_id"),
                correlation_id=f"PROPERTY_JURISDICTION_PATCH_FALLBACK:{property_id}",
            )
    elif applicability_changed:
        from services.compliance_recalc_queue import (
            enqueue_compliance_recalc,
            TRIGGER_PROPERTY_UPDATED,
            ACTOR_CLIENT,
        )
        await enqueue_compliance_recalc(
            property_id=property_id,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_PROPERTY_UPDATED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"PROPERTY_UPDATED:{property_id}",
        )

    if jurisdiction_changed or applicability_changed:
        try:
            from services.score_events_service import write_score_event, EVENT_PROPERTY_UPDATED, ACTOR_ROLE_CLIENT
            trig = "jurisdiction_changed" if jurisdiction_changed else "applicability_changed"
            await write_score_event(
                client_id=user["client_id"],
                event_type=EVENT_PROPERTY_UPDATED,
                actor_user_id=user.get("portal_user_id"),
                actor_role=ACTOR_ROLE_CLIENT,
                property_id=property_id,
                metadata={"trigger": trig},
            )
        except Exception as ev_err:
            logger.debug("Score event PROPERTY_UPDATED skip: %s", ev_err)

    return {"message": "Property updated", "property_id": property_id}


# Controlled reason list for NOT_REQUIRED (no legal advice; user selects from list)
NOT_REQUIRED_REASONS = ["no_gas_supply", "exempt", "not_applicable", "other"]


class MarkNotApplicableRequest(BaseModel):
    """Mark a catalog requirement as not applicable for this property (creates or updates requirement row)."""
    requirement_code: str
    not_required_reason: str
    reason: str = Field(..., min_length=10, description="Mandatory free-text audit reason (trimmed server-side)")


@router.post("/{property_id}/requirements/mark-not-applicable")
async def mark_requirement_not_applicable(
    request: Request,
    property_id: str,
    data: MarkNotApplicableRequest,
):
    """Create or update a requirement row to mark a catalog item as not applicable for this property."""
    user = await client_route_guard(request)
    client_id = user["client_id"]
    db = database.get_db()

    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "property_id": 1, "jurisdiction": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1})
    from services.compliance_rules_registry import portfolio_jurisdiction_label
    from services.requirement_mark_not_applicable_catalog import (
        mark_catalog_requirement_not_applicable_for_property,
        sync_audit_enqueue_after_catalog_not_applicable,
    )

    portfolio_juris = portfolio_jurisdiction_label(prop, client_doc or {})
    preset = (data.not_required_reason or "").strip()
    if preset not in NOT_REQUIRED_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"not_required_reason must be one of: {NOT_REQUIRED_REASONS}",
        )
    audit = (data.reason or "").strip()
    requirement_id, normalized_code, created = await mark_catalog_requirement_not_applicable_for_property(
        db,
        client_id=client_id,
        property_id=property_id,
        requirement_code=data.requirement_code.strip(),
        not_required_preset=preset,
        audit_free_text=audit,
        portfolio_jurisdiction=portfolio_juris,
    )
    await sync_audit_enqueue_after_catalog_not_applicable(
        db,
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        requirement_code=normalized_code,
        not_required_preset=preset,
        audit_free_text=audit,
        created=created,
        actor_portal_user_id=user.get("portal_user_id"),
        transition_origin="routes.properties.mark_requirement_not_applicable",
    )
    return {"message": "Marked as not applicable", "requirement_id": requirement_id, "created": created}


class PatchRequirementRequest(BaseModel):
    """Update expiry, applicability, or certificate fields for a property requirement."""
    confirmed_expiry_date: Optional[str] = None  # ISO date
    issue_date: Optional[str] = None  # ISO date
    certificate_number: Optional[str] = None
    applicability: Optional[str] = None  # REQUIRED | NOT_REQUIRED | UNKNOWN
    not_required_reason: Optional[str] = None  # Required when applicability=NOT_REQUIRED; one of NOT_REQUIRED_REASONS
    not_applicable_audit_reason: Optional[str] = None  # Required when applicability=NOT_REQUIRED; min 10 chars (trimmed server-side)


@router.patch("/{property_id}/requirements/{requirement_id}")
async def patch_requirement(
    request: Request,
    property_id: str,
    requirement_id: str,
    data: PatchRequirementRequest,
):
    """Update a requirement's confirmed expiry date or applicability (e.g. mark NOT_REQUIRED with reason)."""
    user = await client_route_guard(request)
    db = database.get_db()

    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")

    patch_confirm_payload: Dict[str, Any] = {}
    if data.confirmed_expiry_date is not None:
        patch_confirm_payload["confirmed_expiry_date"] = data.confirmed_expiry_date
    if data.issue_date is not None:
        patch_confirm_payload["issue_date"] = data.issue_date
    if data.certificate_number is not None:
        patch_confirm_payload["certificate_number"] = data.certificate_number

    prop_row = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "jurisdiction": 1},
    ) or {}
    client_row = await db.clients.find_one(
        {"client_id": user["client_id"]},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    unset_na_metadata = False

    def _parse_patch_iso(raw: str) -> datetime:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    if patch_confirm_payload:
        from services.lifecycle_confirm_apply import get_patch_requirement_update
        from services.lifecycle_confirm_validation import enforce_lifecycle_confirm_or_raise

        try:
            patch_confirm_payload = enforce_lifecycle_confirm_or_raise(
                req,
                patch_confirm_payload,
                surface="patch_requirement",
                requirement_id=requirement_id,
            )
        except HTTPException:
            raise

        try:
            patch_plan = get_patch_requirement_update(
                req,
                confirmed_expiry_date=patch_confirm_payload.get("confirmed_expiry_date")
                if data.confirmed_expiry_date is not None
                else None,
                issue_date=patch_confirm_payload.get("issue_date")
                if data.issue_date is not None
                else None,
                certificate_number=patch_confirm_payload.get("certificate_number")
                if data.certificate_number is not None
                else None,
                parse_iso=_parse_patch_iso,
                requirement_id=requirement_id,
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format; use YYYY-MM-DD or ISO datetime",
            ) from exc
        for key, value in patch_plan.update_fields.items():
            update[key] = value

    if data.applicability is not None:
        app = data.applicability.strip().upper()
        if app not in ("REQUIRED", "NOT_REQUIRED", "UNKNOWN"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="applicability must be REQUIRED, NOT_REQUIRED, or UNKNOWN",
            )
        update["applicability"] = app
        if app == "NOT_REQUIRED":
            reason = (data.not_required_reason or "").strip()
            if not reason or reason not in NOT_REQUIRED_REASONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"not_required_reason is required when applicability is NOT_REQUIRED and must be one of: {NOT_REQUIRED_REASONS}",
                )
            audit = (data.not_applicable_audit_reason or "").strip()
            if len(audit) < 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="not_applicable_audit_reason must be at least 10 characters when applicability is NOT_REQUIRED",
                )
            update["not_required_reason"] = reason
            update["not_applicable_audit_reason"] = audit
        elif app in ("REQUIRED", "UNKNOWN"):
            unset_na_metadata = True

    if len(update) <= 1 and not unset_na_metadata:
        return {"message": "No updates", "requirement_id": requirement_id}

    # Set status from deterministic rule when expiry or applicability changed
    merged = {**req, **update}
    if unset_na_metadata:
        merged["not_required_reason"] = None
        merged["not_applicable_audit_reason"] = None
    update["status"] = get_computed_status(merged, property_doc=prop_row, client_doc=client_row)

    mongo_update: Dict[str, Any] = {"$set": update}
    if unset_na_metadata:
        mongo_update["$unset"] = {"not_required_reason": "", "not_applicable_audit_reason": ""}

    await db.requirements.update_one(
        {"requirement_id": requirement_id, "property_id": property_id, "client_id": user["client_id"]},
        mongo_update,
    )

    from services.requirement_evidence_authority import sync_requirement_evidence_authority
    from services.requirement_transition_observability import (
        attach_downstream_trigger_observation,
        ensure_requirement_transition_correlation_id,
    )

    transition_fanout: Dict[str, Any] = {}
    recalc_correlation_id = f"REQUIREMENT_UPDATED:{requirement_id}"
    sync_correlation_id = ensure_requirement_transition_correlation_id(
        requirement_id=str(requirement_id),
        property_id=str(property_id),
        client_id=str(user.get("client_id") or ""),
        correlation_id=recalc_correlation_id,
    )
    await sync_requirement_evidence_authority(
        db,
        requirement_id,
        property_id_hint=property_id,
        correlation_id=sync_correlation_id,
        transition_origin="routes.properties.patch_requirement",
        transition_observability_out=transition_fanout,
    )

    fields_changed: List[str] = []
    if data.confirmed_expiry_date is not None:
        fields_changed.append("confirmed_expiry_date")
    if data.issue_date is not None:
        fields_changed.append("issue_date")
    if data.certificate_number is not None:
        fields_changed.append("certificate_number")
    if data.applicability is not None:
        fields_changed.append("applicability")
        app_fc = data.applicability.strip().upper()
        if app_fc in ("REQUIRED", "UNKNOWN"):
            fields_changed.extend(["not_required_reason", "not_applicable_audit_reason"])
    if data.not_required_reason is not None and str(data.not_required_reason).strip():
        fields_changed.append("not_required_reason")
    if data.not_applicable_audit_reason is not None and str(data.not_applicable_audit_reason).strip():
        fields_changed.append("not_applicable_audit_reason")

    await create_audit_log(
        action=AuditAction.REQUIREMENT_ACTION_TRIGGERED,
        actor_id=user.get("portal_user_id"),
        client_id=user["client_id"],
        resource_type="requirement",
        resource_id=requirement_id,
        metadata={
            "event": "client_patch_requirement",
            "mutation_source": "routes.properties.patch_requirement",
            "property_id": property_id,
            "requirement_id": requirement_id,
            "fields_changed": fields_changed,
            "status_before": req.get("status"),
            "status_after": update.get("status"),
            "correlation_id": recalc_correlation_id,
        },
    )

    # Recalculate property compliance when requirement expiry/status changes (e.g. confirm details later)
    from services.compliance_recalc_queue import enqueue_compliance_recalc, TRIGGER_PROPERTY_UPDATED, ACTOR_CLIENT

    recalc_result = None
    recalc_exc: Optional[Exception] = None
    try:
        recalc_result = await enqueue_compliance_recalc(
            property_id=property_id,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_PROPERTY_UPDATED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=recalc_correlation_id,
        )
    except Exception as exc:
        recalc_exc = exc
        logger.warning("enqueue_compliance_recalc after patch_requirement failed: %s", exc)
    if transition_fanout:
        attach_downstream_trigger_observation(
            transition_fanout,
            downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
            trigger_mode="async_queue",
            propagation_stage="post_authority_sync",
            downstream_correlation_id=getattr(recalc_result, "correlation_id", None) if recalc_result is not None else recalc_correlation_id,
            trigger_origin="routes.properties.patch_requirement",
            enqueue_result=recalc_result,
            enqueue_exc=recalc_exc,
        )
    try:
        from services.score_events_service import write_score_event, EVENT_REQUIREMENT_STATUS_CHANGED, ACTOR_ROLE_CLIENT
        await write_score_event(
            client_id=user["client_id"],
            event_type=EVENT_REQUIREMENT_STATUS_CHANGED,
            actor_user_id=user.get("portal_user_id"),
            actor_role=ACTOR_ROLE_CLIENT,
            property_id=property_id,
            requirement_id=requirement_id,
            metadata={"status_before": req.get("status"), "status_after": update.get("status"), "due_date": update.get("due_date")},
        )
    except Exception as ev_err:
        logger.debug("Score event REQUIREMENT_STATUS_CHANGED skip: %s", ev_err)

    return {"message": "Requirement updated", "requirement_id": requirement_id}


@router.get("/list")
async def list_properties(request: Request):
    """List all properties for the authenticated client.
    
    This is a convenience endpoint that returns the same data
    as the dashboard endpoint.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        properties = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        client_row = await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0}) or {}
        all_reqs = await db.requirements.find(
            {"client_id": user["client_id"]},
            {"_id": 0},
        ).to_list(2000)

        all_reqs = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            requirements=all_reqs,
            client_doc=client_row,
            properties=properties,
        )
        projected_reqs = [project_requirement_row_client_runtime(r) for r in all_reqs]
        by_pid: Dict[str, List[Dict[str, Any]]] = {}
        for r in projected_reqs:
            pid = r.get("property_id")
            if not pid:
                continue
            by_pid.setdefault(str(pid), []).append(r)

        for prop in properties:
            requirements = by_pid.get(str(prop.get("property_id")), [])
            prop["requirements_count"] = len(requirements)
            prop["compliant_count"] = sum(1 for r in requirements if r.get("status") == "COMPLIANT")
            prop["overdue_count"] = sum(1 for r in requirements if r.get("status") == "OVERDUE")
        
        return {"properties": properties}
    
    except Exception as e:
        logger.error(f"List properties error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load properties"
        )


class BulkPropertyItem(BaseModel):
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    property_type: str = "residential"
    number_of_units: int = 1
    # Optional per-row override from CSV/import source.
    jurisdiction: Optional[str] = Field(None, description="Scotland | England | Wales | Northern Ireland")


class BulkImportRequest(BaseModel):
    properties: List[BulkPropertyItem]


def _resolve_bulk_import_jurisdiction(raw_jurisdiction: Optional[str], client_default_jurisdiction: Optional[str]) -> Optional[str]:
    """
    Resolve import-row jurisdiction safely for mixed portfolios.

    Order:
      1) Explicit per-row jurisdiction (if valid)
      2) Client default jurisdiction (if valid)
      3) None (system fallback only at scoring-time if both missing/invalid)
    """
    from services.compliance_rules_registry import canonicalize_uk_portfolio_label

    raw = str(raw_jurisdiction or "").strip()
    row_label = canonicalize_uk_portfolio_label(raw)
    if raw and not row_label:
        raise ValueError("jurisdiction must be Scotland, England, Wales, or Northern Ireland when provided")
    if row_label:
        return row_label
    return canonicalize_uk_portfolio_label(client_default_jurisdiction)


@router.post("/bulk-import")
async def bulk_import_properties(request: Request, data: BulkImportRequest):
    """Import multiple properties from a list (e.g., parsed CSV data).
    
    Accepts a list of property objects and creates them with requirements.
    Useful for letting agents managing multiple properties.
    
    Returns summary of successful and failed imports.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        from services.provisioning import ProvisioningService
        
        # Verify client is provisioned
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not client or client["onboarding_status"] != "PROVISIONED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account must be fully provisioned to add properties"
            )

        # Property cap enforcement (plan_registry canonical) – count only active properties
        active_count = await db.properties.count_documents({
            "client_id": user["client_id"],
            "$or": [{"is_active": True}, {"is_active": {"$exists": False}}],
        })
        import_count = len(data.properties)
        from services.plan_registry import plan_registry
        allowed, error_msg, error_details = await plan_registry.enforce_property_limit(
            user["client_id"], active_count + import_count
        )
        if not allowed:
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole(user["role"]),
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                metadata={
                    "action_type": "PLAN_LIMIT_EXCEEDED",
                    "feature": "property_bulk_import",
                    "current_count": active_count,
                    "import_count": import_count,
                },
            )
            detail = dict(error_details or {})
            detail["error_code"] = "PLAN_LIMIT"
            detail["message"] = detail.get("message") or error_msg
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )

        results = {
            "total": len(data.properties),
            "successful": 0,
            "failed": 0,
            "errors": [],
            "created_properties": []
        }

        provisioning = ProvisioningService()
        
        for idx, prop_data in enumerate(data.properties):
            try:
                # Validate required fields
                if not prop_data.address_line_1 or not prop_data.city or not prop_data.postcode:
                    results["failed"] += 1
                    results["errors"].append({
                        "row": idx + 1,
                        "error": "Missing required field (address_line_1, city, or postcode)"
                    })
                    continue
                
                # Check for duplicate address
                existing = await db.properties.find_one({
                    "client_id": user["client_id"],
                    "address_line_1": prop_data.address_line_1,
                    "postcode": prop_data.postcode
                })
                
                if existing:
                    results["failed"] += 1
                    results["errors"].append({
                        "row": idx + 1,
                        "address": f"{prop_data.address_line_1}, {prop_data.postcode}",
                        "error": "Property already exists"
                    })
                    continue
                
                prop_jurisdiction = _resolve_bulk_import_jurisdiction(
                    prop_data.jurisdiction,
                    client.get("default_jurisdiction"),
                )

                # Create property
                property_obj = Property(
                    client_id=user["client_id"],
                    address_line_1=prop_data.address_line_1,
                    address_line_2=prop_data.address_line_2,
                    city=prop_data.city,
                    postcode=prop_data.postcode,
                    property_type=prop_data.property_type,
                    number_of_units=prop_data.number_of_units,
                    compliance_status=ComplianceStatus.RED,
                    jurisdiction=prop_jurisdiction,
                )
                
                prop_doc = property_obj.model_dump()
                await db.properties.insert_one(prop_doc)
                
                # Generate requirements using internal method
                req_count = 0
                try:
                    await provisioning._generate_requirements(
                        client_id=user["client_id"],
                        property_id=property_obj.property_id
                    )
                    # Count generated requirements
                    req_count = await db.requirements.count_documents({
                        "property_id": property_obj.property_id
                    })
                except Exception as req_err:
                    logger.warning(f"Failed to generate requirements for {property_obj.property_id}: {req_err}")
                
                results["successful"] += 1
                results["created_properties"].append({
                    "property_id": property_obj.property_id,
                    "address": f"{prop_data.address_line_1}, {prop_data.city}",
                    "jurisdiction": prop_jurisdiction,
                    "requirements_created": req_count
                })
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "row": idx + 1,
                    "error": str(e)
                })
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="property",
            metadata={
                "action": "bulk_import",
                "total": results["total"],
                "successful": results["successful"],
                "failed": results["failed"]
            }
        )
        
        logger.info(f"Bulk import: {results['successful']}/{results['total']} properties created for {user['email']}")
        
        return {
            "message": f"Imported {results['successful']} of {results['total']} properties",
            "summary": results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk import error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import properties"
        )



@router.get("/upcoming-deadlines")
async def get_upcoming_deadlines(request: Request, days: int = 30):
    """Get upcoming compliance deadlines for dashboard widget."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        from datetime import timedelta
        
        # Get all requirements for client
        requirements = await db.requirements.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        props_all = await db.properties.find({"client_id": user["client_id"]}, {"_id": 0}).to_list(1000)
        client_row_ud = await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0}) or {}

        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            requirements=requirements,
            client_doc=client_row_ud,
            properties=props_all,
        )
        requirements = [project_requirement_row_client_runtime(r) for r in requirements]

        # Filter for upcoming deadlines
        now = datetime.now(timezone.utc)
        deadline_threshold = now + timedelta(days=days)
        
        upcoming = []
        for req in requirements:
            if req.get("client_surface_visible") is False:
                continue
            if not is_included_for_calendar(req):
                continue
            due_date = get_effective_expiry_date(req)
            if due_date is None or not (now <= due_date <= deadline_threshold):
                continue
            # Get property details
            prop = await db.properties.find_one(
                {"property_id": req["property_id"]},
                {"_id": 0}
            )
            days_until_due = (due_date - now).days
            upcoming.append({
                "requirement_id": req["requirement_id"],
                "description": req.get("description", ""),
                "due_date": due_date.isoformat(),
                "days_until_due": days_until_due,
                "status": req.get("status", "PENDING"),
                "property_address": f"{prop['address_line_1']}, {prop['city']}" if prop else "Unknown",
                "property_id": req["property_id"]
            })
        
        # Sort by due date
        upcoming.sort(key=lambda x: x["days_until_due"])
        
        return {
            "upcoming_deadlines": upcoming[:10],  # Return top 10
            "total_upcoming": len(upcoming)
        }
    
    except Exception as e:
        logger.error(f"Get upcoming deadlines error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load upcoming deadlines"
        )


@router.get("/{property_id}/requirements")
async def get_property_requirements_api(request: Request, property_id: str):
    """List enriched requirements for one property (same shape as GET /api/client/properties/{id}/requirements)."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    requirements = await db.requirements.find(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0},
    ).to_list(100)

    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=user["client_id"],
        requirements=requirements,
        client_doc=await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0}) or {},
        properties=[prop],
    )
    requirements = [project_requirement_row_client_runtime(r) for r in requirements]
    from services.requirement_truth import enrich_requirements_for_client

    enriched, presentation = await enrich_requirements_for_client(db, user["client_id"], requirements)
    enriched = [r for r in enriched if r.get("client_surface_visible", True)]
    return {"requirements": enriched, "presentation": presentation}


@router.post("/{property_id}/requirements/sync")
async def sync_property_requirements_from_registry(request: Request, property_id: str):
    """Re-run catalog registry materialisation for this property (idempotent upsert + obsolete reconcile)."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    from services.requirement_materialization_service import materialize_requirements_for_property
    from services.provisioning import provisioning_service
    from services.compliance_recalc_queue import enqueue_compliance_recalc, TRIGGER_PROPERTY_UPDATED, ACTOR_CLIENT

    result = await materialize_requirements_for_property(user["client_id"], property_id, reconcile_obsolete=True)
    await provisioning_service._update_property_compliance(property_id)
    await enqueue_compliance_recalc(
        property_id=property_id,
        client_id=user["client_id"],
        trigger_reason=TRIGGER_PROPERTY_UPDATED,
        actor_type=ACTOR_CLIENT,
        actor_id=user.get("portal_user_id"),
        correlation_id=f"REQUIREMENTS_SYNC:{property_id}",
    )
    return {"message": "Requirements synchronized", **(result or {})}
