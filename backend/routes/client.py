from fastapi import APIRouter, HTTPException, Request, Depends, status
from database import database
from middleware import client_route_guard
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/client", tags=["client"], dependencies=[Depends(client_route_guard)])

@router.get("/dashboard")
async def get_dashboard(request: Request):
    """Get client dashboard data."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0})
        
        # Get properties
        properties = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        # Get requirements summary
        requirements = await db.requirements.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        
        # Calculate compliance summary
        total_requirements = len(requirements)
        compliant = sum(1 for r in requirements if r["status"] == "COMPLIANT")
        overdue = sum(1 for r in requirements if r["status"] == "OVERDUE")
        expiring = sum(1 for r in requirements if r["status"] == "EXPIRING_SOON")
        
        return {
            "client": client,
            "properties": properties,
            "compliance_summary": {
                "total_requirements": total_requirements,
                "compliant": compliant,
                "overdue": overdue,
                "expiring_soon": expiring
            }
        }
    
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load dashboard"
        )

@router.get("/properties")
async def get_properties(request: Request):
    """Get client properties."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        properties = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        return {"properties": properties}
    
    except Exception as e:
        logger.error(f"Properties error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load properties"
        )

@router.get("/properties/{property_id}/requirements")
async def get_property_requirements(request: Request, property_id: str):
    """Get requirements for a property."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify property belongs to client
        prop = await db.properties.find_one(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        requirements = await db.requirements.find(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        return {"requirements": requirements}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Requirements error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requirements"
        )

@router.get("/documents")
async def get_documents(request: Request):
    """Get client documents."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        documents = await db.documents.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        
        return {"documents": documents}
    
    except Exception as e:
        logger.error(f"Documents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load documents"
        )
