"""Post-validate LLM narration against Graph Service envelope authoritative refs."""
from __future__ import annotations

from typing import Any, Dict, List, Set


def _collect_allowed_ids(envelope: Dict[str, Any]) -> Dict[str, Set[str]]:
    decision_ids: Set[str] = set()
    snapshot_ids: Set[str] = set()
    node_ids: Set[str] = set()

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "decision_id" and isinstance(v, str) and v:
                    decision_ids.add(v)
                elif k == "snapshot_id" and isinstance(v, str) and v:
                    snapshot_ids.add(v)
                elif k in ("node_ids", "evidence_node_ids") and isinstance(v, list):
                    node_ids.update(str(x) for x in v if x)
                elif k == "node_id" and isinstance(v, str) and v:
                    node_ids.add(v)
                else:
                    _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(envelope.get("authoritative_references"))
    _walk(envelope.get("historical_references"))
    _walk(envelope.get("evidence_lineage"))
    _walk(envelope.get("payload"))
    return {"decision_ids": decision_ids, "snapshot_ids": snapshot_ids, "node_ids": node_ids}


def paragraph_is_cited(paragraph: Dict[str, Any], allowed: Dict[str, Set[str]]) -> bool:
    refs = paragraph.get("authoritative_references") or {}
    if not isinstance(refs, dict):
        return False

    did = refs.get("decision_id")
    if did and str(did) in allowed["decision_ids"]:
        return True
    snap = refs.get("snapshot_id")
    if snap and str(snap) in allowed["snapshot_ids"]:
        return True
    fields = refs.get("snapshot_fields")
    if isinstance(fields, list) and fields:
        return True
    nodes = refs.get("node_ids")
    if isinstance(nodes, list) and nodes:
        return all(str(n) in allowed["node_ids"] for n in nodes if n)
    decision_ids = refs.get("decision_ids")
    if isinstance(decision_ids, list) and decision_ids:
        return all(str(d) in allowed["decision_ids"] for d in decision_ids if d)
    return False


def validate_and_strip_narration(
    narration: Dict[str, Any], envelope: Dict[str, Any]
) -> Dict[str, Any]:
    """Keep only paragraphs with valid citations; mark insufficient if none remain."""
    allowed = _collect_allowed_ids(envelope)
    kept: List[Dict[str, Any]] = []
    for p in narration.get("paragraphs") or []:
        if isinstance(p, dict) and paragraph_is_cited(p, allowed):
            kept.append(p)
    out = dict(narration)
    out["paragraphs"] = kept
    if not kept:
        out["insufficient_evidence"] = True
    return out
