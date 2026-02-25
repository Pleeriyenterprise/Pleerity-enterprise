# Services (AI & Automation, Market Research, Document Packs, Compliance Audits) — Structure, Flow & Replaceability Audit

**Purpose:** Understand how these four service areas are structured and wired end-to-end, what the marketing pages show (and what was there before), and whether they can be replaced along with their intake. **Audit only — no implementation.**

---

## 1. High-Level Structure

| Service area        | Marketing slug       | Catalogue category  | Intake path           | Post-payment fulfilment                    |
|---------------------|----------------------|---------------------|------------------------|--------------------------------------------|
| AI & Automation     | `ai-automation`      | `ai_automation`     | Unified Intake Wizard  | Order workflow (QUEUED → generation)       |
| Market Research     | `market-research`    | `market_research`    | Unified Intake Wizard  | Order workflow (QUEUED → generation)       |
| Document Packs      | `document-packs`     | `document_pack`     | Unified Intake Wizard  | Document Pack Orchestrator (webhook)        |
| Compliance Audits   | `compliance-audits`  | `compliance`        | Unified Intake Wizard  | Order workflow (QUEUED → generation)       |

All four use the **same** marketing URL pattern and **same** order intake wizard; only **Document Packs** have a dedicated webhook/orchestrator path after payment.

---

## 2. Marketing Pages: What Exists and Why They Can Look “Empty”

### 2.1 Route and component wiring

- **Routes (App.js):**
  - `/services/:categorySlug` → **CategoryPageCMS** (e.g. `/services/ai-automation`, `/services/document-packs`)
  - `/services/:categorySlug/:serviceSlug` → **ServicePageCMS** (e.g. `/services/document-packs/essential-document-pack`)
- **Hub:** `/services` → **ServicesHubPageCMS** (or ServicesHubPage); lists the four categories and links to each category page.
- **Data source:** All category and service content is **CMS-driven**:
  - **Category:** `GET /api/marketing/services/category/{categorySlug}` → `cms_service.get_category_page(category_slug)` (reads `cms_pages` + `service_catalogue_v2`).
  - **Service:** `GET /api/marketing/services/{categorySlug}/{serviceSlug}` → `cms_service.get_service_page(...)` (CMS page + catalogue + CTA config).

### 2.2 Why pages can look “empty”

1. **Category page “empty”:**  
   - **CategoryPageCMS** shows “No services available in this category yet” when `services` from the API is empty.  
   - That happens when there are **no published SERVICE-type CMS pages** for that `category_slug` (e.g. no `page_type: "SERVICE"`, `category_slug: "ai-automation"`, `status: "published"` in `cms_pages`).
   - **Category** itself can still exist: `get_category_page` builds a fallback from `CATEGORY_CONFIG` if no CATEGORY page exists, but the **services** list comes only from CMS service pages. So if the seeder or admin never created/linked service pages for that category, the grid is empty.

2. **Service page “empty” or 404:**  
   - **ServicePageCMS** 404s if `get_service_page` returns null. That happens when there is no **published** CMS page with `page_type: "SERVICE"`, that `category_slug`, and that `service_slug`.  
   - So “empty” here usually means **no CMS service page** for that slug, or it’s unpublished.

3. **What was there before:**  
   - **Intended design:** Category and service content live in **CMS** (`cms_pages`) and are optionally seeded from the **Service Catalogue** via `scripts/seed_cms_pages.py`. The seeder creates HUB, CATEGORY, and SERVICE pages from `service_catalogue_v2` and `CATEGORY_CONFIG`, and links SERVICE pages to `service_code`.  
   - If the seed script has been run and `service_catalogue_v2` is populated for ai_automation, market_research, compliance, document_pack, then category pages get services and service pages exist.  
   - If the seed was never run, or CMS pages were removed/unpublished, or the catalogue is missing entries, category pages show “No services” and individual service URLs can 404. So “what was there before” is **CMS + catalogue-driven content**; “empty” = missing or unpublished CMS pages and/or missing catalogue entries.

### 2.3 Category configuration (single source of truth)

- **Backend:** `backend/models/cms.py` → **CATEGORY_CONFIG**:
  - `ai-automation` → AI & Automation Services  
  - `market-research` → Market Research Services  
  - `compliance-audits` → Compliance & Audit Services  
  - `document-packs` → Landlord Document Packs  
- Each entry has `name`, `tagline`, `description`, `icon`, `display_order`, and **`service_catalogue_category`** (e.g. `ai_automation`, `market_research`, `compliance`, `document_pack`) used to map catalogue services to CMS category slugs in the seeder.

---

## 3. End-to-End Flow (All Four Services)

### 3.1 Marketing → Intake (same for all)

1. User visits **Services Hub** (`/services`) or **Category** (`/services/ai-automation`, etc.).
2. Clicks a **service** → **ServicePageCMS** (`/services/{categorySlug}/{serviceSlug}`). CTA is built by `build_cta_config` in `cms_service`:
   - **STANDALONE:** “Start Now” → `/order/intake?service={service_code}`
   - **CVP_ADDON:** “Add to CVP” → `/order/intake?service={service_code}&mode=addon`
   - **BOTH:** “Buy Standalone” + “Add to CVP”.
3. **UnifiedIntakeWizard** (`/order/intake` or `/order/intake/:draftId`):
   - Step 1: Select service (and for document packs: pack tier + document selection + add-ons).
   - Step 2: Client identity (name, email, phone, etc.).
   - Step 3: Service-specific fields (from intake schema per `service_code`).
   - Step 4: Review.
   - Step 5: Payment (Stripe Checkout).
4. Frontend calls **intake wizard API**:
   - Create draft → **POST /api/intake/draft**
   - Update draft (steps) → **PATCH /api/intake/draft/:draftRef**
   - Validate → **POST /api/intake/draft/:draftRef/validate**
   - Create checkout session → **POST /api/intake/draft/:draftRef/checkout**
5. User pays via Stripe; redirect to **/order/confirmation** (or success URL with session).

### 3.2 Backend: Draft → Order (same for all)

- **Stripe webhook:** `checkout.session.completed` for **order** context (metadata has `draft_id` / order ref, not CVP `client_id`).
- **Handler:** `_handle_order_payment` in `stripe_webhook_service.py`:
  - Converts **draft → order** via `convert_draft_to_order` (writes to `orders`).
  - Inserts normalized **payment** for revenue analytics.
  - **Then:** if `order.service_code` is in **Document Pack** codes → calls **DocumentPackWebhookHandler.handle_checkout_completed**; else no document-pack-specific step.

### 3.3 Post-payment: Document Packs vs others

**Document Packs (DOC_PACK_ESSENTIAL, DOC_PACK_PLUS, DOC_PACK_PRO):**

- **document_pack_webhook_handler.handle_checkout_completed**:
  - Updates order status to PAID, then creates **document_pack_items** from the order’s selected documents and intake data.
  - Sets order status to **QUEUED**.
  - Admin/document pack orchestrator then **generates** each item (e.g. via **document_pack_orchestrator**), review, and delivery.
- **Routes:** `backend/routes/document_packs.py` (admin) — e.g. create items, generate document, generate-all.
- **Services:** `document_pack_orchestrator.py`, `document_pack_webhook_handler.py`, `pack_registry.py`.

**AI & Automation, Market Research, Compliance Audits:**

- **No** document-pack webhook branch. Order is created and stored in `orders` with status PAID (and possibly transitioned to QUEUED elsewhere).
- **Order workflow** (order_workflow.py, workflow_automation_service, etc.): PAID → QUEUED → IN_PROGRESS → DRAFT_READY → INTERNAL_REVIEW → … → COMPLETED. Fulfilment is via **workflow automation** / report generation (e.g. AI workflow, market research report, compliance audit report) and optional **order_delivery_service**.
- **Prompts/orchestration:** `prompts.py`, `prompt_service.py`, `document_orchestrator.py` (e.g. Basic Market Research Report Generator, HMO Compliance Audit Report Generator, Document Pack Orchestrator) define how outputs are generated per service type.

So: **one** intake and **one** draft→order path for all; **two** fulfilment paths — (1) **Document Packs:** webhook + document_pack_orchestrator + admin document generation; (2) **Others:** order state machine + workflow automation / report generation.

---

## 4. Where Each Service Is Wired (File-Level)

| Layer            | AI & Automation     | Market Research      | Document Packs        | Compliance Audits     |
|------------------|----------------------|----------------------|------------------------|------------------------|
| **Marketing**    | Category slug `ai-automation`, CMS + CATEGORY_CONFIG | Same, `market-research` | Same, `document-packs` | Same, `compliance-audits` |
| **Catalogue**    | service_catalogue_v2, service_definitions_v2 (AI_WF_BLUEPRINT, AI_PROC_MAP, AI_TOOL_REPORT) | MR_BASIC, MR_ADV      | DOC_PACK_ESSENTIAL/PLUS/PRO, pack_registry | HMO_AUDIT, FULL_AUDIT, MOVE_CHECKLIST |
| **Intake API**   | intake_wizard.py list_available_services; intake_draft_service (pricing, schema) | Same                  | Same + pack add-ons, document selection | Same                  |
| **Intake schema**| intake_schema_registry (per service_code) | Same                  | Same + pack docs       | Same                  |
| **Checkout**     | Same Stripe checkout for all orders (intake_draft_service create_checkout_session) | Same                  | Same                   | Same                  |
| **Webhook**      | Order payment only; no doc-pack branch | Same                  | document_pack_webhook_handler after order create | Same                  |
| **Fulfilment**   | workflow_automation_service, order_workflow, prompts | Same                  | document_pack_orchestrator, document_packs routes | Same                  |
| **Support/other**| support_service (ai_automation), support_chatbot, SLA_CONFIG_BY_CATEGORY | Same (market_research) | Same (document_pack)   | compliance (audits)   |

---

## 5. Can the Marketing Pages and Their Intake Be Replaced?

### 5.1 Marketing pages (category + service)

- **Yes, they can be replaced.**  
  - Content is driven by **CMS** (`cms_pages`) and **CATEGORY_CONFIG** (cms.py).  
  - Replacing means either:  
  - **Option A:** Change the **frontend components** (e.g. replace CategoryPageCMS / ServicePageCMS with new pages or a new hub) while keeping the same API contracts (`/api/marketing/services/category/:slug`, `/api/marketing/services/:cat/:slug`), or  
  - **Option B:** Change the **API and data model** (e.g. new CMS structure or new marketing content source) and then update the frontend to consume it.  
- **Important:** If you remove or rename category slugs, update **CATEGORY_CONFIG**, any **redirects** (cms_redirects), and **nav/footer** links (PublicHeader, PublicFooter, ServicesHubPageCMS) so URLs stay consistent or redirect.

### 5.2 Intake (Unified Intake Wizard)

- **Shared intake:** All four service areas use the **same** **UnifiedIntakeWizard** and same **intake API** (draft create/update/validate/checkout).  
- **Replacing “the intake”** can mean:  
  - **Replace the UI only:** New wizard or flow that still calls the same backend (`/api/intake/draft`, etc.) → minimal backend change; only frontend and routing (e.g. what points to the new wizard).  
  - **Replace the flow entirely:** New backend endpoints and/or new checkout (e.g. different Stripe product), new draft/order model → larger change; then you must either migrate existing orders/drafts or keep the old path for legacy.  
- **Document Packs** are the only ones with **extra** post-payment logic (document_pack_items, orchestrator). Replacing “intake” for document packs only (e.g. a different pack builder) is possible as long as the **order** and **document_pack_webhook_handler** still get the data they need (service_code, selected docs, intake payload).  
- **Safe approach:** Replace marketing pages and/or intake **incrementally** (e.g. new route + new component, same API; or new API version alongside old) and keep existing order/draft/webhook behaviour until the new flow is proven.

### 5.3 Replacing a whole service area (e.g. “drop AI & Automation”)

- **Possible.** You would:  
  - Remove or hide from nav/hub the category (e.g. ai-automation).  
  - Stop listing that category’s services in the intake wizard (intake_wizard.py `list_available_services` and/or frontend filter).  
  - Optionally remove or hide from catalogue (service_catalogue_v2, service_definitions_v2) so no one can start a new draft for those codes.  
  - Leave existing **orders** and **order workflow** for that service_code in place (or add a “discontinued” path) so historical orders still show and, if needed, still run.  
- **Document Packs** are the most “special” due to the webhook and orchestrator; removing them implies not creating new document pack orders and eventually retiring the document_pack_webhook_handler and document_pack_orchestrator usage for new orders.

---

## 6. Summary Table

| Question | Answer |
|----------|--------|
| How are the four services structured? | Same marketing pattern (CMS category + service pages), same intake (UnifiedIntakeWizard + intake draft API), same Stripe order checkout. Document Packs add webhook + document_pack_orchestrator; others use generic order workflow + workflow/report generation. |
| End-to-end flow? | Marketing (hub → category → service) → CTA to `/order/intake?service=...` → Wizard (draft → steps → checkout) → Stripe → Webhook (draft→order; if doc pack, create items + QUEUED) → Fulfilment (orchestrator for packs; workflow/report for others). |
| Why do marketing pages look empty? | No or unpublished **SERVICE** CMS pages for that category, and/or no matching **service_catalogue_v2** entries. Category fallback exists from CATEGORY_CONFIG; service list and detail come from CMS + catalogue. |
| What was there before? | CMS-driven content; optional seed from `seed_cms_pages.py` using CATEGORY_CONFIG and service_catalogue_v2. If seeded and published, category and service pages are populated. |
| Can marketing pages be replaced? | Yes. Replace components and/or API; keep or migrate CATEGORY_CONFIG and nav/redirects. |
| Can intake be replaced? | Yes: UI-only replacement (same API) is low risk; full flow replacement needs new backend/checkout and care for existing orders/drafts. |
| Can a whole service (e.g. AI & Automation) be replaced or removed? | Yes. Hide from nav/catalogue and intake list; optionally retire fulfilment for new orders; keep or sunset order workflow for that code. |

---

## 7. Impact on Compliance Vault Pro (CVP) — Will Activating These Services Affect CVP?

**Short answer: No.** Activating the four services (making marketing pages and order intake live) is designed **not** to affect CVP subscription or provisioning.

**Why they are isolated:**

1. **Different Stripe checkout types**
   - **CVP:** Checkout session is created with `mode: "subscription"` and metadata `client_id`, `plan_code` (see `stripe_service.py`). Webhook branches to `_handle_subscription_checkout` → client billing, entitlements, **provisioning** (portal user, etc.).
   - **Four services (orders):** Checkout session is created with `mode: "payment"` and metadata `type: "order_intake"`, `draft_id`, `draft_ref`, `service_code` (see `intake_draft_service.py`). Webhook branches to `_handle_order_payment` → draft → order, then document-pack handler only if pack.

   In `stripe_webhook_service.py`, `_handle_checkout_completed` routes **only** on `session.mode` and `metadata.type`; the two paths do not share logic or DB writes for the same event.

2. **Different data**
   - CVP: `clients`, `portal_users`, `client_billing`, `provisioning_jobs`, etc.
   - Orders: `orders`, `intake_drafts`, `document_pack_items` (for packs). No CVP collections are written by the order flow.

3. **Different intake**
   - CVP: `IntakePage` at `/intake/start` → `POST /api/intake/submit`, `POST /api/intake/checkout`.
   - Orders: `UnifiedIntakeWizard` at `/order/intake` → `POST /api/intake/draft`, `PATCH /api/intake/draft/...`, `POST .../checkout`. Different URLs and endpoints.

So turning on the four services does not change how CVP signup, payment, or provisioning run.

**Safest recommendation**

1. **Do not change CVP code** when activating. Only enable/seed the **marketing and order intake** (e.g. run `seed_cms_pages.py`, ensure `/order/intake` and service CTAs are reachable). Leave `/intake/start`, intake submit/checkout, and the subscription webhook branch untouched.
2. **Test in staging first:** Run the CMS seed, place one CVP subscription signup and one order (e.g. document pack or market research). Confirm CVP still provisions (portal user, dashboard access) and the order appears in orders and (for packs) document pack flow.
3. **Optional safeguard:** Add or run a test that a `checkout.session.completed` with `mode: "subscription"` is handled by `_handle_subscription_checkout` and one with `mode: "payment"` and `metadata.type == "order_intake"` by `_handle_order_payment`, so future webhook changes don’t mix the two.

**Summary:** Activating AI & Automation, Market Research, Document Packs, and Compliance Audits does not affect Compliance Vault Pro functionality. Safest approach: activate without changing CVP code and verify both flows in staging.

---

## 8. Key File References

- **Marketing routes (public):** `backend/routes/marketing.py` — GET `/api/marketing/services/category/{category_slug}`, GET `/api/marketing/services/{category_slug}/{service_slug}`.  
- **CMS category/service logic:** `backend/services/cms_service.py` — `get_category_page`, `get_service_page`, `list_category_services`, `build_cta_config`.  
- **Category config:** `backend/models/cms.py` — `CATEGORY_CONFIG`.  
- **Frontend:** `CategoryPageCMS.js`, `ServicePageCMS.js`, `ServicesHubPageCMS.js`; nav/footer in `PublicHeader.js`, `PublicFooter.js`.  
- **Intake:** `frontend/src/pages/UnifiedIntakeWizard.js`; `backend/routes/intake_wizard.py`; `backend/services/intake_draft_service.py`, `intake_schema_registry.py`, `pack_registry.py`.  
- **Stripe order payment:** `backend/services/stripe_webhook_service.py` — `_handle_order_payment`; `document_pack_webhook_handler.handle_checkout_completed` for packs.  
- **Document pack fulfilment:** `backend/routes/document_packs.py`, `backend/services/document_pack_orchestrator.py`, `document_pack_webhook_handler.py`.  
- **Order workflow (non-pack):** `backend/services/order_workflow.py`, `workflow_automation_service.py`; prompts in `prompts.py`, `prompt_service.py`.
- **CVP vs order webhook branching:** `backend/services/stripe_webhook_service.py` — `_handle_checkout_completed` (mode + metadata); CVP checkout: `backend/services/stripe_service.py` (mode subscription); order checkout: `backend/services/intake_draft_service.py` (mode payment, type order_intake).
