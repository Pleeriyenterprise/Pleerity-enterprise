"""Requirement Rules Management Routes - Admin only"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import admin_route_guard
from models import RequirementRule, RuleCategory, PropertyTypeApplicability, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/rules", tags=["Admin - Rules"])

# Default rules to seed the database
DEFAULT_RULES = [
    {
        "rule_type": "gas_safety",
        "name": "Gas Safety Certificate",
        "description": "Annual gas safety inspection required for all properties with gas appliances",
        "category": RuleCategory.SAFETY.value,
        "frequency_days": 365,
        "warning_days": 30,
        "applicable_to": PropertyTypeApplicability.ALL.value,
        "is_mandatory": True,
        "risk_weight": 5,
        "regulatory_reference": "Gas Safety (Installation and Use) Regulations 1998"
    },
    {
        "rule_type": "eicr",
        "name": "Electrical Installation Condition Report",
        "description": "Electrical safety inspection required every 5 years",
        "category": RuleCategory.ELECTRICAL.value,
        "frequency_days": 1825,
        "warning_days": 60,
        "applicable_to": PropertyTypeApplicability.ALL.value,
        "is_mandatory": True,
        "risk_weight": 5,
        "regulatory_reference": "The Electrical Safety Standards in the Private Rented Sector (England) Regulations 2020"
    },
    {
        "rule_type": "epc",
        "name": "Energy Performance Certificate",
        "description": "Valid EPC required, minimum rating E for rental properties",
        "category": RuleCategory.ENERGY.value,
        "frequency_days": 3650,
        "warning_days": 90,
        "applicable_to": PropertyTypeApplicability.ALL.value,
        "is_mandatory": True,
        "risk_weight": 3,
        "regulatory_reference": "The Energy Efficiency (Private Rented Property) (England and Wales) Regulations 2015"
    },
    {
        "rule_type": "fire_alarm",
        "name": "Fire Alarm Inspection",
        "description": "Annual smoke and carbon monoxide alarm checks",
        "category": RuleCategory.FIRE.value,
        "frequency_days": 365,
        "warning_days": 30,
        "applicable_to": PropertyTypeApplicability.ALL.value,
        "is_mandatory": True,
        "risk_weight": 5,
        "regulatory_reference": "Smoke and Carbon Monoxide Alarm (Amendment) Regulations 2022"
    },
    {
        "rule_type": "legionella",
        "name": "Legionella Risk Assessment",
        "description": "Risk assessment for legionella bacteria in water systems",
        "category": RuleCategory.HEALTH.value,
        "frequency_days": 730,
        "warning_days": 60,
        "applicable_to": PropertyTypeApplicability.ALL.value,
        "is_mandatory": True,
        "risk_weight": 4,
        "regulatory_reference": "Health and Safety at Work Act 1974"
    },
    {
        "rule_type": "hmo_license",
        "name": "HMO License",
        "description": "Mandatory licensing for Houses in Multiple Occupation",
        "category": RuleCategory.REGULATORY.value,
        "frequency_days": 1825,
        "warning_days": 90,
        "applicable_to": PropertyTypeApplicability.HMO.value,
        "is_mandatory": True,
        "risk_weight": 5,
        "regulatory_reference": "Housing Act 2004"
    },
    {
        "rule_type": "portable_appliance_test",
        "name": "Portable Appliance Testing (PAT)",
        "description": "Testing of portable electrical appliances",
        "category": RuleCategory.ELECTRICAL.value,
        "frequency_days": 365,
        "warning_days": 30,
        "applicable_to": PropertyTypeApplicability.ALL.value,
        "is_mandatory": False,
        "risk_weight": 2,
        "regulatory_reference": "The Electricity at Work Regulations 1989"
    }
]


@router.get("")
async def list_rules(
    request: Request,
    active_only: bool = True,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """List all requirement rules."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Build query
        query = {}
        if active_only:
            query["is_active"] = True
        if category:
            query["category"] = category
        
        # Get rules
        rules = await db.requirement_rules.find(
            query,
            {"_id": 0}
        ).sort("category", 1).skip(skip).limit(limit).to_list(limit)
        
        total = await db.requirement_rules.count_documents(query)
        
        return {
            "rules": rules,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    except Exception as e:
        logger.error(f"List rules error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list rules"
        )


@router.get("/categories")
async def get_categories(request: Request):
    """Get available rule categories."""
    await admin_route_guard(request)
    
    return {
        "categories": [
            {"value": c.value, "label": c.value.replace("_", " ").title()}
            for c in RuleCategory
        ],
        "property_types": [
            {"value": p.value, "label": p.value.replace("_", " ").title()}
            for p in PropertyTypeApplicability
        ]
    }


@router.get("/{rule_id}")
async def get_rule(request: Request, rule_id: str):
    """Get a specific rule by ID."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        rule = await db.requirement_rules.find_one(
            {"rule_id": rule_id},
            {"_id": 0}
        )
        
        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rule not found"
            )
        
        return rule
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get rule error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get rule"
        )


@router.post("")
async def create_rule(request: Request):
    """Create a new requirement rule."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        body = await request.json()
        
        # Check if rule_type already exists
        existing = await db.requirement_rules.find_one(
            {"rule_type": body.get("rule_type")}
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rule with type '{body.get('rule_type')}' already exists"
            )
        
        # Create rule
        rule = RequirementRule(
            rule_type=body.get("rule_type"),
            name=body.get("name"),
            description=body.get("description"),
            category=RuleCategory(body.get("category", "OTHER")),
            frequency_days=body.get("frequency_days", 365),
            warning_days=body.get("warning_days", 30),
            applicable_to=PropertyTypeApplicability(body.get("applicable_to", "ALL")),
            is_mandatory=body.get("is_mandatory", True),
            is_active=body.get("is_active", True),
            risk_weight=body.get("risk_weight", 1),
            regulatory_reference=body.get("regulatory_reference"),
            notes=body.get("notes"),
            created_by=user["portal_user_id"]
        )
        
        doc = rule.model_dump()
        for key in ["created_at", "updated_at"]:
            if doc.get(key):
                doc[key] = doc[key].isoformat()
        
        await db.requirement_rules.insert_one(doc)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            metadata={
                "action": "rule_created",
                "rule_id": rule.rule_id,
                "rule_type": rule.rule_type,
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Rule created: {rule.rule_type} by {user['email']}")
        
        return {
            "message": "Rule created successfully",
            "rule_id": rule.rule_id,
            "rule": doc
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create rule error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rule"
        )


@router.put("/{rule_id}")
async def update_rule(request: Request, rule_id: str):
    """Update an existing requirement rule."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        body = await request.json()
        
        # Get existing rule
        existing = await db.requirement_rules.find_one(
            {"rule_id": rule_id},
            {"_id": 0}
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rule not found"
            )
        
        # Build update
        update_fields = {}
        allowed_fields = [
            "name", "description", "category", "frequency_days", "warning_days",
            "applicable_to", "is_mandatory", "is_active", "risk_weight",
            "regulatory_reference", "notes"
        ]
        
        for field in allowed_fields:
            if field in body:
                update_fields[field] = body[field]
        
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.requirement_rules.update_one(
            {"rule_id": rule_id},
            {"$set": update_fields}
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            metadata={
                "action": "rule_updated",
                "rule_id": rule_id,
                "updated_fields": list(update_fields.keys()),
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Rule updated: {rule_id} by {user['email']}")
        
        # Get updated rule
        updated = await db.requirement_rules.find_one(
            {"rule_id": rule_id},
            {"_id": 0}
        )
        
        return {
            "message": "Rule updated successfully",
            "rule": updated
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update rule error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update rule"
        )


@router.delete("/{rule_id}")
async def delete_rule(request: Request, rule_id: str):
    """Soft-delete a requirement rule (sets is_active to False)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get existing rule
        existing = await db.requirement_rules.find_one(
            {"rule_id": rule_id},
            {"_id": 0}
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rule not found"
            )
        
        # Soft delete
        await db.requirement_rules.update_one(
            {"rule_id": rule_id},
            {"$set": {
                "is_active": False,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            metadata={
                "action": "rule_deleted",
                "rule_id": rule_id,
                "rule_type": existing["rule_type"],
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Rule deleted: {rule_id} by {user['email']}")
        
        return {"message": "Rule deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete rule error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete rule"
        )


@router.post("/seed")
async def seed_default_rules(request: Request):
    """Seed the database with default UK compliance rules."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        created_count = 0
        skipped_count = 0
        
        for rule_data in DEFAULT_RULES:
            # Check if rule already exists
            existing = await db.requirement_rules.find_one(
                {"rule_type": rule_data["rule_type"]}
            )
            
            if existing:
                skipped_count += 1
                continue
            
            # Create rule
            rule = RequirementRule(
                rule_type=rule_data["rule_type"],
                name=rule_data["name"],
                description=rule_data["description"],
                category=RuleCategory(rule_data["category"]),
                frequency_days=rule_data["frequency_days"],
                warning_days=rule_data["warning_days"],
                applicable_to=PropertyTypeApplicability(rule_data["applicable_to"]),
                is_mandatory=rule_data["is_mandatory"],
                risk_weight=rule_data["risk_weight"],
                regulatory_reference=rule_data.get("regulatory_reference"),
                created_by="SYSTEM"
            )
            
            doc = rule.model_dump()
            for key in ["created_at", "updated_at"]:
                if doc.get(key):
                    doc[key] = doc[key].isoformat()
            
            await db.requirement_rules.insert_one(doc)
            created_count += 1
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            metadata={
                "action": "rules_seeded",
                "created": created_count,
                "skipped": skipped_count,
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Rules seeded: {created_count} created, {skipped_count} skipped")
        
        return {
            "message": "Default rules seeded",
            "created": created_count,
            "skipped": skipped_count
        }
    
    except Exception as e:
        logger.error(f"Seed rules error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seed rules"
        )
