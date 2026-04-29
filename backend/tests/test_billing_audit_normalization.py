from services.billing_audit_normalization import normalized_billing_audit_metadata


def test_normalized_billing_audit_metadata_contains_expected_fields():
    meta = normalized_billing_audit_metadata(
        machine_event_type="billing.sync.completed",
        human_label="Billing sync completed",
        actor_type="admin",
        client_id="client-1",
    )
    assert meta["machine_event_type"] == "billing.sync.completed"
    assert meta["human_label"] == "Billing sync completed"
    assert meta["actor_type"] == "admin"
    assert meta["client_id"] == "client-1"
    assert meta.get("occurred_at_utc")
    assert meta.get("correlation_id")
