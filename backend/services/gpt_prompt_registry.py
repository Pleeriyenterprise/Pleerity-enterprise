"""
GPT Prompt Registry - Authoritative storage for all document generation prompts.

This registry contains the master prompts for each service_code.
Prompts are selected based on service_code and executed with intake data.

Based on:
- AUTHORITATIVE PROMPT FRAMEWORK.docx
- GPT PROMPTS FOR ALL SERVICES.docx
- GPT PROMPTS FOR DOCUMENT PACKS.docx
- DOCUMENT PACK ORCHESTRATOR PROMPT.docx
"""
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PromptType(str, Enum):
    """Types of prompts in the system."""
    MASTER = "MASTER"           # Main generation prompt
    SECTION = "SECTION"         # Section-specific prompt
    ORCHESTRATOR = "ORCHESTRATOR"  # Document pack orchestrator
    VALIDATION = "VALIDATION"   # Output validation prompt


@dataclass
class PromptDefinition:
    """Definition of a GPT prompt."""
    prompt_id: str
    prompt_type: PromptType
    service_code: str
    name: str
    description: str
    system_prompt: str
    user_prompt_template: str
    output_schema: Dict[str, Any]
    temperature: float = 0.3
    max_tokens: int = 4000
    required_fields: List[str] = field(default_factory=list)
    gpt_sections: List[str] = field(default_factory=list)


# ============================================================================
# AUTHORITATIVE PROMPT FRAMEWORK (HARD GUARDRAILS)
# ============================================================================

AUTHORITATIVE_FRAMEWORK = """
ROLE:
You are a UK Property Compliance and Business Consulting Assistant for Pleerity Enterprise Ltd.
Your role is to generate structured, professional outputs based on user-submitted data.

HARD GUARDRAILS (NON-NEGOTIABLE):
1. Never fabricate or estimate numerical figures (prices, dates, legal fees, etc.)
2. Never provide legal or financial advice — output analysis and summaries only
3. Never recommend specific contractors, solicitors, or service providers by name
4. Never speculate on outcomes (e.g., "you will save £X" or "this will pass inspection")
5. Never generate content outside the scope of user-provided inputs
6. If input data is missing or ambiguous, flag explicitly in output rather than assume
7. Always cite UK-specific compliance standards where applicable (England/Wales unless specified otherwise)

OUTPUT STRUCTURE:
All outputs must be returned as structured JSON matching the defined schema.
Each section must be clearly labelled and self-contained.

TONE & STYLE:
- Professional, clear, and concise
- Avoid jargon unless necessary for compliance terminology
- Use bullet points for lists
- Use tables where comparison is required
- Avoid filler phrases ("In today's market...", "It's important to note...")
"""


# ============================================================================
# AI AUTOMATION SERVICE PROMPTS
# ============================================================================

AI_WF_BLUEPRINT_PROMPT = PromptDefinition(
    prompt_id="AI_WF_BLUEPRINT_MASTER",
    prompt_type=PromptType.MASTER,
    service_code="AI_WF_BLUEPRINT",
    name="Workflow Automation Blueprint Generator",
    description="Generates structured automation planning document",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are generating a Workflow Automation Blueprint for a business.
This document identifies which workflows to automate, recommends tools, and outlines efficiency gains.

DOCUMENT SECTIONS:
1. Executive Summary
2. Current State Assessment
3. Workflow Analysis & Mapping
4. Automation Opportunities (prioritized)
5. Tool Recommendations
6. Implementation Roadmap
7. Expected Outcomes & Metrics
""",
    user_prompt_template="""
Generate a Workflow Automation Blueprint based on the following client inputs:

BUSINESS INFORMATION:
- Business Description: {business_description}
- Team Size: {team_size}
- Current Tools: {current_tools}

PROCESS INFORMATION:
- Current Process Overview: {current_process_overview}
- Processes to Focus On: {processes_to_focus}
- Main Challenges: {main_challenges}

GOALS:
- Goals & Objectives: {goals_objectives}
- Priority Goal: {priority_goal}

ADDITIONAL CONTEXT:
{additional_notes}

Generate the complete blueprint following the output schema.
Flag any missing information that would improve the analysis.
""",
    output_schema={
        "executive_summary": {
            "type": "string",
            "description": "2-3 paragraph overview of findings and recommendations"
        },
        "current_state_assessment": {
            "type": "object",
            "properties": {
                "business_overview": {"type": "string"},
                "current_tools_analysis": {"type": "string"},
                "pain_points": {"type": "array", "items": {"type": "string"}},
                "maturity_level": {"type": "string", "enum": ["Manual", "Partially Automated", "Mostly Automated"]}
            }
        },
        "workflow_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string"},
                    "current_state": {"type": "string"},
                    "automation_potential": {"type": "string", "enum": ["High", "Medium", "Low"]},
                    "complexity": {"type": "string", "enum": ["Simple", "Moderate", "Complex"]},
                    "recommended_approach": {"type": "string"}
                }
            }
        },
        "automation_opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "opportunity": {"type": "string"},
                    "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                    "estimated_time_savings": {"type": "string"},
                    "implementation_effort": {"type": "string", "enum": ["Low", "Medium", "High"]}
                }
            }
        },
        "tool_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "recommended_tool": {"type": "string"},
                    "alternatives": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                    "pricing_tier": {"type": "string"}
                }
            }
        },
        "implementation_roadmap": {
            "type": "object",
            "properties": {
                "phase_1_quick_wins": {"type": "array", "items": {"type": "string"}},
                "phase_2_core_automation": {"type": "array", "items": {"type": "string"}},
                "phase_3_optimization": {"type": "array", "items": {"type": "string"}}
            }
        },
        "expected_outcomes": {
            "type": "object",
            "properties": {
                "efficiency_gains": {"type": "array", "items": {"type": "string"}},
                "risk_reduction": {"type": "array", "items": {"type": "string"}},
                "success_metrics": {"type": "array", "items": {"type": "string"}}
            }
        },
        "data_gaps_flagged": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any missing information that would improve analysis"
        }
    },
    temperature=0.3,
    max_tokens=4000,
    required_fields=["business_description", "current_process_overview", "goals_objectives", "priority_goal", "team_size", "processes_to_focus", "main_challenges"],
    gpt_sections=["GPT_WF_OVERVIEW", "GPT_WF_MAP", "GPT_RECOMMENDATIONS"]
)


AI_PROC_MAP_PROMPT = PromptDefinition(
    prompt_id="AI_PROC_MAP_MASTER",
    prompt_type=PromptType.MASTER,
    service_code="AI_PROC_MAP",
    name="Business Process Mapping Generator",
    description="Generates detailed workflow mapping with As-Is and To-Be states",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are generating a Business Process Map for a specific workflow.
This document provides detailed visual/narrative mapping identifying inefficiencies and automation opportunities.

DOCUMENT SECTIONS:
1. Process Overview
2. As-Is Process Map (current state)
3. Issue Identification
4. To-Be Process Map (optimized state)
5. Gap Analysis
6. Optimization Recommendations
7. Implementation Notes
""",
    user_prompt_template="""
Generate a Business Process Map based on the following client inputs:

BUSINESS CONTEXT:
- Business Description: {business_description}
- Team Size: {team_size}
- Current Tools: {current_tools}

PROCESS TO MAP:
- Process Name: {single_process_name}
- Process Steps Description: {process_steps_description}
- Current Process Overview: {current_process_overview}

CHALLENGES & GOALS:
- Main Challenges: {main_challenges}
- Priority Goal: {priority_goal}
- Goals & Objectives: {goals_objectives}

ADDITIONAL CONTEXT:
{additional_notes}

Generate the complete process map following the output schema.
""",
    output_schema={
        "process_overview": {
            "type": "object",
            "properties": {
                "process_name": {"type": "string"},
                "process_owner": {"type": "string"},
                "frequency": {"type": "string"},
                "stakeholders": {"type": "array", "items": {"type": "string"}},
                "inputs": {"type": "array", "items": {"type": "string"}},
                "outputs": {"type": "array", "items": {"type": "string"}}
            }
        },
        "as_is_process_map": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer"},
                    "step_name": {"type": "string"},
                    "description": {"type": "string"},
                    "actor": {"type": "string"},
                    "tools_used": {"type": "array", "items": {"type": "string"}},
                    "time_estimate": {"type": "string"},
                    "pain_points": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "issues_identified": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "issue": {"type": "string"},
                    "impact": {"type": "string", "enum": ["High", "Medium", "Low"]},
                    "root_cause": {"type": "string"},
                    "affected_steps": {"type": "array", "items": {"type": "integer"}}
                }
            }
        },
        "to_be_process_map": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer"},
                    "step_name": {"type": "string"},
                    "description": {"type": "string"},
                    "automation_level": {"type": "string", "enum": ["Manual", "Semi-Automated", "Fully Automated"]},
                    "tools_recommended": {"type": "array", "items": {"type": "string"}},
                    "time_estimate": {"type": "string"},
                    "improvements": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "gap_analysis": {
            "type": "object",
            "properties": {
                "process_gaps": {"type": "array", "items": {"type": "string"}},
                "technology_gaps": {"type": "array", "items": {"type": "string"}},
                "skill_gaps": {"type": "array", "items": {"type": "string"}}
            }
        },
        "optimization_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "recommendation": {"type": "string"},
                    "priority": {"type": "string", "enum": ["P1", "P2", "P3"]},
                    "effort": {"type": "string", "enum": ["Low", "Medium", "High"]},
                    "expected_benefit": {"type": "string"}
                }
            }
        },
        "data_gaps_flagged": {"type": "array", "items": {"type": "string"}}
    },
    temperature=0.3,
    max_tokens=4500,
    required_fields=["business_description", "single_process_name", "process_steps_description", "main_challenges", "priority_goal"],
    gpt_sections=["GPT_PROC_MAP", "GPT_ISSUES", "GPT_OPTIMISATIONS"]
)


AI_TOOLS_PROMPT = PromptDefinition(
    prompt_id="AI_TOOLS_MASTER",
    prompt_type=PromptType.MASTER,
    service_code="AI_TOOLS",
    name="AI Tool Recommendation Report Generator",
    description="Generates objective AI tool assessment and recommendations",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are generating an AI Tool Recommendation Report.
This document provides vendor-neutral assessment of AI tools matched to operational requirements.

IMPORTANT:
- Do NOT recommend specific pricing as this changes frequently
- Use pricing tiers (Free, Starter, Pro, Enterprise) not specific amounts
- Focus on capabilities and fit, not cost comparison

DOCUMENT SECTIONS:
1. Requirements Summary
2. Tool Categories Assessed
3. Comparison Matrix
4. Top Recommendations
5. Implementation Considerations
6. Alternative Options
""",
    user_prompt_template="""
Generate an AI Tool Recommendation Report based on the following client inputs:

BUSINESS CONTEXT:
- Business Description: {business_description}
- Business Overview: {business_overview}
- Team Size: {team_size}
- Current Tools: {current_tools}

REQUIREMENTS:
- Current Process Overview: {current_process_overview}
- Main Challenges: {main_challenges}
- Goals & Objectives: {goals_objectives}
- Priority Goal: {priority_goal}

CONSTRAINTS:
- Monthly Tool Budget: {tool_budget_range}
- Technical Preference: {technical_preference}

ADDITIONAL CONTEXT:
{additional_notes}

Generate the complete tool recommendation report following the output schema.
""",
    output_schema={
        "requirements_summary": {
            "type": "object",
            "properties": {
                "primary_needs": {"type": "array", "items": {"type": "string"}},
                "technical_requirements": {"type": "array", "items": {"type": "string"}},
                "budget_tier": {"type": "string"},
                "integration_requirements": {"type": "array", "items": {"type": "string"}}
            }
        },
        "tool_categories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "relevance": {"type": "string", "enum": ["Essential", "Recommended", "Optional"]},
                    "description": {"type": "string"}
                }
            }
        },
        "comparison_matrix": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "category": {"type": "string"},
                    "key_features": {"type": "array", "items": {"type": "string"}},
                    "pricing_tier": {"type": "string"},
                    "ease_of_use": {"type": "string", "enum": ["Easy", "Moderate", "Technical"]},
                    "integration_capability": {"type": "string", "enum": ["Excellent", "Good", "Limited"]},
                    "fit_score": {"type": "string", "enum": ["Excellent", "Good", "Fair", "Poor"]}
                }
            }
        },
        "top_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "tool_name": {"type": "string"},
                    "category": {"type": "string"},
                    "rationale": {"type": "string"},
                    "best_for": {"type": "string"},
                    "considerations": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "implementation_considerations": {
            "type": "object",
            "properties": {
                "quick_start_tools": {"type": "array", "items": {"type": "string"}},
                "training_required": {"type": "array", "items": {"type": "string"}},
                "integration_notes": {"type": "string"}
            }
        },
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scenario": {"type": "string"},
                    "recommended_tool": {"type": "string"},
                    "reason": {"type": "string"}
                }
            }
        },
        "data_gaps_flagged": {"type": "array", "items": {"type": "string"}}
    },
    temperature=0.3,
    max_tokens=4000,
    required_fields=["business_description", "current_process_overview", "main_challenges", "priority_goal", "tool_budget_range", "technical_preference"],
    gpt_sections=["GPT_TOOL_LIST", "GPT_COMPARISON_TABLE", "GPT_RECOMMENDATION"]
)


# ============================================================================
# MARKET RESEARCH PROMPTS
# ============================================================================

MR_BASIC_PROMPT = PromptDefinition(
    prompt_id="MR_BASIC_MASTER",
    prompt_type=PromptType.MASTER,
    service_code="MR_BASIC",
    name="Basic Market Research Report Generator",
    description="Generates concise market overview with competitor insights",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are generating a Basic Market Research Report.
This provides a concise market overview for early-stage decision-making.

IMPORTANT:
- Use publicly available market data and trends
- Do NOT fabricate specific market size numbers
- Use ranges and qualitative assessments where exact data unavailable
- Clearly state assumptions and limitations

DOCUMENT SECTIONS:
1. Market Overview
2. Target Segment Analysis
3. Competitor Overview (3-5 key players)
4. Key Findings
5. Strategic Summary
""",
    user_prompt_template="""
Generate a Basic Market Research Report based on the following client inputs:

RESEARCH SCOPE:
- Target Industry: {target_industry}
- Target Region: {target_region}
- Target Audience: {target_audience_description}
- Main Research Question: {main_research_question}

BUSINESS CONTEXT:
- Business Description: {business_description}
- Offer/Product Description: {offer_description}
- Known Competitors: {known_competitors}

ADDITIONAL CONTEXT:
{additional_notes}

Generate the complete market research report following the output schema.
Focus on directional insights rather than specific numerical data.
""",
    output_schema={
        "market_overview": {
            "type": "object",
            "properties": {
                "industry_summary": {"type": "string"},
                "market_characteristics": {"type": "array", "items": {"type": "string"}},
                "market_maturity": {"type": "string", "enum": ["Emerging", "Growing", "Mature", "Declining"]},
                "key_trends": {"type": "array", "items": {"type": "string"}}
            }
        },
        "target_segment_analysis": {
            "type": "object",
            "properties": {
                "segment_description": {"type": "string"},
                "segment_size_indicator": {"type": "string"},
                "buying_behaviors": {"type": "array", "items": {"type": "string"}},
                "pain_points": {"type": "array", "items": {"type": "string"}},
                "decision_factors": {"type": "array", "items": {"type": "string"}}
            }
        },
        "competitor_overview": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "competitor_name": {"type": "string"},
                    "market_position": {"type": "string"},
                    "key_strengths": {"type": "array", "items": {"type": "string"}},
                    "key_weaknesses": {"type": "array", "items": {"type": "string"}},
                    "target_segment": {"type": "string"}
                }
            }
        },
        "key_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding": {"type": "string"},
                    "implication": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["High", "Medium", "Low"]}
                }
            }
        },
        "strategic_summary": {
            "type": "object",
            "properties": {
                "market_opportunity": {"type": "string"},
                "recommended_positioning": {"type": "string"},
                "key_success_factors": {"type": "array", "items": {"type": "string"}},
                "risks_to_consider": {"type": "array", "items": {"type": "string"}}
            }
        },
        "research_limitations": {"type": "array", "items": {"type": "string"}},
        "data_gaps_flagged": {"type": "array", "items": {"type": "string"}}
    },
    temperature=0.4,
    max_tokens=3500,
    required_fields=["target_industry", "target_region", "target_audience_description", "main_research_question", "business_description"],
    gpt_sections=["GPT_OVERVIEW", "GPT_COMP_TABLE", "GPT_FINDINGS"]
)


MR_ADV_PROMPT = PromptDefinition(
    prompt_id="MR_ADV_MASTER",
    prompt_type=PromptType.MASTER,
    service_code="MR_ADV",
    name="Advanced Market Research Report Generator",
    description="Generates comprehensive research with SWOT, pricing, and trends",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are generating an Advanced Market Research Report.
This is a premium, enterprise-grade report for strategic decision-making.

IMPORTANT:
- Use publicly available market data and trends
- Provide ranges rather than fabricated specific numbers
- SWOT analysis must be balanced and evidence-based
- Pricing analysis should be tier-based, not specific amounts
- Trends should be supportable by observable market behavior

DOCUMENT SECTIONS:
1. Executive Summary
2. Market Data & Size Analysis
3. Detailed Competitor Analysis
4. SWOT Analysis
5. Pricing Landscape
6. Trends & Forecasts
7. Strategic Recommendations
""",
    user_prompt_template="""
Generate an Advanced Market Research Report based on the following client inputs:

RESEARCH SCOPE:
- Target Industry: {target_industry}
- Target Region: {target_region}
- Target Audience: {target_audience_description}
- Main Research Question: {main_research_question}
- Time Horizon: {time_horizon}

BUSINESS CONTEXT:
- Business Description: {business_description}
- Offer/Product Description: {offer_description}
- Known Competitors: {known_competitors}
- Pricing Intent: {pricing_intent}

ADDITIONAL CONTEXT:
{additional_notes}

Generate the complete advanced market research report following the output schema.
Ensure SWOT analysis is balanced and pricing analysis uses tiers not specific amounts.
""",
    output_schema={
        "executive_summary": {
            "type": "string",
            "description": "3-4 paragraph strategic overview"
        },
        "market_data": {
            "type": "object",
            "properties": {
                "market_size_indicator": {"type": "string"},
                "growth_trajectory": {"type": "string", "enum": ["Rapid Growth", "Steady Growth", "Stable", "Declining"]},
                "market_segments": {"type": "array", "items": {"type": "string"}},
                "market_drivers": {"type": "array", "items": {"type": "string"}},
                "market_barriers": {"type": "array", "items": {"type": "string"}}
            }
        },
        "competitor_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "competitor_name": {"type": "string"},
                    "market_share_indicator": {"type": "string"},
                    "positioning": {"type": "string"},
                    "value_proposition": {"type": "string"},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                    "recent_moves": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "swot_analysis": {
            "type": "object",
            "properties": {
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
                "opportunities": {"type": "array", "items": {"type": "string"}},
                "threats": {"type": "array", "items": {"type": "string"}}
            }
        },
        "pricing_landscape": {
            "type": "object",
            "properties": {
                "pricing_models_observed": {"type": "array", "items": {"type": "string"}},
                "price_tiers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tier_name": {"type": "string"},
                            "typical_range": {"type": "string"},
                            "value_proposition": {"type": "string"}
                        }
                    }
                },
                "pricing_recommendations": {"type": "string"}
            }
        },
        "trends_and_forecasts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "trend": {"type": "string"},
                    "direction": {"type": "string", "enum": ["Increasing", "Stable", "Decreasing"]},
                    "time_horizon": {"type": "string"},
                    "impact": {"type": "string", "enum": ["High", "Medium", "Low"]},
                    "implications": {"type": "string"}
                }
            }
        },
        "strategic_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "recommendation": {"type": "string"},
                    "priority": {"type": "string", "enum": ["Critical", "High", "Medium", "Low"]},
                    "rationale": {"type": "string"},
                    "implementation_notes": {"type": "string"}
                }
            }
        },
        "research_limitations": {"type": "array", "items": {"type": "string"}},
        "data_gaps_flagged": {"type": "array", "items": {"type": "string"}}
    },
    temperature=0.4,
    max_tokens=5000,
    required_fields=["target_industry", "target_region", "target_audience_description", "main_research_question", "business_description", "pricing_intent", "time_horizon"],
    gpt_sections=["GPT_EXEC_SUMMARY", "GPT_MARKET_DATA_TABLES", "GPT_COMPETITOR_ANALYSIS", "GPT_SWOT_ANALYSIS", "GPT_PRICING_INSIGHTS", "GPT_TRENDS_AND_FORECASTS", "GPT_INSIGHTS_AND_RECOMMENDATIONS"]
)


# ============================================================================
# COMPLIANCE SERVICE PROMPTS
# ============================================================================

COMP_HMO_PROMPT = PromptDefinition(
    prompt_id="COMP_HMO_MASTER",
    prompt_type=PromptType.MASTER,
    service_code="COMP_HMO",
    name="HMO Compliance Audit Report Generator",
    description="Generates HMO-specific compliance audit report",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are generating an HMO Compliance Audit Report for a UK House in Multiple Occupation.
This document assesses compliance against current HMO regulations.

UK HMO COMPLIANCE AREAS:
- HMO licensing (mandatory and additional schemes)
- Fire safety (doors, alarms, extinguishers, escape routes)
- Room sizes (minimum 6.51m² single, 10.22m² double)
- Kitchen/bathroom ratios
- Gas safety (annual CP12 certificate)
- Electrical safety (5-yearly EICR)
- Energy performance (EPC rating E minimum)
- Management regulations (waste, common areas)

IMPORTANT:
- Reference specific UK regulations where applicable
- Flag any items requiring professional inspection
- Do NOT confirm compliance status - provide assessment only
- Recommend professional verification for all safety items
""",
    user_prompt_template="""
Generate an HMO Compliance Audit Report based on the following property information:

PROPERTY DETAILS:
- Address: {property_address_line1}, {property_address_line2}, {property_town_city}, {property_postcode}
- Property Type: {property_type}
- Number of Bedrooms: {number_of_bedrooms}
- Number of Occupants: {hmo_number_of_occupants}
- Region: {country_region}

HMO STATUS:
- Current HMO Licence Status: {current_hmo_licence_status}
- Licence Required: {licence_required}
- Managing Agent Involved: {managing_agent_involved}

CERTIFICATES & DOCUMENTATION:
- Current Certificates Held: {current_certificates_list}
- Certificate Status Notes: {hmo_certificate_status_notes}

KNOWN ISSUES:
{hmo_known_issues}

TOP CONCERNS:
{top_three_concerns}

CLIENT DETAILS:
- Name: {client_full_name}
- Role: {client_role}

Generate the complete HMO compliance audit report following the output schema.
""",
    output_schema={
        "property_summary": {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "property_type": {"type": "string"},
                "hmo_category": {"type": "string"},
                "occupancy": {"type": "string"},
                "licence_status": {"type": "string"}
            }
        },
        "licensing_assessment": {
            "type": "object",
            "properties": {
                "licence_type_required": {"type": "string"},
                "current_status": {"type": "string"},
                "compliance_status": {"type": "string", "enum": ["Compliant", "Action Required", "Non-Compliant", "Verification Needed"]},
                "notes": {"type": "string"},
                "actions_required": {"type": "array", "items": {"type": "string"}}
            }
        },
        "safety_certificates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "certificate_type": {"type": "string"},
                    "status": {"type": "string", "enum": ["Valid", "Expiring Soon", "Expired", "Not Provided", "Unknown"]},
                    "expiry_date": {"type": "string"},
                    "compliance_status": {"type": "string", "enum": ["Compliant", "Action Required", "Non-Compliant", "Verification Needed"]},
                    "actions_required": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "fire_safety_assessment": {
            "type": "object",
            "properties": {
                "overall_status": {"type": "string", "enum": ["Satisfactory", "Improvements Needed", "Urgent Action Required", "Professional Assessment Needed"]},
                "areas_assessed": {"type": "array", "items": {"type": "string"}},
                "concerns_identified": {"type": "array", "items": {"type": "string"}},
                "recommendations": {"type": "array", "items": {"type": "string"}}
            }
        },
        "room_standards_assessment": {
            "type": "object",
            "properties": {
                "bedroom_compliance": {"type": "string"},
                "kitchen_facilities": {"type": "string"},
                "bathroom_facilities": {"type": "string"},
                "common_areas": {"type": "string"},
                "concerns": {"type": "array", "items": {"type": "string"}}
            }
        },
        "management_compliance": {
            "type": "object",
            "properties": {
                "waste_management": {"type": "string"},
                "common_area_maintenance": {"type": "string"},
                "tenant_information": {"type": "string"},
                "concerns": {"type": "array", "items": {"type": "string"}}
            }
        },
        "risk_summary": {
            "type": "object",
            "properties": {
                "overall_risk_level": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
                "critical_items": {"type": "array", "items": {"type": "string"}},
                "high_priority_items": {"type": "array", "items": {"type": "string"}},
                "medium_priority_items": {"type": "array", "items": {"type": "string"}}
            }
        },
        "action_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "priority": {"type": "string", "enum": ["Immediate", "Within 30 Days", "Within 90 Days", "Ongoing"]},
                    "responsible_party": {"type": "string"},
                    "notes": {"type": "string"}
                }
            }
        },
        "disclaimers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Legal disclaimers and professional verification recommendations"
        },
        "data_gaps_flagged": {"type": "array", "items": {"type": "string"}}
    },
    temperature=0.2,
    max_tokens=4500,
    required_fields=["property_address_line1", "property_postcode", "number_of_bedrooms", "hmo_number_of_occupants", "current_hmo_licence_status", "top_three_concerns"],
    gpt_sections=["GPT_HMO_STATUS", "GPT_COMPLIANCE_GAPS", "GPT_REQUIRED_ACTIONS"]
)


COMP_FULL_AUDIT_PROMPT = PromptDefinition(
    prompt_id="COMP_FULL_AUDIT_MASTER",
    prompt_type=PromptType.MASTER,
    service_code="COMP_FULL_AUDIT",
    name="Full Compliance Audit Report Generator",
    description="Generates comprehensive property compliance audit report",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are generating a Full Compliance Audit Report for a UK rental property.
This comprehensive review covers all regulatory compliance areas.

UK RENTAL COMPLIANCE AREAS:
- Gas safety (CP12 certificate - annual)
- Electrical safety (EICR - 5-yearly, or before new tenancy)
- Energy performance (EPC - E rating minimum for new tenancies)
- Smoke & CO alarms (all floors, CO in rooms with solid fuel)
- Right to Rent checks
- Deposit protection (within 30 days, in government scheme)
- How to Rent guide (provided before tenancy)
- Licensing (selective, additional, mandatory HMO)
- Legionella risk assessment (reasonable precautions)

IMPORTANT:
- Reference specific UK regulations
- Clearly state what requires professional verification
- Do NOT confirm compliance - provide assessment only
- Flag all items that need documentary evidence
""",
    user_prompt_template="""
Generate a Full Compliance Audit Report based on the following property information:

PROPERTY DETAILS:
- Address: {property_address_line1}, {property_address_line2}, {property_town_city}, {property_postcode}
- Property Type: {property_type}
- Number of Bedrooms: {number_of_bedrooms}
- Region: {country_region}

OWNERSHIP & MANAGEMENT:
- Properties Owned: {number_of_properties_owned}
- Portfolio Scope: {portfolio_scope}
- Managing Agent Involved: {managing_agent_involved}

TENANCY INFORMATION:
- Tenancy Type: {tenancy_type}
- Deposit Scheme: {deposit_scheme_used}

COMPLIANCE DOCUMENTATION:
- Licence Required: {licence_required}
- Current Certificates: {current_certificates_list}

TOP CONCERNS:
{top_three_concerns}

CLIENT DETAILS:
- Name: {client_full_name}
- Role: {client_role}

Generate the complete compliance audit report following the output schema.
""",
    output_schema={
        "audit_summary": {
            "type": "object",
            "properties": {
                "property_address": {"type": "string"},
                "audit_date": {"type": "string"},
                "overall_compliance_status": {"type": "string", "enum": ["Compliant", "Minor Issues", "Significant Issues", "Non-Compliant", "Verification Needed"]},
                "risk_level": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
                "key_findings_summary": {"type": "string"}
            }
        },
        "safety_certificates": {
            "type": "object",
            "properties": {
                "gas_safety": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "expiry": {"type": "string"},
                        "compliance": {"type": "string"},
                        "actions": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "electrical_safety": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "expiry": {"type": "string"},
                        "compliance": {"type": "string"},
                        "actions": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "epc": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "rating": {"type": "string"},
                        "expiry": {"type": "string"},
                        "compliance": {"type": "string"},
                        "actions": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        },
        "smoke_co_alarms": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "compliance": {"type": "string"},
                "concerns": {"type": "array", "items": {"type": "string"}},
                "actions": {"type": "array", "items": {"type": "string"}}
            }
        },
        "licensing_status": {
            "type": "object",
            "properties": {
                "licence_type_required": {"type": "string"},
                "current_status": {"type": "string"},
                "compliance": {"type": "string"},
                "actions": {"type": "array", "items": {"type": "string"}}
            }
        },
        "deposit_protection": {
            "type": "object",
            "properties": {
                "scheme_used": {"type": "string"},
                "status": {"type": "string"},
                "compliance": {"type": "string"},
                "actions": {"type": "array", "items": {"type": "string"}}
            }
        },
        "tenancy_documentation": {
            "type": "object",
            "properties": {
                "tenancy_agreement": {"type": "string"},
                "how_to_rent_guide": {"type": "string"},
                "right_to_rent": {"type": "string"},
                "prescribed_information": {"type": "string"},
                "actions": {"type": "array", "items": {"type": "string"}}
            }
        },
        "risk_assessment": {
            "type": "object",
            "properties": {
                "critical_risks": {"type": "array", "items": {"type": "string"}},
                "high_risks": {"type": "array", "items": {"type": "string"}},
                "medium_risks": {"type": "array", "items": {"type": "string"}},
                "low_risks": {"type": "array", "items": {"type": "string"}}
            }
        },
        "action_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "category": {"type": "string"},
                    "priority": {"type": "string", "enum": ["Immediate", "Within 14 Days", "Within 30 Days", "Within 90 Days"]},
                    "responsible_party": {"type": "string"}
                }
            }
        },
        "regulatory_references": {"type": "array", "items": {"type": "string"}},
        "disclaimers": {"type": "array", "items": {"type": "string"}},
        "data_gaps_flagged": {"type": "array", "items": {"type": "string"}}
    },
    temperature=0.2,
    max_tokens=5000,
    required_fields=["property_address_line1", "property_postcode", "tenancy_type", "current_certificates_list", "top_three_concerns"],
    gpt_sections=["GPT_COMPLIANCE_OVERVIEW", "GPT_RISK_RATING", "GPT_NON_COMPLIANCE_SUMMARY", "GPT_REQUIRED_ACTIONS"]
)


COMP_MOVEOUT_PROMPT = PromptDefinition(
    prompt_id="COMP_MOVEOUT_MASTER",
    prompt_type=PromptType.MASTER,
    service_code="COMP_MOVEOUT",
    name="Move-In/Move-Out Checklist Generator",
    description="Generates structured property condition checklist",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are generating a Move-In/Move-Out Checklist for a UK rental property.
This structured document records property condition to reduce deposit disputes.

PURPOSE:
- Document property condition at tenancy start/end
- Provide dated evidence for deposit disputes
- Support TDS/DPS adjudication if needed

CHECKLIST AREAS:
- External areas (front, rear, garden)
- Each room (walls, floors, ceiling, fixtures)
- Kitchen (appliances, units, surfaces)
- Bathroom(s) (sanitaryware, tiles, fixtures)
- Utilities (meters, heating, hot water)
- Keys and access items
- Furnishings (if applicable)
""",
    user_prompt_template="""
Generate a Move-In/Move-Out Checklist based on the following property information:

PROPERTY DETAILS:
- Address: {property_address_line1}, {property_address_line2}, {property_town_city}, {property_postcode}
- Property Type: {property_type}
- Number of Bedrooms: {number_of_bedrooms}
- Furnished Status: {property_furnished}

TENANCY INFORMATION:
- Tenancy Start Date: {tenancy_start_date}
- Tenancy End Date: {tenancy_end_date}
- Tenant Name: {tenant_full_name}

SPECIAL AREAS TO NOTE:
{special_areas_to_note}

CLIENT DETAILS:
- Name: {client_full_name}
- Role: {client_role}

Generate the complete checklist following the output schema.
Create appropriate room entries based on the property type and bedroom count.
""",
    output_schema={
        "checklist_header": {
            "type": "object",
            "properties": {
                "property_address": {"type": "string"},
                "tenant_name": {"type": "string"},
                "tenancy_start_date": {"type": "string"},
                "tenancy_end_date": {"type": "string"},
                "checklist_type": {"type": "string", "enum": ["Move-In", "Move-Out", "Both"]},
                "property_type": {"type": "string"},
                "furnished_status": {"type": "string"}
            }
        },
        "external_areas": {
            "type": "object",
            "properties": {
                "front_exterior": {"type": "array", "items": {"type": "string"}},
                "rear_exterior": {"type": "array", "items": {"type": "string"}},
                "garden_areas": {"type": "array", "items": {"type": "string"}},
                "parking": {"type": "array", "items": {"type": "string"}}
            }
        },
        "room_checklists": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "room_name": {"type": "string"},
                    "room_type": {"type": "string"},
                    "ceiling": {"type": "array", "items": {"type": "string"}},
                    "walls": {"type": "array", "items": {"type": "string"}},
                    "floor": {"type": "array", "items": {"type": "string"}},
                    "windows": {"type": "array", "items": {"type": "string"}},
                    "doors": {"type": "array", "items": {"type": "string"}},
                    "lighting": {"type": "array", "items": {"type": "string"}},
                    "electrical": {"type": "array", "items": {"type": "string"}},
                    "heating": {"type": "array", "items": {"type": "string"}},
                    "fixtures": {"type": "array", "items": {"type": "string"}},
                    "furnishings": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "kitchen_checklist": {
            "type": "object",
            "properties": {
                "appliances": {"type": "array", "items": {"type": "string"}},
                "units_worktops": {"type": "array", "items": {"type": "string"}},
                "sink_taps": {"type": "array", "items": {"type": "string"}},
                "floor_walls": {"type": "array", "items": {"type": "string"}},
                "ventilation": {"type": "array", "items": {"type": "string"}}
            }
        },
        "bathroom_checklists": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "bathroom_name": {"type": "string"},
                    "sanitaryware": {"type": "array", "items": {"type": "string"}},
                    "tiles_grouting": {"type": "array", "items": {"type": "string"}},
                    "taps_shower": {"type": "array", "items": {"type": "string"}},
                    "ventilation": {"type": "array", "items": {"type": "string"}},
                    "fixtures": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "utilities_meters": {
            "type": "object",
            "properties": {
                "electricity_meter": {"type": "array", "items": {"type": "string"}},
                "gas_meter": {"type": "array", "items": {"type": "string"}},
                "water_meter": {"type": "array", "items": {"type": "string"}},
                "heating_system": {"type": "array", "items": {"type": "string"}},
                "hot_water": {"type": "array", "items": {"type": "string"}}
            }
        },
        "keys_access": {
            "type": "object",
            "properties": {
                "front_door_keys": {"type": "string"},
                "back_door_keys": {"type": "string"},
                "window_keys": {"type": "string"},
                "garage_remotes": {"type": "string"},
                "alarm_codes": {"type": "string"},
                "other_access": {"type": "array", "items": {"type": "string"}}
            }
        },
        "special_notes": {"type": "array", "items": {"type": "string"}},
        "signature_section": {
            "type": "object",
            "properties": {
                "landlord_signature_block": {"type": "string"},
                "tenant_signature_block": {"type": "string"},
                "date_block": {"type": "string"},
                "witness_block": {"type": "string"}
            }
        }
    },
    temperature=0.2,
    max_tokens=4000,
    required_fields=["property_address_line1", "property_postcode", "number_of_bedrooms", "property_furnished", "tenancy_start_date", "tenant_full_name"],
    gpt_sections=["GPT_MOVE_IN_CHECKLIST", "GPT_MOVE_OUT_CHECKLIST"]
)


# ============================================================================
# DOCUMENT PACK ORCHESTRATOR PROMPT
# ============================================================================

DOC_PACK_ORCHESTRATOR_PROMPT = PromptDefinition(
    prompt_id="DOC_PACK_ORCHESTRATOR",
    prompt_type=PromptType.ORCHESTRATOR,
    service_code="DOC_PACK_ORCHESTRATOR",
    name="Document Pack Orchestrator",
    description="Controls document pack generation, selecting appropriate documents and prompts",
    system_prompt=AUTHORITATIVE_FRAMEWORK + """
SERVICE CONTEXT:
You are the Document Pack Orchestrator for Pleerity Enterprise Ltd.
Your role is to orchestrate the generation of document bundles.

ORCHESTRATION RULES:
1. Determine which documents are needed based on user selection
2. Validate required fields for each document type
3. Generate content for each selected document
4. Flag any missing information
5. Ensure all documents follow the same data context

DOCUMENT PACKS:
- ESSENTIAL: Rent arrears, Deposit refund, Tenant reference, Rent receipt, GDPR notice
- PLUS (Tenancy): AST, PRT, Renewal, Notice to quit, Rent increase, Guarantor
- PRO (Ultimate): All above + Inventory, Deposit info, Property access, Additional notices

IMPORTANT:
- Legal documents must use controlled template language
- GPT sections enhance but don't replace template content
- All monetary amounts must come from user input
- Dates must be validated and formatted correctly
""",
    user_prompt_template="""
Orchestrate document pack generation based on the following:

PACK SELECTED: {pack_type}
DOCUMENTS REQUESTED: {documents_required}

LANDLORD INFORMATION:
- Name: {landlord_name}
- Address: {landlord_address}

TENANT INFORMATION:
- Name: {doc_tenant_full_name}
- Address: {tenant_address}

PROPERTY INFORMATION:
- Address: {property_address_line1}, {property_postcode}
- Bedrooms: {number_of_bedrooms}
- Region: {country_region}

TENANCY DETAILS:
- Start Date: {doc_tenancy_start_date}
- Rent Amount: {current_rent_amount}
- Rent Frequency: {rent_frequency}

Generate the orchestration response following the output schema.
For each document, provide the specific GPT-enhanced content sections.
""",
    output_schema={
        "orchestration_metadata": {
            "type": "object",
            "properties": {
                "pack_type": {"type": "string"},
                "documents_to_generate": {"type": "array", "items": {"type": "string"}},
                "total_documents": {"type": "integer"},
                "validation_status": {"type": "string", "enum": ["Valid", "Missing Data", "Invalid"]}
            }
        },
        "document_contents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "document_code": {"type": "string"},
                    "document_name": {"type": "string"},
                    "gpt_sections": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    },
                    "merge_fields": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    }
                }
            }
        },
        "validation_issues": {"type": "array", "items": {"type": "string"}},
        "data_gaps_flagged": {"type": "array", "items": {"type": "string"}}
    },
    temperature=0.2,
    max_tokens=6000,
    required_fields=["pack_type", "documents_required", "landlord_name", "doc_tenant_full_name"],
    gpt_sections=[]
)


# ============================================================================
# PROMPT REGISTRY
# ============================================================================

PROMPT_REGISTRY: Dict[str, PromptDefinition] = {
    # AI Automation
    "AI_WF_BLUEPRINT": AI_WF_BLUEPRINT_PROMPT,
    "AI_PROC_MAP": AI_PROC_MAP_PROMPT,
    "AI_TOOLS": AI_TOOLS_PROMPT,
    
    # Market Research
    "MR_BASIC": MR_BASIC_PROMPT,
    "MR_ADV": MR_ADV_PROMPT,
    
    # Compliance
    "COMP_HMO": COMP_HMO_PROMPT,
    "COMP_FULL_AUDIT": COMP_FULL_AUDIT_PROMPT,
    "COMP_MOVEOUT": COMP_MOVEOUT_PROMPT,
    
    # Document Pack Orchestrator
    "DOC_PACK_ORCHESTRATOR": DOC_PACK_ORCHESTRATOR_PROMPT,
}


def get_prompt_for_service(service_code: str) -> Optional[PromptDefinition]:
    """Get the master prompt for a service code."""
    return PROMPT_REGISTRY.get(service_code)


def get_all_prompts() -> Dict[str, PromptDefinition]:
    """Get all registered prompts."""
    return PROMPT_REGISTRY.copy()


def validate_intake_data(service_code: str, intake_data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate intake data against prompt requirements.
    Returns (is_valid, list_of_missing_fields).
    """
    prompt = get_prompt_for_service(service_code)
    if not prompt:
        return False, [f"No prompt found for service: {service_code}"]
    
    missing = []
    for field in prompt.required_fields:
        if field not in intake_data or not intake_data[field]:
            missing.append(field)
    
    return len(missing) == 0, missing
