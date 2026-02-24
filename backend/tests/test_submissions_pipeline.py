"""
Submissions pipeline tests: validation, sanitization, dedupe, rate limit, RBAC, PATCH audit, export CSV.
"""
import pytest
from datetime import datetime, timezone


class TestSubmissionUtils:
    """Unit tests for utils/submission_utils."""

    def test_sanitize_html_strips_script(self):
        from utils.submission_utils import sanitize_html
        out = sanitize_html("<script>alert(1)</script>hello")
        assert "script" not in out.lower()
        assert "hello" in out

    def test_sanitize_html_strips_tags(self):
        from utils.submission_utils import sanitize_html
        out = sanitize_html("<p>Hello <b>world</b></p>")
        assert "<" not in out
        assert "Hello" in out and "world" in out

    def test_sanitize_html_none_returns_empty(self):
        from utils.submission_utils import sanitize_html
        assert sanitize_html(None) == ""
        assert sanitize_html("") == ""

    def test_sanitize_html_max_length_truncates(self):
        from utils.submission_utils import sanitize_html, MAX_MESSAGE_LENGTH
        long_str = "a" * (MAX_MESSAGE_LENGTH + 100)
        out = sanitize_html(long_str)
        assert len(out) <= MAX_MESSAGE_LENGTH

    def test_compute_dedupe_key_deterministic(self):
        from utils.submission_utils import compute_dedupe_key
        k1 = compute_dedupe_key("contact", "a@b.com", "123", "hi", None)
        k2 = compute_dedupe_key("contact", "a@b.com", "123", "hi", None)
        assert k1 == k2
        assert len(k1) == 64

    def test_compute_dedupe_key_different_type_different_key(self):
        from utils.submission_utils import compute_dedupe_key
        k1 = compute_dedupe_key("contact", "a@b.com", "123", "hi", None)
        k2 = compute_dedupe_key("talent", "a@b.com", "123", "hi", None)
        assert k1 != k2

    def test_check_rate_limit_allows_under_limit(self):
        from utils.submission_utils import check_rate_limit
        # New key should be allowed
        assert check_rate_limit("192.168.1.1", "test-key-unique-xyz") is True

    def test_is_honeypot_filled(self):
        from utils.submission_utils import is_honeypot_filled
        assert is_honeypot_filled(None) is False
        assert is_honeypot_filled("") is False
        assert is_honeypot_filled("   ") is False
        assert is_honeypot_filled("bot") is True
        assert is_honeypot_filled(" x ") is True

    def test_is_website_honeypot_filled(self):
        from utils.submission_utils import is_website_honeypot_filled
        assert is_website_honeypot_filled(None, None) is False
        assert is_website_honeypot_filled("", "") is False
        assert is_website_honeypot_filled("url", None) is True
        assert is_website_honeypot_filled(None, "x") is True

    def test_compute_spam_score_honeypot(self):
        from utils.submission_utils import compute_spam_score, SPAM_SCORE_HONEYPOT
        score, _ = compute_spam_score("Hello", honeypot_filled=True)
        assert score >= SPAM_SCORE_HONEYPOT


# Admin API tests use TestClient from conftest
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture
def admin_token(client):
    """Get admin token for protected endpoints."""
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if response.status_code != 200:
        pytest.skip("Admin login not available (missing credentials or DB)")
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestAdminSubmissionsRBAC:
    """Admin submissions endpoints require auth."""

    def test_list_submissions_without_auth_returns_401(self, client):
        response = client.get("/api/admin/submissions?type=contact")
        assert response.status_code == 401

    def test_get_submission_without_auth_returns_401(self, client):
        response = client.get("/api/admin/submissions/contact-CONTACT-ABC123")
        assert response.status_code == 401

    def test_export_csv_without_auth_returns_401(self, client):
        response = client.get("/api/admin/submissions/export/csv?type=contact")
        assert response.status_code == 401


class TestAdminSubmissionsExportCSV:
    """Export CSV returns CSV with auth."""

    def test_export_csv_returns_csv_with_auth(self, client, admin_headers):
        response = client.get(
            "/api/admin/submissions/export/csv?type=contact",
            headers=admin_headers,
        )
        if response.status_code == 401:
            pytest.skip("Admin auth not available")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "submission_id" in response.text or "full_name" in response.text

    def test_export_csv_accepts_q_parameter(self, client, admin_headers):
        response = client.get(
            "/api/admin/submissions/export/csv?type=contact&q=test",
            headers=admin_headers,
        )
        if response.status_code == 401:
            pytest.skip("Admin auth not available")
        assert response.status_code == 200


class TestContactPrivacyRequired:
    """Contact form requires privacy_accepted."""

    def test_contact_without_privacy_accepted_returns_422(self, client):
        payload = {
            "full_name": "Test User",
            "email": "privacy-test@example.com",
            "subject": "Test",
            "message": "Hello",
            "contact_reason": "general",
        }
        response = client.post("/api/public/contact", json=payload)
        assert response.status_code == 422

    def test_contact_with_privacy_accepted_false_returns_422(self, client):
        payload = {
            "full_name": "Test User",
            "email": "privacy-test@example.com",
            "subject": "Test",
            "message": "Hello",
            "contact_reason": "general",
            "privacy_accepted": False,
        }
        response = client.post("/api/public/contact", json=payload)
        assert response.status_code == 422

    def test_contact_with_privacy_accepted_true_accepted(self, client):
        from database import database
        if database.get_db() is None:
            pytest.skip("Database not available (e.g. pytest without MongoDB)")
        payload = {
            "full_name": "Test User",
            "email": "privacy-ok@example.com",
            "subject": "Test",
            "message": "Hello",
            "contact_reason": "general",
            "privacy_accepted": True,
        }
        response = client.post("/api/public/contact", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        assert "submission_id" in data


class TestContactSpamHoneypot:
    """Honeypot (website) filled leads to SPAM status when score >= 50."""

    def test_contact_with_website_honeypot_filled_stored_as_spam(self, client, admin_headers):
        payload = {
            "full_name": "Bot",
            "email": "honeypot-test@example.com",
            "subject": "Test",
            "message": "Hello",
            "contact_reason": "general",
            "privacy_accepted": True,
            "website": "https://spam.example.com",
        }
        response = client.post("/api/public/contact", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True
        sid = data.get("submission_id")
        if not sid:
            pytest.skip("No submission_id returned")
        get_resp = client.get(
            f"/api/admin/submissions/contact-{sid}",
            headers=admin_headers,
        )
        if get_resp.status_code != 200:
            pytest.skip("Admin auth or submission not available")
        doc = get_resp.json()
        assert doc.get("status") == "SPAM"
        assert (doc.get("spam_score") or 0) >= 50


class TestContactDedupeUpdate:
    """Dedupe by (type + email) within 24h updates existing and returns same id."""

    def test_contact_duplicate_within_24h_returns_same_id_and_duplicate_ping(self, client, admin_headers):
        email = "dedupe-test@example.com"
        payload = {
            "full_name": "Dedupe User",
            "email": email,
            "subject": "First",
            "message": "First message",
            "contact_reason": "general",
            "privacy_accepted": True,
        }
        r1 = client.post("/api/public/contact", json=payload)
        assert r1.status_code == 200
        d1 = r1.json()
        sid1 = d1.get("submission_id")
        assert sid1
        payload["subject"] = "Second"
        payload["message"] = "Second message"
        r2 = client.post("/api/public/contact", json=payload)
        assert r2.status_code == 200
        d2 = r2.json()
        sid2 = d2.get("submission_id")
        assert sid2 == sid1
        get_resp = client.get(
            f"/api/admin/submissions/contact-{sid1}",
            headers=admin_headers,
        )
        if get_resp.status_code != 200:
            pytest.skip("Admin auth or submission not available")
        doc = get_resp.json()
        audit_actions = [a.get("action") for a in (doc.get("audit") or [])]
        assert "duplicate_ping" in audit_actions
        assert doc.get("last_activity_at")
