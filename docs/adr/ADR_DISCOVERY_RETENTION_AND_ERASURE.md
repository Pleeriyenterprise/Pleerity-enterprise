# ADR: Discovery Retention and Erasure

```yaml
---
Status: ACCEPTED
Authority Level: TIER_1
Date: 2026-06-02
Related:
  - docs/governance/DISCOVERY_COMPLIANCE_AND_CONSENT.md
  - docs/governance/DISCOVERY_APPROVAL_IMPORT_GOVERNANCE_FREEZE_01.md
  - docs/DISCOVERY_FOUNDATION_ARCHITECTURE.md
Source Audits:
  - DISCOVERY-FOUNDATION-ARCHITECTURE-HARDENING-REVIEW-01
---
```

## Context

Discovery stores pre-CRM personal data (email, phone, names, locations), raw provider payloads, and immutable audit logs. GDPR data minimisation, storage limitation, and erasure rights apply. Imported prospects link to `leads` which have separate retention and nurture obligations.

Audit immutability conflicts with naive TTL deletion. Hardening review requires explicit cascade rules before build.

---

## Decision

Adopt **tiered retention** with **legal hold override**, **payload separation**, and **lead cascade on erasure**.

---

## Retention periods

| Record class | `review_status` / condition | Hot retention | Archive | Deletion |
|--------------|------------------------------|---------------|---------|----------|
| Rejected prospect | `rejected` | 90 days queryable | 90d → `archived` | 365d post-archive: anonymise PII, delete raw payload |
| Duplicate (not imported) | `duplicate_detected`, not imported | 90 days | 90d → `archived` | 365d: anonymise PII, delete raw payload |
| Approved not imported | `approved`, no `imported_lead_id` | 180 days | Reviewer alert at 30d | 365d: anonymise or force reject |
| Imported prospect | `imported` | Indefinite link row | N/A | Anonymise only via erasure workflow |
| Raw payload | any | While prospect hot | With prospect archive | Delete payload first on erasure |
| Audit log | all events | 24 months hot queryable | 24m → warm archive (export only) | Never delete; anonymise actor PII on erasure request |
| Discovery metrics | rollups | 36 months | N/A | Aggregates only; no PII |

**No Mongo TTL auto-delete on audit collection.**

---

## Archived prospect handling

- Set `review_status = archived`, `archived_at = now`
- Remove `raw_payload` from store via `RawPayloadStore.delete(reference)`
- Retain anonymised stub: `prospect_id`, `review_status`, `imported_lead_id`, `content_hash`, `email_hash`, `phone_hash`, lineage refs, audit refs
- Audit event: `PROSPECT_ARCHIVED`

---

## Raw payload deletion

- Payloads stored only via `raw_payload_reference` (never uncontrolled inline on main doc)
- On archive/erasure: delete blob first, then clear reference
- Audit event: `RAW_PAYLOAD_DELETED` with reason code

---

## Legal hold handling

- Field: `legal_hold = true` on prospect or run
- Blocks automated retention sweep
- Requires owner role to release
- Audit event: `LEGAL_HOLD_SET` / `LEGAL_HOLD_RELEASED`

---

## Erasure workflow (GDPR Art. 17)

### Pre-import prospect

1. Verify erasure request / admin GDPR action
2. Delete raw payload
3. Anonymise prospect PII fields (email, phone, names, location → `[ERASED]`)
4. Set `erasure_status = erased`, `erased_at`
5. Audit: `PROSPECT_ERASED` (immutable; no PII in details)
6. **Retain** `content_hash`, `email_hash`, `phone_hash`, and lineage structure — see Hash retention

### Hash retention after erasure

| Retained | Erased |
|----------|--------|
| `content_hash`, `email_hash`, `phone_hash` | Raw email, phone, names, location, website |
| `origin_lineage` structure (provider refs, run ids, entry hashes) | Raw payload blobs |
| `prospect_id`, audit refs | `canonical_identity_snapshot` PII when implemented |

See `DISCOVERY_COMPLIANCE_AND_CONSENT.md` §12 for rationale.

### Post-import prospect (lead exists)

1. Execute pre-import steps on prospect record
2. Set `source_metadata.discovery.erased_at` on linked lead (do not delete lead automatically)
3. Set `source_metadata.discovery.erasure_status = erased`
4. If `marketing_consent` was true: write `consent_events` withdrawal if not already unsubscribed
5. Block future nurture via existing `LeadStatus.UNSUBSCRIBED` or consent path — **do not** send erasure notification via discovery
6. Audit: `PROSPECT_ERASED` + `LEAD_DISCOVERY_PROVENANCE_ERASED` (lead audit bridge event)
7. Ops runbook: manual review if lead converted to `client_id`

### Suppression of future outreach

- Post-erasure: add email/phone hash to internal suppression list (hook; Phase 1 flags only)
- Re-ingest matching `email_hash` or `phone_hash` with active erasure → reject with `ERASURE_SUPPRESSION`
- `content_hash` match alone is **insufficient** for suppression — contact hashes are authoritative

---

## `source_metadata.discovery.erased_at` behaviour

When set on lead:

- Discovery UI must show "provenance erased" — no PII from discovery payload
- Reporting excludes from active campaign funnel
- Re-import requires new prospect id and explicit compliance review
- Field is **append-only**; never unset

---

## Retention job

- **Job name:** `discovery_retention_sweep` (daily, feature-flagged)
- Respects `legal_hold`
- Idempotent per prospect
- Metrics: `prospects_archived`, `payloads_deleted`, `prospects_anonymised`

---

## Conflicts resolved

| Conflict | Resolution |
|----------|------------|
| Audit immutability vs TTL | Audit never TTL-deleted; PII anonymised in place |
| 90d rejected vs accountability | Audit retains event; prospect PII anonymised at 365d |
| Lead retention vs prospect erasure | Lead retained; discovery provenance marked erased |

---

## Status

**ACCEPTED** — implement in tracker Stages I, T before staging validation.
