# Chat Assistant – System Prompt Installation (Task vs Codebase Audit)

## Goal (task)

Ensure the assistant follows a **consistent behaviour, tone, and conversation flow** by installing a canonical system prompt used for every AI response.

---

## 1. Task Requirements Summary

1. **Create a file** to store the system prompt (task example: `frontend/src/chat/systemPrompt.ts`), export constant `SYSTEM_PROMPT`.
2. **Insert** the provided system prompt text exactly.
3. **Update AI request logic** so every assistant response includes this system prompt (example: `messages = [ { role: "system", content: SYSTEM_PROMPT }, ...conversationHistory, { role: "user", content: userMessage } ]`).
4. **System prompt must be the first message** sent to the LLM.
5. **Do not show** the system prompt to users.
6. **Work alongside** intent detection, knowledge base retrieval, context memory, and recommendation logic.
7. **Deliverables:** file where prompt is stored, file where it is injected, example request payload.

---

## 2. Where the AI Is Actually Invoked

| Component | Role |
|-----------|------|
| **Frontend** (`SupportChatWidget.js`) | Sends **user message** and optional `conversation_id` / `conversation_context` to `POST /api/support/chat`. It does **not** call any LLM, build a messages array, or send a system prompt. |
| **Backend** (`backend/routes/support.py`) | Receives the request, loads conversation history, calls `handle_chat_message()`. |
| **Backend** (`backend/services/support_chatbot.py`) | `handle_chat_message()` runs intent detection, problem detection, qualification, retrieval, etc. When no structured path matches, it calls **`generate_ai_response(message, conversation_history, client_context)`**. |
| **`generate_ai_response()`** | Builds a **system prompt inline** (short rules + full KB JSON), then calls **`utils.llm_chat.chat(system_prompt=..., user_text=...)`**. The LLM (Gemini via `LLM_API_KEY`) is invoked **only here**. |

So: **every AI-generated support chat response is produced in the backend.** The frontend never sends a system prompt or a messages array to an LLM.

---

## 3. Current System Prompt (Backend)

In `support_chatbot.py`, `generate_ai_response()` builds the system prompt as:

```python
system_parts = [
    "You are Pleerity Support, a helpful AI assistant for Pleerity Enterprise Ltd.",
    "You help customers with: Compliance Vault Pro, Document Packs, AI Automation, Market Research, and general account queries.",
    "",
    "IMPORTANT RULES:",
    "1. NEVER provide legal advice, interpret legislation, or predict council enforcement.",
    "2. Be helpful, professional, and concise.",
    "3. If you can't help, offer to connect them with a human agent.",
    "4. For account-specific queries, ask for their CRN (Customer Reference Number).",
    "",
    "KNOWLEDGE BASE (use frontend_links for sign-in, pricing, CVP landing - never invent URLs):",
    json.dumps(get_chatbot_knowledge_base(), indent=2),
]
# + optional CUSTOMER CONTEXT if authenticated
```

Then it passes `system_prompt="\n".join(system_parts)` and a single `user_text` (previous conversation snippet + latest customer message) to `chat()`. So the system prompt is **already** the first thing the LLM sees (Gemini uses `system_instruction`, OpenAI uses `messages[0]` with role system). It is **not** shown to users.

---

## 4. Gaps vs Task

| Requirement | Current | Gap |
|-------------|---------|-----|
| **1. File to store prompt** | No dedicated file. Prompt is built inline in `generate_ai_response()`. | Task suggests `frontend/src/chat/systemPrompt.ts`; in this codebase the LLM is **backend-only**, so a frontend file would **not** be used for the website chat. |
| **2. Use the provided prompt text** | Current prompt is shorter and different (rules + KB JSON). | The **full** task-provided system prompt (behaviour, services, flow, examples, intent recognition, response style, unknown questions, welcome, problem-first, link behaviour) is **not** present as the canonical instruction. |
| **3. Inject into AI request** | Backend already passes a system prompt to `chat(system_prompt=..., user_text=...)`. | Need to **replace or extend** the current inline prompt with the canonical text (and still append KB/context so the model has facts and URLs). |
| **4. First message to LLM** | Already satisfied: backend sends one system prompt then one user payload. | No change needed. |
| **5. Don’t show to users** | Satisfied: system prompt is never returned in the API response. | No change needed. |
| **6. Work with intent/KB/context/recommendation** | Structured paths (intent, problem, qualification, retrieval) run **before** `generate_ai_response()`; only when no path matches do we call the LLM. So the system prompt applies only to **fallback** AI replies. | The canonical prompt should still be used for those fallback responses and can reference “intent detection, knowledge base, context, recommendation” so the model’s style aligns when it does answer. |

---

## 5. Conflict and Recommended Approach

| Task assumption | Codebase reality | Recommendation |
|-----------------|------------------|-----------------|
| **Store prompt in frontend** (`frontend/src/chat/systemPrompt.ts`) | The **website** support chat does **not** call an LLM from the frontend. The frontend only calls `POST /support/chat` with the user message. | **Do not** create a frontend system prompt file for the **website** chat assistant. It would be dead code. Store the canonical prompt in the **backend** (see below). |
| **“Update the AI request logic”** with `messages = [ system, ...history, user ]` | The AI request is built in the backend; `utils.llm_chat.chat(system_prompt, user_text)` takes a single system string and a single user string (history is folded into that user string). | **Keep** the backend as the place where the system prompt is injected. Build the system string from the canonical prompt (+ optional KB/context appendix) and pass it as the first argument to `chat()`. |

**Safest implementation:**

1. **Create a backend file** that holds the exact system prompt text (and only that), so it’s easy to maintain and audit.
   - **Option A:** `backend/prompts/support_assistant_system_prompt.py` – define a constant `SUPPORT_ASSISTANT_SYSTEM_PROMPT = """..."""` (or load from a `.txt` file if you prefer).
   - **Option B:** `backend/prompts/support_assistant_system_prompt.txt` – single file with the prompt; Python reads it at runtime. No need for a `frontend/src/chat` folder for this feature.

2. **Inject in the backend** in `generate_ai_response()`:
   - Build the final system prompt as: **canonical prompt** (from the new file) **+** a short appendix: “KNOWLEDGE BASE (use only the following; never invent URLs):” + `get_chatbot_knowledge_base()` JSON, and optionally “CUSTOMER CONTEXT (if present):” + client_context. That way the model gets the full behaviour/tone/flow from the canonical prompt and still has live KB and context.

3. **First message to LLM:** Continue passing this combined system prompt as the first/only “system” instruction (already the case with `chat(system_prompt=..., user_text=...)`). Do not show it to users.

4. **Compatibility:** Intent detection, problem detection, qualification, retrieval, and recommendation all run **before** `generate_ai_response()`. When we do call the LLM, we use the new system prompt so fallback AI behaviour matches the intended tone and flow. No need to change frontend for “injection”; only backend changes.

---

## 6. Proposed Implementation (When Approved)

### Backend

1. **New file:** `backend/prompts/support_assistant_system_prompt.py` (or `.txt`).
   - Content: the **exact** system prompt text from the task (SYSTEM PROMPT – PLEERITY SUPPORT ASSISTANT through LINK BEHAVIOUR), as a single string constant or file content.

2. **Modify:** `backend/services/support_chatbot.py`, function `generate_ai_response()`:
   - Import (or read) the canonical prompt from the new file.
   - Set `system_parts = [ canonical_prompt ]` then append:
     - `""`, `"KNOWLEDGE BASE (use only the following; never invent URLs):"`, `json.dumps(get_chatbot_knowledge_base(), indent=2)`.
     - If `client_context`: append `""`, `"CUSTOMER CONTEXT (authenticated):"`, `json.dumps(client_context, indent=2)`.
   - Pass `"\n".join(system_parts)"` as `system_prompt` to `chat(...)` as today. So the **canonical prompt is always first**; KB and context follow.

3. **Result:** Every AI-generated support response uses the same behaviour/tone/flow; KB and context remain available to the model; intent/KB/context/recommendation logic unchanged.

### Frontend

- **No change** required for the website chat assistant. No `frontend/src/chat/systemPrompt.ts` and no frontend “injection” of the system prompt.

### Deliverables

- **File where the system prompt is stored:** `backend/prompts/support_assistant_system_prompt.py` (or `.txt`).
- **File where it is injected into the AI request:** `backend/services/support_chatbot.py` (inside `generate_ai_response()`).
- **Example request payload (conceptual):** The backend calls `chat(system_prompt=<canonical prompt> + "\n\n" + KNOWLEDGE BASE + optional CUSTOMER CONTEXT, user_text="Previous conversation:\n..." + "Customer's new message: " + message)`. The system prompt is not sent to the client; the client only receives the final `response` in the chat API response body.

---

## 7. Status

- **Audit:** Complete.
- **Implementation:** Done.
  - **File where prompt is stored:** `backend/prompts/support_assistant_system_prompt.py` (constant `SUPPORT_ASSISTANT_SYSTEM_PROMPT`).
  - **File where it is injected:** `backend/services/support_chatbot.py`, in `generate_ai_response()`.
  - **Payload shape:** `system_prompt` = canonical prompt + `"\n\n"` + "KNOWLEDGE BASE (use only the following; never invent URLs):" + `json.dumps(get_chatbot_knowledge_base(), indent=2)` + optional "CUSTOMER CONTEXT (authenticated):" + `json.dumps(client_context, indent=2)`; `user_text` = previous conversation snippet + "Customer's new message: " + message.
