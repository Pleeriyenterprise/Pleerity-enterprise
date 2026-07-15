# CRM Schema Reconciliation — `Pleerity_Lead_ID`

**Date:** 2026-07-14  
**Scope:** Code-derived only (implementation + existing implementation-pack docs that mirror `CRM_FIELD_MAP`).  
**Sandbox evidence (operator):** Leads Standard Layout — field absent; Fields listing — no hits for `Pleerity`, `Lead ID`, or `Pleerity_Lead_ID`.  
**Live evidence (C12):** `GET /crm/v6/Leads/search?criteria=(Pleerity_Lead_ID:equals:…)` → `INVALID_QUERY` / `the field is not available for search` / `api_name: Pleerity_Lead_ID`.

---

## 1. Every implementation reference

### Runtime code (authoritative)

| Location | Role |
|---|---|
| `services/integrations/zoho/registry.py` — `CRM_FIELD_MAP["lead_id"] = "Pleerity_Lead_ID"` | Outbound field map |
| `map_lead_to_zoho_crm()` | Always sets `payload["Pleerity_Lead_ID"] = lead["lead_id"]` |
| `validate_crm_outbound_payload()` | Requires `Pleerity_Lead_ID` non-empty string |
| `adapters/crm.py` — `build_pleerity_lead_id_search_criteria()` | Builds `(Pleerity_Lead_ID:equals:{lead_id})` |
| `adapters/crm.py` — `lookup_zoho_id_by_pleerity_lead_id()` | **Only** remote identity lookup |
| `adapters/crm.py` — `execute()` identity order | Local Mongo key → Pleerity_Lead_ID lookup → create → persist |
| `adapters/crm.py` — duplicate-conflict recovery | Re-lookup by same criteria after Zoho DUPLICATE errors |
| `config.py` — `crm_target_config_snapshot()` | Publishes `identity_field: "Pleerity_Lead_ID"` and resolution order |
| `operational_health.py` / Control Centre | Surfaces identity field / lookup source labels |

### Persistence (not a Zoho field)

| Location | Role |
|---|---|
| `sync_store.store_external_key("crm", lead_id, zoho_id)` / `get_external_key` | **Pleerity Mongo** `zoho_external_keys` — local binding after successful create/update |

There is **no** code that:

- calls Zoho Settings/Fields APIs to create custom fields  
- reads module metadata / layouts to verify fields exist  
- uses COQL (`/coql`)  
- uses Zoho “External ID” record APIs as the primary identity mechanism  
- matches by Email / Name  

### Implementation-pack documentation (expects manual create)

| Doc | Statement |
|---|---|
| `ZOHO_SANDBOX_READINESS_REPORT.md` §5 | **“Create custom fields on the Leads module in sandbox CRM before enabling `ZOHO_CRM_SYNC_ENABLED`.”** Table lists `Pleerity_Lead_ID` as Single Line, unique, external key |
| `STAGING_PILOT_PLAN.md` | Checklist: create `Pleerity_Lead_ID`, … in sandbox |
| `ZOHO_INTEGRATION_EXECUTIVE_SUMMARY.md` | “Configure CRM custom fields (`Pleerity_Lead_ID`, etc.)” |
| `CRM_CONFIGURATION_VALIDATION.md` / field registry | Identity field = Zoho custom `Pleerity_Lead_ID` |

### Tests

`tests/integrations/zoho/test_zoho_crm.py` asserts criteria string and map output contain `Pleerity_Lead_ID`; mocks lookup — never provisions CRM.

---

## 2. Was the field expected to be auto-provisioned, manual, or omitted?

| Hypothesis | Supported by code/docs? |
|---|---|
| Auto-provisioned by Pleerity | **No.** Zero provisioning/describe/settings-write code under `services/integrations/zoho`. |
| Accidental omit from code map | **No.** Present in map, validator, lookup, health, and tests. |
| **Manual CRM sandbox/deployment prerequisite** | **Yes.** Explicit Phase C prerequisite in `ZOHO_SANDBOX_READINESS_REPORT.md` §5 and pilot plan. |

**Why it is absent now:** the field was **never created in this Zoho sandbox**. Enabling `ZOHO_CRM_SYNC_ENABLED=true` skipped the sandbox checklist item that required creating CRM custom fields. C11 status checks only verify env/oauth/module name — they **do not** (and cannot, without a describe call) verify Zoho field existence. The live search error is therefore a **sandbox↔contract gap**, not a missing map entry in code.

The error text (“not available for search”) is also the response Zoho returns when the API name is unknown / not searchable — consistent with **field does not exist** (confirmed by Fields listing).

---

## 3. Lookup mechanism as implemented (not assumed)

```text
GET {ZOHO_API_BASE}/crm/v6/{ZOHO_CRM_MODULE}/search
    ?criteria=(Pleerity_Lead_ID:equals:{pleerity_lead_id})
```

| Mechanism | Used? |
|---|---|
| Record **Search API** with **criteria** | **Yes** (sole remote lookup) |
| COQL | No |
| External ID / `getRecordByExternalId` | No |
| Email / name / word search | Explicitly forbidden |
| Local Mongo external key | Yes — **first** in identity order (before Search) |

Identity order in `ZohoCrmAdapter.execute`:

1. `zoho_external_keys` (Pleerity DB)  
2. Search API by `Pleerity_Lead_ID`  
3. `POST /crm/v6/Leads` create  
4. Persist returned CRM id into `zoho_external_keys`  

Governance forbids changing step 2 to email/name heuristics. Switching to COQL would still require the **same custom field to exist**. External-ID APIs would require a different Zoho feature configuration and are **not** what the current adapter calls.

---

## 4. Exact CRM field contract derived from code + readiness table

Code only names the **API name** and requires it on outbound payloads and in Search criteria. Type/unique/length are specified in the readiness report that is explicitly sourced from `CRM_FIELD_MAP`. Combined contract:

| Attribute | Value | Derivation |
|---|---|---|
| **Module** | `Leads` (default `ZOHO_CRM_MODULE`) | `zoho_crm_module()` / search path |
| **Label (UI)** | `Pleerity Lead ID` | Not in code; conventional UI label for API `Pleerity_Lead_ID` (ops may use this exact label so API name stays `Pleerity_Lead_ID`) |
| **API name** | `Pleerity_Lead_ID` | Hardcoded in map + criteria — **must match exactly** |
| **Field type** | Single Line (text) | `ZOHO_SANDBOX_READINESS_REPORT.md` §5 |
| **Length** | Not hardcoded; implement ≥ **64** (Pleerity ids like `LEAD-20260714090602-6D5752` ≈ 28 chars; leave headroom) | Length not in code; practical bound from `lead_id` format |
| **Unique constraint** | **Yes (required for governed upsert)** | Readiness §5 “Yes”; config guide “Unique recommended” → treat as **required** for duplicate prevention when local key missing |
| **Zoho “External Field” checkbox** | **Not referenced in code** | Docs use “external key” to mean **Pleerity identity key mirrored into CRM**, stored locally in `zoho_external_keys`. Do **not** require Zoho’s separate External Field product setting unless ops later chooses that as an *additional* option (would need adapter change). |
| **Searchability / index** | **Mandatory** | Lookup uses Search API criteria; field must be searchable / criteria-eligible |
| **Duplicate check participation (Zoho)** | Not configured via API in code; uniqueness of the custom field is the intended CRM-side guard | Duplicate recovery in code re-searches same field after DUPLICATE errors |
| **Layout** | Readiness: add Pleerity fields to a dedicated Lead layout section | Not enforced by API |
| **Required on layout** | Outbound code always sends it; Zoho “required” on layout optional for QA | Validator requires it before HTTP |

Related custom fields in the same map (also undocumented in this sandbox if Fields search shows none — expect same gap):  
`Pleerity_Client_ID`, `Pleerity_Status`, `Pleerity_Service_Interest`, `Pleerity_Created_At`, `Pleerity_Updated_At`, and possibly custom `Lead_Score` if not using a standard field.

---

## 5. Recommendation: manual CRM configuration (aligned with design)

**Manual creation is the intended, governed path.**  
Replacing it with implementation shortcuts (skip lookup, match email, invent API name) would weaken the SoR identity contract already certified for Phase C.

**Optional smallest code improvement (separate change request — not required to unblock sandbox):**

- Add a **config/preflight** that describes Leads fields (or a hard fail after a probe search) and surfaces `CONFIG_INVALID` / `missing_crm_field:Pleerity_Lead_ID` in `crm_ops` before enqueue.  
- Does **not** remove the need to create the field in Zoho.

Do **not** change identity order or switch to COQL solely to work around a missing field.

---

## 6. Click-by-click sandbox guide (exact match to implementation)

Perform in the **same Zoho CRM org** that issued `ZOHO_CRM_REFRESH_TOKEN` (EU sandbox matching `ZOHO_API_BASE`).

### A. Create the identity field

1. Sign in to Zoho CRM (sandbox).  
2. Go to **Setup** (gear).  
3. Under **Customization**, open **Modules and Fields**.  
4. Open module **Leads**.  
5. Open the **Fields** listing for Leads (not only the layout canvas).  
6. **New Field** → type **Single Line**.  
7. Set:  
   - **Label:** `Pleerity Lead ID`  
   - Confirm **API Name** is exactly `Pleerity_Lead_ID` (edit API name if Zoho defaulted to something else).  
8. Set **Maximum length** to at least **64**.  
9. Enable **Do not allow duplicate values** / Unique (wording varies by CRM edition).  
10. Ensure the field is **usable in search / criteria / filters** (edition-specific checkbox; required for Search API).  
11. **Do not** rely on Email as identity.  
12. Save.

### B. Layout visibility (QA)

1. Still under Leads → **Layouts** → Standard (or the layout used by the integration user).  
2. Add **Pleerity Lead ID** to a section named e.g. `Pleerity Integration`.  
3. Save layout.

### C. Verify API name before re-running C12

1. Fields listing → open `Pleerity Lead ID` → confirm API name `Pleerity_Lead_ID`.  
2. Optional: Search API smoke with a fake value should return **204/empty**, not `INVALID_QUERY` / “field is not available for search”.

### D. Remaining custom fields (same session — map will send them)

Create (or confirm) similarly, per readiness §5 / `CRM_FIELD_MAP`:

| API name | Type (from readiness) |
|---|---|
| `Pleerity_Client_ID` | Single Line |
| `Pleerity_Status` | Single Line |
| `Pleerity_Service_Interest` | Single Line |
| `Pleerity_Created_At` | DateTime |
| `Pleerity_Updated_At` | DateTime |
| `Lead_Score` | Number (if not already a searchable standard/custom field) |

Outbound write may still partially succeed for create once identity field exists; missing optional customs can cause Zoho field errors — create these before the next controlled sync.

### E. After fields exist

1. Resolve/replay CRM dead letter for `ZSYNC-361872C6B860` or leave resolved and use a **new** test lead.  
2. Drain/inspect pending CRM queue items.  
3. Re-run `PHASE_C_CRM_LIVE_STAGING_ACTIVATION_01` C12 — do not auto-retry loops.

---

## 7. Summary verdict of reconciliation

| Question | Answer |
|---|---|
| Why is the field absent? | Never auto-created; manual prerequisite was not completed in this sandbox. |
| Does code expect it? | Yes — map, validator, Search criteria, recovery. |
| How must lookup work? | Record Search API + criteria on `Pleerity_Lead_ID` only. |
| Safer path? | **Create the field manually to the contract above**; keep implementation. Optional later: preflight describe. |

**Do not invent Email/Name matching or drop identity lookup to “make C12 green.”**
