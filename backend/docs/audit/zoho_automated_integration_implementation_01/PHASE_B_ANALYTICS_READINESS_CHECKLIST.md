# Phase B — Analytics Readiness Checklist

**Programme:** ZOHO SANDBOX PILOT IMPLEMENTATION  
**Date:** 2026-07-10  
**Prerequisite:** Phase A live validation **PASS** (`PHASE_A_LIVE_VALIDATION_REPORT.md`)  
**Status:** Readiness only — **do not** enable `ZOHO_ANALYTICS_SYNC_ENABLED` until this checklist is complete and governance signs off

**Code baseline:** `build_analytics_export()` → `ZohoAnalyticsAdapter.execute("export_aggregates")`  
**API (corrected):** `POST {ZOHO_ANALYTICS_API_BASE}/restapi/v2/workspaces/{workspace_id}/views/{view_id}/data`  
with query `CONFIG={"importType":"append","fileType":"json","autoIdentify":"true"}`, multipart `DATA` = JSON array of one aggregate row, header `ZANALYTICS-ORGID`.  
See `PHASE_B_ANALYTICS_TARGET_TABLE_REVIEW.md`.

---

## 0. Gate conditions (must remain true)

| Condition | Required |
|-----------|----------|
| `ZOHO_INTEGRATION_ENABLED` | `true` (Phase A) |
| `ZOHO_ANALYTICS_SYNC_ENABLED` | **`false` until go-live** |
| All other per-integration flags | `false` |
| `ZOHO_KILL_SWITCH` | `false` |
| Production Zoho | Unchanged / inactive |
| Scheduler cron for Zoho | **Not wired** |

---

## 1. Zoho Analytics workspace creation

| Step | Action | Done |
|------|--------|------|
| 1.1 | Log in to Zoho Analytics **EU** sandbox org (same org as Phase A OAuth client) | ☐ |
| 1.2 | Create workspace named e.g. `Pleerity Staging Aggregates` | ☐ |
| 1.3 | Record **Workspace ID** → `ZOHO_ANALYTICS_WORKSPACE_ID` (staging: `272205000000016002`) | ☐ |
| 1.4 | Create table `pleerity_daily_aggregates` with columns in §2 | ☐ |
| 1.5 | Record table **View ID** → `ZOHO_ANALYTICS_VIEW_ID` | ☐ |
| 1.6 | Record Analytics **Org ID** → `ZOHO_ANALYTICS_ORG_ID` (`ZANALYTICS-ORGID`) | ☐ |
| 1.7 | Confirm workspace is **sandbox-only** — no production customer PII | ☐ |

---

## 2. Required table / schema

Create a table that accepts **one row per daily aggregate export** (append import).

**Suggested table name:** `pleerity_daily_aggregates`

| Column | Data type (Zoho Analytics) | Nullable | Notes |
|--------|----------------------------|----------|-------|
| `payload_version` | Number / Integer | No | Currently `1` |
| `period_start` | Date-Time / Plain Text | No | ISO-8601 UTC — inclusive start of last completed UTC day |
| `period_end` | Date-Time / Plain Text | No | ISO-8601 UTC — exclusive end (next UTC midnight); not export execution time |
| `leads_created_count` | Number / Integer | No | Period count |
| `leads_converted_count` | Number / Integer | No | Period count |
| `total_leads_count` | Number / Integer | No | Snapshot total |
| `conversion_rate_pct` | Number / Decimal | No | Percentage |
| `active_subscriptions_count` | Number / Integer | No | Active billing rows |
| `mrr_summary_gbp` | Number / Decimal | No | Sum of `mrr_gbp` — **no per-customer rows** |
| `support_tickets_open_count` | Number / Integer | No | Open + pending |
| `support_tickets_closed_count` | Number / Integer | No | Closed in period |
| `export_type` | Plain Text | No | Constant `aggregated_daily` |

**Registry note:** `ANALYTICS_EXPORT_METRICS` also lists `churn_count` and `new_subscriptions_count`. The **current builder does not emit these fields**. Do **not** require them for Phase B v1 unless the builder is extended in a separate change. Table may include optional empty columns for future use.

**Import mode:** Append via existing-table API (`importType: append`). First export does **not** auto-create the table — View ID is required.

---

## 3. Exact column names (source of truth)

From `services/integrations/zoho/metrics/analytics_export.py` (runtime payload):

```
payload_version
period_start
period_end
leads_created_count
leads_converted_count
total_leads_count
conversion_rate_pct
active_subscriptions_count
mrr_summary_gbp
support_tickets_open_count
support_tickets_closed_count
export_type
```

Sample: `PHASE_B_ANALYTICS_SAMPLE_PAYLOAD.json`

---

## 4. Analytics-only OAuth scope

Mint a **dedicated** refresh token for Analytics (Option B). Do **not** reuse CRM or legacy tokens.

| Item | Value |
|------|-------|
| Env var | `ZOHO_ANALYTICS_REFRESH_TOKEN` |
| Scope string (Self Client, comma-separated, no spaces) | `ZohoAnalytics.data.create` |
| Shared client | Existing Phase A `ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET` |
| Cache id | `zoho_oauth_access_token_analytics` |

Optional recommended (not required by current code): `ZohoAnalytics.workspace.READ` for workspace validation tooling.

---

## 5. Generate `ZOHO_ANALYTICS_REFRESH_TOKEN`

| Step | Action | Done |
|------|--------|------|
| 5.1 | Open [Zoho API Console (EU)](https://api-console.zoho.eu/) — same Self Client as Phase A | ☐ |
| 5.2 | Self Client → Generate Code with scope **`ZohoAnalytics.data.create` only** | ☐ |
| 5.3 | Exchange code: `POST https://accounts.zoho.eu/oauth/v2/token` with `grant_type=authorization_code`, client id/secret, code | ☐ |
| 5.4 | Store **refresh_token** as Render staging secret `ZOHO_ANALYTICS_REFRESH_TOKEN` | ☐ |
| 5.5 | Confirm `oauth_by_integration.analytics.refresh_token_source` becomes `per_integration` after redeploy | ☐ |

---

## 6. Obtain `ZOHO_ANALYTICS_WORKSPACE_ID`

| Method | How |
|--------|-----|
| UI | Analytics workspace → Settings / URL path often contains workspace id |
| API (after token) | List workspaces via Zoho Analytics API using the Analytics access token |

Store as Render staging env/secret: `ZOHO_ANALYTICS_WORKSPACE_ID=<id>`

Without workspace ID, view ID, and Analytics org ID, adapter returns `SKIPPED` / `analytics_import_target_not_configured_export_built_locally` — **not** a live pilot success.

---

## 7. Render staging variables to add (Phase B gate)

| Variable | Type | Value | When |
|----------|------|-------|------|
| `ZOHO_ANALYTICS_REFRESH_TOKEN` | Secret | Analytics-only refresh token | Before enable |
| `ZOHO_ANALYTICS_WORKSPACE_ID` | Env/Secret | e.g. `272205000000016002` | Before enable |
| `ZOHO_ANALYTICS_VIEW_ID` | Env/Secret | View ID of `pleerity_daily_aggregates` | Before enable |
| `ZOHO_ANALYTICS_ORG_ID` | Env/Secret | Analytics org ID for `ZANALYTICS-ORGID` | Before enable |
| `ZOHO_ANALYTICS_API_BASE` | Env | Optional; default `https://analyticsapi.zoho.eu` | Optional |
| `ZOHO_ANALYTICS_SYNC_ENABLED` | Env | `true` | **Only after checklist + validation plan ready** |

**Do not change:** production secrets, other integration flags, cron wiring.

**Already present from Phase A:** `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_INTEGRATION_ENABLED=true`, `ZOHO_ENVIRONMENT=staging`.

---

## 8. Sample export payload

See `PHASE_B_ANALYTICS_SAMPLE_PAYLOAD.json`.

Illustrative shape (counts are examples only):

```json
{
  "payload_version": 1,
  "period_start": "2026-07-09T00:00:00+00:00",
  "period_end": "2026-07-10T00:00:00+00:00",
  "leads_created_count": 3,
  "leads_converted_count": 1,
  "total_leads_count": 42,
  "conversion_rate_pct": 33.33,
  "active_subscriptions_count": 12,
  "mrr_summary_gbp": 1488.0,
  "support_tickets_open_count": 2,
  "support_tickets_closed_count": 1,
  "export_type": "aggregated_daily"
}
```

---

## 9. PII review (aggregate-only)

| Check | Expected | Done |
|-------|----------|------|
| No `email`, `phone`, `name`, `address`, `postcode` keys | Enforced by `is_aggregate_export_safe()` | ☐ |
| No row-level customer identifiers | Counts / sums only | ☐ |
| MRR is portfolio sum, not per-client | `mrr_summary_gbp` aggregate | ☐ |
| DPO / governance sign-off for Analytics pilot | Written approval | ☐ |

**Blocked if PII present:** sync status `SKIPPED`, reason `PII_BLOCKED` / `aggregate_export_contains_pii`.

---

## 10. Manual job execution steps (after flag enable — not this task)

| Step | Action |
|------|--------|
| 10.1 | Confirm `ZOHO_ANALYTICS_SYNC_ENABLED=true` and credentials configured |
| 10.2 | Admin JWT → `POST /api/admin/jobs/run` with `job: "zoho_analytics_export"` (portfolio_wide / governance scope as required by job runner) |
| 10.3 | Or: `POST /api/admin/integrations/zoho/sync` with `{"integration":"analytics","operation":"export_aggregates","payload":{}}` |
| 10.4 | Do **not** wire scheduler cron |

---

## 11. Expected outcomes

| Surface | Expected on success |
|---------|---------------------|
| Sync run | `status: success`, `message: analytics_export_delivered` |
| Audit log | `ZOHO_SYNC` action with integration `analytics` |
| Admin status | `integrations.analytics: true`; OAuth `oauth_status: healthy` after first refresh |
| Health | `oauth_integrations_configured` includes `analytics`; queue/dead-letter unchanged if single success |
| Zoho Analytics table | New appended row matching payload columns |

| Failure / skip | Meaning |
|----------------|---------|
| `DISABLED` | Flag still false |
| `NO_CREDENTIALS` / workspace skip | Missing refresh token or workspace id |
| `PII_BLOCKED` | Payload failed aggregate safety |
| `FAILED` / dead letter | API/OAuth error |

---

## 12. Kill-switch test

| Step | Action | Expected |
|------|--------|----------|
| 12.1 | Set `ZOHO_KILL_SWITCH=true` (staging) | ☐ |
| 12.2 | Attempt analytics sync / job | `SKIPPED` / kill switch; `overall_status: disabled` |
| 12.3 | Set `ZOHO_KILL_SWITCH=false` | Restore |

---

## 13. Rollback procedure

| Priority | Action |
|----------|--------|
| 1 | Set `ZOHO_ANALYTICS_SYNC_ENABLED=false` |
| 2 | Or set `ZOHO_KILL_SWITCH=true` for immediate stop of all Zoho sync |
| 3 | Optionally remove / rotate `ZOHO_ANALYTICS_REFRESH_TOKEN` |
| 4 | Call `ZohoOAuthManager.invalidate("analytics")` or restart to clear cache |
| 5 | Leave Phase A master flag as-is unless full Zoho shell rollback required |

---

## 14. Sign-off

| Role | Sign-off | Date |
|------|----------|------|
| Platform ops | ☐ Workspace + secrets staged | |
| Engineering | ☐ Schema matches builder | |
| DPO / governance | ☐ Aggregate-only approved | |
| Programme lead | ☐ Authorise enable flag | |

**After sign-off:** execute `PHASE_B_ANALYTICS_VALIDATION_PLAN.md`. Do not enable the Analytics flag during readiness preparation alone.
