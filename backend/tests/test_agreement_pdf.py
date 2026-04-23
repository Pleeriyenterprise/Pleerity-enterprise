"""Agreement PDF placeholder merge and build (regression: ctx.items() not ctx.keys())."""

from __future__ import annotations

from services.agreement_pdf import build_agreement_pdf_bytes, merge_placeholders


def test_merge_placeholders_items_not_keys():
    assert merge_placeholders("Hello {{name}}", {"name": "Ada"}) == "Hello Ada"
    assert merge_placeholders("{{a}} and {{b}}", {"a": "1", "b": "2"}) == "1 and 2"


def test_merge_placeholders_unknown_key_stripped():
    assert merge_placeholders("X={{unknown}}-Y", {"x": "y"}) == "X=-Y"
    assert merge_placeholders("{{only_unknown}}", {}) == ""


def test_merge_placeholders_none_ctx():
    assert merge_placeholders("{{x}}", None) == ""


def test_merge_placeholders_longest_key_first():
    """Longer placeholder keys replaced first so shorter keys are not corrupted."""
    out = merge_placeholders("{{ab}} {{a}}", {"a": "A", "ab": "AB"})
    assert "AB" in out and "A" in out
    assert "{{" not in out


def test_build_agreement_pdf_bytes_with_placeholders():
    pdf = build_agreement_pdf_bytes(
        title="Order {{order_id}} — {{client_name}}",
        subtitle="Ref {{reference}}",
        content_blocks=[
            {"order": 1, "label": "Terms", "content": "You agreed on {{signed_at}}.\n\nNext: {{next_step}}.", "enabled": True},
        ],
        render_ctx={
            "order_id": "ORD-1",
            "client_name": "Test Client",
            "reference": "REF-99",
            "signed_at": "2026-01-15",
            "next_step": "Pay invoice",
        },
        footer_text="Footer for {{client_name}} ({{order_id}})",
    )
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 200
