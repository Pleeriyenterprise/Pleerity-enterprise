# Admin – Compliance Score (Training Manual)

## 1. Module name
**Compliance Score (Admin view)**

## 2. Audience
**Admin / internal staff.** Clients see their own score on Dashboard and Compliance Score page; this manual covers how the score works and how admins can view or use it.

## 3. Purpose
The compliance score (0–100) and associated grade/band reflect the client’s portfolio-wide compliance health based on requirements and evidence. Admins need to understand how it is calculated, where to see a client’s score, and how reporting/export works (including plan-gating).

## 4. Where to find it in the UI
- **Client context:** When viewing a client in admin, their compliance score may be shown in summary or in a dedicated section. Data comes from the same backend as client: `GET /api/client/compliance-score` (client-scoped); admin may call equivalent or get it via client dashboard payload.
- **Reporting:** Admin reporting or analytics may include score data; **needs runtime confirmation** for exact routes.
- **Client-facing (for reference):** Client sees score on Dashboard and on `/compliance-score`; can export PDF/CSV if plan allows (`reports_pdf` or similar).

## 5. What the user sees
- **Score value:** 0–100.
- **Grade/band:** e.g. A/B (low risk), C (moderate), D/F (high risk). Logic in code: e.g. ≥80 → A/B, ≥60 → C, ≥40 → D, &lt;40 → F.
- **Drivers:** Requirements and evidence that push score up or down (e.g. missing evidence, overdue items).
- **Trend:** Score over time (sparkline or chart); from compliance trend service and score timeline APIs.

## 6. Step-by-step actions
| Action | What to do | What happens |
|--------|------------|--------------|
| View a client’s score | Open client in admin; find score in summary or compliance section | Score and possibly trend load from backend. |
| Understand why score is low | View “drivers” or requirements list for that client; look for overdue, missing evidence, expiring soon | Same drivers the client sees on Compliance Score page. |
| Export score/report (client) | Client uses Compliance Score page → Download PDF or CSV | Backend: `GET /reports/score-explanation.pdf` or `GET /reports/score-drivers.csv`; 403 if plan does not include export. |
| Export from admin (if available) | Use reporting/export feature for a client | Implementation-specific; confirm in build. |

## 7. What happens after each action
- View: Read-only.
- Export (client): PDF/CSV generated; download starts. If 403, client may see upgrade prompt.
- Score updates: Driven by recalc jobs and evidence/requirement changes; not instant after every change.

## 8. Status/outcome examples
- **Score 85, grade B:** Portfolio in good standing; minor items may be expiring.
- **Score 45, grade D:** Overdue or missing evidence; drivers will show which requirements.
- **403 on export:** Client’s plan does not include report export; client sees upgrade modal or message.

## 9. Common errors or confusing points
- **Score vs property status:** Score is portfolio-level (0–100); property status is GREEN/AMBER/RED per property. Both use the same underlying requirement/evidence data.
- **When does score update?** After recalc jobs run (scheduled) or after evidence/requirement updates that trigger recalc; there can be a delay.
- **Methodology:** Client can expand “Methodology” and “Definitions” on Compliance Score page; admins can use the same logic to explain to clients.

## 10. Current limitations or known gaps
- Admin-specific “compliance score report for all clients” or bulk export **needs runtime confirmation**.
- Export is plan-gated; exact entitlement name (e.g. `reports_pdf`) and behaviour per plan should be confirmed in environment.
- Score calculation source: `calculate_compliance_score` in backend; uses catalog or stored scores; exact weighting and rules are in code.

## 11. Notes for training staff
- Use “drivers” to explain to a client why their score is low and what to fix (upload evidence, update dates, mark not applicable).
- If client says “I exported but got an error,” check their plan for report/PDF entitlement.
- Recalculation is automatic; avoid promising “score updates in 1 minute” unless you’ve verified timing in your environment.

---

## Trainer walkthrough (5 minutes)

1. **Open a client** that has properties and requirements → locate where score is shown (summary or compliance section).
2. **Explain:** “This is the same 0–100 score they see on their dashboard and Compliance Score page.”
3. **Show drivers (if visible):** “These are what pull the score down—overdue, missing evidence, etc.”
4. **Mention export:** “Clients can download PDF/CSV from their Compliance Score page if their plan includes it; we don’t export for them from here unless we have a reporting tool.”
