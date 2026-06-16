# Feature flag design — customer_status_projector_v2

**Programme:** S2-CUSTOMER-STATUS-PROJECTOR-IMPLEMENTATION-PLAN-01  
**Status:** DESIGN ONLY — do not implement in this phase

---

## Flag identity

| Item | Value |
|------|-------|
| **Logical name** | `customer_status_projector_v2` |
| **Config module** | `backend/services/customer_status_projector_config.py` |
| **Resolver** | `get_customer_status_projector_mode() -> Literal["disabled", "shadow", "active"]` |

---

## Modes

| Mode | Projector executes | Divergence logged | Customer-visible status authority | `customer_status_*` on API |
|------|-------------------|-------------------|-----------------------------------|----------------------------|
| `disabled` | No | No | `derive_truth_presentation` | Absent |
| `shadow` | Yes | Yes | `derive_truth_presentation` (legacy) | Present but non-authoritative |
| `active` | Yes | Yes (optional sample) | `customer_status_projector_v2` | Authoritative |

---

## Configuration source

| Layer | Mechanism | Precedence |
|-------|-----------|------------|
| **Primary** | Environment variable | Highest |
| **Secondary** | Per-tenant admin pilot flag (future) | Overrides env for tenant cohort only |
| **Tertiary** | Server default constant | `disabled` |

### Environment variable

| Item | Value |
|------|-------|
| **Name** | `CUSTOMER_STATUS_PROJECTOR_V2_MODE` |
| **Valid values** | `disabled`, `shadow`, `active` (case-insensitive) |
| **Invalid value** | Log warning; treat as `disabled` |

### Pattern alignment

Follow `evidence_review_config.py` env pattern; tri-state string (not boolean) because shadow is required.

### API exposure (read-only)

```json
"server_feature_flags": {
  "customer_status_projector_v2_mode": "shadow"
}
```

Expose on `GET` client/admin bootstrap payloads alongside `evidence_review_v2_enabled` — **read-only in S2**; no admin PATCH for this flag in S2 PR (ops env flip only).

---

## Default per environment

| Environment | Default on deploy | After S2 merge |
|-------------|-------------------|----------------|
| Local dev | `disabled` | Developer sets `shadow` for testing |
| CI | `shadow` | Exercises projector + shadow tests |
| Staging | `disabled` → `shadow` | `shadow` within 24h of merge |
| Production | `disabled` | `shadow` only after staging G1–G6 |

**Never default `active`** in any environment on first deploy.

---

## Rollback behaviour

| Trigger | Action | Data impact |
|---------|--------|-------------|
| Enrich error rate spike | `active` → `shadow` | None |
| Badge contradiction report | `active` → `shadow` | None |
| Projector exception storm | `shadow` → `disabled` | None |
| Bad deploy | Redeploy with `disabled` | None |

Rollback is **env var flip only** — no Mongo migration, no row backfill.

### Rollback ordering

1. Set `CUSTOMER_STATUS_PROJECTOR_V2_MODE=shadow` (keeps observability)
2. If enrich broken: set `disabled`
3. Redeploy not required if runtime reads env on each request (implement refresh per request or 60s cache max)

---

## Logging behaviour

| Mode | Log events |
|------|------------|
| `disabled` | None |
| `shadow` | `customer_status_projector_divergence` on mismatch; 100% staging |
| `active` | Invariant violations; sampled divergence if legacy mirror ≠ projector (should be 0) |

### Flag transition audit

Log `customer_status_projector_mode_transition` with `{ from, to, environment }` on mode change detection — no PII.

---

## Relationship to other flags

| Flag | Interaction |
|------|-------------|
| `FEATURE_EVIDENCE_REVIEW_V2` | Queue membership **input** — independent |
| `customer_status_projector_v2` | Presentation only — does not change review workflow |

---

## Implementation tasks (S2 PR — not this phase)

| Task | File |
|------|------|
| 2.9.1 | Create `customer_status_projector_config.py` |
| 2.9.2 | Wire into `enrich_requirement_dict` |
| 2.9.3 | Expose on `routes/client.py` + `routes/admin.py` |
| 2.9.4 | Document in ops runbook (not governance doc edit unless requested) |

---

## Per-tenant pilot (optional post-S2)

| Item | Design |
|------|--------|
| Mechanism | Reuse `PATCH /api/admin/ops/clients/{id}/feature-flags` pattern |
| Key | `customer_status_projector_v2_mode` |
| Scope | Staging pilot tenants first |
| S2 PR | **Out of scope** — env-only in initial release |
