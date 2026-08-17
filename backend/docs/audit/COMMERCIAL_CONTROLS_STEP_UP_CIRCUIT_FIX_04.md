# Commercial Controls — STEP_UP_REQUIRED circuit-breaker fix 04

**Programme:** `COMMERCIAL-CONTROLS-RUNTIME-CERTIFICATION-CLOSURE-04`  
**Defect (03):** HTTP 403 `STEP_UP_REQUIRED` incremented the frontend API circuit-breaker (`CIRCUIT_FAILURE_THRESHOLD=2`, 90s cooldown). Cancel then retry opened the circuit.  
**Fix commit:** `f88ce26d6711e881fc20cdae148ac8bff4b2f9cb` on local `develop`  
**Fingerprint:** `cc-step-up-circuit-fix-04` (`window.__CC_STEP_UP_CIRCUIT_FIX__`)  
**Backend SHA:** unchanged `7c77391a5ee65f0a85372d9c462448c270b6b066`  
**Production frontend:** unchanged `main.eac95fab.js` (no fingerprint)

Preserves 03 UI evidence: `COMMERCIAL_CONTROLS_STEP_UP_RUNTIME_03.md`.

## Rule implemented

```text
if HTTP 403
and machine-readable error code == STEP_UP_REQUIRED
then
    do not increment circuit failure count
    do not open circuit
    invoke step-up flow normally
```

Not every 403 is excluded. Ordinary authorization 403s still count. `STEP_UP_INVALID` is not in the exclusion set.

Files:

- `frontend/src/utils/apiRequestCircuit.js` — `EXPECTED_AUTH_CHALLENGE_CODES`, early return in `recordApiCircuitFailure`
- `frontend/src/api/client.js` — interceptor passes `detail.error_code` as the fourth argument
- `frontend/src/utils/p0StagingRuntimeStabilization.test.js` — three new cases

## Unit tests

`p0StagingRuntimeStabilization.test.js`: STEP_UP_REQUIRED ×2 leaves circuit closed; cancel+retry leaves circuit closed; genuine 403 ×2 still opens. Suite 10/10.

## Staging frontend deploy (frontend only)

| Item | Value |
| --- | --- |
| Alias | `https://pleerity-enterprise-9jjg.vercel.app` |
| Bundle | `main.7fd31560.js` |
| Fingerprint | present |
| `commercial-step-up-modal-host` | present |
| Staging API host | `pleerity-enterprise.onrender.com` |
| Production API host in bundle | absent |
| Production site | `https://pleerityenterprise.co.uk` still `main.eac95fab.js` |
| `main` | not merged |
| Render staging backend | not redeployed (`f88ce26d` not pushed; auto-deploy would restart backend) |

Mongo soak was **not** interrupted by this frontend-only alias deploy.

## Runtime proof (Playwright MCP, staging alias)

Operator: prosper@yopmail.com. Client: lere `ce8d3b56-…`. Commercial Controls expander open. Fingerprint `cc-step-up-circuit-fix-04`.

| Step | Result |
| --- | --- |
| Submit Suspend billing (reason ≥10, confirm, email unchecked) | POST execute **403** |
| Step-up modal | **Confirm your password** visible; `data-testid=commercial-step-up-modal-host` |
| Circuit | no 90s pause copy; last API error 403 “Confirm your password to continue.” |
| Cancel | modal dismissed; execute dialog remained; Apply enabled; spinner not stuck |
| Immediate retry Apply | second POST execute **403** within seconds (network requests 76 and 90) |
| Modal again | Confirm your password; no circuit language |
| Cancel again | no persist; governance remained ACTIVE; no second Stripe pause |

Successful execute after step-up (spinner end, Stripe pause, refresh) is proven on the **same fixture** via the governed API harness at 20:43Z (`COMMERCIAL_CONTROLS_ACTIVE_SUSPEND_RUNTIME_04.md`). UI Continue was not completed after the circuit proof so the recovered fixture was not paused a second time.

## Verdict for this defect

```text
PASS
```
