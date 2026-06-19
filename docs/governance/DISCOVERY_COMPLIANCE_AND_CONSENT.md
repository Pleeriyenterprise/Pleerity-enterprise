# Discovery Compliance and Consent Governance

```yaml
---
Status: ACTIVE
Authority Level: TIER_1
Related:
  - docs/adr/ADR_DISCOVERY_RETENTION_AND_ERASURE.md
  - docs/governance/DISCOVERY_APPROVAL_IMPORT_GOVERNANCE_FREEZE_01.md
  - backend/services/consent_service.py
  - backend/services/lead_service.py
Last Review: 2026-06-18
---
```

## 1. Scope

Governs personal data processing for Phase 1 prospect discovery: CSV/manual ingest, review queue, import to leads, retention, and erasure.

**Not in scope:** Phase 2 US provider transfer (fields reserved), automated outreach from providers.

---

## 2. GDPR controls

| Control | Implementation |
|---------|----------------|
| Lawfulness | `lawful_basis` required on every prospect and run |
| Purpose limitation | Discovery for B2B prospect qualification only — documented in campaign purpose |
| Data minimisation | Canonical fields only; raw payload in separate store; delete payload on archive |
| Accuracy | Reviewer edit pre-import; `platform_quality_score` flags incomplete records |
| Storage limitation | Retention per `ADR_DISCOVERY_RETENTION_AND_ERASURE.md` |
| Integrity/confidentiality | Admin auth, audit logs, no public discovery APIs Phase 1 |
| Accountability | Admin attestation, immutable audit, LIA reference on campaign |

---

## 3. PECR controls

| Rule | Requirement |
|------|-------------|
| Default consent | `marketing_consent = false` on all imported leads unless explicit per-row evidence |
| Nurture gate | Import service must not set `marketing_consent=true` without `lawful_basis=consent` |
| Outreach path | Only existing `lead_followup_service` after import — discovery never triggers sends |
| Soft opt-in | **Not assumed** for CSV lists — B2B LI may apply for non-electronic contact only per LIA |
| Suppression | Suppression list hook before import (TPS/CTPS/MPS) — Phase 1: flag `risk_flags`, block optional |

---

## 4. Lawful basis handling

| Basis | When allowed | Evidence required |
|-------|--------------|-------------------|
| `legitimate_interest_b2b` | B2B prospecting aligned with campaign ICP | Campaign LIA reference id |
| `consent` | Explicit marketing consent in source data | Consent timestamp/source in row or attestation |
| `unknown` | **Rejected at import** | — |

**Run-level default:** Admin selects lawful basis at CSV upload. Row-level override allowed only with stricter basis.

---

## 5. LIA requirement

- Every `discovery_campaign` with `lawful_basis=legitimate_interest_b2b` must have `lia_reference_id` (document id or URL)
- Campaign cannot accept runs without LIA when LI basis selected
- Phase 1 pilot: single platform LIA may cover CSV pilot with campaign record linking to it

---

## 6. Admin attestation

Required on every `discovery_run` (CSV/manual):

```json
{
  "attestation": {
    "lawful_basis_declared": "legitimate_interest_b2b",
    "lia_reference_id": "LIA-2026-DISCOVERY-PILOT-01",
    "data_source_description": "Purchased B2B list / conference attendees / etc.",
    "consent_not_assumed": true,
    "attested_by_id": "admin_user_id",
    "attested_by_email": "admin@pleerity.com",
    "attested_at": "2026-06-02T12:00:00Z"
  }
}
```

Audit event: `RUN_ATTESTED`

---

## 7. Marketing consent default false

- Schema default: `marketing_consent: false`
- CSV column `marketing_consent` optional; if `true`, row must have `lawful_basis=consent` and `consent_evidence` or row rejected
- Import service assertion test: 100% staging imports without explicit consent column must have `marketing_consent=false`

---

## 8. Suppression list hook

**Phase 1:** `discovery_import_service` calls `check_suppression_list(email, phone)` at **import validation** (after `IMPORT_REQUESTED`, before `IMPORT_VALIDATED` — see `DISCOVERY_APPROVAL_IMPORT_GOVERNANCE_FREEZE_01.md` §5–§6):

- Returns: `{ suppressed: bool, lists: ["TPS"], action: "flag" | "block" }`
- Phase 1 default: `action=flag` → `risk_flags: ["suppression_list_match"]`
- Phase 2: configurable `block` for phone outreach lists

---

## 9. consent_events alignment

When imported lead has `marketing_consent=true`:

- Write `consent_events` record via `consent_service` pattern (not lead field alone)
- Event type: `MARKETING_CONSENT_CAPTURED`
- Include `source: discovery_import`, `discovery_prospect_id`, `lawful_basis`

When erasure requested on imported lead:

- Write consent withdrawal event if marketing was active
- Align with `consent_service` retention (`CONSENT_RETENTION_MONTHS`)

---

## 10. Retention rules

See `ADR_DISCOVERY_RETENTION_AND_ERASURE.md`. Summary:

- Rejected/duplicate-not-imported: 90d → archive → 365d anonymise
- Imported: indefinite link; erasure via cascade workflow
- Audit: 24m hot, warm archive after; never delete events

---

## 11. Erasure cascade

1. Anonymise `discovery_prospects` PII
2. Delete raw payload
3. Set `source_metadata.discovery.erased_at` on lead
4. Consent withdrawal if needed
5. Suppression hash to block re-ingest
6. Audit: `PROSPECT_ERASED`, `LEAD_DISCOVERY_PROVENANCE_ERASED`

---

## 12. Hash retention after erasure

Per `ADR_DISCOVERY_RETENTION_AND_ERASURE.md` and Architecture §12.

### Retained after erasure (non-reversible identifiers)

| Field | Rationale |
|-------|-----------|
| `content_hash` | Suppression protection; audit integrity; duplicate prevention |
| `email_hash` | Cross-run suppression and dedupe without storing raw email |
| `phone_hash` | Cross-run suppression and dedupe without storing raw phone |
| `origin_lineage` structure | Provenance chain (provider refs, run ids, hashes) — no direct identifiers |
| `prospect_id`, `imported_lead_id` | Accountability linkage |

### Erased / anonymised

| Field | Treatment |
|-------|-----------|
| `email`, `phone` | Cleared / null |
| `contact_name`, `company_name` | `[ERASED]` or null |
| `website`, `location` | Cleared |
| Raw payload content | Deleted via `RawPayloadStore.delete` |
| `canonical_identity_snapshot` (future) | Anonymised when implemented |

**Rationale for hash retention:** GDPR erasure removes identifiable data while preserving non-reversible hashes enables (1) blocking re-ingest of erased subjects, (2) maintaining immutable audit trail integrity, (3) preventing duplicate re-creation without storing PII.

Re-ingest of erased subject matching `email_hash` / `phone_hash` → reject with `ERASURE_SUPPRESSION` (not `content_hash` alone).

---

## 13. Raw payload handling

- Stored via `RawPayloadStore` only — reference on prospect doc
- May contain provider PII — same retention/erasure as prospect
- Admin export of raw payload: owner role only, audited
- No raw payload in API list responses (detail view with permission only)

---

## 14. Import workflow compliance

Import to CRM is governed by `DISCOVERY_APPROVAL_IMPORT_GOVERNANCE_FREEZE_01.md`:

- Sole path: `DiscoveryImportService` → `LeadService.create_lead`
- Audit chain: `IMPORT_REQUESTED` → `IMPORT_VALIDATED` → `PROSPECT_IMPORTED` or `IMPORT_BLOCKED` / `IMPORT_FAILED`
- Reviewer attribution mandatory on approval and import request actions
- `request_changes` does not imply consent or import eligibility

---

## 15. Provider transfer basis (reserved — Phase 2)

Fields reserved on `discovery_runs` and metadata contract:

- `data_transfer_basis`: `adequacy` | `scc` | `uk_extension` | `none`
- `provider_data_region`: e.g. `US`, `EU`, `UK`
- Required before enabling `DISCOVERY_PROVIDER_APOLLO_ENABLED` or `DISCOVERY_PROVIDER_CLAY_ENABLED`

Phase 1 CSV/manual: `data_transfer_basis=none`, `provider_data_region=UK`

---

## 14. Data minimisation rules

| Rule | Enforcement |
|------|-------------|
| No collection of special category data | CSV schema rejects sensitive columns |
| No unnecessary fields in list API | Projection excludes `raw_payload_reference` in list |
| Hash storage | `email_hash`, `phone_hash` for dedupe; `content_hash` for ingest fingerprint; hashes retained after erasure per §12 |
| Audit details | No full email in audit `details` — use masked/hash |

---

## 15. Compliance sign-off gate

Before staging validation (Tracker Stage W):

- [ ] LIA reference recorded for pilot campaign
- [ ] Admin attestation flow implemented
- [ ] marketing_consent default false verified by test
- [ ] Erasure cascade documented in ops runbook
- [ ] Anti-lock-in checklist DL-001–DL-019 reviewed
