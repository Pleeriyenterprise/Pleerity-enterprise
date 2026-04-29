"""Canonical structured agreement rendering authority."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Tuple

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")
ALLOWED_NODE_TYPES = {"paragraph", "subheading", "bullet_list"}


def _clean_text(value: Any) -> str:
    s = str(value or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "".join(ch for ch in s if ch == "\n" or ord(ch) >= 32)
    s = " ".join(s.split()) if "\n" not in s else "\n".join(" ".join(p.split()) for p in s.split("\n"))
    # No arbitrary HTML rendering; if tags appear, keep text only.
    s = s.replace("<", "").replace(">", "")
    s = s.replace("**", "").replace("__", "").replace("`", "")
    if s.lstrip().startswith("#"):
        s = s.lstrip("#").strip()
    return s.strip()


def _replace_placeholders(text: str, context: Dict[str, Any]) -> Tuple[str, List[str]]:
    out = str(text or "")
    missing: List[str] = []
    for key in sorted({m.group(1) for m in PLACEHOLDER_RE.finditer(out)}, key=len, reverse=True):
        if key in context:
            out = out.replace("{{" + key + "}}", _clean_text(context.get(key)))
        else:
            missing.append(key)
    return out, missing


def _normalize_nodes(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = block.get("nodes")
    if isinstance(nodes, list) and nodes:
        out: List[Dict[str, Any]] = []
        for n in nodes:
            t = str((n or {}).get("type") or "").strip().lower()
            if t not in ALLOWED_NODE_TYPES:
                continue
            if t == "bullet_list":
                items = [str(i or "") for i in ((n or {}).get("items") or []) if str(i or "").strip()]
                out.append({"type": "bullet_list", "items": items})
            else:
                out.append({"type": t, "text": str((n or {}).get("text") or "")})
        if out:
            return out
    raw = str(block.get("content") or "")
    if not raw.strip():
        return []
    return [{"type": "paragraph", "text": raw}]


def compile_agreement_document(
    *,
    template_name: str,
    template_code: str,
    template_id: str,
    version_id: str,
    version_number: int,
    published_at: str | None,
    effective_from: str | None,
    title: str,
    subtitle: str,
    content_blocks: List[Dict[str, Any]],
    render_context: Dict[str, Any],
) -> Dict[str, Any]:
    issues: List[str] = []
    rendered_title, miss_title = _replace_placeholders(title, render_context)
    rendered_subtitle, miss_subtitle = _replace_placeholders(subtitle, render_context)
    if miss_title:
        issues.append("missing_title_placeholders:" + ",".join(sorted(set(miss_title))))
    if miss_subtitle:
        issues.append("missing_subtitle_placeholders:" + ",".join(sorted(set(miss_subtitle))))

    sections: List[Dict[str, Any]] = []
    for block in sorted([b for b in (content_blocks or []) if isinstance(b, dict) and b.get("enabled", True)], key=lambda b: int(b.get("order") or 0)):
        heading = _clean_text(block.get("label") or block.get("key") or "Section")
        rendered_nodes: List[Dict[str, Any]] = []
        for n in _normalize_nodes(block):
            if n["type"] == "bullet_list":
                items: List[str] = []
                for item in n.get("items") or []:
                    v, miss = _replace_placeholders(item, render_context)
                    if miss:
                        issues.append("missing_list_placeholders:" + ",".join(sorted(set(miss))))
                    items.append(_clean_text(v))
                rendered_nodes.append({"type": "bullet_list", "items": [i for i in items if i]})
            else:
                v, miss = _replace_placeholders(str(n.get("text") or ""), render_context)
                if miss:
                    issues.append("missing_text_placeholders:" + ",".join(sorted(set(miss))))
                rendered_nodes.append({"type": n["type"], "text": _clean_text(v)})
        sections.append(
            {
                "key": str(block.get("key") or ""),
                "heading": heading,
                "nodes": [x for x in rendered_nodes if (x.get("text") or x.get("items"))],
            }
        )

    lines: List[str] = [_clean_text(rendered_title), _clean_text(rendered_subtitle)]
    for s in sections:
        lines.append(_clean_text(s.get("heading")))
        for n in s.get("nodes") or []:
            if n.get("type") == "bullet_list":
                for item in n.get("items") or []:
                    lines.append(f"- {_clean_text(item)}")
            else:
                lines.append(_clean_text(n.get("text")))
    canonical_text = "\n".join([l for l in lines if l]).strip()
    if PLACEHOLDER_RE.search(canonical_text):
        issues.append("unresolved_placeholder")
    if not canonical_text:
        issues.append("empty_document")

    render_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest() if canonical_text else ""
    document = {
        "meta": {
            "template_name": template_name,
            "template_code": template_code,
            "template_id": template_id,
            "version_id": version_id,
            "version_number": int(version_number or 1),
            "published_at": published_at,
            "effective_from": effective_from,
        },
        "title": _clean_text(rendered_title),
        "subtitle": _clean_text(rendered_subtitle),
        "sections": sections,
    }
    return {
        "valid": len(issues) == 0,
        "issues": sorted(set(issues)),
        "document": document,
        "canonical_text": canonical_text,
        "render_hash_sha256": render_hash,
    }


def canonical_text_from_document_structure(document_structure: Dict[str, Any]) -> str:
    """Stable text projection for an already-rendered document structure."""
    doc = document_structure if isinstance(document_structure, dict) else {}
    lines: List[str] = []
    lines.append(_clean_text(doc.get("title") or ""))
    lines.append(_clean_text(doc.get("subtitle") or ""))
    for s in doc.get("sections") or []:
        if not isinstance(s, dict):
            continue
        lines.append(_clean_text(s.get("heading") or ""))
        for n in s.get("nodes") or []:
            if not isinstance(n, dict):
                continue
            if str(n.get("type") or "").lower() == "bullet_list":
                for item in n.get("items") or []:
                    lines.append(f"- {_clean_text(item)}")
            else:
                lines.append(_clean_text(n.get("text") or ""))
    return "\n".join([l for l in lines if l]).strip()


def hash_document_structure_sha256(document_structure: Dict[str, Any]) -> str:
    txt = canonical_text_from_document_structure(document_structure)
    if not txt:
        return ""
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()

