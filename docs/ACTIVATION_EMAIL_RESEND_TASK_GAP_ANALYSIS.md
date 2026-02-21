# Activation Email Resend – Task vs Codebase Gap Analysis

This document maps the **TASK** requirements to the current implementation to show what is implemented, what is missing, and how to avoid duplication or conflict.

---

## 1. Resend endpoint must NOT return success unless provider accepts

| Requirement | Status | Implementation / Gap |
|-------------|--------|------------------------|
| Only return 200 when provider returns accepted + message_id | **Done** | `backend/routes/admin.py` `resend_password_setup`: treats `outcome == "blocked"` and `outcome == "failed"` as non-success (raises 500). Success only when `outcome in ("sent", "duplicate_ignored")`. |
| If Postmark token missing or FROM not configured → 500, `error_code="EMAIL_NOT_CONFIGURED"` | **Partial** | Orchestrator returns `outcome="blocked"`, `block_reason="BLOCKED_PROVIDER_NOT_CONFIGURED"`. Admin then raises 500 with `error_code="EMAIL_SEND_FAILED"`, not `EMAIL_NOT_CONFIGURED`. **Gap:** Task asks for distinct `EMAIL_NOT_CONFIGURED`; FROM email is not explicitly validated (DEFAULT_SENDER has env default). |
| If Postmark rejects → 502, `error_code="EMAIL_PROVIDER_REJECTED"` + provider error | **Missing** | Admin uses 500 and `EMAIL_SEND_FAILED` for all failures. No 502 or `EMAIL_PROVIDER_REJECTED`. **Gap:** Add 502 + `EMAIL_PROVIDER_REJECTED` when provider rejects (orchestrator would need to expose provider rejection vs config missing). |
| FRONTEND_PUBLIC_URL missing → 500, `error_code="FRONTEND_PUBLIC_URL_MISSING"` | **Partial** | `get_frontend_base_url()` raises `ValueError`; admin catches and returns **503** with `error_code="APP_URL_NOT_CONFIGURED"`. **Gap:** Task wants **500** and `FRONTEND_PUBLIC_URL_MISSING`. |

**Relevant code:**  
- `backend/routes/admin.py` lines 1045–1203 (`resend_password_setup`).  
- `backend/utils/public_app_url.py` (`get_frontend_base_url`).  
- `backend/services/notification_orchestrator.py` `_send_email` (blocked/failed outcomes).

---

## 2. Always write a notification log entry (SUCCESS or FAILED)

| Requirement | Status | Implementation / Gap |
|-------------|--------|------------------------|
| Create notification log on every attempt; status SUCCESS or FAILED so Notification Health reflects reality | **Partial** | Orchestrator **does** write a `message_log` for admin resend: it inserts PENDING before send, then updates to SENT or FAILED (or on provider-not-configured to **BLOCKED_PROVIDER_NOT_CONFIGURED**). Notification Health **summary/timeseries** only count `status: "SENT"` and `status: "FAILED"`. **Gap:** When outcome is **blocked** (e.g. provider not configured), status is `BLOCKED_PROVIDER_NOT_CONFIGURED`, so the attempt does **not** appear in “failed” counts. Task wants every attempt as SUCCESS or FAILED so health reflects reality → either (a) set status to **FAILED** (with `error_message`) when blocked, or (b) extend health APIs to include blocked. (a) is minimal and matches “SUCCESS or FAILED” wording.) |

**Relevant code:**  
- `backend/services/notification_orchestrator.py`: insert at ~281–294, `_send_email` update_one at ~491–494 (blocked) and 509–511 / 559–561 (failed/sent).  
- `backend/routes/admin.py` notification-health: `get_notification_health_summary` (counts SENT/FAILED only), `get_notification_health_recent` (lists all statuses).

---

## 3. Admin resend: return activation link in API response (manual fallback)

| Requirement | Status | Implementation / Gap |
|-------------|--------|------------------------|
| For admin-only resend, return generated activation link in response so ops can copy-paste if email fails | **Missing** | Admin resend returns only `{"message": "Password setup link resent"}`. **Gap:** Add `activation_link` (and optionally `provider_message_id`) to the 200 response. Link is already built as `setup_link` in the handler; do not expose raw token in API, only the full URL. |

**Relevant code:**  
- `backend/routes/admin.py` `resend_password_setup`: `setup_link` is built; response at ~1192.  
- Frontend expects no link today; will need to show “Copy link” when present (see §6).

---

## 4. Persist latest activation link + timestamps on client for audit/support

| Requirement | Status | Implementation / Gap |
|-------------|--------|------------------------|
| `activation_email_last_sent_at` | **Partial** | Codebase uses `activation_email_sent_at` (and portal setup-status exposes `activation_email_last_sent_at` as alias). **Gap:** Task names `activation_email_last_sent_at`; can align by persisting same value under that name or keep current name and document as equivalent. |
| `activation_email_last_status` (SENT/FAILED/SKIPPED) | **Partial** | Current field is `activation_email_status`. **Gap:** Task wants `activation_email_last_status`; same value (SENT/FAILED/SKIPPED). Admin resend **does not** update client at all today. **Missing:** Admin must update client with last status (and sent_at/error) on every resend attempt. |
| `activation_email_last_error` (nullable) | **Partial** | Current field is `activation_email_error`. **Gap:** Task name `activation_email_last_error`; same semantics. Admin resend does not set it. |
| `activation_link_last_url` (admin-visible only; do not expose publicly) | **Missing** | Not stored anywhere. **Gap:** On each admin resend, persist the generated setup URL (or domain-only if you prefer) on the client (or portal_user) for audit/support; expose only in admin APIs, never in portal/setup-status. |

**Relevant code:**  
- Client fields today: `activation_email_status`, `activation_email_sent_at`, `activation_email_error` (used in `portal.py` setup-status and resend-activation, and in provisioning).  
- `backend/routes/admin.py` `resend_password_setup`: no `db.clients.update_one` for activation fields.  
- `backend/routes/portal.py` setup-status and resend_activation: read/update `activation_email_*`.

---

## 5. Audit / notification log entry on every attempt

| Requirement | Status | Implementation / Gap |
|-------------|--------|------------------------|
| type: ACTIVATION_EMAIL_RESEND | **Partial** | Audit uses `AuditAction.PORTAL_INVITE_RESENT` on success only. **Gap:** Task wants an explicit type like `ACTIVATION_EMAIL_RESEND`; could add `AuditAction.ACTIVATION_EMAIL_RESEND` and use it for admin resend (or keep PORTAL_INVITE_RESENT and add `event_type: "ACTIVATION_EMAIL_RESEND"` in metadata). |
| status: SUCCESS or FAILED | **Partial** | Success path creates audit; failure path does not create audit in admin (orchestrator may create NOTIFICATION_PROVIDER_NOT_CONFIGURED etc.). **Gap:** Ensure every attempt (success and failure) creates one audit record with status SUCCESS or FAILED and required metadata. |
| metadata: client_id, portal_user_id, email, provider_message_id (if any), error (if any), activation_link_domain | **Partial** | PORTAL_INVITE_RESENT metadata currently has `admin_email`. **Gap:** Add client_id, portal_user_id, email (or masked), provider_message_id when present, error when failed, activation_link_domain (domain of setup link, not full URL). |

**Relevant code:**  
- `backend/routes/admin.py` create_audit_log after success (~1170–1174).  
- `backend/models/core.py` AuditAction (PORTAL_INVITE_RESENT, ACTIVATION_EMAIL_SENT, ACTIVATION_EMAIL_FAILED exist; no ACTIVATION_EMAIL_RESEND).  
- Orchestrator creates NOTIFICATION_PROVIDER_NOT_CONFIGURED, NOTIFICATION_FAILED_PERMANENT, etc.

---

## 6. Frontend: toast from API response; “Copy link” when activation_link returned

| Requirement | Status | Implementation / Gap |
|-------------|--------|------------------------|
| Toast based on actual API response; if API returns error, show error toast with message | **Done** | Admin dashboard `handleResendPassword`: on catch, shows `detail.message` or generic message; success toast only on no throw. So when backend returns 500/502, user sees error toast. |
| If API returns activation_link, show “Copy link” button | **Missing** | Backend does not return `activation_link` yet. **Gap:** Once backend returns `activation_link` on 200, frontend should show a “Copy link” button (e.g. next to success toast or in modal) so ops can paste link manually if email failed. |

**Relevant code:**  
- `frontend/src/pages/AdminDashboard.js`: `handleResendPassword` (~283–296), “Resend Password Link” button (~707–714).  
- No handling of `res.data.activation_link` today.

---

## 7. Summary: what to change (no duplication)

- **Backend – admin resend (`admin.py`)**  
  - **Already done:** Don’t return 200 on blocked/failed; return 500 with detail; use `get_frontend_base_url()` for link.  
  - **Add:** Return 200 with `activation_link` and `provider_message_id` (when sent).  
  - **Add:** On every attempt (success and failure), update client: `activation_email_last_sent_at`, `activation_email_last_status` (SENT/FAILED/SKIPPED), `activation_email_last_error`, `activation_link_last_url` (admin-only; store full URL or domain).  
  - **Add:** On every attempt, create one audit with type ACTIVATION_EMAIL_RESEND (or equivalent), status SUCCESS/FAILED, and full metadata (client_id, portal_user_id, email/masked, provider_message_id, error, activation_link_domain).  
  - **Align status codes:** FRONTEND_PUBLIC_URL missing → 500 + `FRONTEND_PUBLIC_URL_MISSING`. Optionally: Postmark missing/FROM not configured → 500 + `EMAIL_NOT_CONFIGURED`; Postmark reject → 502 + `EMAIL_PROVIDER_REJECTED`.  

- **Backend – notification orchestrator**  
  - When send is **blocked** (e.g. provider not configured), set `message_log.status` to **FAILED** (with `error_message`) instead of `BLOCKED_PROVIDER_NOT_CONFIGURED`, so Notification Health “failed” counts and recent list reflect the attempt.  

- **Frontend – Admin dashboard**  
  - When resend returns 200 and `activation_link`, show success toast and a “Copy link” button that copies `activation_link` to clipboard.  

- **Avoid duplication**  
  - Portal `resend_activation` (portal.py) and provisioning flows already persist `activation_email_status` / `activation_email_sent_at` / `activation_email_error` on the client. Reuse the same client fields (or the new last_* names) for admin resend so one source of truth.  
  - Do not add a second “resend” path for activation email; the single admin endpoint is `POST /api/admin/clients/{client_id}/resend-password-setup`.  
  - Notification log is already written by the orchestrator; only adjust status for blocked → FAILED so health is consistent.

---

## 8. Manual verification checklist (from task)

| Check | Current / After fixes |
|-------|------------------------|
| Resend → Network 200 + `{ provider_message_id, activation_link }` → email arrives | After: 200 includes these; email still sent by orchestrator. |
| Postmark misconfigured → Network 500 + EMAIL_NOT_CONFIGURED, UI error toast | After: 500 with appropriate error_code; UI already shows error on non-2xx. |
| Notification Health lists both success and failed attempts | After: blocked attempts stored as FAILED so they appear in failed count and recent list. |

---

## 9. Files to touch (concise)

- **Backend:**  
  - `backend/routes/admin.py` – resend_password_setup: response body, client update, audit with full metadata, optional status-code/error_code alignment.  
  - `backend/services/notification_orchestrator.py` – when blocked (e.g. provider not configured), set message_log status to FAILED.  
  - `backend/utils/public_app_url.py` – optional: no change if we only standardise error_code in admin (admin can map ValueError to FRONTEND_PUBLIC_URL_MISSING + 500).  
  - `backend/models/core.py` – optional: add `AuditAction.ACTIVATION_EMAIL_RESEND` if desired.  

- **Frontend:**  
  - `frontend/src/pages/AdminDashboard.js` – handle `activation_link` in resend response and show “Copy link” when present.

- **Notification health:**  
  - No new APIs; existing message_logs + summary/recent. Ensuring blocked attempts are stored as FAILED makes health reflect reality.

This gap analysis is the single reference to implement the task without duplicating or conflicting with existing activation email and notification health behaviour.
