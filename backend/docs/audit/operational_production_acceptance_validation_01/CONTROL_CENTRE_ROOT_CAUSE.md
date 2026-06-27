# Control Centre Failure — Root Cause Analysis

**Programme:** OPERATIONAL-PRODUCTION-ACCEPTANCE-VALIDATION-01  
**Resolved:** 2026-06-27  
**Fix SHA:** `f2c1044279a900a12ece7607c671b4479f2241d0`

---

## Symptom

`GET /api/admin/control-centre/snapshot` returned **HTTP 500** (~28–33s) on staging while:

- Health summary returned **HTTP 200**
- Job runs and incidents APIs returned **HTTP 200**

---

## Failing component (runtime bisect)

| Step | Result | Latency |
|---|---|---|
| `build_health_summary_payload` | OK | ~16s |
| `get_security_dashboard_summary` | OK | ~1.3s |
| `_collect_engagement_block` | OK | ~0.4s |
| `summarize_workflow_drift_from_requirements_sample` | **FAIL** | ~2.8s |
| `get_control_centre_snapshot` (full) | **FAIL** | ~21s |

**Evidence:** `LOCAL_BISECT.json`

---

## Root cause

```
summarize_workflow_drift_from_requirements_sample
  → enrich_requirements_for_admin
    → build_compliance_timeline
      → _family_rules_for_requirement
        → normalize_requirement_code(slug).upper()   # slug truthy, normalize returns None
```

Staging requirements exist whose storage slug does not normalize to a canonical code. `normalize_requirement_code()` returns `None`; calling `.upper()` raised `AttributeError`, aborting the entire Control Centre snapshot.

This is **not** a timeout, revenue collector, or health-summary regression. It is an unhandled edge case in compliance timeline family resolution triggered by the workflow drift audit sample path.

---

## Fix

```python
# compliance_timeline.py — before
canonical = normalize_requirement_code(slug).upper() if slug else ""

# after
canonical = (normalize_requirement_code(slug) or "").upper() if slug else ""
```

Unnormalizable slugs fall through to semantics-based family rules instead of crashing.

---

## Post-fix validation (staging)

| Check | Result |
|---|---|
| Control Centre HTTP | **200** |
| Latency | **30.6s** (under 60s acceptance target) |
| Payload complete | system, automation, security, engagement, alerts, compliance_workflow_audit |
| Platform status | `critical` (reflects genuine P0/P1/P2 conditions — not false healthy) |
| Automation health score | 70 |
| Job confidence | 78 |

**Evidence:** `RUNTIME_ACCEPTANCE.json`, `CONTROL_CENTRE_BISECT.json` (post-deploy cc_status 200)

---

## Residual

Control Centre latency (~31s) is dominated by health summary build (~16s) plus workflow drift enrichment (~3s) plus engagement property scan. Acceptable for staging acceptance; monitor at production scale.
