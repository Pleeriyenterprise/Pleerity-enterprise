# ILP-6 — Background Processing Runtime Authority Report

**Programme:** ILP-6-BACKGROUND-PROCESSING-RUNTIME-AUTHORITY-01  
**Branch:** `develop`  
**Status:** Implementation complete — **closeout regression pending**  
**Production ready:** No (awaiting ILP-6 closeout gate)

---

## Summary

ILP-6 introduces a central **Background Runtime Authority** and migrates customer-facing background domains to consume the Account Lifecycle Runtime Contract instead of legacy subscription, entitlement, or plan-registry checks.

---

## Deliverables

| Item | Status |
|------|--------|
| Background processor inventory | ✓ (52 APScheduler jobs + 2 queue workers catalogued) |
| `account_background_runtime_authority.py` | ✓ |
| Decision model (CONTINUE/PAUSE/SKIP/TERMINATE/RETENTION_ONLY) | ✓ |
| Reminder/notification gating | ✓ |
| Digest & scheduled report gating | ✓ |
| Compliance monitoring gating | ✓ |
| Queue runtime suppression (recalc + risk regen) | ✓ |
| Auditable suppressed-job logging | ✓ |
| Targeted tests | ✓ 16 authority + 2 notification SMS tests |
| Documentation | ✓ `ACCOUNT_BACKGROUND_RUNTIME_AUTHORITY.md`, `ACCOUNT_BACKGROUND_PROCESSING_POLICY.md` |
| Evidence | ✓ `ACCOUNT_LIFECYCLE_ILP_06_EVIDENCE.json` |

---

## Key changes

### Central guard

`BackgroundRuntimeAuthority.evaluate()` loads the runtime contract, evaluates `background_policy`, optional `communication_policy`, and plan-gated capabilities (`CAP_NOTIF_EMAIL`, `CAP_REPORT_SCHEDULE`, etc.).

### Domain migrations

- **`jobs.py`** — daily reminders, monthly digests, compliance status checks, scheduled reports no longer filter on `subscription_status` / `entitlement_status`; per-client runtime gate applied.
- **`notification_orchestrator.py`** — `_apply_gating` uses runtime authority + capability compatibility instead of `requires_active_subscription`, `requires_entitlement_enabled`, and `plan_registry.enforce_feature`.
- **Queue workers** — `compliance_recalc_worker` and `risk_signal_regen_worker` reschedule or terminate items with auditable metadata when runtime denies processing.

### Blocker fix

`CAP_NOTIF_SMS` plan feature mapping corrected to `sms_reminders` so runtime contract plan-gated SMS resolves correctly (governance-aligned; not a schema change).

---

## Testing

Targeted run (ILP-6 policy):

```
pytest tests/test_account_background_runtime_authority.py -q   → 16 passed
pytest tests/test_notification_orchestrator.py::test_professional_sms_allowed \
       tests/test_notification_orchestrator.py::test_solo_sms_returns_403_plan_gate_denied -q → 2 passed
```

Full backend/frontend regression **deferred** to ILP-6 closeout per programme testing policy.

---

## Deferred

- Platform/admin-only schedulers (lead pipeline, order delivery, SLA platform monitors) — inventoried; not customer lifecycle gates in this sprint.
- ILP-6 closeout full regression and production-ready verdict.

---

## ILP-7 readiness

After closeout regression passes, downstream programmes may proceed. Background customer processing is now aligned with the same runtime contract authority as the portal (ILP-4/5).
