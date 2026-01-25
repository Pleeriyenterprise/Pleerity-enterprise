"""ClearForm Document Type Service

Admin-configurable document types - changes take effect immediately.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging

from database import database
from clearform.models.document_types import (
    DocumentTypeConfig,
    DocumentCategoryConfig,
    DocumentTemplate,
    DocumentCategory,
    DEFAULT_CATEGORIES,
    DEFAULT_DOCUMENT_TYPES,
)

logger = logging.getLogger(__name__)


class DocumentTypeService:
    """Service for managing document types and templates."""
    
    def __init__(self):
        self.db = None
        self._cache = {}
        self._cache_time = None
        self._cache_ttl = 60  # 1 minute cache
    
    def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    async def initialize_defaults(self) -> Dict[str, int]:
        """Initialize default categories and document types if not present."""
        db = self._get_db()
        
        categories_added = 0
        types_added = 0
        
        # Initialize categories
        for cat in DEFAULT_CATEGORIES:
            existing = await db.clearform_document_categories.find_one({"code": cat.code.value})
            if not existing:
                await db.clearform_document_categories.insert_one(cat.model_dump())
                categories_added += 1
        
        # Initialize document types
        for doc_type in DEFAULT_DOCUMENT_TYPES:
            existing = await db.clearform_document_types.find_one({"code": doc_type.code})
            if not existing:
                await db.clearform_document_types.insert_one(doc_type.model_dump())
                types_added += 1
        
        logger.info(f"Initialized {categories_added} categories, {types_added} document types")
        return {"categories_added": categories_added, "types_added": types_added}
    
    async def get_all_types(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all document types."""
        db = self._get_db()
        
        query = {}
        if active_only:
            query["is_active"] = True
        
        cursor = db.clearform_document_types.find(query, {"_id": 0}).sort("display_order", 1)
        return await cursor.to_list(100)
    
    async def get_type_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get a document type by code."""
        db = self._get_db()
        return await db.clearform_document_types.find_one({"code": code}, {"_id": 0})
    
    async def get_types_by_category(self, category: DocumentCategory, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get document types by category."""
        db = self._get_db()
        
        query = {"category": category.value}
        if active_only:
            query["is_active"] = True
        
        cursor = db.clearform_document_types.find(query, {"_id": 0}).sort("display_order", 1)
        return await cursor.to_list(50)
    
    async def create_type(self, config: DocumentTypeConfig, admin_id: str) -> DocumentTypeConfig:
        """Create a new document type (admin only)."""
        db = self._get_db()
        
        # Check code uniqueness
        existing = await db.clearform_document_types.find_one({"code": config.code})
        if existing:
            raise ValueError(f"Document type with code '{config.code}' already exists")
        
        config.created_by = admin_id
        config.created_at = datetime.now(timezone.utc)
        config.updated_at = datetime.now(timezone.utc)
        
        await db.clearform_document_types.insert_one(config.model_dump())
        
        logger.info(f"Created document type: {config.code} by {admin_id}")
        return config
    
    async def update_type(self, code: str, updates: Dict[str, Any], admin_id: str) -> Optional[Dict[str, Any]]:
        """Update a document type (admin only)."""
        db = self._get_db()
        
        updates["updated_at"] = datetime.now(timezone.utc)
        
        # Don't allow changing code
        updates.pop("code", None)
        updates.pop("type_id", None)
        
        result = await db.clearform_document_types.update_one(
            {"code": code},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated document type: {code} by {admin_id}")
            return await self.get_type_by_code(code)
        
        return None
    
    async def toggle_type_active(self, code: str, is_active: bool, admin_id: str) -> bool:
        """Enable/disable a document type."""
        db = self._get_db()
        
        result = await db.clearform_document_types.update_one(
            {"code": code},
            {
                "$set": {
                    "is_active": is_active,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"{'Enabled' if is_active else 'Disabled'} document type: {code} by {admin_id}")
            return True
        return False
    
    async def delete_type(self, code: str, admin_id: str) -> bool:
        """Delete a document type (soft delete - sets inactive)."""
        return await self.toggle_type_active(code, False, admin_id)
    
    # =========================================================================
    # Category Management
    # =========================================================================
    
    async def get_all_categories(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all document categories."""
        db = self._get_db()
        
        query = {}
        if active_only:
            query["is_active"] = True
        
        cursor = db.clearform_document_categories.find(query, {"_id": 0})
        return await cursor.to_list(20)
    
    async def get_category(self, code: DocumentCategory) -> Optional[Dict[str, Any]]:
        """Get a category by code."""
        db = self._get_db()
        return await db.clearform_document_categories.find_one({"code": code.value}, {"_id": 0})
    
    # =========================================================================
    # Template Management (User-level)
    # =========================================================================
    
    async def create_template(
        self,
        user_id: str,
        name: str,
        document_type_code: str,
        saved_fields: Dict[str, Any],
        saved_intent: Optional[str] = None,
        description: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> DocumentTemplate:
        """Create a user template."""
        db = self._get_db()
        
        template = DocumentTemplate(
            user_id=user_id,
            workspace_id=workspace_id,
            name=name,
            description=description,
            document_type_code=document_type_code,
            saved_fields=saved_fields,
            saved_intent=saved_intent,
        )
        
        await db.clearform_templates.insert_one(template.model_dump())
        
        logger.info(f"Created template: {template.template_id} for user {user_id}")
        return template
    
    async def get_user_templates(
        self,
        user_id: str,
        workspace_id: Optional[str] = None,
        document_type_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get user's templates."""
        db = self._get_db()
        
        query = {"user_id": user_id}
        if workspace_id:
            query["workspace_id"] = workspace_id
        if document_type_code:
            query["document_type_code"] = document_type_code
        
        cursor = db.clearform_templates.find(query, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(100)
    
    async def get_template(self, user_id: str, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific template."""
        db = self._get_db()
        return await db.clearform_templates.find_one(
            {"template_id": template_id, "user_id": user_id},
            {"_id": 0}
        )
    
    async def update_template(
        self,
        user_id: str,
        template_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update a template."""
        db = self._get_db()
        
        updates["updated_at"] = datetime.now(timezone.utc)
        updates.pop("template_id", None)
        updates.pop("user_id", None)
        
        result = await db.clearform_templates.update_one(
            {"template_id": template_id, "user_id": user_id},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            return await self.get_template(user_id, template_id)
        return None
    
    async def delete_template(self, user_id: str, template_id: str) -> bool:
        """Delete a template."""
        db = self._get_db()
        
        result = await db.clearform_templates.delete_one(
            {"template_id": template_id, "user_id": user_id}
        )
        return result.deleted_count > 0
    
    async def use_template(self, user_id: str, template_id: str) -> Optional[Dict[str, Any]]:
        """Mark template as used and return it."""
        db = self._get_db()
        
        result = await db.clearform_templates.update_one(
            {"template_id": template_id, "user_id": user_id},
            {
                "$set": {"last_used_at": datetime.now(timezone.utc)},
                "$inc": {"use_count": 1}
            }
        )
        
        if result.modified_count > 0:
            return await self.get_template(user_id, template_id)
        return None
    
    async def toggle_favorite(self, user_id: str, template_id: str) -> Optional[Dict[str, Any]]:
        """Toggle template favorite status."""
        db = self._get_db()
        
        template = await self.get_template(user_id, template_id)
        if not template:
            return None
        
        new_status = not template.get("is_favorite", False)
        
        await db.clearform_templates.update_one(
            {"template_id": template_id, "user_id": user_id},
            {"$set": {"is_favorite": new_status, "updated_at": datetime.now(timezone.utc)}}
        )
        
        template["is_favorite"] = new_status
        return template


# Global instance
document_type_service = DocumentTypeService()
