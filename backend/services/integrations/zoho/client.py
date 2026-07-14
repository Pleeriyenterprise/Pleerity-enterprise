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
        headers: Optional[Dict[str, str]] = None,
        form_data: Optional[Dict[str, str]] = None,
        api_base: Optional[str] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        if zoho_circuit_breaker.is_open(integration):
            return False, None, "circuit_breaker_open"

        token = await zoho_oauth_manager.get_access_token(integration)
        if not token:
            return False, None, "no_access_token"

        base = (api_base or zoho_api_base()).rstrip("/")
        url = path if path.startswith("http") else f"{base}{path}"
        req_headers: Dict[str, str] = {
            "Authorization": f"Zoho-oauthtoken {token}",
        }
        if headers:
            req_headers.update(headers)

        try:
            async with httpx.AsyncClient() as client:
                if form_data is not None:
                    # Zoho Analytics import expects multipart/form-data (FILE or DATA).
                    files = {key: (None, value) for key, value in form_data.items()}
                    response = await client.request(
                        method,
                        url,
                        headers=req_headers,
                        params=params,
                        files=files,
                        timeout=30.0,
                    )
                else:
                    req_headers.setdefault("Content-Type", "application/json")
                    response = await client.request(
                        method,
                        url,
                        headers=req_headers,
                        json=json_body,
                        params=params,
                        timeout=30.0,
                    )
                if response.status_code in (200, 201, 202, 204):
                    zoho_circuit_breaker.record_success(integration)
                    if response.status_code == 204 or not (response.content or b"").strip():
                        return True, {"data": []}, None
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
