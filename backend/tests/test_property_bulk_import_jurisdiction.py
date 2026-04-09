from routes.properties import _resolve_bulk_import_jurisdiction


def test_bulk_import_row_explicit_jurisdiction_wins_over_account_default():
    assert _resolve_bulk_import_jurisdiction("Wales", "England") == "Wales"


def test_bulk_import_blank_row_uses_account_default():
    assert _resolve_bulk_import_jurisdiction("", "Scotland") == "Scotland"
    assert _resolve_bulk_import_jurisdiction(None, "Scotland") == "Scotland"


def test_bulk_import_blank_row_and_blank_default_returns_none():
    assert _resolve_bulk_import_jurisdiction("", "") is None


def test_bulk_import_invalid_explicit_jurisdiction_is_rejected():
    try:
        _resolve_bulk_import_jurisdiction("Atlantis", "England")
    except ValueError as exc:
        assert "jurisdiction must be Scotland, England, Wales, or Northern Ireland" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid explicit row jurisdiction")
