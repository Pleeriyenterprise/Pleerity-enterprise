"""Compatibility wrapper for canonical agreement rendering authority."""

from __future__ import annotations

from typing import Any, Dict, List

from services.agreement_document_authority import compile_agreement_document


def render_and_validate_agreement(
    *,
    title: str,
    subtitle: str,
    content_blocks: List[Dict[str, Any]],
    render_context: Dict[str, Any],
) -> Dict[str, Any]:
    out = compile_agreement_document(
        template_name="Service Agreement",
        template_code="property_compliance_management_agreement",
        template_id="",
        version_id="",
        version_number=1,
        published_at=None,
        effective_from=None,
        title=title,
        subtitle=subtitle,
        content_blocks=content_blocks,
        render_context=render_context if isinstance(render_context, dict) else {},
    )
    rendered_blocks: List[Dict[str, Any]] = []
    for s in (out.get("document") or {}).get("sections") or []:
        text_parts: List[str] = []
        for node in s.get("nodes") or []:
            if node.get("type") == "bullet_list":
                text_parts.extend([f"- {str(i)}" for i in (node.get("items") or [])])
            else:
                text_parts.append(str(node.get("text") or ""))
        rendered_blocks.append({"key": s.get("key"), "label": s.get("heading"), "content": "\n".join(text_parts)})
    return {
        "valid": bool(out.get("valid")),
        "issues": list(out.get("issues") or []),
        "rendered": {
            "title": (out.get("document") or {}).get("title") or "",
            "subtitle": (out.get("document") or {}).get("subtitle") or "",
            "content_blocks": rendered_blocks,
            "document_structure": (out.get("document") or {}),
        },
        "render_hash_sha256": str(out.get("render_hash_sha256") or ""),
    }

