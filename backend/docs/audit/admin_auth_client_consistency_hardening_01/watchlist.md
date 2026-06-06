# Admin auth client consistency watchlist

- Classification: `PARTIAL`
- Run tag: `20260606T172720Z`

## Deploy

- [ ] Deploy frontend with hardened AdminNewsletterPage / FAQ / Insights pages
- [ ] Re-run harness; expect `VERIFIED_OPERATIONALLY` when staging browser shows subscriber count

## Follow-up migrations

- [ ] Migrate `AdminContactEnquiriesPage` to adminAPI + useAuthenticatedQuery
- [ ] Migrate `AdminBlogPage`, `AdminServiceCataloguePage` off manual fetch
- [ ] Remove `AdminOrdersPage.old.js` dead code

## Completed

- [x] Zero legacy `localStorage.getItem('token')` reads
- [x] authStorage + axios interceptor centralization
- [x] AdminFetchStatePanel error surfaces
- [x] Newsletter API closeout (subscribe + admin count + Kit sync)
- [x] Backend + frontend regression tests
