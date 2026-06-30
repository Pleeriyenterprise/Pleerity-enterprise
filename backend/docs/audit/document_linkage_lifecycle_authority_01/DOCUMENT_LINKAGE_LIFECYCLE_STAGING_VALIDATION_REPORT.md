# DOCUMENT-LINKAGE-LIFECYCLE-AUTHORITY-01 — Staging Validation

- **Validated at:** 2026-06-30T21:00:09Z (marker `DLLA-STAGING-20260630T205847Z`)
- **Commit:** `ca6bc7963d2202d1baa79613bbccba73ad57b44c`
- **Branch:** `develop` only — production not touched, main not merged
- **Cohort:** OPS pilot landlord `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / property `d35a58ae-3c81-491c-9694-1d021dd3b8ad`
- **Verdict:** **GO** — all 11 staging checks passed

## Deploy

| Surface | Target | SHA / bundle |
|---------|--------|--------------|
| Backend (Render staging) | `https://pleerity-enterprise.onrender.com/api` | `ca6bc796` |
| Frontend (Vercel alias) | `https://pleerity-enterprise-9jjg.vercel.app` | `main.e25946bd.js` |

Frontend bundle markers: `View linked evidence` present, `open_only` Issues filter present.

## Scenario

1. Impersonated OPS pilot landlord with pre-existing open bridge issue `0e01e3fb-ecf8-46f7-a980-97e7eaf69a6c` (MISMATCHED_EVIDENCE / “could not confidently match” copy).
2. Uploaded supporting legionella fixture (`2c2a2c75-b366-4e8c-b31f-f2867c8238c3`) with `NO_REQUIREMENT_LINK`.
3. Confirmed issue visible in Open Issues (176 open) with CTA **Review uploaded document**.
4. `POST /documents/{id}/reconcile-linkage` with `link_requirement` → requirement `62589167-4e34-4aef-ad75-4967383e71bc`.
5. Reconcile response returned `resolved_issue_ids: ["0e01e3fb-ecf8-46f7-a980-97e7eaf69a6c"]` and `document_linkage_state: LINKED`.

## Checks (11/11 PASS)

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 1 | Staging landlord with open bridge linkage issues | PASS | Issue `0e01e3fb` status `triaged`, `compliance_gap:MISMATCHED_EVIDENCE` |
| 2 | Issue in Open Issues before linkage | PASS | Present in `open_only=true` list; open count 176 |
| 3 | Link document to correct requirement | PASS | Reconcile HTTP 200 |
| 4 | `document_linkage_state` → LINKED | PASS | Reconcile payload `document.document_linkage_state: LINKED` |
| 5 | Related issue → resolved | PASS | Status `resolved`, `auto_resolved: true` |
| 6 | Open Issues count drops | PASS | 176 → 175 |
| 7 | Issue absent from active Open Issues | PASS | Not in `open_only=true` list |
| 8 | Resolved issue historically visible | PASS | Retrievable via `GET /maintenance/issues/{id}` and full list |
| 9 | CTA → View linked evidence | PASS | Before: Review uploaded document; after: View linked evidence |
| 10 | Document Operations Need Attention empty for linked doc | PASS | Linked doc `document_attention_required: false`; not in attention queue |
| 11 | Today / Command Centre / risk — no stale linkage work | PASS | No document/linkage tasks in Today; CC actions 0; risk linkage signals 0 |

## Notes

- Property-level attention queue still shows 3 legacy probe documents (expired / extraction-failed); these are unrelated to the validated linkage issue and do not block GO — check 10 scopes to the reconciled document only, matching product intent (linked supporting evidence clears linkage attention for that file).
- `operational_cognition_service.py` CTA enrichment was not in the scoped commit; resolved CTA **View linked evidence** is delivered via `resolution_linked_*` fields + `primaryActionResolver` / `issueLifecycleAuthority` on the frontend.

## Artefacts

- Machine evidence: `DOCUMENT_LINKAGE_LIFECYCLE_STAGING_VALIDATION.json`
- Pre-staging authority audit: `DOCUMENT_LINKAGE_LIFECYCLE_AUTHORITY_REPORT.md`
