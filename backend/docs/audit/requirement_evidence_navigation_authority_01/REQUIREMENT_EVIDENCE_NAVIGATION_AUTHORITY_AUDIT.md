# REQUIREMENT-EVIDENCE-NAVIGATION-AUTHORITY-01 — Audit Report

**Programme:** REQUIREMENT-EVIDENCE-NAVIGATION-AUTHORITY-01  
**Branch:** `develop` (audit only — no implementation)  
**Date:** 2026-07-01  
**Verdict:** **D — Navigation should be lifecycle-aware** (with **C** — current verified document-primary behaviour violates governed destination)

## Executive summary

Governance clearly separates **Document Operations** (attention / linkage / review queue) from **Property Evidence Registry** (settled evidence). The observed defect — **Verified + 1 document → View evidence → empty Document Operations queue** — is not intentional empty-state design. It arises from **authority drift** between:

1. Presentation governance (`workspaceOrientationCopy`, `documentEvidenceAuthority`) — settled evidence belongs in Evidence Registry.
2. Backend + `authoritativeEvidenceView` — document-primary verified evidence routes to `/documents?...`.
3. `executeRequirementPrimaryCta` — prefers `resolveAuthoritativeEvidenceViewPath` **before** `resolveSettledEvidenceNavigationTarget`, so linked verified documents never reach the registry rewrite.

The landlord expectation (see observed behaviour on Gas Safety / EICR / EPC satisfied cards) matches **governed intent**, not current routing for document-primary verified requirements.

---

## Required questions — answers

### 1. What does "View evidence" mean according to governance?

**Governed meaning:** Show the authoritative evidence that satisfies or supports the requirement — document, structured submission, or declaration — in a **read/context surface**, not an upload or empty operator queue.

Sources:
- `workspaceOrientationCopy.js` — Document operations queue is for items needing review/linkage/expiry action; **settled evidence lives in each property's Evidence Registry**.
- `documentEvidenceAuthority.js` module header — operations queue is review/linkage/action only; settled evidence lives in Property → Documents (registry).
- `document_operational_visibility_verify` — default queue surfaces **ATTENTION_REQUIRED** only; registry sections render settled evidence.

### 2. Intended destination?

| Evidence model | Governed destination |
|----------------|---------------------|
| Linked verified document | **Property Evidence Registry** (requirement-scoped row / preview) |
| Structured declaration / CER | **Intel modal inspect panel** or registry deep link `?open=intel&focus=submission` |
| Self-certified / assessment record | Same as CER (record-primary) |
| Pending review document | **Document Operations** (attention queue) or review workflow |
| Missing evidence | **Upload** path (`/documents` with upload intent, or guided resolve) |
| Needs linkage | **Document Operations** reconciliation |

**Not** governed as primary "View evidence" destination: empty operations queue for verified settled documents.

### 3. Is Document Operations an operator workspace?

**Yes.** Upload intake, attention queue (default `ATTENTION_REQUIRED`), linkage reconciliation, expiry confirmation. Copy explicitly states settled evidence is elsewhere.

### 4. Is Evidence Registry a landlord/auditor workspace?

**Yes.** Per-property tab (`/properties/{id}?tab=evidence`) with sections: active evidence, pending review, expiring soon, historical. Read-oriented with preview/download; links back to Document Operations only when attention is required.

### 5. Should a satisfied requirement navigate into an empty operator queue?

**No.** When `document_client_visibility_state` is `ACTIVE_EVIDENCE` and requirement is `VERIFIED`, the document is **excluded** from the default attention filter (`filterDocumentsForQueueView` → `documentAttentionRequired`). Deep-linking to `/documents` with `requirement_id` pre-fills upload form but does **not** surface the settled file in the queue — producing the observed empty state.

### 6. Is there an Evidence Registry capable of displaying linked evidence?

**Yes.** `PropertyEvidenceRegistrySections.jsx` + `groupDocumentsForPropertyRegistry` render linked documents by visibility section. Deep link: `resolvePropertyEvidenceRegistryPath(propertyId, requirementId)`.

### 7. "View evidence" by satisfaction model

| Model | Governed open target |
|-------|---------------------|
| Uploaded certificate (verified) | Property Evidence Registry (+ optional doc preview) |
| Structured declaration (verified CER) | Intel inspect panel / registry + `open=intel&focus=submission` |
| Self-certified record | Intel inspect / submission view |
| Manual evidence on file | Registry or intel by record type |
| Linked document (verified) | Registry row for that requirement |

### 8. Source of truth for linked evidence

**Backend:** `evidence_authority` on requirement row (`effective_verified_document_id`, `primary_evidence_record_id`, `state`, `state_reason`). Document visibility from `document_visibility_governance` / `document_client_visibility_state`.

**APIs:** `GET /api/client/requirements` (enriched rows), property evidence endpoints on Property Detail tab.

### 9. Does Requirement Authority expose linked evidence identifier?

**Yes.** `evidence_authority.effective_verified_document_id`, `document_id`, `evidence_doc_id`, `primary_evidence_record_id`. Requirement row also exposes `take_action.primary.route` (often `/documents?...`).

### 10. Does Document Linkage Authority define canonical destination?

**Partially.** `DOCUMENT_LINKAGE_LIFECYCLE_AUTHORITY.md` defines Document Operations for linkage/reconciliation attention. It does **not** define "View evidence" CTA routing; it reinforces that linkage problems surface in the operations queue, not that verified linked docs should be viewed there.

### 11–12. Lifecycle-aware navigation (governed target state)

| Lifecycle | CTA label (examples) | Governed destination |
|-----------|---------------------|----------------------|
| Missing / ACTION_REQUIRED | Upload document / Record | Upload or guided resolve |
| Needs linkage | Review / reconcile | Document Operations |
| Pending review | Review evidence / Awaiting review | Document Operations or review drawer |
| Satisfied unverified (declaration) | View submission | Intel inspect |
| **Verified (document-primary)** | **View evidence** | **Evidence Registry** |
| **Verified (record-primary)** | **View evidence** | **Intel inspect / registry** |
| Expiring soon (verified) | Renew / upload replacement | Upload or registry with expiry context |

### 13. CTAs that violate lifecycle governance today

| Surface | Violation |
|---------|-----------|
| Requirements primary CTA | Verified + linked doc → `/documents` (empty queue) via `authPath` precedence |
| Backend `operational_cognition_service._verified_view_primary_action` | Emits `/documents` when `doc_id` present |
| Backend `requirement_action_resolver` | Default `doc_route` for document-class requirements |
| `authoritativeEvidenceView.resolveAuthoritativeEvidenceViewPath` | Document-primary explicitly returns `/documents` (test-locked) |
| RequirementIntelligenceModal `viewAuthoritativeEvidence` | Uses same path → navigates away to empty queue |
| Property Evidence Registry row "Open in Document Operations" | Correct for attention docs; misleading if used for settled-only view |

**Aligned surfaces:**
- `resolveSettledEvidenceNavigationTarget` (when reached)
- `requirementCtaParity` test without `document_id` → registry
- Compliance Score driver fallback tier B → registry
- Modal inspect for record-primary CER (`shouldViewEvidenceInModalInspectPanel`)

### 14. Same wording, different destinations?

**Yes — "View evidence"** is used for:
- `/documents?...` (operations / upload context)
- `/properties/...?tab=evidence&requirement_id=...` (registry)
- In-modal scroll (intel inspect)
- Guided evidence flows (legacy)

Lifecycle presentation rewrites labels (`requirementLifecyclePresentation.js`) but does not unify routes.

### 15. Duplicate navigation paths that drifted?

| Layer | Module | Behaviour |
|-------|--------|-----------|
| Backend resolver | `requirement_action_resolver.py` | `doc_route` → `/documents` |
| Backend cognition | `operational_cognition_service.py` | Verified view → `/documents` if doc_id |
| Frontend authoritative | `authoritativeEvidenceView.js` | Document-primary → `/documents` |
| Frontend settled rewrite | `documentEvidenceAuthority.js` | View settled → registry |
| Frontend execution | `requirementCtaParity.js` | `authPath \|\| settledTarget \|\| route` (**authPath wins**) |
| Modal | `RequirementIntelligenceModal.js` | `settledEvidencePath \|\| route` (better ordering in primaryHandler) |

POST-SUBMISSION-EVIDENCE-UX-FIX-P0 documented document-primary → `/documents` as intentional for that programme; it **conflicts** with later Document Operational Visibility governance.

---

## Root cause (observed defect)

```
Requirements card: VERIFIED + effective_verified_document_id + "View evidence"
  → applyLifecycleAwareCtaPresentation → label "View evidence"
  → executeRequirementPrimaryCta
  → resolveAuthoritativeEvidenceViewPath → /documents?property_id&requirement_id
  → navigate(authPath)  // settledTarget never evaluated
  → DocumentsPage default queueView = attention
  → verified doc has ACTIVE_EVIDENCE (not ATTENTION_REQUIRED)
  → queue empty + upload panel
```

---

## Navigation authority chain (as designed)

```
Requirement Authority (row + evidence_authority)
  → requirement_action_resolver.take_action.primary.route
  → operational_cognition_service (display envelope)
  → Frontend: resolveRequirementAction → applyLifecycleAwareCtaPresentation
  → executeRequirementPrimaryCta / RequirementIntelligenceModal
  → [CONFLICT] authoritativeEvidenceView vs documentEvidenceAuthority settled rewrite
```

**Canonical presentation modules (intended):**
- `documentEvidenceAuthority.js` — settled vs operations split
- `authoritativeEvidenceView.js` — record vs document primary
- `requirementCtaParity.js` — cross-surface execution

---

## Evidence Registry analysis

- **Exists:** Property Detail → Documents tab → Evidence Registry sections.
- **Deep link:** `?tab=evidence&requirement_id={rid}` (+ optional `open=intel&focus=submission`).
- **Shows:** Settled documents grouped by visibility; preview/download; requirement linkage label.
- **Gap:** Requirements "View evidence" does not consistently route here for document-primary verified rows.

## Document Operations analysis

- **Purpose:** Portfolio-wide operator queue; default **Needs action** filter.
- **Empty state copy:** Correctly directs users to Evidence Registry — proving product knows queue is wrong destination for settled view.
- **Deep link behaviour:** `property_id` + `requirement_id` query params pre-select upload target; do not inject settled docs into attention list.

---

## Cross-platform CTA matrix (summary)

| Surface | View evidence / equivalent | Typical route today | Governed? |
|---------|---------------------------|---------------------|-----------|
| Requirements list | View evidence (primary) | `/documents` if linked doc | **No** |
| Property Detail compliance | executeRequirementPrimaryCta | Same conflict | **No** |
| Requirement Intel modal | View evidence footer | authPath → `/documents` or in-modal | Partial |
| Compliance Score drivers | Open requirement (tier B) | Registry | **Yes** |
| Today | Review evidence (tasks) | Task-specific URL | Operational (separate) |
| Command Centre | Triage CTAs | Mixed | Operational |
| Dashboard score recs | Fix now | Entity route upload | N/A |
| Documents registry rows | Preview / Open in ops | Registry / ops | **Yes** |
| Reports / Digest | Humanized text links | Report-layer | Audit view |

---

## Recommended global implementation (audit recommendation only — not implemented)

1. **Single navigation authority function** consumed by all surfaces: `resolveEvidenceNavigationTarget(requirement, ctaIntent, lifecycle)` — no per-page route inference.
2. **Lifecycle matrix** as specified in programme brief (missing → upload; linkage → ops; pending → review; verified document → registry; verified record → intel inspect).
3. **Fix precedence:** For `view_evidence` intent, prefer registry/inspect over raw `/documents` when lifecycle is VERIFIED and visibility is ACTIVE_EVIDENCE.
4. **Align backend** `take_action` routes or document `primary.intent` so API contract matches presentation (e.g. `intent: view_settled_evidence`).
5. **Reconcile tests:** `authoritativeEvidenceView.test.js` document-primary case vs `documentEvidenceAuthority.test.js` / `requirementCtaParity.test.js` — currently contradictory.
6. **Copy audit:** Reserve "View evidence" for read surfaces; use "Upload document", "Review in queue", "Reconcile linkage" for operations.

---

## Production impact

- **Observed on production-capable builds:** Yes — routing logic is in shared frontend modules and backend resolver; not environment-specific.
- **Data authority:** Unchanged — defect is navigation/presentation only.
- **Risk:** High landlord confusion; support burden; perceived platform bug for satisfied portfolios.

## Risk assessment

| Risk | Level | Note |
|------|-------|------|
| Landlord trust / comprehension | High | Label promises evidence; queue is empty |
| Authority drift regression | Medium | Multiple modules can override each other |
| Jurisdiction / requirement-type scale | High | Affects all document-primary certificates (Gas, EICR, EPC, etc.) |
| Structured declaration paths | Lower | P0 fix improved intel inspect path |

---

## Acceptance verdict

**D (+ C):** Navigation should be lifecycle-aware. Current verified document-primary "View evidence" **violates** governed destination (Evidence Registry) and lands users in an empty operator workspace. Document Operations is **not** the governed destination for viewing settled verified evidence.

**Not A:** Empty queue is not intentional success state for this CTA.  
**Partially B:** Wording "View evidence" is misleading when destination is operations upload context — but root issue is routing, not label alone.

---

## Affected files (reference — no changes made)

**Frontend:** `requirementCtaParity.js`, `authoritativeEvidenceView.js`, `documentEvidenceAuthority.js`, `RequirementIntelligenceModal.js`, `RequirementsPage.js`, `PropertyDetailPage.js`, `DocumentsPage.js`, `workspaceOrientationCopy.js`

**Backend:** `requirement_action_resolver.py`, `operational_cognition_service.py`, `document_visibility_governance` (consumer)

**Governance:** `DOCUMENT_LINKAGE_LIFECYCLE_AUTHORITY.md`, `COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`, `post_submission_evidence_ux_audit_01/FIX_P0.md`, `document_operational_visibility_verify/REPORT.md`
