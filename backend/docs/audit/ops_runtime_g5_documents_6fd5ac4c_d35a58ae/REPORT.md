# G5 Documents — 6fd5ac4c_d35a58ae

**Run:** `20260524T190110Z`  
**Classification:** `OPERATIONAL_ORPHAN_STATE`  
**Pilot:** client `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / property `d35a58ae-3c81-491c-9694-1d021dd3b8ad`

## Summary

Documents surface boot, document truth authority, review honesty, cross-surface coherence, resolution walks, G9 integrity, and real browser upload mutation **passed**. Document↔requirement linkage **failed** due to orphan and drift rows on pilot property data.

## Checkpoint results

| Checkpoint | Result |
|------------|--------|
| Boot | True |
| Document truth | True |
| Linkage | False |
| Mutation | True |
| Resolution walks | True |
| Cross-surface | True |
| Review honesty | True |
| G9 | True |
| G10 | False (linkage authority) |
| Convergence | True (75s, stable UPLOADED/EXTRACTION_FAILED) |

## Linkage failures

| Kind | IDs |
|------|-----|
| Orphan (no `requirement_id`, PROPERTY scope) | `f3ad6a0e-…`, `67f88f49-…`, `76552abb-…` |
| Drift (requirement not in runtime set) | doc `65cfb0b0-…` → req `d2066cd2-bcbd-4b7c-8e98-95412a5ccdd6` |

## Mutation

- Target: `hmo_license` (`71e89158-5de0-422a-970c-5a2163fcc823`), document type `Other`
- Upload: browser POST `/documents/upload` → 200, doc `be01b673-c810-48c7-87fc-871cac5161ec`
- Post-upload: `UPLOADED` / `EXTRACTION_FAILED` (upload ≠ verified)

## Remediation before G6

1. Link or retire 3 orphan PROPERTY-scoped documents.
2. Reconcile doc `65cfb0b0-…` with superseded/archived requirement `d2066cd2-…` or re-link to active requirement row.
