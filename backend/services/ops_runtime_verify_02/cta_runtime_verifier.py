"""
CTA-RUNTIME-ROUTE-01 framework (no browser execution in infrastructure phase).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .schemas import CtaProbeResult


class CtaRuntimeVerifier:
    def __init__(self) -> None:
        self._probes: List[CtaProbeResult] = []
        self._seen_keys: Dict[str, str] = {}

    def register_cta(
        self,
        *,
        cta_id: str,
        label: str,
        source_route: str,
        destination_route: str,
        mutation_owner: str = "none",
    ) -> CtaProbeResult:
        probe = CtaProbeResult(
            cta_id=cta_id,
            label=label,
            source_route=source_route,
            destination_route=destination_route,
            mutation_owner_present=mutation_owner not in ("", "none"),
        )
        self._probes.append(probe)
        return probe

    def evaluate_probe(
        self,
        probe: CtaProbeResult,
        *,
        pre_state: Dict[str, object],
        post_state: Dict[str, object],
        post_refresh_state: Optional[Dict[str, object]] = None,
        destination_reachable: bool = True,
    ) -> CtaProbeResult:
        key = f"{probe.source_route}:{probe.label}:{probe.destination_route}"
        if key in self._seen_keys and self._seen_keys[key] != probe.cta_id:
            probe.duplicate_cta = True
            probe.notes.append("duplicate_cta_same_action")
        else:
            self._seen_keys[key] = probe.cta_id

        probe.reachable = destination_reachable and bool(probe.destination_route)
        if not probe.reachable:
            probe.dead_end = True
            probe.notes.append("dead_end")

        if pre_state == post_state and probe.mutation_owner_present:
            probe.noop_detected = True
            probe.notes.append("FAIL_OPERATIONAL_NOOP")

        if post_refresh_state is not None and post_refresh_state != post_state and pre_state == post_state:
            probe.notes.append("optimistic_only_ui")

        return probe

    def detect_contradictory_pair(self, a: CtaProbeResult, b: CtaProbeResult) -> bool:
        if a.source_route == b.source_route and a.cta_id != b.cta_id:
            if a.destination_route != b.destination_route and a.label.split()[0] == b.label.split()[0]:
                a.contradictory_cta = True
                b.contradictory_cta = True
                return True
        return False

    def build_matrix(self) -> Dict[str, object]:
        return {
            "probes": [p.to_dict() for p in self._probes],
            "noop_detected": any(p.noop_detected for p in self._probes),
            "duplicate_cta": any(p.duplicate_cta for p in self._probes),
            "dead_end": any(p.dead_end for p in self._probes),
            "contradictory": any(p.contradictory_cta for p in self._probes),
        }
