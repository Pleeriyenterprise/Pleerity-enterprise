# Public support assistant — conversational orchestration

Incremental behaviour (no replacement of tickets, escalation, retrieval, or guardrails).

## Turn order (anonymous web widget)

1. **Legal / statutory advice** — `is_legal_advice_request` → refusal (no LLM, no retrieval sales path).
2. **Problem → product map** — existing `detect_problem_intent` / onboarding steps.
3. **Small-talk** — short social replies; no escalation from these alone.
4. **Vague account clarify** — one clarifying question before account cards / deep routing.
5. **Conversational-first stage** (`run_conversational_first_turn` in `support_conversational_orchestrator.py`, anonymous only) — light `conversation_context` memory; very short generic “help” starters; then `defer_public_kb_for_operational_routing` (pricing/orders/tokens/handoff/password/high-confidence ops **except** `is_informational_public_support_query` for account/compliance/receipts/onboarding intents so “how does X work?” can use KC first); then `try_public_support_content_answer`. Optional Gemini synthesis as before. `_synthesis_context` never returned to clients.
6. **`router_turn`** — operational tools; **ASK_VERIFY** is skipped for the same informational pattern (no CRN+email yet) so the main pipeline can answer educationally.
7. **Guided / intent / pricing shortcuts** — unchanged registry-backed paths.
8. **Static Q&A retrieval** — legacy keyword KB.
9. **Escalation counters** then **LLM** with approved knowledge JSON.

## Signed-in portal

KC/site chunk retrieval runs **after** guided shortcuts (same as before), via `is_authenticated` branch only.

## Retrieval priority (unchanged)

Indexed chunks: **KC (`kb_article`)** over **site (`site_page`)** when KC clears its score threshold. Static Q&A remains separate in `support_chatbot_retrieval`. Answers use **conversational excerpt + Read full article** (not raw multi-paragraph dumps).

## Operational vs conversational

- **Conversational:** small-talk, clarifying questions, synthesized KC/site text, LLM with approved JSON.
- **Operational:** tickets, handoff options, CRN+email verification tools, order lookup, registry pricing lines, legal refusal.

## Session memory keys (client round-trip `conversation_context`)

`active_topic`, `last_user_goal`, `last_support_area`, `recent_entities` (bounded list of recent user lines, truncated), `escalation_context` (reserved). Populated by the conversational-first stage where applicable; does not replace audit logs or server-side session stores.

## GPT-first mode (optional)

Set `SUPPORT_GPT_FIRST_ENABLED=true` (or `1`/`yes`/`on`) for **anonymous** public widget sessions only.

Order after vague account clarify:

1. `touch_session_memory` + `try_generalist_help_starter` (same as before; no LLM).
2. `try_gpt_first_deterministic_shortcuts`: explicit human handoff, high-confidence password reset canned path, verified **order ref + email** lookup, verified **CRN + email** snapshot, or order clarifying prompt when an order question lacks tokens.
3. `run_gpt_first_public_turn`: one Gemini planner call with KC/site chunk excerpts (unless `defer_public_kb_for_operational_routing`), `format_pricing_paragraph_for_prompt` registry facts, policy snippets, compact transcript, and handoff channel flags. Returns JSON-shaped plan → `reply_text`, metadata (`intent_summary`, `confidence`, `should_show_actions`, `needs_clarification`, `escalation_recommended`, `safety_boundary`, `sources_used`), and optional **allowlisted** action buttons (`sign_in`, `pricing`, `services`, `compliance_vault`, `dashboard`, `talk_to_support`).

If the flag is off, the planner is skipped. If the flag is on but there is no `LLM_API_KEY`, JSON parse fails, or the model errors, execution falls through to `run_conversational_first_turn` → `router_turn` → existing guided/static/LLM paths (no crash).

## Known limitations

- Optional synthesis runs **one** LLM call per KC/site hit when a key is present; without a key, behaviour stays close to templated excerpt + CTA.
- `defer_public_kb_for_operational_routing` uses the same rule-based `classify_support_intent` as the router; edge overlaps should be monitored in logs.
- Portal (`is_authenticated`) sessions skip the conversational-first stage; KC ordering there is unchanged.
