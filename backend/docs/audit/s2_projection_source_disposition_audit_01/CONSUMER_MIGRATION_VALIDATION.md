# Consumer migration validation

**Programme:** S2-PROJECTION-SOURCE-DISPOSITION-AUDIT-01  
**Date:** 2026-06-02  
**Authority:** `s2_customer_status_projector_planning_01/CONSUMER_MIGRATION_MATRIX.json`

---

## Expected migration sequence

| Phase | Scope | Customer-visible |
|-------|-------|------------------|
| **S2** | Backend projector on enrich path; cognition/CTA backend alignment | Shadow: no. Active: partial (API fields change; FE fallbacks remain) |
| **S3** | Frontend consumption — remove fallback projection | Full portal alignment |
| **S4** | Reports, digests, notification emails | Export/email alignment |
| **S5** | Admin explain, progress contract, admin queues | Admin parity |

---

## S2 in-scope consumers (validated)

| ID | Surface | Current source | S2 action | Sequence OK |
|----|---------|----------------|-----------|-------------|
| C-12 | Enrich API | requirement_truth enrich | Primary projector deliverable | Yes |
| C-04 | Today page | operational_cognition | Backend cognition reads customer_status_* | Yes |
| C-05 | Command Centre | operational_cognition | Same as C-04 | Yes |
| C-11 | Admin explain API | Raw enrich + lifecycle | Add customer_status_* + debug | Yes |
| C-14 | Unified tasks | take_action + attention | Attention internal; CTA post-projector | Yes |

---

## S3 deferred consumers (validated — no S2 violation if unchanged)

| ID | Surface | Risk | Sequence OK |
|----|---------|------|-------------|
| C-01 | Requirements page | HIGH | Yes — API populated in S2 shadow |
| C-02 | Property matrix | HIGH | Yes |
| C-03 | Requirement modal | HIGH | Yes — D2/D3 persist until S3 |
| C-06 | Documents page | HIGH | Yes — doc-row scoping preserved |
| C-07 | Dashboard widgets | LOW | Yes |
| C-13 | Property operating hub | MEDIUM | Yes |

---

## S4 deferred consumers (validated)

| ID | Surface | Sequence OK |
|----|---------|-------------|
| C-08 | Reports PDF/export | Yes |
| C-09 | Monthly digest email | Yes |
| C-10 | Scheduled report email | Yes |

---

## Sequence violations

### Violation V-01 — Partial backend consumer in wrong order (remediated in S2 plan)

| Source | Issue | Remediation |
|--------|-------|-------------|
| PS-06 operational_cognition | Emits customer copy today independent of projector | **S2 task** — migrate before flag=active |
| PS-08 audience_governance | Emits status_label on enrich today | **S2 partial** — landlord interpretation read-through only; full export buckets S4 |

**Verdict:** Planned remediation exists; not a blocker for S2 **start** if cognition migration is in S2 PR scope before active promotion.

### Violation V-02 — Frontend sources active during S2 active (accepted)

| Sources | Issue | Remediation |
|---------|-------|-------------|
| PS-16–PS-20 | FE fallbacks override API customer_status_* | **Accepted** per S2/S3 boundary — documented in planning GO/NO-GO |
| PropertyDetailPage.js | Direct truth_presentation_label read | S3 |

**Verdict:** Not a sequence violation — explicit partial customer-visible drift during S2 active-only API phase.

### Violation V-03 — Reports before S3 (none)

PS-13/14/15 correctly deferred S4. No report consumer migrates before frontend.

### Violation V-04 — Admin before S5 (none in S2)

`progress_contract_service.py` admin labels — S5 scope. No S2 change required.

---

## Projection source vs consumer phase map

| PS-ID | Classification | Consumer phase alignment |
|-------|----------------|--------------------------|
| PS-01–11, PS-21 | A/B backend | S2 |
| PS-02 label path | C | Shadow S2 → retire S3/S4 |
| PS-05, PS-06, PS-08, PS-12 | B | S2 partial |
| PS-13–15 | D | S4 |
| PS-16–20 | D | S3 |

---

## Required remediation before S2 flag=active

1. PS-03: remove client_lifecycle_label overwrite from truth_presentation_label
2. PS-02: disable derive_truth_presentation customer label emission
3. PS-06: cognition envelope from customer_status_*
4. PS-05: no truth_presentation_stage mutation for status
5. PS-21: take_action resolved after projector

---

## Overall validation

| Check | Result |
|-------|--------|
| S2 limited to backend enrich + cognition | **PASS** |
| S3 owns all FE fallback retirement | **PASS** |
| S4 owns reports/emails | **PASS** |
| No source forces S4 before S3 | **PASS** |
| S2 active blockers identified | **PASS** with 5 backend remediations |

**Consumer migration sequence: VALID** with documented S2-active partial drift until S3.
