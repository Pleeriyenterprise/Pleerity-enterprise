"""Report Presentation Authority facade."""

from __future__ import annotations

from report_presentation.actions import format_actions_closing_lines, present_recommended_actions
from report_presentation.appendix import (
    customer_snapshot_line,
    governance_appendix_lines,
    readiness_section_intro,
)
from report_presentation.actors import present_actor_label
from report_presentation.confidence import present_confidence_block
from report_presentation.constants import AUTHORITY_VERSION
from report_presentation.evidence import infer_document_title, present_evidence_row
from report_presentation.executive import build_executive_summary_payload
from report_presentation.profiles import profile_config, resolve_profile
from report_presentation.technical_language import (
    contains_technical_language_leak,
    sanitize_customer_section_text,
)
from report_presentation.timeline import (
    build_layered_timeline,
    humanize_audit_event_action,
    present_technical_forensic_row,
    present_timeline_row,
)
from report_presentation.timestamps import format_customer_timestamp, format_technical_timestamp


class ReportPresentationAuthority:
    """Single entry point for governed report presentation."""

    version = AUTHORITY_VERSION

    resolve_profile = staticmethod(resolve_profile)
    profile_config = staticmethod(profile_config)
    build_executive_summary = staticmethod(build_executive_summary_payload)
    build_layered_timeline = staticmethod(build_layered_timeline)
    present_timeline_row = staticmethod(present_timeline_row)
    present_technical_forensic_row = staticmethod(present_technical_forensic_row)
    humanize_audit_event = staticmethod(humanize_audit_event_action)
    present_actor = staticmethod(present_actor_label)
    format_customer_timestamp = staticmethod(format_customer_timestamp)
    format_technical_timestamp = staticmethod(format_technical_timestamp)
    present_evidence_row = staticmethod(present_evidence_row)
    infer_document_title = staticmethod(infer_document_title)
    present_confidence = staticmethod(present_confidence_block)
    present_recommended_actions = staticmethod(present_recommended_actions)
    format_actions_closing_lines = staticmethod(format_actions_closing_lines)
    customer_snapshot_line = staticmethod(customer_snapshot_line)
    governance_appendix_lines = staticmethod(governance_appendix_lines)
    readiness_section_intro = staticmethod(readiness_section_intro)
    contains_technical_leak = staticmethod(contains_technical_language_leak)
    sanitize_customer_text = staticmethod(sanitize_customer_section_text)
