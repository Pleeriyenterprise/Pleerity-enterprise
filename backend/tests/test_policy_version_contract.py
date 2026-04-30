from services.portfolio_risk_policy import POLICY_CLASSIFICATION_VERSION, policy_contract_metadata


def test_policy_classification_version_is_frozen_contract_value():
    assert POLICY_CLASSIFICATION_VERSION == "v1"


def test_policy_contract_metadata_declares_no_severity_only_logic():
    meta = policy_contract_metadata()
    assert meta["policy_classification_version"] == "v1"
    assert meta["severity_only_critical_breach_forbidden"] is True
    assert "version bump" in meta["predicate_freeze_rule"].lower()
