# TODAY-PRESENTATION-AUTHORITY-ALIGNMENT-01

**Verdict:** `A_BANNER_ALIGNED_TO_OPERATIONAL_NEEDS_ACTION`  
**Run:** 2026-06-30  
**Branch:** `develop` (staging only — no production, no merge to main)  
**Predecessor audit:** TODAY-AUTHORITY-CONSISTENCY-AUDIT-01

---

## Executive summary

Today presentation now uses a **single governed authority module** (`todayPresentationAuthority.js`) for banner copy, KPI counters, lane lists, list-cap disclosure, and filter semantics.

**Semantic decision: Option A** — the banner describes **operational Needs Action only**, derived from the same bucket classifier as the Needs action KPI and list. Server priority-engine urgent lane counts remain available for continuation disclosure but no longer drive banner wording.

**Work-order global rule:** Urgent/upcoming work orders requiring landlord action classify to `needs_action_now`. Contractor-wait states (`ASSIGNED`, `SCHEDULED`, `AWAITING_VISIT`) classify to `waiting_on_others`. Work orders in the server `in_progress` lane stay in **In progress** and do not inflate the Needs Action banner.

This resolves the Nancy/OPS screenshot pattern (banner 1 urgent, Needs action 0) for urgent-lane work orders without client-specific patches.

---

## Final semantic decision

| Concept | Authority | Used for |
|---------|-----------|----------|
| Priority urgent lane | Server (`summary.urgent_count` / `habit.urgent_open_total`) | Sorting, list-cap continuation disclosure only |
| Operational Needs Action | `classifyTaskOperationalBucket` → `needs_action_now` | Banner, Needs action KPI, hero, Needs action list |
| Waiting | `waiting_on_others` | Waiting KPI and list |
| In progress | `in_progress` (incl. server `in_progress` lane) | In progress KPI and list; urgent-priority items disclosed in lane hint |
| Recently completed | `recently_completed` | Recently completed list |
| Snoozed | Server snoozed section + filters | Snoozed KPI and list |

**Banner copy (Needs Action > 0):**  
“You have **N** item(s) needing action now.”

**Not used:** “You have N urgent item(s) right now” (removed — implied Needs Action when it measured priority lane).

---

## Authority chain (after)

```
GET /api/today/items
    ↓ sections + summary + bucket_continuation
alignTodayPayloadTaskSections (portalRequirementAttention)
    ↓
buildTodayPresentationModel (todayPresentationAuthority.js)  ← SINGLE AUTHORITY
    ├─ classifyTaskOperationalBucket (global WO / approval / requirement rules)
    ├─ buildOperationalSections → lane lists
    ├─ pickPrimaryExecutionTask (from needs_action_now only)
    ├─ banner.needsAction ← counters.needsAction
    ├─ listCap ← bucket_continuation (per-bucket disclosure)
    └─ inProgressDisclosure (priority urgent items in in_progress lane)
ClientTasksPage
    ├─ Banner, KPIs, lanes, empty states, filter notices
    └─ data-testid hooks for regression tests
```

---

## Before / after examples

### A. Urgent work order in server urgent lane (prior bug)

| Surface | Before | After |
|---------|--------|-------|
| Banner | “1 urgent item right now” | “1 item needing action now” |
| Needs action | 0 | 1 |
| In progress | 7 (includes WO) | 6 (WO in Needs action) |

### B. Work order in server in_progress lane

| Surface | Before | After |
|---------|--------|-------|
| Banner | Could show 1 urgent (priority lane) | No Needs Action banner line |
| Needs action | 0 | 0 |
| In progress | 1 | 1 (hint if priority urgent tracked) |

### C. List cap (bucket_continuation.urgent = 9)

| Surface | Before | After |
|---------|--------|-------|
| Banner | Counted all urgent (server) | Counts visible operational needs-action rows |
| Disclosure | Generic “rows are capped” | “9 more priority items needing action exist beyond this list” |

### D. Category filter active

| Surface | Before | After |
|---------|--------|-------|
| Notice | “summary counts include all categories” | “banner, counters, and lists show only filtered category” |
| Counts | Could disagree with lists | Aligned via shared `applyFilter` |

---

## Work-order global rule (documented)

```
section === 'in_progress'           → in_progress
WO status ASSIGNED|SCHEDULED|AWAITING_VISIT → waiting_on_others
source_type === 'work_order' (else) → needs_action_now   [was: always in_progress]
```

Contractor-active jobs remain in In progress when the server places them there. Landlord-action jobs in the urgent/upcoming lanes surface in Needs Action and the banner.

---

## Changed files

| File | Change |
|------|--------|
| `frontend/src/utils/todayPresentationAuthority.js` | **New** — presentation authority, classifier fix, model builder |
| `frontend/src/utils/todayPresentationAuthority.test.js` | **New** — 12 regression scenarios + WO rules |
| `frontend/src/utils/todayExecutionWorkspace.js` | Re-export shim to presentation authority |
| `frontend/src/utils/todayExecutionWorkspace.test.js` | WO classification regression cases |
| `frontend/src/pages/ClientTasksPage.js` | Consume `buildTodayPresentationModel`; banner/KPI/lanes/filters |
| `frontend/src/pages/ClientCommandCenterPage.js` | Neutral Today continuation copy (no “urgent” mismatch) |

**Not changed:** RAOD requirement authority, PAA lifecycle, compliance risk semantics, backend priority engine.

---

## Tests run

```text
npm test -- --testPathPattern="todayPresentationAuthority|todayExecutionWorkspace" --watchAll=false

Test Suites: 2 passed, 2 total
Tests:       24 passed, 24 total
```

Regression scenarios covered in `todayPresentationAuthority.test.js`:

1. Zero urgent items  
2. One urgent item in Needs Action  
3. One urgent work order in server in_progress lane  
4. Multiple urgent split across Needs Action and In Progress  
5. Large urgent list with bucket_continuation  
6. Property filter applied  
7. Category filter applied  
8. Requirements-only urgent items  
9. Work-orders-only urgent items  
10. Mixed requirements and work orders  
11. Fully satisfied landlord  
12. Fresh onboarding landlord  

Each asserts `isSemanticallyConsistent`: banner count = Needs action KPI = visible Needs action list length (incl. hero).

---

## Staging validation recommendation

1. Deploy `develop` frontend to staging (no backend change required).  
2. Impersonate a landlord with an urgent-lane work order — confirm banner count matches Needs action KPI and hero/list.  
3. Impersonate a landlord with in_progress-only jobs — confirm banner does not claim Needs Action.  
4. Apply property and category filters — confirm KPIs match visible lists.  
5. Use a landlord with >8 urgent items — confirm list-cap disclosure appears in banner and KPI card.  
6. Command Centre freshness line — confirm “more items on Today (list capped)” when `urgent_continuation` present.

---

## Remaining risks

| Risk | Mitigation |
|------|------------|
| Command Centre `urgentCount` still uses server `habit.urgent_open_total` for portfolio verdict | CC measures portfolio priority, not Today lanes; Today link copy neutralised |
| Dashboard `/client/today/items` bucket counts | Separate endpoint; may still show server sections — out of scope unless dashboard adds presentation authority |
| Server list caps hide needs-action rows | `buildListCapDisclosure` surfaces overflow; banner counts visible filtered rows only |
| WO status enum drift | Rule uses documented statuses; new statuses default to needs_action_now for urgent-lane WOs |

---

## Production recommendation

**Do not promote until staging sign-off.**

After staging validation:

1. Cherry-pick or merge presentation authority files on a release branch from `develop`.  
2. Frontend-only deploy sufficient.  
3. Re-run Jest suite in CI.  
4. Spot-check one urgent-WO landlord and one satisfied landlord on production after deploy.

**Do not merge to `main` as part of this task.**

---

## Acceptance criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Banner and lane counts no longer mislead | Pass (Option A) |
| 2 | Urgent work orders handled by documented global rule | Pass |
| 3 | Needs Action count and list agree | Pass |
| 4 | In Progress count and list agree | Pass |
| 5 | Banner wording matches source count | Pass |
| 6 | Hidden/continued items disclosed | Pass |
| 7 | Tests pass across mixed task types and filters | Pass (24 tests) |
| 8 | Audit evidence written | Pass |
