# Risk Check → Lead Capture → Activate Monitoring → Pre-filled Intake — How to Test End-to-End

## Prerequisites

- Backend and frontend running (see project README).
- **Backend env:** `RISK_LEAD_TOKEN_SECRET` or `SECRET_KEY` set (for signed lead_token).  
  For activation link in emails: `FRONTEND_PUBLIC_URL` or `PUBLIC_APP_URL` (app origin, no trailing slash).  
  Example: `FRONTEND_PUBLIC_URL=https://portal.pleerityenterprise.co.uk`
- **Frontend env:** `REACT_APP_BACKEND_URL` pointing at your backend API (or proxy).

---

## 1. Risk Check creates lead only (no Client)

1. Open **Risk Check** page:  
   `https://<marketing-or-app-origin>/risk-check`
2. Complete the 5 questions (property count, HMO, gas/eicr status, tracking method).
3. Enter **email** (and optional first name), submit.
4. **Expected:** Full report with score/band; “Report sent” (email sent if configured).
5. **Verify in DB:**  
   - `risk_leads` has one document with that email (and `last_activation_link_sent_at` set if email sent).  
   - **No** new document in `clients` or `portal_users`.  
   - No subscription or provisioning triggered.

---

## 2. Activation link in email (lead_token)

1. After step 1, check the “Your Compliance Risk Snapshot” email (or logs if email not configured).
2. **Expected:** “Activate Monitoring” link is:  
   `https://<APP_ORIGIN>/intake/start?lead_token=<signed_token>`  
   APP_ORIGIN must be the **app** (portal) origin from `FRONTEND_PUBLIC_URL` / `PUBLIC_APP_URL`, not the marketing domain.
3. Token must be a long string (signed payload + signature).  
4. **Optional:** If email provider is not configured, backend may return or log the activation URL; use that URL in the next step.

---

## 3. Lead-from-token → pre-filled intake

1. Open the activation link from the email (or use a valid `lead_token` from your env):  
   `https://<APP_ORIGIN>/intake/start?lead_token=<token>`
2. **Expected:**  
   - Intake page loads.  
   - **GET /api/risk-check/lead-from-token?lead_token=...** is called (network tab).  
   - Form is **pre-filled** with: email, name (first_name/full_name), phone if present, first property’s “is HMO” if lead had HMO, optional document method hint from tracking_method.  
   - **Banner:** “We preloaded your setup from your risk check. You can change anything.”  
   - If lead had `property_count` > 1: on Step 3, “You indicated X properties; add them here.”  
   - **Plan** is **not** auto-set (default or from `?plan=` only).  
   - **Consent checkboxes** are **not** checked (user must tick them).
3. Edit any field; submit intake and complete Stripe checkout as usual.

---

## 4. Conversion (lead → converted after payment)

1. Complete intake + Stripe checkout using either:  
   - Link with **lead_token** (prefill), or  
   - Link with **lead_id** (e.g. from risk-check page CTA: `/intake/start?lead_id=RISK-xxx&from=risk-check`).
2. **Expected:**  
   - After Stripe `checkout.session.completed`, `risk_leads` document is updated:  
     `status = "converted"`, `converted_at` set, `client_id` set.  
   - Provisioning runs as before (unchanged); no extra provisioning from conversion.
3. **Fallback by email:**  
   - Use an intake/checkout **without** `lead_id` in metadata (e.g. direct `/intake/start` with same email as a risk lead).  
   - After payment, webhook should still find the risk lead by **customer email** (case-insensitive) and set `converted`, `converted_at`, `client_id` on that lead.

---

## 5. Token expiry

1. Use an **old or tampered** token:  
   `https://<APP_ORIGIN>/intake/start?lead_token=expired-or-invalid`
2. **Expected:**  
   - **GET /api/risk-check/lead-from-token** returns **401** (or 400 if token missing).  
   - Frontend shows a toast/error like “Invalid or expired link. Request a new report from the risk check.”  
   - No prefill; user can still complete intake manually.

---

## 6. URLs and env (single source of truth)

- **Activation links in emails:** Always use **app origin** (`FRONTEND_PUBLIC_URL` / `PUBLIC_APP_URL`). Do **not** use request `Origin` or marketing domain for this link.
- **Backend:** Prefer `FRONTEND_PUBLIC_URL` or `PUBLIC_APP_URL` for any link to the frontend (intake, set-password, etc.).
- **Frontend:** `REACT_APP_BACKEND_URL` for API calls; app origin for redirects/success URLs can match `window.location.origin` when app is served from the same host.

---

## Quick checklist

| Step | Action | Expected |
|------|--------|----------|
| 1 | Submit risk check with email | 200, lead in `risk_leads`, no client |
| 2 | Open “Activate Monitoring” from email | Link = app origin + `/intake/start?lead_token=...` |
| 3 | Open link in browser | Prefill + banner; plan/consents not auto-set |
| 4 | Complete intake + payment | Lead marked converted; provisioning unchanged |
| 5 | Invalid/expired token | 401, error message, no prefill |

---

## File references (implementation)

- **Token:** `backend/utils/risk_lead_token.py` — `create_lead_token`, `verify_lead_token`
- **Activation URL:** `backend/services/risk_lead_email_service.py` — `_activate_url(lead, activation_token)`; app origin + `?lead_token=`
- **Report + upsert:** `backend/routes/risk_check.py` — POST `/report` (upsert by email), token generation, `last_activation_link_sent_at`
- **Lead prefill API:** `backend/routes/risk_check.py` — GET `/lead-from-token`
- **Webhook conversion:** `backend/services/stripe_webhook_service.py` — lead_id in metadata; fallback find by customer email
- **Intake prefill:** `frontend/src/pages/IntakePage.js` — `lead_token` in URL → `getLeadFromToken` → prefill + banner; `frontend/src/api/client.js` — `getLeadFromToken`
- **Tests:** `backend/tests/test_risk_check.py`, `backend/tests/test_risk_lead_email_service.py`


## PR-ready diff summary

| Area | Change |
|------|--------|
| **Backend – token** | New `utils/risk_lead_token.py`: `create_lead_token(lead_id, expiry_days=7)`, `verify_lead_token(token)` (HMAC-signed, 7-day expiry). |
| **Backend – email** | `services/risk_lead_email_service.py`: `_activate_url(lead, activation_token=None)` uses app origin (`get_public_app_url`) and appends `?lead_token=...` when token provided. `send_risk_lead_email(lead, step, activation_token=None)`; step 1 body uses token. |
| **Backend – report** | `routes/risk_check.py`: POST `/report` upserts by email (find_one then update or insert), generates token, sends email with token, sets `last_activation_link_sent_at` and `source`. |
| **Backend – lead-from-token** | New GET `/api/risk-check/lead-from-token?lead_token=...`: verify token, return sanitized payload (no score/exposure). 400 if missing token, 401 if invalid/expired. |
| **Backend – webhook** | `stripe_webhook_service.py`: After converting by `lead_id` in metadata, fallback: if no lead_id, find risk_lead by customer email (case-insensitive) and set converted/converted_at/client_id. No provisioning change. |
| **Frontend – API** | `api/client.js`: `intakeAPI.getLeadFromToken(leadToken)` → GET `/risk-check/lead-from-token`. |
| **Frontend – IntakePage** | Read `lead_token` from URL; useEffect calls `getLeadFromToken`, prefills full_name/email/phone, first property is_hmo, optional document_submission_method; sets `marketing.lead_id`; banner “We preloaded your setup from your risk check”; Step 3 `leadPropertyCountHint` “You indicated X properties; add them here.” Does not set billing_plan or consents. |
| **Tests** | `test_risk_check.py`: report does not create client, lead-from-token 200/sanitized, 400 missing token, 401 invalid/expired. `test_risk_lead_email_service.py`: app origin URL, token in URL, step1 with token. New `test_risk_lead_token.py`: roundtrip, expired, tampered, empty. |
| **Docs** | `docs/RISK_CHECK_LEAD_TOKEN_E2E_TEST.md`: How to test end-to-end, checklist, env, file refs. `docs/RISK_CHECK_LEAD_CAPTURE_PREFILL_TASK_AUDIT.md`: Audit (existing). |

**Env:** Backend: `RISK_LEAD_TOKEN_SECRET` or `SECRET_KEY`; `FRONTEND_PUBLIC_URL` or `PUBLIC_APP_URL` for activation links. Frontend: `REACT_APP_BACKEND_URL` (unchanged).
