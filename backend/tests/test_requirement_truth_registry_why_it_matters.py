from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict


def _base_requirement(jurisdiction="England"):
    return {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "jurisdiction": jurisdiction,
        "status": "PENDING",
        "registry_metadata": {},
    }


def test_enrich_requirement_uses_published_registry_why_it_matters_without_materialization():
    req = _base_requirement("England")
    published = {
        "GAS_SAFETY|DEFAULT": {
            "canonical_code": "GAS_SAFETY",
            "scope_key": "DEFAULT",
            "jurisdiction": {"display_jurisdictions": ["England", "Wales", "Scotland", "Northern Ireland"]},
            "why_it_matters_short": "Published short copy",
            "why_it_matters_long": "Published long copy",
            "action_links": [],
        }
    }
    out = enrich_requirement_dict(
        req,
        EVIDENCE_MISSING,
        audience="client",
        published_registry_entries=published,
    )
    assert out.get("why_it_matters_short") == "Published short copy"
    assert out.get("why_it_matters_long") == "Published long copy"


def test_jurisdiction_override_beats_default():
    req = _base_requirement("Scotland")
    published = {
        "GAS_SAFETY|DEFAULT": {
            "canonical_code": "GAS_SAFETY",
            "scope_key": "DEFAULT",
            "jurisdiction": {"display_jurisdictions": ["England", "Wales", "Scotland", "Northern Ireland"]},
            "why_it_matters_short": "Default short",
            "why_it_matters_long": "Default long",
            "why_it_matters_by_jurisdiction": {
                "SCOTLAND": {"short": "Scotland short", "long": "Scotland long"}
            },
            "action_links": [],
        }
    }
    out = enrich_requirement_dict(
        req,
        EVIDENCE_MISSING,
        audience="client",
        published_registry_entries=published,
    )
    assert out.get("why_it_matters_short") == "Scotland short"
    assert out.get("why_it_matters_long") == "Scotland long"


def test_no_published_entries_means_no_draft_leak():
    req = _base_requirement("England")
    out = enrich_requirement_dict(
        req,
        EVIDENCE_MISSING,
        audience="client",
        published_registry_entries=None,
    )
    assert out.get("why_it_matters_short") is None
    assert out.get("why_it_matters_long") is None

