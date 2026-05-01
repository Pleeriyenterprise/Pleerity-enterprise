"""Stream E phase 3: structured compliance_fanout logging helper."""
import sys
from pathlib import Path

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_compliance_fanout_extra_omits_none_and_includes_dedupe():
    from utils.compliance_fanout_log import compliance_fanout_extra

    d = compliance_fanout_extra(
        op="recalc_enqueue",
        stage="dedupe",
        client_id="c1",
        property_id="p1",
        correlation_id="corr:1",
        trigger_reason="DOC_UPLOADED",
        dedupe=True,
    )
    assert d["event"] == "compliance_fanout"
    assert d["op"] == "recalc_enqueue"
    assert d["stage"] == "dedupe"
    assert d["client_id"] == "c1"
    assert d["property_id"] == "p1"
    assert d["correlation_id"] == "corr:1"
    assert d["trigger_reason"] == "DOC_UPLOADED"
    assert d["dedupe"] is True
    assert "requirement_id" not in d
    assert "error_count" not in d


def test_compliance_fanout_extra_partial_gap_fields():
    from utils.compliance_fanout_log import compliance_fanout_extra

    d = compliance_fanout_extra(
        op="gap_sync",
        stage="partial",
        client_id="c1",
        property_id="p1",
        requirement_id="r1",
        error_count=2,
    )
    assert d["error_count"] == 2
    assert d["requirement_id"] == "r1"
