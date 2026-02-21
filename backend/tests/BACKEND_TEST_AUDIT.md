# Backend test setup audit

## 1) Tests: requests (integration) vs FastAPI TestClient (unit)

| Style | Count | Files |
|-------|-------|--------|
| **TestClient (unit)** | 10 files | test_portal_setup_status.py, test_onboarding_status.py, test_intake_plans.py, test_pending_payment_recovery.py, test_intake_submit_cert_licence.py, test_intake_checkout_errors.py, test_legacy_otp_410.py, test_notification_orchestrator.py, test_intake_uploads.py, test_version_and_client_dashboard.py |
| **TestClient (migrated)** | 24 files | All former requests-based integration tests now use TestClient (see migration status below). |

- **TestClient tests**: use `from server import app` and `TestClient(app)`; mock DB/deps with `patch`; no live HTTP.
- **requests tests**: use `from conftest import BASE_URL` and `requests.get/post(f"{BASE_URL}/api/...")`; expect a running server (integration).

---

## 2) Where the FastAPI app is defined

- **Primary app**: `backend/server.py` → `app = FastAPI(...)` at line 498.
- **Module path for uvicorn**: `server:app` (when run from `backend/` with `PYTHONPATH=.`).
- **Test-only apps**: `test_legacy_otp_410.py` and `test_notification_orchestrator.py` create local `FastAPI()` instances for isolated tests; they do not use `server.app`.

---

## 3) .github/workflows/backend-tests.yml

| Question | Answer |
|----------|--------|
| **Runs in backend/?** | Yes. Step "Run backend tests" does `cd backend` then `PYTHONPATH=. python -m pytest tests -v`. |
| **Installs backend/requirements.txt?** | Yes. Step "Install backend dependencies" runs `pip install -r backend/requirements.txt` (from repo root). |
| **Starts uvicorn before pytest?** | **No.** The workflow only runs pytest; no server is started. |

So in CI, any test that uses `requests` against `BACKEND_URL` (default `http://127.0.0.1:8000`) will get connection refused unless a server is started.

---

## 4) Recommendation and minimal code changes

**Recommendation: B) Refactor tests to use TestClient.**

Reasons:
- **Option A** would require starting uvicorn and a MongoDB (app lifespan uses `database` and scheduler with MongoDB job store). That adds CI services and env/config.
- **Option B** needs no extra CI steps, matches the 10 existing TestClient tests, and runs in-process with mocks (fast, no flakiness from network/DB).

**Exact minimal code changes for Option B:**

1. **backend/tests/conftest.py**  
   - Add a shared `client` fixture that returns `TestClient(app)` from `server`, so all tests can use the same app instance and relative URLs.

2. **Integration-style test files (24 files)**  
   - Use the `client` fixture instead of `requests` and `BASE_URL`.
   - Replace `requests.get(f"{BASE_URL}/api/...")` with `client.get("/api/...")` (and same for post/put/delete).
   - Get auth tokens via `client.post("/api/auth/login", json={...})` (or `/api/auth/admin/login` where used) instead of `requests.post(f"{BASE_URL}/api/auth/login", ...)`.
   - Remove `from conftest import BASE_URL` and any `import requests` used only for those calls.

3. **Optional**  
   - Keep `BASE_URL` in conftest for any external or script use; TestClient-based tests do not need it.

The refactor is mechanical: same request params/headers/body, only the transport changes from HTTP over the wire to TestClient in-process.

---

## Exact minimal code changes applied (Option B)

### 1. backend/tests/conftest.py

- Added `import pytest`, `from fastapi.testclient import TestClient`, `from server import app`.
- Added fixture:
  ```python
  @pytest.fixture
  def client():
      """Return a TestClient for the main FastAPI app (server:app). Use for unit-style API tests."""
      return TestClient(app)
  ```
- Left `BASE_URL` in place for any scripts or tests that still call a live server.

### 2. Example refactor: test_clearform_admin_pricing.py

- Removed `import requests` and `from conftest import BASE_URL`.
- In class fixtures: added `client` parameter (e.g. `def setup(self, client):`) and used `client.post(...)` / `client.get(...)` with **relative paths** (e.g. `/api/auth/login`, `/api/admin/clearform/stats`).
- Stored `self.client = client` in setup where tests need it, or passed `client` into test methods (e.g. `def test_health_endpoint(self, client):`).
- Replaced every `requests.get(f"{BASE_URL}/api/...")` with `client.get("/api/...")` and same for `post`; removed `BASE_URL` from all URLs.

### 3. Remaining 23 integration-style files

Apply the same pattern to each file that still has `from conftest import BASE_URL` and `requests`:

- Add `client` to the fixture/test parameters that perform HTTP calls.
- Replace `requests.METHOD(f"{BASE_URL}/api/...", ...)` with `client.METHOD("/api/...", ...)` (or `self.client` if stored in setup).
- Auth: use `client.post("/api/auth/login", json={...})` or `client.post("/api/auth/admin/login", ...)` instead of `requests.post(f"{BASE_URL}/api/auth/login", ...)`.
- Remove `from conftest import BASE_URL` and drop `import requests` if it is no longer used.

**Migration status:** All 24 integration-style files have been migrated to use the shared `client` fixture and relative paths. No test file uses `requests` or `BASE_URL` for API calls anymore.
