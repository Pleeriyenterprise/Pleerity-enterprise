# Chat Assistant – Clickable Links / Actions (Task vs Codebase Audit)

## Goal (task)

Improve UX in the chat widget by rendering **actions as clickable links or buttons** instead of raw links.

---

## 1. Task Requirements Summary

1. **Structured actions in response** – Assistant responses may contain an `actions` array: `[{ label: "See pricing", url: "/pricing" }, ...]`.
2. **UI** – Render actions as button-style links or hyperlinked text (e.g. "See pricing", "Create account", "Contact support").
3. **Click behaviour** – Open URL in a new tab; do not interrupt the chat session.
4. **Avoid raw URLs in text** – Prefer converting URLs in KB/assistant text into clickable links (or moving them into the actions array).
5. **Scope** – Knowledge base answers, onboarding responses, support (guided/canned) responses.
6. **Deliverables** – Files modified, chat rendering logic changes, example responses with clickable links.

---

## 2. Current Implementation

### Backend

| Area | Behaviour |
|------|-----------|
| **Response shape** | Chat returns a **single text body**: `result["response"]` (string). There is **no** `actions` array in the API. `ChatResponse` has: `conversation_id`, `response`, `action`, `metadata`, `handoff_options`, `conversation_context`. |
| **How URLs get into the text** | All responses that include links are built as **plain text** with **absolute URLs** embedded: e.g. `"1. See pricing: https://pleerityenterprise.co.uk/pricing"`. Used in: `build_guided_response()` (support_chatbot.py), `build_response_from_entry()` (support_chatbot_retrieval.py), canned responses (e.g. pricing), handoff text. |
| **URL format** | Backend uses `FRONTEND_BASE` (env) + path, so **full absolute URLs** (e.g. `https://pleerityenterprise.co.uk/pricing`). No relative URLs like `/pricing` in the response text. |

### Frontend

| Area | Behaviour |
|------|-----------|
| **Rendering** | `MessageBubble` renders `message.text` only. For **bot** messages it runs `linkifyText(message.text)` which: finds substrings matching `https?://...` and renders them as `<a href={...} target="_blank" rel="noopener noreferrer" className="text-teal-600 underline">`. So **full URLs already become clickable links**. |
| **What is not linkified** | Relative URLs (e.g. `/pricing`) are **not** matched by `URL_REGEX` (`https?://...`), so they would appear as plain text if they existed. Currently backend does not send relative URLs in the body. |
| **Message object** | Messages are `{ id, text, sender, timestamp, metadata }`. There is no `actions` property; the frontend never receives or stores a separate actions array. |
| **New tab** | Links from linkify already use `target="_blank"` and `rel="noopener noreferrer"`, so **opening in a new tab** is already in place. |

### Summary

- **Already done:** Full `https://` URLs in bot messages are turned into clickable links that open in a new tab. No chat interruption.
- **Not done:** No structured `actions` array; no button-style or label-only links (e.g. "See pricing" as link). Actions are only present **inside** the text as lines like "1. See pricing: https://...", so the link is the long URL, not the label.

---

## 3. Gaps vs Task

| Requirement | Current state | Gap |
|-------------|---------------|-----|
| **1. Actions array in response** | Backend does not return `actions`. Response is text only. | Add optional `actions: [{ label, url }]` to the chat API (and populate it wherever we build guided/KB/canned responses that have action links). |
| **2. Render actions as buttons/links** | Only linkify of full URL in text. No separate action chips. | If `actions` is present, render each as a clickable element (button or `<a>`) with **label** as text and **url** as href; open in new tab. |
| **3. New tab, no interrupt** | Already satisfied for linkified URLs. | No change needed for behaviour; same for new action links. |
| **4. Prevent raw URLs in messages** | URLs are in the text as full strings; linkify makes them clickable but they still **show** the long URL. | With structured actions: we can **omit** the "1. Label: URL" lines from the displayed text when `actions` is present, so only labels appear as buttons/links and the bubble has no raw URL. For KB entries that embed a URL in the answer body (not in actions), keep linkify so that URL is still clickable. |
| **5. KB, onboarding, support** | Same pipeline: all go through `handle_chat_message` (or quick-action) and return `response` (text). | Once backend adds `actions` for guided, retrieval, and canned responses, and frontend renders `actions`, all three are covered. Onboarding options are separate UI (buttons that send a message); they are not part of the assistant message body. |

---

## 4. Conflict and Recommendation

| Task detail | Codebase | Recommendation |
|-------------|----------|------------------|
| **Example actions use relative URL** (`url: "/pricing"`) | Backend and env use **absolute** URLs (`FRONTEND_BASE + "/pricing"`) everywhere. Frontend may be served from a different origin (e.g. SPA on same domain but API elsewhere). | **Keep using absolute URLs** in the API for `actions[].url`. Frontend can use them as-is for `href` and `target="_blank"`. Avoids base-URL logic and cross-origin issues. |

---

## 5. Proposed Implementation (Safest)

### Backend

1. **Return structured actions from the chatbot**
   - Where responses are built from known actions (guided, retrieval, canned), also build a list of `{ "label": str, "url": str | null }` (url `null` for in-chat actions like "Ask a question").
   - In `handle_chat_message` (and quick-action path), set `result["actions"]` when the response is from:
     - `build_guided_response` → derive from `get_guided_knowledge()[intent]["actions"]`
     - `build_response_from_entry` (retrieval) → from `entry["actions"]`
     - Canned responses that include links (e.g. pricing) → from the same source as the canned text
   - Use **absolute** URLs (current `FRONTEND_BASE` + path). Omit or null URL for actions that are not links (e.g. "Ask a question", "Talk to support").

2. **Optional: trim action lines from response text when actions are present**
   - When returning `actions`, you may strip the trailing "What would you like to do?\n1. Label: URL" block from `result["response"]` so the bubble does not duplicate URLs. Then the only links are the rendered action buttons. Alternatively keep the full text for accessibility and still render actions below (no trim). **Recommendation:** trim to avoid duplicate links and long URLs in the bubble.

3. **API contract**
   - Add to chat result and to `ChatResponse`: `actions: Optional[List[Dict[str, str]]] = None` (e.g. `[{ "label": "See pricing", "url": "https://..." }, { "label": "Ask a question", "url": null }]`). Ensure `MessageCreate` / stored metadata can hold actions if you want history to show them (e.g. store in message metadata when saving the bot message).

### Frontend

1. **Store actions on the message**
   - When appending a bot message from chat or quick-action, set `message.actions = response.data.actions || null`. For older messages or when `actions` is absent, leave `message.actions` undefined.

2. **Rendering**
   - In `MessageBubble`, for bot messages:
     - Continue to render `message.text` with `linkifyText(message.text)` (handles any remaining URLs in body and KB text).
     - If `message.actions` is present and non-empty, below the text render a row of action links:
       - Each item: `<a href={url} target="_blank" rel="noopener noreferrer">` when `url` is present, else a `<span>` or button that does nothing (or triggers “Ask a question” in chat). Use **label** as the visible text.
       - Style as “button-style” (e.g. small pill/button) or underlined links per design.

3. **New tab**
   - Use `target="_blank"` and `rel="noopener noreferrer"` on action links that have a URL. Do not navigate the main window; chat session stays open.

### Scope

- **Knowledge base answers** – Retrieval responses built by `build_response_from_entry`; add `actions` from entry and optionally trim action lines from text.
- **Onboarding responses** – These are the guided intent responses (e.g. after “Manage property compliance”); same as guided, add `actions` from guided knowledge.
- **Support / guided / canned** – All paths that call `build_guided_response` or return canned text with links; include the same `actions` list and optional text trim.

---

## 6. Files to Touch (When Implementing)

| File | Change |
|------|--------|
| `backend/services/support_chatbot.py` | When building a response that has actions (guided, qualification, recommendation, lead capture, escalation), build `result["actions"]` from the same source as the text (e.g. from `get_guided_knowledge()[intent]["actions"]`). Optionally trim "What would you like to do?" and numbered action lines from `result["response"]` when actions are returned. |
| `backend/services/support_chatbot_retrieval.py` | Either return both body and actions from `build_response_from_entry` (e.g. return a dict with `text` and `actions`) or have the caller derive actions from the entry and optionally trim the response text. Caller in support_chatbot sets `result["actions"]` for retrieval responses. |
| `backend/routes/support.py` | Include `result.get("actions")` in the chat response. Extend `ChatResponse` with `actions: Optional[List[Dict[str, Any]]] = None`. When saving the bot message, optionally store `actions` in message metadata so history can show them. |
| `frontend/src/components/SupportChatWidget.js` | When pushing a bot message, set `message.actions = response.data.actions ?? null`. In `MessageBubble`, if `message.actions` exists, render action links/buttons below the linkified text; use label as text, url as href; `target="_blank"` for links. |

---

## 7. Example Assistant Responses (After Implementation)

- **Guided (e.g. CVP):**  
  - Text: intro + “Key features:” + bullets + “Pricing: …” (no “1. See pricing: https://…” in text).  
  - Actions: [See pricing, Create account, Check your compliance risk, Ask a question] as button-style links (first three open in new tab).

- **KB retrieval (e.g. “How much is CVP?”):**  
  - Text: answer paragraph only.  
  - Actions: [View pricing, Create account, Check your compliance risk, Ask a question] as links.

- **Canned (e.g. pricing quick action):**  
  - Text: short pricing summary.  
  - Actions: [View pricing, Learn more] as links.

In all cases, clicking an action with a URL opens that URL in a new tab and the chat stays open.

---

## 8. Status

- **Audit:** Complete.  
- **Implementation:** Done. Backend returns `actions` for guided, retrieval, and canned (cvp_info, pricing, reset_password); response text trimmed when actions present. API includes `actions` in ChatResponse and quick-action; stored in bot message metadata. Frontend renders `message.actions` as button-style links (new tab); in-chat-only actions shown as non-clickable chips.
