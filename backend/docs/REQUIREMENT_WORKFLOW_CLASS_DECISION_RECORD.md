# Requirement workflow class — formal decision record

**Document type:** Product / policy / architecture decision record (pre-implementation).  
**Status:** Open — awaiting explicit approvals listed in §5.  
**Audience:** Product leadership, compliance/legal reviewers, platform architecture owners.

**Hard constraints (by governance programme):**

- **Do not** implement resolver, registry data, evidence authority, or client runtime changes based solely on this document until blockers in §5 are cleared and §6 rules are satisfied.
- **Do not** treat this file as runtime configuration.

---

## 1. Scope

### 1.1 Requirement codes included

This record covers **every canonical requirement storage slug** intended for compliance workflows in codebase inventory **plus** explicit policy-only slugs used only in evidence defaults or tests:

| Source | Codes covered |
|--------|----------------|
| **`CANONICAL_REQUIREMENT_CODES`** (`services/requirement_code_registry.py`) | `gas_safety`, `eicr`, `epc`, `smoke_heat_alarms`, `legionella`, `fire_risk_assessment`, `hmo_fire_risk`, `hmo_fire_risk_evidence`, `portable_appliance_test`, `hmo_license`, `property_licence`, `selective_license`, `landlord_registration`, `scotland_landlord_registration`, `occupation_contract`, `wales_occupation_contract`, `deposit_pi`, `right_to_rent`, `rent_smart_wales`, `landlord_registration_ni`, `how_to_rent`, `tenancy_agreement` |
| **Policy / evidence defaults only** (`DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE` in `services/compliance_evidence_record_service.py`) | `deposit_prescribed_info` *(also deposit_pi / how_to_rent / right_to_rent overlap with canonical; `smoke_heat_alarms` keys defaults but is **canonical** — §2.6)* |
| **Engine operational JOB slugs** (`_SPECS_BY_STORAGE_SLUG` in `services/compliance_requirement_engine.py`) | `emergency_lighting`, `fire_extinguisher`, `communal_cleaning`, `communal_fire_doors` |
| **System classification** | `hmo_classification`, `property_classification` |
| **Catalog seed** (`database.py` → `requirements_catalog`) | Aligns with canonical + `fire_alarm` legacy; seed list is a **subset** of canonical + legacy inspection labels |

### 1.2 Aliases included

| Alias / legacy string | Normalizes / maps to | Source |
|----------------------|----------------------|--------|
| `gas_safety_certificate` | `gas_safety` (product copy; normalize via registry / `normalize_requirement_code`) | `frontend/src/domain/domain_labels.json` |
| `fire_alarm`, `fire_detection`, `smoke_alarms`, `co_alarms` (legacy storage / labels) | `smoke_heat_alarms` | `requirement_code_registry._LEGACY_ALIASES`; runtime alias family `requirement_client_runtime_surface.py` |
| `smoke_heat_alarms` | Canonical domestic alarm code; alias family groups legacy smoke/CO/fire-detection labels | `_ALIAS_FAMILY_BY_CANONICAL` |
| `tenancy_deposit_protection` | Deposit family (`deposit_pi` / prescribed) | `_ALIAS_FAMILY_BY_CANONICAL` |
| `deposit_prescribed_info` | Tenancy deposit alias family | `_ALIAS_FAMILY_BY_CANONICAL` |
| `right_to_rent_checks` | `right_to_rent` family | `_ALIAS_FAMILY_BY_CANONICAL` |
| `hmo_fire_risk` ↔ `hmo_fire_risk_evidence` | Shared alias family | `_ALIAS_FAMILY_BY_CANONICAL` |

### 1.3 Source files used for this audit

| File | Use |
|------|-----|
| `backend/services/requirement_code_registry.py` | Canonical codes, legacy aliases |
| `backend/services/compliance_requirement_engine.py` | Engine class per slug (DOCUMENT / JOB / OBLIGATION / SYSTEM) |
| `backend/services/compliance_evidence_record_service.py` | `effective_evidence_resolution`, defaults, evidence modes |
| `backend/services/requirement_action_resolver.py` | `take_action` envelope, intents, enrich metadata |
| `backend/services/requirement_truth.py` | Enriched row contract for client APIs |
| `backend/services/requirement_client_runtime_surface.py` | Alias families, client surface gates |
| `backend/database.py` | `requirements_catalog` seed |
| `frontend/src/domain/domain_labels.json` | Display labels (not authority) |
| `backend/docs/STREAM_D_CTA_PARITY_ENFORCEMENT.md` | Related CTA contract discipline |

### 1.4 Warning — live published registry

The **published compliance registry** in production may define additional **`canonical_code`** values or jurisdiction-conditioned drafts **not** listed in static code enumerations. Operations must **export** the live registry snapshot periodically and **append** rows to this decision record (or a registry appendix) before claiming completeness.

---

## 2. Current reality (taxonomy)

### 2.1 Canonical codes

See §1.1 table (`CANONICAL_REQUIREMENT_CODES` ∪ policy-only slugs).

### 2.2 Aliases

See §1.2. Normalization **must** remain the single entry point so aliases do not fork workflows in UI.

### 2.3 Policy-only slugs

| Slug | Meaning |
|------|---------|
| `deposit_prescribed_info` | Prescribed information; part of deposit family; evidence defaults present |

**Note:** `smoke_heat_alarms` was historically discussed as policy-only / consolidation risk; it is **now** the **canonical** domestic alarm code in `requirement_code_registry` — see **§2.6** (unified workflow and evidence completeness).

### 2.4 Operations / job slugs

| Slug | Engine pattern |
|------|----------------|
| `emergency_lighting`, `fire_extinguisher`, `communal_cleaning`, `communal_fire_doors` | `_JOB_EXECUTION` — maintenance-style job execution, not certificate upload |

### 2.5 System classification slugs

| Slug | Engine pattern |
|------|----------------|
| `hmo_classification`, `property_classification` | `_SYSTEM_CLASSIFICATION` — internal / derived |

### 2.6 Domestic alarm unified workflow (`smoke_heat_alarms`) and evidence completeness

**Unified workflow:** `smoke_heat_alarms` is the **single** registry-facing domestic alarm requirement identity (unified workflow). Legacy slugs may still normalise into it; the product treats one obligation surface, not parallel smoke vs heat rows for the same property context.

**Separation from requirement state:** **Evidence completeness** for this workflow is evaluated **separately** from the top-level requirement compliance state (e.g. satisfied / gap / scoring). Completeness answers “which evidence components does policy expect for audit/visibility?” — it does **not** replace or override scoring engines.

**Component rules:** **`smoke_alarm`** evidence is **always** required for completeness where the unified requirement applies. **`co_alarm`** is **conditionally** required based on **property and registry** context (jurisdiction / obligation rules), not as a universal second upload for every portfolio.

**Non-enforcement:** Completeness is **visibility and audit support only** — it informs client/admin UI and workflow audit signals; it is **not** a separate scoring enforcement layer and must not be read as an alternate compliance verdict.

**Current limitation:** A **generic document** upload can **heuristically** satisfy the smoke component for completeness (filename/title matching). That is intentional for continuity but **imprecise** vs structured evidence.

**Future improvement:** **Explicit evidence component tagging** (or equivalent metadata on evidence records) so completeness reflects tagged components rather than inference from document text alone.

### 2.7 Phase 1 — How to Rent (`how_to_rent`) — `TENANT_DELIVERY` (implemented)

**Scope (narrow):** England & Wales How to Rent leaflet delivery duty **only where** published registry / obligation applicability exposes the requirement (no UK-wide claim beyond jurisdiction rules).

**Runtime class:** `workflow_class` = **`TENANT_DELIVERY`** when `primary_resolution_workflow` on effective evidence policy is `TENANT_DELIVERY` (resolver enrich path).

**Evidence modes (defaults):** **`STRUCTURED_DECLARATION`** first (primary — delivery record), **`DOCUMENT_UPLOAD`** second (supporting proof only). Legacy rows that only have document evidence remain display-safe; document-only **published** overrides raise admin audit flag `TENANT_DELIVERY_DOCUMENT_ONLY`.

**Structured fields (declaration checklist):** tenancy start date; guide version / publication (text if date unknown); delivery date; delivery method (email, hand delivery, post, tenant portal, other); tenant/recipient; optional proof reference; declaration confirmation (yes/no).

**Client copy:** Primary CTA — **“Record How to Rent delivery”**; secondary document path — **“Upload delivery proof”** (not “upload the guide” as the main action). Modal includes **client-safe disclosure**: records delivery details for platform review — **not** government/court verification or legal advice.

**Explicit non-goals for Phase 1:** No change to compliance **scoring** formulas; no bulk Mongo migration; no tenant entity linkage; no deposit / prescribed information changes.

### 2.8 Phase 1 — Right to Rent (`right_to_rent` / `right_to_rent_checks`) — `GUIDED_DECLARATION` (implemented)

**Scope:** England statutory checks **only where** catalog / scoring / planner applicability already exposes the obligation (**not** Wales, Scotland, or NI via existing jurisdiction rules).

**Runtime class:** `workflow_class` = **`GUIDED_DECLARATION`** when `primary_resolution_workflow` is **`GUIDED_DECLARATION`** on effective evidence policy.

**Evidence modes (defaults):** **`STRUCTURED_DECLARATION`** first, **`DOCUMENT_UPLOAD`** second (supporting only). Legacy document-only rows remain valid; published overrides that allow **only** `DOCUMENT_UPLOAD` raise admin audit flag **`RIGHT_TO_RENT_GUIDED_DECLARATION_DOCUMENT_ONLY`**.

**Structured fields:** tenant name; check date; document type (select); optional document reference; outcome (`unlimited` / `time_limited` / `not_verified`); follow-up required (yes/no); optional follow-up date; declaration confirmation.

**Client copy:** Primary CTA — **“Record Right to Rent check”**; modal title matches; secondary document path — **“Upload supporting evidence”**. **Client disclosure:** records check details for platform review — **not** Home Office verification or legal advice.

**Alias:** `right_to_rent_checks` normalises to the same defaults and schema as `right_to_rent`.

**Explicit non-goals for Phase 1:** No scoring or `_applies_if` changes; no tenant entity linkage; no claim of statutory verification beyond record-keeping support.

---

## 3. Proposed workflow classes (definitions)

These are **client-facing workflow classes** (`client_workflow_class`). They **must not** be inferred from evidence modes alone; **policy + resolver** assign exactly one class per requirement row.

| Class | Definition | Primary user outcome |
|-------|------------|----------------------|
| **DOCUMENT_UPLOAD** | Single authoritative path: upload a requirement-scoped certificate/report to the evidence vault; verification and recalc follow existing evidence authority. | Valid document on file, tracked and verified per policy. |
| **MULTI_EVIDENCE** | Guided resolution: user adds evidence via **allowed modes only** (declaration, checklist, contractor confirmation, document as permitted inside policy — exact modes are **inputs**, not the class). | Complex obligations evidenced without forcing a single certificate. |
| **GUIDED_DECLARATION** | Primary path is structured declaration / checklist (supporting document optional per policy). | Procedural compliance captured as structured, auditable evidence. |
| **TENANT_DELIVERY** | Evidence that information was delivered to tenant(s) (delivery record, method, date, proof). **Requires** dedicated capture semantics (may extend beyond current four evidence modes). | Proof of delivery for statutory information duties. |
| **EXTERNAL_REMEDIATION_TRACKING** | Landlord arranges assessment externally; platform records completion / uploads outcome — **no** implication that Pleerity performs or books regulated work. | External assessment evidenced without marketplace/scheduling claims. |
| **REMEDIATION_JOB** | Compliance-related work tracked through **operations** job/work-order lifecycle linked to requirement/property where applicable. | Operational remediation with SLA and completion proof. |
| **GUIDANCE_ONLY** | No evidence submission path on client surface; education, applicability, or official links only. | Understanding obligation without implying a false action. |
| **HIDDEN_SYSTEM** | Row exists for classification/scoring but **must not** drive a primary client CTA (suppress or admin-only). | Prevents misleading user actions on system rows. |

**Strict separation (programme rule):** `DOCUMENT_UPLOAD`, `EXTERNAL_REMEDIATION_TRACKING`, and `REMEDIATION_JOB` **must not overlap** for the same requirement identity — **one** class, **one** primary entry point.

---

## 4. Decision table

**Legend — implementation gate:**

| Gate | Meaning |
|------|---------|
| **ALLOWED*** | Narrow technical work may proceed **only** where no §5 blocker applies to that code (documented in row). |
| **BLOCKED** | No implementation until §5 decisions are approved for that row or family. |

**Legend — authority affected:** abbreviated — **PR** policy/registry, **RS** resolver, **EV** evidence authority, **SC** scoring, **AU** audit, **OP** operations/jobs.

| canonical_code | Current code behaviour (summary) | Proposed `client_workflow_class` | Unresolved decision | Migration risk | Authority affected | Gate |
|----------------|-----------------------------------|-----------------------------------|----------------------|----------------|-------------------|------|
| gas_safety | DOCUMENT upload path; resolver doc labels | DOCUMENT_UPLOAD | None if labels fixed in resolver/registry copy | Low | PR, RS, EV, SC, AU | ALLOWED* |
| eicr | Same | DOCUMENT_UPLOAD | None | Low | PR, RS, EV, SC, AU | ALLOWED* |
| epc | Same | DOCUMENT_UPLOAD | None | Low | PR, RS, EV, SC, AU | ALLOWED* |
| portable_appliance_test | DOCUMENT default; registry may extend modes | DOCUMENT_UPLOAD | Whether extended modes flip class to MULTI_EVIDENCE | Med | PR, RS | BLOCKED if multi-mode without class rule |
| hmo_license | DOCUMENT | DOCUMENT_UPLOAD | None | Low | PR, RS, EV | ALLOWED* |
| property_licence | DOCUMENT | DOCUMENT_UPLOAD | Jurisdiction variants | Med | PR | BLOCKED until jurisdiction matrix |
| selective_license | DOCUMENT | DOCUMENT_UPLOAD | Local authority variance | Med | PR | BLOCKED until matrix |
| landlord_registration | DOCUMENT | DOCUMENT_UPLOAD | Nation-specific copy | Low–Med | PR | ALLOWED* |
| scotland_landlord_registration | DOCUMENT | DOCUMENT_UPLOAD | Same | Med | PR | ALLOWED* |
| rent_smart_wales | DOCUMENT | DOCUMENT_UPLOAD | Wales-only | Med | PR | BLOCKED until regional approval |
| landlord_registration_ni | DOCUMENT | DOCUMENT_UPLOAD | NI-only | Med | PR | BLOCKED until regional approval |
| fire_detection | DOCUMENT default; alias family | DOCUMENT_UPLOAD **or** MULTI_EVIDENCE | **§5.2** — class vs multi-mode | High | PR, RS | BLOCKED |
| smoke_alarms | Engine FIRE_DETECTION; catalog doc-heavy | MULTI_EVIDENCE (target) | **§5.1** consolidation | **Critical** | PR, RS | BLOCKED |
| co_alarms | Same family | MULTI_EVIDENCE (target) | **§5.1** | **Critical** | PR, RS | BLOCKED |
| smoke_heat_alarms | Multi-mode in policy defaults; not canonical | MULTI_EVIDENCE | **§5.1** | **Critical** | PR, RS | BLOCKED |
| fire_risk_assessment | HMO_FIRE engine; overlaps with hmo fire | DOCUMENT_UPLOAD **or** MULTI_EVIDENCE | **§5.3** | High | PR, RS | BLOCKED |
| hmo_fire_risk | Multi-mode defaults | MULTI_EVIDENCE | Overlap with fire_risk_assessment | Med | PR, RS | BLOCKED |
| hmo_fire_risk_evidence | Same family as hmo_fire_risk | MULTI_EVIDENCE | Same | Med | PR, RS | BLOCKED |
| right_to_rent | Phase 1: `GUIDED_DECLARATION` workflow, structured check schema, supporting upload secondary, disclosure; audit if registry document-only | GUIDED_DECLARATION | Follow-up validation rules may tighten later | Low | PR, RS, EV, AU | ALLOWED* (Phase 1) |
| deposit_pi | Tenancy deposit family | GUIDED_DECLARATION **or** MULTI_EVIDENCE | **§5.4** jurisdiction | **Critical** | PR, Legal | BLOCKED |
| deposit_prescribed_info | Same family | GUIDED_DECLARATION **or** MULTI_EVIDENCE | **§5.4** | **Critical** | PR, Legal | BLOCKED |
| how_to_rent | Phase 1: `TENANT_DELIVERY` — structured delivery record + supporting upload; disclosure copy; audit if registry forces document-only | TENANT_DELIVERY | **§5.5** — Phase 1 subset implemented; broader programme items remain open | Med (legacy / overrides) | PR, RS, EV, AU | ALLOWED* (Phase 1) |
| tenancy_agreement | Obligation-style retention | GUIDED_DECLARATION **or** DOCUMENT_UPLOAD | Product choice | Med | PR | BLOCKED |
| occupation_contract | Wales | GUIDED_DECLARATION | None vs wales_occupation_contract | Low | PR | ALLOWED* |
| wales_occupation_contract | Wales | GUIDED_DECLARATION | Duplicate messaging vs occupation_contract | Low | PR | ALLOWED* |
| legionella | DOCUMENT engine | EXTERNAL_REMEDIATION_TRACKING **or** DOCUMENT_UPLOAD | **§5.6** | Med | PR, RS, Copy | BLOCKED |
| emergency_lighting | JOB execution | REMEDIATION_JOB | **§5.7** feedback loop | Med | OP, RS, SC | BLOCKED |
| fire_extinguisher | JOB execution | REMEDIATION_JOB | **§5.7** | Med | OP, RS | BLOCKED |
| communal_cleaning | JOB execution | REMEDIATION_JOB | **§5.7** | Med | OP, RS | BLOCKED |
| communal_fire_doors | JOB execution | REMEDIATION_JOB | **§5.7** | Med | OP, RS | BLOCKED |
| hmo_classification | SYSTEM | HIDDEN_SYSTEM **or** GUIDANCE_ONLY | **§5.8** | Low | PR, RS | BLOCKED |
| property_classification | SYSTEM | HIDDEN_SYSTEM **or** GUIDANCE_ONLY | **§5.8** | Low | PR, RS | BLOCKED |

\* **ALLOWED*** still requires §6 global gates (registry column / resolver tests / no production frontend fallback).

---

## 5. Blockers requiring owner approval

| ID | Topic | Decision required |
|----|--------|-------------------|
| **5.1** | **Smoke / heat / CO canonical consolidation** | Single canonical slug vs three slugs with identical class; fate of `smoke_heat_alarms` vs `smoke_alarms`/`co_alarms`; migration of historical rows. |
| **5.2** | **`fire_detection` vs smoke alarms** | Whether `fire_detection` remains pure DOCUMENT_UPLOAD or becomes MULTI_EVIDENCE when registry allows checklist/contractor; alias family behaviour under one class. |
| **5.3** | **`fire_risk_assessment` vs `hmo_fire_risk`** | Distinct obligations vs merged product narrative; avoid duplicate competing CTAs for same property. |
| **5.4** | **Deposit / prescribed information jurisdiction model** | Per-nation `client_workflow_class` and evidence modes (England vs Wales vs Scotland vs NI); legal review. |
| **5.5** | **How to Rent tenant delivery model** | **Phase 1 (narrow)** implemented: defaults + resolver + `TENANT_DELIVERY` class + structured schema + CTAs + audit flag for document-only published overrides. **Remaining:** tenant linkage, expanded proof types, or cross-border product scope beyond jurisdiction rules — require separate approval. |
| **5.6** | **Legionella: document vs external remediation tracking** | Pick primary class; forbid booking/scheduling language; align copy with EXTERNAL_REMEDIATION_TRACKING if chosen. |
| **5.7** | **Job-based requirements and compliance feedback loop** | Whether JOB slugs appear as requirement CTAs at all vs operations-only; how job completion links to evidence verification and score (no “job done = compliant” without evidence path). |
| **5.8** | **System classification visibility** | HIDDEN_SYSTEM vs GUIDANCE_ONLY for tenants; admin visibility only vs full hide. |

---

## 6. Implementation rules (preconditions)

No code may implement a proposed `client_workflow_class` until **all** applicable conditions hold:

1. **Decision approved** — relevant §5 rows cleared in writing (product + compliance/legal as needed).
2. **Registry / policy authority updated** — published or draft registry schema supports class + evidence modes without contradicting scoring applicability.
3. **Resolver behaviour tested** — `resolve_take_action_envelope` (+ enrich) emits **one** primary CTA and correct class; Stream D parity tests extended.
4. **Evidence modes validated** — `effective_evidence_resolution` and `client_compliance_evidence` routes reject disallowed modes; modal contracts match.
5. **Migration / alias handling defined** — normalization tables and backward compatibility for legacy slugs; no silent behaviour change without flag or migration note.
6. **No production frontend fallback** — client **must not** synthesize workflow from labels when `take_action` missing (disabled / error state + telemetry).

---

## 7. Tests required before implementation

| Category | Examples |
|----------|----------|
| **Alias normalization** | Every legacy alias → canonical code; alias families do not fork `client_workflow_class`. |
| **Resolver / CTA** | One primary per envelope; JOB secondary only when explicitly allowed; parity fixtures updated. |
| **Evidence mode** | POST rejected when mode ∉ policy; modal GET matches resolver. |
| **Jurisdiction gating** | Deposit / regional rows resolve correct class per portfolio/property jurisdiction. |
| **Migration safety** | Historical rows with old slug still resolve; snapshot tests for frozen requirement payloads. |
| **No frontend fallback** | Missing `take_action` → no navigate; production-safe UI state; logging assertions. |
| **Job vs compliance** | Job completion does **not** imply compliance satisfied unless evidence + verification path exists (integration or contract test). |

---

## 8. Document control

| Field | Value |
|-------|--------|
| **Owner** | Product leadership (primary); compliance architecture reviewer |
| **Reviewers** | Legal/compliance (deposit, R2R, How to Rent); platform architecture (resolver authority) |
| **Next action** | Schedule decision forum for §5 blockers; export live registry appendix if production codes exceed this inventory |

**Related programme docs:** `STREAM_D_CTA_PARITY_ENFORCEMENT.md`, `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md`, `PRODUCT_VALUE_GAP_TRACKER.md` (PVG-003, PVG-006 cross-references). Domestic alarm completeness semantics: **§2.6**.
