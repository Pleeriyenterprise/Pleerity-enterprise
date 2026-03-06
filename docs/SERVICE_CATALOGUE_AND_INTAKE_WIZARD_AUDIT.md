# Service Catalogue & Unified Intake Wizard — Codebase Audit

**Purpose:** Check the codebase against the two task sets (1) Build Service Catalogue for the four services, (2) Implement unified Intake Wizard. Identify what is implemented, what is missing, and any conflicting instructions. **Do not implement blindly.**

**Scope:** Four services only — AI automation, Market research, Compliance services, Document packs. CVP remains out of scope.

---

## Part 1 — Service Catalogue

### 1.1 Task requirements (summary)

| Requirement | Detail |
|-------------|--------|
| Collection | `services` authoritative, admin-editable |
| Fields | service_code, name, category, description_preview, description_full (optional), pricing (one_time/subscription), base_price, currency, add_ons, intake_schema_id, requires_review, document_types[], is_active, sort_order, seo_slug |
| API | GET /api/services (public), GET /api/services/:service_code, POST/PUT/PATCH admin (activate/deactivate) |
| Frontend | Services listing, Learn More → /services/[slug], Get Started → /order/intake?service=SERVICE_CODE |
| Canonical | service_code used everywhere |

### 1.2 What exists today

| Item | Status | Implementation |
|------|--------|-----------------|
| **Authoritative collection** | ✅ Implemented | `service_catalogue_v2` (name differs from task’s “services”) |
| **Admin-editable** | ✅ Implemented | Admin API: POST, PUT, activate, deactivate at `/api/admin/services/v2/` |
| **service_code canonical** | ✅ Implemented | Unique index, used in orders, drafts, checkout, prompts |
| **Fields vs task** | ⚠️ Different names, same intent | See mapping below |
| **Public API** | ⚠️ Different path | `GET /api/public/v2/services`, `GET /api/public/v2/services/{service_code}` (not `/api/services`) |
| **Admin API** | ⚠️ Method difference | Activate/deactivate are **POST** (not PATCH) at `/api/admin/services/v2/{service_code}/activate` and `.../deactivate` |
| **Frontend listing** | ✅ Implemented | ServicesHubPageCMS, ServicesCataloguePage, CategoryPageCMS, ServicePageCMS |
| **Learn More** | ✅ Implemented | `/services/:categorySlug/:serviceSlug` (e.g. /services/ai-automation/workflow-blueprint) |
| **Get Started** | ✅ Implemented | Links to `/order/intake?service=SERVICE_CODE` (e.g. ServiceDetailPage, ServicesCataloguePage, cms_service build_cta_config) |

**Field mapping (task → current)**

| Task field | Current field / note |
|------------|----------------------|
| service_code | `service_code` ✅ |
| name | `service_name` ✅ |
| category | `category` (enum value) ✅ |
| description_preview | `description` or `website_preview` ✅ |
| description_full | `long_description` ✅ |
| pricing (one_time/subscription) | `pricing_model` (e.g. one_time, subscription_monthly) ✅ |
| base_price, currency | `base_price` (pence), `price_currency` ✅ |
| add_ons | `fast_track_*`, `printed_copy_*`, `pricing_variants` ✅ |
| intake_schema_id | No single ID; intake defined by `intake_fields[]` (full schema per service) ⚠️ |
| requires_review | `review_required` ✅ |
| document_types[] | `documents_generated` (template list) ✅ |
| is_active | `active` ✅ |
| sort_order | `display_order` ✅ |
| seo_slug | `learn_more_slug` ✅ |

### 1.3 Gaps and conflicts (Service Catalogue)

- **API path:** Task expects `GET /api/services` and `GET /api/services/:service_code`. Codebase uses `GET /api/public/v2/services` and `GET /api/public/v2/services/{service_code}`. Changing to `/api/services` would break existing frontend and any external callers. **Recommendation:** Keep current paths; document the mapping. If a single “public” path is required, add thin aliases (e.g. `GET /api/services` → proxy to public v2) without removing v2.
- **Activate/deactivate:** Task says PATCH; codebase uses POST. RESTfully PATCH is acceptable for “toggle state”; POST is also valid for action endpoints. **Recommendation:** Keep POST unless you need strict REST; no change required for behaviour.
- **Collection name:** Task says “services”; codebase uses `service_catalogue_v2`. Renaming the collection would require a data migration and updates everywhere. **Recommendation:** Keep `service_catalogue_v2`; treat “services” as the logical name in docs only.
- **intake_schema_id:** Task asks for a single ID; codebase embeds `intake_fields[]` per service. Adding an optional `intake_schema_id` for reference (e.g. to a shared schema registry) is possible without breaking existing behaviour.

**Conclusion (Service Catalogue):** The catalogue is implemented and authoritative; field coverage matches the task with different names. Only optional improvements: path aliases and/or optional `intake_schema_id`. No breaking changes recommended.

---

## Part 2 — Unified Intake Wizard

### 2.1 Task requirements (summary)

| Requirement | Detail |
|-------------|--------|
| Stack | **Next.js** |
| URL | /order/intake?service=SERVICE_CODE |
| Behaviour | Load service from backend; universal + service-specific fields; helper text; optional file uploads |
| Draft | Save as `intake_submissions` with status `DRAFT_INTAKE`; draft_ref e.g. **DRAFT-YYYYMMDD-XXXX** |
| No payment on this step | Payment on separate step |
| Save and resume | User can resume via link containing draft_ref token |
| Validation | Per-field via **Zod** (universal + service-specific) |
| After submit | Route to **checkout page** `/order/checkout?draft=DRAFT_REF` |

### 2.2 What exists today

| Item | Status | Implementation |
|------|--------|-----------------|
| **Framework** | ❌ Conflict | App is **React (CRA)**, not Next.js. Task explicitly asks for Next.js. |
| **URL** | ✅ Implemented | `/order/intake` and `?service=SERVICE_CODE`; service pre-selected from URL |
| **Load service from backend** | ✅ Implemented | Services from `/api/intake/services`; schema from `/api/intake/schema/{service_code}` (intake_wizard + service_catalogue_v2) |
| **Universal + service-specific fields** | ✅ Implemented | Client identity step + service-specific step; schema-driven (intake_schema_registry, service intake_fields) |
| **Helper text** | ⚠️ Partial | Schema supports `help_text`; UI may not show it everywhere |
| **Optional file uploads** | ⚠️ Backend only | `SERVICES_WITH_UPLOADS`, intake_uploads; frontend upload UX may be service-specific or partial |
| **Draft persistence** | ✅ Implemented | **intake_drafts** (task says “intake_submissions”); status DRAFT, READY_FOR_PAYMENT, CONVERTED, ABANDONED (task says “DRAFT_INTAKE”) |
| **draft_ref format** | ⚠️ Different | Current: **INT-YYYYMMDD-XXXX** (e.g. INT-20250220-0001). Task: **DRAFT-YYYYMMDD-XXXX**. |
| **No payment on intake step** | ✅ Implemented | Payment is step 5: “Proceed to Payment” creates Stripe session and redirects to Stripe (no payment on intake form itself). |
| **Save and resume via link** | ⚠️ Partial | Backend: `GET /api/intake/draft/by-ref/{draft_ref}`. Frontend: route `/order/intake/:draftId` exists but wizard does **not** read `draftId` from URL and does **not** call the by-ref API to load draft; resume is via **localStorage** only (same device/browser). Shareable “resume link” (e.g. /order/intake?draft=INT-... or /order/intake/INT-...) is not wired. |
| **Validation** | ⚠️ Different | Backend: Pydantic + intake_schema_registry. Frontend: form state + ad-hoc validation. Task asks for **Zod** (typically in TS/Next). |
| **After submit → checkout page** | ❌ Different flow | Task: “route to checkout page /order/checkout?draft=DRAFT_REF”. Current: from Review step user clicks “Proceed to Payment” → `createCheckoutSession(draft.draft_ref)` → redirect to **Stripe** (no separate /order/checkout page). There is no `/order/checkout` route. |

### 2.3 Gaps and conflicts (Intake Wizard)

1. **Next.js vs React**  
   Task: “Implement unified Intake Wizard **in Next.js**”. Codebase: **React (CRA)**. Implementing the wizard in Next.js would mean a separate app or a full migration. **Recommendation:** Implement behaviour in the **existing React app** (UnifiedIntakeWizard.js) so the product stays single-stack. Treat “Next.js” as a spec mismatch; do not add a Next.js app for this flow unless you explicitly decide to split or migrate.

2. **intake_submissions vs intake_drafts**  
   Task: “saves draft intake as **intake_submissions** with status **DRAFT_INTAKE**”. Codebase: **intake_drafts**, status **DRAFT** (and READY_FOR_PAYMENT, etc.). Renaming to intake_submissions and adding a status “DRAFT_INTAKE” would require migration and broad changes. **Recommendation:** Keep `intake_drafts` and existing statuses; document “intake_submissions” as the logical name if needed. Optionally add a synonym status DRAFT_INTAKE = DRAFT for clarity only if something else relies on that label.

3. **DRAFT- vs INT- prefix**  
   Task: draft_ref “e.g. **DRAFT-YYYYMMDD-XXXX**”. Codebase: **INT-YYYYMMDD-XXXX**. Changing prefix would affect existing drafts, orders, and references (Stripe metadata, emails). **Recommendation:** Keep **INT-**; document that “draft_ref” in the task maps to the existing INT- format. Do not change to DRAFT- without a migration and product decision.

4. **Resume via shareable link**  
   Task: “user must be able to save and resume **via link containing draft_ref token**”. Current: resume only via localStorage (no backend load by draft_ref in the wizard). Backend already supports `GET /api/intake/draft/by-ref/{draft_ref}`. **Recommendation:** Implement resume by link in the existing React wizard: e.g. support `?draft=INT-...` or path `/order/intake/INT-...`, read draft_ref from URL, call GET by-ref, and prefill/advance steps. No collection or ref format change needed.

5. **Zod validation**  
   Task: “validation per field via **Zod** schemas”. Codebase: no Zod; backend Pydantic, frontend plain JS. Introducing Zod in React would mean adding Zod and wiring it to the same fields. **Recommendation:** Either (a) add Zod (and optionally @hookform/resolvers/zod) in the existing React app for intake forms only, or (b) keep current validation and document that “Zod” in the spec is satisfied by “structured validation” (backend Pydantic + frontend rules). Prefer (a) only if you want a single, shareable schema (e.g. for future TS or Next).

6. **Checkout page /order/checkout?draft=DRAFT_REF**  
   Task: “After submit: route to **checkout page** /order/checkout?draft=DRAFT_REF”. Current: no checkout page; “Proceed to Payment” creates a Stripe session and redirects to Stripe. **Recommendation:** Two options.  
   - **Option A (minimal):** Add a dedicated **checkout page** at `/order/checkout` that accepts `?draft=INT-...`, loads draft (by-ref), shows summary and a “Pay now” button that calls createCheckoutSession and redirects to Stripe. Intake wizard then “submits” to “Review” and from Review navigates to `/order/checkout?draft=<draft_ref>` instead of calling Stripe immediately.  
   - **Option B (current):** Keep “Proceed to Payment” → Stripe directly; document that “checkout” is the Stripe Checkout session, not an in-app page.  
   Choose A if you need a clear “submit intake → then checkout” separation and a shareable checkout link; otherwise B is sufficient.

---

## Part 3 — Summary and safest approach

### Service catalogue

- **Implemented:** Authoritative, admin-editable catalogue (`service_catalogue_v2`); service_code canonical; public and admin APIs; frontend listing, Learn More, Get Started with `/order/intake?service=SERVICE_CODE`.
- **Not done / optional:** Exact API path `/api/services` (aliases only if needed); PATCH for activate/deactivate (optional); optional `intake_schema_id`.
- **Do not:** Rename collection to `services` or change field names without a migration and product decision.

### Intake wizard

- **Implemented:** URL with service param; load service and schema from backend; universal + service-specific steps; draft in DB (intake_drafts, INT- ref); no payment on intake; backend GET draft by-ref.
- **Missing or different:**  
  - Resume via **shareable link** (frontend not using draft_ref from URL).  
  - **Zod** per-field validation (optional in current stack).  
  - **/order/checkout** page and “after submit → checkout” flow (optional; current flow goes straight to Stripe).
- **Conflicts:**  
  - **Next.js:** Keep implementation in **React** unless you decide to introduce Next.js.  
  - **intake_submissions / DRAFT_INTAKE / DRAFT-:** Keep **intake_drafts**, current statuses, and **INT-** ref; no change unless you explicitly migrate.

### Recommended next steps (no blind implementation)

1. **Service catalogue:** No breaking changes. Optionally add path alias `GET /api/services` → current list/detail if you need that contract.
2. **Intake wizard (React):**  
   - Add **resume by link:** support `?draft=<draft_ref>` or path param, call `GET /api/intake/draft/by-ref/{draft_ref}`, prefill and set step.  
   - Optionally: add `/order/checkout?draft=...` page that shows summary and “Pay” → Stripe; and from Review step navigate to that page instead of calling Stripe directly.  
   - Optionally: introduce Zod for intake form validation in React.
3. **Do not:** Switch to Next.js for this wizard, rename collection to intake_submissions, or change draft_ref prefix to DRAFT- without a clear migration plan.

---

## Reference — key files

| Area | Files |
|------|--------|
| Service catalogue (backend) | `backend/services/service_catalogue_v2.py`, `service_definitions_v2.py` |
| Public services API | `backend/routes/public_services_v2.py` |
| Admin services API | `backend/routes/admin_services_v2.py` |
| Intake API | `backend/routes/intake_wizard.py` |
| Draft service | `backend/services/intake_draft_service.py` |
| Intake schema | `backend/services/intake_schema_registry.py` |
| Frontend wizard | `frontend/src/pages/UnifiedIntakeWizard.js` |
| Frontend routes | `frontend/src/App.js` |
| Service pages | `frontend/src/pages/public/ServiceDetailPage.js`, ServicePageCMS.js, ServicesCataloguePage.js, CategoryPageCMS.js |
