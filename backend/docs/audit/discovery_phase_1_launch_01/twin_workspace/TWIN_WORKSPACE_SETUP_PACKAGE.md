# Twin Workspace Setup Package

**Authority:** `TWIN-PROVIDER-AGENT-SPECIFICATION-01`  
**Agent:** Pleerity Discovery Agent  
**Provider:** `twin` (Discovery Foundation)  
**Scope:** Prospect discovery only — no outreach, CRM, import, or nurture  
**Branch:** `develop` / staging only until Stage X GREEN with real export

---

## Package contents

| # | Deliverable | File |
|---|-------------|------|
| 1 | Twin workspace configuration | `twin_workspace_manifest.json` |
| 2 | Twin agent system prompt | `twin_agent_system_prompt.md` |
| 3 | Twin task instructions | §3 below + system prompt §Tasks |
| 4 | Search strategy | §4 below |
| 5 | Source rules | §5 below |
| 6 | Qualification rules | §6 below |
| 7 | Output schema | `twin_export_schema.json` |
| 8 | Export format | §8 below |
| 9 | Twin → Discovery field mapping | `twin_discovery_field_mapping.json` |
| 10 | Stage X rerun checklist | `STAGE_X_RERUN_CHECKLIST.md` |

Copy-paste assets for Twin.so workspace configuration are in this directory.

---

## 1. Twin workspace configuration

Use `twin_workspace_manifest.json` as the configuration record. Configure the Twin workspace with these settings:

### Workspace identity

| Setting | Value |
|---------|-------|
| Workspace name | `Pleerity Discovery — Compliance Vault Pro` |
| Environment | Staging / validation only |
| Region focus | United Kingdom (`GB`) |
| Primary platform | Compliance Vault Pro (CVP) |

### Agent binding

| Setting | Value |
|---------|-------|
| Agent name | **Pleerity Discovery Agent** |
| Agent role | Prospect Discovery Agent |
| Provider ID | `twin` |
| Adapter version | `1.0.0` (Stage W) |
| Workflow ID | `wf-cvp-prospect-discovery-v1` |
| Output destination | JSON export file → Discovery `TwinProvider.ingest_async()` |
| Enrichment | Allowed (stored in raw payload only) |
| Async ingest | Supported |

### Enabled capabilities

| Capability | Enabled |
|------------|---------|
| Public web search | Yes |
| Company website reading | Yes |
| Public directory lookup | Yes |
| LinkedIn company page reading (public) | Yes |
| Prospect record generation | Yes |
| JSON batch export | Yes |

### Disabled capabilities (hard prohibitions)

| Capability | Enabled |
|------------|---------|
| Email sending | **No** |
| LinkedIn messaging | **No** |
| SMS / WhatsApp | **No** |
| CRM integration | **No** |
| Lead creation | **No** |
| Auto-import to Discovery | **No** |
| Nurture sequences | **No** |
| Approval / rejection actions | **No** |
| Consent generation or inference | **No** |
| Suppression / legal-hold override | **No** |

### Discovery integration (staging)

| Setting | Value |
|---------|-------|
| `DISCOVERY_PROVIDER_TWIN_ENABLED` | `false` (enable only for validation runs) |
| Ingest path | `TwinProvider.ingest_async()` → `discovery_prospects` |
| Campaign lawful basis | Set on Discovery campaign — agent does **not** override |
| Review queue | Automatic (`needs_review`) |
| Import | Manual via `DiscoveryImportService` after human approval |

### Export targets

| Target | Path (repo) |
|--------|-------------|
| Staging export | `backend/docs/audit/discovery_phase_1_launch_01/twin_exports/twin_staging_export.json` |
| Workspace manifest snapshot | `backend/docs/audit/discovery_phase_1_launch_01/twin_exports/twin_workspace_manifest.json` |

---

## 2. Twin agent system prompt

Full copy-paste prompt: **`twin_agent_system_prompt.md`**

---

## 3. Twin task instructions

### Primary task

Discover UK-based landlords and property-related businesses that are likely to benefit from Compliance Vault Pro. For each qualified prospect, produce one Discovery Prospect record in the approved Twin export format.

### Per-run workflow

1. **Plan** — Select search queries from the approved search strategy (§4) for the target segment (e.g. HMO operators in Scotland).
2. **Discover** — Find businesses using only allowed public sources (§5).
3. **Verify** — Confirm UK geography and property-management relevance from public evidence.
4. **Qualify** — Score using qualification rules (§6). Discard below 50.
5. **Collect** — Gather canonical fields only (§9). Put everything else in enrichment/raw payload.
6. **Reference** — Assign a unique `twin_id` and `source_url` for every prospect.
7. **Export** — Append to batch JSON export. Do not send to CRM or email tools.
8. **Hand off** — Export file is ingested by Discovery staging validation or operations.

### Batch targets

| Metric | Minimum | Target |
|--------|---------|--------|
| Prospects per export | 50 | 100 |
| `provider_confidence` ≥ 50 | 100% of exported | — |
| `provider_confidence` ≥ 70 | — | ≥ 70% of exported |
| Duplicate rate (post-ingest) | — | < 5% |

### Agent responsibilities

- Prospect discovery
- Public data collection
- Enrichment (raw payload only)
- Canonical field mapping
- Confidence scoring
- Export payload generation

### Explicitly out of scope

- Lead creation, CRM updates, import, approval, rejection
- Email, LinkedIn messages, SMS, WhatsApp
- Nurture, follow-up, task creation
- Consent generation, lawful-basis override, suppression override

---

## 4. Search strategy

### Priority geography

1. Scotland  
2. England  
3. Wales  
4. Northern Ireland  

### Segment search matrix

| Segment | Example queries | `business_type` |
|---------|-----------------|-----------------|
| Independent landlords | `"landlord" "rental properties" site:.co.uk` | `landlord` |
| HMO operators | `"HMO" "houses in multiple occupation" UK` | `hmo_operator` |
| Letting agencies | `"letting agency" [city] UK` | `letting_agency` |
| Property managers | `"property management" company UK` | `property_manager` |
| Serviced accommodation | `"serviced accommodation" operator UK` | `property_manager` |
| Portfolio landlords | `"property portfolio" landlord UK` | `landlord` |
| Compliance-aware landlords | `"landlord compliance" OR "gas safety certificate" landlord UK` | `landlord` |

Replace `[city]` with: Edinburgh, Glasgow, Manchester, Birmingham, Leeds, Bristol, Cardiff, Belfast, London (outer boroughs preferred over central corporate).

### Search execution rules

- Run **breadth-first** across segments before deep-diving one segment.
- Prefer **company-level** results over individual social profiles.
- Require at least **one property-management signal** (§6) per prospect.
- De-duplicate within batch by `company_name` + `website` before export.
- Stop searching a source after 3 consecutive low-confidence (< 50) results.

### Ideal prospect signals (search for evidence of)

- Manages rental properties or HMOs
- Provides letting or property management services
- Advertises rental listings or landlord services
- Discusses landlord compliance, gas safety, EPC, licensing
- Employs property managers or letting agents
- Operates serviced accommodation at scale

---

## 5. Source rules

### Allowed (public only)

| Source type | Use for | `source_url` priority |
|-------------|---------|----------------------|
| Company website | Identity, services, contact | 1 (preferred) |
| Google Business / public directory | Location, phone, website | 2 |
| LinkedIn company page (public) | Company name, size signals | 3 |
| Property association / directory listings | Sector validation | 2 |
| Open web search snippets | Initial discovery only | 4 |
| Public property forums / communities | Qualification signals only | 5 — never as sole source |

### Prohibited

- Private or password-protected systems
- Purchased contact databases
- Scraped personal LinkedIn profiles (company pages only)
- Restricted or paywalled data without licence
- Any source requiring impersonation or ToS violation

### Source URL rule

Every prospect **must** have `source_url` — the single best public page proving the business exists and matches the qualification. Must be `http://` or `https://`.

### Data minimisation

Collect only what is needed for Discovery canonical fields plus optional enrichment in raw payload. Do not collect personal data beyond publicly listed business contact details.

---

## 6. Qualification rules

### Must have (else discard)

| Rule | Requirement |
|------|-------------|
| UK presence | `country` = `GB` OR city/region in UK |
| Identity | At least one of: `company_name`, `website`, `email`, `phone` |
| Property relevance | ≥ 1 ideal prospect signal (§4) |
| Public evidence | Valid `source_url` |
| Confidence | `provider_confidence` ≥ 50 |
| Unique reference | Unique `twin_id` per prospect |

### Must not

| Rule | Action |
|------|--------|
| Confidence < 50 | Discard — do not export |
| Non-UK primary market | Discard |
| Residential individual (not a business) | Discard |
| Duplicate in current batch | Merge or skip |
| No property-management signal | Discard |
| Fabricated email or phone | Discard — public data only |

### Confidence scoring

| Score | Label | Criteria |
|-------|-------|----------|
| 90–100 | Strong match | Clear UK property business; explicit landlord/HMO/letting/management services; website + contact; compliance language optional bonus |
| 70–89 | Likely match | UK property business; services evident; good public evidence; minor gaps (e.g. no phone) |
| 50–69 | Possible match | UK business with property signals but limited detail — export only if segment under-represented |
| < 50 | Discard | Weak or ambiguous fit |

**Confidence factors (weight in order):**

1. Relevant `business_type` category confirmed  
2. UK location confirmed  
3. Property-related services evidenced  
4. Compliance-related language on public pages (+5 to +10)  
5. Evidence quality (primary website > directory > search snippet)

### `business_type` assignment

| Evidence | Value |
|----------|-------|
| Letting agency branding | `letting_agency` |
| Property management services | `property_manager` |
| HMO licensing / multi-let focus | `hmo_operator` |
| Individual / portfolio landlord | `landlord` |
| Compliance-only vendor (not landlord) | `compliance_provider` |
| Unclear | `unknown` |

### `landlord_type` assignment

| Evidence | Value |
|----------|-------|
| Single-property signals | `single_property` |
| Portfolio / multiple properties | `portfolio` |
| HMO operator | `hmo` |
| Unclear | `unknown` |

---

## 7. Output schema

Machine-readable schema: **`twin_export_schema.json`**

---

## 8. Export format

### Batch envelope

```json
{
  "export_id": "exp-cvp-staging-YYYYMMDD-HHMMSS",
  "workspace_id": "<twin-workspace-id>",
  "agent_id": "<twin-agent-id>",
  "workflow_id": "wf-cvp-prospect-discovery-v1",
  "exported_at": "2026-06-19T12:00:00Z",
  "provenance": "real_workspace",
  "records": []
}
```

### Per-record shape (Twin export → adapter)

```json
{
  "twin_id": "twin-cvp-20260619-0001",
  "company_name": "Example Lettings Ltd",
  "website": "https://www.examplelettings.co.uk",
  "email": "info@examplelettings.co.uk",
  "phone": "+441234567890",
  "contact_name": "Office",
  "city": "Edinburgh",
  "region": "Scotland",
  "postcode": "EH1 1AA",
  "country": "GB",
  "business_type": "letting_agency",
  "landlord_type": "portfolio",
  "confidence_score": 82,
  "linkedin_url": "https://www.linkedin.com/company/example-lettings",
  "enrichment_data": {
    "company_description": "Independent letting agency managing 40+ properties across Edinburgh.",
    "property_count_estimate": 40,
    "qualification_signals": ["letting services", "property management", "landlord compliance page"],
    "discovered_at": "2026-06-19T12:00:00Z",
    "origin_lineage": "google_search → company_website → linkedin_company"
  }
}
```

### Fields the agent must NOT set

| Field | Reason |
|-------|--------|
| `lawful_basis` | Discovery campaign governs — agent must not infer |
| `marketing_consent` | Agent must not generate consent |
| `prospect_id` | Assigned by Discovery |
| `imported_lead_id` | Assigned after approved import |
| Any CRM ID | CRM boundary |

### Ingest command (staging)

```bash
cd backend
python scripts/discovery_phase_1_twin_staging_validate.py \
  --twin-export docs/audit/discovery_phase_1_launch_01/twin_exports/twin_staging_export.json \
  --workspace-manifest docs/audit/discovery_phase_1_launch_01/twin_exports/twin_workspace_manifest.json
```

---

## 9. Twin → Discovery field mapping

Full mapping table: **`twin_discovery_field_mapping.json`**

Summary:

| Twin export field | Discovery canonical | Notes |
|-------------------|---------------------|-------|
| `twin_id` | `provider_reference` | Prefixed `twin:` by adapter if missing |
| `external_id` | `provider_reference` | Alias |
| `company` / `organisation` | `company_name` | Aliases |
| `website` / `url` | `website` | |
| `linkedin_url` / `profile_url` | `source_url` | Primary evidence URL |
| `email` | `email` | Public business email only |
| `phone` | `phone` | |
| `contact` / `name` | `contact_name` | Optional |
| `confidence_score` | `provider_confidence` | Integer 0–100 |
| `business_type` | `business_type` | Enum — see §6 |
| `landlord_type` | `landlord_type` | Enum — see §6 |
| `city`, `region`, `postcode`, `country` | `provider_extensions.location` | Structured location |
| `workflow_id`, `twin_campaign_id`, `enrichment_*` | Raw payload only | Never on prospect document |

---

## 10. Stage X rerun checklist

See **`STAGE_X_RERUN_CHECKLIST.md`**.

---

## Architectural compliance statement

This package conforms to:

- Discovery Provider Protocol (`TwinProvider`, adapter `1.0.0`)
- Provider-neutral metrics, compliance, lifecycle, audit
- CRM boundary — no `LeadService` or CRM writes from Twin
- Stage W adapter validation + Stage X operational validation path

**No architectural exceptions required.** Twin conforms to Discovery; Discovery does not conform to Twin.

---

## Workflow (reference)

```
Twin Discovery Agent
        ↓
Discovery Prospect (via TwinProvider.ingest_async)
        ↓
Review Queue
        ↓
Compliance Validation
        ↓
Human Approval
        ↓
DiscoveryImportService
        ↓
LeadService
        ↓
CRM
```

Twin stops at export. Everything after ingest is Discovery Foundation governance.
