from fastapi import APIRouter, HTTPException, Request, Depends, status
from database import database
from middleware import client_route_guard
from services.assistant_service import assistant_service
from utils.rate_limiter import rate_limiter
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskQuestionRequest(BaseModel):
    question: str


class AssistantResponse(BaseModel):
    """Structured response from the AI assistant."""
    answer: str
    what_this_is_based_on: list = []
    next_actions: list = []
    refused: bool = False
    refusal_reason: str = None
    correlation_id: str = None


@router.get("/snapshot")
async def get_snapshot(request: Request):
    """Get sanitized data snapshot for assistant context (read-only).
    
    This endpoint provides the same data the client already sees in their dashboard,
    formatted for AI assistant context.
    """
    user = await client_route_guard(request)
    
    try:
        snapshot = await assistant_service.get_client_snapshot(user["client_id"])
        return snapshot
    
    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve snapshot"
        )


@router.post("/ask", response_model=AssistantResponse)
async def ask_question(request: Request, data: AskQuestionRequest):
    """Ask assistant a question about compliance data (read-only).
    
    The assistant can only explain existing data. It cannot create, modify,
    or trigger any actions.
    
    Returns structured response with:
    - answer: Main response text
    - what_this_is_based_on: List of data points used
    - next_actions: Recommended portal actions
    - correlation_id: For support/debugging
    """
    user = await client_route_guard(request)
    
    try:
        # Rate limiting - 10 questions per 10 minutes per client
        allowed, error_msg = await rate_limiter.check_rate_limit(
            key=f"assistant_{user['client_id']}",
            max_attempts=10,
            window_minutes=10
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        
        # Validate question
        if not data.question or len(data.question.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty"
            )
        
        if len(data.question) > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question too long (max 500 characters)"
            )
        
        # Process question
        result = await assistant_service.ask_question(
            client_id=user["client_id"],
            actor_id=user["portal_user_id"],
            question=data.question
        )
        
        return AssistantResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assistant ask error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assistant unavailable. Please try again or refresh."
        )
