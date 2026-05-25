# PRELAUNCH-ADMIN-RUNTIME-VERIFY-01

**Run:** `20260525T141144Z`  
**Classification:** `VERIFIED_OPERATIONALLY`  
**Pilot:** Wales HMO `6fd5ac4c_d35a58ae`

| Family | Pass |
|--------|------|
| A1 | True |
| A2 | True |
| A3 | True |
| A4 | True |
| A5 | True |
| G9 | True |
| G10 | True |
| Convergence | True |

Proof: real admin session, API + browser, staging `https://pleerity-enterprise.onrender.com/api`.

**A1:** Client issue → work order → admin assign/close → impersonated resolve; client `/operations/issues/{id}` shows terminal state.

**A2:** Wales client is ACTIVE subscriber but not a pilot-lifecycle account (404 on `/accounts/{id}`). Waiver granted via `POST .../eligibility-overrides` (`recover_onboarding`, 30d expiry) plus reference `onboarding-fee-policy` on active pilot `1e15cd2f-...`. Client blocked (403); plan unchanged (`PLAN_3_PRO`).

**A3/A4:** Dashboard stats match API; analytics v2 summary reachable in browser.

**A5:** Admin routes reject unauthenticated, client, tenant, contractor tokens.

Harness: `backend/tmp_admin_runtime_verify_01_execute.py`.
