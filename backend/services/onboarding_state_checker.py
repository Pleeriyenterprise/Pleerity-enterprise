"""
Behaviour-aware state for landlord onboarding sequence.
Used before sending each onboarding email to decide whether to send, skip, or cancel the sequence.
"""
from typing import Dict, Any
from database import database


async def check_onboarding_state(client_id: str) -> Dict[str, Any]:
    """
    Return current onboarding state for the client.
    - has_added_property: at least one property exists for this client.
    - has_uploaded_certificate: at least one document exists for this client (any document counts as certificate/store).
    - monitoring_enabled: compliance_notifications_enabled is True (user has opted into compliance alerts).
    When monitoring_enabled is True, the onboarding sequence should stop (cancel remaining emails).
    """
    db = database.get_db()
    if not client_id:
        return {"has_added_property": False, "has_uploaded_certificate": False, "monitoring_enabled": False}

    props_count = await db.properties.count_documents({"client_id": client_id})
    docs_count = await db.documents.count_documents({"client_id": client_id})

    prefs = await db.notification_preferences.find_one(
        {"client_id": client_id},
        {"_id": 0, "compliance_notifications_enabled": 1},
    )
    monitoring_enabled = bool(prefs and prefs.get("compliance_notifications_enabled") is True)

    return {
        "has_added_property": props_count >= 1,
        "has_uploaded_certificate": docs_count >= 1,
        "monitoring_enabled": monitoring_enabled,
    }
