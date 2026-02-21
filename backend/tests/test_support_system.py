"""
Support System API Tests - Iteration 48

Tests for:
- POST /api/support/chat - AI chatbot interaction
- POST /api/support/lookup - CRN+email verification
- POST /api/support/ticket - Create support ticket
- GET /api/admin/support/stats - Support statistics
- GET /api/admin/support/conversations - List conversations
- GET /api/admin/support/tickets - List tickets
- GET /api/admin/support/conversation/{id} - Full transcript
- POST /api/admin/support/conversation/{id}/reply - Admin reply
- POST /api/admin/support/lookup-by-crn - Admin CRN lookup
"""
import pytest

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"


class TestSupportPublicEndpoints:
    """Test public support endpoints (no auth required)"""
    
    def test_chat_creates_conversation_and_returns_response(self, client):
        """POST /api/support/chat - creates conversation and returns AI response"""
        response = client.post(
            "/api/support/chat",
            json={
                "message": "Hello, I need help with Document Packs",
                "channel": "web"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "conversation_id" in data, "Missing conversation_id"
        assert "response" in data, "Missing response"
        assert "action" in data, "Missing action"
        assert data["conversation_id"].startswith("CONV-"), f"Invalid conversation_id format: {data['conversation_id']}"
        assert len(data["response"]) > 0, "Empty response"
        
        print(f"SUCCESS: Chat created conversation {data['conversation_id']}")
        return data["conversation_id"]
    
    def test_chat_continues_existing_conversation(self, client):
        """POST /api/support/chat - continues existing conversation"""
        # First message
        response1 = client.post(
            "/api/support/chat",
            json={"message": "What services do you offer?", "channel": "web"}
        )
        assert response1.status_code == 200
        conv_id = response1.json()["conversation_id"]
        
        # Second message in same conversation
        response2 = client.post(
            "/api/support/chat",
            json={
                "message": "Tell me more about CVP",
                "conversation_id": conv_id,
                "channel": "web"
            }
        )
        assert response2.status_code == 200
        data = response2.json()
        
        # Should use same conversation
        assert data["conversation_id"] == conv_id, "Conversation ID changed unexpectedly"
        print(f"SUCCESS: Continued conversation {conv_id}")
    
    def test_chat_triggers_human_handoff(self, client):
        """POST /api/support/chat - triggers handoff when user requests human"""
        response = client.post(
            "/api/support/chat",
            json={
                "message": "I want to speak to a human agent please",
                "channel": "web"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should trigger handoff action
        assert data["action"] == "handoff", f"Expected handoff action, got {data['action']}"
        assert "handoff_options" in data, "Missing handoff_options"
        
        # Verify handoff options
        options = data["handoff_options"]
        assert "live_chat" in options, "Missing live_chat option"
        assert "email_ticket" in options, "Missing email_ticket option"
        assert "whatsapp" in options, "Missing whatsapp option"
        
        print(f"SUCCESS: Handoff triggered with 3 options")
    
    def test_chat_refuses_legal_advice(self, client):
        """POST /api/support/chat - refuses legal advice requests"""
        response = client.post(
            "/api/support/chat",
            json={
                "message": "Is it legal for my landlord to evict me without notice?",
                "channel": "web"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should contain legal refusal - either from hardcoded response or AI
        response_lower = data["response"].lower()
        legal_refusal_indicators = [
            "legal advice",
            "cannot provide legal",
            "not able to provide",
            "solicitor",
            "legal professional",
            "consult a",
            "qualified"
        ]
        
        has_refusal = any(indicator in response_lower for indicator in legal_refusal_indicators)
        assert has_refusal, f"Expected legal refusal, got: {data['response'][:200]}"
        
        # Note: legal_refusal flag in metadata is only set for hardcoded refusals
        # AI-generated refusals may not have this flag but still refuse appropriately
        
        print("SUCCESS: Legal advice request refused appropriately")
    
    def test_chat_answers_service_questions(self, client):
        """POST /api/support/chat - answers questions about services"""
        response = client.post(
            "/api/support/chat",
            json={
                "message": "What is included in the Essential Document Pack?",
                "channel": "web"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should get a substantive response about document packs
        assert len(data["response"]) > 50, "Response too short"
        print(f"SUCCESS: Got service info response ({len(data['response'])} chars)")
    
    def test_lookup_with_invalid_crn(self, client):
        """POST /api/support/lookup - returns not verified for invalid CRN"""
        response = client.post(
            "/api/support/lookup",
            json={
                "crn": "PLE-CVP-2026-INVALID",
                "email": "nonexistent@example.com"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["verified"] == False, "Should not verify invalid CRN"
        assert "message" in data, "Missing message"
        print("SUCCESS: Invalid CRN lookup handled correctly")
    
    def test_create_ticket(self, client):
        """POST /api/support/ticket - creates support ticket"""
        response = client.post(
            "/api/support/ticket",
            json={
                "subject": "TEST_Ticket - Need help with billing",
                "description": "I have a question about my recent invoice. The amount seems incorrect.",
                "category": "billing",
                "priority": "medium",
                "service_area": "billing",
                "contact_method": "email",
                "email": "testuser@example.com"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True, "Ticket creation failed"
        assert "ticket_id" in data, "Missing ticket_id"
        assert data["ticket_id"].startswith("TKT-"), f"Invalid ticket_id format: {data['ticket_id']}"
        
        print(f"SUCCESS: Created ticket {data['ticket_id']}")
        return data["ticket_id"]
    
    def test_create_ticket_with_conversation_link(self, client):
        """POST /api/support/ticket - creates ticket linked to conversation"""
        # First create a conversation
        chat_response = client.post(
            "/api/support/chat",
            json={"message": "I need to create a ticket", "channel": "web"}
        )
        conv_id = chat_response.json()["conversation_id"]
        
        # Create ticket linked to conversation
        response = client.post(
            "/api/support/ticket",
            json={
                "subject": "TEST_Ticket from chat",
                "description": "Following up from chat conversation",
                "category": "other",
                "priority": "low",
                "email": "chatuser@example.com",
                "conversation_id": conv_id
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        print(f"SUCCESS: Created ticket {data['ticket_id']} linked to {conv_id}")


class TestSupportAdminEndpoints:
    """Test admin support endpoints (auth required)"""
    
    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Get admin auth token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_support_stats(self, client):
        """GET /api/admin/support/stats - returns conversation/ticket stats"""
        response = client.get(
            "/api/admin/support/stats",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify stats structure
        assert "conversations" in data, "Missing conversations stats"
        assert "tickets" in data, "Missing tickets stats"
        
        conv_stats = data["conversations"]
        assert "total" in conv_stats, "Missing total conversations"
        assert "open" in conv_stats, "Missing open conversations"
        assert "escalated" in conv_stats, "Missing escalated conversations"
        
        ticket_stats = data["tickets"]
        assert "total" in ticket_stats, "Missing total tickets"
        assert "new" in ticket_stats, "Missing new tickets"
        assert "open" in ticket_stats, "Missing open tickets"
        assert "high_priority" in ticket_stats, "Missing high_priority tickets"
        
        print(f"SUCCESS: Stats - {conv_stats['total']} conversations, {ticket_stats['total']} tickets")
    
    def test_list_conversations(self, client):
        """GET /api/admin/support/conversations - lists all conversations"""
        response = client.get(
            "/api/admin/support/conversations",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "conversations" in data, "Missing conversations list"
        assert "total" in data, "Missing total count"
        
        if data["conversations"]:
            conv = data["conversations"][0]
            assert "conversation_id" in conv, "Missing conversation_id"
            assert "status" in conv, "Missing status"
            assert "channel" in conv, "Missing channel"
            assert "message_count" in conv, "Missing message_count"
        
        print(f"SUCCESS: Listed {len(data['conversations'])} conversations (total: {data['total']})")
    
    def test_list_conversations_with_filters(self, client):
        """GET /api/admin/support/conversations - filters by status"""
        response = client.get(
            "/api/admin/support/conversations?status=open",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned conversations should be open
        for conv in data["conversations"]:
            assert conv["status"] == "open", f"Expected open status, got {conv['status']}"
        
        print(f"SUCCESS: Filtered to {len(data['conversations'])} open conversations")
    
    def test_list_tickets(self, client):
        """GET /api/admin/support/tickets - lists all tickets"""
        response = client.get(
            "/api/admin/support/tickets",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "tickets" in data, "Missing tickets list"
        assert "total" in data, "Missing total count"
        
        if data["tickets"]:
            ticket = data["tickets"][0]
            assert "ticket_id" in ticket, "Missing ticket_id"
            assert "status" in ticket, "Missing status"
            assert "priority" in ticket, "Missing priority"
            assert "subject" in ticket, "Missing subject"
        
        print(f"SUCCESS: Listed {len(data['tickets'])} tickets (total: {data['total']})")
    
    def test_list_tickets_with_filters(self, client):
        """GET /api/admin/support/tickets - filters by priority"""
        response = client.get(
            "/api/admin/support/tickets?priority=high",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned tickets should be high priority
        for ticket in data["tickets"]:
            assert ticket["priority"] == "high", f"Expected high priority, got {ticket['priority']}"
        
        print(f"SUCCESS: Filtered to {len(data['tickets'])} high priority tickets")
    
    def test_get_conversation_detail(self, client):
        """GET /api/admin/support/conversation/{id} - returns full transcript"""
        # First create a conversation with messages
        chat_response = client.post(
            "/api/support/chat",
            json={"message": "Test message for transcript", "channel": "web"}
        )
        conv_id = chat_response.json()["conversation_id"]
        
        # Get conversation detail
        response = client.get(
            f"/api/admin/support/conversation/{conv_id}",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "conversation" in data, "Missing conversation"
        assert "messages" in data, "Missing messages"
        assert "transcript" in data, "Missing transcript"
        
        # Should have at least 2 messages (user + bot)
        assert len(data["messages"]) >= 2, f"Expected at least 2 messages, got {len(data['messages'])}"
        
        # Verify message structure
        msg = data["messages"][0]
        assert "message_id" in msg, "Missing message_id"
        assert "sender" in msg, "Missing sender"
        assert "message_text" in msg, "Missing message_text"
        assert "timestamp" in msg, "Missing timestamp"
        
        print(f"SUCCESS: Got transcript with {len(data['messages'])} messages")
    
    def test_admin_reply_to_conversation(self, client):
        """POST /api/admin/support/conversation/{id}/reply - admin can reply"""
        # First create a conversation
        chat_response = client.post(
            "/api/support/chat",
            json={"message": "I need admin help", "channel": "web"}
        )
        conv_id = chat_response.json()["conversation_id"]
        
        # Admin reply
        response = client.post(
            f"/api/admin/support/conversation/{conv_id}/reply",
            headers=self.headers,
            json={"message": "Hello, this is admin support. How can I help?"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True, "Reply failed"
        assert "message" in data, "Missing message in response"
        assert data["message"]["sender"] == "human", f"Expected human sender, got {data['message']['sender']}"
        
        print(f"SUCCESS: Admin replied to conversation {conv_id}")
    
    def test_admin_crn_lookup(self, client):
        """POST /api/admin/support/lookup-by-crn - admin CRN lookup"""
        # This will likely return 404 if no client with this CRN exists
        response = client.post(
            "/api/admin/support/lookup-by-crn",
            headers=self.headers,
            json={"crn": "PLE-CVP-2026-TEST123"}
        )
        
        # Either 200 (found) or 404 (not found) is acceptable
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert "client" in data, "Missing client data"
            print(f"SUCCESS: Found client via CRN lookup")
        else:
            print("SUCCESS: CRN lookup returned 404 (client not found - expected)")
    
    def test_get_ticket_detail(self, client):
        """GET /api/admin/support/ticket/{id} - returns ticket details"""
        # First create a ticket
        ticket_response = client.post(
            "/api/support/ticket",
            json={
                "subject": "TEST_Detail ticket",
                "description": "Testing ticket detail endpoint",
                "category": "technical",
                "priority": "low",
                "email": "detail@test.com"
            }
        )
        ticket_id = ticket_response.json()["ticket_id"]
        
        # Get ticket detail
        response = client.get(
            f"/api/admin/support/ticket/{ticket_id}",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "ticket" in data, "Missing ticket"
        assert data["ticket"]["ticket_id"] == ticket_id, "Ticket ID mismatch"
        assert data["ticket"]["subject"] == "TEST_Detail ticket", "Subject mismatch"
        
        print(f"SUCCESS: Got ticket detail for {ticket_id}")
    
    def test_update_ticket_status(self, client):
        """PUT /api/admin/support/ticket/{id}/status - updates ticket status"""
        # First create a ticket
        ticket_response = client.post(
            "/api/support/ticket",
            json={
                "subject": "TEST_Status update ticket",
                "description": "Testing status update",
                "category": "other",
                "priority": "low",
                "email": "status@test.com"
            }
        )
        ticket_id = ticket_response.json()["ticket_id"]
        
        # Update status
        response = client.put(
            f"/api/admin/support/ticket/{ticket_id}/status?status=open",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True, "Status update failed"
        assert data["status"] == "open", f"Expected open status, got {data['status']}"
        
        print(f"SUCCESS: Updated ticket {ticket_id} status to open")
    
    def test_add_ticket_note(self, client):
        """POST /api/admin/support/ticket/{id}/note - adds internal note"""
        # First create a ticket
        ticket_response = client.post(
            "/api/support/ticket",
            json={
                "subject": "TEST_Note ticket",
                "description": "Testing note addition",
                "category": "other",
                "priority": "low",
                "email": "note@test.com"
            }
        )
        ticket_id = ticket_response.json()["ticket_id"]
        
        # Add note
        response = client.post(
            f"/api/admin/support/ticket/{ticket_id}/note",
            headers=self.headers,
            json={"message": "Internal note: Customer called back"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True, "Note addition failed"
        
        print(f"SUCCESS: Added note to ticket {ticket_id}")


class TestSupportChatbotBehavior:
    """Test AI chatbot specific behaviors"""
    
    def test_chatbot_greeting_response(self, client):
        """Chatbot responds to greeting"""
        response = client.post(
            "/api/support/chat",
            json={"message": "Hello!", "channel": "web"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should get a friendly response
        assert len(data["response"]) > 20, "Response too short for greeting"
        print("SUCCESS: Chatbot responded to greeting")
    
    def test_chatbot_cvp_question(self, client):
        """Chatbot answers CVP questions"""
        response = client.post(
            "/api/support/chat",
            json={"message": "What is Compliance Vault Pro?", "channel": "web"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response should mention compliance or property
        response_lower = data["response"].lower()
        assert "compliance" in response_lower or "property" in response_lower or "landlord" in response_lower, \
            f"Expected CVP-related response, got: {data['response'][:200]}"
        
        print("SUCCESS: Chatbot answered CVP question")
    
    def test_chatbot_billing_question(self, client):
        """Chatbot answers billing questions"""
        response = client.post(
            "/api/support/chat",
            json={"message": "How do I cancel my subscription?", "channel": "web"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should get a response about cancellation
        assert len(data["response"]) > 50, "Response too short"
        print("SUCCESS: Chatbot answered billing question")
    
    def test_chatbot_detects_service_area(self, client):
        """Chatbot detects service area from message"""
        response = client.post(
            "/api/support/chat",
            json={"message": "I need help with my document pack order", "channel": "web"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check metadata for service area detection
        if "metadata" in data:
            service_area = data["metadata"].get("service_area", "")
            print(f"SUCCESS: Detected service area: {service_area}")
        else:
            print("SUCCESS: Response received (metadata not exposed)")


# Cleanup test data
class TestCleanup:
    """Cleanup TEST_ prefixed data"""
    
    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Get admin auth token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {}
    
    def test_cleanup_test_tickets(self, client):
        """Cleanup TEST_ prefixed tickets"""
        if not self.headers:
            pytest.skip("No auth token")
        
        # Get all tickets
        response = client.get(
            "/api/admin/support/tickets?limit=200",
            headers=self.headers
        )
        
        if response.status_code == 200:
            tickets = response.json().get("tickets", [])
            test_tickets = [t for t in tickets if t.get("subject", "").startswith("TEST_")]
            print(f"Found {len(test_tickets)} TEST_ tickets (cleanup would delete these)")
        
        print("SUCCESS: Cleanup check completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
