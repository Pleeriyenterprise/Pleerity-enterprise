# CRM Concurrency / Race-Condition Validation

**Generated:** `2026-07-14T20:17:43.360526+00:00` (raw races) / settlement `2026-07-14T20:29:49.933525+00:00`
**Staging SHA:** `476b6c970c1a7deecfbcd3963cf3fe5da50f0b5b`
**Production SHA:** `89217062481b4eb858a8b530ec90c83de067a4be`
**Verdict:** **CRM_CONCURRENCY_PASS_WITH_CONDITIONS**

## Executive result

| Claim | Result |
|---|---|
| Exactly one CRM Lead per Pleerity lead (Search) | **PASS** |
| External key authoritative & single | **PASS** |
| No duplicate CRM records under races | **PASS** |
| Queue / replay / manual converge | **PASS with DL/settle conditions** |
| Hard queue locking / CRM run-lock | **ABSENT** (Analytics-only pattern) |
| Optimistic concurrency | **ABSENT** |
| Production untouched | **PASS** (`89217062…`) |

## Findings

- Concurrent create/queue/manual paths issued overlapping POSTs; Zoho returned DUPLICATE_DATA on Pleerity_Lead_ID.
- Zoho unique constraint prevented a second CRM Lead for the same Pleerity_Lead_ID (Search count never >1 after settle).
- Adapter duplicate recovery did not always absorb DUPLICATE_DATA under concurrency (search lag / parallel loser → dead letter).
- External key remained single-document and matched the sole CRM id after settle upsert/replay.
- Queue has no claim/lock; concurrent process-queue is racy but final CRM identity still converged via unique field + key upsert.
- No optimistic concurrency on zoho_external_keys; last writer wins (observed single zoho_id).
- crm_ops remained healthy; production pin unchanged.

## Conditions

- `soft_idempotency_not_hard_locking`
- `no_queue_claim_no_crm_run_lock`
- `duplicate_data_under_concurrency_relies_on_zoho_unique_field`
- `search_index_lag_can_break_duplicate_recovery_path`
- `induced_lead_not_found_dl_residue_classified`

## Code-derived controls

```json
{
  "queue_claim": false,
  "crm_run_lock": false,
  "admin_serialized": false,
  "external_key_upsert": true,
  "pleerity_lead_id_search_before_create": true,
  "duplicate_conflict_recovery": true,
  "optimistic_versioning": false,
  "processing_status_written": false,
  "notes": "CRM relies on soft identity (local key \u2192 Search Pleerity_Lead_ID \u2192 create \u2192 persist) plus Zoho unique field + duplicate recovery. Unlike Analytics, no DB run-lock / queue claim."
}
```

## Settlement proofs

```json
{
  "leads_checked": 8,
  "identity_converged": true,
  "strict_no_dl": true,
  "duplicate_crm_records_detected": false,
  "leads_failed_identity": [],
  "leads_with_dl_after_settle": []
}
```

```json
[
  {
    "lead_id": "LEAD-20260714201807-6BC2A8",
    "settle_upsert_status": "success",
    "settle_external_id": "625014000001956001",
    "replays": [
      {
        "dead_letter_id": "ZDL-9CCDC0C2448D",
        "status": "success",
        "message": "crm_outbound_update_ok",
        "external_id": null
      },
      {
        "dead_letter_id": "ZDL-526B7245733C",
        "status": "success",
        "message": "crm_outbound_update_ok",
        "external_id": null
      },
      {
        "dead_letter_id": "ZDL-22315CEF3F6D",
        "status": "success",
        "message": "crm_outbound_update_ok",
        "external_id": null
      }
    ],
    "proof": {
      "lead_id": "LEAD-20260714201807-6BC2A8",
      "external_key_docs": 1,
      "external_key_zoho_ids": [
        "625014000001956001"
      ],
      "search_http": 200,
      "search_ids": [
        "625014000001956001"
      ],
      "search_count": 1,
      "get_http": 200,
      "get_id": "625014000001956001",
      "get_pleerity_lead_id": "LEAD-20260714201807-6BC2A8",
      "unresolved_dl": 0,
      "dl_ids": [],
      "duplicate_crm": false,
      "single_crm_record": true,
      "pass_strict_no_dl": true,
      "pass_identity": true
    }
  },
  {
    "lead_id": "LEAD-20260714201828-2EDEAE",
    "settle_upsert_status": "success",
    "settle_external_id": "625014000001946001",
    "replays": [],
    "proof": {
      "lead_id": "LEAD-20260714201828-2EDEAE",
      "external_key_docs": 1,
      "external_key_zoho_ids": [
        "625014000001946001"
      ],
      "search_http": 200,
      "search_ids": [
        "625014000001946001"
      ],
      "search_count": 1,
      "get_http": 200,
      "get_id": "625014000001946001",
      "get_pleerity_lead_id": "LEAD-20260714201828-2EDEAE",
      "unresolved_dl": 0,
      "dl_ids": [],
      "duplicate_crm": false,
      "single_crm_record": true,
      "pass_strict_no_dl": true,
      "pass_identity": true
    }
  },
  {
    "lead_id": "LEAD-20260714201904-7CCA51",
    "settle_upsert_status": "success",
    "settle_external_id": "625014000001947002",
    "replays": [],
    "proof": {
      "lead_id": "LEAD-20260714201904-7CCA51",
      "external_key_docs": 1,
      "external_key_zoho_ids": [
        "625014000001947002"
      ],
      "search_http": 200,
      "search_ids": [
        "625014000001947002"
      ],
      "search_count": 1,
      "get_http": 200,
      "get_id": "625014000001947002",
      "get_pleerity_lead_id": "LEAD-20260714201904-7CCA51",
      "unresolved_dl": 0,
      "dl_ids": [],
      "duplicate_crm": false,
      "single_crm_record": true,
      "pass_strict_no_dl": true,
      "pass_identity": true
    }
  },
  {
    "lead_id": "LEAD-20260714201920-82FE08",
    "settle_upsert_status": "success",
    "settle_external_id": "625014000001964002",
    "replays": [],
    "proof": {
      "lead_id": "LEAD-20260714201920-82FE08",
      "external_key_docs": 1,
      "external_key_zoho_ids": [
        "625014000001964002"
      ],
      "search_http": 200,
      "search_ids": [
        "625014000001964002"
      ],
      "search_count": 1,
      "get_http": 200,
      "get_id": "625014000001964002",
      "get_pleerity_lead_id": "LEAD-20260714201920-82FE08",
      "unresolved_dl": 0,
      "dl_ids": [],
      "duplicate_crm": false,
      "single_crm_record": true,
      "pass_strict_no_dl": true,
      "pass_identity": true
    }
  },
  {
    "lead_id": "LEAD-20260714202013-830C30",
    "settle_upsert_status": "success",
    "settle_external_id": "625014000001964012",
    "replays": [],
    "proof": {
      "lead_id": "LEAD-20260714202013-830C30",
      "external_key_docs": 1,
      "external_key_zoho_ids": [
        "625014000001964012"
      ],
      "search_http": 200,
      "search_ids": [
        "625014000001964012"
      ],
      "search_count": 1,
      "get_http": 200,
      "get_id": "625014000001964012",
      "get_pleerity_lead_id": "LEAD-20260714202013-830C30",
      "unresolved_dl": 0,
      "dl_ids": [],
      "duplicate_crm": false,
      "single_crm_record": true,
      "pass_strict_no_dl": true,
      "pass_identity": true
    }
  },
  {
    "lead_id": "LEAD-20260714202015-7FEAFC",
    "settle_upsert_status": "success",
    "settle_external_id": "625014000001952001",
    "replays": [],
    "proof": {
      "lead_id": "LEAD-20260714202015-7FEAFC",
      "external_key_docs": 1,
      "external_key_zoho_ids": [
        "625014000001952001"
      ],
      "search_http": 200,
      "search_ids": [
        "625014000001952001"
      ],
      "search_count": 1,
      "get_http": 200,
      "get_id": "625014000001952001",
      "get_pleerity_lead_id": "LEAD-20260714202015-7FEAFC",
      "unresolved_dl": 0,
      "dl_ids": [],
      "duplicate_crm": false,
      "single_crm_record": true,
      "pass_strict_no_dl": true,
      "pass_identity": true
    }
  },
  {
    "lead_id": "LEAD-20260714202016-13F8A4",
    "settle_upsert_status": "success",
    "settle_external_id": "625014000001953002",
    "replays": [],
    "proof": {
      "lead_id": "LEAD-20260714202016-13F8A4",
      "external_key_docs": 1,
      "external_key_zoho_ids": [
        "625014000001953002"
      ],
      "search_http": 200,
      "search_ids": [
        "625014000001953002"
      ],
      "search_count": 1,
      "get_http": 200,
      "get_id": "625014000001953002",
      "get_pleerity_lead_id": "LEAD-20260714202016-13F8A4",
      "unresolved_dl": 0,
      "dl_ids": [],
      "duplicate_crm": false,
      "single_crm_record": true,
      "pass_strict_no_dl": true,
      "pass_identity": true
    }
  },
  {
    "lead_id": "LEAD-20260714201754-D32F82",
    "settle_upsert_status": "success",
    "settle_external_id": "625014000001935002",
    "replays": [],
    "proof": {
      "lead_id": "LEAD-20260714201754-D32F82",
      "external_key_docs": 1,
      "external_key_zoho_ids": [
        "625014000001935002"
      ],
      "search_http": 200,
      "search_ids": [
        "625014000001935002"
      ],
      "search_count": 1,
      "get_http": 200,
      "get_id": "625014000001935002",
      "get_pleerity_lead_id": "LEAD-20260714201754-D32F82",
      "unresolved_dl": 0,
      "dl_ids": [],
      "duplicate_crm": false,
      "single_crm_record": true,
      "pass_strict_no_dl": true,
      "pass_identity": true
    }
  }
]
```

## crm_ops after settlement

```json
{
  "healthy": true,
  "oauth_status": "healthy",
  "queue_depth_pending": 0,
  "dead_letter_count": 4,
  "last_success_at": "2026-07-14T20:29:33.877703+00:00",
  "incident_policy": {
    "level": "ok",
    "reason": "healthy",
    "actionable_incident": false,
    "consecutive_failures": 0
  }
}
```

## Smallest governed follow-up (proposed — not implemented)

1. On Zoho `DUPLICATE_DATA` for `Pleerity_Lead_ID`, prefer bind from `details.duplicate_record.id` before Search (avoids search-lag miss).
2. Add Analytics-style claim (`pending`→`processing`) for CRM queue fetch.
3. Optional per-lead sync mutex (short TTL) around create path.
4. Unique index on `zoho_external_keys(integration,pleerity_id,resource_type)`.

