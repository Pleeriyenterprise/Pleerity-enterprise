# Knowledge Centre – Task vs codebase status

**Purpose:** Align task requirements with actual implementation. No conflicting instructions; one gap (category card click) is fixed in code.

---

## 1. Implemented vs missing

| Requirement | Status | Notes |
|-------------|--------|--------|
| Admin Knowledge Centre at `/admin/knowledge-base` | ✅ Implemented | Articles, Categories, Analytics, Help Assistant tabs. |
| Articles tab: list, filters, Create/Edit/Publish/Archive/Delete, PDF export | ✅ Implemented | Reads from `kb_articles`. Empty until articles exist. |
| Categories tab: grid of category cards, Edit/Delete | ✅ Implemented | Categories from backend; article count from `kb_articles`. |
| **Category card click → show articles in that category** | ❌ Was missing, now fixed | Card click switches to Articles tab and sets category filter; Edit/Delete unchanged. |
| Analytics tab: Published/Total, Most Viewed, Top Searches, Searches with No Results | ✅ Implemented | Data from `kb_articles` and analytics; shows 0 / "No data" until content exists. |
| Help Assistant tab: search published articles | ✅ Implemented | Returns results only from **published** articles. |
| Training manuals as drafts | ✅ On disk only | `docs/knowledge-centre-drafts/drafts/*.md` (6 articles). **Not in DB** until import. |
| Import script for drafts | ✅ Implemented | `backend/scripts/import_kb_drafts.py` – inserts into `kb_articles` with `status=draft`. No UI button. |

---

## 2. Why training manuals are not visible for review/publish

- Drafts live in **files**: `docs/knowledge-centre-drafts/drafts/01-getting-started.md` … `06-release-note-template.md`.
- The Knowledge Centre UI reads **MongoDB** (`kb_articles`). Nothing in the app imports those files automatically.
- So until the import script is run (or articles are created manually), the Articles tab is empty and there is nothing to review or publish.

**No conflict:** Docs and script say “do not auto-publish”; the script sets `status = draft`. Running it is the intended way to get drafts into the KC.

---

## 3. Why tabs look empty and what fills them

| Tab | Why it looks empty | What fills it | When / how |
|-----|--------------------|---------------|------------|
| **Articles** | No documents in `kb_articles` | Draft/published articles | Run `backend/scripts/import_kb_drafts` once (with app MongoDB), or create via “New Article”. |
| **Categories** | Categories exist; “0 articles” per card | Article count per category | After articles exist (import or create), counts update. |
| **Analytics** | No articles, no search events | Published count, views, searches | After articles exist, some are published, and users search/view. |
| **Help Assistant** | No published articles | Published articles only | After import (or create), admin publishes articles; then search returns them. |

**Order:** (1) Run import script → Articles tab and category counts get data. (2) In Articles tab, review drafts and click Publish. (3) Analytics and Help Assistant then get data as articles are published and used.

---

## 4. Conflicting instructions

- **None.** Codebase and docs agree: drafts in `drafts/*.md`, import via script with `status = draft`, no auto-publish; admin reviews and publishes in the UI.
- **Recommendation:** Do not add automatic import on startup (risk of overwrite/duplication). Keep one-time script run (and document for ops). An optional “Import drafts” admin button could call a dedicated API later if added.

---

## 5. Making training manuals available for review and publish

1. **Run the import once** (using the app’s MongoDB):
   ```bash
   cd backend && PYTHONPATH=. python -m scripts.import_kb_drafts
   ```
   This creates draft articles from `docs/knowledge-centre-drafts/drafts/*.md` in `kb_articles` with `status = draft`.

2. **In Admin → Knowledge Centre:**
   - **Articles** tab lists the imported drafts (and any manual ones).
   - **Categories** tab shows article counts per category.
   - **Click a category card** to open the Articles tab filtered by that category; open each article to review and click **Publish** when ready.

3. **Analytics and Help Assistant** start showing data once articles are published and users perform searches or views.

The training manuals are already drafted in `docs/knowledge-centre-drafts/drafts/`. Import makes them visible in the KC for review and publish; no need to redraft.
