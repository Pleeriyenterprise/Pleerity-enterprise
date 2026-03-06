"""
Order View Token Service
Generates and validates short-lived tokens for one-time users to view order and download documents (no login).
"""

import os
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "default-secret-change-in-production")
VIEW_ORDER_TOKEN_VALIDITY_DAYS = 30


def generate_order_view_token(
    order_id: str,
    customer_email: str,
    validity_days: int = VIEW_ORDER_TOKEN_VALIDITY_DAYS,
) -> str:
    """
    Generate a token for customer to view order and download documents without logging in.
    """
    expiry = datetime.now(timezone.utc) + timedelta(days=validity_days)
    payload = {
        "type": "order_view",
        "order_id": order_id,
        "email": customer_email,
        "exp": expiry,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def validate_order_view_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate order view token. Returns payload if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "order_view":
            return None
        if not payload.get("order_id"):
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Order view token expired")
        return None
    except jwt.InvalidTokenError:
        return None
