# Four Services Audit (AI Automation, Market Research, Compliance, Document Packs) & Repo Structure Conflict

**Purpose:** (1) Check the codebase against requirements for the **four services only** — what’s implemented, what’s missing, how it was implemented, and how to avoid affecting CVP. (2) Address the requested “Create a repo structure” (Next.js, Node.js API, monorepo) and state **conflicting instructions** with a clear, safe recommendation. **No implementation** of the new structure in this document.

**Scope:** Services = AI automation services, Market research, Compliance services, Document packs. **CVP (Compliance Vault Pro)** must not be changed or broken by any services-only work.

---

## 1. Current Repo Structure (Fact)

The codebase is **not** a monorepo with `apps/web`, `apps/api`, `packages/shared`, `packages/ui`. It is:

| Layer | Current implementation |
|-------|------------------------|
| **Frontend** | `frontend/` — **React** (Create React App), JavaScript. Deployed on Vercel. |
| **Backend** | `backend/` — **Python FastAPI**, MongoDB (Motor), Stripe, Postmark, LLM usage (e.g. GPT) in services. No Node.js, no Express/Fastify. |
| **Shared** | No `packages/shared`; types/constants live in backend (Pydantic, Python) and frontend (JS). No Zod; validation is Pydantic (backend) and form libs (frontend). |
| **Workspaces** | No root `package.json` workspaces; single `frontend/package.json`. Backend is Python (`requirements.txt` or similar). |

So: **stack = React + FastAPI + MongoDB + Stripe + Postmark**, not Next.js + Node.js + TypeScript + Zod.

---

## 2. Four Services — What Is Implemented

### 2.1 Catalogue & categories

| Item | Status | Where |
|------|--------|--------|
| Service catalogue V2 | Implemented | `backend/services/service_catalogue_v2.py`, `service_definitions_v2.py` — categories: `ai_automation`, `market_research`, `compliance`, `document_pack`. |
| Category config (CMS) | Implemented | `backend/models/cms.py` — `CATEGORY_CONFIG` for slugs `ai-automation`, `market-research`, `compliance-audits`, `document-packs` with name, tagline, `service_catalogue_category`. |
| AI Automation services | Implemented | e.g. `AI_WF_BLUEPRINT`, `AI_PROC_MAP`, `AI_TOOL_REPORT` in `service_definitions_v2.py`; intake schema, pricing, workflow names. |
| Market Research | Implemented | `MR_BASIC`, `MR_ADV` in catalogue and `intake_draft_service.SERVICE_BASE_PRICES`. |
| Compliance services | Implemented | `HMO_AUDIT`, `FULL_AUDIT`, `MOVE_CHECKLIST` in catalogue and intake. |
| Document packs | Implemented | `DOC_PACK_ESSENTIAL`, `DOC_PACK_PLUS`, `DOC_PACK_PRO` (and legacy TENANCY/ULTIMATE); `document_pack_webhook_handler.VALID_PACK_CODES`, `document_pack_orchestrator`, `pack_registry`. |

### 2.2 Intake & checkout (orders only — not CVP)

| Item | Status | Where |
|------|--------|--------|
| Order intake (draft API) | Implemented | `backend/routes/intake_wizard.py`, `intake_draft_service.py` — create draft, update, validate, checkout. Stripe checkout with `mode: "payment"`, `metadata.type: "order_intake"`. |
| Unified Intake Wizard (UI) | Implemented | `frontend/src/pages/UnifiedIntakeWizard.js` — service selection, client info, service-specific fields, review, payment. Uses `/order/intake?service=...`. |
| CVP intake (separate) | Implemented | `/intake/start` → `POST /api/intake/submit`, `POST /api/intake/checkout` — subscription, `client_id`, `plan_code`. **Not** used for the four services. |

### 2.3 Stripe webhook — services vs CVP

| Flow | Trigger | Handler | Collections touched |
|------|---------|--------|----------------------|
| **Order payment** (four services) | `checkout.session.completed` with `mode === "payment"` and `metadata.type === "order_intake"` | `_handle_order_payment` → `convert_draft_to_order`; if pack, `document_pack_webhook_handler.handle_checkout_completed` | `orders`, `intake_drafts`, `document_pack_items` (packs only). **No** `clients`, `portal_users`, `provisioning_jobs`. |
| **CVP subscription** | `mode === "subscription"` | `_handle_subscription_checkout` → client billing, provisioning | `clients`, `client_billing`, `provisioning_jobs`, `portal_users`, etc. |

**Conclusion:** The four services and CVP are already separated at Stripe and in the DB. Services do not write to CVP collections.

### 2.4 Fulfilment

| Service area | Fulfilment path | Where |
|--------------|-----------------|--------|
| Document packs | Webhook → create `document_pack_items` → QUEUED → document_pack_orchestrator (generate items) | `document_pack_webhook_handler.py`, `document_pack_orchestrator.py`, `routes/document_packs.py` |
| AI Automation, Market Research, Compliance audits | Order workflow (QUEUED → workflow_automation_service, prompts, report generation) | `order_workflow.py`, `workflow_automation_service.py`, `prompt_service.py`, `document_orchestrator.py`, etc. |

### 2.5 Marketing & public routes

| Item | Status | Where |
|------|--------|--------|
| Services hub / category pages | Implemented | CMS-driven: `get_category_page`, `get_service_page`; slugs from `CATEGORY_CONFIG`. Frontend: `ServicesHubPageCMS.js`, category/service pages. |
| Public API for services | Implemented | e.g. `GET /api/marketing/services/category/{slug}`, `GET /api/marketing/services/{category_slug}/{service_slug}`; `public_services_v2.py`, `checkout_validation.py`. |
| Seed (catalogue + CMS pages) | Implemented | `server.py` seeds `service_catalogue_v2` and (optionally) CMS pages; `scripts/seed_cms_pages.py`, `restore_services.py`. |

### 2.6 What could be “missing” or improved (services only)

- **CMS pages empty:** If SERVICE-type CMS pages for a category were never seeded or are unpublished, category/service pages can show “No services” or 404. Fix: run seed and/or publish pages; do **not** change CVP or shared auth.
- **Stripe products/prices:** Service codes must have matching Stripe products/prices for checkout. Handled in `intake_draft_service` and Stripe config; ensure env/Stripe dashboard align with catalogue.
- **LLM/abstraction:** Backend uses LLM (e.g. GPT) in prompts/document generation; there is no single “LLM provider abstraction” module. Any refactor to a shared abstraction should live in backend only and must not change CVP or subscription flows.
- **Logging:** Backend uses Python `logging`; no Pino (Node). If the new structure were Node, Pino would apply there only.
- **Validation:** Backend uses Pydantic; no Zod (Zod is JS/TS). Shared Zod would only apply if a Node/TS layer is introduced.

---

## 3. How to Work on the Four Services Without Affecting CVP

- **Stripe:** Do not change `_handle_subscription_checkout` or subscription event handlers. Only touch `_handle_order_payment` and order/pack logic when adding or changing **order** flows.
- **Intake:** Do not change `/intake/start`, `POST /api/intake/submit`, or CVP checkout. Only change `/order/intake`, draft API, or order checkout for the four services.
- **Data:** Do not add writes to `clients`, `portal_users`, `provisioning_jobs`, `client_billing` from order/pack code. Orders use `orders`, `intake_drafts`, `document_pack_items`.
- **Auth:** CVP portal auth (JWT, portal_users) is shared; adding or changing **public** or **order** routes must not change how CVP users log in or how subscription status is enforced for the portal.
- **Testing:** Run CVP signup + subscription flow and at least one order (e.g. document pack or market research) to confirm both paths still work (see `docs/SERVICES_AI_MARKETRESEARCH_DOCPACKS_AUDIT.md` §7).

---

## 4. Conflicting Instructions: “Create a Repo Structure” (Next.js, Node, Monorepo)

You asked to:

- Create a repo structure: `/apps/web` (Next.js on Vercel), `/apps/api` (Node.js API on Render), `/packages/shared`, `/packages/ui`.
- Backend: Node.js + Express or Fastify, MongoDB Atlas, Stripe, Postmark, LLM provider abstraction.
- Use TypeScript everywhere, Zod in shared, strict env validation, Pino logging, error-handling middleware.
- Deliver: full folder structure, package.json workspaces, env.example files, minimal health endpoints, README.

**Conflict:** The **current** codebase is **React (frontend) + FastAPI (backend)**, not Next.js + Node.js. So:

- **Option A — Create the new structure inside this repo:** You would have two frontends (React + Next.js) and two backends (FastAPI + Node). CVP and the four services today run on React + FastAPI. Adding `apps/web` (Next) and `apps/api` (Node) would not “replace” the four services without a full migration; CVP would stay on the current stack. So you’d have two stacks in one repo (complex, two deploy pipelines, shared DB/Stripe only).
- **Option B — Create the new structure as a replacement:** Migrating the whole platform (CVP + four services) to Next.js + Node would **affect CVP** (rewrite). That contradicts “must not affect CVP.”
- **Option C — Create the new structure for “services only” in a separate repo:** The four services could live in a new monorepo (Next.js + Node), and CVP stays in this repo (React + FastAPI). Then you have two codebases, two deployments; shared MongoDB/Stripe/Postmark would need clear rules (e.g. same DB, different collections or prefixes for “services” if needed). CVP is untouched. This is the only way to have the **requested** stack without touching CVP.
- **Option D — Do not create the new structure; keep current stack:** Continue with React + FastAPI for both CVP and the four services. The “repo structure” and tech (Next, Node, Zod, Pino) are documented as a **future** or **alternative** target, and no new folders/workspaces are added. No risk to CVP; no second stack.

---

## 5. Recommendation (Safest, No Blind Implementation)

- **For the four services (AI automation, Market research, Compliance services, Document packs):**
  - **Keep using the current codebase.** The implementation is already in place (catalogue, intake, Stripe routing, order workflow, document pack orchestrator), and it is **already isolated** from CVP (different Stripe mode/metadata, different collections, different intake URLs and handlers).
  - Any enhancement (e.g. new service codes, CMS seed, LLM abstraction) should stay in **backend (Python)** and **frontend (React)** and follow the “do not touch CVP” rules above.

- **For the requested “Create a repo structure” (Next.js, Node, monorepo, TypeScript, Zod, Pino):**
  - **Do not implement it inside the current repo** as the main app without an explicit decision to migrate (which would affect CVP).
  - **Preferred:** Treat the requested structure as a **spec for a separate “services platform”** or a **future migration**. If you want that stack for the four services only, the only safe way that “must not affect CVP” is **Option C**: a **separate** repo (or separate root) containing:
    - `apps/web` (Next.js) — for services marketing/order intake only.
    - `apps/api` (Node.js, Express or Fastify) — for order/draft/checkout/document-pack API only.
    - `packages/shared` (TypeScript, Zod, constants).
    - `packages/ui` if needed.
  - CVP would remain in **this** repo (React + FastAPI). No CVP code or routes in the new monorepo.
  - If you instead want a **single** codebase, then **Option D** is the safest: keep React + FastAPI, and do **not** create the Next.js/Node structure (to avoid two stacks and no clear “which app is production for what”).

**Summary:**

- **Audit:** The four services are implemented; CVP and services are already separated in Stripe and DB. Working on services only and following the “do not touch CVP” rules above is safe.
- **Repo structure ask:** It assumes a different stack (Next.js, Node). The only way to have that stack and “must not affect CVP” is a **separate** repo/root for the services platform (Option C). Otherwise, keep the current repo and stack (Option D) and do not create the new folder structure.

No new repo structure or code has been implemented in this task; only this audit and recommendation document.

---

## 6. Reference: Key Files (Services Only, No CVP)

| Area | Files |
|------|--------|
| Catalogue | `backend/services/service_catalogue_v2.py`, `service_definitions_v2.py` |
| Categories (CMS) | `backend/models/cms.py` (CATEGORY_CONFIG) |
| Draft / order intake | `backend/services/intake_draft_service.py`, `backend/routes/intake_wizard.py` |
| Stripe order vs CVP | `backend/services/stripe_webhook_service.py` (`_handle_checkout_completed` → `_handle_order_payment` vs `_handle_subscription_checkout`) |
| Document packs | `backend/services/document_pack_webhook_handler.py`, `document_pack_orchestrator.py`, `backend/routes/document_packs.py` |
| Order workflow (non-pack) | `backend/services/order_workflow.py`, `workflow_automation_service.py` |
| Frontend intake | `frontend/src/pages/UnifiedIntakeWizard.js` |
| Marketing | `frontend/src/pages/public/ServicesHubPageCMS.js`, category/service CMS pages; `backend/routes/marketing.py`, `cms_service.py` |
| CVP (do not change for services work) | `backend/routes/intake.py` (submit), `stripe_service.py` (CVP checkout), `_handle_subscription_checkout`, provisioning; `frontend` routes under `/intake/start`, `/dashboard`, etc. |

---

*Audit and conflict analysis only. No implementation of the new repo structure.*
