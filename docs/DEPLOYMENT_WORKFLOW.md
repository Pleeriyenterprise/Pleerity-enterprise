# Pleerity Enterprise — Staging-to-Production Deployment Workflow

This document formalises how Cursor, developers, and CI/CD promote tested changes from **staging** to **production** without cross-contaminating data, secrets, or payment modes.

**Current state (audit):** A single Render service (`pleerity-api`) and Vercel production domain share one operational stack with `pleerity_staging` data. Production infrastructure is **documented but not provisioned yet**. Follow this workflow when splitting environments.

---

## 1. Branch strategy

| Branch | Purpose | Deploys to |
|--------|---------|------------|
| **`main`** | Production-ready code only | Production Render + Vercel production (after approval) |
| **`develop`** | Integration / staging | Staging Render + Vercel preview/staging (auto-deploy) |
| **`feature/*`** | Individual fixes and features | None (CI only) |
| **`hotfix/*`** | Urgent production fixes | Staging first, then fast-track to `main` |

### Rules

- **Never** commit directly to `main` (branch protection required).
- **Always** branch from `develop` for features: `feature/short-description`.
- **Merge** feature → `develop` via PR; staging auto-deploys.
- **Promote** `develop` → `main` only after staging verification checklist passes.
- **Hotfix:** branch from `main` → `hotfix/issue` → PR to `main` **and** back-merge to `develop`.

### Bootstrap (one-time)

```bash
git checkout main
git pull origin main
git checkout -b develop
git push -u origin develop
```

Configure Render staging service to track `develop`. Keep production Render on `main` (manual deploy recommended).

---

## 2. Render deployment separation

Two **separate** Render Web Services — never share disks, secrets, or databases.

| Setting | Staging (`pleerity-api-staging`) | Production (`pleerity-api-production`) |
|---------|----------------------------------|------------------------------------------|
| **Blueprint** | `render.staging.yaml` | `render.production.yaml` |
| **Git branch** | `develop` | `main` |
| **Auto-deploy** | ON | OFF (manual after approval) |
| **`DEPLOYMENT_TIER`** | `staging` | `production` |
| **`ENVIRONMENT`** | `staging` | `production` |
| **`DB_NAME`** | `pleerity_staging` | `pleerity_production` |
| **`STRIPE_MODE`** | `test` | `live` |
| **Disk** | `pleerity-data-staging` (new) | `pleerity-data-production` (new, empty) |
| **`JWT_SECRET`** | Staging-only value | Unique production value |
| **Stripe keys** | `STRIPE_SECRET_KEY_TEST`, `STRIPE_WEBHOOK_SECRET_TEST` | `STRIPE_SECRET_KEY_LIVE`, `STRIPE_WEBHOOK_SECRET_LIVE` |
| **Postmark** | Staging server/token | Production server/token |
| **`APP_BASE_URL`** | Staging frontend URL | `https://pleerityenterprise.co.uk` |
| **`API_BASE_URL`** | Staging API URL | `https://api.pleerityenterprise.co.uk` |

### Legacy service (`pleerity-api`)

The existing `render.yaml` / `pleerity-api` service is the **current combined stack**. Retain it as staging until production is provisioned, then:

1. Point staging Render at `develop` + `render.staging.yaml` env.
2. Create new production service from `render.production.yaml`.
3. Do **not** copy staging disk or database to production.

### Startup guardrails

`backend/utils/deployment_environment_guard.py` runs at API boot (unless `SKIP_DEPLOYMENT_GUARD=1` or `PYTEST_RUNNING=1`):

**Production refuses boot if:**

- `DB_NAME` contains `staging`
- `STRIPE_MODE` ≠ `live`
- `APP_BASE_URL` or `API_BASE_URL` resolve to localhost, `*.vercel.app`, `pleerity-enterprise.onrender.com`, or `staging.*`
- `JWT_SECRET` missing or default placeholder

**Staging refuses boot if:**

- `STRIPE_MODE=live`
- `DB_NAME=pleerity_production`
- Production frontend/API URLs configured **when `DEPLOYMENT_TIER=staging` is set explicitly**

Until `DEPLOYMENT_TIER=staging` is set, production URL mismatches on staging log **warnings** only (migration path for the legacy single stack).

---

## 3. Vercel deployment separation

| Setting | Staging | Production |
|---------|---------|------------|
| **Project / env** | Preview or `staging` project | Production project |
| **Domain** | `https://pleerity-enterprise-9jjg.vercel.app` (Vercel develop preview) or `staging.pleerityenterprise.co.uk` when DNS live | `pleerityenterprise.co.uk` |
| **`APP_BASE_URL` (Render staging)** | `https://pleerity-enterprise-9jjg.vercel.app` | `https://pleerityenterprise.co.uk` |
| **`REACT_APP_BACKEND_URL`** | Staging API URL | `https://api.pleerityenterprise.co.uk` |
| **Stripe publishable** | `REACT_APP_STRIPE_PUBLISHABLE_KEY_TEST` | `REACT_APP_STRIPE_PUBLISHABLE_KEY_LIVE` |
| **Deploy branch** | `develop` (auto) | `main` (manual promote) |

### `REACT_APP_BACKEND_URL`

- Set **only** in Vercel environment variables — **never** hardcode in `frontend/src/`.
- Verified: application code reads `process.env.REACT_APP_BACKEND_URL` (`frontend/src/api/client.js`).
- Dev fallback: `frontend/src/setupProxy.js` proxies to localhost when unset.

---

## 4. Cursor / developer workflow

### Daily feature work

```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-change
# … edit in Cursor …
cd backend && python -m pytest tests/test_deployment_environment_guard.py -q
cd ../frontend && npm test -- --watchAll=false --passWithNoTests 2>/dev/null | tail -5
git add -p
git commit -m "feat(area): description"
git push -u origin feature/my-change
```

Open PR: `feature/my-change` → `develop`.

### Deploy to staging

1. Merge PR to `develop`.
2. Render staging auto-deploys (watch Render dashboard).
3. Vercel staging/preview deploys from `develop`.
4. Run **Staging verification checklist** (below).

### Promote to production

1. Confirm staging checklist **all passed**.
2. Open PR: `develop` → `main` (release PR with summary).
3. Wait for CI (backend tests + deployment governance gate).
4. Obtain **manual approval** (code owner).
5. Merge to `main`.
6. **Manually** trigger production Render deploy (if auto-deploy off).
7. Promote Vercel production deployment.
8. Run **Production promotion checklist** (below).
9. Monitor logs, Stripe webhooks, Postmark for 30 minutes.

### Hotfix

```bash
git checkout main && git pull
git checkout -b hotfix/critical-fix
# minimal fix only
git push -u origin hotfix/critical-fix
```

1. PR → `main` (expedited review).
2. Deploy production after CI + approval.
3. **Back-merge** `main` → `develop` immediately.

### Before every merge — required commands

```bash
# Backend
cd backend
PYTHONPATH=. python -m pytest tests -q --tb=no
PYTHONPATH=. python scripts/deployment_governance_ci_gate.py
PYTHONPATH=. python scripts/semantic_governance_ci_gate.py

# Frontend (when UI touched)
cd frontend
npm test -- --watchAll=false
npm run build
```

### Never do

- Push directly to `main`.
- Set `STRIPE_MODE=live` on staging.
- Point staging `DB_NAME` at `pleerity_production`.
- Copy staging MongoDB or Render disk into production.
- Share `JWT_SECRET`, Stripe keys, or Postmark tokens between environments.
- Set `SKIP_DEPLOYMENT_GUARD=1` on production (emergency staging only).
- Commit `.env`, credentials, or `sk_live_` / `whsec_` strings.
- Hardcode `pleerity-enterprise.onrender.com` in `frontend/src/` (use `REACT_APP_BACKEND_URL`).
- Enable `RENT_REMINDERS_PRODUCTION_MODE` on staging.

---

## 5. GitHub branch protections (recommended)

Configure in **GitHub → Settings → Branches → Branch protection rules**:

### `main`

- [ ] Require pull request before merging
- [ ] Require approvals: **1** (minimum; 2 for pilot launch week)
- [ ] Require status checks: `Backend tests`, `Deployment governance`
- [ ] Require branches to be up to date before merging
- [ ] Do not allow bypassing the above settings
- [ ] Restrict who can push to matching branches
- [ ] Do not allow force pushes

### `develop`

- [ ] Require pull request before merging (optional: allow maintainer direct push)
- [ ] Require status checks: `Backend tests`, `Deployment governance`
- [ ] Allow force push: **disabled**

### Environment protection (GitHub Environments)

Create **production** environment with required reviewers for workflow jobs that deploy production (when added).

---

## 6. CI checks

Workflows in `.github/workflows/`:

| Workflow | Triggers | Purpose |
|----------|----------|---------|
| `backend-tests.yml` | PR/push to `main`, `develop` | Full pytest + semantic governance |
| `deployment-governance.yml` | PR/push to `main`, `develop` | Secrets scan, staging URL in frontend, production blueprint |

Governance gate (`backend/scripts/deployment_governance_ci_gate.py`) blocks:

- Committed `sk_live_`, `pk_live_`, `whsec_`, MongoDB URIs with credentials in app code
- Hardcoded `pleerity-enterprise.onrender.com` in `frontend/src/` (except `setupProxy.js`)
- `pleerity_staging` or `STRIPE_MODE=test` in `render.production.yaml`

---

## 7. Staging verification checklist

Run after every staging deploy before promoting to `main`.

### Auth & onboarding

- [ ] Client login (`/login/client`)
- [ ] Admin login (`/admin/signin`)
- [ ] Password reset / set-password email links use **staging** `APP_BASE_URL`
- [ ] New intake submission (test email)
- [ ] Onboarding / provisioning completes

### Billing (test mode only)

- [ ] `STRIPE_MODE=test` confirmed in staging Render env
- [ ] Checkout completes with Stripe test card `4242…`
- [ ] Webhook received at staging API (`/api/webhook/stripe`)
- [ ] Subscription status updates in portal

### Core product

- [ ] Document upload + download
- [ ] Compliance score / requirements visible
- [ ] Admin dashboard loads
- [ ] Operations modules (if entitled test user)

### Safety

- [ ] Rent reminders **not** sent to real tenant emails (allowlist / yopmail only)
- [ ] Test emails go to staging Postmark stream / safe inboxes
- [ ] No live Stripe charges (`sk_live_` not used)
- [ ] `DB_NAME=pleerity_staging` confirmed

### Technical

- [ ] `/api/health` returns 200
- [ ] Startup logs show `Deployment guard OK: tier=staging`
- [ ] No CRITICAL storage path warnings (`/tmp` in production paths)

---

## 8. Production promotion checklist

Complete **after** merging to `main` and **before** announcing pilot availability.

### Pre-deploy

- [ ] Staging verification checklist passed on release commit
- [ ] DB migrations / index changes reviewed (idempotent seeds only)
- [ ] Release notes written
- [ ] Rollback plan: previous Render deploy ID + Vercel deployment noted

### Environment

- [ ] `DEPLOYMENT_TIER=production`, `ENVIRONMENT=production`
- [ ] `DB_NAME=pleerity_production` (empty or pilot-seeded only)
- [ ] `STRIPE_MODE=live` + live keys + **separate** webhook secret
- [ ] Stripe Dashboard webhook → `https://api.pleerityenterprise.co.uk/api/webhook/stripe`
- [ ] `JWT_SECRET` unique (not staging value)
- [ ] `APP_BASE_URL` / `API_BASE_URL` production URLs set
- [ ] `REACT_APP_BACKEND_URL` production API in Vercel production env
- [ ] Postmark production server + templates
- [ ] Atlas backup enabled on production cluster

### Post-deploy smoke

- [ ] `/api/health` 200; logs show `Deployment guard OK: tier=production`
- [ ] Login (pilot account)
- [ ] Stripe **live** webhook test event (Dashboard → Send test webhook)
- [ ] One document upload on production disk
- [ ] Admin alert email configured (`ADMIN_ALERT_EMAILS`)

### Rollback

If production smoke fails:

1. Roll back Render to previous deploy.
2. Roll back Vercel production deployment.
3. Do **not** run destructive DB scripts; investigate with logs.
4. Fix on `develop`, re-verify staging, re-promote.

---

## 9. Reference files

| File | Purpose |
|------|---------|
| `render.staging.yaml` | Staging Render blueprint |
| `render.production.yaml` | Production Render blueprint (provision when approved) |
| `render.yaml` | Legacy single-service reference |
| `backend/utils/deployment_environment_guard.py` | Boot-time tier validation |
| `backend/scripts/deployment_governance_ci_gate.py` | CI governance script |
| `docs/URL_ENVIRONMENT.md` | URL env var reference |
| `backend/docs/STRIPE_MODE_GOVERNANCE.md` | Stripe live/test governance |

---

## 10. Migration from current single stack

**Do not provision production until explicitly approved.**

1. Create `develop` branch; point existing Render at `develop` + staging env vars.
2. Set `DEPLOYMENT_TIER=staging` on existing service when staging URLs are ready.
3. Create Vercel staging env pointing at staging API.
4. When ready, provision **new** production Render + `pleerity_production` DB (empty).
5. Point `main` deploys and `pleerityenterprise.co.uk` at production only after promotion checklist passes.

The legacy combined stack remains usable during migration; startup guards warn (not refuse) on URL mismatches until `DEPLOYMENT_TIER=staging` is explicit.
