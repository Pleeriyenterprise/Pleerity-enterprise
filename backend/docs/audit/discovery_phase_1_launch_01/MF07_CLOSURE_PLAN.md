# MF-07 — Legacy CSV Import Decommission Closure Plan

**Authority:** STAGE-V-REAL-STAGING-VALIDATION-AND-PROVIDER-EXPANSION-READINESS-AUTHORITY-01  
**Status:** Plan only — no implementation in Stage V  
**Branch:** develop  
**Date:** 2026-06-02  

---

## Objective

Retire the legacy admin leads CSV import placeholder and converge all CSV prospect ingest on the Discovery Foundation path:

```text
CSV file → Discovery run (attestation) → CSVImportProvider → discovery_prospects → Review → DiscoveryImportService → LeadService
```

---

## Current state (audited on real staging validation)

| Path | Location | Behaviour | CRM write |
|------|----------|-----------|-----------|
| **Legacy** | `POST /api/admin/leads/import/csv` in `backend/routes/leads.py` | Placeholder — returns `success: false`, feature flag `LEAD_IMPORT_CSV` | None today |
| **Discovery CSV** | `CSVImportProvider.ingest_async()` in `backend/services/discovery/providers/csv_import_provider.py` | Ingests to `discovery_prospects` only | None at ingest |
| **Discovery import** | `DiscoveryImportService.import_prospect()` | Sole approved CRM crossing | `LeadService.create_lead()` |
| **Admin review** | `backend/routes/admin_discovery.py` | Review queue/actions only — no import route | None |

---

## Overlap risks

1. **Dual mental model** — operators may assume `/admin/leads/import/csv` is the canonical CSV path when it is a stub.
2. **Future activation risk** — if the legacy placeholder is implemented without governance, it would bypass review, attestation, audit, and compliance gates.
3. **Export vs import confusion** — multiple CSV *export* routes exist (leads export, submissions, reports). These are read-only and not in scope for MF-07 except labelling.
4. **Property bulk import** — `backend/routes/properties.py` list import is property data, not lead discovery; keep separate.

---

## Migration requirements (implementation deferred)

### Phase MF-07-A — Deprecation signal

- Change legacy endpoint to `410 Gone` with body pointing to Discovery run CSV workflow documentation.
- Add structured audit log entry `LEGACY_CSV_IMPORT_DEPRECATED` when endpoint is hit (optional telemetry).
- Update admin UI copy to remove “coming soon” lead CSV import CTA.

### Phase MF-07-B — Discovery operator path

- Expose admin UI for: create campaign → create CSV run with attestation → upload CSV → monitor ingest result.
- No auto-import; no import HTTP route (per governance freeze).

### Phase MF-07-C — Enforcement

- Add regression test `test_legacy_csv_import_deprecated.py` asserting 410/redirect.
- Extend `test_discovery_crm_boundary_regression.py` guard if any new CSV→Lead shortcut appears.
- Update `DISCOVERY_PHASE_1_IMPLEMENTATION_TRACKER.md` MF-07 to DONE with evidence.

### Phase MF-07-D — Communications

- Operator runbook: “All new prospect CSV ingest uses Discovery runs.”
- Note in launch gate LG documentation.

---

## Out of scope for MF-07

- Report/export CSV routes (read-only).
- Property portfolio CSV import.
- Twin/Apollo/Clay/crawler adapters.
- Production rollout.

---

## Stage V evidence

Real staging validation processed Datasets A–E via `CSVImportProvider` against MongoDB `pleerity_staging`. Legacy route remains placeholder only. **MF-07 implementation remains NOT_STARTED**; this document satisfies Stage V closure-plan deliverable only.

---

## Acceptance for MF-07 DONE (future)

- [ ] Legacy route returns 410 or governed redirect
- [ ] No code path writes leads from CSV except `DiscoveryImportService`
- [ ] Deprecation test in CI
- [ ] Tracker MF-07 marked DONE with PR evidence
