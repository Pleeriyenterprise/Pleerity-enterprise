# Support channels, live chat, and WhatsApp — known limitations

This note complements the public support retrieval runbook (`SUPPORT_PUBLIC_CONTENT_RETRIEVAL.md`) and admin support operations.

## Tawk.to live chat

- Live chat is hosted by **Tawk.to** (external). The Pleerity widget only opens the provider session when `TAWKTO_PROPERTY_ID` / `TAWKTO_WIDGET_ID` (or `REACT_APP_*` equivalents) are configured on the environment that serves the widget and the API.
- **Transcripts may not fully sync** into Pleerity `support_conversations` / `support_messages`. Operators must use Tawk’s own history when investigating what was said in the external session.
- When Tawk is not configured, the public API marks live chat as **unavailable**, shows user-facing copy (“Live chat is not available right now…”), and still offers **email ticket** (and WhatsApp only when configured).

## WhatsApp

- WhatsApp is implemented as an **outbound deeplink** (`wa.me/...`) with a prefilled message and **audit** of public support actions where applicable. There is **no inbound thread sync** into Pleerity as a unified messaging channel.
- If `SUPPORT_WHATSAPP_NUMBER` is unset or disabled, the handoff UI **hides** the WhatsApp option rather than adding a new provider.

## Handoff and operators

- During human handoff, **check the correct system**: Pleerity ticket/queue vs Tawk vs WhatsApp thread, depending on how the customer continued.
- Do not treat bot or indexed answers as **legal or compliance guarantees**; escalation paths remain authoritative for regulated advice.
