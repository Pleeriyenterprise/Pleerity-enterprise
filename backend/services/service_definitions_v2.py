"""
Authoritative Service Definitions - Phase 1

This file contains the authoritative service definitions as specified.
These are seeded into the service_catalogue_v2 collection.

Categories:
- ai_automation: Workflow blueprints, process mapping, AI tools
- market_research: Basic and advanced market research
- compliance: HMO audits, full audits, move-in/out checklists, CVP tracking
- document_pack: Essential, Tenancy (Plus), Ultimate (Pro) packs
- subscription: CVP subscription tiers

Document Pack Hierarchy:
- ESSENTIAL: Core landlord forms (£29)
- PLUS (Tenancy): ESSENTIAL + legal notices (£49)
- PRO (Ultimate): PLUS + comprehensive coverage (£79)

Add-ons:
- Fast Track: +£20, 24hr delivery
- Printed Copy: +£25, postal delivery
"""
from datetime import datetime, timezone
from services.service_catalogue_v2 import (
    ServiceCatalogueEntryV2,
    ServiceCategory,
    PricingModel,
    ProductType,
    DeliveryType,
    GenerationMode,
    PackTier,
    PricingVariant,
    DocumentTemplate,
    IntakeFieldSchema,
    IntakeFieldType,
    service_catalogue_v2,
)
from database import database
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# COMMON INTAKE FIELDS (CRM Field Dictionary)
# ============================================================================

# Client Information Fields
CLIENT_INFO_FIELDS = [
    IntakeFieldSchema(
        field_id="client_full_name",
        label="Full Name",
        field_type=IntakeFieldType.TEXT,
        required=True,
        order=1
    ),
    IntakeFieldSchema(
        field_id="client_email",
        label="Email Address",
        field_type=IntakeFieldType.EMAIL,
        required=True,
        order=2
    ),
    IntakeFieldSchema(
        field_id="client_phone",
        label="Phone Number",
        field_type=IntakeFieldType.PHONE,
        required=True,
        order=3
    ),
    IntakeFieldSchema(
        field_id="client_role",
        label="Your Role",
        field_type=IntakeFieldType.SELECT,
        required=True,
        options=["Landlord", "Letting Agent", "Property Manager", "Other"],
        order=4
    ),
    IntakeFieldSchema(
        field_id="company_name",
        label="Company Name",
        field_type=IntakeFieldType.TEXT,
        required=False,
        order=5
    ),
]

# Property Details Fields
PROPERTY_FIELDS = [
    IntakeFieldSchema(
        field_id="property_address_line1",
        label="Address Line 1",
        field_type=IntakeFieldType.TEXT,
        required=True,
        order=10
    ),
    IntakeFieldSchema(
        field_id="property_address_line2",
        label="Address Line 2",
        field_type=IntakeFieldType.TEXT,
        required=False,
        order=11
    ),
    IntakeFieldSchema(
        field_id="property_town_city",
        label="Town/City",
        field_type=IntakeFieldType.TEXT,
        required=True,
        order=12
    ),
    IntakeFieldSchema(
        field_id="property_postcode",
        label="Postcode",
        field_type=IntakeFieldType.TEXT,
        required=True,
        order=13
    ),
    IntakeFieldSchema(
        field_id="country_region",
        label="Country/Region",
        field_type=IntakeFieldType.SELECT,
        required=True,
        options=["England", "Wales", "Scotland", "Northern Ireland"],
        order=14
    ),
    IntakeFieldSchema(
        field_id="property_type",
        label="Property Type",
        field_type=IntakeFieldType.SELECT,
        required=True,
        options=["Flat", "House", "HMO", "Studio", "Bungalow", "Commercial"],
        order=15
    ),
    IntakeFieldSchema(
        field_id="number_of_bedrooms",
        label="Number of Bedrooms",
        field_type=IntakeFieldType.NUMBER,
        required=True,
        order=16
    ),
]


# ============================================================================
# AUTOMATION SERVICES
# ============================================================================

AI_AUTOMATION_SERVICES = [
    # Workflow Automation Blueprint - £79
    ServiceCatalogueEntryV2(
        service_code="AI_WF_BLUEPRINT",
        service_name="Workflow Automation Blueprint",
        description="Structured automation plan identifying which workflows to automate, which tools to use, and expected efficiency gains.",
        long_description="""Our Workflow Automation Blueprint provides a comprehensive analysis of your business processes 
        and delivers a structured automation plan. We identify which workflows can be automated, recommend appropriate tools, 
        and outline expected efficiency gains. This document serves as your roadmap for operational transformation.""",
        category=ServiceCategory.AI_AUTOMATION,
        website_preview="Structured automation plan identifying which workflows to automate, which tools to use, and expected efficiency gains.",
        learn_more_slug="workflow-automation-blueprint",
        pricing_model=PricingModel.ONE_TIME,
        base_price=7900,  # £79
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=7900,
                stripe_price_id="price_AI_WF_BLUEPRINT_std",
                target_due_hours=48
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=9900,
                stripe_price_id="price_AI_WF_BLUEPRINT_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        delivery_type=DeliveryType.DIGITAL,
        standard_turnaround_hours=48,
        workflow_name="wf_ai_blueprint",
        documents_generated=[
            DocumentTemplate(
                template_code="ai_workflow_blueprint_template",
                template_name="Workflow Automation Blueprint",
                format="pdf",
                generation_order=1,
                gpt_sections=["GPT_WF_OVERVIEW", "GPT_WF_MAP", "GPT_RECOMMENDATIONS"]
            )
        ],
        intake_fields=CLIENT_INFO_FIELDS + [
            IntakeFieldSchema(
                field_id="business_description",
                label="Business Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="Describe your business and what it does",
                order=20
            ),
            IntakeFieldSchema(
                field_id="current_process_overview",
                label="Current Process Overview",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="Describe your current key processes",
                order=21
            ),
            IntakeFieldSchema(
                field_id="goals_objectives",
                label="Goals & Objectives",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="What do you want to achieve with automation?",
                order=22
            ),
            IntakeFieldSchema(
                field_id="priority_goal",
                label="Priority Goal",
                field_type=IntakeFieldType.TEXT,
                required=True,
                help_text="What is your single most important goal?",
                order=23
            ),
            IntakeFieldSchema(
                field_id="team_size",
                label="Team Size",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["1-5", "6-20", "21-50", "51-100", "100+"],
                order=24
            ),
            IntakeFieldSchema(
                field_id="processes_to_focus",
                label="Processes to Focus On",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="Which specific processes should we analyse?",
                order=25
            ),
            IntakeFieldSchema(
                field_id="current_tools",
                label="Current Tools Used",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                help_text="List any software tools you currently use",
                order=26
            ),
            IntakeFieldSchema(
                field_id="main_challenges",
                label="Main Challenges",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="What are the biggest pain points in your current processes?",
                order=27
            ),
            IntakeFieldSchema(
                field_id="additional_notes",
                label="Additional Notes",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=28
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="AI_WF_BLUEPRINT_MASTER",
        gpt_sections=["GPT_WF_OVERVIEW", "GPT_WF_MAP", "GPT_RECOMMENDATIONS"],
        review_required=True,
        active=True,
        display_order=10,
        tags=["automation", "workflow", "ai", "efficiency"]
    ),
    
    # Business Process Mapping - £129
    ServiceCatalogueEntryV2(
        service_code="AI_PROC_MAP",
        service_name="Business Process Mapping",
        description="Detailed workflow mapping to identify inefficiencies, compliance gaps, and automation opportunities before implementation.",
        long_description="""Our Business Process Mapping service provides a detailed visual and narrative mapping of your 
        business workflows. We identify inefficiencies, compliance gaps, and automation opportunities, giving you clear 
        As-Is and To-Be process flows with actionable recommendations.""",
        category=ServiceCategory.AI_AUTOMATION,
        website_preview="Detailed workflow mapping to identify inefficiencies, compliance gaps, and automation opportunities before implementation.",
        learn_more_slug="business-process-mapping",
        pricing_model=PricingModel.ONE_TIME,
        base_price=12900,  # £129
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=12900,
                stripe_price_id="price_AI_PROC_MAP_std",
                target_due_hours=48
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=14900,
                stripe_price_id="price_AI_PROC_MAP_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        delivery_type=DeliveryType.DIGITAL,
        standard_turnaround_hours=48,
        workflow_name="wf_ai_process",
        documents_generated=[
            DocumentTemplate(
                template_code="ai_process_map_template",
                template_name="Business Process Map",
                format="pdf",
                generation_order=1,
                gpt_sections=["GPT_PROC_MAP", "GPT_ISSUES", "GPT_OPTIMISATIONS"]
            )
        ],
        intake_fields=CLIENT_INFO_FIELDS + [
            IntakeFieldSchema(
                field_id="business_description",
                label="Business Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=20
            ),
            IntakeFieldSchema(
                field_id="current_process_overview",
                label="Current Process Overview",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=21
            ),
            IntakeFieldSchema(
                field_id="goals_objectives",
                label="Goals & Objectives",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=22
            ),
            IntakeFieldSchema(
                field_id="current_tools",
                label="Current Tools Used",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=23
            ),
            IntakeFieldSchema(
                field_id="main_challenges",
                label="Main Challenges",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=24
            ),
            IntakeFieldSchema(
                field_id="priority_goal",
                label="Priority Goal",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=25
            ),
            IntakeFieldSchema(
                field_id="team_size",
                label="Team Size",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["1-5", "6-20", "21-50", "51-100", "100+"],
                order=26
            ),
            IntakeFieldSchema(
                field_id="single_process_name",
                label="Process Name to Map",
                field_type=IntakeFieldType.TEXT,
                required=True,
                help_text="Name of the specific process to map",
                order=27
            ),
            IntakeFieldSchema(
                field_id="process_steps_description",
                label="Process Steps Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="Describe the steps in this process as you currently perform them",
                order=28
            ),
            IntakeFieldSchema(
                field_id="additional_notes",
                label="Additional Notes",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=29
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="AI_PROC_MAP_MASTER",
        gpt_sections=["GPT_PROC_MAP", "GPT_ISSUES", "GPT_OPTIMISATIONS"],
        review_required=True,
        active=True,
        display_order=11,
        tags=["process", "mapping", "workflow", "efficiency"]
    ),
    
    # AI Tool Recommendation Report - £59
    ServiceCatalogueEntryV2(
        service_code="AI_TOOLS",
        service_name="AI Tool Recommendation Report",
        description="Objective assessment of AI tools matched to operational requirements, budget constraints, and integration capabilities.",
        long_description="""Our AI Tool Recommendation Report provides an objective, vendor-neutral assessment of AI and 
        automation tools suited to your specific needs. We analyse your requirements, budget, and technical constraints 
        to recommend the best tools with clear comparison tables and implementation guidance.""",
        category=ServiceCategory.AI_AUTOMATION,
        website_preview="Objective assessment of AI tools matched to operational requirements, budget constraints, and integration capabilities.",
        learn_more_slug="ai-tool-recommendation",
        pricing_model=PricingModel.ONE_TIME,
        base_price=5900,  # £59
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=5900,
                stripe_price_id="price_AI_TOOLS_std",
                target_due_hours=48
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=7900,
                stripe_price_id="price_AI_TOOLS_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        delivery_type=DeliveryType.DIGITAL,
        standard_turnaround_hours=48,
        workflow_name="wf_ai_tools",
        documents_generated=[
            DocumentTemplate(
                template_code="ai_tool_recommend_template",
                template_name="AI Tool Recommendations",
                format="pdf",
                generation_order=1,
                gpt_sections=["GPT_TOOL_LIST", "GPT_COMPARISON_TABLE", "GPT_RECOMMENDATION"]
            )
        ],
        intake_fields=CLIENT_INFO_FIELDS + [
            IntakeFieldSchema(
                field_id="business_description",
                label="Business Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=20
            ),
            IntakeFieldSchema(
                field_id="current_process_overview",
                label="Current Process Overview",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=21
            ),
            IntakeFieldSchema(
                field_id="goals_objectives",
                label="Goals & Objectives",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=22
            ),
            IntakeFieldSchema(
                field_id="business_overview",
                label="Business Overview",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=23
            ),
            IntakeFieldSchema(
                field_id="current_tools",
                label="Current Tools Used",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                help_text="List any software tools you currently use",
                order=24
            ),
            IntakeFieldSchema(
                field_id="main_challenges",
                label="Main Challenges",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=25
            ),
            IntakeFieldSchema(
                field_id="priority_goal",
                label="Priority Goal",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=26
            ),
            IntakeFieldSchema(
                field_id="team_size",
                label="Team Size",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["1-5", "6-20", "21-50", "51-100", "100+"],
                order=27
            ),
            IntakeFieldSchema(
                field_id="tool_budget_range",
                label="Monthly Tool Budget",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Under £100", "£100-500", "£500-1000", "£1000+"],
                order=28
            ),
            IntakeFieldSchema(
                field_id="technical_preference",
                label="Technical Preference",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["No-code only", "Mixed (some technical)", "Technical solutions welcome"],
                order=29
            ),
            IntakeFieldSchema(
                field_id="additional_notes",
                label="Additional Notes",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=30
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="AI_TOOLS_MASTER",
        gpt_sections=["GPT_TOOL_LIST", "GPT_COMPARISON_TABLE", "GPT_RECOMMENDATION"],
        review_required=True,
        active=True,
        display_order=12,
        tags=["ai", "tools", "recommendation", "software"]
    ),
]


# ============================================================================
# MARKET RESEARCH SERVICES
# ============================================================================

MARKET_RESEARCH_SERVICES = [
    # Market Research - Basic - £69
    ServiceCatalogueEntryV2(
        service_code="MR_BASIC",
        service_name="Market Research – Basic",
        description="Concise market overview with competitor insights and high-level trends for early-stage decision-making.",
        long_description="""Our Basic Market Research provides a clear, professional overview of your target market. 
        Includes market overview, target segment analysis, key findings, competitor overview, and strategic summary. 
        Written for decision-makers who need directional insights without complex data tables.""",
        category=ServiceCategory.MARKET_RESEARCH,
        website_preview="Concise market overview with competitor insights and high-level trends for early-stage decision-making.",
        learn_more_slug="market-research-basic",
        pricing_model=PricingModel.ONE_TIME,
        base_price=6900,  # £69
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=6900,
                stripe_price_id="price_MR_BASIC_std",
                target_due_hours=48
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=8900,
                stripe_price_id="price_MR_BASIC_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        delivery_type=DeliveryType.DIGITAL,
        standard_turnaround_hours=48,
        workflow_name="wf_mr_basic",
        documents_generated=[
            DocumentTemplate(
                template_code="mr_basic_template",
                template_name="Market Research Report (Basic)",
                format="pdf",
                generation_order=1,
                gpt_sections=["GPT_OVERVIEW", "GPT_COMP_TABLE", "GPT_FINDINGS"]
            )
        ],
        intake_fields=CLIENT_INFO_FIELDS + [
            IntakeFieldSchema(
                field_id="business_description",
                label="Business Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=20
            ),
            IntakeFieldSchema(
                field_id="target_industry",
                label="Target Industry",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=21
            ),
            IntakeFieldSchema(
                field_id="target_region",
                label="Target Region",
                field_type=IntakeFieldType.TEXT,
                required=True,
                help_text="e.g., UK, London, North West England",
                order=22
            ),
            IntakeFieldSchema(
                field_id="target_audience_description",
                label="Target Audience Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="Describe your ideal customer",
                order=23
            ),
            IntakeFieldSchema(
                field_id="offer_description",
                label="Your Offer/Product Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=24
            ),
            IntakeFieldSchema(
                field_id="main_research_question",
                label="Main Research Question",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="What is the key question you want answered?",
                order=25
            ),
            IntakeFieldSchema(
                field_id="known_competitors",
                label="Known Competitors",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                help_text="List any competitors you're aware of",
                order=26
            ),
            IntakeFieldSchema(
                field_id="additional_notes",
                label="Additional Notes",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=27
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="MR_BASIC_MASTER",
        gpt_sections=["GPT_OVERVIEW", "GPT_COMP_TABLE", "GPT_FINDINGS"],
        review_required=True,
        active=True,
        display_order=20,
        tags=["market", "research", "competitors", "analysis"]
    ),
    
    # Market Research - Advanced - £149
    ServiceCatalogueEntryV2(
        service_code="MR_ADV",
        service_name="Market Research – Advanced",
        description="Comprehensive research report covering market size, pricing analysis, competitor positioning, and structured findings.",
        long_description="""Our Advanced Market Research is a premium, enterprise-grade report for serious decision-makers. 
        Includes executive summary, market data tables, detailed competitor analysis, SWOT analysis, pricing insights, 
        trends and forecasts, and actionable recommendations. Suitable for investor presentations and strategic planning.""",
        category=ServiceCategory.MARKET_RESEARCH,
        website_preview="Comprehensive research report covering market size, pricing analysis, competitor positioning, and structured findings.",
        learn_more_slug="market-research-advanced",
        pricing_model=PricingModel.ONE_TIME,
        base_price=14900,  # £149
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=14900,
                stripe_price_id="price_MR_ADV_std",
                target_due_hours=48
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=16900,
                stripe_price_id="price_MR_ADV_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        delivery_type=DeliveryType.DIGITAL,
        standard_turnaround_hours=48,
        workflow_name="wf_mr_advanced",
        documents_generated=[
            DocumentTemplate(
                template_code="mr_advanced_template",
                template_name="Market Research Report (Advanced)",
                format="pdf",
                generation_order=1,
                gpt_sections=["GPT_OVERVIEW", "GPT_COMP_TABLE", "GPT_SWOT", "GPT_PRICING", "GPT_TRENDS", "GPT_CHARTS"]
            )
        ],
        intake_fields=CLIENT_INFO_FIELDS + [
            IntakeFieldSchema(
                field_id="business_description",
                label="Business Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=20
            ),
            IntakeFieldSchema(
                field_id="target_industry",
                label="Target Industry",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=21
            ),
            IntakeFieldSchema(
                field_id="target_region",
                label="Target Region",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=22
            ),
            IntakeFieldSchema(
                field_id="target_audience_description",
                label="Target Audience Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=23
            ),
            IntakeFieldSchema(
                field_id="offer_description",
                label="Your Offer/Product Description",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=24
            ),
            IntakeFieldSchema(
                field_id="main_research_question",
                label="Main Research Question",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=25
            ),
            IntakeFieldSchema(
                field_id="known_competitors",
                label="Known Competitors",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=26
            ),
            IntakeFieldSchema(
                field_id="pricing_intent",
                label="Pricing Intent",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Premium positioning", "Mid-market", "Value/budget", "Undecided"],
                order=27
            ),
            IntakeFieldSchema(
                field_id="time_horizon",
                label="Time Horizon",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["1-3 months", "3-6 months", "6-12 months", "1-2 years", "2+ years"],
                order=28
            ),
            IntakeFieldSchema(
                field_id="additional_notes",
                label="Additional Notes",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=29
            ),
        ],
        generation_mode=GenerationMode.GPT_FULL,
        master_prompt_id="MR_ADV_MASTER",
        gpt_sections=["GPT_EXEC_SUMMARY", "GPT_MARKET_DATA_TABLES", "GPT_COMPETITOR_ANALYSIS", 
                      "GPT_SWOT_ANALYSIS", "GPT_PRICING_INSIGHTS", "GPT_TRENDS_AND_FORECASTS",
                      "GPT_INSIGHTS_AND_RECOMMENDATIONS"],
        review_required=True,
        active=True,
        display_order=21,
        tags=["market", "research", "advanced", "swot", "competitors"]
    ),
]


# ============================================================================
# COMPLIANCE SERVICES
# ============================================================================

COMPLIANCE_SERVICES = [
    # HMO Compliance Audit - £79
    ServiceCatalogueEntryV2(
        service_code="COMP_HMO",
        service_name="HMO Compliance Audit",
        description="Structured audit assessing HMO documentation, safety requirements, and licensing obligations against current regulations.",
        long_description="""Our HMO Compliance Audit provides a professional assessment of your House in Multiple Occupation 
        against current UK regulations. Covers licensing requirements, safety certificates, management responsibilities, 
        and provides a prioritised remediation plan. Suitable for landlord records and advisor review.""",
        category=ServiceCategory.COMPLIANCE,
        website_preview="Structured audit assessing HMO documentation, safety requirements, and licensing obligations against current regulations.",
        learn_more_slug="hmo-compliance-audit",
        pricing_model=PricingModel.ONE_TIME,
        base_price=7900,  # £79
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=7900,
                stripe_price_id="price_COMP_HMO_std",
                target_due_hours=72
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=9900,
                stripe_price_id="price_COMP_HMO_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        delivery_type=DeliveryType.DIGITAL,
        standard_turnaround_hours=72,
        workflow_name="wf_comp_hmo",
        documents_generated=[
            DocumentTemplate(
                template_code="comp_hmo_audit_template",
                template_name="HMO Compliance Audit Report",
                format="pdf",
                generation_order=1,
                gpt_sections=["GPT_RISK_SUMMARY", "GPT_HMO_NOTES"]
            )
        ],
        intake_fields=CLIENT_INFO_FIELDS + PROPERTY_FIELDS + [
            IntakeFieldSchema(
                field_id="hmo_number_of_occupants",
                label="Number of Occupants",
                field_type=IntakeFieldType.NUMBER,
                required=True,
                order=30
            ),
            IntakeFieldSchema(
                field_id="current_hmo_licence_status",
                label="Current HMO Licence Status",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Licensed", "Application Pending", "Not Licensed", "Unsure"],
                order=31
            ),
            IntakeFieldSchema(
                field_id="licence_required",
                label="Is HMO Licence Required?",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Yes", "No", "Unsure"],
                order=32
            ),
            IntakeFieldSchema(
                field_id="managing_agent_involved",
                label="Managing Agent Involved?",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Yes", "No"],
                order=33
            ),
            IntakeFieldSchema(
                field_id="current_certificates_list",
                label="Current Certificates Held",
                field_type=IntakeFieldType.MULTI_SELECT,
                required=False,
                options=["Gas Safety", "EICR", "EPC", "Fire Risk Assessment", "None"],
                order=34
            ),
            IntakeFieldSchema(
                field_id="hmo_certificate_status_notes",
                label="Certificate Status Notes",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                help_text="Any notes about certificate expiry or issues",
                order=35
            ),
            IntakeFieldSchema(
                field_id="hmo_known_issues",
                label="Known Issues or Council Contacts",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                order=36
            ),
            IntakeFieldSchema(
                field_id="top_three_concerns",
                label="Top Three Concerns",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="What are your three biggest compliance concerns?",
                order=37
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="COMP_HMO_MASTER",
        gpt_sections=["GPT_HMO_STATUS", "GPT_COMPLIANCE_GAPS", "GPT_REQUIRED_ACTIONS"],
        review_required=True,
        active=True,
        display_order=30,
        tags=["hmo", "compliance", "audit", "licensing"]
    ),
    
    # Full Compliance Audit Report - £99
    ServiceCatalogueEntryV2(
        service_code="COMP_FULL_AUDIT",
        service_name="Full Compliance Audit Report",
        description="Comprehensive compliance review covering certificates, licensing, documentation, deposits, notices, and regulatory risk areas.",
        long_description="""Our Full Compliance Audit provides a comprehensive review of your property's compliance status 
        across all regulatory areas. Covers gas safety, electrical safety, EPC, smoke and carbon monoxide regulations, 
        licensing, deposit protection, right to rent, and management responsibilities. Includes prioritised remediation plan.""",
        category=ServiceCategory.COMPLIANCE,
        website_preview="Comprehensive compliance review covering certificates, licensing, documentation, deposits, notices, and regulatory risk areas.",
        learn_more_slug="full-compliance-audit",
        pricing_model=PricingModel.ONE_TIME,
        base_price=9900,  # £99
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=9900,
                stripe_price_id="price_COMP_FULL_AUDIT_std",
                target_due_hours=72
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=11900,
                stripe_price_id="price_COMP_FULL_AUDIT_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        delivery_type=DeliveryType.DIGITAL,
        standard_turnaround_hours=72,
        workflow_name="wf_comp_full_audit",
        documents_generated=[
            DocumentTemplate(
                template_code="comp_full_audit_template",
                template_name="Full Compliance Audit Report",
                format="pdf",
                generation_order=1,
                gpt_sections=["GPT_COMPLIANCE_OVERVIEW", "GPT_RISK_RATING", "GPT_NON_COMPLIANCE_SUMMARY", "GPT_REQUIRED_ACTIONS"]
            )
        ],
        intake_fields=CLIENT_INFO_FIELDS + PROPERTY_FIELDS + [
            IntakeFieldSchema(
                field_id="number_of_properties_owned",
                label="Number of Properties Owned",
                field_type=IntakeFieldType.NUMBER,
                required=True,
                order=30
            ),
            IntakeFieldSchema(
                field_id="portfolio_scope",
                label="Portfolio Scope",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Single Property", "Multiple Properties"],
                order=31
            ),
            IntakeFieldSchema(
                field_id="licence_required",
                label="Licence Required?",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Yes", "No", "Unsure"],
                order=32
            ),
            IntakeFieldSchema(
                field_id="managing_agent_involved",
                label="Managing Agent Involved?",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Yes", "No"],
                order=33
            ),
            IntakeFieldSchema(
                field_id="tenancy_type",
                label="Tenancy Type",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["AST", "Contractual", "Company Let", "Other"],
                order=34
            ),
            IntakeFieldSchema(
                field_id="deposit_scheme_used",
                label="Deposit Scheme Used",
                field_type=IntakeFieldType.TEXT,
                required=False,
                help_text="e.g., DPS, TDS, MyDeposits",
                order=35
            ),
            IntakeFieldSchema(
                field_id="current_certificates_list",
                label="Current Certificates",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                help_text="List certificates held with expiry dates",
                order=36
            ),
            IntakeFieldSchema(
                field_id="top_three_concerns",
                label="Top Three Concerns",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=37
            ),
        ],
        generation_mode=GenerationMode.GPT_FULL,
        master_prompt_id="COMP_FULL_AUDIT_MASTER",
        gpt_sections=["GPT_COMPLIANCE_OVERVIEW", "GPT_RISK_RATING", "GPT_NON_COMPLIANCE_SUMMARY", "GPT_REQUIRED_ACTIONS"],
        review_required=True,
        active=True,
        display_order=31,
        tags=["compliance", "audit", "full", "certificates"]
    ),
    
    # Move-In / Move-Out Checklist - £35
    ServiceCatalogueEntryV2(
        service_code="COMP_MOVEOUT",
        service_name="Move-In / Move-Out Checklist",
        description="Structured digital checklist documenting property condition at tenancy start and end to reduce deposit disputes.",
        long_description="""Our Move-In/Move-Out Checklist provides a structured digital document for recording property 
        condition at tenancy start and end. Helps reduce deposit disputes by providing clear, dated evidence of property 
        condition. Suitable for landlords, agents, and dispute resolution preparation.""",
        category=ServiceCategory.COMPLIANCE,
        website_preview="Structured digital checklist documenting property condition at tenancy start and end to reduce deposit disputes.",
        learn_more_slug="move-in-move-out-checklist",
        pricing_model=PricingModel.ONE_TIME,
        base_price=3500,  # £35
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=3500,
                stripe_price_id="price_COMP_MOVEOUT_std",
                target_due_hours=72
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=5500,
                stripe_price_id="price_COMP_MOVEOUT_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        delivery_type=DeliveryType.DIGITAL,
        standard_turnaround_hours=72,
        workflow_name="wf_comp_moveout",
        documents_generated=[
            DocumentTemplate(
                template_code="comp_movein_moveout_template",
                template_name="Move-In/Move-Out Checklist",
                format="pdf",
                generation_order=1,
                gpt_sections=["GPT_SUMMARY_NOTES"]
            )
        ],
        intake_fields=CLIENT_INFO_FIELDS + PROPERTY_FIELDS + [
            IntakeFieldSchema(
                field_id="tenancy_start_date",
                label="Tenancy Start Date",
                field_type=IntakeFieldType.DATE,
                required=True,
                order=30
            ),
            IntakeFieldSchema(
                field_id="tenancy_end_date",
                label="Tenancy End Date",
                field_type=IntakeFieldType.DATE,
                required=False,
                help_text="Leave blank if ongoing",
                order=31
            ),
            IntakeFieldSchema(
                field_id="tenant_full_name",
                label="Tenant Full Name",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=32
            ),
            IntakeFieldSchema(
                field_id="property_furnished",
                label="Property Furnished?",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Furnished", "Part-Furnished", "Unfurnished"],
                order=33
            ),
            IntakeFieldSchema(
                field_id="licence_required",
                label="Licence Required?",
                field_type=IntakeFieldType.SELECT,
                required=False,
                options=["Yes", "No", "Unsure"],
                order=34
            ),
            IntakeFieldSchema(
                field_id="managing_agent_involved",
                label="Managing Agent Involved?",
                field_type=IntakeFieldType.SELECT,
                required=False,
                options=["Yes", "No"],
                order=35
            ),
            IntakeFieldSchema(
                field_id="special_areas_to_note",
                label="Special Areas to Note",
                field_type=IntakeFieldType.TEXTAREA,
                required=False,
                help_text="Any specific areas to pay attention to",
                order=36
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="COMP_MOVEOUT_MASTER",
        gpt_sections=["GPT_MOVE_IN_CHECKLIST", "GPT_MOVE_OUT_CHECKLIST"],
        review_required=True,
        active=True,
        display_order=32,
        tags=["move-in", "move-out", "checklist", "inventory"]
    ),
]


# ============================================================================
# DOCUMENT PACKS (with Hierarchy)
# ============================================================================

DOCUMENT_PACK_SERVICES = [
    # Essential Landlord Document Pack - £29
    ServiceCatalogueEntryV2(
        service_code="DOC_PACK_ESSENTIAL",
        service_name="Essential Landlord Document Pack",
        description="Core landlord forms and notices automatically generated from structured inputs, covering essential tenancy documentation.",
        long_description="""The Essential Landlord Document Pack provides core landlord forms and notices. Documents are 
        generated using controlled templates and populated with your submitted information. Includes rent arrears letter, 
        deposit refund/explanation letter, tenant reference letter, rent receipt template, and GDPR notice.""",
        category=ServiceCategory.DOCUMENT_PACK,
        website_preview="Core landlord forms and notices automatically generated from structured inputs, covering essential tenancy documentation.",
        learn_more_slug="essential-landlord-document-pack",
        pricing_model=PricingModel.ONE_TIME,
        base_price=2900,  # £29
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=2900,
                stripe_price_id="price_DOC_PACK_ESSENTIAL_std",
                target_due_hours=72
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=4900,
                stripe_price_id="price_DOC_PACK_ESSENTIAL_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
            PricingVariant(
                variant_code="printed",
                variant_name="Printed Copy (+£25)",
                price_amount=5400,
                stripe_price_id="price_DOC_PACK_ESSENTIAL_print",
                target_due_hours=72,
                is_addon=True,
                addon_type="delivery_format"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        printed_copy_available=True,
        printed_copy_price=2500,
        delivery_type=DeliveryType.DIGITAL_PRINTED,
        standard_turnaround_hours=72,
        workflow_name="wf_doc_pack_essential",
        pack_tier=PackTier.ESSENTIAL,
        includes_lower_tiers=False,
        documents_generated=[
            DocumentTemplate(
                template_code="doc_rent_arrears_letter_template",
                template_name="Rent Arrears Letter",
                format="docx",
                generation_order=1,
                gpt_sections=["GPT_ARREARS_REASON_PARAGRAPH"]
            ),
            DocumentTemplate(
                template_code="doc_deposit_refund_letter_template",
                template_name="Deposit Refund or Explanation Letter",
                format="docx",
                generation_order=2,
                gpt_sections=["GPT_DEPOSIT_EXPLANATION"]
            ),
            DocumentTemplate(
                template_code="doc_tenant_reference_letter_template",
                template_name="Tenant Reference Letter",
                format="docx",
                generation_order=3,
                gpt_sections=[]
            ),
            DocumentTemplate(
                template_code="doc_rent_receipt_template",
                template_name="Rent Receipt Template",
                format="docx",
                generation_order=4,
                gpt_sections=[]
            ),
            DocumentTemplate(
                template_code="doc_gdpr_notice_template",
                template_name="GDPR / Data Processing Notice",
                format="docx",
                generation_order=5,
                gpt_sections=[]
            ),
        ],
        intake_fields=[
            # Landlord details
            IntakeFieldSchema(
                field_id="landlord_name",
                label="Landlord Full Name",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=1
            ),
            IntakeFieldSchema(
                field_id="landlord_address",
                label="Landlord Address",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=2
            ),
            # Tenant details
            IntakeFieldSchema(
                field_id="doc_tenant_full_name",
                label="Tenant Full Name",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=3
            ),
            IntakeFieldSchema(
                field_id="tenant_address",
                label="Tenant/Property Address",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=4
            ),
            # Tenancy details
            IntakeFieldSchema(
                field_id="doc_tenancy_start_date",
                label="Tenancy Start Date",
                field_type=IntakeFieldType.DATE,
                required=True,
                order=5
            ),
            IntakeFieldSchema(
                field_id="current_rent_amount",
                label="Current Rent Amount (£)",
                field_type=IntakeFieldType.CURRENCY,
                required=True,
                order=6
            ),
            IntakeFieldSchema(
                field_id="rent_frequency",
                label="Rent Frequency",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Weekly", "Fortnightly", "Monthly", "Quarterly"],
                order=7
            ),
            # Document-specific fields
            IntakeFieldSchema(
                field_id="documents_required",
                label="Documents Required",
                field_type=IntakeFieldType.MULTI_SELECT,
                required=True,
                options=["Rent Arrears Letter", "Deposit Refund Letter", "Tenant Reference Letter", "Rent Receipt", "GDPR Notice"],
                help_text="Select which documents you need",
                order=8
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="DOC_PACK_ESSENTIAL_ORCHESTRATOR",
        gpt_sections=["GPT_ARREARS_REASON_PARAGRAPH", "GPT_DEPOSIT_EXPLANATION"],
        review_required=True,
        active=True,
        display_order=40,
        tags=["documents", "landlord", "essential", "templates"]
    ),
    
    # Tenancy Legal & Notices Pack - £49
    ServiceCatalogueEntryV2(
        service_code="DOC_PACK_PLUS",
        service_name="Tenancy Legal & Notices Pack",
        description="Tenancy agreements, legal notices, and guarantor documents prepared using controlled templates and automated generation.",
        long_description="""The Tenancy Legal & Notices Pack provides tenancy agreements and legal notices. Includes 
        AST agreement, PRT agreement (where applicable), tenancy renewal document, notice to quit, rent increase notice, 
        and guarantor agreement. All documents generated using controlled templates.""",
        category=ServiceCategory.DOCUMENT_PACK,
        website_preview="Tenancy agreements, legal notices, and guarantor documents prepared using controlled templates and automated generation.",
        learn_more_slug="tenancy-legal-notices-pack",
        pricing_model=PricingModel.ONE_TIME,
        base_price=4900,  # £49
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=4900,
                stripe_price_id="price_DOC_PACK_PLUS_std",
                target_due_hours=72
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=6900,
                stripe_price_id="price_DOC_PACK_PLUS_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
            PricingVariant(
                variant_code="printed",
                variant_name="Printed Copy (+£25)",
                price_amount=7400,
                stripe_price_id="price_DOC_PACK_PLUS_print",
                target_due_hours=72,
                is_addon=True,
                addon_type="delivery_format"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        printed_copy_available=True,
        printed_copy_price=2500,
        delivery_type=DeliveryType.DIGITAL_PRINTED,
        standard_turnaround_hours=72,
        workflow_name="wf_doc_pack_plus",
        pack_tier=PackTier.PLUS,
        includes_lower_tiers=True,
        parent_pack_code="DOC_PACK_ESSENTIAL",
        documents_generated=[
            DocumentTemplate(
                template_code="doc_tenancy_agreement_ast_template",
                template_name="Assured Shorthold Tenancy (AST) Agreement",
                format="docx",
                generation_order=1,
                gpt_sections=["GPT_CUSTOM_CLAUSE_SUMMARY"]
            ),
            DocumentTemplate(
                template_code="doc_tenancy_agreement_prt_template",
                template_name="Private Residential Tenancy (PRT) Agreement",
                format="docx",
                generation_order=2,
                gpt_sections=[]
            ),
            DocumentTemplate(
                template_code="doc_tenancy_renewal_template",
                template_name="Tenancy Renewal or Extension Document",
                format="docx",
                generation_order=3,
                gpt_sections=[]
            ),
            DocumentTemplate(
                template_code="doc_notice_quit_template",
                template_name="Notice to Quit",
                format="docx",
                generation_order=4,
                gpt_sections=["GPT_NOTICE_REASON"]
            ),
            DocumentTemplate(
                template_code="doc_rent_increase_notice_template",
                template_name="Rent Increase Notice",
                format="docx",
                generation_order=5,
                gpt_sections=[]
            ),
            DocumentTemplate(
                template_code="doc_guarantor_agreement_template",
                template_name="Guarantor Agreement",
                format="docx",
                generation_order=6,
                gpt_sections=[]
            ),
        ],
        intake_fields=[
            # Landlord details
            IntakeFieldSchema(
                field_id="landlord_name",
                label="Landlord Full Name",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=1
            ),
            IntakeFieldSchema(
                field_id="landlord_address",
                label="Landlord Address",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=2
            ),
            # Tenant details
            IntakeFieldSchema(
                field_id="doc_tenant_full_name",
                label="Tenant Full Name",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=3
            ),
            IntakeFieldSchema(
                field_id="tenant_address",
                label="Tenant/Property Address",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=4
            ),
            # Property details
            IntakeFieldSchema(
                field_id="property_address_line1",
                label="Property Address Line 1",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=5
            ),
            IntakeFieldSchema(
                field_id="property_postcode",
                label="Property Postcode",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=6
            ),
            # Tenancy details
            IntakeFieldSchema(
                field_id="doc_tenancy_start_date",
                label="Tenancy Start Date",
                field_type=IntakeFieldType.DATE,
                required=True,
                order=7
            ),
            IntakeFieldSchema(
                field_id="current_rent_amount",
                label="Current Rent Amount (£)",
                field_type=IntakeFieldType.CURRENCY,
                required=True,
                order=8
            ),
            IntakeFieldSchema(
                field_id="rent_frequency",
                label="Rent Frequency",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Weekly", "Fortnightly", "Monthly", "Quarterly"],
                order=9
            ),
            IntakeFieldSchema(
                field_id="country_region",
                label="Country/Region",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["England", "Wales", "Scotland", "Northern Ireland"],
                help_text="Determines which tenancy type applies",
                order=10
            ),
            # Document selection
            IntakeFieldSchema(
                field_id="documents_required",
                label="Documents Required",
                field_type=IntakeFieldType.MULTI_SELECT,
                required=True,
                options=["AST Agreement", "PRT Agreement", "Tenancy Renewal", "Notice to Quit", "Rent Increase Notice", "Guarantor Agreement"],
                order=11
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="DOC_PACK_PLUS_ORCHESTRATOR",
        gpt_sections=["GPT_NOTICE_REASON", "GPT_CUSTOM_CLAUSE_SUMMARY"],
        review_required=True,
        active=True,
        display_order=41,
        tags=["documents", "tenancy", "legal", "notices"]
    ),
    
    # Ultimate Landlord Document Pack - £79
    ServiceCatalogueEntryV2(
        service_code="DOC_PACK_PRO",
        service_name="Ultimate Landlord Document Pack",
        description="Comprehensive landlord documentation covering all core tenancy documents plus compliance-related forms for full operational coverage.",
        long_description="""The Ultimate Landlord Document Pack is our comprehensive bundle including all documents from 
        the Essential and Tenancy packs, plus additional supporting records: inventory and condition record template, 
        deposit information pack, property access notice, and additional landlord notices. Complete operational coverage.""",
        category=ServiceCategory.DOCUMENT_PACK,
        website_preview="Comprehensive landlord documentation covering all core tenancy documents plus compliance-related forms for full operational coverage.",
        learn_more_slug="ultimate-landlord-document-pack",
        pricing_model=PricingModel.ONE_TIME,
        base_price=7900,  # £79
        pricing_variants=[
            PricingVariant(
                variant_code="standard",
                variant_name="Standard",
                price_amount=7900,
                stripe_price_id="price_DOC_PACK_PRO_std",
                target_due_hours=72
            ),
            PricingVariant(
                variant_code="fast_track",
                variant_name="Fast Track (+£20)",
                price_amount=9900,
                stripe_price_id="price_DOC_PACK_PRO_ft",
                target_due_hours=24,
                is_addon=True,
                addon_type="delivery_speed"
            ),
            PricingVariant(
                variant_code="printed",
                variant_name="Printed Copy (+£25)",
                price_amount=10400,
                stripe_price_id="price_DOC_PACK_PRO_print",
                target_due_hours=72,
                is_addon=True,
                addon_type="delivery_format"
            ),
        ],
        fast_track_available=True,
        fast_track_price=2000,
        fast_track_hours=24,
        printed_copy_available=True,
        printed_copy_price=2500,
        delivery_type=DeliveryType.DIGITAL_PRINTED,
        standard_turnaround_hours=72,
        workflow_name="wf_doc_pack_pro",
        pack_tier=PackTier.PRO,
        includes_lower_tiers=True,
        parent_pack_code="DOC_PACK_PLUS",
        documents_generated=[
            DocumentTemplate(
                template_code="doc_inventory_condition_template",
                template_name="Inventory and Condition Record",
                format="docx",
                generation_order=1,
                gpt_sections=["GPT_INVENTORY_SUMMARY"]
            ),
            DocumentTemplate(
                template_code="doc_deposit_info_pack_template",
                template_name="Deposit Information Pack",
                format="docx",
                generation_order=2,
                gpt_sections=["GPT_DEPOSIT_EXPLANATION"]
            ),
            DocumentTemplate(
                template_code="doc_property_access_notice_template",
                template_name="Property Access Notice",
                format="docx",
                generation_order=3,
                gpt_sections=["GPT_ACCESS_REASON_PARAGRAPH"]
            ),
            DocumentTemplate(
                template_code="doc_additional_notice_template",
                template_name="Additional Landlord Notice",
                format="docx",
                generation_order=4,
                gpt_sections=["GPT_NOTICE_REASON"]
            ),
        ],
        intake_fields=[
            # Landlord details
            IntakeFieldSchema(
                field_id="landlord_name",
                label="Landlord Full Name",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=1
            ),
            IntakeFieldSchema(
                field_id="landlord_address",
                label="Landlord Address",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=2
            ),
            # Tenant details
            IntakeFieldSchema(
                field_id="doc_tenant_full_name",
                label="Tenant Full Name",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=3
            ),
            IntakeFieldSchema(
                field_id="tenant_address",
                label="Tenant/Property Address",
                field_type=IntakeFieldType.TEXTAREA,
                required=True,
                order=4
            ),
            # Property details
            IntakeFieldSchema(
                field_id="property_address_line1",
                label="Property Address Line 1",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=5
            ),
            IntakeFieldSchema(
                field_id="property_address_line2",
                label="Property Address Line 2",
                field_type=IntakeFieldType.TEXT,
                required=False,
                order=6
            ),
            IntakeFieldSchema(
                field_id="property_town_city",
                label="Town/City",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=7
            ),
            IntakeFieldSchema(
                field_id="property_postcode",
                label="Postcode",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=8
            ),
            IntakeFieldSchema(
                field_id="number_of_bedrooms",
                label="Number of Bedrooms",
                field_type=IntakeFieldType.NUMBER,
                required=True,
                order=9
            ),
            IntakeFieldSchema(
                field_id="country_region",
                label="Country/Region",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["England", "Wales", "Scotland", "Northern Ireland"],
                order=10
            ),
            # Tenancy details
            IntakeFieldSchema(
                field_id="doc_tenancy_start_date",
                label="Tenancy Start Date",
                field_type=IntakeFieldType.DATE,
                required=True,
                order=11
            ),
            IntakeFieldSchema(
                field_id="current_rent_amount",
                label="Current Rent Amount (£)",
                field_type=IntakeFieldType.CURRENCY,
                required=True,
                order=12
            ),
            IntakeFieldSchema(
                field_id="rent_frequency",
                label="Rent Frequency",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Weekly", "Fortnightly", "Monthly", "Quarterly"],
                order=13
            ),
            # Document selection
            IntakeFieldSchema(
                field_id="documents_required",
                label="Documents Required",
                field_type=IntakeFieldType.MULTI_SELECT,
                required=True,
                options=[
                    "Inventory and Condition Record",
                    "Deposit Information Pack",
                    "Property Access Notice",
                    "Additional Landlord Notice",
                    "Include Essential Pack Documents",
                    "Include Tenancy Pack Documents"
                ],
                help_text="Select which documents you need from this pack",
                order=14
            ),
        ],
        generation_mode=GenerationMode.GPT_ENHANCED,
        master_prompt_id="DOC_PACK_PRO_ORCHESTRATOR",
        gpt_sections=["GPT_INVENTORY_SUMMARY", "GPT_ACCESS_REASON_PARAGRAPH", "GPT_NOTICE_REASON", "GPT_DEPOSIT_EXPLANATION"],
        review_required=True,
        active=True,
        display_order=42,
        tags=["documents", "landlord", "ultimate", "comprehensive"]
    ),
]


# ============================================================================
# CVP SUBSCRIPTION SERVICE
# ============================================================================

CVP_SUBSCRIPTION_SERVICES = [
    ServiceCatalogueEntryV2(
        service_code="CVP_SUBSCRIPTION",
        service_name="Compliance Vault Pro",
        description="Ongoing compliance management for UK landlords. Tracks certificate expiry dates, flags documentation gaps, and generates audit-ready compliance packs on demand.",
        long_description="""Compliance Vault Pro is our ongoing compliance management platform for UK landlords. 
        Tracks certificate expiry dates, flags documentation gaps, and generates audit-ready compliance packs on demand. 
        Includes Safety Certificate Tracking and Council Licence Reminder Setup.
        
        Available tiers:
        - Solo Landlord (£19/month + £49 setup): Up to 2 properties
        - Portfolio (£39/month + £79 setup): Up to 10 properties
        - Professional (£79/month + £149 setup): Up to 25 properties""",
        category=ServiceCategory.SUBSCRIPTION,
        website_preview="Ongoing compliance management for UK landlords. Tracks certificate expiry dates, flags documentation gaps, and generates audit-ready compliance packs on demand.",
        learn_more_slug="compliance-vault-pro",
        pricing_model=PricingModel.SUBSCRIPTION_MONTHLY,
        base_price=1900,  # £19/month (Solo tier base)
        product_type=ProductType.RECURRING,
        pricing_variants=[
            # Solo Landlord
            PricingVariant(
                variant_code="solo_monthly",
                variant_name="Solo Landlord (£19/month)",
                price_amount=1900,
                stripe_price_id="price_CVP_SOLO_monthly",
                target_due_hours=24
            ),
            PricingVariant(
                variant_code="solo_setup",
                variant_name="Solo Setup Fee (£49)",
                price_amount=4900,
                stripe_price_id="price_CVP_SOLO_setup",
                target_due_hours=24,
                is_addon=True,
                addon_type="setup_fee"
            ),
            # Portfolio
            PricingVariant(
                variant_code="portfolio_monthly",
                variant_name="Portfolio (£39/month)",
                price_amount=3900,
                stripe_price_id="price_CVP_PORTFOLIO_monthly",
                target_due_hours=24
            ),
            PricingVariant(
                variant_code="portfolio_setup",
                variant_name="Portfolio Setup Fee (£79)",
                price_amount=7900,
                stripe_price_id="price_CVP_PORTFOLIO_setup",
                target_due_hours=24,
                is_addon=True,
                addon_type="setup_fee"
            ),
            # Professional
            PricingVariant(
                variant_code="professional_monthly",
                variant_name="Professional (£79/month)",
                price_amount=7900,
                stripe_price_id="price_CVP_PROFESSIONAL_monthly",
                target_due_hours=24
            ),
            PricingVariant(
                variant_code="professional_setup",
                variant_name="Professional Setup Fee (£149)",
                price_amount=14900,
                stripe_price_id="price_CVP_PROFESSIONAL_setup",
                target_due_hours=24,
                is_addon=True,
                addon_type="setup_fee"
            ),
        ],
        delivery_type=DeliveryType.PORTAL,
        standard_turnaround_hours=24,
        workflow_name="wf_cvp_subscription",
        is_cvp_feature=True,
        requires_cvp_subscription=False,  # This IS the subscription
        documents_generated=[],  # CVP generates reports through separate endpoints
        intake_fields=[
            IntakeFieldSchema(
                field_id="client_full_name",
                label="Full Name",
                field_type=IntakeFieldType.TEXT,
                required=True,
                order=1
            ),
            IntakeFieldSchema(
                field_id="client_email",
                label="Email Address",
                field_type=IntakeFieldType.EMAIL,
                required=True,
                order=2
            ),
            IntakeFieldSchema(
                field_id="client_phone",
                label="Phone Number",
                field_type=IntakeFieldType.PHONE,
                required=True,
                order=3
            ),
            IntakeFieldSchema(
                field_id="subscription_tier",
                label="Subscription Tier",
                field_type=IntakeFieldType.SELECT,
                required=True,
                options=["Solo Landlord (up to 2 properties)", "Portfolio (up to 10 properties)", "Professional (up to 25 properties)"],
                order=4
            ),
            IntakeFieldSchema(
                field_id="number_of_properties",
                label="Number of Properties",
                field_type=IntakeFieldType.NUMBER,
                required=True,
                order=5
            ),
        ],
        generation_mode=GenerationMode.TEMPLATE_MERGE,
        review_required=False,
        active=True,
        display_order=50,
        tags=["cvp", "subscription", "compliance", "tracking"]
    ),
]


# ============================================================================
# SEED FUNCTION
# ============================================================================

ALL_SERVICES = (
    AI_AUTOMATION_SERVICES +
    MARKET_RESEARCH_SERVICES +
    COMPLIANCE_SERVICES +
    DOCUMENT_PACK_SERVICES +
    CVP_SUBSCRIPTION_SERVICES
)


async def seed_service_catalogue_v2():
    """
    Seed the service catalogue V2 with authoritative service definitions.
    Only creates services that don't already exist.
    """
    db = database.get_db()
    
    created_count = 0
    skipped_count = 0
    
    for service in ALL_SERVICES:
        existing = await db[service_catalogue_v2.COLLECTION].find_one(
            {"service_code": service.service_code}
        )
        
        if not existing:
            service.created_at = datetime.now(timezone.utc)
            service.updated_at = datetime.now(timezone.utc)
            service.created_by = "system"
            service.updated_by = "system"
            
            await db[service_catalogue_v2.COLLECTION].insert_one(service.to_dict())
            logger.info(f"Seeded service: {service.service_code}")
            created_count += 1
        else:
            logger.debug(f"Service already exists: {service.service_code}")
            skipped_count += 1
    
    # Create indexes
    await service_catalogue_v2.ensure_indexes()
    
    logger.info(f"Service catalogue V2 seeding complete: {created_count} created, {skipped_count} skipped")
    return {"created": created_count, "skipped": skipped_count}


async def clear_and_reseed_catalogue():
    """
    Clear and reseed the entire catalogue (use with caution!).
    For development/testing only.
    """
    db = database.get_db()
    
    # Drop collection
    await db[service_catalogue_v2.COLLECTION].drop()
    logger.warning("Service catalogue V2 collection dropped")
    
    # Reseed
    return await seed_service_catalogue_v2()
