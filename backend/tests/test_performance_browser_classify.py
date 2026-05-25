"""Regression tests for performance browser verification classification gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "tmp_performance_browser_verify_01.py"
_spec = importlib.util.spec_from_file_location("perf_browser_verify", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
classify = _mod.classify


def _deploy_ready() -> dict:
    return {"deploy_ready": True}


def _cold_navigation() -> list:
    return [
        {"surface": "P1_Today", "progressive_shell": True, "full_page_spinner_only_detected": False, "primary_content_ms": 3000},
        {"surface": "P2_CommandCentre", "progressive_shell": True, "full_page_spinner_only_detected": False, "primary_content_ms": 3000},
        {"surface": "P3_Dashboard", "progressive_shell": True, "full_page_spinner_only_detected": False, "primary_content_ms": 5000},
        {"surface": "P4_Properties", "progressive_shell": True, "full_page_spinner_only_detected": False, "primary_content_ms": 2500},
    ]


def _browser(*, warm_primary_ms: int = 2332, stale_in_warm: bool = False, stale_probe: bool = False) -> dict:
    return {
        "cold_navigation": _cold_navigation(),
        "warm_navigation": [
            {
                "surface": "P4_Properties_revisit",
                "stale_banner_seen": stale_in_warm,
                "primary_content_ms": warm_primary_ms,
            }
        ],
        "stale_refresh_disclosure_probe": {"stale_banner_seen": stale_probe},
        "login_status": 200,
    }


def test_fast_warm_revisit_alone_does_not_verify_operationally():
    """Bug regression: ~2.3s warm revisit must not satisfy stale disclosure charter."""
    result = classify(_deploy_ready(), _browser(warm_primary_ms=2300, stale_in_warm=False, stale_probe=False))
    assert result["warm_revisit_fast"] is True
    assert result["stale_refresh_disclosed_in_browser"] is False
    assert result["classification"] == "PARTIAL"
    assert result["verified_operationally"] is False
    assert "insufficient" in result["reason"].lower() or "not observed" in result["reason"].lower()


def test_stale_banner_observed_can_verify_when_backend_acceptable():
    result = classify(_deploy_ready(), _browser(stale_probe=True))
    assert result["stale_refresh_disclosed_in_browser"] is True
    assert result["classification"] == "VERIFIED_OPERATIONALLY"
    assert result["verified_operationally"] is True


def test_unacceptable_backend_still_partial_even_with_stale_disclosed():
    browser = _browser(stale_probe=True)
    browser["cold_navigation"] = [
        {"surface": "P1_Today", "progressive_shell": True, "full_page_spinner_only_detected": False, "primary_content_ms": 3000},
        {"surface": "P2_CommandCentre", "progressive_shell": True, "full_page_spinner_only_detected": False, "primary_content_ms": 97000},
        {"surface": "P3_Dashboard", "progressive_shell": True, "full_page_spinner_only_detected": False},
        {"surface": "P4_Properties", "progressive_shell": True, "full_page_spinner_only_detected": False, "primary_content_ms": 2500},
    ]
    result = classify(_deploy_ready(), browser)
    assert result["stale_refresh_disclosed_in_browser"] is True
    assert result["unacceptable_backend_latency"] is True
    assert result["classification"] == "PARTIAL"
    assert result["verified_operationally"] is False
