"""
G7 report freshness authority framework.
"""
from __future__ import annotations

from typing import Dict, Optional


class ReportFreshnessService:
    def capture(
        self,
        *,
        report_id: str,
        generation_timestamp_visible: bool,
        snapshot_timestamp_visible: bool,
        freshness_wording_visible: bool,
        lag_disclosure_visible: bool,
        export_timestamp_coherent: bool,
        live_vs_report_distinction_clear: bool,
        staleness_seconds: int,
        freshness_window_seconds: int = 60,
        g2_snapshot_reference: str = "",
    ) -> Dict[str, object]:
        stale = staleness_seconds > freshness_window_seconds
        deception = stale and not lag_disclosure_visible
        return {
            "report_id": report_id,
            "generation_timestamp_visible": generation_timestamp_visible,
            "snapshot_timestamp_visible": snapshot_timestamp_visible,
            "freshness_wording_visible": freshness_wording_visible,
            "lag_disclosure_visible": lag_disclosure_visible,
            "export_timestamp_coherent": export_timestamp_coherent,
            "live_vs_report_distinction_clear": live_vs_report_distinction_clear,
            "g2_snapshot_reference": g2_snapshot_reference,
            "staleness_seconds": staleness_seconds,
            "freshness_window_seconds": freshness_window_seconds,
            "stale": stale,
            "classification_hints": self._hints(
                deception,
                generation_timestamp_visible,
                snapshot_timestamp_visible,
                live_vs_report_distinction_clear,
            ),
        }

    def _hints(
        self,
        deception: bool,
        gen_visible: bool,
        snap_visible: bool,
        distinction_clear: bool,
    ) -> list:
        hints = []
        if deception:
            hints.extend(["REPORT_FRESHNESS_DECEPTION", "COGNITIVE_TRUST_RISK"])
        if not distinction_clear and not snap_visible:
            hints.append("TEMPORAL_PROJECTION_INVERSION")
        if not gen_visible and not snap_visible:
            hints.append("PROJECTION_LAG_UNDISCLOSED")
        return sorted(set(hints))
