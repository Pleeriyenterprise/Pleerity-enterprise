# Support channels, live chat, and WhatsApp — known limitations

This note complements the public support retrieval runbook (`SUPPORT_PUBLIC_CONTENT_RETRIEVAL.md`) and admin support operations.

## Tawk.to live chat

- Live chat is hosted by **Tawk.to** (external). The Pleerity widget only opens the provider session when `TAWKTO_PROPERTY_ID` / `TAWKTO_WIDGET_ID` (or `REACT_APP_*` equivalents) are configured on the environment that serves the widget and the API.
- **Availability (backend, single source of truth for bot copy + `handoff_options`):** `compute_public_live_chat_state()` in `services/support_chatbot.py` sets `live_chat.configured`, `enabled`, `within_support_hours`, and `available`. There is **no** call to Tawk’s HTTP APIs from the backend; wall-clock uses `SUPPORT_LIVE_CHAT_TIMEZONE` (default `Europe/London`), `SUPPORT_LIVE_CHAT_WEEKDAYS` (default `0,1,2,3,4` = Mon–Fri), and `SUPPORT_LIVE_CHAT_START_HOUR` / `SUPPORT_LIVE_CHAT_END_HOUR` (default `9`–`18`, half-open local interval). Set `SUPPORT_LIVE_CHAT_ENABLED=0|false|off` to hide live chat handoff even if Tawk IDs are present.
- **Visitor widget status (frontend only):** After the Tawk script loads, `Tawk_API.onStatusChange` updates `window.__PLEERITY_TAWK_STATUS` (`online` | `away` | `offline`). The support handoff panel may **disable** the live chat button when the widget reports `offline`, even inside support hours — without changing the initial bot paragraph (copy stays conservative and does not claim an agent is online).
- **Transcripts may not fully sync** into Pleerity `support_conversations` / `support_messages`. Operators must use Tawk’s own history when investigating what was said in the external session.
- When Tawk is not configured, `live_chat.configured` is **false**: the handoff **panel hides** the live chat row, bot intro lists only email (and WhatsApp when configured), and `live_chat_notice` still carries the short “not available / create a ticket” line where useful.

## WhatsApp

- WhatsApp is implemented as an **outbound deeplink** (`wa.me/...`) with a prefilled message and **audit** of public support actions where applicable. There is **no inbound thread sync** into Pleerity as a unified messaging channel.
- If `SUPPORT_WHATSAPP_NUMBER` is unset or disabled, the handoff UI **hides** the WhatsApp option rather than adding a new provider.

## Handoff and operators

- During human handoff, **check the correct system**: Pleerity ticket/queue vs Tawk vs WhatsApp thread, depending on how the customer continued.
- Do not treat bot or indexed answers as **legal or compliance guarantees**; escalation paths remain authoritative for regulated advice.
