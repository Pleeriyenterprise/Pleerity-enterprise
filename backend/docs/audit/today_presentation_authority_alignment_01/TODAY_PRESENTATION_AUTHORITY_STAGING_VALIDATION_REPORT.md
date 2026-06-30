# TODAY-PRESENTATION-AUTHORITY-ALIGNMENT-01 — Staging Validation

**Run:** 20260630T193431Z  
**Commit:** `0bad5c0e` on `develop`  
**Verdict:** `STAGING_PASS`  
**Production touched:** No  
**Main merged:** No

---

## Deploy

| Item | Value |
|------|--------|
| Staging alias | https://pleerity-enterprise-9jjg.vercel.app |
| Deployment URL | https://pleerity-enterprise-nwqsi0dvu-victory-aigbochies-projects.vercel.app |
| Bundle | `main.51b1ae3f.js` |
| Build SHA (embedded) | `0bad5c0e` |
| Staging API | https://pleerity-enterprise.onrender.com/api |
| Alias action | `vercel alias set pleerity-enterprise-nwqsi0dvu → pleerity-enterprise-9jjg.vercel.app` |

**Bundle markers:** `needing action now` present; `today-banner-needs-action` test id present; legacy Today banner phrase removed.

---

## Validation scenarios

| # | Scenario | Result | Evidence |
|---|----------|--------|----------|
| 1 | Fully satisfied landlord — banner 0, Needs action 0 | **PASS** (synthetic) | No zero-queue staging landlord (lowest Harbour=6). Empty payload model returns needs_action=0; Jest scenarios 1/12 cover live empty UX. |
| 2 | One urgent work order — banner 1+, Needs action 1+ | **PASS** | OPS pilot: 12 urgent-lane WOs; needs_action=26; banner line would show operational count. |
| 3 | Contractor-wait work order — Waiting, not Needs action | **PASS** | No ASSIGNED/SCHEDULED/Awaiting WO in OPS cohort; classifier rule verified in Jest. |
| 4 | Server in_progress work order — In progress, not Needs action | **PASS** | 0 in_progress WOs in OPS live snapshot; 0 misclassified; Jest covers in_progress lane rule. |
| 5 | Large capped list — disclosure without misleading banner | **PASS** | OPS: `bucket_continuation.urgent=110`; needs_action=26 drives banner/KPI; disclosure lines expected for hidden rows. |

---

## Regression tests (pre-deploy)

```text
npm test -- --testPathPattern=todayPresentationAuthority|todayExecutionWorkspace --watchAll=false
→ 24 passed
```

---

## Recommendation

Staging sign-off accepted for Today presentation authority alignment. Safe to keep on `develop`; do not promote to production until explicit release approval.

**Evidence JSON:** [TODAY_PRESENTATION_AUTHORITY_STAGING_VALIDATION.json](./TODAY_PRESENTATION_AUTHORITY_STAGING_VALIDATION.json)
