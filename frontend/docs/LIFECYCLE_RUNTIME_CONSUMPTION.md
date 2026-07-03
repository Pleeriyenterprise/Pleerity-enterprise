# Lifecycle Runtime Consumption (Frontend)

**Programme:** ILP-3-PORTAL-MODE-CONSUMPTION-01

---

## Provider

`LifecycleRuntimeProvider` is mounted in `App.js` inside `EntitlementsProvider`.

### Hooks

| Hook | Use |
|------|-----|
| `useLifecycleRuntime()` | Full runtime contract + refetch |
| `usePortalMode()` | Presentation-only: `portalMode`, `customerExperience`, `navigationPolicy` |

**Never use `portalMode` for permission checks.**

---

## Lifecycle Shell

`LifecycleShell` renders in `ClientPortalLayout` above page content:

- Governed heading, explanation, reason, CTAs
- Fallback message when runtime unavailable (no Error Boundary)
- Read-only route hint (presentation only)

---

## Page integration

- `PortalModePageBanner` — compact per-page indicator
- `PortalPageWithLifecyclePresentation` — page root wrapper
- `PortalPageShell` — includes banner for shell-based pages

---

## Navigation

`annotateNavWithLifecyclePolicy()` adds `lifecycleNavHint` to nav items:

- `locked`, `read_only`, `de_emphasized`, `normal`

Routes are **not removed** — only visual presentation changes.

---

## Diagnostics

- Development: always available via `<LifecycleRuntimeDiagnostics />`
- Production: append `?lifecycle_debug=1` to any client portal URL

---

## Fallback behaviour

When `GET /api/client/lifecycle-runtime` fails:

- `portalMode` defaults to `FULL_ACCESS` presentation fallback
- User sees safe governed message
- Permissions remain on legacy entitlements path

---

## Tests

```bash
cd frontend
npm test -- --testPathPattern="LifecycleRuntime|portalNavigationPolicy|ClientPortalLayout.navigation" --watchAll=false
```
