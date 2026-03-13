# Admin Console – Training Manual

## 1. Module name
**Admin Console** (full structure and navigation)

## 2. Audience
**Admin / internal staff only.** This is the entire admin application after login.

## 3. Purpose
Single reference for where to find every major admin function: dashboard, customers, products & services, operations & compliance, ClearForm, content, support, and settings. Use this for onboarding new admins and for “where do I do X?” answers.

## 4. Where to find it in the UI
- **Entry:** Log in at `/login/admin` or `/admin/signin` → land on admin app.
- **Layout:** Sidebar (UnifiedAdminLayout) with sections; each section has a label and list of links. Main content area shows the selected page.

## 5. What the user sees (navigation structure)

From the codebase, the admin sidebar includes:

| Section | Label | Example items (routes) |
|---------|--------|-------------------------|
| **Dashboard** | Dashboard | Overview (`/admin/dashboard`), Analytics (`/admin/analytics`), Executive Overview (`/admin/analytics/executive`), Reporting (`/admin/reporting`) |
| **Customers** | Customers | Lead Management (`/admin/leads`), Risk Check Leads (`/admin/risk-leads`), Talent Pool, Partnership Enquiries, Contact Enquiries, Clients (tab on dashboard), Orders Pipeline (`/admin/orders`) |
| **Products & Services** | Products & Services | Service Catalogue (`/admin/services`), Intake Schema (`/admin/intake-schema`), Pricing & Billing (`/admin/billing`), Pending Payments |
| **Operations & Compliance** | Operations & Compliance | Overview (`/admin/ops`), Compliance (`/admin/ops/compliance`), Maintenance (`/admin/ops/maintenance`), Contractors (`/admin/ops/contractors`), Risk & Insights, Audit & Logs, Feature Controls (`/admin/ops/feature-controls`) |
| **ClearForm** | ClearForm | ClearForm Users, Document Management, Organizations, Document Types, Audit Logs |
| **Content Management** | Content Management | Site Builder (`/admin/site-builder`), Knowledge Centre (`/admin/knowledge-base`), Blog/Insights, FAQ Management, Insights Feedback, Canned Responses, Legal Pages, Newsletter |
| **Support** | Support | Support Dashboard (`/admin/support`), Postal Tracking |
| **Settings & System** | Settings & System | Team Permissions (`/admin/team`), Prompt Manager (`/admin/prompts`), Enablement Engine (`/admin/enablement`), Privacy & Consent, Automation Rules (tab on dashboard), Email Templates (tab), Email delivery (tab), Notification Health (`/admin/notification-health`), System Health (`/admin/system-health`), Automation Centre (`/admin/automation`), Incidents (`/admin/incidents`), Knowledge Centre (duplicate link in Content) |

*Some items are owner/admin-only (e.g. Analytics, Executive Overview, Operations & Compliance). Exact labels and order should be confirmed at runtime.*

## 6. Step-by-step actions (navigation)
| Goal | Action |
|------|--------|
| Find a client | Dashboard → Overview (or Customers) → use global search or Clients tab. |
| Manage leads | Customers → Lead Management. |
| Change billing or plans | Products & Services → Pricing & Billing (or Pending Payments). |
| View compliance across clients | Operations & Compliance → Compliance. |
| Manage automation jobs | Settings & System → Automation Centre (or System Health). |
| Edit help content | Content Management → Knowledge Centre. |
| Check notification/email health | Settings & System → Notification Health or Email delivery (tab). |
| Manage team/permissions | Settings & System → Team Permissions. |

## 7. What happens after each action
- Clicking a sidebar link navigates to that route; the corresponding page loads (e.g. AdminDashboard, AdminAutomationCentrePage, AdminKnowledgeBasePage).
- Tabs on the dashboard (Rules, Templates, Email delivery) switch in-page content without changing the URL in some implementations.

## 8. Status/outcome examples
- **403 or hidden section:** User role may not have access (e.g. owner/admin-only sections). Redirect or empty state may appear.
- **Page not found:** Route may have changed or be feature-flagged; confirm with dev or config.

## 9. Common errors or confusing points
- **Two “Knowledge Centre” links:** One under Content Management, one possibly under Settings; both typically go to `/admin/knowledge-base`. Use either.
- **Rules / Templates / Email delivery:** These are tabs on the main dashboard, not separate sidebar pages. “Automation Rules” and “Email Templates” in the sidebar may open the dashboard with that tab selected (tabTarget).
- **ClearForm:** Separate product; its admin section is for ClearForm-specific config (users, documents, orgs). Don’t confuse with main platform Documents/Evidence.

## 10. Current limitations or known gaps
- Some links may open the same dashboard with a `tabTarget` query or state; **needs runtime confirmation** for which items are tabs vs separate pages.
- Not all sections may be fully implemented (e.g. some Ops pages may be placeholder). See TRAINING_GAP_ANALYSIS.md.
- Role-based visibility: owner/admin-only sections hide or restrict for other roles; exact matrix should be confirmed.

## 11. Notes for training staff
- Use this manual as the “map” for new admins: “If you need to do X, go to section Y → link Z.”
- Demo one path from each section (e.g. Dashboard → search client; Content → Knowledge Centre; Settings → Automation Centre) so they see the pattern.
- Mention that some menu items are for “owner or admin only” so they don’t worry if they don’t see everything.

---

## Trainer walkthrough (5–10 minutes)

1. **Log in as admin** → show sidebar. “This is the whole admin console.”
2. **Name each section** (Dashboard, Customers, Products & Services, Ops, ClearForm, Content, Support, Settings).
3. **Demo 3–4 common tasks:**  
   - “Find a client” → Dashboard → search.  
   - “Check automation” → Settings → Automation Centre (or System Health).  
   - “Edit help articles” → Content → Knowledge Centre.  
   - “Billing” → Products & Services → Pricing & Billing.
4. **Mention tabs:** “Some things like Rules and Email Templates are tabs on the main dashboard, not separate menu items.”
5. **Q&A:** “Where would you go to…?” (answer using this map.)
