"""Read-only AI Assistant Service for Compliance Vault Pro

This assistant explains existing dashboard data and compliance status
without creating, modifying, or influencing any system state.

NON-NEGOTIABLE PRINCIPLES:
- Read-only: No create/update/delete operations
- Deterministic: Only uses stored data, no guessing
- No legal advice: Explains system, not legal requirements
- Client-scoped: Uses existing RBAC
- Audited: All interactions logged
- Observable: Proper correlation IDs and error tracking
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from database import database
from models import AuditAction
from utils.audit import create_audit_log
from emergentintegrations.llm.chat import LlmChat, UserMessage
from dotenv import load_dotenv
import json

load_dotenv()

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
Your response must be in this exact JSON format:
{
  "answer": "Your main response here",
  "what_this_is_based_on": ["List of specific data points used from the snapshot"],
  "next_actions": ["List of recommended portal actions"]
}

**Refusal scenarios**
If asked for legal advice, to modify data, or to access restricted info, respond with:
{
  "answer": "I cannot help with that request. [Brief explanation]",
  "what_this_is_based_on": [],
  "next_actions": ["Contact professional advisor for legal questions", "Use portal buttons to modify data"]
}
"""


class AssistantService:
    def __init__(self):
        self.api_key = os.getenv("EMERGENT_LLM_KEY", "sk-emergent-f9533226f52E25cF35")
        self.model_provider = "gemini"
        self.model_name = "gemini-3-flash-preview"
    
    def _generate_correlation_id(self) -> str:
        """Generate a unique correlation ID for request tracing."""
        return f"ast-{uuid.uuid4().hex[:12]}"
    
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
                "subscription_status": 1,
                "customer_reference": 1
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
        compliant = sum(1 for r in requirements if r.get("status") == "COMPLIANT")
        overdue = sum(1 for r in requirements if r.get("status") == "OVERDUE")
        expiring = sum(1 for r in requirements if r.get("status") == "EXPIRING_SOON")
        pending = sum(1 for r in requirements if r.get("status") == "PENDING")
        
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
                "pending": pending,
                "compliance_percentage": round((compliant / total_reqs * 100) if total_reqs > 0 else 0, 1)
            },
            "snapshot_generated_at": datetime.now(timezone.utc).isoformat()
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
                "what_this_is_based_on": list,
                "next_actions": list,
                "refused": bool,
                "refusal_reason": str (optional),
                "correlation_id": str
            }
        """
        correlation_id = self._generate_correlation_id()
        logger.info(f"[{correlation_id}] Assistant request started for client {client_id[:8]}...")
        
        try:
            # Check for forbidden actions in question
            forbidden_keywords = [
                "create", "upload", "delete", "modify", "update", "change",
                "send email", "generate report", "trigger", "provision"
            ]
            
            question_lower = question.lower()
            if any(keyword in question_lower for keyword in forbidden_keywords):
                logger.warning(f"[{correlation_id}] Refused: Question implies action")
                await self._audit_interaction(
                    client_id=client_id,
                    actor_id=actor_id,
                    question=question,
                    correlation_id=correlation_id,
                    success=False,
                    reason_code="ACTION_KEYWORD_DETECTED"
                )
                return {
                    "answer": "I can only explain what the system currently shows. I cannot create, modify, or trigger actions. Please use the appropriate buttons in the portal to perform actions.",
                    "what_this_is_based_on": [],
                    "next_actions": ["Use portal navigation to perform the desired action"],
                    "refused": True,
                    "refusal_reason": "Request implies system modification",
                    "correlation_id": correlation_id
                }
            
            # Get client snapshot
            logger.info(f"[{correlation_id}] Retrieving client snapshot...")
            snapshot = await self.get_client_snapshot(client_id)
            
            if "error" in snapshot:
                logger.error(f"[{correlation_id}] Snapshot retrieval failed: {snapshot['error']}")
                await self._audit_interaction(
                    client_id=client_id,
                    actor_id=actor_id,
                    question=question,
                    correlation_id=correlation_id,
                    success=False,
                    reason_code="SNAPSHOT_RETRIEVAL_FAILED"
                )
                return {
                    "answer": "Unable to retrieve your data. Please try again or contact support.",
                    "what_this_is_based_on": [],
                    "next_actions": ["Refresh the page", "Contact support if the issue persists"],
                    "refused": True,
                    "refusal_reason": "Data retrieval error",
                    "correlation_id": correlation_id
                }
            
            # Check snapshot size to avoid payload issues
            snapshot_str = json.dumps(snapshot, default=str)
            snapshot_size = len(snapshot_str)
            logger.info(f"[{correlation_id}] Snapshot size: {snapshot_size} bytes")
            
            if snapshot_size > 50000:  # 50KB limit
                logger.warning(f"[{correlation_id}] Snapshot too large, truncating...")
                # Truncate requirements and documents to most recent
                snapshot["requirements"] = snapshot["requirements"][:50]
                snapshot["documents"] = snapshot["documents"][:50]
                snapshot["_truncated"] = True
            
            # Build context message
            context_message = f"""Here is the current state of the Compliance Vault Pro system for this client:

{json.dumps(snapshot, indent=2, default=str)}

The client's question is: {question}

Provide a helpful answer based ONLY on the data shown above. Follow all rules in your system prompt.
Remember to respond in the exact JSON format specified."""
            
            # Initialize chat with emergentintegrations
            logger.info(f"[{correlation_id}] Calling LLM ({self.model_provider}/{self.model_name})...")
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"assistant-{client_id}-{correlation_id}",
                system_message=SYSTEM_PROMPT
            ).with_model(self.model_provider, self.model_name)
            
            # Send message
            user_message = UserMessage(text=context_message)
            response_text = await chat.send_message(user_message)
            
            logger.info(f"[{correlation_id}] LLM response received, length: {len(response_text)}")
            
            # Parse JSON response
            try:
                # Try to extract JSON from response
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                
                parsed_response = json.loads(response_text.strip())
                answer = parsed_response.get("answer", response_text)
                what_based_on = parsed_response.get("what_this_is_based_on", [])
                next_actions = parsed_response.get("next_actions", [])
            except json.JSONDecodeError:
                # Fallback if response is not valid JSON
                logger.warning(f"[{correlation_id}] Could not parse JSON response, using raw text")
                answer = response_text
                what_based_on = []
                next_actions = []
            
            # Audit successful response
            await self._audit_interaction(
                client_id=client_id,
                actor_id=actor_id,
                question=question,
                correlation_id=correlation_id,
                success=True,
                answer_preview=answer[:200] if answer else ""
            )
            
            logger.info(f"[{correlation_id}] Request completed successfully")
            
            return {
                "answer": answer,
                "what_this_is_based_on": what_based_on,
                "next_actions": next_actions,
                "refused": False,
                "correlation_id": correlation_id
            }
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{correlation_id}] Assistant error: {error_msg}", exc_info=True)
            
            # Audit the failure
            await self._audit_interaction(
                client_id=client_id,
                actor_id=actor_id,
                question=question,
                correlation_id=correlation_id,
                success=False,
                reason_code="PROCESSING_ERROR",
                error_message=error_msg
            )
            
            # Return user-friendly error
            return {
                "answer": "Assistant unavailable. Please try again or refresh the page.",
                "what_this_is_based_on": [],
                "next_actions": ["Refresh the page and try again", "Contact support if the issue persists"],
                "refused": True,
                "refusal_reason": "Processing error",
                "correlation_id": correlation_id
            }
    
    async def _audit_interaction(
        self,
        client_id: str,
        actor_id: str,
        question: str,
        correlation_id: str,
        success: bool,
        reason_code: str = None,
        answer_preview: str = None,
        error_message: str = None
    ):
        """Audit assistant interactions with full observability."""
        try:
            metadata = {
                "action": "CLIENT_ASSISTANT_QUERY",
                "correlation_id": correlation_id,
                "question_length": len(question),
                "success": success,
                "model": f"{self.model_provider}/{self.model_name}"
            }
            
            if reason_code:
                metadata["reason_code"] = reason_code
            if answer_preview:
                metadata["answer_preview"] = answer_preview
            if error_message:
                metadata["error_message"] = error_message[:500]  # Truncate long errors
            
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,  # Reuse existing action for now
                actor_id=actor_id,
                client_id=client_id,
                metadata=metadata,
                reason_code=reason_code
            )
        except Exception as e:
            logger.error(f"[{correlation_id}] Failed to create audit log: {e}")


assistant_service = AssistantService()
