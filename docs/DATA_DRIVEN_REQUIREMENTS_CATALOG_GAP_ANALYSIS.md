# Data-Driven UK Landlord Requirement Catalog – Task vs Codebase Gap Analysis

**Constraints:** Do NOT change Stripe, provisioning, or auth flows. Do NOT claim legal compliance or certification in UI.

This document compares the **catalog task** (data-driven requirements_catalog, property_requirements, rule evaluator, compliance endpoints, seed data) to the **current implementation** and identifies what exists, what’s missing, conflicts, and the safest implementation path.

---

## Summary: Current State vs Task

| Area | Current implementation | Task requirement | Status |
|------|------------------------|------------------|--------|
| **Catalog of requirement definitions** | `requirement_rules` collection (rule_type, name, description, category, frequency_days, applicable_to, risk_weight) + hardcoded `FALLBACK_REQUIREMENT_RULES` in provisioning | `requirements_catalog` with code, title, description, category, criticality, weight, expiry_type, validity_days, applies_to JSON, evidence_required, etc. | **Different shape** – no `requirements_catalog`; `requirement_rules` is simpler and used by provisioning + admin rules API |
| **Property-level requirement state** | `requirements` collection (client_id, property_id, requirement_id, requirement_type, description, frequency_days, due_date, status) | `property_requirements` (property_id, requirement_code, status, expiry_date, evidence_doc_id, …) | **Conceptually same** – current `requirements` is per-property state; task names it property_requirements and keys by catalog code |
| **Applicability rules** | Provisioning: `applicable_to` (ALL / property type), or hardcoded conditions (e.g. has_gas_supply, is_hmo) | `applies_to` JSON with `all`/`any` and leaf `{field, op, value}`; ops: ==, !=, in, not_in, exists, true, false | **Missing** – no generic rule evaluator |
| **GET /api/properties/{id}/compliance-detail** | Does not exist. Client uses GET `/api/client/properties/{id}/requirements` (flat list). Property detail page builds matrix from that; no doc links or days_to_expiry in one response | Load property + catalog, filter applicable, join state, return matrix + property_score + risk_index + risk_level | **Missing** |
| **GET /api/portfolio/compliance-summary** | Exists. Reads `requirements` only; fixed points (VALID=100, EXPIRING_SOON=70, …); equal weight; no catalog; no KPIs/updated_at/name/expiring_30/missing | Use catalog weights + applicability; return portfolio_score, portfolio_risk_level, KPIs, property list | **Partial** – endpoint exists but not catalog-driven |
| **Scoring / risk** | Portfolio: equal weight, fixed points. Shared `utils/risk_bands`. No Risk Index; no HIGH-only guardrails | Weighted scoring with applicability denominator; Risk Index on HIGH critical only; guardrails: 1 HIGH overdue => at least HIGH; 2+ => CRITICAL | **Partial** – risk bands exist; weights and guardrails from catalog not implemented |
| **Frontend** | Dashboard uses compliance-summary + client compliance_score; property detail uses getPropertyRequirements; “How scoring works” collapsible exists | Consume new endpoints; Requirements Matrix from API; “How scoring works” with disclaimer | **Partial** – matrix is from requirements list, not compliance-detail API |
| **Seed data** | `rules.py` has DEFAULT_RULES (gas_safety, eicr, epc, fire_alarm, legionella, hmo_license, pat); provisioning has FALLBACK_REQUIREMENT_RULES + HMO_REQUIREMENTS | Seed requirements_catalog: GAS_CP12, EICR, EPC, SMOKE_ALARMS, CO_ALARMS, DEPOSIT_PI, RIGHT_TO_RENT, HOW_TO_RENT, TENANCY_AGREEMENT, HMO_LICENCE (conditional), FIRE_RISK (conditional), LEGIONELLA (low) | **Different** – different codes and list; no catalog seed |

---

## A) Backend Data Model – Detail

### 1) requirements_catalog (task)

- **Task:** Collection with code (unique), title, description, category, criticality (HIGH/MED/LOW), weight (number), expiry_type (EXPIRING/NON_EXPIRING/EVENT_BASED), validity_days, expiring_windows_days, evidence_required, evidence_types[], evidence_tags[], applies_to (JSON with all/any conditions), default_actions[], help_text.
- **Current:** No such collection. **requirement_rules** has: rule_id, rule_type, name, description, category (RuleCategory), frequency_days, warning_days, applicable_to (ALL or property type string), is_mandatory, is_active, risk_weight (1–5), regulatory_reference. So: no `code` (rule_type is the key), no criticality enum, no numeric `weight` for scoring, no expiry_type/validity_days/expiring_windows_days, no evidence_required/evidence_types/evidence_tags, no structured applies_to (only applicable_to), no default_actions/help_text.
- **Conflict:** Two definitions of “requirement definition”: **requirement_rules** (used by provisioning and admin rules API) vs task **requirements_catalog**. If we add a new collection with a different schema, we have two sources of truth unless we migrate or unify.
- **Safest option:**  
  - **Option A (recommended):** Add **requirements_catalog** as a new collection for **read-side** compliance (compliance-detail, compliance-summary). Keep **requirement_rules** and provisioning unchanged. Compliance endpoints resolve “applicable requirements” from catalog + rule evaluator; for **state** they keep using the existing **requirements** collection (join by mapping requirement_type → catalog code where possible). No change to how requirements are created (provisioning still uses requirement_rules or FALLBACK).  
  - **Option B:** Extend **requirement_rules** to add catalog-like fields (criticality, weight, applies_to JSON, expiry_type, etc.) and add a seed that matches the task list. Then compliance reads from requirement_rules. Risk: requirement_rules schema and admin API are already in use; extending may require migrations and API changes.  
  Recommendation: **Option A** – new `requirements_catalog` collection and seed; compliance logic uses it; provisioning unchanged.

### 2) property_requirements (task)

- **Task:** Table with property_id, requirement_code, status, expiry_date, evidence_doc_id, last_updated_at, source, notes, audit fields.
- **Current:** **requirements** collection has: requirement_id, client_id, property_id, requirement_type, description, frequency_days, due_date, status, created_at, updated_at. Documents link via `documents.requirement_id` (not a single evidence_doc_id on the requirement row).
- **Conflict:** Task uses “property_requirements” and requirement_code; we have “requirements” and requirement_type. Conceptually the same (per-property requirement state). Adding a **new** property_requirements table would duplicate state and require migrating documents and all consumers.
- **Safest option:** **Do not add a second table.** Treat **requirements** as the property-level state store. Add a **requirement_code** field (or treat requirement_type as the catalog code when it matches catalog). For compliance-detail, join requirements to catalog by code/type and attach evidence (e.g. latest VERIFIED document per requirement_id). If the task insists on the name “property_requirements”, it can be an alias (e.g. a view or a DTO built from requirements + documents) in the API response, not a new collection.

---

## B) Rule Evaluation – Detail

- **Task:** Evaluator for applies_to with keys `all`/`any` and leaf conditions `{field, op, value}`; ops: ==, !=, in, not_in, exists, true, false. Given property profile, return whether requirement applies.
- **Current:** Provisioning uses: (1) `applicable_to == "ALL" or applicable_to == property_type`, (2) conditions like `has_gas_supply`, `hmo_license_required` in code. No generic evaluator.
- **Gap:** New. Implement a small **rule evaluator** module that takes (property_profile: dict, applies_to: dict) and returns bool. Property profile should include fields the task expects (e.g. property_type, is_hmo, has_gas_supply, local_authority, etc.) from the property document. Use this **only** for catalog-driven compliance (compliance-detail, compliance-summary); do not change provisioning logic (non-goal).

---

## C) Compliance Endpoints – Detail

### 1) GET /api/properties/{id}/compliance-detail

- **Exists:** No. Client has GET `/api/client/properties/{id}/requirements` (list of requirements for that property).
- **Task:** Load property → load catalog → filter applicable (applies_to) → join property_requirements state → per requirement: status label + numeric score (expiry decay), criticality, weight, expiry_date, days_to_expiry, evidence link → return matrix + property_score + risk_index + risk_level.
- **Implementation path:** Add GET `/api/portfolio/properties/{property_id}/compliance-detail` (or under `/api/client/...`) with client_route_guard. Load property (must belong to client); load requirements_catalog; for each catalog item evaluate applies_to against property; for applicable items, find matching row in **requirements** (by requirement_type or requirement_code); compute status/score (expiry decay from earlier task); attach evidence (document(s) with that requirement_id). Return matrix, property_score, risk_index (HIGH only), risk_level (using shared risk_bands + guardrails). If catalog is empty, fall back to current behaviour (requirements list + simple scoring) so existing UI keeps working.

### 2) GET /api/portfolio/compliance-summary

- **Exists:** Yes. Reads requirements only; fixed points; equal weight; no catalog; no KPIs/updated_at/property name/expiring_30/missing.
- **Task:** For each property compute score/risk using same model as compliance-detail; return portfolio_score, portfolio_risk_level, KPIs, property list.
- **Conflict:** Extending the endpoint to be catalog-driven (weights, applicability, risk index, guardrails) without breaking existing clients. Keep response shape backward-compatible (e.g. keep risk_level as alias for portfolio_risk_level); add new fields (updated_at, kpis, name, expiring_30_count, missing_count). When catalog is present, compute using catalog weights and applicability; when catalog is empty, keep current logic (no breaking change).

---

## D) Scoring and Risk Model – Detail

- **Task:** Weighted scoring with applicability-filtered denominator. Risk Index only on HIGH criticality. Guardrails: any HIGH overdue => risk at least HIGH; 2+ HIGH overdue => CRITICAL.
- **Current:** Portfolio uses equal weight and fixed points; risk from `utils/risk_bands` (score bands only). No Risk Index; no criticality-based guardrails.
- **Gap:** In catalog-driven path: (1) Filter requirements by applies_to. (2) S_property = sum(weight_i * score_i) / sum(weight_i) over applicable. (3) Portfolio = weighted average of property scores by sum of weights per property. (4) Risk Index R = (3*overdue + 2*missing + 1*expiring_soon) / max(1, total_high_applicable). (5) Final risk = max(score-based band, risk-index band); then apply guardrails (1 HIGH overdue => at least HIGH; 2+ => CRITICAL). Use shared `utils/risk_bands` for band labels; add guardrail logic in the same place that computes risk_level.

---

## E) Frontend – Detail

- **Task:** Update dashboard + property views to consume new endpoints; render Requirements Matrix from API response; “How scoring works” collapsible with non-legal disclaimer.
- **Current:** Dashboard uses getComplianceSummary (portfolio) and client compliance score; property detail uses getPropertyRequirements; “Compliance Framework – how scoring works” collapsible exists with disclaimer.
- **Gap:** (1) Add client API method for GET compliance-detail (property). (2) Property detail page: optionally call compliance-detail and render matrix from that (status, expiry, days_to_expiry, evidence link); fallback to getPropertyRequirements if compliance-detail 404 or catalog empty. (3) Dashboard already uses compliance-summary; when backend adds kpis/updated_at/name, extend UI to show them. (4) Keep “How scoring works” wording non-legal (already in place).

---

## F) Seed Data – Detail

- **Task:** Initial seed for requirements_catalog: GAS_CP12, EICR, EPC, SMOKE_ALARMS, CO_ALARMS, DEPOSIT_PI, RIGHT_TO_RENT, HOW_TO_RENT, TENANCY_AGREEMENT, HMO_LICENCE (conditional), FIRE_RISK (conditional), LEGIONELLA (low); realistic weights and applies_to.
- **Current:** rules.py DEFAULT_RULES: gas_safety, eicr, epc, fire_alarm, legionella, hmo_license, portable_appliance_test. Provisioning FALLBACK has gas_safety, eicr, epc, fire_alarm, legionella; HMO_REQUIREMENTS has hmo_license, fire_risk_assessment, etc. No DEPOSIT_PI, RIGHT_TO_RENT, HOW_TO_RENT, TENANCY_AGREEMENT in rules seed; no GAS_CP12 (gas_safety exists).
- **Conflict:** Catalog seed uses different codes (e.g. GAS_CP12 vs gas_safety). Existing requirements in DB use requirement_type from provisioning (e.g. gas_safety, eicr). So we need a **mapping** from catalog code to requirement_type for join (e.g. GAS_CP12 ↔ gas_safety) or we seed catalog with codes that match existing requirement_type where possible (e.g. gas_safety, eicr, epc) and add new codes (DEPOSIT_PI, RIGHT_TO_RENT, …) for which no requirement rows may exist yet.
- **Safest option:** Seed requirements_catalog with **codes** that match existing requirement_type where applicable (gas_safety, eicr, epc, legionella, hmo_license, fire_risk_assessment, etc.) plus task codes (GAS_CP12 can alias to gas_safety, or we use gas_safety in catalog). So: one-to-one mapping between catalog code and requirement_type for existing types; new catalog-only codes can exist and simply show as “not yet present” for a property until provisioning or manual flow creates them. No change to provisioning: it continues to create requirements with existing types; compliance-detail joins on requirement_type == catalog code (or explicit mapping table/code field).

---

## Conflicts Summary and Recommended Approach

| Issue | Conflict | Safest option |
|-------|----------|----------------|
| **Catalog vs requirement_rules** | Two definition sources | Add **requirements_catalog** for read-side compliance only; leave requirement_rules and provisioning as-is. |
| **property_requirements vs requirements** | Task wants separate table | Use **requirements** as the state store; no new table; join by requirement_type/code and attach evidence from documents. |
| **Catalog code vs requirement_type** | Different naming (GAS_CP12 vs gas_safety) | Seed catalog with codes that match requirement_type where possible; add mapping or alias (e.g. code gas_safety) so existing data joins. |
| **Rule evaluator vs provisioning** | New applies_to (all/any) vs current applicable_to | Implement evaluator for **compliance only**; provisioning logic unchanged. |
| **Compliance-summary behaviour** | Catalog-driven vs current | When catalog has data, use catalog weights + applicability; when catalog empty or feature-flagged, keep current behaviour; response shape backward-compatible. |

---

## Implementation Order (Safe, No Provisioning/Auth Change)

1. **Data model**  
   - Add **requirements_catalog** collection and indexes (e.g. code unique).  
   - Do **not** add property_requirements collection; keep using **requirements**; ensure requirements have or can be joined to catalog (e.g. requirement_type = catalog code).

2. **Rule evaluator**  
   - New module: input (property dict, applies_to dict) → bool. Support all/any and leaf {field, op, value}; ops ==, !=, in, not_in, exists, true, false. Used only by compliance logic.

3. **Seed**  
   - Seed requirements_catalog with task items (GAS_CP12/gas_safety, EICR, EPC, SMOKE_ALARMS, CO_ALARMS, DEPOSIT_PI, RIGHT_TO_RENT, HOW_TO_RENT, TENANCY_AGREEMENT, HMO_LICENCE, FIRE_RISK, LEGIONELLA) with weights and applies_to. Use codes that match requirement_type where possible for existing data.

4. **GET /api/portfolio/properties/{id}/compliance-detail**  
   - New endpoint; client_route_guard; load property + catalog; filter applicable (evaluator); join requirements (+ documents for evidence); compute scores (expiry decay), risk index (HIGH), risk_level (bands + guardrails); return matrix + property_score + risk_index + risk_level.

5. **GET /api/portfolio/compliance-summary**  
   - Extend to optionally use catalog: when catalog present, for each property compute score/risk as in compliance-detail; aggregate portfolio_score, portfolio_risk_level, KPIs; add updated_at, kpis, property name, expiring_30_count, missing_count. When catalog empty, keep current behaviour.

6. **Frontend**  
   - Add getComplianceDetail(propertyId). Property detail: prefer compliance-detail for matrix when available; fallback to getPropertyRequirements. Dashboard: use extended compliance-summary (kpis, names, etc.) when returned.

7. **Non-goals**  
   - No change to Stripe, provisioning, or auth. No legal certification wording in UI.

This keeps a single source of requirement **state** (requirements collection), adds a single source of **definitions** (requirements_catalog) for read-side compliance, and avoids duplication or breaking existing flows.
