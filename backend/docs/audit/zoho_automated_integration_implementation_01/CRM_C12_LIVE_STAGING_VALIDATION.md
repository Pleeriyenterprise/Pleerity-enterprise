# CRM_C12_LIVE_STAGING_VALIDATION

**Phase:** `PHASE_C_CRM_LIVE_STAGING_ACTIVATION_01`
**Generated:** `2026-07-14T19:54:14.987237+00:00`
**Staging SHA:** `476b6c970c1a7deecfbcd3963cf3fe5da50f0b5b`
**Production SHA:** `89217062481b4eb858a8b530ec90c83de067a4be`
**Test lead:** `LEAD-20260714195426-198E68`
**CRM external id:** `625014000001948001`
**Verdict:** **CRM_STAGING_PASS_WITH_CONDITIONS**

## Summary

| Item | Value |
|---|---|
| Dedicated lead | `LEAD-20260714195426-198E68` |
| CRM Lead id | `625014000001948001` |
| Create path | Queue `lead.created` `ZSYNC-2327F1C59A60` → `crm_outbound_create_ok` |
| Update / lost / idempotency | All PUT / same CRM id |
| Queue / DL after | 0 / 0 |
| Inbound webhook | Rejected (401) |
| Production | `89217062…` unchanged |

## Recovery prerequisite

See `CRM_SEARCHABILITY_RECOVERY_REPORT.md` — recovery_verdict=`PASS`

**Note:** Prior invalid run reused recovery lead `LEAD-20260714090602-6D5752`; this dedicated run supersedes it.

## Checks

| Check | Pass |
|---|---|
| `staging_commit_healthy_prod_pin` | PASS |
| `crm_oauth_per_integration_no_legacy` | PASS |
| `queue_dl_clear_before_c12` | PASS |
| `create_dedicated_test_lead` | PASS |
| `first_upsert_create_or_bind_with_external_id` | PASS |
| `pleerity_update` | PASS |
| `second_upsert_update_same_external_id` | PASS |
| `pleerity_mark_lost` | PASS |
| `lost_status_update_only_same_key` | PASS |
| `idempotency_two_further_upserts_single_external_id` | PASS |
| `inbound_crm_webhook_rejected` | PASS |
| `queue_and_dl_clear_after` | PASS |
| `other_integrations_off` | PASS |
| `platform_health_healthy` | PASS |
| `production_still_unchanged` | PASS |
| `crm_oauth_after_live_call` | PASS |

## Conditions

- `analytics_flag_still_enabled_not_executed`
- `first_crm_create_occurred_via_queue_drain_before_explicit_sync`

## `search_probe_inherited`

```json
{
  "oauth_refresh_via": "upsert_lead_on_prior_failed_lead",
  "probe_sync_status": "success",
  "probe_sync_message": "crm_outbound_create_ok",
  "probe_sync_external_id": "625014000001936001",
  "probe_sync_id": "ZSYNC-BAAC8BDFB65D",
  "token_expires_in_s": 3594.255357503891,
  "refresh_token_source_cached": "per_integration",
  "readonly_search": {
    "metadata_http": 200,
    "field": {
      "api_name": "Pleerity_Lead_ID",
      "display_label": "Pleerity Lead ID",
      "data_type": "text",
      "searchable": true,
      "id": "625014000001931007",
      "unique": {
        "case_sensitive": false
      }
    },
    "search_http": 204,
    "criteria": "(Pleerity_Lead_ID:equals:PLEERITY_SEARCHABILITY_PROBE_NO_MATCH)",
    "invalid_query": false,
    "search_body_code": null,
    "search_message": null,
    "search_reason": null,
    "supports_search": true
  }
}
```

## `create_sync`

```json
{
  "success": true,
  "sync_id": "ZSYNC-CED2B90E0E60",
  "status": "success",
  "message": "crm_outbound_update_ok",
  "skip_reason": null,
  "external_id": "625014000001948001",
  "metadata": {
    "result_summary": {
      "lead_id": "LEAD-20260714195426-198E68",
      "external_id": "625014000001948001",
      "http_method": "PUT",
      "identity_source": "external_key",
      "module": "Leads",
      "payload_version": 1,
      "mapping_version": "1.0.0",
      "identity_field": "Pleerity_Lead_ID",
      "duplicate_create_prevented": false,
      "operation": "upsert_lead"
    }
  },
  "_http_status": 200
}
```

## `update_sync`

```json
{
  "success": true,
  "sync_id": "ZSYNC-A8C5247B6555",
  "status": "success",
  "message": "crm_outbound_update_ok",
  "skip_reason": null,
  "external_id": "625014000001948001",
  "metadata": {
    "result_summary": {
      "lead_id": "LEAD-20260714195426-198E68",
      "external_id": "625014000001948001",
      "http_method": "PUT",
      "identity_source": "external_key",
      "module": "Leads",
      "payload_version": 1,
      "mapping_version": "1.0.0",
      "identity_field": "Pleerity_Lead_ID",
      "duplicate_create_prevented": false,
      "operation": "upsert_lead"
    }
  },
  "_http_status": 200
}
```

## `lost_sync`

```json
{
  "success": true,
  "sync_id": "ZSYNC-9C29618FEC7F",
  "status": "success",
  "message": "crm_outbound_update_ok",
  "skip_reason": null,
  "external_id": "625014000001948001",
  "metadata": {
    "result_summary": {
      "lead_id": "LEAD-20260714195426-198E68",
      "external_id": "625014000001948001",
      "http_method": "PUT",
      "identity_source": "external_key",
      "module": "Leads",
      "payload_version": 1,
      "mapping_version": "1.0.0",
      "identity_field": "Pleerity_Lead_ID",
      "duplicate_create_prevented": false,
      "operation": "lead.lost"
    }
  },
  "_http_status": 200
}
```

## `idempotency_sync_a`

```json
{
  "success": true,
  "sync_id": "ZSYNC-7C5D44EEDFF3",
  "status": "success",
  "message": "crm_outbound_update_ok",
  "skip_reason": null,
  "external_id": "625014000001948001",
  "metadata": {
    "result_summary": {
      "lead_id": "LEAD-20260714195426-198E68",
      "external_id": "625014000001948001",
      "http_method": "PUT",
      "identity_source": "external_key",
      "module": "Leads",
      "payload_version": 1,
      "mapping_version": "1.0.0",
      "identity_field": "Pleerity_Lead_ID",
      "duplicate_create_prevented": false,
      "operation": "upsert_lead"
    }
  },
  "_http_status": 200
}
```

## `idempotency_sync_b`

```json
{
  "success": true,
  "sync_id": "ZSYNC-15AB7DBD7FC5",
  "status": "success",
  "message": "crm_outbound_update_ok",
  "skip_reason": null,
  "external_id": "625014000001948001",
  "metadata": {
    "result_summary": {
      "lead_id": "LEAD-20260714195426-198E68",
      "external_id": "625014000001948001",
      "http_method": "PUT",
      "identity_source": "external_key",
      "module": "Leads",
      "payload_version": 1,
      "mapping_version": "1.0.0",
      "identity_field": "Pleerity_Lead_ID",
      "duplicate_create_prevented": false,
      "operation": "upsert_lead"
    }
  },
  "_http_status": 200
}
```

## `crm_ops_after`

```json
{
  "enabled": true,
  "manual_only": true,
  "healthy": true,
  "configuration_complete": true,
  "configuration_missing": [],
  "crm_target": {
    "module": "Leads",
    "module_configured": true,
    "oauth_configured": true,
    "shared_client_configured": true,
    "api_base": "https://www.zohoapis.eu",
    "identity_field": "Pleerity_Lead_ID",
    "identity_resolution_order": [
      "external_key",
      "pleerity_lead_id_lookup",
      "create",
      "persist_external_key"
    ],
    "forbidden_identity_matchers": [
      "email",
      "name",
      "heuristic"
    ],
    "expected_scope": "ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.leads.UPDATE,ZohoCRM.modules.leads.READ",
    "target_complete": true,
    "missing": []
  },
  "oauth_status": "healthy",
  "last_success_at": "2026-07-14T19:54:58.778207+00:00",
  "last_success_sync_id": "ZSYNC-15AB7DBD7FC5",
  "last_failure_at": "2026-07-14T09:06:06.418924+00:00",
  "last_failure_sync_id": "ZSYNC-361872C6B860",
  "last_failure_error": "Zoho API 400: {\"code\":\"INVALID_QUERY\",\"details\":{\"reason\":\"the field is not available for search\",\"api_name\":\"Pleerity_Lead_ID\"},\"message\":\"Invalid query formed\",\"status\":\"error\"}\n",
  "consecutive_failures": 0,
  "failure_count_24h": 1,
  "queue_depth_pending": 0,
  "queue_depth_failed": 0,
  "duplicate_skips": 0,
  "dead_letter_count": 0,
  "replay_count": 0,
  "next_expected_sync": "manual_only_no_cron",
  "incident_policy": {
    "level": "ok",
    "reason": "healthy",
    "actionable_incident": false,
    "consecutive_failures": 0
  },
  "identity_resolution_order": [
    "external_key",
    "pleerity_lead_id_lookup",
    "create",
    "persist_external_key"
  ]
}
```

## `external_ids_observed`

```json
[
  "625014000001948001",
  "625014000001948001",
  "625014000001948001"
]
```
