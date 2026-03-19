"""Tests for unified LLM failover helpers (quota / rate limit / timeout detection)."""
import asyncio
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.unified_llm_service import should_attempt_failover, _error_summary  # noqa: E402


def test_timeout_triggers_failover():
    assert should_attempt_failover(asyncio.TimeoutError()) is True
    assert should_attempt_failover(TimeoutError()) is True


def test_message_429_triggers_failover():
    assert should_attempt_failover(RuntimeError("Error 429 rate limited")) is True
    assert should_attempt_failover(ValueError("Resource exhausted")) is True
    assert should_attempt_failover(Exception("quota exceeded for model")) is True


def test_missing_key_triggers_failover():
    assert should_attempt_failover(ValueError("OPENAI_API_KEY not set")) is True
    assert should_attempt_failover(ValueError("LLM_API_KEY not found in environment")) is True


def test_auth_401_does_not_failover_by_message_alone():
    # Unless openai marks it — generic 401 string may not include our keywords
    assert should_attempt_failover(Exception("401 unauthorized")) is False


def test_error_summary_nonempty():
    s = _error_summary(ValueError("boom"))
    assert "ValueError" in s
    assert "boom" in s
