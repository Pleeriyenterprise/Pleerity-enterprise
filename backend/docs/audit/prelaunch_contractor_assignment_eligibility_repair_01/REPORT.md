# PRELAUNCH-CONTRACTOR-ASSIGNMENT-ELIGIBILITY-REPAIR-01 — Closeout

## Classification

**VERIFIED_OPERATIONALLY**

## Deploy continuity

- Backend SHA: `0b65717ab818d689a3f7bda5ab0fce0abea21d5b` (includes programme commits `7f980d9b`, hotfix `a86f4442`)
- Frontend bundle: `/static/js/main.def1ffcc.js`
- Recovery testids present; job detail page loads without error boundary
- Assignable-contractors API returns `recovery_guidance` and `exclusion_samples`

## Programme commits

| Commit | Purpose |
|--------|---------|
| `7f980d9b` | Eligibility authority + recovery UX (portfolio vs postcode, API guidance, modal) |
| `a86f4442` | Hotfix: restore missing recovery helper hooks that crashed job detail page |
| `0b65717a` | Closeout harness updates |

## Runtime summary

- **Eligibility:** 30/30 maintenance jobs sampled with eligible contractors; Scotland job `63509f71…` remains 0 eligible (authoritative); invalid contractor assign blocked (HTTP 400)
- **Dropdown:** 1 eligible contractor in modal; assign disabled until selected; “All trades” / funnel copy present
- **Assignment E2E:** Contractor linked to job `f31ba8b8…` via browser assign flow
- **Recovery:** Scotland zero-eligible job returns 4 recovery actions + 4 exclusion sample groups (API); no dead-end
- **Cross-surface:** Assign modal authoritative on job detail; Command Centre / Today route via `/operations/jobs/{id}`

## Closeout captured

2026-05-30T03:09:56Z — `tmp_prelaunch_contractor_assignment_eligibility_repair_01_closeout.py`
