"""ClearForm Workspace & Profile Routes"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging

from clearform.routes.auth import get_current_clearform_user
from clearform.services.workspace_service import workspace_service

logger = logging.getLogger(__name__)

workspaces_router = APIRouter(prefix="/api/clearform/workspaces", tags=["ClearForm Workspaces"])
profiles_router = APIRouter(prefix="/api/clearform/profiles", tags=["ClearForm Profiles"])


# ============================================================================
# Workspace Routes
# ============================================================================

class CreateWorkspaceRequest(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#10b981"
    icon: str = "folder"


class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_default: Optional[bool] = None


@workspaces_router.get("")
async def get_workspaces(
    include_archived: bool = False,
    user = Depends(get_current_clearform_user),
):
    """Get user's workspaces."""
    try:
        workspaces = await workspace_service.get_user_workspaces(user.user_id, include_archived)
        
        # Ensure at least one workspace exists
        if not workspaces:
            default = await workspace_service.ensure_default_workspace(user.user_id)
            workspaces = [default.model_dump()]
        
        return {"workspaces": workspaces, "total": len(workspaces)}
    except Exception as e:
        logger.error(f"Failed to get workspaces: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workspaces")


@workspaces_router.post("")
async def create_workspace(
    request: CreateWorkspaceRequest,
    user = Depends(get_current_clearform_user),
):
    """Create a new workspace."""
    try:
        workspace = await workspace_service.create_workspace(
            user_id=user.user_id,
            name=request.name,
            description=request.description,
            color=request.color,
            icon=request.icon,
        )
        return {"message": "Workspace created", "workspace": workspace.model_dump()}
    except Exception as e:
        logger.error(f"Failed to create workspace: {e}")
        raise HTTPException(status_code=500, detail="Failed to create workspace")


@workspaces_router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    user = Depends(get_current_clearform_user),
):
    """Get a specific workspace."""
    try:
        workspace = await workspace_service.get_workspace(user.user_id, workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return workspace
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workspace: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workspace")


@workspaces_router.put("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    request: UpdateWorkspaceRequest,
    user = Depends(get_current_clearform_user),
):
    """Update a workspace."""
    try:
        updates = request.model_dump(exclude_none=True)
        result = await workspace_service.update_workspace(user.user_id, workspace_id, updates)
        if not result:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"message": "Workspace updated", "workspace": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workspace: {e}")
        raise HTTPException(status_code=500, detail="Failed to update workspace")


@workspaces_router.delete("/{workspace_id}")
async def archive_workspace(
    workspace_id: str,
    user = Depends(get_current_clearform_user),
):
    """Archive a workspace."""
    try:
        success = await workspace_service.archive_workspace(user.user_id, workspace_id)
        if not success:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"message": "Workspace archived"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to archive workspace: {e}")
        raise HTTPException(status_code=500, detail="Failed to archive workspace")


# ============================================================================
# Smart Profile Routes
# ============================================================================

class CreateProfileRequest(BaseModel):
    name: str
    profile_type: str = "personal"
    workspace_id: Optional[str] = None
    is_default: bool = False
    
    # Personal details
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    postcode: Optional[str] = None
    
    # Professional
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    
    # Custom
    custom_fields: Dict[str, Any] = {}


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    is_default: Optional[bool] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    postcode: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None


@profiles_router.get("")
async def get_profiles(
    profile_type: Optional[str] = None,
    workspace_id: Optional[str] = None,
    user = Depends(get_current_clearform_user),
):
    """Get user's smart profiles."""
    try:
        profiles = await workspace_service.get_user_profiles(
            user_id=user.user_id,
            profile_type=profile_type,
            workspace_id=workspace_id,
        )
        return {"profiles": profiles, "total": len(profiles)}
    except Exception as e:
        logger.error(f"Failed to get profiles: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profiles")


@profiles_router.post("")
async def create_profile(
    request: CreateProfileRequest,
    user = Depends(get_current_clearform_user),
):
    """Create a smart profile."""
    try:
        profile_data = request.model_dump(exclude={"name", "profile_type", "workspace_id", "is_default"})
        
        profile = await workspace_service.create_profile(
            user_id=user.user_id,
            name=request.name,
            profile_type=request.profile_type,
            workspace_id=request.workspace_id,
            is_default=request.is_default,
            **profile_data,
        )
        return {"message": "Profile created", "profile": profile.model_dump()}
    except Exception as e:
        logger.error(f"Failed to create profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to create profile")


@profiles_router.get("/default")
async def get_default_profile(
    profile_type: str = "personal",
    user = Depends(get_current_clearform_user),
):
    """Get default profile of a type."""
    try:
        profile = await workspace_service.get_default_profile(user.user_id, profile_type)
        if not profile:
            return {"profile": None, "message": "No default profile set"}
        return profile
    except Exception as e:
        logger.error(f"Failed to get default profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to get default profile")


@profiles_router.get("/{profile_id}")
async def get_profile(
    profile_id: str,
    user = Depends(get_current_clearform_user),
):
    """Get a specific profile."""
    try:
        profile = await workspace_service.get_profile(user.user_id, profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")


@profiles_router.put("/{profile_id}")
async def update_profile(
    profile_id: str,
    request: UpdateProfileRequest,
    user = Depends(get_current_clearform_user),
):
    """Update a profile."""
    try:
        updates = request.model_dump(exclude_none=True)
        result = await workspace_service.update_profile(user.user_id, profile_id, updates)
        if not result:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"message": "Profile updated", "profile": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to update profile")


@profiles_router.delete("/{profile_id}")
async def delete_profile(
    profile_id: str,
    user = Depends(get_current_clearform_user),
):
    """Delete a profile."""
    try:
        success = await workspace_service.delete_profile(user.user_id, profile_id)
        if not success:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"message": "Profile deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete profile")


@profiles_router.post("/{profile_id}/use")
async def use_profile(
    profile_id: str,
    user = Depends(get_current_clearform_user),
):
    """Mark profile as used (for auto-fill tracking)."""
    try:
        profile = await workspace_service.use_profile(user.user_id, profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"message": "Profile used", "profile": profile}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to use profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to use profile")
