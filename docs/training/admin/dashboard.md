# Admin Dashboard – Training Manual

## 1. Module name
**Admin Dashboard** (Overview)

## 2. Audience
**Admin / internal staff only.** Not visible to client users.

## 3. Purpose
Central landing page for admins after login. Provides quick access to clients, global search, and tabs for Clients, Automation Rules, Email Templates, Email delivery, and other configuration. Used to find and open client records and to manage system-wide settings from one place.

## 4. Where to find it in the UI
- **URL:** `/admin/dashboard`
- **Navigation:** After logging in at `/login/admin` (or `/admin/signin`), the default landing can be the dashboard. Sidebar: **Dashboard → Overview**.

## 5. What the user sees on the page
- **Header** with global search (client search).
- **Tabs** (implementation-dependent; from codebase): e.g. **Clients**, **Rules**, **Templates**, **Email delivery**, and possibly others. Each tab shows different content (client list, automation rules, email templates, delivery/health).
- **Client list / search results:** When searching or on the Clients tab, admins see client records (e.g. name, email, status, client_id). Clicking a client may open client detail or switch context to that client.
- **Quick actions** (if present): e.g. resend invite, set password, view in portal.
- **Stats or summary cards** (if implemented): e.g. total clients, recent sign-ups.

*Exact layout and tab order should be confirmed at runtime; the codebase uses a single AdminDashboard component with multiple tabs/sections.*

## 6. Step-by-step actions the user can take

| Action | What to click | What happens |
|--------|----------------|--------------|
| Search for a client | Type in global search (min 2 characters) | Backend: `GET /admin/search?q=...&limit=10`. Results show matching clients; selecting one may navigate or set context. |
| View client list | Open or stay on **Clients** tab | Client list loads (source: admin dashboard data). List may be paginated or filterable. |
| Open a client | Click a client row or “View” | Navigates to client detail or dashboard with that client in context (exact behaviour is implementation-specific). |
| Manage automation rules | Open **Rules** tab | Shows automation rules (if implemented). Editable or view-only depending on implementation. |
| Manage email templates | Open **Templates** tab | Shows email templates list. Admin can edit templates (implementation-specific). |
| Check email delivery | Open **Email delivery** tab | Shows delivery/health or logs related to email (e.g. from notification health). |

## 7. What happens after each action
- **Search:** Results appear in a dropdown or panel; selecting a result typically navigates or loads that client.
- **Tab switch:** Content for that tab loads (clients, rules, templates, or email delivery). Data is fetched from admin API endpoints.
- **Client open:** Admin can then perform client-specific actions (billing, provisioning, view as client, etc.) depending on routes and permissions.

## 8. Status/outcome examples
- **Search returns no results:** User sees empty state; refine query or confirm client exists and is searchable.
- **Tab shows empty list:** No records for that section (e.g. no rules, no templates) or API error; check network and permissions.
- **403 on an action:** Insufficient role; some tabs or actions may be owner/admin-only.

## 9. Common errors or confusing points
- **Too many tabs:** New admins may not know which tab to use. Training: “Clients = find/open clients; Rules = automation; Templates = email content; Email delivery = delivery health.”
- **Search scope:** Search is client-focused (name/email/etc.); it does not search KB or other content. Clarify in training.
- **Dashboard vs other admin pages:** “Overview” is the main dashboard; Analytics, Reporting, etc. are under Dashboard submenu but separate pages.

## 10. Current limitations or known gaps
- Exact tab set and order may vary; **needs runtime confirmation**.
- Some sections (e.g. Rules, Templates) may be placeholder or partially implemented; verify in environment.
- No in-app guided tour; use this manual for “first look” training.

## 11. Notes for training staff
- Use the dashboard as the “home base” for admin: “Start here to find a client or change system settings.”
- Demonstrate search with a real client name; then show one tab (e.g. Clients) and where to go next (e.g. client detail, billing).
- If Email delivery or Notification Health is in use, show where to check for delivery issues.

---

## Trainer walkthrough (5–10 minutes)

1. **Log in as admin** → land on `/admin/dashboard`.
2. **Point out the sidebar** → Dashboard → Overview is this page.
3. **Global search:** Type part of a client name → show results → click one → show what opens (client context or page).
4. **Tabs:** Switch to Clients tab → explain “this is the client list.” Optionally open Rules/Templates/Email delivery and say one sentence each (what they’re for).
5. **Next steps:** “To manage a specific client’s billing or properties, open the client from here or from Customers → Lead Management / Clients.”
6. **Q&A:** “Where do you go to resend a client invite?” (Usually from client detail or support dashboard; confirm in your build.)
