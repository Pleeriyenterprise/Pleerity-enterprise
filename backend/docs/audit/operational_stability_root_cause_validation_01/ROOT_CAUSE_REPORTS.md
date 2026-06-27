# Root Cause Reports — Remaining Alerts

**Programme:** OPERATIONAL-STABILITY-ROOT-CAUSE-VALIDATION-01  
**Evidence:** `INCIDENT_RECONSTRUCTION.json`, MongoDB `job_runs` / `incidents`

---

## 1. Scheduler heartbeat stale (P1) — Incident `6a3feb07…`

| Field | Detail |
|---|---|
| **Why it fired** | `last_heartbeat_at` aged beyond `HEARTBEAT_STALE_SECONDS` (300s) |
| **Runtime condition** | Deploy restart ~15:20 UTC; heartbeat gap **435.6s** (15:37→15:44) |
| **Alert correct?** | **Yes** — scheduler was genuinely unavailable |
| **Platform behaved correctly?** | **Yes** — incident created, single email (15:43), auto-resolved 16:10 |
| **Scheduler stopped?** | Process down during container recycle, not logic bug |
| **Jobs stopped?** | Yes during gap; resumed after boot |
| **Remediation** | None required — use `PLATFORM_DEPLOY_SUPPRESSION_UNTIL` during planned deploys if ops wants fewer deploy emails |
| **Classification** | **Expected deployment behaviour** |

**Timeline:** 15:23:51 incident → 15:43 email → 15:50 recovered → 16:10 resolved

---

## 2. Scheduler heartbeat stale (P1) — Incident `6a404678…`

| Field | Detail |
|---|---|
| **Why it fired** | Same as #1 during `f2c10442` deploy |
| **Runtime condition** | Heartbeat gap **414.0s** (21:48→21:55) |
| **Alert correct?** | **Yes** |
| **Recovery** | Auto-resolved 22:30; heartbeat fresh at 22:29 |
| **Classification** | **Expected deployment behaviour** |

---

## 3. Compliance risk updates delayed (P0) — risk_signal_regen_worker `6a3feb19…`

| Field | Detail |
|---|---|
| **Presentation title** | "Compliance risk updates are delayed" (`operational_alert_presentation.py`) |
| **Stored title** | Job risk_signal_regen_worker missed SLA |
| **Why it fired** | Last success 15:19; at 15:24 watchdog measured **4 min delay** > **3 min** max (`max_delay_minutes` for 30s-interval job) |
| **Runtime condition** | Deploy gap **268.8s** in job_runs |
| **Alert correct?** | **Yes** — job did not complete within SLA during restart |
| **Customer impact** | **Delay only** — risk regen resumed; queue depth 0; no incorrect risk scores observed |
| **Recovery** | Success run 15:29; incident resolved 15:44 |
| **Classification** | **Expected deployment behaviour** (downstream of Cluster A) |

---

## 4. Compliance risk updates delayed (P0) — `6a40468a…` (second deploy)

Same as #3 during `f2c10442` deploy (gap 283.9s, created 21:54, resolved 22:15).

**Classification:** **Expected deployment behaviour**

---

## 5. Scheduled admin communications missed window (P0) — `6a3feb25…`

| Field | Detail |
|---|---|
| **Why it fired** | Last success 15:18; delay **6 min** > **5 min** SLA at 15:24 |
| **Runtime condition** | Deploy Cluster A; cron `*/2` job could not fire during process down |
| **Alert correct?** | **Yes** |
| **Recovery** | Success 15:30; resolved 15:46 |
| **Customer impact** | Admin comms delayed ~6 min; no data corruption |
| **Classification** | **Expected deployment behaviour** |

---

## 6. Work order schedule reminders missed SLA (P2) — `6a3ff3a1…`

| Field | Detail |
|---|---|
| **Why it fired** | Hourly :20 job; last success 14:20; at 16:00 delay **110 min** > 90 min SLA |
| **Runtime condition** | 15:20 deploy missed 15:20 slot; subsequent slots delayed until scheduler stable |
| **Recovery** | 17:20 success; resolved 18:20 |
| **Classification** | **Expected deployment behaviour** |

---

## 7. Evening compliance check delayed (P2, OPEN) — `6a402e21…`

| Field | Detail |
|---|---|
| **Presentation** | "Evening compliance status check is delayed" |
| **Why it fired** | SLA watchdog uses last **success/degraded** only; last success 2026-06-26T18:01 |
| **Critical runtime fact** | Job **did run** 2026-06-27T18:00:22 — status **failed** |
| **Failure error** | `'NoneType' object has no attribute 'upper'` (compliance timeline canonical code bug) |
| **Alert correct?** | **Yes** — no successful evening check since prior day |
| **Application defect?** | **Yes** — same bug fixed in `f2c10442` (deployed 21:45, after this run) |
| **Customer impact** | Evening compliance **check did not complete** that day; scores not refreshed by this batch — **stale, not incorrect** |
| **Remediation** | **Done** (`f2c10442`); await 2026-06-28T18:00 run or manual incident resolve |
| **Classification** | **Application defect (remediated)** |

---

## 8. Notification retry worker delayed — NOT OBSERVED

503 successful runs in validation window. No incident. **No root cause investigation required** — alert type listed in presentation map only.

---

## Summary table

| Alert | Classification | Remediation |
|---|---|---|
| Heartbeat stale (×2) | Expected deployment | Optional deploy suppression env |
| Risk regen delayed (×2) | Expected deployment | None |
| Admin comms missed (×1) | Expected deployment | None |
| Work order reminders (×1) | Expected deployment | None |
| Evening compliance (×1 open) | Application defect (fixed) | Verify next 18:00 run |
| Notification retry | N/A — no alert in window | None |
