# Newsletter and Kit.com Configuration

The system collects newsletter signups on the website and syncs them to **Kit.com** (ConvertKit). Email campaigns are sent from Kit; the app only handles signup and one-way sync.

## How it works

1. **Public signup**  
   - `/newsletter` (Newsletter page) and footer/Insights “Subscribe” call `POST /api/newsletter/subscribe?email=...&source=...`.  
   - Subscribers are stored in MongoDB (`newsletter_subscribers`) and pushed to Kit via the Kit API.

2. **Kit sync**  
   - Each signup is sent to Kit using the **Kit API v4** “Create a subscriber” endpoint.  
   - Subscriber is created with `state: active` and a custom field **Source** (e.g. `newsletter_page`, `website`, `insights`).  
   - If Kit is unavailable, the subscriber is still saved locally and marked `kit_sync_status: FAILED` so you can retry or export CSV.

3. **Admin**  
   - **Admin → Marketing → Newsletter** lists subscribers and their Kit sync status (SYNCED / FAILED / PENDING).  
   - You can export CSV from that page.

## Incorporating your Kit account

### 1. Get your Kit API key

1. Log in at [kit.com](https://kit.com).  
2. Go to **Settings → API** (or **Account → API**).  
3. Create or copy an **API Key** (or OAuth access token).  
4. The integration uses **Bearer token** authentication.

### 2. Set the environment variable

Set your Kit API key in the environment used by the backend (e.g. `.env` or your host’s env config):

```bash
KIT_API_KEY=your_kit_api_key_here
```

- Do **not** commit this value to git.  
- Restart the backend after changing it.

Optional (only if Kit uses a different base URL):

```bash
KIT_API_BASE=https://api.kit.com/v4
```

### 3. Create the “Source” custom field in Kit (recommended)

The app sends signup **source** (e.g. `newsletter_page`, `website`, `insights`) as a Kit custom field named **Source**.

- In Kit: **Subscribers → Custom fields** (or **Settings → Custom fields**).  
- Add a custom field with the exact name **Source** (type Text or similar).  
- If you don’t create it, Kit may ignore the value; subscriber creation will still succeed.

### 4. Verify

1. Restart the backend with `KIT_API_KEY` set.  
2. Submit a test signup on `/newsletter` (or any form that calls `POST /api/newsletter/subscribe`).  
3. In **Admin → Marketing → Newsletter**, the new subscriber should show **Kit Sync: SYNCED**.  
4. In Kit’s dashboard, the subscriber should appear with the **Source** value you passed (e.g. `newsletter_page`).

If Kit sync shows **FAILED**, check backend logs for the Kit API error (e.g. invalid key, 401, or 422). A 401 usually means `KIT_API_KEY` is wrong or expired.

## Where newsletter is used in the app

| Place              | Route / usage |
|--------------------|----------------|
| Public newsletter  | `/newsletter` → `NewsletterPage.js` → `POST /api/newsletter/subscribe` |
| Footer link        | “Newsletter” in `PublicFooter.js` → `/newsletter` |
| Insights CTA       | “Subscribe” in `InsightsHubPage.js` → `/newsletter` |
| Admin list/export  | **Admin → Marketing → Newsletter** → `GET /api/admin/newsletter/subscribers` (or equivalent) |

## Backend details

- **Subscribe endpoint:** `POST /api/newsletter/subscribe`  
  - Query params: `email` (required), `source` (optional, default `website`).  
  - Response: `{ "success": true, "message": "Subscribed successfully" }` (or “Already subscribed”).  
- **Kit integration:** `backend/services/kit_integration.py`  
  - Uses Kit API v4 `POST /v4/subscribers` with `email_address`, `state`, and `fields.Source`.  
  - If `KIT_API_KEY` is empty, sync is skipped and the subscriber is still saved with `kit_sync_status: FAILED` and an error message indicating the key is not set.

## Sending campaigns

- **All email campaigns are sent from Kit**, not from the app.  
- Use Kit’s UI (or Kit’s own automation) to create and send campaigns, segment by **Source** if needed, and manage unsubscribes/compliance.
