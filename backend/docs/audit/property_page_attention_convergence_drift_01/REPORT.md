# PROPERTY-PAGE-ATTENTION-CONVERGENCE-DRIFT-01

**Classification:** `VERIFIED_OPERATIONALLY`

## Summary

Property page Operating, Compliance, and Documents surfaces now share convergence truth from the compliance-detail matrix. Satisfied self-recorded rows and document-linked platform-review rows no longer inflate missing-document counts or show stale Upload CTAs.

## Root cause

The compliance-detail matrix omitted `requirement_satisfied`, `missing_required_document`, and `requirement_attention_eligible`, forcing legacy PENDING/no-doc heuristics on the property page.

## Fix

- Matrix passthrough of convergence fields + linked `document_id` as `evidence_doc_id`
- `buildNeedsAttentionSubset` uses `isRequirementActionRequired` when convergence fields present
- Platform review / escalation CTA: **Review pending** / **Awaiting platform review**

## Tests

Frontend: `pass` | Backend: `pass`

## Watchlist

See `watchlist.md`.
