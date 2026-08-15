# Commercial Controls — Step-up runtime 02

**Audit ID:** `COMMERCIAL-CONTROLS-AUTHORITY-CORRECTION-AND-E2E-CERTIFICATION-02`  
**Date:** 2026-08-15

## Source (certified in unit/source tests)

`CommercialEntitlementControls` hosts `{stepUp.modal}` in `data-testid="commercial-step-up-modal-host"`. Execute uses `timeout: 60000`. Dialog does not close overlay while loading.

Deployed staging bundle `main.c8b6a433.js` contains `commercial-step-up-modal-host`.

## Live operator flow

**Not runtime-certified in this exercise.**

### Phase 1 lockout

Exercise 01 blocked on `POST /api/auth/admin/login` → **423 Locked** (`get_auth_lock_state`, portal `admin`, `AUTH_LOCK_EMAIL_MINUTES` default 15).

| Item | Finding |
| --- | --- |
| Root cause | Governed email lock after failed admin login attempts (threshold default 5) |
| Recovery used | Wait for lock expiry. Authentication controls were **not** weakened. Locks were **not** deleted. |
| This exercise login | **401 Invalid credentials** (lock no longer present) using the stored ops_verify temp password file |
| Operator | Intended: `aigbochievictory@gmail.com` / `ROLE_ADMIN` / step-up eligible via `commercial_entitlement_execute` |
| Blocker | Current staging admin password is not available in env (`STAGING_ADMIN_PASSWORD` unset) and the gitignored ops_verify temp password is stale |

A second password guess campaign was **not** run, to avoid re-triggering lockout.

Correct password / incorrect password / cancelled modal / expired token / timeout / duplicate submit therefore remain **unverified at runtime**.
