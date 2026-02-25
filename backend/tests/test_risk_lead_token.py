"""
Tests for risk lead token: create_lead_token and verify_lead_token (signed, expiry).
"""
import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta


def test_create_and_verify_roundtrip():
    """Valid token produced by create_lead_token is accepted by verify_lead_token."""
    from utils.risk_lead_token import create_lead_token, verify_lead_token
    with patch("utils.risk_lead_token._secret", return_value="test-secret"):
        token = create_lead_token("RISK-ABC123", expiry_days=7)
        assert token and "." in token
        lead_id = verify_lead_token(token)
        assert lead_id == "RISK-ABC123"


def test_verify_expired_returns_none():
    """Expired token returns None (caller should return 401)."""
    from utils.risk_lead_token import create_lead_token, verify_lead_token
    with patch("utils.risk_lead_token._secret", return_value="test-secret"):
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        with patch("utils.risk_lead_token.datetime") as mock_dt:
            mock_dt.now.return_value = past
            # Allow datetime(x,y,z) for fromisoformat in verify
            class RealDatetime(type(past)):
                @classmethod
                def now(cls, tz=None):
                    return past
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a else past
            token = create_lead_token("RISK-X", expiry_days=7)
        # Verify without patch: real now is after exp
        lead_id = verify_lead_token(token)
        assert lead_id is None


def test_verify_tampered_returns_none():
    """Tampered token (wrong signature) returns None."""
    from utils.risk_lead_token import verify_lead_token
    with patch("utils.risk_lead_token._secret", return_value="test-secret"):
        invalid = "eyJsZWFkX2lkIjoiUlISy1BCTyJ9.0000000000000000000000000000000000000000"
        assert verify_lead_token(invalid) is None


def test_verify_empty_returns_none():
    """Empty or None token returns None."""
    from utils.risk_lead_token import verify_lead_token
    assert verify_lead_token("") is None
    assert verify_lead_token(None) is None
