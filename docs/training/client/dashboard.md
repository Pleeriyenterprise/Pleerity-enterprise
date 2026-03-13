# Client Dashboard – Training Manual

## 1. Module name
**Client Dashboard**

## 2. Audience
**Client / end user** (landlords, property managers). Visible only after client login.

## 3. Purpose
First page after client login. Shows portfolio summary, compliance score, score trend, setup checklist (first-time), properties at a glance, and—if entitled—operations KPIs (work orders, predictive insights, risk signals). Helps the user see “where I stand” and what to do next.

## 4. Where to find it in the UI
- **URL:** `/dashboard`
- **Navigation:** After logging in at `/login/client`, user is typically redirected to `/dashboard`. Sidebar: **Dashboard** (first item in client portal).

## 5. What the user sees on the page
- **Header:** Client context; may show customer reference (CRN) or name.
- **Compliance score card:** Overall score (0–100), grade (A/B/C/D/F), and short message (e.g. “Low risk – good standing”). May include a sparkline or trend.
- **Score trend card:** Option to view “Portfolio” vs “Property”; trend chart or sparkline; summary (e.g. change over 30 days, best/worst over 90 days). From APIs: `/api/client/score-trend/portfolio`, property-specific trend.
- **Setup checklist (first-time or incomplete):** If onboarding checklist is enabled and not done, a checklist may appear (e.g. add property, upload evidence). User can tick items or skip.
- **Properties at a glance:** List or cards of properties with compliance status (GREEN/AMBER/RED), score, or “attention needed.” Click property → property detail.
- **Requirements summary:** May show count of requirements due soon or overdue; link to Compliance (Requirements) page.
- **Operations (if entitled):** Work orders, predictive insights, risk signals (feature-gated: maintenance_workflows, predictive_maintenance). Shown only if plan includes these features.
- **Restrict/error states:** If client not provisioned or plan missing, a message may appear (e.g. “Client not found”, “Account must be provisioned”) and some content may be hidden.
- **Help/Support:** Link to Help Centre (`/help`) and possibly support email.

## 6. Step-by-step actions the user can take

| Action | What to click | What happens |
|--------|----------------|--------------|
| View score and trend | N/A (visible on load) | Data from `GET /api/client/dashboard`, `GET /api/client/compliance-score`, `GET /api/client/score-trend/portfolio` (and property trend when property selected). |
| Open a property | Click property card/row | Navigate to `/properties/{propertyId}` (Property Detail page). |
| Complete setup checklist | Tick item or “Done” | Calls onboarding checklist API; checklist state updates; may redirect to “portfolio” or “documents” view or stay on dashboard. |
| Switch trend to property view | Toggle or select “Property” | Fetches trend for selected property; chart updates. |
| Go to Compliance (requirements) | Link “Compliance” or “Requirements” | Navigate to `/requirements`. |
| Go to Documents | Link “Documents” or “Upload evidence” | Navigate to `/documents`. |
| Go to Help | Link “Help Centre” or “Help” | Navigate to `/help`. |

## 7. What happens after each action
- **Property click:** Navigates to property detail; user can then view/edit property, see requirements, upload evidence for that property.
- **Checklist complete:** Backend updates checklist state; UI may collapse checklist or show next steps.
- **Trend switch:** New API call; trend card shows property-specific data.
- **Navigation links:** Route change; no backend call except when the new page loads its data.

## 8. Status/outcome examples
- **Score 85, grade B:** “Low risk – good standing.” No urgent action; user can still improve by uploading evidence or updating dates.
- **Score 50, grade D:** “High risk – action required.” Drivers (on Compliance Score page) will show what to fix.
- **Restrict reason “not_provisioned”:** Account not yet provisioned after payment; user may see message to wait or contact support.
- **Empty properties:** “Add your first property” CTA; link to `/properties/create`.

## 9. Common errors or confusing points
- **“Client not found” or blank dashboard:** User may have logged in with wrong portal (e.g. admin) or account not linked to a client_id. Use correct login and ensure client exists and is provisioned.
- **Score not updating:** Score is recalculated by scheduled jobs; there can be a delay after uploading evidence or changing dates.
- **Operations section missing:** Normal if plan does not include maintenance_workflows or predictive_maintenance; these are feature-gated.
- **Setup checklist keeps showing:** User may have skipped; checklist can be dismissed or marked done depending on implementation. If it blocks usage, escalate.

## 10. Current limitations or known gaps
- **Needs runtime confirmation:** Exact layout, order of cards, and when setup checklist appears (e.g. first login only vs every time until complete) depend on build and config.
- No in-dashboard “what to do next” wizard beyond checklist; user may need to go to Compliance or Documents manually.
- Score trend “property” view requires selecting a property; if only one property, behaviour should be confirmed.

## 11. Notes for training staff
- Use dashboard as “home”: “After login you see your score and properties. Green/amber/red tells you which properties need attention.”
- Emphasise: “Click a property to open it and add or update evidence.”
- If user has no properties, direct them to “Add Property” then Requirements then Documents.
- For “my score is wrong,” explain recalculation delay and suggest checking Compliance Score page drivers.

---

## Trainer walkthrough (5–10 minutes)

1. **Log in as client** → land on `/dashboard`.
2. **Point out:** Compliance score card, grade, and message.
3. **Show score trend:** Switch Portfolio vs Property (if multiple properties); explain “this shows how your score changed over time.”
4. **Show properties list:** “Green = good, amber = attention, red = overdue. Click a property to manage it.”
5. **If checklist visible:** “New users may see a setup list; you can complete it or skip.”
6. **Quick links:** “Compliance and Documents are in the sidebar; use them to fix overdue items or upload certificates.”
7. **Operations (if present):** “If you have Work Orders or Risk Signals, they appear here; otherwise they’re hidden.”
