# Discovery Phase 1 Launch Gate

```yaml
---
Status: ACTIVE
Authority Level: TIER_1
Related:
  - docs/trackers/DISCOVERY_PHASE_1_IMPLEMENTATION_TRACKER.md
  - docs/governance/DISCOVERY_FEATURE_FLAGS.md
  - docs/governance/DISCOVERY_ANTI_LOCK_IN_CHECKLIST.md
  - docs/governance/DISCOVERY_APPROVAL_IMPORT_GOVERNANCE_FREEZE_01.md
  - backend/docs/launch/LAUNCH_AUTHORITY_TRACKER.md
Last Review: 2026-06-18
---

```

## 1. Purpose

GO/NO-GO gate for enabling discovery feature flags in **production**. Staging validation must complete first (Tracker Stage W).

**Branch rule:** `develop` / staging only until this gate passes. No `main` merge for discovery without GO.

---

## 2. GO criteria (all required)

### Architecture

- [ ] **LG-001** `DiscoveryProvider` protocol implemented with idempotency + canonical mapping
- [ ] **LG-002** `discovery_campaigns` collection live; runs link `campaign_id`
- [ ] **LG-003** Global cross-run dedupe per Architecture §13 (`email_hash`, `phone_hash` primary; `merged_into_prospect_id`)
- [ ] **LG-004** `source_metadata.discovery` validates against `DISCOVERY_SOURCE_METADATA_V1.json`
- [ ] **LG-005** `RawPayloadStore` abstraction — no uncontrolled inline payloads
- [ ] **LG-006** `platform_quality_score` separate from `provider_confidence`
- [ ] **LG-007** `content_hash` Canonical Ingest Fingerprint documented (Architecture §12); provider_reference uniqueness enforced
- [ ] **LG-008** `discovery_jobs` stub operational (CSV creates completed job)
- [ ] **LG-009** `origin_lineage[]` populated on every prospect and import metadata

### Governance

- [ ] **LG-010** `DISCOVERY_ANTI_LOCK_IN_CHECKLIST.md` DL-001–DL-019 signed
- [ ] **LG-011** `DISCOVERY_COMPLIANCE_AND_CONSENT.md` sign-off complete
- [ ] **LG-012** Admin attestation required on CSV runs
- [ ] **LG-013** Retention sweep + erasure cascade tested on staging
- [ ] **LG-014** Legacy `POST /api/admin/leads/import/csv` returns 410 or redirect — not active second path

### Workflow

- [ ] **LG-015** Full E2E: CSV upload → review → approve → lead created via `LeadService.create_lead` only
- [ ] **LG-016** Confirmed duplicate blocks import without override
- [ ] **LG-017** Override duplicate requires reason code + audit
- [ ] **LG-018** 100% staging imports without explicit consent column have `marketing_consent=false`
- [ ] **LG-019** No nurture email sent on import with `marketing_consent=false` (regression test)
- [ ] **LG-020** Audit trail complete for sample run (discover → review → import)
- [ ] **LG-029** Approval/import governance freeze signed (`DISCOVERY_APPROVAL_IMPORT_GOVERNANCE_FREEZE_01.md`)
- [ ] **LG-030** Reviewer actions include `actor_id` + `actor_email` in audit sample

### Tests

- [ ] **LG-021** All Tracker Stage V tests green on CI
- [ ] **LG-022** No regression on existing `test_lead_*` suite
- [ ] **LG-023** Grep guard: no `db.leads.insert` from `services/discovery/`

### Staging evidence

- [ ] **LG-024** Staging harness artifact: 50-row CSV, ≥45 imported, duplicates handled
- [ ] **LG-025** Metrics dashboard shows campaign funnel
- [ ] **LG-026** Feature flag rollback tested (`DISCOVERY_MODULE_ENABLED=false`)

### Documentation

- [ ] **LG-027** Ops runbook: upload, review, erasure request
- [ ] **LG-028** LIA reference recorded for pilot campaign

---

## 3. NO-GO criteria (any triggers NO-GO)

| Code | Condition |
|------|-----------|
| **NG-001** | Any provider bypasses approval queue |
| **NG-002** | Any provider writes directly to `leads` |
| **NG-003** | Any import bypasses `DiscoveryImportService` |
| **NG-004** | Any import bypasses `LeadService.create_lead` |
| **NG-005** | Imported prospect defaults `marketing_consent=true` without explicit consent |
| **NG-006** | Duplicate detection incomplete (no global cross-run dedupe) |
| **NG-007** | Audit trail missing for any workflow action |
| **NG-008** | `source_metadata.discovery` unversioned or fails schema validation |
| **NG-009** | `discovery_campaigns` absent |
| **NG-010** | `origin_lineage` absent on imports |
| **NG-011** | `content_hash` / idempotency absent |
| **NG-012** | Retention and erasure governance not implemented |
| **NG-013** | Legacy CSV import remains active as second path |
| **NG-014** | Production discovery flag enabled before staging evidence (LG-024) |
| **NG-015** | Any Phase 2 provider flag `true` in production |
| **NG-016** | Provider calls `notification_orchestrator` or outreach services |
| **NG-017** | Nurture fires on `marketing_consent=false` import |
| **NG-018** | Twin/Apollo/Clay/crawler integrated in Phase 1 build |
| **NG-019** | `content_hash` semantics undocumented (Architecture §12) |
| **NG-020** | Dedupe hierarchy undocumented (Architecture §13) |
| **NG-021** | Idempotency semantics conflict with implementation (Provider Protocol §4.4) |
| **NG-022** | `DISCOVERY_SOURCE_METADATA_V1.json` conflicts with `OriginLineageEntry` code model |
| **NG-023** | Provider protocol idempotency format conflicts with `discovery_hashing.py` |
| **NG-024** | Stage K governance prerequisites incomplete (Tracker §Stage K prerequisites) |
| **NG-025** | Approval workflow bypasses audit (missing events or actor attribution) |
| **NG-026** | Import bypasses `DiscoveryImportService` |
| **NG-027** | Any discovery provider or approval path can call `LeadService` |
| **NG-028** | Reviewer governance actions lack `actor_id` / `actor_email` attribution |
| **NG-029** | Import eligibility rules undocumented or not enforced at `DiscoveryImportService` |

---

## 4. Required evidence bundle

Store under `backend/docs/audit/discovery_phase_1_launch_01/`:

| Artifact | Description |
|----------|-------------|
| `STAGING_E2E_RESULTS.json` | Harness output |
| `AUDIT_TRAIL_SAMPLE.json` | Full run audit export |
| `CONSENT_DEFAULT_VERIFICATION.json` | 100% false default proof |
| `DEDUPE_TEST_RESULTS.json` | Cross-run + CRM dedupe |
| `ROLLBACK_TEST.json` | Flag off verification |
| `ANTI_LOCK_IN_GREP.txt` | CI grep outputs |
| `LAUNCH_SIGNOFF.md` | Product + engineering + compliance signatures |

---

## 5. Production enablement sequence

Only after GO:

1. Merge discovery to `main` via controlled release PR
2. Deploy with all flags `false`
3. Enable flags in order per `DISCOVERY_FEATURE_FLAGS.md`
4. Monitor 7 days: import volume, duplicate rate, nurture regression, support tickets
5. Record in `LAUNCH_AUTHORITY_TRACKER.md` as new item `L-DISC-001`

---

## 6. Rollback

1. `DISCOVERY_MODULE_ENABLED=false` immediately
2. No data rollback required
3. Document incident in launch tracker
4. NO-GO remains until root cause fixed and LG-021–LG-026 re-passed

---

## 7. Sign-off

| Role | Name | Date | GO / NO-GO |
|------|------|------|------------|
| Engineering Lead | | | |
| Product | | | |
| Compliance | | | |
| Platform Ops | | | |

**Gate decision:** _______________

**Date:** _______________
