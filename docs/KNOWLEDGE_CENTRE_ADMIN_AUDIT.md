# Knowledge Centre – Admin review & publish audit

**Purpose:** Clarify what is implemented, what is missing, why tabs are empty, and how to make training manuals available for admin to review and publish. No duplicate or conflicting behaviour.

---

## 1. What is implemented

| Area | Implementation |
|------|----------------|
| **Admin Knowledge Centre** | `/admin/knowledge-base` – Articles, Categories, Analytics, Help Assistant tabs. |
| **Articles tab** | List from `kb_articles` with search + filters (status, audience, category). Create/Edit/Publish/Unpublish/Archive/Delete, PDF export. Empty state: "No articles found" + "Create your first article". |
| **Categories tab** | Grid of category cards (name, icon, description, article count, order). Each card has **Edit** and **Delete** buttons. The card body is **not** clickable to show articles (see §4). |
| **Analytics tab** | Published count, total articles, searches (30d), Most Viewed, Top Searches, Searches with No Results. Data comes from `kb_articles` and `kb_search_analytics`. |
| **Help Assistant tab** | Search over **published** Knowledge Centre articles only (USER + STAFF + ADMIN). Answers from documentation only. |
| **Draft training manuals** | Exist as **Markdown files** in `docs/knowledge-centre-drafts/drafts/`: `01-getting-started.md` … `06-release-note-template.md` (see README there). They are **not** in the database until imported. |
| **Import script** | `backend/scripts/import_kb_drafts.py` reads those `.md` files and inserts into `kb_articles` with **status = draft**. Idempotent by slug (skips if slug exists). Does **not** publish. |

---

## 2. Why training manuals are not available for admin to review and publish

- The **drafts are on disk only** (`docs/knowledge-centre-drafts/drafts/*.md`). The Knowledge Centre UI reads from **MongoDB** (`kb_articles`).
- **Nothing in the UI or app startup imports these drafts.** The only way to get them into the KC is to run the import script (or create articles manually).
- So: until `import_kb_drafts` has been run (or articles created by hand), the Articles tab is empty and there is nothing for admin to review or publish.

**No conflict:** The task and docs say "do not auto-publish"; the script sets `status = draft` and does not publish. Running it is the intended way to make drafts available in the KC.

---

## 3. Why the tabs are empty and what fills them

| Tab | Why it’s empty | What fills it | When / how |
|-----|----------------|---------------|------------|
| **Articles** | No documents in `kb_articles` (drafts never imported, or no manual creation). | Articles (draft or published) in `kb_articles`. | **When:** Run `backend/scripts/import_kb_drafts` once (with MongoDB reachable), or create articles via "New Article". **How:** From repo: `cd backend && PYTHONPATH=. python -m scripts.import_kb_drafts`. There is no "Import drafts" button in the UI. |
| **Categories** | Categories are **not** empty; they come from backend defaults (`knowledge_base.py`). Each card shows **article_count** (number of articles in that category). So "0 articles" is correct until articles exist. | Article count per category is computed from `kb_articles`. | After articles exist (import or create), counts appear. |
| **Analytics** | "0 Published", "0 Total", "No data yet" – no articles and no search events. | Published articles and usage (views, searches). | After articles exist and some are **published**, and after clients/staff use Help search, analytics and "Most Viewed" / "Top Searches" populate. |
| **Help Assistant** | "Search published Knowledge Centre articles" – no results until there are **published** articles. | Published articles in `kb_articles`. | After import (or create), admin reviews and **publishes** articles; then Help Assistant can return them. |

**Order of operations:** (1) Run import script (or create articles) → Articles tab and category counts fill. (2) Admin reviews drafts in Articles tab and clicks Publish where appropriate. (3) Analytics and Help Assistant then have content/data.

---

## 4. Category blocks: should they show draft content when clicked?

- **Current behaviour:** Only the **Edit** icon opens the category edit modal. The category card itself does nothing when clicked.
- **Desired behaviour (your requirement):** Clicking a category block should show the content for that category – i.e. the list of articles (including drafts) in that category so admin can review and publish.
- **Safest implementation (no conflict):** Make the **category card** (the main body, not the Edit/Delete buttons) **clickable**: on click, switch to the **Articles** tab and set the **category filter** to that category. Result: admin sees all articles in that category (draft + published), can open each to review and publish. Edit/Delete on the category card still only edit/delete the category.

**Implementation status:** Implemented: clicking the category card (main content area) switches to the Articles tab and sets the category filter to that category; Edit/Delete buttons use stopPropagation so they still open the modal or delete. Card has cursor-pointer and role="button" for accessibility.

---

## 5. Conflicting instructions?

- **None found.** The codebase and docs agree: drafts in `drafts/*.md`, import via script with `status = draft`, do not auto-publish; admin reviews and publishes in the UI.
- **Recommendation:** Do **not** add an automatic import on app startup (could overwrite or duplicate if slugs change). Keep the explicit "run script once" (or document it for ops) and optional future "Import drafts" admin button that calls a dedicated API if you add one.

---

## 6. Summary: make training manuals available for review and publish

1. **Run the import script once** (with the app’s MongoDB env):
   ```bash
   cd backend && PYTHONPATH=. python -m scripts.import_kb_drafts
   ```
   This creates draft articles from `docs/knowledge-centre-drafts/drafts/*.md` in `kb_articles`. All have `status = draft`.

2. **In Admin → Knowledge Centre:**  
   - **Articles** tab will list the imported drafts (and any manually created ones).  
   - **Categories** tab will show correct article counts per category.  
   - Click a **category card** (after the change in §4) to open Articles filtered by that category; open each article to review and click **Publish** when ready.

3. **Analytics and Help Assistant** will start to show data once articles are published and users perform searches or views.

No need to "draft" the training manuals again – they are already drafted in `docs/knowledge-centre-drafts/drafts/`. Import makes them visible in the KC for review and publish.
