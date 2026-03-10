# Compliance Tab – Task vs Codebase Audit

**Task:** Implement the Compliance tab for the Property Detail page as an enterprise-grade property compliance workspace.

**Audit purpose:** Identify what is implemented, what is missing, how it was implemented, and any conflicting instructions with a recommended safest option. **No implementation in this document** – audit only.

**References:** [Property Command Centre audit](PROPERTY_COMMAND_CENTRE_TASK_AUDIT.md) (Compliance mentioned in §4–5); existing Compliance tab and compliance-detail API.

---

## 1. TAB PURPOSE (Task §1)

**Task:** Property-level control room combining obligation list, statuses, due dates, evidence linkage, urgency, action buttons, impact indicators. “Practical working side of the property’s compliance score.”

**Current state:**
- **Implemented:** Obligation list (matrix from compliance-detail or requirements fallback), statuses (via evidenceStatus), due dates and days left, evidence linkage (evidence_doc_id → View document / Upload), actions (View document, Upload, Mark not applicable, Request help). Score and risk shown in a summary row.
- **Missing:** Urgency aggregation in one place, impact indicators per obligation, “control room” layout (summary cards, filters, urgent panel).

**Gap:** Tab is functional but not yet structured as the task’s “compliance operations console”; add summary cards, filters, impact column, and urgent panel.

---

## 2. TAB STRUCTURE (Task §2)

**Task order:** A) Compliance Summary Row → B) Requirement Status Filters → C) Obligation Table / Cards → D) Urgent Items Panel → E) Compliance Notes / Guidance strip (optional).

**Current structure:**
- **A) Summary row:** Single row with score, risk level, risk index, last updated; optional score-delta + “View change history”. Not the task’s card-based summary (Total applicable, Valid, Expiring Soon, Overdue, Missing, Next due).
- **B) Filters:** None.
- **C) Table:** Single “Requirements” table; no cards on mobile.
- **D) Urgent panel:** None on Compliance tab (Overview has overdue/expiring links that go to Compliance).
- **E) Notes strip:** None.

**Gap:** Restructure into the five sections; add summary cards, filter row, optional notes strip; add urgent panel and mobile cards.

---

## 3. COMPLIANCE SUMMARY ROW (Task §3)

**Task:** Summary cards: Total applicable obligations, Valid, Expiring Soon, Overdue, Missing Evidence, Next due date. Deep-link or apply filters where practical.

**Current:** One row: “Evidence readiness score: X/100”, “Risk level: …”, “Risk index: …”, “Last updated: …”, and optionally score delta + “View change history”. No count cards for Valid / Expiring Soon / Overdue / Missing, no “Next due” date in this row.

**Backend:** `GET /api/portfolio/properties/{property_id}/compliance-detail` returns `matrix`, `kpis` (overdue, expiring_30, missing, compliant), `property_score`, `risk_level`, `last_updated_at`. So **totalApplicable** = matrix.length, **valid** = kpis.compliant, **expiringSoon** = kpis.expiring_30, **overdue** = kpis.overdue, **missingEvidence** = kpis.missing. **nextDueDate** can be derived client-side from matrix (e.g. earliest future due_date among non-COMPLIANT, or earliest of all).

**Gap:** Add a summary row of cards (or compact stat row) with these six items; make cards clickable to set filter (e.g. click “Overdue” → filter = Overdue). No new endpoint required if frontend derives from existing `complianceDetail.matrix` and `complianceDetail.kpis`.

---

## 4. REQUIREMENT STATUS FILTERS (Task §4)

**Task:** Filter row: All, Valid, Expiring Soon, Overdue, Missing Evidence, Unlinked Evidence, Not Applicable (if supported). Optional: search by obligation name, sort by due date / urgency / score impact.

**Current:** No filters; all requirements shown.

**Backend:** Matrix rows have `status` (COMPLIANT, EXPIRING_SOON, OVERDUE, PENDING, MISSING, etc.) and optionally applicability (NOT_REQUIRED excluded from catalog matrix). “Unlinked Evidence” = documents with no requirement_id – would need evidence data or a flag; can be a later enhancement. “Not Applicable” = requirements with applicability NOT_REQUIRED are already excluded from matrix in catalog_compliance; if the task means “show and filter by N/A”, that would require including them in matrix with a status or flag.

**Gap:** Add filter state (e.g. statusFilter: '' | 'VALID' | 'EXPIRING_SOON' | 'OVERDUE' | 'MISSING' | 'NOT_APPLICABLE'); filter matrix (or requirements) client-side. Optional: search input (filter by title/requirement_code), sort dropdown (due date, urgency, impact). **Safest:** Implement All + Valid + Expiring Soon + Overdue + Missing Evidence from existing status; add Unlinked Evidence and Not Applicable only if product agrees (may need API or data changes).

---

## 5. OBLIGATION TABLE / CARD LIST (Task §5)

**Task:** Table (desktop) / cards (mobile). Columns: Obligation name, Category/type, Status, Due/expiry, Evidence linked (count, latest name, confirmation status), Score impact (High/Medium/Low), Action. Status values: Valid, Expiring Soon, Overdue, Missing Evidence, Needs Confirmation, Not Applicable. Action by state: Missing → Upload; Needs Confirmation → Confirm Details; Expiring/Overdue → View Evidence, Update Dates, Replace; Valid → View Details.

**Current:**
- **Columns:** Requirement (title), Evidence status (chip), Expiry date, Days left, Action. **Missing:** Category/type, Evidence (count + latest name + confirmation), Score impact.
- **Status:** Uses getEvidenceStatus (VALID, COMPLIANT, EXPIRING_SOON, OVERDUE, MISSING, PENDING, PENDING_VERIFICATION). Task’s “Needs Confirmation” maps to PENDING_VERIFICATION or to “has extraction not yet applied” (evidence side); can align label.
- **Evidence column:** Only shows status chip; no document count, latest evidence name, or confirmation status. Backend matrix has `evidence_doc_id` only; evidence count/latest name/confirmation would need either joining with documents in a new endpoint or loading evidence for property and matching client-side.
- **Impact:** Matrix has `criticality` (HIGH, MED). Can map to “High” / “Medium” / “Low” badge. Not currently shown.
- **Actions:** Current: View document or Upload, Mark not applicable, Request help. Task: state-based (Missing → Upload; Needs Confirmation → Confirm Details; Expiring/Overdue → View Evidence, Update Dates, Replace; Valid → View Details). “Update Dates” / “Replace” can link to Documents page with requirement_id; “Confirm Details” can link to Evidence tab or Documents.
- **Mobile:** Single table only; no stacked cards.

**Gap:** Add Category/type column (requirement_code or title category). Add Evidence column (at least “Linked”/“—” and optional count/latest name when data available). Add Impact column (High/Medium/Low from criticality). Extend actions by status (Confirm Details when applicable; Replace/Update Dates as links to documents). Add responsive cards for small screens.

---

## 6. URGENT ITEMS PANEL (Task §6)

**Task:** Panel listing overdue, expiring within 30 days, missing critical evidence. Each row: title, short explanation, due/overdue info, CTA. Examples: “Gas Safety overdue by 12 days → Upload or replace evidence”.

**Current:** No dedicated panel on Compliance tab. Overview tab shows overdue/expiring items and “fix in Compliance” / “review in Compliance” links.

**Gap:** Add “Urgent Items” panel/section on Compliance tab: derive from matrix (status OVERDUE, EXPIRING_SOON, MISSING/PENDING); show title, days overdue or days to expiry, and CTA (Upload evidence, View evidence, Replace document). Reuse existing navigation to Documents/Evidence.

---

## 7. REQUIREMENT DETAIL EXPANSION / DRAWER (Task §7)

**Task:** On row click, expandable panel or drawer with: full description, status explanation, due date/recurrence, evidence linked, last updated, score impact, linked asset (if relevant), timeline/history, action buttons.

**Current:** No expand/drawer; only table row and action buttons.

**Backend:** Matrix row has title, status, expiry_date, days_to_expiry, evidence_doc_id, requirement_id, criticality, weight. No full description, recurrence, last_updated_at per requirement, or linked_asset_id in current matrix. Requirements collection may have more fields (e.g. description, updated_at); catalog has title/code. Timeline/history for a requirement would come from score ledger or timeline filtered by requirement_id.

**Gap:** Add expandable row or drawer. Populate from matrix + optional GET requirement detail or reuse compliance-detail. Show description (from catalog or requirement), status, due date, evidence (link to Evidence tab), “Last updated” if available from requirement. **Placeholder:** Linked asset and “recurrence” can be “—” until assets/recurrence are available. Timeline: link to “View in Timeline” with filter by requirement or use existing timeline API filtered by entity.

---

## 8. BACKEND EXPECTATIONS (Task §8)

**Task suggests:** `GET /api/properties/:propertyId/compliance` with summary (totalApplicable, valid, expiringSoon, overdue, missingEvidence, nextDueDate) and obligations (id, name, category, status, dueDate, evidenceCount, latestEvidenceLabel, confirmationStatus, scoreImpact, linkedAssetId, lastUpdatedAt).

**Current:** No `GET /properties/:id/compliance`. **Existing:** `GET /api/portfolio/properties/{property_id}/compliance-detail` returns:
- **matrix[]:** requirement_code, title, status, numeric_score, criticality, weight, expiry_date, days_to_expiry, evidence_doc_id, requirement_id.
- **property_score,** **risk_level,** **risk_index,** **kpis** (overdue, expiring_30, missing, compliant), **last_updated_at,** **score_delta,** **score_change_summary.**

So we have status, due/expiry, criticality (→ score impact), evidence_doc_id. We do **not** have per-row: evidenceCount, latestEvidenceLabel, confirmationStatus, linkedAssetId, lastUpdatedAt. These can be added later or derived (e.g. by joining with documents in a new endpoint).

**Conflict / recommendation:**
- **New endpoint vs existing:** Task suggests a dedicated “compliance” endpoint. **Safest:** Keep using **GET /portfolio/properties/{property_id}/compliance-detail** as the single source. Frontend derives summary counts and nextDueDate from matrix + kpis. Optionally add **nextDueDate** and, if needed, **obligations[]** with evidenceCount/latestEvidenceLabel in the same endpoint (additive) so the tab has one place to load from. Do not duplicate scoring or matrix logic; keep it in catalog_compliance.
- **Naming:** Task uses “obligations”; codebase uses “matrix” / “requirements”. Keep **matrix** in API; UI can label as “Obligations” or “Requirements” consistently.

---

## 9. EVIDENCE + SCORE + ASSET LINKAGE (Task §9)

**Task:** Compliance tab must link to Evidence tab (uploads, replacements, confirmations), Timeline tab (requirement history), Assets tab (if obligation supports an asset). Visibly connect to score; when evidence is confirmed, status and score update accordingly. Reuse current engine; do not create new score logic.

**Current:**
- **Evidence:** Actions “View document” / “Upload” navigate to `/documents?property_id=...&requirement_id=...`. No explicit “Open Evidence tab” link from Compliance; Evidence tab is separate. Link exists implicitly via Documents page.
- **Timeline:** No link from Compliance tab to Timeline tab or requirement-level history.
- **Assets:** No link from Compliance to Assets; no linkedAssetId on requirements/matrix.
- **Score:** Score and risk are shown; score_delta and change history are available. Confirmation flow (apply-extraction) already updates requirement and score via existing engine.

**Gap:** Add explicit “View in Evidence tab” (or “View evidence”) that switches to Evidence tab. Add “View history” / “View in Timeline” that opens Timeline tab with filter (e.g. by requirement or COMPLIANCE category). Document “linked asset” as future when asset–requirement mapping exists. No change to score logic.

---

## 10. MISSING EVIDENCE / EMPTY STATES (Task §10)

**Task:** If property has obligations but no evidence: empty state “No evidence has been uploaded for this property yet.” + Upload Evidence, View Evidence Tab. If no obligations: “No compliance obligations are currently configured for this property.” + optionally “Review property setup”.

**Current:** Only one empty state: “No requirements returned for this property.” (when requirements.length === 0). No distinction between “no obligations configured” and “obligations exist but no evidence yet”. No CTA to Evidence tab.

**Gap:** When matrix.length === 0, show “No compliance obligations are currently configured for this property.” and optional “Review property setup” if applicable. When matrix.length > 0 but all have missing evidence (or a dedicated “no evidence at all” state), show “No evidence has been uploaded for this property yet.” with **Upload Evidence** and **View Evidence Tab** (setActiveTab(TAB_EVIDENCE)). Refine copy to match task.

---

## 11. FEATURE FLAG / PLAN BEHAVIOUR (Task §11)

**Task:** If compliance engine is disabled for the user’s plan, show locked state, explain what the tab provides, show upgrade CTA. Do not expose compliance data without entitlements.

**Current:** Compliance tab has **no feature flag**; it is always shown and always loads compliance-detail. Maintenance, Contractors, Risk Signals use hasFeature('...'); Compliance and Evidence do not.

**Gap:** If product defines a compliance feature flag (e.g. `compliance_workspace` or reuse existing plan behaviour): when disabled, show tab content as locked (same pattern as Maintenance/Contractors) with short explanation and upgrade CTA. Backend compliance-detail is not currently gated by a feature; if gating is added, ensure 403 or equivalent is handled and UI shows locked state. **Safest:** Add feature check only if product explicitly requires it; otherwise keep Compliance tab always available and document that “compliance engine” is considered always-on for current plans.

---

## 12. COMPLIANCE-SAFE LANGUAGE (Task §12)

**Task:** Use “Status based on portal records”, “Informational indicator”, “Review required”, “Expiring soon”, “Overdue based on recorded dates”. Avoid “Legally compliant”, “Guaranteed compliant”, definitive legal conclusions.

**Current:** “Evidence readiness score”, “Risk level”, status chips “Valid”, “Expiring soon”, “Overdue”, “Missing evidence”. No “legally compliant” or “guaranteed” in the Compliance tab. Minor: “Evidence readiness score” is already safe.

**Gap:** Add a short disclaimer or footnote where appropriate (e.g. “Status based on portal records” under the summary or table). Keep existing wording; avoid adding any legal claims.

---

## 13. DESIGN / UX RULES (Task §13)

**Task:** Enterprise table/card layout, clear status chips, clear action buttons, compact but readable, mobile responsive, no flashy effects, calm serious tone.

**Current:** Table with status chips and buttons; layout is clean. No mobile cards; table may overflow on small screens.

**Gap:** Add responsive cards for mobile; ensure summary and filters are compact and readable. No design-system change required.

---

## 14. ACCEPTANCE CRITERIA (Task §14)

| Criterion | Status | Notes |
|-----------|--------|--------|
| Compliance tab shows summary, filters, obligations list, and urgent items | **Partial** | Summary row exists but not card-based; no filters; no urgent panel. |
| Each obligation is actionable | **Done** | View document / Upload, Mark not applicable. |
| Evidence linkage is visible | **Partial** | evidence_doc_id drives “View document” vs “Upload”; no count/latest name/confirmation in table. |
| Score impact visible in simplified form | **Missing** | criticality in API not shown; no High/Medium/Low badge. |
| Requirement details can be expanded | **Missing** | No drawer/expand. |
| Locked state if compliance disabled | **Missing** | No feature flag for Compliance tab. |
| No existing compliance or evidence flow broken | **Done** | Additive only. |

---

## 15. CONFLICTS AND RECOMMENDED OPTIONS

| Conflict | Recommendation |
|----------|-----------------|
| **New GET /properties/:id/compliance vs existing compliance-detail** | Keep **GET /portfolio/properties/{id}/compliance-detail** as source. Derive summary (counts, nextDueDate) and filters client-side. Optionally extend this endpoint with nextDueDate and per-row evidence summary (evidenceCount, latestEvidenceLabel) if needed for the tab. |
| **“Obligations” vs “Requirements” / “matrix”** | Keep API field names (matrix, requirements). UI can use “Obligations” or “Requirements” consistently; avoid renaming backend contracts. |
| **Unlinked Evidence / Not Applicable filters** | Implement core filters (All, Valid, Expiring Soon, Overdue, Missing) first. Add “Unlinked Evidence” and “Not Applicable” only if product needs them; may require API or data support. |
| **Compliance feature flag** | Implement locked state only if product defines a compliance feature key; otherwise leave tab always on and document. |

---

## 16. OUTPUT REQUIRED (Task “OUTPUT REQUIRED”)

### Files to change (when implementing)

- **Frontend:** `frontend/src/pages/PropertyDetailPage.js` – Compliance tab only:
  - **A)** Compliance summary row as cards/compact stats: total applicable, valid, expiring soon, overdue, missing, next due (from complianceDetail.matrix + kpis); deep-link to filters.
  - **B)** Requirement status filter row (All, Valid, Expiring Soon, Overdue, Missing); optional search/sort.
  - **C)** Obligation table: add Category/type column, Evidence column (linked/— or count+latest when available), Impact column (High/Medium/Low from criticality); state-based actions (Confirm Details, Replace, Update Dates, View Details where applicable); mobile cards.
  - **D)** Urgent Items panel: overdue + expiring soon + missing, with CTAs.
  - **E)** Optional compliance notes/guidance strip (e.g. “Status based on portal records”).
  - **F)** Requirement detail expansion/drawer: on row click show description, status, due date, evidence link, last updated, impact, link to Timeline; placeholder for linked asset/recurrence.
  - **G)** Empty states: no obligations vs no evidence yet; CTAs Upload Evidence, View Evidence Tab, Review property setup.
  - **H)** If feature flag exists: locked state with upgrade CTA when compliance disabled.
- **Backend (additive only):**
  - Optional: extend `GET /portfolio/properties/{property_id}/compliance-detail` with `next_due_date` (ISO) and, if needed, per-matrix-item `evidence_count`, `latest_evidence_label`, `confirmation_status` (by joining documents). No new route required for first version if frontend derives summary and next due from matrix.

### Endpoints

- **Reused:** `GET /api/portfolio/properties/{property_id}/compliance-detail` (matrix, kpis, score, risk, last_updated_at, score_delta, score_change_summary). Optional: `GET /client/properties/{property_id}/requirements` (fallback when no catalog).
- **Created (optional):** None for MVP; or extend compliance-detail response with next_due_date, and with obligations[] enriched with evidence summary if needed.

### Data fields added or reused

- **Already in compliance-detail:** matrix[].requirement_code, title, status, numeric_score, criticality, weight, expiry_date, days_to_expiry, evidence_doc_id, requirement_id; kpis (overdue, expiring_30, missing, compliant); property_score, risk_level, risk_index, last_updated_at, score_delta, score_change_summary.
- **Derived in UI:** totalApplicable = matrix.length; valid = kpis.compliant; expiringSoon = kpis.expiring_30; overdue = kpis.overdue; missingEvidence = kpis.missing; nextDueDate = min(expiry_date) from matrix (e.g. soonest future or soonest among non-compliant). scoreImpact = criticality (HIGH→High, MED→Medium, else Low).
- **Optional backend:** next_due_date; per-row evidence_count, latest_evidence_label, confirmation_status (from documents join).

### Notes on linkage

- **Evidence tab:** Upload/View document already go to Documents with property_id + requirement_id. Add “View Evidence tab” CTA that sets activeTab(TAB_EVIDENCE). Confirm Details can link to Evidence tab or Documents (existing flow).
- **Timeline tab:** Add “View history” / “View in Timeline” from Compliance that sets activeTab(TAB_TIMELINE) and applies category or entity filter if supported.
- **Assets tab:** No link until obligation–asset mapping exists; use placeholder “—” or “Linked asset” future.
- **Score:** Already driven by existing engine; confirmation (apply-extraction) updates requirement and score; no change needed.

### Placeholders / future-ready

- **Linked asset:** Show “—” or “Not linked” in detail drawer until asset–requirement linkage is implemented.
- **Recurrence:** Show “—” or “Annual” if not in catalog/requirement yet.
- **Unlinked Evidence filter:** Omit or show as disabled until evidence list is available for property and can be matched to requirements.
- **Compliance notes strip:** Optional one-line “Status based on portal records. Informational only.”

---

**End of audit.** Implement only the Compliance tab with additive changes; reuse existing compliance-detail and scoring; do not break existing compliance or evidence flows.
