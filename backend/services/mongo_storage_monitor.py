"""
MongoDB cluster storage capacity monitoring for Atlas Flex / shared-quota incidents.

Uses dbStats across configured databases on the connected cluster.
Does not call Atlas Admin API (no extra secrets). Thresholds are percentage of
MONGO_STORAGE_LIMIT_BYTES (default 5 GiB Flex logical data+index style budget).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_LIMIT_BYTES = 5 * 1024 * 1024 * 1024  # Atlas Flex 5 GB
THRESHOLDS = (
    (95, "emergency"),
    (90, "platform_alert"),
    (85, "critical"),
    (75, "attention"),
    (60, "warning"),
)

INCIDENT_SOURCE = "mongo_storage_capacity"
INCIDENT_FINGERPRINT = "atlas_flex_storage_pressure"


def _limit_bytes() -> int:
    raw = (os.getenv("MONGO_STORAGE_LIMIT_BYTES") or "").strip()
    if raw.isdigit():
        return max(int(raw), 1)
    return DEFAULT_LIMIT_BYTES


def _db_names_to_scan(primary_db_name: Optional[str]) -> List[str]:
    raw = (os.getenv("MONGO_STORAGE_SCAN_DBS") or "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    names = []
    if primary_db_name:
        names.append(primary_db_name)
    # Shared Flex: always include sibling env DB when present on same cluster
    for sibling in ("pleerity_staging", "pleerity_production"):
        if sibling not in names:
            names.append(sibling)
    return names


def classify_usage_pct(pct: float) -> str:
    for threshold, level in THRESHOLDS:
        if pct >= threshold:
            return level
    return "ok"


async def collect_mongo_storage_snapshot() -> Dict[str, Any]:
    from database import database

    db = database.get_db()
    client = getattr(database, "client", None)
    primary = getattr(db, "name", None) if db is not None else None
    limit = _limit_bytes()
    now = datetime.now(timezone.utc).isoformat()

    if client is None or db is None:
        return {
            "available": False,
            "reason": "database_unavailable",
            "captured_at": now,
            "limit_bytes": limit,
        }

    per_db: List[Dict[str, Any]] = []
    total_data = 0
    total_index = 0
    for name in _db_names_to_scan(primary):
        try:
            stats = await client[name].command("dbStats")
        except Exception as exc:
            per_db.append({"database": name, "error": str(exc)[:160]})
            continue
        data_b = int(stats.get("dataSize") or 0)
        index_b = int(stats.get("indexSize") or 0)
        total_data += data_b
        total_index += index_b
        per_db.append(
            {
                "database": name,
                "data_size_bytes": data_b,
                "index_size_bytes": index_b,
                "storage_size_bytes": int(stats.get("storageSize") or 0),
                "collections": int(stats.get("collections") or 0),
                "objects": int(stats.get("objects") or 0),
            }
        )

    used = total_data + total_index
    pct = (used / limit) * 100.0 if limit else 0.0
    level = classify_usage_pct(pct)
    return {
        "available": True,
        "captured_at": now,
        "primary_database": primary,
        "limit_bytes": limit,
        "used_bytes": used,
        "data_size_bytes": total_data,
        "index_size_bytes": total_index,
        "usage_percent": round(pct, 2),
        "level": level,
        "thresholds_percent": {lvl: thr for thr, lvl in THRESHOLDS},
        "databases": per_db,
        "writes_at_risk": pct >= 90,
        "incident_recommended": pct >= 85,
    }


async def maybe_raise_storage_incident(snapshot: Dict[str, Any]) -> Optional[str]:
    """Create/update operational incident when usage >= 85%."""
    if not snapshot.get("available") or not snapshot.get("incident_recommended"):
        return None
    try:
        from services.incident_lifecycle_service import record_operational_detection

        pct = snapshot.get("usage_percent")
        level = snapshot.get("level")
        severity = "P0" if (pct or 0) >= 95 else "P1" if (pct or 0) >= 90 else "P2"
        outcome = await record_operational_detection(
            severity=severity,
            title=f"MongoDB storage capacity {level} ({pct}%)",
            description=(
                f"Cluster logical data+indexes at {pct}% of configured limit "
                f"({snapshot.get('used_bytes')} / {snapshot.get('limit_bytes')} bytes). "
                "Reclaim operational telemetry before Atlas blocks writes."
            ),
            source=INCIDENT_SOURCE,
            related_job_name="mongo_storage_capacity_monitor",
            metadata={
                "triggering_reason": INCIDENT_FINGERPRINT,
                "usage_percent": pct,
                "level": level,
                "used_bytes": snapshot.get("used_bytes"),
                "limit_bytes": snapshot.get("limit_bytes"),
                "databases": snapshot.get("databases"),
            },
        )
        incident_id = getattr(outcome, "incident_id", None) if outcome is not None else None
        if incident_id is None and isinstance(outcome, dict):
            incident_id = outcome.get("incident_id") or outcome.get("id")
        return str(incident_id) if incident_id else None
    except Exception as exc:
        logger.warning("mongo storage incident raise failed: %s", exc)
        return None


async def run_mongo_storage_capacity_monitor() -> Dict[str, Any]:
    snapshot = await collect_mongo_storage_snapshot()
    incident_id = await maybe_raise_storage_incident(snapshot)
    snapshot["incident_id"] = incident_id
    snapshot["message"] = f"Mongo storage {snapshot.get('level')} at {snapshot.get('usage_percent')}%"
    snapshot["count"] = 1 if snapshot.get("available") else 0
    snapshot["outcome_metrics"] = {
        "usage_percent": snapshot.get("usage_percent"),
        "level": snapshot.get("level"),
        "writes_at_risk": snapshot.get("writes_at_risk"),
    }
    return snapshot
