"""Registry coverage validation for lifecycle semantics — non-blocking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.lifecycle_semantics_fallback_map import (
    all_documented_canonical_codes,
    all_documented_storage_slugs,
    fallback_entry_for_canonical_code,
    fallback_entry_for_storage_slug,
)
from services.lifecycle_semantics_registry_loader import extract_lifecycle_from_registry_row
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_types import LIFECYCLE_SEMANTICS_VALUES


@dataclass
class LifecycleClassificationReport:
    total: int = 0
    resolved: int = 0
    unresolved: List[str] = field(default_factory=list)
    conflicting: List[Dict[str, Any]] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    by_semantics: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "resolved": self.resolved,
            "unresolved": list(self.unresolved),
            "conflicting": list(self.conflicting),
            "unsupported": list(self.unsupported),
            "by_semantics": dict(self.by_semantics),
            "unresolved_rate": (len(self.unresolved) / self.total) if self.total else 0.0,
        }


def validate_registry_row_lifecycle_block(registry_row: Dict[str, Any]) -> List[str]:
    """Validate optional lifecycle block on a registry draft. Non-blocking errors."""
    errs: List[str] = []
    block = registry_row.get("lifecycle")
    if block is None:
        return errs
    if not isinstance(block, dict):
        return ["lifecycle must be an object when present"]
    semantics = str(block.get("semantics") or "").strip().upper()
    if not semantics:
        errs.append("lifecycle.semantics is required when lifecycle block present")
    elif semantics not in LIFECYCLE_SEMANTICS_VALUES:
        errs.append(f"unsupported lifecycle.semantics: {semantics}")
    fc = block.get("field_contract")
    if fc is not None and not isinstance(fc, dict):
        errs.append("lifecycle.field_contract must be an object")
    return errs


def build_classification_report_for_codes(
    codes: List[str],
    *,
    use_registry_rows: Optional[Dict[str, Dict[str, Any]]] = None,
) -> LifecycleClassificationReport:
    report = LifecycleClassificationReport()
    registry_rows = use_registry_rows or {}
    for code in codes:
        report.total += 1
        slug = code.strip().lower()
        canonical = code.strip().upper()
        stub_req = {"requirement_code": slug, "canonical_code": canonical}
        row = registry_rows.get(canonical) or registry_rows.get(slug)
        resolved = resolve_lifecycle_semantics(stub_req, registry_row=row)
        sem = resolved.lifecycle_semantics
        report.by_semantics[sem] = report.by_semantics.get(sem, 0) + 1
        if resolved.resolution_source == "default" or "unresolved_used_default" in resolved.validation_issues:
            report.unresolved.append(canonical or slug)
        else:
            report.resolved += 1
        if resolved.validation_issues:
            conflicting = [i for i in resolved.validation_issues if i.startswith("conflict_")]
            if conflicting:
                report.conflicting.append(
                    {
                        "code": canonical or slug,
                        "issues": conflicting,
                        "semantics": sem,
                    }
                )
        if sem not in LIFECYCLE_SEMANTICS_VALUES:
            report.unsupported.append(canonical or slug)
    return report


def documented_fallback_coverage_report() -> Dict[str, Any]:
    """Coverage of documented fallback map entries."""
    canonical = sorted(all_documented_canonical_codes())
    slugs = sorted(all_documented_storage_slugs())
    missing_canonical_resolution = [
        c for c in canonical if not fallback_entry_for_canonical_code(c)
    ]
    missing_slug_resolution = [s for s in slugs if not fallback_entry_for_storage_slug(s)]
    registry_only = [
        c
        for c in canonical
        if extract_lifecycle_from_registry_row({"lifecycle": {"semantics": "EXPIRY_BASED", "field_contract": {}}})
    ]
    return {
        "documented_canonical_codes": len(canonical),
        "documented_storage_slugs": len(slugs),
        "missing_canonical_resolution": missing_canonical_resolution,
        "missing_slug_resolution": missing_slug_resolution,
        "registry_loader_smoke": bool(registry_only),
    }
