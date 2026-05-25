"""Payload contract for dashboard property create (address lookup parity must not change shape)."""

from routes.properties import CreatePropertyRequest


def test_create_property_request_accepts_normalized_address_fields():
    req = CreatePropertyRequest(
        nickname="Flat A",
        address_line_1="10 High Street",
        address_line_2="Flat 4",
        city="London",
        postcode="SW1A 1AA",
        jurisdiction="England",
        property_type="residential",
        number_of_units=1,
    )
    assert req.address_line_1 == "10 High Street"
    assert req.postcode == "SW1A 1AA"
    assert req.jurisdiction == "England"


def test_create_property_request_jurisdiction_optional():
    req = CreatePropertyRequest(
        address_line_1="1 Road",
        city="Cardiff",
        postcode="CF10 1AA",
    )
    assert req.jurisdiction is None
    assert req.nickname is None
