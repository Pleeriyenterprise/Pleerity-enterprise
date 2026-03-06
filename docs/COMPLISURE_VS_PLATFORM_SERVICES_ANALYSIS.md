# CompliSure vs Platform Services — Alignment, Integration & Recommendation

**Purpose:** Compare CompliSure (SME compliance product from the Business Plan PDF) with the platform’s four service areas — **Automation services**, **Market research**, **Compliance services**, and **Document pack** — and recommend whether to replace, add alongside, or replace totally. **Analysis only — DO NOT IMPLEMENT** until approved.

**References:**  
- Existing: `docs/COMPLISURE_BUSINESS_PLAN_ALIGNMENT_AND_RECOMMENDATION.md` (CompliSure vs CVP).  
- Platform services: `docs/SERVICES_AI_MARKETRESEARCH_DOCPACKS_AUDIT.md`, `backend/services/service_definitions_v2.py`, `service_catalogue_v2.py`, `intake_draft_service.py`, `stripe_webhook_service.py`.

---

## 1. What the Platform’s Four Services Are (Codebase)

| Service area | Catalogue category | Examples (service_code) | What it is | Fulfilment |
|--------------|-------------------|--------------------------|------------|------------|
| **Automation services** | `ai_automation` | AI_WF_BLUEPRINT, AI_PROC_MAP, AI_TOOL_REPORT | One-time paid deliverables: workflow automation blueprints, process mapping, AI tool reports. Business-process focused. | Order workflow (QUEUED → workflow_automation_service, prompts, report generation). |
| **Market research** | `market_research` | MR_BASIC, MR_ADV | One-time paid reports: basic and advanced property/market research. | Same order workflow + report generation. |
| **Compliance services** | `compliance` | HMO_AUDIT, FULL_AUDIT, MOVE_CHECKLIST | One-time paid property compliance audits and checklists (HMO, full audit, move-in/out). | Same order workflow + audit report generation. |
| **Document pack** | `document_pack` | DOC_PACK_ESSENTIAL, DOC_PACK_PLUS, DOC_PACK_PRO | Landlord document packs (essential, tenancy/plus, ultimate/pro). Fixed pack contents + add-ons (e.g. fast track, printed). | Stripe webhook → document_pack_webhook_handler → document_pack_items → document_pack_orchestrator; separate from generic order workflow. |

**Shared across all four:**  
- Marketing: CMS-driven category/service pages (`/services/ai-automation`, `/services/market-research`, `/services/document-packs`, `/services/compliance-audits`).  
- Intake: **Unified Intake Wizard** (`/order/intake?service=...`), same draft API (`intake_draft_service`), same Stripe checkout (mode `payment`, metadata `type: order_intake`).  
- Orders live in `orders`; Document Packs additionally use `document_pack_items` and the pack orchestrator.

**Distinct from CVP:**  
- CVP is subscription intake (`/intake/start` → submit → checkout with `client_id`) and provisioning (properties, requirements, portal).  
- These four are **one-time order** flows; no CVP provisioning.  
- So: **Automation, Market research, Compliance services, Document pack** = order-based professional services. **CVP** = subscription product (Compliance Vault Pro).

---

## 2. What CompliSure Is (From Existing Alignment Doc)

- **Target:** UK SMEs (care, recruitment, childcare, property mgmt, finance, construction) — **organisation-centric**, not property-centric.  
- **Outputs:** Policies, procedures, staff handbooks, risk assessments, registers, DPIA, RoPA — **fact- and rule-driven document generation**.  
- **Mechanics:** 7-step intake → **IntakeSession**, **Answer**, **Facts** → **Rule engine** (conditions on facts → require_document, add_obligation, pricing_add) → **Obligations**, **DocumentDefinitions**, **Clause** library → **DocumentInstance** (versioned, facts_snapshot_hash). Complexity-based pricing (base + adders + caps). Regulatory alerts (impacted rules/docs, “apply update”).  
- **Not in current build:** Organisation model, question bank, Facts, Rule engine, Obligations, clause library, fact-driven doc gen, complexity pricing, regulatory alerts.  
- **Conclusion from alignment doc:** CompliSure fits as a **parallel product** (separate routes, intake, collections, provisioning). Shared: auth, Stripe, admin shell, hosting. Do **not** merge with CVP intake or replace CVP.

---

## 3. Does CompliSure Align With Each of the Four Services?

### 3.1 Automation services (AI & Automation)

| Dimension | Platform (Automation services) | CompliSure |
|-----------|---------------------------------|------------|
| **Domain** | Business process automation (workflow blueprints, process mapping, AI tool reports). | SME **regulatory** compliance (policies, handbooks, rules). |
| **Deliverable** | One-time reports/documents (e.g. PDF blueprint, process map). | Ongoing compliance docs (policies, DPIA, RoPA) generated from facts/rules. |
| **Trigger** | Customer orders a specific service (AI_WF_BLUEPRINT, etc.). | Intake answers → facts → rules → required documents. |
| **Alignment** | **No.** Different problem space (operational efficiency vs regulatory compliance). CompliSure does not replicate or substitute “Automation services.” |

**Verdict:** CompliSure does **not** align with Automation services. No duplication, no conflict. Keep both.

---

### 3.2 Market research

| Dimension | Platform (Market research) | CompliSure |
|-----------|-----------------------------|------------|
| **Domain** | Property/market research (MR_BASIC, MR_ADV). | No market research. |
| **Alignment** | **None.** CompliSure has no equivalent. |

**Verdict:** No alignment. No conflict. Keep Market research.

---

### 3.3 Compliance services (Compliance audits)

| Dimension | Platform (Compliance services) | CompliSure |
|-----------|----------------------------------|------------|
| **Domain** | **Property** compliance audits (HMO, full audit, move-in/out checklists) — certificate/evidence and property-centric. | **Organisation** compliance (GDPR, employment, H&S, sector regulators); obligations and policy/handbook generation. |
| **Output** | Audit reports, checklists (property-focused). | Policies, handbooks, registers, DPIA, RoPA (org-focused). |
| **Model** | One-time order → report generation. | Intake → facts → rules → obligations + document instances (ongoing, versioned). |
| **Alignment** | **Partial in name only.** Both use the word “compliance,” but platform = property/certificate audits; CompliSure = SME org compliance. Different data (properties vs organisations), different outputs (audit report vs policy docs). |

**Verdict:** CompliSure does **not** replace or duplicate “Compliance services” as implemented. They can coexist: one is property audit orders, the other is SME compliance product. No need to remove platform Compliance services.

---

### 3.4 Document pack

| Dimension | Platform (Document pack) | CompliSure |
|-----------|---------------------------|------------|
| **Domain** | Landlord document packs (fixed packs: essential, tenancy/plus, ultimate/pro). | SME document generation from **facts + rules** (DocumentDefinition, Clause library, DocumentInstance). |
| **Content** | Predefined landlord docs (tenancy, letters, etc.); pack tier + add-ons. | Dynamic: which documents are required is determined by rules; content from clause library and facts. |
| **Pipeline** | Order → document_pack_webhook_handler → document_pack_items → document_pack_orchestrator. | Org + facts + rules → required document keys → template + clauses → DocumentInstance (version, facts_snapshot_hash). |
| **Alignment** | **Conceptual only.** Both produce documents. Platform = fixed packs, order-triggered; CompliSure = rule-driven, fact-driven, versioned. Different data model, different templates, different triggers. |

**Verdict:** CompliSure does **not** replace Document pack. Landlord packs stay. CompliSure would add a **separate** document pipeline (org/facts/rules → DocumentInstance). Possible future reuse of “document generation” patterns (e.g. template + variables) but not the same service or catalogue.

---

## 4. Can CompliSure Be Integrated With the Four Services?

**Yes**, in the same way as with CVP: as a **separate product line**, not as a replacement or merge of the four.

- **Same platform:** Shared auth, Stripe, admin, hosting, support routing (e.g. support_chatbot can add a “CompliSure” service area).  
- **Separate:**  
  - CompliSure has its own intake (e.g. 7-step CompliSure wizard), own API (e.g. `/api/complisure/...`), own collections (organisations, intake_sessions, answers, facts, rules, obligations, document_definitions, document_instances).  
  - The four services keep: Unified Intake Wizard, `intake_draft_service`, `orders`, document_pack flow for packs, order workflow for the rest.  
- **No change** to Automation, Market research, Compliance services, or Document pack flows: no removal, no replacement of catalogue or intake.

So: **integration = add CompliSure alongside** the four services (and alongside CVP). No replacement.

---

## 5. Options: Replace vs Add vs Replace Totally

| Option | Meaning | Recommendation |
|--------|--------|----------------|
| **Replace (the four services) with CompliSure** | Discontinue Automation, Market research, Compliance services, Document pack and offer only CompliSure. | **No.** Would remove existing order-based services and break existing customers and positioning. CompliSure does not cover market research or automation services at all; it does not replicate property compliance audits or landlord document packs. |
| **Add CompliSure to the platform and retain the four services** | Keep all four service areas and CVP; introduce CompliSure as an additional product (e.g. new hub or “SME Compliance”) with its own intake, fulfilment, and data. | **Yes.** No conflict with existing services; shared infra; clear positioning (landlord/property vs SME compliance). |
| **Replace services totally with CompliSure** | Same as first option: only CompliSure, no Automation, Market research, Compliance, Document pack. | **No.** Same reasons; also “replace totally” would imply deleting or retiring the existing service catalogue, intake wizard, order workflow, and document pack orchestrator — unnecessary and harmful. |

**Best professional approach:** **Add CompliSure and retain all four services (and CVP).** Do not replace any of them with CompliSure.

---

## 6. Conflicts and Duplication (Codebase vs CompliSure)

- **Naming:** Platform has “Compliance” (property audits). CompliSure is “compliance” (SME/org). Both can live under the same roof with clear naming (e.g. “Property compliance audits” vs “SME Compliance” or “CompliSure”).  
- **Intake:** Platform uses **Unified Intake Wizard** and draft API for the four services. CompliSure needs a **different** intake (7 steps, question bank, answers, facts). No conflict if CompliSure uses separate routes and backend (e.g. `/complisure/start`, CompliSure-specific API).  
- **Documents:** Platform has **document_pack_orchestrator** and pack-specific logic. CompliSure needs **fact/rule-driven** doc gen and DocumentInstance. Different collections and pipelines; no need to reuse document_pack_items or pack webhook for CompliSure.  
- **Orders:** Platform **orders** are for one-time services (automation, market research, compliance audits, document packs). CompliSure could use a separate “CompliSure order” or subscription model; if one-time, a separate order type or product code keeps accounting and reporting clear.  
- **Catalogue:** `service_catalogue_v2` and `service_definitions_v2` define the four categories and their services. CompliSure does not belong in that catalogue (different product). Add CompliSure as a separate “product” or “hub” (e.g. `/complisure` or a fifth category that is clearly “SME Compliance” and not mixed with ai_automation / market_research / compliance / document_pack).

So: **no technical conflict** if CompliSure is implemented as a parallel product. **Duplication** is avoided by not reusing the same intake, same order type, or same document pipeline for CompliSure.

---

## 7. What Is Implemented vs What CompliSure Would Need

- **Already in codebase (for the four services):**  
  - Service catalogue V2 (categories: ai_automation, market_research, compliance, document_pack).  
  - Unified Intake Wizard, intake draft API, Stripe checkout for orders.  
  - Order workflow and document_pack_webhook_handler + document_pack_orchestrator.  
  - Marketing CMS (category/service pages).  
  - Support routing (e.g. support_chatbot) for these service areas.

- **Not in codebase (CompliSure-specific):**  
  - Organisation-centric model, 7-step CompliSure intake, question bank, Answer, Facts.  
  - Rule engine (conditions on facts → require_document, add_obligation, pricing_add).  
  - Obligations, DocumentDefinition with required_facts, Clause library, DocumentInstance (version, facts_snapshot_hash).  
  - Complexity-based pricing (base + adders + caps) and “Why this price.”  
  - Regulatory alerts and “apply update” / regenerate.  
  - CompliSure provisioning (org + optional initial doc gen) instead of CVP provisioning.

So: **reuse** platform auth, Stripe, admin shell, hosting, and patterns (intake → payment → fulfilment). **Build new** for CompliSure: intake API, facts, rules, obligations, doc gen pipeline, pricing engine, alerts. **Do not** repurpose the four services’ catalogue or order flow as CompliSure.

---

## 8. Summary and Recommendation

| Question | Answer |
|----------|--------|
| Does CompliSure align with Automation services? | **No.** Different domain (process automation vs SME compliance). |
| With Market research? | **No.** CompliSure has no market research. |
| With Compliance services? | **Only in name.** Platform = property audits; CompliSure = org compliance. Different. |
| With Document pack? | **Conceptually** (both produce documents). Different model (fixed packs vs rule/fact-driven). |
| Can CompliSure be integrated? | **Yes**, as a **parallel product** (separate intake, API, data, fulfilment). |
| Replace the four with CompliSure? | **No.** Would remove working services and confuse positioning. |
| Add CompliSure and retain the four? | **Yes.** Recommended. |
| Replace services totally with CompliSure? | **No.** Same as “replace”; do not retire the four services. |
| Conflicts if we add CompliSure? | **None** if CompliSure is separate (routes, collections, intake, doc pipeline). |
| Duplication risk? | **Low** if CompliSure does not reuse the same intake, order type, or document pack flow. |

**Best professional approach:**  
- **Add CompliSure to the platform** as a separate product (e.g. dedicated CompliSure hub and intake).  
- **Retain** Automation services, Market research, Compliance services, and Document pack unchanged.  
- **Retain** CVP (subscription, property-centric) unchanged.  
- Implement CompliSure per the existing CompliSure alignment doc (parallel product, Phases 1–5), **without** replacing or merging the four services or CVP.

**Do not:**  
- Replace any of the four services with CompliSure.  
- Merge CompliSure intake or document pipeline with the Unified Intake Wizard or document_pack_orchestrator.  
- Put CompliSure into the same service catalogue as ai_automation / market_research / compliance / document_pack without clear separation (prefer a distinct “product” or “hub” for CompliSure).

---

*Analysis only; no implementation. For implementation details, see `docs/COMPLISURE_BUSINESS_PLAN_ALIGNMENT_AND_RECOMMENDATION.md` and the phased plan there.*
