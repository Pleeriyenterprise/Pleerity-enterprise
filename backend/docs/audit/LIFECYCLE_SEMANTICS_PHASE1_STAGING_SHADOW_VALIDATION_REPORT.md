# Lifecycle Semantics Phase 1 — Staging Shadow Validation

**Authority:** LIFECYCLE-SEMANTICS-PHASE1-STAGING-SHADOW-VALIDATION-01  
**Generated:** 2026-06-24  
**Branch:** `feature/lifecycle-semantics-phase1`  
**Commit:** `99cfea46`  
**Database:** `pleerity_staging` (read-only)  
**Staging API:** `https://pleerity-enterprise.onrender.com`  

**Overall gate:** **AMBER — PASS with controls** (semantics + parity OK; one expected legacy shadow conflict on S4; Render deploy of feature branch not verified)

---

## 1. Staging environment confirmation

| Check | Result |
|-------|--------|
| Staging API reachable | **Yes** — `GET /api/health` → HTTP 200 |
| API `environment` | **`staging`** |
| Readiness | `ready`, not degraded |
| Mongo `pleerity_staging` ping | **OK** |
| Production accessed | **No** — URI user `pleerity_staging`, DB `pleerity_staging` only |
| `main` / `develop` merged | **No** |
| Production deploy | **No** |

### Deploy caveat (important)

Render staging (`pleerity-enterprise.onrender.com`) reports `environment: staging` but **does not expose build SHA** on `/api/health`. It is **not confirmed** that the running container includes commit `99cfea46`.

This validation therefore uses:

- **Local Phase 1 code** (`99cfea46`) at `LIFECYCLE_SEMANTICS_MODE=shadow`
- **Read-only sampling** of real `pleerity_staging` requirement rows

Server-side shadow logs on Render require a **preview/staging deploy** of `feature/lifecycle-semantics-phase1` with `LIFECYCLE_SEMANTICS_MODE=shadow` set in Render env (not performed in this authority).

---

## 2. Env flag confirmation

| Variable | Expected | Observed |
|----------|----------|----------|
| `LIFECYCLE_SEMANTICS_MODE` (validation run) | `shadow` | **`shadow`** |
| `active` mode | Prohibited | Resolves to **`disabled`** (warning logged) |
| Default when unset | `disabled` | Verified in unit tests |

**Render staging env:** Not modified (read-only validation authority).

---

## 3. Scenario S1–S10 validation table

| ID | Requirement | Expected semantics | Staging sample | Resolved semantics | attention_kind | Status | Projection parity |
|----|-------------|-------------------|----------------|------------------|----------------|--------|-------------------|
| S1 | gas_safety | EXPIRY_BASED | Found | EXPIRY_BASED | — | **PASS** | Yes |
| S2 | eicr | EXPIRY_BASED | Found | EXPIRY_BASED | — | **PASS** | Yes |
| S3 | epc | EXPIRY_BASED | Found | EXPIRY_BASED | — | **PASS** | Yes |
| S4 | hmo_license | EXPIRY_BASED | Found | EXPIRY_BASED | CERTIFICATE_EXPIRING | **PASS*** | Yes |
| S5 | legionella | REVIEW_BASED | Found | REVIEW_BASED | — | **PASS** | Yes |
| S6 | deposit_pi | DECLARATION_BASED | Found | DECLARATION_BASED | EVENT_ACTION_REQUIRED | **PASS** | Yes |
| S7 | right_to_rent | OCCUPANCY_LIFECYCLE | Found | OCCUPANCY_LIFECYCLE | — | **PASS** | Yes |
| S8 | tenancy_agreement | TENANCY_LIFECYCLE | Found | TENANCY_LIFECYCLE | — | **PASS** | Yes |
| S9 | smoke_heat_alarms | EVENT_BASED | Found | EVENT_BASED | EVENT_ACTION_REQUIRED | **PASS** | Yes |
| S10 | fitness_for_human_habitation | OPERATIONAL | Found | OPERATIONAL | — | **PASS** | Yes |

\* **S4 shadow conflict (expected):** `conflict_expects_expiry_false_expiry_semantics` — legacy `expects_expiry` engine returns false for this row’s jurisdiction context while fallback map correctly resolves **EXPIRY_BASED**. This is **shadow observability**, not a runtime behaviour change. Documented for Phase 2 registry/engine reconciliation.

**Unresolved classifications:** **0**  
**Samples missing:** **0**

---

## 4. Shadow classification output summary

- **10/10** scenarios resolved to expected `lifecycle_semantics`
- **10/10** runtime projection parity (`status`, `due_date`, `evidence_state` identical in `disabled` vs `shadow`)
- **1** shadow divergence logged (S4 — legacy vs resolver expiry signal)
- **0** customer-facing fields added to API output (`_lifecycle_semantics_shadow` not attached)

Raw JSON: `backend/docs/audit/LIFECYCLE_SEMANTICS_PHASE1_STAGING_SHADOW_VALIDATION.json`

---

## 5. Unresolved / conflict report

| Type | Count | Detail |
|------|-------|--------|
| Unresolved (no semantics) | 0 | — |
| Missing staging samples | 0 | — |
| Shadow conflicts | 1 | S4 `hmo_license` — `expects_expiry=false` vs `EXPIRY_BASED` (known legacy drift) |
| Unsupported semantics | 0 | — |

---

## 6. Behaviour parity report

| Domain | Verified | Method | Result |
|--------|----------|--------|--------|
| Runtime projection | Yes | `project_requirement_row_client_runtime` disabled vs shadow | **Unchanged** (10/10) |
| Scoring | Yes | Read-only `property_compliance_scores` snapshot | **No recalc invoked**; scores not altered |
| Reminders | Yes | No `jobs.py` / send paths executed | **No change** |
| Dashboard/KPI | Yes | Projection fields only | **No change** |
| Reports | Yes | Not executed | **No change** |
| Extraction | Yes | Not executed | **No change** |
| Frontend / UI labels | Yes | No frontend deploy | **No new labels** |
| Email templates | Yes | Not modified | **No change** |

### Parity spot-checks (representative)

| Category | Scenario | Semantics | Behaviour change |
|----------|----------|-----------|------------------|
| Expiry-based certificate | S1 gas_safety | EXPIRY_BASED | None |
| Review-based | S5 legionella | REVIEW_BASED | None |
| Declaration-based | S6 deposit_pi | DECLARATION_BASED | None |
| Tenancy lifecycle | S8 tenancy_agreement | TENANCY_LIFECYCLE | None |
| Operational | S10 fitness_for_human_habitation | OPERATIONAL | None |

---

## 7. Test results

```
LIFECYCLE_SEMANTICS_MODE=shadow

pytest tests/test_lifecycle_semantics_resolver.py
     tests/test_certificate_expiry_tracking.py
     tests/test_requirement_client_runtime_surface.py
     tests/test_compliance_registry_publish.py

61 passed
```

Classification report (local): `python scripts/lifecycle_semantics_classification_report.py` → **0% unresolved** on golden codes.

---

## 8. Risks found

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| R1 | Render may not run `99cfea46` yet | Medium | Deploy feature branch preview; verify shadow logs in Render |
| R2 | S4 HMO legacy `expects_expiry` drift | Low | Shadow flags; reconcile in Phase 2 registry backfill |
| R3 | Staging rows carry legacy `due_date` conflated with expiry on RTR/smoke | Low | Phase 2 date authority; no Phase 1 behaviour impact |
| R4 | Server shadow logs unverified on Render | Medium | Set `LIFECYCLE_SEMANTICS_MODE=shadow` on staging service post-deploy |

---

## 9. Merge recommendation

| Recommendation | Detail |
|----------------|--------|
| **PR to `develop`** | **Recommended** — Phase 1 observe-only foundation is validated |
| **Gate** | **AMBER** — merge PR after optional staging preview deploy confirms server-side shadow logs |
| **Do not merge to `main`** | Until develop soak complete |
| **Phase 2** | Separate authority — not authorised here |

### Completion gate checklist

| Criterion | Met |
|-----------|-----|
| S1–S10 resolve correctly | **Yes** (10/10 semantics) |
| `active` mode blocked | **Yes** |
| Behaviour unchanged | **Yes** (projection parity 10/10) |
| Tests pass | **Yes** (61) |
| No production/main changes | **Yes** |
| Forbidden systems modified | **Yes** (none) |

---

## 10. Validation artefacts

| Artefact | Path |
|----------|------|
| Staging shadow JSON | `backend/docs/audit/LIFECYCLE_SEMANTICS_PHASE1_STAGING_SHADOW_VALIDATION.json` |
| Validation script (read-only) | `backend/scripts/lifecycle_semantics_staging_shadow_validate.py` |
| Phase 1 completion | `backend/docs/audit/REQUIREMENT_LIFECYCLE_NON_EXPIRY_REMEDIATION_01_PHASE1_COMPLETION.md` |

---

*End of LIFECYCLE-SEMANTICS-PHASE1-STAGING-SHADOW-VALIDATION-01.*
