"""Advanced Reporting Service - Generate PDF and CSV reports for compliance data.

Report Types:
1. Compliance Status Summary - Overview of property compliance
2. Requirements by Property - Detailed requirements list
3. Audit Log Extract - Admin-only audit trail
"""
from database import database
from models import AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import csv
import io
import logging

logger = logging.getLogger(__name__)


class ReportingService:
    """Generate compliance reports in PDF and CSV formats."""
    
    def __init__(self):
        self.db = None
    
    async def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    async def generate_compliance_summary_report(
        self,
        client_id: str,
        format: str = "csv",
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Generate compliance status summary report.
        
        Includes:
        - Overall compliance statistics
        - Property-by-property status
        - Upcoming expirations
        """
        db = await self._get_db()
        
        # Get client info
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise ValueError("Client not found")
        
        # Get properties
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(1000)
        
        # Get requirements
        requirements = await db.requirements.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(10000)
        
        # Calculate statistics
        total_properties = len(properties)
        green_count = sum(1 for p in properties if p.get("compliance_status") == "GREEN")
        amber_count = sum(1 for p in properties if p.get("compliance_status") == "AMBER")
        red_count = sum(1 for p in properties if p.get("compliance_status") == "RED")
        
        total_requirements = len(requirements)
        compliant_count = sum(1 for r in requirements if r.get("status") == "COMPLIANT")
        pending_count = sum(1 for r in requirements if r.get("status") == "PENDING")
        overdue_count = sum(1 for r in requirements if r.get("status") == "OVERDUE")
        expiring_soon_count = sum(1 for r in requirements if r.get("status") == "EXPIRING_SOON")
        
        # Get expiring in next 30/60/90 days
        now = datetime.now(timezone.utc)
        thirty_days = (now + timedelta(days=30)).isoformat()
        sixty_days = (now + timedelta(days=60)).isoformat()
        ninety_days = (now + timedelta(days=90)).isoformat()
        
        expiring_30 = sum(1 for r in requirements 
                         if r.get("due_date") and r["due_date"] <= thirty_days and r["due_date"] >= now.isoformat())
        expiring_60 = sum(1 for r in requirements 
                         if r.get("due_date") and r["due_date"] <= sixty_days and r["due_date"] >= now.isoformat())
        expiring_90 = sum(1 for r in requirements 
                         if r.get("due_date") and r["due_date"] <= ninety_days and r["due_date"] >= now.isoformat())
        
        report_data = {
            "report_type": "Compliance Status Summary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "client": {
                "name": client.get("full_name"),
                "email": client.get("email"),
                "company": client.get("company_name")
            },
            "summary": {
                "total_properties": total_properties,
                "compliance_breakdown": {
                    "green": green_count,
                    "amber": amber_count,
                    "red": red_count
                },
                "compliance_rate": round((green_count / total_properties * 100), 1) if total_properties > 0 else 0,
                "total_requirements": total_requirements,
                "requirements_breakdown": {
                    "compliant": compliant_count,
                    "pending": pending_count,
                    "overdue": overdue_count,
                    "expiring_soon": expiring_soon_count
                },
                "expiring_next_30_days": expiring_30,
                "expiring_next_60_days": expiring_60,
                "expiring_next_90_days": expiring_90
            }
        }
        
        if include_details:
            # Add property details
            property_details = []
            for prop in properties:
                prop_reqs = [r for r in requirements if r.get("property_id") == prop["property_id"]]
                property_details.append({
                    "address": f"{prop.get('address_line_1', '')}, {prop.get('city', '')} {prop.get('postcode', '')}",
                    "property_type": prop.get("property_type", "N/A"),
                    "compliance_status": prop.get("compliance_status", "UNKNOWN"),
                    "total_requirements": len(prop_reqs),
                    "compliant": sum(1 for r in prop_reqs if r.get("status") == "COMPLIANT"),
                    "overdue": sum(1 for r in prop_reqs if r.get("status") == "OVERDUE")
                })
            report_data["properties"] = property_details
        
        if format == "csv":
            return self._generate_compliance_csv(report_data)
        else:
            return self._generate_compliance_pdf_data(report_data)
    
    async def generate_requirements_report(
        self,
        client_id: str,
        property_id: Optional[str] = None,
        format: str = "csv"
    ) -> Dict[str, Any]:
        """
        Generate detailed requirements report.
        
        Includes:
        - All requirements with status
        - Due dates and last updated
        - Linked documents
        """
        db = await self._get_db()
        
        # Build query
        query = {"client_id": client_id}
        if property_id:
            query["property_id"] = property_id
        
        requirements = await db.requirements.find(query, {"_id": 0}).to_list(10000)
        
        # Get properties for address info
        prop_ids = list(set(r.get("property_id") for r in requirements if r.get("property_id")))
        properties = await db.properties.find(
            {"property_id": {"$in": prop_ids}},
            {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1}
        ).to_list(1000)
        prop_map = {p["property_id"]: p for p in properties}
        
        # Get documents linked to requirements
        req_ids = [r.get("requirement_id") for r in requirements]
        documents = await db.documents.find(
            {"requirement_id": {"$in": req_ids}},
            {"_id": 0, "requirement_id": 1, "file_name": 1, "status": 1, "uploaded_at": 1}
        ).to_list(10000)
        doc_map = {}
        for doc in documents:
            req_id = doc.get("requirement_id")
            if req_id not in doc_map:
                doc_map[req_id] = []
            doc_map[req_id].append(doc)
        
        report_data = {
            "report_type": "Requirements Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "requirements": []
        }
        
        for req in requirements:
            prop = prop_map.get(req.get("property_id"), {})
            docs = doc_map.get(req.get("requirement_id"), [])
            
            report_data["requirements"].append({
                "requirement_id": req.get("requirement_id"),
                "property_address": f"{prop.get('address_line_1', 'N/A')}, {prop.get('city', '')} {prop.get('postcode', '')}",
                "requirement_type": req.get("requirement_type", "N/A"),
                "description": req.get("description", "N/A"),
                "status": req.get("status", "UNKNOWN"),
                "due_date": req.get("due_date", "N/A")[:10] if req.get("due_date") else "N/A",
                "frequency_days": req.get("frequency_days", "N/A"),
                "documents_count": len(docs),
                "latest_document": docs[-1].get("file_name") if docs else "None",
                "latest_doc_status": docs[-1].get("status") if docs else "N/A"
            })
        
        if format == "csv":
            return self._generate_requirements_csv(report_data)
        else:
            return self._generate_requirements_pdf_data(report_data)
    
    async def generate_audit_log_report(
        self,
        client_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        actions: Optional[List[str]] = None,
        format: str = "csv",
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Generate audit log extract report (Admin-only).
        
        Includes:
        - Filtered audit trail
        - Action types, actors, timestamps
        - Resource changes
        """
        db = await self._get_db()
        
        # Build query
        query = {}
        if client_id:
            query["client_id"] = client_id
        if start_date:
            if "timestamp" not in query:
                query["timestamp"] = {}
            query["timestamp"]["$gte"] = start_date
        if end_date:
            if "timestamp" not in query:
                query["timestamp"] = {}
            query["timestamp"]["$lte"] = end_date
        if actions:
            query["action"] = {"$in": actions}
        
        logs = await db.audit_logs.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        report_data = {
            "report_type": "Audit Log Extract",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": {
                "client_id": client_id,
                "start_date": start_date,
                "end_date": end_date,
                "actions": actions
            },
            "total_records": len(logs),
            "logs": []
        }
        
        for log in logs:
            report_data["logs"].append({
                "timestamp": log.get("timestamp", "N/A"),
                "action": log.get("action", "N/A"),
                "actor_id": log.get("actor_id", "System"),
                "actor_role": log.get("actor_role", "N/A"),
                "resource_type": log.get("resource_type", "N/A"),
                "resource_id": log.get("resource_id", "N/A"),
                "client_id": log.get("client_id", "N/A"),
                "has_before_state": "Yes" if log.get("before_state") else "No",
                "has_after_state": "Yes" if log.get("after_state") else "No",
                "metadata_summary": str(log.get("metadata", {}))[:100] if log.get("metadata") else "N/A"
            })
        
        if format == "csv":
            return self._generate_audit_csv(report_data)
        else:
            return self._generate_audit_pdf_data(report_data)
    
    def _generate_compliance_csv(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate CSV for compliance summary."""
        output = io.StringIO()
        
        # Write header info
        output.write(f"Report: {data['report_type']}\n")
        output.write(f"Generated: {data['generated_at']}\n")
        output.write(f"Client: {data['client']['name']}\n\n")
        
        # Summary section
        output.write("=== SUMMARY ===\n")
        summary = data['summary']
        output.write(f"Total Properties,{summary['total_properties']}\n")
        output.write(f"Compliance Rate,{summary['compliance_rate']}%\n")
        output.write(f"Green (Compliant),{summary['compliance_breakdown']['green']}\n")
        output.write(f"Amber (Attention),{summary['compliance_breakdown']['amber']}\n")
        output.write(f"Red (Action Required),{summary['compliance_breakdown']['red']}\n\n")
        
        output.write(f"Total Requirements,{summary['total_requirements']}\n")
        output.write(f"Compliant,{summary['requirements_breakdown']['compliant']}\n")
        output.write(f"Pending,{summary['requirements_breakdown']['pending']}\n")
        output.write(f"Overdue,{summary['requirements_breakdown']['overdue']}\n")
        output.write(f"Expiring Soon,{summary['requirements_breakdown']['expiring_soon']}\n\n")
        
        output.write(f"Expiring in 30 days,{summary['expiring_next_30_days']}\n")
        output.write(f"Expiring in 60 days,{summary['expiring_next_60_days']}\n")
        output.write(f"Expiring in 90 days,{summary['expiring_next_90_days']}\n\n")
        
        # Properties section
        if 'properties' in data:
            output.write("=== PROPERTIES ===\n")
            writer = csv.DictWriter(output, fieldnames=[
                'address', 'property_type', 'compliance_status', 
                'total_requirements', 'compliant', 'overdue'
            ])
            writer.writeheader()
            for prop in data['properties']:
                writer.writerow(prop)
        
        return {
            "content": output.getvalue(),
            "filename": f"compliance_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "content_type": "text/csv"
        }
    
    def _generate_requirements_csv(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate CSV for requirements report."""
        output = io.StringIO()
        
        output.write(f"Report: {data['report_type']}\n")
        output.write(f"Generated: {data['generated_at']}\n")
        output.write(f"Total Requirements: {len(data['requirements'])}\n\n")
        
        writer = csv.DictWriter(output, fieldnames=[
            'property_address', 'requirement_type', 'description', 'status',
            'due_date', 'frequency_days', 'documents_count', 
            'latest_document', 'latest_doc_status'
        ])
        writer.writeheader()
        
        for req in data['requirements']:
            # Remove requirement_id from output
            row = {k: v for k, v in req.items() if k != 'requirement_id'}
            writer.writerow(row)
        
        return {
            "content": output.getvalue(),
            "filename": f"requirements_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "content_type": "text/csv"
        }
    
    def _generate_audit_csv(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate CSV for audit log extract."""
        output = io.StringIO()
        
        output.write(f"Report: {data['report_type']}\n")
        output.write(f"Generated: {data['generated_at']}\n")
        output.write(f"Total Records: {data['total_records']}\n\n")
        
        if data['logs']:
            writer = csv.DictWriter(output, fieldnames=[
                'timestamp', 'action', 'actor_id', 'actor_role',
                'resource_type', 'resource_id', 'client_id',
                'has_before_state', 'has_after_state', 'metadata_summary'
            ])
            writer.writeheader()
            
            for log in data['logs']:
                writer.writerow(log)
        else:
            output.write("No audit logs found for the specified criteria.\n")
        
        return {
            "content": output.getvalue(),
            "filename": f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "content_type": "text/csv"
        }
    
    def _generate_compliance_pdf_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate structured data for PDF rendering (client-side)."""
        return {
            "format": "pdf",
            "data": data,
            "filename": f"compliance_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        }
    
    def _generate_requirements_pdf_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate structured data for PDF rendering (client-side)."""
        return {
            "format": "pdf",
            "data": data,
            "filename": f"requirements_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        }
    
    def _generate_audit_pdf_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate structured data for PDF rendering (client-side)."""
        return {
            "format": "pdf",
            "data": data,
            "filename": f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        }


# Singleton instance
reporting_service = ReportingService()
