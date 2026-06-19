# Discovery Approval & Import Governance Freeze — 01

```yaml
---
Status: ACTIVE
Authority Level: TIER_1
Programme: DISCOVERY-APPROVAL-IMPORT-GOVERNANCE-FREEZE-01
Related:
  - docs/DISCOVERY_FOUNDATION_ARCHITECTURE.md
  - docs/trackers/DISCOVERY_PHASE_1_IMPLEMENTATION_TRACKER.md
  - docs/launch/DISCOVERY_PHASE_1_LAUNCH_GATE.md
  - docs/contracts/DISCOVERY_PROVIDER_PROTOCOL.md
  - docs/adr/ADR_DISCOVERY_PROVIDER_NEUTRAL_ARCHITECTURE.md
  - docs/adr/ADR_DISCOVERY_RETENTION_AND_ERASURE.md
  - docs/governance/DISCOVERY_COMPLIANCE_AND_CONSENT.md
Source Design: STAGE-NOP-APPROVAL-IMPORT-BOUNDARY-AUTHORITY-01
Last Review: 2026-06-18
Branch: develop / staging only — no production
Scope: Governance documentation only — no code, schema, routes, or UI
---
```

## 1. Purpose

Freeze governance prerequisites required **before Stage N (Approval Queue)** implementation begins.

This document is behavioural authority for:

- Frozen audit events (approval + import sub-workflow)
- `request_changes` reviewer semantics
- Reviewer attribution requirements
- Import workflow stages and eligibility
- CRM protection rules

**Code sync:** Enum and service enforcement deferred to Stages N and P. This freeze is documentation authority until implementation.

---

## 2. Frozen audit events (taxonomy extension)

The following events are **frozen** and added to the Phase 1 audit taxonomy. They must be added to `discovery_models.py` frozen enums during Stage N/P implementation — not before.

### 2.1 Event catalogue

| Event | Phase | Meaning | Actor required |
|-------|-------|---------|----------------|
| `PROSPECT_REVIEWED` | 1 | Reviewer records review activity without approve/reject — including `request_changes` | Yes |
| `IMPORT_REQUESTED` | 1 | Import workflow initiated for an approved prospect | Yes |
| `IMPORT_VALIDATED` | 1 | Import eligibility validation passed; CRM write may proceed | Yes or `system` |
| `IMPORT_BLOCKED` | 1 | Import validation failed **before** any `LeadService` call | Yes or `system` |

**Existing events (unchanged):** `PROSPECT_APPROVED`, `PROSPECT_REJECTED`, `PROSPECT_IMPORTED`, `IMPORT_FAILED`, `DUPLICATE_DETECTED`, `DUPLICATE_OVERRIDDEN`.

### 2.2 Payload expectations (sanitised — no raw PII dumps)

| Event | Required payload fields | Optional fields |
|-------|-------------------------|-----------------|
| `PROSPECT_REVIEWED` | `review_status` (before/after), `action` | `change_request_notes`, `review_decision_id` |
| `IMPORT_REQUESTED` | `prospect_id`, `import_decision_id` | `reviewer_id` echo |
| `IMPORT_VALIDATED` | `eligibility_checklist` (boolean map), `prospect_id` | `content_hash`, `duplicate_status_at_validation` |
| `IMPORT_BLOCKED` | `failure_code`, `failure_message` (no PII) | `eligibility_checklist`, `blocked_reason` |
| `PROSPECT_IMPORTED` | `imported_lead_id`, `source_metadata_version` | `quality_snapshot` reference |

### 2.3 Retention requirements

- All events: append-only in `discovery_audit_logs`; never update or delete (ADR retention)
- Duplicate evidence: frozen snapshot referenced or embedded at `DUPLICATE_DETECTED`, `DUPLICATE_OVERRIDDEN`, and import validation — never regenerated
- Provenance: `origin_lineage` copied to lead at `PROSPECT_IMPORTED`; audit retains prospect_id + hash references only
- Hot retention: 24 months minimum per `DISCOVERY_COMPLIANCE_AND_CONSENT.md` §10

### 2.4 Governance violation

Emitting a frozen event type not in taxonomy, or emitting without required actor when mandated, is a **governance violation** and launch-gate NO-GO.

---

## 3. `request_changes` governance

### 3.1 Decision semantics (frozen)

| Rule | Requirement |
|------|-------------|
| New review status | **No** — does not create a new enum value |
| Resulting status | `needs_review` |
| Required input | `change_request_notes` (non-empty) |
| Audit event | `PROSPECT_REVIEWED` |
| Duplicate classification | **Unchanged** |
| Import eligibility | **Unchanged** (remains not eligible unless already `approved`) |
| CRM interaction | **None** |

### 3.2 Allowed from states

- `needs_review`
- `duplicate_detected` (returns to `needs_review` with notes; does not clear duplicate without `clear_duplicate`)

### 3.3 Prohibited

- Using `request_changes` to bypass duplicate override governance
- Using `request_changes` to imply approval or import eligibility

---

## 4. Reviewer attribution governance

### 4.1 Actions requiring actor attribution

| Action | Audit event(s) | `actor_id` | `actor_email` | `timestamp` |
|--------|----------------|------------|---------------|-------------|
| `approve` | `PROSPECT_APPROVED` | Required | Required | Required |
| `reject` | `PROSPECT_REJECTED` | Required | Required | Required |
| `request_changes` | `PROSPECT_REVIEWED` | Required | Required | Required |
| `mark_duplicate` | `DUPLICATE_DETECTED` | Required | Required | Required |
| `clear_duplicate` | `DUPLICATE_OVERRIDDEN` | Required | Required | Required |
| `archive` | `PROSPECT_ARCHIVED` | Required | Required | Required |
| `import_request` | `IMPORT_REQUESTED` | Required | Required | Required |
| `import_override` | `DUPLICATE_OVERRIDDEN` + approval path | Required | Required | Required |

### 4.2 Violation rule

**Missing `actor_id` or `actor_email` on any governance action above is a governance violation.**

Enforcement point: `DiscoveryAuditService.validate_audit_event()` and approval/import services at Stage N/P.

### 4.3 Permission model (reserved — Stage N)

| Permission | Scope |
|------------|-------|
| `discovery:review:read` | Queue and review detail |
| `discovery:review:decide` | approve, reject, request_changes |
| `discovery:review:duplicate` | mark_duplicate, clear_duplicate, duplicate override approve |
| `discovery:import:execute` | Initiate import (Stage P) — separate from approval |

---

## 5. Import workflow governance

### 5.1 Authoritative success path

```text
IMPORT_REQUESTED
    ↓
IMPORT_VALIDATED
    ↓
LeadService.create_lead()    ← sole CRM write
    ↓
PROSPECT_IMPORTED
```

### 5.2 Failure path (pre-CRM)

```text
IMPORT_REQUESTED
    ↓
IMPORT_BLOCKED
```

`IMPORT_FAILED` is reserved for failures **after** validation passes but during or after `LeadService.create_lead()` attempt.

### 5.3 Allowed transitions

| From | To | Condition |
|------|-----|-----------|
| — | `IMPORT_REQUESTED` | Actor initiates import on eligible prospect |
| `IMPORT_REQUESTED` | `IMPORT_VALIDATED` | All Phase 1 eligibility checks pass |
| `IMPORT_REQUESTED` | `IMPORT_BLOCKED` | Any eligibility check fails |
| `IMPORT_VALIDATED` | `PROSPECT_IMPORTED` | `create_lead` succeeds; prospect updated |
| `IMPORT_VALIDATED` | `IMPORT_FAILED` | `create_lead` fails or prospect post-update fails |

### 5.4 Blocked transitions

| Transition | Reason |
|------------|--------|
| Any → `PROSPECT_IMPORTED` without `IMPORT_VALIDATED` | Bypasses eligibility gate |
| Provider → `LeadService` | CRM protection |
| Approval queue → `LeadService` | CRM protection |
| Route → `LeadService` (except via Import Service) | CRM protection |
| `IMPORT_BLOCKED` → `PROSPECT_IMPORTED` without new validated request | Stale/bypass |

### 5.5 Enforcement owner

`DiscoveryImportService` — sole orchestrator of import workflow and audit chain.

---

## 6. Import eligibility checklist (frozen)

### 6.1 Phase 1 required (must pass before `IMPORT_VALIDATED`)

| Check | Owner | Enforcement |
|-------|-------|-------------|
| `review_status == approved` | Discovery | `DiscoveryImportService` |
| Not `archived` | Discovery | `DiscoveryImportService` |
| Not `erased` (`erasure_status != erased`) | Discovery | `DiscoveryImportService` |
| `lawful_basis != unknown` | Discovery | `DiscoveryImportService` |
| Duplicate governance satisfied (no `confirmed` without override on record) | Discovery | `DiscoveryImportService` |
| `imported_lead_id` absent | Discovery | `DiscoveryImportService` |

### 6.2 Reserved — Stage R / production hardening

| Check | Owner | Stage |
|-------|-------|-------|
| Suppression list (TPS/CTPS/MPS) | Discovery | R |
| LIA reference when `lawful_basis=legitimate_interest_b2b` | Discovery | R |
| CRM duplicate (`LeadService.find_duplicate`) | Discovery read / CRM | P |

### 6.3 Marketing consent rule (frozen)

`marketing_consent=true` requires `lawful_basis=consent` at import validation — block with `IMPORT_BLOCKED` if violated.

---

## 7. Discovery CRM protection rules (frozen)

Launch-gate **critical**. No exceptions in Phase 1.

| Path | Verdict |
|------|---------|
| Provider → CRM (`leads` collection) | **PROHIBITED** |
| Provider → `LeadService` | **PROHIBITED** |
| Approval Queue → CRM | **PROHIBITED** |
| Approval Queue → `LeadService` | **PROHIBITED** |
| Review Workflow (UI/API) → CRM | **PROHIBITED** |
| Discovery routes → `LeadService` | **PROHIBITED** (except Import Service delegation) |
| `DiscoveryImportService` → `LeadService.create_lead` | **ONLY PERMITTED PATH** |

### 7.1 Enforcement strategy

| Layer | Mechanism |
|-------|-----------|
| Protocol | `PROHIBITED_PROVIDER_CAPABILITIES` includes `CRM_WRITE` |
| CI grep (Stage Q) | `create_lead` only in `discovery_import_service.py` |
| Launch gate | NG-001–NG-004, NG-025–NG-029 |
| Code review | Any discovery + leads PR requires import-path review |

---

## 8. Drift resolution

| Drift | Resolution |
|-------|------------|
| Tracker listed `PROSPECT_REVIEWED` before code enum | Frozen in this doc; code sync in Stage N |
| `IMPORT_REQUESTED` / `IMPORT_VALIDATED` / `IMPORT_BLOCKED` absent from code | Frozen in this doc; code sync in Stage P |
| `request_changes` undefined | Formalised §3 — no new enum |
| Import path undocumented in launch gate | NG-025–NG-029 added |
| CRM protection not standalone architecture section | Architecture §16 added |

---

## 9. Readiness sign-off

| Domain | Status |
|--------|--------|
| Approval Queue Governance | **GREEN** |
| Review Workflow Governance | **GREEN** |
| Import Governance | **GREEN** |
| CRM Protection Governance | **GREEN** |

**Recommendation:** Proceed to **Stage N** implementation on `develop`.

---

## 10. Change control

- TIER_1 — product + platform sign-off required for changes
- New audit events require tracker + launch gate update
- No production enablement until launch gate GO
