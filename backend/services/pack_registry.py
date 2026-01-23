"""
Document Pack Registry - Canonical document ordering for Document Packs.

This module defines the AUTHORITATIVE document list and generation order
for each pack type. The server is the single source of truth for what
documents are included in each pack.

Rules:
1. Generation order and delivery order must always follow canonical order
2. UI may display selection but server remains authoritative
3. Pack contents are fixed per pack type (no client customization)
4. Ultimate includes all Essential + all Tenancy documents in order
"""
from typing import Dict, List, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PackType(str, Enum):
    """Document pack types."""
    ESSENTIAL = "ESSENTIAL"
    TENANCY = "TENANCY"
    ULTIMATE = "ULTIMATE"


class DocumentCode(str, Enum):
    """All available document codes."""
    # Essential Pack Documents
    RENT_ARREARS_LETTER = "RENT_ARREARS_LETTER"
    DEPOSIT_REFUND_LETTER = "DEPOSIT_REFUND_LETTER"
    TENANT_REFERENCE_LETTER = "TENANT_REFERENCE_LETTER"
    RENT_RECEIPT_TEMPLATE = "RENT_RECEIPT_TEMPLATE"
    GDPR_NOTICE = "GDPR_NOTICE"
    
    # Tenancy Pack Documents
    AST_AGREEMENT = "AST_AGREEMENT"
    PRT_AGREEMENT = "PRT_AGREEMENT"
    TENANCY_RENEWAL = "TENANCY_RENEWAL"
    NOTICE_TO_QUIT = "NOTICE_TO_QUIT"
    RENT_INCREASE_NOTICE = "RENT_INCREASE_NOTICE"
    GUARANTOR_AGREEMENT = "GUARANTOR_AGREEMENT"
    
    # Ultimate Pack Additional Documents
    INVENTORY_CONDITION = "INVENTORY_CONDITION"
    DEPOSIT_INFO_PACK = "DEPOSIT_INFO_PACK"
    PROPERTY_ACCESS_NOTICE = "PROPERTY_ACCESS_NOTICE"
    LANDLORD_NOTICE_GENERAL = "LANDLORD_NOTICE_GENERAL"


# ============================================================================
# DOCUMENT DEFINITIONS
# ============================================================================

DOCUMENT_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    DocumentCode.RENT_ARREARS_LETTER.value: {
        "code": "RENT_ARREARS_LETTER",
        "name": "Rent Arrears Letter",
        "description": "Formal letter addressing outstanding rent payments",
        "format": "docx",
        "template_id": "TPL_RENT_ARREARS",
        "requires_tenant_info": True,
    },
    DocumentCode.DEPOSIT_REFUND_LETTER.value: {
        "code": "DEPOSIT_REFUND_LETTER",
        "name": "Deposit Refund Explanation Letter",
        "description": "Letter explaining deposit deductions or full refund",
        "format": "docx",
        "template_id": "TPL_DEPOSIT_REFUND",
        "requires_tenant_info": True,
    },
    DocumentCode.TENANT_REFERENCE_LETTER.value: {
        "code": "TENANT_REFERENCE_LETTER",
        "name": "Tenant Reference Letter",
        "description": "Landlord reference letter for departing tenant",
        "format": "docx",
        "template_id": "TPL_TENANT_REF",
        "requires_tenant_info": True,
    },
    DocumentCode.RENT_RECEIPT_TEMPLATE.value: {
        "code": "RENT_RECEIPT_TEMPLATE",
        "name": "Rent Receipt Template",
        "description": "Reusable rent payment receipt template",
        "format": "docx",
        "template_id": "TPL_RENT_RECEIPT",
        "requires_tenant_info": False,
    },
    DocumentCode.GDPR_NOTICE.value: {
        "code": "GDPR_NOTICE",
        "name": "GDPR Privacy Notice",
        "description": "Data protection notice for tenants",
        "format": "docx",
        "template_id": "TPL_GDPR",
        "requires_tenant_info": False,
    },
    DocumentCode.AST_AGREEMENT.value: {
        "code": "AST_AGREEMENT",
        "name": "Assured Shorthold Tenancy Agreement",
        "description": "Standard AST contract for England/Wales",
        "format": "docx",
        "template_id": "TPL_AST",
        "requires_tenant_info": True,
        "jurisdiction": "england_wales",
    },
    DocumentCode.PRT_AGREEMENT.value: {
        "code": "PRT_AGREEMENT",
        "name": "Private Residential Tenancy Agreement",
        "description": "PRT contract for Scotland",
        "format": "docx",
        "template_id": "TPL_PRT",
        "requires_tenant_info": True,
        "jurisdiction": "scotland",
    },
    DocumentCode.TENANCY_RENEWAL.value: {
        "code": "TENANCY_RENEWAL",
        "name": "Tenancy Renewal/Extension Letter",
        "description": "Letter to offer tenancy extension",
        "format": "docx",
        "template_id": "TPL_RENEWAL",
        "requires_tenant_info": True,
    },
    DocumentCode.NOTICE_TO_QUIT.value: {
        "code": "NOTICE_TO_QUIT",
        "name": "Notice to Quit / Possession Notice",
        "description": "Formal notice ending tenancy",
        "format": "docx",
        "template_id": "TPL_NOTICE_QUIT",
        "requires_tenant_info": True,
    },
    DocumentCode.RENT_INCREASE_NOTICE.value: {
        "code": "RENT_INCREASE_NOTICE",
        "name": "Rent Increase Notice",
        "description": "Formal notice of rent increase",
        "format": "docx",
        "template_id": "TPL_RENT_INCREASE",
        "requires_tenant_info": True,
    },
    DocumentCode.GUARANTOR_AGREEMENT.value: {
        "code": "GUARANTOR_AGREEMENT",
        "name": "Guarantor Agreement",
        "description": "Agreement for rent guarantor",
        "format": "docx",
        "template_id": "TPL_GUARANTOR",
        "requires_tenant_info": True,
    },
    DocumentCode.INVENTORY_CONDITION.value: {
        "code": "INVENTORY_CONDITION",
        "name": "Inventory & Condition Record",
        "description": "Property condition documentation",
        "format": "docx",
        "template_id": "TPL_INVENTORY",
        "requires_tenant_info": False,
    },
    DocumentCode.DEPOSIT_INFO_PACK.value: {
        "code": "DEPOSIT_INFO_PACK",
        "name": "Deposit Information Pack",
        "description": "Required deposit protection information",
        "format": "docx",
        "template_id": "TPL_DEPOSIT_INFO",
        "requires_tenant_info": True,
    },
    DocumentCode.PROPERTY_ACCESS_NOTICE.value: {
        "code": "PROPERTY_ACCESS_NOTICE",
        "name": "Property Access Notice",
        "description": "Notice for scheduled property access",
        "format": "docx",
        "template_id": "TPL_ACCESS",
        "requires_tenant_info": True,
    },
    DocumentCode.LANDLORD_NOTICE_GENERAL.value: {
        "code": "LANDLORD_NOTICE_GENERAL",
        "name": "General Landlord Notice",
        "description": "Multi-purpose landlord notification",
        "format": "docx",
        "template_id": "TPL_LANDLORD_NOTICE",
        "requires_tenant_info": False,
    },
}


# ============================================================================
# CANONICAL PACK CONTENTS (AUTHORITATIVE)
# ============================================================================

# Essential Pack - Core landlord forms
ESSENTIAL_DOCUMENTS = [
    DocumentCode.RENT_ARREARS_LETTER.value,
    DocumentCode.DEPOSIT_REFUND_LETTER.value,
    DocumentCode.TENANT_REFERENCE_LETTER.value,
    DocumentCode.RENT_RECEIPT_TEMPLATE.value,
    DocumentCode.GDPR_NOTICE.value,
]

# Tenancy Pack - Legal notices and agreements
TENANCY_DOCUMENTS = [
    DocumentCode.AST_AGREEMENT.value,
    DocumentCode.PRT_AGREEMENT.value,
    DocumentCode.TENANCY_RENEWAL.value,
    DocumentCode.NOTICE_TO_QUIT.value,
    DocumentCode.RENT_INCREASE_NOTICE.value,
    DocumentCode.GUARANTOR_AGREEMENT.value,
]

# Ultimate Pack - Complete coverage (Essential + Tenancy + Additional)
ULTIMATE_ADDITIONAL_DOCUMENTS = [
    DocumentCode.INVENTORY_CONDITION.value,
    DocumentCode.DEPOSIT_INFO_PACK.value,
    DocumentCode.PROPERTY_ACCESS_NOTICE.value,
    DocumentCode.LANDLORD_NOTICE_GENERAL.value,
]


# ============================================================================
# PACK REGISTRY
# ============================================================================

PACK_REGISTRY: Dict[str, Dict[str, Any]] = {
    PackType.ESSENTIAL.value: {
        "pack_type": PackType.ESSENTIAL.value,
        "name": "Essential Document Pack",
        "description": "Core landlord forms and letters",
        "price_pence": 2900,  # £29
        "documents": ESSENTIAL_DOCUMENTS,
        "document_count": len(ESSENTIAL_DOCUMENTS),
        "includes_previous": False,
    },
    PackType.TENANCY.value: {
        "pack_type": PackType.TENANCY.value,
        "name": "Tenancy Document Pack",
        "description": "Essential + Legal agreements and notices",
        "price_pence": 4900,  # £49
        "documents": ESSENTIAL_DOCUMENTS + TENANCY_DOCUMENTS,
        "document_count": len(ESSENTIAL_DOCUMENTS + TENANCY_DOCUMENTS),
        "includes_previous": True,
        "includes": [PackType.ESSENTIAL.value],
    },
    PackType.ULTIMATE.value: {
        "pack_type": PackType.ULTIMATE.value,
        "name": "Ultimate Document Pack",
        "description": "Complete coverage - all documents included",
        "price_pence": 7900,  # £79
        "documents": ESSENTIAL_DOCUMENTS + TENANCY_DOCUMENTS + ULTIMATE_ADDITIONAL_DOCUMENTS,
        "document_count": len(ESSENTIAL_DOCUMENTS + TENANCY_DOCUMENTS + ULTIMATE_ADDITIONAL_DOCUMENTS),
        "includes_previous": True,
        "includes": [PackType.ESSENTIAL.value, PackType.TENANCY.value],
    },
}


# ============================================================================
# ADD-ONS
# ============================================================================

PACK_ADDONS = {
    "FAST_TRACK": {
        "addon_code": "FAST_TRACK",
        "name": "Fast Track Delivery",
        "description": "24-hour priority processing",
        "price_pence": 2000,  # £20
        "applies_to": ["ESSENTIAL", "TENANCY", "ULTIMATE"],
        "effects": {
            "priority": True,
            "sla_hours": 24,
            "queue_priority": 5,
        },
    },
    "PRINTED_COPY": {
        "addon_code": "PRINTED_COPY",
        "name": "Printed & Posted Copy",
        "description": "Physical copy sent by Royal Mail",
        "price_pence": 2500,  # £25
        "applies_to": ["ESSENTIAL", "TENANCY", "ULTIMATE"],
        "requires_postal_address": True,
        "effects": {
            "delivery_modes": ["EMAIL", "POSTAL"],
            "requires_postal_delivery": True,
        },
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_pack_contents(pack_type: str) -> Dict[str, Any]:
    """
    Get canonical pack contents and pricing.
    Server-authoritative - this is the source of truth.
    """
    pack = PACK_REGISTRY.get(pack_type.upper())
    if not pack:
        raise ValueError(f"Unknown pack type: {pack_type}")
    
    return {
        "pack_type": pack["pack_type"],
        "name": pack["name"],
        "description": pack["description"],
        "price_pence": pack["price_pence"],
        "documents": [
            {
                "code": doc_code,
                "order": idx + 1,
                **DOCUMENT_DEFINITIONS.get(doc_code, {}),
            }
            for idx, doc_code in enumerate(pack["documents"])
        ],
        "document_count": pack["document_count"],
    }


def get_pack_documents_ordered(pack_type: str) -> List[Dict[str, Any]]:
    """
    Get documents for a pack in canonical generation order.
    This order MUST be used for generation and delivery.
    """
    pack = PACK_REGISTRY.get(pack_type.upper())
    if not pack:
        raise ValueError(f"Unknown pack type: {pack_type}")
    
    return [
        {
            "code": doc_code,
            "generation_order": idx + 1,
            "delivery_order": idx + 1,
            **DOCUMENT_DEFINITIONS.get(doc_code, {}),
        }
        for idx, doc_code in enumerate(pack["documents"])
    ]


def calculate_pack_price(
    pack_type: str,
    addons: List[str] = None,
) -> Dict[str, Any]:
    """
    Calculate total price for pack with add-ons.
    All prices in pence.
    """
    pack = PACK_REGISTRY.get(pack_type.upper())
    if not pack:
        raise ValueError(f"Unknown pack type: {pack_type}")
    
    addons = addons or []
    
    base_price = pack["price_pence"]
    addon_total = 0
    addon_details = []
    
    for addon_code in addons:
        addon = PACK_ADDONS.get(addon_code.upper())
        if addon and pack_type.upper() in addon["applies_to"]:
            addon_total += addon["price_pence"]
            addon_details.append({
                "code": addon["addon_code"],
                "name": addon["name"],
                "price_pence": addon["price_pence"],
            })
    
    total_price = base_price + addon_total
    
    return {
        "pack_type": pack_type.upper(),
        "base_price_pence": base_price,
        "addon_total_pence": addon_total,
        "total_price_pence": total_price,
        "addons": addon_details,
        "currency": "gbp",
        # Formatted for display
        "base_price_display": f"£{base_price / 100:.2f}",
        "addon_total_display": f"£{addon_total / 100:.2f}",
        "total_price_display": f"£{total_price / 100:.2f}",
    }


def get_addon_requirements(addon_code: str) -> Dict[str, Any]:
    """Get requirements for an addon (e.g., postal address for printed copy)."""
    addon = PACK_ADDONS.get(addon_code.upper())
    if not addon:
        return {}
    
    return {
        "requires_postal_address": addon.get("requires_postal_address", False),
        "effects": addon.get("effects", {}),
    }


def validate_pack_addons(pack_type: str, addons: List[str]) -> Dict[str, Any]:
    """Validate that selected addons are valid for the pack type."""
    errors = []
    valid_addons = []
    
    pack = PACK_REGISTRY.get(pack_type.upper())
    if not pack:
        return {"valid": False, "errors": [f"Unknown pack type: {pack_type}"]}
    
    for addon_code in addons:
        addon = PACK_ADDONS.get(addon_code.upper())
        if not addon:
            errors.append(f"Unknown addon: {addon_code}")
        elif pack_type.upper() not in addon["applies_to"]:
            errors.append(f"Addon {addon_code} not available for {pack_type}")
        else:
            valid_addons.append(addon_code.upper())
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "valid_addons": valid_addons,
    }


def get_all_packs() -> List[Dict[str, Any]]:
    """Get all available packs with details."""
    return [
        {
            **pack,
            "price_display": f"£{pack['price_pence'] / 100:.2f}",
        }
        for pack in PACK_REGISTRY.values()
    ]


def get_all_addons() -> List[Dict[str, Any]]:
    """Get all available add-ons."""
    return [
        {
            **addon,
            "price_display": f"£{addon['price_pence'] / 100:.2f}",
        }
        for addon in PACK_ADDONS.values()
    ]
