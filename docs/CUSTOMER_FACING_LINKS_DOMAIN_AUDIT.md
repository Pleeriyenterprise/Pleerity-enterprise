# Customer-facing links domain audit

**Date:** 2026-02  
**Issue:** Password reset (and other) emails were sending users to `https://pleerity-enterprise-9jjg.vercel.app` instead of the custom domain `https://pleerityenterprise.co.uk`.

---

## 1. Root cause: password reset link

**Exact cause:** The backend builds the password reset link in `backend/routes/auth.py` using `get_frontend_base_url()` from `backend/utils/public_app_url.py`. That helper used a fallback chain that included **VERCEL_URL**. When `FRONTEND_PUBLIC_URL`, `PUBLIC_APP_URL`, and `FRONTEND_URL` were unset (or not set on the backend/Render), the code fell back to `VERCEL_URL` (or similar), which in some deployments resolves to the default Vercel deployment hostname `pleerity-enterprise-9jjg.vercel.app`. So users received reset links pointing at the Vercel default domain instead of the custom domain.

**Fix applied:**
- **`backend/utils/public_app_url.py`**: Removed `VERCEL_URL` and `RENDER_EXTERNAL_URL` from the fallback chain. Customer-facing email links must never use deployment hostnames. When no env is set, the code now returns the **canonical production URL** `https://pleerityenterprise.co.uk` for `for_email_links=True`, so password reset and activation links always use the custom domain.

---

## 2. Files where the old domain or wrong fallbacks were found

| File | Finding | Change |
|------|---------|--------|
| `backend/utils/public_app_url.py` | Used VERCEL_URL / RENDER_EXTERNAL_URL fallback; could raise when env missing | Removed Vercel/Render from chain; added canonical fallback `https://pleerityenterprise.co.uk` for email links |
| `backend/tests/test_public_app_url.py` | Tests used `pleerity-enterprise-9jjg.vercel.app`; one test expected ValueError when env missing | Switched examples to `pleerityenterprise.co.uk`; updated test to expect canonical URL when env unset |
| `frontend/src/config/branding.js` | `SITE_URL = 'https://pleerity.com'` (wrong for this product) | Set to `https://pleerityenterprise.co.uk` |
| `backend/utils/branding.py` | `WEBSITE_URL = "https://pleerity.com"` | Set to `https://pleerityenterprise.co.uk` |
| `README.md` | Examples used `your-app.vercel.app`, `pleerity-enterprise-9jjg.vercel.app`; fallback order mentioned VERCEL_URL | Examples now use `pleerityenterprise.co.uk`; doc updated to state canonical fallback |
| `backend/server.py` | `_CORS_REQUIRED_ORIGINS` includes `https://pleerity-enterprise.vercel.app` | **Left as-is** – CORS must allow the Vercel deployment origin for browser requests; this does not affect email link URLs |
| `docs/PRODUCTION_DEPLOYMENT_AUDIT.md` | Descriptive list of frontend URLs | **Left as-is** – documents allowed origins |

---

## 3. Canonical source of truth for customer-facing links

**Preferred:** Set in deployment (Render backend):

```bash
FRONTEND_URL=https://pleerityenterprise.co.uk
FRONTEND_PUBLIC_URL=https://pleerityenterprise.co.uk
```

**Code behaviour:**
- **Email links (password reset, activation, invite, onboarding):** `get_frontend_base_url()` / `get_public_app_url(for_email_links=True)` — reads `FRONTEND_PUBLIC_URL` → `PUBLIC_APP_URL` → `FRONTEND_URL`; if none set, returns `https://pleerityenterprise.co.uk`. Never uses `VERCEL_URL` or `RENDER_EXTERNAL_URL`.
- **Other frontend URLs (Stripe return, portal links, etc.):** Various files use `os.getenv("FRONTEND_URL", "https://pleerityenterprise.co.uk")` or `get_public_app_url()`; see §4.

---

## 4. Links corrected / verified

| Area | Where | Source of URL | Status |
|------|--------|----------------|--------|
| Password reset email | `auth.py` | `get_frontend_base_url()` | Fixed (canonical fallback; no Vercel) |
| Activation / set-password (admin invite) | `admin.py`, `provisioning.py`, `admin_billing.py` | `get_frontend_base_url()` / `get_public_app_url()` | Uses same module |
| Portal invite (tenant) | `client.py` (invite_url, login_url) | `body.base_url` from caller | Caller must pass correct base_url |
| Onboarding / intake | `risk_lead_email_service.py`, `lead_nurture_service.py` | `get_public_app_url()` or `FRONTEND_URL` | Lead nurture fallback was localhost; kept for dev; prod should set FRONTEND_URL |
| Report share links | `reporting.py` | `PUBLIC_URL` | Doc recommends `PUBLIC_URL=https://pleerityenterprise.co.uk` |
| Stripe return / billing portal | `admin_billing.py`, `stripe_webhook_service.py` | `get_public_app_url()` | Correct |
| Support chatbot / assistant | `support_chatbot.py`, `support_chatbot_knowledge.py`, `assistant_prompt.py` | `FRONTEND_URL` or `get_public_app_url()` | Fallback `https://pleerityenterprise.co.uk` |
| Email templates (portal link, CTA) | `email_service.py`, `order_email_templates.py`, `order_delivery_service.py` | `FRONTEND_URL` / `PORTAL_BASE_URL` / model | order_delivery_service default localhost; prod must set FRONTEND_URL |
| Document preview / provide-info | `admin_orders.py`, `documents.py` | `FRONTEND_URL` | Default `https://pleerityenterprise.co.uk` |
| Schema / meta / logo (frontend) | `branding.js` (`SITE_URL`, `SCHEMA_LOGO_URL`) | Hardcoded | Updated to `https://pleerityenterprise.co.uk` |
| Backend branding (PDF, footer) | `utils/branding.py` (`WEBSITE_URL`) | Hardcoded | Updated to `https://pleerityenterprise.co.uk` |

---

## 5. Env variables to set in deployment

**Backend (Render):**

| Variable | Value | Purpose |
|----------|--------|--------|
| `FRONTEND_URL` | `https://pleerityenterprise.co.uk` | All frontend links (emails, redirects, portal) |
| `FRONTEND_PUBLIC_URL` | `https://pleerityenterprise.co.uk` | Activation/set-password links (optional if FRONTEND_URL set) |
| `PUBLIC_URL` | `https://pleerityenterprise.co.uk` | Report share link URLs (optional) |

No trailing slash. Do **not** set `VERCEL_URL` on the backend for link building; the code no longer uses it for customer-facing links.

**Frontend (Vercel):**

| Variable | Value | Purpose |
|----------|--------|--------|
| `REACT_APP_BACKEND_URL` | `https://api.pleerityenterprise.co.uk` | API base URL |

---

## 6. Summary

- **Password reset (and activation/invite) link fix:** `public_app_url.py` no longer uses `VERCEL_URL` or `RENDER_EXTERNAL_URL`; when env is unset, email links use `https://pleerityenterprise.co.uk`.
- **Single canonical domain:** Customer-facing links use `FRONTEND_URL` (or canonical fallback). Frontend `SITE_URL` and backend `WEBSITE_URL` set to `https://pleerityenterprise.co.uk`.
- **Tests and docs:** Tests and README updated to use the custom domain; audit doc added for future reference.
