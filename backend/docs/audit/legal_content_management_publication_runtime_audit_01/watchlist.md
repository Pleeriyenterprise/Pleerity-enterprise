# Legal content publication watchlist

- Classification: `PARTIAL` (convergence run `20260605T120217Z`)
- Implementation commit: `d5ef4b8d` — `fix(cms): publish legal content from governed CMS source`

## Verified on staging (convergence run)

- [x] Public API `/api/public/legal-content/{slug}` live with CMS + canonical fallback
- [x] Canonical seed idempotent (`canonical_seed_v1` provenance on 6/7 slugs)
- [x] All 7 public pages render CMS-backed content (Playwright screenshots)
- [x] Markdown sanitisation strips scripts on save
- [x] Reset-default works for all 7 slugs including `about`
- [x] Admin UI copy updated (`Save & Publish`, `auth_token` fix)
- [x] Restore-to-version API (`POST /{slug}/restore/{version}`)
- [x] Permissions enforced; public API does not leak audit metadata
- [x] Terms include SaaS subscription / recurring billing / Stripe language
- [x] Regression: `test_legal_content_publication.py` passes

## Remaining for VERIFIED_OPERATIONALLY

- [ ] **edit→public marker probe:** careers slug was left at 18 chars during audit permutations; harness now pre-resets. Re-run `legal_content_publication_convergence_01_execute.py` after `POST /careers/reset-default`.
- [ ] **Frontend CDN:** confirm Vercel deploy of `PublicLegalContentPage.jsx` fully propagated (rendering probe passed on run 3).
- [ ] Admin UI: add restore-to-version button (API exists).

## Optional

- [ ] Tune `Cache-Control` on public legal API if propagation delay >60s observed
- [ ] Re-seed careers if content drift detected
