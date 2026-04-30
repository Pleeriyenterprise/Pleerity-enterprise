import pytest

from services.hiua_operational_uncertainty import (
    HIUA_EXPIRING_SOON_MAX_DAYS,
    derive_hiua_signal_for_open_gap,
    hiua_command_centre_copy,
    hiua_digest_report_copy,
)
from services.policy_reason_codes import PolicyReasonCode


def _gap_gas_unknown_missing(**overrides):
    base = {
        "status": "open",
        "gap_kind": "MISSING_EVIDENCE",
        "requirement_code": "gas_safety",
        "applicability_state": "UNKNOWN",
        "is_mandatory": True,
        "policy_criticality": "MEDIUM",
        "evidence_state_normalized": "MISSING",
        "high_risk_gap": False,
        "critical_mandatory_breach": False,
        "authority_snapshot": {},
    }
    base.update(overrides)
    return base


def test_hiua_true_gas_safety_unknown_missing_evidence():
    assert derive_hiua_signal_for_open_gap(_gap_gas_unknown_missing()) is True


def test_hiua_false_when_high_risk_gap_set():
    g = _gap_gas_unknown_missing(high_risk_gap=True)
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_false_when_critical_mandatory_breach_set():
    g = _gap_gas_unknown_missing(critical_mandatory_breach=True)
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_false_when_applicability_required():
    g = _gap_gas_unknown_missing(applicability_state="REQUIRED")
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_false_when_gap_snapshot_effective_required_operator_path():
    """PR5: stale applicability_state on gap must not mask effective REQUIRED."""
    g = _gap_gas_unknown_missing(
        applicability_state="UNKNOWN",
        pipeline_applicability_state="UNKNOWN",
        effective_applicability_state="REQUIRED",
        applicability_resolution_source="OPERATOR_OVERRIDE",
    )
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_false_low_impact_code():
    g = _gap_gas_unknown_missing(requirement_code="epc")
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_false_when_evidence_verified_on_material_kind():
    g = _gap_gas_unknown_missing(evidence_state_normalized="VERIFIED")
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_false_non_open_status():
    g = _gap_gas_unknown_missing(status="closed")
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_expiring_soon_within_window_not_verified():
    g = _gap_gas_unknown_missing(
        gap_kind="EXPIRING_SOON",
        days_to_expiry=14,
        evidence_state_normalized="UPLOADED_UNCONFIRMED",
    )
    assert derive_hiua_signal_for_open_gap(g) is True


def test_hiua_expiring_soon_outside_window():
    g = _gap_gas_unknown_missing(
        gap_kind="EXPIRING_SOON",
        days_to_expiry=HIUA_EXPIRING_SOON_MAX_DAYS + 5,
        evidence_state_normalized="UPLOADED_UNCONFIRMED",
    )
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_expiring_soon_verified_suppresses():
    g = _gap_gas_unknown_missing(
        gap_kind="EXPIRING_SOON",
        days_to_expiry=10,
        evidence_state_normalized="VERIFIED",
    )
    assert derive_hiua_signal_for_open_gap(g) is False


def test_hiua_ignores_severity_field():
    g = _gap_gas_unknown_missing(severity="LOW")
    assert derive_hiua_signal_for_open_gap(g) is True


@pytest.mark.asyncio
async def test_hiua_tenant_summary_bounded():
    from services.hiua_operational_uncertainty import hiua_tenant_operational_summary

    rows = [_gap_gas_unknown_missing(gap_key="gk1"), _gap_gas_unknown_missing(gap_key="gk2")]

    class _Cursor:
        def __init__(self, data):
            self._data = data

        def limit(self, _n):
            return self

        async def to_list(self, cap):
            return list(self._data[:cap])

    class _Coll:
        def __init__(self, data):
            self._data = data

        def find(self, *_a, **_k):
            return _Cursor(self._data)

    class _Db:
        compliance_gaps = _Coll(rows)

    out = await hiua_tenant_operational_summary(_Db(), "c1", max_gaps_scan=10, max_detail=1)
    assert out["hiua_active"] is True
    assert out["hiua_open_gap_count"] == 2
    assert PolicyReasonCode.HIGH_IMPACT_UNRESOLVED_APPLICABILITY.value in out["hiua_reason_codes"]
    assert len(out["hiua_gap_details"]) == 1


def test_hiua_copy_inactive():
    assert hiua_command_centre_copy(active=False, count=0)["message"] is None
    assert hiua_digest_report_copy(active=False, count=0)["digest_line"] is None


def test_hiua_copy_active():
    cc = hiua_command_centre_copy(active=True, count=2)
    assert cc["message"] and "2" in cc["message"]
    assert cc["filter_label"]
    dr = hiua_digest_report_copy(active=True, count=1)
    assert dr["digest_line"] and dr["report_framing_notice"]
