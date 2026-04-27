"""
DEPRECATED compatibility wrapper.

This module has been superseded by:
`services.compliance_audit_evidence_pack_service`.

Removal guidance:
- Keep this wrapper only for temporary import compatibility.
- Update direct imports to `compliance_audit_evidence_pack_service`.
- Remove this module after all references are migrated.
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional

from services import compliance_audit_evidence_pack_service as _new

# Backward-compatible constants now delegated to the new authority.
GRIDFS_BUCKET = _new.GRIDFS_BUCKET
CONTRACT_VERSION = _new.CONTRACT_VERSION


def _warn() -> None:
    warnings.warn(
        "services.compliance_audit_pack_service is deprecated; use "
        "services.compliance_audit_evidence_pack_service instead.",
        DeprecationWarning,
        stacklevel=2,
    )


async def read_audit_pack_zip_bytes(gridfs_id: str) -> Optional[bytes]:
    _warn()
    return await _new.read_audit_pack_zip_bytes(gridfs_id)


async def build_compliance_audit_pack(
    *,
    client_id: str,
    property_id: str,
    initiated_by_user_id: str,
    initiated_by_role: Optional[str],
    purpose: str = "governed_audit_export",
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    _warn()
    return await _new.build_compliance_audit_pack(
        client_id=client_id,
        property_id=property_id,
        initiated_by_user_id=initiated_by_user_id,
        initiated_by_role=initiated_by_role,
        purpose=purpose,
        ip_address=ip_address,
    )


async def get_audit_pack_record(*, client_id: str, pack_id: str) -> Optional[Dict[str, Any]]:
    _warn()
    return await _new.get_audit_pack_record(client_id=client_id, pack_id=pack_id)


async def list_audit_packs_for_scope(*, client_id: str, property_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    _warn()
    return await _new.list_audit_packs_for_scope(client_id=client_id, property_id=property_id, limit=limit)
