# Logo and favicon

Place your brand assets in **`frontend/public/branding/`** so the app can use them. All references go through `src/config/branding.js`.

## Required files

| File | Location | Used by |
|------|----------|--------|
| **favicon.png** | `frontend/public/branding/favicon.png` | Browser tab, bookmarks, apple-touch-icon (index.html) |
| **pleerity-logo.png** | `frontend/public/branding/pleerity-logo.png` | Public header, admin sidebar, portal selector, ClearForm pages, login |

## Notes

- **Favicon**: `index.html` uses `%PUBLIC_URL%/branding/favicon.png`. Prefer PNG (e.g. 32×32; 180×180 for apple-touch). Same file is used for both.
- **Logo**: Components use `BRAND_LOGO_URL` from `src/config/branding.js`, which points to `/branding/pleerity-logo.png`. To use a different name or format, update `branding.js` and any direct references.
- After adding files, restart the dev server if they don’t appear (browser may cache the old favicon).
