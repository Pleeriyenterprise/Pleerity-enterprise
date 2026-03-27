"""
Operational policy for contractor assignment. Recommendations are always produced; auto-assign is opt-in via env.
"""
import os
from typing import Any, Dict, List, Optional


def get_contractor_assignment_policy(client_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns real policy from environment (default: admin confirms, no auto-assign).
    CONTRACTOR_AUTO_ASSIGN_ENABLED=true|false
    CONTRACTOR_AUTO_ASSIGN_CATEGORIES=plumbing,electrical (comma-separated work order categories)

    Service area matching for eligibility remains prefix + exact postcode (see contractor_service); tune via
    contractor data (areas_served / coverage_area / registration_postcode), not dummy scores.
    """
    raw = (os.environ.get("CONTRACTOR_AUTO_ASSIGN_ENABLED") or "").strip().lower()
    enabled = raw in ("1", "true", "yes", "on")
    cats_raw = (os.environ.get("CONTRACTOR_AUTO_ASSIGN_CATEGORIES") or "").strip()
    categories: List[str] = [c.strip().lower() for c in cats_raw.split(",") if c.strip()]
    return {
        "auto_assign_enabled": enabled,
        "auto_assign_categories": categories,
        "admin_confirms_assignment_default": True,
        "client_id": client_id,
    }
