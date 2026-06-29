"""Registered Compliance Intelligence Artefact types."""
from __future__ import annotations

from typing import FrozenSet

ARTEFACT_TYPE_RECOMMENDATION = "recommendation"
ARTEFACT_TYPE_PRIORITY_ASSESSMENT = "priority_assessment"
ARTEFACT_TYPE_DECISION_IMPACT = "decision_impact_assessment"
ARTEFACT_TYPE_DEPENDENCY_CHAIN = "dependency_chain"
ARTEFACT_TYPE_PORTFOLIO_INSIGHT = "portfolio_insight"
ARTEFACT_TYPE_PORTFOLIO_RISK = "portfolio_risk_assessment"
ARTEFACT_TYPE_PORTFOLIO_READINESS = "portfolio_readiness_assessment"
ARTEFACT_TYPE_REGULATORY_IMPACT = "regulatory_impact_assessment"
ARTEFACT_TYPE_FORECAST = "forecast"
ARTEFACT_TYPE_WORKLOAD_FORECAST = "workload_forecast"
ARTEFACT_TYPE_AUDIT_READINESS = "audit_readiness_assessment"
ARTEFACT_TYPE_INSURANCE_READINESS = "insurance_readiness_assessment"
ARTEFACT_TYPE_COMPLIANCE_TREND = "compliance_trend"
ARTEFACT_TYPE_OPERATIONAL_INSIGHT = "operational_insight"
ARTEFACT_TYPE_REMEDIATION_STRATEGY = "remediation_strategy"

ALL_ARTEFACT_TYPES: FrozenSet[str] = frozenset(
    {
        ARTEFACT_TYPE_RECOMMENDATION,
        ARTEFACT_TYPE_PRIORITY_ASSESSMENT,
        ARTEFACT_TYPE_DECISION_IMPACT,
        ARTEFACT_TYPE_DEPENDENCY_CHAIN,
        ARTEFACT_TYPE_PORTFOLIO_INSIGHT,
        ARTEFACT_TYPE_PORTFOLIO_RISK,
        ARTEFACT_TYPE_PORTFOLIO_READINESS,
        ARTEFACT_TYPE_REGULATORY_IMPACT,
        ARTEFACT_TYPE_FORECAST,
        ARTEFACT_TYPE_WORKLOAD_FORECAST,
        ARTEFACT_TYPE_AUDIT_READINESS,
        ARTEFACT_TYPE_INSURANCE_READINESS,
        ARTEFACT_TYPE_COMPLIANCE_TREND,
        ARTEFACT_TYPE_OPERATIONAL_INSIGHT,
        ARTEFACT_TYPE_REMEDIATION_STRATEGY,
    }
)


def is_registered_artefact_type(value: str) -> bool:
    return (value or "").strip().lower() in ALL_ARTEFACT_TYPES
