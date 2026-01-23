"""
Lead AI Summary Service

Generates AI-powered summaries for leads using Gemini.
Summaries are:
- Assistive only (helps admin, not automated decisions)
- Deterministic and safe (only summarizes what the lead said)
- Never infers legal/compliance claims
- Audit logged
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from database import database
from services.lead_service import LeadService
from models.lead_models import LeadAuditEvent

logger = logging.getLogger(__name__)

LEADS_COLLECTION = "leads"

# Emergent LLM Key (for Gemini)
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")


class LeadAISummaryService:
    """Service for generating AI summaries of leads."""
    
    SUMMARY_PROMPT = """You are a helpful assistant summarizing a sales lead for a CRM system.

Based on the lead information below, write a concise 2-3 sentence summary that:
1. States what service the lead is interested in
2. Summarizes their main question or need (if provided)
3. Notes any important context (e.g., number of properties, urgency)

IMPORTANT RULES:
- Only summarize what is explicitly provided
- DO NOT make assumptions about legal, compliance, or regulatory matters
- DO NOT infer intent beyond what is stated
- Keep it factual and neutral
- Use professional business language

LEAD INFORMATION:
- Source: {source_platform}
- Service Interest: {service_interest}
- Name: {name}
- Company: {company_name}
- Message: {message}
- UTM Campaign: {utm_campaign}
- Properties Count: {property_count}
- Plan Selected: {plan_selected}

Write a brief summary:"""

    @staticmethod
    async def generate_summary(lead_id: str) -> Optional[str]:
        """
        Generate an AI summary for a lead.
        Returns the summary text or None if generation fails.
        """
        lead = await LeadService.get_lead(lead_id)
        if not lead:
            logger.error(f"Lead not found: {lead_id}")
            return None
        
        # Skip if already has summary
        if lead.get("ai_summary"):
            return lead["ai_summary"]
        
        # Build prompt context
        context = {
            "source_platform": lead.get("source_platform", "Unknown"),
            "service_interest": lead.get("service_interest", "Unknown"),
            "name": lead.get("name") or "Not provided",
            "company_name": lead.get("company_name") or "Not provided",
            "message": lead.get("message_summary") or "No message provided",
            "utm_campaign": lead.get("utm_campaign") or "None",
            "property_count": "Unknown",
            "plan_selected": "Not selected",
        }
        
        # Try to get additional context from intake draft
        if lead.get("intake_draft_id"):
            db = database.get_db()
            draft = await db["intake_drafts"].find_one(
                {"draft_id": lead["intake_draft_id"]},
                {"_id": 0}
            )
            if draft:
                payload = draft.get("intake_payload", {})
                properties = payload.get("properties", [])
                context["property_count"] = str(len(properties)) if properties else "None"
                context["plan_selected"] = payload.get("selected_plan") or "Not selected"
        
        # Generate summary using Gemini
        summary = await LeadAISummaryService._call_gemini(context)
        
        if summary:
            # Store summary
            db = database.get_db()
            await db[LEADS_COLLECTION].update_one(
                {"lead_id": lead_id},
                {
                    "$set": {
                        "ai_summary": summary,
                        "ai_summary_generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                }
            )
            
            # Audit log
            await LeadService.log_audit(
                event=LeadAuditEvent.LEAD_AI_SUMMARY_CREATED,
                lead_id=lead_id,
                actor_id="system",
                actor_type="ai",
                details={
                    "summary_length": len(summary),
                    "model": "gemini",
                },
            )
            
            logger.info(f"AI summary generated for lead {lead_id}")
        
        return summary
    
    @staticmethod
    async def _call_gemini(context: Dict[str, str]) -> Optional[str]:
        """Call Gemini API to generate summary."""
        if not EMERGENT_LLM_KEY:
            logger.warning("Emergent LLM key not configured, skipping AI summary")
            return None
        
        try:
            from emergentintegrations.llm.gemini import GeminiChat
            
            # Format prompt
            prompt = LeadAISummaryService.SUMMARY_PROMPT.format(**context)
            
            # Call Gemini
            gemini = GeminiChat(
                emergent_api_key=EMERGENT_LLM_KEY,
            )
            
            response = await gemini.send_message(prompt)
            
            if response and response.text:
                # Clean up response
                summary = response.text.strip()
                # Ensure reasonable length
                if len(summary) > 500:
                    summary = summary[:497] + "..."
                return summary
            
            return None
            
        except ImportError:
            logger.warning("emergentintegrations not available, skipping AI summary")
            return None
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    @staticmethod
    async def regenerate_summary(lead_id: str, actor_id: str) -> Optional[str]:
        """
        Regenerate AI summary for a lead (admin action).
        Clears existing summary first.
        """
        db = database.get_db()
        
        # Clear existing summary
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {"$unset": {"ai_summary": 1, "ai_summary_generated_at": 1}}
        )
        
        # Generate new summary
        summary = await LeadAISummaryService.generate_summary(lead_id)
        
        if summary:
            await LeadService.log_audit(
                event=LeadAuditEvent.LEAD_AI_SUMMARY_CREATED,
                lead_id=lead_id,
                actor_id=actor_id,
                actor_type="admin",
                details={
                    "action": "regenerate",
                    "summary_length": len(summary),
                },
            )
        
        return summary


async def generate_summaries_batch(limit: int = 50):
    """
    Batch generate summaries for leads without one.
    Called by scheduled job.
    """
    db = database.get_db()
    
    # Find leads without summary
    leads = await db[LEADS_COLLECTION].find(
        {
            "ai_summary": None,
            "status": {"$nin": ["MERGED", "LOST"]},
        },
        {"_id": 0, "lead_id": 1}
    ).limit(limit).to_list(length=limit)
    
    generated = 0
    for lead in leads:
        summary = await LeadAISummaryService.generate_summary(lead["lead_id"])
        if summary:
            generated += 1
    
    logger.info(f"Generated {generated} AI summaries")
    return generated
