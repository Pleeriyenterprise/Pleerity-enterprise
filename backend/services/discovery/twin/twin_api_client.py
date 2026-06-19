"""Authenticated Twin REST API client — Stage Y."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from services.discovery.twin.twin_connector_constants import twin_api_base_url

logger = logging.getLogger(__name__)


class TwinApiError(Exception):
    def __init__(self, code: str, message: str, *, status: Optional[int] = None):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class TwinApiClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 4,
    ) -> None:
        if not api_key or not api_key.strip():
            raise TwinApiError("MISSING_API_KEY", "TWIN_API_KEY is required")
        self._api_key = api_key.strip()
        self._base_url = (base_url or twin_api_base_url()).rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    def _headers(self) -> Dict[str, str]:
        return {"x-api-key": self._api_key, "Accept": "application/json"}

    async def get_me(self) -> Dict[str, Any]:
        return await self._request_json("GET", "/v1/me")

    async def list_run_events(
        self,
        agent_id: str,
        run_id: str,
        *,
        page_limit: int = 50,
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        after_index = 0
        while True:
            params = {"limit": page_limit, "after_index": after_index}
            payload = await self._request_json(
                "GET",
                f"/v1/agents/{agent_id}/runs/{run_id}/events",
                params=params,
            )
            page = payload.get("events") or []
            if not page:
                break
            events.extend(page)
            last_index = page[-1].get("index")
            if last_index is None:
                break
            if len(page) < page_limit:
                break
            after_index = int(last_index)
        return events

    async def list_runs(
        self,
        agent_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
        filter_status: Optional[str] = None,
        filter_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if filter_status:
            params["filter_status"] = filter_status
        if filter_run_id:
            params["filter_run_id"] = filter_run_id
        return await self._request_json(
            "GET",
            f"/v1/agents/{agent_id}/runs",
            params=params,
        )

    async def get_run(self, agent_id: str, run_id: str) -> Dict[str, Any]:
        listed = await self.list_runs(agent_id, filter_run_id=run_id, page_size=5)
        runs = listed.get("runs") or []
        if runs:
            return runs[0]
        raise TwinApiError(
            "RUN_NOT_FOUND",
            f"Run {run_id} not found for agent {agent_id}",
            status=404,
        )

    async def start_run(
        self,
        agent_id: str,
        *,
        run_mode: str = "run",
        user_message: str = "",
    ) -> Dict[str, Any]:
        payload = await self._request_json(
            "POST",
            f"/v1/agents/{agent_id}/runs",
            json_body={"run_mode": run_mode, "user_message": user_message},
        )
        run = payload.get("run")
        if not isinstance(run, dict):
            raise TwinApiError("INVALID_RUN_RESPONSE", "Twin start run response missing run object")
        return run

    async def list_webhooks(self, agent_id: str) -> List[Dict[str, Any]]:
        payload = await self._request_json("GET", f"/v1/agents/{agent_id}/webhooks")
        return payload.get("webhooks") or []

    async def create_webhook(
        self,
        agent_id: str,
        *,
        url: str,
        events: List[str],
    ) -> Dict[str, Any]:
        payload = await self._request_json(
            "POST",
            f"/v1/agents/{agent_id}/webhooks",
            json_body={"url": url, "events": events},
        )
        return payload

    async def delete_webhook(self, agent_id: str, webhook_id: str) -> None:
        await self._request_json(
            "DELETE",
            f"/v1/agents/{agent_id}/webhooks/{webhook_id}",
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        attempt = 0
        while True:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=self._headers(),
                        params=params,
                        json=json_body,
                    )
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise TwinApiError("HTTP_ERROR", str(exc)) from exc
                await asyncio.sleep(min(2 ** attempt, 16))
                continue

            if response.status_code in (429, 500, 502, 503, 504):
                if attempt >= self._max_retries:
                    self._raise_problem(response)
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 16)
                await asyncio.sleep(delay)
                continue

            if response.status_code >= 400:
                self._raise_problem(response)

            if response.status_code == 204 or not response.content:
                return {}
            data = response.json()
            if not isinstance(data, dict):
                raise TwinApiError("INVALID_JSON", "Twin API response must be a JSON object")
            return data

    def _raise_problem(self, response: httpx.Response) -> None:
        detail = response.text[:500]
        try:
            problem = response.json()
            if isinstance(problem, dict):
                detail = str(problem.get("detail") or problem.get("title") or detail)
        except Exception:
            pass
        raise TwinApiError(
            "TWIN_API_ERROR",
            detail or f"Twin API error HTTP {response.status_code}",
            status=response.status_code,
        )
