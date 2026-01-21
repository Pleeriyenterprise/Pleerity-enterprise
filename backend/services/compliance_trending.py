"""Compliance Score Trending Service - Track compliance score changes over time.

Captures daily snapshots of compliance scores for trend analysis.
Provides "what changed" explanations for score movements.
"""
from database import database
from services.compliance_score import calculate_compliance_score
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


async def capture_daily_snapshot(client_id: str) -> Dict[str, Any]:
    """Capture a daily compliance score snapshot for a client.
    
    Should be called by scheduler once per day per client.
    Stores the snapshot in compliance_score_history collection.
    
    Returns:
        dict with snapshot_id and captured score
    """
    db = database.get_db()
    
    try:
        # Calculate current compliance score
        score_data = await calculate_compliance_score(client_id)
        
        now = datetime.now(timezone.utc)
        date_key = now.strftime("%Y-%m-%d")
        
        # Check if snapshot already exists for today
        existing = await db.compliance_score_history.find_one({
            "client_id": client_id,
            "date_key": date_key
        })
        
        if existing:
            # Update existing snapshot (allows re-run if needed)
            await db.compliance_score_history.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "score": score_data.get("score", 0),
                    "grade": score_data.get("grade", "?"),
                    "color": score_data.get("color", "gray"),
                    "breakdown": score_data.get("breakdown", {}),
                    "stats": score_data.get("stats", {}),
                    "updated_at": now.isoformat()
                }}
            )
            return {
                "snapshot_id": existing.get("snapshot_id"),
                "action": "updated",
                "score": score_data.get("score", 0)
            }
        
        # Create new snapshot
        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        
        snapshot = {
            "snapshot_id": snapshot_id,
            "client_id": client_id,
            "date_key": date_key,
            "timestamp": now.isoformat(),
            "score": score_data.get("score", 0),
            "grade": score_data.get("grade", "?"),
            "color": score_data.get("color", "gray"),
            "breakdown": score_data.get("breakdown", {}),
            "stats": score_data.get("stats", {}),
            "created_at": now.isoformat()
        }
        
        await db.compliance_score_history.insert_one(snapshot)
        
        logger.info(f"Captured compliance snapshot for client {client_id}: score={score_data.get('score')}")
        
        return {
            "snapshot_id": snapshot_id,
            "action": "created",
            "score": score_data.get("score", 0)
        }
    
    except Exception as e:
        logger.error(f"Failed to capture compliance snapshot for {client_id}: {e}")
        raise


async def get_score_trend(
    client_id: str,
    days: int = 30,
    include_breakdown: bool = False
) -> Dict[str, Any]:
    """Get compliance score trend data for a client.
    
    Args:
        client_id: The client to get trend for
        days: Number of days of history (default 30)
        include_breakdown: Include detailed breakdown per day
        
    Returns:
        dict with trend data, sparkline points, and change analysis
    """
    db = database.get_db()
    
    try:
        # Calculate date range
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Fetch snapshots
        projection = {
            "_id": 0,
            "date_key": 1,
            "score": 1,
            "grade": 1,
            "color": 1,
            "stats": 1
        }
        
        if include_breakdown:
            projection["breakdown"] = 1
        
        snapshots = await db.compliance_score_history.find(
            {
                "client_id": client_id,
                "date_key": {"$gte": start_date}
            },
            projection
        ).sort("date_key", 1).to_list(days + 1)
        
        if not snapshots:
            return {
                "has_history": False,
                "message": "No score history available yet",
                "sparkline": [],
                "data_points": [],
                "trend_direction": "neutral",
                "change_7d": None,
                "change_30d": None
            }
        
        # Generate sparkline data (just scores for chart)
        sparkline = [s.get("score", 0) for s in snapshots]
        
        # Generate data points with dates
        data_points = [
            {
                "date": s["date_key"],
                "score": s.get("score", 0),
                "grade": s.get("grade", "?"),
                "color": s.get("color", "gray"),
                "stats": s.get("stats", {}) if include_breakdown else None
            }
            for s in snapshots
        ]
        
        # Calculate changes
        latest_score = snapshots[-1].get("score", 0) if snapshots else 0
        
        # 7-day change
        change_7d = None
        if len(snapshots) >= 7:
            score_7d_ago = snapshots[-7].get("score", 0)
            change_7d = latest_score - score_7d_ago
        elif len(snapshots) > 1:
            score_first = snapshots[0].get("score", 0)
            change_7d = latest_score - score_first
        
        # 30-day change
        change_30d = None
        if len(snapshots) >= 30:
            score_30d_ago = snapshots[-30].get("score", 0)
            change_30d = latest_score - score_30d_ago
        elif len(snapshots) > 1:
            score_first = snapshots[0].get("score", 0)
            change_30d = latest_score - score_first
        
        # Determine trend direction
        if change_7d is not None:
            if change_7d > 2:
                trend_direction = "up"
            elif change_7d < -2:
                trend_direction = "down"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "neutral"
        
        # Get min/max for chart scaling
        all_scores = [s.get("score", 0) for s in snapshots]
        
        return {
            "has_history": True,
            "days_of_data": len(snapshots),
            "latest_score": latest_score,
            "sparkline": sparkline,
            "data_points": data_points,
            "trend_direction": trend_direction,
            "change_7d": change_7d,
            "change_30d": change_30d,
            "min_score": min(all_scores) if all_scores else 0,
            "max_score": max(all_scores) if all_scores else 100,
            "avg_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
        }
    
    except Exception as e:
        logger.error(f"Failed to get score trend for {client_id}: {e}")
        return {
            "has_history": False,
            "error": str(e),
            "sparkline": [],
            "data_points": [],
            "trend_direction": "neutral"
        }


async def get_score_change_explanation(
    client_id: str,
    compare_days: int = 7
) -> Dict[str, Any]:
    """Generate a plain-English explanation of what changed in the score.
    
    Compares current state to N days ago and explains the difference.
    
    Args:
        client_id: The client to analyze
        compare_days: Days back to compare (default 7)
        
    Returns:
        dict with explanation text and change details
    """
    db = database.get_db()
    
    try:
        now = datetime.now(timezone.utc)
        today_key = now.strftime("%Y-%m-%d")
        compare_date = (now - timedelta(days=compare_days)).strftime("%Y-%m-%d")
        
        # Get today's snapshot (or most recent)
        today_snapshot = await db.compliance_score_history.find_one(
            {"client_id": client_id},
            {"_id": 0},
            sort=[("date_key", -1)]
        )
        
        # Get comparison snapshot
        compare_snapshot = await db.compliance_score_history.find_one(
            {
                "client_id": client_id,
                "date_key": {"$lte": compare_date}
            },
            {"_id": 0},
            sort=[("date_key", -1)]
        )
        
        if not today_snapshot:
            return {
                "has_comparison": False,
                "explanation": "No score history available yet. Check back tomorrow for trend data.",
                "changes": []
            }
        
        if not compare_snapshot:
            return {
                "has_comparison": False,
                "explanation": f"Not enough history for {compare_days}-day comparison. Score tracking started recently.",
                "current_score": today_snapshot.get("score", 0),
                "changes": []
            }
        
        # Calculate changes
        current_score = today_snapshot.get("score", 0)
        previous_score = compare_snapshot.get("score", 0)
        score_change = current_score - previous_score
        
        current_stats = today_snapshot.get("stats", {})
        previous_stats = compare_snapshot.get("stats", {})
        
        changes = []
        explanations = []
        
        # Analyze what changed
        compliant_change = current_stats.get("compliant", 0) - previous_stats.get("compliant", 0)
        overdue_change = current_stats.get("overdue", 0) - previous_stats.get("overdue", 0)
        expiring_change = current_stats.get("expiring_soon", 0) - previous_stats.get("expiring_soon", 0)
        
        if compliant_change > 0:
            changes.append({
                "type": "positive",
                "category": "compliant",
                "change": f"+{compliant_change}",
                "text": f"{compliant_change} requirement(s) became compliant"
            })
            explanations.append(f"{compliant_change} requirement(s) became compliant")
        elif compliant_change < 0:
            changes.append({
                "type": "negative",
                "category": "compliant",
                "change": str(compliant_change),
                "text": f"{abs(compliant_change)} requirement(s) lost compliance"
            })
            explanations.append(f"{abs(compliant_change)} requirement(s) lost compliance")
        
        if overdue_change > 0:
            changes.append({
                "type": "negative",
                "category": "overdue",
                "change": f"+{overdue_change}",
                "text": f"{overdue_change} new overdue item(s)"
            })
            explanations.append(f"{overdue_change} new overdue item(s)")
        elif overdue_change < 0:
            changes.append({
                "type": "positive",
                "category": "overdue",
                "change": str(overdue_change),
                "text": f"{abs(overdue_change)} overdue item(s) resolved"
            })
            explanations.append(f"{abs(overdue_change)} overdue item(s) resolved")
        
        if expiring_change > 0:
            changes.append({
                "type": "warning",
                "category": "expiring",
                "change": f"+{expiring_change}",
                "text": f"{expiring_change} item(s) now expiring soon"
            })
            explanations.append(f"{expiring_change} item(s) now expiring soon")
        elif expiring_change < 0:
            changes.append({
                "type": "positive",
                "category": "expiring",
                "change": str(expiring_change),
                "text": f"{abs(expiring_change)} item(s) no longer expiring soon"
            })
            explanations.append(f"{abs(expiring_change)} item(s) no longer expiring soon")
        
        # Generate explanation text
        if score_change > 0:
            direction = "improved"
            emoji = "📈"
        elif score_change < 0:
            direction = "decreased"
            emoji = "📉"
        else:
            direction = "remained stable"
            emoji = "➡️"
        
        if explanations:
            explanation_text = f"{emoji} Your score {direction} by {abs(score_change)} points in the last {compare_days} days. "
            explanation_text += "Key changes: " + "; ".join(explanations) + "."
        else:
            explanation_text = f"{emoji} Your score {direction} by {abs(score_change)} points in the last {compare_days} days."
        
        return {
            "has_comparison": True,
            "current_score": current_score,
            "previous_score": previous_score,
            "score_change": score_change,
            "compare_days": compare_days,
            "explanation": explanation_text,
            "changes": changes,
            "current_date": today_snapshot.get("date_key"),
            "compare_date": compare_snapshot.get("date_key")
        }
    
    except Exception as e:
        logger.error(f"Failed to generate score explanation for {client_id}: {e}")
        return {
            "has_comparison": False,
            "explanation": "Unable to analyze score changes at this time.",
            "error": str(e),
            "changes": []
        }


async def capture_all_client_snapshots() -> Dict[str, Any]:
    """Capture daily snapshots for all active clients.
    
    Called by the scheduler job daily.
    
    Returns:
        dict with success/failure counts
    """
    db = database.get_db()
    
    try:
        # Get all active clients
        clients = await db.clients.find(
            {"subscription_status": "ACTIVE"},
            {"_id": 0, "client_id": 1}
        ).to_list(1000)
        
        success_count = 0
        error_count = 0
        errors = []
        
        for client in clients:
            try:
                await capture_daily_snapshot(client["client_id"])
                success_count += 1
            except Exception as e:
                error_count += 1
                errors.append({
                    "client_id": client["client_id"],
                    "error": str(e)
                })
        
        logger.info(f"Compliance snapshot job completed: {success_count} success, {error_count} errors")
        
        return {
            "total_clients": len(clients),
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors[:10]  # Limit error details
        }
    
    except Exception as e:
        logger.error(f"Compliance snapshot job failed: {e}")
        return {
            "total_clients": 0,
            "success_count": 0,
            "error_count": 1,
            "errors": [{"error": str(e)}]
        }
