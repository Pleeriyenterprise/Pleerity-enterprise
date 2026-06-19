# Discovery Anti-Lock-In Checklist

```yaml
---
Status: ACTIVE
Authority Level: TIER_1
Related: docs/contracts/DISCOVERY_PROVIDER_PROTOCOL.md
Last Review: 2026-06-02
---
```

Phase 1 and all future discovery work must pass this checklist before merge to `develop` and before launch gate sign-off.

## Core architecture

- [ ] **DL-001** No Twin-specific fields in core `leads` records — only generic `source_metadata.discovery` per `DISCOVERY_SOURCE_METADATA_V1.json`
- [ ] **DL-002** No Apollo/Clay/crawler-specific fields in `leads` core schema
- [ ] **DL-003** No provider-specific CRM pipeline stages — use existing `LeadStage` enum only
- [ ] **DL-004** No provider-specific nurture rules — nurture triggered only by existing `LeadService` / follow-up paths
- [ ] **DL-005** No provider direct writes to `leads` collection — grep CI guard: no `db.leads.insert` from `services/discovery/`
- [ ] **DL-006** No provider direct outreach — providers cannot call `notification_orchestrator`, email services, or SMS
- [ ] **DL-007** No provider direct compliance/evidence/document access — discovery services must not import evidence or compliance modules for provider callbacks

## Provider adapter rules

- [ ] **DL-008** Every provider implements `DiscoveryProvider` protocol (`docs/contracts/DISCOVERY_PROVIDER_PROTOCOL.md`)
- [ ] **DL-009** Provider data maps to canonical prospect schema via `map_to_canonical()` — provider-specific data in `provider_extensions` or raw payload store only
- [ ] **DL-010** All provider records preserve `origin_lineage[]` with `provider_id`, `provider_reference`, `ingested_at`
- [ ] **DL-011** `idempotency_key()` prevents duplicate ingest on retry (ingest-scoped via `build_discovery_idempotency_key`; Architecture §12–§13)
- [ ] **DL-012** Provider adapters registered in config registry — not hardcoded `if provider == "apollo"` in CRM or nurture code
- [ ] **DL-013** Each provider behind dedicated feature flag (default `false` in production)

## Removal safety

- [ ] **DL-014** Disabling a provider flag stops new ingest only — no data loss on existing prospects/leads
- [ ] **DL-015** Provider removal must not require CRM migration — `source_metadata.discovery` is self-describing
- [ ] **DL-016** No foreign provider IDs as primary keys — platform `prospect_id` / `lead_id` always authoritative

## Phase 1 specific

- [ ] **DL-017** Only `csv` and `manual` providers may be active in Phase 1
- [ ] **DL-018** Legacy `POST /api/admin/leads/import/csv` deprecated — single discovery path
- [ ] **DL-019** Twin/Apollo/Clay/crawler flags remain `false` until Phase 2 ADR amendment

## Verification commands (staging / CI)

```bash
# No direct leads insert from discovery package
rg "db\[.?leads.?\]\.insert|db\.leads\.insert" backend/services/discovery/

# No notification orchestrator from discovery
rg "notification_orchestrator" backend/services/discovery/

# No provider-specific lead stage mutations
rg "apollo|clay|twin" backend/services/lead_service.py backend/services/lead_followup_service.py
```

## Sign-off

| Role | Name | Date | Pass |
|------|------|------|------|
| Engineering | | | |
| Product | | | |
| Compliance | | | |
