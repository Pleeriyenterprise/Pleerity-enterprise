# Design system governance — Pleerity Brand v1.0

**Scope:** Compliance Vault Pro, client portal, admin portal, and related Pleerity marketing surfaces that share the React frontend.  
**Non-goals:** Backend authority, scoring, notifications, or API contracts — this document governs **presentation only**.

**Brand owner:** Pleerity Enterprise Ltd  
**Tagline:** AI-Driven Solutions & Compliance  
**Positioning:** Trust, authority, operational intelligence, calm professionalism, modern enterprise SaaS (comparable discipline to Stripe / Notion / Linear / Plaid — not consumer hype).

---

## 1. Canonical sources (drift prevention)

| Layer | Path | Use |
|-------|------|-----|
| Brand copy, logo URLs, core hex | `frontend/src/config/branding.js` | `branding.colors`, `branding.surfaces`, `branding.text`, `branding.chart`, `branding.typography` |
| Charts, inline styles, legacy hex | `frontend/src/design-tokens.js` | `colors`, `chartDonutPalette`, `chartTokens` |
| Global CSS variables (shadcn) | `frontend/src/index.css` | `:root` HSL tokens — **must** stay aligned with Brand v1.0 |
| Tailwind extensions | `frontend/tailwind.config.js` | `midnight-blue`, `electric-teal`, `brand-*` utilities |
| User-visible tokens → copy | `frontend/src/utils/presentationLanguage.js` | `operationalLabelForToken` — see [Presentation language governance](./PRESENTATION_LANGUAGE_GOVERNANCE.md) |

**Rule:** No new hardcoded `#RRGGBB` in feature code unless justified (e.g. third-party embed) and logged in PR description.

**Midnight blue:** `#0B1D3A` only — **never** `#0B1D3` (truncated / typo).

---

## 2. Approved colour system

| Role | Hex | Usage |
|------|-----|--------|
| Midnight Blue | `#0B1D3A` | Navigation, headers, dashboard chrome, professional document headings |
| Electric Teal | `#00B8A9` | **Primary CTA buttons**, links, active UI states, score highlights |
| Success / compliant | `#10B981` | Positive compliance / success (risk indicator — not legal proof) |
| Warning / expiring | `#F59E0B` | Moderate risk, expiring soon |
| Critical / overdue | `#EF4444` | Overdue, failed checks, destructive |
| Informational | `#3B82F6` | Neutral information |
| App background | `#F8FAFC` | Page canvas |
| Card surface | `#FFFFFF` | Cards, modals |
| Border | `#E5E7EB` | Dividers, table borders |
| Primary text | `#111827` | Body emphasis |
| Secondary text | `#6B7280` | Captions, meta |
| Chart trend secondary | `#64748B` | Non-primary series |
| Chart baseline | `#E5E7EB` | Reference / grid |

---

## 3. Typography

| Use | Font | Weights |
|-----|------|---------|
| Headings | Montserrat | SemiBold / Bold |
| Body / UI | Inter | Regular / Medium |

**Implementation:** Google Fonts import in `src/index.css`; `h1–h6` use Montserrat; `body` uses Inter.

---

## 4. Component ownership

| Component | Location | Notes |
|-----------|----------|--------|
| Button | `src/components/ui/button.jsx` | **Default** = Electric Teal CTA. `secondary` = muted neutral. `link` = teal. `destructive` = red. |
| Card / Form primitives | `src/components/ui/*` | Use shadcn patterns; no duplicate button systems. |
| Client shell | `ClientPortal`, layouts | Prefer `bg-background` (canvas) + white cards. |

**Forbidden:** Feature-specific parallel `Button` implementations with bespoke colour stacks.

---

## 5. Spacing, radius, elevation

- Prefer consistent padding: card `p-4`–`p-6`, section gaps `gap-4`–`gap-6`.
- Radius: `--radius` base `0.5rem`; cards may use `rounded-lg` / `rounded-xl` consistently within a surface.
- Shadows: subtle only — avoid heavy drop shadows that read “consumer startup.”

---

## 6. Mobile standards

- Minimum tap targets: use `.tap-target` utility where applicable (`index.css`).
- Modals: `.portal-modal-scroll` — content must not trap off-screen on small viewports.
- Filters: stack vertically on narrow screens; preserve horizontal scroll only for tables — not whole page.

---

## 7. Accessibility

- Maintain WCAG-oriented contrast for text on Midnight and on white/teal buttons.
- Focus rings: use `focus-visible:ring-ring` (teal ring) on interactive elements.
- Do not rely on colour alone for compliance state — pair with labels / icons already supplied by domain copy.

---

## 8. Async honesty & authority (visual)

**Must not imply:**

- Instant legal truth or regulator-grade finality  
- Guaranteed verification because the UI is green  
- Completed authority reconciliation when backend may still be pending  

**Must preserve:**

- Existing pending / recalculation / notice patterns driven by API (e.g. `compliance_score_pending`, propagation notices, queue timing)  
- Copy that matches `PILOT_LAUNCH_GOVERNANCE.md` and client status authority docs  

**Rule:** Visual success (green) follows **data** — do not add decorative “all done” treatments that contradict payload semantics.

---

## 9. Knowledge Centre & documentation surfaces

- Use `.help-article-markdown` styles (`index.css`) — headings Midnight, links Electric Teal.
- Public KB and in-app Help should feel like **enterprise documentation**, not internal admin tooling — same typography and card patterns as the portal where possible.

---

## 10. Forbidden UI patterns

- Beige / pink “chat app” mock chrome for enterprise previews (use neutral slate + subtle semantic tint).
- Rainbow chart palettes unrelated to brand semantic colours.
- Arbitrary per-page `bg-[#...]` except rare charts — use tokens.
- “Hype” visuals: exaggerated AI iconography, neon gradients unrelated to brand.
- Consumer-style oversized rounded “pill” overload on dense operational pages.

---

## 11. Change control

1. Any change to `branding.js` primary palette requires **this doc** + `LAUNCH_AUTHORITY_TRACKER.md` UI section update.  
2. Marketing site and portal must stay visually coherent — if `FEATURE_MATRIX` or pricing changes, **no** visual change should imply ungated features.  
3. PRs touching `index.css` `:root` or `button.jsx` variants: require **design review** label for pilot week.

---

## 12. Deferred work (continuous)

- Burn down remaining page-level `bg-[#...]` and legacy teal-only chart paths to `chartDonutPalette` / `brand-*`.  
- Align all marketing CTAs that manually duplicate `bg-electric-teal` with the Button default variant where appropriate.  
- Optional: `@tailwindcss/typography` for long-form only — evaluate bundle impact.

---

## 13. Plan gating & upgrade discoverability (presentation)

**Scope:** Client portal only — copy, hierarchy, and calm discoverability. **Out of scope:** `FEATURE_MATRIX`, enforcement, entitlements, Stripe, routing, API contracts.

- **No hostile gating:** Avoid punitive “locked”, red “blocked” chrome, fear-based urgency, or repeated upgrade modals/toasts in one flow. Prefer slate/neutral surfaces and operational language (scale, automation, portfolio maturity).
- **No upgrade fatigue:** At most one prominent discoverability surface per viewport for the same intent; avoid lock icons scattered across every row.
- **No stacked discoverability:** Do not combine multiple full upgrade cards, marketing “preview” billboards, and header billing CTAs for the same capability in one viewport — use **discoverability budgeting** (see `PLAN_GATING_UX_GOVERNANCE.md` §12).
- **No discoverability saturation:** Avoid multiple teal Billing CTAs stacked vertically on dashboard or settings — one calm path is enough.
- **Operational-first viewport hierarchy:** Operational tasks and inbox/compliance content must appear **before** tier-expansion copy on dense pages (dashboard, property hub, reports).
- **Operational CTA priority:** In plan-gated *workflow* surfaces, the primary control must complete or redirect the user’s operational task (e.g. upload evidence, log issue, view requirements). Billing / “View plans” is **secondary** (outline or ghost), never the only obvious path out of urgent remediation.
- **Discoverability placement:** Put tier hints on the **natural surface** for that capability (reports scheduling on Reports, SMS on Notifications, webhooks on Integrations); avoid unrelated global banners.
- **Discoverability vs frustration:** Higher tiers should read as *optional capability*, not a judgement on the current plan. Solo and lower tiers should feel complete for core compliance operations.
- **Reuse:** Prefer `PlanGatingDiscoverability.jsx` and governed patterns in `docs/governance/PLAN_GATING_UX_GOVERNANCE.md` over ad hoc amber/red cards.

**Maintainer:** Frontend + design liaison — update this file when Brand v1.1 ships.
