# Watchlist — PRELAUNCH-OPERATIONAL-TRUST-GUARDRAILS-01

- **Classification:** PARTIAL
- **Secondary risks:** COGNITION_FRAGMENTATION_RISK, AUTHORITY_DRIFT_RISK

## Non-negotiable invariants

- Never use `projection=list` on surfaces rendering authority CTAs or cognition chips (Today/Requirements compliant; CC/Dashboard **gap**).
- Frontend formats authority; must not invent primary actions when server envelope is present.
- False calm forbidden — operational debt must be disclosed or visible.
- Duplicate workflow mint forbidden — idempotent replay required.

## P0 watch (trust-breaking)

1. Command Centre + Dashboard → `requirementsOperational` migration (RM-P0-001)
2. CC all-clear under `pressure_degraded` (RM-P0-002)
3. Today silent requirements `.catch` (RM-P0-003)
4. `primaryActionResolver` dangerous fallbacks (RM-P0-004)
5. Risk-signal WO HTTP idempotency test (RM-P0-005)

## CI additions (this programme)

- `frontend/src/utils/operationalCognition.test.js`
- `frontend/src/utils/operationalProjectionGuard.test.js`
- `backend/tmp_prelaunch_operational_trust_guardrails_01.py`

## Pre-release staging bundle

```bash
python backend/tmp_prelaunch_operational_trust_guardrails_01.py
python backend/tmp_prelaunch_today_execution_workspace_01.py
python backend/tmp_prelaunch_operations_outcome_coherence_01.py
```

## Extends

- AUTHORITY-INVARIANTS-BASELINE-01
- PRELAUNCH-AUTHORITY-HARDENING-PLAN-01
- operational_cognition_v1 envelope programme
