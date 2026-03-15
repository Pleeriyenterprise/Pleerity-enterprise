# Knowledge Centre – Admin review & publish (quick reference)

## What’s implemented vs what you see

| Item | Implemented | Why it looks empty / not clickable |
|------|-------------|------------------------------------|
| **Articles tab** | ✅ List, filters, New Article, Edit, Publish/Archive/Delete, PDF export | Empty until articles exist in DB. Data comes from MongoDB `kb_articles`, not from files. |
| **Categories tab** | ✅ Grid of category cards; Edit (modal), Delete | **Category cards are clickable** in current code: click switches to **Articles** tab and sets the category filter so you see articles in that category. If your build doesn’t do that, deploy latest `AdminKnowledgeBasePage.js`. |
| **Analytics tab** | ✅ Published/Total counts, Most Viewed, Top Searches, Searches with No Results | Shows 0 / “No data yet” until there are articles and (for some widgets) until users view or search. |
| **Help Assistant tab** | ✅ Search over **published** Knowledge Centre articles only | No results until at least one article is **published**. |

## Where the “training manuals” live

- **On disk (drafts):** `docs/knowledge-centre-drafts/drafts/*.md` — 6 articles (Getting Started, Dashboard Guide, Admin Console Overview, Monitor Reminder Jobs, Playbook Failed Provisioning, Release Note Template). These are **not** in the database until imported.
- **In the app:** Admin Knowledge Centre reads from MongoDB collection `kb_articles`. So drafts must be **imported** once to appear in the Articles tab for review and publish.

## Making drafts available for review and publish

1. **Run the import once** (uses your app’s MongoDB; ensure `backend/.env` has `MONGO_URL` and `DB_NAME`):
   ```bash
   cd backend && PYTHONPATH=. python -m scripts.import_kb_drafts
   ```
   - Idempotent: skips any slug that already exists.
   - All imported articles get **status = draft** (no auto-publish).
   - After this, the **Articles** tab and category article counts will show the imported drafts.

2. **In Admin → Knowledge Centre:**
   - Open **Articles** tab to see drafts (use filters: Status = Draft, or Category).
   - **Click a category card** in the Categories tab to open Articles tab filtered by that category.
   - Open each article (Edit), review, then click **Publish** when ready.
   - After publishing, **Help Assistant** and **Analytics** (views/searches) will start showing data.

## Empty tabs – what fills them, when and how

| Tab | What fills it | When / how |
|-----|----------------|-----------|
| **Articles** | Draft and published articles from `kb_articles` | Run `import_kb_drafts` once and/or create articles via “New Article”. |
| **Categories** | Categories are pre-defined; “X articles” per card | Backend provides categories; article count updates when articles exist in `kb_articles`. |
| **Analytics** | Published count, total count, view counts, search counts, “searches with no results” | After articles exist and (for views/searches) after users use Help Centre / Help Assistant. |
| **Help Assistant** | Search results from **published** articles only | After you publish at least one article; then admin (and optionally user) search returns those articles. |

## Conflicting instructions

- **None.** Docs and code agree: drafts live in `drafts/*.md`; import via script with `status = draft`; admin reviews and publishes in the UI. Do not auto-import on startup (to avoid overwrite/duplication).

## Safe approach

- Run the import script **once** per environment (dev/staging/prod) when you want the drafted training manuals available in Knowledge Centre.
- After import, use only the Admin UI to review, edit, and publish. No need to redraft the manuals; they are already in `docs/knowledge-centre-drafts/drafts/`.
