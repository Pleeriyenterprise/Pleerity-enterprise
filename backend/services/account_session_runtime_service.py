"""
Session Runtime Authority (ILP-5).

Binds authenticated portal sessions to the Runtime Contract without embedding
permissions in JWTs. JWT carries identity + version hints for staleness detection only.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from fastapi import HTTPException, status

from services.account_lifecycle_runtime_contract import (
    CONTRACT_VERSION,
    resolve_runtime_contract_for_client,
    runtime_contract_to_dict,
)

logger = logging.getLogger(__name__)

SESSION_RUNTIME_COLLECTION = "portal_session_runtime"


class SessionRuntimeState(str, Enum):
    ACTIVE = "ACTIVE"
    REFRESH_REQUIRED = "REFRESH_REQUIRED"
    FORCE_REAUTH = "FORCE_REAUTH"
    TERMINATED = "TERMINATED"


class SessionRefreshAction(str, Enum):
    CONTINUE = "CONTINUE"
    REFRESH_RUNTIME = "REFRESH_RUNTIME"
    REFRESH_TOKEN = "REFRESH_TOKEN"
    FORCE_REAUTH = "FORCE_REAUTH"


CLIENT_PORTAL_ROLES = frozenset({"ROLE_CLIENT", "ROLE_CLIENT_ADMIN"})


@dataclass(frozen=True)
class SessionValidationResult:
    action: SessionRefreshAction
    session_state: SessionRuntimeState
    reasons: List[str] = field(default_factory=list)
    runtime_version: Optional[int] = None
    entitlements_version: Optional[int] = None
    contract_version: str = CONTRACT_VERSION
    lifecycle_state: Optional[str] = None
    portal_mode: Optional[str] = None
    force_refresh: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "session_state": self.session_state.value,
            "reasons": list(self.reasons),
            "runtime_version": self.runtime_version,
            "entitlements_version": self.entitlements_version,
            "contract_version": self.contract_version,
            "lifecycle_state": self.lifecycle_state,
            "portal_mode": self.portal_mode,
            "force_refresh": self.force_refresh,
        }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _session_policy(contract: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(contract.get("session_policy") or {})


def is_client_portal_user(user: Optional[Mapping[str, Any]]) -> bool:
    if not user:
        return False
    role = (user.get("role") or "").strip()
    return role in CLIENT_PORTAL_ROLES and bool(user.get("client_id"))


def build_client_auth_claims(
    portal_user: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    session_id: str,
) -> Dict[str, Any]:
    """
    Authentication claims for client portal JWTs.
    Version fields are staleness hints only — never used as permission authority.
    """
    policy = _session_policy(contract)
    now = _utcnow()
    claims: Dict[str, Any] = {
        "portal_user_id": portal_user["portal_user_id"],
        "client_id": portal_user.get("client_id"),
        "email": portal_user["auth_email"],
        "role": portal_user["role"],
        "session_version": int(portal_user.get("session_version") or 0),
        "session_id": session_id,
        "runtime_version": int(contract.get("runtime_version") or 0),
        "contract_version": str(contract.get("contract_version") or CONTRACT_VERSION),
        "entitlements_version": int(policy.get("entitlements_version") or 1),
        "issued_at": int(now.timestamp()),
    }
    return claims


def session_runtime_document(
    *,
    session_id: str,
    portal_user_id: str,
    client_id: str,
    contract: Mapping[str, Any],
    refresh_reason: str = "login",
) -> Dict[str, Any]:
    policy = _session_policy(contract)
    now = _utcnow()
    now_iso = _iso(now)
    return {
        "session_id": session_id,
        "portal_user_id": portal_user_id,
        "client_id": client_id,
        "runtime_version": int(contract.get("runtime_version") or 0),
        "contract_version": str(contract.get("contract_version") or CONTRACT_VERSION),
        "entitlements_version": int(policy.get("entitlements_version") or 1),
        "issued_at": now_iso,
        "last_runtime_validation": now_iso,
        "last_runtime_refresh": now_iso,
        "last_capability_refresh": now_iso,
        "refresh_reason": refresh_reason,
        "session_state": SessionRuntimeState.ACTIVE.value,
        "lifecycle_state": contract.get("lifecycle_state"),
        "portal_mode": contract.get("portal_mode"),
    }


def validate_session_against_contract(
    jwt_claims: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    session_record: Optional[Mapping[str, Any]] = None,
) -> SessionValidationResult:
    """
    Compare JWT/session version hints with the authoritative Runtime Contract.
    Does not evaluate capabilities — contract remains sole permission authority.
    """
    policy = _session_policy(contract)
    reasons: List[str] = []
    lifecycle_state = str(contract.get("lifecycle_state") or "")
    portal_mode = str(contract.get("portal_mode") or "")
    current_runtime = int(contract.get("runtime_version") or 0)
    current_entitlements = int(policy.get("entitlements_version") or 1)
    current_contract_version = str(contract.get("contract_version") or CONTRACT_VERSION)

    if policy.get("force_reauth"):
        return SessionValidationResult(
            action=SessionRefreshAction.FORCE_REAUTH,
            session_state=SessionRuntimeState.FORCE_REAUTH,
            reasons=["session_policy_force_reauth"],
            runtime_version=current_runtime,
            entitlements_version=current_entitlements,
            contract_version=current_contract_version,
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            force_refresh=True,
        )

    if not policy.get("jwt_valid", True):
        return SessionValidationResult(
            action=SessionRefreshAction.FORCE_REAUTH,
            session_state=SessionRuntimeState.TERMINATED,
            reasons=["session_policy_jwt_invalid"],
            runtime_version=current_runtime,
            entitlements_version=current_entitlements,
            contract_version=current_contract_version,
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            force_refresh=True,
        )

    jwt_runtime = jwt_claims.get("runtime_version")
    jwt_entitlements = jwt_claims.get("entitlements_version")
    jwt_contract = jwt_claims.get("contract_version")
    jwt_session_id = jwt_claims.get("session_id")

    if jwt_runtime is not None and int(jwt_runtime) != current_runtime:
        reasons.append("runtime_version_changed")
    if jwt_entitlements is not None and int(jwt_entitlements) != current_entitlements:
        reasons.append("entitlements_version_changed")
    if jwt_contract is not None and str(jwt_contract) != current_contract_version:
        reasons.append("contract_version_changed")

    if session_record:
        rec_runtime = int(session_record.get("runtime_version") or 0)
        rec_entitlements = int(session_record.get("entitlements_version") or 0)
        if rec_runtime != current_runtime:
            reasons.append("session_record_runtime_stale")
        if rec_entitlements != current_entitlements:
            reasons.append("session_record_entitlements_stale")
        if jwt_session_id and session_record.get("session_id") != jwt_session_id:
            reasons.append("session_id_mismatch")
        stored_lifecycle = session_record.get("lifecycle_state")
        stored_portal = session_record.get("portal_mode")
        if stored_lifecycle and stored_lifecycle != lifecycle_state:
            reasons.append("lifecycle_state_changed")
        if stored_portal and stored_portal != portal_mode:
            reasons.append("portal_mode_changed")

    if reasons:
        needs_token = any(
            r in reasons
            for r in (
                "entitlements_version_changed",
                "session_record_entitlements_stale",
                "contract_version_changed",
            )
        )
        return SessionValidationResult(
            action=SessionRefreshAction.REFRESH_TOKEN if needs_token else SessionRefreshAction.REFRESH_RUNTIME,
            session_state=SessionRuntimeState.REFRESH_REQUIRED,
            reasons=reasons,
            runtime_version=current_runtime,
            entitlements_version=current_entitlements,
            contract_version=current_contract_version,
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            force_refresh=True,
        )

    return SessionValidationResult(
        action=SessionRefreshAction.CONTINUE,
        session_state=SessionRuntimeState.ACTIVE,
        runtime_version=current_runtime,
        entitlements_version=current_entitlements,
        contract_version=current_contract_version,
        lifecycle_state=lifecycle_state,
        portal_mode=portal_mode,
        force_refresh=False,
    )


def enforce_terminal_session_policy(contract: Mapping[str, Any]) -> None:
    """Raise 401 when session_policy requires re-authentication."""
    validation = validate_session_against_contract({}, contract)
    if validation.action == SessionRefreshAction.FORCE_REAUTH:
        code = (
            "SESSION_FORCE_REAUTH"
            if "session_policy_force_reauth" in validation.reasons
            else "SESSION_TERMINATED"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": code,
                "message": "Session is no longer valid. Please sign in again.",
                "lifecycle_state": validation.lifecycle_state,
                "portal_mode": validation.portal_mode,
            },
        )


class SessionRuntimeService:
    """Persists and refreshes portal session runtime metadata."""

    def __init__(self, db):
        self.db = db

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None
        return await self.db[SESSION_RUNTIME_COLLECTION].find_one(
            {"session_id": session_id},
            {"_id": 0},
        )

    async def create_session(
        self,
        *,
        portal_user_id: str,
        client_id: str,
        contract: Mapping[str, Any],
        refresh_reason: str = "login",
    ) -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        doc = session_runtime_document(
            session_id=session_id,
            portal_user_id=portal_user_id,
            client_id=client_id,
            contract=contract,
            refresh_reason=refresh_reason,
        )
        await self.db[SESSION_RUNTIME_COLLECTION].insert_one(doc)
        return doc

    async def touch_validation(self, session_id: str) -> None:
        if not session_id:
            return
        await self.db[SESSION_RUNTIME_COLLECTION].update_one(
            {"session_id": session_id},
            {"$set": {"last_runtime_validation": _iso(_utcnow())}},
        )

    async def refresh_session(
        self,
        *,
        session_id: str,
        portal_user_id: str,
        client_id: str,
        refresh_reason: str,
        contract: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if contract is None:
            contract = await resolve_runtime_contract_for_client(self.db, client_id)
        now_iso = _iso(_utcnow())
        policy = _session_policy(contract)
        update = {
            "runtime_version": int(contract.get("runtime_version") or 0),
            "contract_version": str(contract.get("contract_version") or CONTRACT_VERSION),
            "entitlements_version": int(policy.get("entitlements_version") or 1),
            "last_runtime_refresh": now_iso,
            "last_capability_refresh": now_iso,
            "last_runtime_validation": now_iso,
            "refresh_reason": refresh_reason,
            "session_state": SessionRuntimeState.ACTIVE.value,
            "lifecycle_state": contract.get("lifecycle_state"),
            "portal_mode": contract.get("portal_mode"),
        }
        existing = await self.get_session(session_id)
        if existing:
            await self.db[SESSION_RUNTIME_COLLECTION].update_one(
                {"session_id": session_id, "portal_user_id": portal_user_id},
                {"$set": update},
            )
            return {**existing, **update}
        doc = session_runtime_document(
            session_id=session_id or str(uuid.uuid4()),
            portal_user_id=portal_user_id,
            client_id=client_id,
            contract=contract,
            refresh_reason=refresh_reason,
        )
        await self.db[SESSION_RUNTIME_COLLECTION].insert_one(doc)
        return doc

    async def validate_for_user(
        self,
        user: Mapping[str, Any],
        *,
        header_runtime_version: Optional[int] = None,
        header_entitlements_version: Optional[int] = None,
    ) -> SessionValidationResult:
        client_id = user.get("client_id")
        if not client_id:
            return SessionValidationResult(
                action=SessionRefreshAction.CONTINUE,
                session_state=SessionRuntimeState.ACTIVE,
            )
        contract = await resolve_runtime_contract_for_client(self.db, client_id)
        enforce_terminal_session_policy(contract)

        session_id = user.get("session_id")
        session_record = await self.get_session(session_id) if session_id else None
        result = validate_session_against_contract(user, contract, session_record=session_record)

        if header_runtime_version is not None:
            current = int(contract.get("runtime_version") or 0)
            if int(header_runtime_version) != current and "runtime_version_changed" not in result.reasons:
                result = SessionValidationResult(
                    action=SessionRefreshAction.REFRESH_RUNTIME,
                    session_state=SessionRuntimeState.REFRESH_REQUIRED,
                    reasons=[*result.reasons, "header_runtime_version_stale"],
                    runtime_version=current,
                    entitlements_version=int(_session_policy(contract).get("entitlements_version") or 1),
                    contract_version=str(contract.get("contract_version") or CONTRACT_VERSION),
                    lifecycle_state=str(contract.get("lifecycle_state") or ""),
                    portal_mode=str(contract.get("portal_mode") or ""),
                    force_refresh=True,
                )
        if header_entitlements_version is not None:
            current_e = int(_session_policy(contract).get("entitlements_version") or 1)
            if int(header_entitlements_version) != current_e and "entitlements_version_changed" not in result.reasons:
                result = SessionValidationResult(
                    action=SessionRefreshAction.REFRESH_TOKEN,
                    session_state=SessionRuntimeState.REFRESH_REQUIRED,
                    reasons=[*result.reasons, "header_entitlements_version_stale"],
                    runtime_version=int(contract.get("runtime_version") or 0),
                    entitlements_version=current_e,
                    contract_version=str(contract.get("contract_version") or CONTRACT_VERSION),
                    lifecycle_state=str(contract.get("lifecycle_state") or ""),
                    portal_mode=str(contract.get("portal_mode") or ""),
                    force_refresh=True,
                )

        if session_id and result.action == SessionRefreshAction.CONTINUE:
            await self.touch_validation(session_id)
        return result

    async def issue_client_access_token(
        self,
        portal_user: Mapping[str, Any],
        *,
        refresh_reason: str = "login",
        session_id: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any], Dict[str, Any]]:
        """Issue JWT with authentication + version-hint claims (not permissions)."""
        from auth import create_access_token

        client_id = portal_user.get("client_id")
        if not client_id:
            raise ValueError("client_id required for client portal token")
        contract = await resolve_runtime_contract_for_client(self.db, client_id, use_cache=False)
        enforce_terminal_session_policy(contract)
        if session_id:
            session_doc = await self.refresh_session(
                session_id=session_id,
                portal_user_id=portal_user["portal_user_id"],
                client_id=client_id,
                refresh_reason=refresh_reason,
                contract=contract,
            )
        else:
            session_doc = await self.create_session(
                portal_user_id=portal_user["portal_user_id"],
                client_id=client_id,
                contract=contract,
                refresh_reason=refresh_reason,
            )
        claims = build_client_auth_claims(portal_user, contract, session_id=session_doc["session_id"])
        token = create_access_token(dict(claims))
        return token, claims, session_doc

    async def build_refresh_payload(
        self,
        user: Mapping[str, Any],
        portal_user: Mapping[str, Any],
        *,
        refresh_reason: str,
    ) -> Dict[str, Any]:
        client_id = user["client_id"]
        session_id = user.get("session_id") or str(uuid.uuid4())
        contract = await resolve_runtime_contract_for_client(self.db, client_id, use_cache=False)
        enforce_terminal_session_policy(contract)
        session_doc = await self.refresh_session(
            session_id=session_id,
            portal_user_id=user["portal_user_id"],
            client_id=client_id,
            refresh_reason=refresh_reason,
            contract=contract,
        )
        validation = validate_session_against_contract(user, contract, session_record=session_doc)
        payload = runtime_contract_to_dict(contract)
        return {
            "session_runtime": session_doc,
            "lifecycle_runtime": payload,
            "validation": validation.to_dict(),
            "auth_claims": build_client_auth_claims(portal_user, contract, session_id=session_doc["session_id"]),
        }


def client_portal_user_out(portal_user: Mapping[str, Any], session_doc: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "portal_user_id": portal_user["portal_user_id"],
        "email": portal_user["auth_email"],
        "role": portal_user["role"],
        "client_id": portal_user.get("client_id"),
        "session_id": session_doc.get("session_id"),
        "runtime_version": session_doc.get("runtime_version"),
        "entitlements_version": session_doc.get("entitlements_version"),
    }


async def issue_client_portal_login_token(
    db,
    portal_user: Mapping[str, Any],
    *,
    refresh_reason: str = "login",
    session_id: Optional[str] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_delta=None,
) -> tuple[str, Dict[str, Any]]:
    """Issue client portal JWT + user payload with session runtime metadata."""
    from auth import create_access_token

    service = SessionRuntimeService(db)
    token, claims, session_doc = await service.issue_client_access_token(
        portal_user,
        refresh_reason=refresh_reason,
        session_id=session_id,
    )
    if extra_claims:
        claims = {**claims, **extra_claims}
        token = create_access_token(dict(claims), expires_delta=expires_delta)
    return token, client_portal_user_out(portal_user, session_doc)
