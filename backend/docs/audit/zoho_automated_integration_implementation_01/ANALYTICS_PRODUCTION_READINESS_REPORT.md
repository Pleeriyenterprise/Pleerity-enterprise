# Analytics Production Readiness Report

**Programme:** PHASE_B_ANALYTICS_OPERATIONAL_HARDENING_01  
**Date (UTC):** 2026-07-14  
**Audience:** Platform / ops governance  

---

## Final verdict

# ANALYTICS_PRODUCTION_READY_WITH_CONDITIONS

---

## Why not unconditional READY

Unattended continuous production (“set and forget”) is **not** yet justified without deliberate acceptance of the following residual conditions. Declaring plain `ANALYTICS_PRODUCTION_READY` would overstate operational maturity relative to Stage H9.

---

## What operators can trust today

| Capability | Status |
|------------|--------|
| Pleerity remains SoR; Analytics append-only | Proven |
| Option B OAuth + token cache | Proven |
| Stable UTC reporting windows | Proven |
| Manual governed export | Proven on staging |
| Audit + sync history | Proven |
| Kill switch / integration flags | Proven |
| Duplicate same-period protection | Hardened (force override) |
| Config / payload preflight | Hardened |
| Soft-fail dead letter + replay resolve | Hardened |
| System Health `analytics_ops` | Hardened |
| Production isolation (no prod Zoho) | Proven historically |

---

## Conditions (must remain explicit)

1. **Manual jobs only** — no Zoho cron; `next_expected_export` remains operator-driven. Unattended daily schedule requires a separate authorised change.  
2. **Remote schema describe deferred** — live Zoho column/type probe not available under `data.create` alone; table drift still needs console discipline or future metadata scope.  
3. **HTTP client has no in-loop retry** — single 30s attempt; DL enables human replay, not automatic backoff.  
4. **Prior successful same-day export must be forced** — `force_reexport=true` for intentional duplicates.  
5. **Deploy + staging re-validation of hardening** — this package is code-complete with unit regression green; production enablement still needs governed staging re-test after deploy.  
6. **Mongo date storage consistency** — period filters use ISO strings; BSON datetime mismatch can undercount period metrics (monitor after first production window).  

---

## Recommended production posture

| Mode | Recommendation |
|------|----------------|
| Staging / pilot | Enabled with flags; manual export; observe `analytics_ops` |
| Production | Enable only after hardening SHA deploys and one supervised manual export; **keep cron off** until separate schedule gate |
| Kill switch | Retain as primary blast-radius control |

---

## Decision guide

| If governance requires… | Verdict path |
|-------------------------|--------------|
| Continuous unattended daily export immediately | **Not ready** until cron + remote schema + retry policy are separately signed off |
| Supervised / on-demand production Analytics | **Ready with conditions** (this verdict) |

---

## Verdict line (copy)

```
ANALYTICS_PRODUCTION_READY_WITH_CONDITIONS
```
