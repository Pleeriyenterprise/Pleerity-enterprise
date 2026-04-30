# Published registry: overlap plus coverage-merge preview

**Source:** Loaded active published entries from Mongo.
**Counts:** previous keys=14, after overlap removal=14, final keys=23 (overlap removal + coverage merge preview); coverage-patched keys=19.

## Grouped by jurisdiction (registry keys)

### ENGLAND

| registry_key |
|---|
| `EICR|DEFAULT` |
| `EPC|DEFAULT` |
| `FIRE_RISK_ASSESSMENT|DEFAULT` |
| `GAS_SAFETY|DEFAULT` |
| `HMO_FIRE_RISK|DEFAULT` |
| `HMO_LICENSING|DEFAULT` |
| `HOW_TO_RENT|DEFAULT` |
| `LEGIONELLA|DEFAULT` |
| `PAT_TESTING|DEFAULT` |
| `RIGHT_TO_RENT|DEFAULT` |
| `SMOKE_HEAT_ALARMS|DEFAULT` |
| `TENANCY_AGREEMENT|DEFAULT` |
| `TENANCY_DEPOSIT_PROTECTION|ENGLAND` |

### WALES

| registry_key |
|---|
| `EICR|DEFAULT` |
| `EPC|DEFAULT` |
| `FIRE_RISK_ASSESSMENT|DEFAULT` |
| `FITNESS_FOR_HUMAN_HABITATION|WALES` |
| `GAS_SAFETY|DEFAULT` |
| `HMO_FIRE_RISK|DEFAULT` |
| `HMO_LICENSING|DEFAULT` |
| `LEGIONELLA|DEFAULT` |
| `OCCUPATION_CONTRACT|DEFAULT` |
| `PAT_TESTING|DEFAULT` |
| `RENT_SMART_WALES_REGISTRATION|WALES` |
| `SMOKE_HEAT_ALARMS|DEFAULT` |
| `TENANCY_AGREEMENT|DEFAULT` |
| `TENANCY_DEPOSIT_PROTECTION|WALES` |

### SCOTLAND

| registry_key |
|---|
| `EICR|DEFAULT` |
| `EPC|DEFAULT` |
| `FIRE_RISK_ASSESSMENT|DEFAULT` |
| `GAS_SAFETY|DEFAULT` |
| `HMO_FIRE_RISK|DEFAULT` |
| `HMO_LICENSING|DEFAULT` |
| `LANDLORD_REGISTRATION|DEFAULT` |
| `LEAD_TESTING|SCOTLAND` |
| `LEGIONELLA|DEFAULT` |
| `PAT_TESTING|DEFAULT` |
| `REPAIRING_STANDARD|SCOTLAND` |
| `SMOKE_HEAT_ALARMS|DEFAULT` |
| `TENANCY_AGREEMENT|DEFAULT` |
| `TENANCY_DEPOSIT_PROTECTION|SCOTLAND` |

### NORTHERN_IRELAND

| registry_key |
|---|
| `EICR|DEFAULT` |
| `EPC|DEFAULT` |
| `FIRE_RISK_ASSESSMENT|DEFAULT` |
| `GAS_SAFETY|DEFAULT` |
| `HMO_FIRE_RISK|DEFAULT` |
| `HMO_LICENSING|DEFAULT` |
| `LANDLORD_REGISTRATION_NI|DEFAULT` |
| `LEGIONELLA|DEFAULT` |
| `PAT_TESTING|DEFAULT` |
| `SMOKE_HEAT_ALARMS|DEFAULT` |
| `TENANCY_AGREEMENT|DEFAULT` |
| `TENANCY_DEPOSIT_PROTECTION|NORTHERN_IRELAND` |

## All entries (detail)

| registry_key | canonical | display_name | jurisdictions | conditions | repair | client_visible | action_mode | CTA | links | why? | mapped types (count) |
|---:|---|---|---|---|---|:---:|:---|:---|---:|---:|---:|
| `EICR|DEFAULT` | EICR | Electrical Installation Condition Report (EICR) | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies to all properties (no rules). | updated | True | upload_document | Upload valid EICR certificate | 3 | yes | 1 |
| `EPC|DEFAULT` | EPC | Energy Performance Certificate (EPC) | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies to all properties (no rules). | updated | True | upload_document | Upload valid EPC document | 4 | yes | 1 |
| `FIRE_RISK_ASSESSMENT|DEFAULT` | FIRE_RISK_ASSESSMENT | Fire risk assessment (FRA) — suitable & sufficient | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies when all of the following are true:
  • Is HMO is Yes | added | True | upload_document | — | 3 | yes | 1 |
| `FITNESS_FOR_HUMAN_HABITATION|WALES` | FITNESS_FOR_HUMAN_HABITATION | Fitness for Human Habitation | WALES | Applies when all of the following are true:
  • Tenancy active equals  | n/a | True | view_guidance | Review habitability obligations | 2 | yes | 1 |
| `GAS_SAFETY|DEFAULT` | GAS_SAFETY | Gas safety certificate | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies to all properties (no rules). | updated | True | upload_document | Upload valid gas safety certificate | 2 | yes | 1 |
| `HMO_FIRE_RISK|DEFAULT` | HMO_FIRE_RISK | HMO fire safety management evidence (log book, tests, compar | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies when all of the following are true:
  • Is HMO is Yes | updated | True | upload_document | Upload fire risk assessment report | 3 | yes | 2 |
| `HMO_LICENSING|DEFAULT` | HMO_LICENSING | HMO / selective / additional licensing (local authority) | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies when all of the following are true:
  • Is HMO is Yes | updated | True | upload_document | Upload valid HMO licence | 2 | yes | 3 |
| `HOW_TO_RENT|DEFAULT` | HOW_TO_RENT | How to rent guide (England) | ENGLAND | Applies to all properties (no rules). | added | True | upload_document | — | 0 | yes | 1 |
| `LANDLORD_REGISTRATION_NI|DEFAULT` | LANDLORD_REGISTRATION_NI | Northern Ireland landlord registration | NORTHERN_IRELAND | Applies to all properties (no rules). | added | True | upload_document | — | 1 | yes | 1 |
| `LANDLORD_REGISTRATION|DEFAULT` | LANDLORD_REGISTRATION | Scottish landlord registration | SCOTLAND | Applies to all properties (no rules). | added | True | upload_document | — | 2 | yes | 2 |
| `LEAD_TESTING|SCOTLAND` | LEAD_TESTING | Lead Testing | SCOTLAND | Applies when all of the following are true:
  • Building age (years) i | n/a | True | upload_document | Upload lead hazard assessment report | 2 | yes | 1 |
| `LEGIONELLA|DEFAULT` | LEGIONELLA | Legionella risk assessment | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies to all properties (no rules). | updated | True | arrange_job | Upload Legionella risk assessment report | 2 | yes | 1 |
| `OCCUPATION_CONTRACT|DEFAULT` | OCCUPATION_CONTRACT | Written occupation contract (Wales) | WALES | Applies to all properties (no rules). | added | True | upload_document | — | 1 | yes | 2 |
| `PAT_TESTING|DEFAULT` | PAT_TESTING | Portable appliance testing (PAT) | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies to all properties (no rules). | updated | True | upload_document | Upload portable appliance testing report | 2 | yes | 2 |
| `RENT_SMART_WALES_REGISTRATION|WALES` | RENT_SMART_WALES_REGISTRATION | Rent Smart Wales Registration | WALES | Applies when all of the following are true:
  • Tenancy active equals  | n/a | True | upload_document | Upload Rent Smart Wales registration evidence | 2 | yes | 2 |
| `REPAIRING_STANDARD|SCOTLAND` | REPAIRING_STANDARD | Repairing Standard Property Review (Scotland) | SCOTLAND | Applies when all of the following are true:
  • Tenancy active is Yes | n/a | True | upload_document | Complete property review | 1 | yes | 1 |
| `RIGHT_TO_RENT|DEFAULT` | RIGHT_TO_RENT | Right to rent compliance | ENGLAND | Applies to all properties (no rules). | added | True | upload_document | — | 0 | yes | 2 |
| `SMOKE_HEAT_ALARMS|DEFAULT` | SMOKE_HEAT_ALARMS | Smoke, Heat & CO Alarm Compliance | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies to all properties (no rules). | updated | True | upload_document | Upload smoke, heat or CO alarm evidence | 4 | yes | 5 |
| `TENANCY_AGREEMENT|DEFAULT` | TENANCY_AGREEMENT | Tenancy agreement | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies to all properties (no rules). | added | True | upload_document | — | 0 | yes | 1 |
| `TENANCY_DEPOSIT_PROTECTION|ENGLAND` | TENANCY_DEPOSIT_PROTECTION | Tenancy deposit protection (England) | ENGLAND | Applies when all of the following are true:
  • Deposit taken is Yes
  | updated | True | upload_document | Upload tenancy deposit protection evidence | 3 | yes | 2 |
| `TENANCY_DEPOSIT_PROTECTION|NORTHERN_IRELAND` | TENANCY_DEPOSIT_PROTECTION | Tenancy deposit protection (Northern Ireland) | NORTHERN_IRELAND | Applies when all of the following are true:
  • Deposit taken is Yes
  | added | True | upload_document | Upload tenancy deposit protection evidence | 0 | yes | 2 |
| `TENANCY_DEPOSIT_PROTECTION|SCOTLAND` | TENANCY_DEPOSIT_PROTECTION | Tenancy deposit protection (Scotland) | SCOTLAND | Applies when all of the following are true:
  • Deposit taken is Yes
  | updated | True | upload_document | Upload tenancy deposit protection evidence | 0 | yes | 2 |
| `TENANCY_DEPOSIT_PROTECTION|WALES` | TENANCY_DEPOSIT_PROTECTION | Tenancy deposit protection (Wales) | WALES | Applies when all of the following are true:
  • Deposit taken is Yes
  | added | True | upload_document | Upload tenancy deposit protection evidence | 0 | yes | 2 |

## Duplication / overlap review (automated index)

```json
{
  "TENANCY_DEPOSIT_PROTECTION_model": {
    "note": "Four jurisdiction-scoped rows (England, Wales, Scotland, Northern Ireland); no UK-wide DEFAULT; each row gates on deposit_taken and tenancy_active.",
    "deposit_pi_keys": [
      "TENANCY_DEPOSIT_PROTECTION|ENGLAND",
      "TENANCY_DEPOSIT_PROTECTION|NORTHERN_IRELAND",
      "TENANCY_DEPOSIT_PROTECTION|SCOTLAND",
      "TENANCY_DEPOSIT_PROTECTION|WALES"
    ],
    "tenancy_deposit_protection_keys": [
      "TENANCY_DEPOSIT_PROTECTION|ENGLAND",
      "TENANCY_DEPOSIT_PROTECTION|NORTHERN_IRELAND",
      "TENANCY_DEPOSIT_PROTECTION|SCOTLAND",
      "TENANCY_DEPOSIT_PROTECTION|WALES"
    ]
  },
  "LANDLORD_REGISTRATION_DEFAULT_vs_LANDLORD_REGISTRATION_NI": {
    "LANDLORD_REGISTRATION|DEFAULT": {
      "registry_key": "LANDLORD_REGISTRATION|DEFAULT",
      "canonical_code": "LANDLORD_REGISTRATION",
      "scope_key": "DEFAULT",
      "display_name": "Scottish landlord registration",
      "display_jurisdictions": [
        "SCOTLAND"
      ],
      "property_conditions_summary": "Applies to all properties (no rules).",
      "coverage_repair": "patched",
      "coverage_repair_action": "added",
      "client_surface_visible": true,
      "primary_action_mode": "upload_document",
      "cta_label_override": null,
      "action_links_count": 2,
      "why_it_matters_present": true,
      "planner_requirement_types_mapped": [
        "landlord_registration",
        "scotland_landlord_registration"
      ],
      "maps_legacy_materialised_rows": "Overlays Mongo requirements / plan rows whose requirement_type is in planner_requirement_types_mapped; does not rewrite legacy rows."
    },
    "LANDLORD_REGISTRATION_NI|DEFAULT": {
      "registry_key": "LANDLORD_REGISTRATION_NI|DEFAULT",
      "canonical_code": "LANDLORD_REGISTRATION_NI",
      "scope_key": "DEFAULT",
      "display_name": "Northern Ireland landlord registration",
      "display_jurisdictions": [
        "NORTHERN_IRELAND"
      ],
      "property_conditions_summary": "Applies to all properties (no rules).",
      "coverage_repair": "patched",
      "coverage_repair_action": "added",
      "client_surface_visible": true,
      "primary_action_mode": "upload_document",
      "cta_label_override": null,
      "action_links_count": 1,
      "why_it_matters_present": true,
      "planner_requirement_types_mapped": [
        "landlord_registration_ni"
      ],
      "maps_legacy_materialised_rows": "Overlays Mongo requirements / plan rows whose requirement_type is in planner_requirement_types_mapped; does not rewrite legacy rows."
    },
    "scotland_slug_keys": [
      "LANDLORD_REGISTRATION|DEFAULT"
    ],
    "ni_slug_keys": [
      "LANDLORD_REGISTRATION_NI|DEFAULT"
    ],
    "generic_landlord_registration_slug_keys": [
      "LANDLORD_REGISTRATION|DEFAULT"
    ]
  },
  "FIRE_DETECTION_vs_SMOKE_HEAT_partition": {
    "fire_alarm": {
      "registry_keys": [
        "SMOKE_HEAT_ALARMS|DEFAULT"
      ],
      "count": 1
    },
    "fire_detection": {
      "registry_keys": [
        "SMOKE_HEAT_ALARMS|DEFAULT"
      ],
      "count": 1
    },
    "smoke_alarms": {
      "registry_keys": [
        "SMOKE_HEAT_ALARMS|DEFAULT"
      ],
      "count": 1
    },
    "co_alarms": {
      "registry_keys": [
        "SMOKE_HEAT_ALARMS|DEFAULT"
      ],
      "count": 1
    },
    "smoke_heat_alarms": {
      "registry_keys": [
        "SMOKE_HEAT_ALARMS|DEFAULT"
      ],
      "count": 1
    }
  },
  "HMO_FIRE_vs_FRA_vs_HMO_LICENSING": {
    "hmo_fire_risk": [
      "HMO_FIRE_RISK|DEFAULT"
    ],
    "hmo_fire_risk_evidence": [
      "HMO_FIRE_RISK|DEFAULT"
    ],
    "fire_risk_assessment": [
      "FIRE_RISK_ASSESSMENT|DEFAULT"
    ],
    "hmo_license": [
      "HMO_LICENSING|DEFAULT"
    ],
    "property_licence": [
      "HMO_LICENSING|DEFAULT"
    ],
    "hmo_licensing": [
      "HMO_LICENSING|DEFAULT"
    ]
  },
  "tenancy_pack": {
    "how_to_rent": [
      "HOW_TO_RENT|DEFAULT"
    ],
    "tenancy_agreement": [
      "TENANCY_AGREEMENT|DEFAULT"
    ],
    "occupation_contract": [
      "OCCUPATION_CONTRACT|DEFAULT"
    ],
    "wales_occupation_contract": [
      "OCCUPATION_CONTRACT|DEFAULT"
    ]
  },
  "right_to_rent_family": {
    "right_to_rent": {
      "registry_keys": [
        "RIGHT_TO_RENT|DEFAULT"
      ],
      "count": 1
    },
    "right_to_rent_checks": {
      "registry_keys": [
        "RIGHT_TO_RENT|DEFAULT"
      ],
      "count": 1
    }
  }
}
```