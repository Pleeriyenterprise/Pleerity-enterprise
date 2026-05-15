"""Central support AI system instructions — content audit guards."""
import json

from services.support_ai_instructions import (
    build_brain_json_schema_instruction,
    build_full_planner_system_prompt,
    build_planner_user_payload,
    build_support_ai_system_instruction,
)


def test_role_and_persona_defined():
    text = build_support_ai_system_instruction().lower()
    assert "support" in text
    assert "human" in text or "staff" in text
    assert "menu" in text or "router" in text


def test_prioritises_current_message():
    text = build_support_ai_system_instruction().lower()
    assert "user_message" in text or "latest user_message" in text
    assert "topic" in text and ("changes topic" in text or "change topic" in text)


def test_concise_conversational_tone():
    text = build_support_ai_system_instruction().lower()
    assert "brief" in text
    assert "natural" in text or "plain english" in text


def test_branding_restraint():
    text = build_support_ai_system_instruction().lower()
    assert "pleerity" in text
    assert "marketing" in text or "do not repeat" in text


def test_clarification_and_recovery():
    text = build_support_ai_system_instruction().lower()
    assert "clarif" in text
    assert "frustrat" in text or "confus" in text


def test_actions_secondary():
    text = build_support_ai_system_instruction().lower()
    assert "show_actions" in text or "actions" in text
    assert "first" in text or "secondary" in text or "after the answer" in text


def test_safety_and_pricing_authority():
    text = build_support_ai_system_instruction().lower()
    assert "legal" in text
    assert "registry_facts" in text
    assert "invent" in text


def test_no_admin_kb_and_no_raw_paste():
    text = build_support_ai_system_instruction().lower()
    assert "admin" in text or "internal" in text
    assert "paste" in text or "paraphrase" in text or "synthes" in text


def test_json_schema_separate_and_complete():
    schema = build_brain_json_schema_instruction(["sign_in", "view_pricing"])
    assert "reply_text" in schema
    assert "show_actions" in schema
    assert "sign_in" in schema
    assert "json object only" in schema.lower() or "json object" in schema.lower()


def test_full_prompt_composes_both_layers():
    full = build_full_planner_system_prompt(["talk_to_support"])
    assert "Role" in full or "## Role" in full
    assert "Output format" in full
    assert "talk_to_support" in full


def test_pleerity_role_and_cvp_scope():
    text = build_support_ai_system_instruction().lower()
    assert "pleerity" in text
    assert "compliance vault" in text


def test_compliance_language_careful_wording():
    text = build_support_ai_system_instruction().lower()
    assert "risk indicator" in text
    assert "legally compliant" in text or "legal compliance" in text
    assert "guaranteed" in text


def test_pricing_actions_gated():
    text = build_support_ai_system_instruction().lower()
    assert "pricing" in text and "show" in text
    assert "subscription" in text or "plans" in text


def test_human_support_no_false_connect():
    text = build_support_ai_system_instruction().lower()
    assert "connect" in text or "available options" in text
    assert "live_chat" in text or "live chat" in text or "live agents" in text


def test_vague_help_clarify_before_cards():
    text = build_support_ai_system_instruction().lower()
    assert "clarif" in text
    assert "do not immediately" in text or "before" in text


def test_anti_template_tone_guidance():
    text = build_support_ai_system_instruction().lower()
    assert "template" in text or "corporate" in text
    assert "plain" in text or "practical" in text


def test_grounding_tiers_and_plan_features():
    text = build_support_ai_system_instruction().lower()
    assert "plan_feature_facts" in text or "plan feature" in text
    assert "do not infer" in text or "do not guess" in text
    assert "registry_facts" in text


def test_frustration_recovery_guidance():
    text = build_support_ai_system_instruction().lower()
    assert "misunderstood" in text or "misunderstand" in text
    assert "verbatim" in text or "repeat" in text


def test_handoff_continuity_in_instructions():
    text = build_support_ai_system_instruction().lower()
    assert "pending_handoff" in text
    assert "conversation_state" in text


def test_confidence_aware_behaviour():
    text = build_support_ai_system_instruction().lower()
    assert "confidence" in text
    assert "0.75" in text or "high confidence" in text


def test_cvp_workflow_explanations():
    text = build_support_ai_system_instruction().lower()
    assert "workflow" in text or "landlord" in text
    assert "audit" in text or "reminder" in text or "certificate" in text


def test_memory_weighting_guidance():
    text = build_support_ai_system_instruction().lower()
    assert "shallow" in text or "weak" in text
    assert "interruption" in text or "corrected" in text


def test_evidence_and_score_grounding_sections():
    text = build_support_ai_system_instruction().lower()
    assert "compliance score" in text
    assert "evidence" in text
    assert "plan comparison" in text or "plan_feature_facts" in text


def test_planner_payload_includes_conversation_state():
    blob = json.loads(
        build_planner_user_payload(
            user_message="what do I do with this",
            conversation_memory={},
            conversation_state={"pending_handoff": True},
            retrieval_chunks=[],
            registry_facts="",
            plan_feature_facts="",
            policy_snippets={},
            handoff_channels={},
            recent_transcript="",
            allowed_action_ids=["talk_to_support"],
        )
    )
    assert blob["conversation_state"]["pending_handoff"] is True
    assert "plan_feature_facts" in blob
