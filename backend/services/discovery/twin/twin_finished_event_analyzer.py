"""Analyse Twin run events — finished event output location (Stage Y-02)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def mask_signing_secret(secret: str) -> Dict[str, Any]:
    if not secret:
        return {"secret_present": False, "secret_length": 0, "secret_prefix_last4": None}
    text = str(secret).strip()
    return {
        "secret_present": True,
        "secret_length": len(text),
        "secret_prefix_last4": f"****{text[-4:]}" if len(text) >= 4 else "****",
    }


def find_finished_event(
    events: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[int]]:
    """Return (event_item, finished_body, event_index)."""
    for item in reversed(events):
        body = item.get("event")
        if isinstance(body, dict) and "finished" in body:
            finished = body.get("finished")
            if isinstance(finished, dict):
                return item, finished, item.get("index")
    return None, None, None


def _scan_records_paths(
    node: Any,
    *,
    path: str,
    out: List[Dict[str, Any]],
) -> None:
    if isinstance(node, dict):
        records = node.get("records")
        if isinstance(records, list):
            sample = records[0] if records and isinstance(records[0], dict) else None
            out.append(
                {
                    "json_path": f"{path}.records",
                    "record_count": len(records),
                    "sample_record_keys": sorted(sample.keys()) if sample else [],
                    "sample_record_shape": sample,
                }
            )
        prospects = node.get("prospects")
        if isinstance(prospects, list):
            sample = prospects[0] if prospects and isinstance(prospects[0], dict) else None
            out.append(
                {
                    "json_path": f"{path}.prospects",
                    "record_count": len(prospects),
                    "sample_record_keys": sorted(sample.keys()) if sample else [],
                    "sample_record_shape": sample,
                }
            )
        for key, value in node.items():
            _scan_records_paths(value, path=f"{path}.{key}", out=out)
    elif isinstance(node, list):
        for idx, item in enumerate(node[:3]):
            _scan_records_paths(item, path=f"{path}[{idx}]", out=out)


def analyze_finished_output(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    event_item, finished_body, event_index = find_finished_event(events)
    result: Dict[str, Any] = {
        "finished_event_located": finished_body is not None,
        "finished_event_index": event_index,
        "finished_event_keys": sorted(finished_body.keys()) if finished_body else [],
        "output_paths": [],
        "final_output_json_path": None,
        "record_count": 0,
        "sample_record_shape": None,
        "extraction_readiness": "RED",
    }

    if not finished_body:
        result["extraction_note"] = "No event.finished object found in run events stream"
        return result

    paths: List[Dict[str, Any]] = []
    _scan_records_paths(finished_body, path=f"events[{event_index}].event.finished", out=paths)
    result["output_paths"] = paths

    records_candidates = [p for p in paths if p["json_path"].endswith(".records")]
    if records_candidates:
        best = max(records_candidates, key=lambda p: p.get("record_count", 0))
        result["final_output_json_path"] = best["json_path"]
        result["record_count"] = best.get("record_count", 0)
        result["sample_record_shape"] = best.get("sample_record_shape")
        if best.get("record_count", 0) > 0 and best.get("sample_record_shape"):
            keys = set(best["sample_record_shape"].keys())
            if {"company_name", "twin_id"} & keys or {"company_name", "email"} & keys:
                result["extraction_readiness"] = "GREEN"
            else:
                result["extraction_readiness"] = "AMBER"
        else:
            result["extraction_readiness"] = "AMBER"
    elif paths:
        result["final_output_json_path"] = paths[0]["json_path"]
        result["extraction_readiness"] = "AMBER"
        result["extraction_note"] = "Candidate output path found but not canonical records[]"
    else:
        result["extraction_note"] = "finished event present but no records[] or prospects[] located"

    return result
