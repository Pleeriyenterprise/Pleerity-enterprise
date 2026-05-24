"""
Projection resolution order — contradiction registration and reconciliation.
"""
from __future__ import annotations

from typing import Dict, List

from .constants import DEFAULT_FRESHNESS_WINDOW_SECONDS, PROJECTION_RESOLUTION_RANKS, Verify02Family
from .schemas import ProjectionContradiction


class ProjectionResolutionService:
    def __init__(self, freshness_window_seconds: int = DEFAULT_FRESHNESS_WINDOW_SECONDS) -> None:
        self.freshness_window_seconds = freshness_window_seconds
        self._contradictions: List[ProjectionContradiction] = []

    def register_value(
        self,
        *,
        source_surface: str,
        projection_type: str,
        value: float,
        disclosure_present: bool = False,
        disclosure_required: bool = False,
    ) -> None:
        rank = self._rank_for_type(projection_type)
        owner = self._owner_for_rank(rank)
        self._contradictions.append(
            ProjectionContradiction(
                source_surface=source_surface,
                projection_type=projection_type,
                authority_rank=rank,
                value=value,
                freshness_window_seconds=self.freshness_window_seconds,
                disclosure_required=disclosure_required,
                disclosure_present=disclosure_present,
                reconciliation_owner=owner,
                contradiction_detected=False,
                resolution="unresolved",
            )
        )

    def evaluate(self) -> List[ProjectionContradiction]:
        if len(self._contradictions) < 2:
            return list(self._contradictions)
        by_metric: Dict[str, List[ProjectionContradiction]] = {}
        for c in self._contradictions:
            by_metric.setdefault(c.projection_type, []).append(c)
        results: List[ProjectionContradiction] = []
        for group in by_metric.values():
            if len(group) < 2:
                results.extend(group)
                continue
            sorted_g = sorted(group, key=lambda x: x.authority_rank)
            winner = sorted_g[0]
            for c in sorted_g[1:]:
                if c.value is None or winner.value is None:
                    results.append(c)
                    continue
                if c.value == winner.value:
                    c.contradiction_detected = False
                    c.resolution = "authoritative_winner"
                else:
                    c.contradiction_detected = True
                    if c.authority_rank > winner.authority_rank and c.disclosure_present:
                        c.resolution = "acceptable_lag"
                    else:
                        c.resolution = "unresolved"
                    c.reconciliation_owner = winner.reconciliation_owner
                results.append(c)
            results.append(winner)
        self._contradictions = results
        return results

    def build_artifact(self) -> Dict[str, object]:
        evaluated = self.evaluate()
        return {
            "canonical_order": [
                {"rank": r, "type": t, "owner": o} for r, t, o in PROJECTION_RESOLUTION_RANKS
            ],
            "contradictions": [c.to_dict() for c in evaluated],
            "contradiction_detected": any(c.contradiction_detected for c in evaluated),
        }

    def reporting_lag(
        self,
        *,
        live_value: float,
        derived_value: float,
        staleness_seconds: int,
        disclosure_present: bool,
    ) -> Dict[str, object]:
        within = staleness_seconds <= self.freshness_window_seconds
        return {
            "live_value": live_value,
            "derived_value": derived_value,
            "staleness_seconds": staleness_seconds,
            "freshness_window_seconds": self.freshness_window_seconds,
            "disclosure_present": disclosure_present,
            "acceptable_lag": within and disclosure_present,
            "classification_hint": None
            if (within and disclosure_present)
            else "PROJECTION_LAG_UNDISCLOSED",
        }

    @staticmethod
    def _rank_for_type(projection_type: str) -> int:
        for rank, t, _ in PROJECTION_RESOLUTION_RANKS:
            if t == projection_type:
                return rank
        return 99

    @staticmethod
    def _owner_for_rank(rank: int) -> str:
        for r, _, owner in PROJECTION_RESOLUTION_RANKS:
            if r == rank:
                return owner
        return Verify02Family.G2.value

    def classify_contradictions(self) -> List[str]:
        tags: List[str] = []
        for c in self.evaluate():
            if not c.contradiction_detected:
                continue
            if c.resolution == "acceptable_lag":
                if c.disclosure_required and not c.disclosure_present:
                    tags.append("PROJECTION_LAG_UNDISCLOSED")
            else:
                tags.append("PROJECTION_RESOLUTION_FAILURE")
            if c.projection_type in ("derived", "exported") and c.disclosure_required and not c.disclosure_present:
                tags.append("TEMPORAL_PROJECTION_INVERSION")
        return sorted(set(tags))
