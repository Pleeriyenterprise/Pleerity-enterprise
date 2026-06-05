# Legal content publication watchlist

- Classification: `PARTIAL`
- Run tag: `20260605T111338Z`

## P0 — publication wiring
- [ ] Wire public legal/marketing pages to `legal_content` (public read API or SSR publish step).
- [ ] Update admin UI copy: distinguish draft CMS vs live publish, or implement instant publish.
- [ ] Add cache-bust / revalidation when legal content changes.

## P1 — governance hardening
- [ ] Add server-side markdown/HTML sanitisation on `PUT /admin/legal-content/{slug}`.
- [ ] Add `about` to reset-default map (currently 400).
- [ ] Fix `AdminLegalContentPage.jsx` `loadAllContent` scope in reset handler.
- [ ] Add restore-to-version endpoint (versions are read-only today).
- [ ] Add `tests/test_admin_legal_content.py` covering save, reset, permissions, versions.

## P2 — content alignment
- [ ] Seed admin CMS from current static JSX canonical copy (one-time migration).
- [ ] Align Terms with SaaS subscription/billing model (Stripe recurring, plan changes, admin cancellation).
- [ ] Review Accessibility statement claims vs actual WCAG testing evidence.

## Verified on this run
- [x] Admin edit/save/version increment/restore on careers (staging, marker restored).
- [x] cookies reset-default + restore; about reset correctly blocked.
- [x] Permissions: non-admin cannot edit; public pages readable.
- [x] Public footer links and page render (Playwright screenshots).
