# Making the Assistant More Intelligent, System-Aware, and Current

**Goal:** Make the in-portal Pleerity Assistant very intelligent, system-aware, up-to-date, able to explain scoring (and score drops/increases), and able to answer questions from the website using the website as part of its knowledge base.

**Approach:** Options only; no implementation. Safest path is to extend existing patterns (KB + portal context) and avoid new frameworks or duplicate systems.

---

## 1. Current state (brief)

- **Context:** Assistant receives `portal_facts` (user, account_state, portfolio_summary with scores, properties, requirements, documents), `portal_urls`, and `kb_snippets` from `backend/docs/assistant_kb/*.md`. No live score explanation or trend data is injected into the assistant context.
- **KB:** Static markdown under `assistant_kb/` (e.g. `how_scoring_works.md` is short and generic). No CMS/website content.
- **Scoring:** Backend has rich logic: `compliance_score.py` (weights, breakdown: status_score, expiry_score, document_score, overdue_penalty_score, risk_score), `compliance_trending.py` (history, trend, `get_score_change_explanation`), and client API `GET /api/client/compliance-score/explanation` (property-level breakdown + key_reasons, or trend comparison). The assistant does **not** call these; it only sees `portfolio_summary.score_portfolio` and `scores_by_property` plus requirements/documents.

---

## 2. Making the assistant “very intelligent and system-aware”

**Already in place:** Portal context (user, account_state, portfolio_summary, properties, requirements, documents), portal_urls, KB snippets, strict safety rules, JSON response format.

**Gaps and options:**

| Gap | Option A (minimal) | Option B (richer) |
|-----|--------------------|--------------------|
| **Richer KB** | Expand `assistant_kb/*.md` with detailed, curated content (scoring, workflows, glossary). | Same + optional “dynamic facts” fetched per query (e.g. one-off explanation API). |
| **System awareness** | Add a small “system facts” block in context (e.g. “Scoring uses status, expiry, document coverage, overdue penalty, risk; weights vary by requirement type”). | Expose structured “how we score” summary from `compliance_score.py` / docs into context (no new API; build a short text summary in retrieval). |
| **Staying current** | KB is file-based: update markdown when product or scoring changes; consider a simple “last updated” or version in prompt. | Same; optional: admin-only “KB refresh” that re-indexes or invalidates cache so new content is picked up without deploy. |

**Recommendation:** Enrich the KB (especially scoring and workflows) and add a **scoring summary** (and optionally score-change explanation) into the context the assistant receives (see section 3). No new product; extend existing retrieval + prompt.

---

## 3. Explaining how scoring works and why a score dropped or increased

**Existing backend (unchanged):**

- **How it works:** `compliance_score.py` documents the model (weights, breakdown components). Client endpoint `GET /api/client/compliance-score/explanation?property_id=...` returns `breakdown_summary` and `key_reasons` (e.g. “Some requirements not yet compliant”, “Upcoming or past expiries”, “Overdue items reducing the score”).
- **Why it changed:** `compliance_trending.get_score_change_explanation(client_id, compare_days)` returns `explanation` text and `changes` (what got better/worse).

**Ways to make the assistant explain scoring and changes:**

1. **KB only (no new API)**  
   - Expand `how_scoring_works.md` (and optionally a new `score_changes.md`) with:  
     - How the score is built (status, expiry, document, overdue penalty, risk; requirement-type weights; HMO multiplier).  
     - Typical reasons for a drop (e.g. new overdue, expiry passed, document removed) or increase (e.g. document uploaded, requirement satisfied).  
   - Assistant uses this plus existing `portfolio_summary` (scores, expiring_soon_count, compliant_count, overdue_requirements_count) to answer.  
   - **Pros:** Simple, no new APIs, no PII in KB. **Cons:** No client-specific “your score dropped because X requirement went overdue”; only generic explanations.

2. **Inject score explanation into context (recommended)**  
   - In `get_portal_facts()` (or a dedicated “assistant context” builder), for the current client:  
     - Call the **same logic** as the client explanation (or call an internal helper that returns property-level breakdown + key_reasons and, if available, a short trend summary).  
     - Do **not** expose a new public API; keep it server-side only.  
   - Add to the payload passed to the LLM a short **score_explanation** (or **score_context**) block, e.g.:  
     - Per property: “Property X: score 72; key reasons: [list from key_reasons].”  
     - Optional: “Compared to 7 days ago: [one sentence from get_score_change_explanation].”  
   - Assistant prompt already says “use only portal context”; add one line: “Use score_explanation / score_context to explain why a score is what it is or why it changed.”  
   - **Pros:** Assistant can say “your score dropped because…” in a system-aware way. **Cons:** Slightly more data in context and one more code path to keep in sync with scoring.

3. **Assistant calls an “explanation” API**  
   - New endpoint, e.g. `GET /api/assistant/score-explanation` (or reuse client explanation behind auth), returns text summary. Assistant is instructed to “call this when the user asks why their score changed”.  
   - **Cons:** Current assistant is single-turn (no tool-calling); adding tools is a larger change. Prefer (2) for minimal change.

**Recommendation:** Combine (1) and (2): expand the KB for “how scoring works” and “typical reasons for score changes,” and **inject a concise score_explanation / score_context** (per property + optional trend) into the assistant context so it can explain both how scoring works and why a score dropped or increased for this user.

---

## 4. Using the website as part of the knowledge base

**Clarification:** “Website” can mean:

- **A) Public marketing/CMS site** (e.g. pleerity.com): content in `cms_pages` (slug, title, blocks/sections); served via `get_published_page(slug)` / `GET /public/cms/pages/{slug}`.  
- **B) The portal app itself** (Compliance Vault Pro): UI copy, help text, feature descriptions. Usually in frontend code or a separate content store.

**Ways to use “website” (e.g. marketing CMS) as KB:**

1. **Curated export (no live CMS dependency)**  
   - Periodically (or on publish) export published CMS content to markdown (or JSON) and drop it into `assistant_kb/` (e.g. `website_services.md`, `website_faq.md`).  
   - Assistant already loads all `*.md` from KB; no code change except the export job and file placement.  
   - **Pros:** Simple, no runtime dependency on CMS, versioned with app. **Cons:** Not real-time; need a job or manual step to refresh.

2. **Live CMS in retrieval**  
   - In `assistant_retrieval_service`, when building context, query `cms_pages` for published pages (or a subset by tag/slug).  
   - Convert title + body (e.g. first N chars per page) into a “website_snippets” or “public_site” section and append to the context string (or merge into the same snippet list with a source_id like `cms_page:slug`).  
   - **Pros:** Always current with published content. **Cons:** More context length; need to limit and sanitize (no internal-only or draft content).

3. **Hybrid**  
   - Use (1) for stable “about us / services / compliance” pages and (2) only for a small set of “FAQ” or “latest offers” slugs that change often.  
   - Or: only (1) and refresh the export when marketing publishes major changes.

**Recommendation:** Start with (1): export published CMS content into `assistant_kb/` so the assistant can answer questions from the website without new frameworks. Add (2) later only if you need answers to change as soon as content is published.

**Portal app (B):** If “website” includes in-portal copy (e.g. “What does the Reports page do?”), that’s best handled by adding or expanding KB articles that describe those features and linking to portal_urls; no need to scrape the SPA.

---

## 5. Keeping the assistant “very current”

- **Scoring logic:** Document changes (e.g. new weights, new breakdown) in the KB and, if you add score_explanation to context, ensure the code that builds that explanation uses the same logic as the live score (single source of truth in `compliance_score` / `compliance_scoring_service`).
- **Product/portal changes:** When you add a new page or workflow, add or update the relevant `assistant_kb/*.md` and, if needed, extend `portal_urls` in `assistant_prompt.get_portal_urls()`.
- **CMS/website:** If you use the “export to KB” approach, run the export after meaningful CMS publishes (or on a schedule). If you use live CMS snippets, they are current by definition.
- **Prompt:** The system prompt is in code; any change to rules or structure is a deploy. Optional: store a “prompt version” or “KB version” in context so support can see which set of rules was used for a given reply.

---

## 6. Summary: safest implementation order

1. **Expand KB**  
   - Richer `how_scoring_works.md` (and optional `score_changes.md`) describing the model and typical reasons for score up/down.  
   - No API or context shape change.

2. **Inject score explanation into context**  
   - In retrieval (or chat service), for the current client, build a short **score_explanation** (per-property breakdown + key_reasons; optional trend sentence from `get_score_change_explanation`).  
   - Add this to the payload sent to the LLM and one line in the system prompt: use it to explain “how scoring works” and “why my score dropped/increased.”  
   - Reuse existing scoring/explanation logic; no new public API.

3. **Website as KB**  
   - Add a process (script or admin action) that exports published CMS content to markdown under `assistant_kb/` (e.g. by slug or category).  
   - Assistant automatically picks it up via existing KB load.  
   - Optionally later: add a small “live CMS” slice in retrieval for a few frequently updated slugs.

4. **Staying current**  
   - Document in your runbook or admin docs: when scoring or product changes, update KB and (if applicable) the score_explanation builder.  
   - If you add CMS export, tie it to publish events or a scheduled job.

**Implementation (done):**
- KB: Expanded `how_scoring_works.md` and added `score_changes.md`.
- Context: `get_portal_facts()` now includes `score_explanation` (per-property key reasons + optional trend from `get_score_change_explanation`). System prompt updated to use it.
- Website as KB: Script `backend/scripts/export_cms_to_kb.py` exports published CMS pages to `assistant_kb/website_<slug>.md`. Run after CMS publishes or on a schedule.
- Staying current: When scoring or product changes, update the KB markdown and ensure the daily compliance snapshot job runs so trend explanation is available. Run `python backend/scripts/export_cms_to_kb.py` after meaningful CMS publishes.

This keeps a single assistant, no new frameworks, no duplication of scoring logic, and avoids exposing internal APIs. The assistant remains JSON-based and safe (no legal verdicts, no fabricated URLs); it just gets better, system-aware, and up-to-date context and KB.
