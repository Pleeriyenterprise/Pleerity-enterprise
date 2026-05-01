# Internal support — Remediation Correlation View (v1)

**Audience:** Support, operations, and engineering using the **admin/support** API. **Not** for landlords or client JWT flows.  
**Companion:** `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` §11 (technical contract).

---

## Purpose

Give a **read-only, single-property** snapshot that **correlates** a known anchor (`gap_key`, maintenance `issue_id`, `work_order_id`, or `risk_signal_id`) with nearby persistence: gaps, issues, work orders, risk signals, a **capped** slice of `audit_logs`, `property_compliance_score_history`, and `score_change_log`.

Use it to **narrow investigations** (e.g. “does this gap have a bridge issue?” “any audits in window?” “score movement in the same window?”) — not to decide compliance outcomes or legal posture.

---

## Who may use it

- **Portal roles:** Owner, Admin, or Support (`require_support_or_above`).
- **Environment:** Staging or production **only** where the feature flag is intentionally enabled for investigation (see below).

Do **not** share responses with tenants as “official” compliance statements.

---

## Feature flag

| Variable | When enabled |
|----------|----------------|
| `FEATURE_REMEDIATION_CORRELATION_VIEW_V1` | `1`, `true`, or `yes` (case-insensitive) |

If disabled or unset: **`POST /api/admin/support/remediation-correlation-view` returns 404** — “Remediation correlation view is disabled”. This is expected in environments that have not turned the tool on.

Coordinate with platform/engineering before enabling in a shared environment.

---

## Example requests

**Endpoint:** `POST /api/admin/support/remediation-correlation-view`  
**Headers:** `Authorization: Bearer <staff_token>`, `Content-Type: application/json`

**Required body fields:** `client_id`, `property_id`, `entry: { "kind", "value" }`  
**Optional:** `as_of` (ISO8601 UTC), `window_half_days` (1–31, default 14 — days **before and after** `as_of` for supporting reads).

### 1. Anchor on a compliance gap

```json
{
  "client_id": "<tenant_client_id>",
  "property_id": "<property_id>",
  "entry": { "kind": "gap_key", "value": "<gap_key_from_gap_row_or_admin_tool>" },
  "window_half_days": 14
}
```

### 2. Anchor on a maintenance issue

```json
{
  "client_id": "<tenant_client_id>",
  "property_id": "<property_id>",
  "entry": { "kind": "issue_id", "value": "<issue_id>" }
}
```

### 3. Anchor on a work order

```json
{
  "client_id": "<tenant_client_id>",
  "property_id": "<property_id>",
  "entry": { "kind": "work_order_id", "value": "<work_order_id>" }
}
```

### 4. Anchor on a risk signal

```json
{
  "client_id": "<tenant_client_id>",
  "property_id": "<property_id>",
  "entry": { "kind": "risk_signal_id", "value": "<signal_id>" }
}
```

**Important:** `client_id` and `property_id` must match the anchor row. Wrong scope → **404** (“Anchor not found…”).

---

## How to interpret `non_authoritative`

Every successful response includes:

- **`non_authoritative`: `true`** — machine-readable flag.
- **`disclaimer`** — human-readable text stating the payload is **not** a source of truth for compliance posture, billing, or legal outcome.

If either is missing on a “success” path, treat the response as suspect and **escalate** (unexpected client or bug).

---

## How to interpret `closure_semantics` (per row)

Each `rows[0].closure_semantics` has four booleans — all **heuristic** and **read-derived**, not legal or billing verdicts:

| Field | Meaning (v1) |
|--------|----------------|
| **`compliance`** | Rough signal from **gap linkage** where applicable (e.g. linked gap `resolved`). **Not** proof of statutory compliance. |
| **`operational`** | Rough signal from **maintenance issue** or **work order** or **risk** terminal-style states on the anchor row. **Does not** prove gaps closed or evidence accepted. |
| **`inbox_visibility`** | Always **`false`** in v1 (Today / unified tasks / tenant inbox are out of scope). |
| **`diagnostic`** | **`true`** when any **`diagnostic_flags`** are present on the row (e.g. risk regen caution, bridge gap missing, score-change mapping advisory). |

**Do not** tell a customer “you are compliant” based on these booleans alone.

---

## What not to conclude from the view

- **“Today / inbox is clear ⇒ compliant”** — v1 does not read unified tasks or tenant inbox; `inbox_visibility` is always false.
- **“Risk gone ⇒ gap gone”** — risk and compliance gaps are **independent** layers.
- **“Work order completed ⇒ score/gap correct”** — not guaranteed without the wired evidence/outcome paths.
- **“This JSON is the audit trail”** — audits are **capped** and filtered; quiet gap sync may not appear as lifecycle audits (see `STREAM_F_FORENSICS_JOIN_RECIPE.md`).
- **“Score change log explains this gap”** — `requirement_key` in change logs maps to portal requirements with care; diagnostic `score_change_log_present_mapping_advisory` only fires when the loaded rows actually carry requirement-level mapping signals (not merely because rows exist).

---

## Known limitations

- **One property per call** — no portfolio-wide or client-wide correlation.
- **Anchors only:** `gap_key`, `issue_id`, `work_order_id`, `risk_signal_id` — **not** `requirement_id`-only (dedupe-by-requirement is unsafe for multiple gaps).
- **Caps** (truncation flags on the envelope when exceeded): audit logs 50; score history 20; score change log 20; linked issues 10; linked work orders 10.
- **No** documents collection, **no** requirements-as-primary anchor, **no** approvals/invoices, **no** new persisted “remediation” store.
- **Risk `signal_id`** can be **regenerated** on the property — `risk_signal_regen_possible` may appear on risk anchors.
- **`primary_snapshot`** contains real operational identifiers — handle as **internal PII**; do not paste into public channels.

---

## When to escalate to engineering

Escalate (ticket / Slack with `client_id`, `property_id`, `entry`, `request_id` if present) when:

1. **404** with flag **on** and you are sure the anchor exists in Mongo for that tenant/property (possible bug or mismatch).
2. **500** or timeouts on the endpoint.
3. **Obvious wrong linkage** (e.g. wrong `issue_ids` for a `gap_key` you can verify in DB) after double-checking IDs and property scope.
4. **Product/legal** question: whether a behaviour should be compliance-closing — engineering + compliance product own the matrix; this tool does not change workflows.
5. **Request to widen scope** (e.g. requirement-only anchor, second property, client-wide scan) — needs tracker/product approval, not ad-hoc API use.

---

## Document control

**Owner:** Platform / compliance product (with Support lead for wording). **Technical contract:** `STREAM_C_REMEDIATION_CORRELATION_RUNBOOK.md` §11. **Updates:** When v1 behaviour, caps, or flag name changes, update this note and §11 in the same PR.
