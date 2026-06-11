# Job detail actionability — post-deploy verification REPORT

**Programme:** `JOB-DETAIL-ACTIONABILITY-POST-DEPLOY-RUNTIME-PROOF-01`  
**Deploy commit:** `024f580e`  
**Classification:** `VERIFIED_OPERATIONALLY`

## Deploy proof

| Surface | Evidence | Match |
|---------|----------|-------|
| Backend | `GET /api/version` → `024f580e9e7018510562c14256c308a1a50b14dc` | Yes |
| Frontend | `main.dd2e386d.js` contains `024f580e`, `cancel-job-lifecycle`, `open-assign-contractor-modal`, `Awaiting contractor assignment` | Yes |

Artifact: `deploy_proof_runtime.json`

## Original defect retest

**Job:** `e670afc5-ef2d-487b-b688-ac8d865daf63` (OPEN, no `contractor_id`, `assign_contractor` in `next_actions`)

| Check | Before fix | After fix (staging browser) |
|-------|------------|----------------------------|
| Hero label | Assign contractor | Assign contractor |
| Hero click | Scrolled to Visit | **Opens assign contractor modal** |
| Progress | Contractor assigned (drift) | **Awaiting contractor assignment** |
| Contractor block | No contractor assigned yet | No contractor assigned yet (aligned) |

Screenshots: `post_deploy_screenshots/hero_assign_hero_before_click.png`, `hero_assign_hero_after_click.png`

## Part summaries

1. **Hero assign** — PASS (`hero_assign_contractor_browser_runtime.json`)
2. **CTA convergence** — PASS — hero + contractor section both open same modal (`contractor_cta_convergence_browser_runtime.json`)
3. **Entitlement** — PASS — Sophie (`contractor_network` disabled): no assign button, upgrade/help visible (`contractor_entitlement_browser_runtime.json`)
4. **Progress alignment** — PASS — Scenario A browser; Scenario B substituted with API proof (no `ASSIGNED`+null `contractor_id` on staging) (`progress_contract_alignment_runtime.json`)
5. **Cancel governance** — PASS — `cancel` visible only when in `next_actions`, in Job options (not hero); requires scroll (`cancel_governance_browser_runtime.json`)
6. **Authority trace** — No multi-authority drift on assign job (`job_action_authority_trace_runtime.json`)
7. **Regression** — 11 frontend + 30 backend targeted tests pass (`job_detail_post_deploy_regression_runtime.json`)

## Staging accounts

- **Nancy** (`nancy@yopmail.com`) — client login browser proof
- **Sophie** — entitlement guard (`contractor_network` disabled)
