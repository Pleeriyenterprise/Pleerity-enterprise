# Public support assistant — orchestration

Incremental behaviour (no replacement of tickets, escalation, retrieval, or guardrails).

## Turn order when `SUPPORT_GPT_FIRST_ENABLED=true` (anonymous web widget)

1. **Rate limit** — `routes/support.py` (IP + conversation buckets).
2. **Legal / statutory advice** — `is_legal_advice_request` → refusal.
3. **AI support brain** (`support_ai_brain.py`) — single primary path:
   - **Protected shortcuts:** human handoff, password reset (canned), order ref+email lookup, CRN+email verified snapshot, order clarify prompt.
   - **Brain turn:** centralized instructions (`support_ai_instructions.py`) + KC/site retrieval (always for grounding) + registry pricing facts + one Gemini JSON planner call → natural `reply_text`, optional allowlisted actions, metadata.
4. **Legacy fallback only** if brain returns `None` (flag off, no API key, LLM/parse failure): `_run_legacy_public_support_orchestration` in `support_chatbot.py` (onboarding, small-talk, conversational-first, `router_turn`, guided, static Q&A, escalation, legacy LLM).

**Old router/guided/menu layers do not run before the brain when the flag is on.**

## Turn order when flag is off (or signed-in portal)

1. Legal refusal.
2. Legacy orchestration (problem map, onboarding, small-talk, vague account clarify, conversational-first for anonymous, `router_turn`, guided, static retrieval, LLM).

## Signed-in portal

KC/site chunk retrieval runs **after** guided shortcuts (same as before), via `is_authenticated` branch only.

## Retrieval priority (unchanged)

Indexed chunks: **KC (`kb_article`)** over **site (`site_page`)** when KC clears its score threshold. Static Q&A remains separate in `support_chatbot_retrieval`. Answers use **conversational excerpt + Read full article** (not raw multi-paragraph dumps).

## Operational vs conversational

- **Conversational:** small-talk, clarifying questions, synthesized KC/site text, LLM with approved JSON.
- **Operational:** tickets, handoff options, CRN+email verification tools, order lookup, registry pricing lines, legal refusal.

## Session memory keys (client round-trip `conversation_context`)

`active_topic`, `last_user_goal`, `last_support_area`, `recent_entities` (bounded list of recent user lines, truncated), `escalation_context` (reserved). Populated by the conversational-first stage where applicable; does not replace audit logs or server-side session stores.

## AI brain schema (planner JSON)

`reply_text`, `intent_summary`, `user_goal`, `topic`, `needs_clarification`, `clarification_question`, `show_actions`, `actions` (allowlisted ids), `escalation_suggested`, `safety_boundary`, `sources_used`, `confidence`.

Allowlisted actions: `view_pricing`, `create_account`, `check_compliance_risk`, `sign_in`, `reset_password`, `create_ticket`, `talk_to_support`, `open_help_article`, `open_compliance_vault`, `open_services` (plus legacy alias ids mapped in `support_ai_brain._map_action_ids_to_buttons`).

## LLM providers (support AI brain)

| Env | Purpose |
|-----|---------|
| `SUPPORT_GPT_FIRST_ENABLED` | `true` to enable AI-first path (anonymous widget) |
| `SUPPORT_AI_PRIMARY_PROVIDER` | Default `openai` |
| `SUPPORT_AI_FALLBACK_PROVIDER` | Default `gemini` |
| `SUPPORT_AI_OPENAI_MODEL` | Overrides model; else `AI_MODEL` (default `gpt-4o-mini`) |
| `SUPPORT_AI_GEMINI_MODEL` | Default `gemini-2.0-flash` |
| `OPENAI_API_KEY` | OpenAI primary (via `utils.ai_config`) |
| `LLM_API_KEY` | Gemini fallback (Google Generative AI) |
| `SUPPORT_AI_LLM_TIMEOUT_SECONDS` | Per-provider timeout (default `45`) |

Gateway: `services/support_llm_gateway.py` — OpenAI first; Gemini only on failure, timeout, or invalid planner JSON. Response metadata may include `provider_used`, `model_used`, `fallback_used`, `llm_latency_ms`, `llm_error_class` (redacted). Prompts and keys are not logged.

## Staging verification

Set `SUPPORT_GPT_FIRST_ENABLED=true`, `OPENAI_API_KEY` (and optionally `LLM_API_KEY` for fallback) on **staging only**. Run `python -m scripts.verify_support_gpt_first_staging` with `SUPPORT_STAGING_BASE_URL` set (see script docstring).

## Staging verification (operator-run)

With staging env `SUPPORT_GPT_FIRST_ENABLED=true`, `LLM_API_KEY` set, and KC/site index populated, run:

`python -m scripts.verify_support_gpt_first_staging` from `backend/` after setting `SUPPORT_STAGING_BASE_URL` to the staging API origin (see script docstring). This prints redacted transcripts, latency, and metadata subsets for legal/password/handoff/CRN and conversational cases.

For **LLM-off fallback**, temporarily clear `LLM_API_KEY` on a throwaway staging slot (or local), re-run the same script; responses should still return HTTP 200 via the legacy stack.

## Known limitations

- Optional synthesis runs **one** LLM call per KC/site hit when a key is present; without a key, behaviour stays close to templated excerpt + CTA.
- `defer_public_kb_for_operational_routing` uses the same rule-based `classify_support_intent` as the router; edge overlaps should be monitored in logs.
- Portal (`is_authenticated`) sessions skip the conversational-first stage; KC ordering there is unchanged.
