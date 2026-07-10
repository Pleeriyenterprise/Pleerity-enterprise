"""Zoho OAuth token management with per-integration DB cache (Option B)."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from database import database
from services.integrations.zoho.config import zoho_accounts_url, zoho_environment
from services.integrations.zoho.credential_resolver import ResolvedOAuthCredentials, resolve_oauth_credentials
from services.integrations.zoho.types import ZOHO_OAUTH_TOKENS_COLLECTION

logger = logging.getLogger(__name__)

# Legacy single-token cache id — retained for reference; new caches use per-integration ids.
LEGACY_TOKEN_DOC_ID = "zoho_oauth_access_token"
ACCESS_TOKEN_BUFFER_SECONDS = 300


class ZohoOAuthError(Exception):
    pass


class ZohoOAuthManager:
    async def get_access_token(self, integration: str) -> Optional[str]:
        credentials = resolve_oauth_credentials(integration)
        if not credentials or not credentials.credentials_configured:
            return None

        cached = await self._get_cached_token(credentials)
        if cached:
            await self._touch_validation(credentials.cache_identifier)
            return cached
        return await self._refresh_access_token(credentials)

    async def _get_cached_token(self, credentials: ResolvedOAuthCredentials) -> Optional[str]:
        db = database.get_db()
        doc = await db[ZOHO_OAUTH_TOKENS_COLLECTION].find_one(
            {"token_id": credentials.cache_identifier, "environment": zoho_environment()},
            {"_id": 0},
        )
        if not doc:
            return None
        expires_at = float(doc.get("expires_at") or 0)
        if time.time() >= expires_at - ACCESS_TOKEN_BUFFER_SECONDS:
            return None
        return doc.get("access_token")

    async def _refresh_access_token(self, credentials: ResolvedOAuthCredentials) -> Optional[str]:
        url = f"{zoho_accounts_url()}/oauth/v2/token"
        params = {
            "refresh_token": credentials.refresh_token,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "grant_type": "refresh_token",
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, timeout=15.0)
                if response.status_code != 200:
                    await self._record_auth_failure(credentials.cache_identifier, response.status_code)
                    logger.error(
                        "Zoho OAuth refresh failed for %s: %s %s",
                        credentials.integration,
                        response.status_code,
                        response.text[:200],
                    )
                    return None
                data = response.json()
                access_token = data.get("access_token")
                if not access_token:
                    await self._record_auth_failure(credentials.cache_identifier, response.status_code)
                    return None
                expires_in = int(data.get("expires_in") or 3600)
                await self._store_token(credentials, access_token, expires_in)
                return access_token
        except Exception as exc:
            await self._record_auth_failure(credentials.cache_identifier, None, str(exc))
            logger.error("Zoho OAuth refresh error for %s: %s", credentials.integration, exc)
            return None

    async def _store_token(
        self,
        credentials: ResolvedOAuthCredentials,
        access_token: str,
        expires_in: int,
    ) -> None:
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        expires_at = time.time() + expires_in
        await db[ZOHO_OAUTH_TOKENS_COLLECTION].update_one(
            {"token_id": credentials.cache_identifier, "environment": zoho_environment()},
            {
                "$set": {
                    "token_id": credentials.cache_identifier,
                    "integration": credentials.integration,
                    "environment": zoho_environment(),
                    "access_token": access_token,
                    "expires_at": expires_at,
                    "updated_at": now,
                    "last_successful_refresh_at": now,
                    "last_validation_at": now,
                    "refresh_token_source": credentials.refresh_token_source.value,
                    "auth_failure_count": 0,
                    "last_auth_failure_at": None,
                    "last_auth_failure_detail": None,
                }
            },
            upsert=True,
        )

    async def _touch_validation(self, cache_identifier: str) -> None:
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        await db[ZOHO_OAUTH_TOKENS_COLLECTION].update_one(
            {"token_id": cache_identifier, "environment": zoho_environment()},
            {"$set": {"last_validation_at": now}},
        )

    async def _record_auth_failure(
        self,
        cache_identifier: str,
        status_code: Optional[int],
        detail: Optional[str] = None,
    ) -> None:
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        failure_detail = detail or (f"http_{status_code}" if status_code else "unknown")
        await db[ZOHO_OAUTH_TOKENS_COLLECTION].update_one(
            {"token_id": cache_identifier, "environment": zoho_environment()},
            {
                "$set": {
                    "last_auth_failure_at": now,
                    "last_auth_failure_detail": failure_detail,
                },
                "$inc": {"auth_failure_count": 1},
            },
            upsert=True,
        )

    async def invalidate(self, integration: Optional[str] = None) -> None:
        db = database.get_db()
        if integration:
            credentials = resolve_oauth_credentials(integration)
            if not credentials:
                return
            await db[ZOHO_OAUTH_TOKENS_COLLECTION].delete_one(
                {"token_id": credentials.cache_identifier, "environment": zoho_environment()}
            )
            return

        await db[ZOHO_OAUTH_TOKENS_COLLECTION].delete_many({"environment": zoho_environment()})

    async def get_token_metadata(self, integration: str) -> Dict[str, Any]:
        credentials = resolve_oauth_credentials(integration)
        if not credentials:
            return {}
        db = database.get_db()
        return (
            await db[ZOHO_OAUTH_TOKENS_COLLECTION].find_one(
                {"token_id": credentials.cache_identifier, "environment": zoho_environment()},
                {
                    "_id": 0,
                    "expires_at": 1,
                    "updated_at": 1,
                    "last_successful_refresh_at": 1,
                    "last_validation_at": 1,
                    "auth_failure_count": 1,
                    "last_auth_failure_at": 1,
                    "refresh_token_source": 1,
                },
            )
            or {}
        )


zoho_oauth_manager = ZohoOAuthManager()
