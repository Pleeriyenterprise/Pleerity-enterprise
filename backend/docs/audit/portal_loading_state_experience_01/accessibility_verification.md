# Accessibility verification

## Implemented

| Requirement | Implementation |
|-------------|----------------|
| `aria-live` loading announcements | `PortalLoadingState` and `PortalCardLoading` use `role="status"` + `aria-live="polite"` |
| Screen-reader stage updates | `sr-only` live region announces active stage label in `PortalLoadingState` |
| No infinite spinners without text | All spinners paired with visible text labels |
| Mobile readability | `break-words`, `min-w-0`, responsive padding (`p-3 sm:p-4`), no hidden loaders |
| Stage list semantics | `<ul aria-label="Loading progress">` with per-stage `sr-only` status prefix |

## Manual checks (post-deploy)

- [ ] VoiceOver / NVDA: Today loading stages announced in order
- [ ] 390px viewport: loading card text wraps without horizontal scroll
- [ ] Error Retry button reachable via keyboard on Today
- [ ] Loading panel does not trap focus (non-modal)

## Unit test coverage

- `PortalLoadingState.test.js` — status role + title + stages
- `PortalCardLoading.test.js` — `aria-live="polite"`
