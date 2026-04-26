from services.agreement_render_validation_service import render_and_validate_agreement


def test_render_validation_rejects_unresolved_placeholders():
    out = render_and_validate_agreement(
        title="Agreement {{client_full_name}}",
        subtitle="",
        content_blocks=[{"key": "k1", "label": "L", "content": "Value {{missing_key}}"}],
        render_context={"client_full_name": "Jane Example"},
    )
    assert out["valid"] is False
    assert any("missing_" in x for x in out["issues"])


def test_render_validation_strips_html_and_markdown():
    out = render_and_validate_agreement(
        title="## Title",
        subtitle="",
        content_blocks=[{"key": "k1", "label": "L", "content": "<strong>Hello</strong> **world**"}],
        render_context={},
    )
    assert out["valid"] is True
    payload = (
        out["rendered"]["title"]
        + out["rendered"]["subtitle"]
        + "".join(b["content"] for b in out["rendered"]["content_blocks"])
    )
    assert "{{" not in payload
    assert "<strong>" not in payload
    assert "**" not in payload
    assert out["render_hash_sha256"]

