# Discovery Hash and Idempotency Governance Review

```yaml
---
Status: ACCEPTED
Authority Level: TIER_1
Review ID: DISCOVERY-HASH-AND-IDEMPOTENCY-GOVERNANCE-REVIEW-01
Alignment Update: DISCOVERY-HASH-GOVERNANCE-ALIGNMENT-UPDATE-01
Date: 2026-06-18
Related:
  - docs/DISCOVERY_FOUNDATION_ARCHITECTURE.md
  - docs/contracts/DISCOVERY_PROVIDER_PROTOCOL.md
  - docs/contracts/DISCOVERY_SOURCE_METADATA_V1.json
  - docs/adr/ADR_DISCOVERY_RETENTION_AND_ERASURE.md
  - docs/governance/DISCOVERY_COMPLIANCE_AND_CONSENT.md
  - docs/trackers/DISCOVERY_PHASE_1_IMPLEMENTATION_TRACKER.md
  - docs/launch/DISCOVERY_PHASE_1_LAUNCH_GATE.md
Scope: Pre-Stage J/K governance review — audit and recommendations only
Alignment Status: COMPLETE (2026-06-18)
---
```

## 1. Purpose

Focused governance review of Discovery Foundation hashing, idempotency, provenance, and deduplication strategy before Stage J/K implementation.

**Review type:** Audit and recommendation.  
**Alignment update:** Documentation and contract alignment only — no algorithm, schema, or code changes.

---

## 2. Review conclusions (summary)

| Area | Pre-review | Post-alignment |
|------|------------|----------------|
| Architecture | Sound | **GREEN** — §12–§14 added |
| Hashing implementation | Acceptable | **GREEN** — semantics frozen as V1 ingest fingerprint |
| Idempotency implementation | Acceptable | **GREEN** — protocol aligned |
| Provenance model | Acceptable | **GREEN** — metadata contract aligned |
| Dedupe architecture | Acceptable | **GREEN** — hierarchy documented §13 |

**Recommendation:** Proceed to Stage J and Stage K implementation.

---

## 3. Hash stability assessment

`content_hash` is a **Canonical Ingest Fingerprint** — not a global person identity key.

**Frozen as V1** with documented field order, separator (`\x1f`), SHA-256, and normalisation rules. See Architecture §12.

**Invalidates hashes:** field order change, algorithm change, normalisation rule change, adding/removing canonical fields.

**Safe changes:** new volatile fields, new non-canonical prospect fields, quality/review fields.

---

## 4. Versioning recommendation

**Option C adopted (governance only):**

| Field | V1 value |
|-------|----------|
| `content_hash_version` | `"1"` |
| `hash_algorithm` | `"sha256"` |

Documented in Architecture §12.3. Persistence deferred to Stage K/P — no database migration in alignment update.

---

## 5. Dedupe compatibility assessment

Cross-run dedupe must **not** depend on `content_hash` as primary signal.

**Authoritative hierarchy:** Architecture §13 — `email_hash` → `phone_hash` → CRM → `content_hash`+run → provider_reference → merge chain.

---

## 6. Idempotency assessment

Format: `{provider}:{provider_reference_segment}:{content_hash}` via `build_discovery_idempotency_key()`.

Ingest-scoped; stable on retry; new key on new run/provider. Provider Protocol §4.4 aligned.

---

## 7. Canonical identity snapshot recommendation

**Reserved** — not implemented Phase 1. Governance in Architecture §14 and metadata contract `$defs/canonical_identity_snapshot`.

---

## 8. Provenance assessment

`OriginLineageEntry` append-only model sufficient for Phase 1 multi-provider workflows. Metadata contract aligned with code fields.

---

## 9. Drift items resolved (alignment update)

| Drift | Resolution |
|-------|------------|
| Protocol idempotency used `discovery_run_id` | Updated to `provider_reference` + `content_hash` |
| `CONTENT_HASH_FIELDS` vs `CANONICAL_HASH_FIELD_ORDER` | Architecture §12 is authoritative |
| Metadata lineage missing `content_hash`, `discovered_at`, `campaign_id` | Contract updated |
| Dedupe role of `content_hash` ambiguous | Architecture §13 hierarchy |
| Hash retention after erasure unclear | Compliance §12; ADR erasure section |
| No hash version governance | Architecture §12.3 |
| Launch gate missing governance NO-GO | NG-019–NG-024 added |

---

## 10. Remaining recommended items (deferred implementation)

| Item | Stage |
|------|-------|
| Persist `content_hash_version` / `hash_algorithm` on prospect + metadata | K / P |
| Implement `canonical_identity_snapshot` | P or Phase 2 |
| Phone E.164 / URL normalisation (V2 hash) | Phase 2 ADR |
| `lineage_event_type` on lineage entries | Phase 2 providers |
| Background rehash audit job | Phase 2 |

---

## 11. Governance status (final)

| Status | Rating |
|--------|--------|
| Hash Governance | **GREEN** |
| Idempotency Governance | **GREEN** |
| Provenance Governance | **GREEN** |
| Dedupe Readiness | **GREEN** |

**Next action:** Proceed to Stage J and Stage K per tracker.
