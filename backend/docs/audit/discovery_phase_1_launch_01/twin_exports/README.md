# Twin exports — Stage X operational validation

Place real Twin workspace exports here for **GREEN** operational provenance.

**Setup package:** See `../twin_workspace/TWIN_WORKSPACE_SETUP_PACKAGE.md` for agent configuration, system prompt, schema, and field mapping.

**Stage Y webhook connector:** See `../twin_workspace/STAGE_Y_TWIN_WEBHOOK_CONNECTOR.md` for env vars and capture-first workflow.

## Required files (real workspace)

| File | Purpose |
|------|---------|
| `twin_staging_export.json` | Real Twin-generated prospect export (min 50, target 100 records) |
| `twin_workspace_manifest.json` | Workspace + agent configuration snapshot |
| `contract_cohort_stage-x-20260619064024.json` | Contract cohort (100 records) for Stage X adapter validation — canonical copy |

## Export format

Twin export JSON must match `TwinProvider` ingest contract:

```json
{
  "export_id": "exp-…",
  "workspace_id": "ws-…",
  "agent_id": "agent-…",
  "records": [
    {
      "twin_id": "twin-unique-id",
      "email": "contact@example.com",
      "company_name": "Example Landlord Ltd",
      "website": "https://example.com",
      "linkedin_url": "https://www.linkedin.com/company/example",
      "confidence_score": 72,
      "lawful_basis": "consent",
      "marketing_consent": true,
      "city": "London",
      "country": "GB"
    }
  ]
}
```

Records may also be a top-level JSON array (auto-wrapped as `{ "records": [...] }`).

## Run validation

From `backend/`:

```bash
# Real export (operational GREEN when all parts pass)
python scripts/discovery_phase_1_twin_staging_validate.py \
  --twin-export docs/audit/discovery_phase_1_launch_01/twin_exports/twin_staging_export.json \
  --workspace-manifest docs/audit/discovery_phase_1_launch_01/twin_exports/twin_workspace_manifest.json

# Contract cohort fallback (adapter path only — operational AMBER)
python scripts/discovery_phase_1_twin_staging_validate.py --allow-contract-cohort
```

## Environment overrides

| Variable | Description |
|----------|-------------|
| `TWIN_EXPORT_PATH` | Path to export JSON |
| `TWIN_WORKSPACE_MANIFEST` | Path to workspace manifest |
| `TWIN_WORKSPACE_ID` | Fallback workspace id when manifest absent |
| `TWIN_AGENT_ID` | Fallback agent id |
| `TWIN_STAGE_X_COST_GBP` | Campaign cost for ROI (default 150) |
| `DISCOVERY_STAGE_X_TAG` | Unique run tag (default timestamp) |

## Outputs

- `TWIN_STAGING_VALIDATION_RESULTS.json`
- `STAGE_X_TWIN_STAGING_REPORT.md`
