# Audit Intelligence Platform – Task vs Codebase Gap Analysis

**Constraint:** Do NOT change Stripe, provisioning, authentication, or entitlement logic.

---

## 1. Restructure dashboard into Compliance Command Centre

| Requirement | Status | Notes |
|-------------|--------|------|
| Restructure dashboard into "Compliance Command Centre" | **Missing** | Client dashboard is a single page with welcome, score widget, recommendations, properties. No explicit "Command Centre" layout or naming. |

**Conflict:** None. Safe to add Command Centre branding and layout (nav/title) without touching auth or billing.

---

## 2. Multi-level scoring model

| Requirement | Status | Notes |
|-------------|--------|------|
| **Requirement-level** (VALID=100, EXPIRING_SOON=70, MISSING=30, OVERDUE=0) | **Partial / Different** | `compliance_scoring_service.calculate_property_compliance` uses: COMPLIANT=100, PENDING=70, EXPIRING_SOON=**40**, else 0. Task specifies EXPIRING_SOON=**70**, **MISSING=30**, OVERDUE=0. Status names: code uses COMPLIANT/PENDING/EXPIRING_SOON/OVERDUE; task uses VALID/EXPIRING_SOON/MISSING/OVERDUE (VALID ≈ COMPLIANT, MISSING ≈ no evidence / PENDING). |
| **Property-level** (weighted average of requirement scores) | **Done** | Property score is computed from requirements (weighted by type + HMO) in `compliance_scoring_service.calculate_property_compliance`. Formula differs from task (35% status, 25% expiry, etc.) but is a weighted combination. |
| **Portfolio-level** (weighted by requirement count) | **Different** | `compliance_score.calculate_compliance_score` uses **simple average** of property scores. Task: "Weighted average across all properties **by requirement count**". |

**Conflict:** Task scoring (100/70/30/0) is a **second, simpler model**. Existing model is more complex (expiry timeline, document coverage, overdue penalty, risk factor). **Safest option:** Add a **dedicated portfolio summary** that uses the task’s requirement-level points and portfolio weighting **only for** `GET /api/portfolio/compliance-summary`. Keep existing property/client score logic for `/client/compliance-score` and stored property scores so current behaviour and recalcs are unchanged.

---

## 3. Explicit Risk Level classification

| Requirement | Status | Notes |
|-------------|--------|------|
| 80–100 = Low Risk | **Missing** | No `risk_level` field. Client score returns `grade` (A–F) and `color` (green/amber/red). |
| 60–79 = Moderate Risk | **Missing** | |
| 40–59 = High Risk | **Missing** | |
| 0–39 = Critical Risk | **Missing** | |
| Add `risk_level` on property and portfolio | **Missing** | Not stored or returned. |

**Conflict:** None. Add `risk_level` as a **derived** value (from score bands) in the new portfolio summary response and, optionally, when reading property/portfolio scores. Prefer **computed on read** for portfolio; optional **stored on property** when we persist score if we want consistency.

---

## 4. Replace vague messaging with risk-based messaging

| Requirement | Status | Notes |
|-------------|--------|------|
| Replace "Below average" etc. with risk-based messaging | **Partial** | `compliance_score.calculate_compliance_score` returns `message` e.g. "Below average - action required" (60–69), "Good compliance status" (80+). Task: use risk-based labels (Low/Moderate/High/Critical) instead. |

**Conflict:** None. We can add a `risk_level` and a `message` (or `risk_message`) based on score bands and keep or deprecate existing `message` for backward compatibility.

---

## 5. Add Audit Log tab

| Requirement | Status | Notes |
|-------------|--------|------|
| Add Audit Log tab (client portal) | **Missing** | Admin has Audit Logs; client portal has no Audit tab. Need a client-scoped, read-only audit/timeline for their own actions (e.g. document uploads, score changes). |

**Conflict:** None. Backend may need a client-safe audit/timeline endpoint (filter by `client_id` and non-sensitive actions) if not already present.

---

## 6. Add Portfolio summary table

| Requirement | Status | Notes |
|-------------|--------|------|
| Portfolio summary table | **Partial** | Dashboard shows properties and score; no dedicated "Portfolio summary" table with columns matching task (e.g. property_id, property_score, risk_level, overdue_count, expiring_soon_count). New endpoint can drive this. |

**Conflict:** None.

---

## 7. Compliance Framework explanation section

| Requirement | Status | Notes |
|-------------|--------|------|
| Static section explaining scoring logic and disclaimers | **Partial** | Dashboard has a short disclaimer ("evidence-based status summary, not legal advice"). No "Compliance Framework" section explaining requirement-level points, property/portfolio weighting, risk bands. |

**Conflict:** None. Add a static, non-legal section (no certification / legal advice).

---

## 8. Recalculate on document upload / expiry update / requirement status change

| Requirement | Status | Notes |
|-------------|--------|------|
| Recalc on **document uploaded** | **Done** | `documents` routes call `enqueue_compliance_recalc` (TRIGGER_DOC_UPLOADED, etc.). |
| Recalc on **expiry updated** | **Done** | Expiry rollover job in `job_runner` enqueues recalc (TRIGGER_EXPIRY_JOB) for affected properties. |
| Recalc on **requirement status changed** | **Gap** | Daily reminder job in `services/jobs.py` updates requirement status to OVERDUE/EXPIRING_SOON but does **not** call `enqueue_compliance_recalc`. Other status changes (e.g. AI applied, admin) may go through code paths that already enqueue. |

**Conflict:** None. **Safest:** After the reminder job (or any job) updates requirement status, enqueue a compliance recalc for each affected `property_id` so scores stay in sync.

---

## 9. New endpoint and response shape

| Requirement | Status | Notes |
|-------------|--------|------|
| **GET /api/portfolio/compliance-summary** | **Missing** | No such route. `/api/reports/compliance-summary` is for **report generation** (CSV/PDF). `/api/client/compliance-score` returns current client score with grade/color/message. |
| Return: portfolio_score, risk_level, properties[] (property_id, property_score, risk_level, overdue_count, expiring_soon_count) | **Missing** | To be implemented. |

**Conflict:** None. Add new router (e.g. `prefix="/api/portfolio"`) with `client_route_guard` so only authenticated clients can call it.

---

## 10. Conflicting instructions and recommended approach

- **Scoring model:** Task specifies a **simple** requirement-level model (100/70/30/0) and portfolio weighted by requirement count. Current code uses a **richer** property-level model (status/expiry/documents/overdue/risk) and simple average for client.  
  **Recommendation:** Implement the task’s model **only** for the new **portfolio summary** API and for any UI that explicitly shows "Audit Intelligence" risk levels. Keep existing `compliance_scoring_service` and `calculate_compliance_score` as-is for existing behaviour and stored scores. Optionally add a small helper that computes "audit intelligence" requirement points (VALID=100, EXPIRING_SOON=70, MISSING=30, OVERDUE=0) and roll up to property/portfolio for this response only.
- **Status names:** Task uses VALID/MISSING; code uses COMPLIANT/PENDING. Map as: VALID ↔ COMPLIANT, MISSING ↔ PENDING (or no evidence). EXPIRING_SOON and OVERDUE align.

---

## Implementation checklist (safe, minimal)

1. **Backend**
   - Add **GET /api/portfolio/compliance-summary** (new router or under client):
     - Use existing client_route_guard.
     - Load client’s properties and requirements.
     - Compute requirement-level points (100/70/30/0) from status; roll up to property (weighted average) and portfolio (weighted by requirement count).
     - Add **risk_level** from score bands (80–100 Low, 60–79 Moderate, 40–59 High, 0–39 Critical).
     - Return JSON: portfolio_score, risk_level, properties[] with property_id, property_score, risk_level, overdue_count, expiring_soon_count.
   - Optionally persist **risk_level** on property when recalc runs (or compute on read in this endpoint only).
   - **Recalc on requirement status change:** In the daily reminder job (or wherever requirement status is set to OVERDUE/EXPIRING_SOON), after bulk status updates, enqueue compliance recalc for each affected property_id (reuse `enqueue_compliance_recalc` with a reason like REQUIREMENT_STATUS_CHANGED).

2. **Frontend**
   - **Compliance Command Centre:** Rename or restructure dashboard title/section to "Compliance Command Centre" (no change to auth or entitlements).
   - **Portfolio summary table:** Consume GET /api/portfolio/compliance-summary and render table (property, score, risk, overdue, expiring).
   - **Risk-based messaging:** Where the app shows score or grade, also show risk_level (Low/Moderate/High/Critical) and use it for messaging instead of "Below average".
   - **Compliance Framework section:** Add a static, collapsible section explaining: requirement scores (100/70/30/0), property = weighted average, portfolio = weighted by requirement count, risk bands, and disclaimer (evidence-based, not legal advice / certification).
   - **Audit Log tab:** Add a tab that shows client-scoped audit/timeline (requires backend endpoint if not present).

3. **No change**
   - Stripe, provisioning, authentication, entitlement logic.
   - Existing `/client/compliance-score` and stored property score calculation (unless we explicitly add risk_level to that response for consistency).
