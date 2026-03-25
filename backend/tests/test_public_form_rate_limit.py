"""Public form hourly rate limit returns 429 and does not require Mongo for the limiter decision."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import Request, HTTPException

from utils.public_form_rate_limit import enforce_public_form_rate, client_ip_from_request


def test_enforce_public_form_rate_raises_429_when_limiter_denies():
    req = Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/api/public/contact",
            "headers": [],
            "client": ("127.0.0.1", 1234),
        }
    )
    with patch(
        "utils.public_form_rate_limit.rate_limiter.check_rate_limit",
        AsyncMock(return_value=(False, "Rate limit exceeded. Try again in 60 seconds.")),
    ):
        with patch("utils.public_form_rate_limit.create_audit_log", AsyncMock()):
            with pytest.raises(HTTPException) as ei:
                asyncio.run(enforce_public_form_rate(req, "contact"))
    assert ei.value.status_code == 429


def test_client_ip_from_request_prefers_x_forwarded_for():
    req = Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [
                (b"x-forwarded-for", b"203.0.113.5, 10.0.0.1"),
            ],
            "client": ("127.0.0.1", 1234),
        }
    )
    assert client_ip_from_request(req) == "203.0.113.5"
