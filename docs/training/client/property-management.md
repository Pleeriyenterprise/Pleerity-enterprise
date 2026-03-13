# Client – Property Management (Training Manual)

## 1. Module name
**Property Management** (Client)

## 2. Audience
**Client / end user.**

## 3. Purpose
Clients view their property portfolio, add new properties, and open a property to see compliance status and manage requirements and evidence. Plan-based property limits are enforced on create.

## 4. Where to find it in the UI
- **List:** `/properties` — **Properties** in sidebar.
- **Add property:** **Add Property** button → `/properties/create`.
- **Property detail:** Click a property → `/properties/{propertyId}`.

## 5. What the user sees on the page

**Properties list (`/properties`):**
- Header: “Properties”, “Manage your property portfolio.”
- **Add Property** button (top right).
- Stats cards: Total, Green (valid), Amber (attention needed), Red (overdue). Clicking a card may filter the list.
- Search: Filter by nickname, address, or postcode.
- Status filter: All / GREEN / AMBER / RED.
- Table or cards: Each row shows property (nickname or address), compliance status badge (Green/Amber/Red), and link to detail. Click row or “View” → property detail.

**Property create (`/properties/create`):**
- Form: Nickname (optional), Address line 1 & 2, City, Postcode, Property type, Number of units.
- Submit creates the property via `POST /api/properties/create`. Plan limit is enforced; 403 if at limit.

**Property detail (`/properties/{propertyId}`):**
- Property info (address, nickname, type, units).
- Compliance status for this property.
- Requirements list for this property; links to add/upload evidence.
- Documents/evidence section; link to upload or view documents.
- “Need help? See: Uploading Evidence guide” link to `/help?article=uploading-evidence`.

## 6. Step-by-step actions

| Action | What to click | What happens |
|--------|----------------|--------------|
| View all properties | Sidebar → Properties | Page loads; list from `GET /api/client/dashboard` (properties array). |
| Filter by status | Click Green/Amber/Red card or status filter | List filters in-page (client-side filter). |
| Search | Type in search box | List filters by nickname, address, postcode. |
| Add property | Add Property → fill form → Submit | `POST /api/properties/create`. Success → redirect to list or detail; 403 if not provisioned or at plan limit. |
| Open property | Click property row | Navigate to `/properties/{propertyId}`. |
| Edit property (if available) | On detail page, Edit or similar | `PATCH /api/properties/{propertyId}`. Implementation-specific. |
| View requirements for property | On detail page, Requirements section | Shows requirements; user can go to Compliance page or upload evidence from here. |

## 7. What happens after each action
- **Create success:** New property appears in list; user can open it and add requirements/evidence.
- **Create 403:** Error message; may show “plan limit” or “upgrade” if at property cap. Audit log records PLAN_LIMIT_EXCEEDED.
- **Open detail:** Property detail loads; requirements and documents for that property shown.

## 8. Status/outcome examples
- **GREEN:** All requirements for that property in good standing (no overdue; evidence in place or not yet due).
- **AMBER:** At least one requirement expiring soon or pending (missing evidence).
- **RED:** At least one requirement overdue or expired.
- **Missing evidence:** Grey or “Pending” in requirements; user should upload evidence or set “not applicable.”

## 9. Common errors or confusing points
- **“Account must be provisioned”:** Client’s onboarding_status is not PROVISIONED; they cannot add properties until admin completes provisioning.
- **“Plan limit reached”:** Client is at maximum properties for their plan; they must upgrade or contact admin.
- **Nickname vs address:** Nickname is optional; if not set, address (or postcode/name) is used for display. Useful for “Property A” style labels.

## 10. Current limitations or known gaps
- Property edit/delete: Implemented in backend (`PATCH`, soft delete); exact UI (buttons, confirm) **needs runtime confirmation**.
- Bulk import: `/properties/import` exists (BulkPropertyImportPage); separate flow; not covered in this short manual.
- No “duplicate property” in base implementation.

## 11. Notes for training staff
- “Add Property first, then add or link requirements, then upload evidence.” Order matters for a clear workflow.
- When at plan limit, direct user to Billing or support for upgrade.
- Property status is derived from requirements; to fix RED/AMBER, user must fix requirements (upload evidence or update dates) on Compliance/Documents pages.

---

## Trainer walkthrough (5–10 minutes)

1. **Open Properties** → show list and stats (Total, Green, Amber, Red).
2. **Filter:** Click Amber → “Only properties that need attention.”
3. **Add Property:** Click Add Property → fill form (address, postcode, type) → Submit → show new property in list.
4. **Open a property** → show detail: address, status, requirements section, link to upload evidence.
5. **Explain status:** “Green = good; Amber = something due or missing; Red = overdue. Fix by uploading evidence or updating dates in Compliance/Documents.”
6. **Mention limit:** “If you hit ‘plan limit’ when adding a property, you’ve reached your plan’s maximum; see Billing to upgrade.”
