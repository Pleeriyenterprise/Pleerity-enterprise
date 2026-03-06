# Production Deployment Configuration Audit

**Date:** 2025-02  
**Frontend:** React on Vercel — https://pleerityenterprise.co.uk, https://www.pleerityenterprise.co.uk, https://pleerity-enterprise.vercel.app, http://localhost:3000  
**Backend:** FastAPI on Render — https://api.pleerityenterprise.co.uk  

---

## Audit summary

| Area | Status | Notes |
|------|--------|--------|
| **1. CORS** | **Needs change → Fixed** | Code now merges required origins; all four origins allowed. |
| **2. Frontend/backend URL env** | **Needs change → Fixed** | Wrong fallbacks (pleerity.com, app.pleerity.co.uk, compliance-vault-pro.pleerity.com) replaced with https://pleerityenterprise.co.uk. |
| **3. Stripe / redirect URLs** | **Needs change → Fixed** | Checkout and intake success/cancel URLs use FRONTEND_URL; fallback set to production domain. |
| **4. Frontend API base URL** | **Safe** | Uses `REACT_APP_BACKEND_URL`; production must set to https://api.pleerityenterprise.co.uk. |
| **5. Cookies / session / auth** | **Safe** | Bearer token in header + localStorage; no cookies. No SameSite/domain issues. |
| **6. Postmark / email links** | **Needs change → Fixed** | All FRONTEND_URL fallbacks in email/portal links updated to production domain. |
| **7. Webhooks** | **Safe** | Stripe/Postmark webhooks target API domain; no code change. |

---

## 1. CORS (CORSMiddleware)

**File:** `backend/server.py`

**Before:**  
`allow_origins=os.environ.get('CORS_ORIGINS', '*').split(',')`  
- Default `*` is not production-safe.  
- If `CORS_ORIGINS` was set, the four required origins had to be manually listed.

**Required origins:**
- https://pleerityenterprise.co.uk  
- https://www.pleerityenterprise.co.uk  
- https://pleerity-enterprise.vercel.app  
- http://localhost:3000  

**Fix applied:**  
- Introduced `_CORS_REQUIRED_ORIGINS` with the four origins.  
- If `CORS_ORIGINS` is set and not `*`, its list is merged with `_CORS_REQUIRED_ORIGINS` (no duplicates).  
- If `CORS_ORIGINS` is unset or `*`, `allow_origins` is set to `_CORS_REQUIRED_ORIGINS`.  
- `allow_credentials=True` unchanged.

**Render:** You can still set `CORS_ORIGINS` to a comma-separated list; the code will add the four required origins if missing.

---

## 2. Frontend / public URL usage (FRONTEND_URL, etc.)

**Single source for email links:** `backend/utils/public_app_url.py` — `get_public_app_url()` / `get_frontend_base_url()` (reads `FRONTEND_PUBLIC_URL`, `PUBLIC_APP_URL`, `FRONTEND_URL`, then Vercel/Render URLs). Correct for production if env is set.

**Wrong fallbacks (replaced with `https://pleerityenterprise.co.uk`):**

| File | Was | Fix |
|------|-----|-----|
| `backend/routes/checkout_validation.py` | `FRONTEND_URL` default `https://pleerity.com` | `https://pleerityenterprise.co.uk` |
| `backend/routes/intake_wizard.py` | `FRONTEND_URL` default `https://pleerity.com` | `https://pleerityenterprise.co.uk` |
| `backend/routes/admin_orders.py` | `FRONTEND_URL` default `https://pleerity.com` (provide-info link) | `https://pleerityenterprise.co.uk` |
| `backend/routes/admin_orders.py` | `FRONTEND_URL` default `""` (document preview URL base) | `https://pleerityenterprise.co.uk` |
| `backend/services/intake_draft_service.py` | `FRONTEND_URL` default `https://pleerity.com` | `https://pleerityenterprise.co.uk` |
| `backend/routes/documents.py` | `FRONTEND_URL` default `https://compliance-vault-pro.pleerity.com` | `https://pleerityenterprise.co.uk` |
| `backend/services/jobs.py` | Portal fallback `https://app.pleerity.co.uk` (2 places) | `https://pleerityenterprise.co.uk` |
| `backend/services/support_email_service.py` | `FRONTEND_URL` default `https://pleerity.com` | `https://pleerityenterprise.co.uk` |
| `backend/routes/client_orders.py` | `FRONTEND_URL` default `https://pleerity.com` | `https://pleerityenterprise.co.uk` |
| `backend/services/order_email_templates.py` | `FRONTEND_URL` default `https://pleerity.com` | `https://pleerityenterprise.co.uk` |

**Left as-is (correct):**  
- `backend/services/order_delivery_service.py`: default `http://localhost:3000` (dev). Production must set `FRONTEND_URL`.  
- `backend/services/email_service.py`: already `https://pleerityenterprise.co.uk`.  
- `backend/services/jobs.py`: remaining `FRONTEND_URL` defaults to `http://localhost:3000` for compliance alert / renewal reminder when env unset (dev); production should set `FRONTEND_URL`.

**Recommendation:**  
On **Render**, set:

- `FRONTEND_URL=https://pleerityenterprise.co.uk`  
- `FRONTEND_PUBLIC_URL=https://pleerityenterprise.co.uk` (for activation/set-password emails)

No trailing slash.

---

## 3. Stripe success_url, cancel_url, return_url, portal URLs

**File and behaviour:**

| File | What | Current / fix |
|------|------|----------------|
| `backend/routes/checkout_validation.py` | success_url, cancel_url for checkout | From `FRONTEND_URL`; fallback set to `https://pleerityenterprise.co.uk`. |
| `backend/routes/intake_wizard.py` | success_url, cancel_url for intake checkout | Same. |
| `backend/services/stripe_service.py` | success_url, cancel_url, return_url | Uses `origin_url` from request or env; no hardcoded domain. |
| `backend/routes/billing.py` | return_url for portal | `origin` from request. |
| `backend/routes/admin_billing.py` | return_url | `base_url` from env. |
| `backend/clearform/routes/subscriptions.py` | success_url, cancel_url, return_url | `FRONTEND_URL` (default localhost; set in prod). |
| `backend/clearform/routes/credits.py` | success_url, cancel_url | Same. |

**Frontend:**  
- `frontend/src/pages/public/ServiceOrderPage.js`: sends `success_url` / `cancel_url` from `window.location.origin` — correct for production.  
- Other checkout flows use backend-built URLs from `FRONTEND_URL`.

**Fix:** Backend fallbacks that built Stripe redirect URLs now use `https://pleerityenterprise.co.uk` where applicable (see §2). No hardcoded Vercel preview or localhost in production-only paths.

---

## 4. Frontend API base URL

**Variable:** `REACT_APP_BACKEND_URL`  
**Read in:** `frontend/src/api/client.js` (baseURL for axios, exported `API_URL`).  
Also used in: ViewOrderPage, DocumentPreviewModal, ServicesCataloguePage, OrderCheckoutPage, ordersApi, and other pages that call the API.

**Production:** In Vercel (and any build), set:

`REACT_APP_BACKEND_URL=https://api.pleerityenterprise.co.uk`

No trailing slash. Build-time only (React env).

---

## 5. Cookies, session, SameSite, Secure, auth

**Auth:** JWT in `Authorization: Bearer <token>`, token stored in `localStorage` as `auth_token`. No auth cookies.

**Result:** No cookie domain or SameSite issues between https://pleerityenterprise.co.uk and https://api.pleerityenterprise.co.uk. CORS with `allow_credentials=True` is correct for credentialed API requests from the frontend.

---

## 6. Postmark / email template links

**Backend:** Email links (portal, view-order, provide-info, billing, etc.) use `FRONTEND_URL` or `get_public_app_url()`.  
**Fixes:** All identified wrong fallbacks now use `https://pleerityenterprise.co.uk` (see §2).  
**Postmark:** Configure webhook to point at API: `https://api.pleerityenterprise.co.uk/api/webhooks/postmark`. No frontend domain in webhook URL.

---

## 7. Webhooks and callbacks

| Service | URL type | Value | Note |
|---------|----------|--------|------|
| **Stripe** | Webhook endpoint | API domain | Set in Stripe Dashboard: `https://api.pleerityenterprise.co.uk/api/webhook/stripe` or `.../api/webhooks/stripe`. |
| **Postmark** | Webhook | API domain | `https://api.pleerityenterprise.co.uk/api/webhooks/postmark`. |
| **Twilio** | Status callbacks | API domain | Any status callback should use API base URL (e.g. `https://api.pleerityenterprise.co.uk/...`). |

**Rule:** Webhooks and provider callbacks → API domain. Redirects and links sent to users (email, Stripe success/cancel) → frontend domain (https://pleerityenterprise.co.uk).

---

## Checklist for production

**Render (backend):**

- [ ] `FRONTEND_URL=https://pleerityenterprise.co.uk`
- [ ] `FRONTEND_PUBLIC_URL=https://pleerityenterprise.co.uk` (for activation/set-password emails)
- [ ] `CORS_ORIGINS` optional; if set, use comma-separated list (required origins are merged in code)
- [ ] Stripe webhook URL: `https://api.pleerityenterprise.co.uk/api/webhook/stripe` (or `/api/webhooks/stripe`)
- [ ] Postmark webhook: `https://api.pleerityenterprise.co.uk/api/webhooks/postmark`

**Vercel (frontend):**

- [ ] `REACT_APP_BACKEND_URL=https://api.pleerityenterprise.co.uk` (build env)
- [ ] Custom domains: pleerityenterprise.co.uk, www.pleerityenterprise.co.uk (already in your setup)

---

## Diff summary (code changes)

1. **backend/server.py**  
   - CORS: added `_CORS_REQUIRED_ORIGINS` and logic to merge with `CORS_ORIGINS` or use required list when env is `*`/unset.

2. **backend/routes/checkout_validation.py**  
   - `FRONTEND_URL` default: `https://pleerity.com` → `https://pleerityenterprise.co.uk`.

3. **backend/routes/intake_wizard.py**  
   - Same default change.

4. **backend/routes/admin_orders.py**  
   - `FRONTEND_URL` default: `https://pleerity.com` → `https://pleerityenterprise.co.uk` (provide-info link).  
   - Document preview `base_url` default: `""` → `https://pleerityenterprise.co.uk`.

5. **backend/services/intake_draft_service.py**  
   - `FRONTEND_URL` default: `https://pleerity.com` → `https://pleerityenterprise.co.uk`.

6. **backend/routes/documents.py**  
   - `FRONTEND_URL` default: `https://compliance-vault-pro.pleerity.com` → `https://pleerityenterprise.co.uk`.

7. **backend/services/jobs.py**  
   - Portal fallback: `https://app.pleerity.co.uk` → `https://pleerityenterprise.co.uk` (2 places).

8. **backend/services/support_email_service.py**  
   - `FRONTEND_URL` default: `https://pleerity.com` → `https://pleerityenterprise.co.uk`.

9. **backend/routes/client_orders.py**  
   - `FRONTEND_URL` default: `https://pleerity.com` → `https://pleerityenterprise.co.uk`.

10. **backend/services/order_email_templates.py**  
    - `FRONTEND_URL` default: `https://pleerity.com` → `https://pleerityenterprise.co.uk`.

No frontend code changes. Localhost defaults kept where they are for local development.
