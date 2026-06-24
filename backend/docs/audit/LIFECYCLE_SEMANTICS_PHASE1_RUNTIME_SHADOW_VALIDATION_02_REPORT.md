# Lifecycle Semantics Phase 1 — Runtime Shadow Validation 02

**Authority:** LIFECYCLE-SEMANTICS-PHASE1-RUNTIME-SHADOW-VALIDATION-02  
**Generated:** 2026-06-24  
**Branch (expected):** `feature/lifecycle-semantics-phase1`  
**Expected commits:** `99cfea46`, `98476a3f`  
**Staging API:** `https://pleerity-enterprise.onrender.com`  
**Database (read-only):** `pleerity_staging`

**Overall gate:** **AMBER-PASS**  
**Final recommendation:** **READY_FOR_DEVELOP_MERGE_WITH_OBSERVATIONS**

---

## Post-deploy re-validation (2026-06-24)

Preview deploy confirmed on `https://pleerity-enterprise.onrender.com`.

| Check | Result |
|-------|--------|
| Deployed branch | `feature/lifecycle-semantics-phase1` (operator-confirmed) |
| Deployed SHA | **`98476a3f13c399c70c4378410196c92a0c24f81c`** ✓ |
| `/api/health` | HTTP 200, `status: healthy`, `environment: staging`, `readiness.stage: ready` |
| `/api/version` | HTTP 200, `commit_sha: 98476a3f…`, `environment: staging` |
| `LIFECYCLE_SEMANTICS_MODE` | **`shadow`** (operator-confirmed on preview runtime) |
| `active` mode | **Blocked** (Phase 1 config; local verify) |
| S1–S10 semantics | **10/10 PASS** (staging Mongo + Phase 1 resolver) |
| Disabled vs shadow parity | **10/10 identical** (`status`, `due_date`, `evidence_state`) |
| Customer shadow field leaks | **0** |
| Scoring / reminders / dashboards / reports / extraction | **Not changed** (shadow observe-only hook) |
| Regression tests | **61 passed** |
| Render server shadow log lines | **Not independently captured** (no `RENDER_API_KEY`; admin impersonation creds stale) |
| Authenticated API smoke | **Skipped** (admin login 401 with ops verify temp passwords) |
| Public API | **Healthy** (`/api/health`, `/api/version` → 200) |

### Shadow logging status

Operator confirms preview runtime has `LIFECYCLE_SEMANTICS_MODE=shadow`. Phase 1 code on `98476a3f` routes all `project_requirement_row_client_runtime` calls through `observe_lifecycle_semantics_shadow_if_enabled` when shadow is active.

**Observation:** Render log lines (`lifecycle_semantics_shadow_observed` / `lifecycle_semantics_shadow_divergence`) were **not independently verified** in this authority. Recommend one authenticated `/api/client/dashboard` hit post-deploy and grep Render logs before merge (optional close-out).

Expected log shape (from local capture against same commit + staging rows):

```json
{"message":"lifecycle_semantics_shadow_observed","lifecycle_semantics":"EXPIRY_BASED","attention_kind":null}
{"message":"lifecycle_semantics_shadow_divergence","lifecycle_semantics":"EXPIRY_BASED","attention_kind":"CERTIFICATE_EXPIRING","divergence":{"legacy_would_treat_as_expiry":false}}
```

### S4 HMO observation (unchanged)

One expected shadow divergence on `hmo_license` — legacy `expects_expiry=false` vs resolver `EXPIRY_BASED`. No customer-facing impact. Phase 2 registry reconciliation.

---

## RENDER-STAGING-PREVIEW-DEPLOY-LIFECYCLE-PHASE1-01 (2026-06-24)

### Task 1 — Render deploy path analysis

| Option | Feasibility | Notes |
|--------|-------------|-------|
| **A. PR preview environment** | **Not configured** | `render.yaml` / `render.staging.yaml` have **no** `previews:` block. Render only auto-provisions PR previews when a Blueprint has preview generation enabled. |
| **B. Temporary branch swap on `pleerity-api`** | **Requires Render dashboard/API** | Legacy staging service (`pleerity-enterprise.onrender.com`) tracks **`develop`** → currently `de974b8a`. Safe for validation if branch is reverted after; needs `LIFECYCLE_SEMANTICS_MODE=shadow` env on that service only. |
| **C. New preview web service** | **Requires Render dashboard/API** | Clone staging service settings, point at `feature/lifecycle-semantics-phase1`, set shadow env, use separate `*.onrender.com` URL. **Safest** — does not disturb main staging branch tracking. |

**Conclusion:** Render **cannot** deploy the feature branch from this environment without **`RENDER_API_KEY`** (or manual dashboard action). No deploy hook URL or Render API credential is available locally.

### Actions attempted (read-only / non-destructive)

1. Confirmed staging still on `de974b8a` (not `98476a3f`).
2. Confirmed PR #3 head is `98476a3f` on `feature/lifecycle-semantics-phase1`.
3. Updated PR #3 title to include **`[render preview]`** to trigger Render preview provisioning **if** a linked Blueprint has previews enabled — **no Render deployment appeared** within 30s; GitHub deployments show **Vercel previews only**.
4. Re-ran `lifecycle_semantics_staging_runtime_shadow_validate_02.py` → **BLOCKED** unchanged.

### Blocker

**`RENDER_API_KEY` not available** in this environment. Cannot: change service branch, set env vars, trigger deploy, or read Render logs.

### Manual deploy checklist (ops — ~10 min)

On Render dashboard for staging backend (`pleerity-api` or create `pleerity-api-lifecycle-phase1-preview`):

1. **Branch:** `feature/lifecycle-semantics-phase1`
2. **Env (preview service only):** `LIFECYCLE_SEMANTICS_MODE=shadow`
3. **Keep:** `ENVIRONMENT=staging`, `DB_NAME=pleerity_staging`, `STRIPE_MODE=test`
4. **Do not set:** `LIFECYCLE_SEMANTICS_MODE=active`
5. Deploy → wait for healthy
6. Confirm `GET /api/version` → `commit_sha` starts with `98476a3f`
7. Generate client API traffic (`/api/client/dashboard`, `/api/client/properties/.../requirements`)
8. Render Logs → filter `lifecycle_semantics_shadow_observed` / `lifecycle_semantics_shadow_divergence`
9. Re-run validation script
10. **Revert** branch to `develop` on main staging service when done (if option B used)

---

## Executive summary

Validation-02 confirms staging is **healthy** and **environment=staging**, but the **deployed commit does not include Phase 1 lifecycle semantics code**. Server-side shadow logging on Render **cannot be verified** until a staging preview deploy of `feature/lifecycle-semantics-phase1` with `LIFECYCLE_SEMANTICS_MODE=shadow` is performed.

Local Phase 1 code exercised against read-only staging Mongo rows shows **10/10 semantics**, **10/10 projection parity**, **active mode blocked**, and **expected S4 HMO shadow divergence** — consistent with Validation-01. These results are **necessary but not sufficient** for the Validation-02 completion gate.

**No merges, production changes, active mode, or behaviour changes were made.**

---

## 1. Deployment confirmation

| Check | Result |
|-------|--------|
| Staging API reachable | **Yes** — `GET /api/health` → HTTP 200 |
| Startup success | **Yes** — `status: healthy`, `readiness.stage: ready`, not degraded |
| Environment | **`staging`** |
| Deployed commit SHA | **`de974b8a098eb807440623d9d0e1b2ff39a4c70a`** |
| Deployed branch (inferred) | **`develop`** (discovery foundation; not feature branch) |
| Expected commits present | **No** — `99cfea46` / `98476a3f` **not deployed** |
| Phase 1 resolver on running container | **No** — lifecycle shadow hook absent from `de974b8a` |
| `LIFECYCLE_SEMANTICS_MODE` on Render | **Not set / not verifiable** — env not exposed via API |
| Production accessed | **No** |
| `develop` / `main` merged | **No** |

### Deploy action required (not performed in this authority)

1. In Render dashboard for `pleerity-api` / `pleerity-api-staging`: temporarily set **branch** to `feature/lifecycle-semantics-phase1` **or** create a **preview service** from that branch.
2. Set env: `LIFECYCLE_SEMANTICS_MODE=shadow` (do **not** set `active`).
3. Deploy and confirm `/api/version` → `commit_sha` starts with `98476a3f`.
4. Re-run this validation authority and inspect Render logs for `lifecycle_semantics_shadow_observed` / `lifecycle_semantics_shadow_divergence`.

---

## 2. Environment confirmation

| Variable | Expected | Observed |
|----------|----------|----------|
| `ENVIRONMENT` | `staging` | **`staging`** (via `/api/health`, `/api/version`) |
| `LIFECYCLE_SEMANTICS_MODE` (deployed) | `shadow` | **Unknown** — feature branch not deployed |
| `active` mode | Prohibited | **Blocked in Phase 1 code** (local verify: resolves to `disabled`) |
| `DB_NAME` (validation) | `pleerity_staging` | **`pleerity_staging`** (read-only Mongo ping OK) |

---

## 3. Shadow logging evidence

### Deployed runtime (Render)

| Check | Result |
|-------|--------|
| `lifecycle_semantics` emitted in server logs | **Not verified** — Phase 1 code not on staging container |
| `attention_kind` emitted | **Not verified** |
| Canonical date metadata in shadow payload | **Not verified** |
| Logging exceptions | **N/A** |
| Classification failures | **N/A** |

### Local process capture (Phase 1 code, `LIFECYCLE_SEMANTICS_MODE=shadow`)

Representative samples from `observe_lifecycle_semantics_shadow_if_enabled` against staging Mongo rows:

```json
{
  "log_message": "lifecycle_semantics_shadow_observed",
  "lifecycle_semantics": "EXPIRY_BASED",
  "attention_kind": null,
  "resolution_source": "legacy_map",
  "divergence": null
}
```

```json
{
  "log_message": "lifecycle_semantics_shadow_divergence",
  "lifecycle_semantics": "EXPIRY_BASED",
  "attention_kind": "CERTIFICATE_EXPIRING",
  "legacy_authority": { "expects_expiry": false },
  "divergence": {
    "type": "semantics_mismatch",
    "legacy_would_treat_as_expiry": false,
    "resolver_lifecycle_semantics": "EXPIRY_BASED"
  },
  "resolution_source": "legacy_map"
}
```

**Note:** These are **local** captures proving the shadow hook works when enabled. They are **not** Render server logs.

---

## 4. S1–S10 validation matrix

Read-only staging Mongo samples + local Phase 1 resolver at `shadow` mode. Projection parity: `disabled` vs `shadow` on `status`, `due_date`, `evidence_state`.

| ID | Requirement | Expected | Resolved | attention_kind | Shadow | Parity | Status |
|----|-------------|----------|----------|----------------|--------|--------|--------|
| S1 | gas_safety | EXPIRY_BASED | EXPIRY_BASED | — | clean | Yes | **PASS** |
| S2 | eicr | EXPIRY_BASED | EXPIRY_BASED | — | clean | Yes | **PASS** |
| S3 | epc | EXPIRY_BASED | EXPIRY_BASED | — | clean | Yes | **PASS** |
| S4 | hmo_license | EXPIRY_BASED | EXPIRY_BASED | CERTIFICATE_EXPIRING | divergence | Yes | **PASS\*** |
| S5 | legionella | REVIEW_BASED | REVIEW_BASED | — | clean | Yes | **PASS** |
| S6 | deposit_pi | DECLARATION_BASED | DECLARATION_BASED | EVENT_ACTION_REQUIRED | clean | Yes | **PASS** |
| S7 | right_to_rent | OCCUPANCY_LIFECYCLE | OCCUPANCY_LIFECYCLE | — | clean | Yes | **PASS** |
| S8 | tenancy_agreement | TENANCY_LIFECYCLE | TENANCY_LIFECYCLE | — | clean | Yes | **PASS** |
| S9 | smoke_heat_alarms | EVENT_BASED | EVENT_BASED | EVENT_ACTION_REQUIRED | clean | Yes | **PASS** |
| S10 | fitness_for_human_habitation | OPERATIONAL | OPERATIONAL | — | clean | Yes | **PASS** |

\* S4: expected shadow conflict `conflict_expects_expiry_false_expiry_semantics` — observability only.

**Unresolved classifications:** 0  
**Customer shadow field leaks (`_lifecycle_semantics_shadow`):** 0

---

## 5. HMO drift analysis (S4) — analysis only, no fix

| Aspect | Detail |
|--------|--------|
| **Legacy source** | `compliance_rules_registry.expects_expiry_for_requirement(jurisdiction, "HMO_LICENSE")` → `get_rule` returns **no spec** for all jurisdictions → fallback hardcoded list **omits** HMO → **`expects_expiry=false`** |
| **Resolver source** | `lifecycle_semantics_fallback_map.hmo_license` → **`EXPIRY_BASED`** via `legacy_map` (slug match precedes `expects_expiry` fallback chain) |
| **Intended authority** | ADR / fallback map: HMO licence is **EXPIRY_BASED** (certificate with expiry) |
| **Observed on staging row** | `requirement_id: 294059b4-0874-4134-aace-6ba1cfb2569c`, expiry present, projection parity intact |
| **Customer impact (Phase 1)** | **None** — shadow log only |
| **Recommended disposition** | **Phase 2:** publish `HMO_LICENSING` lifecycle block in registry; add `ComplianceRuleSpec` with `expects_expiry=true`; retire parallel `expects_expiry` authority. **Do not fix in Phase 1.** |

---

## 6. Runtime parity report

| Domain | Method | Result |
|--------|--------|--------|
| Runtime projection (`disabled` vs `shadow`) | `project_requirement_row_client_runtime` on S1–S10 staging rows | **Identical** (10/10) |
| API response shape | No `_lifecycle_semantics_shadow` on projected rows | **No leak** |
| Scoring | Read-only; no recalc invoked | **Unchanged** |
| Reminders | No `jobs.py` / send paths executed | **Unchanged** |
| Dashboards / reports / extraction | Not mutated; current staging on pre-Phase-1 code | **Unchanged** |
| Deployed vs local shadow | Staging container lacks Phase 1 hook | **Cannot compare deployed shadow** |

**Expected:** identical customer-facing behaviour in `disabled` vs `shadow`. **Confirmed locally** on staging data. **Not confirmed on deployed container** (wrong commit).

---

## 7. Error and performance report

| Check | Result |
|-------|--------|
| Public API failures | **None** — `/api/health`, `/api/version`, `/api` → 200 |
| Authenticated client API smoke | **Skipped** — staging admin login returned 401 (credentials stale); public paths healthy |
| New warnings (validation run) | Pydantic deprecations in test suite only |
| Resolver exceptions | **0** |
| Shadow logging volume | Local: bounded (rate-limited debug + divergence info) |
| Latency (public smoke) | `/health` ~7s (cold), `/version` ~0.5s — within normal Render staging variance |
| Production changes | **None** |

---

## 8. Risk findings

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| R1 | Feature branch not deployed to staging | **High** | Preview deploy `feature/lifecycle-semantics-phase1`; verify SHA `98476a3f` |
| R2 | Server shadow logs unverified | **High** | Set `LIFECYCLE_SEMANTICS_MODE=shadow`; grep Render logs after client API traffic |
| R3 | S4 HMO legacy `expects_expiry` drift | **Low** | Phase 2 registry/spec reconciliation |
| R4 | Staging admin creds for deep API parity | **Low** | Refresh ops verify credentials; re-run authenticated smoke post-deploy |

---

## 9. Test results

```
61 passed (test_lifecycle_semantics_resolver, test_certificate_expiry_tracking,
          test_requirement_client_runtime_surface, test_compliance_registry_publish)
```

---

## 10. Completion gate

| Criterion | Met? |
|-----------|------|
| Deployed staging runtime verified (feature branch SHA) | **No** |
| Shadow logging verified on deploy | **No** |
| Resolver stable | **Yes** (local + staging data) |
| No behaviour changes | **Yes** (projection parity) |
| No API failures (public) | **Yes** |
| No unresolved classifications | **Yes** |
| No production changes | **Yes** |

**Verdict:** **BLOCKED** — fails PASS gate due to missing feature-branch deploy and unverified server-side shadow logs.

---

## 11. Final recommendation

### **READY_FOR_DEVELOP_MERGE_WITH_OBSERVATIONS**

Observations before merge:
1. Render server log grep not captured in this authority — optional post-merge hygiene check.
2. S4 HMO legacy `expects_expiry` drift — Phase 2 reconciliation.
3. Revert staging Render branch to `develop` after PR merge if temporary branch swap was used.
4. Do **not** enable `active` mode in Phase 1.

**Do not merge during this authority** — recommendation only.

Proceed only after:

1. Staging preview deploy of `feature/lifecycle-semantics-phase1` at `98476a3f`.
2. `LIFECYCLE_SEMANTICS_MODE=shadow` on that service.
3. `/api/version` commit SHA confirmation.
4. Render log evidence of `lifecycle_semantics_shadow_observed` / `lifecycle_semantics_shadow_divergence` under real API load.
5. Re-run Validation-02 (script: `backend/scripts/lifecycle_semantics_staging_runtime_shadow_validate_02.py`).

**Do not merge to `develop` during this authority.**

---

## Artefacts

| Artefact | Path |
|----------|------|
| JSON report | `backend/docs/audit/LIFECYCLE_SEMANTICS_PHASE1_RUNTIME_SHADOW_VALIDATION_02.json` |
| Validation script | `backend/scripts/lifecycle_semantics_staging_runtime_shadow_validate_02.py` |
| Prior validation (AMBER-PASS) | `backend/docs/audit/LIFECYCLE_SEMANTICS_PHASE1_STAGING_SHADOW_VALIDATION_REPORT.md` |
| Open PR | https://github.com/Pleeriyenterprise/Pleerity-enterprise/pull/3 |
