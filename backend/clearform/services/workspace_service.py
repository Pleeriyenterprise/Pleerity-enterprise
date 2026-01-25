"""ClearForm Workspace & Profile Service

Manages workspaces, smart profiles, and workspace membership.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging

from database import database
from clearform.models.workspaces import Workspace, SmartProfile, WorkspaceMember, WorkspaceRole

logger = logging.getLogger(__name__)


class WorkspaceService:
    """Service for workspace and profile management."""
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    # =========================================================================
    # Workspace Management
    # =========================================================================
    
    async def create_workspace(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        color: str = "#10b981",
        icon: str = "folder",
        is_default: bool = False,
    ) -> Workspace:
        """Create a new workspace."""
        db = self._get_db()
        
        # If this is the default, unset any existing default
        if is_default:
            await db.clearform_workspaces.update_many(
                {"owner_id": user_id, "is_default": True},
                {"$set": {"is_default": False}}
            )
        
        workspace = Workspace(
            owner_id=user_id,
            name=name,
            description=description,
            color=color,
            icon=icon,
            is_default=is_default,
        )
        
        await db.clearform_workspaces.insert_one(workspace.model_dump())
        
        logger.info(f"Created workspace: {workspace.workspace_id} for user {user_id}")
        return workspace
    
    async def get_user_workspaces(self, user_id: str, include_archived: bool = False) -> List[Dict[str, Any]]:
        """Get all workspaces for a user."""
        db = self._get_db()
        
        query = {"owner_id": user_id}
        if not include_archived:
            query["is_archived"] = False
        
        cursor = db.clearform_workspaces.find(query, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(50)
    
    async def get_workspace(self, user_id: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific workspace."""
        db = self._get_db()
        return await db.clearform_workspaces.find_one(
            {"workspace_id": workspace_id, "owner_id": user_id},
            {"_id": 0}
        )
    
    async def update_workspace(
        self,
        user_id: str,
        workspace_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update workspace."""
        db = self._get_db()
        
        updates["updated_at"] = datetime.now(timezone.utc)
        updates.pop("workspace_id", None)
        updates.pop("owner_id", None)
        
        # Handle default workspace logic
        if updates.get("is_default"):
            await db.clearform_workspaces.update_many(
                {"owner_id": user_id, "is_default": True},
                {"$set": {"is_default": False}}
            )
        
        result = await db.clearform_workspaces.update_one(
            {"workspace_id": workspace_id, "owner_id": user_id},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            return await self.get_workspace(user_id, workspace_id)
        return None
    
    async def archive_workspace(self, user_id: str, workspace_id: str) -> bool:
        """Archive a workspace."""
        db = self._get_db()
        
        result = await db.clearform_workspaces.update_one(
            {"workspace_id": workspace_id, "owner_id": user_id},
            {
                "$set": {
                    "is_archived": True,
                    "is_default": False,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        return result.modified_count > 0
    
    async def update_workspace_stats(self, workspace_id: str) -> None:
        """Update workspace document/template counts."""
        db = self._get_db()
        
        doc_count = await db.clearform_documents.count_documents({"workspace_id": workspace_id})
        tpl_count = await db.clearform_templates.count_documents({"workspace_id": workspace_id})
        
        await db.clearform_workspaces.update_one(
            {"workspace_id": workspace_id},
            {
                "$set": {
                    "document_count": doc_count,
                    "template_count": tpl_count,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
    
    async def ensure_default_workspace(self, user_id: str) -> Workspace:
        """Ensure user has a default workspace, create if not."""
        db = self._get_db()
        
        existing = await db.clearform_workspaces.find_one(
            {"owner_id": user_id, "is_default": True},
            {"_id": 0}
        )
        
        if existing:
            return Workspace(**existing)
        
        # Create default workspace
        return await self.create_workspace(
            user_id=user_id,
            name="My Documents",
            description="Default workspace",
            is_default=True,
        )
    
    # =========================================================================
    # Smart Profile Management
    # =========================================================================
    
    async def create_profile(
        self,
        user_id: str,
        name: str,
        profile_type: str = "personal",
        workspace_id: Optional[str] = None,
        is_default: bool = False,
        **profile_data,
    ) -> SmartProfile:
        """Create a smart profile."""
        db = self._get_db()
        
        # If this is the default of its type, unset existing
        if is_default:
            await db.clearform_profiles.update_many(
                {"user_id": user_id, "profile_type": profile_type, "is_default": True},
                {"$set": {"is_default": False}}
            )
        
        profile = SmartProfile(
            user_id=user_id,
            workspace_id=workspace_id,
            profile_type=profile_type,
            name=name,
            is_default=is_default,
            **profile_data,
        )
        
        await db.clearform_profiles.insert_one(profile.model_dump())
        
        logger.info(f"Created profile: {profile.profile_id} for user {user_id}")
        return profile
    
    async def get_user_profiles(
        self,
        user_id: str,
        profile_type: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get user's profiles."""
        db = self._get_db()
        
        query = {"user_id": user_id}
        if profile_type:
            query["profile_type"] = profile_type
        if workspace_id:
            query["$or"] = [
                {"workspace_id": workspace_id},
                {"workspace_id": None},  # Global profiles
            ]
        
        cursor = db.clearform_profiles.find(query, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(50)
    
    async def get_profile(self, user_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific profile."""
        db = self._get_db()
        return await db.clearform_profiles.find_one(
            {"profile_id": profile_id, "user_id": user_id},
            {"_id": 0}
        )
    
    async def get_default_profile(self, user_id: str, profile_type: str = "personal") -> Optional[Dict[str, Any]]:
        """Get user's default profile of a type."""
        db = self._get_db()
        return await db.clearform_profiles.find_one(
            {"user_id": user_id, "profile_type": profile_type, "is_default": True},
            {"_id": 0}
        )
    
    async def update_profile(
        self,
        user_id: str,
        profile_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update profile."""
        db = self._get_db()
        
        updates["updated_at"] = datetime.now(timezone.utc)
        updates.pop("profile_id", None)
        updates.pop("user_id", None)
        
        # Handle default logic
        if updates.get("is_default"):
            profile = await self.get_profile(user_id, profile_id)
            if profile:
                await db.clearform_profiles.update_many(
                    {"user_id": user_id, "profile_type": profile["profile_type"], "is_default": True},
                    {"$set": {"is_default": False}}
                )
        
        result = await db.clearform_profiles.update_one(
            {"profile_id": profile_id, "user_id": user_id},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            return await self.get_profile(user_id, profile_id)
        return None
    
    async def delete_profile(self, user_id: str, profile_id: str) -> bool:
        """Delete a profile."""
        db = self._get_db()
        
        result = await db.clearform_profiles.delete_one(
            {"profile_id": profile_id, "user_id": user_id}
        )
        return result.deleted_count > 0
    
    async def use_profile(self, user_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
        """Mark profile as used."""
        db = self._get_db()
        
        result = await db.clearform_profiles.update_one(
            {"profile_id": profile_id, "user_id": user_id},
            {
                "$set": {"last_used_at": datetime.now(timezone.utc)},
                "$inc": {"use_count": 1}
            }
        )
        
        if result.modified_count > 0:
            return await self.get_profile(user_id, profile_id)
        return None


# Global instance
workspace_service = WorkspaceService()
