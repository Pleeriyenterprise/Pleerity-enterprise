"""HTTP client for Zoho APIs with rate-limit awareness."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from services.integrations.zoho.circuit_breaker import zoho_circuit_breaker
from services.integrations.zoho.config import zoho_api_base
from services.integrations.zoho.oauth import zoho_oauth_manager

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ZohoApiError(Exception):
    def __init__(self, status_code: int, message: str, retryable: bool = False):
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)


class ZohoHttpClient:
    async def request(
        self,
        method: str,
        path: str,
        *,
        integration: str = "global",
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        if zoho_circuit_breaker.is_open(integration):
            return False, None, "circuit_breaker_open"

        token = await zoho_oauth_manager.get_access_token()
        if not token:
            return False, None, "no_access_token"

        url = path if path.startswith("http") else f"{zoho_api_base()}{path}"
        headers = {"Authorization": f"Zoho-oauthtoken {token}", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    params=params,
                    timeout=30.0,
                )
                if response.status_code in (200, 201, 202):
                    zoho_circuit_breaker.record_success(integration)
                    try:
                        return True, response.json(), None
                    except Exception:
                        return True, {"raw": response.text}, None

                retryable = response.status_code in RETRYABLE_STATUS
                if retryable:
                    zoho_circuit_breaker.record_failure(integration)
                msg = f"Zoho API {response.status_code}: {response.text[:300]}"
                logger.warning(msg)
                return False, None, msg
        except httpx.TimeoutException:
            zoho_circuit_breaker.record_failure(integration)
            return False, None, "timeout"
        except Exception as exc:
            zoho_circuit_breaker.record_failure(integration)
            return False, None, str(exc)


zoho_http_client = ZohoHttpClient()
