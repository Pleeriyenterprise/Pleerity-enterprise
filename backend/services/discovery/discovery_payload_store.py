"""
Raw payload storage abstraction — Stage I.

Protocol + in-memory test implementation only. No S3/GridFS/production storage.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from services.discovery.discovery_hashing import validate_content_hash_hex

RAW_PAYLOAD_REFERENCE_MAX_LEN = 512

# Canonical reference formats (no PII — content_hash is SHA-256 hex).
PAYLOAD_URI_PATTERN = re.compile(
    r"^payload://discovery/[a-z][a-z0-9_]*/[A-Za-z0-9._-]+/[a-f0-9]{64}$"
)
PAYLOAD_REF_PATTERN = re.compile(
    r"^ref:discovery:[a-z][a-z0-9_]*:[A-Za-z0-9._-]+:[a-f0-9]{64}$"
)
# Legacy Stage G format retained for backward compatibility in validation only.
LEGACY_PAYLOAD_PATTERN = re.compile(
    r"^(payload://[A-Z][A-Za-z0-9._-]+|ref:(?!discovery:)[A-Za-z0-9._:-]{1,128})$"
)

EMAIL_IN_REFERENCE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class RawPayloadStoreError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def build_raw_payload_reference(
    *,
    provider: str,
    discovery_run_id: str,
    content_hash: str,
    style: str = "payload_uri",
) -> str:
    """
    Build a PII-free payload reference.

    style: ``payload_uri`` -> payload://discovery/{provider}/{run_id}/{hash}
           ``ref_token``   -> ref:discovery:{provider}:{run_id}:{hash}
    """
    hash_errors = validate_content_hash_hex(content_hash)
    if hash_errors:
        raise RawPayloadStoreError("INVALID_HASH", hash_errors[0])

    provider_id = str(provider).strip().lower()
    run_id = str(discovery_run_id).strip()
    ch = content_hash.strip().lower()

    if style == "ref_token":
        ref = f"ref:discovery:{provider_id}:{run_id}:{ch}"
    else:
        ref = f"payload://discovery/{provider_id}/{run_id}/{ch}"

    if len(ref) > RAW_PAYLOAD_REFERENCE_MAX_LEN:
        raise RawPayloadStoreError("REFERENCE_TOO_LONG", "raw_payload_reference too long")
    if EMAIL_IN_REFERENCE.search(ref):
        raise RawPayloadStoreError("PII_IN_REFERENCE", "reference must not contain email")
    return ref


def validate_raw_payload_reference(reference: Optional[str]) -> list[str]:
    """Validate reference format, length, and absence of PII."""
    errors: list[str] = []
    if reference is None or not str(reference).strip():
        return errors

    ref = str(reference).strip()
    if len(ref) > RAW_PAYLOAD_REFERENCE_MAX_LEN:
        errors.append("raw_payload_reference exceeds maximum length")
    if EMAIL_IN_REFERENCE.search(ref):
        errors.append("raw_payload_reference must not contain email")
    if not (
        PAYLOAD_URI_PATTERN.match(ref)
        or PAYLOAD_REF_PATTERN.match(ref)
        or LEGACY_PAYLOAD_PATTERN.match(ref)
    ):
        errors.append(
            "raw_payload_reference must match payload://discovery/... or ref:discovery:... format"
        )
    return errors


@runtime_checkable
class RawPayloadStore(Protocol):
    """Store opaque provider payloads outside discovery_prospects documents."""

    def put(self, payload: Any, metadata: Dict[str, Any]) -> str:
        """Persist payload; return raw_payload_reference (not inline on prospect)."""
        ...

    def get(self, raw_payload_reference: str) -> Any:
        ...

    def delete(self, raw_payload_reference: str) -> None:
        ...

    def validate_reference(self, raw_payload_reference: str) -> list[str]:
        ...


class InMemoryRawPayloadStore:
    """Test-only in-memory payload store. Not for production."""

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def put(self, payload: Any, metadata: Dict[str, Any]) -> str:
        provider = metadata.get("provider")
        discovery_run_id = metadata.get("discovery_run_id")
        content_hash = metadata.get("content_hash")
        if not provider or not discovery_run_id or not content_hash:
            raise RawPayloadStoreError(
                "METADATA_REQUIRED",
                "metadata must include provider, discovery_run_id, content_hash",
            )
        ref = build_raw_payload_reference(
            provider=str(provider),
            discovery_run_id=str(discovery_run_id),
            content_hash=str(content_hash),
            style=metadata.get("reference_style", "payload_uri"),
        )
        ref_errors = self.validate_reference(ref)
        if ref_errors:
            raise RawPayloadStoreError("INVALID_REFERENCE", "; ".join(ref_errors))
        self._store[ref] = payload
        return ref

    def get(self, raw_payload_reference: str) -> Any:
        ref_errors = self.validate_reference(raw_payload_reference)
        if ref_errors:
            raise RawPayloadStoreError("INVALID_REFERENCE", "; ".join(ref_errors))
        if raw_payload_reference not in self._store:
            raise RawPayloadStoreError("NOT_FOUND", "payload not found")
        return self._store[raw_payload_reference]

    def delete(self, raw_payload_reference: str) -> None:
        ref_errors = self.validate_reference(raw_payload_reference)
        if ref_errors:
            raise RawPayloadStoreError("INVALID_REFERENCE", "; ".join(ref_errors))
        self._store.pop(raw_payload_reference, None)

    def validate_reference(self, raw_payload_reference: str) -> list[str]:
        return validate_raw_payload_reference(raw_payload_reference)
