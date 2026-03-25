# Security: rate limits, session idle, and re-authentication

This document describes **route-scoped rate limiting**, **session inactivity handling**, and **step-up (re-auth)** for Pleerity Enterprise. Limits are **configurable via environment variables** (see `backend/config/security_limits.py`). The limiter is **in-process**; use a shared store (e.g. Redis) for strict parity across multiple app instances.

## Rate limiting (HTTP 429)

On exceed, the API returns **429 Too Many Requests** with a clear `detail` message. Important events are **logged** (`security.rate_limit` and/or audit `RATE_LIMIT_EXCEEDED`) where implemented.

### Authentication and account recovery

| Area | Scope keys (concept) | Environment variables (defaults) |
|------|----------------------|-----------------------------------|
| Client login | Per IP + per email | `RATE_LIMIT_LOGIN_CLIENT_IP_MAX` (5), `RATE_LIMIT_LOGIN_CLIENT_EMAIL_MAX` (5), `RATE_LIMIT_LOGIN_WINDOW_MINUTES` (10) |
| Admin/staff login | Per IP + per email | `RATE_LIMIT_LOGIN_ADMIN_IP_MAX` (5), `RATE_LIMIT_LOGIN_ADMIN_WINDOW_MINUTES` (10) |
| Contractor login | Per IP | `RATE_LIMIT_LOGIN_CONTRACTOR_IP_MAX` (10), `RATE_LIMIT_LOGIN_CONTRACTOR_WINDOW_MINUTES` (15) |
| Forgot password | Per IP + per email | `RATE_LIMIT_FORGOT_PASSWORD_*` (IP: 5 / 60 min; email: 3 / 60 min) |
| Set password (token link) | Per IP | `RATE_LIMIT_SET_PASSWORD_*` (5 / 30 min) |

Failed logins use **peek-then-record** so successful logins do not consume the failure budget.

### Portal

| Endpoint | Notes |
|----------|--------|
| `POST /api/portal/resend-activation` | Per `client_id`, hourly cap: `RATE_LIMIT_RESEND_ACTIVATION_PER_HOUR` (default 3) |
| `GET /api/portal/setup-status` | When polling with `client_id` query and no JWT: separate IP window (see `portal.py`) |

### Public lead / marketing capture

All `POST /api/leads/capture/*` public capture routes share a **per-IP hourly** bucket: `RATE_LIMIT_LEADS_PUBLIC_PER_HOUR` (default 15).

### Public website forms (`/api/public/*`, partnerships, talent pool)

Hourly **per-IP** cap shared pattern via `utils/public_form_rate_limit.py`: `RATE_LIMIT_PUBLIC_FORM_PER_IP_HOUR` (default **15**). Used for contact, lead, track, service-inquiry, contractor self-register, order provide-info, partnership enquiry, talent pool submit, etc. (each uses a distinct rate key suffix so one form type does not exhaust another’s budget incorrectly — keys are `public_form:{scope}:{ip}`.)

### Compliance risk check (public)

| Route | Variable (default) |
|-------|-------------------|
| `POST /api/risk-check/preview` | `RATE_LIMIT_RISK_CHECK_PREVIEW_PER_HOUR` (10) |
| `POST /api/risk-check/report` | `RATE_LIMIT_RISK_CHECK_REPORT_PER_HOUR` (10) |
| `POST /api/risk-check/activate` | `RATE_LIMIT_RISK_CHECK_ACTIVATE_PER_HOUR` (20) |

### Assistant (authenticated client)

Existing **per-user / 10 min** and **per-client daily** limits remain on chat/ask. An additional **per-IP hourly** cap: `RATE_LIMIT_ASSISTANT_IP_PER_HOUR` (default **60**) on **`GET /api/assistant/snapshot`**, **`POST /api/assistant/ask`**, **`POST /api/assistant/chat`**, and **`POST /api/assistant/escalate`**.

### Documents

**Per `client_id` per hour** for uploads: `RATE_LIMIT_DOCUMENT_UPLOAD_PER_CLIENT_HOUR` (default **20**), applied to client `POST /api/documents/upload`, `bulk-upload`, `zip-upload`, and admin `POST /api/documents/admin/upload` (for the target client).

### Maintenance (client)

| Action | Variable (default) |
|--------|---------------------|
| Create issue | `RATE_LIMIT_MAINTENANCE_ISSUE_CREATE_PER_CLIENT_HOUR` (30) |
| Create work order | `RATE_LIMIT_MAINTENANCE_WORK_ORDER_CREATE_PER_CLIENT_HOUR` (20) |

### Reports / exports

**Per client per hour** for heavy client report/export endpoints: `RATE_LIMIT_REPORT_EXPORT_PER_CLIENT_HOUR` (default **10**).  
**Per staff user per hour** for admin audit extract: `RATE_LIMIT_ADMIN_EXPORT_PER_STAFF_HOUR` (default **5**), used for `GET /api/reports/audit-logs`.

### Admin manual jobs

**Per staff user per hour** for manual job / provisioning runner triggers: `RATE_LIMIT_ADMIN_JOB_RUN_PER_STAFF_HOUR` (default **10**). Applied to `POST /api/admin/jobs/run`, `POST /api/admin/jobs/trigger/{type}`, `POST /api/admin/provisioning-jobs/{id}/retry`, `POST /api/admin/provisioning-jobs/{id}/resend-invite`.

### Admin auth

Stricter login limits are configured under `RATE_LIMIT_LOGIN_ADMIN_*` (see above). Sensitive admin **mutations** require **step-up** (below), not a separate rate limit.

---

## Session inactivity (client vs staff)

### Behaviour

- **Client portal** (`ClientPortalLayout`): idle timeout from `REACT_APP_SESSION_IDLE_MINUTES_CLIENT` (default **45** minutes).
- **Staff portal** (OWNER, ADMIN, SUPPORT, CONTENT, AUDITOR — `UnifiedAdminLayout`): `REACT_APP_SESSION_IDLE_MINUTES_STAFF` (default **20** minutes).
- **Warning** appears **REACT_APP_SESSION_IDLE_WARNING_SECONDS** (default **120** seconds) before hard logout (capped so it never exceeds the idle window).
- **Stay signed in** calls `POST /api/auth/session/extend`, which issues a **new access JWT** and writes `SESSION_EXTENDED` to the audit log.
- On hard timeout, the SPA calls `POST /api/auth/session/idle-notify` (best effort), clears the session, and redirects to login with `session_expired=1`.

### Tokens

- **Session**: access JWT via `JWT_EXPIRATION_HOURS` (default **24h**) **unless** `JWT_EXPIRATION_MINUTES` is set — then new tokens use that many minutes (overrides hours). There is **no refresh token**; extending the session uses `POST /auth/session/extend` (idle modal) and, when the JWT is short-lived, the SPA **proactively** calls extend when less than ~5 minutes remain (`SessionIdleGuard`).
- **Step-up**: short-lived JWT with `token_use: step_up`, sent as **`X-Step-Up-Token`**. It is **not** accepted as a Bearer session token.
- **Impersonation**: `/auth/session/extend` **preserves** impersonation claims and does **not** extend beyond the current JWT `exp` for impersonated sessions.

---

## Re-authentication (step-up)

Password verification: `POST /api/auth/step-up/verify` (Bearer required) returns `step_up_token`. Sensitive admin routes require header:

`X-Step-Up-Token: <step_up_token>`

### Backend (current)

Step-up is enforced on:

- `POST /api/admin/admins/invite`
- `DELETE /api/admin/admins/{portal_user_id}` (deactivate)
- `POST /api/admin/admins/{portal_user_id}/reactivate`
- `POST /api/admin/admins/{portal_user_id}/force-logout`
- `POST /api/admin/admins/{portal_user_id}/resend-invite`
- `POST /api/admin/clients/{client_id}/resend-password-setup`
- `GET /api/admin/clients/{client_id}/password-setup-link` when `generate_new=true`

**Client portal (sensitive financial / commitment):**

- `POST /api/billing/checkout`
- `POST /api/billing/portal`
- `POST /api/billing/cancel`

**Client portal (invoice approvals):**

- `PATCH /api/client/approvals/{invoice_id}` (approve, reject, needs_info, mark_paid)

On missing/invalid step-up, the API returns **403** with `detail.error_code` **`STEP_UP_REQUIRED`** or **`STEP_UP_INVALID`**.

### Frontend

- **Admin Users** tab: invite / deactivate / reactivate / resend invite use the step-up modal when the server returns `STEP_UP_REQUIRED`.
- **Clients** and **Email delivery**: resend password setup uses the same pattern.
- **Client Control Panel** (`/admin/clients/:clientId/control-panel`): **New password link** calls `GET .../password-setup-link?generate_new=true` via `useStepUpApi` (password modal). **Password link status** calls the same endpoint with `generate_new=false` (no step-up).
- **Billing** (`/settings/billing`): checkout, Stripe portal, and cancel subscription use `useStepUpApi`.
- **Approvals** (`/operations/approvals`): approve / reject / needs info / mark paid use `useStepUpApi`.

Step-up token lifetime: `STEP_UP_TOKEN_MINUTES` / `security_limits.step_up_token_minutes` (default 10).

---

## Audit / security-related events

Logged (non-exhaustive):

- **Failed logins** — existing auth audit actions.
- **Rate limits** — `RATE_LIMIT_EXCEEDED` + structured logs for scopes such as `login_client`, `leads_public`, `report_export`, etc.
- **Password reset abuse** — IP/email caps on forgot-password; generic client response when email bucket is full.
- **Session extended** — `SESSION_EXTENDED`.
- **Session idle timeout** — `SESSION_IDLE_TIMEOUT` (via `/auth/session/idle-notify` when the client timer fires).
- **Step-up** — `STEP_UP_VERIFIED`, `STEP_UP_FAILED`.

---

## Operational notes

1. **Horizontal scaling**: In-memory rate limits are per instance. For production clusters, front with a shared rate limiter or API gateway limits.
2. **Trusting IP**: Limits use `X-Forwarded-For` first hop when present; ensure your proxy sets it correctly.
3. **Tuning**: Start from defaults in `security_limits.py` and adjust env vars per environment (staging vs production).
