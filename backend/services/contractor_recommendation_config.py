"""
Configurable weights and thresholds for the rule-based Contractor Recommendation Engine.
Adjust these to tune ranking without refactoring business logic.
"""
from typing import Dict

# Scoring weights (must sum to 100). Used by contractor_recommendation.recommend_contractors().
DEFAULT_WEIGHTS: Dict[str, int] = {
    "trade_match": 30,
    "region_match": 20,
    "credential_match": 20,
    "sla_performance": 10,
    "rating": 10,
    "rework_rate": 5,
    "price_fit": 5,
}

# Minimum total score (0-100) to consider a contractor a "strong match". Below this, API returns no_strong_match=True.
MIN_SCORE_STRONG_MATCH = 25

# Job type -> required credential keys (contractor.credentials must contain one of these, or vetted=True).
# Keys are recommended_contractor_type from work order / triage.
REQUIRED_CREDENTIALS_BY_TYPE: Dict[str, list] = {
    "gas_safe": ["gas_safe", "gas safe", "gas safe register"],
    "plumber": [],  # No mandatory credential; vetted or trade match suffices
    "electrician": [],  # NICEIC etc optional
    "damp_inspection": ["damp", "cswa", "cst"],
    "general": [],
}

# Job types that require vetted=True when credential is not present (e.g. gas_safe).
VERIFICATION_REQUIRED_TYPES = ["gas_safe"]

# Region: postcode prefix length to match (e.g. "G1" = Glasgow). Contractors with region or areas_served containing this match.
POSTCODE_PREFIX_LEN = 2

# Rework: lower is better. Score 5 when rework_rate is 0, 0 when >= 0.2 (20%). Linear in between.
REWORK_RATE_MAX_PENALTY = 0.2
