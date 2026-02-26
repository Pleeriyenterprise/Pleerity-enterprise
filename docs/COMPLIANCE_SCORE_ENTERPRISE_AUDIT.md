# Enterprise Compliance Score Page – Implementation Audit

**Purpose:** Compare the codebase to the “Enterprise Compliance Score Explanation Page” task requirements. Identifies what is implemented, what is missing, conflicts, and the recommended order of work. **Do not implement blindly**—use this to avoid duplication and conflict.

---

## 1. Implemented vs Spec

### A) Top Summary Banner (Upgrade)

| Spec requirement | Status | Notes |
|------------------|--------|--------|
| Last recalculated: `{score_last_calculated_at}` (relative + exact on hover) | **Missing** | Backend does not return this; property-level `compliance_last_calculated_at` exists but is not in score API. |
| Score scope tag: "Portfolio Score (Weighted)" + info tooltip | **Missing** | Page shows "Based on X tracked items across Y properties" but no explicit "Portfolio Score (Weighted)" tag or tooltip text from spec. |
| Data Quality badge: "Data completeness: {x}%" + tooltip | **Missing** | Not in API or UI. |
| Replace "Critical risk – immediate action needed" with calmer copy | **Partial** | Backend (`risk_bands.py`) returns "Critical risk - immediate action needed" for grade F. Spec wants: "High urgency: overdue items detected" and always "Informational indicator based on portal records. Not legal advice." |
| Acceptance: Top banner shows timestamp and scope; copy is calm and non-accusatory | **Not met** | Pending above. |

### B) Score Scope & Definitions Block

| Spec requirement | Status | Notes |
|------------------|--------|--------|
| Compact card "Score scope" with 4 bullets (included / excluded / how counted / how updates) | **Missing** | No such block. |
| "View definitions" link → modal or accordion (Valid / Expiring Soon / Overdue; Applicable vs Not applicable; Date confidence; Tracked item) | **Missing** | No definitions modal/accordion. |
| Acceptance: Users understand "tracked items"; definitions exist without cluttering | **Not met** | Pending above. |

### C) How This Score is Calculated (Refactor)

| Spec requirement | Status | Notes |
|------------------|--------|--------|
| Standardised card template: Title, Weight, What it measures, Your result, Why (one line with counts) | **Partial** | Four weighting cards exist (Status, Timeline, Documents, Overdue Penalty). They do not follow the exact template: no "Your result: X%", no "Why" line with counts (e.g. "0 valid • 0 expiring • 2 overdue"). |
| Rename "Overdue Penalty" → "Urgency Impact" | **Missing** | Still "Overdue Penalty" in UI. |
| "Advanced details" accordion (collapsed): longer text, thresholds, model version, model updated | **Missing** | No accordion; no model version or model_updated_at in API or UI. |
| Backend weights vs spec | **Conflict** | Spec: Status 40%, Timeline 30%, Documents 15%, Urgency 15%. Backend (`compliance_score.py`): status 35%, expiry 25%, documents 15%, overdue_penalty 15%, risk_factor 10%. Backend has five components and different weights. |
| Acceptance: Cards shorter, consistent, explain "why"; model version visible in advanced area | **Not met** | Pending refactor and backend alignment. |

### D) Score Drivers Table

| Spec requirement | Status | Notes |
|------------------|--------|--------|
| Section "Score drivers (what is affecting your score)" | **Missing** | No such section. |
| Table: Requirement, Property, Status, Date used + confidence, Evidence, Action button | **Missing** | Not implemented. |
| Action logic: Missing evidence → "Upload document"; Needs confirmation → "Confirm details"; Overdue/Expiring with evidence → "View requirement" | **Missing** | No drivers, no actions. |
| If backend doesn't provide drivers: UI with placeholder from requirement list + info note | **N/A** | Backend does not return `drivers`; spec allows client-side derivation from requirements. |
| Acceptance: User sees e.g. "2 overdue" and can click to fix; score not a black box | **Not met** | Pending implementation. |

### E) Reconciliation Microcopy

| Spec requirement | Status | Notes |
|------------------|--------|--------|
| One-liner near timeline/status: "Overdue items are not counted as 'due soon' because their due date has already passed." | **Missing** | Not present. |
| Acceptance: No perceived contradiction between "0 due within 30 days" and "2 overdue" | **Not met** | Pending. |

### F) Property Breakdown (Upgrade)

| Spec requirement | Status | Notes |
|------------------|--------|--------|
| Property name + postcode | **Done** | Already shown. |
| Property score (big) | **Partial** | Page shows "contribution" score computed client-side via `getPropertyScoreContribution` (different formula than backend). Backend has per-property `compliance_score` but does not return it in score API. |
| Mini status chips: "Valid x" "Expiring x" "Overdue x" | **Done** | Chips already present. |
| "View drivers" link → scroll to Score Drivers table filtered by property | **Missing** | No drivers section yet; no link. |
| "View property dashboard" button | **Partial** | Click goes to `/app/properties?property_id=...` (redirects to `/properties`); spec says "View property dashboard" and `/properties/:propertyId`. So link could go to property detail. |
| Acceptance: Portfolio vs property score obvious; drilldown from property row works | **Partial** | Chips and list exist; need "View drivers" and clear "View property dashboard" (e.g. to `/properties/:propertyId`). |

### G) Enterprise Add-ons (UI only)

| Spec requirement | Status | Notes |
|------------------|--------|--------|
| "Download score explanation (PDF)" – disabled + "Coming soon" if not implemented | **Missing** | No button. |
| "Export score drivers (CSV)" – same | **Missing** | No button. |
| No backend PDF/CSV required for this task | **OK** | UI hooks only. |

### Data Contract

| Field (spec) | Backend currently | Frontend use |
|--------------|-------------------|--------------|
| `portfolio_score` | `score` | Used. |
| `grade` | `grade` | Used. |
| `valid_count`, `expiring_count`, `overdue_count` | In `stats` (e.g. `compliant`, `expiring_soon`, `overdue`) but naming differs | Mapped in UI. |
| `tracked_items_total`, `properties_count` | `stats.total_requirements`, `properties_count` | Available. |
| `score_last_calculated_at` | **Not returned** | — |
| `score_model_version`, `model_updated_at` | **Not returned** | — |
| `data_completeness_percent` | **Not returned** | — |
| `components` (status/timeline/documents/urgency with weights + counts) | **Partial** | `breakdown` has scores; weights and per-component counts (valid/expiring/overdue, due_0_30, etc.) not in current shape. |
| `drivers[]` | **Not returned** | Can be derived client-side from requirements + documents. |
| `property_breakdown[]` (score, valid, expiring, overdue per property) | **Not returned** | Can be derived from dashboard properties + requirements. |

Backend response shape is in `backend/services/compliance_score.py` and `backend/routes/client.py` (GET `/client/compliance-score`). It does not include the new spec fields; backend can stub or extend, or frontend can derive where the spec allows.

### Navigation Targets (Spec vs Actual)

| Spec | Actual | Recommendation |
|------|--------|----------------|
| `/documents/upload?propertyId=...&requirementId=...` | No `/documents/upload` route. Documents page is `/documents` with `property_id` and `requirement_id` query params. | Use **`/documents?property_id=...&requirement_id=...`** for "Upload document". Do not add `/documents/upload` unless product explicitly wants a separate upload route. |
| `/requirements/:requirementId?propertyId=...` | No `/requirements/:id` route. Requirement detail is in context of a property. | Use **`/properties/:propertyId`** (property detail) and optionally focus the requirement (e.g. hash or query). "View requirement" → property detail with requirement in context. |
| `/properties/:propertyId` | Exists. | Use as-is for "View property dashboard". |
| Confirm Certificate Details modal | Modal exists on **DocumentsPage** (inline state), not a shared component. No route. | **Option A:** "Confirm details" links to `/documents?property_id=...&requirement_id=...` (user opens document and uses existing confirm flow). **Option B:** Add a small shared `ConfirmCertificateDetailsModal` and open it from the score page with `requirement_id` + `property_id` (and optional `document_id`) when backend supports it. Prefer A for minimal change; B if UX requires in-page confirm from score. |

### Non-Legal / Safety Language

- Backend currently returns "Critical risk - immediate action needed" and similar. Spec: never "You are compliant" / "Legally compliant"; use "informational indicator", "based on portal records", "may apply depending on your situation"; F-grade: "High urgency: overdue items detected" and always "Informational indicator based on portal records. Not legal advice."
- **Action:** Update backend message for F (and optionally others) and ensure all score copy on the page follows the safety rules above.

---

## 2. Conflicts and Safest Choices

### 2.1 Weighting model (Status 40% vs backend 35% + risk 10%)

- **Conflict:** Spec assumes four components with 40/30/15/15. Backend has five (status 35%, expiry 25%, documents 15%, overdue_penalty 15%, risk_factor 10%).
- **Recommendation:** Treat backend as source of truth. Do not change backend weights to match spec unless product explicitly agrees. In the UI:
  - Show the four main cards (Status, Timeline, Documents, Urgency/Overdue) using backend weights and scores; if "risk_factor" is separate, either fold it into one of these (e.g. Urgency) or show a fifth card, and document the mapping in the advanced section.
  - Use backend labels/weights in the card template (e.g. "Status (35%)" if that’s what the API returns). Align copy with backend so the page is auditable.

### 2.2 Routes and confirm modal

- **Conflict:** Spec mentions `/documents/upload` and `/requirements/:requirementId` and a "ConfirmCertificateDetailsModal".
- **Recommendation:**
  - Use **existing routes only**: `/documents?property_id=...&requirement_id=...`, `/properties/:propertyId`. No new routes unless product requests them.
  - "Confirm details" from Score Drivers: link to Documents with `property_id` and `requirement_id`; optionally later add `?confirm=1` or similar to auto-open the existing confirm modal on Documents page. Do not add a duplicate modal unless UX requires it.

### 2.3 Property score source

- **Conflict:** Spec wants "property score" in breakdown. Backend stores per-property score but doesn’t return it in the compliance-score response. Frontend currently computes a "contribution" score locally.
- **Recommendation:** Prefer backend as source. If backend can return `property_breakdown[]` with `score`, `valid`, `expiring`, `overdue` per property, use that. If not, keep deriving from dashboard + requirements and document that property score is "derived from current requirements" until API is extended.

---

## 3. Recommended Order of Work

1. **Backend (optional but recommended)**  
   - Add to score response (or document as optional): `score_last_calculated_at`, `score_model_version`, `model_updated_at`, `data_completeness_percent`.  
   - Optionally add `components` (with per-component counts) and `property_breakdown[]`; if not, frontend derives from existing APIs.  
   - Optionally add `drivers[]`; if not, frontend builds from requirements list.  
   - Align F-grade (and risk) messaging with spec (calmer copy + "Informational indicator..." line).

2. **Frontend – Banner and copy**  
   - Add last recalculated (relative + tooltip); score scope tag + tooltip; data completeness badge (with null/unknown state).  
   - Replace critical/accusatory wording with spec copy; add "Informational indicator based on portal records. Not legal advice." in banner.

3. **Score scope & definitions**  
   - Add "Score scope" card (4 bullets).  
   - Add "View definitions" (modal or accordion) with definitions from spec.

4. **How calculated – cards and advanced**  
   - Refactor weighting cards to spec template (Title, Weight, What it measures, Your result, Why with counts). Use backend weights/labels; rename "Overdue Penalty" to "Urgency Impact" in UI if backend allows or keep one label for both.  
   - Add "Advanced details" accordion (collapsed) with long text, thresholds (if available), model version and model updated.

5. **Score drivers**  
   - Add "Score drivers" section.  
   - If API provides `drivers[]`, use it; else build from requirements (filter status !== valid) and map to columns (Requirement, Property, Status, Date used, confidence, Evidence, Action).  
   - Actions: Upload document → `/documents?property_id=...&requirement_id=...`; Confirm details → same URL (or open confirm on Documents); View requirement → `/properties/:propertyId`.  
   - Add info note if data is incomplete.  
   - Loading/empty state: "No issues detected based on current portal records."

6. **Reconciliation microcopy**  
   - Add the one-liner about overdue not being "due soon" near timeline/status summary.

7. **Property breakdown**  
   - Keep name, postcode, score, chips. Add "View drivers" (scroll + filter by property) and "View property dashboard" button to `/properties/:propertyId`.  
   - Normalise links to `/properties` and `/properties/:propertyId` (replace `/app/properties` and `/app/dashboard` with `/dashboard` and `/properties` for consistency).

8. **Export UI**  
   - Add "Download score explanation (PDF)" and "Export score drivers (CSV)" buttons; disabled with "Coming soon" tooltip if backend not ready.

9. **Polish**  
   - Loading/skeleton for drivers and components; mobile: Score Drivers as stacked cards; ensure no new broken routes; use existing component library and branding.

---

## 4. Definition of Done Checklist (from spec)

- [ ] Score page shows: timestamp, scope, data completeness badge.  
- [ ] Score weighting cards follow the new standard format (with backend as source of truth).  
- [ ] Score Drivers section exists and users can click actions to resolve.  
- [ ] Property breakdown has status chips and drilldown (View drivers, View property dashboard).  
- [ ] Reconciliation microcopy present.  
- [ ] No new broken routes; if any target is missing, use placeholders/safe copy and existing routes as above.

---

## 5. Files to Touch (Summary)

- **Backend:** `backend/services/compliance_score.py`, `backend/routes/client.py`, optionally `backend/utils/risk_bands.py` (messages).  
- **Frontend:** `frontend/src/pages/ComplianceScorePage.js` (main changes); optionally a small shared modal for confirm-details if chosen.  
- **Routes:** Use existing `/documents`, `/properties`, `/properties/:propertyId`, `/dashboard`; no new route required for this spec.  
- **Docs:** This audit; update any API contract doc when backend adds new fields.

Implement only after approval of this audit and the chosen options for weighting display, routes, and confirm-details flow.
