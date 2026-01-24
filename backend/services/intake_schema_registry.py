"""
Intake Schema Registry - Service-specific intake field definitions.

This module defines all intake field schemas for non-CVP services.
Schemas are used for:
1. Frontend dynamic field rendering
2. Server-side validation
3. Admin management

Each service has a complete field definition with:
- field_key: Unique identifier
- label: Display label
- type: Field type (text, textarea, select, multi-select, etc.)
- required: Whether field is mandatory
- helper_text: Guidance for users
- placeholder: Example text
- validation: Validation rules
- visibility_conditions: Conditional display logic
- order: Display order
"""
from typing import Dict, List, Any, Optional
from enum import Enum
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# FIELD TYPES
# ============================================================================

class IntakeFieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    MULTI_TEXT = "multi_text"  # Multiple text inputs (add more)
    CHECKBOX = "checkbox"
    CHECKBOX_GROUP = "checkbox_group"
    DATE = "date"
    CURRENCY = "currency"
    ADDRESS = "address"  # Address group (line1, line2, city, postcode)
    FILE_UPLOAD = "file_upload"
    HIDDEN = "hidden"


# ============================================================================
# FIELD SCHEMA MODEL
# ============================================================================

class IntakeField(BaseModel):
    """Single intake field definition."""
    field_key: str
    label: str
    type: IntakeFieldType
    required: bool = False
    helper_text: Optional[str] = None
    placeholder: Optional[str] = None
    options: Optional[List[str]] = None  # For select/multi-select
    default_value: Optional[Any] = None
    validation: Optional[Dict[str, Any]] = None  # min, max, pattern, etc.
    visibility_conditions: Optional[List[Dict[str, Any]]] = None  # [{field: value}]
    order: int = 0
    group: Optional[str] = None  # For grouping related fields
    max_items: Optional[int] = None  # For multi_text/multi_select


# ============================================================================
# UNIVERSAL CLIENT IDENTITY FIELDS (Every Service)
# ============================================================================

UNIVERSAL_CLIENT_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="full_name",
        label="Full Name",
        type=IntakeFieldType.TEXT,
        required=True,
        placeholder="John Smith",
        order=1,
        group="client_identity"
    ),
    IntakeField(
        field_key="email",
        label="Email Address",
        type=IntakeFieldType.EMAIL,
        required=True,
        placeholder="john@example.com",
        order=2,
        group="client_identity"
    ),
    IntakeField(
        field_key="phone",
        label="Phone Number",
        type=IntakeFieldType.PHONE,
        required=True,
        placeholder="+44 7xxx xxxxxx",
        order=3,
        group="client_identity"
    ),
    IntakeField(
        field_key="role",
        label="Your Role",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Landlord", "Business Owner", "Manager", "Other"],
        order=4,
        group="client_identity"
    ),
    IntakeField(
        field_key="role_other_text",
        label="Please specify your role",
        type=IntakeFieldType.TEXT,
        required=True,  # Required when role=Other
        placeholder="e.g., Consultant, Investor",
        visibility_conditions=[{"field": "role", "value": "Other"}],
        order=5,
        group="client_identity"
    ),
    IntakeField(
        field_key="company_name",
        label="Company Name",
        type=IntakeFieldType.TEXT,
        required=False,
        placeholder="Acme Properties Ltd",
        order=6,
        group="client_identity"
    ),
    IntakeField(
        field_key="company_website",
        label="Company Website",
        type=IntakeFieldType.TEXT,
        required=False,
        placeholder="https://www.example.com",
        order=7,
        group="client_identity"
    ),
]


# ============================================================================
# UNIVERSAL DELIVERY & CONSENT FIELDS (Every Service)
# ============================================================================

UNIVERSAL_DELIVERY_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="preferred_delivery_email",
        label="Delivery Email",
        type=IntakeFieldType.EMAIL,
        required=False,
        helper_text="Leave blank to use your account email",
        placeholder="delivery@example.com",
        order=100,
        group="delivery"
    ),
    IntakeField(
        field_key="consent_terms_privacy",
        label="I agree to the Terms of Service and Privacy Policy",
        type=IntakeFieldType.CHECKBOX,
        required=True,
        order=101,
        group="consent"
    ),
    IntakeField(
        field_key="accuracy_confirmation",
        label="I confirm the information provided is accurate to the best of my knowledge",
        type=IntakeFieldType.CHECKBOX,
        required=True,
        order=102,
        group="consent"
    ),
]


# ============================================================================
# CATEGORY: AI AUTOMATION SERVICES
# ============================================================================

AI_WF_BLUEPRINT_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="business_description",
        label="Business Description",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="What do you do and who do you serve? 2-5 sentences.",
        placeholder="We are a property management company serving landlords in the South East...",
        validation={"min_length": 50, "max_length": 2000},
        order=10
    ),
    IntakeField(
        field_key="team_size",
        label="Team Size",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Solo (1)", "Small (2-5)", "Medium (6-20)", "Large (21-50)", "Enterprise (50+)"],
        order=11
    ),
    IntakeField(
        field_key="current_tools_used",
        label="Current Tools & Systems",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="List tools you currently use: Zoho, Google Workspace, Excel, WhatsApp, etc.",
        placeholder="Add a tool...",
        max_items=15,
        order=12
    ),
    IntakeField(
        field_key="current_process_overview",
        label="Current Process Overview",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="Describe your current workflow step-by-step. What happens from start to finish?",
        placeholder="1. Client enquiry comes in via email\n2. We manually add to spreadsheet\n3. ...",
        validation={"min_length": 100, "max_length": 5000},
        order=13
    ),
    IntakeField(
        field_key="main_pain_points",
        label="Main Pain Points",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="What slows you down or causes errors? List 3-5 specific issues.",
        placeholder="Add a pain point...",
        validation={"min_items": 3, "max_items": 5},
        max_items=5,
        order=14
    ),
    IntakeField(
        field_key="goals_objectives",
        label="Goals & Objectives",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="What does success look like in 30-90 days? Be specific.",
        placeholder="In 90 days, I want to have reduced manual data entry by 50% and...",
        validation={"min_length": 50, "max_length": 2000},
        order=15
    ),
    IntakeField(
        field_key="workflows_to_focus",
        label="Workflows to Focus On",
        type=IntakeFieldType.MULTI_SELECT,
        required=True,
        helper_text="Select up to 3 workflows you want to automate first.",
        options=[
            "Lead/Enquiry Management",
            "Client Onboarding",
            "Document Generation",
            "Invoice & Payments",
            "Task Assignment",
            "Reporting & Analytics",
            "Communication/Follow-ups",
            "Compliance Tracking",
            "Property Management",
            "Other"
        ],
        validation={"max_items": 3},
        max_items=3,
        order=16
    ),
    IntakeField(
        field_key="budget_range",
        label="Budget Range",
        type=IntakeFieldType.SELECT,
        required=False,
        options=["Under £500", "£500-£2,000", "£2,000-£5,000", "£5,000-£10,000", "£10,000+", "Flexible"],
        order=17
    ),
    IntakeField(
        field_key="constraints",
        label="Constraints & Requirements",
        type=IntakeFieldType.CHECKBOX_GROUP,
        required=False,
        helper_text="Select any constraints that apply.",
        options=[
            "Must be GDPR compliant",
            "Prefer no-code/low-code solutions",
            "Must integrate with existing systems",
            "Data must stay in UK/EU",
            "Need mobile access",
            "Requires approval workflows"
        ],
        order=18
    ),
    IntakeField(
        field_key="additional_notes",
        label="Additional Notes",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        placeholder="Any other information that would help us...",
        order=19
    ),
]


AI_PROC_MAP_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="business_description",
        label="Business Description",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="Brief overview of your business and what you do.",
        validation={"min_length": 50, "max_length": 2000},
        order=10
    ),
    IntakeField(
        field_key="team_size",
        label="Team Size",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Solo (1)", "Small (2-5)", "Medium (6-20)", "Large (21-50)", "Enterprise (50+)"],
        order=11
    ),
    IntakeField(
        field_key="processes_to_map",
        label="Processes to Map",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="Name each process you want mapped. Be specific.",
        placeholder="e.g., New tenant onboarding",
        validation={"min_items": 1, "max_items": 5},
        max_items=5,
        order=12
    ),
    IntakeField(
        field_key="current_steps",
        label="Current Process Steps",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="Describe the current steps in your primary process from start to finish.",
        placeholder="Step 1: Receive enquiry\nStep 2: Check availability\nStep 3: ...",
        validation={"min_length": 100, "max_length": 5000},
        order=13
    ),
    IntakeField(
        field_key="roles_involved",
        label="Roles Involved",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="List all roles/people involved in this process.",
        placeholder="e.g., Property Manager",
        validation={"min_items": 1},
        max_items=10,
        order=14
    ),
    IntakeField(
        field_key="inputs_outputs_per_step",
        label="Inputs & Outputs",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="What goes into each step and what comes out?",
        placeholder="Step 1: Input = enquiry email, Output = CRM record\nStep 2: ...",
        validation={"min_length": 50},
        order=15
    ),
    IntakeField(
        field_key="bottlenecks_failure_points",
        label="Bottlenecks & Failure Points",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="Where does the process slow down or fail?",
        validation={"min_length": 50},
        order=16
    ),
    IntakeField(
        field_key="systems_touched",
        label="Systems & Tools Used",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="List all systems/tools involved in this process.",
        placeholder="e.g., Excel, Gmail",
        max_items=15,
        order=17
    ),
    IntakeField(
        field_key="compliance_requirements",
        label="Compliance Requirements",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        helper_text="Any regulatory or compliance requirements?",
        placeholder="e.g., GDPR, FCA, industry-specific",
        order=18
    ),
    IntakeField(
        field_key="additional_notes",
        label="Additional Notes",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        order=19
    ),
]


AI_TOOL_REPORT_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="business_description",
        label="Business Description",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="Brief overview of your business.",
        validation={"min_length": 50, "max_length": 1000},
        order=10
    ),
    IntakeField(
        field_key="use_case",
        label="Primary Use Case",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="What specific problem do you want AI tools to solve?",
        placeholder="I need to automate customer support responses and...",
        validation={"min_length": 50, "max_length": 2000},
        order=11
    ),
    IntakeField(
        field_key="must_have_features",
        label="Must-Have Features",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="List features the tool MUST have.",
        placeholder="e.g., API access",
        validation={"min_items": 2},
        max_items=10,
        order=12
    ),
    IntakeField(
        field_key="data_sensitivity_level",
        label="Data Sensitivity Level",
        type=IntakeFieldType.SELECT,
        required=True,
        helper_text="How sensitive is the data the tool will handle?",
        options=["Low - Public data only", "Medium - Internal business data", "High - Personal/financial data"],
        order=13
    ),
    IntakeField(
        field_key="integrations_needed",
        label="Required Integrations",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="What systems must the tool integrate with?",
        placeholder="e.g., Salesforce, Slack",
        max_items=10,
        order=14
    ),
    IntakeField(
        field_key="budget_range",
        label="Monthly Budget",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Under £50/month", "£50-200/month", "£200-500/month", "£500-1000/month", "£1000+/month"],
        order=15
    ),
    IntakeField(
        field_key="skill_level",
        label="Technical Skill Level",
        type=IntakeFieldType.SELECT,
        required=True,
        helper_text="How technical is your team?",
        options=["Beginner - No coding", "Intermediate - Basic scripting", "Advanced - Can code/configure"],
        order=16
    ),
    IntakeField(
        field_key="additional_notes",
        label="Additional Requirements",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        order=17
    ),
]


# ============================================================================
# CATEGORY: MARKET RESEARCH
# ============================================================================

MR_BASIC_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="business_product_description",
        label="Business/Product Description",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="Describe your business or the product/service you're researching.",
        validation={"min_length": 50, "max_length": 2000},
        order=10
    ),
    IntakeField(
        field_key="target_geography",
        label="Target Geography",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["UK Only", "UK & Ireland", "Europe", "North America", "Global", "Other"],
        order=11
    ),
    IntakeField(
        field_key="target_geography_other",
        label="Specify Geography",
        type=IntakeFieldType.TEXT,
        required=True,
        visibility_conditions=[{"field": "target_geography", "value": "Other"}],
        order=12
    ),
    IntakeField(
        field_key="target_customer_profile",
        label="Target Customer Profile",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="Who is your ideal customer? Demographics, behaviours, needs.",
        placeholder="Small landlords with 1-5 properties, aged 35-55...",
        validation={"min_length": 50},
        order=13
    ),
    IntakeField(
        field_key="known_competitors",
        label="Known Competitors",
        type=IntakeFieldType.MULTI_TEXT,
        required=False,
        helper_text="List competitors you're aware of (we'll find more).",
        placeholder="e.g., Competitor name",
        max_items=10,
        order=14
    ),
    IntakeField(
        field_key="price_point_offer",
        label="Your Price Point / Offer",
        type=IntakeFieldType.TEXT,
        required=False,
        helper_text="What price range are you considering?",
        placeholder="e.g., £49-99/month",
        order=15
    ),
    IntakeField(
        field_key="key_questions",
        label="Key Research Questions",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="What specific questions do you need answered? (Max 3)",
        placeholder="e.g., What is the market size?",
        validation={"min_items": 1, "max_items": 3},
        max_items=3,
        order=16
    ),
    IntakeField(
        field_key="additional_notes",
        label="Additional Context",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        order=17
    ),
]


MR_ADVANCED_FIELDS: List[IntakeField] = MR_BASIC_FIELDS + [
    IntakeField(
        field_key="customer_segments_personas",
        label="Customer Segments & Personas",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="Describe your different customer segments in detail.",
        validation={"min_length": 100},
        order=20
    ),
    IntakeField(
        field_key="pricing_assumptions",
        label="Pricing Assumptions",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="What pricing model are you considering? Any assumptions?",
        placeholder="Subscription model at £X/month, one-time fee of £Y, etc.",
        order=21
    ),
    IntakeField(
        field_key="current_channels",
        label="Current Marketing Channels",
        type=IntakeFieldType.MULTI_SELECT,
        required=True,
        options=[
            "Organic Search/SEO",
            "Paid Search (Google Ads)",
            "Social Media Organic",
            "Social Media Paid",
            "Email Marketing",
            "Content Marketing",
            "Referrals/Word of Mouth",
            "Partnerships",
            "Events/Conferences",
            "Direct Sales",
            "None yet"
        ],
        max_items=10,
        order=22
    ),
    IntakeField(
        field_key="differentiators",
        label="Key Differentiators",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        helper_text="What makes you different from competitors?",
        validation={"min_length": 50},
        order=23
    ),
    IntakeField(
        field_key="constraints_limitations",
        label="Constraints & Limitations",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        helper_text="Any constraints affecting your market entry?",
        order=24
    ),
]


# ============================================================================
# CATEGORY: COMPLIANCE SERVICES
# ============================================================================

PROPERTY_ADDRESS_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="property_address_line1",
        label="Address Line 1",
        type=IntakeFieldType.TEXT,
        required=True,
        placeholder="123 High Street",
        order=30,
        group="property_address"
    ),
    IntakeField(
        field_key="property_address_line2",
        label="Address Line 2",
        type=IntakeFieldType.TEXT,
        required=False,
        placeholder="Flat 2",
        order=31,
        group="property_address"
    ),
    IntakeField(
        field_key="property_city",
        label="City/Town",
        type=IntakeFieldType.TEXT,
        required=True,
        placeholder="London",
        order=32,
        group="property_address"
    ),
    IntakeField(
        field_key="property_postcode",
        label="Postcode",
        type=IntakeFieldType.TEXT,
        required=True,
        placeholder="SW1A 1AA",
        validation={"pattern": r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$"},
        order=33,
        group="property_address"
    ),
]


HMO_AUDIT_FIELDS: List[IntakeField] = PROPERTY_ADDRESS_FIELDS + [
    IntakeField(
        field_key="local_authority",
        label="Local Authority",
        type=IntakeFieldType.TEXT,
        required=False,
        helper_text="If known, enter the local council name.",
        placeholder="e.g., Bristol City Council",
        order=34
    ),
    IntakeField(
        field_key="property_type",
        label="Property Type",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["House", "Flat", "Maisonette", "Converted Building", "Purpose-Built HMO"],
        order=35
    ),
    IntakeField(
        field_key="bedrooms",
        label="Number of Bedrooms",
        type=IntakeFieldType.NUMBER,
        required=True,
        validation={"min": 1, "max": 50},
        order=36
    ),
    IntakeField(
        field_key="occupants",
        label="Number of Occupants",
        type=IntakeFieldType.NUMBER,
        required=True,
        validation={"min": 1, "max": 100},
        order=37
    ),
    IntakeField(
        field_key="tenancy_type",
        label="Tenancy Type",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["AST (Assured Shorthold)", "Assured Tenancy", "Licence Agreement", "Company Let", "Other"],
        order=38
    ),
    IntakeField(
        field_key="licence_status",
        label="HMO Licence Status",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Yes - Licensed", "No - Not Required", "No - Required but not obtained", "Unknown"],
        order=39
    ),
    IntakeField(
        field_key="certificates_list",
        label="Current Certificates",
        type=IntakeFieldType.MULTI_TEXT,
        required=False,
        helper_text="List certificates you currently have (Gas Safety, EICR, EPC, etc.)",
        placeholder="e.g., Gas Safety Certificate",
        max_items=15,
        order=40
    ),
    IntakeField(
        field_key="certificates_expiry_dates",
        label="Certificate Expiry Dates",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        helper_text="List expiry dates for each certificate.",
        placeholder="Gas Safety: 15/06/2025\nEICR: 20/09/2026",
        order=41
    ),
    IntakeField(
        field_key="known_issues",
        label="Known Issues or Council Contact",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        helper_text="Any known compliance issues or recent council correspondence?",
        order=42
    ),
    IntakeField(
        field_key="top_concerns",
        label="Top Concerns",
        type=IntakeFieldType.MULTI_TEXT,
        required=True,
        helper_text="What are your main compliance concerns? (Max 3)",
        validation={"min_items": 1, "max_items": 3},
        max_items=3,
        order=43
    ),
    IntakeField(
        field_key="supporting_docs_upload",
        label="Supporting Documents",
        type=IntakeFieldType.FILE_UPLOAD,
        required=False,
        helper_text="Upload any relevant certificates, photos, or documents.",
        order=44
    ),
]


FULL_AUDIT_FIELDS: List[IntakeField] = HMO_AUDIT_FIELDS + [
    IntakeField(
        field_key="deposit_scheme_details",
        label="Deposit Protection Details",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        helper_text="Which scheme? When was deposit protected?",
        placeholder="e.g., DPS, protected on 01/01/2024",
        order=50
    ),
    IntakeField(
        field_key="prescribed_info_served",
        label="Prescribed Information Served?",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Yes", "No", "Unknown"],
        helper_text="Was the prescribed information given to tenant within 30 days?",
        order=51
    ),
    IntakeField(
        field_key="inventory_checkin_status",
        label="Inventory/Check-in Completed?",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Yes - Signed", "Yes - Not Signed", "No", "Unknown"],
        order=52
    ),
    IntakeField(
        field_key="notices_served_history",
        label="Previous Notices Served?",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Yes", "No", "Unknown"],
        helper_text="Have you served any Section 21 or Section 8 notices?",
        order=53
    ),
    IntakeField(
        field_key="maintenance_log_status",
        label="Maintenance Log Kept?",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Yes - Up to date", "Yes - Outdated", "No", "Unknown"],
        order=54
    ),
]


MOVE_CHECKLIST_FIELDS: List[IntakeField] = PROPERTY_ADDRESS_FIELDS + [
    IntakeField(
        field_key="checklist_type",
        label="Checklist Type",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["Move-In", "Move-Out"],
        order=35
    ),
    IntakeField(
        field_key="tenancy_start_date",
        label="Tenancy Start Date",
        type=IntakeFieldType.DATE,
        required=True,
        order=36
    ),
    IntakeField(
        field_key="tenancy_end_date",
        label="Tenancy End Date",
        type=IntakeFieldType.DATE,
        required=True,
        visibility_conditions=[{"field": "checklist_type", "value": "Move-Out"}],
        order=37
    ),
    IntakeField(
        field_key="landlord_name",
        label="Landlord Name",
        type=IntakeFieldType.TEXT,
        required=True,
        order=38
    ),
    IntakeField(
        field_key="tenant_name",
        label="Tenant Name",
        type=IntakeFieldType.TEXT,
        required=False,
        order=39
    ),
    IntakeField(
        field_key="room_list",
        label="Rooms to Include",
        type=IntakeFieldType.MULTI_SELECT,
        required=True,
        options=[
            "Entrance/Hallway",
            "Living Room",
            "Kitchen",
            "Bedroom 1",
            "Bedroom 2",
            "Bedroom 3",
            "Bathroom",
            "En-suite",
            "Utility Room",
            "Garden/Outside",
            "Garage",
            "Other"
        ],
        max_items=15,
        order=40
    ),
    IntakeField(
        field_key="inventory_notes",
        label="Additional Notes",
        type=IntakeFieldType.TEXTAREA,
        required=False,
        order=41
    ),
]


# ============================================================================
# CATEGORY: DOCUMENT PACKS
# ============================================================================

DOC_PACK_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="pack_type",
        label="Pack Type",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["ESSENTIAL", "TENANCY", "ULTIMATE"],
        helper_text="Essential: Core forms | Tenancy: + Legal notices | Ultimate: Complete pack",
        order=10
    ),
    # Landlord details
    IntakeField(
        field_key="landlord_name",
        label="Landlord Full Name",
        type=IntakeFieldType.TEXT,
        required=True,
        order=20,
        group="landlord_details"
    ),
    IntakeField(
        field_key="landlord_email",
        label="Landlord Email",
        type=IntakeFieldType.EMAIL,
        required=True,
        order=21,
        group="landlord_details"
    ),
    IntakeField(
        field_key="landlord_phone",
        label="Landlord Phone",
        type=IntakeFieldType.PHONE,
        required=True,
        order=22,
        group="landlord_details"
    ),
    IntakeField(
        field_key="landlord_address",
        label="Landlord Address",
        type=IntakeFieldType.TEXTAREA,
        required=True,
        placeholder="Full correspondence address",
        order=23,
        group="landlord_details"
    ),
    # Tenant details
    IntakeField(
        field_key="tenant_name",
        label="Tenant Full Name",
        type=IntakeFieldType.TEXT,
        required=True,
        order=30,
        group="tenant_details"
    ),
    IntakeField(
        field_key="tenant_email",
        label="Tenant Email",
        type=IntakeFieldType.EMAIL,
        required=False,
        order=31,
        group="tenant_details"
    ),
    # Property address
    IntakeField(
        field_key="property_address_line1",
        label="Property Address Line 1",
        type=IntakeFieldType.TEXT,
        required=True,
        order=40,
        group="property_address"
    ),
    IntakeField(
        field_key="property_address_line2",
        label="Property Address Line 2",
        type=IntakeFieldType.TEXT,
        required=False,
        order=41,
        group="property_address"
    ),
    IntakeField(
        field_key="property_city",
        label="City/Town",
        type=IntakeFieldType.TEXT,
        required=True,
        order=42,
        group="property_address"
    ),
    IntakeField(
        field_key="property_postcode",
        label="Postcode",
        type=IntakeFieldType.TEXT,
        required=True,
        order=43,
        group="property_address"
    ),
    # Tenancy details
    IntakeField(
        field_key="tenancy_type",
        label="Tenancy Type",
        type=IntakeFieldType.SELECT,
        required=True,
        options=["AST (Assured Shorthold)", "Periodic", "Fixed Term", "Company Let"],
        order=50,
        group="tenancy_details"
    ),
    IntakeField(
        field_key="tenancy_start_date",
        label="Tenancy Start Date",
        type=IntakeFieldType.DATE,
        required=True,
        order=51,
        group="tenancy_details"
    ),
    IntakeField(
        field_key="tenancy_end_date",
        label="Tenancy End Date",
        type=IntakeFieldType.DATE,
        required=False,
        helper_text="Leave blank for periodic tenancy",
        order=52,
        group="tenancy_details"
    ),
    IntakeField(
        field_key="rent_amount",
        label="Monthly Rent (£)",
        type=IntakeFieldType.CURRENCY,
        required=True,
        validation={"min": 1},
        order=53,
        group="tenancy_details"
    ),
    IntakeField(
        field_key="deposit_amount",
        label="Deposit Amount (£)",
        type=IntakeFieldType.CURRENCY,
        required=False,
        order=54,
        group="tenancy_details"
    ),
    IntakeField(
        field_key="supporting_docs_upload",
        label="Supporting Documents",
        type=IntakeFieldType.FILE_UPLOAD,
        required=False,
        helper_text="Upload any existing agreements or relevant documents.",
        order=60
    ),
]


# ============================================================================
# POSTAL ADDRESS FIELDS (for Printed Copy add-on)
# ============================================================================

POSTAL_ADDRESS_FIELDS: List[IntakeField] = [
    IntakeField(
        field_key="postal_recipient_name",
        label="Recipient Name",
        type=IntakeFieldType.TEXT,
        required=True,
        order=200,
        group="postal_address"
    ),
    IntakeField(
        field_key="postal_address_line1",
        label="Address Line 1",
        type=IntakeFieldType.TEXT,
        required=True,
        order=201,
        group="postal_address"
    ),
    IntakeField(
        field_key="postal_address_line2",
        label="Address Line 2",
        type=IntakeFieldType.TEXT,
        required=False,
        order=202,
        group="postal_address"
    ),
    IntakeField(
        field_key="postal_city",
        label="City",
        type=IntakeFieldType.TEXT,
        required=True,
        order=203,
        group="postal_address"
    ),
    IntakeField(
        field_key="postal_postcode",
        label="Postcode",
        type=IntakeFieldType.TEXT,
        required=True,
        validation={"pattern": r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$"},
        order=204,
        group="postal_address"
    ),
    IntakeField(
        field_key="postal_phone",
        label="Contact Phone",
        type=IntakeFieldType.PHONE,
        required=True,
        order=205,
        group="postal_address"
    ),
]


# ============================================================================
# SERVICE SCHEMA REGISTRY
# ============================================================================

SERVICE_INTAKE_SCHEMAS: Dict[str, List[IntakeField]] = {
    # AI Automation
    "AI_WF_BLUEPRINT": AI_WF_BLUEPRINT_FIELDS,
    "AI_PROC_MAP": AI_PROC_MAP_FIELDS,
    "AI_TOOL_REPORT": AI_TOOL_REPORT_FIELDS,
    
    # Market Research
    "MR_BASIC": MR_BASIC_FIELDS,
    "MR_ADV": MR_ADVANCED_FIELDS,
    
    # Compliance Services
    "HMO_AUDIT": HMO_AUDIT_FIELDS,
    "FULL_AUDIT": FULL_AUDIT_FIELDS,
    "MOVE_CHECKLIST": MOVE_CHECKLIST_FIELDS,
    
    # Document Packs
    "DOC_PACK_ESSENTIAL": DOC_PACK_FIELDS,
    "DOC_PACK_PLUS": DOC_PACK_FIELDS,
    "DOC_PACK_PRO": DOC_PACK_FIELDS,
}


# Services that allow file uploads
SERVICES_WITH_UPLOADS = {
    "HMO_AUDIT",
    "FULL_AUDIT",
    "DOC_PACK_ESSENTIAL",
    "DOC_PACK_PLUS",
    "DOC_PACK_PRO",
}


def get_service_schema(service_code: str) -> Dict[str, Any]:
    """Get complete intake schema for a service."""
    service_fields = SERVICE_INTAKE_SCHEMAS.get(service_code, [])
    
    # Build complete schema with universal fields
    all_fields = (
        UNIVERSAL_CLIENT_FIELDS +
        service_fields +
        UNIVERSAL_DELIVERY_FIELDS
    )
    
    # Add file upload if service supports it
    supports_uploads = service_code in SERVICES_WITH_UPLOADS
    
    return {
        "service_code": service_code,
        "schema_version": "1.0",
        "supports_uploads": supports_uploads,
        "supports_fast_track": service_code.startswith("DOC_PACK"),
        "supports_printed_copy": service_code.startswith("DOC_PACK"),
        "fields": [f.model_dump() for f in all_fields],
        "field_groups": _extract_field_groups(all_fields),
        "visibility_rules": _extract_visibility_rules(all_fields),
    }


def get_postal_address_schema() -> List[Dict[str, Any]]:
    """Get postal address fields schema."""
    return [f.model_dump() for f in POSTAL_ADDRESS_FIELDS]


def _extract_field_groups(fields: List[IntakeField]) -> Dict[str, List[str]]:
    """Extract field groups from fields."""
    groups = {}
    for field in fields:
        if field.group:
            if field.group not in groups:
                groups[field.group] = []
            groups[field.group].append(field.field_key)
    return groups


def _extract_visibility_rules(fields: List[IntakeField]) -> List[Dict[str, Any]]:
    """Extract visibility rules from fields."""
    rules = []
    for field in fields:
        if field.visibility_conditions:
            rules.append({
                "target_field": field.field_key,
                "conditions": field.visibility_conditions,
            })
    return rules


def validate_intake_payload(service_code: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate intake payload against service schema.
    
    Returns:
        {
            "valid": bool,
            "errors": List[{field_key, message}],
            "warnings": List[{field_key, message}]
        }
    """
    schema = get_service_schema(service_code)
    fields = schema.get("fields", [])
    errors = []
    warnings = []
    
    for field_def in fields:
        field_key = field_def["field_key"]
        field_type = field_def["type"]
        required = field_def.get("required", False)
        validation = field_def.get("validation", {})
        visibility_conditions = field_def.get("visibility_conditions", [])
        
        # Check visibility conditions
        is_visible = True
        if visibility_conditions:
            for condition in visibility_conditions:
                cond_field = condition.get("field")
                cond_value = condition.get("value")
                if payload.get(cond_field) != cond_value:
                    is_visible = False
                    break
        
        # Skip validation for hidden fields
        if not is_visible:
            continue
        
        value = payload.get(field_key)
        
        # Required check
        if required and (value is None or value == "" or value == []):
            errors.append({
                "field_key": field_key,
                "message": f"{field_def['label']} is required"
            })
            continue
        
        # Skip further validation if no value
        if value is None or value == "":
            continue
        
        # Type-specific validation
        if field_type == "email" and value:
            import re
            if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
                errors.append({
                    "field_key": field_key,
                    "message": "Invalid email address"
                })
        
        if field_type == "phone" and value:
            # Basic phone validation
            cleaned = ''.join(c for c in str(value) if c.isdigit() or c == '+')
            if len(cleaned) < 10:
                errors.append({
                    "field_key": field_key,
                    "message": "Invalid phone number"
                })
        
        if field_type == "number" and value is not None:
            try:
                num = float(value)
                if "min" in validation and num < validation["min"]:
                    errors.append({
                        "field_key": field_key,
                        "message": f"Must be at least {validation['min']}"
                    })
                if "max" in validation and num > validation["max"]:
                    errors.append({
                        "field_key": field_key,
                        "message": f"Must be at most {validation['max']}"
                    })
            except (ValueError, TypeError):
                errors.append({
                    "field_key": field_key,
                    "message": "Must be a number"
                })
        
        if field_type in ["text", "textarea"] and value:
            if "min_length" in validation and len(str(value)) < validation["min_length"]:
                errors.append({
                    "field_key": field_key,
                    "message": f"Must be at least {validation['min_length']} characters"
                })
            if "max_length" in validation and len(str(value)) > validation["max_length"]:
                errors.append({
                    "field_key": field_key,
                    "message": f"Must be at most {validation['max_length']} characters"
                })
            if "pattern" in validation:
                import re
                if not re.match(validation["pattern"], str(value), re.IGNORECASE):
                    errors.append({
                        "field_key": field_key,
                        "message": "Invalid format"
                    })
        
        if field_type in ["multi_text", "multi_select"] and isinstance(value, list):
            if "min_items" in validation and len(value) < validation["min_items"]:
                errors.append({
                    "field_key": field_key,
                    "message": f"Select at least {validation['min_items']} items"
                })
            if "max_items" in validation and len(value) > validation["max_items"]:
                errors.append({
                    "field_key": field_key,
                    "message": f"Select at most {validation['max_items']} items"
                })
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
