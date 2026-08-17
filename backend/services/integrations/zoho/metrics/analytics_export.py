"""Build aggregated analytics export — no row-level PII."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from database import database
from services.integrations.zoho.version import DEFAULT_PAYLOAD_VERSION

# Evidence (writers): lead_service / support_service persist created_at, converted_at,
# updated_at via datetime.now(timezone.utc).isoformat() — ISO strings are primary.
# Convert paths also parse created_at with fromisoformat (string expectation).
# Historical BSON UTC datetimes remain possible; dual-bound queries avoid undercount.
TIMESTAMP_STORAGE_NOTE = (
    "primary_iso_strings_with_dual_bound_query_for_bson_compat"
)


def period_timestamp_filter(
    field: str,
    period_start_dt: datetime,
    period_end_dt: datetime,
) -> Dict[str, Any]:
    """
    Match documents whose ``field`` falls in [start, end).

    Compatible with both ISO-8601 string timestamps and BSON UTC datetimes.
    """
    start_iso = period_start_dt.isoformat()
    end_iso = period_end_dt.isoformat()
    return {
        "$or": [
            {field: {"$gte": start_iso, "$lt": end_iso}},
            {field: {"$gte": period_start_dt, "$lt": period_end_dt}},
        ]
    }

# Contractual Phase B daily aggregate columns (12). Append-only import schema.
ANALYTICS_DAILY_AGGREGATE_COLUMNS: Tuple[str, ...] = (
    "payload_version",
    "period_start",
    "period_end",
    "leads_created_count",
    "leads_converted_count",
    "total_leads_count",
    "conversion_rate_pct",
    "active_subscriptions_count",
    "mrr_summary_gbp",
    "support_tickets_open_count",
    "support_tickets_closed_count",
    "export_type",
)

_NUMERIC_COLUMNS = frozenset(
    {
        "payload_version",
        "leads_created_count",
        "leads_converted_count",
        "total_leads_count",
        "conversion_rate_pct",
        "active_subscriptions_count",
        "mrr_summary_gbp",
        "support_tickets_open_count",
        "support_tickets_closed_count",
    }
)


def resolve_daily_reporting_period(
    now: datetime | None = None,
) -> Tuple[datetime, datetime]:
    """
    Return the last completed UTC calendar day as [start, end).

    period_start / period_end identify the aggregation window for
    ``export_type=aggregated_daily``, not export execution time. Boundaries
    are UTC midnights so repeated exports on the same calendar day emit the
    same period identifiers.
    """
    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    else:
        clock = clock.astimezone(timezone.utc)
    period_end = clock.replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = period_end - timedelta(days=1)
    return period_start, period_end


def validate_analytics_export_payload(export_data: Dict[str, Any]) -> List[str]:
    """
    Pre-transmission payload checks. Returns actionable issue strings (empty = ok).

    Does not call Zoho; validates Pleerity contract only.
    """
    issues: List[str] = []
    if not isinstance(export_data, dict) or not export_data:
        return ["payload_empty_or_not_object"]

    keys = set(export_data.keys())
    required = set(ANALYTICS_DAILY_AGGREGATE_COLUMNS)
    missing = sorted(required - keys)
    unexpected = sorted(keys - required)
    if missing:
        issues.append(f"missing_required_columns:{','.join(missing)}")
    if unexpected:
        issues.append(f"unexpected_columns:{','.join(unexpected)}")

    if export_data.get("export_type") != "aggregated_daily":
        issues.append("export_type_must_be_aggregated_daily")
    if export_data.get("payload_version") != DEFAULT_PAYLOAD_VERSION:
        issues.append(
            f"payload_version_mismatch:expected_{DEFAULT_PAYLOAD_VERSION}"
            f":got_{export_data.get('payload_version')!r}"
        )

    period_start = export_data.get("period_start")
    period_end = export_data.get("period_end")
    if not isinstance(period_start, str) or not period_start:
        issues.append("period_start_must_be_non_empty_iso_string")
    if not isinstance(period_end, str) or not period_end:
        issues.append("period_end_must_be_non_empty_iso_string")
    if isinstance(period_start, str) and isinstance(period_end, str) and period_start and period_end:
        try:
            start_dt = datetime.fromisoformat(period_start)
            end_dt = datetime.fromisoformat(period_end)
            if start_dt.tzinfo is None or end_dt.tzinfo is None:
                issues.append("period_boundaries_must_be_timezone_aware")
            else:
                start_utc = start_dt.astimezone(timezone.utc)
                end_utc = end_dt.astimezone(timezone.utc)
                if (
                    start_utc.hour,
                    start_utc.minute,
                    start_utc.second,
                    start_utc.microsecond,
                ) != (0, 0, 0, 0) or (
                    end_utc.hour,
                    end_utc.minute,
                    end_utc.second,
                    end_utc.microsecond,
                ) != (0, 0, 0, 0):
                    issues.append("period_boundaries_must_be_utc_midnight")
                if end_utc - start_utc != timedelta(days=1):
                    issues.append("period_end_must_be_exactly_one_day_after_period_start")
        except ValueError:
            issues.append("period_boundaries_not_parseable_iso8601")

    for col in _NUMERIC_COLUMNS:
        if col not in export_data:
            continue
        val = export_data.get(col)
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            issues.append(f"column_not_numeric:{col}")
        elif isinstance(val, float) and (val != val):  # NaN
            issues.append(f"column_nan:{col}")
        elif col.endswith("_count") and isinstance(val, (int, float)) and val < 0:
            issues.append(f"count_negative:{col}")

    return issues


async def build_analytics_export() -> Dict[str, Any]:
    db = database.get_db()
    period_start_dt, period_end_dt = resolve_daily_reporting_period()
    period_start = period_start_dt.isoformat()
    period_end = period_end_dt.isoformat()

    # Period-scoped counts use inclusive start / exclusive end (UTC midnights).
    # Dual-bound filters support ISO string and BSON datetime storage.
    leads_created = await db.leads.count_documents(
        period_timestamp_filter("created_at", period_start_dt, period_end_dt)
    )
    leads_converted = await db.leads.count_documents(
        period_timestamp_filter("converted_at", period_start_dt, period_end_dt)
    )
    total_leads = await db.leads.count_documents({})
    conversion_rate = round((leads_converted / leads_created * 100), 2) if leads_created else 0.0

    active_subs = await db.client_billing.count_documents({"subscription_status": "active"})
    mrr_summary = 0.0
    try:
        pipeline = [
            {"$match": {"subscription_status": "active"}},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$mrr_gbp", 0]}}}},
        ]
        agg = await db.client_billing.aggregate(pipeline).to_list(1)
        if agg:
            mrr_summary = float(agg[0].get("total") or 0)
    except Exception:
        mrr_summary = 0.0

    open_tickets = await db.support_tickets.count_documents({"status": {"$in": ["open", "pending"]}})
    closed_tickets = await db.support_tickets.count_documents(
        {
            "status": "closed",
            **period_timestamp_filter("updated_at", period_start_dt, period_end_dt),
        }
    )

    return {
        "payload_version": DEFAULT_PAYLOAD_VERSION,
        "period_start": period_start,
        "period_end": period_end,
        "leads_created_count": leads_created,
        "leads_converted_count": leads_converted,
        "total_leads_count": total_leads,
        "conversion_rate_pct": conversion_rate,
        "active_subscriptions_count": active_subs,
        "mrr_summary_gbp": mrr_summary,
        "support_tickets_open_count": open_tickets,
        "support_tickets_closed_count": closed_tickets,
        "export_type": "aggregated_daily",
    }
