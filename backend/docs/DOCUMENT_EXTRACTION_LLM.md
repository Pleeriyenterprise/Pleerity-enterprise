# Document extraction LLM providers

Compliance field extraction uses **text-only** input (PDF text + optional OCR), not raw file upload to Gemini.

## Provider order

| Role | Provider | Env |
|------|----------|-----|
| Primary | OpenAI | `OPENAI_API_KEY` |
| Fallback | Gemini | `LLM_API_KEY` |

Configuration (`services/document_extraction_llm_gateway.py`):

- `DOCUMENT_EXTRACTION_PRIMARY_PROVIDER` (default `openai`)
- `DOCUMENT_EXTRACTION_FALLBACK_PROVIDER` (default `gemini`)
- `DOCUMENT_EXTRACTION_OPENAI_MODEL` (default `AI_MODEL` or `gpt-4o-mini`)
- `DOCUMENT_EXTRACTION_GEMINI_MODEL` (default `gemini-2.5-flash`)
- `DOCUMENT_EXTRACTION_LLM_TIMEOUT_SECONDS` (default `45`)

Also requires `AI_ENABLED=true` (see `utils.ai_config`).

## Call paths

| Path | Entry | LLM |
|------|-------|-----|
| Pipeline | `document_extraction_service.run_extraction_job` | `ai_provider.extract_compliance_fields_async` |
| Upload analysis | `document_analysis.analyze_document` | Same gateway via `ai_provider` |

Support assistant uses `support_llm_gateway` separately — unchanged.

## Failure behaviour

- User-facing messages via `extraction_error_presentation` (no raw quota URLs).
- Internal audit fields: `provider_used`, `fallback_used`, `llm_error_class`, `llm_latency_ms`.
- Status `FAILED` with message e.g. “Extraction failed — review manually.”

## Gemini quota errors

With OpenAI configured, Gemini quota errors should not appear to users unless OpenAI also failed and Gemini was attempted as fallback. If both fail, users see a controlled unavailable message.
