"""Today page analytics: allowlisted event names and JWT → analytics role mapping."""

from services.product_analytics_service import ALLOWED_EVENTS
from utils.analytics_event_logger import analytics_role_from_jwt_role


def test_today_analytics_events_allowlisted():
    for name in (
        "TODAY_PAGE_VIEWED",
        "TODAY_PAGE_REQUESTED",
        "TODAY_PAGE_LOAD_FAILED",
        "TODAY_TASK_CLICKED",
        "TODAY_TASK_COMPLETED",
        "TODAY_TASK_SNOOZED",
        "TODAY_TASK_DISMISSED",
        "TODAY_PRIMARY_ACTION_TRIGGERED",
    ):
        assert name in ALLOWED_EVENTS


def test_analytics_role_from_jwt_role():
    assert analytics_role_from_jwt_role("ROLE_CLIENT") == "client"
    assert analytics_role_from_jwt_role("ROLE_CLIENT_ADMIN") == "client"
    assert analytics_role_from_jwt_role("ROLE_ADMIN") == "admin"
    assert analytics_role_from_jwt_role("ROLE_CONTRACTOR") == "contractor"
    assert analytics_role_from_jwt_role(None) == "client"
    assert analytics_role_from_jwt_role("") == "client"
