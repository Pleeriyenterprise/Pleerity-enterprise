# Phase B — Analytics Target Table Compatibility Review

**Programme:** ZOHO SANDBOX PILOT IMPLEMENTATION  
**Date:** 2026-07-10  
**Staging workspace ID (operator-provided):** `272205000000016002`  
**Export run:** None (analysis + code correction only)  
**Verdict:** Pre-fix adapter was **incompatible** with Zoho Analytics API V2. **Smallest safe correction implemented** (existing-table append path).

---

## 1. Pre-fix behaviour (as found)

| Item | Implemented value |
|------|-------------------|
| Path | `/analytics/v2/workspaces/{workspace_id}/data` |
| Host | `{ZOHO_API_BASE}` default `https://www.zohoapis.eu` |
| Full URL example | `https://www.zohoapis.eu/analytics/v2/workspaces/272205000000016002/data` |
| Body | JSON `{"data": <object>, "import_type": "append"}` |
| Table name in request | **None** |
| View ID | **None** |
| `ZANALYTICS-ORGID` | **Not sent** |
| `/restapi/v2` | **Absent** |

This path does **not** match Zoho Analytics Bulk Import V2.

---

## 2. Official Zoho Analytics API V2 (EU)

| Mode | URI | Creates table? |
|------|-----|----------------|
| **New table** | `POST https://analyticsapi.zoho.eu/restapi/v2/workspaces/{workspace-id}/data` | Yes — requires `CONFIG.tableName`; returns `viewId` |
| **Existing table** | `POST https://analyticsapi.zoho.eu/restapi/v2/workspaces/{workspace-id}/views/{view-id}/data` | No — appends/updates existing view |

Both require:

- Header `Authorization: Zoho-oauthtoken …`
- Header `ZANALYTICS-ORGID: <org-id>`
- Query `CONFIG` (JSON): `importType`, `fileType`, `autoIdentify` (existing) or `tableName` + `fileType` + `autoIdentify` (new)
- Multipart body: `FILE` or `DATA`

References:

- [Import Data — Existing Table](https://www.zoho.com/analytics/api/v2/bulk-api/import-data/existing-table.html)
- [Import Data — New Table](https://www.zoho.com/analytics/api/v2/bulk-api/import-data/new-table.html)
- [API Specification / DC hosts](https://www.zoho.com/analytics/api/v2/api-specification.html) — EU host `analyticsapi.zoho.eu`

---

## 3. Answers to review questions

### 1. Exact request URL produced (pre-fix)

```
https://www.zohoapis.eu/analytics/v2/workspaces/272205000000016002/data
```

(assuming default `ZOHO_API_BASE` and workspace ID above)

### 2. New-table vs existing-table endpoint?

**Neither.** Pre-fix URL was a non-official inventedish path. It was closer in shape to “workspace `/data`” (new-table) but used wrong host, wrong path prefix, wrong body, and no `tableName` / org header.

### 3. Does the first export create a table automatically?

**Pre-fix:** No reliable create — request would fail against official API.  
**Post-fix:** **No.** Adapter uses **existing-table** import only. Operator must create the table first and supply its View ID.

### 4. Exact table name supplied in the API request?

**Pre-fix:** None.  
**Post-fix:** Table name is **not** sent on existing-table import (Zoho targets by **view ID**). Documented operator table name constant: `pleerity_daily_aggregates` (`ANALYTICS_AGGREGATE_TABLE_NAME`).

### 5. Subsequent exports — append or duplicate tables?

**Post-fix:** `CONFIG.importType = append` to the **same** `view-id` → appends rows; does **not** create new tables.

### 6. Does an existing table require a Zoho View ID?

**Yes.** Official existing-table URI includes `/views/{view-id}/data`.

### 7. Is `ZOHO_ANALYTICS_VIEW_ID` required?

**Yes** (post-fix). Also require Analytics org ID via `ZOHO_ANALYTICS_ORG_ID` (fallback: `ZOHO_ORG_ID`).

### 8. `/restapi/v2` path and organisation header?

| Requirement | Pre-fix | Post-fix |
|-------------|-----------|------------|
| `/restapi/v2/...` | No | Yes |
| `ZANALYTICS-ORGID` | No | Yes |
| Host `analyticsapi.zoho.eu` | No (`zohoapis.eu`) | Yes (`ZOHO_ANALYTICS_API_BASE`) |

### 9. JSON payload / config vs API V2?

| Aspect | Pre-fix | Post-fix |
|--------|-----------|------------|
| Body | Application JSON object | Multipart `DATA` = JSON **array** of one row |
| Config | `import_type` in body | Query `CONFIG` with `importType` / `fileType` / `autoIdentify` |
| Match V2 | **No** | **Yes** (existing-table sync import) |

### 10. Column names and Zoho data types

| Column | Pleerity type | Compatible Zoho type |
|--------|---------------|----------------------|
| `payload_version` | int | NUMBER |
| `period_start` | ISO-8601 string | PLAIN (or DATE if formatted) |
| `period_end` | ISO-8601 string | PLAIN (or DATE if formatted) |
| `leads_created_count` | int | NUMBER |
| `leads_converted_count` | int | NUMBER |
| `total_leads_count` | int | NUMBER |
| `conversion_rate_pct` | float | DECIMAL_NUMBER / PERCENT |
| `active_subscriptions_count` | int | NUMBER |
| `mrr_summary_gbp` | float | DECIMAL_NUMBER / CURRENCY |
| `support_tickets_open_count` | int | NUMBER |
| `support_tickets_closed_count` | int | NUMBER |
| `export_type` | string | PLAIN |

---

## 4. Correction implemented (smallest safe)

**Choice:** Existing-table append (matches Phase B checklist: create table first, then append).

| Change | Detail |
|--------|--------|
| Adapter | `services/integrations/zoho/adapters/analytics.py` |
| URL | `{ZOHO_ANALYTICS_API_BASE}/restapi/v2/workspaces/{ws}/views/{view}/data` |
| Default API base | `https://analyticsapi.zoho.eu` |
| Headers | `ZANALYTICS-ORGID` |
| CONFIG | `importType=append`, `fileType=json`, `autoIdentify=true` |
| DATA | JSON array `[export_row]` |
| Skip if missing | `ZOHO_ANALYTICS_WORKSPACE_ID`, `ZOHO_ANALYTICS_VIEW_ID`, `ZOHO_ANALYTICS_ORG_ID` |
| Client | Multipart + custom headers + optional `api_base` |
| Config accessors | `zoho_analytics_view_id`, `zoho_analytics_org_id`, `zoho_analytics_api_base` |
| Tests | `tests/integrations/zoho/test_zoho_analytics_import.py` |

**Not implemented (intentionally):** new-table auto-create path (would risk duplicate tables if `tableName` reused incorrectly without storing returned `viewId`).

---

## 5. Post-fix request (workspace `272205000000016002`)

```
POST https://analyticsapi.zoho.eu/restapi/v2/workspaces/272205000000016002/views/{ZOHO_ANALYTICS_VIEW_ID}/data
  ?CONFIG={"importType":"append","fileType":"json","autoIdentify":"true"}

Headers:
  Authorization: Zoho-oauthtoken <token>
  ZANALYTICS-ORGID: <ZOHO_ANALYTICS_ORG_ID>

Multipart:
  DATA: [{"payload_version":1,"period_start":"...","export_type":"aggregated_daily",...}]
```

---

## 6. Operator prerequisites before Phase B enable

| Variable | Required | Notes |
|----------|----------|-------|
| `ZOHO_ANALYTICS_WORKSPACE_ID` | Yes | `272205000000016002` |
| `ZOHO_ANALYTICS_VIEW_ID` | Yes | View ID of `pleerity_daily_aggregates` (or chosen table) |
| `ZOHO_ANALYTICS_ORG_ID` | Yes | From Analytics Get Organizations API |
| `ZOHO_ANALYTICS_REFRESH_TOKEN` | Yes | Scope `ZohoAnalytics.data.create` |
| `ZOHO_ANALYTICS_API_BASE` | Optional | Default `https://analyticsapi.zoho.eu` |
| `ZOHO_ANALYTICS_SYNC_ENABLED` | Keep `false` until live validation | Not enabled by this change |

**How to get View ID:** Zoho Analytics UI → open table → URL / settings often expose view id; or list views via Analytics metadata API after OAuth is ready.

---

## 7. Constraints honoured

| Constraint | Status |
|------------|--------|
| No Analytics export run | Yes |
| No Render secrets added | Yes |
| Production untouched | Yes |
| Flag not enabled | Yes |

---

## 8. Follow-up

1. Create table `pleerity_daily_aggregates` in workspace `272205000000016002` with columns in §3.10  
2. Record View ID → set `ZOHO_ANALYTICS_VIEW_ID` on staging  
3. Set `ZOHO_ANALYTICS_ORG_ID`  
4. Proceed with Phase B readiness checklist / validation plan  
5. Do **not** enable `ZOHO_ANALYTICS_SYNC_ENABLED` until those secrets exist
