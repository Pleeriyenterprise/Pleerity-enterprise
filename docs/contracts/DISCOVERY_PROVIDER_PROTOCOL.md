# Discovery Provider Protocol Contract

```yaml
---
Status: ACTIVE
Authority Level: TIER_1
Version: 1.0.0
Related:
  - docs/DISCOVERY_FOUNDATION_ARCHITECTURE.md
  - docs/contracts/DISCOVERY_SOURCE_METADATA_V1.json
Phase 1 Active Providers: csv, manual
---

```

## 1. Overview

All discovery data sources implement the `DiscoveryProvider` protocol. Providers map external data to the **canonical prospect schema** and return an **idempotency key**. Providers never write to CRM, send outreach, or access compliance/evidence systems.

**Implementation:** `backend/services/discovery/providers/discovery_provider_protocol.py` (Python `Protocol` or ABC)

---

## 2. Provider identity

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | string | Stable id: `csv`, `manual`, `apollo`, `clay`, `twin`, `internal_crawler` |
| `adapter_version` | string | Semver e.g. `1.0.0` — bump on breaking mapping changes |

---

## 3. Capabilities object

```python
@dataclass
class ProviderCapabilities:
    supports_async: bool
    supports_enrichment: bool
    supports_cost_tracking: bool
    supports_webhook: bool
    max_batch_size: int
    prohibited_capabilities: frozenset[str]  # always includes OUTREACH, CRM_WRITE, COMPLIANCE_ACCESS
```

**Prohibited capabilities (all providers, all phases):**

| Capability | Description |
|------------|-------------|
| `OUTREACH` | Email, SMS, voice, social DM |
| `CRM_WRITE` | Direct writes to `leads`, `clients` |
| `NURTURE_TRIGGER` | Direct follow-up sequence start |
| `COMPLIANCE_ACCESS` | Read/write evidence, documents, requirements |
| `NOTIFICATION_SEND` | `notification_orchestrator` or equivalent |
| `BILLING_WRITE` | Stripe, invoices, entitlements |

---

## 4. Protocol methods

### 4.1 `capabilities() -> ProviderCapabilities`

Returns static capability declaration for registry and UI.

### 4.2 `validate(raw_row: dict, context: IngestContext) -> ValidationResult`

- Schema validation
- Required field checks (at least one of email, phone, company_name)
- Lawful basis / consent column rules
- Returns `{ valid: bool, errors: [], warnings: [], risk_flags: [] }`

### 4.3 `map_to_canonical(raw_row: dict, context: IngestContext) -> CanonicalProspect`

Maps provider row to platform canonical fields:

```python
CanonicalProspect:
  company_name, contact_name, email, phone, website, location,
  business_type, landlord_type, source_url, source_type,
  provider_confidence, marketing_consent, lawful_basis,
  provider_extensions: dict  # provider-specific, not on lead
```

### 4.4 `idempotency_key(canonical: CanonicalProspect, context: IngestContext) -> str`

**Implementation authority:** `build_discovery_idempotency_key(provider, provider_reference, content_hash)` in `backend/services/discovery/discovery_hashing.py`

**Format:** `{provider_id}:{provider_reference_segment}:{content_hash}`

Where:

- `provider_id` = normalised provider identifier (e.g. `csv`, `manual`)
- `provider_reference_segment` = normalised, namespaced provider reference (PII-safe; email in reference is hashed to short hex segment)
- `content_hash` = SHA-256 Canonical Ingest Fingerprint per `DISCOVERY_FOUNDATION_ARCHITECTURE.md` §12

**`content_hash` computation:** `compute_canonical_content_hash()` over `CANONICAL_HASH_FIELD_ORDER` (13 fields including ingest context). See Architecture §12 — **not** the legacy `CONTENT_HASH_FIELDS` identity subset alone.

#### Idempotency semantics

| Scenario | Behaviour |
|----------|-----------|
| **Retry** (same row, same run) | Stable — same `provider_reference` + same canonical content → same key |
| **Re-ingest** (new run) | New key — `discovery_run_id` in `content_hash` changes digest |
| **Provider replacement** | New key — `provider` segment changes |
| **Schema / hash version bump** | New key — `content_hash` changes per version rules |

#### Non-goals

- Idempotency is **ingest-scoped** — it prevents duplicate rows within the same ingest context on retry
- Idempotency is **not** a cross-provider identity mechanism
- Idempotency is **not** a substitute for cross-run dedupe (`email_hash`, `phone_hash` — Architecture §13)

Ensures re-upload and retry do not create duplicate prospects **within the same discovery run** when combined with dedupe engine.

### 4.5 `ingest(source: IngestSource, context: IngestContext) -> IngestResult`

**Sync providers (csv, manual):** parse all rows, return prospect creates.

**Async providers (Phase 2):** create `discovery_job`, return job_id; worker calls validate/map per row.

```python
IngestResult:
  discovery_run_id: str
  discovery_job_id: str | None
  accepted_count: int
  rejected_count: int
  errors: list[RowError]
```

---

## 5. IngestContext

```python
IngestContext:
  discovery_run_id: str
  discovery_campaign_id: str | None
  discovery_job_id: str | None
  tenant_id: str  # default "pleerity"
  actor_id: str
  actor_email: str
  lawful_basis: str
  attestation: AttestationRecord
  provider_mapping_profile_id: str | None  # reserved Phase 2
```

---

## 6. Provider adapter registry

```python
PROVIDER_REGISTRY: dict[str, DiscoveryProvider] = {
  "csv": CsvImportProvider(),
  "manual": ManualImportProvider(),
  # Phase 2 — register only when flag enabled:
  # "apollo": ApolloImportProvider(),
}
```

Flags gate registration at startup — unregistered provider_id returns 404.

---

## 7. Provider Capability Matrix

| Capability | CSV | Manual | Apollo | Clay | Twin | Internal crawler |
|------------|:---:|:------:|:------:|:----:|:----:|:----------------:|
| **Phase 1 active** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Sync ingest | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Async ingest | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Enrichment | ❌ | ❌ | ✅ | ✅ | via chain | ❌ |
| Cost tracking | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| Webhook | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| **OUTREACH** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **CRM_WRITE** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **COMPLIANCE_ACCESS** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |

Legend: ✅ supported | ❌ not in phase | 🚫 **prohibited always**

### Twin note

Twin is **orchestration**, not a canonical data authority. Twin adapter receives export webhooks and calls `validate` / `map_to_canonical` — same as CSV rows. Twin must not execute outreach steps inside platform boundary.

### Internal crawler note (Phase 2+)

Requires additional crawl session fields in `provider_extensions` and audit events `CRAWL_SESSION_*`. Not Phase 1.

---

## 8. Canonical CSV schema (Phase 1)

**Required (at least one per row):** `email` | `phone` | `company_name`

**Optional columns:**

```text
contact_name, website, city, region, postcode, country,
business_type, landlord_type, source_url, tags, notes,
marketing_consent, lawful_basis, consent_evidence, provider_reference
```

**Mapping profiles (reserved):** `provider_mapping_profiles` collection for custom column maps — Phase 1 uses fixed canonical map.

---

## 9. Versioning

- `adapter_version` bump: breaking change to `map_to_canonical` output
- `DISCOVERY_SOURCE_METADATA_V1.schema_version` bump: breaking change to lead metadata
- `content_hash_version` bump: breaking change to canonical hash field set or normalisation (Architecture §12.3)
- Both must be updated in lockstep when import mapping changes

---

## 10. Idempotency and hash cross-reference

| Concern | Authority |
|---------|-----------|
| `content_hash` definition | `DISCOVERY_FOUNDATION_ARCHITECTURE.md` §12 |
| Dedupe hierarchy | `DISCOVERY_FOUNDATION_ARCHITECTURE.md` §13 |
| Idempotency key format | This doc §4.4; `discovery_hashing.build_discovery_idempotency_key` |
| Governance review | `docs/governance/DISCOVERY_HASH_AND_IDEMPOTENCY_GOVERNANCE_REVIEW_01.md` |

---

## 11. Compliance hooks (all providers)

Every `ingest()` must:

1. Respect `marketing_consent` default false
2. Attach run attestation to context
3. Write `discovery_audit_logs` via audit service (not direct collection access)
4. Store raw row in `RawPayloadStore` — not inline on prospect doc

**Import and approval audit events** (frozen — see `DISCOVERY_APPROVAL_IMPORT_GOVERNANCE_FREEZE_01.md` §2): `PROSPECT_REVIEWED`, `IMPORT_REQUESTED`, `IMPORT_VALIDATED`, `IMPORT_BLOCKED`. Providers must not emit import events — only `DiscoveryImportService` may emit the import sub-workflow chain.
