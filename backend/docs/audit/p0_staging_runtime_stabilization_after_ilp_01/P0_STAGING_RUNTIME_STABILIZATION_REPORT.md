# P0 — Staging Runtime Stabilization Report

**Programme:** P0-STAGING-RUNTIME-STABILIZATION-AFTER-ILP-01  
**Branch:** `develop`  
**Executed:** 2026-07-06 UTC  

## Verdict

**`STAGING_RUNTIME_STABILIZED_WITH_CONDITIONS`**

Root causes identified and remediated in code. Targeted tests pass. **Staging browser smoke pending post-deploy** to Render + Vercel preview.

---

## Root cause analysis

### 1. React Minified Error #31 (P0)

**Cause:** ILP-7 structured HTTP `detail` objects (lifecycle/capability denials) were passed directly into React state and rendered by `ErrorBanner` (`{message}`). React cannot render plain objects as children.

**Fix:** `formatApiErrorDetail()` utility; `ErrorBanner` coerces to string; `ClientTasksPage` uses `formatApiErrorMessage()`.

### 2. 429 retry storm (P0)

**Cause:** `ClientPortalLayout` retried `portal-context` up to 4 times per load, on a 180s interval, while every page simultaneously fetched dashboard/requirements/notifications. Failed 403/429 responses triggered more retries → rate limiting → apparent CORS failures.

**Fix:** Portal-trust circuit breaker (max 2 attempts, 5-minute open circuit); `apiRequestCircuit.js` pauses repeated calls to the same path after 4 failures.

### 3. Guard + event emission overhead (P1)

**Cause:** ILP-10 `_client_context_guard` called `resolve_runtime_contract_for_client()` on every `/api/client/*` request with lifecycle event publication enabled.

**Fix:** Guard uses `emit_events=False`; restored billing-row early return for clients without billing records.

### 4. CORS appearance on blocked requests (P1)

**Cause:** Security monitoring 429 responses could surface in the browser without `Access-Control-Allow-Origin`, masquerading as CORS errors.

**Fix:** `_cors_headers_for_origin()` applied to security-block 429 responses.

### 5. Governed lifecycle UI not shown (P1)

**Cause:** `LifecycleRuntimeContext` treated all lifecycle-runtime 403s as generic "unavailable" instead of parsing denial payload `customer_experience`.

**Fix:** On structured 403, apply denial payload to runtime fallback state.

---

## Affected surfaces

| Page | Symptom |
|------|---------|
| Today | Error #31 crash |
| Dashboard | Network error / empty widgets |
| Command Centre | Network error banner |
| Properties / Requirements / Documents | Failed to load + retry |
| Billing | Failed to load plan information |
| All | portal-context / entitlements 403 loops |

---

## Fixes summary

| Area | Change |
|------|--------|
| Frontend errors | `formatApiErrorDetail`, `ErrorBanner`, `ClientTasksPage` |
| Frontend retries | `apiRequestCircuit.js`, `ClientPortalLayout` circuit |
| Frontend lifecycle | `LifecycleRuntimeContext` denial payload handling |
| Backend guard | billing early return, `emit_events=False` |
| Backend CORS | 429 security block headers |
| Backend contract | `emit_events` parameter on resolve |

---

## Targeted tests

```
pytest tests/test_p0_staging_runtime_stabilization.py tests/test_platform_convergence.py tests/test_cors_origins.py -q  → 26 passed
npm test -- --testPathPattern=p0StagingRuntimeStabilization --watchAll=false  → 4 passed
```

---

## Post-deploy staging smoke checklist

After Render (API) and Vercel (frontend) redeploy from `develop`:

- [ ] Login as staging test client
- [ ] No CORS errors in console on `/today`
- [ ] No React Error #31
- [ ] Dashboard loads data or governed empty state
- [ ] Today, Properties, Requirements, Documents load or show governed denial
- [ ] Billing loads plan or recovery CTA
- [ ] No 429 storm within 60s of page load

---

## Remaining conditions

- `BillingPage` still calls `/client/entitlements` (deprecated but functional when guard passes)
- Legitimate cancelled/suspended accounts see recovery UI, not full portal — by design
- Full platform regression remains deferred

---

## Release readiness

**Do not proceed** to Platform Release Readiness audit until staging smoke checklist passes.

**Outcome:** `STAGING_RUNTIME_STABILIZED_WITH_CONDITIONS`
