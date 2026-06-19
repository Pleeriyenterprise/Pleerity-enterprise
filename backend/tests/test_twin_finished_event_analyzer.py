"""Tests for Twin finished event analyzer — Stage Y-02."""
from services.discovery.twin.twin_finished_event_analyzer import (
    analyze_finished_output,
    find_finished_event,
    mask_signing_secret,
)


def test_mask_signing_secret():
    masked = mask_signing_secret("whsec_abcd1234wxyz")
    assert masked["secret_present"] is True
    assert masked["secret_length"] == 18
    assert masked["secret_prefix_last4"] == "****wxyz"
    assert "whsec" not in masked["secret_prefix_last4"]


def test_find_finished_event():
    events = [
        {"index": 1, "event": {"started": {}}},
        {
            "index": 2,
            "event": {
                "finished": {
                    "output": {
                        "records": [
                            {
                                "twin_id": "twin-1",
                                "company_name": "Co",
                                "email": "a@b.com",
                                "source_url": "https://x.com",
                                "confidence_score": 80,
                                "country": "GB",
                            }
                        ]
                    }
                }
            },
        },
    ]
    item, body, idx = find_finished_event(events)
    assert idx == 2
    assert body is not None
    analysis = analyze_finished_output(events)
    assert analysis["finished_event_located"] is True
    assert analysis["record_count"] == 1
    assert analysis["extraction_readiness"] == "GREEN"
    assert "finished" in analysis["final_output_json_path"]
