# Staging Validation — Phase 2

**Programme:** ADMIN-CUSTOMER-OPERATIONS-CENTRE-PHASE-2-01  

## Local validation (executed)

| Suite | Result |
|-------|--------|
| `test_admin_lifecycle_operations_centre_01.py` | 4/4 PASS |
| `test_admin_customer_operations_centre_phase2_01.py` | 4/4 PASS |
| `AdminLifecycleOperationsPanel.test.js` | 4/4 PASS |

## Staging checklist (post-deploy)

Harness: `python tmp_admin_customer_operations_centre_phase2_01.py`

| Check | Method |
|-------|--------|
| Backend on latest develop | `GET /api/version` |
| Customer health summary | snapshot `customer_health.overall` |
| Authority chain | `authority_chain.length > 0` |
| Operational timeline | `operational_timeline` array |
| Runtime diagnostics | `runtime_diagnostics.runtime_version` |
| Background processing | `background_processing.sampled_job_groups` |
| Communications | `communications.communication_policy` |
| Webhook diagnostics | `webhook_diagnostics.replay_policy` |
| Support bundle | POST export-support-bundle → ZIP |
| Governed actions | refresh/reconcile still 200 with governance |
| No duplicate pages | single Customer ops tab |
| Tab label | "Customer ops" |

## Browser validation

1. Admin login → Client Control Panel → **Customer ops** tab  
2. Verify health banner, authority chain, timeline render  
3. Export support bundle downloads ZIP  
4. Run refresh runtime — success + audit  
5. Billing Centre link works  

## Verdict

Updated in `ADMIN_CUSTOMER_OPERATIONS_PHASE2_EVIDENCE.json` after harness run.
