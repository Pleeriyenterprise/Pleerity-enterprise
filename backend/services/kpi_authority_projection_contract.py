"""
KPI-authoritative projection contract (L-002 guardrail).

Enforces ``docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md``: modules that compute or
shape **client-visible compliance KPIs** from requirement rows must either:

* **projection_chain** — reference both ``filter_requirement_rows_for_client_runtime_surfaces`` and
  ``project_requirement_row_client_runtime`` in source (the canonical row-shaping path), or
* **scorer_delegate** — derive counts only via ``calculate_compliance_score`` and must not touch
  ``db.requirements`` / ``requirements.find`` directly.

This is a **regression net** only: extend the registry when new KPI surfaces are added.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Tuple

BackendRoot = Path

BACKEND_ROOT: BackendRoot = Path(__file__).resolve().parent.parent

ContractKind = Literal["projection_chain", "scorer_delegate_no_raw_requirements"]

# (relative path from backend/, contract kind)
KPI_AUTHORITY_MODULE_CONTRACTS: Tuple[Tuple[str, ContractKind], ...] = (
    ("routes/client.py", "projection_chain"),
    ("services/compliance_score.py", "projection_chain"),
    ("routes/portfolio.py", "projection_chain"),
    ("routes/properties.py", "projection_chain"),
    ("services/command_center_service.py", "scorer_delegate_no_raw_requirements"),
    ("services/reporting_service.py", "projection_chain"),
    ("services/professional_reports.py", "projection_chain"),
    ("services/monthly_digest_assembly_service.py", "projection_chain"),
    ("services/catalog_compliance.py", "projection_chain"),
    ("services/client_value_insights_service.py", "scorer_delegate_no_raw_requirements"),
)


def _read_module(rel_path: str) -> str:
    path = BACKEND_ROOT / rel_path
    if not path.is_file():
        raise FileNotFoundError(f"kpi_authority_projection_contract: missing {rel_path}")
    return path.read_text(encoding="utf-8", errors="replace")


def assert_kpi_authority_projection_contracts() -> None:
    """Raise AssertionError if any registered module violates its contract."""
    for rel, kind in KPI_AUTHORITY_MODULE_CONTRACTS:
        text = _read_module(rel)
        if kind == "projection_chain":
            if "filter_requirement_rows_for_client_runtime_surfaces" not in text:
                raise AssertionError(
                    f"{rel}: KPI projection_chain requires filter_requirement_rows_for_client_runtime_surfaces "
                    "(see COMPLIANCE_CLIENT_STATUS_AUTHORITY.md)"
                )
            if "project_requirement_row_client_runtime" not in text:
                raise AssertionError(
                    f"{rel}: KPI projection_chain requires project_requirement_row_client_runtime "
                    "(see COMPLIANCE_CLIENT_STATUS_AUTHORITY.md)"
                )
        else:
            if "calculate_compliance_score" not in text:
                raise AssertionError(
                    f"{rel}: scorer_delegate_no_raw_requirements must reference calculate_compliance_score"
                )
            if "requirements.find" in text or "db.requirements" in text:
                raise AssertionError(
                    f"{rel}: scorer_delegate_no_raw_requirements must not query requirements collection directly"
                )
