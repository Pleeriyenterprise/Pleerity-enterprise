# PRESENTATION-AUTHORITY-PRODUCTION-PROMOTION-01

**Verdict:** `PRODUCTION_PROMOTION_SUCCESSFUL`  
**Run:** 20260630T184500Z  
**Status:** EXECUTED

---

## Executive summary

Presentation Authority Alignment (PAA) was **scoped-promoted** from `develop` to `main` via cherry-pick of **three commits only**. Full `develop` → `main` merge was **not performed** (26+ out-of-scope commits remain on develop).

Staging post-deploy smoke passed at `7474362a`. Production backend and frontend deployed. Production smoke confirms promoted SHA `7b99a80e`.

**Production reconciliation execute was NOT run** (per policy).

---

## Promotion SHAs

| Field | SHA |
|-------|-----|
| develop validated head | `7474362a` |
| main before | `75230a31` |
| main after / production | `7b99a80e` |

### Cherry-picked commits

| develop | main | Message |
|---------|------|---------|
| `8a830365` | `1280ac18` | fix(presentation): align lifecycle authority across onboarding and counts |
| `aa8bf7b7` | `0686c888` | docs(presentation): add staging backend validation evidence |
| `7474362a` | `7b99a80e` | fix(presentation): validate dashboard and digest lifecycle wording |

---

## Staging gate (passed)

| Check | Result |
|-------|--------|
| Staging API `/api/version` | `7474362a` |
| Dashboard no ErrorBoundary | **PASS** |
| Onboarding count semantics | **PASS** |
| Command Centre + Requirements API | **PASS** |
| Monthly digest suffix evidence | **PASS** |
| Frontend Jest (23) + backend pytest (21) | **PASS** |

Evidence: [STAGING_POST_DEPLOY_SMOKE.json](./STAGING_POST_DEPLOY_SMOKE.json)

---

## Scope verification

- **33 files** changed on main (PAA programme only)
- **No** lifecycle-kpi-wip files restored
- **No** tmp scripts or unrelated develop commits included
- **No** production reconciliation execute

---

## Production deployment

| Component | URL | SHA / bundle |
|-----------|-----|--------------|
| Backend | https://api.pleerityenterprise.co.uk | `7b99a80e` |
| Frontend | https://pleerityenterprise.co.uk | `main.c00f6d82.js` (baked `7b99a80e`) |

Frontend deployed via `vercel deploy --prod` (`dpl_ECKhZJVSSi6s81vTnvwvAs3ZcJy8`).

---

## Production smoke

| Check | Result |
|-------|--------|
| API health | **200** healthy |
| `/api/version` | **7b99a80e** production |
| Frontend prod API baked in | **PASS** |
| Staging API absent from bundle | **PASS** |
| PAA triage lens in bundle | **PASS** |
| Legacy overdue affecting compliance | **absent** |
| Dashboard / requirements unauthenticated | **401** |

Note: Production bundle still contains pre-existing `lifecycle-kpi-attention-strip` from prior baseline — **not** introduced by this PAA cherry-pick.

Evidence: [PRODUCTION_SMOKE.json](./PRODUCTION_SMOKE.json)

---

## Deferred (non-blocking)

- Authenticated production walkthrough (dashboard digest preview UI) — optional follow-up
- Production reconciliation dry-run — requires `pleerity_production` operator shell; **execute not approved**

---

## Rollback

If regression detected: redeploy Render to previous production SHA `75230a31` and Vercel production to prior deployment. PAA changes are presentation copy only; no destructive DB mutations in this programme.

Machine-readable: [PRESENTATION_AUTHORITY_PRODUCTION_PROMOTION.json](./PRESENTATION_AUTHORITY_PRODUCTION_PROMOTION.json)
