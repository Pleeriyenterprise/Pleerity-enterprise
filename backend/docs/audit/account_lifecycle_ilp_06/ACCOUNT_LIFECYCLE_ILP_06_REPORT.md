# ILP-6 — Background Processing Runtime Authority Report

**Programme:** ILP-6-BACKGROUND-PROCESSING-RUNTIME-AUTHORITY-01  
**Branch:** `develop`  
**Executed:** 2026-07-06 UTC  

## Verdict

**`ILP_06_IMPLEMENTED_TARGETED_VALIDATION_PASS_REGRESSION_DEFERRED`**

Implementation is complete for customer-facing background domains. Targeted validation passed. Full backend/frontend regression is **deferred** under the approved testing policy until the final production-critical ILP gate (all production-critical ILPs implemented).

**Production ready:** No — full regression remains a programme closeout gate, not an ILP-6 blocker.

---

## Reason

Full regression is deferred under the approved testing policy: use targeted tests during ILP implementation; reserve full regression for the final production-critical ILP gate or platform-wide release readiness.

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
| Targeted tests | ✓ 18 passed (see below) |
| Documentation | ✓ `ACCOUNT_BACKGROUND_RUNTIME_AUTHORITY.md`, `ACCOUNT_BACKGROUND_PROCESSING_POLICY.md` |
| Evidence | ✓ `ACCOUNT_LIFECYCLE_ILP_06_EVIDENCE.json` |

---

## Domains migrated

1. **Reminder & notification scheduling** — `jobs.py`, `notification_orchestrator.py`
2. **Email/SMS dispatch guards** — `notification_orchestrator.py` (runtime + capability)
3. **Scheduled reports & monthly digests** — `jobs.py`
4. **Compliance monitoring** — `jobs.py` compliance status check
5. **Score/risk queue processing** — `job_runner.py`, `risk_signal_regen_queue.py`, `risk_signals_job`

---

## Deferred (non-customer schedulers)

Platform/admin-only jobs inventoried but **not** migrated in ILP-6 (no customer lifecycle gate required):

- SLA monitors (`compliance_recalc_sla_monitor`, `sla_watchdog`, `sla_monitoring`)
- Lead pipeline (`lead_followup_processing`, `lead_compliance_gap_detection`, etc.)
- Order/delivery pipeline (`order_delivery_processing`, `queued_order_processing`, etc.)
- Scheduler heartbeat, delivery reconciliation, admin digests
- Stripe/billing fact-source jobs (unchanged by design)

---

## Targeted tests (passed)

```
pytest tests/test_account_background_runtime_authority.py -q          → 16 passed
pytest tests/test_notification_orchestrator.py::test_professional_sms_allowed \
       tests/test_notification_orchestrator.py::test_solo_sms_returns_403_plan_gate_denied -q → 2 passed
```

**Total:** 18 passed, 0 failed.

---

## Remaining closeout gate

| Gate | Status |
|------|--------|
| Full backend regression | **Deferred** — final programme validation |
| Full frontend regression | **Deferred** — no ILP-6 frontend changes |
| Production-ready verdict | **Pending** closeout gate |

---

## Key changes

### Central guard

`BackgroundRuntimeAuthority.evaluate()` loads the runtime contract, evaluates `background_policy`, optional `communication_policy`, and plan-gated capabilities.

### Blocker fix

`CAP_NOTIF_SMS` plan feature mapping corrected to `sms_reminders` (governance-aligned plan key).

---

## ILP-7 readiness

**Ready to begin ILP-7** (next programme in the implementation sequence). ILP-6 targeted validation complete; full regression not required to start ILP-7.

Recommended next: **API Lifecycle Responses** (governance ILP-6 scope) — normalized capability-denial payloads, `lifecycle_redirect`, and recovery-tier read APIs consuming runtime contract.
