# Phase 2 — Production Registry Repair Dry-Run Review

**Generated:** 2026-06-14  
**Mode:** Dry-run only (`repair_published_registry_coverage.py`, no `--apply`)  
**Target:** `pleerity_production` → `compliance_requirement_registry_published`  
**Raw artifact:** `production_dry_run.json`

## Summary

| Metric | Value |
|--------|-------|
| `dry_run` | **true** |
| `previous_version` | **1** |
| `previous_entry_count` | **8** |
| `merged_entry_count` | **19** |
| `validation_error_keys` | **[]** |
| Projected next version on `--apply` | **2** |
| `activation_kind` on apply | `coverage_repair` |

## Overlap keys removed before merge (not in changelog; applied pre-merge)

| registry_key | Reason |
|--------------|--------|
| `FIRE_DETECTION\|DEFAULT` | Superseded by `SMOKE_HEAT_ALARMS\|DEFAULT` |
| `LANDLORD_REGISTRATION\|SCOTLAND` | Superseded by `LANDLORD_REGISTRATION\|DEFAULT` |
| `OCCUPATION_CONTRACT\|WALES` | Superseded by `OCCUPATION_CONTRACT\|DEFAULT` |

## Changelog (19 operations)

| Action | Count | Keys |
|--------|-------|------|
| **updated** | 5 | `GAS_SAFETY\|DEFAULT`, `EICR\|DEFAULT`, `EPC\|DEFAULT`, `LEGIONELLA\|DEFAULT`, `HMO_FIRE_RISK\|DEFAULT` |
| **added** | 14 | `SMOKE_HEAT_ALARMS\|DEFAULT`, `PAT_TESTING\|DEFAULT`, `RIGHT_TO_RENT\|DEFAULT`, `HOW_TO_RENT\|DEFAULT`, `TENANCY_AGREEMENT\|DEFAULT`, `TENANCY_DEPOSIT_PROTECTION\|{ENGLAND,WALES,SCOTLAND,NORTHERN_IRELAND}`, `HMO_LICENSING\|DEFAULT`, `FIRE_RISK_ASSESSMENT\|DEFAULT`, `OCCUPATION_CONTRACT\|DEFAULT`, `LANDLORD_REGISTRATION\|DEFAULT`, `LANDLORD_REGISTRATION_NI\|DEFAULT` |

## Editorial outcome (all 19 merged keys)

- **Placeholder `why_it_matters_short`:** eliminated on all patched keys (patch specs use editorial strings).
- **`LEGIONELLA|DEFAULT`:** reclassified to JOB / `arrange_job` primary action.
- **CTA labels:** populated where defined in patch specs (e.g. deposit protection uploads).

## Rollback (unchanged)

1. Pre-apply backup: export active singleton v1 + history row.
2. Emergency rollback: `revert_active_published_to_line_version(1)` → creates v3 revert history row.
3. Rollback restores placeholder content — emergency use only.

## Apply gate

**Do not run `--apply` until this dry-run is explicitly signed off.**

Sign-off checklist:

- [ ] Changelog matches expected 5 updated + 14 added
- [ ] `validation_errors` empty
- [ ] KPI parity code (Option C) deployed to production first or concurrently
- [ ] Ops backup of v1 singleton captured

## Not in scope (this phase)

Five staging-only keys remain out of scope — see `registry_staging_only_keys_followup_audit.md`.
