# Audit: Marketing Screenshot Previews (Task vs Codebase)

**Implementation completed.** Summary of changes below.

## Files changed (implementation)

| File | Change |
|------|--------|
| `frontend/src/components/public/MarketingImage.js` | **New.** PNG-first image component: `src="/images/marketing/{name}.png"`, onError fallback to `.svg`, dev-only console warning, optional placeholder if both fail. |
| `frontend/src/components/public/index.js` | Export `MarketingImage`. |
| `frontend/src/pages/public/HomePage.js` | Replaced two `<img>` + local error state with `<MarketingImage name="hero-command-centre" />` and `<MarketingImage name="feature-expiry-list" />`. Removed `useState` for image errors. |
| `frontend/src/pages/public/CVPLandingPage.js` | Replaced two `<img>` + local error state with `<MarketingImage name="hero-command-centre" />` and `<MarketingImage name="support-calendar" />`. Removed `useState` for image errors. |
| `frontend/docs/MARKETING_IMAGES.md` | Updated overview: PNG as single source of truth, absolute paths, SVG fallback; usage notes for `<MarketingImage>`. |

**Folder and filenames:** `frontend/public/images/marketing/` already exists. Required PNG names (exact): `hero-command-centre.png`, `feature-expiry-list.png`, `support-calendar.png`. Currently only SVGs are committed; PNGs can be added via `npm run generate-marketing-images` (with raw files in `public/images/raw/`) or by committing the PNGs. Until then, `<MarketingImage>` shows the existing SVGs.

**All image `src` values:** Implemented via `<MarketingImage name="…" />` which resolves to absolute paths only: `/images/marketing/hero-command-centre.png` (then `.svg` on error), `/images/marketing/feature-expiry-list.png`, `/images/marketing/support-calendar.png`. No relative paths; no imports from `src/assets` for these images.

---

## Task summary

- **Goal:** Fix broken marketing screenshot previews on Vercel; make image rendering reliable and consistent.
- **Required decision:** Store images in `frontend/public/images/marketing/` and reference via absolute paths starting with `/`.
- **Required filenames (exact, case-sensitive):** `hero-command-centre.png`, `feature-expiry-list.png`, `support-calendar.png`.

---

## 1. What is already implemented

| Requirement | Status | Details |
|-------------|--------|---------|
| Folder `frontend/public/images/marketing/` | ✅ Exists | Contains `.gitkeep` and three **SVG** files (see below). |
| Absolute paths (no relative) | ✅ Yes | All `<img src="...">` use `/images/marketing/...` (leading slash). |
| Single location (public, not src) | ✅ Yes | No marketing screenshots in `src/assets`; all references point to `public/images/marketing/`. |
| Consistent spelling | ✅ Yes | All use `hero-command-centre` (UK), `feature-expiry-list`, `support-calendar`. No `center` or `calender` in code. |
| Route-independent paths | ✅ Yes | Absolute paths; safe on `/`, `/about`, `/compliance-vault-pro`, etc. |

**Current image references (all absolute):**

- **HomePage.js** (2):  
  - `/images/marketing/hero-command-centre.svg`  
  - `/images/marketing/feature-expiry-list.svg`
- **CVPLandingPage.js** (2):  
  - `/images/marketing/hero-command-centre.svg`  
  - `/images/marketing/support-calendar.svg`

**Current files in `public/images/marketing/`:**

- `hero-command-centre.svg`
- `feature-expiry-list.svg`
- `support-calendar.svg`
- `.gitkeep`

**No PNGs** with the three required names exist in the repo. The task asks for `.png`; the current implementation uses `.svg` by design (see conflict below).

---

## 2. What is missing vs task

| Task step | Status | Notes |
|-----------|--------|--------|
| Ensure PNGs exist with exact names | ❌ Missing | Repo has SVGs only. PNGs would need to be added or generated. |
| References use `.png` | ❌ No | All references use `.svg`. |
| Dev-only `onError` console warning | ❌ Missing | No helper for `<img>` onError in dev. |
| Verification (build + URLs + subroutes) | N/A | To run after changes. |

---

## 3. Conflict: SVG vs PNG

**Task says:**

- “Ensure these files exist with EXACT names: … `.png`”
- “Confirm the images still load when visiting subroutes”
- “Confirm Homepage and CVP page show **real screenshots, not placeholders**”

**Current design (see `docs/MARKETING_IMAGES.md`):**

- **SVG placeholders** are committed so images always load without a build step.
- **PNGs** are optional: produced by `scripts/generateMarketingImages.js` (sharp) from raw screenshots in `public/images/raw/`; script is run manually or in CI (“optionally run before `npm run build`”).
- Pages reference SVGs by default; doc says to “change the page `src` from `.svg` to `.png`” when PNGs are available.

So:

- **Current:** Reliable loading (SVG), optional “real” screenshots (PNG via script).
- **Task:** Reliable loading + “real screenshots” + **required** PNG filenames and absolute paths.

**Recommended approach (safest / most professional):**

1. **Adopt the task’s single source of truth: PNG in `public/images/marketing/`.**
2. **Ensure the three PNGs exist** in that folder with exact names:
   - Either **commit** the three PNGs (from existing design or from running `npm run generate-marketing-images` with raw assets in `public/images/raw/`), **or**
   - Add a **prebuild step** in CI/Vercel that runs `generate-marketing-images` when raw files exist, and commit at least minimal/placeholder PNGs so the build never ships without them.
3. **Switch all four `<img src="...">` references** from `.svg` to `.png` (paths stay absolute).
4. **Optional fallback:** If you want to keep SVGs as fallback when a PNG is missing (e.g. local dev without raw assets), use the same absolute path for PNG and add `onError` to switch to the `.svg` for that slot. Otherwise, use PNG only and rely on step 2 to guarantee files exist.
5. **Do not** use relative paths or `src/assets` for these marketing images.
6. **Spelling/case:** Keep `hero-command-centre.png`, `feature-expiry-list.png`, `support-calendar.png` everywhere (already correct in script and docs).

This keeps one canonical location and extension (PNG), avoids duplication (no second “marketing” tree elsewhere), and avoids route-dependent breakage (absolute paths already in place).

---

## 4. Mismatch audit (spelling / case)

- **centre vs center:** All code and script use `centre`. Task specifies `hero-command-centre.png`. ✅ No change.
- **.png vs .PNG:** Script and docs use lowercase `.png`. ✅ Use `.png` everywhere.
- **support-calendar:** No `support-calender` in page code; script accepts `support-calender.png` as alternate **input** name only. Output is `support-calendar.png`. ✅ No conflict.

No other marketing image filenames or capitalisation variants found in the codebase.

---

## 5. Files to touch (when implementing)

| File | Change |
|------|--------|
| `frontend/public/images/marketing/` | Ensure `hero-command-centre.png`, `feature-expiry-list.png`, `support-calendar.png` exist (add or generate). |
| `frontend/src/pages/public/HomePage.js` | Replace `.svg` with `.png` in both `src` (keep absolute paths). Optionally add dev-only `onError` (see below). |
| `frontend/src/pages/public/CVPLandingPage.js` | Replace `.svg` with `.png` in both `src` (keep absolute paths). Optionally add dev-only `onError`. |
| New small helper (e.g. `frontend/src/components/public/MarketingImage.js` or inline) | Dev-only: log console warning on `<img onError>` when `process.env.NODE_ENV === 'development'`. Use for the three marketing images only. |
| `frontend/docs/MARKETING_IMAGES.md` | Update to state PNG as default in `public/images/marketing/`, SVGs optional fallback if you keep onError; or remove SVG default and document PNG-only. |

**No changes** needed to:

- `ProductScreenshot.js` (does not alter `src`).
- `scripts/generateMarketingImages.js` (already outputs correct PNG names; can stay as-is for generation).
- Any other routes or assets.

---

## 6. Verification checklist (after implementation)

- [ ] `npm run build` succeeds.
- [ ] These URLs return the correct image (200, correct content-type):
  - `/images/marketing/hero-command-centre.png`
  - `/images/marketing/feature-expiry-list.png`
  - `/images/marketing/support-calendar.png`
- [ ] Homepage and CVP page show the intended screenshots (not broken placeholders).
- [ ] Direct load of subroutes (e.g. `/about`, `/compliance-vault-pro`) still shows the images (absolute paths).
- [ ] Dev-only: trigger an intentional broken `src` and confirm console warning appears; production build has no extra noise.

---

## 7. Summary

- **Implemented:** Folder, absolute paths, public-only location, consistent spelling, no route-dependent paths.
- **Missing:** PNG files with exact names, references switched from `.svg` to `.png`, dev-only `onError` warning.
- **Conflict:** Current design uses SVG-by-default for reliability; task requires PNG and “real screenshots.” **Recommended:** Make PNG the single source of truth in `public/images/marketing/`, ensure the three PNGs exist (committed or via prebuild), and update all `<img src="...">` to the absolute paths ending in `.png`. Optionally keep SVG as fallback via `onError` for dev only.
