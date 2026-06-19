# Stage X Rerun Checklist

**Authority:** `STAGE-X-TWIN-STAGING-OPERATIONAL-VALIDATION-AUTHORITY-01`  
**Prerequisite:** Real Twin workspace configured per `TWIN_WORKSPACE_SETUP_PACKAGE.md`

---

## Pre-flight

- [ ] Twin workspace created in Twin.so (staging)
- [ ] **Pleerity Discovery Agent** deployed with system prompt from `twin_agent_system_prompt.md`
- [ ] Agent capabilities verified: discovery + export only (no outreach/CRM tools enabled)
- [ ] `workspace_id` and `agent_id` recorded in `twin_workspace_manifest.json`
- [ ] Manifest copied to `twin_exports/twin_workspace_manifest.json`
- [ ] `DISCOVERY_PROVIDER_TWIN_ENABLED` remains `false` until validation complete
- [ ] Staging MongoDB available (`pleerity_staging`, `MONGO_URI` / `MONGO_URL` in `.env`)

---

## Export generation

- [ ] Agent run completed against real UK property targets
- [ ] Export contains **≥ 50** records (target **100**)
- [ ] Every record has unique `twin_id`
- [ ] Every record has `source_url` (https)
- [ ] Every record has `company_name`
- [ ] Every record has `confidence_score` ≥ 50
- [ ] Every record has `country` = `GB`
- [ ] No `lawful_basis` or `marketing_consent` on any record
- [ ] No CRM IDs (`lead_id`, `prospect_id`, `customer_id`)
- [ ] `enrichment_data.discovered_at` and `origin_lineage` present on all records
- [ ] Batch envelope includes `export_id`, `workspace_id`, `agent_id`, `exported_at`
- [ ] `provenance` set to `real_workspace` (or omitted — loader defaults to real)
- [ ] Export saved to `twin_exports/twin_staging_export.json`

---

## Schema spot-check (5 random records)

- [ ] `business_type` is valid enum value
- [ ] `landlord_type` is valid enum value
- [ ] `confidence_score` is integer 50–100
- [ ] `website` / `source_url` are valid URLs where present
- [ ] `email` is public business email (not fabricated)
- [ ] Twin-only fields (`workflow_id`, `enrichment_data`) present only as allowed

---

## Run Stage X validation

From `backend/`:

```bash
python scripts/discovery_phase_1_twin_staging_validate.py \
  --twin-export docs/audit/discovery_phase_1_launch_01/twin_exports/twin_staging_export.json \
  --workspace-manifest docs/audit/discovery_phase_1_launch_01/twin_exports/twin_workspace_manifest.json
```

Optional cost input:

```bash
set TWIN_STAGE_X_COST_GBP=150
```

---

## Acceptance gates (must pass for GREEN)

| Part | Gate |
|------|------|
| A — Workspace | `export_provenance=real_workspace`; manifest has workspace_id + agent_id |
| B — Export | ≥ 50 records; field coverage ≥ 80% on required fields |
| C — Ingest | Success rate ≥ 90%; accepted ≥ 50 |
| D — Review | Sample ≥ 10; workflow exercised |
| E — Import | Primary import succeeds; retry idempotent; blocks enforced |
| F — Metrics | `provider_metrics.twin` reconciled; no Twin-specific metrics logic |
| G — Compliance | Legal hold blocks import |
| H — Lifecycle | Erasure + suppression behave identically to CSV |
| I — Cost | Cost metrics recorded |
| J — Comparison | CSV vs Twin comparison completed |
| K — Failure matrix | All scenarios PASS |
| L — Readiness | Overall **GREEN** (not AMBER) |

---

## Post-run evidence

- [ ] `TWIN_STAGING_VALIDATION_RESULTS.json` updated
- [ ] `STAGE_X_TWIN_STAGING_REPORT.md` updated
- [ ] Tracker `DISCOVERY_PHASE_1_IMPLEMENTATION_TRACKER.md` Stage X → GREEN
- [ ] Operational recommendation reviewed by Product + Compliance

---

## Final business question

> Should Twin become an operational prospect source for Compliance Vault Pro?

| Overall | Answer |
|---------|--------|
| **GREEN** | YES — measured staging evidence supports operational use (still no production enablement without launch gate) |
| **AMBER** | CONDITIONAL — adapter viable; real export quality/ROI thresholds not yet met |
| **RED** | NO — blockers must be resolved |

---

## Hard prohibitions (verify none occurred)

- [ ] No auto-import
- [ ] No outreach (email, LinkedIn, SMS, WhatsApp)
- [ ] No nurture workflows
- [ ] No CRM writes from Twin agent
- [ ] No Discovery architecture changes introduced
- [ ] No production Twin activation

---

## If validation fails

1. Record failure part and message from `TWIN_STAGING_VALIDATION_RESULTS.json`
2. If ingest/mapping failure → check `twin_discovery_field_mapping.json` against export
3. If compliance/lifecycle failure → architectural exception report required (do not patch around governance)
4. If quality failure → adjust agent qualification rules (§6), re-export, rerun
