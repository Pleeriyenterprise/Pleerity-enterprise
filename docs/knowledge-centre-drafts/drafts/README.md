# Draft Knowledge Centre Articles

These Markdown files are **first-draft** articles for the Knowledge Centre. They follow the task template (Title, Audience, Category, Module, Summary, Purpose, When to use, Steps, What happens next, Common mistakes, Related guides, Verification status).

## Usage

- **Do not auto-publish.** All drafts are intended to be created in the Knowledge Centre with **status = draft**.
- **Import via script (safest):** From the repo, with MongoDB available (e.g. `MONGO_URL` and `DB_NAME` set, or same env as the app), run:
  ```bash
  cd backend && PYTHONPATH=. python -m scripts.import_kb_drafts
  ```
  The script creates each draft as an article with **status = draft**, and skips any slug that already exists. It does not publish.
- **Import manually:** In Admin → Knowledge Centre → New Article, set Audience and Category from the frontmatter, set Status to **Draft**, then paste the body (from "Purpose" through "Verification status"). Use the slug in frontmatter as the article slug.
- **YAML frontmatter** (at the top of each file) provides: `title`, `slug`, `audience`, `category_id`, `module`, `tags`, `status`. Use these when creating the article via the API or UI.
- **Excerpt:** For API import, use the first paragraph under "Summary" in the body, or a 1–2 sentence summary (max 500 characters), as the `excerpt` field.
- **Conflict with seed:** The seed script (`backend/scripts/seed_kb_articles.py`) creates four **published** USER articles (uploading-evidence, adding-a-property, compliance-score-explained, reminders-and-alerts). These drafts use **different slugs** (getting-started, dashboard-guide, admin-console-overview, monitor-reminder-jobs, playbook-failed-provisioning, release-note-template) so they do not overwrite existing content. When importing, if your KC already has an article with the same slug, skip or use a variant slug (e.g. add `-v2`).

## Files

| File | Slug | Audience | Category |
|------|------|----------|----------|
| 01-getting-started.md | getting-started | USER | getting-started |
| 02-dashboard-guide.md | dashboard-guide | USER | dashboard-guide |
| 03-admin-console-overview.md | admin-console-overview | ADMIN | admin-console |
| 04-monitor-reminder-jobs.md | monitor-reminder-jobs | ADMIN | job-monitoring |
| 05-playbook-failed-provisioning.md | playbook-failed-provisioning | ADMIN | operations-playbooks |
| 06-release-note-template.md | release-note-template | ADMIN | release-notes |

## Verification

Each draft ends with **Verification status: Draft. Needs product review.** Review against `../ACCURACY_WARNINGS.md` before publishing.
