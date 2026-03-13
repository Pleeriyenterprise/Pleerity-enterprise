# Knowledge Centre Taxonomy and Import Guide

## 1. Suggested Knowledge Centre taxonomy

The existing Knowledge Centre already defines categories in `backend/routes/knowledge_base.py`. Use these **category_id** values when creating or importing articles.

### USER categories (Help Centre)

| category_id | name | Use for |
|-------------|------|--------|
| getting-started | Getting Started | First steps, overview. |
| adding-properties | Adding Properties | Add property, property list, property detail, alerts. |
| documents-uploads | Uploading Evidence | Upload certificates, document types, confirm details. |
| compliance-score | Compliance Score | Score meaning, drivers, export. |
| dashboard-guide | Dashboard Guide | Dashboard layout, score card, trend, checklist. |
| reminders | Reminders | How reminders work, notification preferences. |
| compliance-packs | Compliance Packs | Download packs (when confirmed). |
| billing-subscriptions | Billing | Plans, billing page, upgrade. |
| troubleshooting | Troubleshooting | Login, password reset, common errors. |

### ADMIN / STAFF categories

| category_id | name | Use for |
|-------------|------|--------|
| staff-training | Staff Training | Training articles for staff. |
| operations-playbooks | Operations Playbooks | Playbooks (recovery, failure response). |
| admin-console | Admin Console | Admin overview, navigation. |
| provisioning | Provisioning | Onboarding, setup status, provisioning. |
| compliance-engine | Compliance Engine | Requirements, scoring, obligations. |
| job-monitoring | Job Monitoring | Automation Centre, reminder jobs, Run Now. |
| feature-flags | Feature Flags | Feature controls, entitlements. |
| support-procedures | Support Procedures | Email failures, escalation, troubleshooting. |
| release-notes | Release Notes | Release note articles (article_type: release_notes). |

---

## 2. Audience mapping

| Audience | Who sees it | API / visibility |
|----------|-------------|-------------------|
| USER | Client portal Help Centre (`/help`); public KB if configured for USER-only | `GET /api/client/help/articles`; `GET /api/kb/articles` (USER filter). |
| STAFF | Admin Knowledge Centre (when staff read is implemented); internal only | Admin KB list; filter by audience STAFF. |
| ADMIN | Admin Knowledge Centre only; not shown in client Help | Admin KB list; all audiences. |

- **Internal/admin-only documentation must not be created as USER-facing.** Set `audience: ADMIN` or `audience: STAFF` for playbooks and staff training.
- Default for user help: `audience: USER`. Default for staff/playbooks: `audience: ADMIN` (or STAFF when supported).

---

## 3. Tags (suggested)

Use tags for search and filtering; keep them consistent.

**User help:** `getting started`, `properties`, `evidence`, `upload`, `compliance score`, `dashboard`, `reminders`, `billing`, `login`, `troubleshooting`, `compliance pack`, `gas safety`, `EICR`, `certificates`.

**Staff / playbooks:** `admin`, `provisioning`, `onboarding`, `automation`, `reminder job`, `email delivery`, `feature flags`, `playbook`, `recovery`, `support`, `compliance engine`, `evidence confirmation`, `scoring`.

---

## 4. How to import drafts (do not auto-publish)

### Option A: Manual create in Admin UI

1. Log in as admin → **Content Management → Knowledge Centre** (`/admin/knowledge-base`).
2. **New Article** for each draft.
3. Set **Audience** (USER / STAFF / ADMIN), **Category**, **Status = Draft**.
4. Paste title, excerpt, and content from the draft Markdown files in `drafts/`.
5. Add tags and save. **Do not** click Publish until review is done.

### Option B: Import script (recommended)

Run the script that reads draft Markdown from `docs/knowledge-centre-drafts/drafts/*.md` and inserts into `kb_articles` with **status = draft**:

```bash
cd backend && PYTHONPATH=. python -m scripts.import_kb_drafts
```

**Requirements:** MongoDB reachable (`MONGO_URL`, `DB_NAME` as for the app). The script uses the same database as the app; it does **not** call the HTTP API. It skips any slug that already exists and never sets `status: "published"`. Ensure default categories exist (run the app or seed_kb_articles once if the DB is fresh).

### Option C: Structured files only

Keep drafts in `docs/knowledge-centre-drafts/drafts/` as Markdown. Use them as the single source of truth; authors create or update articles in the Knowledge Centre manually from these files. No import script required.

---

## 5. Module name (product_module)

Optional field for linking docs to product areas. Suggested values:

- `Dashboard`, `Properties`, `Compliance`, `Evidence`, `Documents`, `Compliance Score`, `Reminders`, `Billing`, `Settings`, `Help Centre`
- `Admin Console`, `Provisioning`, `Automation`, `Job Monitoring`, `Feature Controls`, `Support`, `Knowledge Centre`

Use one per article where it helps.
