# PRELAUNCH-OPS-RUNTIME-VERIFY-01 — Family 1 Issues (`ops_runtime_01_issues`)

**Run:** `20260523T104439Z`  
**Classification:** `FAIL_SYSTEM` (+ `TRUST_RISK_PRESENT`)  
**Authoritative owner:** `ops_runtime_01_issues`  
**Proof mode:** `operational_browser`  

## Pilot
- client_id: `6fd5ac4c-3fd4-4112-ade7-156977deb49f`
- property_id: `d35a58ae-3c81-491c-9694-1d021dd3b8ad`
- jurisdiction: Wales

## Summary
- Preflight: PASS
- API/browser lifecycle (create, view, edit, transition, close, refresh, cross-surface): PASS in same run
- **G9 idempotency: FAIL** — rapid duplicate POST created two distinct issues with identical description visible in queue (no dedupe).
- G10 authority: PASS (unauthenticated/forbidden; closed state monotonic)
- Convergence: PASS (closed state stable after 35s)
- Direct DB audit: not available on harness host (`MONGO_URL` absent); system outcome verified via production API reads.

## Remediation before upgrade
- Add idempotent create protection (client disable + server dedupe key) for maintenance issues.

## F2 proceed
**NO** — F2 requires `VERIFIED_OPERATIONALLY` or signed WATCHLIST with explicit issue-lifecycle waiver. Remediate G9 first, then rerun F1 browser bundle.
