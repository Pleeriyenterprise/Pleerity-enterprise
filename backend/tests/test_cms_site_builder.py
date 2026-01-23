"""
CMS Site Builder API Tests - Iteration 52
Tests for Admin Site Builder CMS functionality:
- Page CRUD operations
- Block management (add, update, delete, reorder)
- Publishing workflow
- Revision history
- Media library
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestCMSPageManagement:
    """Test CMS Page CRUD operations"""
    
    def test_list_pages(self, admin_headers):
        """Test listing CMS pages"""
        response = requests.get(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to list pages: {response.text}"
        data = response.json()
        assert "pages" in data
        assert "total" in data
        assert isinstance(data["pages"], list)
        print(f"✓ Listed {len(data['pages'])} pages, total: {data['total']}")
    
    def test_list_pages_requires_auth(self):
        """Test that listing pages requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/cms/pages")
        assert response.status_code in [401, 403], "Should require auth"
        print("✓ List pages requires authentication")
    
    def test_create_page(self, admin_headers):
        """Test creating a new CMS page"""
        unique_slug = f"test-page-{uuid.uuid4().hex[:8]}"
        payload = {
            "slug": unique_slug,
            "title": "TEST Page Title",
            "description": "Test page description for CMS testing"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed to create page: {response.text}"
        data = response.json()
        assert data["slug"] == unique_slug
        assert data["title"] == "TEST Page Title"
        assert data["status"] == "DRAFT"
        assert "page_id" in data
        print(f"✓ Created page with ID: {data['page_id']}")
        return data["page_id"]
    
    def test_create_page_duplicate_slug(self, admin_headers):
        """Test that duplicate slugs are rejected"""
        # First create a page
        unique_slug = f"test-dup-{uuid.uuid4().hex[:8]}"
        payload = {"slug": unique_slug, "title": "First Page"}
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201
        
        # Try to create another with same slug
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 400, "Should reject duplicate slug"
        print("✓ Duplicate slug correctly rejected")
    
    def test_create_page_invalid_slug(self, admin_headers):
        """Test that invalid slugs are rejected"""
        payload = {
            "slug": "Invalid Slug With Spaces!",
            "title": "Test Page"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 422, f"Should reject invalid slug, got {response.status_code}"
        print("✓ Invalid slug correctly rejected")
    
    def test_get_page_by_id(self, admin_headers):
        """Test getting a page by ID"""
        # First create a page
        unique_slug = f"test-get-{uuid.uuid4().hex[:8]}"
        create_response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json={"slug": unique_slug, "title": "Get Test Page"}
        )
        assert create_response.status_code == 201
        page_id = create_response.json()["page_id"]
        
        # Get the page
        response = requests.get(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to get page: {response.text}"
        data = response.json()
        assert data["page_id"] == page_id
        assert data["slug"] == unique_slug
        print(f"✓ Retrieved page: {data['title']}")
    
    def test_get_page_not_found(self, admin_headers):
        """Test getting a non-existent page"""
        response = requests.get(
            f"{BASE_URL}/api/admin/cms/pages/PG-NONEXISTENT123",
            headers=admin_headers
        )
        assert response.status_code == 404, "Should return 404 for non-existent page"
        print("✓ Non-existent page returns 404")
    
    def test_update_page(self, admin_headers):
        """Test updating a page"""
        # Create a page
        unique_slug = f"test-update-{uuid.uuid4().hex[:8]}"
        create_response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json={"slug": unique_slug, "title": "Original Title"}
        )
        assert create_response.status_code == 201
        page_id = create_response.json()["page_id"]
        
        # Update the page
        update_payload = {
            "title": "Updated Title",
            "description": "Updated description"
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}",
            headers=admin_headers,
            json=update_payload
        )
        assert response.status_code == 200, f"Failed to update page: {response.text}"
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["description"] == "Updated description"
        print(f"✓ Updated page title to: {data['title']}")
    
    def test_delete_page(self, admin_headers):
        """Test archiving a page"""
        # Create a page
        unique_slug = f"test-delete-{uuid.uuid4().hex[:8]}"
        create_response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json={"slug": unique_slug, "title": "To Be Deleted"}
        )
        assert create_response.status_code == 201
        page_id = create_response.json()["page_id"]
        
        # Delete (archive) the page
        response = requests.delete(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to delete page: {response.text}"
        
        # Verify page is archived
        get_response = requests.get(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}",
            headers=admin_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "ARCHIVED"
        print("✓ Page archived successfully")


class TestCMSBlockManagement:
    """Test CMS Block operations"""
    
    @pytest.fixture
    def test_page(self, admin_headers):
        """Create a test page for block operations"""
        unique_slug = f"test-blocks-{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json={"slug": unique_slug, "title": "Block Test Page"}
        )
        assert response.status_code == 201
        return response.json()["page_id"]
    
    def test_add_hero_block(self, admin_headers, test_page):
        """Test adding a HERO block"""
        payload = {
            "block_type": "HERO",
            "content": {
                "headline": "Welcome to Our Site",
                "subheadline": "The best service provider",
                "cta_text": "Get Started",
                "cta_link": "/contact",
                "alignment": "center"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed to add block: {response.text}"
        data = response.json()
        assert data["block_type"] == "HERO"
        assert data["content"]["headline"] == "Welcome to Our Site"
        assert "block_id" in data
        print(f"✓ Added HERO block: {data['block_id']}")
        return data["block_id"]
    
    def test_add_text_block(self, admin_headers, test_page):
        """Test adding a TEXT_BLOCK"""
        payload = {
            "block_type": "TEXT_BLOCK",
            "content": {
                "title": "About Us",
                "body": "We are a leading provider of compliance services.",
                "alignment": "left"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed to add text block: {response.text}"
        data = response.json()
        assert data["block_type"] == "TEXT_BLOCK"
        print(f"✓ Added TEXT_BLOCK: {data['block_id']}")
    
    def test_add_cta_block(self, admin_headers, test_page):
        """Test adding a CTA block"""
        payload = {
            "block_type": "CTA",
            "content": {
                "headline": "Ready to Get Started?",
                "description": "Contact us today for a free consultation",
                "button_text": "Contact Us",
                "button_link": "/contact",
                "style": "primary"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed to add CTA block: {response.text}"
        print("✓ Added CTA block")
    
    def test_add_faq_block(self, admin_headers, test_page):
        """Test adding a FAQ block"""
        payload = {
            "block_type": "FAQ",
            "content": {
                "title": "Frequently Asked Questions",
                "items": [
                    {"question": "What services do you offer?", "answer": "We offer compliance audits and more."},
                    {"question": "How much does it cost?", "answer": "Pricing varies by service."}
                ]
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed to add FAQ block: {response.text}"
        print("✓ Added FAQ block")
    
    def test_add_block_invalid_content(self, admin_headers, test_page):
        """Test that invalid block content is rejected"""
        payload = {
            "block_type": "HERO",
            "content": {
                # Missing required 'headline' field
                "subheadline": "Only subheadline"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 400, f"Should reject invalid content, got {response.status_code}"
        print("✓ Invalid block content correctly rejected")
    
    def test_add_video_embed_youtube(self, admin_headers, test_page):
        """Test adding a VIDEO_EMBED block with YouTube URL"""
        payload = {
            "block_type": "VIDEO_EMBED",
            "content": {
                "title": "Our Introduction Video",
                "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "caption": "Watch our intro",
                "autoplay": False
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed to add video block: {response.text}"
        print("✓ Added VIDEO_EMBED block with YouTube URL")
    
    def test_add_video_embed_invalid_url(self, admin_headers, test_page):
        """Test that non-YouTube/Vimeo URLs are rejected"""
        payload = {
            "block_type": "VIDEO_EMBED",
            "content": {
                "title": "Malicious Video",
                "video_url": "https://malicious-site.com/video.mp4",
                "autoplay": False
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 400, f"Should reject non-YouTube/Vimeo URL, got {response.status_code}"
        print("✓ Non-YouTube/Vimeo URL correctly rejected")
    
    def test_update_block(self, admin_headers, test_page):
        """Test updating a block"""
        # Add a block first
        add_response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json={
                "block_type": "HERO",
                "content": {"headline": "Original Headline", "alignment": "center"}
            }
        )
        assert add_response.status_code == 201
        block_id = add_response.json()["block_id"]
        
        # Update the block
        update_payload = {
            "content": {"headline": "Updated Headline", "alignment": "left"}
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks/{block_id}",
            headers=admin_headers,
            json=update_payload
        )
        assert response.status_code == 200, f"Failed to update block: {response.text}"
        data = response.json()
        assert data["content"]["headline"] == "Updated Headline"
        print("✓ Block updated successfully")
    
    def test_toggle_block_visibility(self, admin_headers, test_page):
        """Test toggling block visibility"""
        # Add a block
        add_response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json={
                "block_type": "TEXT_BLOCK",
                "content": {"body": "Test content", "alignment": "left"}
            }
        )
        assert add_response.status_code == 201
        block_id = add_response.json()["block_id"]
        assert add_response.json()["visible"] == True
        
        # Toggle visibility off
        response = requests.put(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks/{block_id}",
            headers=admin_headers,
            json={"visible": False}
        )
        assert response.status_code == 200
        assert response.json()["visible"] == False
        print("✓ Block visibility toggled successfully")
    
    def test_delete_block(self, admin_headers, test_page):
        """Test deleting a block"""
        # Add a block
        add_response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json={
                "block_type": "SPACER",
                "content": {"height": "md"}
            }
        )
        assert add_response.status_code == 201
        block_id = add_response.json()["block_id"]
        
        # Delete the block
        response = requests.delete(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks/{block_id}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to delete block: {response.text}"
        print("✓ Block deleted successfully")
    
    def test_reorder_blocks(self, admin_headers, test_page):
        """Test reordering blocks"""
        # Add multiple blocks
        block_ids = []
        for i in range(3):
            response = requests.post(
                f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
                headers=admin_headers,
                json={
                    "block_type": "TEXT_BLOCK",
                    "content": {"body": f"Block {i}", "alignment": "left"}
                }
            )
            assert response.status_code == 201
            block_ids.append(response.json()["block_id"])
        
        # Reorder: reverse the order
        reversed_order = list(reversed(block_ids))
        response = requests.put(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks/reorder",
            headers=admin_headers,
            json={"block_order": reversed_order}
        )
        assert response.status_code == 200, f"Failed to reorder blocks: {response.text}"
        data = response.json()
        assert len(data) >= 3
        print("✓ Blocks reordered successfully")


class TestCMSPublishingWorkflow:
    """Test CMS publishing and revision workflow"""
    
    @pytest.fixture
    def test_page_with_blocks(self, admin_headers):
        """Create a test page with blocks for publishing tests"""
        unique_slug = f"test-publish-{uuid.uuid4().hex[:8]}"
        # Create page
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json={"slug": unique_slug, "title": "Publish Test Page"}
        )
        assert response.status_code == 201
        page_id = response.json()["page_id"]
        
        # Add a block
        requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}/blocks",
            headers=admin_headers,
            json={
                "block_type": "HERO",
                "content": {"headline": "Test Headline", "alignment": "center"}
            }
        )
        return page_id
    
    def test_publish_page(self, admin_headers, test_page_with_blocks):
        """Test publishing a page"""
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page_with_blocks}/publish",
            headers=admin_headers,
            json={"notes": "Initial publish for testing"}
        )
        assert response.status_code == 200, f"Failed to publish page: {response.text}"
        data = response.json()
        assert data["status"] == "PUBLISHED"
        assert data["current_version"] == 1
        assert data["published_at"] is not None
        print(f"✓ Page published, version: {data['current_version']}")
    
    def test_publish_creates_revision(self, admin_headers, test_page_with_blocks):
        """Test that publishing creates a revision"""
        # Publish the page
        requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page_with_blocks}/publish",
            headers=admin_headers,
            json={"notes": "First publish"}
        )
        
        # Get revisions
        response = requests.get(
            f"{BASE_URL}/api/admin/cms/pages/{test_page_with_blocks}/revisions",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to get revisions: {response.text}"
        data = response.json()
        # Response is wrapped in {"revisions": [...]}
        revisions = data.get("revisions", data) if isinstance(data, dict) else data
        assert len(revisions) >= 1
        assert revisions[0]["version"] >= 1
        print(f"✓ Revision created, found {len(revisions)} revision(s)")
    
    def test_edit_published_page_creates_draft(self, admin_headers, test_page_with_blocks):
        """Test that editing a published page reverts to draft"""
        # Publish first
        requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page_with_blocks}/publish",
            headers=admin_headers,
            json={}
        )
        
        # Edit the page
        response = requests.put(
            f"{BASE_URL}/api/admin/cms/pages/{test_page_with_blocks}",
            headers=admin_headers,
            json={"title": "Modified Title"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "DRAFT"
        print("✓ Editing published page creates draft state")
    
    def test_rollback_to_revision(self, admin_headers, test_page_with_blocks):
        """Test rolling back to a previous revision"""
        page_id = test_page_with_blocks
        
        # Publish version 1
        requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}/publish",
            headers=admin_headers,
            json={"notes": "Version 1"}
        )
        
        # Modify and publish version 2
        requests.put(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}",
            headers=admin_headers,
            json={"title": "Version 2 Title"}
        )
        requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}/publish",
            headers=admin_headers,
            json={"notes": "Version 2"}
        )
        
        # Get revisions
        revisions_response = requests.get(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}/revisions",
            headers=admin_headers
        )
        data = revisions_response.json()
        # Response is wrapped in {"revisions": [...]}
        revisions = data.get("revisions", data) if isinstance(data, dict) else data
        assert len(revisions) >= 2, f"Expected at least 2 revisions, got {len(revisions)}"
        
        # Rollback to version 1
        v1_revision = next((r for r in revisions if r["version"] == 1), None)
        assert v1_revision is not None
        
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{page_id}/rollback",
            headers=admin_headers,
            json={"revision_id": v1_revision["revision_id"], "notes": "Rolling back to v1"}
        )
        assert response.status_code == 200, f"Failed to rollback: {response.text}"
        data = response.json()
        assert data["status"] == "DRAFT"  # Rollback creates draft
        print("✓ Rollback to previous revision successful")


class TestCMSMediaLibrary:
    """Test CMS Media Library operations"""
    
    def test_list_media(self, admin_headers):
        """Test listing media items"""
        response = requests.get(
            f"{BASE_URL}/api/admin/cms/media",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to list media: {response.text}"
        data = response.json()
        assert "media" in data
        assert "total" in data
        print(f"✓ Listed {len(data['media'])} media items")
    
    def test_list_media_requires_auth(self):
        """Test that media listing requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/cms/media")
        assert response.status_code in [401, 403]
        print("✓ Media listing requires authentication")


class TestExistingTestPage:
    """Test operations on the existing 'homepage' test page"""
    
    def test_get_existing_homepage(self, admin_headers):
        """Test getting the existing homepage"""
        response = requests.get(
            f"{BASE_URL}/api/admin/cms/pages/PG-314F2A5B4B67",
            headers=admin_headers
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Found existing homepage: {data['title']}, status: {data['status']}")
            print(f"  Blocks: {len(data['blocks'])}, Version: {data['current_version']}")
        else:
            print(f"Note: Existing homepage not found (status {response.status_code})")
    
    def test_get_published_page_public(self, admin_headers):
        """Test getting published page content for public rendering"""
        response = requests.get(
            f"{BASE_URL}/api/cms/pages/homepage",
            headers={"Content-Type": "application/json"}  # No auth needed for public
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Public page accessible: {data.get('title', 'N/A')}")
        else:
            print(f"Note: Public homepage not accessible (status {response.status_code})")


class TestBlockTypes:
    """Test all available block types"""
    
    @pytest.fixture
    def test_page(self, admin_headers):
        """Create a test page for block type tests"""
        unique_slug = f"test-blocktypes-{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages",
            headers=admin_headers,
            json={"slug": unique_slug, "title": "Block Types Test"}
        )
        assert response.status_code == 201
        return response.json()["page_id"]
    
    def test_add_pricing_table_block(self, admin_headers, test_page):
        """Test adding PRICING_TABLE block"""
        payload = {
            "block_type": "PRICING_TABLE",
            "content": {
                "title": "Our Pricing",
                "subtitle": "Choose the plan that fits your needs",
                "tiers": [
                    {
                        "name": "Basic",
                        "price": "£29/mo",
                        "description": "For small landlords",
                        "features": ["5 properties", "Email support"],
                        "cta_text": "Get Started",
                        "cta_link": "/signup",
                        "is_highlighted": False
                    },
                    {
                        "name": "Pro",
                        "price": "£99/mo",
                        "description": "For growing portfolios",
                        "features": ["Unlimited properties", "Priority support"],
                        "cta_text": "Get Started",
                        "cta_link": "/signup",
                        "is_highlighted": True
                    }
                ]
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed: {response.text}"
        print("✓ Added PRICING_TABLE block")
    
    def test_add_features_grid_block(self, admin_headers, test_page):
        """Test adding FEATURES_GRID block"""
        payload = {
            "block_type": "FEATURES_GRID",
            "content": {
                "title": "Our Features",
                "subtitle": "Everything you need",
                "features": [
                    {"icon": "check", "title": "Feature 1", "description": "Description 1"},
                    {"icon": "star", "title": "Feature 2", "description": "Description 2"}
                ],
                "columns": 3
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed: {response.text}"
        print("✓ Added FEATURES_GRID block")
    
    def test_add_testimonials_block(self, admin_headers, test_page):
        """Test adding TESTIMONIALS block"""
        payload = {
            "block_type": "TESTIMONIALS",
            "content": {
                "title": "What Our Clients Say",
                "testimonials": [
                    {
                        "quote": "Excellent service!",
                        "author_name": "John Doe",
                        "author_title": "Property Manager",
                        "author_company": "ABC Properties",
                        "rating": 5
                    }
                ],
                "style": "cards"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed: {response.text}"
        print("✓ Added TESTIMONIALS block")
    
    def test_add_contact_form_block(self, admin_headers, test_page):
        """Test adding CONTACT_FORM block"""
        payload = {
            "block_type": "CONTACT_FORM",
            "content": {
                "title": "Contact Us",
                "subtitle": "We'd love to hear from you",
                "form_type": "contact",
                "success_message": "Thanks for reaching out!"
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed: {response.text}"
        print("✓ Added CONTACT_FORM block")
    
    def test_add_stats_bar_block(self, admin_headers, test_page):
        """Test adding STATS_BAR block"""
        payload = {
            "block_type": "STATS_BAR",
            "content": {
                "stats": [
                    {"value": "500+", "label": "Properties Managed"},
                    {"value": "98%", "label": "Client Satisfaction"},
                    {"value": "24/7", "label": "Support"}
                ]
            }
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed: {response.text}"
        print("✓ Added STATS_BAR block")
    
    def test_add_spacer_block(self, admin_headers, test_page):
        """Test adding SPACER block"""
        payload = {
            "block_type": "SPACER",
            "content": {"height": "lg"}
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/cms/pages/{test_page}/blocks",
            headers=admin_headers,
            json=payload
        )
        assert response.status_code == 201, f"Failed: {response.text}"
        print("✓ Added SPACER block")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
