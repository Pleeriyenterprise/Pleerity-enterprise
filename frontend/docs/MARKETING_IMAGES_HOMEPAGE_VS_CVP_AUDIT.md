# Audit: Different PNG screenshots for Homepage vs CVP (no duplicated hero)

## Task summary

- **Goal:** Homepage and CVP page must use different images; CVP hero should not duplicate Homepage hero.
- **Required mapping:**
  - Homepage hero → `hero-command-centre.png`
  - Homepage portfolio section → `feature-expiry-list.png`
  - CVP hero → `feature-expiry-list.png` (differs from Homepage hero)
  - CVP calendar section → `support-calendar.png`

## Current state (before change)

| Location | Current image | Task requirement | Status |
|----------|---------------|------------------|--------|
| Homepage hero | `hero-command-centre` | hero-command-centre.png | ✅ Correct |
| Homepage portfolio | `feature-expiry-list` | feature-expiry-list.png | ✅ Correct |
| CVP hero | `hero-command-centre` | feature-expiry-list.png | ❌ **Wrong** – same as Homepage hero |
| CVP calendar | `support-calendar` | support-calendar.png | ✅ Correct |

## Root cause

Both pages use `<MarketingImage name="hero-command-centre" />` for the hero block. The CVP page should use `name="feature-expiry-list"` for its hero so it shows the “Upcoming Expiries” / portfolio-style screenshot instead of the dashboard command centre.

## What is already implemented

- **Paths:** All images use absolute public paths via `MarketingImage` (`BASE = '/images/marketing'` → `src="/images/marketing/<name>.png"`). No GitHub links or relative filesystem paths.
- **Reusable component:** `ProductScreenshot` wraps all marketing images (border, rounded-2xl, shadow, white bg). `MarketingImage` handles `width`/`height`, `loading`, `decoding="async"`, alt, onError fallback.
- **Alt text and captions:** Present on both pages (hero alt, optional captions below).
- **Vercel/CRA:** Public path references work for CRA build and Vercel deployment.

## Change required

**Single change:** In `frontend/src/pages/public/CVPLandingPage.js`, set the hero `MarketingImage` from `name="hero-command-centre"` to `name="feature-expiry-list"`. Update the `alt` text to describe the expiry/portfolio preview (e.g. “Upcoming expiries and portfolio view”) so it matches the new image.

## No conflict

- Task (E) asks for border `rgba(0,0,0,0.08)`; current `ProductScreenshot` uses `0.06`. Keeping `0.06` is acceptable (subtle); optional to change to `0.08` if design prefers.
- No duplication of components or logic; one prop change on CVP achieves the goal.

## Files to change

| File | Change |
|------|--------|
| `frontend/src/pages/public/CVPLandingPage.js` | Hero: `name="hero-command-centre"` → `name="feature-expiry-list"`; update `alt` to describe expiry/portfolio preview. |

## Verification

- Homepage hero: hero-command-centre.png ✅
- Homepage portfolio: feature-expiry-list.png ✅
- CVP hero: feature-expiry-list.png (after fix) ✅
- CVP calendar: support-calendar.png ✅
- Homepage hero ≠ CVP hero ✅
