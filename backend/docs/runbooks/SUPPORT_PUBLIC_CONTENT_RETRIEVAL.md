# Public support content retrieval (Knowledge Centre + allowlisted site)

## Purpose

The public website support assistant (`POST /api/support/chat`) answers from **indexed** content in MongoDB collection **`support_public_content_chunks`**, not from live HTTP crawls on each message.

## Source priority (editorial + technical truth)

1. **Registries (authoritative for prices and catalogue facts)** — `plan_registry`, `pack_registry`, `SERVICE_BASE_PRICES` — injected via `support_assistant_catalog` / existing support prompts. Marketing or KC prose must **not** override these figures.
2. **Knowledge Centre — published `audience=USER` articles** — primary editorial truth for long-form help (`source_type: kb_article`).
3. **Allowlisted marketing routes** — secondary context (`source_type: site_page`). Sync only via admin reindex or scheduled job, **never per chat turn**.
4. **Legacy static Q&A** (`support_chatbot_knowledge` keyword retrieval) — fallback until migrated.
5. **LLM summarisation** — only when no strong match; must not invent facts beyond approved JSON + retrieved excerpts.

## Audience isolation

- Only **`status=published`**, **`is_active=true`**, **`audience=USER`** (explicit; no “missing audience” rows) are indexed for public support.
- **STAFF** and **ADMIN** articles must **never** appear in `support_public_content_chunks` for this pipeline.

## Reindexing

| Trigger | Behaviour |
|--------|------------|
| KB article **publish / update / unpublish / archive / deactivate** | `sync_public_support_index_for_kb_article` runs from `knowledge_base` admin routes. |
| **Manual / scheduled** | `POST /api/admin/support/public-content/reindex` with body `{ "scope": "kb" \| "site" \| "all", "site_base_url": null }`. Requires support role or above. |
| **Site pages** | `scope=site` or `all` fetches only the allowlisted paths in `support_public_content_index_service.SITE_PAGE_ALLOWLIST` (no arbitrary URLs). |

## Response metadata

Successful KC or site answers set `metadata.sources` (list of `{ source_type, article_id?, slug?, title?, url? }`) and `metadata.retrieval_path` (e.g. `["kc_article"]`). Static Q&A uses `["static_qna"]`. LLM path defaults `["llm_fallback"]`.

## Operational notes

- Ensure Mongo indexes exist: `create_support_indexes()` (or app startup path that calls it) includes `ensure_support_public_content_indexes()`.
- If KC answers seem stale after an edit, confirm the article is still **published USER** and run **`scope=kb`** reindex if hooks did not run (e.g. direct DB edit).
