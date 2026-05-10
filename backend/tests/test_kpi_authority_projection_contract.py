"""L-002: KPI-authoritative modules must satisfy projection contract (COMPLIANCE_CLIENT_STATUS_AUTHORITY.md)."""

from __future__ import annotations

import pytest

from services.kpi_authority_projection_contract import assert_kpi_authority_projection_contracts


def test_kpi_authority_projection_contracts():
    assert_kpi_authority_projection_contracts()
