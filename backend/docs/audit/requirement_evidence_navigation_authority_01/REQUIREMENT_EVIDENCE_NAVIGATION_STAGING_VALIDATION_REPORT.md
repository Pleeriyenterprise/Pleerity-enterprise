# REQUIREMENT-EVIDENCE-NAVIGATION — Staging Validation

**Programme:** REQUIREMENT-EVIDENCE-NAVIGATION-AUTHORITY-IMPLEMENTATION-01-STAGING-VALIDATION  
**Run:** 20260701T114948Z  
**Commit:** `028547b4`  
**Verdict:** `STAGING_VALIDATION_GO`

## Deploy

| Layer | URL / artifact | Status |
|-------|----------------|--------|
| Backend (Render) | `https://pleerity-enterprise.onrender.com/api` | SHA `028547b487b4…` |
| Frontend (Vercel preview) | `https://pleerity-enterprise-ez8hxwvys-victory-aigbochies-projects.vercel.app` | `main.43ce3d9b.js` |
| Staging alias | `https://pleerity-enterprise-9jjg.vercel.app` | Aliased to preview deployment |

Bundle markers: `view_settled_evidence`, `review_uploaded_document`, `tab=evidence`, `focus=upload`, build SHA `028547b4`.

## Acceptance checks

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Verified linked document → Evidence Registry (not Document Operations) | **PASS** | Gas Safety (`c5abaeba…`): cognition URL `/properties/…?tab=evidence&requirement_id=…`; stale `take_action` still `/documents` — frontend resolver rewrites at click |
| 2 | Missing evidence → Upload / Document Operations route | **PASS** | EICR + EPC on OPS property: `take_action` → `/documents?…` |
| 3 | Pending review → Document Operations queue | **PASS** | HMO licence (`71e89158…`): `take_action` → `/documents?…` |
| 4 | Structured declaration → inspect / view submission | **PASS** | Legionella (`537da91b…`): cognition → registry + `open=intel&focus=submission` |
| 5 | Surface parity (shared route authority) | **PASS** | Bundle contains canonical resolver intents; `executeRequirementPrimaryCta` path via `view_settled_evidence` + `focus=upload` |
| 6 | No empty queue after View evidence on satisfied requirements | **PASS** | Verified linked cognition no longer targets `/documents`; registry deep link confirmed |

## Local regression

37 tests passed across:

- `resolveEvidenceNavigationTarget.test.js`
- `authoritativeEvidenceView.test.js`
- `documentEvidenceAuthority.test.js`
- `requirementCtaParity.test.js`

## OPS pilot samples (client `6fd5ac4c`, property `d35a58ae`)

- **Verified + linked document:** `gas_safety` → registry URL (backend cognition aligned)
- **Missing:** `eicr`, `epc` → `/documents` take_action routes
- **Pending review:** `hmo_license` → `/documents` take_action route
- **Structured verified:** `legionella` → intel submission inspect URL

## Notes

- API `take_action.primary.route` may still emit legacy `/documents` for verified rows; **presentation resolver** on the client is the governed navigation authority and overrides at CTA execution.
- No production or `main` changes in this programme.
