"""Registry version identifiers — v1 seeds for CIE-1.5."""
from __future__ import annotations

# Strategy registry v1
REC_STRATEGY_V1 = "rec_strategy_v1.0.0"
PRIORITY_STRATEGY_V1 = "priority_strategy_v1.0.0"
DEPENDENCY_STRATEGY_V1 = "dependency_strategy_v1.0.0"
IMPACT_STRATEGY_V1 = "impact_strategy_v1.0.0"

# Weight registry v1
WEIGHT_SET_V1 = "weights_v1.0.0"

# Constraint registry v1
CONSTRAINT_SET_V1 = "constraints_v1.0.0"

# Scoring / runtime context v1
SCORING_MODEL_V1 = "scoring_model_v1.0.0"
RUNTIME_CONTEXT_V1 = "runtime_ctx_v1.0.0"

ALL_V1_STRATEGY_IDS = frozenset(
    {
        REC_STRATEGY_V1,
        PRIORITY_STRATEGY_V1,
        DEPENDENCY_STRATEGY_V1,
        IMPACT_STRATEGY_V1,
    }
)
