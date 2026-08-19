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
        return {
            "has_added_property": False,
            "has_uploaded_certificate": False,
            "monitoring_enabled": False,
            "jurisdiction_label": "",
            "jurisdiction_known": False,
        }

    props_count = await db.properties.count_documents({"client_id": client_id})
    docs_count = await db.documents.count_documents({"client_id": client_id})

    prefs = await db.notification_preferences.find_one(
        {"client_id": client_id},
        {"_id": 0, "compliance_notifications_enabled": 1},
    )
    monitoring_enabled = bool(prefs and prefs.get("compliance_notifications_enabled") is True)

    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1, "enabled_jurisdictions": 1},
    )
    jurisdictions = []
    seen = set()
    for label in [
        (client or {}).get("default_jurisdiction"),
        *list((client or {}).get("enabled_jurisdictions") or []),
    ]:
        s = str(label or "").strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            jurisdictions.append(s)
    cursor = db.properties.find({"client_id": client_id}, {"_id": 0, "jurisdiction": 1})
    async for prop in cursor:
        s = str((prop or {}).get("jurisdiction") or "").strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            jurisdictions.append(s)
    jurisdiction_known = len(jurisdictions) == 1
    return {
        "has_added_property": props_count >= 1,
        "has_uploaded_certificate": docs_count >= 1,
        "monitoring_enabled": monitoring_enabled,
        "jurisdiction_label": jurisdictions[0] if jurisdiction_known else "",
        "jurisdiction_known": jurisdiction_known,
    }
