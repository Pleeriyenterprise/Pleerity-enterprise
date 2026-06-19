"""Extract Discovery export JSON from Twin run events — Stage Y.

Export extraction is intentionally deferred until real Twin run events are captured
and inspected via discovery_twin_run_event_captures.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _event_summary(event_item: Dict[str, Any]) -> Dict[str, Any]:
    index = event_item.get("index")
    event_body = event_item.get("event")
    summary: Dict[str, Any] = {"index": index, "event_keys": []}
    if isinstance(event_body, dict):
        summary["event_keys"] = sorted(event_body.keys())
        for key, value in event_body.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                summary[f"event.{key}"] = value
            elif isinstance(value, dict):
                summary[f"event.{key}_keys"] = sorted(value.keys())[:20]
            elif isinstance(value, list):
                summary[f"event.{key}_len"] = len(value)
    else:
        summary["event_type"] = type(event_body).__name__
    return summary


def summarize_events_for_capture(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build diagnostics to help lock extraction logic after first real Twin run."""
    summaries = [_event_summary(item) for item in events]
    all_keys: List[str] = []
    for item in events:
        body = item.get("event")
        if isinstance(body, dict):
            all_keys.extend(body.keys())
    unique_keys = sorted(set(all_keys))
    return {
        "event_count": len(events),
        "event_index_min": min((e.get("index") for e in events if e.get("index") is not None), default=None),
        "event_index_max": max((e.get("index") for e in events if e.get("index") is not None), default=None),
        "top_level_event_keys": unique_keys,
        "summaries": summaries[:50],
        "summaries_truncated": len(summaries) > 50,
    }


def _find_records_candidate(node: Any, path: str = "$") -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    if isinstance(node, dict):
        records = node.get("records")
        if isinstance(records, list) and records and all(isinstance(r, dict) for r in records):
            found.append({"path": path, "record_count": len(records)})
        for key, value in node.items():
            found.extend(_find_records_candidate(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for idx, value in enumerate(node[:10]):
            found.extend(_find_records_candidate(value, f"{path}[{idx}]"))
    return found


def extract_export_from_events(
    events: List[Dict[str, Any]],
    *,
    twin_run_id: str,
    twin_agent_id: str,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Attempt export extraction. Returns (payload, diagnostics).

    Phase Y1: extraction locked — always returns None with rich diagnostics unless
    DISCOVERY_TWIN_EXPORT_EXTRACTION_ENABLED=true and a records[] candidate is found.
    """
    import os

    diagnostics = summarize_events_for_capture(events)
    diagnostics["twin_run_id"] = twin_run_id
    diagnostics["twin_agent_id"] = twin_agent_id
    diagnostics["extraction_status"] = "deferred"
    diagnostics["records_candidates"] = []

    for item in events:
        diagnostics["records_candidates"].extend(
            _find_records_candidate(item, path=f"event_index:{item.get('index')}")
        )

    extraction_enabled = os.environ.get("DISCOVERY_TWIN_EXPORT_EXTRACTION_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    if not extraction_enabled:
        diagnostics["extraction_note"] = (
            "Capture-only mode or extraction disabled. Inspect discovery_twin_run_event_captures."
        )
        logger.info(
            "Twin export extraction deferred run_id=%s agent_id=%s event_count=%s candidates=%s",
            twin_run_id,
            twin_agent_id,
            len(events),
            len(diagnostics["records_candidates"]),
        )
        return None, diagnostics

    # Best-effort extraction when explicitly enabled (post schema lock-in).
    for item in reversed(events):
        body = item.get("event")
        if not isinstance(body, dict):
            continue
        for candidate in (body, body.get("output"), body.get("result"), body.get("message")):
            if isinstance(candidate, dict) and isinstance(candidate.get("records"), list):
                records = candidate["records"]
                if records and all(isinstance(r, dict) for r in records):
                    export_id = candidate.get("export_id") or f"exp-twin-{twin_run_id}"
                    payload = {
                        "export_id": export_id,
                        "workspace_id": candidate.get("workspace_id"),
                        "agent_id": twin_agent_id,
                        "records": records,
                        "provenance": "real_workspace",
                    }
                    diagnostics["extraction_status"] = "extracted"
                    diagnostics["extraction_path"] = "enabled_scan"
                    return payload, diagnostics

    diagnostics["extraction_status"] = "not_found"
    diagnostics["extraction_note"] = "No records[] envelope found in run events"
    return None, diagnostics


def events_json_preview(events: List[Dict[str, Any]], *, max_chars: int = 200_000) -> str:
    text = json.dumps(events, indent=2, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... truncated ({len(text)} chars total)"
