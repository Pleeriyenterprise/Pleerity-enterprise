"""
Contractor service: CRUD for contractors (Ops & Compliance / Contractor Network).
Contractors can be system-wide (client_id None) or client-preferred (client_id set).
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from database import database
import logging
import re

from services.assignment_eligibility_recovery import (
    EXCLUSION_SAMPLE_LIMIT,
    build_assignment_eligibility_recovery,
    contractor_exclusion_sample,
)
from services.compliance_contractor_capability import (
    contractor_verified_qualifies_for_requirement,
    parse_execution_capabilities,
    parse_verified_execution_capabilities,
)
from services.compliance_rules_registry import (
    canonicalize_uk_portfolio_label,
    portfolio_jurisdiction_label,
)
from services.requirement_code_registry import CANONICAL_REQUIREMENT_CODES, normalize_requirement_code
from services.work_order_execution_constants import (
    ALLOWED_EXECUTION_CAPABILITIES,
    EXECUTION_CAPABILITY_COMPLIANCE,
    EXECUTION_CAPABILITY_MAINTENANCE,
    WORK_ORDER_KIND_COMPLIANCE,
    WORK_ORDER_KIND_MAINTENANCE,
)

logger = logging.getLogger(__name__)

try:
    from bson import ObjectId
except ImportError:
    ObjectId = None  # type: ignore[misc, assignment]

# Entry path / visibility (task: three models)
SOURCE_LANDLORD_ADDED = "landlord_added"
SOURCE_PLATFORM_NETWORK = "platform_network"
SOURCE_SELF_REGISTERED = "self_registered"
SOURCE_CLIENT_SUPPLIED_PERSONAL = "client_supplied_personal"
STATUS_ACTIVE = "active"
STATUS_PENDING_REVIEW = "pending_review"
STATUS_SUSPENDED = "suspended"
PORTAL_ACCESS_NOT_INVITED = "not_invited"
PORTAL_ACCESS_NOT_ACTIVATED = "not_activated"  # synonym stored as not_invited in practice
PORTAL_ACCESS_INVITE_PENDING = "invite_pending"
PORTAL_ACCESS_ENABLED = "enabled"
PORTAL_ACCESS_DISABLED = "disabled"

# Derived onboarding / invite truth (admin + landlord UI)
ONBOARDING_DIRECTORY_CREATED = "directory_created"
ONBOARDING_JOB_INVITE_SENT = "job_invite_sent"
ONBOARDING_PORTAL_INVITE_SENT = "portal_invite_sent"
ONBOARDING_ACTIVATION_PENDING = "portal_activation_pending"
ONBOARDING_ACTIVE = "active"
ONBOARDING_UNAVAILABLE = "unavailable"
ONBOARDING_DISABLED = "disabled"

ONBOARDING_STATE_LABELS = {
    ONBOARDING_DIRECTORY_CREATED: "Not invited",
    ONBOARDING_JOB_INVITE_SENT: "Job invite sent",
    ONBOARDING_PORTAL_INVITE_SENT: "Portal invite sent",
    ONBOARDING_ACTIVATION_PENDING: "Activation pending",
    ONBOARDING_ACTIVE: "Active",
    ONBOARDING_UNAVAILABLE: "Unavailable",
    ONBOARDING_DISABLED: "Disabled",
}

# Canonical lifecycle status (contractor.status)
LC_INVITED = "invited"
LC_PENDING_APPROVAL = "pending_approval"
LC_APPROVED = "approved"
LC_ACTIVE = "active"
LC_SUSPENDED = "suspended"
LC_ARCHIVED = "archived"

# Client job assign API: unvetted landlord_added rows created from the portal (not vetted network contractors).
ASSIGNMENT_PROFILE_CLIENT_PORTAL_LANDLORD = "client_portal_landlord_contractor"

# Rework: follow-up work order at same property within this many days of a prior completion counts as rework.
REWORK_DAYS = 30

RECOMMENDED_TYPE_TO_TRADES = {
    "gas_safe": ["heating", "gas", "gas_safe", "boiler"],
    "plumber": ["plumbing", "plumber"],
    "electrician": ["electrical", "electrician"],
    "damp_inspection": ["damp", "inspection", "damp_inspection"],
    "general": ["general", "handyman"],
}


def normalize_contractor_service_regions_list(raw: Optional[List[str]]) -> Optional[List[str]]:
    """Canonical UK portfolio labels only; None = caller should treat as unrestricted."""
    if not raw:
        return None
    out: List[str] = []
    for x in raw:
        c = canonicalize_uk_portfolio_label(x)
        if c and c not in out:
            out.append(c)
    return out if out else None


def _merged_service_regions_for_create(
    service_regions: Optional[List[str]],
    region: Optional[str],
) -> Optional[List[str]]:
    out = list(normalize_contractor_service_regions_list(service_regions) or [])
    c = canonicalize_uk_portfolio_label(region)
    if c and c not in out:
        out.append(c)
    return out if out else None


def contractor_service_regions_allow_jurisdiction(contractor: Dict[str, Any], job_jurisdiction: str) -> bool:
    """When contractor.service_regions is set, job portfolio label must be included."""
    regions = contractor.get("service_regions")
    if not regions or not isinstance(regions, list):
        return True
    canon_c = normalize_contractor_service_regions_list(regions)
    if not canon_c:
        return True
    job_c = canonicalize_uk_portfolio_label(job_jurisdiction)
    if not job_c:
        return True
    return job_c in canon_c


async def resolve_effective_work_order_jurisdiction(
    db,
    work_order: Dict[str, Any],
    client_id: str,
) -> str:
    """Effective portfolio label for the job (same resolution as work order creation)."""
    j = canonicalize_uk_portfolio_label(work_order.get("jurisdiction"))
    if j:
        return j
    lpr = (work_order.get("linked_property_requirement_id") or "").strip()
    if lpr:
        r = await db.requirements.find_one(
            {"requirement_id": lpr, "client_id": client_id},
            {"_id": 0, "jurisdiction": 1},
        )
        j2 = canonicalize_uk_portfolio_label((r or {}).get("jurisdiction"))
        if j2:
            return j2
    pid = work_order.get("property_id")
    if pid:
        p = await db.properties.find_one(
            {"property_id": pid, "client_id": client_id},
            {"_id": 0, "jurisdiction": 1},
        )
        c = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1})
        return portfolio_jurisdiction_label(p or {}, c or {})
    c_only = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1})
    return portfolio_jurisdiction_label({}, c_only or {})


async def _assert_contractor_jurisdiction_for_assignment(
    db,
    contractor_s: Dict[str, Any],
    wo: Dict[str, Any],
    client_id: str,
) -> None:
    job_j = await resolve_effective_work_order_jurisdiction(db, wo, client_id)
    if not contractor_service_regions_allow_jurisdiction(contractor_s, job_j):
        raise ValueError(
            "Contractor service regions do not cover this job's jurisdiction "
            f"({job_j}). Update the contractor's regions or choose a different contractor."
        )


def normalize_email_for_lookup(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def _coerce_execution_capabilities(raw: Optional[str]) -> str:
    v = (raw or EXECUTION_CAPABILITY_MAINTENANCE).strip().lower()
    if v not in ALLOWED_EXECUTION_CAPABILITIES:
        raise ValueError(
            f"execution_capabilities must be one of: {', '.join(sorted(ALLOWED_EXECUTION_CAPABILITIES))}"
        )
    return v


def _coerce_supported_requirement_codes(raw: Optional[List[str]]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in raw or []:
        c = normalize_requirement_code(str(x))
        if not c or c not in CANONICAL_REQUIREMENT_CODES:
            raise ValueError(f"Invalid supported_requirement_codes entry: {x!r}")
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def contractor_passes_work_order_execution_gate(contractor: Dict[str, Any], wo: Dict[str, Any]) -> bool:
    """Backend gate: maintenance vs compliance capability must match work order kind."""
    kind = (wo.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        caps_v = parse_verified_execution_capabilities(contractor)
        if EXECUTION_CAPABILITY_COMPLIANCE not in caps_v:
            return False
        code = (wo.get("requirement_code") or "").strip().lower()
        if code and not contractor_verified_qualifies_for_requirement(contractor, code):
            return False
        return True
    caps_m = parse_execution_capabilities(contractor)
    if caps_m == {EXECUTION_CAPABILITY_COMPLIANCE}:
        return False
    return EXECUTION_CAPABILITY_MAINTENANCE in caps_m


def normalize_lifecycle_status(status: Optional[str]) -> str:
    s = (status or "").strip().lower()
    if s == STATUS_PENDING_REVIEW:
        return LC_PENDING_APPROVAL
    if s == LC_ARCHIVED:
        return LC_ARCHIVED
    return s


def portal_access_is_activated(contractor: Dict[str, Any]) -> bool:
    return (contractor.get("portal_access_status") or "").strip().lower() == PORTAL_ACCESS_ENABLED


def contractor_is_job_link_active(contractor: Dict[str, Any]) -> bool:
    """Job-link API requires lifecycle active and portal not disabled."""
    if (contractor.get("portal_access_status") or "").strip().lower() == PORTAL_ACCESS_DISABLED:
        return False
    return normalize_lifecycle_status(contractor.get("status")) == LC_ACTIVE


def derive_contractor_onboarding_state(contractor: Dict[str, Any]) -> str:
    """
    Single invite/activation truth for admin and landlord surfaces.
    Job assignment email and portal invite are tracked separately; never show directory-only
    when a job invite was actually sent.
    """
    portal = (contractor.get("portal_access_status") or "").strip().lower()
    lifecycle = normalize_lifecycle_status(contractor.get("status"))
    if portal == PORTAL_ACCESS_DISABLED:
        return ONBOARDING_DISABLED
    if lifecycle in (LC_SUSPENDED, LC_ARCHIVED):
        return ONBOARDING_UNAVAILABLE
    if contractor_is_job_link_active(contractor) and portal_access_is_activated(contractor):
        return ONBOARDING_ACTIVE
    if portal == PORTAL_ACCESS_INVITE_PENDING:
        return ONBOARDING_ACTIVATION_PENDING
    if portal == PORTAL_ACCESS_ENABLED and lifecycle != LC_ACTIVE:
        return ONBOARDING_ACTIVATION_PENDING
    if contractor.get("portal_invite_sent_at"):
        return ONBOARDING_PORTAL_INVITE_SENT
    if contractor.get("job_invite_sent_at"):
        return ONBOARDING_JOB_INVITE_SENT
    return ONBOARDING_DIRECTORY_CREATED


def onboarding_state_label(state: str) -> str:
    return ONBOARDING_STATE_LABELS.get((state or "").strip().lower(), "Not invited")


def enrich_contractor_onboarding_view(contractor: Dict[str, Any]) -> Dict[str, Any]:
    """Attach derived onboarding fields for API responses."""
    out = dict(contractor)
    state = derive_contractor_onboarding_state(out)
    out["onboarding_state"] = state
    out["onboarding_state_label"] = onboarding_state_label(state)
    out["portal_activation_required"] = state not in (ONBOARDING_ACTIVE, ONBOARDING_DISABLED, ONBOARDING_UNAVAILABLE)
    return out


def contractor_trade_matches_category(contractor: Dict[str, Any], category: Optional[str]) -> bool:
    cat = (category or "").strip().lower()
    if not cat:
        return True
    trades = [str(t).strip().lower() for t in (contractor.get("trade_types") or []) if str(t).strip()]
    if not trades:
        return False
    for t in trades:
        if t in cat or cat in t:
            return True
    for key, synonyms in RECOMMENDED_TYPE_TO_TRADES.items():
        key_l = key.lower()
        if key_l in cat or cat in key_l:
            if any(s in trades for s in synonyms):
                return True
    return False


def _uk_postcode_outward(pc: str) -> str:
    s = (pc or "").strip().upper().replace("  ", " ")
    if not s:
        return ""
    parts = s.split()
    return parts[0] if parts else s


def _contractor_location_strings(contractor: Dict[str, Any]) -> List[str]:
    pools: List[str] = []
    for field in ("areas_served", "coverage_area"):
        v = contractor.get(field)
        if isinstance(v, list):
            pools.extend(str(x).strip() for x in v if str(x).strip())
        elif v:
            pools.append(str(v).strip())
    reg = contractor.get("registration_postcode")
    if reg:
        pools.append(str(reg).strip())
    r = contractor.get("region")
    if r:
        pools.append(str(r).strip())
    return pools


def contractor_location_matches_property(
    contractor: Dict[str, Any],
    property_postcode: Optional[str],
    *,
    property_jurisdiction: Optional[str] = None,
) -> bool:
    """
    True when contractor location data is absent, informational only, or matches the property.

    Portfolio labels (England, Scotland, …) match job/property jurisdiction — not postcodes.
    Postcode-like fragments match the property postcode (outward or full).
    Free-text labels (e.g. London, Midlands) are informational and do not block assignment.
    """
    prop_pc = (property_postcode or "").strip().upper()
    outward_prop = _uk_postcode_outward(prop_pc) if prop_pc else ""
    job_j = canonicalize_uk_portfolio_label(property_jurisdiction or "") if property_jurisdiction else None
    pools = _contractor_location_strings(contractor)
    if not pools:
        return True

    portfolio_entries: List[str] = []
    postcode_entries: List[str] = []
    for p in pools:
        pl = canonicalize_uk_portfolio_label(p)
        if pl:
            if pl not in portfolio_entries:
                portfolio_entries.append(pl)
        elif _looks_like_uk_postcode_fragment(p):
            postcode_entries.append(p)

    if not portfolio_entries and not postcode_entries:
        return True

    if portfolio_entries and job_j and job_j in portfolio_entries:
        return True

    if not prop_pc:
        if portfolio_entries:
            return False
        return True

    prop_norm = prop_pc.replace(" ", "")
    for p in postcode_entries:
        pn = p.upper().replace(" ", "")
        if not pn:
            continue
        if pn == prop_norm:
            return True
        out_c = _uk_postcode_outward(p)
        if outward_prop and out_c and (
            out_c == outward_prop or outward_prop.startswith(out_c) or out_c.startswith(outward_prop)
        ):
            return True
    return False


_UK_POSTCODE_FRAGMENT_RE = re.compile(
    r"^[A-Z]{1,2}\d{1,2}[A-Z]?$|^[A-Z]{1,2}\d{1,2}[A-Z]?\d[A-Z]{2}$",
    re.IGNORECASE,
)


def _looks_like_uk_postcode_fragment(value: str) -> bool:
    """True when a location string is postcode-like, not a region or city label."""
    compact = (value or "").strip().upper().replace(" ", "")
    if not compact or len(compact) > 8:
        return False
    if canonicalize_uk_portfolio_label(value):
        return False
    return bool(_UK_POSTCODE_FRAGMENT_RE.match(compact))


def contractor_property_scope_allows(contractor: Dict[str, Any], property_id: Optional[str]) -> bool:
    scope = contractor.get("property_scope")
    if not scope:
        return True
    if not isinstance(scope, list) or not property_id:
        return True
    allowed = {str(x).strip() for x in scope if str(x).strip()}
    if not allowed:
        return True
    return property_id.strip() in allowed


def contractor_client_link_allows(contractor: Dict[str, Any], client_id: str) -> bool:
    cid = contractor.get("client_id")
    if cid is None or cid == "":
        return True
    return str(cid).strip() == str(client_id).strip()


def contractor_is_assignable(contractor: Dict[str, Any]) -> Tuple[bool, str]:
    st = normalize_lifecycle_status(contractor.get("status"))
    if st in (LC_SUSPENDED, "suspended"):
        return False, "Contractor is suspended"
    if st == LC_ARCHIVED:
        return False, "Contractor is archived"
    email = (contractor.get("email") or "").strip()
    if not email:
        return False, "Contractor has no email address"
    if not contractor.get("vetted"):
        return False, "Contractor is not vetted for assignment"
    if not portal_access_is_activated(contractor):
        return False, "Contractor has not activated the contractor portal"
    if contractor.get("available_for_assignment") is False:
        return False, "Contractor is marked unavailable for assignments"
    if st == LC_ACTIVE:
        return True, ""
    if st == STATUS_ACTIVE and portal_access_is_activated(contractor) and contractor.get("vetted"):
        return True, ""
    return False, "Contractor must be active with an activated portal before assignment"


async def get_contractor_by_email_normalized(email: str) -> Optional[Dict[str, Any]]:
    norm = normalize_email_for_lookup(email)
    if not norm:
        return None
    db = database.get_db()
    doc = await db.contractors.find_one({"email_normalized": norm})
    if doc:
        return _sanitize_doc(doc)
    doc = await db.contractors.find_one({"email": norm})
    if doc:
        return _sanitize_doc(doc)
    return None


def _make_json_safe(obj: Any) -> Any:
    """Convert MongoDB ObjectId and other non-JSON types so FastAPI can serialize responses."""
    if ObjectId is not None and isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(x) for x in obj]
    return obj


def _sanitize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe copy of a contractor document (no raw ObjectId)."""
    out = dict(doc)
    out.pop("_id", None)
    return enrich_contractor_onboarding_view(_make_json_safe(out))


def _default_vetting_status(vetted: bool, status: Optional[str]) -> str:
    normalized = (status or "").strip().lower()
    if normalized in (STATUS_PENDING_REVIEW, LC_PENDING_APPROVAL):
        return LC_PENDING_APPROVAL
    return "approved" if vetted else "not_vetted"


async def list_contractors(
    client_id: Optional[str] = None,
    vetted_only: bool = False,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    pending_network_review: bool = False,
) -> Dict[str, Any]:
    """List contractors, optionally filtered by client_id, vetted, source_type, status.

    When pending_network_review=True: landlord_added contractors submitted for network promotion
    (submitted_to_network_at set, not yet approved_for_network_at, no rejection reason).
    """
    db = database.get_db()
    q: Dict[str, Any] = {}
    if client_id is not None:
        q["client_id"] = client_id
    if vetted_only:
        q["vetted"] = True
    if pending_network_review:
        q["source_type"] = SOURCE_LANDLORD_ADDED
        q["$and"] = [
            {"submitted_to_network_at": {"$exists": True, "$nin": [None, ""]}},
            {
                "$or": [
                    {"approved_for_network_at": {"$exists": False}},
                    {"approved_for_network_at": None},
                    {"approved_for_network_at": ""},
                ]
            },
            {
                "$or": [
                    {"network_submission_rejection_reason": {"$exists": False}},
                    {"network_submission_rejection_reason": None},
                    {"network_submission_rejection_reason": ""},
                ]
            },
        ]
    elif source_type is not None:
        q["source_type"] = source_type
    if status is not None:
        st = (status or "").strip().lower()
        # Pending Approvals tab: include legacy pending_review and canonical pending_approval (public applications).
        if st == STATUS_PENDING_REVIEW:
            q["status"] = {"$in": [STATUS_PENDING_REVIEW, LC_PENDING_APPROVAL]}
        else:
            q["status"] = status
    cursor = db.contractors.find(q).sort("name", 1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.contractors.count_documents(q)
    return {
        "contractors": [_sanitize_doc(d) for d in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


def _client_visible_statuses() -> List[str]:
    """Statuses a client may see for directory / assignment UI (excludes suspended)."""
    return [
        STATUS_ACTIVE,
        LC_ACTIVE,
        LC_APPROVED,
        LC_INVITED,
        LC_PENDING_APPROVAL,
        STATUS_PENDING_REVIEW,
    ]


def _visibility_query(client_id: str) -> Dict[str, Any]:
    """Contractors visible to a client: org match, platform network, or vetted self-registered. Excludes suspended."""
    vis = _client_visible_statuses()
    return {
        "$or": [
            {"client_id": client_id, "status": {"$in": vis}},
            {"client_id": client_id, "status": {"$exists": False}},
            {"client_id": None, "source_type": SOURCE_PLATFORM_NETWORK, "status": {"$in": vis}},
            {"client_id": None, "source_type": SOURCE_SELF_REGISTERED, "vetted": True, "status": {"$in": vis}},
            {"client_id": client_id, "source_type": SOURCE_CLIENT_SUPPLIED_PERSONAL},
        ],
    }


async def contractor_visible_to_client(contractor_id: str, client_id: str) -> bool:
    """Return True if the contractor is visible to the client (own private, network, or approved marketplace). Used to enforce assignment rules."""
    if not contractor_id or not client_id:
        return False
    db = database.get_db()
    q = {"contractor_id": contractor_id}
    q.update(_visibility_query(client_id))
    doc = await db.contractors.find_one(q, {"_id": 1, "status": 1})
    if not doc:
        return False
    st = normalize_lifecycle_status(doc.get("status"))
    return st not in (LC_SUSPENDED, "suspended", LC_ARCHIVED)


async def list_contractors_for_client(
    client_id: str,
    vetted_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    source_type: Optional[str] = None,
) -> Dict[str, Any]:
    """List contractors visible to a client: org-assigned, platform network, or approved marketplace. Only status=active."""
    db = database.get_db()
    q = _visibility_query(client_id)
    if vetted_only:
        q["vetted"] = True
    if source_type is not None:
        q["source_type"] = source_type
    cursor = db.contractors.find(q).sort("name", 1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.contractors.count_documents(q)
    return {
        "contractors": [_sanitize_doc(d) for d in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


async def get_contractor(contractor_id: str) -> Optional[Dict[str, Any]]:
    """Get a single contractor by id."""
    db = database.get_db()
    doc = await db.contractors.find_one({"contractor_id": contractor_id})
    if not doc:
        return None
    return _sanitize_doc(doc)


async def create_contractor(
    name: str,
    trade_types: Optional[List[str]] = None,
    vetted: bool = False,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    client_id: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    notes: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    contact_name: Optional[str] = None,
    region: Optional[str] = None,
    portal_access_status: Optional[str] = None,
    vetting_status: Optional[str] = None,
    coverage_area: Optional[List[str]] = None,
    property_scope: Optional[List[str]] = None,
    registration_postcode: Optional[str] = None,
    skip_email_duplicate_check: bool = False,
    execution_capabilities: Optional[str] = None,
    supported_requirement_codes: Optional[List[str]] = None,
    declared_execution_capabilities: Optional[str] = None,
    declared_supported_requirement_codes: Optional[List[str]] = None,
    declared_credentials: Optional[List[str]] = None,
    verified_execution_capabilities: Optional[str] = None,
    verified_supported_requirement_codes: Optional[List[str]] = None,
    service_regions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new contractor. Sets source_type/status when provided; defaults for backward compat."""
    from datetime import datetime, timezone
    import uuid

    email_norm = normalize_email_for_lookup(email) if email else ""
    if email_norm and not skip_email_duplicate_check:
        clash = await get_contractor_by_email_normalized(email_norm)
        if clash:
            raise ValueError("A contractor with this email already exists")

    now = datetime.now(timezone.utc).isoformat()
    eff_status = status or LC_APPROVED
    eff_exec = _coerce_execution_capabilities(execution_capabilities)
    eff_req_codes = _coerce_supported_requirement_codes(supported_requirement_codes)
    doc = {
        "contractor_id": str(uuid.uuid4()),
        "client_id": client_id,
        "name": name,
        "trade_types": trade_types or [],
        "vetted": vetted,
        "email": email,
        "email_normalized": email_norm or None,
        "phone": phone,
        "company_name": company_name,
        "areas_served": areas_served or coverage_area or [],
        "coverage_area": coverage_area or areas_served or [],
        "notes": notes,
        "created_at": now,
        "updated_at": now,
        "source_type": source_type or (SOURCE_LANDLORD_ADDED if client_id else SOURCE_PLATFORM_NETWORK),
        "status": eff_status,
        "credentials": credentials or [],
        "insurance_details": insurance_details,
        "contact_name": contact_name,
        "region": region,
        "rating_average": None,
        "job_count": 0,
        "sla_compliance_rate": None,
        "rework_rate": None,
        "linked_client_id": client_id,
        "linked_network": bool(not client_id and ((source_type or "").strip().lower() == SOURCE_PLATFORM_NETWORK)),
        "portal_access_status": (portal_access_status or PORTAL_ACCESS_NOT_INVITED).strip().lower(),
        "portal_invite_sent_at": None,
        "portal_invite_expires_at": None,
        "portal_invite_last_token_id": None,
        "portal_invite_accepted_at": None,
        "activated_at": None,
        "job_invite_sent_at": None,
        "job_invite_last_work_order_id": None,
        "available_for_assignment": True,
        "property_scope": property_scope or [],
        "registration_postcode": (registration_postcode or "").strip().upper() or None,
        "vetting_status": (vetting_status or _default_vetting_status(vetted, eff_status)).strip().lower(),
        "execution_capabilities": eff_exec,
        "supported_requirement_codes": eff_req_codes,
    }
    mr = _merged_service_regions_for_create(service_regions, region)
    if mr:
        doc["service_regions"] = mr
    if declared_execution_capabilities is not None:
        doc["declared_execution_capabilities"] = _coerce_execution_capabilities(declared_execution_capabilities)
    if declared_supported_requirement_codes is not None:
        doc["declared_supported_requirement_codes"] = _coerce_supported_requirement_codes(
            declared_supported_requirement_codes
        )
    if declared_credentials is not None:
        doc["declared_credentials"] = list(declared_credentials)
    if vetted:
        ve_src = (
            verified_execution_capabilities
            if verified_execution_capabilities is not None
            else execution_capabilities
        )
        vc_src = (
            verified_supported_requirement_codes
            if verified_supported_requirement_codes is not None
            else supported_requirement_codes
        )
        doc["verified_execution_capabilities"] = _coerce_execution_capabilities(ve_src)
        doc["verified_supported_requirement_codes"] = _coerce_supported_requirement_codes(vc_src)
        doc["verified_at"] = now
        doc["verified_by"] = "system_on_create"
    if client_id and (source_type or "").strip().lower() == SOURCE_LANDLORD_ADDED:
        doc["visibility_scope"] = "private"
    elif not client_id and (source_type or "").strip().lower() == SOURCE_PLATFORM_NETWORK:
        doc["visibility_scope"] = "network"
    elif not client_id and (source_type or "").strip().lower() == SOURCE_SELF_REGISTERED and vetted:
        doc["visibility_scope"] = "marketplace"
    elif client_id and (source_type or "").strip().lower() == SOURCE_CLIENT_SUPPLIED_PERSONAL:
        doc["visibility_scope"] = "client_personal"
    db = database.get_db()
    await db.contractors.insert_one(doc)
    return _sanitize_doc(doc)


async def update_contractor(
    contractor_id: str,
    name: Optional[str] = None,
    trade_types: Optional[List[str]] = None,
    vetted: Optional[bool] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    client_id: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    notes: Optional[str] = None,
    status: Optional[str] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    contact_name: Optional[str] = None,
    region: Optional[str] = None,
    submitted_to_network_at: Optional[str] = None,
    approved_for_network_at: Optional[str] = None,
    approved_by_admin_id: Optional[str] = None,
    network_submission_rejection_reason: Optional[str] = None,
    portal_access_status: Optional[str] = None,
    portal_invite_sent_at: Optional[str] = None,
    portal_invite_expires_at: Optional[str] = None,
    portal_invite_last_token_id: Optional[str] = None,
    portal_invite_accepted_at: Optional[str] = None,
    job_invite_sent_at: Optional[str] = None,
    job_invite_last_work_order_id: Optional[str] = None,
    vetting_status: Optional[str] = None,
    coverage_area: Optional[List[str]] = None,
    activated_at: Optional[str] = None,
    available_for_assignment: Optional[bool] = None,
    property_scope: Optional[List[str]] = None,
    registration_postcode: Optional[str] = None,
    execution_capabilities: Optional[str] = None,
    supported_requirement_codes: Optional[List[str]] = None,
    declared_execution_capabilities: Optional[str] = None,
    declared_supported_requirement_codes: Optional[List[str]] = None,
    declared_credentials: Optional[List[str]] = None,
    verified_execution_capabilities: Optional[str] = None,
    verified_supported_requirement_codes: Optional[List[str]] = None,
    verified_at: Optional[str] = None,
    verified_by: Optional[str] = None,
    service_regions: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Update a contractor. Only provided fields are updated."""
    from datetime import datetime, timezone

    db = database.get_db()
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    verified_touched = (
        verified_execution_capabilities is not None or verified_supported_requirement_codes is not None
    )
    cur_snapshot: Optional[Dict[str, Any]] = None
    if verified_touched:
        cur_snapshot = await db.contractors.find_one({"contractor_id": contractor_id})
    if name is not None:
        update["name"] = name
    if trade_types is not None:
        update["trade_types"] = trade_types
    if vetted is not None:
        update["vetted"] = vetted
    if email is not None:
        update["email"] = email
        en = normalize_email_for_lookup(email)
        update["email_normalized"] = en or None
        if en:
            clash = await db.contractors.find_one(
                {"email_normalized": en, "contractor_id": {"$ne": contractor_id}},
                {"contractor_id": 1},
            )
            if clash:
                raise ValueError("A contractor with this email already exists")
    if phone is not None:
        update["phone"] = phone
    if company_name is not None:
        update["company_name"] = company_name
    if client_id is not None:
        update["client_id"] = client_id
    if areas_served is not None:
        update["areas_served"] = areas_served
    if notes is not None:
        update["notes"] = notes
    if status is not None:
        update["status"] = status
    if credentials is not None:
        update["credentials"] = credentials
    if insurance_details is not None:
        update["insurance_details"] = insurance_details
    if contact_name is not None:
        update["contact_name"] = contact_name
    if region is not None:
        update["region"] = region
    if service_regions is not None:
        norm_sr = normalize_contractor_service_regions_list(service_regions)
        update["service_regions"] = norm_sr
    if submitted_to_network_at is not None:
        update["submitted_to_network_at"] = submitted_to_network_at
    if approved_for_network_at is not None:
        update["approved_for_network_at"] = approved_for_network_at
    if approved_by_admin_id is not None:
        update["approved_by_admin_id"] = approved_by_admin_id
    if network_submission_rejection_reason is not None:
        update["network_submission_rejection_reason"] = network_submission_rejection_reason
    if portal_access_status is not None:
        update["portal_access_status"] = portal_access_status
    if portal_invite_sent_at is not None:
        update["portal_invite_sent_at"] = portal_invite_sent_at
    if portal_invite_expires_at is not None:
        update["portal_invite_expires_at"] = portal_invite_expires_at
    if portal_invite_last_token_id is not None:
        update["portal_invite_last_token_id"] = portal_invite_last_token_id
    if portal_invite_accepted_at is not None:
        update["portal_invite_accepted_at"] = portal_invite_accepted_at
    if job_invite_sent_at is not None:
        update["job_invite_sent_at"] = job_invite_sent_at
    if job_invite_last_work_order_id is not None:
        update["job_invite_last_work_order_id"] = job_invite_last_work_order_id
    if vetting_status is not None:
        update["vetting_status"] = vetting_status
    if coverage_area is not None:
        update["coverage_area"] = coverage_area
        update["areas_served"] = coverage_area
    if activated_at is not None:
        update["activated_at"] = activated_at
    if available_for_assignment is not None:
        update["available_for_assignment"] = available_for_assignment
    if property_scope is not None:
        update["property_scope"] = property_scope
    if registration_postcode is not None:
        update["registration_postcode"] = (registration_postcode or "").strip().upper() or None
    if execution_capabilities is not None:
        update["execution_capabilities"] = _coerce_execution_capabilities(execution_capabilities)
    if supported_requirement_codes is not None:
        update["supported_requirement_codes"] = _coerce_supported_requirement_codes(supported_requirement_codes)
    if declared_execution_capabilities is not None:
        update["declared_execution_capabilities"] = _coerce_execution_capabilities(declared_execution_capabilities)
    if declared_supported_requirement_codes is not None:
        update["declared_supported_requirement_codes"] = _coerce_supported_requirement_codes(
            declared_supported_requirement_codes
        )
    if declared_credentials is not None:
        update["declared_credentials"] = declared_credentials
    if verified_execution_capabilities is not None:
        update["verified_execution_capabilities"] = _coerce_execution_capabilities(verified_execution_capabilities)
    if verified_supported_requirement_codes is not None:
        update["verified_supported_requirement_codes"] = _coerce_supported_requirement_codes(
            verified_supported_requirement_codes
        )
    if verified_touched and cur_snapshot is not None:
        eff_ve = (
            update["verified_execution_capabilities"]
            if "verified_execution_capabilities" in update
            else cur_snapshot.get("verified_execution_capabilities")
        )
        eff_vc = (
            update["verified_supported_requirement_codes"]
            if "verified_supported_requirement_codes" in update
            else cur_snapshot.get("verified_supported_requirement_codes")
        )
        if eff_ve is not None:
            update["execution_capabilities"] = _coerce_execution_capabilities(eff_ve)
        if eff_vc is not None:
            update["supported_requirement_codes"] = list(eff_vc)
        update["verified_at"] = verified_at or datetime.now(timezone.utc).isoformat()
        if verified_by is not None:
            update["verified_by"] = verified_by

    result = await db.contractors.find_one_and_update(
        {"contractor_id": contractor_id},
        {"$set": update},
        return_document=True,
    )
    if not result:
        return None
    return _sanitize_doc(result)


async def delete_contractor(contractor_id: str) -> bool:
    """Hard-delete a contractor only when dependency preflight passes; otherwise raises ValueError."""
    from services.contractor_identity_lifecycle import contractor_permanent_delete_preflight

    db = database.get_db()
    allowed, blockers = await contractor_permanent_delete_preflight(db, contractor_id)
    if not allowed:
        raise ValueError("preflight_failed:" + ",".join(blockers))
    result = await db.contractors.delete_one({"contractor_id": contractor_id})
    return result.deleted_count > 0


async def create_contractor_landlord(
    client_id: str,
    company_name: str,
    trade_types: List[str],
    phone: Optional[str] = None,
    email: Optional[str] = None,
    contact_name: Optional[str] = None,
    region: Optional[str] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    notes: Optional[str] = None,
    *,
    execution_capabilities: Optional[str] = None,
    supported_requirement_codes: Optional[List[str]] = None,
    pending_admin_review: bool = False,
    service_regions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Landlord adds a contractor: source_type=landlord_added, org-private. Optional pending_admin_review for portal clients."""
    name = contact_name or company_name
    if pending_admin_review:
        eff_status = LC_PENDING_APPROVAL
        eff_vetting = "pending_admin_review"
        gov = "Governance: pending admin review (client portal job flow)."
    else:
        eff_status = LC_APPROVED
        eff_vetting = "not_vetted"
        gov = ""
    note_parts = [p for p in (gov, (notes or "").strip()) if p]
    combined_notes = " ".join(note_parts) if note_parts else None
    return await create_contractor(
        name=name,
        company_name=company_name,
        trade_types=trade_types,
        vetted=False,
        phone=phone,
        email=email,
        client_id=client_id,
        areas_served=areas_served,
        notes=combined_notes,
        source_type=SOURCE_LANDLORD_ADDED,
        status=eff_status,
        credentials=credentials,
        insurance_details=insurance_details,
        contact_name=contact_name,
        region=region,
        portal_access_status=PORTAL_ACCESS_NOT_INVITED,
        vetting_status=eff_vetting,
        coverage_area=areas_served,
        execution_capabilities=execution_capabilities,
        supported_requirement_codes=supported_requirement_codes,
        service_regions=service_regions,
    )


async def create_contractor_client_supplied_personal(
    client_id: str,
    name: str,
    email: str,
    trade_types: List[str],
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    execution_capabilities: Optional[str] = None,
    supported_requirement_codes: Optional[List[str]] = None,
    credentials: Optional[List[str]] = None,
    region: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    extra_notes: Optional[str] = None,
    *,
    pending_admin_review: bool = False,
    service_regions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Client-added contractor for assignment without prior portal onboarding.
    Distinct from vetted network contractors; visible only to owning client.
    """
    norm = normalize_email_for_lookup(email)
    if not norm:
        raise ValueError("email is required")
    existing = await get_contractor_by_email_normalized(norm)
    if existing:
        if str(existing.get("client_id") or "").strip() != str(client_id).strip():
            raise ValueError("This email is already used by another contractor record")
        if (existing.get("source_type") or "").strip().lower() != SOURCE_CLIENT_SUPPLIED_PERSONAL:
            raise ValueError("This email is already linked to a non-personal contractor")
        return existing
    display = (name or "").strip() or norm.split("@")[0]
    db = database.get_db()
    name_key = display.casefold()
    if name_key:
        c2 = db.contractors.find(
            {
                "client_id": str(client_id).strip(),
                "source_type": SOURCE_CLIENT_SUPPLIED_PERSONAL,
            },
            {"_id": 0, "email": 1, "name": 1},
        )
        async for row in c2:
            if (str(row.get("name") or "").strip().casefold() == name_key) and normalize_email_for_lookup(
                row.get("email")
            ) != norm:
                raise ValueError(
                    "A personal contractor with this name already exists for your organisation (different email). "
                    "Pick the existing contact from search or use a distinct name."
                )
    lifecycle = LC_PENDING_APPROVAL if pending_admin_review else LC_APPROVED
    vetting = "pending_admin_review" if pending_admin_review else "client_supplied_unvetted"
    note = (
        "Created from client portal job assign flow; pending admin review before network visibility."
        if pending_admin_review
        else "Created from client portal as personal/external contractor for assignment."
    )
    if extra_notes and str(extra_notes).strip():
        note = f"{note} {str(extra_notes).strip()}".strip()
    return await create_contractor(
        name=display,
        company_name=(company_name or "").strip() or None,
        trade_types=trade_types or ["general"],
        vetted=False,
        email=norm,
        phone=phone,
        client_id=client_id,
        source_type=SOURCE_CLIENT_SUPPLIED_PERSONAL,
        status=lifecycle,
        portal_access_status=PORTAL_ACCESS_NOT_INVITED,
        vetting_status=vetting,
        notes=note,
        credentials=credentials,
        region=(region or "").strip() or None,
        areas_served=areas_served,
        insurance_details=(insurance_details or "").strip() or None,
        coverage_area=areas_served,
        execution_capabilities=execution_capabilities,
        supported_requirement_codes=supported_requirement_codes,
        service_regions=service_regions,
    )


async def create_contractor_for_client_job_portal(
    *,
    client_id: str,
    portal_user_role_upper: str,
    company_name: str,
    trade_types: List[str],
    phone: Optional[str],
    email: Optional[str],
    contact_name: Optional[str] = None,
    region: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    accreditation_certification: Optional[str] = None,
    notes: Optional[str] = None,
    work_order: Optional[Dict[str, Any]] = None,
    service_regions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Single implementation for client job UI contractor creation (POST /api/contractors and legacy assign route).

    - ROLE_CLIENT + email: client_supplied_personal (email dedupe, optional pending_admin_review).
    - ROLE_CLIENT + phone-only: landlord_added with pending_admin_review.
    - Other roles: landlord_added approved (org admin / elevated portal users).
    Compliance execution stamps come from work_order when kind is COMPLIANCE.
    """
    role_u = (portal_user_role_upper or "").strip().upper()
    pending_client = role_u == "ROLE_CLIENT"
    creds = [c.strip() for c in (credentials or []) if c and str(c).strip()]
    if accreditation_certification and str(accreditation_certification).strip():
        creds.append(str(accreditation_certification).strip())

    exec_cap: Optional[str] = None
    sup_codes: Optional[List[str]] = None
    if work_order and (work_order.get("work_order_kind") or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE:
        exec_cap = EXECUTION_CAPABILITY_COMPLIANCE
        raw_code = (work_order.get("requirement_code") or "").strip()
        if raw_code:
            norm = normalize_requirement_code(raw_code)
            if norm and norm in CANONICAL_REQUIREMENT_CODES:
                sup_codes = [norm]

    merged_sr = _merged_service_regions_for_create(service_regions, region)
    if not merged_sr and work_order and (work_order.get("work_order_kind") or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE:
        db = database.get_db()
        jl = await resolve_effective_work_order_jurisdiction(db, work_order, client_id)
        if jl:
            merged_sr = [jl]

    email_stripped = (email or "").strip()
    phone_stripped = (phone or "").strip()
    if email_stripped:
        if pending_client:
            display = (contact_name or "").strip() or (company_name or "").strip() or email_stripped.split("@")[0]
            return await create_contractor_client_supplied_personal(
                client_id=client_id,
                name=display,
                email=email_stripped,
                trade_types=trade_types or ["general"],
                phone=phone_stripped or None,
                company_name=(company_name or "").strip() or None,
                execution_capabilities=exec_cap,
                supported_requirement_codes=sup_codes,
                credentials=creds or None,
                region=(region or "").strip() or None,
                areas_served=areas_served,
                insurance_details=(insurance_details or "").strip() or None,
                extra_notes=(notes or "").strip() or None,
                pending_admin_review=True,
                service_regions=merged_sr,
            )
        return await create_contractor_landlord(
            client_id=client_id,
            company_name=(company_name or "").strip(),
            trade_types=trade_types or ["general"],
            phone=phone_stripped or None,
            email=email_stripped,
            contact_name=(contact_name or "").strip() or None,
            region=(region or "").strip() or None,
            credentials=creds or None,
            insurance_details=(insurance_details or "").strip() or None,
            areas_served=areas_served,
            notes=(notes or "").strip() or None,
            execution_capabilities=exec_cap,
            supported_requirement_codes=sup_codes,
            pending_admin_review=False,
            service_regions=merged_sr,
        )
    if not phone_stripped:
        raise ValueError("email or phone is required")
    return await create_contractor_landlord(
        client_id=client_id,
        company_name=(company_name or "").strip(),
        trade_types=trade_types or ["general"],
        phone=phone_stripped,
        email=None,
        contact_name=(contact_name or "").strip() or None,
        region=(region or "").strip() or None,
        credentials=creds or None,
        insurance_details=(insurance_details or "").strip() or None,
        areas_served=areas_served,
        notes=(notes or "").strip() or None,
        execution_capabilities=exec_cap,
        supported_requirement_codes=sup_codes,
        pending_admin_review=pending_client,
        service_regions=merged_sr,
    )


async def create_contractor_network(
    company_name: str,
    trade_types: List[str],
    phone: Optional[str] = None,
    email: Optional[str] = None,
    region: Optional[str] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    contact_name: Optional[str] = None,
    notes: Optional[str] = None,
    skip_email_duplicate_check: bool = False,
    service_regions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Admin adds to platform network: client_id=null, vetted=True, status=approved, source_type=platform_network."""
    name = contact_name or company_name
    return await create_contractor(
        name=name,
        company_name=company_name,
        trade_types=trade_types,
        vetted=True,
        phone=phone,
        email=email,
        client_id=None,
        areas_served=areas_served,
        notes=notes,
        source_type=SOURCE_PLATFORM_NETWORK,
        status=LC_APPROVED,
        credentials=credentials,
        insurance_details=insurance_details,
        contact_name=contact_name,
        region=region,
        portal_access_status=PORTAL_ACCESS_NOT_INVITED,
        vetting_status="approved",
        coverage_area=areas_served,
        skip_email_duplicate_check=skip_email_duplicate_check,
        service_regions=service_regions,
    )


async def create_contractor_self_registered(
    company_name: str,
    contact_name: str,
    trade_types: List[str],
    phone: Optional[str] = None,
    email: Optional[str] = None,
    coverage_regions: Optional[List[str]] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    declared_execution_capabilities: Optional[str] = None,
    declared_supported_requirement_codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Self-registration: client_id=null, vetted=False, status=pending_approval, source_type=self_registered."""
    creds = list(credentials) if credentials else []
    decl_exec = declared_execution_capabilities or EXECUTION_CAPABILITY_MAINTENANCE
    decl_codes = declared_supported_requirement_codes if declared_supported_requirement_codes is not None else []
    return await create_contractor(
        name=contact_name,
        company_name=company_name,
        trade_types=trade_types,
        vetted=False,
        phone=phone,
        email=email,
        client_id=None,
        areas_served=coverage_regions,
        notes=None,
        source_type=SOURCE_SELF_REGISTERED,
        status=LC_PENDING_APPROVAL,
        credentials=creds,
        insurance_details=insurance_details,
        contact_name=contact_name,
        region=coverage_regions[0] if coverage_regions else None,
        portal_access_status=PORTAL_ACCESS_NOT_INVITED,
        vetting_status=LC_PENDING_APPROVAL,
        coverage_area=coverage_regions,
        execution_capabilities=EXECUTION_CAPABILITY_MAINTENANCE,
        supported_requirement_codes=[],
        declared_execution_capabilities=decl_exec,
        declared_supported_requirement_codes=decl_codes,
        declared_credentials=creds,
    )


def _contractor_invite_email_html(setup_url: str, portal_login_url: str, include_next_steps: bool) -> str:
    parts = [
        "<p>You have been invited to the Pleerity contractor portal.</p>",
        f'<p><a href="{setup_url}">Set your password</a> (required before first login).</p>',
        f'<p>After setting your password, sign in here: <a href="{portal_login_url}">Contractor portal sign-in</a> (also reachable from Portal login on the website).</p>',
    ]
    if include_next_steps:
        parts.append(
            "<p><strong>What happens next:</strong> once your account is active, you will receive work order "
            "assignments by email and can view and update jobs in the portal.</p>"
        )
    parts.append("<p>This link expires in 24 hours. If it expires, ask your administrator to resend the invite.</p>")
    return "".join(parts)


async def record_contractor_job_invite_sent(contractor_id: str, work_order_id: str) -> None:
    """Persist landlord/job assignment email truth for admin and landlord UI."""
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    await update_contractor(
        contractor_id,
        job_invite_sent_at=now_iso,
        job_invite_last_work_order_id=(work_order_id or "").strip() or None,
    )


async def ensure_portal_invite_for_job_assignment(
    contractor_id: str,
    *,
    actor_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    return_job_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    When a contractor is assigned via the client portal, issue a portal setup invite if they
    are not yet activated. Job assignment email alone does not activate the contractor profile.
    """
    doc = await get_contractor(contractor_id)
    if not doc:
        return None
    if contractor_is_job_link_active(doc) and portal_access_is_activated(doc):
        return None
    if (doc.get("portal_access_status") or "").strip().lower() == PORTAL_ACCESS_DISABLED:
        return None
    if not (doc.get("email") or "").strip():
        logger.warning(
            "Skipping portal invite for contractor %s (assignment %s): no email",
            contractor_id,
            work_order_id or "-",
        )
        return None
    portal = (doc.get("portal_access_status") or "").strip().lower()
    resend = portal in (PORTAL_ACCESS_INVITE_PENDING, PORTAL_ACCESS_ENABLED)
    try:
        return await issue_contractor_portal_invite(
            contractor_id,
            actor_id=actor_id,
            actor_role="system_assignment",
            resend=resend,
            include_next_steps=True,
            return_job_token=return_job_token,
        )
    except ValueError as e:
        logger.warning(
            "Portal invite skipped for contractor %s after assignment %s: %s",
            contractor_id,
            work_order_id or "-",
            e,
        )
        return None


async def issue_contractor_portal_invite(
    contractor_id: str,
    *,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    resend: bool = False,
    include_next_steps: bool = False,
    return_job_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a single active contractor_invite token (revokes unused siblings), update contractor invite fields, send email.
    Raises ValueError for missing email, disabled portal, or existing active portal account.
    """
    from auth import generate_secure_token, hash_token
    from utils.public_app_url import get_frontend_base_url
    from utils.audit import create_audit_log
    from models import AuditAction
    from services.contractor_portal_auth_service import get_account_by_contractor_id

    doc = await get_contractor(contractor_id)
    if not doc:
        raise ValueError("Contractor not found")
    if (doc.get("portal_access_status") or "").strip().lower() == PORTAL_ACCESS_DISABLED:
        raise ValueError("Contractor portal access is disabled")
    email = (doc.get("email") or "").strip()
    if not email:
        raise ValueError("Contractor has no email; add one before sending a portal invite")
    existing = await get_account_by_contractor_id(contractor_id)
    if existing and (existing.get("status") or "").lower() == "active":
        raise ValueError("Contractor already has an active portal account")

    db = database.get_db()
    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)
    now_iso = now.isoformat()
    await db.password_tokens.update_many(
        {
            "purpose": "contractor_invite",
            "metadata.contractor_id": contractor_id,
            "used": {"$ne": True},
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now_iso, "revoked_reason": "invite_replaced"}},
    )
    await db.password_tokens.insert_one({
        "token_hash": token_hash,
        "purpose": "contractor_invite",
        "metadata": {"contractor_id": contractor_id, "email": email},
        "expires_at": expires_at,
        "used": False,
        "revoked_at": None,
        "created_at": now_iso,
    })
    await update_contractor(
        contractor_id,
        portal_access_status=PORTAL_ACCESS_INVITE_PENDING,
        portal_invite_sent_at=now_iso,
        portal_invite_expires_at=expires_at.isoformat(),
        portal_invite_last_token_id=token_hash,
    )
    base_url = get_frontend_base_url().rstrip("/")
    setup_url = f"{base_url}/contractor-set-password?token={raw_token}"
    job_tok = (return_job_token or "").strip()
    if job_tok:
        from urllib.parse import quote

        setup_url = f"{setup_url}&return_to={quote(f'/job?token={job_tok}', safe='')}"
    portal_login_url = f"{base_url}/contractor/login"
    body_html = _contractor_invite_email_html(setup_url, portal_login_url, include_next_steps=include_next_steps)
    try:
        from services.notification_orchestrator import notification_orchestrator

        await notification_orchestrator.send(
            template_key="ADMIN_MANUAL",
            client_id=None,
            context={
                "recipient": email,
                "subject": "Pleerity contractor portal — set your password",
                "message": body_html,
                "company_name": "Pleerity Enterprise Ltd",
            },
            idempotency_key=f"contractor_invite_{contractor_id}_{now.timestamp()}",
            event_type="contractor_portal_invite",
        )
    except Exception as e:
        logger.warning("Contractor invite email send failed: %s", e)
    try:
        await create_audit_log(
            action=AuditAction.CONTRACTOR_INVITE_RESENT if resend else AuditAction.CONTRACTOR_INVITE_SENT,
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type="contractor",
            resource_id=contractor_id,
            metadata={"email": email, "expires_at": expires_at.isoformat(), "triggered_by": "admin" if actor_id else "system"},
        )
    except Exception as e:
        logger.warning("Audit log for contractor invite failed: %s", e)
    return {
        "ok": True,
        "setup_url": setup_url,
        "expires_at": expires_at.isoformat(),
        "portal_access_status": PORTAL_ACCESS_INVITE_PENDING,
    }


async def invite_contractor_by_admin(
    *,
    email: str,
    name: Optional[str] = None,
    trade_types: Optional[List[str]] = None,
    phone: Optional[str] = None,
    client_id: Optional[str] = None,
    property_scope: Optional[List[str]] = None,
    vetted: Optional[bool] = None,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
) -> Dict[str, Any]:
    """Admin invite flow: create or update contractor, issue portal invite token and email."""
    norm = normalize_email_for_lookup(email)
    if not norm:
        raise ValueError("email is required")
    existing = await get_contractor_by_email_normalized(norm)
    if existing:
        st = normalize_lifecycle_status(existing.get("status"))
        if st == LC_ACTIVE and portal_access_is_activated(existing) and existing.get("vetted"):
            raise ValueError("Contractor is already active on the portal; use resend only if they lost the link")
        contractor_id = existing["contractor_id"]
        patch: Dict[str, Any] = {}
        if name is not None and name.strip():
            patch["name"] = name.strip()
        if trade_types is not None:
            patch["trade_types"] = trade_types
        if phone is not None:
            patch["phone"] = phone
        if client_id is not None:
            patch["client_id"] = client_id
        if property_scope is not None:
            patch["property_scope"] = property_scope
        if vetted is not None:
            patch["vetted"] = vetted
        if patch:
            await update_contractor(contractor_id, **patch)
        invite = await issue_contractor_portal_invite(
            contractor_id,
            actor_id=actor_id,
            actor_role=actor_role,
            resend=True,
            include_next_steps=False,
        )
        out = await get_contractor(contractor_id)
        return {"contractor": out, "invite": invite, "created": False}
    display_name = (name or "").strip() or norm.split("@")[0]
    eff_vetted = False if vetted is None else bool(vetted)
    created = await create_contractor(
        name=display_name,
        trade_types=trade_types or [],
        vetted=eff_vetted,
        email=norm,
        phone=phone,
        client_id=client_id,
        source_type=SOURCE_PLATFORM_NETWORK if not client_id else SOURCE_LANDLORD_ADDED,
        status=LC_INVITED,
        portal_access_status=PORTAL_ACCESS_NOT_INVITED,
        property_scope=property_scope,
    )
    contractor_id = created["contractor_id"]
    invite = await issue_contractor_portal_invite(
        contractor_id,
        actor_id=actor_id,
        actor_role=actor_role,
        resend=False,
        include_next_steps=False,
    )
    return {"contractor": await get_contractor(contractor_id), "invite": invite, "created": True}


async def register_contractor_public(
    *,
    name: str,
    email: str,
    phone: Optional[str],
    trade_types: List[str],
    registration_postcode: str,
    certifications: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    declared_execution_capabilities: Optional[str] = None,
    declared_supported_requirement_codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Public self-registration: pending approval, notify admin, acknowledgment email to applicant."""
    norm = normalize_email_for_lookup(email)
    pc = (registration_postcode or "").strip()
    if not norm:
        raise ValueError("email is required")
    if not pc:
        raise ValueError("location (postcode) is required")
    existing = await get_contractor_by_email_normalized(norm)
    if existing:
        raise ValueError("An application or account already exists for this email")
    creds = list(certifications) if certifications else []
    doc = await create_contractor_self_registered(
        company_name=name.strip(),
        contact_name=name.strip(),
        trade_types=trade_types,
        phone=phone,
        email=norm,
        coverage_regions=[pc.upper()],
        credentials=creds,
        insurance_details=(insurance_details or "").strip() or None,
        declared_execution_capabilities=declared_execution_capabilities,
        declared_supported_requirement_codes=declared_supported_requirement_codes,
    )
    doc = await update_contractor(
        doc["contractor_id"],
        registration_postcode=pc.upper(),
        status=LC_PENDING_APPROVAL,
        vetting_status=LC_PENDING_APPROVAL,
    )
    assert doc is not None
    try:
        from utils.submission_utils import notify_admin_new_submission

        await notify_admin_new_submission(
            "contractor_registration",
            doc["contractor_id"],
            f"{name.strip()} &lt;{norm}&gt; — pending contractor approval",
            detail_url_path=f"/admin/ops/contractors/{doc['contractor_id']}",
        )
    except Exception as e:
        logger.warning("Admin notify for contractor registration failed: %s", e)
    try:
        from utils.audit import create_audit_log
        from models import AuditAction

        await create_audit_log(
            action=AuditAction.CONTRACTOR_REGISTERED_PUBLIC,
            actor_id="system",
            resource_type="contractor",
            resource_id=doc["contractor_id"],
            metadata={"email": norm, "triggered_by": "public_self_register"},
        )
    except Exception as e:
        logger.warning("Audit log for contractor self-register failed: %s", e)
    try:
        import html as html_module

        from services.notification_orchestrator import notification_orchestrator
        from utils.public_app_url import get_frontend_base_url

        portal_login = f"{get_frontend_base_url().rstrip('/')}/login"
        safe_name = html_module.escape(name.strip())
        ack_html = (
            f"<p>Hi {safe_name},</p>"
            "<p>Thank you for applying to join the Pleerity contractor network. We have received your application.</p>"
            "<p><strong>What happens next:</strong> our team will review your details. If you are approved, you will receive "
            "a separate email with a secure link to set your password and activate your contractor portal account.</p>"
            f'<p>For all secure sign-in options (including contractor access after activation), use '
            f'<a href="{portal_login}">Portal login</a> on our website.</p>'
        )
        await notification_orchestrator.send(
            template_key="ADMIN_MANUAL",
            client_id=None,
            context={
                "recipient": norm,
                "subject": "We received your contractor network application",
                "message": ack_html,
                "company_name": "Pleerity Enterprise Ltd",
            },
            idempotency_key=f"contractor_register_ack_{doc['contractor_id']}",
            event_type="contractor_registration_ack",
        )
    except Exception as e:
        logger.warning("Contractor application acknowledgment email failed: %s", e)
    return {"ok": True, "contractor_id": doc["contractor_id"], "status": LC_PENDING_APPROVAL}


async def validate_contractor_for_work_order_assignment(
    contractor_id: str,
    client_id: str,
    work_order_id: str,
    *,
    assignment_profile: str = "standard",
) -> None:
    """Raise ValueError if contractor cannot be assigned to this work order."""
    db = database.get_db()
    contractor = await db.contractors.find_one({"contractor_id": contractor_id})
    if not contractor:
        raise ValueError("Contractor not found")
    contractor_s = _sanitize_doc(contractor)
    if assignment_profile == "client_supplied_personal":
        st = normalize_lifecycle_status(contractor_s.get("status"))
        if st in (LC_SUSPENDED, "suspended"):
            raise ValueError("Contractor is suspended")
        if st == LC_ARCHIVED:
            raise ValueError("Contractor is archived")
        if (contractor_s.get("source_type") or "").strip().lower() != SOURCE_CLIENT_SUPPLIED_PERSONAL:
            raise ValueError("Not a client-supplied personal contractor record")
        if str(contractor_s.get("client_id") or "").strip() != str(client_id).strip():
            raise ValueError("Personal contractor is not linked to your organisation")
        email = (contractor_s.get("email") or "").strip()
        if not email:
            raise ValueError("Personal contractor must have an email before assignment")
        wo = await db.work_orders.find_one(
            {"work_order_id": work_order_id},
            {
                "_id": 0,
                "client_id": 1,
                "property_id": 1,
                "jurisdiction": 1,
                "linked_property_requirement_id": 1,
            },
        )
        if not wo or (wo.get("client_id") or "").strip() != (client_id or "").strip():
            raise ValueError("Work order not found for this client")
        await _assert_contractor_jurisdiction_for_assignment(db, contractor_s, wo, client_id)
        return
    if assignment_profile == ASSIGNMENT_PROFILE_CLIENT_PORTAL_LANDLORD:
        st = normalize_lifecycle_status(contractor_s.get("status"))
        if st in (LC_SUSPENDED, "suspended"):
            raise ValueError("Contractor is suspended")
        if st == LC_ARCHIVED:
            raise ValueError("Contractor is archived")
        if (contractor_s.get("source_type") or "").strip().lower() != SOURCE_LANDLORD_ADDED:
            raise ValueError("Not an organisation directory contractor record")
        if str(contractor_s.get("client_id") or "").strip() != str(client_id).strip():
            raise ValueError("Contractor is not linked to your organisation")
        wo = await db.work_orders.find_one(
            {"work_order_id": work_order_id},
            {
                "_id": 0,
                "client_id": 1,
                "property_id": 1,
                "category": 1,
                "work_order_kind": 1,
                "requirement_code": 1,
                "jurisdiction": 1,
                "linked_property_requirement_id": 1,
            },
        )
        if not wo or (wo.get("client_id") or "").strip() != (client_id or "").strip():
            raise ValueError("Work order not found for this client")
        if not contractor_client_link_allows(contractor_s, client_id):
            raise ValueError("Contractor is scoped to a different client")
        if not contractor_property_scope_allows(contractor_s, wo.get("property_id")):
            raise ValueError("Contractor is not scoped to this property")
        if not contractor_passes_work_order_execution_gate(contractor_s, wo):
            raise ValueError(
                "Contractor execution capabilities do not match this work order "
                "(maintenance repair vs compliance inspection/renewal)"
            )
        prop_pc = None
        if wo.get("property_id"):
            prop = await db.properties.find_one(
                {"property_id": wo["property_id"], "client_id": client_id},
                {"_id": 0, "postcode": 1},
            )
            prop_pc = (prop or {}).get("postcode")
        job_j = await resolve_effective_work_order_jurisdiction(db, wo, client_id)
        if not contractor_location_matches_property(contractor_s, prop_pc, property_jurisdiction=job_j):
            raise ValueError("Contractor location does not match the property postcode")
        kind = (wo.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
        if kind == WORK_ORDER_KIND_MAINTENANCE:
            if not contractor_trade_matches_category(contractor_s, wo.get("category")):
                raise ValueError("Contractor trade types do not match this maintenance work order category")
        await _assert_contractor_jurisdiction_for_assignment(db, contractor_s, wo, client_id)
        return
    ok, reason = contractor_is_assignable(contractor_s)
    if not ok:
        raise ValueError(reason)
    vis = await contractor_visible_to_client(contractor_id, client_id)
    if not vis:
        raise ValueError("Contractor is not available to your organisation")
    wo = await db.work_orders.find_one(
        {"work_order_id": work_order_id},
        {
            "_id": 0,
            "client_id": 1,
            "property_id": 1,
            "category": 1,
            "work_order_kind": 1,
            "requirement_code": 1,
            "jurisdiction": 1,
            "linked_property_requirement_id": 1,
        },
    )
    if not wo or (wo.get("client_id") or "").strip() != (client_id or "").strip():
        raise ValueError("Work order not found for this client")
    if not contractor_client_link_allows(contractor_s, client_id):
        raise ValueError("Contractor is scoped to a different client")
    if not contractor_property_scope_allows(contractor_s, wo.get("property_id")):
        raise ValueError("Contractor is not scoped to this property")
    if not contractor_passes_work_order_execution_gate(contractor_s, wo):
        raise ValueError(
            "Contractor execution capabilities do not match this work order "
            "(maintenance repair vs compliance inspection/renewal)"
        )
    prop_pc = None
    if wo.get("property_id"):
        prop = await db.properties.find_one(
            {"property_id": wo["property_id"], "client_id": client_id},
            {"_id": 0, "postcode": 1},
        )
        prop_pc = (prop or {}).get("postcode")
    job_j = await resolve_effective_work_order_jurisdiction(db, wo, client_id)
    if not contractor_location_matches_property(contractor_s, prop_pc, property_jurisdiction=job_j):
        raise ValueError("Contractor location does not match the property postcode")
    kind = (wo.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
    if kind == WORK_ORDER_KIND_MAINTENANCE:
        if not contractor_trade_matches_category(contractor_s, wo.get("category")):
            raise ValueError("Contractor trade types do not match this maintenance work order category")
    await _assert_contractor_jurisdiction_for_assignment(db, contractor_s, wo, client_id)


async def list_assignable_contractors_for_work_order(
    client_id: str,
    work_order_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """Contractors visible to the client who pass assignment readiness and work-order filters."""
    db = database.get_db()
    wo = await db.work_orders.find_one(
        {"work_order_id": work_order_id},
        {
            "_id": 0,
            "client_id": 1,
            "property_id": 1,
            "category": 1,
            "work_order_kind": 1,
            "requirement_code": 1,
            "jurisdiction": 1,
            "linked_property_requirement_id": 1,
        },
    )
    if not wo or wo.get("client_id") != client_id:
        empty_diag = {
            "visible_in_directory": 0,
            "excluded_not_assignment_ready": 0,
            "excluded_wrong_client_scope": 0,
            "excluded_property_scope": 0,
            "excluded_location_postcode": 0,
            "excluded_execution_capability": 0,
            "excluded_maintenance_trade": 0,
            "excluded_service_region_jurisdiction": 0,
            "eligible": 0,
        }
        return {
            "contractors": [],
            "total": 0,
            "skip": skip,
            "limit": limit,
            "job_jurisdiction": None,
            "filter_diagnostics": empty_diag,
            "exclusion_samples": {},
            "recovery_guidance": build_assignment_eligibility_recovery(empty_diag, eligible=0),
        }
    job_jurisdiction = await resolve_effective_work_order_jurisdiction(db, wo, client_id)
    prop_pc = None
    if wo.get("property_id"):
        prop = await db.properties.find_one(
            {"property_id": wo["property_id"], "client_id": client_id},
            {"_id": 0, "postcode": 1},
        )
        prop_pc = (prop or {}).get("postcode")
    q = _visibility_query(client_id)
    cursor = db.contractors.find(q).sort("name", 1)
    all_rows = await cursor.to_list(500)
    matched: List[Dict[str, Any]] = []
    diag = {
        "visible_in_directory": len(all_rows),
        "excluded_not_assignment_ready": 0,
        "excluded_wrong_client_scope": 0,
        "excluded_property_scope": 0,
        "excluded_location_postcode": 0,
        "excluded_execution_capability": 0,
        "excluded_maintenance_trade": 0,
        "excluded_service_region_jurisdiction": 0,
        "eligible": 0,
    }
    exclusion_samples: Dict[str, List[Dict[str, Any]]] = {
        "excluded_not_assignment_ready": [],
        "excluded_wrong_client_scope": [],
        "excluded_property_scope": [],
        "excluded_location_postcode": [],
        "excluded_execution_capability": [],
        "excluded_maintenance_trade": [],
        "excluded_service_region_jurisdiction": [],
    }

    def _record_exclusion(reason_key: str, contractor_row: Dict[str, Any]) -> None:
        diag[reason_key] += 1
        bucket = exclusion_samples[reason_key]
        if len(bucket) < EXCLUSION_SAMPLE_LIMIT:
            bucket.append(contractor_exclusion_sample(contractor_row))

    for raw in all_rows:
        c = _sanitize_doc(raw)
        ok, _ = contractor_is_assignable(c)
        if not ok:
            _record_exclusion("excluded_not_assignment_ready", c)
            continue
        if not contractor_client_link_allows(c, client_id):
            _record_exclusion("excluded_wrong_client_scope", c)
            continue
        if not contractor_property_scope_allows(c, wo.get("property_id")):
            _record_exclusion("excluded_property_scope", c)
            continue
        if not contractor_location_matches_property(c, prop_pc, property_jurisdiction=job_jurisdiction):
            _record_exclusion("excluded_location_postcode", c)
            continue
        if not contractor_passes_work_order_execution_gate(c, wo):
            _record_exclusion("excluded_execution_capability", c)
            continue
        kind = (wo.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
        if kind == WORK_ORDER_KIND_MAINTENANCE:
            if not contractor_trade_matches_category(c, wo.get("category")):
                _record_exclusion("excluded_maintenance_trade", c)
                continue
        if not contractor_service_regions_allow_jurisdiction(c, job_jurisdiction):
            _record_exclusion("excluded_service_region_jurisdiction", c)
            continue
        matched.append(c)
    total = len(matched)
    diag["eligible"] = total
    page = matched[skip : skip + limit]
    recovery_guidance = build_assignment_eligibility_recovery(
        diag,
        job_jurisdiction=job_jurisdiction,
        property_postcode=prop_pc,
        eligible=total,
    )
    return {
        "contractors": page,
        "total": total,
        "skip": skip,
        "limit": limit,
        "job_jurisdiction": job_jurisdiction,
        "property_postcode": prop_pc,
        "filter_diagnostics": diag,
        "exclusion_samples": exclusion_samples,
        "recovery_guidance": recovery_guidance,
    }


async def approve_contractor(
    contractor_id: str,
    *,
    approved_by: Optional[str] = None,
    approved_by_role: Optional[str] = None,
    verified_execution_capabilities: Optional[str] = None,
    verified_supported_requirement_codes: Optional[List[str]] = None,
    accept_declared_capabilities: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Approve a contractor for operations: vetted=True, status active if portal already activated else approved,
    and send portal invite when needed. Optional verified_* (or accept_declared_capabilities) records trusted
    compliance capability for routing; omitting them leaves verified layer unchanged (e.g. self-reg stays
    maintenance-only in legacy fields until admin sets verified compliance).
    """
    from utils.audit import create_audit_log
    from models import AuditAction

    db = database.get_db()
    raw = await db.contractors.find_one({"contractor_id": contractor_id})
    if not raw:
        return None
    cur = _sanitize_doc(raw)
    portal_on = portal_access_is_activated(cur)
    new_status = LC_ACTIVE if portal_on else LC_APPROVED
    patch_kw: Dict[str, Any] = {
        "contractor_id": contractor_id,
        "status": new_status,
        "vetted": True,
        "vetting_status": "approved",
    }
    if accept_declared_capabilities:
        de = cur.get("declared_execution_capabilities") or EXECUTION_CAPABILITY_MAINTENANCE
        patch_kw["verified_execution_capabilities"] = _coerce_execution_capabilities(str(de))
        patch_kw["verified_supported_requirement_codes"] = _coerce_supported_requirement_codes(
            cur.get("declared_supported_requirement_codes") or []
        )
        patch_kw["verified_by"] = approved_by or "admin_accept_declared"
    else:
        if verified_execution_capabilities is not None:
            patch_kw["verified_execution_capabilities"] = verified_execution_capabilities
        if verified_supported_requirement_codes is not None:
            patch_kw["verified_supported_requirement_codes"] = verified_supported_requirement_codes
        if verified_execution_capabilities is not None or verified_supported_requirement_codes is not None:
            patch_kw["verified_by"] = approved_by or "admin"
        else:
            st = (cur.get("source_type") or "").strip().lower()
            if st != SOURCE_SELF_REGISTERED and "verified_execution_capabilities" not in raw:
                le = cur.get("execution_capabilities")
                if le is not None and str(le).strip():
                    patch_kw["verified_execution_capabilities"] = le
                lsup = cur.get("supported_requirement_codes")
                if lsup is not None:
                    patch_kw["verified_supported_requirement_codes"] = list(lsup)
                if "verified_execution_capabilities" in patch_kw or "verified_supported_requirement_codes" in patch_kw:
                    patch_kw["verified_by"] = approved_by or "legacy_mirror_on_approve"
    updated = await update_contractor(**patch_kw)
    if not updated:
        return None
    try:
        await create_audit_log(
            action=AuditAction.CONTRACTOR_LIFECYCLE_APPROVED,
            actor_id=approved_by,
            actor_role=approved_by_role,
            resource_type="contractor",
            resource_id=contractor_id,
            metadata={"triggered_by": "admin", "portal_already_activated": portal_on},
        )
    except Exception as e:
        logger.warning("Audit log for contractor approve failed: %s", e)
    if not portal_on:
        try:
            await issue_contractor_portal_invite(
                contractor_id,
                actor_id=approved_by,
                actor_role=approved_by_role,
                resend=False,
                include_next_steps=True,
            )
        except ValueError as e:
            logger.warning("Could not send onboarding invite after approval: %s", e)
    return await get_contractor(contractor_id)


def _property_label_for_assigned_job(prop: Optional[Dict[str, Any]]) -> Optional[str]:
    """Human-readable property line for admin/ops lists (matches contractor portal pattern)."""
    if not prop:
        return None
    nick = (prop.get("nickname") or "").strip()
    if nick:
        return nick
    parts = [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")]
    joined = ", ".join(p for p in parts if p)
    return joined or None


async def list_assigned_jobs(contractor_id: str, include_closed: bool = False, limit: int = 200) -> Dict[str, Any]:
    """List jobs currently assigned to the contractor, with optional closed/completed rows."""
    db = database.get_db()
    q: Dict[str, Any] = {"contractor_id": contractor_id}
    if not include_closed:
        q["status"] = {"$nin": ["COMPLETED", "CANCELLED", "CLOSED", "VERIFIED"]}
    rows = await db.work_orders.find(
        q,
        {"_id": 0, "work_order_id": 1, "client_id": 1, "property_id": 1, "status": 1, "priority": 1, "title": 1, "description": 1, "created_at": 1, "updated_at": 1},
    ).sort("created_at", -1).to_list(limit)
    prop_ids = list({r.get("property_id") for r in rows if r.get("property_id")})
    props_by_id: Dict[str, Any] = {}
    if prop_ids:
        async for p in db.properties.find(
            {"property_id": {"$in": prop_ids}},
            {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1, "nickname": 1},
        ):
            props_by_id[p["property_id"]] = p
    for r in rows:
        pid = r.get("property_id")
        r["property_label"] = _property_label_for_assigned_job(props_by_id.get(pid)) if pid else None
    return {"jobs": rows, "total": len(rows)}


async def disable_portal_access(contractor_id: str) -> Dict[str, Any]:
    """
    Disable contractor portal access and revoke active invite/job tokens.
    Returns revocation counts and currently assigned open jobs requiring reassignment.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    contractor = await db.contractors.find_one({"contractor_id": contractor_id}, {"_id": 0})
    if not contractor:
        return {"ok": False, "reason": "not_found"}

    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"portal_access_status": PORTAL_ACCESS_DISABLED, "updated_at": now_iso}},
    )
    account_result = await db.contractor_portal_accounts.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"status": "inactive", "updated_at": now_iso, "disabled_at": now_iso}},
    )
    invite_revoke_result = await db.password_tokens.update_many(
        {
            "purpose": "contractor_invite",
            "metadata.contractor_id": contractor_id,
            "used": {"$ne": True},
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now_iso, "revoked_reason": "portal_access_disabled"}},
    )
    job_revoke_result = await db.contractor_job_tokens.update_many(
        {
            "contractor_id": contractor_id,
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now_iso, "revoked_reason": "portal_access_disabled"}},
    )
    jobs_result = await list_assigned_jobs(contractor_id=contractor_id, include_closed=False, limit=500)
    return {
        "ok": True,
        "contractor_id": contractor_id,
        "portal_access_status": PORTAL_ACCESS_DISABLED,
        "portal_account_disabled": account_result.modified_count > 0 or account_result.matched_count > 0,
        "revoked_invite_tokens": int(invite_revoke_result.modified_count or 0),
        "revoked_job_tokens": int(job_revoke_result.modified_count or 0),
        "reassignment_required_jobs": jobs_result.get("jobs", []),
        "reassignment_required_count": jobs_result.get("total", 0),
    }


async def submit_contractor_to_network(contractor_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    """Landlord submits their private contractor for network review. Sets submitted_to_network_at. Contractor remains private until admin approves."""
    db = database.get_db()
    doc = await db.contractors.find_one({"contractor_id": contractor_id})
    if not doc:
        return None
    if doc.get("client_id") != client_id:
        return None
    if doc.get("source_type") != SOURCE_LANDLORD_ADDED:
        return None
    if doc.get("submitted_to_network_at"):
        return _sanitize_doc(doc)
    now = datetime.now(timezone.utc).isoformat()
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"submitted_to_network_at": now, "updated_at": now}},
    )
    updated = await get_contractor(contractor_id)
    try:
        from utils.submission_utils import notify_admin_new_submission

        cname = (doc.get("name") or doc.get("company_name") or contractor_id).strip()
        await notify_admin_new_submission(
            "contractor_network_submission",
            contractor_id,
            f"Client {client_id}: {cname} submitted a private contractor for platform network review.",
            detail_url_path=f"/admin/ops/contractors",
        )
    except Exception as e:
        logger.warning("Admin notify for contractor network submission failed: %s", e)
    return updated


async def approve_contractor_to_network(
    contractor_id: str,
    approved_by_admin_id: str,
) -> Optional[Dict[str, Any]]:
    """Admin approves a private contractor for the network. Creates a new platform_network contractor (copy) and marks the private record as approved. Private record is unchanged except approved_for_network_at and approved_by_admin_id."""
    db = database.get_db()
    private = await db.contractors.find_one({"contractor_id": contractor_id})
    if not private or private.get("source_type") != SOURCE_LANDLORD_ADDED or not private.get("submitted_to_network_at"):
        return None
    now = datetime.now(timezone.utc).isoformat()
    new_network = await create_contractor_network(
        company_name=private.get("company_name") or private.get("name") or "Contractor",
        trade_types=private.get("trade_types") or ["general"],
        phone=private.get("phone"),
        email=private.get("email"),
        region=private.get("region"),
        credentials=private.get("credentials"),
        insurance_details=private.get("insurance_details"),
        areas_served=private.get("areas_served"),
        contact_name=private.get("contact_name"),
        notes=private.get("notes"),
        skip_email_duplicate_check=True,
    )
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {
            "$set": {
                "approved_for_network_at": now,
                "approved_by_admin_id": approved_by_admin_id,
                "updated_at": now,
                "promoted_to_network_contractor_id": new_network.get("contractor_id"),
            },
        },
    )
    return new_network


async def reject_contractor_network_submission(
    contractor_id: str,
    reason: Optional[str] = None,
    rejected_by_admin_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Admin rejects a network submission. Sets network_submission_rejection_reason; submitted_to_network_at is left for audit."""
    db = database.get_db()
    doc = await db.contractors.find_one({"contractor_id": contractor_id})
    if not doc or doc.get("source_type") != SOURCE_LANDLORD_ADDED:
        return None
    now = datetime.now(timezone.utc).isoformat()
    update = {"updated_at": now, "network_submission_rejection_reason": reason or ""}
    if rejected_by_admin_id is not None:
        update["network_submission_rejected_by_admin_id"] = rejected_by_admin_id
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": update},
    )
    return await get_contractor(contractor_id)


async def load_price_books(client_id: Optional[str]) -> List[Dict[str, Any]]:
    """Load price_books for a client (client-specific + global). Returns list; empty if collection missing or no docs."""
    db = database.get_db()
    q = {"$or": [{"client_id": client_id}, {"client_id": None}]} if client_id else {"client_id": None}
    try:
        cursor = db.get_collection("price_books").find(q, {"_id": 0})
        return await cursor.to_list(100)
    except Exception:
        return []


_TERMINAL_WORK_ORDER_STATUSES = ("COMPLETED", "CANCELLED", "CLOSED", "VERIFIED")


async def aggregate_contractor_open_workloads(client_id: str) -> Dict[str, int]:
    """Count open (non-terminal) work orders per contractor_id for this client."""
    db = database.get_db()
    pipeline = [
        {
            "$match": {
                "client_id": client_id,
                "contractor_id": {"$nin": [None, ""]},
                "status": {"$nin": list(_TERMINAL_WORK_ORDER_STATUSES)},
            },
        },
        {"$group": {"_id": "$contractor_id", "n": {"$sum": 1}}},
    ]
    out: Dict[str, int] = {}
    try:
        async for row in db.work_orders.aggregate(pipeline):
            if row.get("_id"):
                out[str(row["_id"])] = int(row.get("n") or 0)
    except Exception as e:
        logger.warning("aggregate_contractor_open_workloads failed: %s", e)
    return out


async def aggregate_contractor_historical_sla_breaches(client_id: str) -> Dict[str, int]:
    """Count work orders with sla_breached_at set per contractor (this client), all statuses."""
    db = database.get_db()
    pipeline = [
        {
            "$match": {
                "client_id": client_id,
                "contractor_id": {"$nin": [None, ""]},
                "sla_breached_at": {"$exists": True, "$ne": None},
            },
        },
        {"$group": {"_id": "$contractor_id", "n": {"$sum": 1}}},
    ]
    out: Dict[str, int] = {}
    try:
        async for row in db.work_orders.aggregate(pipeline):
            if row.get("_id"):
                out[str(row["_id"])] = int(row.get("n") or 0)
    except Exception as e:
        logger.warning("aggregate_contractor_historical_sla_breaches failed: %s", e)
    return out


async def recommend_contractors_for_work_order(
    work_order_id: str,
    client_id: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Return suggested contractors for a work order: rule-based scoring (trade, region, credential, SLA, rating, rework). No auto-assign."""
    db = database.get_db()
    wo = await db.work_orders.find_one(
        {"work_order_id": work_order_id},
        {
            "_id": 0,
            "client_id": 1,
            "property_id": 1,
            "category": 1,
            "recommended_contractor_type": 1,
            "severity": 1,
            "work_order_id": 1,
            "sla_complete_by": 1,
            "sla_respond_by": 1,
            "sla_breach_risk_at": 1,
            "sla_breached_at": 1,
            "status": 1,
            "work_order_kind": 1,
            "requirement_code": 1,
            "compliance_purpose": 1,
            "jurisdiction": 1,
            "linked_property_requirement_id": 1,
        },
    )
    if not wo:
        from services.contractor_recommendation import compute_assignment_routing_meta
        from services.contractor_assignment_policy import get_contractor_assignment_policy

        empty_meta = compute_assignment_routing_meta({"work_order_id": work_order_id})
        pol = get_contractor_assignment_policy(client_id)
        return {
            "contractors": [],
            "total": 0,
            "work_order_id": work_order_id,
            "no_strong_match": True,
            "routing": {
                **empty_meta,
                "no_eligible_contractors": True,
                "no_strong_match": True,
                "policy": {
                    "admin_confirms_assignment": pol.get("admin_confirms_assignment_default", True),
                    "auto_assign_enabled": pol.get("auto_assign_enabled", False),
                    "auto_assign_categories": pol.get("auto_assign_categories", []),
                },
                "routing_messages": (empty_meta.get("routing_messages") or []) + ["Work order not found."],
            },
        }
    cid = client_id or wo.get("client_id")
    q = _visibility_query(cid) if cid else {"$or": [{"client_id": None}, {"status": {"$exists": False}}]}
    cursor = db.contractors.find(q)
    all_contractors = await cursor.to_list(500)
    property_doc = None
    if wo.get("property_id") and cid:
        property_doc = await db.properties.find_one(
            {"property_id": wo["property_id"], "client_id": cid},
            {"_id": 0, "postcode": 1, "region": 1},
        )
    elif wo.get("property_id"):
        property_doc = await db.properties.find_one(
            {"property_id": wo["property_id"]},
            {"_id": 0, "postcode": 1, "region": 1},
        )
    prop_pc = (property_doc or {}).get("postcode")
    eff_client = str(cid or wo.get("client_id") or "").strip()
    job_jurisdiction = (
        await resolve_effective_work_order_jurisdiction(db, wo, eff_client)
        if eff_client
        else portfolio_jurisdiction_label({}, {})
    )
    filtered_raw: List[Dict[str, Any]] = []
    for raw in all_contractors:
        c = _sanitize_doc(raw)
        ok_assign, _ = contractor_is_assignable(c)
        if not ok_assign:
            continue
        if cid and not contractor_client_link_allows(c, cid):
            continue
        if cid and not contractor_property_scope_allows(c, wo.get("property_id")):
            continue
        if not contractor_location_matches_property(c, prop_pc, property_jurisdiction=job_jurisdiction):
            continue
        if not contractor_passes_work_order_execution_gate(c, wo):
            continue
        wk = (wo.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
        if wk == WORK_ORDER_KIND_MAINTENANCE:
            if not contractor_trade_matches_category(c, wo.get("category")):
                continue
        if not contractor_service_regions_allow_jurisdiction(c, job_jurisdiction):
            continue
        filtered_raw.append(raw)
    perf_map: Dict[str, Tuple[int, int]] = {}
    if cid:
        perf_cursor = db.contractor_performance.find(
            {"client_id": cid},
            {"_id": 0, "contractor_id": 1, "jobs_completed": 1, "jobs_on_time": 1},
        )
        async for p in perf_cursor:
            j = p.get("jobs_completed") or 0
            o = p.get("jobs_on_time") or 0
            perf_map[p["contractor_id"]] = (j, o)
    price_books = await load_price_books(cid)
    from services.contractor_recommendation import compute_assignment_routing_meta, recommend_contractors as rule_recommend
    from services.contractor_assignment_policy import get_contractor_assignment_policy

    pool = filtered_raw if filtered_raw else []
    if not pool:
        pol = get_contractor_assignment_policy(cid)
        routing_meta = compute_assignment_routing_meta(wo, now_utc=datetime.now(timezone.utc))
        empty = rule_recommend(
            work_order=wo,
            property_doc=property_doc,
            contractors=[],
            performance_map={},
            price_books=price_books if price_books else None,
            workload_map={},
            breach_count_map={},
            client_id_for_preference=cid,
            routing_meta=routing_meta,
            assignment_policy=pol,
            eligible_only=True,
        )
        return empty
    workload_map: Dict[str, int] = {}
    breach_map: Dict[str, int] = {}
    if cid:
        workload_map = await aggregate_contractor_open_workloads(str(cid))
        breach_map = await aggregate_contractor_historical_sla_breaches(str(cid))
    routing_meta = compute_assignment_routing_meta(wo, now_utc=datetime.now(timezone.utc))
    policy = get_contractor_assignment_policy(str(cid) if cid else None)
    result = rule_recommend(
        work_order=wo,
        property_doc=property_doc,
        contractors=pool,
        performance_map=perf_map,
        price_books=price_books if price_books else None,
        workload_map=workload_map,
        breach_count_map=breach_map,
        client_id_for_preference=cid,
        routing_meta=routing_meta,
        assignment_policy=policy,
        eligible_only=True,
    )
    result["contractors"] = result["contractors"][:limit]
    result["total"] = len(result["contractors"])
    return result


async def create_contractor_rating(
    contractor_id: str,
    client_id: str,
    rating: int,
    work_order_id: Optional[str] = None,
    property_id: Optional[str] = None,
    completion_speed: Optional[int] = None,
    professionalism: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a rating for a contractor (e.g. after work order completion). Updates contractor.rating_average."""
    import uuid
    from datetime import datetime, timezone

    if not (1 <= rating <= 5):
        raise ValueError("rating must be between 1 and 5")
    db = database.get_db()
    contractor = await db.contractors.find_one({"contractor_id": contractor_id}, {"_id": 1})
    if not contractor:
        raise ValueError("Contractor not found")
    rating_id = f"rating_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "rating_id": rating_id,
        "contractor_id": contractor_id,
        "client_id": client_id,
        "rating": rating,
        "work_order_id": work_order_id,
        "property_id": property_id,
        "completion_speed": completion_speed,
        "professionalism": professionalism,
        "notes": (notes or "").strip()[:2000] or None,
        "created_at": now,
    }
    await db.contractor_ratings.insert_one(doc)
    await _update_contractor_rating_average(contractor_id)
    return _sanitize_doc(doc)


async def _update_contractor_rating_average(contractor_id: str) -> None:
    """Recompute contractor.rating_average from contractor_ratings and update the contractor doc."""
    db = database.get_db()
    cursor = db.contractor_ratings.find({"contractor_id": contractor_id}, {"_id": 0, "rating": 1})
    ratings = [r["rating"] for r in await cursor.to_list(1000)]
    if not ratings:
        return
    from datetime import datetime, timezone
    avg = round(sum(ratings) / len(ratings), 2)
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"rating_average": avg, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )


async def compute_rework_rate(contractor_id: str, client_id: str, rework_days: int = REWORK_DAYS) -> Optional[float]:
    """
    Compute rework rate for a contractor within a client: proportion of completed work orders
    that are follow-up jobs at the same property within rework_days of a prior completion.
    Returns value in [0, 1] or None if no completed jobs. Updates contractor.rework_rate.
    """
    db = database.get_db()
    cursor = db.work_orders.find(
        {"contractor_id": contractor_id, "client_id": client_id, "status": "COMPLETED"},
        {"_id": 0, "work_order_id": 1, "property_id": 1, "created_at": 1, "completed_at": 1},
    )
    wos = await cursor.to_list(500)
    if not wos:
        return None

    def _parse_dt(s: Any):
        if s is None:
            return None
        if isinstance(s, datetime):
            return s.replace(tzinfo=timezone.utc) if s.tzinfo is None else s
        try:
            dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except Exception:
            return None

    rework_count = 0
    for wo in wos:
        prop_id = wo.get("property_id")
        created = _parse_dt(wo.get("created_at"))
        if not prop_id or not created:
            continue
        # This WO is rework if there exists another completed WO at same property whose completed_at
        # is before this WO's created_at and within rework_days of it.
        for other in wos:
            if other.get("work_order_id") == wo.get("work_order_id"):
                continue
            if other.get("property_id") != prop_id:
                continue
            other_completed = _parse_dt(other.get("completed_at"))
            if not other_completed or other_completed >= created:
                continue
            delta = (created - other_completed).total_seconds() / 86400
            if 0 < delta <= rework_days:
                rework_count += 1
                break

    rate = round(rework_count / len(wos), 4) if wos else None
    now = datetime.now(timezone.utc).isoformat()
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"rework_rate": rate, "updated_at": now}},
    )
    return rate


async def backfill_verified_capabilities_from_legacy(
    *,
    dry_run: bool = False,
    include_vetted_self_registered_legacy_trusted: bool = False,
) -> Dict[str, Any]:
    """
    One-time / ops migration: copy legacy execution_capabilities and supported_requirement_codes into
    verified_* for documents that never had verified_execution_capabilities stored.

    Assumptions:
    - Non-self_registered rows were admin- or org-managed; mirroring legacy into verified preserves
      pre–declared-vs-verified behaviour after routing starts requiring verified fields for self_reg.
    - self_registered is skipped by default so unverified marketplace applicants do not gain trusted
      compliance from legacy fields alone. Set include_vetted_self_registered_legacy_trusted=True only
      if historical data was already treated as admin-trusted (e.g. post-incident repair).
    """
    db = database.get_db()
    q: Dict[str, Any] = {"verified_execution_capabilities": {"$exists": False}}
    touched = 0
    skipped = 0
    async for raw in db.contractors.find(q):
        st = (raw.get("source_type") or "").strip().lower()
        if st == SOURCE_SELF_REGISTERED and not include_vetted_self_registered_legacy_trusted:
            skipped += 1
            continue
        if st == SOURCE_SELF_REGISTERED and include_vetted_self_registered_legacy_trusted:
            if not raw.get("vetted"):
                skipped += 1
                continue
        le = raw.get("execution_capabilities")
        lsup = raw.get("supported_requirement_codes")
        if le is None and lsup is None:
            skipped += 1
            continue
        now = datetime.now(timezone.utc).isoformat()
        set_doc: Dict[str, Any] = {
            "updated_at": now,
            "verified_at": now,
            "verified_by": "migration_backfill_legacy",
        }
        if le is not None and str(le).strip():
            try:
                set_doc["verified_execution_capabilities"] = _coerce_execution_capabilities(str(le))
            except ValueError:
                skipped += 1
                continue
        if lsup is not None:
            try:
                set_doc["verified_supported_requirement_codes"] = _coerce_supported_requirement_codes(list(lsup))
            except ValueError:
                skipped += 1
                continue
        if "verified_execution_capabilities" not in set_doc and "verified_supported_requirement_codes" not in set_doc:
            skipped += 1
            continue
        if "verified_execution_capabilities" in set_doc:
            set_doc["execution_capabilities"] = set_doc["verified_execution_capabilities"]
        if "verified_supported_requirement_codes" in set_doc:
            set_doc["supported_requirement_codes"] = set_doc["verified_supported_requirement_codes"]
        if dry_run:
            touched += 1
            continue
        await db.contractors.update_one({"contractor_id": raw["contractor_id"]}, {"$set": set_doc})
        touched += 1
    return {"updated": touched, "skipped": skipped, "dry_run": dry_run}
