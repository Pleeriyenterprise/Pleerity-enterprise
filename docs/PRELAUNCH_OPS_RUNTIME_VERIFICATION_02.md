# PRELAUNCH-OPS-RUNTIME-VERIFY-02 — Client Operational-Control Surface Verification Charter

**Programme ID:** `PRELAUNCH-OPS-RUNTIME-VERIFY-02`  
**Programme type:** **OPERATIONAL_CONTROL_PLANE_VERIFICATION** (not generic surface QA)  
**Status:** G0 **`VERIFIED_OPERATIONALLY`**; G1 **`VERIFIED_OPERATIONALLY`** (run `20260524T162503Z`); G2 **`VERIFIED_OPERATIONALLY`** (run `20260524T170848Z`); G3 **`VERIFIED_OPERATIONALLY`** (run `20260524T175910Z`); G4 **`VERIFIED_OPERATIONALLY`** (run `20260524T182816Z`); G5–G7 **NOT_EXECUTED** (G5 unblocked)  
**Authority:** Governed operational-control-plane verification only — **not** launch authorization, UK rollout approval, architecture redesign, projection redesign, lifecycle redesign, reporting-engine certification, or calendar/scheduler certification.

**Prerequisite:** `PRELAUNCH-OPS-RUNTIME-VERIFY-01` **COMPLETE** (F1–F8 `VERIFIED_OPERATIONALLY`) is a **lineage dependency only**. It does **not** confer surface coherence, CTA truth, or operator-trust guarantees.

**Charter (prior programme):** [`docs/PRELAUNCH_OPS_RUNTIME_VERIFICATION.md`](PRELAUNCH_OPS_RUNTIME_VERIFICATION.md)

---

## 0. Operational control-plane doctrine (foundational)

### 0.1 Programme identity

VERIFY-02 is **OPERATIONAL_CONTROL_PLANE_VERIFICATION** — not merely per-page surface checks.

It verifies whether, under real runtime conditions, these remain **coherent together**:

| Control-plane layer | Verification intent |
|---------------------|---------------------|
| **Operators** | Can act with justified confidence |
| **Projections** | Live and derived truths are authoritative in the right place |
| **CTAs** | Route, mutate, and confirm truthfully |
| **Lifecycle truth** | Displayed state matches persisted operational state |
| **Navigation** | Every surfaced debt has a truthful path to **resolution** (not a loop) |
| **Resolution authority** | Operators know which surface owns the next truthful action |
| **Operational cognition** | Priority and urgency are comprehensible |
| **Cross-surface understanding** | No island, orphan, circular routing, or projection ambiguity |

| Programme | Proves |
|-----------|--------|
| **VERIFY-01** | The **machinery works** — domain lifecycles, cross-role sync, async convergence, authority boundaries on mutations |
| **VERIFY-02** | The **control plane remains cognitively truthful, navigable, and trustworthy** — operators can understand and act on operational truth across surfaces |

### 0.2 Failure classes the control plane must detect

| Failure class | Model section | Primary families |
|---------------|---------------|------------------|
| Operational cognition failure | §0.1 | All |
| Attention arbitration failure | §3.1 `ATTENTION_AUTHORITY_RULES` | **G1** |
| Widget-island contradiction | §3.2 `WIDGET_ISLAND_FAILURE` | **G2** |
| Stale operational authority | §2.3 projection authority | **G2**, **G7** |
| Operational orphan state | §3.4 `OPERATIONAL_ORPHAN_STATE` | G1–G7 (audit per family) |
| Reporting freshness deception | §3.3 `REPORT_FRESHNESS_AUTHORITY` | **G7** |

### 0.3 Operational cognition dimensions

| Dimension | Verification intent |
|-----------|----------------------|
| **Operational cognition** | Operator can infer correct next action from visible state |
| **Attention arbitration** | Today/Command Centre order debt by truthful urgency (G1 owns) |
| **Cross-surface coherence** | Surfaces agree on the same operational facts |
| **Operational trust continuity** | Post-action refresh does not regress or contradict prior truthful state |
| **Projection comprehension** | Counts, badges, summaries match explainable runtime truth |
| **Actionable clarity** | CTAs route to the correct target with correct scope |
| **Cognitive contradiction detection** | No paired widgets/CTAs/wording implying incompatible states |
| **Navigability** | No orphan; no circular routing without resolution owner |
| **Resolution clarity** | When projections disagree, operator knows authoritative source (§3.6) |
| **Trust continuity under contradiction** | Cross-surface conflicts do not collapse operator confidence without disclosure |

This doctrine guides **G-CTA**, **G-CTA-NOOP**, **G-CYCLE**, **G-RESOLVE**, **G7 freshness**, **G2 widget coherence**, **G1 attention authority**, and trust-risk classifications.

---

## 0.4 Implementation infrastructure (rev 4)

| Component | Location |
|-----------|----------|
| Shared framework | `backend/services/ops_runtime_verify_02/` |
| G0 harness (local) | `backend/tmp_ops_control_g0_programme_precheck_execute.py` |
| G0 cycle triage harness (local) | `backend/tmp_ops_control_g0_cycle_triage_execute.py` |
| Programme audit root | `backend/docs/audit/ops_control_verify_02/` |
| Family alias scaffolds | `backend/docs/audit/ops_runtime_g{1..7}_*/STATUS.json` |
| Unit tests | `backend/tests/test_ops_runtime_verify_02_framework.py` |

**Harness default:** `--scaffold-only` (implicit) — emits static artifacts with `NOT_EXECUTED`; no staging API.  
**G0 execution:** requires explicit `--execute-runtime` (deferred).

---

## 1. Programme architecture (refined)

```
PROGRAMME G0 (ops_control_g0_programme_precheck)
    │  pilot lock · VERIFY-01 lineage · baseline snapshots · CTA inventory
    ▼
G1 today_page → G2 command_centre → G3 properties_page → G4 requirements_page
    → G5 documents_page → G6 calendar_page → G7 reports_page
    │  each: bounded same-run · operational_browser · G-CTA · G-CTA-NOOP · G9/G10
    ▼
(Optional future G8 cross-surface control integrity — integration-only; not in initial scope)
```

| Layer | Rule |
|-------|------|
| **Families** | G0 (programme) + G1–G7 (surfaces); one bundle per owner per pilot |
| **Proof mode** | `operational_browser` mandatory for `VERIFIED_OPERATIONALLY` |
| **Harness** | `backend/tmp_ops_control_g{N}_*_execute.py` — local only; never committed |
| **Anti-scope-creep** | `SURFACE_SCOPE_DRIFT` if family re-proves VERIFY-01 domain lifecycles |
| **Anti-inheritance fallacy** | F1–F8 PASS ≠ G1–G7 PASS |

**Execution order:** G0 → G1 → G2 → G3 → G4 → G5 → G6 → G7 (sequential; no parallel runs on same pilot in same window).

**Blocking:** G{N+1} **BLOCKED** if G0 or any required upstream G-family is `FAIL_SYSTEM`, `TRUST_RISK_PRESENT`, `PROJECTION_AUTHORITY_DRIFT`, or `BLOCKED`.

---

## 2. Ownership boundaries (hardened)

### 2.1 Surface family map

| Family | Slug | Routes | Authoritative for |
|--------|------|--------|-----------------|
| **G0** | `ops_control_g0_programme_precheck` | (none — programme) | Baseline lineage, pilot lock, pre-execution snapshots |
| **G1** | `ops_control_g1_today_page` | `/today`, `/tasks`→redirect | **Attention arbitration** — urgency ordering, snooze/dismiss rules, operational debt precedence (§3.1) |
| **G2** | `ops_control_g2_command_centre` | `/command-center` | **Live** runtime truth + **cross-widget coherence** — no widget islands (§3.2) |
| **G3** | `ops_control_g3_properties_page` | `/properties`, `/properties/:id` | Property summaries, tabs, cross-tab linkage, property CTAs |
| **G4** | `ops_control_g4_requirements_page` | `/requirements` | Requirement lifecycle **display**, evidence **visibility**, follow-up CTAs |
| **G5** | `ops_control_g5_documents_page` | `/documents`, `/documents/bulk-upload` | Document **surface** upload/visibility/routing/linkage (see §2.4) |
| **G6** | `ops_control_g6_calendar_page` | `/calendar` | Operational calendar **surface** coherence (see §2.5) |
| **G7** | `ops_control_g7_reports_page` | `/reports/*` | **Derived/exported** truth + **report freshness authority** — no masquerading as live (§2.3, §3.3) |

### 2.2 VERIFY-01 inherited — not re-proved (programme-wide)

Families G1–G7 **must not** re-verify:

| VERIFY-01 domain | Owner slug | VERIFY-02 may only |
|------------------|------------|---------------------|
| Issue lifecycle | `ops_runtime_01_issues` | Reference IDs; deeplink to issue surfaces |
| WO / job lifecycle | `ops_runtime_02_work_orders` | Reference IDs; open WO from property/calendar |
| Contractor portal | `ops_runtime_03_contractor` | Observe client-side visibility only |
| Risk propagation | `ops_runtime_04_risk_signals` | Read live widgets; no regen certification |
| Client sync projections | `ops_runtime_05_client_sync` | Compare G2 live truth to F5 bundle; no full re-sync run |
| Rent ops | `ops_runtime_06_rent_ops` | Read rent widgets on G2/G7; no payment lifecycle rerun |
| Tenant portal | `ops_runtime_07_tenant_portal` | Out of VERIFY-02 scope (client surfaces only) |
| Cross-domain chain | `ops_runtime_08_cross_domain` | Lineage reference in G0 only |

**Violation:** classify run **`SURFACE_SCOPE_DRIFT`**; do not commit as `VERIFIED_OPERATIONALLY`.

### 2.3 Projection authority boundary (G2 vs G7)

**Semantic artifact (required in G2 and G7 bundles):** `projection_authority_boundary.md`

#### G2 OWNS (authoritative for live runtime)

- Live operational widgets and cards
- Live counts (open issues, WOs, attention items, alerts)
- Live operational attention state and urgency ordering
- Live projection freshness (async convergence on **live** surfaces)
- Drill-down from Command Centre to **runtime** targets (property, requirement, issue, calendar entry)
- Cross-widget **live** non-contradiction on `/command-center`

#### G2 DOES NOT OWN

- Report PDF/export generation correctness
- Report aggregation windows / rollups / historical snapshots
- Exported file contents or CSV semantics
- Reporting lag policy or disclosure copy (beyond noting live vs derived mismatch)
- Compliance certification truth in report narratives
- Derived KPI definitions used only in `/reports/*`

#### G7 OWNS (authoritative for derived reporting)

- Report summaries and section totals on `/reports/*`
- Export/download flows (surface + file presence + summary coherence)
- Reporting drilldowns and report-internal navigation
- Reporting aggregation coherence (rollup = sum of explainable parts)
- **Reporting lag disclosures** — document and verify stated vs observed lag
- Derived/exported KPI truth **within reporting surfaces**

#### G7 DOES NOT OWN

- Live Command Centre widget freshness (references G2 bundle)
- Live Today task ordering
- Real-time alert firing logic
- Domain lifecycle mutations (issues, WOs, documents upload pipeline internals)
- Re-proving F5 client-sync convergence run

#### Shared KPI reference inheritance

| KPI / metric | Live authority | Derived authority | Divergence handling |
|--------------|----------------|-------------------|---------------------|
| Open issues count | **G2** | G7 cites G2 + `reporting_lag.json` | G7 run: compare report total to G2 snapshot + lag window; mismatch → **`PROJECTION_AUTHORITY_DRIFT`** |
| WO / job open counts | **G2** | G7 | Same |
| Requirement overdue / attention | **G2** (live) / **G4** (requirement surface detail) | G7 | G4 wins on requirement row truth; G2 wins on aggregate widget; G7 must not contradict both |
| Compliance score / certification KPIs | Observe-only | **G7** (wording + derived only) | Must not claim ops-only action changed compliance |

**When counts diverge:**

1. **Live UI (G2) vs API live endpoint** → G2 owner remediates; **`FAIL_OPERATIONAL`** or **`PROJECTION_AUTHORITY_DRIFT`**.
2. **Report (G7) vs G2 live snapshot** → If within documented lag → G7 PASS with `reporting_lag.json`; if outside lag → **`PROJECTION_AUTHORITY_DRIFT`** (G7 owner).
3. **G7 vs G4 requirement row** → G4 wins row-level; G7 aggregate must reconcile or **`PROJECTION_AUTHORITY_DRIFT`**.

G2 bundle **must** include `live_projection_snapshot.json` and `projection_resolution_order.json` (live reconciler). G7 bundle **must** include `derived_projection_snapshot.json`, `reporting_lag.json`, and `projection_resolution_order.json` (derived reconciler) with explicit G2 bundle reference. See §3.6 when counts disagree (e.g. Today 5 / CC 3 / Report 7).

### 2.4 G5 documents — surface boundary

#### G5 MAY verify

- Upload surface coherence (file selected → progress → visible row)
- Document visibility on `/documents`
- Document routing and deeplinks
- Review visibility (status visible to client; not reviewer-assistance logic)
- Requirement linkage **visibility** (linked requirement appears; navigation works)
- Projection freshness after upload/review on **documents surface**
- Refresh persistence
- CTA coherence (no dead/duplicate document actions)
- Upload lifecycle **visibility** (states shown match API document state)

#### G5 MUST NOT re-verify

- Extraction correctness
- AI extraction truth
- Compliance derivation
- Authority derivation internals
- Certification correctness
- Reviewer-assistance logic
- Full operational closure pipelines (requirement satisfied / compliance complete)
- OPS-VERIFY-01 evidence journeys

**Bounded mutation:** One client upload or attach-to-known-requirement; observe surface propagation only.

### 2.5 G6 calendar — scope boundary (`CALENDAR_SCOPE_BOUNDARY`)

#### G6 verifies ONLY

- Operational calendar surface coherence on `/calendar`
- Event appearance (jobs, reminders, inspections, renewals as presented)
- Scheduling **visibility** and deeplink routing
- Reminder/job/inspection **projection** on calendar (not worker correctness)
- Date/time **presentation** truthfulness (display matches API event fields for pilot timezone)
- Refresh persistence after known lifecycle mutation (from G4/G5 or referenced VERIFY-01 IDs)
- Async propagation **visibility** (event appears within convergence SLA)

#### G6 EXPLICITLY EXCLUDES

- Recurring scheduler certification
- Timezone edge-case certification (pilot-local presentation only)
- ICS/export integrations
- Long-range recurrence engines
- Worker fleet correctness / cron certification
- Scheduler architecture redesign
- Full WO scheduling lifecycle (VERIFY-01 F2 owns)

---

## 3. Control-plane verification models

### 3.1 G1 — Attention authority (`ATTENTION_AUTHORITY_RULES`)

**Doctrine:** `/today` is an **operational attention arbitration surface**, not merely a task list.

G1 is authoritative for **attention ordering truth** on the Today page. G2 owns live aggregate widgets; G1 owns **list order, urgency semantics, and snooze/dismiss behaviour** on `/today`.

#### Precedence rules (mandatory evaluation)

| Rank | Debt class | Rule |
|------|------------|------|
| 1 | **Overdue remediation** | Outranks informational reminders and passive nudges |
| 2 | **Active risk / remediation signals** | Outrank passive document nudges and non-blocking info |
| 3 | **Open operational debt** (issues, WOs, requirements needing action) | Outrank informational-only items |
| 4 | **Time-bound reminders** | Ordered by due date / expiry truth |
| 5 | **Informational / passive nudges** | Lowest; must not appear above higher-rank debt without documented filter |

#### Ordering semantics

| Rule | Verification |
|------|--------------|
| **Urgency precedence** | Higher urgency badge rank appears before lower for same debt class |
| **Operational debt precedence** | Actionable debt before read-only informational rows |
| **Risk/remediation precedence** | Risk-linked items before unrelated document nudges |
| **Informational vs actionable** | Informational rows must be labelled or styled distinctly; must not mimic actionable urgency |
| **Snooze reappearance** | Snoozed items reappear **only** after snooze expiry or documented unsnooze mutation |
| **Dismiss resurrection** | Dismissed items **must not** silently return without state mutation + audit |
| **Stale dismiss detection** | If API shows dismissed but UI shows active (or reverse) → **`OPERATIONAL_ATTENTION_CONTRADICTION`** |
| **Contradictory urgency badges** | Same entity with conflicting badges across list vs detail → **`OPERATIONAL_ATTENTION_CONTRADICTION`** |
| **Priority drift** | Order contradicts precedence rules while API debt unchanged → **`ATTENTION_PRIORITY_DRIFT`** |

**Required artifact (G1):** `attention_authority.json`

```json
{
  "ordered_items": [{ "id": "", "class": "", "urgency_rank": 0, "position": 0 }],
  "precedence_violations": [],
  "snooze_expiry_checks": [],
  "dismiss_resurrection_checks": [],
  "cross_badge_contradictions": []
}
```

**Cross-reference:** G1 `attention_authority.json` compared to G2 `widget_coherence_matrix.json` for aggregate vs list agreement (G2 owns widget-level contradiction; G1 owns list order).

### 3.2 G2 — Widget-island failure (`WIDGET_ISLAND_FAILURE`)

**Definition:** Individual widgets are **internally coherent** but **globally contradictory** operationally.

| Example contradiction | Detection |
|-------------------------|-----------|
| Risk widget `critical_count=5` | vs attention widget `urgent_actions=0` |
| Property health “healthy” | vs Today showing unresolved critical debt |
| Open issues count > 0 | vs “all clear” summary card |

#### G2 MUST verify

- Cross-widget operational agreement (same debt class, same magnitude direction)
- Attention hierarchy agreement with G1 precedence (read G1 bundle after G1 complete)
- Alert vs widget agreement (alert severity matches widget counts)
- Projection coherence across all Command Centre widgets
- No isolated truth islands

**Required artifact (G2):** `widget_coherence_matrix.json`

```json
{
  "widgets": [{ "id": "", "metrics": {}, "internal_coherent": true }],
  "cross_widget_pairs": [{ "a": "", "b": "", "coherent": true, "note": "" }],
  "island_failures": []
}
```

**Classification:** Any confirmed island → **`WIDGET_ISLAND_FAILURE`** minimum; also **`COGNITIVE_TRUST_RISK`**. Blocks `VERIFIED_OPERATIONALLY` until remediated.

### 3.3 G7 — Report freshness authority (`REPORT_FRESHNESS_AUTHORITY`)

**Doctrine:** Reports must **not** silently masquerade as live truth.

Derived surfaces must make **staleness legible** to operators.

#### G7 MUST verify (visible + coherent)

| Element | Requirement |
|---------|-------------|
| Report generation timestamp | Visible on report view or export metadata |
| Snapshot / as-of timestamp | Visible where rollup is point-in-time |
| Freshness wording | Copy distinguishes live vs derived (e.g. “as of”, “generated”) |
| Lag disclosure | Stated lag or refresh policy visible when snapshot lags live |
| Export generation time | Export file/metadata time coherent with on-screen snapshot |
| Live-vs-report distinction | Operator can understand report is not real-time Command Centre |

**Required artifact (G7):** `report_freshness_capture.json`

```json
{
  "report_id": "",
  "generation_timestamp_visible": true,
  "snapshot_timestamp_visible": true,
  "freshness_wording_visible": true,
  "lag_disclosure_visible": true,
  "export_timestamp_coherent": true,
  "live_vs_report_distinction_clear": true,
  "g2_snapshot_reference": "ops_control_g2_.../live_projection_snapshot.json",
  "staleness_seconds": 0
}
```

**Classification:**

| Condition | Classification |
|-----------|----------------|
| Report stale vs G2 live **and** no freshness disclosure visible | **`REPORT_FRESHNESS_DECEPTION`** minimum + **`COGNITIVE_TRUST_RISK`** |
| Stale but disclosure visible and accurate | PASS with `reporting_lag.json` |
| Timestamps missing | **`REPORT_FRESHNESS_DECEPTION`** or **`COGNITIVE_TRUST_RISK`** |

### 3.4 Operational orphan state (`OPERATIONAL_ORPHAN_STATE`)

**Definition:** An operational entity **exists** in runtime (API/DB) but has **no coherent operational ownership/navigation path** from control surfaces.

| Orphan pattern | Example |
|----------------|---------|
| Hidden debt | Issue open in API; unreachable from property/tasks/reports |
| Actionless requirement | Requirement exists; no actionable route from Requirements/Property/Today |
| Lifecycle-hidden document | Document exists; no visible lifecycle state on Documents surface |
| Report ghost reference | Report cites operational debt with broken drilldown |
| Broken Today deeplink | Today item visible; deeplink 404 while entity still open |

#### Verification requirements (all families, programme discipline)

1. Every **surfaced** operational entity must have ≥1 **truthful** navigation path (CTA or deeplink) to authoritative detail.  
2. Every **open** debt known to API for pilot scope must be reachable from ≥1 of: G1, G2, G3, G4, G5, G6, G7 (family records reachability in audit).  
3. Orphaned entities recorded explicitly — not ignored as “edge case”.  
4. Dead operational references (UI points to missing entity) → orphan or **`TRUST_RISK_PRESENT`**.

**Required artifact (per family):** `operational_orphan_audit.json` (G0 captures baseline empty template + route map)

```json
{
  "entities_checked": [{ "type": "", "id": "", "open": true }],
  "navigation_paths": [{ "entity_id": "", "from_surface": "", "reachable": true, "route": "" }],
  "orphans": [],
  "dead_references": []
}
```

**Classification:**

| Condition | Classification |
|-----------|----------------|
| Entity open; no reachable path | **`OPERATIONAL_ORPHAN_STATE`** |
| User-visible row/deeplink contradicts reachability | **`OPERATIONAL_ORPHAN_STATE`** + **`TRUST_RISK_PRESENT`** minimum |
| Report-only unreachable debt | **`OPERATIONAL_ORPHAN_STATE`** (G7 owner if report-introduced) |
| Orphan reachable only via circular path | **`OPERATIONAL_ORPHAN_STATE`** + **`CONTROL_PLANE_CIRCULARITY`** |

### 3.5 Control-plane circularity (`CONTROL_PLANE_CIRCULARITY`)

**Definition:** Multiple operational surfaces route operators between each other **without** a clearly authoritative **operational action / resolution owner**.

Operators bounce across surfaces but cannot complete a truthful mutation or reach authoritative detail.

#### Examples

| Pattern | Failure |
|---------|---------|
| Surface loop | Today → report → command centre → property → Today (no mutation owner) |
| CTA loop | Deeplinks circularly redirect with no terminal detail |
| Debt via loop only | Operational entity reachable only through circular navigation |
| Escalation without owner | Surfaces reference each other; no actionable resolution CTA |
| Infinite drilldown | Repeated “view more” across surfaces past depth limit |

#### `CONTROL_PLANE_CIRCULARITY_RULES` (mandatory detection)

| Rule | Detection |
|------|-----------|
| **Circular CTA loops** | Same entity visited on ≥2 surfaces with no terminal authoritative detail |
| **Unresolved routing cycles** | Navigation graph contains cycle without `authoritative_resolution_owner` |
| **Navigation recursion** | Same route/surface repeats in path without state transition |
| **Authority-owner ambiguity** | Cycle path has conflicting `mutation_owner` / `resolution_owner` |
| **Mutationless chains** | ≥3 surface hops with zero persisted mutation where action implied |
| **Infinite drilldown** | Depth > `max_allowed_navigation_depth` (default **5**) without terminal entity |
| **Escalation without resolution** | “Review” / “investigate” CTAs only route to another aggregate surface |

**Required artifact (G0 baseline + per family):** `control_plane_circularity.json`

```json
{
  "entry_surface": "",
  "cycle_path": ["", ""],
  "authoritative_resolution_owner": "",
  "mutation_owner_present": false,
  "max_navigation_depth": 5,
  "loop_detected": false,
  "resolution_reachable": true,
  "cycles": []
}
```

**Classification:**

| Condition | Classification |
|-----------|----------------|
| Loop without resolution owner | **`CONTROL_PLANE_CIRCULARITY`** minimum + **`COGNITIVE_TRUST_RISK`** |
| User-visible unresolved loop | **`CONTROL_PLANE_CIRCULARITY`** + **`TRUST_RISK_PRESENT`** |
| Loop masks orphan | Also **`OPERATIONAL_ORPHAN_STATE`** |

**G0:** Static route-graph scan + CTA inventory cycle detection. **G1–G7:** Runtime path walks from material CTAs.

### 3.6 Projection resolution order (`PROJECTION_RESOLUTION_ORDER`)

**Purpose:** When projections disagree, operators must know **which surface is authoritative first** — and whether disagreement is drift, acceptable lag, or trust-risking ambiguity.

#### Canonical authority hierarchy (rank 1 = highest)

| Rank | Projection class | Authoritative surface / family | `projection_type` |
|------|------------------|------------------------------|-------------------|
| **1** | Live operational runtime | Command Centre / APIs backing live widgets | **G2** — `live` |
| **2** | Operational attention projections | Today list ordering & attention badges | **G1** — `attention_list` |
| **3** | Property-scoped summaries | Property detail tabs & row truth | **G3** (display); row detail **G4** for requirements |
| **4** | Derived reporting projections | Reports on-screen rollups | **G7** — `derived` |
| **5** | Exported / static reporting artifacts | PDF/CSV/export files | **G7** — `exported` |

**Override rules:**

| Situation | Authoritative | Notes |
|-----------|---------------|-------|
| Today **5** vs Command Centre **3** (open debt count) | **G2 live** for aggregate count; **G1** for list order | List vs aggregate mismatch → apply §3.6 reconciliation |
| Command Centre **3** vs Report **7** | **G2** for live; **G7** if within `freshness_window` + disclosure | Outside window → **`PROJECTION_AUTHORITY_DRIFT`** or **`PROJECTION_LAG_UNDISCLOSED`** |
| Report **7** vs requirement row **5** | **G4** row wins entity-level; **G7** must reconcile aggregate | Else **`PROJECTION_RESOLUTION_FAILURE`** |
| Lag within `freshness_window` + truthful disclosure | **Acceptable** — not drift | Record in `reporting_lag.json` |
| Lag outside window OR no disclosure | **Not acceptable** | **`PROJECTION_LAG_UNDISCLOSED`** or **`PROJECTION_AUTHORITY_DRIFT`** |
| Operator cannot determine winner | — | **`PROJECTION_RESOLUTION_FAILURE`** + **`TRUST_RISK_PRESENT`** minimum |

**Reconciliation owner:**

| Disagreement type | Owner family |
|-------------------|--------------|
| Live vs live (G2 widgets, G1 list) | **G2** leads; G1 documents attention-specific deltas |
| Live vs derived (G2 vs G7) | **G7** run reconciles against G2 snapshot; G2 owns live truth |
| Row vs aggregate (G4 vs G7) | **G4** row; G7 fixes rollup or classifies failure |
| Any unresolved cross-rank | Programme classifier; block downstream until resolved |

**Required artifact (G0 template + G2/G7 mandatory):** `projection_resolution_order.json`

```json
{
  "contradictions": [{
    "source_surface": "",
    "projection_type": "live|attention_list|property_summary|derived|exported",
    "authority_rank": 1,
    "value": 0,
    "freshness_window_seconds": 60,
    "disclosure_required": false,
    "disclosure_present": true,
    "reconciliation_owner": "ops_control_g2_command_centre",
    "contradiction_detected": false,
    "resolution": "acceptable_lag|authoritative_winner|unresolved"
  }]
}
```

**Relationship to `projection_authority_owner`:** `projection_authority_owner` (route map) declares **who may assert** truth on a route; `PROJECTION_RESOLUTION_ORDER` declares **who wins** when multiple assertions conflict.

---

## 4. Programme-level G0 bundle

**Owner slug:** `ops_control_g0_programme_precheck`  
**Path:** `backend/docs/audit/ops_control_g0_programme_precheck_{client_id}_{property_id}/`

**Purpose:** Establish immutable pre-execution baseline so later divergence cannot be attributed to unknown pre-existing state.

### 4.1 Required artifacts

| Artifact | Content |
|----------|---------|
| `REPORT.md` | Programme G0 summary |
| `07_classification.json` | G0 classification (see §4.2) |
| `pilot_lock.json` | client_id, property_id, landlord session role, slug |
| `deployment_continuity.json` | origin/main SHA, staging URL, behavioural smoke notes, `/api/version` attestation |
| `verify_01_lineage.json` | F1–F8 bundle paths + classifications (read-only inheritance) |
| `active_routes_snapshot.json` | Canonical + `/app/*` redirect map for G1–G7 routes |
| **`route_authority_map.json`** | Route ownership + resolution rank + cycle exemptions (§4.4) |
| **`projection_resolution_order.json`** | Baseline template + rank definitions (§3.6) |
| **`control_plane_circularity.json`** | G0 static cycle scan + unresolved escalation chains (§3.5) |
| `cta_inventory_baseline.json` | Programme-level CTA catalog — refined per family |
| `entitlement_snapshot.json` | Reports PDF, white-label, feature gates affecting G7 |
| `feature_flag_snapshot.json` | Flags affecting control surfaces |
| `surface_availability.json` | Each route reachable (HTTP + shell mount) |
| `baseline_projection_snapshot.json` | Live API snapshots: tasks, command-centre counts, open issues, requirements summary |
| `projection_authority_boundary.md` | G2/G7 authority semantics (copy of charter §2.3) |
| `operational_orphan_audit.json` | Baseline orphan scan + orphan-to-loop interactions |
| `watchlist.md` | Known gaps before G1 (e.g. version SHA unknown) |

### 4.2 G0 classification rules

| Classification | Criteria |
|----------------|----------|
| **`VERIFIED_OPERATIONALLY`** | All G0 artifacts present; VERIFY-01 F1–F8 all `VERIFIED_OPERATIONALLY`; pilot reachable; deployment continuity recorded; surfaces available |
| **`BLOCKED`** | Any VERIFY-01 family not `VERIFIED_OPERATIONALLY`; pilot unreachable; staging down |
| **`FAIL_SYSTEM`** | Lineage bundles missing on origin; pilot data corrupt |
| **`WATCHLIST`** | Non-blocking gaps (e.g. deploy SHA unknown) with signed owner before G1 |

**G0 does not prove G1–G7 surfaces** — only baseline and readiness.

### 4.3 G0 governance and inheritance

- **Tracker:** `LAUNCH_AUTHORITY_TRACKER.md` § PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G0 row updated on G0 completion.
- **Inheritance:** Every G1–G7 bundle `shared_dependency_bundle_ids` **must** include `ops_control_g0_programme_precheck_*/07_classification.json`.
- **Route authority:** Every G-family run **must** cite `route_authority_map.json` for routes touched; must not assert authority outside assigned owner.
- **Immutability:** G0 bundle committed before G1 starts; G1 must not mutate G0 artifacts.
- **Re-G0 trigger:** Pilot change, VERIFY-01 reclassification, or major deploy changing routes/entitlements → new G0 run required.

### 4.4 G0 route ownership snapshot (`route_authority_map.json`)

**Purpose:** Prevent ownership ambiguity between G1/G2, G2/G7, G2/G3, G4/G5 before execution.

**G0 baseline scans (rev 4):**

| Scan | Artifact | Detects |
|------|----------|---------|
| Circular route detection | `control_plane_circularity.json` | Static CTA/route cycles in inventory |
| Unresolved escalation chains | `control_plane_circularity.json` | Aggregate→aggregate paths without resolution owner |
| Orphan-to-loop interaction | `operational_orphan_audit.json` | Entity reachable only via loop (not true reachability) |
| Projection rank registration | `projection_resolution_order.json` | All surfaces mapped to authority rank |

**Required per route entry:**

| Field | Description |
|-------|-------------|
| `route` | Canonical path (and `/app/*` alias if any) |
| `authoritative_family_owner` | G-family slug that owns surface truth |
| `authoritative_resolution_owner` | Family/slug owning **terminal operational resolution** for primary debt on this route |
| `inherited_dependency_owners` | VERIFY-01 or upstream G slugs (read-only) |
| `operational_domain` | e.g. `attention`, `live_projection`, `property_hub`, `requirement`, `document`, `calendar`, `reporting` |
| `primary_cta_owner` | Family owning CTA-RUNTIME-ROUTE-01 for primary actions |
| `mutation_owner` | VERIFY-01 slug or G-family slug for primary mutations (or `none` if read-only) |
| `projection_authority_owner` | `live`, `attention_list`, `row`, `derived`, `exported`, `surface_visibility`, `temporal_visibility`, `none` |
| `projection_resolution_rank` | Integer **1–5** per §3.6 canonical hierarchy |
| `cycle_detection_exemptions` | Documented benign redirects (e.g. `/tasks`→`/today`) — must not mask operational loops |
| `max_allowed_navigation_depth` | Default **5** hops from entry surface to terminal entity |

**Example entries:**

| route | authoritative_family_owner | projection_authority_owner |
|-------|---------------------------|----------------------------|
| `/today` | `ops_control_g1_today_page` | `attention_list` |
| `/command-center` | `ops_control_g2_command_centre` | `live` |
| `/properties/:id` | `ops_control_g3_properties_page` | `live` (display); aggregates defer to G2 |
| `/requirements` | `ops_control_g4_requirements_page` | `row` |
| `/documents` | `ops_control_g5_documents_page` | `surface_visibility` |
| `/calendar` | `ops_control_g6_calendar_page` | `temporal_visibility` |
| `/reports/*` | `ops_control_g7_reports_page` | `derived` |

**Dispute resolution:** If two families assert same projection authority → run **`PROJECTION_AUTHORITY_DRIFT`**; charter §2.3 and `route_authority_map.json` prevail.

---

## 5. Checkpoint taxonomy (refined)

| Code | Layer |
|------|--------|
| **G0** | Preflight / programme or family |
| **G1** | Browser action executed |
| **G2** | User outcome (visible truth) |
| **G3** | System outcome (API/DB) |
| **G4** | Async convergence |
| **G5** | Refresh persistence |
| **G7** | Wording / forbidden semantics |
| **G9** | Idempotency |
| **G10** | Authority integrity |
| **G-CTA** | CTA-RUNTIME-ROUTE-01 |
| **G-CTA-NOOP** | Silent success / no runtime change (§5) |
| **G-LINK** | Deeplink resolution |
| **G-ATTN** | G1 attention authority (`ATTENTION_AUTHORITY_RULES`) |
| **G-WIDGET** | G2 cross-widget coherence (`WIDGET_ISLAND_FAILURE`) |
| **G-FRESH** | G7 report freshness (`REPORT_FRESHNESS_AUTHORITY`) |
| **G-ORPHAN** | Operational orphan audit (`OPERATIONAL_ORPHAN_STATE`) |

**Minimum `VERIFIED_OPERATIONALLY`:** G0 + G1 + G2 + G3 + G4 (if async) + G5 + G7 + G9 + G10 + G-CTA + G-CTA-NOOP + G-LINK + family-mandatory G-ATTN (G1), G-WIDGET (G2), G-FRESH (G7), G-ORPHAN (all).

---

## 6. Silent CTA no-op model (`G-CTA-NOOP`)

### 6.1 Detection definition

A CTA **appears successful** but runtime truth is unchanged:

| Signal | Probe |
|--------|-------|
| No mutation persisted | API/DB entity unchanged (id, status, timestamps) |
| Optimistic-only UI | UI changes before refresh; gone after hard reload |
| Modal closes, no transition | Modal dismiss without state change |
| Browser diverges after refresh | Post-refresh UI ≠ pre-action API truth |
| API unchanged after action | Same response on re-GET |
| Queue never receives work | No job/event/audit row where design expects one |
| Projection unchanged | Counts/lists identical despite success toast |

### 5.2 Required probes (every material CTA)

1. **Pre-capture:** API + visible state (T0)  
2. **Post-action:** Immediate API compare (T+1s)  
3. **Post-refresh:** Hard reload browser compare (T+5s)  
4. **Mutation timestamp:** Where applicable, `updated_at` / audit event must advance  
5. **Convergence:** T+30s / T+60s stability (no rollback)

**Artifact:** `cta_noop_probes.json`

### 6.3 Classification guidance

| Finding | Classification |
|---------|----------------|
| Optimistic-only; refresh restores unchanged state | **`FAIL_OPERATIONAL_NOOP`** |
| Toast/success but API/DB unchanged | **`FAIL_OPERATIONAL_NOOP`** |
| Second click creates duplicate while first was silent no-op | **`TRUST_RISK_PRESENT`** minimum |
| Persisted duplicate row + UI shows single success | **`TRUST_RISK_PRESENT`** + **`FAIL_SYSTEM`** |
| Technical success but operator misled (confusing copy) | **`COGNITIVE_TRUST_RISK`** |

`FAIL_OPERATIONAL_NOOP` **blocks** `VERIFIED_OPERATIONALLY` until remediated and same-run rerun.

---

## 7. Cross-surface CTA model (`CTA-RUNTIME-ROUTE-01`)

Unchanged intent; hardened with G-CTA-NOOP (§5). Each family updates `cta_inventory.json` from G0 baseline.

**Programme rules:**

- No duplicate CTAs for same mutation on same entity  
- No contradictory CTAs on same entity  
- No dead-end CTAs  
- No stale deeplinks (`/app/*` vs canonical)  
- No upload-primary contradiction on operational workflows  
- No false “resolved / compliant / current” wording  
- No **circular routing** without `authoritative_resolution_owner` (§3.5)

---

## 7.1 G-family integration (circularity + resolution)

| Family | G-CYCLE focus | G-RESOLVE focus |
|--------|---------------|-----------------|
| **G1** | Today deeplink loops; escalation chains that only route to G2/G7 aggregates | Attention list vs G2 live count reconciliation |
| **G2** | Widget drill-down loops; alert → widget → alert recursion | **Primary live reconciler** — `projection_resolution_order.json` for cross-widget + vs G1 |
| **G3** | Property tab drilldown ownership; tab ↔ hub ↔ Today cycles | Property summary vs G2 live; row vs tab |
| **G4** | Requirement follow-up recursion (req → doc → req without action) | Row-level truth vs G2/G7 aggregates |
| **G5** | Document ↔ requirement navigation loops | Surface visibility vs G4 row |
| **G6** | Event deeplink ↔ property ↔ calendar recursion | Temporal visibility vs G2 live scheduling counts |
| **G7** | Report drilldown ↔ CC ↔ property loops | **Derived reconciler** — report vs G2 snapshot; lag disclosure |

---

## 8. Convergence model

| Surface class | SLA |
|---------------|-----|
| Task snooze/dismiss (G1) | 60s |
| Command Centre widgets (G2) | 60s |
| Property tabs (G3) | 60s |
| Requirements (G4) | 60–90s |
| Document upload (G5) | 90s |
| Calendar event appearance (G6) | 60–90s |
| Report generation (G7) | 90s + `reporting_lag.json` |

**Agreement rule:** Browser == live API == DB marker (where applicable). Derived G7 may lag within documented bound only.

---

## 9. G9 / G10 (not weakened)

Same discipline as VERIFY-01. Surface-specific:

- **G9:** repeat CTA, repeat tab open, repeat report generate, duplicate visible rows  
- **G10:** false closure, tenant/client boundary on client surfaces, monotonic requirement display  

---

## 10. Classification taxonomy (control-plane matrix)

### 10.1 Core classifications

| Classification | When | Minimum severity | Blocks `VERIFIED_OPERATIONALLY` |
|----------------|------|------------------|--------------------------------|
| **`VERIFIED_OPERATIONALLY`** | Full checkpoints incl. control-plane gates | — | — |
| **`VERIFIED_SYSTEM_ONLY`** | API/DB without browser/CTA/control-plane proof | Info | Yes (cannot upgrade without rerun) |
| **`FAIL_OPERATIONAL`** | User-visible incorrect state; broken route; stale live UI | High | Yes |
| **`FAIL_OPERATIONAL_NOOP`** | Apparent success; runtime unchanged (§6) | High | Yes |
| **`FAIL_SYSTEM`** | Persistence, duplicate debt, authority leak | Critical | Yes |
| **`TRUST_RISK_PRESENT`** | Visible truth contradicts system; false completion | Critical | Yes |
| **`COGNITIVE_TRUST_RISK`** | Functional but misleading/confusing for operators | High | Yes |
| **`PROJECTION_AUTHORITY_DRIFT`** | Wrong family or G2 vs G7 vs G4 authority mismatch | High | Yes |
| **`SURFACE_SCOPE_DRIFT`** | Re-proved VERIFY-01 or excluded scope | High | Yes |
| **`ASYNC_CONVERGENCE_PARTIAL`** | Persisted; UI lags past SLA | Medium | Yes |
| **`BLOCKED`** | G0/upstream/VERIFY-01 dependency failed | — | Yes |
| **`WATCHLIST`** | Signed waiver + re-verify date | Low | No (if waiver signed) |

### 10.2 Control-plane classifications (rev 3)

| Classification | Trigger conditions | Minimum severity | Coexistence with `TRUST_RISK_PRESENT` |
|----------------|-------------------|------------------|--------------------------------------|
| **`ATTENTION_PRIORITY_DRIFT`** | Today list order violates §3.1 precedence while API debt unchanged | High | Add if user sees wrong “top” action |
| **`OPERATIONAL_ATTENTION_CONTRADICTION`** | Conflicting urgency badges; dismiss/snooze UI vs API mismatch | High | **Always add** when user-visible |
| **`WIDGET_ISLAND_FAILURE`** | `widget_coherence_matrix.json` records island (§3.2) | High | **Always add** `COGNITIVE_TRUST_RISK` |
| **`OPERATIONAL_ORPHAN_STATE`** | Open entity; no truthful navigation path (§3.4) | High | Add if user sees debt without path |
| **`REPORT_FRESHNESS_DECEPTION`** | Stale report; missing/ false freshness disclosure (§3.3) | High | **Always add** `COGNITIVE_TRUST_RISK` |

### 10.3 Control-plane classifications (rev 4)

| Classification | Trigger conditions | Minimum severity | Coexistence with `TRUST_RISK_PRESENT` |
|----------------|-------------------|------------------|--------------------------------------|
| **`CONTROL_PLANE_CIRCULARITY`** | Routing loop without `authoritative_resolution_owner` (§3.5) | High | **Always add** `COGNITIVE_TRUST_RISK`; add `TRUST_RISK_PRESENT` if user-visible |
| **`PROJECTION_RESOLUTION_FAILURE`** | Contradictory projections; operator cannot determine winner (§3.6) | High | **Always add** minimum |
| **`PROJECTION_LAG_UNDISCLOSED`** | Lag outside `freshness_window` OR lag with no truthful disclosure | High | Add if user could treat stale as live |

### 10.4 Coexistence rules

- `WIDGET_ISLAND_FAILURE` → **must** also record `COGNITIVE_TRUST_RISK` (minimum).  
- `REPORT_FRESHNESS_DECEPTION` → **must** also record `COGNITIVE_TRUST_RISK`.  
- `OPERATIONAL_ORPHAN_STATE` + user-visible deeplink/row → **must** add `TRUST_RISK_PRESENT`.  
- `ATTENTION_PRIORITY_DRIFT` alone → may pass without `TRUST_RISK_PRESENT` only if mis-order is not user-visible (rare); default add `COGNITIVE_TRUST_RISK`.  
- Multiple control-plane tags allowed in `07_classification.json` `secondary_classifications[]`.
- `CONTROL_PLANE_CIRCULARITY` → **must** add `COGNITIVE_TRUST_RISK`; add `TRUST_RISK_PRESENT` if user-visible unresolved loop.
- `PROJECTION_RESOLUTION_FAILURE` → **must** add `TRUST_RISK_PRESENT` minimum.
- `PROJECTION_LAG_UNDISCLOSED` → add `COGNITIVE_TRUST_RISK`; add `REPORT_FRESHNESS_DECEPTION` when on G7.
- Unresolved operator loops → **`COGNITIVE_TRUST_RISK`** minimum (automatic).
- Contradictory projections without resolution authority → **`TRUST_RISK_PRESENT`** minimum (automatic).

**Upgrade rule:** `VERIFIED_SYSTEM_ONLY` → `VERIFIED_OPERATIONALLY` only via new same-run browser proof.

**Combinations:** `FAIL_OPERATIONAL_NOOP` + duplicate on retry → add `TRUST_RISK_PRESENT`. `PROJECTION_AUTHORITY_DRIFT` on G7 → attach G2 `live_projection_snapshot.json`.

---

## 11. Operational lineage discipline

1. **VERIFY-01:** read `07_classification.json` only — never re-classify F1–F8 from G runs.  
2. **G0:** mandatory before G1; committed baseline.  
3. **G{N}:** reads G0 + G1…G{N-1} owner bundles.  
4. **`VERIFIED_OPERATIONALLY`:** commit safe bundle → push → deploy continuity smoke → update trackers.  
5. **Fail families:** no runtime commits unless bounded remediation PR.  
6. **Local ≠ authoritative:** unpushed bundles do not update tracker to verified.

---

## 12. Artifact / bundle structure

### 12.1 G0 programme bundle

```
backend/docs/audit/ops_control_g0_programme_precheck_{client}_{property}/
  REPORT.md
  07_classification.json
  pilot_lock.json
  deployment_continuity.json
  verify_01_lineage.json
  active_routes_snapshot.json
  route_authority_map.json          # mandatory
  cta_inventory_baseline.json
  entitlement_snapshot.json
  feature_flag_snapshot.json
  surface_availability.json
  baseline_projection_snapshot.json
  projection_authority_boundary.md
  operational_orphan_audit.json     # baseline scan
  watchlist.md
```

### 12.2 G-family bundles (additive by owner)

| Artifact | G0 | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
|----------|----|----|----|----|----|----|----|-----|
| `route_authority_map.json` (cite) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `attention_authority.json` | | ✓ | | | | | | |
| `widget_coherence_matrix.json` | | | ✓ | | | | | |
| `report_freshness_capture.json` | | | | | | | | ✓ |
| `operational_orphan_audit.json` | baseline | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `live_projection_snapshot.json` | | | ✓ | | | | | |
| `derived_projection_snapshot.json` | | | | | | | | ✓ |
| `reporting_lag.json` | | | | | | | | ✓ |
| `cta_*` / `deeplink_*` / `convergence.json` | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `g9_*` / `g10_*` | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**Common core (all G1–G7):** `REPORT.md`, `07_classification.json`, `run_manifest.json`, `chain_precheck.json`, `browser_capture.json`, `mutation_sequence.json`, `operational_orphan_audit.json`, `watchlist.md`

**Harness:** `backend/tmp_ops_control_g0_programme_precheck_execute.py`, `backend/tmp_ops_control_g1_today_page_execute.py`, …

---

## 12. Family execution summary

| Order | Family | Bounded mutation |
|-------|--------|------------------|
| 0 | G0 programme precheck | None (snapshots only) |
| 1 | G1 today | Snooze/dismiss/review one task + deeplink |
| 2 | G2 command centre | Live widget read + one drill-down (no domain lifecycle) |
| 3 | G3 properties | Tab navigation + one deeplink per tab class |
| 4 | G4 requirements | Bounded review/ack/follow-up CTA (no upload-only closure) |
| 5 | G5 documents | One upload or attach; surface propagation only |
| 6 | G6 calendar | Observe propagation of known event; one scheduling deeplink |
| 7 | G7 reports | Open/generate one report slice; **G-FRESH** capture; derived vs G2 snapshot |

---

## 14. Anti-scope-creep controls

| Control | Enforcement |
|---------|-------------|
| Mutation budget | Max **one** primary bounded mutation per family per run |
| VERIFY-01 wall | `SURFACE_SCOPE_DRIFT` if lifecycle re-proved |
| G2/G7 wall | `PROJECTION_AUTHORITY_DRIFT` if wrong family asserts authority |
| G5 wall | No extraction/compliance/certification probes |
| G6 wall | `SURFACE_SCOPE_DRIFT` if scheduler/worker/ICS tested |
| No mega-run | G1–G7 never combined in one classifier |
| No launch auth | Programme completion ≠ launch |

---

## 15. Relationship to VERIFY-01

| VERIFY-01 | VERIFY-02 |
|-----------|-----------|
| Domain machinery | Control-surface cognition |
| F1–F8 bundles | G0 + G1–G7 bundles |
| Creates/issues/WOs | Surfaces that **display** them |
| F5 client sync | G2 **live** truth; G7 **derived** truth |

---

## 16. Intentionally deferred

- Launch authorization  
- Architecture / projection / lifecycle / reporting / calendar redesign  
- VERIFY-02 G8 cross-surface integration family (optional future)  
- Accessibility / visual polish / component tests / mock-data tests  

---

*Maintainers: update trackers after G0 and each G-family classification. Do not execute G0 until harness implements rev 4 artifacts (`route_authority_map.json` extended fields, `control_plane_circularity.json`, `projection_resolution_order.json`) and checkpoints G-CYCLE / G-RESOLVE. Do not start G1 until G0 is `VERIFIED_OPERATIONALLY` or signed `WATCHLIST` with explicit G1 waiver.*
