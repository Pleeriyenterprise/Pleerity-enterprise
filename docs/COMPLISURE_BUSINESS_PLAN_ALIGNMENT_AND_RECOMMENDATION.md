# CompliSure Business Plan — Alignment, Integration & Implementation Recommendation

**Document purpose:** Compare the CompliSure UK Business Plan (PDF) with the current Compliance Vault Pro (CVP) build; assess alignment, integration feasibility, and provide a concrete enhancement/implementation plan without breaking existing flows.

**Status:** Analysis only — **DO NOT IMPLEMENT** until approved.

---

## 1. Executive Summary

| Question | Answer |
|----------|--------|
| **Does CompliSure align with the current build?** | **Partially.** Same high-level pattern (intake → payment → provisioning → portal) and tech stack (React, FastAPI, MongoDB, Stripe, Postmark). Core **domain and data model differ**: CVP is **property/landlord compliance**; CompliSure is **general SME compliance** (GDPR, employment, H&S, sector-specific). |
| **Can it be integrated?** | **Yes**, as a **separate product line** on the same platform (shared auth, billing, admin, hosting). **Not** as a drop-in replacement or a simple “add more intake fields” to the current wizard. |
| **Will it work without major change?** | **No.** Delivering the full CompliSure vision (rule engine, facts → obligations, regulation-aware document generation, complexity-based pricing) requires **new backend domains** (Organisation, IntakeSession, Answer, Fact, Rule, Obligation) and a **new intake flow** (7 steps, question bank, conditional logic). The current property-centric intake and requirement catalog cannot be stretched to cover SME policies, handbooks, DPIA, RoPA, etc. |
| **Recommendation** | **Option A (recommended):** Implement CompliSure as a **parallel product** with its own routes, intake, and document pipeline. Shared: Stripe, portal_users, admin shell, hosting. **Option B:** Add a limited “business context” layer to CVP for pricing/positioning only (no full CompliSure doc engine). **Do not** merge both products into one intake or pivot CVP into CompliSure (would break existing clients). |

---

## 2. Side-by-Side Comparison

### 2.1 Business & Vertical

| Dimension | CompliSure (PDF) | CVP (current build) |
|-----------|------------------|----------------------|
| **Target** | UK SMEs (care, recruitment, childcare, property mgmt, finance, construction) | UK landlords, letting agents, property portfolios |
| **Primary entity** | **Organisation** (org_id); optional multi-entity/franchise | **Client** + **Properties** (property-centric) |
| **Compliance focus** | GDPR, employment, H&S, sector regulators (ICO, CQC, Ofsted, FCA, HSE) | Property compliance (gas, EICR, EPC, licences, tenancy/deposit) |
| **Outputs** | Policies, procedures, staff handbooks, risk assessments, registers, DPIA, RoPA | Property requirements, certificates, evidence; optional document packs (tenancy, letters) |

### 2.2 Intake Flow

| Dimension | CompliSure (PDF) | CVP (current build) |
|-----------|------------------|----------------------|
| **Steps** | 7: Business identity → Jurisdiction & regulators → Workforce & operations → Data & privacy (GDPR) → Industry-specific (conditional) → Review (coverage + doc list) → Plan & pricing | 5: Your Details → Select Plan → Properties → Preferences → Review |
| **Step 1** | Legal name, trading name, company type (sole trader, limited, partnership, charity/CIC) | Full name, email, phone, company name, client type, preferred contact, consents |
| **Step 2** | Primary jurisdiction (England/Scotland/Wales/Multiple), primary regulator (ICO, CQC, Ofsted, FCA, HSE, Other) | N/A (no jurisdiction/regulator step) |
| **Step 3** | Worker count band, worker types (employees, contractors, agency, volunteers), digital staff records; conditional: written contracts if employees | N/A (no workforce step) |
| **Step 4** | Collect personal data (Y/N); types (names, financial, health, criminal, children); storage location; third-party sharing; third-party types | N/A (no GDPR step) |
| **Step 5** | Primary industry (care, recruitment, childcare, property mgmt, finance, construction, other); **conditional industry module** (e.g. care: CQC, regulated activities, vulnerable adults, medication) | Properties: address, type, bedrooms, occupancy, HMO, licence, certs (gas, EICR, EPC), reminders |
| **Step 6** | **Internal only:** Risk & complexity scoring (not visible to user) | Preferences: document submission method, optional uploads |
| **Step 7** | Review (doc list + gaps) → Plan & pricing (base + adders + cap, add-ons) | Review (details, plan, properties, preferences) → Proceed to payment |
| **Pricing logic** | Complexity-based: base £99 + adders (staff band, special category data, regulated, multi-jurisdiction, children/vulnerable); caps (£49 micro, £149 SME, £299+ regulated) | Plan-based: Solo (2 props) / Portfolio (10) / Pro (25); fixed monthly + onboarding by plan |
| **Conditional logic** | Rich: show_when by question_id/op/value; multi-select “contains”; industry modules only if industry selected | Plan cap on property count; no jurisdiction/regulator/workforce/GDPR branching |

### 2.3 Data Model & Rule Engine

| Dimension | CompliSure (PDF) | CVP (current build) |
|-----------|------------------|----------------------|
| **Intake storage** | IntakeSession, Answer (question_id, value, answered_at); normalised **Facts** (typed, derived from answers) | Client + Properties created at submit; intake form data flattened onto client/properties |
| **Rules** | Versioned Rule (condition on facts → actions: require_document, add_obligation, require_task, risk_delta, pricing_add); scope (jurisdiction, industry); ruleset_version, facts_snapshot_hash | **Requirement catalog** (property attributes → applicable requirement keys); **compliance scoring** (evidence-based score); no generic fact/rule/obligation engine |
| **Obligations** | Obligation (obligation_key, category, title, severity, status, evidence_required, created_from_rule) | Requirements (per property, from catalog); no first-class “obligation” entity |
| **Documents** | DocumentDefinition (document_key, required_facts, template_id, jurisdictions); DocumentInstance (versioned, facts_snapshot_hash, ruleset_version, storage URLs); **Clause** library (variants by jurisdiction, requires_facts) | Requirement ↔ evidence (documents); document packs (order-based) with DocumentDefinition in service_catalogue / document_pack_orchestrator; no clause library or fact-driven doc gen |
| **Alerts** | Alert (regulatory update → impacted rules/docs → recommended_actions: regenerate_document); customer “apply update” flow | Reminders (expiry/overdue); digest emails; **no** “regulatory update → impacted docs → regenerate” pipeline |

### 2.4 Post-Onboarding & Admin

| Dimension | CompliSure (PDF) | CVP (current build) |
|-----------|------------------|----------------------|
| **Customer dashboard** | Compliance %, next actions, alerts (regulatory), document list (view/download/request sign-off), sign-offs, audit pack export | Score, trend, portfolio, properties, requirements, documents, calendar, reports, audit & change history, orders |
| **Pricing display** | Base price + line-item adders + cap (“Why this price”) | Plan name, property cap, monthly/onboarding price |
| **Admin** | Ops Admin + Compliance Admin; Intake Sessions (resume, diff); Rules (list, edit, test, publish); Templates & Clauses; Alerts & regulatory updates; Human review queue; Partners; Billing with same adder reasons | Single admin: clients, properties, documents, orders, observability (health, automation, incidents), audit logs, leads, analytics, CMS, prompts, support |

---

## 3. Gap Summary

### 3.1 CompliSure Has; CVP Does Not

- **Organisation-centric model** (org_id, no property as primary entity for SME track).
- **7-step intake** with Business identity, Jurisdiction & regulators, Workforce, GDPR, Industry (+ conditional modules).
- **Question bank** (question_id, step, type, tooltip, show_when, maps_to_facts) and **Answer** storage per session.
- **Facts** (derived from answers; typed key/value).
- **Rule engine** (conditions on facts → require_document, add_obligation, risk_delta, pricing_add); ruleset versioning; facts_snapshot_hash on outputs.
- **Obligations** as first-class entities (from rules).
- **DocumentDefinitions** keyed by document_key with required_facts; **Clause** library with jurisdiction variants and fact dependencies.
- **DocumentInstance** with version, facts_snapshot_hash, ruleset_version (audit trail for generated docs).
- **Complexity-based pricing** (base + adders from facts + caps); “Why this price” in UI.
- **Regulatory alerts** (impacted rules/docs, “apply update” / regenerate).
- **Sign-offs** and **audit pack** (version history, change logs, sign-off records) in the CompliSure sense (policy sign-off, not just score history).
- **Two admin layers** (Ops vs Compliance) and **Rule Engine Console** (edit, test, publish rules).

### 3.2 CVP Has; CompliSure Spec Does Not Emphasise

- **Property-centric** model and **requirement catalog** (gas, EICR, EPC, licence, tenancy, deposit).
- **Compliance score** (property/portfolio) and **score ledger** (Audit & Change History).
- **Intake uploads** (staged, then migrated to vault after provisioning).
- **Order workflow** (draft → … → FINALISING → delivery email → COMPLETED) and **order delivery** job.
- **Risk-check funnel** (pre-intake: property count, HMO → report → activate → intake with lead_id).
- **Observability** (job runs, incidents, SLA watchdog).

### 3.3 Shared (Reusable)

- **Auth & users:** portal_users, set-password, login.
- **Payments:** Stripe (checkout, webhooks, subscription status).
- **Email:** Postmark, templates, message_logs.
- **Hosting:** Vercel (frontend), Render (backend), MongoDB Atlas.
- **Admin shell:** layout, nav, auth; can add CompliSure-specific sections.
- **Provisioning pattern:** post-payment job → create portal user → invite email (CompliSure would provision “org” + optional initial doc gen instead of properties + requirements).

---

## 4. Can CompliSure Be Integrated?

### 4.1 As a Parallel Product (Recommended)

**Yes.** Treat CompliSure as a **second product line** on the same platform:

- **Routes:** e.g. `/complisure`, `/complisure/start`, `/complisure/dashboard`, or under a product switcher (Landlord Compliance vs SME Compliance).
- **Intake:** New 7-step wizard (new frontend + new API: e.g. `POST /api/complisure/intake/answer`, `POST /api/complisure/intake/submit`). Store **IntakeSession**, **Answer**; derive **Facts**; run **Rule** evaluation.
- **Data:** New collections (e.g. `organisations`, `complisure_intake_sessions`, `answers`, `facts`, `rules`, `obligations`, `document_definitions`, `document_instances`, `alerts`) or namespaced (e.g. `org_*`). **No** change to existing `clients`, `properties`, `requirements`, `score_ledger_events`.
- **Provisioning:** After Stripe success for a “CompliSure” product, run **CompliSure provisioning** (create org, create portal user, optionally generate initial document set), not CVP provisioning (properties, requirements, recalc queue).
- **Billing:** Same Stripe; product/price differentiation via Stripe product/price IDs (e.g. CompliSure plans vs CVP plans).
- **Admin:** Extend nav with “CompliSure” section: Organisations, Intake Sessions, Rules, Documents, Alerts, Human Review Queue; keep existing CVP clients/orders/observability.

**Result:** Both products coexist; no breaking change to CVP flows.

### 4.2 By Extending Current Intake Only

**Partial.** You could add a “business context” step or extra fields to the **existing** intake (e.g. company type, jurisdiction, regulator, worker count, industry) and use them for:

- **Pricing:** Map to a “complexity” band and show a different price or plan (e.g. upsell to a “Regulated” tier).
- **Display:** Show different dashboard copy or badges.

You would **not** get:

- CompliSure’s document set (policies, handbooks, DPIA, RoPA) or clause library.
- Rule engine, obligations, or regulatory alerts.
- Full “Why this price” adder breakdown.

So this is an **enhancement for positioning/pricing only**, not full CompliSure.

### 4.3 By Replacing CVP with CompliSure

**No.** Replacing the current intake and flow with CompliSure’s would:

- Break **existing** landlord clients (no properties-first model, no requirement catalog as-is).
- Require migrating or retiring property compliance, score ledger, and order delivery.

**Not recommended.**

---

## 5. Enhancement / Implementation Plan (No Breaking Changes)

Assumption: **Option A — CompliSure as a parallel product.**

### Phase 1 — Foundation (no change to CVP intake or provisioning)

1. **Data model (backend)**  
   - Add collections: `organisations`, `complisure_intake_sessions`, `answers`, `facts` (or equivalent).  
   - Org: org_id, legal_name, trading_name, company_type, jurisdiction_primary, jurisdictions[], regulator, industry, worker_count_band, worker_types[], etc. (from CompliSure spec).  
   - No changes to `clients` / `properties` / `requirements`.

2. **Question bank & intake API**  
   - Store CompliSure question set (JSON or DB) per PDF Section 3 (question_id, step, label, type, options, tooltip, show_when, maps_to_facts).  
   - API: create session, save answer(s), get session state; **submit** → create Organisation + finalise session (no entitlement until payment).  
   - Conditional logic: evaluate `show_when` in API so frontend only receives questions that apply.

3. **Frontend: CompliSure intake wizard**  
   - New route (e.g. `/complisure/start`).  
   - 7 steps as per wireframes (Business identity, Jurisdiction, Workforce, GDPR, Industry, Review, Plan & pricing).  
   - Call new API; no changes to existing IntakePage or UnifiedIntakeWizard.

4. **Checkout & product differentiation**  
   - Stripe: separate product/price IDs for CompliSure (e.g. Micro £49, SME £99–£149, Regulated £299).  
   - Create-checkout endpoint for CompliSure: pass `product_type=complisure` (or similar) and org_id/session_id; webhook creates **CompliSure provisioning job** (not CVP).

### Phase 2 — Rules, facts & pricing

5. **Fact derivation**  
   - On answer save (or submit): derive **Facts** from answers (e.g. collects_personal_data, processes_special_category_data, staff_band, regulated_industry, multi_jurisdiction, children_or_vulnerable_groups).  
   - Store in `facts` (or embedded in org/session) with derived_from references.

6. **Rule engine v1**  
   - Rule schema: condition (fact-based, operators ==, in, etc.), actions (require_document, add_obligation, risk_delta, pricing_add).  
   - Scope: jurisdiction, industry.  
   - Evaluate rules after fact update; output: required document keys, obligations, complexity score, pricing adders.  
   - Store ruleset_version and list of rules fired (for audit).

7. **Pricing engine**  
   - Config: tier_base (micro 49, sme 99, regulated 299), sme_cap 149, adders (from PDF).  
   - Input: facts. Output: recommended tier, line items (base + adders), cap, “Why this price” copy.  
   - Expose in API for Step 7 and for Stripe price selection.

### Phase 3 — Documents & provisioning

8. **Document definitions & clause library**  
   - DocumentDefinition: document_key, required_facts, template_id, category, jurisdictions.  
   - Clause: clause_key, variants (default, jurisdiction), requires_facts.  
   - Start with 5–10 doc types for one niche (e.g. care: privacy notice, retention, RoPA, DPIA if needed, staff handbook, H&S policy).

9. **Document generation pipeline**  
   - Given org + facts + rules: determine required documents; for each, select template + clauses; generate DocumentInstance (version, facts_snapshot_hash, ruleset_version); store (e.g. HTML/PDF/DOCX URLs or file refs).  
   - No change to CVP document vault or requirement evidence flow.

10. **CompliSure provisioning**  
    - On Stripe success (CompliSure product): create Organisation (if not already), create portal_user linked to org (or client_id representing “CompliSure org”), set onboarding_status = PROVISIONED; optionally run doc gen and create initial DocumentInstances; send set-password email.  
    - Do **not** run CVP provisioning (no properties, no requirement catalog).

### Phase 4 — Alerts & customer experience

11. **Alerts (manual in MVP)**  
    - Create “regulatory update” (admin): attach impacted rule(s) and doc(s).  
    - Run impact: which orgs match conditions → create **Alert** per org with recommended_actions (e.g. regenerate_document:PRIVACY_NOTICE).  
    - Customer dashboard: list alerts; “Apply update” → trigger regeneration of listed docs.

12. **Post-onboarding CompliSure dashboard**  
    - Dashboard: compliance summary, next actions (obligations, sign-offs), alerts, document list (view/download, request sign-off).  
    - Audit pack: export (PDF/ZIP) with latest docs, version history, change logs, sign-offs.  
    - Can reuse CVP portal layout with a “product” or “tenant” switch (e.g. CompliSure org vs CVP client).

### Phase 5 — Admin & ops

13. **Admin: CompliSure section**  
    - Organisations (list + detail: timeline, facts, rules fired, documents, alerts, sign-offs, billing).  
    - Intake Sessions (list + detail, resume link, answers, computed facts, pricing explanation).  
    - Rules (list, scope, version; editor + test harness; publish → ruleset_version).  
    - Documents (definitions, instances; filters by doc type, industry, “needs sign-off”).  
    - Alerts & regulatory updates (create update, impact simulation, publish → customer alerts).  
    - Human review queue (if upsell: request review → queue → publish “Expert Reviewed” version).

14. **Event model**  
    - Emit events: intake.answer_saved, facts.updated, rules.evaluated, document.generated, document.regenerated, alert.created, alert.applied, signoff.requested, signoff.completed, auditpack.exported.  
    - Admin timeline = ordered list of these events (same pattern as CVP audit/timeline).

---

## 6. What to Reuse vs Build New

| Component | Reuse | Build new |
|-----------|--------|-----------|
| Auth (login, set-password, portal_users) | ✅ | — |
| Stripe (checkout, webhooks, customer, subscription) | ✅ | CompliSure product/price IDs and webhook branch for “CompliSure” |
| Postmark, message_logs, templates | ✅ | CompliSure-specific templates (e.g. welcome, alert) |
| Frontend app (React, routing) | ✅ | New routes and CompliSure wizard components |
| Admin layout & auth | ✅ | New nav section and CompliSure pages |
| Intake “submit → create entity” pattern | ✅ (concept) | New entity (Organisation), new API, new collections |
| Provisioning “post-payment job → invite” | ✅ (pattern) | New job type: CompliSure provisioning (org + doc gen + invite) |
| Requirement catalog, compliance scoring, score ledger | — | Not used for CompliSure |
| Property, client (CVP), documents (vault for evidence) | — | Not used for CompliSure (separate org + document_instances) |
| Rule engine, facts, obligations, DocumentDefinition/Clause | — | New (CompliSure only) |
| Pricing (plan_registry) | ✅ (for CVP) | New pricing engine for CompliSure (facts → adders + caps) |

---

## 7. If You Only Enhance CVP (Option B)

If you do **not** want a full second product and only want “CompliSure-lite” inside CVP:

- Add to **existing** intake (or a single extra step): company type, primary jurisdiction, primary regulator, worker count band, industry (optional).  
- Store on **client** (e.g. `client.company_type`, `client.jurisdiction_primary`, …).  
- **Pricing:** Use these to select plan or show an “upgrade” (e.g. Regulated tier) or to display a different price before checkout; keep Stripe plan structure as today (Solo/Portfolio/Pro) or add one more plan.  
- **No** new rule engine, no obligations, no policy/handbook/DPIA/RoPA generation, no regulatory alerts.  
- **Risk:** Two different mental models (property vs org) on same client record; limited value compared to full CompliSure.

**Recommendation:** Only do Option B if the goal is light positioning/upsell. For the full CompliSure vision, Option A is required.

---

## 8. Hosting (Unchanged)

- **Frontend:** Vercel; add CompliSure routes and env (same `REACT_APP_BACKEND_URL`).  
- **Backend:** Render; same API service; new routes under e.g. `/api/complisure/*`.  
- **Database:** MongoDB Atlas; new collections as above.  
- **Stripe / Postmark:** Same; add CompliSure products/prices and templates.

No new hosting; no change to existing CVP hosting.

---

## 9. Conclusion

- **Alignment:** CompliSure and CVP share the same **funnel pattern** (intake → payment → provisioning → portal) and **tech stack**, but **different domains** (SME compliance vs property compliance) and **different data and logic** (org/facts/rules/obligations vs client/properties/requirements/score).  
- **Integration:** Feasible as a **parallel product** (Option A); not feasible as a “replace” or “merge into one intake” without breaking CVP.  
- **Recommendation:** Implement CompliSure as a **separate product line** (Phases 1–5). Do **not** merge both intakes or replace CVP. If only light alignment is needed, add minimal “business context” to CVP (Option B) and accept that full CompliSure (rules, docs, alerts) will not exist.  
- **Breaking changes:** None to existing CVP intake, provisioning, properties, requirements, score ledger, or order delivery, provided CompliSure is implemented in its own routes, collections, and provisioning path.

---

*Reference: Business Plan CompliSure PDF (intake fields, wireframes, rule engine schema, question bank, pricing, admin IA). Current build: docs/BUSINESS_FLOW_AND_USER_JOURNEY_REPORT.md, backend routes (intake, provisioning), plan_registry, requirement_catalog, compliance_scoring_service.*
