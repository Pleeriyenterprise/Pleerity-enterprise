from __future__ import annotations

from datetime import datetime, timezone
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from services.compliance_registry_publish_service import fetch_active_published_registry_entries
from services.compliance_registry_admin_service import registry_entry_key
from services.compliance_requirement_registry import resolve_published_entry_for_requirement
from services.compliance_rules_registry import portfolio_jurisdiction_label
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_client_runtime_surface import (
    filter_requirement_rows_for_client_runtime_surfaces,
    project_requirement_row_client_runtime,
    client_portal_surface_visible_row,
    compute_client_portal_requirement_stats,
)

LEGACY_STATE_ACTIVE = "active"
LEGACY_STATE_MAPPED_READONLY = "mapped_readonly"
LEGACY_STATE_UNMAPPED_READONLY = "unmapped_readonly"
LEGACY_STATE_HIDDEN_DEPRECATED = "hidden_deprecated"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _linked_counts(db, row: Dict[str, Any]) -> Dict[str, int]:
    rid = str(row.get("requirement_id") or "").strip()
    cid = str(row.get("client_id") or "").strip()
    if not rid or not cid:
        return {"documents": 0, "work_orders": 0, "reminders": 0, "invoices": 0}
    return {
        "documents": int(await db.documents.count_documents({"client_id": cid, "$or": [{"requirement_id": rid}, {"requirement_ids": rid}]})),
        "work_orders": int(await db.work_orders.count_documents({"client_id": cid, "$or": [{"requirement_id": rid}, {"related_requirement_id": rid}, {"metadata.requirement_id": rid}]})),
        "reminders": int(await db.reminder_item_state.count_documents({"client_id": cid, "target_ref": rid})),
        "invoices": int(await db.invoices.count_documents({"client_id": cid, "$or": [{"requirement_id": rid}, {"related_requirement_id": rid}, {"metadata.requirement_id": rid}]})),
    }


def _has_links(counts: Dict[str, int]) -> bool:
    return sum(int(v or 0) for v in counts.values()) > 0


async def _cleanup_reminders_and_open_gaps_for_requirement(
    db,
    client_id: str,
    requirement_id: str,
) -> Dict[str, int]:
    """
    Remove scheduler reminder rows and resolve open compliance gaps tied to a requirement.

    Called on migration --apply for rows that are hidden/deprecated or unmapped ghosts without
    financial/evidence links, so operational artifacts do not outlive client-truth classification.
    """
    cid = str(client_id or "").strip()
    rid = str(requirement_id or "").strip()
    if not cid or not rid:
        return {"reminder_item_state_deleted": 0, "compliance_gaps_resolved": 0}
    rem = await db.reminder_item_state.delete_many({"client_id": cid, "target_ref": rid})
    now = datetime.now(timezone.utc)
    gap_res = await db.compliance_gaps.update_many(
        {"client_id": cid, "requirement_id": rid, "status": "open"},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": now,
                "updated_at": now,
                "resolved_reason": "client_truth_migration_cleanup",
            }
        },
    )
    return {
        "reminder_item_state_deleted": int(rem.deleted_count),
        "compliance_gaps_resolved": int(gap_res.modified_count),
    }


def _state_payload(*, legacy_state: str, canonical_code: Optional[str], mapped_code: Optional[str], counts: Dict[str, int], source: str) -> Dict[str, Any]:
    review_required = legacy_state == LEGACY_STATE_UNMAPPED_READONLY
    readonly_visible = legacy_state in (LEGACY_STATE_MAPPED_READONLY, LEGACY_STATE_UNMAPPED_READONLY)
    return {
        "legacy_requirement_state": legacy_state,
        "legacy_readonly_visible": readonly_visible,
        "legacy_canonical_requirement_code": canonical_code,
        "legacy_mapped_published_requirement_code": mapped_code,
        "legacy_review_required": review_required,
        "legacy_linkage_summary": counts,
        "client_surface_source_classification": source,
        "legacy_state_updated_at": _now_iso(),
    }


async def _match_published(*, row: Dict[str, Any], property_doc: Dict[str, Any], client_doc: Dict[str, Any], published_registry_entries: Dict[str, Any], requirement_type: str) -> bool:
    plabel = portfolio_jurisdiction_label(property_doc, client_doc or {})
    pe = resolve_published_entry_for_requirement(
        published_registry_entries=published_registry_entries,
        requirement_type=requirement_type,
        portfolio_label=str(plabel or ""),
        property_doc=property_doc,
        enforce_conditions=True,
    )
    return isinstance(pe, dict)


def _matching_published_code_from_row(row: Dict[str, Any]) -> Optional[str]:
    code = str(row.get("requirement_type") or row.get("requirement_code") or "").strip()
    return code or None


def _published_entry_key(
    *,
    row: Dict[str, Any],
    property_doc: Dict[str, Any],
    client_doc: Dict[str, Any],
    published_registry_entries: Dict[str, Any],
    requirement_type: str,
) -> Optional[str]:
    plabel = portfolio_jurisdiction_label(property_doc, client_doc or {})
    pe = resolve_published_entry_for_requirement(
        published_registry_entries=published_registry_entries,
        requirement_type=requirement_type,
        portfolio_label=str(plabel or ""),
        property_doc=property_doc,
        enforce_conditions=True,
    )
    return registry_entry_key(pe) if isinstance(pe, dict) else None


async def evaluate_client_truth_migration(db, *, client_id: Optional[str] = None, limit: int = 20000, apply: bool = False) -> Dict[str, Any]:
    q: Dict[str, Any] = {"client_id": client_id} if client_id else {}
    reqs = await db.requirements.find(q, {"_id": 0}).limit(max(100, int(limit))).to_list(max(100, int(limit)))
    if not reqs:
        return {"mode": "apply" if apply else "dry_run", "scanned": 0, "changed": 0, "state_counts": {}, "rows": []}

    client_ids = sorted({str(r.get("client_id") or "").strip() for r in reqs if str(r.get("client_id") or "").strip()})
    client_docs = {cid: (await db.clients.find_one({"client_id": cid}, {"_id": 0}) or {}) for cid in client_ids}
    prop_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    props = await db.properties.find({"client_id": {"$in": client_ids}}, {"_id": 0}).to_list(50000)
    for p in props:
        prop_by_key[(str(p.get("client_id") or ""), str(p.get("property_id") or ""))] = p
    published = await fetch_active_published_registry_entries(db)

    changed = 0
    operational_cleanup = {
        "reminder_item_state_deleted": 0,
        "compliance_gaps_resolved": 0,
        "cleanup_invocations": 0,
    }
    state_counts: Dict[str, int] = {}
    out_rows: List[Dict[str, Any]] = []
    grouped = defaultdict(int)
    ghost_visible_rows: List[Dict[str, Any]] = []
    linkage_totals = {
        "rows_with_linked_reminders_only": 0,
        "rows_with_linked_documents": 0,
        "rows_with_linked_work_orders": 0,
        "rows_with_linked_invoices": 0,
    }
    dup_by_prop_pub_key: Dict[Tuple[str, str, str], int] = defaultdict(int)
    for row in reqs:
        cid = str(row.get("client_id") or "").strip()
        pid = str(row.get("property_id") or "").strip()
        prop = prop_by_key.get((cid, pid)) or {}
        cdoc = client_docs.get(cid) or {}
        raw_type = str(row.get("requirement_type") or row.get("requirement_code") or "").strip()
        canon = normalize_requirement_code(raw_type)
        published_match = await _match_published(
            row=row,
            property_doc=prop,
            client_doc=cdoc,
            published_registry_entries=published,
            requirement_type=raw_type,
        ) if raw_type and prop else False
        # Canonical-path match: same published resolution using normalize_requirement_code(raw).
        # When published_match is True, this should normally match; divergence flags alias/registry skew.
        mapped_match = False
        if canon and prop:
            mapped_match = await _match_published(
                row=row,
                property_doc=prop,
                client_doc=cdoc,
                published_registry_entries=published,
                requirement_type=canon,
            )
        elif published_match:
            mapped_match = True
        links = await _linked_counts(db, row)
        if links.get("reminders", 0) > 0 and links.get("documents", 0) == 0 and links.get("work_orders", 0) == 0 and links.get("invoices", 0) == 0:
            linkage_totals["rows_with_linked_reminders_only"] += 1
        if links.get("documents", 0) > 0:
            linkage_totals["rows_with_linked_documents"] += 1
        if links.get("work_orders", 0) > 0:
            linkage_totals["rows_with_linked_work_orders"] += 1
        if links.get("invoices", 0) > 0:
            linkage_totals["rows_with_linked_invoices"] += 1
        pub_key_raw = None
        if published_match and raw_type and prop:
            pub_key_raw = _published_entry_key(
                row=row,
                property_doc=prop,
                client_doc=cdoc,
                published_registry_entries=published,
                requirement_type=raw_type,
            )
            if pub_key_raw:
                dup_by_prop_pub_key[(cid, pid, pub_key_raw)] += 1

        if published_match:
            state = LEGACY_STATE_ACTIVE
            source = "published"
            mapped_code = canon if canon and mapped_match else None
        elif _has_links(links):
            state = LEGACY_STATE_MAPPED_READONLY if mapped_match else LEGACY_STATE_UNMAPPED_READONLY
            source = "legacy_readonly"
            mapped_code = canon if mapped_match else None
        else:
            state = LEGACY_STATE_HIDDEN_DEPRECATED
            source = "baseline"
            mapped_code = None
        payload = _state_payload(legacy_state=state, canonical_code=canon, mapped_code=mapped_code, counts=links, source=source)
        if state == LEGACY_STATE_HIDDEN_DEPRECATED:
            payload["client_surface_visible"] = False
        state_counts[state] = state_counts.get(state, 0) + 1
        grouped[(state, raw_type, canon or "", bool(published_match), bool(mapped_match))] += 1
        rid = str(row.get("requirement_id") or "")
        changed_fields = [k for k, v in payload.items() if row.get(k) != v]
        if changed_fields and apply and rid:
            await db.requirements.update_one({"client_id": cid, "requirement_id": rid}, {"$set": payload})
            changed += 1
            should_clean_ops = state == LEGACY_STATE_HIDDEN_DEPRECATED or (
                (not published_match)
                and state == LEGACY_STATE_UNMAPPED_READONLY
                and int(links.get("documents") or 0) == 0
                and int(links.get("work_orders") or 0) == 0
                and int(links.get("invoices") or 0) == 0
            )
            if should_clean_ops:
                cr = await _cleanup_reminders_and_open_gaps_for_requirement(db, cid, rid)
                operational_cleanup["reminder_item_state_deleted"] += int(cr["reminder_item_state_deleted"])
                operational_cleanup["compliance_gaps_resolved"] += int(cr["compliance_gaps_resolved"])
                operational_cleanup["cleanup_invocations"] += 1
        matched_published_code = _matching_published_code_from_row(row) if published_match else None
        alias_normalized_changed = bool(canon and str(canon).strip().lower() != str(raw_type).strip().lower())
        pub_key_canon = None
        if canon and prop:
            pub_key_canon = _published_entry_key(
                row=row,
                property_doc=prop,
                client_doc=cdoc,
                published_registry_entries=published,
                requirement_type=canon,
            )
        # Visible to clients if not explicitly hidden (matches portal semantics).
        if (not published_match) and row.get("client_surface_visible") is not False:
            ghost_visible_rows.append(
                {
                    "requirement_id": rid,
                    "client_id": cid,
                    "property_id": pid,
                    "requirement_type": raw_type,
                    "canonical_code": canon,
                    "client_surface_visible": row.get("client_surface_visible"),
                    "legacy_state_after_migration": state,
                }
            )
        out_rows.append(
            {
                "requirement_id": rid,
                "client_id": cid,
                "property_id": pid,
                "requirement_type": raw_type,
                "canonical_code": canon,
                "matched_published_code": matched_published_code,
                "published_registry_entry_key_raw": pub_key_raw,
                "published_registry_entry_key_canonical": pub_key_canon,
                "published_match": published_match,
                "mapped_match": mapped_match,
                "legacy_state": state,
                "client_surface_visible_current": row.get("client_surface_visible") is not False,
                "changed_fields": changed_fields,
                "linkage": links,
            }
        )

    mismatch_rows: List[Dict[str, Any]] = []
    for r in out_rows:
        if not r.get("published_match") or r.get("mapped_match"):
            continue
        raw_type = str(r.get("requirement_type") or "")
        canon = r.get("canonical_code")
        pub_key_raw = r.get("published_registry_entry_key_raw")
        pub_key_canon = r.get("published_registry_entry_key_canonical")
        alias_normalized_changed = bool(canon and str(canon).strip().lower() != raw_type.strip().lower())
        if canon is None:
            why = "canonical_code_none_but_row_matched_on_raw"
        elif not pub_key_raw and not pub_key_canon:
            why = "published_match_true_but_no_registry_entry_key"
        elif pub_key_raw and pub_key_canon and pub_key_raw != pub_key_canon:
            why = "raw_vs_canonical_resolve_different_published_entry"
        elif pub_key_raw and not pub_key_canon:
            why = "canonical_code_does_not_resolve_to_published_entry"
        else:
            why = "published_on_raw_fails_on_canonical_lookup"
        dup_n = int(dup_by_prop_pub_key.get((str(r.get("client_id") or ""), str(r.get("property_id") or ""), str(pub_key_raw or "")), 0) or 0) if pub_key_raw else 0
        mismatch_rows.append(
            {
                "requirement_id": r.get("requirement_id"),
                "client_id": r.get("client_id"),
                "property_id": r.get("property_id"),
                "requirement_type": raw_type,
                "canonical_code": canon,
                "matched_published_code": r.get("matched_published_code"),
                "published_registry_entry_key_raw": pub_key_raw,
                "published_registry_entry_key_canonical": pub_key_canon,
                "why_mapping_failed": why,
                "alias_normalization_changed_code": alias_normalized_changed,
                "would_duplicate_canonical_after_apply": bool(pub_key_raw and dup_n > 1),
                "same_property_same_published_key_row_count": dup_n,
            }
        )

    grouped_rows = [
        {
            "legacy_state": k[0],
            "requirement_type": k[1],
            "canonical_code": k[2] or None,
            "published_match": k[3],
            "mapped_match": k[4],
            "count": v,
        }
        for k, v in sorted(grouped.items(), key=lambda kv: (-kv[1], str(kv[0])))
    ]

    simulation_clients = await _pick_simulation_clients(db)
    simulations = []
    for sim in simulation_clients:
        simulations.append(await _simulate_client_before_after(db, sim["client_id"], sim["label"]))

    return {
        "mode": "apply" if apply else "dry_run",
        "scanned": len(reqs),
        "changed": changed if apply else len([r for r in out_rows if r.get("changed_fields")]),
        "operational_cleanup": operational_cleanup if apply else {},
        "state_counts": state_counts,
        "grouped_counts": grouped_rows,
        "published_true_mapped_false_rows": mismatch_rows,
        "published_true_mapped_false_count": len(mismatch_rows),
        "linkage_exact_counts": linkage_totals,
        "ghost_currently_visible_rows": ghost_visible_rows,
        "ghost_currently_visible_count": len(ghost_visible_rows),
        "visibility_simulation": simulations,
        "rows": out_rows,
    }


async def _pick_simulation_clients(db) -> List[Dict[str, str]]:
    clients = await db.clients.find({}, {"_id": 0, "client_id": 1, "default_jurisdiction": 1}).to_list(10000)
    cids = [c for c in clients if c.get("client_id")]
    if not cids:
        return []
    england = next((c for c in cids if str(c.get("default_jurisdiction") or "").lower() == "england"), None)
    scotland = next((c for c in cids if str(c.get("default_jurisdiction") or "").lower() == "scotland"), None)
    mixed = None
    for c in cids:
        props = await db.properties.find({"client_id": c["client_id"]}, {"_id": 0, "jurisdiction": 1}).to_list(2000)
        jset = {str(p.get("jurisdiction") or "").strip().lower() for p in props if str(p.get("jurisdiction") or "").strip()}
        if len(jset) > 1:
            mixed = c
            break
    out: List[Dict[str, str]] = []
    if england:
        out.append({"client_id": str(england["client_id"]), "label": "england"})
    if scotland:
        out.append({"client_id": str(scotland["client_id"]), "label": "scotland"})
    if mixed:
        out.append({"client_id": str(mixed["client_id"]), "label": "mixed_jurisdiction"})
    return out


async def _simulate_client_before_after(db, client_id: str, label: str) -> Dict[str, Any]:
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    props = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(5000)
    raw = await db.requirements.find({"client_id": client_id}, {"_id": 0}).to_list(20000)
    before_visible = [r for r in raw if r.get("client_surface_visible") is not False]
    after = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=raw,
        client_doc=client,
        properties=props,
    )
    before_projected = [project_requirement_row_client_runtime(r) for r in before_visible]
    before_portal = [r for r in before_projected if client_portal_surface_visible_row(r)]
    after_projected = [project_requirement_row_client_runtime(r) for r in after]
    after_portal = [r for r in after_projected if client_portal_surface_visible_row(r)]
    before_stats = compute_client_portal_requirement_stats(before_portal)
    after_stats = compute_client_portal_requirement_stats(after_portal)
    req_b, req_a = len(before_portal), len(after_portal)
    ovb, ova = int(before_stats.get("overdue") or 0), int(after_stats.get("overdue") or 0)
    tb, ta = (
        len([r for r in before_portal if str(r.get("status") or "").upper() in {"OVERDUE", "EXPIRED", "EXPIRING_SOON", "PENDING", "MISSING"}]),
        len([r for r in after_portal if str(r.get("status") or "").upper() in {"OVERDUE", "EXPIRED", "EXPIRING_SOON", "PENDING", "MISSING"}]),
    )
    tot_b, tot_a = int(before_stats.get("total_requirements") or 0), int(after_stats.get("total_requirements") or 0)
    return {
        "label": label,
        "client_id": client_id,
        "requirements_page_count_before": req_b,
        "requirements_page_count_after": req_a,
        "requirements_page_count_delta": req_a - req_b,
        "dashboard_overdue_before": ovb,
        "dashboard_overdue_after": ova,
        "dashboard_overdue_delta": ova - ovb,
        "today_requirement_tasks_before": tb,
        "today_requirement_tasks_after": ta,
        "today_requirement_tasks_delta": ta - tb,
        "compliance_score_total_before": tot_b,
        "compliance_score_total_after": tot_a,
        "compliance_score_total_delta": tot_a - tot_b,
    }

