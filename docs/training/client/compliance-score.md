# Client – Compliance Score – Training Manual

## 1. Module name
**Compliance Score** (Client)

## 2. Audience
**Client / end user.**

## 3. Purpose
Dedicated page for the portfolio compliance score (0–100), grade/band, trend over time, “drivers” (what helps or hurts the score), and optional methodology/definitions. Users with the right plan can export PDF or CSV. This complements the score card on the Dashboard with full detail and export.

## 4. Where to find it in the UI
- **URL:** `/compliance-score`
- **Navigation:** Sidebar → **Compliance Score** or link from Dashboard score card.

## 5. What the user sees on the page
- **Score and grade:** Large display of 0–100 and letter grade (A/B/C/D/F) with short message (e.g. “Low risk – good standing”, “High risk – action required”).
- **Last updated / as of:** When the score was last calculated (from backend).
- **Drivers:** List or table of factors that affect the score: e.g. missing evidence, overdue items, expiring soon, valid evidence. May be filterable by property. Clicking a driver may link to the relevant property or requirement.
- **Trend:** Chart or sparkline of score over time (e.g. last 90 days). From `/api/client/compliance-score/trend`, timeline, or score-trend APIs.
- **Methodology (expandable):** Explanation of how the score is calculated; may be in an accordion or “Learn more” section.
- **Definitions (expandable):** Definitions of terms (e.g. PENDING, EXPIRING_SOON, OVERDUE, valid evidence). Optional modal or expandable section.
- **Export:** Buttons “Download PDF” and “Download CSV” (or similar). **Plan-gated:** If plan does not include report export (e.g. `reports_pdf`), clicking may show 403 or an upgrade modal.
- **Advanced details (optional):** Extra breakdown (e.g. by property or requirement type) if implemented.

## 6. Step-by-step actions

| Action | What to click | What happens |
|--------|----------------|--------------|
| Load score and drivers | Open Compliance Score page | `GET /api/client/compliance-score`, trend/timeline APIs; drivers and score load. |
| Filter drivers by property | Select property in filter (if available) | Drivers list filters to that property. |
| View methodology | Expand “Methodology” or “How we calculate” | In-page text explains formula and weights (no API). |
| View definitions | Expand “Definitions” or open help | In-page or modal with term definitions. |
| Download PDF | Click Download PDF | `GET /reports/score-explanation.pdf` (blob). If 403, upgrade modal. Success → file downloads. |
| Download CSV | Click Download CSV | `GET /reports/score-drivers.csv` (blob). If 403, upgrade modal. Success → file downloads. |
| Open a driver item | Click driver row (if linked) | May navigate to property detail or Requirements for that item. |

## 7. What happens after each action
- **Load:** Score and drivers from backend; trend from trend/timeline APIs. Read-only except for navigation.
- **Export:** PDF/CSV generated server-side; browser downloads. 403 if not entitled; frontend may show “Upgrade to export” or similar.
- **Navigate from driver:** Goes to property or Compliance (requirements) to fix the item.

## 8. Status/outcome examples
- **Score 90, grade A:** “Low risk – good standing.” Drivers may show minor items (e.g. one expiring in 60 days).
- **Score 55, grade D:** “High risk – action required.” Drivers show overdue or missing evidence; user should upload evidence or update dates on Documents/Compliance.
- **403 on export:** “Your plan doesn’t include report export.” User can still view score and drivers in the UI; upgrade or contact support for export.
- **Empty drivers:** No requirements or all in good standing; list may be empty or show “No negative drivers.”

## 9. Common errors or confusing points
- **Score didn’t change after upload:** Recalculation runs on a schedule; there can be a delay (minutes to next job run). Not a bug; set expectation in training.
- **Export button does nothing or shows error:** Likely 403 (plan); explain “export is available on higher plans” or show upgrade modal.
- **Grade vs score:** Grade is a band (A–F) derived from score; both reflect the same underlying data. Methodology section explains bands if present.
- **Drivers “missing evidence”:** Means no document linked to that requirement or document not yet confirmed; user should upload and confirm on Documents page.

## 10. Current limitations or known gaps
- **Needs runtime confirmation:** Exact layout (order of blocks, where methodology/definitions live) and whether “advanced details” exists.
- Export entitlement name (e.g. `reports_pdf`) and which plans have it should be confirmed in plan config.
- Score calculation is backend-only; user cannot “recalculate now” from this page.

## 11. Notes for training staff
- “Use drivers to see what to fix first—overdue and missing evidence pull the score down.”
- “After you upload evidence or update dates, the score will update after the next run; it’s not instant.”
- “If Download PDF/CSV asks you to upgrade, that feature is on higher plans; you can still see everything on screen.”
- Point users to Compliance (requirements) and Documents to act on drivers.

---

## Trainer walkthrough (5–10 minutes)

1. **Open Compliance Score** → show score, grade, and message.
2. **Show drivers:** “These are what affect your score. Fix overdue and missing evidence first.”
3. **Filter by property (if available):** “See drivers for one property only.”
4. **Expand Methodology:** “This explains how we get the number.”
5. **Export:** Click Download PDF → if allowed, show download; if 403, “On your plan export may require an upgrade.”
6. **Link to action:** “To fix a driver, go to Compliance or Documents and upload/update that requirement.”
