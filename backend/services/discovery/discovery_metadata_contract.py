"""
Validation against docs/contracts/DISCOVERY_SOURCE_METADATA_V1.json

Stage B: contract validation only — no import workflow.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_CONTRACT_RELATIVE = Path("docs") / "contracts" / "DISCOVERY_SOURCE_METADATA_V1.json"


def _repo_root() -> Path:
    # backend/services/discovery/discovery_metadata_contract.py -> repo root
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def load_discovery_source_metadata_schema() -> Dict[str, Any]:
    path = _repo_root() / _CONTRACT_RELATIVE
    if not path.is_file():
        raise FileNotFoundError(f"Discovery metadata contract not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def get_discovery_metadata_validator() -> Draft202012Validator:
    schema = load_discovery_source_metadata_schema()
    return Draft202012Validator(schema)


def validate_discovery_source_metadata(
    payload: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Validate lead-side source_metadata.discovery payload.
    Returns (ok, error_messages).
    """
    validator = get_discovery_metadata_validator()
    errors: List[str] = []
    for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{path}: {err.message}")
    return (len(errors) == 0, errors)


def example_valid_discovery_metadata() -> Dict[str, Any]:
    """Example from contract — used by tests."""
    schema = load_discovery_source_metadata_schema()
    examples = schema.get("examples") or []
    if not examples:
        raise ValueError("Contract has no examples")
    return examples[0]
