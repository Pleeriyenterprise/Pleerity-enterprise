# Document Status Service – Gap Analysis

## Goal (task)
Deterministic document status computation + scoring inputs. Enterprise-safe, no legal verdict. Pick single evidence doc per requirement type; compute status from doc; map to score fraction.

## Current state
- **compliance_scoring.py:** Uses requirements (status, due_date) + documents grouped by requirement_id. Picks “best” requirement per catalog key by status_factor(requirement.status, days_to_expiry, has_doc, needs_review). Status factor: Valid 1.0, Expiring 0.7, Overdue 0.25, Missing 0.0, Needs review 0.5. No document-level filtering (deleted/quarantined/malware); no single “pick evidence doc” by expiry/uploaded_at.
- **Documents:** Have requirement_id, status (DocumentStatus), uploaded_at, ai_extraction (data.document_type, expiry_date, confidence_scores.overall). Optional: expiry_date at top level after apply; confidence_score at top level. No deleted/quarantined/malware_flagged in core model (optional DB fields).
- **Candidate docs:** Currently “all docs for property” then grouped by requirement_id; no filter by document_type at query time; no “furthest future expiry” rule.

## Task vs current
| Aspect | Current | Task |
|--------|--------|------|
| Evidence selection | Best requirement row (by status_factor); docs only for “has_doc” / needs_review | pick_evidence_document(docs, document_type): exclude deleted/quarantined/malware/DISABLED; then furthest future expiry, else newest uploaded_at, else updated_at, _id |
| Status source | Requirement status + due_date + doc presence | compute_requirement_status(today, doc, expects_expiry, expiring_soon_days): from doc only (expiry_date, verification_status, confidence) |
| Fractions | Valid 1.0, Expiring 0.7, Overdue 0.25, Missing 0.0, Needs review 0.5 | VALID=1.0, EXPIRING_SOON=0.8, NEEDS_REVIEW=0.5, EXPIRED=0.1, MISSING_EVIDENCE=0.0 |

## Conflicts and choice
- **Expired fraction:** Current 0.25, task 0.1. **Choice:** Use task (0.1) when using document-status path.
- **Expiring soon fraction:** Current 0.7, task 0.8. **Choice:** Use task (0.8).
- **Candidate docs by type:** DB has no document_type index; docs linked via requirement_id. **Choice:** Derive candidates per requirement_key by requirement_id in (requirements that map to that key). Pass those docs to pick_evidence_document; document_type used for optional filter if doc has type stored (e.g. ai_extraction.data.document_type).
- **expects_expiry:** Task: “If expects_expiry and doc.expiry_date missing -> NEEDS_REVIEW”. **Choice:** True for GAS_SAFETY_CERT, EICR_CERT, EPC_CERT, PROPERTY_LICENCE; false for tenancy/deposit event-based.

## Implementation
- New **document_status_service.py**: pick_evidence_document, compute_requirement_status; config EXPIRING_SOON_DAYS (env default 60), CONFIDENCE_THRESHOLD (env optional).
- **compliance_scoring.py**: After applicable requirements, for each key get document_type, get candidate docs (by requirement_id mapping to key), pick evidence doc, compute_requirement_status, map status to fraction; keep weights renormalized over applicable only. Coexist with existing requirement-based path: use document-status result when we have a picked doc or explicit MISSING_EVIDENCE; fallback to current status_factor only when not using document-status (or we fully replace – task says “map status to fraction … renormalize” so we use new fractions as primary).
