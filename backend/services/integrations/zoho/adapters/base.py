"""Zoho adapter base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from services.integrations.zoho.registry import SIGN_FORBIDDEN_CATEGORIES, WORKDRIVE_FORBIDDEN_CATEGORIES
from services.integrations.zoho.types import SyncResult


class BaseZohoAdapter(ABC):
    integration: str = "base"

    @abstractmethod
    async def execute(self, operation: str, payload: Dict[str, Any]) -> SyncResult:
        ...

    def authority_check_outbound(self, payload: Dict[str, Any]) -> Optional[str]:
        """Return error message if outbound payload violates authority boundaries."""
        resource = str(payload.get("resource_type") or payload.get("category") or "")

        if self.integration == "workdrive":
            cat = str(payload.get("category") or "").lower()
            if cat in WORKDRIVE_FORBIDDEN_CATEGORIES:
                return f"workdrive_forbidden_category:{cat}"
        if self.integration == "sign":
            cat = str(payload.get("category") or "").lower()
            if cat in SIGN_FORBIDDEN_CATEGORIES:
                return f"sign_forbidden_category:{cat}"
        if "client_billing" in resource or payload.get("collection") == "client_billing":
            return "books_cannot_touch_client_billing"
        return None
