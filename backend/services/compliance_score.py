"""Compliance Score Service - Calculate overall compliance health score
Provides a 0-100 score based on requirement statuses, expiry timelines, and documents.
"""
from database import database
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def calculate_compliance_score(client_id: str) -> Dict[str, Any]:
    """Calculate the overall compliance score for a client.
    
    Score is calculated based on:
    - Requirement status distribution (40% weight)
    - Days until next expiry (30% weight)  
    - Document upload rate (15% weight)
    - Overdue items penalty (15% weight)
    
    Returns:
        dict with score (0-100), grade (A-F), breakdown, and recommendations
    """
    db = database.get_db()
    
    try:
        # Get all properties for this client
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(100)
        
        if not properties:
            return {
                "score": 100,
                "grade": "A",
                "color": "green",
                "message": "No properties to evaluate",
                "breakdown": {},
                "recommendations": []
            }
        
        property_ids = [p["property_id"] for p in properties]
        
        # Get all requirements
        requirements = await db.requirements.find(
            {"property_id": {"$in": property_ids}},
            {"_id": 0}
        ).to_list(500)
        
        if not requirements:
            return {
                "score": 100,
                "grade": "A",
                "color": "green",
                "message": "No requirements to evaluate",
                "breakdown": {},
                "recommendations": []
            }
        
        # Get all documents
        documents = await db.documents.find(
            {"property_id": {"$in": property_ids}},
            {"_id": 0}
        ).to_list(500)
        
        now = datetime.now(timezone.utc)
        
        # ============================================
        # 1. REQUIREMENT STATUS SCORE (40% weight)
        # ============================================
        status_counts = {"COMPLIANT": 0, "PENDING": 0, "EXPIRING_SOON": 0, "OVERDUE": 0, "EXPIRED": 0}
        
        for req in requirements:
            status = req.get("status", "PENDING")
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts["PENDING"] += 1
        
        total_reqs = len(requirements)
        compliant_count = status_counts["COMPLIANT"]
        pending_count = status_counts["PENDING"]
        expiring_soon_count = status_counts["EXPIRING_SOON"]
        overdue_count = status_counts["OVERDUE"] + status_counts["EXPIRED"]
        
        # Calculate status score (0-100)
        # Compliant = 100 points, Pending = 70 points, Expiring Soon = 40 points, Overdue = 0 points
        status_points = (
            (compliant_count * 100) +
            (pending_count * 70) +
            (expiring_soon_count * 40) +
            (overdue_count * 0)
        )
        status_score = (status_points / (total_reqs * 100)) * 100 if total_reqs > 0 else 100
        
        # ============================================
        # 2. EXPIRY TIMELINE SCORE (30% weight)
        # ============================================
        # Based on days until next expiry
        min_days_until_expiry = float('inf')
        
        for req in requirements:
            if req.get("status") in ["COMPLIANT", "PENDING", "EXPIRING_SOON"]:
                due_date_str = req.get("due_date")
                if due_date_str:
                    try:
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')) if isinstance(due_date_str, str) else due_date_str
                        days_until = (due_date - now).days
                        if days_until < min_days_until_expiry:
                            min_days_until_expiry = days_until
                    except:
                        pass
        
        # Score based on nearest expiry
        # 90+ days = 100, 60+ days = 90, 30+ days = 70, 14+ days = 50, 7+ days = 30, <7 days = 10
        if min_days_until_expiry == float('inf'):
            expiry_score = 100
        elif min_days_until_expiry >= 90:
            expiry_score = 100
        elif min_days_until_expiry >= 60:
            expiry_score = 90
        elif min_days_until_expiry >= 30:
            expiry_score = 70
        elif min_days_until_expiry >= 14:
            expiry_score = 50
        elif min_days_until_expiry >= 7:
            expiry_score = 30
        elif min_days_until_expiry >= 0:
            expiry_score = 10
        else:
            expiry_score = 0  # Already expired
        
        # ============================================
        # 3. DOCUMENT UPLOAD RATE (15% weight)
        # ============================================
        # Percentage of requirements that have associated documents
        requirements_with_docs = set()
        for doc in documents:
            if doc.get("requirement_id"):
                requirements_with_docs.add(doc["requirement_id"])
        
        doc_rate = (len(requirements_with_docs) / total_reqs * 100) if total_reqs > 0 else 0
        doc_score = min(doc_rate, 100)  # Cap at 100
        
        # ============================================
        # 4. OVERDUE PENALTY (15% weight)
        # ============================================
        # Heavy penalty for overdue items
        overdue_penalty_score = 100 - (overdue_count / total_reqs * 100) if total_reqs > 0 else 100
        overdue_penalty_score = max(0, overdue_penalty_score)  # Ensure non-negative
        
        # ============================================
        # CALCULATE FINAL SCORE
        # ============================================
        final_score = (
            (status_score * 0.40) +
            (expiry_score * 0.30) +
            (doc_score * 0.15) +
            (overdue_penalty_score * 0.15)
        )
        
        final_score = round(max(0, min(100, final_score)))  # Clamp to 0-100
        
        # Determine grade
        if final_score >= 90:
            grade = "A"
            color = "green"
            message = "Excellent compliance health"
        elif final_score >= 80:
            grade = "B"
            color = "green"
            message = "Good compliance status"
        elif final_score >= 70:
            grade = "C"
            color = "amber"
            message = "Moderate - some attention needed"
        elif final_score >= 60:
            grade = "D"
            color = "amber"
            message = "Below average - action required"
        else:
            grade = "F"
            color = "red"
            message = "Critical - immediate action needed"
        
        # Generate recommendations
        recommendations = []
        
        if overdue_count > 0:
            recommendations.append({
                "priority": "high",
                "action": f"Address {overdue_count} overdue requirement(s) immediately",
                "impact": "+15-25 points"
            })
        
        if expiring_soon_count > 0:
            recommendations.append({
                "priority": "medium",
                "action": f"Renew {expiring_soon_count} certificate(s) expiring soon",
                "impact": "+10-15 points"
            })
        
        if doc_rate < 50:
            recommendations.append({
                "priority": "low",
                "action": "Upload more supporting documents for your requirements",
                "impact": "+5-10 points"
            })
        
        if min_days_until_expiry < 30 and min_days_until_expiry > 0:
            recommendations.append({
                "priority": "medium",
                "action": f"Next expiry in {int(min_days_until_expiry)} days - schedule renewal",
                "impact": "+10 points"
            })
        
        return {
            "score": final_score,
            "grade": grade,
            "color": color,
            "message": message,
            "breakdown": {
                "status_score": round(status_score, 1),
                "expiry_score": round(expiry_score, 1),
                "document_score": round(doc_score, 1),
                "overdue_penalty_score": round(overdue_penalty_score, 1)
            },
            "stats": {
                "total_requirements": total_reqs,
                "compliant": compliant_count,
                "pending": pending_count,
                "expiring_soon": expiring_soon_count,
                "overdue": overdue_count,
                "documents_uploaded": len(documents),
                "document_coverage_percent": round(doc_rate, 1),
                "days_until_next_expiry": int(min_days_until_expiry) if min_days_until_expiry != float('inf') else None
            },
            "recommendations": recommendations[:3],  # Top 3 recommendations
            "properties_count": len(properties)
        }
    
    except Exception as e:
        logger.error(f"Error calculating compliance score: {e}")
        return {
            "score": 0,
            "grade": "?",
            "color": "gray",
            "message": "Unable to calculate score",
            "breakdown": {},
            "recommendations": [],
            "error": str(e)
        }
