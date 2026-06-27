# Notification Lifecycle — Runtime Validation

**Programme:** OPERATIONAL-PRODUCTION-ACCEPTANCE-VALIDATION-01  
**Code deployed:** `12ea3502` (incident lifecycle fix)  
**Baseline recorded:** 2026-06-27T21:56Z — `SOAK_MONITOR.json`

---

## Code behaviour (Audit 01/02 fix)

`_record_repeat` no longer re-sends email when suppression window expires for unchanged DEGRADED conditions. Email sends only on:

- Severity escalation
- OPEN → DEGRADED transition
- Missing initial alert (retry path)

---

## Runtime observations (staging)

| Incident | repeat_count | lifecycle | last_alert_email_at | Re-email since fix? |
|---|---|---|---|---|
| activation_reminder_processing P2 | 29 | DEGRADED | 2026-06-27T15:00:32Z | **No** (≥6h unchanged at validation) |
| daily_reminders degraded P2 | 76 | DEGRADED | 2026-06-27T15:00:10Z | **No** |
| subscription_ops_digest P2 | 133 | RECOVERED | 2026-06-26T09:30:11Z | **No** |
| compliance_check_evening P2 | 10 | DEGRADED | 2026-06-27T20:20:09Z | Single alert (likely degraded transition post-deploy) |

**Duplicate fingerprint rows:** 0 (dedupe intact)

---

## 24-hour soak status

| Requirement | Status |
|---|---|
| Baseline snapshot recorded | **Done** — sample 1 in `SOAK_MONITOR.json` |
| Elapsed ≥24h with zero new emails on unchanged P2 | **Pending** — requires re-run of `tmp_incident_soak_monitor.py` after 2026-06-28T21:56Z |
| Automated monitor script | `tmp_incident_soak_monitor.py` |

**Interim verdict:** No evidence of hourly re-email regression since lifecycle fix deploy. Full 24h soak **not yet complete** — condition for unconditional GO.

---

## How to close soak

```bash
cd backend
python tmp_incident_soak_monitor.py   # repeat after 24h
```

Compare `last_alert_email_at` across samples for incidents with unchanged `lifecycle_state=DEGRADED` and stable `repeat_count` growth without new email timestamps.
