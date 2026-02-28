# Marketing image generation

## Overview

Cropped marketing screenshots are produced by a **build-time** Node script using **sharp**. Raw full-page screenshots go in `public/images/raw/`; cropped outputs are written to `public/images/marketing/`.

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

- `frontend/scripts/generateMarketingImages.js` – crop script
- `frontend/public/images/raw/.gitkeep` – placeholder so `raw/` is committed
- `frontend/public/images/marketing/.gitkeep` – placeholder so `marketing/` is committed
- `frontend/src/components/public/ProductScreenshot.js` – reusable screenshot wrapper (rounded-xl, border, shadow-md, white background)
- `frontend/docs/MARKETING_IMAGES.md` – this file

## Files modified

- `frontend/package.json` – added script `generate-marketing-images`; `sharp` in devDependencies
- `frontend/src/pages/public/HomePage.js` – hero uses `/images/marketing/hero-command-centre.png` + caption; feature section uses `/images/marketing/feature-expiry-list.png`; ProductScreenshot wrapper; priority/lazy and width/height on images
- `frontend/src/pages/public/CVPLandingPage.js` – hero uses `hero-command-centre.png`; Reminders section uses `support-calendar.png`; ProductScreenshot wrapper
- `frontend/src/components/public/index.js` – export `ProductScreenshot`

## Routes changed

None. `/demo` already redirects to `/risk-check`. No new or removed routes.

## Usage in pages

- **Hero image**: `fetchPriority="high"`, explicit `width`/`height`, caption “Illustrative portfolio example. Live score generated after structured assessment.”
- **Other images**: `loading="lazy"`, `width`/`height` to avoid layout shift.
- All screenshots use `<ProductScreenshot>` for consistent styling.
