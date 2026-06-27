# Incident Lifecycle Improvements

**Programme:** OPERATIONAL-RELIABILITY-OBSERVABILITY-INTEGRITY-AUDIT-01

---

## Existing lifecycle (validated in code review)

| Stage | Implementation |
|---|---|
| Detection | `record_operational_detection` with SHA-256 fingerprint |
| Dedupe | Same fingerprint → update existing OPEN incident, not create duplicate |
| Suppression | Severity-based windows (P0 15m, P1 30m, P2 60m, P3 2h) |
| Flap protection | Transition threshold in 30 min window |
| Deploy suppression | `PLATFORM_DEPLOY_SUPPRESSION_UNTIL` env |
| Recovery | `incident_recovery.resolve_recovered_incidents_for_job` on success |
| Auto-resolve | Configurable delay after RECOVERED lifecycle state |
| Email | `INTERNAL_ALERT` via notification orchestrator — linked to incident, not standalone flood |

---

## Staging runtime observations

| Observation | Assessment |
|---|---|
| 4 open P2 incidents | Genuine — SLA watchdog active |
| `activation_reminder_processing` repeating detections | Same incident updated (`updated_at` refreshed) — dedupe working |
| Health summary `open_incidents_count=4` matches API | Consistent (when API parsed as `{items}`) |

---

## Alert vs incident separation

| Channel | When used |
|---|---|
| `incidents` collection | Persistent operational faults requiring ack/resolve |
| OPS email | Notify on new/worsened incident; suppressed by fingerprint window |
| Notification spike monitor | Email-only (no incident row) — appropriate for transient spikes |

**Preferred lifecycle confirmed:** detect → open incident → update → recover → resolve → recovery notification (via incident lifecycle, not repeated cold emails).

---

## Improvements from this audit

| Change | Effect |
|---|---|
| Registry completeness | Missed SLA now detectable for 3 previously invisible jobs |
| No alert suppression added | Governance preserved |

---

## Recommended follow-ups

1. Verify auto-resolve fires when `activation_reminder_processing` succeeds post-recovery
2. Document incidents API `{items}` response for integrators
3. Add incident count to Platform Status snapshot error responses when partial failure occurs
