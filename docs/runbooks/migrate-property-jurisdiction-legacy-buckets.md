# Runbook: Migrate legacy scoring buckets out of `properties.jurisdiction`

**Purpose:** Remove historical data corruption where compliance recalc stored scoring buckets (`SCOTLAND`, `ENGLAND_WALES`, etc.) in `properties.jurisdiction`, and align stored data with the current model:

- **Portfolio label** → `properties.jurisdiction` (England, Wales, Scotland, Northern Ireland)
- **Scoring bucket** → `properties.scoring_jurisdiction_bucket` (`SCOTLAND` | `ENGLAND_WALES`)

**Script:** `backend/scripts/migrate_property_jurisdiction_legacy_buckets.py`

---

## Prerequisites

1. **Working directory:** repository `backend` folder (same layout as CI and local dev).

   - Linux/macOS: `cd /path/to/Pleerity-enterprise/backend`
   - Windows (PowerShell): `cd C:\path\to\Pleerity-enterprise\backend`

2. **Environment:** Use the **same** `MONGODB_URI` (and any related env vars) as the **production** API that serves client traffic. Confirm database name and cluster before running.

3. **Python:** Same interpreter / venv the backend uses in production or release tooling (dependencies that load `database.database`).

4. **Access:** Operator can connect to MongoDB from the machine running the script (VPN / IP allowlist / bastion as required).

5. **Backup (recommended before `--apply`):** MongoDB **snapshot**, **PITR**, or export of affected docs, e.g.:

   ```javascript
   // mongosh — export legacy rows only (example; adjust connection)
   const sc = { jurisdiction: /^scotland$/i };
   const ew = {
     $or: [
       { jurisdiction: /^england_wales$/i },
       { jurisdiction: /^england\/wales$/i },
       { jurisdiction: /^england wales$/i },
       { jurisdiction: "ENGLAND_WALES" },
     ],
   };
   // Use mongoexport or aggregate $out to a staging collection
   ```

---

## Step 1 — Count (no writes)

### Exact command

```bash
python -m scripts.migrate_property_jurisdiction_legacy_buckets --count
```

Optional machine-readable output (stdout JSON for monitoring / ticketing):

```bash
python -m scripts.migrate_property_jurisdiction_legacy_buckets --count --json
```

### Expected output

**Default (`--count`):** one log line to stderr (INFO), for example:

```text
INFO:migrate_property_jurisdiction_legacy_buckets:legacy_jurisdiction_migration_counts scotland_bucket=3 england_wales_bucket=12 total=15
```

Interpretation:

| Log segment | Meaning |
|-------------|---------|
| `scotland_bucket=N` | Documents where `jurisdiction` matches the legacy Scotland **bucket** token (case-insensitive `scotland` only). |
| `england_wales_bucket=M` | Documents where `jurisdiction` is `ENGLAND_WALES` or common variants (`england_wales`, `england/wales`, `england wales`). |
| `total=T` | `N + M` |

**With `--json`:** stdout only, for example:

```json
{
  "legacy_jurisdiction_scotland_bucket": 3,
  "legacy_jurisdiction_england_wales_bucket": 12,
  "legacy_jurisdiction_total": 15
}
```

If **both bucket counts are `0`**, there is nothing to migrate; skip `--apply`.

---

## Step 2 — Dry run (no writes)

### Exact command

```bash
python -m scripts.migrate_property_jurisdiction_legacy_buckets --dry-run
```

### Expected output

1. Same style of **count** lines as Step 1:

   ```text
   INFO:...:Found N properties with legacy SCOTLAND bucket in jurisdiction
   INFO:...:Found M properties with legacy ENGLAND_WALES bucket in jurisdiction
   ```

2. Up to **20 sample lines** per category:

   ```text
   INFO:...:  [dry-run] SCOTLAND→Scotland property_id=<id> client_id=<id> raw='scotland'
   ...
   INFO:...:  [dry-run] ENGLAND_WALES→clear jurisdiction, set bucket property_id=<id> client_id=<id> raw='ENGLAND_WALES'
   ```

3. If more than 20 rows in a category:

   ```text
   INFO:...:  ... and K more (Scotland bucket)
   INFO:...:  ... and L more (ENGLAND_WALES bucket)
   ```

Use samples to confirm `property_id` / `client_id` look like real production tenants and that raw values match the **legacy bucket** pattern (not legitimate user typos you need to handle separately).

---

## Step 3 — Apply (writes)

### Exact command

```bash
python -m scripts.migrate_property_jurisdiction_legacy_buckets --apply
```

Run during an agreed window if you want to coordinate with support (large `M` may briefly increase “missing jurisdiction” UX for EW-legacy rows until clients set labels).

### Expected output

1. **Before** updates:

   ```text
   INFO:...:Before apply: scotland_bucket=N england_wales_bucket=M
   ```

2. **Per updated document** (Scotland bucket rows):

   ```text
   INFO:...:Updated property_id=<id>: jurisdiction=Scotland, scoring_jurisdiction_bucket=SCOTLAND
   ```

3. **Per updated document** (England & Wales bucket rows):

   ```text
   INFO:...:Updated property_id=<id>: unset jurisdiction (ambiguous legacy), scoring_jurisdiction_bucket=ENGLAND_WALES
   ```

4. **Warnings** (if any doc matches the query but has no `property_id`):

   ```text
   WARNING:...:Skipping document without property_id: <_id>
   ```

5. **After** updates:

   ```text
   INFO:...:After apply: scotland_bucket=0 england_wales_bucket=0 (expect 0, 0)
   ```

If `After apply` does not show `0` and `0`, stop and investigate (partial failure, different DB, or new legacy writes during the run).

---

## Step 4 — Post-migration verification

### 4.1 Script verification (required)

```bash
python -m scripts.migrate_property_jurisdiction_legacy_buckets --count
```

**Pass criteria:** log line shows `scotland_bucket=0 england_wales_bucket=0 total=0`.

Optional:

```bash
python -m scripts.migrate_property_jurisdiction_legacy_buckets --count --json
```

**Pass criteria:** both `legacy_jurisdiction_scotland_bucket` and `legacy_jurisdiction_england_wales_bucket` are `0`.

### 4.2 MongoDB verification (optional cross-check)

```javascript
db.properties.countDocuments({ jurisdiction: /^scotland$/i })
// expect 0

db.properties.countDocuments({
  $or: [
    { jurisdiction: /^england_wales$/i },
    { jurisdiction: /^england\/wales$/i },
    { jurisdiction: /^england wales$/i },
    { jurisdiction: "ENGLAND_WALES" },
  ],
})
// expect 0
```

### 4.3 Sample property checks (API)

Use a **client JWT** for a tenant that owned migrated rows. Base path for client API: **`/api/client`** (see `routes/client.py`).

| Check | Method | Endpoint | What to verify |
|-------|--------|----------|----------------|
| Property list / detail | GET | `/api/client/properties` | For a former **Scotland-bucket** row: `jurisdiction` is **`Scotland`** (canonical string). |
| Property detail | GET | `/api/client/properties` (single property in list) or property-scoped routes you use | For a former **ENGLAND_WALES-bucket** row: `jurisdiction` is **absent/null** unless the user or account default filled it later; `scoring_jurisdiction_bucket` may be **`ENGLAND_WALES`**. |
| Portfolio compliance | GET | `/api/client/compliance-score` | `jurisdictions` (if present) should list **portfolio labels** (e.g. England, Wales, Scotland), not `ENGLAND_WALES`. |
| Per-property breakdown | GET | `/api/client/compliance-score` | In `score_breakdown_by_property[]`: `jurisdiction` = portfolio label; `scoring_jurisdiction_bucket` = `SCOTLAND` or `ENGLAND_WALES` as applicable. |
| Explainability | GET | `/api/client/properties/{property_id}/compliance-score/explanation` | `effective_jurisdiction_label` reflects resolution (property → account default → system); `scoring_jurisdiction_bucket` / legacy `jurisdiction` field on this payload = **bucket** (see code comments). |

### 4.4 Sample property checks (UI)

Sign in as a user for the same `client_id` as in the dry-run samples.

| Screen | Path (app routes) | What to verify |
|--------|-------------------|----------------|
| Property detail — jurisdiction | `/properties/{propertyId}` | **Portfolio jurisdiction** card shows England / Wales / Scotland / Northern Ireland (or account default messaging), not `ENGLAND_WALES` / `SCOTLAND` bucket strings in the saved property field. |
| Compliance explainability (same page) | Same page | **Portfolio jurisdiction** vs **Scoring rules** show label vs bucket separately. |
| Compliance score | `/compliance-score` | Jurisdiction copy per property aligns with cleaned data; no bucket strings in place of country names where the UI is label-oriented. |
| Client dashboard | `/dashboard` | Property snippets using jurisdiction / effective label look correct for sampled `property_id`s. |
| Reports | `/reports` | Rows that show jurisdiction / source match expectations for migrated clients. |
| Jurisdiction settings | `/settings/jurisdiction` | After EW-legacy cleanup, properties with unset `jurisdiction` may appear in “missing jurisdiction” flows; confirm bulk “apply default” behaviour if you use it. |

### 4.5 Functional smoke (recommended)

- Trigger or wait for a normal **compliance recalc** on one migrated property; confirm `properties.jurisdiction` is **not** overwritten with `ENGLAND_WALES` / `SCOTLAND` (only `scoring_jurisdiction_bucket` should carry the bucket).

---

## Rollback and recovery

### Scotland-bucket rows (`scotland` → `Scotland`)

- **Low risk:** 1:1 mapping.
- **Rollback:** If you must revert a specific property: set `jurisdiction` back to the previous raw string only if you captured it from backup; otherwise leave `Scotland` — it matches intended semantics.

### ENGLAND_WALES-bucket rows (unset `jurisdiction`, set `scoring_jurisdiction_bucket`)

- **By design** the true portfolio label was **ambiguous**; the migration **does not** guess England vs Wales vs NI.
- **Rollback:** Restore from **pre-migration backup** only if you must undo in bulk. There is no safe automatic inverse mapping from `ENGLAND_WALES` alone to a single portfolio label.
- **Operational follow-up:** For affected properties, use **Settings → Jurisdiction** (account default) or **per-property jurisdiction** on `/properties/{id}` so `jurisdiction` is set explicitly.

### Unexpected dry-run patterns

| Observation | Suggested action |
|-------------|------------------|
| Rows with **missing `property_id`** | Script skips them; fix data or handle with a one-off query keyed by `_id`. |
| **`jurisdiction` values that are not** simple bucket tokens but **look like free text** | Do **not** run `--apply` blindly; extend filters or handle those IDs manually after product/legal review. |
| **Very large `M`** for ENGLAND_WALES | Plan comms: after apply, more properties may show “missing jurisdiction” until defaults are applied. |
| **Counts increase between count and apply** | Investigate whether something is still writing bucket strings into `jurisdiction`; fix that deployment before migrating. |

---

## Quick reference — commands

```bash
cd <path-to>/Pleerity-enterprise/backend

python -m scripts.migrate_property_jurisdiction_legacy_buckets --count
python -m scripts.migrate_property_jurisdiction_legacy_buckets --count --json
python -m scripts.migrate_property_jurisdiction_legacy_buckets --dry-run
python -m scripts.migrate_property_jurisdiction_legacy_buckets --apply
python -m scripts.migrate_property_jurisdiction_legacy_buckets --count   # post-apply: expect 0 / 0
```
