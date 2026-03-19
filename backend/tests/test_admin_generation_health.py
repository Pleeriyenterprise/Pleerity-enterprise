"""Unit tests for generation health: failure summarization and safe admin messaging."""
import pytest

from services.admin_failure_summary import (
    classify_generation_error,
    summarize_generation_failure,
    order_failure_fields_from_message,
)


def test_classify_quota_and_retryable():
    t, r = classify_generation_error("You exceeded your current quota")
    assert t == "quota_exceeded"
    assert r is True


def test_classify_schema_not_retryable():
    t, r = classify_generation_error("LLM output not valid JSON", error_code="LLM_INVALID_JSON")
    assert t == "schema_error"
    assert r is False


def test_summarize_short_message_no_raw_dump():
    long = "x" * 5000
    out = summarize_generation_failure("rate_limit", long)
    assert len(out["short_message"]) < 600
    assert "retry" in out["recommended_action"].lower() or "Wait" in out["recommended_action"]


def test_order_failure_fields_shape():
    f = order_failure_fields_from_message("429 Too Many Requests", both_providers_exhausted=False)
    assert "last_generation_error_type" in f
    assert "last_generation_error_short" in f
    assert "retryable_failure" in f
