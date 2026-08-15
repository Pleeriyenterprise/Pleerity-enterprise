# Commercial Controls — post-commit smoke 05

**Programme:** `COMMERCIAL-CONTROLS-CERTIFICATION-CLOSURE-AND-PROMOTION-GATE-05`

Full 01–04 certification was **not** repeated.

## Source identity

Certified FE source `f88ce26d` matches the deployed alias bundle `main.7fd31560.js` (fingerprint `cc-step-up-circuit-fix-04`). No post-certification modification of those files. Backend commercial behaviour remains `02533d50` inside staging `7c77391a`.

Therefore affected-path revalidation of ACTIVE Suspend Billing is **not** mandatory. 04 provider-level proof stands.

## Step-up / circuit (04 same-day UI, still the live alias)

```text
submit → 403 STEP_UP_REQUIRED → modal → cancel → immediate retry (second 403) → no 90s circuit pause
```

Network: two POSTs to commercial-entitlement/execute both 403. Governance on lere remained ACTIVE (second pause avoided).

## Representative control

04 shared-path API smoke on nancy `6fd5ac4c-…`: grant grace, sponsored, retention, waive, recovery, restrict — each HTTP 200 then revoke. Left with no active exception.

## Suspend Billing

Not re-paused. 04 ACTIVE (lere) and 03 CANCELLED (allison) remain the provider-level proofs. Source/deployment of that path are unchanged.

## After origin push

If Render/Vercel change SHAs or the FE bundle hash, re-check:

* staging `/api/version`
* alias bundle still contains `cc-step-up-circuit-fix-04`
* production still `89217062` / `main.eac95fab.js`

If the FE fingerprint disappeared, this smoke is invalid and the circuit path must be re-proven.
