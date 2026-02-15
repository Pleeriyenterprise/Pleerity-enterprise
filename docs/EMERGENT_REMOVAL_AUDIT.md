# Emergent platform removal – audit and checklist

This document lists all Emergent-related references and how they were handled so the app runs on **Render (backend) + Vercel (frontend) + MongoDB Atlas** with no Emergent dependencies.

---

## 1. Audit: Emergent-related references

### Packages / imports (Python)

| Item | Type | Action |
|------|------|--------|
| `emergentintegrations` (commented in requirements.txt) | HARD | Removed; was not on PyPI. Replaced with `utils.llm_chat` using `google-generativeai`. |
| Imports `emergentintegrations.llm.chat` (LlmChat, UserMessage, FileContentWithMimeType) in prompt_service, document_orchestrator, document_analysis, assistant_service, admin.py, support_chatbot, lead_ai_service, clearform template_service, document_service | HARD | Replaced with `utils.llm_chat` (chat, chat_with_file, _get_api_key). |
| Imports `emergentintegrations.llm.gemini` (GeminiChat) in lead_ai_service | HARD | Replaced with `utils.llm_chat.chat`. |

### Environment variables

| Variable | Type | Action |
|----------|------|--------|
| `EMERGENT_LLM_KEY` | HARD | Replaced by `LLM_API_KEY`. Code still reads `EMERGENT_LLM_KEY` as fallback for backward compat. |
| `FRONTEND_URL` default `https://order-fulfillment-9.preview.emergentagent.com` | SOFT | Default set to `http://localhost:3000` in backend. |
| `UNSUBSCRIBE_URL` default Emergent URL | SOFT | Default set to `http://localhost:3000/unsubscribe`. |
| `STRIPE_API_KEY` default `sk_test_emergent` | SOFT | Default set to `""`; must be set in env for Stripe. |
| `REACT_APP_BACKEND_URL` in docs/samples (Emergent URL) | SOFT | Replaced with `https://your-backend.onrender.com` / placeholder in README. |

### Config folders / files

| Item | Type | Action |
|------|------|--------|
| `.emergent/emergent.yml` (Emergent job/image metadata) | SOFT | Deleted; `.emergent/` added to `.gitignore`. |

### Scripts / deploy / build

| Item | Type | Action |
|------|------|--------|
| Backend entry | — | Already standard: `uvicorn server:app --host 0.0.0.0 --port 8001` (see README / Render). |
| Frontend build | — | Already standard: `npm run build` (CRA); Vercel runs this. |
| `scripts/production_check.sh` curl to Emergent URL | SOFT | Left as-is (script may be updated to use env or Render URL when used). |

### Docs references

| Item | Type | Action |
|------|------|--------|
| README: "Deployment: Emergent Platform" | SOFT | Updated to "Render (backend), Vercel (frontend), MongoDB Atlas". |
| README: Stripe "via emergentintegrations" | SOFT | Removed. |
| README: curl examples with order-fulfillment-9.preview.emergentagent.com | SOFT | Replaced with `YOUR_BACKEND_URL` / `your-backend.onrender.com`. |
| README: env samples with Emergent URLs / EMERGENT_LLM_KEY | SOFT | Replaced with Render/Vercel placeholders and `LLM_API_KEY`. |
| docs/BLANK_SCREEN_*.md, LAUNCH_READINESS_*.md, etc. | SOFT | Left as historical; can be updated later to reference Render/Vercel. |
| Test files (BASE_URL default order-fulfillment-9...) | SOFT | Can default to `http://localhost:8001` or rely on `REACT_APP_BACKEND_URL` in CI. |

---

## 2. Env vars required after cleanup (Render + Vercel + Atlas)

### Backend (Render)

| Variable | Required | Notes |
|----------|----------|--------|
| `MONGO_URL` | Yes | MongoDB Atlas connection string |
| `DB_NAME` | Yes | e.g. `compliance_vault_pro` |
| `CORS_ORIGINS` | Yes | Include Vercel frontend origin (e.g. `https://your-app.vercel.app`) |
| `JWT_SECRET` | Yes | Strong secret for JWT |
| `JWT_ALGORITHM` | Optional | Default HS256 |
| `JWT_EXPIRATION_HOURS` | Optional | Default 24 |
| `STRIPE_API_KEY` | Yes | Stripe secret key (test or live) |
| `FRONTEND_URL` | Yes | Full frontend URL (e.g. `https://your-app.vercel.app`) |
| `POSTMARK_SERVER_TOKEN` | If using email | Postmark API token |
| `UNSUBSCRIBE_URL` | If using email | e.g. `{FRONTEND_URL}/unsubscribe` |
| `LLM_API_KEY` | If using AI | Google AI Studio / Gemini API key |
| `ENVIRONMENT` | Optional | `production` on Render |
| `ADMIN_DASHBOARD_URL` | Optional | Defaults from FRONTEND_URL + `/admin/leads` |

### Frontend (Vercel)

| Variable | Required | Notes |
|----------|----------|--------|
| `REACT_APP_BACKEND_URL` | Yes | Backend base URL (e.g. `https://your-app.onrender.com`), no trailing slash |

### MongoDB Atlas

- Use the same `MONGO_URL` and `DB_NAME` as in Render.
- No Emergent-specific config.

---

## 3. Summary

- **HARD:** All `emergentintegrations` usage removed and replaced with `backend/utils/llm_chat.py` (Google Generative AI). LLM env is `LLM_API_KEY` (with `EMERGENT_LLM_KEY` fallback).
- **SOFT:** Emergent URLs and Stripe/Emergent defaults removed from code and README; `.emergent` removed and ignored; docs/env aligned to Render + Vercel + Atlas.
- **Product behavior:** Auth, RBAC, Stripe, Tawk, and app behavior unchanged except for removal of Emergent-specific code and config.
