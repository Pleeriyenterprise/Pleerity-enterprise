# LIFECYCLE-COMMUNICATION-AUTHORITY-AUDIT-01

**Branch:** `develop` only  
**Date:** 2026-06-30  
**Mode:** Audit-only — no fixes, no template changes, no production  
**Evidence:** [`LIFECYCLE_COMMUNICATION_AUTHORITY_EVIDENCE.json`](./LIFECYCLE_COMMUNICATION_AUTHORITY_EVIDENCE.json)

---

## Executive verdict: **B**

**Communication authority is partially governed but fragmented. A shared Lifecycle Communication Authority should extend existing presentation authorities — not replace Lifecycle or Requirement Authority.**

Technical lifecycle decisions are authoritative (`lifecycle_semantics_resolver`, `client_requirement_lifecycle`, `reminder_truth_service`). Customer-facing wording is split across at least **nine parallel authorities** with inconsistent consumption. Most production reminder traffic still flows through **expiry-centric legacy templates** because `LIFECYCLE_AWARE_REMINDERS` defaults to `off`.

This is **not** verdict A (fully governed communication) because:
- Daily reminder emails/SMS for most tenants use `COMPLIANCE_EXPIRY_REMINDER` copy regardless of lifecycle family.
- Enablement assistant templates apply renewal/expiry language to non-expiry obligations.
- Frontend status chips (`evidenceStatus.js`) use expiry-biased labels instead of `client_lifecycle_label`.
- Monthly digest narrative reuses generic renewal/overdue framing across families.

This is **not** verdict C (greenfield rewrite) because strong foundations already exist:
- `lifecycle_reminder_template_registry` — family-aware reminder copy per `attention_kind`.
- `lifecycle_authority_copy` ↔ `lifecycleAuthorityCopy.js` — governed digest/calendar phrases.
- `requirement_action_resolver` ↔ `requirementTakeActionResolver.js` — unified Take Action CTAs.
- `presentation/label_service` + `domain_labels.json` — requirement naming SSOT.
- `email_presentation/` — email shell/greeting/colour (EPA programme, now on production).
- `todayPresentationAuthority.js` — Today banner/bucket semantics (separate from lifecycle copy).

---

## Objective

Determine whether every customer-facing communication **consumes** existing lifecycle authority correctly — not whether lifecycle rules are correct.

A landlord should immediately understand:

| Question | Required |
|----------|----------|
| **WHY** | Why am I being contacted? |
| **WHAT** | What do I need to do? |
| **WHEN** | When must it be completed? |
| **HOW** | How do I complete it? |
| **WHAT NEXT** | What happens after completion? |

---

## Communication Authority map

| Authority layer | Location | Scope | Consumes lifecycle authority? | Classification |
|-----------------|----------|-------|-------------------------------|----------------|
| **Lifecycle semantics (technical SSOT)** | `lifecycle_semantics_resolver.py`, `lifecycle_semantics_types.py` | `lifecycle_semantics`, `attention_kind`, dates | N/A — defines truth | NO_CHANGE_REQUIRED |
| **Client lifecycle labels** | `client_requirement_lifecycle.py` | `client_lifecycle_state`, `client_lifecycle_label` | Yes — projects truth | NO_CHANGE_REQUIRED |
| **Lifecycle reminder copy (governed)** | `lifecycle_reminder_template_registry.py` | Email/SMS per `attention_kind` (6 kinds) | Yes — when active | NO_CHANGE_REQUIRED (when active) |
| **Lifecycle authority copy (partial)** | `lifecycle_authority_copy.py` ↔ `lifecycleAuthorityCopy.js` | Digest suffixes, calendar sublines, count footnotes | Partial — digest only | AUTHORITY_DUPLICATION (FE has extra branches) |
| **Legacy expiry reminder** | `COMPLIANCE_EXPIRY_REMINDER` via `email_service.py`, `enablement_templates.py` | Default daily reminder path | No — expiry-centric | LEGACY_PRESENTATION |
| **Grouped reminder headings** | `email_service._build_grouped_reminder_sections_*` | Section headings in digest-style reminder emails | Partial — groups by bucket not attention_kind | MISLEADING_COMMUNICATION |
| **Enablement assistant** | `enablement_templates.py` | In-app/email enablement nudges | No — renewal/expiry for all | LIFECYCLE_MISMATCH |
| **Take Action CTAs** | `requirement_action_resolver.py` ↔ `requirementTakeActionResolver.js` | Portal surfaces (Today, Property Detail, Requirement modal) | Partial — evidence-mode aware; status-key overrides generic | WORDING_IMPROVEMENT |
| **Domain labels** | `presentation/label_service.py`, `domain_labels.json` | Requirement names, inbox titles | Names only — not action verbs | NO_CHANGE_REQUIRED |
| **Evidence status chips** | `frontend/src/utils/evidenceStatus.js` | Property Detail, lists | No — expiry-biased | COMMUNICATION_DRIFT |
| **Risk signal copy** | `risk_signal_service.py` `RECOMMENDED_ACTIONS` | Command Centre risk cards | Partial — certificate framing leaks | LIFECYCLE_MISMATCH |
| **Monthly digest narrative** | `monthly_digest_operational_intelligence.py` | Digest body, highlights | No — generic renewal/overdue | COMMUNICATION_DRIFT |
| **Today presentation** | `todayPresentationAuthority.js`, `today_projection_service.py` | Banner, lanes, counters | Operational bucket ≠ lifecycle family | COMMUNICATION_DRIFT (documented in TODAY-AUTHORITY-CONSISTENCY-01) |
| **Email presentation** | `email_presentation/` | Shell, greeting, colours, CTA styling | Presentation only — not lifecycle verbs | NO_CHANGE_REQUIRED |
| **Documents confirm** | `lifecycleAwareConfirm.js` | Upload confirm field labels | Date-field aware | NO_CHANGE_REQUIRED |
| **Navigation** | `requirement_action_links.py`, FE resolvers | Routes to evidence flows | Consumes action resolver | NO_CHANGE_REQUIRED |

Full inventory: evidence JSON `communication_authority_map`, `duplicate_wording_inventory`, `legacy_wording_inventory`.

---

## Lifecycle family communication matrix (summary)

Platform technical families (`lifecycle_semantics`) map to customer `attention_kind` for reminders. Audit scope families that are sub-types roll up as noted.

| Family | Attention kind / bucket | Primary action (governed verb) | Family-aware reminder (active mode) | Default production path | Cross-surface consistency |
|--------|-------------------------|----------------------------------|-------------------------------------|-------------------------|---------------------------|
| **EXPIRY_BASED** | `CERTIFICATE_EXPIRING` | Renew / Upload renewed certificate | Yes | Legacy expiry reminder | **Drift** — enablement + chips use expiry; registry correct when active |
| **LICENSING** | `CERTIFICATE_EXPIRING` (HMO etc.) | Renew licence / Upload renewed licence | Partial — registry uses "renewal" | Legacy "expires" wording | **Drift** — CTA specific in action resolver |
| **REGISTRATION** | `CERTIFICATE_EXPIRING` | Renew registration | Partial | Legacy expiry | **Drift** |
| **DECLARATION_BASED** | `declaration_reminders` group | Complete declaration | No dedicated attention_kind | Legacy + misleading group headings | **Mismatch** — expiry language on declarations |
| **TENANCY_LIFECYCLE** | `TENANCY_TERM_ENDING` | Upload agreement / Record milestone | Yes when active | Legacy | **Drift** |
| **OCCUPANCY_LIFECYCLE** | `OCCUPANCY_REVIEW_DUE` | Record occupancy verification | Yes when active | Legacy | **Drift** |
| **REVIEW_BASED** | `REVIEW_DUE` | Review | Yes when active | Legacy "renewal" in digest | **Drift** |
| **EVENT_BASED** | `EVENT_ACTION_REQUIRED` | Record event | Yes when active | Legacy | **Drift** |
| **DOCUMENT_EVIDENCE** | Evidence upload modes | Upload evidence | Via action resolver | Generic "Add compliance evidence" | **Partial** |
| **STRUCTURED_EVIDENCE** | Structured declaration mode | Submit compliance declaration | Via action resolver | OK when mode detected | **Partial** |
| **SELF_CERTIFIED** | Declaration variants | Complete declaration | No | Legacy expiry | **Mismatch** |
| **INSPECTION** | Inspection checklist mode | Arrange inspection / Complete checklist | Via action resolver + risk signals | Certificate inspection wording in risks | **Partial** |
| **ASSESSMENT** | `assessment_reminders` group | Complete assessment | Group heading only | Generic digest renewal | **Drift** |
| **OPERATIONAL** | `OPERATIONAL_ACTION_REQUIRED` | Resolve operational issue | Yes when active | Legacy "Compliance action required" fallback | **Drift** |

Full matrix: evidence JSON `lifecycle_family_matrix`.

---

## Surface matrix (summary)

| Surface | Primary wording authority | Consumes lifecycle authority? | Key gap |
|---------|---------------------------|-------------------------------|---------|
| **Daily reminder email** | Legacy `reminder` alias OR `lifecycle_reminder_template_registry` | Only when `LIFECYCLE_AWARE_REMINDERS=active` (default `off`) | Production uses expiry-centric path |
| **Daily reminder SMS** | Same dual path | Same | Generic "compliance item(s) need attention" in legacy |
| **Enablement emails** | `enablement_templates.py` | No | `requirement_expiring_soon` / `requirement_overdue` always renewal/expiry |
| **Monthly digest** | `monthly_digest_operational_intelligence.py` + `digest_action_line_suffix` | Partial — suffixes governed, body generic | "Renewal approaching" for all due-soon states |
| **Weekly digest** | Same assembly stack | Partial | Same renewal framing |
| **Executive report / PDF** | Report builders + label_service | Names OK; action narrative generic | Renewal/overdue aggregation |
| **Today page** | `todayPresentationAuthority.js` + `take_action` from API | Operational buckets, not lifecycle verbs | Banner "urgent" ≠ lifecycle family |
| **Command Centre** | Risk signals + KPI labels | Risk copy hardcoded | Certificate expiry framing on compliance risks |
| **Property Detail** | `evidenceStatus.js` + API labels | Chips ignore `client_lifecycle_label` | "Expiring soon" / "Overdue" for all |
| **Requirement Detail / modal** | `take_action` contract | Best — action resolver | Status-key override → generic CTA |
| **Compliance Score** | Score presentation authority | Recommendations lens separate | KPI recommendations not lifecycle-family aware |
| **Evidence Registry / Documents** | `lifecycleAwareConfirm.js` | Date-field aware | OK for upload confirm |
| **Portal notifications** | `notification_orchestrator` + templates | Template-dependent | Mixed legacy + lifecycle keys |
| **Admin / reminder previews** | Same as production render path | Mirrors production drift | Previews show legacy copy |
| **Issue / risk cards** | `risk_signal_service.py` | Hardcoded `RECOMMENDED_ACTIONS` | Certificate language on non-cert risks |

Full matrix: evidence JSON `surface_matrix`.

---

## Authority consumption matrix

| Consumer | Lifecycle Authority | Requirement Authority | Navigation Authority | Presentation Authority | Email Presentation Authority |
|----------|--------------------|-----------------------|----------------------|------------------------|------------------------------|
| `lifecycle_reminder_template_registry` | ✅ `attention_kind` | ✅ req name from truth | ✅ portal link | ❌ copy owned locally | ✅ via EmailService |
| `COMPLIANCE_EXPIRY_REMINDER` | ❌ assumes expiry | Partial | ✅ | ❌ local expiry copy | ✅ shell only |
| `enablement_templates` | ❌ | Partial name tokens | Partial | ❌ independent | Partial |
| `email_service` grouped sections | Partial bucket | ✅ row labels | ✅ | ❌ heading_map local | ✅ |
| `requirement_action_resolver` | Partial via evidence mode | ✅ | ✅ | ✅ labels | N/A |
| `evidenceStatus.js` | ❌ status enum | Partial | N/A | ❌ local chip map | N/A |
| `monthly_digest_operational_intelligence` | ❌ status strings | Partial counts | ✅ links | Partial suffix only | ✅ |
| `risk_signal_service` | ❌ rule-local | Partial | ✅ suggested actions | ❌ `RECOMMENDED_ACTIONS` | N/A |
| `client_requirement_lifecycle` | ✅ SSOT labels | ✅ | N/A | Emits labels | N/A |

**Violations:** Templates or UI modules that independently determine lifecycle action, evidence type, or customer verb without consuming `attention_kind` / `client_lifecycle_label` / `take_action`.

Full matrix: evidence JSON `authority_consumption_matrix`.

---

## Communication structure audit (WHY / WHAT / WHEN / HOW / WHAT NEXT)

| Channel | WHY | WHAT | WHEN | HOW | WHAT NEXT | Missing elements |
|---------|-----|------|------|-----|-----------|------------------|
| Lifecycle reminder (active) | ✅ `why_received` + intro | ✅ req name + action framing | ✅ `due_date` | ⚠️ portal CTA only | ❌ not stated | WHAT NEXT |
| Legacy expiry reminder | ⚠️ generic monitoring | ⚠️ "expires" / "renewal" | ✅ expiry_date | ⚠️ upload implied | ⚠️ "maintain compliance" | WHY specific to obligation type |
| Enablement expiring soon | ❌ "Heads up" | ⚠️ renewal implied | ✅ expiry_date | ❌ | ⚠️ vague | WHY for non-expiry items |
| Grouped reminder sections | ❌ section heading only | ⚠️ type label + semantic line | ⚠️ semantic line sometimes | ❌ | ❌ | WHY, HOW, WHAT NEXT |
| SMS (legacy) | ❌ | ❌ "need attention" | ❌ | ❌ link only | ❌ | All except link |
| SMS (lifecycle active) | ❌ | ⚠️ family noun in body | ❌ | ❌ link | ❌ | WHY, WHEN, HOW, WHAT NEXT |
| Monthly digest | ⚠️ portfolio summary | ⚠️ counts | ⚠️ implied | ⚠️ "review obligation dates" | ❌ | Family-specific WHAT/HOW |
| Today banner | ⚠️ "urgent item(s)" | ❌ | ❌ | ❌ hero only | ❌ | WHY, WHAT, WHEN for non-hero |
| Risk cards | ⚠️ risk type label | ✅ `recommended_action` | ❌ | ⚠️ suggested action codes | ❌ | WHEN, WHAT NEXT |
| Take Action CTA | From parent surface | ✅ primary label | From requirement dates | ✅ route | ❌ | WHAT NEXT on completion |
| Property Detail chips | ❌ | ❌ status only | ⚠️ implied by chip | ❌ | ❌ | WHY, HOW, WHAT NEXT |

Full matrix: evidence JSON `communication_structure_matrix`.

---

## Lifecycle verb matrix (summary)

| Family | Governed verb | Observed verbs (drift) | Issue |
|--------|---------------|------------------------|-------|
| EXPIRY_BASED | Renew | expires, renewal, overdue | OK in registry; legacy uses "expires" |
| LICENSING | Renew licence | renew certificate, upload certificate | Certificate wording on licences |
| REGISTRATION | Renew registration | renew, expires | Registration → expiry leakage |
| DECLARATION_BASED | Complete | renew, evidence required, upload | **Expiry leakage** |
| TENANCY_LIFECYCLE | Upload / Record | renewal, expires, milestone | Partial in registry |
| OCCUPANCY_LIFECYCLE | Record | review, overdue | OK in registry |
| REVIEW_BASED | Review | renewal, expires | **Review → renewal leakage** in digest |
| EVENT_BASED | Record | action required, expires | Generic "action" |
| DOCUMENT_EVIDENCE | Upload | add compliance evidence | Generic CTA |
| STRUCTURED_EVIDENCE | Submit declaration | upload, evidence | Mode-aware when detected |
| INSPECTION | Arrange / Complete | review certificate, schedule inspection | Cert wording in electrical risk |
| ASSESSMENT | Complete | renewal, review | Digest renewal framing |
| OPERATIONAL | Resolve | attention required, compliance action | Generic fallback |

Full matrix: evidence JSON `lifecycle_verb_matrix`.

---

## Heading matrix — misleading headings

| Heading | Location | May contain | Classification |
|---------|----------|-------------|----------------|
| **Certificates & Expiring Evidence** | `email_service._build_grouped_reminder_sections_*` | Licences, registrations, some non-cert expiry items | WORDING_IMPROVEMENT |
| **Declarations & Tenancy Records** | Same | Declarations, tenancy docs, occupancy | NO_CHANGE_REQUIRED (reasonable) |
| **Assessments & Reviews** | Same | Reviews, assessments, recommendations | WORDING_IMPROVEMENT if recommendations included |
| **Property Conditions & Remediation** | Same | Condition issues, remediation | NO_CHANGE_REQUIRED |
| **Other Compliance Actions** | Same | Operational, event-based, mixed | MISLEADING_COMMUNICATION (vague) |
| **Compliance renewal reminder** | `lifecycle_reminder_template_registry` CERTIFICATE_EXPIRING | Certificates only when attention correct | NO_CHANGE_REQUIRED |
| **Compliance review reminder** | REVIEW_DUE spec | Reviews | NO_CHANGE_REQUIRED |
| Enablement **requirement_expiring_soon** subject | `enablement_templates.py` | Any requirement type | LIFECYCLE_MISMATCH |

Fallback semantic lines when forbidden fragments detected (`_safe_reminder_semantic_line`) replace specific copy with group defaults — better than legal overclaim but still generic ("Compliance action required").

Full matrix: evidence JSON `heading_matrix`.

---

## CTA matrix (summary)

| Surface | Generic CTAs found | Lifecycle-specific CTAs | Classification |
|---------|---------------------|-------------------------|----------------|
| `requirement_action_resolver` | "Add compliance evidence" (fallback) | Upload Gas Safety, Submit declaration, Complete inspection checklist | WORDING_IMPROVEMENT on fallback |
| Customer status projector | "Add compliance evidence" for `action_required` | Overrides mode-specific labels | INCORRECT_CUSTOMER_ACTION when active |
| Email reminders | "View in portal" / settings link | No family-specific CTA text | WORDING_IMPROVEMENT |
| Risk suggested actions | Internal codes (`create_issue`) | UI maps separately | NO_CHANGE_REQUIRED (internal) |
| Enablement | "arrange renewal" | None per family | LIFECYCLE_MISMATCH |

Full matrix: evidence JSON `cta_matrix`.

---

## Reason wording matrix (summary)

| Pattern | Example | Acceptable? | Where violated |
|---------|---------|-------------|----------------|
| Specific expiry | "expires on {date}" | ✅ for EXPIRY_BASED | Used for all types in enablement |
| Specific review | "review due on {date}" | ✅ | Only in lifecycle registry (active) |
| Specific declaration | "declaration not completed" | ✅ | Not in legacy path |
| Vague | "Action required" | ❌ unless supported | `_safe_reminder_semantic_line` fallback, SMS legacy |
| Vague | "Compliance action required" | ❌ | `email_service.py` line 215 |
| Vague | "need attention" | ❌ | SMS bodies, enablement |
| Vague | "Issue detected" | ❌ | Not primary path but risk headlines can be generic |

Full matrix: evidence JSON `reason_wording_matrix`.

---

## Evidence wording matrix (summary)

| Family | Governed evidence phrase | Drift observed |
|--------|--------------------------|----------------|
| EXPIRY_BASED | Upload renewed certificate | OK in action resolver |
| DECLARATION_BASED | Record / submit declaration | "Evidence required", upload language |
| TENANCY_LIFECYCLE | Upload signed agreement | "renewal" in digest |
| INSPECTION | Upload inspection report | "Review electrical certificate" in risks |
| OPERATIONAL | Resolve / provide supporting evidence | "Compliance action required" |

Full matrix: evidence JSON `evidence_wording_matrix`.

---

## Duplicate wording inventory (high priority)

| Phrase domain | Authority A | Authority B | Drift risk |
|---------------|-------------|-------------|------------|
| Reminder intro/subject | `lifecycle_reminder_template_registry` | `enablement_templates` + legacy `COMPLIANCE_EXPIRY_REMINDER` | **High** — production default is B |
| Calendar overdue subline | `lifecycle_authority_copy.py` | `lifecycleAuthorityCopy.js` (+ FE-only PENDING_REVIEW branch) | Medium |
| Digest action suffix | `digest_action_line_suffix` | Inline digest body in `monthly_digest_operational_intelligence` | **High** |
| Primary CTA | `requirement_action_resolver` | `_CUSTOMER_STATUS_CTA_PRIMARY` when projector on | Medium |
| Status chip text | API `client_lifecycle_label` | `evidenceStatus.js` STATUS_CONFIG | **High** |
| Risk recommended action | `risk_signal_service.RECOMMENDED_ACTIONS` | FE `riskSignalPresentationHeadline` | Medium |
| Email greeting/shell | `email_presentation` | Legacy inline (mostly migrated) | Low post-EPA |

---

## Legacy wording inventory

| Legacy stack | Still reachable in production? | Notes |
|--------------|-------------------------------|-------|
| `COMPLIANCE_EXPIRY_REMINDER` | **Yes** — default when `LIFECYCLE_AWARE_REMINDERS=off` | Expiry-centric subject, intro, SMS |
| `enablement_templates` requirement_expiring/overdue | **Yes** | Independent renewal narrative |
| `email_service._safe_reminder_semantic_line` forbidden-fragment fallbacks | **Yes** | Generic replacements |
| `evidenceStatus.js` EXPIRING_SOON/OVERDUE chips | **Yes** | All surfaces using chips |
| `monthly_digest_operational_intelligence` renewal highlights | **Yes** | Portfolio-level generic copy |
| `risk_signal_service.RECOMMENDED_ACTIONS` | **Yes** | Hardcoded per risk_type |

---

## Classified findings (top 20)

| ID | Classification | Surface | Summary |
|----|----------------|---------|---------|
| LCA-001 | **AUTHORITY_DUPLICATION** | Reminders | Dual vocabulary: `lifecycle_reminder_template_registry` vs legacy `COMPLIANCE_EXPIRY_REMINDER` |
| LCA-002 | **LEGACY_PRESENTATION** | Reminders | `LIFECYCLE_AWARE_REMINDERS` default `off` — family-aware copy not production-authoritative |
| LCA-003 | **LIFECYCLE_MISMATCH** | Enablement | `requirement_expiring_soon` / `requirement_overdue` use expiry/renewal for all requirement types |
| LCA-004 | **MISLEADING_COMMUNICATION** | Reminder email | Heading "Certificates & Expiring Evidence" may include licences/registrations |
| LCA-005 | **MISLEADING_COMMUNICATION** | Reminder email | "Other Compliance Actions" — vague bucket |
| LCA-006 | **COMMUNICATION_DRIFT** | Property Detail | `evidenceStatus.js` ignores `client_lifecycle_label` |
| LCA-007 | **AUTHORITY_VIOLATION** | Property Detail | Chips independently determine customer status wording |
| LCA-008 | **COMMUNICATION_DRIFT** | FE/BE | `lifecycleAuthorityCopy.js` has branches not mirrored in backend |
| LCA-009 | **COMMUNICATION_DRIFT** | Monthly digest | Body uses generic renewal/overdue; suffixes only partially governed |
| LCA-010 | **LIFECYCLE_MISMATCH** | Monthly digest | "Renewal approaching" for non-expiry families |
| LCA-011 | **INCORRECT_CUSTOMER_ACTION** | Take Action | `_CUSTOMER_STATUS_CTA_PRIMARY` → "Add compliance evidence" overrides mode-specific CTAs |
| LCA-012 | **WORDING_IMPROVEMENT** | Take Action | Fallback `"Add compliance evidence"` too generic for governed verbs |
| LCA-013 | **LIFECYCLE_MISMATCH** | Risk cards | `RISK_TYPE_ELECTRICAL` recommended action uses certificate framing |
| LCA-014 | **LIFECYCLE_MISMATCH** | Risk cards | `RISK_TYPE_CERTIFICATE_EXPIRY_SOON` applied to non-cert semantics in comments |
| LCA-015 | **MISLEADING_COMMUNICATION** | Reminder semantic | Fallback "Compliance action required" lacks specific WHY |
| LCA-016 | **COMMUNICATION_DRIFT** | Today | Banner urgent count ≠ lifecycle family (see TODAY-AUTHORITY-CONSISTENCY-01) |
| LCA-017 | **WORDING_IMPROVEMENT** | SMS | Legacy SMS: "compliance item(s) need attention" — no WHY/WHAT/WHEN |
| LCA-018 | **LIFECYCLE_MISMATCH** | Declarations | Expiry/reminder path can reach declaration obligations |
| LCA-019 | **NO_CHANGE_REQUIRED** | Lifecycle registry | Six `attention_kind` specs are well-structured when active |
| LCA-020 | **NO_CHANGE_REQUIRED** | Email presentation | EPA governs shell; out of scope for lifecycle verbs |

Full findings list: evidence JSON `findings` (48 rows).

---

## Production impact

| Area | Current production behaviour | Landlord impact |
|------|---------------------------|-----------------|
| Daily reminders | Legacy expiry reminder path (`LIFECYCLE_AWARE_REMINDERS=off`) | Declarations, tenancy, operational items may read as certificate renewals |
| Enablement nudges | Expiry templates for milestone notifications | Misleading WHY/WHAT for non-expiry obligations |
| Portal status chips | Expiring soon / Overdue | Landlord may think all items are certificate/expiry problems |
| Monthly digest | Generic renewal narrative | Portfolio summary obscures family-specific actions |
| Command Centre risks | Certificate-oriented recommended actions | Electrical/operational risks framed as cert renewal |
| Today page | Urgent vs needs-action vocabulary split | Confusion about what needs landlord action (documented) |
| Take Action CTAs | Mostly correct when projector off; generic when on | Wrong CTA label for declarations/operational when projector active |

**EPA note:** Email shell, greeting, and colour authority was promoted to production (`30f816df`). This audit does not change EPA. Lifecycle **verb** authority remains separate.

---

## Risk assessment

| Risk | Severity | Likelihood | Mitigation direction (audit only) |
|------|----------|------------|-----------------------------------|
| Landlord renews wrong artifact (declaration treated as cert) | High | Medium | Single Lifecycle Communication Authority consuming `attention_kind` |
| Missed operational action due to vague SMS/email | Medium | Medium | Family-specific WHY/WHAT in all channels |
| Trust erosion from alarmist/vague copy | Medium | Medium | Ban unsupported "Action required" without reason |
| Compliance churn from inconsistent Today banner | Medium | Low–Medium | Align urgent copy with lifecycle verbs (separate programme) |
| Admin preview shows different copy than governed registry | Low | Medium | Preview uses same authority module as send path |

---

## Recommended implementation roadmap (no implementation in this programme)

### Phase 1 — Establish Lifecycle Communication Authority (LCA)

1. Create `lifecycle_communication/` module (mirror pattern of `email_presentation/`).
2. Single API: `resolve_customer_communication(requirement_row, surface, channel) → {why, what, when, how, what_next, cta_label, evidence_phrase, heading}`.
3. Consume: `attention_kind`, `client_lifecycle_label`, `take_action`, `lifecycle_reminder_spec`, `digest_action_line_suffix` — **no new lifecycle rules**.

### Phase 2 — Consolidate duplicate authorities

1. Route `enablement_templates` requirement nudges through LCA.
2. Deprecate legacy `COMPLIANCE_EXPIRY_REMINDER` copy; keep alias as thin wrapper.
3. Align `evidenceStatus.js` to prefer `client_lifecycle_label` with chip styling only.
4. Sync FE/BE `lifecycle_authority_copy` — single generated or validated pair.

### Phase 3 — Surface rollout (communication only)

1. Reminder email/SMS (after `LIFECYCLE_AWARE_REMINDERS` promotion decision).
2. Monthly/weekly digest body narrative.
3. Risk `RECOMMENDED_ACTIONS` → LCA lookups by `attention_kind` + risk_type.
4. Grouped reminder headings → LCA heading resolver.

### Phase 4 — Flag promotion & validation

1. Staging: `LIFECYCLE_AWARE_REMINDERS=active` with LCA-backed copy.
2. Cohort validation per lifecycle family (compare WHY/WHAT/WHEN across email, portal, digest).
3. Production promotion via cherry-pick (same pattern as EPA) — **not in this audit**.

**Explicitly out of scope for LCA programme:** reminder schedules, notification routing, scoring, requirement determination, navigation routes.

---

## Acceptance criteria

| Criterion | Answer |
|-----------|--------|
| Where communication authority currently exists | Partially — see Communication Authority map; strongest in `lifecycle_reminder_template_registry` (inactive by default), `requirement_action_resolver`, `lifecycle_authority_copy`, `label_service` |
| Which lifecycle families communicate correctly | **None end-to-end across all surfaces.** EXPIRY_BASED is closest when lifecycle-aware reminders are active. DECLARATION_BASED and OPERATIONAL have worst cross-surface drift. |
| Which communication surfaces drift | Reminders (legacy path), enablement, Property Detail chips, monthly digest body, risk cards, Today banner vocabulary |
| Which wording authorities are duplicated | Reminder copy (registry vs legacy vs enablement), status chips vs lifecycle labels, digest suffix vs body, FE/BE lifecycle copy |
| Which families require communication improvements | DECLARATION_BASED, OPERATIONAL, REVIEW_BASED, TENANCY_LIFECYCLE — all non-expiry families in production reminder path |
| Whether one shared Lifecycle Communication Authority should be introduced | **Yes — Verdict B.** Extend existing authorities; do not replace Lifecycle or Requirement Authority. |

---

## Related audits

- EMAIL-TEMPLATE-AUTHORITY-AUDIT-01 — template/shell duplication (verdict C → led to EPA)
- EMAIL-PRESENTATION-AUTHORITY-01 — implemented shell/greeting/colour (production `30f816df`)
- PRESENTATION-AUTHORITY-ALIGNMENT-01 — digest suffix governance
- TODAY-AUTHORITY-CONSISTENCY-01 — Today banner vs needs-action bucket
- AUTHORITATIVE-DATE-LIFECYCLE-ARCHITECTURE-AUDIT-01 — technical lifecycle SSOT

---

## Constraints observed

- No fixes implemented  
- No template modifications  
- No production changes  
- No merge to `main`  
- Lifecycle Authority, Requirement Authority, scoring, reminders, notification orchestration untouched  
