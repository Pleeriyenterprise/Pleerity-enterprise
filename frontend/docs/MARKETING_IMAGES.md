# Marketing image generation

## Overview

The marketing site shows product visuals in three places: homepage hero, homepage “Portfolio in one view”, and CVP page hero + calendar section. **PNG is the single source of truth**; all references use absolute paths from `public/images/marketing/`:

- `hero-command-centre.png` – dashboard preview (fallback: `.svg` if PNG missing)
- `feature-expiry-list.png` – upcoming expiries preview
- `support-calendar.png` – calendar preview

The `<MarketingImage>` component loads the PNG first; if it fails (e.g. PNG not yet generated), it falls back to the SVG and in development logs a console warning. This keeps rendering reliable on all routes (no relative paths).

To get **real cropped PNGs** in `public/images/marketing/`: add raw screenshots to `public/images/raw/` and run `npm run generate-marketing-images`. The script writes the three PNGs with the exact names above. Until then, the committed SVGs are used as fallback.

## Commands

```bash
npm run generate-marketing-images
```

Run after adding raw screenshots to `public/images/raw/`. Optionally run before `npm run build` (e.g. in CI or a prebuild step).

## Crop coordinates used

| Output file | trimTop (px) | trimBottom (px) | Resize target |
|-------------|--------------|-----------------|---------------|
| hero-command-centre.png | 120 | 100 | 1200×850 |
| feature-expiry-list.png | 120 | 80 | 1200×800 |
| support-calendar.png | 120 | 80 | 1200×800 |

Crops remove top navigation and (where applicable) footer. Coordinates are configurable in `scripts/generateMarketingImages.js` (`CROP_SPECS`).

## Raw input names

The script looks for files in `public/images/raw/` with any of these names (first match wins):

- **hero-command-centre.png**: `hero-command-centre.png`, `hero-command-centre-raw.png`
- **feature-expiry-list.png**: `feature-expiry-list.png`, `feature-expiry-list-raw.png`
- **support-calendar.png**: `support-calendar.png`, `support-calendar-raw.png`, `support-calender.png`, `support-calender-raw.png`

## Files created by implementation

- `frontend/scripts/generateMarketingImages.js` – crop script (run to produce PNGs from raw screenshots)
- `frontend/public/images/raw/.gitkeep` – placeholder so `raw/` is committed
- `frontend/public/images/marketing/.gitkeep` – placeholder so `marketing/` is committed
- `frontend/public/images/marketing/hero-command-centre.svg`, `feature-expiry-list.svg`, `support-calendar.svg` – committed SVG fallbacks
- `frontend/src/components/public/MarketingImage.js` – PNG-first image with SVG fallback and dev-only onError warning
- `frontend/src/components/public/ProductScreenshot.js` – reusable screenshot wrapper (rounded-xl, border, shadow-md)
- `frontend/docs/MARKETING_IMAGES.md` – this file

## Files modified

- `frontend/package.json` – added script `generate-marketing-images`; `sharp` in devDependencies
- `frontend/src/pages/public/HomePage.js` – uses `<MarketingImage name="hero-command-centre" />` and `<MarketingImage name="feature-expiry-list" />` (absolute paths)
- `frontend/src/pages/public/CVPLandingPage.js` – uses `<MarketingImage name="hero-command-centre" />` and `<MarketingImage name="support-calendar" />` (absolute paths)
- `frontend/src/components/public/index.js` – export `MarketingImage`

## Routes changed

None. `/demo` already redirects to `/risk-check`. No new or removed routes.

## Usage in pages

- All marketing screenshots use `<MarketingImage name="…" />` with **exact names** (no extension): `hero-command-centre`, `feature-expiry-list`, `support-calendar`. Paths are always absolute (`/images/marketing/<name>.png` then `.svg` on error).
- **Hero image**: `fetchPriority="high"`, explicit `width`/`height`, caption “Illustrative portfolio example. Live score generated after structured assessment.”
- **Other images**: `loading="lazy"`, `width`/`height` to avoid layout shift.
- All are wrapped in `<ProductScreenshot>` for consistent styling.
- **Dev-only:** If a PNG fails to load, the console shows a warning and the component falls back to SVG.
