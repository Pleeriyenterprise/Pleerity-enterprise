"""
Phase 2 S1 — resolve extraction profile from requirement + registry row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.lifecycle_extraction_profiles import (
    ExtractionProfile,
    default_profile_for_semantics,
    get_extraction_profile,
    profile_for_storage_slug,
)
from services.lifecycle_semantics_registry_loader import extract_lifecycle_from_registry_row
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_types import LifecycleSemantics, ResolutionSource


@dataclass(frozen=True)
class ResolvedExtractionProfile:
    profile_id: str
    profile: ExtractionProfile
    lifecycle_semantics: LifecycleSemantics
    resolution_source: ResolutionSource
    requirement_code: Optional[str]


def _requirement_storage_slug(requirement: Dict[str, Any]) -> Optional[str]:
    for key in ("requirement_code", "requirement_type", "canonical_code"):
        raw = requirement.get(key)
        if raw:
            from services.requirement_code_registry import normalize_requirement_code

            normalized = normalize_requirement_code(raw)
            if normalized:
                return str(normalized).strip().lower()
            return str(raw).strip().lower()
    return None


def _profile_id_from_registry_row(registry_row: Optional[Dict[str, Any]]) -> Optional[str]:
    if not registry_row or not isinstance(registry_row, dict):
        return None
    lifecycle = registry_row.get("lifecycle")
    if not isinstance(lifecycle, dict):
        return None
    pid = lifecycle.get("extraction_profile_id")
    if pid and str(pid).strip():
        return str(pid).strip()
    return None


def resolve_extraction_profile(
    requirement: Dict[str, Any],
    *,
    registry_row: Optional[Dict[str, Any]] = None,
) -> ResolvedExtractionProfile:
    """
    Resolution order (Phase 2 design):
    1. registry.lifecycle.extraction_profile_id
    2. PROFILE_BY_STORAGE_SLUG[slug]
    3. PROFILE_BY_SEMANTICS[lifecycle_semantics]
    4. supporting_document_v1
    """
    resolved_lifecycle = resolve_lifecycle_semantics(requirement, registry_row=registry_row)
    semantics = resolved_lifecycle.lifecycle_semantics
    slug = _requirement_storage_slug(requirement)

    registry_pid = _profile_id_from_registry_row(registry_row)
    if registry_pid:
        profile = get_extraction_profile(registry_pid)
        if profile:
            return ResolvedExtractionProfile(
                profile_id=registry_pid,
                profile=profile,
                lifecycle_semantics=semantics,
                resolution_source="registry",
                requirement_code=slug,
            )

    slug_pid = profile_for_storage_slug(slug)
    if slug_pid:
        profile = get_extraction_profile(slug_pid)
        if profile:
            return ResolvedExtractionProfile(
                profile_id=slug_pid,
                profile=profile,
                lifecycle_semantics=semantics,
                resolution_source=resolved_lifecycle.resolution_source,
                requirement_code=slug,
            )

    default_pid = default_profile_for_semantics(semantics)
    profile = get_extraction_profile(default_pid)
    if not profile:
        fallback = get_extraction_profile("supporting_document_v1")
        assert fallback is not None
        return ResolvedExtractionProfile(
            profile_id="supporting_document_v1",
            profile=fallback,
            lifecycle_semantics=semantics,
            resolution_source="default",
            requirement_code=slug,
        )

    return ResolvedExtractionProfile(
        profile_id=default_pid,
        profile=profile,
        lifecycle_semantics=semantics,
        resolution_source=resolved_lifecycle.resolution_source,
        requirement_code=slug,
    )


def resolve_extraction_profile_from_slug(
    storage_slug: Optional[str],
    *,
    registry_row: Optional[Dict[str, Any]] = None,
) -> ResolvedExtractionProfile:
    """Resolve profile when only a document type / storage slug is known."""
    req: Dict[str, Any] = {}
    if storage_slug:
        req["requirement_code"] = storage_slug
    return resolve_extraction_profile(req, registry_row=registry_row)
