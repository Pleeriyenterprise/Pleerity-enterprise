# ADR: Discovery Provider-Neutral Architecture

```yaml
---
Status: ACCEPTED
Authority Level: TIER_1
Date: 2026-06-02
Deciders: Product, Platform Engineering
Source Audits:
  - PROSPECT-DISCOVERY-STRATEGY-AND-PROVIDER-ARCHITECTURE-AUDIT-01
  - DISCOVERY-FOUNDATION-IMPLEMENTATION-PLAN-01
  - DISCOVERY-FOUNDATION-ARCHITECTURE-HARDENING-REVIEW-01
Related:
  - docs/DISCOVERY_FOUNDATION_ARCHITECTURE.md
  - docs/contracts/DISCOVERY_PROVIDER_PROTOCOL.md
---
```

## Context

Prospect discovery is a genuine capability gap. Lead capture, scoring, qualification, nurture, CRM, support, onboarding, and conversion already exist natively. Previous audits scored **Option D — Hybrid architecture** highest (8/10): native foundations with provider-neutral adapters, platform database as source of truth, approval queue before CRM.

Twin.so is not present in the codebase. Native LLM assistants, lead CRM, and nurture are mature. Duplicating those capabilities via an external orchestration platform would increase cost and compliance risk without closing the discovery gap.

---

## Decision

**Approve Phase 1 Prospect Discovery Foundations** with:

1. Provider-neutral `DiscoveryProvider` protocol
2. CSV and manual as the only active Phase 1 providers
3. Pre-CRM `discovery_prospects` store with approval queue
4. `DiscoveryImportService` as the sole bridge to `LeadService.create_lead`
5. Campaigns, jobs, origin lineage, content hash, and versioned discovery metadata as **required schema**, not optional

**Hash governance (post Stage H-GOV):** `content_hash` is a Canonical Ingest Fingerprint (Architecture §12), not a global identity key. Cross-run dedupe uses `email_hash` / `phone_hash` (Architecture §13).

Twin, Apollo, Clay, and internal crawler are **future adapters only** — not Phase 1 scope.

---

## Rationale

### Why Hybrid architecture was approved

| Option | Score | Outcome |
|--------|-------|---------|
| Build native only | 4/10 | Slow time-to-value for list sourcing |
| Twin only | 5/10 | Orchestration ≠ CRM; duplicates nurture/compliance |
| Other provider only | 7/10 | Vendor lock-in risk |
| **Hybrid** | **8/10** | Native governance + external sourcing flexibility |

Hybrid preserves platform ownership of leads, consent, nurture, and compliance while allowing external list providers to **suggest** candidates through adapters.

### Why Twin-specific integration was rejected for Phase 1

- Twin is a **workflow orchestration** tool, not a canonical prospect store
- Native nurture, CRM, scoring, and compliance already exist
- Twin integration would blur boundaries (outreach, enrichment, CRM writes)
- Correct future pattern: Twin exports → discovery ingest endpoint → approval queue

### Why CSV-first was selected

- Lowest risk path to validate full architecture (campaign → run → prospect → review → import)
- No API credentials, credit metering, or cross-border transfer in Phase 1
- Existing stub `POST /admin/leads/import/csv` proves demand but must be **replaced**, not extended
- Enables staging validation without external vendor dependency

### Why LeadService remains source of truth

- `leads` collection already powers CRM, nurture, scoring, conversion, pilot attribution
- `LeadService.create_lead` handles dedupe, audit, tags, and follow-up eligibility
- Direct provider writes would bypass consent checks, audit, and duplicate governance
- Code anchor: `backend/services/lead_service.py`

### Why providers cannot send outreach

- PECR and GDPR require platform-controlled consent and lawful basis
- `consent_service` and `lead_followup_service` are the only sanctioned outreach paths
- Provider-initiated email/SMS would create unaudited marketing activity
- Providers may not call `notification_orchestrator`

### Why providers cannot write directly to CRM

- Platform database is source of truth
- Approval queue is mandatory governance control
- Provider data quality varies; human review required for Phase 1
- Prevents lock-in where CRM schema becomes provider-shaped

### Why campaigns, jobs, origin lineage, content hash, and versioned metadata are required

Hardening review identified migration debt if deferred:

| Abstraction | Without it |
|-------------|------------|
| `discovery_campaigns` | No ROI, no compliance context, no ICP tracking |
| `discovery_jobs` | Apollo/Clay async ingest requires rewrite |
| `origin_lineage` | Multi-provider provenance lost |
| `content_hash` | Re-upload duplicates, no idempotency |
| Versioned `source_metadata.discovery` | Reporting fragmentation, unsafe replay |

### How future provider replacement will work

1. Implement new adapter conforming to `DiscoveryProvider` protocol
2. Enable per-provider feature flag (default `false`)
3. Map provider payload → canonical prospect via `map_to_canonical()`
4. Preserve `origin_lineage` and `provider_reference`
5. Disable old provider flag — existing leads retain discovery metadata
6. No CRM migration — `leads.source_metadata.discovery` is self-describing

---

## Consequences

### Positive

- Validated architecture before vendor spend
- Clear compliance boundary
- Extensible without CRM changes

### Negative

- Higher Phase 1 schema surface (campaigns, jobs, lineage)
- Manual review throughput limit until automation in Phase 2

### Risks mitigated

- Provider lock-in → protocol + canonical schema
- PECR breach → consent default false + import service gate
- Duplicate CRM leads → global dedupe + LeadService gate

---

## Compliance with hardening Must Fix (12/12)

All items recorded in `DISCOVERY_FOUNDATION_ARCHITECTURE.md` §9 and enforced via implementation tracker Stages C–U.

---

## Status

**ACCEPTED** — conditional on governance doc completion before code (authority update 2026-06-02).

**Amendment 2026-06-18 (DISCOVERY-APPROVAL-IMPORT-GOVERNANCE-FREEZE-01):** Approval queue, import workflow audit chain, `request_changes` semantics, reviewer attribution, and CRM protection rules frozen in `docs/governance/DISCOVERY_APPROVAL_IMPORT_GOVERNANCE_FREEZE_01.md`. Stage N implementation authorised on `develop`.
