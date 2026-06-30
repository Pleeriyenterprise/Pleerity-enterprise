# PRESENTATION-AUTHORITY-ALIGNMENT-01-STAGING-VALIDATION-01

**Verdict:** `STAGING_BACKEND_ACCEPTED_FRONTEND_PENDING`  
**Run:** 20260630T162517Z  
**Staging API SHA:** `8a83036543afea5a4a3e7ceb8e47964f2643ac3f`

---

## Backend validation (PASS)

| Check | Result |
|-------|--------|
| Local RAOD + PAA pytest | PASS (9) |
| Staging API at `8a830365` | PASS |
| Setup-status semantic fields | PASS |
| Onboarding count applicable (18 identified / 12 tracked) | PASS |
| Checklist `setup_presentation` backend | PASS |
| Monthly digest lifecycle copy | PASS |

### Setup-status sample

```json
{
  "requirements_count": 18,
  "requirements_tracked_attention_count": 12,
  "requirements_runtime_visible_count": 12,
  "requirements_count_semantics": "tracked_attention_document_job_excludes_obligation"
}
```

---

## Frontend probe investigation

### Why the initial probe failed

The validation harness requested `https://pleerity-enterprise.onrender.com/` expecting SPA HTML with `/static/js/*.js`. That URL is the **Render staging API service** (`pleerity-api-staging`), not the client portal.

Root response (108 bytes JSON):

```json
{"service":"Compliance Vault Pro","api":"/api","health":"/api/health","docs":"/docs","status":"operational"}
```

No React bundle exists at the API origin — this is expected architecture, not a deploy failure.

### Canonical staging frontend URL

| Role | URL | Source |
|------|-----|--------|
| Staging API | `https://pleerity-enterprise.onrender.com` | `render.staging.yaml` |
| Staging frontend (SPA) | `https://pleerity-enterprise-9jjg.vercel.app` | `render.staging.yaml` → `APP_BASE_URL` |

### Vercel bundle probe (post-investigation)

| Signal | Result |
|--------|--------|
| Bundle | `/static/js/main.bef35a51.js` |
| PAA “Actively tracked” copy | **Absent** |
| PAA calendar verdict copy | **Absent** |
| Legacy “affecting compliance” | **Still present** |

**Conclusion:** Frontend is probeable at the Vercel URL but the deployed bundle **predates** `8a830365`. UI browser walkthrough remains blocked until Vercel preview deploy from `develop`.

---

## Production recommendation

**Do not promote** until:

1. Vercel staging frontend deploys from `develop` @ `8a830365` or later  
2. Browser walkthrough passes (onboarding counts, documents wizard, OVERDUE chips, Command Centre lens)

---

## Harness fix (follow-up)

Update `tmp_presentation_authority_staging_validation_01.py` to probe `APP_BASE_URL` / Vercel frontend, not the Render API root.
