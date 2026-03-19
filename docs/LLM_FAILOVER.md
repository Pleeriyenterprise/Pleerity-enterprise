# Document generation LLM failover (OpenAI ↔ Gemini)

## Behaviour

- **Primary** provider is controlled by `DOCUMENT_LLM_PREFERRED_PROVIDER` (`openai` default, or `gemini`).
- On **failover-eligible** errors from the first provider, the second provider is tried once.
- **Orders / pack items are not marked FAILED** if the second provider returns valid output.
- **FAILED** only when both providers fail (or the error is not eligible for failover, e.g. some auth errors).

## Failover triggers

- HTTP **429**, **rate limit**, **quota**, **resource exhausted** (message heuristics + SDK types where available)
- **Timeouts** (`asyncio.TimeoutError`, `TimeoutError`, deadline exceeded)
- **Missing API key** for the preferred provider (`ValueError` patterns) so the other key may still work

## Logging

Structured log lines from `services.unified_llm_service`:

- `document_llm_failover` — primary failed, trying secondary (includes error summary).
- `document_llm_ok` — success with `provider_used`, `fallback_used`, `primary_attempted`, `fallback_reason`.
- `document_llm_failed` / final `RuntimeError` — both providers exhausted (message includes both errors).

## `generation_runs` fields

| Field | Meaning |
|--------|---------|
| `provider_used` | Provider that produced the output (`openai` / `gemini`) |
| `provider` | Same as `provider_used` (legacy readers) |
| `fallback_used` | `true` if the successful run used the secondary provider |
| `primary_provider_attempted` | First provider tried (`DOCUMENT_LLM_PREFERRED_PROVIDER`) |
| `fallback_reason` | e.g. `openai_failed:...` on success after failover; `both_llm_providers_failed` on FAILED when applicable |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMENT_LLM_PREFERRED_PROVIDER` | `openai` | `openai` or `gemini` |
| `DOCUMENT_LLM_TIMEOUT_SECONDS` | `120` | Per-provider HTTP / wall-clock budget |
| `OPENAI_DOCUMENT_MODEL` | `gpt-4o-mini` | OpenAI model for document paths (overrides if set) |
| `DOCUMENT_GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model for **single-doc orchestrator** |
| `DOCUMENT_PACK_GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model for **document pack** generation |

OpenAI still uses `OPENAI_API_KEY` / `ai_config.get_openai_api_key()`; Gemini uses `LLM_API_KEY`.

## Code entry points

- `services/unified_llm_service.py` — `generate_with_failover`, `should_attempt_failover`
- `services/document_orchestrator.py` — `_execute_gpt` → unified service; `generation_runs` + `orchestration_executions` store provider metadata
- `services/document_pack_orchestrator.py` — pack generation uses the same unified service
