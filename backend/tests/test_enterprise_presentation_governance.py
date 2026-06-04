"""REPORTING-ENTERPRISE-PRESENTATION-GOVERNANCE-01 — presentation/governance audit guards."""

from services.reporting_semantics_v1 import (
    EXPORT_GRADE_DEFINITIONS,
    GRADE_AUDIT_ARTIFACT,
    PDF_ENGINE_JSPDF,
    PDF_ENGINE_RULES,
    SURFACE_EXPORT_REGISTRY,
)


def test_surface_registry_covers_key_client_exports():
    required = {
        "evidence_readiness_pdf",
        "audit_evidence_pack_zip",
        "compliance_summary_csv",
        "compliance_summary_pdf_jspdf",
        "professional_compliance_pdf",
    }
    assert required.issubset(set(SURFACE_EXPORT_REGISTRY.keys()))


def test_audit_pack_has_immutable_determinism_and_grade():
    reg = SURFACE_EXPORT_REGISTRY["audit_evidence_pack_zip"]
    assert reg["export_grade"] == GRADE_AUDIT_ARTIFACT
    assert reg["determinism"] == "immutable_artifact"
    assert "manifest" in (reg.get("disclosure") or "").lower() or "immutable" in (reg.get("disclosure") or "").lower()


def test_jspdf_surfaces_not_audit_grade():
    for key, reg in SURFACE_EXPORT_REGISTRY.items():
        if reg.get("pdf_engine") == PDF_ENGINE_JSPDF:
            assert reg["export_grade"] != GRADE_AUDIT_ARTIFACT


def test_export_grade_definitions_complete():
    assert "OPERATIONAL_EXPORT" in EXPORT_GRADE_DEFINITIONS
    assert "REGULATORY_SUBMISSION" in EXPORT_GRADE_DEFINITIONS
    assert "disclaimer" in EXPORT_GRADE_DEFINITIONS[GRADE_AUDIT_ARTIFACT] or "artifact" in str(
        EXPORT_GRADE_DEFINITIONS[GRADE_AUDIT_ARTIFACT]
    ).lower()


def test_reportlab_allowed_regulatory_path():
    from services.reporting_semantics_v1 import PDF_ENGINE_REPORTLAB

    assert GRADE_AUDIT_ARTIFACT in PDF_ENGINE_RULES[PDF_ENGINE_REPORTLAB]["allowed_grades"]
