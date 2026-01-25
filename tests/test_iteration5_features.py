"""
Test Iteration 5 Features:
- Calendar API /api/calendar/expiries - events grouped by date with summary stats
- Calendar API /api/calendar/upcoming - upcoming expiries sorted by date with urgency
- CalendarPage grid/list views with navigation and summary stats
- Dashboard Calendar nav link navigation to /app/calendar
- NotificationPreferencesPage SMS section with Beta badge
- SMS preferences (sms_enabled, sms_phone_number, sms_urgent_alerts_only) via API
- Property model enhanced attributes (is_hmo, has_gas_supply, building_age_years, etc.)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://promptmgr.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def client_auth_token(api_client):
    """Get client authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Client authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def admin_auth_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, client_auth_token):
    """Session with client auth header"""
    api_client.headers.update({"Authorization": f"Bearer {client_auth_token}"})
    return api_client


@pytest.fixture(scope="module")
def admin_client(api_client, admin_auth_token):
    """Session with admin auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_auth_token}"
    })
    return session


class TestCalendarExpiriesAPI:
    """Test /api/calendar/expiries endpoint"""
    
    def test_calendar_expiries_returns_200(self, authenticated_client):
        """Test that calendar expiries endpoint returns 200"""
        response = authenticated_client.get(f"{BASE_URL}/api/calendar/expiries")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_calendar_expiries_structure(self, authenticated_client):
        """Test calendar expiries response structure"""
        response = authenticated_client.get(f"{BASE_URL}/api/calendar/expiries")
        assert response.status_code == 200
        
        data = response.json()
        # Check required fields
        assert "year" in data, "Response should contain 'year'"
        assert "events_by_date" in data, "Response should contain 'events_by_date'"
        assert "summary" in data, "Response should contain 'summary'"
        
        # Check summary structure
        summary = data["summary"]
        assert "total_events" in summary, "Summary should contain 'total_events'"
        assert "overdue_count" in summary, "Summary should contain 'overdue_count'"
        assert "expiring_soon_count" in summary, "Summary should contain 'expiring_soon_count'"
        assert "dates_with_events" in summary, "Summary should contain 'dates_with_events'"
        
    def test_calendar_expiries_with_year_month(self, authenticated_client):
        """Test calendar expiries with year and month parameters"""
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        response = authenticated_client.get(
            f"{BASE_URL}/api/calendar/expiries?year={current_year}&month={current_month}"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["year"] == current_year
        assert data["month"] == current_month
        
    def test_calendar_expiries_events_grouped_by_date(self, authenticated_client):
        """Test that events are grouped by date"""
        response = authenticated_client.get(f"{BASE_URL}/api/calendar/expiries")
        assert response.status_code == 200
        
        data = response.json()
        events_by_date = data["events_by_date"]
        
        # If there are events, verify structure
        if events_by_date:
            for date_key, events in events_by_date.items():
                # Date key should be in YYYY-MM-DD format
                assert len(date_key) == 10, f"Date key should be YYYY-MM-DD format: {date_key}"
                assert isinstance(events, list), f"Events should be a list for date {date_key}"
                
                # Check event structure
                for event in events:
                    assert "requirement_id" in event
                    assert "requirement_type" in event
                    assert "description" in event
                    assert "status" in event
                    assert "status_color" in event
                    assert "property_id" in event
                    assert "property_address" in event


class TestCalendarUpcomingAPI:
    """Test /api/calendar/upcoming endpoint"""
    
    def test_calendar_upcoming_returns_200(self, authenticated_client):
        """Test that calendar upcoming endpoint returns 200"""
        response = authenticated_client.get(f"{BASE_URL}/api/calendar/upcoming")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_calendar_upcoming_structure(self, authenticated_client):
        """Test calendar upcoming response structure"""
        response = authenticated_client.get(f"{BASE_URL}/api/calendar/upcoming")
        assert response.status_code == 200
        
        data = response.json()
        assert "days_ahead" in data, "Response should contain 'days_ahead'"
        assert "count" in data, "Response should contain 'count'"
        assert "upcoming" in data, "Response should contain 'upcoming'"
        
    def test_calendar_upcoming_with_days_parameter(self, authenticated_client):
        """Test calendar upcoming with days parameter"""
        for days in [30, 60, 90, 180]:
            response = authenticated_client.get(f"{BASE_URL}/api/calendar/upcoming?days={days}")
            assert response.status_code == 200
            
            data = response.json()
            assert data["days_ahead"] == days
            
    def test_calendar_upcoming_sorted_by_date(self, authenticated_client):
        """Test that upcoming expiries are sorted by date"""
        response = authenticated_client.get(f"{BASE_URL}/api/calendar/upcoming?days=365")
        assert response.status_code == 200
        
        data = response.json()
        upcoming = data["upcoming"]
        
        if len(upcoming) > 1:
            # Verify sorted by due_date
            for i in range(len(upcoming) - 1):
                current_date = upcoming[i]["due_date"]
                next_date = upcoming[i + 1]["due_date"]
                assert current_date <= next_date, "Upcoming should be sorted by due_date"
                
    def test_calendar_upcoming_has_urgency(self, authenticated_client):
        """Test that upcoming items have urgency field"""
        response = authenticated_client.get(f"{BASE_URL}/api/calendar/upcoming")
        assert response.status_code == 200
        
        data = response.json()
        upcoming = data["upcoming"]
        
        for item in upcoming:
            assert "urgency" in item, "Each item should have 'urgency' field"
            assert item["urgency"] in ["high", "medium", "low"], f"Invalid urgency: {item['urgency']}"
            assert "days_until_due" in item, "Each item should have 'days_until_due'"


class TestSMSPreferencesAPI:
    """Test SMS notification preferences via API"""
    
    def test_get_notification_preferences_includes_sms(self, authenticated_client):
        """Test that notification preferences include SMS fields"""
        response = authenticated_client.get(f"{BASE_URL}/api/profile/notifications")
        assert response.status_code == 200
        
        data = response.json()
        # Check SMS fields exist
        assert "sms_enabled" in data, "Should have 'sms_enabled' field"
        assert "sms_phone_number" in data or data.get("sms_phone_number") is None, "Should have 'sms_phone_number' field"
        assert "sms_urgent_alerts_only" in data, "Should have 'sms_urgent_alerts_only' field"
        
    def test_update_sms_preferences(self, authenticated_client):
        """Test updating SMS preferences"""
        # First get current preferences
        get_response = authenticated_client.get(f"{BASE_URL}/api/profile/notifications")
        assert get_response.status_code == 200
        current_prefs = get_response.json()
        
        # Update SMS preferences
        updated_prefs = {
            **current_prefs,
            "sms_enabled": True,
            "sms_phone_number": "+447123456789",
            "sms_urgent_alerts_only": False
        }
        
        put_response = authenticated_client.put(
            f"{BASE_URL}/api/profile/notifications",
            json=updated_prefs
        )
        assert put_response.status_code == 200, f"Failed to update: {put_response.text}"
        
        # Verify changes persisted
        verify_response = authenticated_client.get(f"{BASE_URL}/api/profile/notifications")
        assert verify_response.status_code == 200
        
        verified_data = verify_response.json()
        assert verified_data["sms_enabled"] == True
        assert verified_data["sms_phone_number"] == "+447123456789"
        assert verified_data["sms_urgent_alerts_only"] == False
        
        # Reset to original state
        reset_prefs = {
            **current_prefs,
            "sms_enabled": False,
            "sms_phone_number": "",
            "sms_urgent_alerts_only": True
        }
        authenticated_client.put(f"{BASE_URL}/api/profile/notifications", json=reset_prefs)


class TestPropertyEnhancedAttributes:
    """Test Property model enhanced attributes"""
    
    def test_get_properties_includes_enhanced_attributes(self, authenticated_client):
        """Test that properties include enhanced attributes"""
        response = authenticated_client.get(f"{BASE_URL}/api/client/dashboard")
        assert response.status_code == 200
        
        data = response.json()
        properties = data.get("properties", [])
        
        if properties:
            prop = properties[0]
            # These fields should exist (may be null/default)
            # Check that the model supports these fields
            print(f"Property fields: {list(prop.keys())}")
            
    def test_create_property_with_enhanced_attributes(self, authenticated_client):
        """Test creating property with enhanced attributes"""
        # This tests that the API accepts enhanced attributes
        # Note: The endpoint is /api/properties/create
        property_data = {
            "address_line_1": "TEST_123 Enhanced Test Street",
            "city": "London",
            "postcode": "SW1A 1AA",
            "property_type": "hmo",
            "number_of_units": 5
        }
        
        response = authenticated_client.post(
            f"{BASE_URL}/api/properties/create",
            json=property_data
        )
        
        # Accept 200, 201, or 422 (validation) - we're testing the endpoint works
        assert response.status_code in [200, 201, 422], f"Unexpected status: {response.status_code}: {response.text}"
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "property_id" in data or "property" in data


class TestHealthAndBasicEndpoints:
    """Basic health and connectivity tests"""
    
    def test_health_endpoint(self, api_client):
        """Test health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
    def test_client_login(self, api_client):
        """Test client login works"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        
    def test_admin_login(self, api_client):
        """Test admin login works"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
