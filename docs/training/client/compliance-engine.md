# Client – Compliance (Requirements) – Training Manual

## 1. Module name
**Compliance** (Requirements) — Client

## 2. Audience
**Client / end user.** In the UI this is labelled **Compliance** in the sidebar; data is “requirements” (compliance items per property).

## 3. Purpose
View all compliance requirements across the portfolio (or by property), see due dates and status, edit applicability (e.g. confirm expiry date, set “not required”), and understand what evidence is missing. This is the main place to see “what’s due” and “what’s overdue.”

## 4. Where to find it in the UI
- **URL:** `/requirements`
- **Navigation:** Sidebar → **Compliance** (icon FileCheck).

## 5. What the user sees on the page
- **Header:** “Compliance” or similar; short description.
- **Group by:** Toggle or dropdown — “By property” vs “By requirement” (group requirements by property or by requirement type).
- **Filters:** URL params or in-page filters: status (all / green / amber / red / etc.), optional “window” (days).
- **Search:** Filter by search term (client-side or API).
- **List:** Accordion or table. Each item: requirement type (e.g. Gas Safety, EICR), property name/address, status (PENDING, EXPIRING_SOON, OVERDUE, etc.), due date, document count. **Edit** opens a modal to set confirmed expiry date, applicability, or “not required” reason.
- **Document count:** Shows how many documents are linked to that requirement; link to Documents page or upload from here if implemented.
- **Edit modal:** Fields: Confirmed expiry date, Applicability, Not required reason (no_gas_supply, exempt, not_applicable, other). Save → `PATCH` to backend (properties or requirements API).

## 6. Step-by-step actions

| Action | What to click | What happens |
|--------|----------------|--------------|
| Load requirements | Open Compliance page | `GET /api/client/requirements` (and dashboard for properties). Requirements and document counts load. |
| Group by property / requirement | Switch group-by | List reorders; same data, different grouping. |
| Filter by status | Select status filter or set URL param | List filters to that status. |
| Edit a requirement | Click Edit (pencil) on a requirement | Modal opens with current values; user can set confirmed_expiry_date, applicability, not_required_reason. Save → `PATCH` (e.g. properties requirement update). |
| Go to upload evidence | Link “Upload” or “Documents” for a requirement | Navigate to Documents page; optionally pre-filter by property/requirement. |
| View property | Click property name/link | Navigate to property detail. |

## 7. What happens after each action
- **Edit and Save:** Backend updates requirement (e.g. due date, not required). Compliance status and score may recalculate (scheduled or on next load). UI refreshes or modal closes.
- **Filter/group:** In-page re-filter or re-group; no new API call for filter in some implementations (data already loaded).
- **Navigate to Documents:** User can then select same property/requirement and upload a file.

## 8. Status/outcome examples
- **PENDING:** Requirement exists; no evidence or evidence not yet confirmed. Due date may be in future or past.
- **EXPIRING_SOON:** Due within threshold (e.g. 30 days); user should renew or upload updated evidence.
- **OVERDUE / EXPIRED:** Due date passed; property may show RED. Urgent: upload evidence or set “not required.”
- **Green / Valid:** Evidence in place and in date.
- **Not required:** User set a reason (e.g. no_gas_supply); requirement may be excluded from score or marked N/A.

## 9. Common errors or confusing points
- **“Compliance” vs “Requirements”:** Same page; backend and docs say “requirements.” Use “Compliance (requirements)” in training.
- **Status meanings:** PENDING = no or incomplete evidence; EXPIRING_SOON = due soon; OVERDUE = past due. Explain in training; no full in-page glossary in base UI.
- **Edit only certain fields:** User can set expiry date and “not required”; they cannot create or delete requirements (those come from catalog/property setup). Deleting evidence is on Documents page.
- **Document count:** Count is of documents linked to that requirement_id; uploading on Documents page and linking to requirement updates this.

## 10. Current limitations or known gaps
- **Needs runtime confirmation:** Whether group-by and filters are URL-driven (shareable links) or only in-page state.
- No inline “add requirement” for a property from this page in base implementation; requirements may be created by system or from property setup.
- Recalculation after edit may be delayed (scheduled jobs).

## 11. Notes for training staff
- “This is your list of what’s due. Red/overdue = fix first. Use Edit to set ‘not required’ or confirm expiry date if you know it.”
- “To add evidence, go to Documents and choose the same property and requirement type.”
- If user says “I don’t have this requirement,” train “Edit → Not required → choose reason.”

---

## Trainer walkthrough (5–10 minutes)

1. **Open Compliance** → show list grouped by property (or requirement).
2. **Point out statuses:** “PENDING = need evidence; EXPIRING_SOON = due soon; OVERDUE = past due.”
3. **Edit one:** Open Edit on a requirement → set “Not required” with reason (e.g. No gas supply) → Save → show list update.
4. **Show document count:** “This number is how many documents you’ve linked; upload more from Documents.”
5. **Filter:** Change status filter → “Focus on what needs action.”
6. **Link to Documents:** “To upload a certificate for this requirement, go to Documents and select this property and type.”
