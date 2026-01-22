"""
Blog API Tests - Testing Admin Blog CRUD and Public Blog endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestBlogAPI:
    """Blog API endpoint tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    # ==================
    # ADMIN ENDPOINTS
    # ==================
    
    def test_admin_list_posts(self, auth_headers):
        """Test GET /api/blog/admin/posts - List all posts (admin)"""
        response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to list posts: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "posts" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        assert isinstance(data["posts"], list)
        print(f"Admin posts list: {data['total']} total posts found")
    
    def test_admin_get_categories(self, auth_headers):
        """Test GET /api/blog/admin/categories - Get categories"""
        response = requests.get(
            f"{BASE_URL}/api/blog/admin/categories",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get categories: {response.text}"
        data = response.json()
        
        assert "categories" in data
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) > 0, "No categories found"
        print(f"Categories: {data['categories']}")
    
    def test_admin_get_tags(self, auth_headers):
        """Test GET /api/blog/admin/tags - Get tags"""
        response = requests.get(
            f"{BASE_URL}/api/blog/admin/tags",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get tags: {response.text}"
        data = response.json()
        
        assert "tags" in data
        assert isinstance(data["tags"], list)
        print(f"Tags: {data['tags']}")
    
    def test_admin_create_post(self, auth_headers):
        """Test POST /api/blog/admin/posts - Create new post"""
        test_post = {
            "title": "TEST_Blog Post for Testing",
            "slug": f"test-blog-post-{int(time.time())}",
            "excerpt": "This is a test blog post excerpt for automated testing.",
            "content": "This is the full content of the test blog post. It contains enough text to pass validation.",
            "category": "Compliance",
            "tags": ["test", "automation"],
            "status": "draft"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/blog/admin/posts",
            headers=auth_headers,
            json=test_post
        )
        assert response.status_code == 200, f"Failed to create post: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert "post" in data
        assert data["post"]["title"] == test_post["title"]
        assert data["post"]["category"] == test_post["category"]
        assert "id" in data["post"]
        
        # Store post ID for later tests
        TestBlogAPI.created_post_id = data["post"]["id"]
        TestBlogAPI.created_post_slug = data["post"]["slug"]
        print(f"Created post ID: {TestBlogAPI.created_post_id}")
        return data["post"]["id"]
    
    def test_admin_get_single_post(self, auth_headers):
        """Test GET /api/blog/admin/posts/{id} - Get single post"""
        post_id = getattr(TestBlogAPI, 'created_post_id', None)
        if not post_id:
            pytest.skip("No post created to fetch")
        
        response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get post: {response.text}"
        data = response.json()
        
        assert "post" in data
        assert data["post"]["id"] == post_id
        print(f"Fetched post: {data['post']['title']}")
    
    def test_admin_update_post(self, auth_headers):
        """Test PUT /api/blog/admin/posts/{id} - Update post"""
        post_id = getattr(TestBlogAPI, 'created_post_id', None)
        if not post_id:
            pytest.skip("No post created to update")
        
        update_data = {
            "title": "TEST_Updated Blog Post Title",
            "excerpt": "Updated excerpt for testing",
            "tags": ["test", "updated", "automation"]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200, f"Failed to update post: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert data["post"]["title"] == update_data["title"]
        assert data["post"]["excerpt"] == update_data["excerpt"]
        print(f"Updated post: {data['post']['title']}")
        
        # Verify update persisted
        verify_response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers
        )
        verify_data = verify_response.json()
        assert verify_data["post"]["title"] == update_data["title"]
    
    def test_admin_publish_post(self, auth_headers):
        """Test POST /api/blog/admin/posts/{id}/publish - Publish post"""
        post_id = getattr(TestBlogAPI, 'created_post_id', None)
        if not post_id:
            pytest.skip("No post created to publish")
        
        response = requests.post(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}/publish",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to publish post: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        print(f"Published post: {post_id}")
        
        # Verify post is now published
        verify_response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers
        )
        verify_data = verify_response.json()
        assert verify_data["post"]["status"] == "published"
    
    def test_admin_unpublish_post(self, auth_headers):
        """Test POST /api/blog/admin/posts/{id}/unpublish - Unpublish post"""
        post_id = getattr(TestBlogAPI, 'created_post_id', None)
        if not post_id:
            pytest.skip("No post created to unpublish")
        
        response = requests.post(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}/unpublish",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to unpublish post: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        print(f"Unpublished post: {post_id}")
        
        # Verify post is now draft
        verify_response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers
        )
        verify_data = verify_response.json()
        assert verify_data["post"]["status"] == "draft"
    
    def test_admin_filter_posts_by_status(self, auth_headers):
        """Test filtering posts by status"""
        response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts?status=published",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned posts should be published
        for post in data["posts"]:
            assert post["status"] == "published", f"Post {post['id']} is not published"
        print(f"Found {len(data['posts'])} published posts")
    
    def test_admin_filter_posts_by_category(self, auth_headers):
        """Test filtering posts by category"""
        response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts?category=Compliance",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned posts should be in Compliance category
        for post in data["posts"]:
            assert post["category"] == "Compliance", f"Post {post['id']} is not in Compliance category"
        print(f"Found {len(data['posts'])} Compliance posts")
    
    def test_admin_search_posts(self, auth_headers):
        """Test searching posts"""
        response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts?search=TEST_",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Search found {len(data['posts'])} posts matching 'TEST_'")
    
    # ==================
    # PUBLIC ENDPOINTS
    # ==================
    
    def test_public_list_posts(self):
        """Test GET /api/blog/posts - List published posts (public)"""
        response = requests.get(f"{BASE_URL}/api/blog/posts")
        assert response.status_code == 200, f"Failed to list public posts: {response.text}"
        data = response.json()
        
        assert "posts" in data
        assert "total" in data
        assert isinstance(data["posts"], list)
        
        # All posts should be published
        for post in data["posts"]:
            assert post["status"] == "published", f"Non-published post in public list: {post['id']}"
        print(f"Public posts: {data['total']} published posts found")
    
    def test_public_get_categories(self):
        """Test GET /api/blog/categories - Get public categories with counts"""
        response = requests.get(f"{BASE_URL}/api/blog/categories")
        assert response.status_code == 200, f"Failed to get public categories: {response.text}"
        data = response.json()
        
        assert "categories" in data
        assert isinstance(data["categories"], list)
        
        # Each category should have name and count
        for cat in data["categories"]:
            assert "name" in cat
            assert "count" in cat
        print(f"Public categories: {data['categories']}")
    
    def test_public_get_popular_tags(self):
        """Test GET /api/blog/tags/popular - Get popular tags"""
        response = requests.get(f"{BASE_URL}/api/blog/tags/popular")
        assert response.status_code == 200, f"Failed to get popular tags: {response.text}"
        data = response.json()
        
        assert "tags" in data
        assert isinstance(data["tags"], list)
        
        # Each tag should have name and count
        for tag in data["tags"]:
            assert "name" in tag
            assert "count" in tag
        print(f"Popular tags: {data['tags']}")
    
    def test_public_get_featured_posts(self):
        """Test GET /api/blog/featured - Get featured posts"""
        response = requests.get(f"{BASE_URL}/api/blog/featured")
        assert response.status_code == 200, f"Failed to get featured posts: {response.text}"
        data = response.json()
        
        assert "posts" in data
        assert isinstance(data["posts"], list)
        print(f"Featured posts: {len(data['posts'])} posts")
    
    def test_public_filter_by_category(self):
        """Test filtering public posts by category"""
        response = requests.get(f"{BASE_URL}/api/blog/posts?category=Compliance")
        assert response.status_code == 200
        data = response.json()
        
        for post in data["posts"]:
            assert post["category"] == "Compliance"
        print(f"Found {len(data['posts'])} public Compliance posts")
    
    def test_public_search_posts(self):
        """Test searching public posts"""
        response = requests.get(f"{BASE_URL}/api/blog/posts?search=landlord")
        assert response.status_code == 200
        data = response.json()
        print(f"Public search found {len(data['posts'])} posts matching 'landlord'")
    
    def test_public_get_single_post_by_slug(self, auth_headers):
        """Test GET /api/blog/posts/{slug} - Get single post by slug"""
        # First, publish the test post so it's accessible publicly
        post_id = getattr(TestBlogAPI, 'created_post_id', None)
        post_slug = getattr(TestBlogAPI, 'created_post_slug', None)
        
        if not post_id or not post_slug:
            pytest.skip("No test post available")
        
        # Publish the post first
        requests.post(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}/publish",
            headers=auth_headers
        )
        
        # Now fetch by slug
        response = requests.get(f"{BASE_URL}/api/blog/posts/{post_slug}")
        assert response.status_code == 200, f"Failed to get post by slug: {response.text}"
        data = response.json()
        
        assert "post" in data
        assert data["post"]["slug"] == post_slug
        print(f"Fetched public post: {data['post']['title']}")
    
    def test_public_view_count_increment(self, auth_headers):
        """Test that view count increments on post view"""
        post_id = getattr(TestBlogAPI, 'created_post_id', None)
        post_slug = getattr(TestBlogAPI, 'created_post_slug', None)
        
        if not post_id or not post_slug:
            pytest.skip("No test post available")
        
        # Get initial view count
        initial_response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers
        )
        initial_count = initial_response.json()["post"]["view_count"]
        
        # View the post publicly
        requests.get(f"{BASE_URL}/api/blog/posts/{post_slug}")
        
        # Check view count increased
        after_response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers
        )
        after_count = after_response.json()["post"]["view_count"]
        
        assert after_count > initial_count, f"View count did not increment: {initial_count} -> {after_count}"
        print(f"View count incremented: {initial_count} -> {after_count}")
    
    def test_public_post_not_found(self):
        """Test 404 for non-existent post slug"""
        response = requests.get(f"{BASE_URL}/api/blog/posts/non-existent-slug-12345")
        assert response.status_code == 404
        print("Correctly returned 404 for non-existent post")
    
    # ==================
    # CLEANUP
    # ==================
    
    def test_admin_delete_post(self, auth_headers):
        """Test DELETE /api/blog/admin/posts/{id} - Delete post (cleanup)"""
        post_id = getattr(TestBlogAPI, 'created_post_id', None)
        if not post_id:
            pytest.skip("No post created to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to delete post: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        print(f"Deleted post: {post_id}")
        
        # Verify post is deleted
        verify_response = requests.get(
            f"{BASE_URL}/api/blog/admin/posts/{post_id}",
            headers=auth_headers
        )
        assert verify_response.status_code == 404, "Post should be deleted"
    
    def test_admin_delete_invalid_post(self, auth_headers):
        """Test deleting non-existent post returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/blog/admin/posts/000000000000000000000000",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("Correctly returned 404 for non-existent post deletion")


class TestBlogAPIUnauthorized:
    """Test unauthorized access to admin endpoints"""
    
    def test_admin_posts_without_auth(self):
        """Admin posts endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/blog/admin/posts")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("Admin posts correctly requires authentication")
    
    def test_admin_create_without_auth(self):
        """Creating post requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/blog/admin/posts",
            json={"title": "Test", "content": "Test content"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("Create post correctly requires authentication")
    
    def test_admin_categories_without_auth(self):
        """Admin categories endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/blog/admin/categories")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("Admin categories correctly requires authentication")
