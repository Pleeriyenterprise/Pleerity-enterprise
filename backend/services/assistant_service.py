"""Read-only AI Assistant Service for Compliance Vault Pro

This assistant explains existing dashboard data and compliance status
without creating, modifying, or influencing any system state.

NON-NEGOTIABLE PRINCIPLES:
- Read-only: No create/update/delete operations
- Deterministic: Only uses stored data, no guessing
- No legal advice: Explains system, not legal requirements
- Client-scoped: Uses existing RBAC
- Audited: All interactions logged
"""
import os
from openai import OpenAI
from database import database
from models import AuditAction
from utils.audit import create_audit_log
import logging
import json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Compliance Vault Pro Assistant for Pleerity Enterprise Ltd.
You are a read-only product assistant that explains what the Compliance Vault Pro system shows.
You must follow these rules:

**Grounding and truth**
- Use ONLY the provided snapshot data.
- Never invent dates, certificates, rules, penalties, council outcomes, deadlines, or legal requirements.
- If data is missing or unclear, say "Unknown" and state what is missing.

**No legal advice**
- Do not provide legal advice, legal interpretations, or predictions of enforcement, fines, or penalties.
- Do not tell the user what they are "legally required" to do.
- You may explain the product's deterministic status logic and what the user can do inside the product (upload document, book inspection, contact support).

**Tone and framing**
- Use factual, calm language.
- Use phrases like: "The system shows…", "According to your records…", "Compliance Vault Pro evaluates this as…"
- Never use: "You must by law…", "This is illegal…", "You will be fined…"

**Data privacy and access**
- Never reveal other clients' data.
- Never reveal admin-only information.
- If asked for restricted info, refuse briefly and offer a safe alternative.

**Output structure**
- Provide a direct answer first.
- Then provide "What this is based on" listing the specific property/requirement/document fields used (IDs ok).
- Then provide "Next actions inside the portal" (non-legal, product actions only).
- If the question asks for legal meaning, refuse and offer to connect them to professional advice.

**Refusal scenarios**
Refuse and explain why if asked:
- Legal advice or interpretations
- To create, modify, or delete data
- To trigger actions (send emails, generate reports, etc.)
- To access other clients' data
- To access admin-only information
- To predict future enforcement or outcomes
"""

class AssistantService:
    def __init__(self):
        api_key = os.getenv("EMERGENT_LLM_KEY", "sk-emergent-f9533226f52E25cF35")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.openai.com/v1"
        )
        self.model = "gpt-4o-mini"
    
    async def get_client_snapshot(self, client_id: str) -> dict:
        """Get sanitized snapshot of client data for assistant context.
        
        Returns only safe, non-sensitive fields that the client already sees
        in their dashboard.
        """
        db = database.get_db()
        
        # Get client info (non-sensitive fields only)
        client = await db.clients.find_one(
            {"client_id": client_id},
            {
                "_id": 0,
                "client_id": 1,
                "full_name": 1,
                "email": 1,
                "company_name": 1,
                "client_type": 1,
                "billing_plan": 1,
                "subscription_status": 1
            }
        )
        
        if not client:
            return {"error": "Client not found"}
        
        # Get properties
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(100)
        
        # Get requirements
        requirements = await db.requirements.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(1000)
        
        # Get documents (metadata only, no file paths)
        documents = await db.documents.find(
            {"client_id": client_id},
            {
                "_id": 0,
                "document_id": 1,
                "property_id": 1,
                "requirement_id": 1,
                "file_name": 1,
                "status": 1,
                "uploaded_at": 1
            }
        ).to_list(1000)
        
        # Calculate compliance summary
        total_reqs = len(requirements)
        compliant = sum(1 for r in requirements if r["status"] == "COMPLIANT")
        overdue = sum(1 for r in requirements if r["status"] == "OVERDUE")
        expiring = sum(1 for r in requirements if r["status"] == "EXPIRING_SOON")
        
        snapshot = {
            "client": client,
            "properties": properties,
            "requirements": requirements,
            "documents": documents,
            "compliance_summary": {
                "total_requirements": total_reqs,
                "compliant": compliant,
                "overdue": overdue,
                "expiring_soon": expiring,
                "compliance_percentage": round((compliant / total_reqs * 100) if total_reqs > 0 else 0, 1)
            }
        }
        
        return snapshot
    
    async def ask_question(
        self,
        client_id: str,
        actor_id: str,
        question: str
    ) -> dict:
        """Process assistant question with strict read-only enforcement.
        
        Returns:
            {
                "answer": str,
                "data_sources": list,
                "next_actions": list,
                "refused": bool,
                "refusal_reason": str (optional)
            }
        """
        try:
            # Check for forbidden actions in question
            forbidden_keywords = [
                "create", "upload", "delete", "modify", "update", "change",
                "send email", "generate report", "trigger", "provision"
            ]
            
            question_lower = question.lower()
            if any(keyword in question_lower for keyword in forbidden_keywords):
                await self._audit_refusal(
                    client_id,
                    actor_id,
                    question,
                    "Question implies action/side-effect"
                )
                return {
                    "answer": "I can only explain what the system currently shows. I cannot create, modify, or trigger actions. Please use the appropriate buttons in the portal to perform actions.",
                    "refused": True,
                    "refusal_reason": "Request implies system modification"
                }
            
            # Get client snapshot
            snapshot = await self.get_client_snapshot(client_id)
            
            if "error" in snapshot:
                return {
                    "answer": "Unable to retrieve your data. Please try again.",
                    "refused": True,
                    "refusal_reason": "Data retrieval error"
                }
            
            # Build context message
            context_message = f"""Here is the current state of the Compliance Vault Pro system for this client:

{json.dumps(snapshot, indent=2, default=str)}

The client's question is: {question}

Provide a helpful answer based ONLY on the data shown above. Follow all rules in your system prompt."""
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context_message}
                ],
                temperature=0.1,  # Low temperature for deterministic responses
                max_tokens=800
            )
            
            answer = response.choices[0].message.content
            
            # Audit successful response
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_id=actor_id,
                client_id=client_id,
                metadata={
                    "action": "ASSISTANT_QUESTION_ANSWERED",
                    "question_length": len(question),
                    "answer_length": len(answer)
                }
            )
            
            return {
                "answer": answer,
                "refused": False
            }
        
        except Exception as e:
            logger.error(f"Assistant error: {e}")
            await self._audit_refusal(
                client_id,
                actor_id,
                question,
                f"Error: {str(e)}"
            )
            return {
                "answer": "I encountered an error processing your question. Please try again or contact support.",
                "refused": True,
                "refusal_reason": "Processing error"
            }
    
    async def _audit_refusal(
        self,
        client_id: str,
        actor_id: str,
        question: str,
        reason: str
    ):
        """Audit refused assistant interactions."""
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=actor_id,
            client_id=client_id,
            metadata={
                "action": "ASSISTANT_REFUSED",
                "question_length": len(question),
                "refusal_reason": reason
            }
        )

assistant_service = AssistantService()
