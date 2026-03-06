# Honest Assessment: “Central Intelligence Layer” Vision vs Current Build

**Purpose:** Compare the described product vision (UK property: reactive maintenance, contractor chaos, compliance, visibility) with the current CVP codebase. No implementation — assessment and integration options only.

**Scope:** Backend + frontend in `Pleerity-enterprise`; docs and tests used only as evidence of what exists.

---

## 1. Vision Summary (from your brief)

- **Core:** A central intelligence layer for property assets — a *decision engine*, not just a maintenance app.
- **Problems:** Reactive maintenance, contractor coordination chaos, compliance tracking (gas, EICR, EPC), poor portfolio visibility; worsened by regulation, ageing stock, skills shortages.
- **Four pillars:**  
  1. **Predictive Maintenance** (property age, past repairs, usage → predict boiler/damp/electrical).  
  2. **Automated Workflows** (tenant report → AI categorise → contractor dispatch → SLA → invoice match).  
  3. **Compliance Engine** (gas, EICR, fire, EPC, legionella; alerts, schedule inspections, store evidence).  
  4. **Contractor Network** (vetted trades, pricing benchmarks, performance scoring → marketplace).
- **Revenue:** SaaS tiers (£5–£15/property), contractor commissions, audits, insurance, data insights.
- **GTM:** Landlords 20–200 props, letting agents, BTR; avoid single-property; start with one pain (compliance or maintenance).

---

## 2. What Is Implemented (codebase evidence)

### 2.1 Compliance Engine — **largely implemented**

| Capability | Status | Where in codebase |
|------------|--------|-------------------|
| Track gas, EICR, EPC, fire risk, legionella, HMO, deposit, etc. | ✅ | `database.py` seeds `requirements_catalog` (gas_safety, eicr, epc, fire_risk_assessment, legionella, hmo_license, deposit_pi, …). `catalog_compliance.py` + `provisioning.py` use it. |
| Alerts | ✅ | `daily_reminders` job, expiry windows, `compliance_sla_monitor`, `compliance_sla_alerts`, notification orchestrator. |
| Schedule inspections | ⚠️ Partial | Calendar/expiry views and reminders; no dedicated “schedule inspection” workflow or calendar booking. |
| Store evidence | ✅ | Document vault, uploads, AI extraction, `confirmed_expiry_date`, linked to requirements. |
| Applicability rules | ✅ | `applies_to` (e.g. gas only if `has_gas_supply`; EICR frequency by `building_age_years` in provisioning). |
| Portfolio visibility | ✅ | Dashboard, score trend, portfolio compliance summary, risk level, score ledger, audit. |

**Conclusion:** The compliance engine is the strongest fit. It already delivers “compliance tracking” and “visibility across portfolios” for certificates and regulatory items. Gaps: no first-class “schedule inspection” flow; no separate “compliance audits” as a sold product (only internal recalc/SLA monitoring).

### 2.2 Predictive Maintenance — **not implemented**

| Capability | Status | Where in codebase |
|------------|--------|-------------------|
| Property age | ⚠️ Data only | `building_age_years` on Property; used for **EICR frequency** in provisioning (`provisioning.py`), not for failure prediction. |
| Past repairs | ❌ | No repairs/maintenance history model or collection. |
| Usage patterns | ❌ | No usage or occupancy-derived signals. |
| Predict boiler/damp/electrical | ❌ | No prediction jobs, no risk models for kit failure. |
| Feature flag | ✅ Placeholder | `PREDICTIVE_MAINTENANCE` in `ops_compliance_feature_flags.py` (default False); no backend behaviour. |

**Conclusion:** Only the data field `building_age_years` exists and is used for compliance (EICR), not for predictive maintenance. No “predictive” logic, no repairs data, no prediction pipeline.

### 2.3 Automated Workflows (maintenance) — **not implemented**

| Capability | Status | Where in codebase |
|------------|--------|-------------------|
| Tenant reports issue | ❌ | Tenant portal is view-only (compliance, download pack); no “report a repair” or maintenance request. |
| AI categorise severity | ❌ | No categorisation of maintenance requests. |
| Approved contractor auto-dispatched | ❌ | No contractors, no dispatch. |
| SLA tracked | ⚠️ Other SLAs only | SLAs exist for: compliance recalc queue, job runs (sla_watchdog), lead follow-up, order workflow (e.g. wf9). **No** maintenance/repair SLA. |
| Invoice matched & approved | ❌ | No invoice–work-order matching; Stripe is for subscriptions/onboarding, not contractor invoices. |

**Conclusion:** “Automated workflows” in the sense of tenant → issue → contractor → SLA → invoice are not in the codebase. Existing SLA/automation is compliance- and operations-focused (recalc, jobs, leads, orders).

### 2.4 Contractor Network — **not implemented**

| Capability | Status | Where in codebase |
|------------|--------|-------------------|
| Vetted trades | ❌ | No contractor/trade entity or vetting flow. |
| Pricing benchmarks | ❌ | No pricing data or benchmark model. |
| Performance scoring | ❌ | No contractor performance or ratings. |
| Marketplace / long-term | ❌ | No marketplace or contractor-facing flows. |
| Feature flag | ✅ Placeholder | `CONTRACTOR_NETWORK` in `ops_compliance_feature_flags.py` (default False); admin “Contractors” is `AdminOpsPlaceholderPage`. |

**Conclusion:** Only the feature flag and a placeholder nav exist. No data model, no APIs, no UI.

### 2.5 Revenue model vs codebase

| Element | Status | Evidence |
|---------|--------|----------|
| Core SaaS (£5–£15/property, tiers) | ✅ | `plan_registry`: Solo/Portfolio/Pro with property limits and Stripe pricing; plan-gating and entitlements. |
| Contractor commissions (5–10%) | ❌ | No contractor or job billing. |
| Compliance audits | ⚠️ | Internal compliance recalc and SLA monitoring exist; no “audit as a product” or sold audit workflow. |
| Insurance partnerships | ❌ | No insurance-specific flows or data. |
| Data insights for institutional landlords | ⚠️ | Reports, score trend, portfolio summary, exports; no dedicated “institutional” or data-product layer. |

### 2.6 Go-to-market and defensibility

- **First pain point:** Risk-check → intake → checkout → provisioning is built; compliance is the solved pain. Maintenance is not.
- **Audience:** Plan limits (2, 10, 25) and B2B intake align with “small portfolios first”; no explicit 20–200 or “avoid single-property” logic in code.
- **Defensibility:** Strong on property + compliance data (requirements, documents, score history, ledger). No maintenance outcome or contractor performance data yet.

---

## 3. Summary: Have we implemented the full vision?

**No.** We have implemented:

- A **compliance-focused** decision layer: certificates, applicability, scoring, alerts, evidence, visibility, and reporting. That matches **one** of the two “Phase 1” options (compliance tracking).
- **Scaffolding** for the rest: feature flags (`MAINTENANCE_WORKFLOWS`, `PREDICTIVE_MAINTENANCE`, `CONTRACTOR_NETWORK`, `INVOICING`), provisioning status for “maintenance” module, Operations & Compliance admin structure (Overview, Maintenance, Contractors placeholders). No behaviour behind maintenance/predictive/contractor.

We have **not** implemented:

- Predictive maintenance (no repairs, no usage, no prediction).
- Maintenance workflows (tenant report → categorise → dispatch → SLA → invoice).
- Contractor network (no trades, pricing, performance, marketplace).
- Revenue from contractors, audits as product, or insurance.

So: **compliance engine and visibility are in place; predictive maintenance, automated maintenance workflows, and contractor network are not.**

---

## 4. How to integrate or implement without breaking existing flow

Principles:

- Keep **intake → checkout → provisioning → client portal** and existing compliance/score/reminder/report flows unchanged.
- Use existing **feature flags** and **provisioning_status** so new modules are opt-in per client and property.
- Add **new** collections, services, and routes; avoid rewriting core compliance or auth.

### 4.1 Predictive maintenance

- **Data:** Add collections (e.g. `property_assets`, `repair_history` or `maintenance_events`) and optional fields on Property (e.g. boiler install date, last service). Reuse `building_age_years` where relevant.
- **Logic:** New service(s) and scheduled job(s) that read from these + catalog; output “risk” or “recommended action” per property/asset. No change to existing scoring or requirements.
- **UX:** New client/admin views and optional dashboard widgets; gated by `PREDICTIVE_MAINTENANCE`. Compliance engine and existing dashboard remain the source of truth for certificate-based compliance.

### 4.2 Automated maintenance workflows

- **Data:** New collections for maintenance requests (tenant/client), work orders, and optionally assignments. Link to property/client; keep tenant and client APIs consistent with current roles.
- **Flow:** New routes for “create request” (tenant or client), optional AI/rule-based categorisation, status lifecycle. SLA can reuse patterns from `compliance_sla_monitor` / `sla_watchdog` (new job + collection) without touching existing SLA code.
- **Contractor side:** Only after contractor network exists; dispatch = assign work order to contractor; SLA = “respond/complete by”.
- **Invoice:** Later phase; match invoice to work order in new service; no change to Stripe subscription/onboarding.

### 4.3 Contractor network

- **Data:** New collections (e.g. contractors, trades, areas, pricing, performance events). No change to `clients` or `properties` beyond optional links (e.g. “preferred contractor”).
- **APIs:** New admin/client routes for contractor CRUD, assignment, performance; gated by `CONTRACTOR_NETWORK`. Existing compliance and document APIs unchanged.
- **UI:** Replace current placeholders (Admin Ops “Contractors”, client-side if needed) with real UIs; keep Feature Controls and plan/usage as they are.

### 4.4 Order of implementation (suggested)

1. **Contractor network (minimal):** Entities, vetted flag, link to client/property. Enables “approved contractor” and dispatch later.
2. **Maintenance workflows:** Requests and work orders, status, SLA, optional dispatch to contractors. Tenant “report issue” can be a new tenant endpoint without changing existing tenant read-only behaviour.
3. **Predictive maintenance:** Data model for assets/repairs, then prediction job and read-only insights. Can run in parallel with (1)–(2).
4. **Invoice matching:** After work orders and contractors exist; new service that matches invoices to completed work.

Throughout: keep compliance engine, score ledger, reminders, and observability (job runs, incidents, SLA watchdog) as they are; add new modules behind feature flags and provisioning status so existing flows stay default and unchanged.

---

## 5. Recommendation

- **Honest assessment:** The full “central intelligence layer” (all four pillars) is **not** implemented. Only the **compliance engine** and **portfolio visibility** are implemented; predictive maintenance, maintenance workflows, and contractor network are scaffolded (flags, placeholders) but not built.
- **Integration:** The codebase is structured so these can be added **incrementally** without breaking intake, provisioning, or compliance: use existing flags, add new collections and services, and gate new UI by plan/flag.
- **Practical path:** Treat the current build as “Phase 1: compliance” and add maintenance/contractor/predictive as Phase 2 modules, with contractor + work orders before predictive (so predictions can eventually drive “recommended repair” or work orders). Keep compliance as the stable core and revenue driver while extending.

---

*Assessment only; no code changes. For implementation details, use this doc plus existing runbooks and spec alignment docs (e.g. `SENIOR_PRODUCT_ENGINEER_SPEC_ALIGNMENT_AND_RECOMMENDATION.md`, `BUSINESS_FLOW_AND_USER_JOURNEY_REPORT.md`).*
