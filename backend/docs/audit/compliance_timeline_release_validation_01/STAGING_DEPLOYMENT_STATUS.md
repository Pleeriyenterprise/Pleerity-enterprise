# Staging Deployment Status

**Programme:** COMPLIANCE-TIMELINE-PHASE-1-AND-2-RELEASE-VALIDATION-01  
**Validated at:** 2026-06-02 (read-only, no environment changes)

## Verdict: **FAIL — deployed SHA does not include Compliance Timeline programme**

Staging runs the same commit as `origin/develop` (`29fbe355`), which predates the Compliance Timeline implementation.

---

## Backend (Render staging)

| Check | Value |
|---|---|
| URL | `https://pleerity-enterprise.onrender.com` |
| `/api/health` | `{"status":"healthy","environment":"staging","readiness":{"stage":"ready","degraded":false}}` |
| `/api/version` | `commit_sha: 29fbe35599213686931a7e45ac9902e263d4f3d9`, `environment: staging` |
| Matches local `origin/develop` | **Yes** |
| Matches local Compliance Timeline work | **No** |

**Phase 1 on staging:** Absent — `compliance_timeline.py` not in deployed tree.  
**Phase 2 on staging:** Absent — no presentation layer, no consumer migrations.

---

## Frontend (Vercel staging alias)

| Check | Value |
|---|---|
| Alias | `https://pleerity-enterprise-9jjg.vercel.app` |
| Bundle | `main.67a36506.js` (observed 2026-06-02) |
| Baked commit (in bundle) | `29fbe355` (confirmed string present) |
| API target in bundle | `pleerity-enterprise.onrender.com` (staging backend) |

**Phase 2 bundle markers:**

| Symbol | Present on staging |
|---|---|
| `getTimelineDateLabel` | **No** |
| `timeline_primary_date_label` | **No** |
| `complianceTimelinePresentation` module | **No** |
| `compliance_timeline` string | Yes (unrelated admin/audit usage — not Phase 2 consumer utility) |

---

## Mixed deployment check

| Layer | SHA / artefact | Programme present |
|---|---|---|
| Backend staging | `29fbe355` | **No** |
| Frontend staging | `29fbe355` + `main.67a36506.js` | **No** |
| Local working tree | Uncommitted timeline work | **Yes (not deployed)** |

**No mixed Phase-1-only / Phase-2-only deployment detected** — both layers lack the programme entirely.

---

## Deployment health

- Backend readiness: **ready**, not degraded
- Frontend: serves index and JS bundle (HTTP 200)
- Auth-gated API: `/api/client/requirements` → `401 Not authenticated` (expected without session)

---

## Blockers before staging re-validation

1. Commit and push Phase 1 + Phase 2 to `origin/develop`
2. Deploy backend staging from new SHA
3. Deploy frontend staging bundle from same SHA
4. Re-run payload, cross-surface, and family validation with authenticated staging session
