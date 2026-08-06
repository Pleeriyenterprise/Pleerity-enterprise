# Staging Frontend Deployment Validation

**Audit ID:** `PRODUCTION-READINESS-CLOSURE-01`  
**Date:** 2026-08-06

## Action

Promoted the develop preview that contains capacity UX to the stable staging alias:

```text
vercel alias set \
  pleerity-enterprise-9jjg-a95yt58aq-victory-aigbochies-projects.vercel.app \
  pleerity-enterprise-9jjg.vercel.app
```

Deployment ID: `dpl_Gd6LmXvF4Rs7zAdxWNnSpHU2tQ7F`  
Project: `pleerity-enterprise-9jjg`  
Stable URL: https://pleerity-enterprise-9jjg.vercel.app

A follow-up develop push (`7d8e3648`) triggered a newer preview build; alias should track the Ready build that includes the same capacity UX.

## Bundle verification

| Check | Result |
|-------|--------|
| Prior stale bundle | `main.53b8a4d1.js` — **no** capacity string |
| After alias (final) | `main.7f15f5f8.js` (from `9jjg-2c0rtmdv6`) |
| `DATABASE_CAPACITY_EXCEEDED` in bundle | **True** |
| User message fragment `system capacity issue` | **True** |
| `Please try again shortly` | **True** |
| Cache after alias | `x-vercel-cache: MISS`, `age: 0` (then HIT on recheck) |
| Bundle SHA-256 (16 hex) | `5b6fa61281212c52` |

## Notes

- Do not use `vercel deploy --prod` on `pleerity-enterprise` (production domain).
- Staging authority is the `9jjg` project + alias only.
- Backend continues to target `https://pleerity-enterprise.onrender.com`.
