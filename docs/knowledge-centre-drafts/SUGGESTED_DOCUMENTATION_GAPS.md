# Suggested Documentation Gaps

Areas where the product exists but documentation still needs manual input or verification before publication.

---

## 1. Product exists; docs need manual input

| Area | Gap | Suggestion |
|------|-----|------------|
| **Calendar** | No draft article in Priority 1–3. Calendar page exists; user may need “How to use the Calendar” or what events are shown. | Add USER article: Calendar Guide (category calendar if exists, else dashboard-guide or new). |
| **Reports** | Reports page exists; no dedicated “How to run or download reports” article. | Add USER article: Reports and exports; confirm what reports are available. |
| **Assistant** | Assistant page exists; no Help article for “How to use the Assistant.” | Add USER article: Assistant guide; verify behaviour (e.g. prompts, context). |
| **Tenant portal** | Tenant routes and TenantDashboard exist (feature-gated). No tenant-specific help. | Add USER article for tenant users: Tenant portal overview (audience USER, or separate tenant audience if supported). |
| **Operations (Issues, Work orders, Contractors, Risk signals, Approvals)** | All feature-gated; no per-module help articles. | Add short articles per area when prioritised (e.g. “Work orders”, “Risk signals”); label as “if available on your plan.” |
| **Bulk upload** | `/documents/bulk-upload` exists; no dedicated “Bulk upload evidence” article. | Add USER article: Bulk upload guide; verify flow and limits. |
| **Integrations / Webhooks** | Page exists (feature-gated). No help article. | Add USER article when prioritised; confirm what integrations are available. |
| **Audit log** | Client audit log page exists; no “What is the audit log” article. | Add short USER article if users ask what it shows. |
| **ClearForm** | Separate product; admin ClearForm section. | Keep ClearForm docs separate; do not mix with main platform Help unless intentional. |

---

## 2. Admin docs that need expansion

| Area | Gap |
|------|-----|
| **Intake Schema** | No staff article for “How to configure intake schema.” Add if admins need it. |
| **Service Catalogue** | No staff article for managing the catalogue. Add if prioritised. |
| **Canned Responses** | No playbook or procedure for when to use which response. |
| **Notification Health** | Draft “How to Review Email Failures” touches this; may need a dedicated “Notification Health dashboard” article. |
| **System Health vs Automation Centre** | Clarify in one article when to use System Health vs Automation Centre. |
| **Incidents** | When to acknowledge vs resolve; when to create manually (if supported). |

---

## 3. Release notes

- **Release note template** is in the inventory; no version-specific release note content. Add version-specific articles (e.g. “Version 1.3”) as releases happen; use article_type `release_notes` and fields release_version, release_date, changes, affected_modules.

---

## 4. Localisation and accessibility

- No guidance in drafts for translated or accessibility-focused content. Consider adding “Needs verification” for any future multi-language or accessibility docs.

---

## 5. Maintenance

- When new routes or features ship, add them to the Documentation Inventory and create or update drafts; run accuracy checks against ACCURACY_WARNINGS.md before publishing.
