# Discovery Provider Capability Matrix

```yaml
---
Status: ACTIVE
Authority Level: TIER_1
Related:
  - docs/contracts/DISCOVERY_PROVIDER_PROTOCOL.md
  - backend/services/discovery/discovery_provider_registry.py
Last Review: 2026-06-02
Phase 1 Active Providers: csv, manual
---

```

## 1. Purpose

Defines **allowed** and **prohibited** capabilities per discovery provider. Enforced by `DiscoveryProviderRegistry` and `validate_provider_capabilities()`.

**Universal rule:** Providers may discover or suggest prospects. They may never write CRM, send outreach, trigger nurture, access compliance/evidence, touch billing, or create customers.

---

## 2. Prohibited capabilities (all providers, all phases)

| Capability | Meaning |
|------------|---------|
| `OUTREACH` | Email, SMS, voice, social direct messages |
| `CRM_WRITE` | Direct writes to `leads`, `clients`, or CRM collections |
| `NURTURE_TRIGGER` | Start or modify nurture / follow-up sequences |
| `COMPLIANCE_ACCESS` | Read/write evidence, documents, requirements |
| `NOTIFICATION_SEND` | Call `notification_orchestrator` or equivalent |
| `BILLING_WRITE` | Stripe, invoices, entitlements, commercial governance |

---

## 3. Provider capability matrix

| Capability | CSV | Manual | Apollo | Clay | Twin | Internal crawler |
|------------|:---:|:------:|:------:|:----:|:----:|:----------------:|
| **Phase** | 1 | 1 | 2 | 2 | 2 | 2 |
| **Phase 1 active** | ✅ metadata | ✅ metadata | ❌ | ❌ | ❌ | ❌ |
| **Ingest implemented (Stage C)** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Discover / suggest prospects | ✅ | ✅ | ✅ | ✅ | ✅ (via export) | ✅ |
| Sync ingest | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Async ingest | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Enrichment | ❌ | ❌ | ✅ | ✅ | via chain | ❌ |
| Cost tracking | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| Webhook | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| Max batch (design) | 2,000 | 100 | 50,000 | 50,000 | 50,000 | 10,000 |
| **OUTREACH** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **CRM_WRITE** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **NURTURE_TRIGGER** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **COMPLIANCE_ACCESS** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **NOTIFICATION_SEND** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| **BILLING_WRITE** | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |
| Create customers | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 | 🚫 |

Legend: ✅ allowed (when enabled) | ❌ not in phase / not supported | 🚫 **prohibited always**

---

## 4. Feature flag enablement

| Provider | Flag(s) required | Default |
|----------|------------------|---------|
| CSV | `DISCOVERY_MODULE_ENABLED` + `DISCOVERY_PROVIDER_LAYER_ENABLED` + `DISCOVERY_PROVIDER_CSV_ENABLED` | all `false` |
| Manual | `DISCOVERY_MODULE_ENABLED` + `DISCOVERY_PROVIDER_LAYER_ENABLED` | all `false` |
| Apollo | above + `DISCOVERY_PROVIDER_APOLLO_ENABLED` | `false` |
| Clay | above + `DISCOVERY_PROVIDER_CLAY_ENABLED` | `false` |
| Twin | above + `DISCOVERY_PROVIDER_TWIN_ENABLED` | `false` |
| Internal crawler | above + `DISCOVERY_PROVIDER_INTERNAL_CRAWLER_ENABLED` | `false` |

`ingest_available` in registry = `enabled` AND `ingest_implemented`. Stage C: **all `ingest_available` are false**.

---

## 5. Twin note

Twin is **orchestration**, not CRM authority. Allowed pattern: external workflow → export webhook → platform ingest endpoint. Twin adapter must not execute prohibited capabilities inside platform boundary.

---

## 6. Enforcement code

- Registry: `backend/services/discovery/discovery_provider_registry.py`
- Protocol: `backend/services/discovery/providers/discovery_provider_protocol.py`
- Flags: `backend/services/discovery/discovery_config.py`

---

## 7. Change control

Adding a provider requires: registry entry, capability row in this matrix, feature flag in `DISCOVERY_FEATURE_FLAGS.md`, ADR amendment for Phase 2 providers.
