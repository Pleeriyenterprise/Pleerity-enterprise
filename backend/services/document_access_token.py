"""
Document Access Token Service
Generates temporary signed tokens for document access in iframes.
"""

import os
import jwt
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Get JWT secret from environment
JWT_SECRET = os.environ.get("JWT_SECRET", "default-secret-change-in-production")

# Token validity duration (in minutes)
DOCUMENT_TOKEN_VALIDITY_MINUTES = 30


def generate_document_access_token(
    order_id: str,
    version: int,
    format: str,
    admin_email: str,
    validity_minutes: int = DOCUMENT_TOKEN_VALIDITY_MINUTES,
) -> str:
    """
    Generate a temporary access token for document preview.
    
    This token allows iframe access without requiring Bearer auth headers.
    Token is short-lived and tied to specific document.
    
    Args:
        order_id: The order ID
        version: Document version number
        format: File format (pdf/docx)
        admin_email: Email of the admin requesting access
        validity_minutes: How long the token is valid
        
    Returns:
        JWT token string
    """
    expiry = datetime.now(timezone.utc) + timedelta(minutes=validity_minutes)
    
    payload = {
        "type": "document_access",
        "order_id": order_id,
        "version": version,
        "format": format,
        "admin_email": admin_email,
        "exp": expiry,
        "iat": datetime.now(timezone.utc),
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    
    logger.debug(f"Generated document access token for {order_id} v{version} ({format})")
    
    return token


def validate_document_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate a document access token.
    
    Args:
        token: The JWT token string
        
    Returns:
        Decoded payload if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        
        # Verify it's a document access token
        if payload.get("type") != "document_access":
            logger.warning("Invalid token type")
            return None
        
        # Check required fields
        required_fields = ["order_id", "version", "format", "admin_email"]
        for field in required_fields:
            if field not in payload:
                logger.warning(f"Missing required field: {field}")
                return None
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.debug("Document access token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid document access token: {e}")
        return None


def get_document_preview_url(
    base_url: str,
    order_id: str,
    version: int,
    format: str,
    admin_email: str,
) -> str:
    """
    Generate a full preview URL with embedded access token.
    
    Args:
        base_url: API base URL (e.g., https://example.com)
        order_id: The order ID
        version: Document version number
        format: File format (pdf/docx)
        admin_email: Email of the admin requesting access
        
    Returns:
        Full URL with token parameter
    """
    token = generate_document_access_token(
        order_id=order_id,
        version=version,
        format=format,
        admin_email=admin_email,
    )
    
    return f"{base_url}/api/admin/orders/{order_id}/documents/{version}/view?format={format}&token={token}"
