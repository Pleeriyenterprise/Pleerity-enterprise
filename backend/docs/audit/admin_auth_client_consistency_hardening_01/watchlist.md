# Admin auth client watchlist

- Classification: `VERIFIED_OPERATIONALLY`
- Browser closeout run: `20260606T174543Z`
- Hardening commit: `b0d7bd41`
- Staging bundle: `main.db99e2f1.js`

## Verified

- [x] Hardened frontend bundle deployed on staging
- [x] Newsletter dashboard shows 11 subscribers in browser
- [x] Kit Sync column, export CSV, refresh operational
- [x] Invalid JWT shows auth error (not fake empty) on newsletter, FAQ, insights
- [x] Regression tests pass

## Follow-up (non-blocking)

- [ ] Migrate `AdminContactEnquiriesPage` to `adminAPI` + `useAuthenticatedQuery`
- [ ] Migrate `AdminBlogPage`, `AdminServiceCataloguePage` off manual fetch
- [ ] Remove dead `AdminOrdersPage.old.js`
