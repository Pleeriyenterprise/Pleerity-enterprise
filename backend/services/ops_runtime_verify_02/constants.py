"""
Programme constants — no pilot IDs; families and authority ranks only.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Tuple

PROGRAMME_ID = "PRELAUNCH-OPS-RUNTIME-VERIFY-02"
PROGRAMME_REV = "rev_4"

# Canonical projection resolution order (rank 1 = highest authority)
PROJECTION_RESOLUTION_RANKS: Tuple[Tuple[int, str, str], ...] = (
    (1, "live", "ops_control_g2_command_centre"),
    (2, "attention_list", "ops_control_g1_today_page"),
    (3, "property_summary", "ops_control_g3_properties_page"),
    (4, "derived", "ops_control_g7_reports_page"),
    (5, "exported", "ops_control_g7_reports_page"),
)

DEFAULT_MAX_NAVIGATION_DEPTH = 5
DEFAULT_FRESHNESS_WINDOW_SECONDS = 60

VERIFY_01_FAMILY_SLUGS: Tuple[str, ...] = (
    "ops_runtime_01_issues",
    "ops_runtime_02_work_orders",
    "ops_runtime_03_contractor",
    "ops_runtime_04_risk_signals",
    "ops_runtime_05_client_sync",
    "ops_runtime_06_rent_ops",
    "ops_runtime_07_tenant_portal",
    "ops_runtime_08_cross_domain",
)


class Verify02Family(str, Enum):
    G0 = "ops_control_g0_programme_precheck"
    G1 = "ops_control_g1_today_page"
    G2 = "ops_control_g2_command_centre"
    G3 = "ops_control_g3_properties_page"
    G4 = "ops_control_g4_requirements_page"
    G5 = "ops_control_g5_documents_page"
    G6 = "ops_control_g6_calendar_page"
    G7 = "ops_control_g7_reports_page"


# Alias paths requested in programme scaffold (bundle family roots)
FAMILY_AUDIT_ALIASES: Dict[str, str] = {
    "ops_runtime_g1_today": Verify02Family.G1.value,
    "ops_runtime_g2_command_centre": Verify02Family.G2.value,
    "ops_runtime_g3_properties": Verify02Family.G3.value,
    "ops_runtime_g4_requirements": Verify02Family.G4.value,
    "ops_runtime_g5_documents": Verify02Family.G5.value,
    "ops_runtime_g6_calendar": Verify02Family.G6.value,
    "ops_runtime_g7_reports": Verify02Family.G7.value,
}

EXECUTION_STATUS_NOT_EXECUTED = "NOT_EXECUTED"
IMPLEMENTATION_STATUS_READY = "IMPLEMENTATION_READY"
