# RENT-OPS-OPERATIONAL-VERIFY-01 Report
- **When:** 2026-05-23T02:47:42.385911+00:00
- **Client:** `rent_ops_verify_01_7bbe8f8b`
- **Plan:** `PLAN_2_PORTFOLIO`

## Area results

| Area | Result | Notes |
|------|--------|-------|
| 10_reports | PASS | reports use same summary source |
| 11_mobile | SKIP | browser skipped |
| 12_stress_scale | PASS | ledgers=55 attention_query_ms=142 |
| 13_timeline_coherence | SKIP | browser skipped |
| 1_first_screen_clarity | SKIP | browser skipped: frontend unreachable: [WinError 10061] No connection could be m |
| 2_rent_setup | FAIL | schedules=5 ledgers=55 |
| 3_payment_flows | PASS | payment_date aggregation coherence |
| 4_overdue_attention | PASS | attention=24 overdue_only=24 |
| 5_reminder_workflow | PASS | idempotent reminders |
| 6_daily_worker | FAIL | global job outcome |
| 7_rbac | PASS | 404 on foreign resources |
| 8_compliance_isolation | PASS | score unchanged after rent mutations |
| 9_property_snapshot | PASS | snapshot fields present |
| env_flags | PASS | RENT_OPERATIONS=True |

## Defects

### [HIGH] Insufficient seeded schedules
- **Area:** 2_rent_setup
- **Expected:** >=8 active schedules
- **Actual:** 5
- **Reproduction:**
  1. Run seed on staging client
  1. Count rent_schedules

