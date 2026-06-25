"""Advanced Reporting Service - Generate PDF and CSV reports for compliance data.

Report Types:
1. Compliance Status Summary - Overview of property compliance
2. Requirements by Property - Detailed requirements list
3. Audit Log Extract - Admin-only audit trail
"""
from database import database
from models import AuditAction
from services.compliance_rules_registry import jurisdiction_attribution_for_property
from utils.audit import create_audit_log
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import csv
import io
import logging
from utils.expiry_utils import get_effective_expiry_date
from services.requirement_client_runtime_surface import (
    filter_requirement_rows_for_client_runtime_surfaces,
    client_portal_surface_visible_row,
    project_requirement_row_client_runtime,
    compute_client_portal_requirement_stats,
)
from services.reporting_semantics_v1 import (
    METRIC_SCORE_TRACKED,
    METRIC_TRACKED,
    async_reporting_disclosure,
    build_reporting_semantics_payload,
    compute_reporting_semantic_counts,
    csv_semantics_preamble_rows,
    load_score_projection_portal_rows,
)
from services.scoring_semantics_v1 import attach_semantics_contract, headline_score_display_for_export
from services.semantic_state_precedence_adapter import REPORT_EXPORT, observe_consumer_precedence_delta

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
        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=client_id,
            requirements=requirements,
            client_doc=client,
            properties=properties,
        )
        projected = [project_requirement_row_client_runtime(r) for r in requirements]
        portal_reqs = [r for r in projected if client_portal_surface_visible_row(r)]
        counts = compute_client_portal_requirement_stats(portal_reqs)

        # Calculate statistics
        total_properties = len(properties)
        green_count = sum(1 for p in properties if p.get("compliance_status") == "GREEN")
        amber_count = sum(1 for p in properties if p.get("compliance_status") == "AMBER")
        red_count = sum(1 for p in properties if p.get("compliance_status") == "RED")

        total_requirements = counts["total_requirements"]
        compliant_count = counts["compliant"]
        pending_count = counts["pending"]
        overdue_count = counts["overdue"]
        expiring_soon_count = counts["expiring_soon"]
        
        # Get expiring in next 30/60/90 days
        now = datetime.now(timezone.utc)
        thirty_days = (now + timedelta(days=30)).isoformat()
        sixty_days = (now + timedelta(days=60)).isoformat()
        ninety_days = (now + timedelta(days=90)).isoformat()
        
        expiring_30 = 0
        expiring_60 = 0
        expiring_90 = 0
        for r in portal_reqs:
            eff = get_effective_expiry_date(r)
            if eff is None:
                continue
            eff_iso = eff.isoformat()
            if eff_iso <= thirty_days and eff_iso >= now.isoformat():
                expiring_30 += 1
            if eff_iso <= sixty_days and eff_iso >= now.isoformat():
                expiring_60 += 1
            if eff_iso <= ninety_days and eff_iso >= now.isoformat():
                expiring_90 += 1
        
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
        from services.lifecycle_kpi_gates import attach_additive_lifecycle_kpi_fields

        attach_additive_lifecycle_kpi_fields(report_data["summary"], portal_reqs)
        try:
            from services.compliance_score import calculate_compliance_score

            cs = await calculate_compliance_score(client_id)
            report_data["summary"]["compliance_score_headline"] = {
                "score": cs.get("score"),
                "score_authority": cs.get("score_authority"),
                "score_status": cs.get("score_status"),
                "last_calculated_at": cs.get("last_calculated_at") or cs.get("portfolio_last_calculated_at"),
                "score_coverage": cs.get("score_coverage"),
                "score_status_message": cs.get("score_status_message"),
                "compliance_score_display": headline_score_display_for_export(
                    cs.get("score"), cs.get("score_status")
                ),
            }
        except Exception as e:
            logger.warning("compliance headline for compliance summary report: %s", e)
            report_data["summary"]["compliance_score_headline"] = {
                "score": None,
                "score_authority": "unavailable",
                "score_status": "unavailable",
                "last_calculated_at": None,
                "score_coverage": None,
                "score_status_message": None,
                "compliance_score_display": "N/A",
            }
        report_data = attach_semantics_contract(report_data)
        report_data["reporting_semantics"] = build_reporting_semantics_payload(
            compute_reporting_semantic_counts(portal_reqs)
        )
        ch = report_data["summary"].get("compliance_score_headline") or {}
        report_data["summary"]["async_reporting_disclosure"] = async_reporting_disclosure(
            score_status=ch.get("score_status"),
            score_status_message=ch.get("score_status_message"),
            last_calculated_at=ch.get("last_calculated_at"),
        )

        if include_details:
            # Add property details
            property_details = []
            client_doc = client or {}
            for prop in properties:
                prop_reqs = [
                    r
                    for r in portal_reqs
                    if r.get("property_id") == prop["property_id"]
                ]
                _att = jurisdiction_attribution_for_property(prop, client_doc)
                prop_counts = compute_client_portal_requirement_stats(prop_reqs)
                property_details.append({
                    "address": f"{prop.get('address_line_1', '')}, {prop.get('city', '')} {prop.get('postcode', '')}",
                    "property_type": prop.get("property_type", "N/A"),
                    "compliance_status": prop.get("compliance_status", "UNKNOWN"),
                    "total_requirements": prop_counts["total_requirements"],
                    "compliant": prop_counts["compliant"],
                    "overdue": prop_counts["overdue"],
                    "effective_jurisdiction_label": _att.get("effective_jurisdiction_label"),
                    "jurisdiction_source": _att.get("jurisdiction_source"),
                })
            report_data["properties"] = property_details

        report_data["portal_requirements"] = portal_reqs
        report_data["properties_portal"] = properties
        report_data["client_doc"] = client or {}
        report_data["client_row"] = client or {}
        
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
        
        client_row = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "default_jurisdiction": 1},
        )

        # Get properties for address info
        prop_ids = list(set(r.get("property_id") for r in requirements if r.get("property_id")))
        properties = await db.properties.find(
            {"property_id": {"$in": prop_ids}},
            {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1, "jurisdiction": 1}
        ).to_list(1000)
        if prop_ids:
            props_full = await db.properties.find(
                {"client_id": client_id, "property_id": {"$in": list(prop_ids)}},
                {"_id": 0},
            ).to_list(1000)
        else:
            props_full = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(1000)

        portal_reqs = await load_score_projection_portal_rows(
            db,
            client_id=client_id,
            client_doc=client_row or {},
            properties=props_full,
            requirements=requirements,
        )
        prop_map = {p["property_id"]: p for p in properties}
        
        # Get documents linked to requirements
        req_ids = [r.get("requirement_id") for r in portal_reqs]
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
            "requirements": [],
            "portal_requirements": portal_reqs,
            "properties_portal": props_full,
            "client_doc": client_row or {},
            "reporting_semantics": build_reporting_semantics_payload(
                compute_reporting_semantic_counts(portal_reqs)
            ),
        }
        
        client_doc = client_row or {}
        for proj in portal_reqs:
            req = proj
            try:
                sem = proj.get("semantic_state") or (
                    (proj.get("evidence_authority") or {}).get("semantic_state")
                    if isinstance(proj.get("evidence_authority"), dict)
                    else None
                )
                if sem:
                    observe_consumer_precedence_delta(
                        REPORT_EXPORT,
                        str(sem),
                        property_id=str(req.get("property_id") or ""),
                        requirement_id=str(req.get("requirement_id") or ""),
                    )
            except Exception:
                # Observe-only hook: never affect report generation.
                pass
            prop = prop_map.get(req.get("property_id"), {})
            docs = doc_map.get(req.get("requirement_id"), [])
            _att = jurisdiction_attribution_for_property(prop or {}, client_doc)
            due_iso = proj.get("due_date")
            due_out = "N/A"
            if due_iso:
                try:
                    due_out = datetime.fromisoformat(str(due_iso).replace("Z", "+00:00")).date().isoformat()
                except Exception:
                    due_out = str(due_iso)[:10]

            report_data["requirements"].append({
                "requirement_id": req.get("requirement_id"),
                "property_address": f"{prop.get('address_line_1', 'N/A')}, {prop.get('city', '')} {prop.get('postcode', '')}",
                "effective_jurisdiction_label": _att.get("effective_jurisdiction_label"),
                "jurisdiction_source": _att.get("jurisdiction_source"),
                "requirement_type": req.get("requirement_type", "N/A"),
                "description": req.get("description", "N/A"),
                "status": str(proj.get("status") or "PENDING").upper(),
                "due_date": due_out,
                "evidence_state": str(proj.get("evidence_state") or "UNKNOWN"),
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
        from services.report_human_language_v1 import (
            human_score_authority_label,
            human_score_status_label,
        )

        output = io.StringIO()
        
        # Write header info
        output.write(f"Report: {data['report_type']}\n")
        output.write(f"Generated: {data['generated_at']}\n")
        output.write(f"Client: {data['client']['name']}\n\n")
        ch = (data.get("summary") or {}).get("compliance_score_headline") or {}
        output.write("=== PORTFOLIO COMPLIANCE SCORE (AUTHORITATIVE HEADLINE) ===\n")
        output.write(f"Displayed score,{ch.get('compliance_score_display') or 'N/A'}\n")
        output.write(
            f"Score authority (human-readable),{human_score_authority_label(ch.get('score_authority'))}\n"
        )
        output.write(
            f"Score status (human-readable),{human_score_status_label(ch.get('score_status'))}\n"
        )
        output.write(f"last_calculated_at,{ch.get('last_calculated_at') or ''}\n")
        output.write(f"score_status_message,{ch.get('score_status_message') or ''}\n")
        output.write(
            "export_snapshot_note,CSV generated at Generated time above; headline uses persisted scores as of "
            "last_calculated_at (not live portal). Headline score is not a legal compliance determination and "
            "may differ from obligation completion rates below.\n"
        )
        sem = (data.get("reporting_semantics") or {}).get("counts") or {}
        async_disc = (data.get("summary") or {}).get("async_reporting_disclosure") or {}
        for msg in async_disc.get("messages") or []:
            output.write(f"async_score_note,{msg}\n")
        for row in csv_semantics_preamble_rows(sem, generated_at=data.get("generated_at", "")):
            output.write(",".join(str(c) for c in row) + "\n")
        from services.report_interpretation_v1 import how_to_read_csv_lines

        for line in how_to_read_csv_lines("compliance_summary"):
            output.write(line + "\n")
        output.write("\n")

        # Summary section
        output.write("=== SUMMARY ===\n")
        summary = data['summary']
        output.write(f"Total Properties,{summary['total_properties']}\n")
        output.write(f"Obligation satisfaction rate,{summary['compliance_rate']}%\n")
        output.write(f"Green (Favourable posture),{summary['compliance_breakdown']['green']}\n")
        output.write(f"Amber (Attention advised),{summary['compliance_breakdown']['amber']}\n")
        output.write(f"Red (Elevated attention),{summary['compliance_breakdown']['red']}\n\n")
        
        output.write(f"Total Requirements,{summary['total_requirements']}\n")
        output.write(
            f"Requirements satisfied in this report,{summary['requirements_breakdown']['compliant']}\n"
        )
        output.write(f"Pending,{summary['requirements_breakdown']['pending']}\n")
        output.write(f"Overdue,{summary['requirements_breakdown']['overdue']}\n")
        output.write(f"Expiring Soon,{summary['requirements_breakdown']['expiring_soon']}\n\n")

        breakdown = summary.get("lifecycle_kpi_breakdown")
        if breakdown and isinstance(breakdown, dict):
            from services.lifecycle_kpi_gates import (
                lifecycle_kpi_breakdown_report_entries,
                lifecycle_kpi_report_framing_note,
            )

            output.write("=== LIFECYCLE ATTENTION BREAKDOWN (SUPPLEMENTAL) ===\n")
            framing = lifecycle_kpi_report_framing_note(summary.get("lifecycle_kpi_effective_mode"))
            if framing:
                output.write(f"lifecycle_kpi_note,{framing}\n")
            output.write(
                f"lifecycle_kpi_effective_mode,{summary.get('lifecycle_kpi_effective_mode') or ''}\n"
            )
            for label, count in lifecycle_kpi_breakdown_report_entries(breakdown):
                output.write(f"{label},{count}\n")
            output.write("\n")
        
        output.write(f"Expiring in 30 days,{summary['expiring_next_30_days']}\n")
        output.write(f"Expiring in 60 days,{summary['expiring_next_60_days']}\n")
        output.write(f"Expiring in 90 days,{summary['expiring_next_90_days']}\n\n")
        
        from services.report_compliance_summary_executive import CSV_FORMAT_VERSION

        output.write(f"csv_format_version,{CSV_FORMAT_VERSION}\n\n")

        portal_reqs = data.get("portal_requirements") or []
        properties_portal = data.get("properties_portal") or []
        client_doc = data.get("client_doc") or {}
        if portal_reqs or properties_portal:
            from services.report_compliance_summary_executive import (
                CSV_PROPERTY_FIELDS,
                build_compliance_summary_executive_csv_rows,
            )
            from services.report_pdf_templates import compute_readiness_indicators

            gen_at = data.get("generated_at") or ""
            try:
                now_dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                now_dt = datetime.now(timezone.utc)
            readiness = compute_readiness_indicators(
                requirements=portal_reqs,
                properties=properties_portal,
                client_doc=client_doc,
                now=now_dt,
            )
            exec_rows = build_compliance_summary_executive_csv_rows(
                properties=properties_portal,
                requirements=portal_reqs,
                client_doc=client_doc,
                readiness=readiness,
            )
            output.write("=== PORTFOLIO POSTURE (EXECUTIVE VIEW) ===\n")
            writer = csv.DictWriter(output, fieldnames=CSV_PROPERTY_FIELDS)
            writer.writeheader()
            for row in exec_rows:
                writer.writerow(row)
            output.write("\n")
        
        return {
            "content": output.getvalue(),
            "filename": f"compliance_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "content_type": "text/csv",
            # For governed email digest (Phase 6) — never send ``content`` as the customer email body.
            "report_summary": dict(data["summary"]),
            "properties_snapshot": list(data.get("properties") or []),
            "rows": [],
        }
    
    def _generate_requirements_csv(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate operational triage CSV for requirements report."""
        from services.report_requirements_operational import (
            CSV_FIELDNAMES,
            build_requirements_operational_csv_rows,
            build_requirements_scheduled_email_rows,
        )

        output = io.StringIO()
        output.write(f"Report: {data['report_type']}\n")
        output.write(f"Generated: {data['generated_at']}\n")
        sem = (data.get("reporting_semantics") or {}).get("counts") or {}
        portal_reqs = data.get("portal_requirements") or data.get("requirements") or []
        properties = data.get("properties_portal") or []
        gen_at = data.get("generated_at")
        try:
            now = datetime.fromisoformat(str(gen_at).replace("Z", "+00:00"))
        except Exception:
            now = datetime.now(timezone.utc)

        csv_rows, triage_counts, enriched = build_requirements_operational_csv_rows(
            requirements=portal_reqs,
            properties=properties,
            client_doc=data.get("client_doc") or {},
            now=now,
        )
        email_rows = build_requirements_scheduled_email_rows(enriched)

        output.write("csv_format_version,requirements_operational_v1\n")
        output.write(f"Total obligations (rows): {len(csv_rows)}\n")
        output.write("=== TRIAGE SUMMARY ===\n")
        for label, count in triage_counts.items():
            from services.report_requirements_operational import TRIAGE_SECTION_TITLES

            human = TRIAGE_SECTION_TITLES.get(label, label)
            output.write(f"{human},{count}\n")
        output.write("\n")
        for row in csv_semantics_preamble_rows(sem, generated_at=data.get("generated_at", "")):
            output.write(",".join(str(c) for c in row) + "\n")
        output.write("\n")
        output.write("=== OBLIGATIONS (OPERATIONAL VIEW) ===\n")

        writer = csv.DictWriter(output, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)

        return {
            "content": output.getvalue(),
            "filename": f"requirements_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "content_type": "text/csv",
            "rows": email_rows,
            "csv_rows": csv_rows,
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
