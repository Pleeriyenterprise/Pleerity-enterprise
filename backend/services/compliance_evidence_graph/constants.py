"""
Compliance Evidence Graph — constants and collection names.

Internal storage for the graph index. Public access via compliance_graph_service only.
"""
from __future__ import annotations

COLLECTION_DECISIONS = "compliance_decisions"
COLLECTION_SNAPSHOTS = "compliance_decision_snapshots"
COLLECTION_NODES = "compliance_evidence_nodes"
COLLECTION_EDGES = "compliance_evidence_edges"

SERVICE_VERSION = "1.0.0"

# Decision types
DECISION_COMPLIANCE_ASSESSMENT = "compliance_assessment"
DECISION_COMPLIANCE_SCORE_CHANGE = "compliance_score_change"
DECISION_RISK_ASSESSMENT = "risk_assessment"
DECISION_REQUIREMENT_APPLICABILITY = "requirement_applicability"
DECISION_EVIDENCE_ACCEPTANCE = "evidence_acceptance"
DECISION_EVIDENCE_REJECTION = "evidence_rejection"
DECISION_REMINDER_GENERATION = "reminder_generation"
DECISION_RECOMMENDATION = "recommendation"
DECISION_WORK_ORDER_CREATION = "work_order_creation"
DECISION_REPORT_GENERATION = "report_generation"
DECISION_REGULATORY_INTERPRETATION = "regulatory_interpretation"

ALL_DECISION_TYPES = frozenset(
    {
        DECISION_COMPLIANCE_ASSESSMENT,
        DECISION_COMPLIANCE_SCORE_CHANGE,
        DECISION_RISK_ASSESSMENT,
        DECISION_REQUIREMENT_APPLICABILITY,
        DECISION_EVIDENCE_ACCEPTANCE,
        DECISION_EVIDENCE_REJECTION,
        DECISION_REMINDER_GENERATION,
        DECISION_RECOMMENDATION,
        DECISION_WORK_ORDER_CREATION,
        DECISION_REPORT_GENERATION,
        DECISION_REGULATORY_INTERPRETATION,
    }
)

# Node types
NODE_COMPLIANCE_DECISION = "compliance_decision"
NODE_DECISION_SNAPSHOT = "decision_snapshot"
NODE_DOCUMENT = "document"
NODE_CER = "cer"
NODE_REQUIREMENT = "requirement"
NODE_PROPERTY = "property"
NODE_RULE = "rule"
NODE_JURISDICTION = "jurisdiction"
NODE_AI_EXTRACTION = "ai_extraction"
NODE_HUMAN_REVIEW = "human_review"
NODE_SCORE_CHANGE = "score_change"
NODE_OPERATIONAL_EVENT = "operational_event"

ALL_NODE_TYPES = frozenset(
    {
        NODE_COMPLIANCE_DECISION,
        NODE_DECISION_SNAPSHOT,
        NODE_DOCUMENT,
        NODE_CER,
        NODE_REQUIREMENT,
        NODE_PROPERTY,
        NODE_RULE,
        NODE_JURISDICTION,
        NODE_AI_EXTRACTION,
        NODE_HUMAN_REVIEW,
        NODE_SCORE_CHANGE,
        NODE_OPERATIONAL_EVENT,
    }
)

# Edge types
EDGE_BELONGS_TO = "belongs_to"
EDGE_GOVERNED_BY = "governed_by"
EDGE_SUPPORTED_BY = "supported_by"
EDGE_DECIDED_UNDER = "decided_under"
EDGE_BASED_ON_EVIDENCE = "based_on_evidence"
EDGE_PRODUCED = "produced"
EDGE_SUPERSEDES = "supersedes"
EDGE_CORRELATES_WITH = "correlates_with"
EDGE_SNAPSHOT_OF = "snapshot_of"

ALL_EDGE_TYPES = frozenset(
    {
        EDGE_BELONGS_TO,
        EDGE_GOVERNED_BY,
        EDGE_SUPPORTED_BY,
        EDGE_DECIDED_UNDER,
        EDGE_BASED_ON_EVIDENCE,
        EDGE_PRODUCED,
        EDGE_SUPERSEDES,
        EDGE_CORRELATES_WITH,
        EDGE_SNAPSHOT_OF,
    }
)

RELATIONSHIP_STRENGTH_AUTHORITATIVE = "authoritative"
RELATIONSHIP_STRENGTH_INFERRED = "inferred"
RELATIONSHIP_STRENGTH_CORRELATED = "correlated"

CONFIDENCE_RUNTIME_CONFIRMED = 100
CONFIDENCE_INDIRECT = 80
