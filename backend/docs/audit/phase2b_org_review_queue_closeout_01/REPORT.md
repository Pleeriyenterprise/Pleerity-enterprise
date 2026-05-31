# PHASE-2B-ORG-REVIEW-QUEUE-CLOSEOUT-01

**Programme:** Closeout + operational verification only  
**Deploy candidate:** `40165e8a68ecb12120d1482f21a0e6737e81f742`  
**Verified at:** 2026-05-31 (staging)  
**Classification:** **VERIFIED_OPERATIONALLY**

## Summary

Phase 2B org review queue convergence is deployed and operationally verified on staging. Org queue inclusion follows governance invariants (`governance_family` + `review_owner` + `queue_backed_review` + pending verification), not lifecycle state alone. Verify/reject reuses the existing `POST .../compliance-evidence/{id}/verification` mutation; queue rows disappear correctly after resolution with post-review convergence across Requirements, Today, Command Centre, and cognition payloads.

## Part 1 — Deploy continuity

| Check | Result |
|-------|--------|
| `/api/version` commit | `40165e8a` ✅ |
| Frontend bundle markers | `compliance-review`, `org-review-queue`, `escalation-queue` ✅ |
| Org queue route (unauth) | 401 ✅ |
| Backend repo markers | `matches_org_review_queue`, `matches_escalation_queue`, `_converge_queue_presentation_fields`, `audit_orphan_queue_states`, `org_verification_pending` ✅ |

## Part 2 — Staging fixtures

| Fixture | Result |
|---------|--------|
| A. ORG_ADMIN_REVIEWED row | `scotland_landlord_registration` @ 78 Trewe Close — `review_owner=org_admin`, `queue_backed_review=true`, `org_verification_pending` ✅ |
| B. Escalation row | 4 existing escalation rows on staging (legionella, fire_alarm, hmo_license, how_to_rent); not visible in org queue ✅ |
| C. Queue-less A/C rows | 5+ SELF_CERTIFIED / PLATFORM_OVERSIGHT_OPTIONAL samples; none queue-backed ✅ |

**Note:** Wales `occupation_contract` was previously verified; reseed does not recreate `PENDING_REVIEW`. Scotland landlord registration used as org queue seed target.

## Part 3 — Org queue runtime

- **Account:** `nancy@yopmail.com` (ROLE_CLIENT_ADMIN)
- **Route:** `GET /api/client/compliance-evidence/org-review-queue` → 200, 1 row
- **Row fields:** property label, requirement type, truth label "Organisation review pending", review owner `org_admin`, submitted date, deeplink ✅
- **Governance invariant:** all checks pass ✅

## Part 4 — Verify / reject flow reuse

| Step | Result |
|------|--------|
| Reject via existing verification mutation | 200 ✅ |
| Queue count before → after reject | 1 → 0 ✅ |
| Reseed Scotland registration | 200 ✅ |
| Verify via existing verification mutation | 200 ✅ |
| Queue count after verify | 0 ✅ |

No queue-specific verification path introduced.

## Part 5 — Post-review convergence

- Requirement label: "Evidence recorded" (no orphan "Organisation review pending")
- Cognition stage: `recorded_on_file` (not `org_verification_pending`)
- Not in org queue after resolution ✅
- Today + Command Centre: 200 ✅

## Part 6 — Escalation queue

- **Admin route:** `GET /api/admin/compliance-evidence/escalation-queue` → 200, 4 rows
- **Separation:** zero overlap with document verification queue requirement IDs ✅
- **Truth labels:** "Escalated for platform review", `review_owner=platform_admin_escalation` ✅
- **Browser:** `/admin/compliance-evidence/escalation-queue` visible ✅

## Part 7 — Queue-less regression

- No A/C family rows with `queue_backed_review=true`
- No A/C requirement IDs present in org queue ✅

## Part 8 — Orphan queue audit

`audit_orphan_queue_states()` over full client requirements projection: **0 orphans** ✅

## Part 9 — Today / CC / cognition

- Today + Command Centre load successfully post-resolution ✅
- No stale `org_verification_pending` cognition on resolved requirement ✅

## Part 10 — Role governance

| Check | Result |
|-------|--------|
| Unauthenticated org queue | 401 ✅ |
| ROLE_CLIENT_ADMIN org queue | 200 ✅ |
| Org token on escalation queue | 403 ✅ |
| Admin escalation queue | 200 ✅ |
| `is_org_reviewer_role("ROLE_CLIENT")` | false ✅ |

**Limitation:** `david@yopmail.com` (ROLE_CLIENT) returns HTTP 423 Locked on staging — live 403 not exercised.

## Part 11 — Browser proof

Screenshots in `screenshots/`:

- `01_org_queue.png` — org queue with pending row
- `02_review_deeplink.png` — property deeplink review surface
- `05_post_resolution_org_queue.png` — queue empty post-resolution
- `03_today.png`, `04_command_center.png` — convergence surfaces
- `05_escalation_queue.png` — admin escalation queue

## Classification

**VERIFIED_OPERATIONALLY** — all closeout criteria met.
