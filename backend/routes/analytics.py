"""
Analytics Dashboard API Routes

Provides business intelligence data for the admin analytics dashboard:
- Revenue metrics (daily, weekly, monthly)
- Order statistics by service, status, time period
- Conversion funnels
- SLA performance metrics
- Customer insights
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, timezone, timedelta
from middleware import admin_route_guard, require_owner_or_admin
from database import database
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/analytics", tags=["admin-analytics"])


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_date_range(period: str) -> tuple:
    """Get start and end dates for a period."""
    now = datetime.now(timezone.utc)
    
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7d":
        start = now - timedelta(days=7)
        end = now
    elif period == "30d":
        start = now - timedelta(days=30)
        end = now
    elif period == "90d":
        start = now - timedelta(days=90)
        end = now
    elif period == "ytd":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "all":
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = now
    else:
        start = now - timedelta(days=30)
        end = now
    
    return start.isoformat(), end.isoformat()


async def get_orders_in_range(start_date: str, end_date: str, filters: dict = None):
    """Get orders within a date range."""
    db = database.get_db()
    query = {
        "created_at": {"$gte": start_date, "$lte": end_date}
    }
    if filters:
        query.update(filters)
    
    cursor = db["orders"].find(query, {"_id": 0})
    return await cursor.to_list(length=10000)


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/summary")
async def get_analytics_summary(
    period: str = Query("30d", description="Time period: today, yesterday, 7d, 30d, 90d, ytd, all"),
    current_user: dict = Depends(admin_route_guard)
):
    """Get summary analytics for the dashboard."""
    start_date, end_date = get_date_range(period)
    
    # Get previous period for comparison
    period_days = {
        "today": 1, "yesterday": 1, "7d": 7, "30d": 30, "90d": 90, "ytd": 365, "all": 0
    }
    days = period_days.get(period, 30)
    
    if days > 0:
        prev_end = start_date
        prev_start = (datetime.fromisoformat(start_date.replace('Z', '+00:00')) - timedelta(days=days)).isoformat()
    else:
        prev_start = prev_end = start_date
    
    # Current period orders
    orders = await get_orders_in_range(start_date, end_date)
    paid_orders = [o for o in orders if o.get("stripe_payment_status") == "paid"]
    
    # Previous period orders for comparison
    prev_orders = await get_orders_in_range(prev_start, prev_end) if days > 0 else []
    prev_paid_orders = [o for o in prev_orders if o.get("stripe_payment_status") == "paid"]
    
    # Calculate revenue
    total_revenue = sum(
        (o.get("pricing", {}).get("total_pence", 0) or 0) 
        for o in paid_orders
    )
    prev_revenue = sum(
        (o.get("pricing", {}).get("total_pence", 0) or 0) 
        for o in prev_paid_orders
    )
    
    # Calculate changes
    revenue_change = ((total_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
    orders_change = ((len(paid_orders) - len(prev_paid_orders)) / len(prev_paid_orders) * 100) if prev_paid_orders else 0
    
    # Average order value
    avg_order_value = total_revenue / len(paid_orders) if paid_orders else 0
    prev_avg = prev_revenue / len(prev_paid_orders) if prev_paid_orders else 0
    aov_change = ((avg_order_value - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0
    
    # Orders by status
    status_counts = {}
    for order in orders:
        status = order.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Completion rate
    completed = status_counts.get("COMPLETED", 0)
    completion_rate = (completed / len(orders) * 100) if orders else 0
    
    return {
        "period": period,
        "date_range": {"start": start_date, "end": end_date},
        "revenue": {
            "total_pence": total_revenue,
            "total_formatted": f"£{total_revenue / 100:,.2f}",
            "change_percent": round(revenue_change, 1),
            "trend": "up" if revenue_change > 0 else "down" if revenue_change < 0 else "flat"
        },
        "orders": {
            "total": len(orders),
            "paid": len(paid_orders),
            "change_percent": round(orders_change, 1),
            "trend": "up" if orders_change > 0 else "down" if orders_change < 0 else "flat"
        },
        "average_order_value": {
            "pence": int(avg_order_value),
            "formatted": f"£{avg_order_value / 100:,.2f}",
            "change_percent": round(aov_change, 1),
        },
        "completion_rate": {
            "percent": round(completion_rate, 1),
            "completed": completed,
            "total": len(orders)
        },
        "status_breakdown": status_counts,
    }


@router.get("/revenue/daily")
async def get_daily_revenue(
    period: str = Query("30d"),
    current_user: dict = Depends(admin_route_guard)
):
    """Get daily revenue breakdown for charts."""
    start_date, end_date = get_date_range(period)
    orders = await get_orders_in_range(
        start_date, end_date, 
        {"stripe_payment_status": "paid"}
    )
    
    # Group by date
    daily_data = {}
    for order in orders:
        date_str = order.get("created_at", "")[:10]  # YYYY-MM-DD
        if date_str:
            if date_str not in daily_data:
                daily_data[date_str] = {"revenue_pence": 0, "orders": 0}
            daily_data[date_str]["revenue_pence"] += order.get("pricing", {}).get("total_pence", 0) or 0
            daily_data[date_str]["orders"] += 1
    
    # Convert to sorted list
    chart_data = [
        {
            "date": date,
            "revenue_pence": data["revenue_pence"],
            "revenue_formatted": f"£{data['revenue_pence'] / 100:,.2f}",
            "orders": data["orders"]
        }
        for date, data in sorted(daily_data.items())
    ]
    
    return {
        "period": period,
        "data": chart_data,
        "total_days": len(chart_data)
    }


@router.get("/services")
async def get_service_analytics(
    period: str = Query("30d"),
    current_user: dict = Depends(admin_route_guard)
):
    """Get analytics by service type."""
    start_date, end_date = get_date_range(period)
    orders = await get_orders_in_range(
        start_date, end_date,
        {"stripe_payment_status": "paid"}
    )
    
    # Group by service
    service_data = {}
    for order in orders:
        service_code = order.get("service_code", "UNKNOWN")
        service_name = order.get("service_name", service_code)
        
        if service_code not in service_data:
            service_data[service_code] = {
                "service_code": service_code,
                "service_name": service_name,
                "orders": 0,
                "revenue_pence": 0,
            }
        
        service_data[service_code]["orders"] += 1
        service_data[service_code]["revenue_pence"] += order.get("pricing", {}).get("total_pence", 0) or 0
    
    # Sort by revenue
    services = sorted(
        service_data.values(),
        key=lambda x: x["revenue_pence"],
        reverse=True
    )
    
    # Add formatted revenue
    for s in services:
        s["revenue_formatted"] = f"£{s['revenue_pence'] / 100:,.2f}"
    
    return {
        "period": period,
        "services": services,
        "total_services": len(services)
    }


@router.get("/sla-performance")
async def get_sla_performance(
    period: str = Query("30d"),
    current_user: dict = Depends(admin_route_guard)
):
    """Get SLA performance metrics."""
    start_date, end_date = get_date_range(period)
    
    # Get completed orders with SLA data
    orders = await get_orders_in_range(start_date, end_date)
    orders_with_sla = [o for o in orders if o.get("sla_target_at")]
    
    # Calculate metrics
    on_time = 0
    breached = 0
    warnings = 0
    
    for order in orders_with_sla:
        if order.get("sla_breach_sent"):
            breached += 1
        elif order.get("sla_warning_sent"):
            warnings += 1
        elif order.get("status") == "COMPLETED":
            completed_at = order.get("completed_at")
            target_at = order.get("sla_target_at")
            if completed_at and target_at and completed_at <= target_at:
                on_time += 1
    
    total_with_sla = len(orders_with_sla)
    on_time_rate = (on_time / total_with_sla * 100) if total_with_sla > 0 else 0
    breach_rate = (breached / total_with_sla * 100) if total_with_sla > 0 else 0
    
    return {
        "period": period,
        "total_orders": total_with_sla,
        "on_time": {
            "count": on_time,
            "percent": round(on_time_rate, 1)
        },
        "warnings_issued": {
            "count": warnings,
            "percent": round(warnings / total_with_sla * 100, 1) if total_with_sla > 0 else 0
        },
        "breached": {
            "count": breached,
            "percent": round(breach_rate, 1)
        },
        "health_score": round(100 - breach_rate, 1)  # Higher is better
    }


@router.get("/customers")
async def get_customer_analytics(
    period: str = Query("30d"),
    current_user: dict = Depends(admin_route_guard)
):
    """Get customer-related analytics."""
    start_date, end_date = get_date_range(period)
    orders = await get_orders_in_range(
        start_date, end_date,
        {"stripe_payment_status": "paid"}
    )
    
    # Group by customer email
    customer_data = {}
    for order in orders:
        email = order.get("customer", {}).get("email") or order.get("client_identity", {}).get("email")
        if not email:
            continue
        
        if email not in customer_data:
            customer_data[email] = {
                "email": email,
                "name": order.get("customer", {}).get("name") or order.get("client_identity", {}).get("full_name"),
                "orders": 0,
                "total_spent_pence": 0,
                "first_order": order.get("created_at"),
                "last_order": order.get("created_at"),
            }
        
        customer_data[email]["orders"] += 1
        customer_data[email]["total_spent_pence"] += order.get("pricing", {}).get("total_pence", 0) or 0
        
        # Track first/last order
        if order.get("created_at") < customer_data[email]["first_order"]:
            customer_data[email]["first_order"] = order.get("created_at")
        if order.get("created_at") > customer_data[email]["last_order"]:
            customer_data[email]["last_order"] = order.get("created_at")
    
    # Calculate metrics
    customers = list(customer_data.values())
    total_customers = len(customers)
    repeat_customers = len([c for c in customers if c["orders"] > 1])
    
    # Top customers by spend
    top_customers = sorted(customers, key=lambda x: x["total_spent_pence"], reverse=True)[:10]
    for c in top_customers:
        c["total_spent_formatted"] = f"£{c['total_spent_pence'] / 100:,.2f}"
    
    return {
        "period": period,
        "total_customers": total_customers,
        "repeat_customers": repeat_customers,
        "repeat_rate": round(repeat_customers / total_customers * 100, 1) if total_customers > 0 else 0,
        "top_customers": top_customers,
        "average_orders_per_customer": round(sum(c["orders"] for c in customers) / total_customers, 1) if total_customers > 0 else 0,
    }


@router.get("/conversion-funnel")
async def get_conversion_funnel(
    period: str = Query("30d"),
    current_user: dict = Depends(admin_route_guard)
):
    """Get conversion funnel metrics (drafts to orders to completion)."""
    start_date, end_date = get_date_range(period)
    
    db = database.get_db()
    
    # Get intake drafts
    drafts_cursor = db["intake_drafts"].find(
        {"created_at": {"$gte": start_date, "$lte": end_date}},
        {"_id": 0}
    )
    drafts = await drafts_cursor.to_list(length=10000)
    
    # Get orders
    orders = await get_orders_in_range(start_date, end_date)
    
    total_drafts = len(drafts)
    converted_drafts = len([d for d in drafts if d.get("status") == "CONVERTED"])
    paid_orders = len([o for o in orders if o.get("stripe_payment_status") == "paid"])
    completed_orders = len([o for o in orders if o.get("status") == "COMPLETED"])
    
    return {
        "period": period,
        "funnel": [
            {
                "stage": "Drafts Created",
                "count": total_drafts,
                "conversion_rate": 100
            },
            {
                "stage": "Payment Started",
                "count": converted_drafts,
                "conversion_rate": round(converted_drafts / total_drafts * 100, 1) if total_drafts > 0 else 0
            },
            {
                "stage": "Payment Completed",
                "count": paid_orders,
                "conversion_rate": round(paid_orders / total_drafts * 100, 1) if total_drafts > 0 else 0
            },
            {
                "stage": "Order Completed",
                "count": completed_orders,
                "conversion_rate": round(completed_orders / total_drafts * 100, 1) if total_drafts > 0 else 0
            }
        ],
        "overall_conversion": round(completed_orders / total_drafts * 100, 1) if total_drafts > 0 else 0
    }


@router.get("/addons")
async def get_addon_analytics(
    period: str = Query("30d"),
    current_user: dict = Depends(admin_route_guard)
):
    """Get add-on usage analytics (Fast Track, Printed Copy)."""
    start_date, end_date = get_date_range(period)
    orders = await get_orders_in_range(
        start_date, end_date,
        {"stripe_payment_status": "paid"}
    )
    
    total_orders = len(orders)
    fast_track_count = 0
    printed_copy_count = 0
    fast_track_revenue = 0
    printed_copy_revenue = 0
    
    for order in orders:
        addons = order.get("addons", [])
        
        if "FAST_TRACK" in addons or order.get("fast_track"):
            fast_track_count += 1
            fast_track_revenue += 2000  # £20
        
        if "PRINTED_COPY" in addons or order.get("requires_postal_delivery"):
            printed_copy_count += 1
            printed_copy_revenue += 2500  # £25
    
    return {
        "period": period,
        "total_orders": total_orders,
        "fast_track": {
            "count": fast_track_count,
            "adoption_rate": round(fast_track_count / total_orders * 100, 1) if total_orders > 0 else 0,
            "revenue_pence": fast_track_revenue,
            "revenue_formatted": f"£{fast_track_revenue / 100:,.2f}"
        },
        "printed_copy": {
            "count": printed_copy_count,
            "adoption_rate": round(printed_copy_count / total_orders * 100, 1) if total_orders > 0 else 0,
            "revenue_pence": printed_copy_revenue,
            "revenue_formatted": f"£{printed_copy_revenue / 100:,.2f}"
        },
        "total_addon_revenue": {
            "pence": fast_track_revenue + printed_copy_revenue,
            "formatted": f"£{(fast_track_revenue + printed_copy_revenue) / 100:,.2f}"
        }
    }


# ============================================================================
# ADVANCED ANALYTICS - CUSTOM DATE RANGES & PERIOD COMPARISON
# ============================================================================

def parse_custom_date(date_str: str) -> datetime:
    """Parse custom date string to datetime."""
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _analytics_events_query(from_date: Optional[str], to_date: Optional[str], source: Optional[str], plan: Optional[str]):
    """Build query and date range for analytics_events. from/to are YYYY-MM-DD or ISO."""
    now = datetime.now(timezone.utc)
    if from_date and to_date:
        start = parse_custom_date(from_date)
        end = parse_custom_date(to_date)
    else:
        end = now
        start = now - timedelta(days=30)
    query = {"ts": {"$gte": start, "$lte": end}}
    if source and source.strip():
        query["source"] = source.strip()
    if plan and plan.strip():
        query["plan_code"] = plan.strip()
    return query, start, end


def get_comparison_period(start: datetime, end: datetime) -> tuple:
    """Calculate the comparison period (same duration, immediately before)."""
    duration = end - start
    comp_end = start
    comp_start = start - duration
    return comp_start, comp_end


@router.get("/v2/summary")
async def get_advanced_summary(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or ISO)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD or ISO)"),
    period: str = Query("30d", description="Preset period if custom dates not provided"),
    compare: bool = Query(True, description="Include comparison with previous period"),
    current_user: dict = Depends(admin_route_guard)
):
    """
    Advanced analytics summary with custom date ranges and period comparison.
    Supports both preset periods and custom date ranges.
    """
    db = database.get_db()
    
    # Determine date range
    if start_date and end_date:
        current_start = parse_custom_date(start_date)
        current_end = parse_custom_date(end_date)
    else:
        start_iso, end_iso = get_date_range(period)
        current_start = parse_custom_date(start_iso)
        current_end = parse_custom_date(end_iso)
    
    # Get comparison period
    comp_start, comp_end = get_comparison_period(current_start, current_end)
    
    # Fetch current period data
    current_orders = await get_orders_in_range(
        current_start.isoformat(), 
        current_end.isoformat()
    )
    current_paid = [o for o in current_orders if o.get("stripe_payment_status") == "paid"]
    
    # Fetch comparison period data
    comp_orders = []
    comp_paid = []
    if compare:
        comp_orders = await get_orders_in_range(
            comp_start.isoformat(),
            comp_end.isoformat()
        )
        comp_paid = [o for o in comp_orders if o.get("stripe_payment_status") == "paid"]
    
    # Calculate metrics
    current_revenue = sum((o.get("pricing", {}).get("total_pence", 0) or 0) for o in current_paid)
    comp_revenue = sum((o.get("pricing", {}).get("total_pence", 0) or 0) for o in comp_paid)
    
    # Get clients in period
    current_clients_cursor = db.clients.find({
        "created_at": {"$gte": current_start.isoformat(), "$lte": current_end.isoformat()}
    }, {"_id": 0})
    current_clients = await current_clients_cursor.to_list(10000)
    
    comp_clients_cursor = db.clients.find({
        "created_at": {"$gte": comp_start.isoformat(), "$lte": comp_end.isoformat()}
    }, {"_id": 0}) if compare else None
    comp_clients = await comp_clients_cursor.to_list(10000) if comp_clients_cursor else []
    
    # Get leads in period
    current_leads_cursor = db.leads.find({
        "created_at": {"$gte": current_start.isoformat(), "$lte": current_end.isoformat()}
    }, {"_id": 0})
    current_leads = await current_leads_cursor.to_list(10000)
    
    comp_leads_cursor = db.leads.find({
        "created_at": {"$gte": comp_start.isoformat(), "$lte": comp_end.isoformat()}
    }, {"_id": 0}) if compare else None
    comp_leads = await comp_leads_cursor.to_list(10000) if comp_leads_cursor else []
    
    # Calculate changes
    def calc_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round((current - previous) / previous * 100, 1)
    
    def get_trend(change):
        if change > 0:
            return "up"
        elif change < 0:
            return "down"
        return "flat"
    
    revenue_change = calc_change(current_revenue, comp_revenue) if compare else 0
    orders_change = calc_change(len(current_paid), len(comp_paid)) if compare else 0
    clients_change = calc_change(len(current_clients), len(comp_clients)) if compare else 0
    leads_change = calc_change(len(current_leads), len(comp_leads)) if compare else 0
    
    # AOV calculation
    current_aov = current_revenue / len(current_paid) if current_paid else 0
    comp_aov = comp_revenue / len(comp_paid) if comp_paid else 0
    aov_change = calc_change(current_aov, comp_aov) if compare else 0
    
    # Completion rate
    completed = len([o for o in current_orders if o.get("status") == "COMPLETED"])
    completion_rate = (completed / len(current_orders) * 100) if current_orders else 0
    
    return {
        "period": {
            "type": "custom" if start_date and end_date else period,
            "current": {
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
                "days": (current_end - current_start).days
            },
            "comparison": {
                "start": comp_start.isoformat(),
                "end": comp_end.isoformat(),
                "days": (comp_end - comp_start).days
            } if compare else None
        },
        "metrics": {
            "revenue": {
                "current": current_revenue,
                "previous": comp_revenue if compare else None,
                "formatted": f"£{current_revenue / 100:,.2f}",
                "change_percent": revenue_change,
                "trend": get_trend(revenue_change)
            },
            "orders": {
                "current": len(current_paid),
                "previous": len(comp_paid) if compare else None,
                "change_percent": orders_change,
                "trend": get_trend(orders_change)
            },
            "average_order_value": {
                "current": int(current_aov),
                "previous": int(comp_aov) if compare else None,
                "formatted": f"£{current_aov / 100:,.2f}",
                "change_percent": aov_change,
                "trend": get_trend(aov_change)
            },
            "new_clients": {
                "current": len(current_clients),
                "previous": len(comp_clients) if compare else None,
                "change_percent": clients_change,
                "trend": get_trend(clients_change)
            },
            "leads": {
                "current": len(current_leads),
                "previous": len(comp_leads) if compare else None,
                "change_percent": leads_change,
                "trend": get_trend(leads_change)
            },
            "completion_rate": {
                "percent": round(completion_rate, 1),
                "completed": completed,
                "total": len(current_orders)
            }
        }
    }


@router.get("/v2/trends")
async def get_trend_data(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    period: str = Query("30d"),
    granularity: str = Query("day", description="Granularity: day, week, month"),
    metrics: str = Query("revenue,orders", description="Comma-separated metrics"),
    compare: bool = Query(True),
    current_user: dict = Depends(admin_route_guard)
):
    """
    Get trend data for charts with comparison overlay.
    Returns time-series data for visualization.
    """
    # Parse dates
    if start_date and end_date:
        current_start = parse_custom_date(start_date)
        current_end = parse_custom_date(end_date)
    else:
        start_iso, end_iso = get_date_range(period)
        current_start = parse_custom_date(start_iso)
        current_end = parse_custom_date(end_iso)
    
    comp_start, comp_end = get_comparison_period(current_start, current_end)
    
    # Fetch orders
    current_orders = await get_orders_in_range(current_start.isoformat(), current_end.isoformat())
    comp_orders = await get_orders_in_range(comp_start.isoformat(), comp_end.isoformat()) if compare else []
    
    # Parse metrics
    metric_list = [m.strip() for m in metrics.split(",")]
    
    # Group by granularity
    def get_period_key(date_str: str, gran: str) -> str:
        if not date_str:
            return ""
        date_part = date_str[:10]  # YYYY-MM-DD
        if gran == "day":
            return date_part
        elif gran == "week":
            dt = datetime.strptime(date_part, "%Y-%m-%d")
            week_start = dt - timedelta(days=dt.weekday())
            return week_start.strftime("%Y-%m-%d")
        elif gran == "month":
            return date_part[:7]  # YYYY-MM
        return date_part
    
    def aggregate_orders(orders, gran):
        data = {}
        for order in orders:
            key = get_period_key(order.get("created_at", ""), gran)
            if not key:
                continue
            if key not in data:
                data[key] = {"revenue": 0, "orders": 0, "clients": set()}
            
            if order.get("stripe_payment_status") == "paid":
                data[key]["revenue"] += order.get("pricing", {}).get("total_pence", 0) or 0
                data[key]["orders"] += 1
            
            client_id = order.get("client_id")
            if client_id:
                data[key]["clients"].add(client_id)
        
        # Convert sets to counts
        for key in data:
            data[key]["unique_clients"] = len(data[key]["clients"])
            del data[key]["clients"]
        
        return data
    
    current_data = aggregate_orders(current_orders, granularity)
    comp_data = aggregate_orders(comp_orders, granularity) if compare else {}
    
    # Build response
    all_keys = sorted(set(current_data.keys()))
    
    series = []
    for metric in metric_list:
        current_values = []
        comp_values = []
        
        for i, key in enumerate(all_keys):
            current_values.append({
                "period": key,
                "value": current_data.get(key, {}).get(metric, 0),
                "index": i
            })
            
            if compare and i < len(comp_data):
                comp_keys = sorted(comp_data.keys())
                if i < len(comp_keys):
                    comp_values.append({
                        "period": comp_keys[i],
                        "value": comp_data.get(comp_keys[i], {}).get(metric, 0),
                        "index": i
                    })
        
        series.append({
            "metric": metric,
            "current": current_values,
            "comparison": comp_values if compare else None
        })
    
    return {
        "granularity": granularity,
        "periods": all_keys,
        "series": series,
        "compare_enabled": compare
    }


@router.get("/v2/breakdown")
async def get_breakdown(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    period: str = Query("30d"),
    dimension: str = Query("service", description="Breakdown by: service, status, day_of_week, hour"),
    current_user: dict = Depends(admin_route_guard)
):
    """
    Get breakdown analytics by different dimensions.
    """
    if start_date and end_date:
        current_start = parse_custom_date(start_date)
        current_end = parse_custom_date(end_date)
    else:
        start_iso, end_iso = get_date_range(period)
        current_start = parse_custom_date(start_iso)
        current_end = parse_custom_date(end_iso)
    
    orders = await get_orders_in_range(current_start.isoformat(), current_end.isoformat())
    paid_orders = [o for o in orders if o.get("stripe_payment_status") == "paid"]
    
    breakdown = {}
    
    for order in paid_orders:
        if dimension == "service":
            key = order.get("service_code", "OTHER")
            label = order.get("service_name", key)
        elif dimension == "status":
            key = order.get("status", "UNKNOWN")
            label = key
        elif dimension == "day_of_week":
            created = order.get("created_at", "")
            if created:
                dt = parse_custom_date(created)
                key = str(dt.weekday())
                label = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]
            else:
                continue
        elif dimension == "hour":
            created = order.get("created_at", "")
            if created:
                dt = parse_custom_date(created)
                key = str(dt.hour)
                label = f"{dt.hour:02d}:00"
            else:
                continue
        else:
            continue
        
        if key not in breakdown:
            breakdown[key] = {"key": key, "label": label, "count": 0, "revenue": 0}
        
        breakdown[key]["count"] += 1
        breakdown[key]["revenue"] += order.get("pricing", {}).get("total_pence", 0) or 0
    
    # Sort and format
    items = sorted(breakdown.values(), key=lambda x: x["revenue"], reverse=True)
    total_revenue = sum(i["revenue"] for i in items)
    
    for item in items:
        item["revenue_formatted"] = f"£{item['revenue'] / 100:,.2f}"
        item["percentage"] = round(item["revenue"] / total_revenue * 100, 1) if total_revenue > 0 else 0
    
    return {
        "dimension": dimension,
        "period": {
            "start": current_start.isoformat(),
            "end": current_end.isoformat()
        },
        "items": items,
        "total_revenue": total_revenue,
        "total_revenue_formatted": f"£{total_revenue / 100:,.2f}"
    }


# ============================================================================
# CONVERSION FUNNEL (analytics_events)
# ============================================================================

def _parse_from_to(from_date: Optional[str], to_date: Optional[str], period: str = "30d") -> tuple:
    """Return (start_dt, end_dt) for analytics_events query."""
    if from_date and to_date:
        try:
            start = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        except ValueError:
            start = datetime.strptime(from_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        try:
            end = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        except ValueError:
            end = datetime.strptime(to_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return start, end
    start_iso, end_iso = get_date_range(period)
    return parse_custom_date(start_iso), parse_custom_date(end_iso)


async def _analytics_events_query(
    start_dt: datetime, end_dt: datetime,
    source: Optional[str] = None, plan: Optional[str] = None,
) -> dict:
    """Build query dict for analytics_events collection."""
    q = {"ts": {"$gte": start_dt, "$lte": end_dt}}
    if source:
        q["source"] = source
    if plan:
        q["plan_code"] = plan
    return q


@router.get("/overview", dependencies=[Depends(require_owner_or_admin)])
async def get_conversion_overview(
    from_date: Optional[str] = Query(None, description="From date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="To date YYYY-MM-DD"),
    period: str = Query("30d", description="Preset if from/to not set"),
    source: Optional[str] = Query(None, description="Filter by source"),
    plan: Optional[str] = Query(None, description="Filter by plan_code"),
    current_user: dict = Depends(admin_route_guard),
):
    """
    Conversion funnel overview from analytics_events.
    Returns KPI counts, conversion rates, median times, leads by source, failure counts.
    """
    db = database.get_db()
    start_dt, end_dt = _parse_from_to(from_date, to_date, period)
    q = await _analytics_events_query(start_dt, end_dt, source, plan)

    pipeline_lead = [
        {"$match": {**q, "event": "lead_captured"}},
        {"$group": {"_id": "$lead_id"}},
        {"$count": "count"},
    ]
    def pipeline_client(ev):
        return [
            {"$match": {**q, "event": ev}},
            {"$group": {"_id": "$client_id"}},
            {"$count": "count"},
        ]
    events_for_count = [
        "lead_captured", "intake_submitted", "checkout_started", "payment_succeeded",
        "provisioning_completed", "activation_email_sent", "password_set", "first_doc_uploaded",
    ]
    kpis = {}
    lead_cur = db.analytics_events.aggregate(pipeline_lead)
    lead_list = await lead_cur.to_list(length=1)
    kpis["leads"] = lead_list[0]["count"] if lead_list else 0
    for ev in events_for_count[1:]:
        cur = db.analytics_events.aggregate(pipeline_client(ev))
        lst = await cur.to_list(length=1)
        kpis[ev] = lst[0]["count"] if lst else 0

    def conv(prev, curr):
        if prev == 0:
            return 0.0
        return round(100.0 * curr / prev, 1)
    conversion_rates = {
        "lead_to_intake": conv(kpis["leads"], kpis["intake_submitted"]),
        "intake_to_checkout": conv(kpis["intake_submitted"], kpis["checkout_started"]),
        "checkout_to_paid": conv(kpis["checkout_started"], kpis["payment_succeeded"]),
        "paid_to_provisioned": conv(kpis["payment_succeeded"], kpis["provisioning_completed"]),
        "provisioned_to_activation_email": conv(kpis["provisioning_completed"], kpis["activation_email_sent"]),
        "activation_to_password_set": conv(kpis["activation_email_sent"], kpis["password_set"]),
        "password_set_to_first_value": conv(kpis["password_set"], kpis["first_doc_uploaded"]),
        "lead_to_paid": conv(kpis["leads"], kpis["payment_succeeded"]),
        "lead_to_activated": conv(kpis["leads"], kpis["password_set"]),
    }

    async def median_seconds(event_a: str, event_b: str):
        cursor = db.analytics_events.find(
            {**q, "event": {"$in": [event_a, event_b]}, "client_id": {"$exists": True, "$ne": None}},
            {"client_id": 1, "event": 1, "ts": 1},
        )
        events_list = await cursor.to_list(length=50000)
        by_client = {}
        for e in events_list:
            cid = e.get("client_id")
            if not cid:
                continue
            if cid not in by_client:
                by_client[cid] = {}
            by_client[cid][e["event"]] = e.get("ts")
        deltas = []
        for cid, evs in by_client.items():
            if event_a in evs and event_b in evs:
                ta = evs[event_a] if isinstance(evs[event_a], datetime) else datetime.fromisoformat((evs[event_a] or "").replace("Z", "+00:00"))
                tb = evs[event_b] if isinstance(evs[event_b], datetime) else datetime.fromisoformat((evs[event_b] or "").replace("Z", "+00:00"))
                deltas.append((tb - ta).total_seconds())
        if not deltas:
            return None
        deltas.sort()
        mid = len(deltas) // 2
        return (deltas[mid - 1] + deltas[mid]) / 2.0 if len(deltas) % 2 == 0 else float(deltas[mid])

    median_paid_to_provisioned = await median_seconds("payment_succeeded", "provisioning_completed")
    median_provisioned_to_password = await median_seconds("provisioning_completed", "password_set")
    median_password_to_first_value = await median_seconds("password_set", "first_doc_uploaded")

    src_pipeline = [
        {"$match": {**q, "event": "lead_captured"}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    src_cur = db.analytics_events.aggregate(src_pipeline)
    leads_by_source = [{"source": x["_id"] or "unknown", "count": x["count"]} for x in await src_cur.to_list(length=100)]

    fail_pipeline = [
        {"$match": {**q, "event": {"$in": ["checkout_failed", "email_failed", "provisioning_failed"]}}},
        {"$group": {"_id": {"event": "$event", "error_code": "$metadata.error_code"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    fail_cur = db.analytics_events.aggregate(fail_pipeline)
    failures_by_error = []
    async for row in fail_cur:
        rid = row.get("_id") or {}
        failures_by_error.append({"event": rid.get("event"), "error_code": rid.get("error_code") or rid.get("event") or "unknown", "count": row["count"]})

    return {
        "from": start_dt.isoformat(),
        "to": end_dt.isoformat(),
        "filters": {"source": source, "plan": plan},
        "kpis": kpis,
        "conversion_rates": conversion_rates,
        "median_seconds": {
            "paid_to_provisioned": median_paid_to_provisioned,
            "provisioned_to_password_set": median_provisioned_to_password,
            "password_set_to_first_value": median_password_to_first_value,
        },
        "leads_by_source": leads_by_source,
        "failures_by_error": failures_by_error,
    }


@router.get("/funnel", dependencies=[Depends(require_owner_or_admin)])
async def get_conversion_funnel_events(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    period: str = Query("30d"),
    source: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    current_user: dict = Depends(admin_route_guard),
):
    """Funnel stage counts, step conversion %, drop-off from analytics_events."""
    db = database.get_db()
    start_dt, end_dt = _parse_from_to(from_date, to_date, period)
    q = await _analytics_events_query(start_dt, end_dt, source, plan)
    stages = [
        ("Lead Captured", "lead_captured", "lead_id"),
        ("Intake Submitted", "intake_submitted", "client_id"),
        ("Checkout Started", "checkout_started", "client_id"),
        ("Paid", "payment_succeeded", "client_id"),
        ("Provisioned", "provisioning_completed", "client_id"),
        ("Activation Email Sent", "activation_email_sent", "client_id"),
        ("Password Set", "password_set", "client_id"),
        ("First Value", "first_doc_uploaded", "client_id"),
    ]
    funnel = []
    prev_count = None
    for label, event_name, id_field in stages:
        pipe = [{"$match": {**q, "event": event_name}}, {"$group": {"_id": f"${id_field}"}}, {"$count": "count"}]
        cur = db.analytics_events.aggregate(pipe)
        lst = await cur.to_list(length=1)
        count = lst[0]["count"] if lst else 0
        step_pct = round(100.0 * count / prev_count, 1) if prev_count and prev_count > 0 else (100.0 if count > 0 else 0)
        drop_off = (prev_count - count) if prev_count is not None and prev_count > count else 0
        drop_pct = round(100.0 * drop_off / prev_count, 1) if prev_count and prev_count > 0 else 0
        funnel.append({
            "stage": label, "event": event_name, "count": count,
            "step_conversion_percent": step_pct, "drop_off_count": drop_off, "drop_off_percent": drop_pct,
        })
        prev_count = count
    return {"from": start_dt.isoformat(), "to": end_dt.isoformat(), "funnel": funnel}


@router.get("/failures", dependencies=[Depends(require_owner_or_admin)])
async def get_analytics_failures(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    period: str = Query("30d"),
    type: Optional[str] = Query(None, description="Filter: checkout | email | provisioning"),
    current_user: dict = Depends(admin_route_guard),
):
    """Recent failure events with request_id/stripe ids and metadata."""
    db = database.get_db()
    start_dt, end_dt = _parse_from_to(from_date, to_date, period)
    q = {"ts": {"$gte": start_dt, "$lte": end_dt}, "event": {"$in": ["checkout_failed", "email_failed", "provisioning_failed"]}}
    if type == "checkout":
        q["event"] = "checkout_failed"
    elif type == "email":
        q["event"] = "email_failed"
    elif type == "provisioning":
        q["event"] = "provisioning_failed"
    cursor = db.analytics_events.find(q).sort("ts", -1).limit(200)
    events = await cursor.to_list(length=200)
    out = []
    for e in events:
        ts = e.get("ts")
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        meta = e.get("metadata") or {}
        out.append({
            "ts": ts, "event": e.get("event"), "client_id": e.get("client_id"), "lead_id": e.get("lead_id"),
            "request_id": meta.get("request_id"), "stripe_session_id": e.get("stripe_session_id"),
            "stripe_subscription_id": e.get("stripe_subscription_id"), "error_code": meta.get("error_code"), "metadata": meta,
        })
    return {"from": start_dt.isoformat(), "to": end_dt.isoformat(), "type_filter": type, "events": out}
