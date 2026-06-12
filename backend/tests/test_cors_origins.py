"""CORS origin resolution — Vercel preview preflight support."""
import os
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from utils.cors_origins import (
    PLEERITY_VERCEL_ORIGIN_REGEX,
    is_cors_origin_allowed,
    resolve_cors_origin_regex,
    resolve_cors_origins,
)

STAGING_PREVIEW_ORIGIN = "https://pleerity-enterprise-9jig.vercel.app"


def test_staging_vercel_preview_origin_not_in_static_list():
    origins = resolve_cors_origins()
    assert "https://pleerity-enterprise.vercel.app" in origins
    assert STAGING_PREVIEW_ORIGIN not in origins


def test_staging_vercel_preview_allowed_by_regex():
    origins = resolve_cors_origins()
    regex = resolve_cors_origin_regex()
    assert regex == PLEERITY_VERCEL_ORIGIN_REGEX
    assert is_cors_origin_allowed(STAGING_PREVIEW_ORIGIN, origins=origins, origin_regex=regex)


def test_production_custom_domain_allowed_by_static_list():
    origins = resolve_cors_origins()
    regex = resolve_cors_origin_regex()
    assert is_cors_origin_allowed("https://pleerityenterprise.co.uk", origins=origins, origin_regex=regex)


def test_unrelated_vercel_project_not_allowed():
    origins = resolve_cors_origins()
    regex = resolve_cors_origin_regex()
    assert not is_cors_origin_allowed("https://other-project-9jig.vercel.app", origins=origins, origin_regex=regex)


def test_cors_origin_regex_env_override():
    with patch.dict(os.environ, {"CORS_ORIGIN_REGEX": r"https://custom\.example\.com"}, clear=False):
        assert resolve_cors_origin_regex() == r"https://custom\.example\.com"


def test_options_preflight_returns_200_for_staging_preview_origin():
    app = FastAPI()
    origins = resolve_cors_origins()
    regex = resolve_cors_origin_regex()
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=origins,
        allow_origin_regex=regex,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/auth/admin/login")
    def admin_login():
        return {"ok": True}

    client = TestClient(app)
    before = client.options(
        "/api/auth/admin/login",
        headers={
            "Origin": STAGING_PREVIEW_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert before.status_code == 200, before.text
    assert before.headers.get("access-control-allow-origin") == STAGING_PREVIEW_ORIGIN

    post = client.post(
        "/api/auth/admin/login",
        headers={"Origin": STAGING_PREVIEW_ORIGIN},
        json={"email": "probe@example.com", "password": "x"},
    )
    assert post.status_code == 200


def test_options_preflight_returns_400_without_regex_for_preview_origin():
    app = FastAPI()
    origins = resolve_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/auth/admin/login")
    def admin_login():
        return {"ok": True}

    client = TestClient(app)
    resp = client.options(
        "/api/auth/admin/login",
        headers={
            "Origin": STAGING_PREVIEW_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 400
    assert "Disallowed CORS origin" in resp.text
