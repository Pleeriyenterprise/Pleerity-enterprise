from fastapi import APIRouter, HTTPException, Request, status
from database import database
from models import (
    LoginRequest,
    ForgotPasswordRequest,
    SetPasswordRequest,
    TokenResponse,
    StepUpPasswordRequest,
    UserRole,
    UserStatus,
    PasswordStatus,
    OnboardingStatus,
    AuditAction,
)
from auth import (
    verify_password,
    hash_password,
    create_access_token,
    hash_token,
    validate_password_strength,
    generate_secure_token,
    create_step_up_token,
)
from utils.audit import create_audit_log
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from config.security_limits import security_limits
from datetime import datetime, timezone, timedelta
import logging
import re
import os
import secrets
from middleware import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

def _client_ip(request: Request) -> str:
    """Prefer X-Forwarded-For when behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"

# Portal separation: which roles may use which login endpoint
CLIENT_PORTAL_ROLES = (UserRole.ROLE_CLIENT.value, UserRole.ROLE_CLIENT_ADMIN.value)
STAFF_PORTAL_ROLES = (UserRole.ROLE_OWNER.value, UserRole.ROLE_ADMIN.value, UserRole.ROLE_SUPPORT.value, UserRole.ROLE_CONTENT.value)


def _frontend_base_url_fallback() -> str:
    from utils.public_app_url import get_frontend_base_url

    try:
        return get_frontend_base_url().rstrip("/")
    except Exception:
        raw = (os.getenv("PUBLIC_APP_URL") or os.getenv("FRONTEND_URL") or "").strip().rstrip("/")
        return raw


def _admin_mfa_required() -> bool:
    return (os.getenv("ADMIN_MFA_REQUIRED") or "false").strip().lower() == "true"


def _admin_mfa_ttl_seconds() -> int:
    raw = (os.getenv("ADMIN_MFA_TTL_SECONDS") or "600").strip()
    try:
        return max(120, min(int(raw), 1800))
    except ValueError:
        return 600


def _admin_mfa_max_attempts() -> int:
    raw = (os.getenv("ADMIN_MFA_MAX_ATTEMPTS") or "5").strip()
    try:
        return max(3, min(int(raw), 10))
    except ValueError:
        return 5


def _generate_mfa_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


async def _issue_admin_mfa_challenge(portal_user: dict, ip: str) -> dict:
    db = database.get_db()
    challenge_id = generate_secure_token()
    raw_code = _generate_mfa_code()
    now = datetime.now(timezone.utc)
    ttl = _admin_mfa_ttl_seconds()
    expires_at = now + timedelta(seconds=ttl)
    await db.admin_login_challenges.insert_one(
        {
            "challenge_id": challenge_id,
            "portal_user_id": portal_user["portal_user_id"],
            "email": (portal_user.get("auth_email") or "").strip().lower(),
            "ip": ip,
            "code_hash": hash_token(raw_code),
            "attempts": 0,
            "max_attempts": _admin_mfa_max_attempts(),
            "created_at": now,
            "expires_at": expires_at,
            "used_at": None,
        }
    )
    from services.notification_orchestrator import notification_orchestrator
    await notification_orchestrator.send(
        template_key="AUTH_ADMIN_MFA_CODE",
        client_id=None,
        context={
            "recipient": (portal_user.get("auth_email") or "").strip().lower(),
            "subject": "Your Pleerity admin verification code",
            "message": (
                f"Use this code to complete admin sign-in: {raw_code}. "
                f"It expires in {max(1, ttl // 60)} minute(s). "
                "If you did not initiate this sign-in, reset your password immediately."
            ),
        },
        idempotency_key=f"admin_mfa_code:{challenge_id}",
        event_type="admin_mfa_code",
    )
    await create_audit_log(
        action=AuditAction.STEP_UP_VERIFIED,
        actor_id=portal_user["portal_user_id"],
        actor_role=UserRole(portal_user["role"]),
        metadata={"reason": "admin_mfa_challenge_issued", "challenge_id": challenge_id},
    )
    return {"challenge_id": challenge_id, "expires_in_seconds": ttl}


async def _verify_admin_mfa_challenge(portal_user: dict, ip: str, challenge_id: str, code: str) -> bool:
    db = database.get_db()
    now = datetime.now(timezone.utc)
    row = await db.admin_login_challenges.find_one(
        {
            "challenge_id": challenge_id,
            "portal_user_id": portal_user["portal_user_id"],
        },
        {"_id": 0},
    )
    if not row:
        return False
    if row.get("used_at"):
        return False
    exp = row.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and now > exp:
        return False
    attempts = int(row.get("attempts") or 0)
    max_attempts = int(row.get("max_attempts") or _admin_mfa_max_attempts())
    if attempts >= max_attempts:
        return False
    ok = hash_token((code or "").strip()) == row.get("code_hash")
    if not ok:
        await db.admin_login_challenges.update_one(
            {"challenge_id": challenge_id},
            {"$inc": {"attempts": 1}, "$set": {"updated_at": now, "last_failed_ip": ip}},
        )
        await create_audit_log(
            action=AuditAction.STEP_UP_FAILED,
            actor_id=portal_user["portal_user_id"],
            actor_role=UserRole(portal_user["role"]),
            metadata={"reason": "admin_mfa_invalid_code", "challenge_id": challenge_id},
        )
        return False
    await db.admin_login_challenges.update_one(
        {"challenge_id": challenge_id},
        {"$set": {"used_at": now, "updated_at": now, "verified_ip": ip}},
    )
    await create_audit_log(
        action=AuditAction.STEP_UP_VERIFIED,
        actor_id=portal_user["portal_user_id"],
        actor_role=UserRole(portal_user["role"]),
        metadata={"reason": "admin_mfa_verified", "challenge_id": challenge_id},
    )
    return True


async def _send_auth_lock_notification(email: str, portal: str, retry_after_seconds: int) -> None:
    """Best-effort lock notification. Uses seeded ADMIN_MANUAL template (no placeholders)."""
    recipient = (email or "").strip().lower()
    if not recipient:
        return
    base = _frontend_base_url_fallback()
    reset_link = f"{base}/forgot-password" if base else "/forgot-password"
    mins = max(1, int((max(0, retry_after_seconds) + 59) / 60))
    from services.notification_orchestrator import notification_orchestrator

    await notification_orchestrator.send(
        template_key="AUTH_ACCOUNT_LOCKED",
        client_id=None,
        context={
            "recipient": recipient,
            "subject": f"Temporary {portal} sign-in lock detected",
            "message": (
                f"We detected repeated failed sign-in attempts on your {portal} account and temporarily locked sign-in for about {mins} minute(s). "
                f"If this was you, wait and try again. If it was not you, reset your password now: {reset_link}"
            ),
        },
        idempotency_key=f"auth_lock_notice:{portal}:{recipient}:{mins}",
        event_type="auth_lock_notice",
    )


async def _send_post_lock_recovery_notice(email: str, portal: str) -> None:
    recipient = (email or "").strip().lower()
    if not recipient:
        return
    from services.notification_orchestrator import notification_orchestrator
    await notification_orchestrator.send(
        template_key="AUTH_LOGIN_RECOVERED",
        client_id=None,
        context={
            "recipient": recipient,
            "subject": f"Sign-in restored for your {portal} account",
            "message": (
                f"Your {portal} sign-in is active again after a temporary lock. "
                "If this sign-in was not you, reset your password immediately and contact support."
            ),
        },
        idempotency_key=f"auth_recovery_notice:{portal}:{recipient}",
        event_type="auth_recovery_notice",
    )

@router.post("/impersonation/stop")
async def stop_impersonation(request: Request):
    """
    End impersonation session (audit only). Frontend restores saved admin session locally.
    """
    user = await require_auth(request)
    if not user.get("impersonation"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not in impersonation mode")

    client_id = user.get("client_id")
    impersonated_by = user.get("impersonated_by_portal_user_id")
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=impersonated_by,
        actor_role=UserRole.ROLE_ADMIN,
        client_id=client_id,
        resource_type="portal_user",
        resource_id=user.get("portal_user_id"),
        metadata={
            "action_type": "impersonation_stop",
            "impersonated_role": user.get("role"),
            "impersonation_started_at": user.get("impersonation_started_at"),
        },
    )
    return {"success": True, "message": "Impersonation stopped"}

@router.post("/session/extend", response_model=TokenResponse)
async def extend_session(request: Request):
    """
    Issue a new access token with the same claims (sliding session length).
    Requires valid Bearer; does not verify password. Used after idle warning.
    """
    user = await require_auth(request)
    db = database.get_db()
    portal_user = await db.portal_users.find_one(
        {"portal_user_id": user["portal_user_id"]},
        {"_id": 0, "portal_user_id": 1, "client_id": 1, "auth_email": 1, "role": 1, "session_version": 1},
    )
    if not portal_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token_data = {
        "portal_user_id": portal_user["portal_user_id"],
        "client_id": portal_user.get("client_id"),
        "email": portal_user["auth_email"],
        "role": portal_user["role"],
        "session_version": portal_user.get("session_version", 0),
    }
    if user.get("impersonation"):
        token_data["impersonation"] = True
        token_data["impersonated_by_portal_user_id"] = user.get("impersonated_by_portal_user_id")
        token_data["impersonated_by_role"] = user.get("impersonated_by_role")
        token_data["impersonation_started_at"] = user.get("impersonation_started_at")

    expires_delta = None
    if user.get("impersonation") and user.get("exp") is not None:
        try:
            exp_claim = user["exp"]
            if isinstance(exp_claim, (int, float)):
                exp_dt = datetime.fromtimestamp(float(exp_claim), tz=timezone.utc)
                now = datetime.now(timezone.utc)
                if exp_dt > now:
                    expires_delta = exp_dt - now
        except (TypeError, ValueError, OSError):
            expires_delta = None

    access_token = create_access_token(token_data, expires_delta=expires_delta)
    await create_audit_log(
        action=AuditAction.SESSION_EXTENDED,
        actor_id=portal_user["portal_user_id"],
        actor_role=UserRole(portal_user["role"]),
        client_id=portal_user.get("client_id"),
        metadata={"path": "session_extend"},
    )
    user_out = {
        "portal_user_id": portal_user["portal_user_id"],
        "email": portal_user["auth_email"],
        "role": portal_user["role"],
        "client_id": portal_user.get("client_id"),
    }
    if user.get("impersonation"):
        user_out["impersonation"] = True
        user_out["impersonated_by_portal_user_id"] = user.get("impersonated_by_portal_user_id")
        user_out["impersonated_by_role"] = user.get("impersonated_by_role")

    return TokenResponse(
        access_token=access_token,
        user=user_out,
    )


@router.post("/session/idle-notify")
async def session_idle_notify(request: Request):
    """Client calls when inactivity timeout fires (before redirect). Audited for security monitoring."""
    user = await require_auth(request)
    actor_role = None
    if user.get("role"):
        try:
            actor_role = UserRole(user["role"])
        except ValueError:
            actor_role = None
    await create_audit_log(
        action=AuditAction.SESSION_IDLE_TIMEOUT,
        actor_id=user.get("portal_user_id"),
        actor_role=actor_role,
        client_id=user.get("client_id"),
        metadata={"source": "client_idle_timer"},
    )
    return {"ok": True}


@router.post("/step-up/verify")
async def step_up_verify(request: Request, body: StepUpPasswordRequest):
    """Verify current password; return short-lived step-up token for sensitive actions."""
    user = await require_auth(request)
    db = database.get_db()
    portal_user = await db.portal_users.find_one(
        {"portal_user_id": user["portal_user_id"]},
        {"_id": 0, "password_hash": 1, "portal_user_id": 1, "role": 1},
    )
    if not portal_user or not portal_user.get("password_hash"):
        await create_audit_log(
            action=AuditAction.STEP_UP_FAILED,
            actor_id=user.get("portal_user_id"),
            metadata={"reason": "no_password"},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot verify password")
    if not verify_password(body.password, portal_user["password_hash"]):
        await create_audit_log(
            action=AuditAction.STEP_UP_FAILED,
            actor_id=user.get("portal_user_id"),
            metadata={"reason": "invalid_password"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    token = create_step_up_token(portal_user["portal_user_id"])
    await create_audit_log(
        action=AuditAction.STEP_UP_VERIFIED,
        actor_id=portal_user["portal_user_id"],
        actor_role=UserRole(portal_user["role"]),
        client_id=user.get("client_id"),
        metadata={},
    )
    return {
        "step_up_token": token,
        "expires_in_seconds": security_limits.step_up_token_minutes * 60,
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, credentials: LoginRequest):
    """Client login endpoint."""
    ip = _client_ip(request)
    email_key = (credentials.email or "").strip().lower()
    try:
        from services.security_monitoring_service import get_auth_lock_state
        lock_state = await get_auth_lock_state(email=email_key, ip=ip, portal="client")
        if lock_state.get("locked"):
            retry_after = int(lock_state.get("retry_after_seconds") or 0)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "message": "Login temporarily locked due to repeated failed attempts. Try again later.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)} if retry_after > 0 else None,
            )
    except HTTPException:
        raise
    except Exception:
        pass
    lim = security_limits
    db = database.get_db()

    async def _record_login_failure() -> None:
        try:
            from services.security_monitoring_service import record_security_event
            await record_security_event(
                event_type="auth.login_failed",
                ip=ip,
                details={"email": email_key, "portal": "client"},
                severity="medium",
            )
            try:
                from services.security_monitoring_service import get_auth_lock_state
                state = await get_auth_lock_state(email=email_key, ip=ip, portal="client")
                if state.get("locked") and state.get("lock_type") == "auth_email":
                    await _send_auth_lock_notification(
                        email=email_key,
                        portal="client",
                        retry_after_seconds=int(state.get("retry_after_seconds") or 0),
                    )
            except Exception:
                pass
        except Exception:
            pass

    try:
        # Find portal user
        portal_user = await db.portal_users.find_one(
            {"auth_email": {"$regex": f"^{re.escape(email_key)}$", "$options": "i"}},
            {"_id": 0}
        )
        
        if not portal_user:
            await create_audit_log(
                action=AuditAction.USER_LOGIN_FAILED,
                metadata={"email": credentials.email, "reason": "user_not_found"}
            )
            await _record_login_failure()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not portal_user.get("password_hash") or not verify_password(
            credentials.password,
            portal_user["password_hash"]
        ):
            await create_audit_log(
                action=AuditAction.USER_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "invalid_password"}
            )
            await _record_login_failure()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check user status
        if portal_user["status"] != UserStatus.ACTIVE.value:
            await _record_login_failure()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active"
            )
        
        # Check password status
        if portal_user["password_status"] != PasswordStatus.SET.value:
            await _record_login_failure()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password not set"
            )
        
        # Enforce client portal: only client roles may use this endpoint
        if portal_user["role"] in STAFF_PORTAL_ROLES:
            await create_audit_log(
                action=AuditAction.USER_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "staff_use_client_portal"}
            )
            await _record_login_failure()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account must sign in via the Staff/Admin portal."
            )
        
        # Staff (OWNER/ADMIN/SUPPORT/CONTENT) don't need client association for admin login
        client = None
        if portal_user["role"] in STAFF_PORTAL_ROLES:
            pass
        else:
            # Get client info for non-admin users
            client = await db.clients.find_one(
                {"client_id": portal_user["client_id"]},
                {"_id": 0}
            )
            
            if not client:
                await _record_login_failure()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Client not found"
                )
            
            # Check provisioning for client users
            if client["onboarding_status"] != OnboardingStatus.PROVISIONED.value:
                await _record_login_failure()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error_code": "ACCOUNT_NOT_READY", "message": "Your portal is still being provisioned."}
                )
        
        # Update last login
        await db.portal_users.update_one(
            {"portal_user_id": portal_user["portal_user_id"]},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Create access token
        token_data = {
            "portal_user_id": portal_user["portal_user_id"],
            "client_id": portal_user.get("client_id"),
            "email": portal_user["auth_email"],
            "role": portal_user["role"],
            "session_version": portal_user.get("session_version", 0),
        }
        access_token = create_access_token(token_data)
        
        await create_audit_log(
            action=AuditAction.USER_LOGIN_SUCCESS,
            actor_role=UserRole(portal_user["role"]),
            actor_id=portal_user["portal_user_id"],
            client_id=portal_user.get("client_id")  # Use .get() to handle None
        )
        try:
            from services.security_monitoring_service import record_security_event
            await record_security_event(
                event_type="auth.login_success",
                user_id=portal_user["portal_user_id"],
                ip=ip,
                details={"role": portal_user.get("role")},
                severity="low",
            )
            from services.security_monitoring_service import clear_auth_lock
            had_lock = await clear_auth_lock(email=email_key, portal="client", reason="login_success")
            if had_lock:
                await _send_post_lock_recovery_notice(email=email_key, portal="client")
        except Exception:
            pass
        # Successful sign-in recovers counters for this account.
        # No in-memory limiter state to clear here; lock state is DB-backed.
        
        # Check if this is first login and emit enablement event
        try:
            # Only emit first login event for client users (admins don't have clients)
            if portal_user.get("client_id"):
                login_count = portal_user.get("login_count", 0)
                if login_count == 0:
                    from services.enablement_service import emit_enablement_event
                    from models.enablement import EnablementEventType
                    
                    # Get client info
                    client = await db.clients.find_one(
                        {"client_id": portal_user["client_id"]},
                        {"_id": 0, "plan_code": 1}
                    )
                    
                    await emit_enablement_event(
                        event_type=EnablementEventType.FIRST_LOGIN,
                        client_id=portal_user["client_id"],
                        plan_code=client.get("plan_code") if client else None,
                        context_payload={"email": portal_user["auth_email"]}
                    )
                    # Milestone + backup dashboard-ready if set-password handler missed it (same guards inside).
                    if portal_user.get("role") == UserRole.ROLE_CLIENT_ADMIN.value:
                        try:
                            from services.onboarding_email_governance import milestone_set_payload

                            await db.clients.update_one(
                                {"client_id": portal_user["client_id"]},
                                {"$set": milestone_set_payload("first_login_completed_at")},
                            )
                            logger.info(
                                "onboarding_milestone_first_login client_id=%s",
                                portal_user["client_id"],
                            )
                        except Exception as m_err:
                            logger.warning("first_login milestone update failed: %s", m_err)
                        try:
                            from services.onboarding_lifecycle_service import (
                                send_dashboard_ready_and_start_sequence,
                            )

                            await send_dashboard_ready_and_start_sequence(portal_user["client_id"])
                        except Exception as dash_err:
                            logger.warning(
                                "send_dashboard_ready_and_start_sequence (first login backup) failed client_id=%s: %s",
                                portal_user["client_id"],
                                dash_err,
                            )
            
            # Increment login count for all users
            await db.portal_users.update_one(
                {"portal_user_id": portal_user["portal_user_id"]},
                {"$inc": {"login_count": 1}}
            )
        except Exception as enable_err:
            logger.warning(f"Failed to emit first login event: {enable_err}")
        
        return TokenResponse(
            access_token=access_token,
            user={
                "portal_user_id": portal_user["portal_user_id"],
                "email": portal_user["auth_email"],
                "role": portal_user["role"],
                "client_id": portal_user.get("client_id")  # Use .get() for admin users
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or __import__("uuid").uuid4().hex[:12]


@router.post("/set-password")
async def set_password(request: Request, data: SetPasswordRequest):
    """Set password using token (production-safe)."""
    ip = _client_ip(request)
    sl = security_limits
    allowed_sp, err_sp = await rate_limiter.check_rate_limit(
        f"set_password_ip:{ip}",
        sl.set_password_ip_max,
        sl.set_password_ip_window_minutes,
    )
    if not allowed_sp:
        log_rate_limit_event("set_password", ip, ip)
        await create_audit_log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            metadata={"scope": "set_password", "ip": ip},
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_sp or "Too many attempts.")
    db = database.get_db()
    request_id = _request_id(request)
    token_prefix = (data.token[:6] if data.token and len(data.token) >= 6 else "short")

    try:
        # Hash the provided token
        token_hash_value = hash_token(data.token)

        # Find token
        password_token = await db.password_tokens.find_one(
            {"token_hash": token_hash_value},
            {"_id": 0}
        )

        if not password_token:
            logger.warning(
                "set_password invalid token request_id=%s token_prefix=%s reason=unknown",
                request_id, token_prefix
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password setup link"
            )

        # Validate token
        now = datetime.now(timezone.utc)

        # Handle both string and datetime objects, ensure timezone-aware
        expires_at_raw = password_token["expires_at"]
        if isinstance(expires_at_raw, str):
            expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
        elif isinstance(expires_at_raw, datetime):
            # Ensure timezone-aware
            if expires_at_raw.tzinfo is None:
                expires_at = expires_at_raw.replace(tzinfo=timezone.utc)
            else:
                expires_at = expires_at_raw
        else:
            expires_at = expires_at_raw

        if password_token.get("used_at"):
            logger.warning(
                "set_password invalid token request_id=%s token_prefix=%s reason=used",
                request_id, token_prefix
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password setup link has already been used"
            )

        if password_token.get("revoked_at"):
            logger.warning(
                "set_password invalid token request_id=%s token_prefix=%s reason=revoked",
                request_id, token_prefix
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password setup link has been revoked"
            )

        if now > expires_at:
            logger.warning(
                "set_password invalid token request_id=%s token_prefix=%s reason=expired",
                request_id, token_prefix
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password setup link has expired"
            )
        
        # Validate password strength
        is_valid, message = validate_password_strength(data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Get portal user
        portal_user = await db.portal_users.find_one(
            {"portal_user_id": password_token["portal_user_id"]},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if this is an admin user - admin users don't need client provisioning check
        is_admin = portal_user.get("role") == UserRole.ROLE_ADMIN.value
        
        if not is_admin:
            # Check client provisioning only for non-admin users
            client = await db.clients.find_one(
                {"client_id": password_token["client_id"]},
                {"_id": 0}
            )
            
            if not client or client["onboarding_status"] != OnboardingStatus.PROVISIONED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Account provisioning incomplete"
                )
        
        # Hash password
        password_hash = hash_password(data.password)
        
        # Update portal user
        await db.portal_users.update_one(
            {"portal_user_id": portal_user["portal_user_id"]},
            {
                "$set": {
                    "password_hash": password_hash,
                    "password_status": PasswordStatus.SET.value,
                    "must_set_password": False,
                    "status": UserStatus.ACTIVE.value
                }
            }
        )
        
        # Mark token as used
        await db.password_tokens.update_one(
            {"token_hash": token_hash_value},
            {"$set": {"used": True, "used_at": now.isoformat()}}
        )
        
        # Audit logs - differentiate between admin invite acceptance and regular password setup
        is_admin_invite = password_token.get("client_id") == "ADMIN_INVITE"
        
        await create_audit_log(
            action=AuditAction.PASSWORD_TOKEN_VALIDATED,
            actor_id=portal_user["portal_user_id"],
            client_id=None if is_admin_invite else password_token.get("client_id")
        )
        
        if is_admin_invite:
            await create_audit_log(
                action=AuditAction.ADMIN_INVITE_ACCEPTED,
                actor_role=UserRole.ROLE_ADMIN,
                actor_id=portal_user["portal_user_id"],
                metadata={
                    "email": portal_user["auth_email"],
                    "accepted_at": now.isoformat()
                }
            )
        else:
            await create_audit_log(
                action=AuditAction.PASSWORD_SET_SUCCESS,
                actor_id=portal_user["portal_user_id"],
                client_id=password_token.get("client_id")
            )
            try:
                from services.onboarding_email_governance import milestone_set_payload

                cid_pw = password_token.get("client_id")
                if cid_pw:
                    await db.clients.update_one(
                        {"client_id": cid_pw},
                        {"$set": milestone_set_payload("password_set_at", now)},
                    )
                    logger.info("onboarding_milestone_password_set client_id=%s", cid_pw)
            except Exception as milexc:
                logger.warning("onboarding milestone password_set_at not persisted: %s", milexc)
            try:
                from services.analytics_service import log_event
                await log_event("password_set", {"client_id": password_token.get("client_id")})
            except Exception:
                pass
            try:
                from services.lead_automation_service import record_client_event, evaluate_client_automation_rules, EVENT_PASSWORD_SET
                client_id_for_event = password_token.get("client_id")
                if client_id_for_event:
                    await record_client_event(
                        client_id=client_id_for_event,
                        event_type=EVENT_PASSWORD_SET,
                        source="auth.password_set",
                        metadata={},
                    )
                    await evaluate_client_automation_rules(client_id_for_event, EVENT_PASSWORD_SET)
            except Exception:
                pass
            try:
                from services.onboarding_lifecycle_service import send_dashboard_ready_and_start_sequence

                await send_dashboard_ready_and_start_sequence(password_token.get("client_id"))
            except Exception as onb_err:
                logger.warning(
                    "send_dashboard_ready_and_start_sequence failed client_id=%s: %s",
                    password_token.get("client_id"),
                    onb_err,
                )
        
        # Create access token for auto-login (include session_version)
        token_data = {
            "portal_user_id": portal_user["portal_user_id"],
            "client_id": portal_user.get("client_id"),
            "email": portal_user["auth_email"],
            "role": portal_user["role"],
            "session_version": portal_user.get("session_version", 0),
        }
        access_token = create_access_token(token_data)
        
        await create_audit_log(
            action=AuditAction.USER_AUTHENTICATED_POST_SETUP,
            actor_role=UserRole(portal_user["role"]),
            actor_id=portal_user["portal_user_id"],
            client_id=portal_user.get("client_id")
        )
        
        return {
            "message": "Password set successfully",
            "access_token": access_token,
            "user": {
                "portal_user_id": portal_user["portal_user_id"],
                "email": portal_user["auth_email"],
                "role": portal_user["role"],
                "client_id": portal_user.get("client_id")
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set password"
        )


@router.post("/contractor-login", response_model=TokenResponse)
async def contractor_login(request: Request, credentials: LoginRequest):
    """Contractor portal login. Returns JWT with role=ROLE_CONTRACTOR and contractor_id."""
    ip = _client_ip(request)
    email_key = (credentials.email or "").strip().lower()
    try:
        from services.security_monitoring_service import get_auth_lock_state
        lock_state = await get_auth_lock_state(email=email_key, ip=ip, portal="contractor")
        if lock_state.get("locked"):
            retry_after = int(lock_state.get("retry_after_seconds") or 0)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "message": "Login temporarily locked due to repeated failed attempts. Try again later.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)} if retry_after > 0 else None,
            )
    except HTTPException:
        raise
    except Exception:
        pass
    cl = security_limits
    try:
        from services.contractor_portal_auth_service import verify_contractor_password
        from services import contractor_service
        acc = await verify_contractor_password(credentials.email, credentials.password)
        if not acc:
            await create_audit_log(
                action=AuditAction.USER_LOGIN_FAILED,
                metadata={"email": credentials.email, "reason": "contractor_invalid_credentials"}
            )
            try:
                from services.security_monitoring_service import record_security_event
                await record_security_event(
                    event_type="auth.login_failed",
                    ip=ip,
                    details={"email": email_key, "portal": "contractor"},
                    severity="medium",
                )
                from services.security_monitoring_service import get_auth_lock_state
                state = await get_auth_lock_state(email=email_key, ip=ip, portal="contractor")
                if state.get("locked") and state.get("lock_type") == "auth_email":
                    await _send_auth_lock_notification(
                        email=email_key,
                        portal="contractor",
                        retry_after_seconds=int(state.get("retry_after_seconds") or 0),
                    )
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        contractor_id = acc["contractor_id"]
        contractor = await contractor_service.get_contractor(contractor_id)
        if not contractor or (contractor.get("status") or "").lower() != contractor_service.STATUS_ACTIVE:
            await create_audit_log(
                action=AuditAction.USER_LOGIN_FAILED,
                metadata={"email": credentials.email, "contractor_id": contractor_id, "reason": "contractor_inactive"}
            )
            try:
                from services.security_monitoring_service import record_security_event
                await record_security_event(
                    event_type="auth.login_failed",
                    ip=ip,
                    details={"email": email_key, "portal": "contractor"},
                    severity="medium",
                )
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contractor account is not active")
        token_data = {
            "portal_user_id": f"contractor_{contractor_id}",
            "contractor_id": contractor_id,
            "email": acc["email"],
            "role": UserRole.ROLE_CONTRACTOR.value,
        }
        access_token = create_access_token(token_data)
        await create_audit_log(
            action=AuditAction.USER_LOGIN_SUCCESS,
            actor_id=contractor_id,
            metadata={"email": acc["email"], "contractor_id": contractor_id}
        )
        try:
            from services.security_monitoring_service import record_security_event
            await record_security_event(
                event_type="auth.login_success",
                user_id=token_data["portal_user_id"],
                ip=ip,
                details={"portal": "contractor"},
                severity="low",
            )
            from services.security_monitoring_service import clear_auth_lock
            had_lock = await clear_auth_lock(email=email_key, portal="contractor", reason="login_success")
            if had_lock:
                await _send_post_lock_recovery_notice(email=email_key, portal="contractor")
        except Exception:
            pass
        # No in-memory limiter state to clear here; lock state is DB-backed.
        return TokenResponse(
            access_token=access_token,
            user={
                "portal_user_id": token_data["portal_user_id"],
                "email": acc["email"],
                "role": UserRole.ROLE_CONTRACTOR.value,
                "contractor_id": contractor_id,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Contractor login error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post("/contractor-set-password")
async def contractor_set_password(request: Request, data: SetPasswordRequest):
    """Set password for contractor portal using invite token. Token must have purpose=contractor_invite and metadata.contractor_id, metadata.email."""
    if not data.token or not data.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token and password required")
    token_hash_value = hash_token(data.token)
    db = database.get_db()
    password_token = await db.password_tokens.find_one({"token_hash": token_hash_value}, {"_id": 0})
    if not password_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link")
    if password_token.get("used"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This link has already been used")
    expires_at = password_token.get("expires_at")
    if expires_at:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        exp = expires_at if isinstance(expires_at, datetime) else datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if now > exp:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This link has expired")
    if password_token.get("purpose") != "contractor_invite":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid link type")
    metadata = password_token.get("metadata") or {}
    contractor_id = metadata.get("contractor_id")
    email = (metadata.get("email") or "").strip().lower()
    if not contractor_id or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite data")
    is_valid, message = validate_password_strength(data.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    from services.contractor_portal_auth_service import create_account, set_password, get_account_by_contractor_id
    now = datetime.now(timezone.utc).isoformat()
    try:
        existing = await get_account_by_contractor_id(contractor_id)
        if existing:
            await set_password(contractor_id, data.password)
        else:
            await create_account(contractor_id, email, data.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.password_tokens.update_one(
        {"token_hash": token_hash_value},
        {"$set": {"used": True, "used_at": now}}
    )
    token_data = {
        "portal_user_id": f"contractor_{contractor_id}",
        "contractor_id": contractor_id,
        "email": email,
        "role": UserRole.ROLE_CONTRACTOR.value,
    }
    access_token = create_access_token(token_data)
    return {
        "message": "Password set successfully",
        "access_token": access_token,
        "user": {"portal_user_id": token_data["portal_user_id"], "email": email, "role": UserRole.ROLE_CONTRACTOR.value, "contractor_id": contractor_id},
    }


@router.post("/forgot-password")
async def forgot_password(request: Request, data: ForgotPasswordRequest):
    """
    Self-service password reset for client portal users.
    If the email matches a provisioned client portal user, sends a password-setup link.
    Always returns the same success message (no user enumeration).
    """
    ip = _client_ip(request)
    email_raw = (data.email or "").strip().lower()
    if not email_raw:
        return {"message": "If an account exists for this email, you will receive a link to set your password. Please check your inbox."}

    sl = security_limits
    # Rate limit by IP
    allowed, err_msg = await rate_limiter.check_rate_limit(
        f"forgot_password_ip:{ip}",
        sl.forgot_password_ip_max,
        sl.forgot_password_ip_window_minutes,
    )
    if not allowed:
        log_rate_limit_event("forgot_password_ip", ip, ip)
        await create_audit_log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            metadata={"scope": "forgot_password_ip", "ip": ip},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=err_msg or "Too many requests. Try again later.",
        )
    # Rate limit by email (abuse / spam)
    allowed_email, _ = await rate_limiter.check_rate_limit(
        f"forgot_password_email:{email_raw}",
        sl.forgot_password_email_max,
        sl.forgot_password_email_window_minutes,
    )
    if not allowed_email:
        return {"message": "If an account exists for this email, you will receive a link to set your password. Please check your inbox."}

    db = database.get_db()
    generic_message = "If an account exists for this email, you will receive a link to set your password. Please check your inbox and spam folder."

    try:
        portal_user = await db.portal_users.find_one(
            {"auth_email": {"$regex": f"^{re.escape(email_raw)}$", "$options": "i"}},
            {"_id": 0, "portal_user_id": 1, "auth_email": 1, "role": 1, "client_id": 1},
        )
        if not portal_user:
            await create_audit_log(
                action=AuditAction.FORGOT_PASSWORD_REQUESTED,
                metadata={"email_masked": email_raw[:3] + "***" if len(email_raw) > 5 else "***", "sent": False, "reason": "user_not_found"},
            )
            return {"message": generic_message}

        # Only client portal users get self-service reset; staff use admin flow
        if portal_user.get("role") in STAFF_PORTAL_ROLES:
            await create_audit_log(
                action=AuditAction.FORGOT_PASSWORD_REQUESTED,
                actor_id=portal_user.get("portal_user_id"),
                metadata={"email_masked": email_raw[:3] + "***", "sent": False, "reason": "staff_user"},
            )
            return {"message": generic_message}

        client_id = portal_user.get("client_id")
        if not client_id:
            await create_audit_log(
                action=AuditAction.FORGOT_PASSWORD_REQUESTED,
                actor_id=portal_user.get("portal_user_id"),
                metadata={"email_masked": email_raw[:3] + "***", "sent": False, "reason": "no_client"},
            )
            return {"message": generic_message}

        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "client_id": 1, "onboarding_status": 1, "email": 1, "contact_email": 1, "full_name": 1},
        )
        if not client or client.get("onboarding_status") != OnboardingStatus.PROVISIONED.value:
            await create_audit_log(
                action=AuditAction.FORGOT_PASSWORD_REQUESTED,
                actor_id=portal_user.get("portal_user_id"),
                client_id=client_id,
                metadata={"email_masked": email_raw[:3] + "***", "sent": False, "reason": "not_provisioned"},
            )
            return {"message": generic_message}

        # Revoke existing unused tokens for this user
        await db.password_tokens.update_many(
            {"portal_user_id": portal_user["portal_user_id"], "used_at": None, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}},
        )

        from models import PasswordToken
        from utils.public_app_url import get_frontend_base_url

        raw_token = generate_secure_token()
        token_hash_value = hash_token(raw_token)
        password_token = PasswordToken(
            token_hash=token_hash_value,
            portal_user_id=portal_user["portal_user_id"],
            client_id=client_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by="SELF_SERVICE",
            send_count=1,
        )
        doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if doc.get(key) and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()
        await db.password_tokens.insert_one(doc)

        try:
            base_url = get_frontend_base_url()
        except ValueError:
            await create_audit_log(
                action=AuditAction.FORGOT_PASSWORD_REQUESTED,
                actor_id=portal_user["portal_user_id"],
                client_id=client_id,
                metadata={"email_masked": email_raw[:3] + "***", "sent": False, "reason": "base_url_missing"},
            )
            return {"message": generic_message}

        setup_link = f"{base_url}/set-password?token={raw_token}"
        recipient = (client.get("contact_email") or client.get("email") or portal_user.get("auth_email") or "").strip()
        if not recipient:
            await create_audit_log(
                action=AuditAction.FORGOT_PASSWORD_REQUESTED,
                actor_id=portal_user["portal_user_id"],
                client_id=client_id,
                metadata={"email_masked": email_raw[:3] + "***", "sent": False, "reason": "no_recipient"},
            )
            return {"message": generic_message}

        from services.notification_orchestrator import notification_orchestrator

        result = await notification_orchestrator.send(
            template_key="PASSWORD_RESET",
            client_id=client_id,
            context={
                "subject": "Reset your password",
                "recipient": recipient,
                "setup_link": setup_link,
                "client_name": client.get("full_name") or "Customer",
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance",
            },
            idempotency_key=None,
            event_type="forgot_password",
        )

        sent = result.outcome == "sent"
        await create_audit_log(
            action=AuditAction.FORGOT_PASSWORD_REQUESTED,
            actor_id=portal_user["portal_user_id"],
            client_id=client_id,
            metadata={
                "email_masked": email_raw[:3] + "***",
                "sent": sent,
                "reason": "email_sent" if sent else (result.block_reason or result.error_message or "send_failed"),
            },
        )
        return {"message": generic_message}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Forgot password error: %s", e)
        return {"message": generic_message}


@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(request: Request, credentials: LoginRequest):
    """
    Admin login endpoint - FULLY INDEPENDENT of client provisioning.
    
    Admins:
    - Do NOT require a Client record
    - Are NOT blocked by onboarding_status, provisioning, or client guards
    - Can log in as long as they have a valid password and ACTIVE status
    """
    ip = _client_ip(request)
    email_key = (credentials.email or "").strip().lower()
    try:
        from services.security_monitoring_service import get_auth_lock_state
        lock_state = await get_auth_lock_state(email=email_key, ip=ip, portal="admin")
        if lock_state.get("locked"):
            retry_after = int(lock_state.get("retry_after_seconds") or 0)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "message": "Login temporarily locked due to repeated failed attempts. Try again later.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)} if retry_after > 0 else None,
            )
    except HTTPException:
        raise
    except Exception:
        pass
    al = security_limits
    db = database.get_db()

    async def _record_admin_failure() -> None:
        try:
            from services.security_monitoring_service import record_security_event
            await record_security_event(
                event_type="auth.login_failed",
                ip=ip,
                details={"email": email_key, "portal": "admin"},
                severity="medium",
            )
            try:
                from services.security_monitoring_service import get_auth_lock_state
                state = await get_auth_lock_state(email=email_key, ip=ip, portal="admin")
                if state.get("locked") and state.get("lock_type") == "auth_email":
                    await _send_auth_lock_notification(
                        email=email_key,
                        portal="admin",
                        retry_after_seconds=int(state.get("retry_after_seconds") or 0),
                    )
            except Exception:
                pass
        except Exception:
            pass

    try:
        # Find user by email (any role); role check happens after password verification
        portal_user = await db.portal_users.find_one(
            {"auth_email": {"$regex": f"^{re.escape(email_key)}$", "$options": "i"}},
            {"_id": 0}
        )
        
        if not portal_user:
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                metadata={"email": credentials.email, "reason": "admin_not_found"}
            )
            await _record_admin_failure()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password exists and is correct
        if not portal_user.get("password_hash") or not verify_password(
            credentials.password,
            portal_user["password_hash"]
        ):
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "invalid_password"}
            )
            await _record_admin_failure()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Enforce staff portal: only staff roles may use this endpoint
        if portal_user.get("role") not in STAFF_PORTAL_ROLES:
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "client_use_staff_portal"}
            )
            await _record_admin_failure()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account must sign in via the Client portal."
            )
        
        # Check user status - admin must be ACTIVE
        if portal_user.get("status") != UserStatus.ACTIVE.value:
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "account_not_active", "status": portal_user.get("status")}
            )
            await _record_admin_failure()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active"
            )
        
        # Check password status - must have set password
        if portal_user.get("password_status") != PasswordStatus.SET.value:
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "password_not_set"}
            )
            await _record_admin_failure()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password not set"
            )

        # Optional production hardening: enforce MFA challenge for staff/admin login.
        if _admin_mfa_required():
            challenge_id = (credentials.mfa_challenge_id or "").strip()
            code = (credentials.mfa_code or "").strip()
            if not challenge_id or not code:
                challenge = await _issue_admin_mfa_challenge(portal_user, ip)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error_code": "MFA_REQUIRED",
                        "message": "Multi-factor verification required. Enter the code sent to your email.",
                        "mfa_challenge_id": challenge["challenge_id"],
                        "expires_in_seconds": challenge["expires_in_seconds"],
                    },
                )
            ok = await _verify_admin_mfa_challenge(portal_user, ip, challenge_id, code)
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"error_code": "MFA_INVALID", "message": "Invalid or expired MFA code."},
                )
        
        # Update last login timestamp
        await db.portal_users.update_one(
            {"portal_user_id": portal_user["portal_user_id"]},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Create access token (include session_version for force-logout invalidation)
        token_data = {
            "portal_user_id": portal_user["portal_user_id"],
            "client_id": None,
            "email": portal_user["auth_email"],
            "role": portal_user["role"],
            "session_version": portal_user.get("session_version", 0),
        }
        access_token = create_access_token(token_data)
        
        await create_audit_log(
            action=AuditAction.ADMIN_LOGIN_SUCCESS,
            actor_role=UserRole(portal_user["role"]),
            actor_id=portal_user["portal_user_id"],
            metadata={"email": credentials.email}
        )
        try:
            from services.security_monitoring_service import record_security_event
            await record_security_event(
                event_type="auth.login_success",
                user_id=portal_user["portal_user_id"],
                ip=ip,
                details={"portal": "admin", "role": portal_user.get("role")},
                severity="low",
            )
            from services.security_monitoring_service import clear_auth_lock
            had_lock = await clear_auth_lock(email=email_key, portal="admin", reason="login_success")
            if had_lock:
                await _send_post_lock_recovery_notice(email=email_key, portal="admin")
        except Exception:
            pass
        # No in-memory limiter state to clear here; lock state is DB-backed.
        
        return TokenResponse(
            access_token=access_token,
            user={
                "portal_user_id": portal_user["portal_user_id"],
                "email": portal_user["auth_email"],
                "role": portal_user["role"]
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )



@router.post("/break-glass")
async def break_glass_reset_owner_password(request: Request):
    """
    Break-glass: reset OWNER password when locked out. Enabled only if BREAK_GLASS_ENABLED=true.
    Protected by BOOTSTRAP_SECRET (header X-Break-Glass-Secret or Authorization Bearer).
    Resets first OWNER's password, increments session_version (force logout), writes BREAK_GLASS_OWNER_USED audit.
    Do not log or return plaintext password.
    """
    import os
    if os.environ.get("BREAK_GLASS_ENABLED", "").strip().lower() != "true":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    secret = os.environ.get("BOOTSTRAP_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Break-glass not configured")
    auth_header = request.headers.get("Authorization", "")
    header_secret = request.headers.get("X-Break-Glass-Secret", "").strip() or (auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else "")
    if header_secret != secret:
        await create_audit_log(action=AuditAction.BREAK_GLASS_OWNER_USED, metadata={"outcome": "invalid_secret"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    new_password = (body.get("new_password") or "").strip()
    if not new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new_password required")
    is_valid, msg = validate_password_strength(new_password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    db = database.get_db()
    owner = await db.portal_users.find_one(
        {"role": UserRole.ROLE_OWNER.value},
        {"_id": 0, "portal_user_id": 1, "auth_email": 1}
    )
    if not owner:
        await create_audit_log(action=AuditAction.BREAK_GLASS_OWNER_USED, metadata={"outcome": "no_owner"})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No OWNER found")
    pid = owner["portal_user_id"]
    await db.portal_users.update_one(
        {"portal_user_id": pid},
        {"$set": {"password_hash": hash_password(new_password)}, "$inc": {"session_version": 1}}
    )
    await create_audit_log(
        action=AuditAction.BREAK_GLASS_OWNER_USED,
        actor_id=pid,
        resource_type="portal_user",
        resource_id=pid,
        metadata={"outcome": "success", "auth_email": owner.get("auth_email")}
    )
    return {"message": "OWNER password reset; all sessions invalidated"}


@router.post("/log-route-guard-block")
async def log_route_guard_block(request: Request):
    """Log when a non-admin user attempts to access admin routes.
    
    This endpoint is called by the frontend when the route guard blocks access.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header else None
        
        user_info = {}
        if token:
            from auth import decode_access_token
            payload = decode_access_token(token)
            if payload:
                user_info = {
                    "portal_user_id": payload.get("portal_user_id"),
                    "email": payload.get("email"),
                    "role": payload.get("role")
                }
        
        # Get attempted path from request body
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        attempted_path = body.get("attempted_path", "unknown")
        
        await create_audit_log(
            action=AuditAction.ADMIN_ROUTE_GUARD_BLOCK,
            actor_id=user_info.get("portal_user_id"),
            metadata={
                "attempted_path": attempted_path,
                "user_role": user_info.get("role"),
                "email": user_info.get("email"),
                "reason": "non_admin_accessing_admin_route"
            }
        )
        
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Failed to log route guard block: {e}")
        return {"status": "error"}