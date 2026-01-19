"""Compliance Pack Generation - Plan-gated feature for PLAN_6_15"""
from database import database
from models import BillingPlan, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class CompliancePackGenerator:
    async def generate_pack(self, client_id: str) -> dict:
        """Generate compliance pack for client (PLAN_6_15 only)."""
        db = database.get_db()
        
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise ValueError("Client not found")
        
        # Check plan eligibility
        if client["billing_plan"] != BillingPlan.PLAN_6_15.value:
            raise PermissionError("Compliance packs are only available for PLAN_6_15 subscribers")
        
        # Get all properties
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(100)
        
        pack_data = {
            "client": {
                "name": client["full_name"],
                "email": client["email"],
                "company": client.get("company_name"),
                "plan": client["billing_plan"]
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "properties": []
        }
        
        # Process each property
        for prop in properties:
            # Get requirements
            requirements = await db.requirements.find(
                {"property_id": prop["property_id"]},
                {"_id": 0}
            ).to_list(100)
            
            # Get documents
            documents = await db.documents.find(
                {"property_id": prop["property_id"]},
                {"_id": 0}
            ).to_list(100)
            
            # Calculate compliance metrics
            total_reqs = len(requirements)
            compliant = sum(1 for r in requirements if r["status"] == "COMPLIANT")
            overdue = sum(1 for r in requirements if r["status"] == "OVERDUE")
            expiring = sum(1 for r in requirements if r["status"] == "EXPIRING_SOON")
            
            compliance_percentage = (compliant / total_reqs * 100) if total_reqs > 0 else 0
            
            property_data = {
                "address": f"{prop['address_line_1']}, {prop['city']}, {prop['postcode']}",
                "compliance_status": prop["compliance_status"],
                "compliance_percentage": round(compliance_percentage, 1),
                "requirements": {
                    "total": total_reqs,
                    "compliant": compliant,
                    "overdue": overdue,
                    "expiring_soon": expiring
                },
                "documents": {
                    "total": len(documents),
                    "verified": sum(1 for d in documents if d["status"] == "VERIFIED"),
                    "pending": sum(1 for d in documents if d["status"] in ["PENDING", "UPLOADED"])
                },
                "requirements_detail": [
                    {
                        "type": r["description"],
                        "status": r["status"],
                        "due_date": r["due_date"],
                        "frequency_days": r["frequency_days"]
                    }
                    for r in requirements
                ]
            }
            
            pack_data["properties"].append(property_data)
        
        # Calculate overall compliance
        all_requirements = []
        for prop_data in pack_data["properties"]:
            all_requirements.extend(prop_data["requirements_detail"])
        
        total_compliance = sum(1 for r in all_requirements if r["status"] == "COMPLIANT")
        overall_percentage = (total_compliance / len(all_requirements) * 100) if all_requirements else 0
        
        pack_data["overall_compliance"] = {
            "percentage": round(overall_percentage, 1),
            "status": "GREEN" if overall_percentage >= 90 else "AMBER" if overall_percentage >= 70 else "RED",
            "total_properties": len(properties),
            "total_requirements": len(all_requirements)
        }
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            client_id=client_id,
            metadata={
                "action": "compliance_pack_generated",
                "properties_count": len(properties),
                "overall_compliance": overall_percentage
            }
        )
        
        logger.info(f"Compliance pack generated for client {client_id}")
        
        return pack_data

compliance_pack_generator = CompliancePackGenerator()
