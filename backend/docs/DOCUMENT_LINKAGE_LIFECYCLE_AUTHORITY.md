# Document Linkage Lifecycle Authority

**Authority ID:** `DOCUMENT_LINKAGE_LIFECYCLE_AUTHORITY`  
**Module:** `backend/services/document_linkage_lifecycle_authority.py`  
**Frontend mirror:** `frontend/src/utils/issueLifecycleAuthority.js`

## Question answered

> Is there still an unresolved document linkage problem?

If **no**, every active operational surface must reflect that automatically while preserving audit history.

## Lifecycle

```
Document uploaded
  → AI extraction / matching
  → Unable to confidently match OR missing requirement link
  → document_linkage_state = RECONCILIATION_REQUIRED (Documents attention queue)
  → Optional: compliance gap opens (MISMATCHED_EVIDENCE / MISSING_EVIDENCE)
  → Optional: bridge creates maintenance issue (operational_root_key = gap_key)
Operator links requirement
  → document_linkage_state = LINKED
  → Gap sync resolves open gaps
  → Bridge auto-resolves linked maintenance issues (status = resolved, auto_resolved = true)
  → Audit preserved (resolution_note, resolution_authority_source, linked IDs)
```

## Issue status semantics

| Status | Meaning |
|--------|---------|
| open / new / triaged / monitoring / investigating / ready_for_work_order / in_progress | Active — surfaces in open queues |
| resolved | Exception cleared — historical only |
| closed / cancelled | Terminal — manual or WO path |

## Auto-resolve triggers

- `requirement_linked` — manual reconcile-linkage when document is LINKED
- `gap_resolved` — compliance gap sync closes stale gap rows
- Future: `evidence_accepted`, `ai_re_match`, `requirement_archived`, `duplicate_reconciled`

## Consumers (single authority)

| Surface | Authority source |
|---------|------------------|
| Document Operations | `document_visibility_governance` + linkage state |
| Issues page / KPIs | `maintenance_issues.status` + `open_only` filter |
| Issue drawer / CTA | `operational_cognition_service` + `issueLifecycleAuthority` |
| Today | `unified_tasks_service` (open issues only; stale suppression unchanged) |
| Dashboard open count | `count_open_issues` (OPEN_ISSUE_STATUSES) |
| Command Centre | Same open issue count + gap aggregates |
| Risk Signals | Independent lifecycle; issue auto-resolve does not delete signals |

## Does not alter

- RAOD requirement authority
- PAA lifecycle presentation
- Today presentation authority (banner/KPI semantics)
- Compliance risk scoring rules
