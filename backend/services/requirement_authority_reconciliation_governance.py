"""
Governance for REQUIREMENT-RECONCILIATION-AUTHORITY-01.

Aligns persisted Mongo requirement rows with the alias-family authority established in
RAOD-01 / ``requirement_client_runtime_surface`` — archive superseded slugs, never delete.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.compliance_rules_registry import portfolio_jurisdiction_label
from services.requirement_client_runtime_surface import (
    requirement_alias_family_catalog,
    requirement_row_alias_family_key,
    requirement_row_authority_dedupe_rank,
    requirement_row_is_registry_archived,
)
from services.requirement_code_registry import normalize_requirement_code

PROGRAMME = "REQUIREMENT-RECONCILIATION-AUTHORITY-01"
ARCHIVE_SOURCE = PROGRAMME
RECONCILIATION_VERSION = "1"
ARCHIVE_REASON = "superseded_alias_duplicate"

# Tie-breaker after runtime dedupe rank: preferred catalog slug per alias family.
CANONICAL_SLUG_PREFERENCE_BY_FAMILY: Dict[str, List[str]] = {
    "wales_occupation_contract_alias_family": ["wales_occupation_contract", "occupation_contract"],
    "fire_detection_alias_family": [
        "fire_detection",
        "fire_alarm",
        "smoke_alarms",
        "co_alarms",
        "smoke_heat_alarms",
    ],
    "hmo_fire_risk_alias_family": ["hmo_fire_risk", "hmo_fire_risk_evidence"],
    "tenancy_deposit_alias_family": [
        "tenancy_deposit_protection",
        "deposit_pi",
        "deposit_prescribed_info",
    ],
    "right_to_rent_alias_family": ["right_to_rent", "right_to_rent_checks"],
}


def requirement_row_canonical_code(row: Dict[str, Any]) -> str:
    raw = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw)
    if canon:
        return canon
    return raw.lower()


def authority_reconciliation_record(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    meta = row.get("registry_metadata") if isinstance(row.get("registry_metadata"), dict) else {}
    rec = meta.get("authority_reconciliation")
    return rec if isinstance(rec, dict) else None


def is_authority_reconciled_superseded(row: Dict[str, Any]) -> bool:
    """Idempotency: row already superseded by this programme."""
    if requirement_row_is_registry_archived(row):
        rec = authority_reconciliation_record(row)
        if rec and rec.get("archive_source") == ARCHIVE_SOURCE and rec.get("canonical_requirement_id"):
            return True
    return False


def is_active_for_alias_reconciliation(row: Dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    if is_authority_reconciled_superseded(row):
        return False
    if requirement_row_is_registry_archived(row):
        return False
    app = str(row.get("applicability") or "").upper()
    if app == "NOT_REQUIRED":
        return False
    return bool(requirement_row_alias_family_key(row))


def jurisdiction_fit_score(
    row: Dict[str, Any],
    *,
    alias_family: str,
    property_doc: Optional[Dict[str, Any]],
    client_doc: Optional[Dict[str, Any]],
) -> int:
    """Penalize catalog slugs on wrong jurisdiction before archive (aligns with runtime leak gates)."""
    if alias_family != "wales_occupation_contract_alias_family" or property_doc is None:
        return 0

    jur = str(portfolio_jurisdiction_label(property_doc, client_doc or "")).strip().lower()
    code = requirement_row_canonical_code(row)
    if jur != "wales" and code == "wales_occupation_contract":
        return -10
    if jur == "wales" and code == "occupation_contract":
        return -1
    return 0


def slug_preference_score(
    row: Dict[str, Any],
    *,
    alias_family: str,
    property_doc: Optional[Dict[str, Any]],
    client_doc: Optional[Dict[str, Any]],
) -> int:
    prefs = list(CANONICAL_SLUG_PREFERENCE_BY_FAMILY.get(alias_family) or [])
    if alias_family == "wales_occupation_contract_alias_family":
        jur = ""
        if property_doc is not None:
            jur = portfolio_jurisdiction_label(property_doc, client_doc or {})
        if str(jur).strip().lower() != "wales":
            prefs = ["occupation_contract", "wales_occupation_contract"]
    code = requirement_row_canonical_code(row)
    if code in prefs:
        return len(prefs) - prefs.index(code)
    return 0


def select_canonical_requirement_row(
    rows: List[Dict[str, Any]],
    *,
    alias_family: str,
    property_doc: Optional[Dict[str, Any]] = None,
    client_doc: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    active = [r for r in rows if is_active_for_alias_reconciliation(r)]
    if not active:
        return None
    if len(active) == 1:
        return active[0]

    def sort_key(r: Dict[str, Any]) -> Tuple[int, int, Any, int, int, str]:
        pub, ev, updated = requirement_row_authority_dedupe_rank(r)
        pref = slug_preference_score(
            r, alias_family=alias_family, property_doc=property_doc, client_doc=client_doc
        )
        jur_fit = jurisdiction_fit_score(
            r, alias_family=alias_family, property_doc=property_doc, client_doc=client_doc
        )
        rid = str(r.get("requirement_id") or "")
        return (pub, ev, updated, pref, jur_fit, rid)

    ordered = sorted(active, key=sort_key, reverse=True)
    return ordered[0]


def build_supersede_registry_metadata(
    row: Dict[str, Any],
    *,
    canonical_row: Dict[str, Any],
    alias_family: str,
    reconciled_at: str,
    reconciled_by: str,
) -> Dict[str, Any]:
    meta = dict(row.get("registry_metadata") or {}) if isinstance(row.get("registry_metadata"), dict) else {}
    life = dict(meta.get("lifecycle") or {}) if isinstance(meta.get("lifecycle"), dict) else {}
    previous_lifecycle = (
        life.get("status")
        or meta.get("lifecycle_status")
        or row.get("client_lifecycle_state")
        or row.get("status")
    )
    canonical_id = str(canonical_row.get("requirement_id") or "")
    canonical_code = requirement_row_canonical_code(canonical_row)
    meta["lifecycle"] = {**life, "status": "superseded"}
    meta["lifecycle_status"] = "superseded"
    meta["authority_reconciliation"] = {
        "archive_reason": ARCHIVE_REASON,
        "archive_source": ARCHIVE_SOURCE,
        "canonical_requirement_id": canonical_id,
        "canonical_requirement_code": canonical_code,
        "alias_family": alias_family,
        "reconciled_at": reconciled_at,
        "reconciled_by": reconciled_by,
        "previous_lifecycle": previous_lifecycle,
        "new_lifecycle": "superseded",
        "reconciliation_version": RECONCILIATION_VERSION,
    }
    return meta


def duplicate_group_key(row: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
    fam = requirement_row_alias_family_key(row)
    if not fam:
        return None
    cid = str(row.get("client_id") or "").strip()
    pid = str(row.get("property_id") or "").strip()
    if not cid or not pid:
        return None
    return (cid, pid, fam)


def all_alias_families() -> List[str]:
    return sorted(set(requirement_alias_family_catalog().values()))
