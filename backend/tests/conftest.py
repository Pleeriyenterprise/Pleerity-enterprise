"""
Pytest configuration and shared test helpers for backend tests.
"""
import os

# Skip heavy server startup (MongoDB, scheduler) when running under pytest.
os.environ.setdefault("PYTEST_RUNNING", "1")

import pytest

# Base URL for HTTP requests in tests. Always includes scheme for CI (requests requires full URL).
# Used only by tests that call a live server; TestClient-based tests use the client fixture instead.
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

# Shared TestClient fixture so tests can use in-process requests without a running server.
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    """Return a TestClient for the main FastAPI app (server:app). Use for unit-style API tests."""
    return TestClient(app)
