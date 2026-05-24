"""
VERIFY-02 classification aggregation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from .constants import EXECUTION_STATUS_NOT_EXECUTED, IMPLEMENTATION_STATUS_READY, PROGRAMME_ID


TRUST_BLOCKING = frozenset(
    {
        "TRUST_RISK_PRESENT",
        "COGNITIVE_TRUST_RISK",
        "CONTROL_PLANE_CIRCULARITY",
        "PROJECTION_RESOLUTION_FAILURE",
        "PROJECTION_LAG_UNDISCLOSED",
        "REPORT_FRESHNESS_DECEPTION",
        "WIDGET_ISLAND_FAILURE",
        "OPERATIONAL_ORPHAN_STATE",
        "FAIL_SYSTEM",
        "FAIL_OPERATIONAL",
        "FAIL_OPERATIONAL_NOOP",
        "RESOLUTION_EXHAUSTION",
        "TEMPORAL_PROJECTION_INVERSION",
    }
)


@dataclass
class Verify02Classification:
    primary: str = EXECUTION_STATUS_NOT_EXECUTED
    secondary: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    family: str = ""
    blocking: bool = False

    def to_dict(self) -> dict:
        return {
            "programme": PROGRAMME_ID,
            "family": self.family,
            "classification": self.primary,
            "secondary_classifications": sorted(set(self.secondary)),
            "reasons": self.reasons,
            "blocking": self.blocking,
        }


class ClassificationAggregator:
    def __init__(self, family: str) -> None:
        self.family = family
        self._tags: Set[str] = set()
        self._reasons: List[str] = []

    def add(self, tag: str, reason: str = "") -> None:
        self._tags.add(tag)
        if reason:
            self._reasons.append(reason)
        self._apply_coexistence(tag)

    def _apply_coexistence(self, tag: str) -> None:
        if tag == "WIDGET_ISLAND_FAILURE":
            self._tags.add("COGNITIVE_TRUST_RISK")
        if tag == "REPORT_FRESHNESS_DECEPTION":
            self._tags.add("COGNITIVE_TRUST_RISK")
        if tag == "CONTROL_PLANE_CIRCULARITY":
            self._tags.add("COGNITIVE_TRUST_RISK")
        if tag == "PROJECTION_RESOLUTION_FAILURE":
            self._tags.add("TRUST_RISK_PRESENT")
        if tag == "OPERATIONAL_ORPHAN_STATE":
            pass  # TRUST_RISK added by caller when user-visible

    def finalize(self, *, execution_completed: bool = False) -> Verify02Classification:
        if not execution_completed:
            return Verify02Classification(
                primary=EXECUTION_STATUS_NOT_EXECUTED,
                secondary=sorted(self._tags),
                reasons=self._reasons or ["Framework scaffold — no runtime execution"],
                family=self.family,
                blocking=False,
            )
        blocking_tags = self._tags & TRUST_BLOCKING
        if blocking_tags:
            primary = sorted(blocking_tags, key=lambda x: x)[0]
            return Verify02Classification(
                primary=primary,
                secondary=sorted(self._tags - {primary}),
                reasons=self._reasons,
                family=self.family,
                blocking=True,
            )
        return Verify02Classification(
            primary="VERIFIED_OPERATIONALLY",
            secondary=sorted(self._tags),
            reasons=self._reasons,
            family=self.family,
            blocking=False,
        )


def implementation_classification(ready: bool) -> str:
    return IMPLEMENTATION_STATUS_READY if ready else "IMPLEMENTATION_INCOMPLETE"
