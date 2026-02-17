"""
Canonical OTP API: POST /api/otp/send and POST /api/otp/verify.
All OTP flows go through otp_service -> NotificationOrchestrator (OTP_CODE_SMS).
"""
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from middleware import client_route_guard
from services.otp_service import send_otp as otp_send, verify_otp as otp_verify
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/otp", tags=["otp"])


class OtpSendBody(BaseModel):
    """POST /api/otp/send. action: verify_phone (phone verification) or step_up (sensitive action)."""
    phone_number: str = Field(..., min_length=10, description="E.164 phone number")
    action: str = Field(..., pattern="^(verify_phone|step_up)$")


class OtpVerifyBody(BaseModel):
    """POST /api/otp/verify."""
    phone_number: str = Field(..., min_length=10)
    action: str = Field(..., pattern="^(verify_phone|step_up)$")
    code: str = Field(..., pattern="^[0-9]{6}$")


def _normalize_phone(phone: str) -> str:
    p = (phone or "").strip()
    if p and not p.startswith("+"):
        p = f"+{p}"
    return p


def _correlation_id(request: Request) -> str:
    return (request.headers.get("X-Correlation-ID") or "").strip() or None


@router.post("/send")
async def otp_send_endpoint(request: Request, data: OtpSendBody):
    """
    Send OTP to phone via NotificationOrchestrator (OTP_CODE_SMS).
    Always 200 with generic message (no user enumeration).
    """
    try:
        phone_e164 = _normalize_phone(data.phone_number)
        await otp_send(
            phone_e164=phone_e164,
            purpose=data.action,
            correlation_id=_correlation_id(request),
        )
        return {"ok": True, "message": "If eligible, an OTP was sent."}
    except Exception as e:
        logger.exception(f"OTP send error: {e}")
        return {"ok": True, "message": "If eligible, an OTP was sent."}


@router.post("/verify")
async def otp_verify_endpoint(request: Request, data: OtpVerifyBody):
    """
    Verify OTP. Success: 200 { "status": "verified" } or { "status": "verified", "step_up_token": "..." }.
    Failure: 400 generic (do not reveal whether phone exists). step_up requires auth.
    """
    cid = _correlation_id(request)
    user_id = None
    if data.action == "step_up":
        try:
            user = await client_route_guard(request)
            user_id = user.get("portal_user_id") or user.get("client_id")
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized"},
            )
        if not user_id:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized"},
            )
    try:
        phone_e164 = _normalize_phone(data.phone_number)
        ok, step_up_token = await otp_verify(
            phone_e164=phone_e164,
            code=data.code,
            purpose=data.action,
            correlation_id=cid,
            user_id=user_id,
        )
        if ok:
            out = {"status": "verified"}
            if step_up_token is not None:
                out["step_up_token"] = step_up_token
            return out
    except Exception as e:
        logger.exception(f"OTP verify error: {e}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Invalid or expired code"},
    )
