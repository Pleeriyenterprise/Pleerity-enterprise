"""Zoho OAuth token management with DB cache."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from database import database
from services.integrations.zoho.config import (
    zoho_accounts_url,
    zoho_client_id,
    zoho_client_secret,
    zoho_credentials_configured,
    zoho_environment,
    zoho_refresh_token,
)
from services.integrations.zoho.types import ZOHO_OAUTH_TOKENS_COLLECTION

logger = logging.getLogger(__name__)

TOKEN_DOC_ID = "zoho_oauth_access_token"
ACCESS_TOKEN_BUFFER_SECONDS = 300


class ZohoOAuthError(Exception):
    pass


class ZohoOAuthManager:
    async def get_access_token(self) -> Optional[str]:
        if not zoho_credentials_configured():
            return None
        cached = await self._get_cached_token()
        if cached:
            return cached
        return await self._refresh_access_token()

    async def _get_cached_token(self) -> Optional[str]:
        db = database.get_db()
        doc = await db[ZOHO_OAUTH_TOKENS_COLLECTION].find_one(
            {"token_id": TOKEN_DOC_ID, "environment": zoho_environment()},
            {"_id": 0},
        )
        if not doc:
            return None
        expires_at = float(doc.get("expires_at") or 0)
        if time.time() >= expires_at - ACCESS_TOKEN_BUFFER_SECONDS:
            return None
        return doc.get("access_token")

    async def _refresh_access_token(self) -> Optional[str]:
        refresh = zoho_refresh_token()
        if not refresh:
            return None
        url = f"{zoho_accounts_url()}/oauth/v2/token"
        params = {
            "refresh_token": refresh,
            "client_id": zoho_client_id(),
            "client_secret": zoho_client_secret(),
            "grant_type": "refresh_token",
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, timeout=15.0)
                if response.status_code != 200:
                    logger.error("Zoho OAuth refresh failed: %s %s", response.status_code, response.text[:200])
                    return None
                data = response.json()
                access_token = data.get("access_token")
                if not access_token:
                    return None
                expires_in = int(data.get("expires_in") or 3600)
                await self._store_token(access_token, expires_in)
                return access_token
        except Exception as exc:
            logger.error("Zoho OAuth refresh error: %s", exc)
            return None

    async def _store_token(self, access_token: str, expires_in: int) -> None:
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        expires_at = time.time() + expires_in
        await db[ZOHO_OAUTH_TOKENS_COLLECTION].update_one(
            {"token_id": TOKEN_DOC_ID, "environment": zoho_environment()},
            {
                "$set": {
                    "token_id": TOKEN_DOC_ID,
                    "environment": zoho_environment(),
                    "access_token": access_token,
                    "expires_at": expires_at,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

    async def invalidate(self) -> None:
        db = database.get_db()
        await db[ZOHO_OAUTH_TOKENS_COLLECTION].delete_one(
            {"token_id": TOKEN_DOC_ID, "environment": zoho_environment()}
        )


zoho_oauth_manager = ZohoOAuthManager()
