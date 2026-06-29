"""Deterministic hashing for Graph Service envelopes (audit reproducibility)."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def envelope_hash(envelope: Dict[str, Any]) -> str:
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
