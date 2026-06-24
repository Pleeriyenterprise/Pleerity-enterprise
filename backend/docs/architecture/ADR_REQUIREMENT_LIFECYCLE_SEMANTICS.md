# ADR: Requirement Lifecycle Semantics

```yaml
---
Status: ACCEPTED
Authority Level: TIER_1
Date: 2026-06-02
Promoted From: REQUIREMENT-LIFECYCLE-ARCHITECTURE-DESIGN-01
Promotion Authority: PROMOTE-REQUIREMENT-LIFECYCLE-ADR-01
Deciders: Product, Platform Engineering, Compliance Architecture
Source Audits:
  - REQUIREMENT-AND-LIFECYCLE-NON-EXPIRY-AUDIT-01
  - REQUIREMENT_LIFECYCLE_ARCHITECTURE_DESIGN_01
Related:
  - backend/docs/WORKFLOW_BEHAVIOUR_GOVERNANCE.md
  - backend/docs/audit/REQUIREMENT_AND_LIFECYCLE_NON_EXPIRY_AUDIT_01.md
  - backend/docs/audit/REQUIREMENT_LIFECYCLE_ARCHITECTURE_DESIGN_01.md
  - backend/docs/GOVERNANCE_INDEX.md
Supersedes (partial):
  - Independent lifecycle inference from expiry_type, expects_expiry, supports_expiry_tracking, or get_effective_expiry_date alone
---
```

## Context

The platform models UK property compliance obligations through multiple overlapping signals: legacy catalog `expiry_type`, engine `expects_expiry`, planner `frequency_days`, workflow `supports_expiry_tracking`, and calendar helpers such as `get_effective_expiry_date`. These layers frequently disagree.

Audit **REQUIREMENT-AND-LIFECYCLE-NON-EXPIRY-AUDIT-01** found that tenancy, deposit, right-to-rent, declaration, and review-based obligations are **partially correct** in guided declaration flows but are **incorrectly swept** into certificate-expiry semantics when they acquire a `due_date`, document upload path, or daily reminder eligibility.

`WORKFLOW_BEHAVIOUR_GOVERNANCE.md` correctly governs **how evidence is captured** (`workflow_class`) but does not provide a single authority for **how dates, reminders, scoring, status, and dashboards behave** across non-certificate lifecycles.

Without a formal lifecycle authority, services independently infer expiry behaviour — producing modelling drift, reminder drift, scoring drift, and customer-language drift.

---

## Decision

**Establish `lifecycle_semantics` as the single authoritative dimension for lifecycle and date behaviour** across requirement obligations, resolved exclusively through a **Lifecycle Semantics Resolver**.

**Preserve `workflow_class` as the authoritative dimension for evidence capture mechanics only.** The two dimensions are **orthogonal** and must not be collapsed.

---

## Architectural rule (mandatory)

> **No service may independently determine lifecycle behaviour.**

All lifecycle decisions — including which date fields apply, whether expiry is required, which reminder template applies, which scoring penalties apply, which status vocabulary applies, and which dashboard KPI bucket applies — **must** be resolved through the **Lifecycle Semantics Resolver** from published registry data (`lifecycle_semantics`, `field_contract`) with documented governance fallbacks.

**Forbidden patterns after adoption:**

- Calling `get_effective_expiry_date` to drive reminders, KPIs, or penalties without resolver mediation  
- Inferring certificate expiry from `workflow_class` alone  
- Writing `confirmed_expiry_date` for non-`EXPIRY_BASED` semantics  
- Applying missing-expiry penalties without `field_contract.requires_expiry_date=true`  
- Routing declaration or event obligations into certificate-expiry reminder pipelines  

Legacy fields (`expiry_type`, `expects_expiry`, `supports_expiry_tracking`) may remain as **resolver inputs** during migration but **must not** remain parallel authorities.

---

## Separation of concerns

| Dimension | Governs | Examples | Authority |
|-----------|---------|----------|-----------|
| **`workflow_class`** | *How* evidence is captured | `DOCUMENT_UPLOAD`, `GUIDED_DECLARATION`, `EXTERNAL_ASSESSMENT_EVIDENCE`, `TENANT_DELIVERY` | `WORKFLOW_BEHAVIOUR_GOVERNANCE.md`, published registry `evidence_resolution`, resolver |
| **`lifecycle_semantics`** | *How* dates, reminders, scoring, status, and dashboards behave | `EXPIRY_BASED`, `REVIEW_BASED`, `TENANCY_LIFECYCLE` | **This ADR**, published registry, Lifecycle Semantics Resolver |
| **`evidence_mode`** | *Which* capture path the user took | upload, structured declaration, checklist | Evidence authority, capture UX |
| **`attention_kind`** | *Why* the user is being nudged | `CERTIFICATE_EXPIRING`, `REVIEW_DUE`, `TERM_ENDING` | Resolver output; consumed by reminders, gaps, KPIs |

**Example:** A tenancy agreement uses `workflow_class=GUIDED_DECLARATION` (capture) and `lifecycle_semantics=TENANCY_LIFECYCLE` (calendar and language). It must **not** use `EXPIRY_BASED` semantics because a document was uploaded.

---

## Definitions

### `lifecycle_semantics`

Normative enum defining **calendar and lifecycle meaning** for a requirement obligation. Published per requirement in the registry. Resolved by the Lifecycle Semantics Resolver.

| Value | Meaning | Certificate expiry applies |
|-------|---------|---------------------------|
| `EXPIRY_BASED` | Valid-until date governs renewal (Gas, EICR, EPC, licences) | **Yes** |
| `REVIEW_BASED` | Assessment on file; review / next-review drives attention | **No** (unless explicit hybrid flag) |
| `EVENT_BASED` | Dated events (served, delivered, checked) | **No** |
| `ONE_TIME` | Record once; no periodic renewal | **No** |
| `DECLARATION_BASED` | Structured declaration is proof of process | **No** |
| `TENANCY_LIFECYCLE` | Agreement term, renewal decision, onboarding | **No** |
| `OCCUPANCY_LIFECYCLE` | Occupancy checks, follow-ups, occupation contracts | **No** |
| `OPERATIONAL_WORKFLOW` | Jobs, maintenance, condition standards | **No** |

### `attention_kind`

Resolver-derived classification of **why** a requirement appears in attention surfaces (reminders, Today, Command Centre, digest). Drives template selection and customer language. Examples:

| `attention_kind` | Typical trigger date | Must not use certificate-expiry language |
|------------------|---------------------|------------------------------------------|
| `CERTIFICATE_EXPIRING` / `CERTIFICATE_OVERDUE` | `confirmed_expiry_date` | — (cert context only) |
| `REVIEW_DUE` | `next_review_date` | **Yes** |
| `TERM_ENDING` | `fixed_term_end_date` | **Yes** |
| `FOLLOW_UP_DUE` | `follow_up_date` | **Yes** |
| `ACTION_REQUIRED` | unsatisfied obligation | **Yes** |
| `OPERATIONAL_DUE` | job / maintenance due | **Yes** |

### `field_contract`

Machine-readable registry object defining **which date and metadata fields are required, optional, or forbidden** for a requirement. Consumed by extraction, confirmation, evidence authority, scoring, and date authority.

```yaml
field_contract:
  requires_expiry_date: bool       # certificate expiry only — EXPIRY_BASED
  requires_issue_date: bool
  requires_review_date: bool
  requires_next_review_date: bool
  requires_event_date: bool
  requires_tenancy_dates: bool
  requires_occupancy_dates: bool
  allows_estimated_expiry: bool
  does_not_expire: bool
```

`field_contract` is the **only** authority for whether missing expiry may penalise score or block satisfaction.

### Lifecycle Semantics Resolver

**Target module:** `services/lifecycle_semantics_resolver.py` (not yet implemented).

**Responsibilities:**

1. **Resolve** `lifecycle_semantics` and `field_contract` for a requirement row (registry → governance fallback → legacy map).  
2. **Produce** `attention_kind` and `effective_attention_date` from canonical date fields — not from overloaded `due_date` alone.  
3. **Expose** `vocabulary_family` for presentation layers.  
4. **Gate** downstream consumers: reminders, scoring penalties, status projector, gap engine, dashboards, reports, extraction profiles, confirmation contracts.  
5. **Shadow-log** divergence from legacy paths during migration (feature-flagged).  
6. **Reject** writes of `confirmed_expiry_date` when `field_contract.requires_expiry_date=false`.

**Precedence (aligned with workflow governance):**

1. Published registry (`lifecycle_semantics`, `field_contract`)  
2. Workflow behaviour governance fallbacks  
3. Legacy `expiry_type` / `expects_expiry` mapping (migration only)  
4. Code defaults (last resort; must be logged)

**Non-responsibilities:** The resolver does **not** replace `workflow_class` capture rules, evidence authority satisfaction logic, or `recalculate_and_persist` as the score write authority.

---

## Mandatory behavioural constraints

The following are **normative** under this ADR:

| # | Constraint |
|---|------------|
| 1 | **Tenancy end date must never map to `confirmed_expiry_date`.** `fixed_term_end_date` lives in structured tenancy payload or dedicated tenancy date fields. |
| 2 | **Declaration dates must never be treated as certificate expiry dates.** |
| 3 | **Event dates must never be treated as certificate expiry dates.** |
| 4 | **Declaration and event workflows must not enter certificate-expiry reminder pipelines** unless `lifecycle_semantics=EXPIRY_BASED` and `field_contract.requires_expiry_date=true`. |
| 5 | **Missing expiry penalties apply only where `field_contract.requires_expiry_date=true`.** |
| 6 | **Extraction profiles must be lifecycle-aware** — keyed by `extraction_profile_id` and `lifecycle_semantics`; no global schema requiring `expiry_date` for all types. |
| 7 | **Confirmation screens must be lifecycle-aware** — driven by `field_contract` and resolver output, not a single expiry-centric modal. |
| 8 | **Reminders must be lifecycle-aware** — eligibility, template, and wording branch on `attention_kind`. |
| 9 | **Dashboards must be lifecycle-aware** — KPIs aggregate by `attention_kind`, not a monolithic `expiring_soon` bucket for all obligations. |
| 10 | **Scoring must be lifecycle-aware** — penalty terms gated on `field_contract`; legacy `due_date` must not produce certificate-style EXPIRING_SOON fractions for non-expiry semantics. |

---

## Lifecycle-aware system requirements

| System | Must be lifecycle-aware | Resolver consumption |
|--------|-------------------------|----------------------|
| **Extraction** | Yes — profile per lifecycle; optional per requirement | `extraction_profile_id`, `field_contract` |
| **Confirmation** | Yes — required/forbidden fields per contract | `field_contract`, `does_not_expire` |
| **Reminders** | Yes — template family per `attention_kind` | `attention_kind`, `effective_attention_date` |
| **Scoring** | Yes — expiry penalty gate | `requires_expiry_date` |
| **Status / projector** | Yes — vocabulary per `vocabulary_family` | `lifecycle_semantics`, `attention_kind` |
| **Dashboards / KPIs** | Yes — split buckets | `attention_kind` aggregates |
| **Gap engine / Today** | Yes — action types per `attention_kind` | not `certificate_expiring_soon` for all |
| **Reports / digest** | Yes — section language per semantics | `vocabulary_family` |

**AI extraction eligibility:** Not all requirements support AI extraction. AI is permitted only where `DOCUMENT_UPLOAD` is an allowed evidence mode **and** a registered `extraction_profile_id` exists. Declaration-primary, operational, and PII-sensitive obligations (e.g. right-to-rent) must not depend on AI for primary closure.

---

## Consequences

### Positive

- Single lifecycle authority eliminates cross-layer drift documented in NON-EXPIRY-AUDIT-01  
- Tenancy, occupancy, and declaration obligations stop masquerading as expiring certificates  
- Customer language, reminders, and KPIs align with legal/commercial meaning  
- Migration can proceed in phases behind feature flags without big-bang rewrite  

### Negative

- Registry backfill required for all published requirements  
- Resolver becomes a hard dependency for new compliance surfaces  
- Short-term dual-read (legacy + resolver shadow) adds operational complexity  

### Risks mitigated

| Risk | Mitigation |
|------|------------|
| Tenancy term → cert expiry | `field_contract` + resolver write guards |
| Declaration → renewal email | `attention_kind` template routing |
| Score penalty on non-certs | `requires_expiry_date` gate |
| New service drift | Architectural rule + CI governance consumption |

---

## Implementation status

| Item | Status |
|------|--------|
| ADR accepted | **ACCEPTED** (documentation) |
| Lifecycle Semantics Resolver | **Not implemented** |
| Registry `lifecycle_semantics` fields | **Not implemented** |
| Remediation authority | **REQUIREMENT-LIFECYCLE-NON-EXPIRY-REMEDIATION-01** (pending) |

**No runtime behaviour changes are authorised by this ADR alone.** Implementation requires a separate remediation authority and phased rollout under **INITIATIVE-REQUIREMENT-LIFECYCLE-SEMANTICS** (see Appendix B).

---

## Status

**ACCEPTED** — 2026-06-02 via PROMOTE-REQUIREMENT-LIFECYCLE-ADR-01.

---

# Appendix A — Governance impact assessment

**Scope:** Documents that should be updated to align with this ADR. **No updates performed in this promotion.**

## A.1 Requirement governance

| Document path | Reason for update | Proposed change summary |
|---------------|-------------------|-------------------------|
| `backend/docs/WORKFLOW_BEHAVIOUR_GOVERNANCE.md` | Defines `workflow_class` only; `supports_expiry_tracking` incorrectly implies cert expiry for declarations | Add § **Lifecycle semantics vs workflow class**; defer calendar behaviour to ADR; clarify `supports_expiry_tracking` is subordinate to `field_contract` |
| `backend/docs/REQUIREMENT_WORKFLOW_CLASS_DECISION_RECORD.md` (if present) | Per-code workflow decisions lack lifecycle dimension | Add `lifecycle_semantics` column to decision table; reference ADR for date behaviour |
| `backend/services/workflow_behaviour_governance.py` | Code mirror of workflow governance | Add read-only lifecycle fallback map consumed only by resolver; mark `supports_expiry_tracking` as non-authoritative for penalties/reminders |

## A.2 Registry governance

| Document path | Reason for update | Proposed change summary |
|---------------|-------------------|-------------------------|
| `backend/docs/PUBLISHED_REGISTRY_CLIENT_TRUTH_AUDIT.md` | Registry truth model lacks lifecycle fields | Document `lifecycle_semantics`, `field_contract`, `extraction_profile_id` as published fields |
| `backend/docs/compliance_registry_publish_service.py` (docstring) | Publish contract silent on lifecycle | State publish must include lifecycle fields or explicit fallback to resolver map |
| `backend/docs/audit/REGISTRY_WORKFLOW_DRIFT_AUDIT.md` | Drift audit workflow-only | Extend drift checks: registry `lifecycle_semantics` vs legacy `expiry_type` / `expects_expiry` |

## A.3 Reminder governance

| Document path | Reason for update | Proposed change summary |
|---------------|-------------------|-------------------------|
| `backend/docs/audit/NOTIFICATION_GOVERNANCE_INVENTORY.json` | Reminders tagged UNGOVERNED in consumption map | Add `attention_kind` routing; split `COMPLIANCE_EXPIRY_REMINDER` from lifecycle templates |
| `backend/docs/NOTIFICATION_TEMPLATE_MATRIX.md` | Template matrix certificate-centric | Add template families: `compliance_review`, `tenancy_lifecycle`, `occupancy_lifecycle`, `obligation_action` |
| `backend/docs/runbooks/SCHEDULER_AND_COMPLIANCE_JOBS.md` | Daily reminders job undocumented lifecycle gate | Document resolver eligibility before `send_daily_reminders` |
| `backend/docs/NOTIFICATION_SEND_INVENTORY.md` | Send inventory lists COMPLIANCE_EXPIRY_REMINDER globally | Annotate lifecycle applicability per template |

## A.4 Scoring governance

| Document path | Reason for update | Proposed change summary |
|---------------|-------------------|-------------------------|
| `backend/docs/STREAM_B_SCORING_AUTHORITY_MATRIX.md` | Penalty paths not lifecycle-gated | Add rows: missing expiry penalty → `requires_expiry_date`; legacy `due_date` fraction rules |
| `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | KPI projection uses expiry-adjacent buckets | Split KPI authority: `attention_kind` buckets; deprecate monolithic `expiring_soon` semantics |
| `docs/governance/TRUST_LANGUAGE_GOVERNANCE.md` | Score explanations may imply cert expiry | Align trust copy with lifecycle semantics for non-cert obligations |

## A.5 Extraction governance

| Document path | Reason for update | Proposed change summary |
|---------------|-------------------|-------------------------|
| `backend/services/ai_provider.py` (module docstring / future `extraction_profiles.md`) | Single `EXTRACTION_SCHEMA` with mandatory `expiry_date` | Document profile registry; EXTRACTED rules per lifecycle |
| `backend/docs/GOVERNANCE_CONSUMPTION_MAP.md` | Extraction not listed; reminders UNGOVERNED | Add extraction + confirmation surfaces; mark reminder UNGOVERNED → PARTIALLY_GOVERNED after remediation |
| `backend/docs/audit/apply_extraction` related audits | Confirm flow drift | Cross-link ADR as target authority for confirm field requirements |

## A.6 Dashboard / KPI governance

| Document path | Reason for update | Proposed change summary |
|---------------|-------------------|-------------------------|
| `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | Dashboard KPI definitions | Define split KPIs: certificates expiring / reviews due / terms ending / actions required |
| `backend/docs/launch/PILOT_LAUNCH_GOVERNANCE.md` | Launch acceptance may reference expiring counts | Update acceptance criteria to lifecycle-aware KPI language |
| `backend/scripts/dashboard_score_widget_semantic_convergence_01.py` (audit artefact) | Documents `due_date_source` as expiry | Reference resolver `effective_attention_date` as target |

## A.7 Customer language governance

| Document path | Reason for update | Proposed change summary |
|---------------|-------------------|-------------------------|
| `docs/governance/PRESENTATION_LANGUAGE_GOVERNANCE.md` | Global "Renewal approaching" / expiring copy | Add `vocabulary_family` bundles; forbid cert expiry phrases for non-`EXPIRY_BASED` |
| `docs/governance/REVIEW_POLICY_VOCABULARY.md` | Obligation badge vocabulary | Add lifecycle-specific status phrases: review due, term ending, recorded on file |
| `docs/governance/CUSTOMER_STATUS_VOCABULARY.json` | Machine-readable status enum | Add `attention_kind` vocabulary mappings; retire misleading expiry labels for declarations |
| `backend/docs/audit/SEMANTIC_COPY_REMEDIATION_PHASE4.json` | Copy remediation plan | Reference ADR as authority for lifecycle copy splits |

## A.8 Routing index (meta-governance)

| Document path | Reason for update | Proposed change summary |
|---------------|-------------------|-------------------------|
| `backend/docs/GOVERNANCE_INDEX.md` | No route for lifecycle semantics | Add TIER_1 row: **Requirement lifecycle semantics** → this ADR + resolver module |
| `backend/docs/GOVERNANCE_CONSUMPTION_MAP.md` | Consumption inventory incomplete | Add resolver consumers; update reminder/gap/scoring tags post-remediation |

---

# Appendix B — Implementation tracker impact assessment

**Scope:** Trackers and programmes that should reference this ADR. **No tracker updates performed in this promotion.**

## B.1 Trackers requiring reference

| Tracker path | Recommended update | Dependency relationship |
|--------------|-------------------|-------------------------|
| `backend/docs/CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` | Add **Programme H — Lifecycle semantics** (or Stream G extension) with phases 0–7 mirroring ADR migration | **Depends on** ADR; **blocks** accurate Stream B KPI alignment and Stream F audit vocabulary |
| `backend/docs/launch/LAUNCH_AUTHORITY_TRACKER.md` | Add launch item **L-LIFECYCLE-001** — lifecycle resolver shadow + staging validation gate | **Depends on** ADR; **related to** L-008 notifications |
| `backend/docs/PRODUCT_VALUE_GAP_TRACKER.md` | Note customer-language drift closure under lifecycle initiative | Informational cross-link |
| `docs/trackers/DISCOVERY_PHASE_1_IMPLEMENTATION_TRACKER.md` | No direct change | **Independent** — no dependency |
| `backend/docs/audit/governance_continuity_audit_02/TRACKER_UPDATE_RECOMMENDATIONS.md` | Add ADR to continuity map | Meta cross-link |

## B.2 Recommended initiative

### INITIATIVE-REQUIREMENT-LIFECYCLE-SEMANTICS

**Purpose:** Phased rollout of lifecycle semantics resolver and lifecycle-aware consumers.

**Suggested home:** New section in `CLOSED_LOOP_COMPLIANCE_ARCHITECTURE_TRACKER.md` **or** dedicated `backend/docs/trackers/INITIATIVE_REQUIREMENT_LIFECYCLE_SEMANTICS.md` (create on first remediation PR only — per GOVERNANCE_INDEX “extend before create”).

| Phase | Name | Deliverable | Feature flag |
|-------|------|-------------|--------------|
| 0 | ADR promotion | This document | — |
| 1 | Resolver + registry backfill | `lifecycle_semantics_resolver.py`, registry fields, shadow logging | `LIFECYCLE_SEMANTICS_SHADOW` |
| 2 | Confirm + extraction | Lifecycle-aware profiles + confirm API | `LIFECYCLE_AWARE_CONFIRM` |
| 3 | Scoring gates | Penalty eligibility via `field_contract` | `LIFECYCLE_AWARE_SCORING` |
| 4 | Reminders + gaps | `attention_kind` templates | `LIFECYCLE_AWARE_REMINDERS` |
| 5 | Dashboard KPIs | Split widgets | `LIFECYCLE_AWARE_KPIS` |
| 6 | Reports + digest | Section language | — |
| 7 | Legacy deprecation | Remove independent expiry inference | — |

**Remediation authority:** `REQUIREMENT-LIFECYCLE-NON-EXPIRY-REMEDIATION-01` implements phases 1–3 initially.

**Staging gate:** Scenarios A–I from `REQUIREMENT_AND_LIFECYCLE_NON_EXPIRY_AUDIT_01.md` §10 before phase 4 production consideration.

---

# Appendix C — Future implementation dependencies

**Scope:** Prerequisites for `REQUIREMENT-LIFECYCLE-NON-EXPIRY-REMEDIATION-01` phases 1–3. **No remediation implemented.**

## C.1 Phase 1 — Resolver + registry backfill

**Goal:** Establish read-only lifecycle authority with shadow logging.

| Prerequisite | Type | Notes |
|--------------|------|-------|
| ADR ACCEPTED | Governance | This document |
| Requirement inventory from NON-EXPIRY-AUDIT-01 §1.2 | Data | Backfill source mapping |
| Published registry publish path stable | Platform | `compliance_registry_publish_service.py` |
| Governance precedence documented | Governance | ADR § Lifecycle Semantics Resolver precedence |
| Legacy map: `expiry_type` → `lifecycle_semantics` | Design | See design doc §10.2 |
| Legacy map: `expects_expiry` → `field_contract.requires_expiry_date` | Design | One-to-one for cert types only |
| CI: resolver unit tests with golden fixtures per semantics | Engineering | Gas, legionella, tenancy, deposit |
| Feature flag infrastructure | Platform | `LIFECYCLE_SEMANTICS_SHADOW` |
| Shadow log sink | Observability | Divergence report without behaviour change |

**Phase 1 outputs (required before Phase 2):**

- `lifecycle_semantics_resolver.py` with `resolve(requirement_row) -> ResolvedLifecycle`  
- Registry schema extension (or governance patch file) for all in-scope requirement codes  
- Shadow log &lt;1% unresolved requirements on staging sample  

**Phase 1 must not:** Change reminder sends, scoring fractions, or confirm UI validation.

## C.2 Phase 2 — Confirmation + extraction

**Goal:** Lifecycle-aware capture surfaces.

| Prerequisite | Type | Notes |
|--------------|------|-------|
| Phase 1 complete | Initiative | Resolver returns stable `field_contract` |
| Registry backfill for top drift codes | Data | tenancy_agreement, deposit_pi, right_to_rent, smoke_heat_alarms, legionella |
| `extraction_profiles` design | Engineering | certificate_standard_v1, tenancy_agreement_v1, supporting_document_v1 |
| Confirm contract API spec | API | Backend exposes `confirm_fields` / `forbidden_fields` |
| Frontend `LifecycleAwareConfirm` plan | UX | Replace expiry-required path in `DocumentsPage.js` |
| `requirement_evidence_authority` integration point | Code anchor | Gate `expiry_confirmation_required` via resolver |
| Automated tests from audit §10.3 | QA | Extend satisfaction + evidence safety tests |
| Feature flag | Platform | `LIFECYCLE_AWARE_CONFIRM` |

**Phase 2 outputs (required before Phase 3):**

- Extraction EXTRACTED rules no longer require `expiry_date` for non-EXPIRY_BASED profiles  
- Confirm modal rejects `confirmed_expiry_date` when forbidden  
- Staging: gas requires expiry; smoke/heat does not force fake expiry  

**Phase 2 must not:** Change daily reminder subjects or dashboard KPI counts.

## C.3 Phase 3 — Scoring gates

**Goal:** Lifecycle-aware penalty eligibility.

| Prerequisite | Type | Notes |
|--------------|------|-------|
| Phase 1 complete | Initiative | `requires_expiry_date` available at score time |
| Phase 2 recommended | Initiative | Confirm path stops writing erroneous expiry on non-certs |
| `compliance_scoring_v2.py` penalty call sites inventoried | Engineering | STREAM_B matrix rows |
| `requirement_satisfaction_service.py` attention suppression rules | Engineering | Extend `legacy_due_date_blocks_renewal_attention` pattern |
| `customer_status_projector_v2.py` vocabulary | Engineering | `EXPIRY_DATE_NEEDED` only when resolver allows |
| KPI surface inventory | Engineering | `requirement_client_runtime_surface.py` |
| Regression tests: gas missing expiry → 0.5; legionella satisfied → ≥0.8 | QA | From audit proxy evidence |
| Feature flag | Platform | `LIFECYCLE_AWARE_SCORING` |
| Batch recalc runbook | Ops | Recompute scores after gate change on staging |

**Phase 3 outputs (required before Phase 4 reminders):**

- Missing expiry penalty only when `requires_expiry_date=true`  
- Legacy `due_date` cannot EXPIRING_SOON non-expiry semantics  
- KPI missing-expiry label split or gated  

**Phase 3 must not:** Enable new reminder templates (Phase 4).

## C.4 Cross-phase dependency graph

```
ADR (Phase 0)
    └── Phase 1: Resolver + registry backfill
            ├── Phase 2: Confirm + extraction (requires Phase 1)
            └── Phase 3: Scoring gates (requires Phase 1; best after Phase 2)
                    └── Phase 4+: Reminders, KPIs, reports (remediation authority extension)
```

**Parallel work allowed:** Phase 2 frontend confirm component can be built against mock resolver API while Phase 1 shadow logging runs on staging.

**Blocked until Phase 3 complete:** Changing production reminder eligibility or email subjects for tenancy/declaration types.

---

*End of ADR_REQUIREMENT_LIFECYCLE_SEMANTICS — promoted via PROMOTE-REQUIREMENT-LIFECYCLE-ADR-01.*
