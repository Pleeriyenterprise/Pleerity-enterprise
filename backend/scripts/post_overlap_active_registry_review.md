# Active published registry (post-overlap correction, no coverage merge)

**Source:** Loaded active published entries from Mongo.
**Counts:** previous keys=14, after overlap removal=14, final keys=14 (no coverage merge).

## Grouped by jurisdiction (registry keys)

### ENGLAND

| registry_key |
|---|
| `EICR|DEFAULT` |
| `EPC|DEFAULT` |
| `GAS_SAFETY|DEFAULT` |
| `HMO_FIRE_RISK|DEFAULT` |
| `HMO_LICENSING|DEFAULT` |
| `LEGIONELLA|DEFAULT` |
| `PAT_TESTING|DEFAULT` |
| `SMOKE_HEAT_ALARMS|DEFAULT` |
| `TENANCY_DEPOSIT_PROTECTION|ENGLAND` |

### WALES

| registry_key |
|---|
| `EICR|DEFAULT` |
| `EPC|DEFAULT` |
| `FITNESS_FOR_HUMAN_HABITATION|WALES` |
| `GAS_SAFETY|DEFAULT` |
| `HMO_LICENSING|DEFAULT` |
| `LEGIONELLA|DEFAULT` |
| `PAT_TESTING|DEFAULT` |
| `RENT_SMART_WALES_REGISTRATION|WALES` |
| `SMOKE_HEAT_ALARMS|DEFAULT` |

### SCOTLAND

| registry_key |
|---|
| `EICR|DEFAULT` |
| `EPC|DEFAULT` |
| `GAS_SAFETY|DEFAULT` |
| `HMO_LICENSING|DEFAULT` |
| `LEAD_TESTING|SCOTLAND` |
| `LEGIONELLA|DEFAULT` |
| `PAT_TESTING|DEFAULT` |
| `REPAIRING_STANDARD|SCOTLAND` |
| `SMOKE_HEAT_ALARMS|DEFAULT` |
| `TENANCY_DEPOSIT_PROTECTION|SCOTLAND` |

### NORTHERN_IRELAND

| registry_key |
|---|
| `EICR|DEFAULT` |
| `EPC|DEFAULT` |
| `GAS_SAFETY|DEFAULT` |
| `HMO_FIRE_RISK|DEFAULT` |
| `LEGIONELLA|DEFAULT` |
| `PAT_TESTING|DEFAULT` |
| `SMOKE_HEAT_ALARMS|DEFAULT` |

## All entries (detail)

| registry_key | canonical | display_name | jurisdictions | conditions | repair | client_visible | action_mode | CTA | links | why? | mapped types (count) |
|---:|---|---|---|---|---|:---:|:---|:---|---:|---:|---:|
| `EICR|DEFAULT` | EICR | Electrical Installation Condition Report | ENGLAND, SCOTLAND, WALES, NORTHERN_IRELAND | Applies when all of the following are true:
  • Tenancy active equals  | n/a | True | upload_document | Upload valid EICR certificate | 3 | yes | 1 |
| `EPC|DEFAULT` | EPC | Energy Performance Certificate | ENGLAND, SCOTLAND, WALES, NORTHERN_IRELAND | Applies when all of the following are true:
  • Tenancy active equals  | n/a | True | upload_document | Upload valid EPC document | 4 | yes | 1 |
| `FITNESS_FOR_HUMAN_HABITATION|WALES` | FITNESS_FOR_HUMAN_HABITATION | Fitness for Human Habitation | WALES | Applies when all of the following are true:
  • Tenancy active equals  | n/a | True | view_guidance | Review habitability obligations | 2 | yes | 1 |
| `GAS_SAFETY|DEFAULT` | GAS_SAFETY | Gas Safety Certificate | ENGLAND, SCOTLAND, WALES, NORTHERN_IRELAND | Applies when all of the following are true:
  • Has gas supply is Yes | n/a | True | upload_document | Upload valid gas safety certificate | 2 | yes | 1 |
| `HMO_FIRE_RISK|DEFAULT` | HMO_FIRE_RISK | Fire Risk Assessment | ENGLAND, NORTHERN_IRELAND | Applies when any of the following are true:
  • Is HMO is Yes
  • Has  | n/a | True | upload_document | Upload fire risk assessment report | 3 | yes | 2 |
| `HMO_LICENSING|DEFAULT` | HMO_LICENSING | HMO Licence | ENGLAND, SCOTLAND, WALES | Applies when all of the following are true:
  • Is HMO equals Yes | n/a | True | upload_document | Upload valid HMO licence | 2 | yes | 3 |
| `LEAD_TESTING|SCOTLAND` | LEAD_TESTING | Lead Testing | SCOTLAND | Applies when all of the following are true:
  • Building age (years) i | n/a | True | upload_document | Upload lead hazard assessment report | 2 | yes | 1 |
| `LEGIONELLA|DEFAULT` | LEGIONELLA | Legionella Risk Assessment | ENGLAND, SCOTLAND, WALES, NORTHERN_IRELAND | Applies when all of the following are true:
  • Tenancy active equals  | n/a | True | upload_document | Upload Legionella risk assessment report | 2 | yes | 1 |
| `PAT_TESTING|DEFAULT` | PAT_TESTING | Portable Appliance Safety Testing | ENGLAND, SCOTLAND, WALES, NORTHERN_IRELAND | Applies when all of the following are true:
  • Furnished equals Yes
  | n/a | True | upload_document | Upload portable appliance testing report | 2 | yes | 2 |
| `RENT_SMART_WALES_REGISTRATION|WALES` | RENT_SMART_WALES_REGISTRATION | Rent Smart Wales Registration | WALES | Applies when all of the following are true:
  • Tenancy active equals  | n/a | True | upload_document | Upload Rent Smart Wales registration evidence | 2 | yes | 2 |
| `REPAIRING_STANDARD|SCOTLAND` | REPAIRING_STANDARD | Repairing Standard Property Review (Scotland) | SCOTLAND | Applies when all of the following are true:
  • Tenancy active is Yes | n/a | True | upload_document | Complete property review | 1 | yes | 1 |
| `SMOKE_HEAT_ALARMS|DEFAULT` | SMOKE_HEAT_ALARMS | Smoke, Heat & CO Alarm Compliance | ENGLAND, WALES, SCOTLAND, NORTHERN_IRELAND | Applies to all properties (no rules). | n/a | True | upload_document | Upload smoke, heat or CO alarm evidence | 4 | yes | 5 |
| `TENANCY_DEPOSIT_PROTECTION|ENGLAND` | TENANCY_DEPOSIT_PROTECTION | Tenancy Deposit Protection | ENGLAND | Applies when all of the following are true:
  • Deposit taken equals Y | n/a | True | upload_document | Upload tenancy deposit protection evidence | 3 | yes | 2 |
| `TENANCY_DEPOSIT_PROTECTION|SCOTLAND` | TENANCY_DEPOSIT_PROTECTION | Tenancy Deposit Protection | SCOTLAND | Applies to all properties (no rules). | n/a | True | upload_document | — | 0 | no | 2 |

## Duplication / overlap review (automated index)

```json
{
  "TENANCY_DEPOSIT_PROTECTION_model": {
    "note": "England and Scotland scoped rows only; no UK-wide DEFAULT; Wales/NI have no published deposit row unless added later.",
    "deposit_pi_keys": [
      "TENANCY_DEPOSIT_PROTECTION|ENGLAND",
      "TENANCY_DEPOSIT_PROTECTION|SCOTLAND"
    ],
    "tenancy_deposit_protection_keys": [
      "TENANCY_DEPOSIT_PROTECTION|ENGLAND",
      "TENANCY_DEPOSIT_PROTECTION|SCOTLAND"
    ]
  },
  "LANDLORD_REGISTRATION_DEFAULT_vs_LANDLORD_REGISTRATION_NI": {
    "LANDLORD_REGISTRATION|DEFAULT": null,
    "LANDLORD_REGISTRATION_NI|DEFAULT": null,
    "scotland_slug_keys": [],
    "ni_slug_keys": [],
    "generic_landlord_registration_slug_keys": []
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
    "fire_risk_assessment": [],
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
    "how_to_rent": [],
    "tenancy_agreement": [],
    "occupation_contract": [],
    "wales_occupation_contract": []
  },
  "right_to_rent_family": {
    "right_to_rent": {
      "registry_keys": [],
      "count": 0
    },
    "right_to_rent_checks": {
      "registry_keys": [],
      "count": 0
    }
  }
}
```