# Commercial Controls — repository reconciliation 05

**Programme:** `COMMERCIAL-CONTROLS-CERTIFICATION-CLOSURE-AND-PROMOTION-GATE-05`  
**Inspected:** 2026-08-15T21:13Z  
**Branch:** `develop`

## SHAs

| Ref | SHA |
| --- | --- |
| Local `HEAD` (`develop`) | `f88ce26d6711e881fc20cdae148ac8bff4b2f9cb` |
| `origin/develop` | `7c77391a5ee65f0a85372d9c462448c270b6b066` |
| `origin/main` | `89217062481b4eb858a8b530ec90c83de067a4be` |
| Staging API `/api/version` | `7c77391a` `environment=staging` |
| Production API `/api/version` | `89217062` `environment=production` |
| Behavioural CC backend | `02533d50` (contained in `7c77391a`) |
| Staging FE bundle | `main.7fd31560.js` |
| Production FE bundle | `main.eac95fab.js` |

Local is **ahead 1** of `origin/develop`. Remote has no commits missing locally.

Unpushed commit:

```text
f88ce26d fix(frontend): do not count STEP_UP_REQUIRED toward the API circuit breaker
```

Files in that commit: `frontend/src/utils/apiRequestCircuit.js`, `frontend/src/api/client.js`, `frontend/src/utils/p0StagingRuntimeStabilization.test.js`, `.gitignore` (`backend/.cc_preflight_token.txt`).

## Source vs certified frontend (Phase 2)

Working tree does **not** modify the three certified frontend files after `f88ce26d`. Fingerprint `cc-step-up-circuit-fix-04` is present in source and on the staging alias bundle.

```text
NO POST_CERTIFICATION_SOURCE_DRIFT
```

Uncommitted `frontend/.gitignore` (`.vercel`, `.env*`) and root `.gitignore` (`.env*`) are **not** part of the certified fix. They must not ride this preservation.

## Outstanding working tree (classification)

The working tree is large. Only Commercial Controls 03/04 evidence and 05 gate documents are in scope for commit. Everything else stays uncommitted.

| Path class | Classification |
| --- | --- |
| `f88ce26d` frontend circuit files + tests | `CERTIFIED_IMPLEMENTATION` (already committed, not pushed) |
| `backend/.cc_preflight_token.txt` gitignore line in `f88ce26d` | `DO_NOT_COMMIT` the token; ignore rule is correct |
| `COMMERCIAL_CONTROLS_*_04.md` + `commercial_controls_*_04.json` | `AUDIT_EVIDENCE` |
| Untracked `COMMERCIAL_CONTROLS_*_03.md` + `commercial_controls_e2e_*_03.json` | `AUDIT_EVIDENCE` (referenced by 04; not on `origin/develop`) |
| `backend/scripts/commercial_controls_*.py` 03/04 | `CERTIFICATION_TEST` |
| 05 gate markdown/JSON | `DOCUMENTATION` |
| `backend/tmp_*`, `frontend/tmp_*` | `TEMPORARY` / `DO_NOT_COMMIT` |
| Gallery PDFs, Zoho CRM extras, orchestration, presentation audits | `UNRELATED_WORK` |
| `.env*`, tokens, passwords | `SECRET_OR_SENSITIVE` / `DO_NOT_COMMIT` |

## Secrets scan (04 pack)

No Stripe secret keys, Postmark tokens, session JWTs, or operator passwords in the 04 markdown/JSON. Stripe ids are prefixed. Scripts read `STAGING_ADMIN_PASSWORD` from the environment and do not write it.
