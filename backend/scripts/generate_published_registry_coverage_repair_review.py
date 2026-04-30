"""
Read-only: load active published registry, merge coverage patches (same as repair script),
emit JSON + Markdown review tables. Does not write Mongo and does not --apply anything.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.compliance_registry_admin_service import (  # noqa: E402
    REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER,
    plan_types_for_draft_canonical,
)
from services.compliance_registry_conditions import human_summary_registry_conditions  # noqa: E402
from services.compliance_registry_publish_service import (  # noqa: E402
    COLLECTION_PUBLISHED,
    SINGLETON_KEY,
    fetch_active_published_registry_entries,
)
from services.published_registry_coverage_patch_specs import merge_coverage_into_published_entries  # noqa: E402
from services.registry_overlap_correction import apply_registry_overlap_correction  # noqa: E402


def _norm_display_regions(entry: Dict[str, Any]) -> List[str]:
    jur = entry.get("jurisdiction") if isinstance(entry.get("jurisdiction"), dict) else {}
    dj = jur.get("display_jurisdictions")
    if not isinstance(dj, list):
        return []
    out: List[str] = []
    for x in dj:
        tok = str(x or "").strip().upper().replace(" ", "_")
        if tok == "NORTHERNIRELAND":
            tok = "NORTHERN_IRELAND"
        if tok in ("ENGLAND", "WALES", "SCOTLAND", "NORTHERN_IRELAND"):
            out.append(tok)
    return out


def _coverage_keys() -> Set[str]:
    merged_empty, log = merge_coverage_into_published_entries({})
    return {x["registry_key"] for x in log}


COVERAGE_REPAIR_KEYS: Set[str] = _coverage_keys()


def _repair_action(registry_key: str, changelog_by_key: Dict[str, str]) -> str:
    if registry_key in changelog_by_key:
        return changelog_by_key[registry_key]
    return "unchanged"


def _row_from_entry(
    registry_key: str,
    ent: Dict[str, Any],
    *,
    changelog_by_key: Dict[str, str],
) -> Dict[str, Any]:
    cc = str(ent.get("canonical_code") or "").strip().upper()
    ident = ent.get("identity") if isinstance(ent.get("identity"), dict) else {}
    name = str(ident.get("name") or "").strip()
    cls = ent.get("classification") if isinstance(ent.get("classification"), dict) else {}
    client_vis = cls.get("client_surface_visible") is not False
    ab = ent.get("action_behaviour") if isinstance(ent.get("action_behaviour"), dict) else {}
    pam = str(ab.get("primary_action_mode") or "upload_document").strip().lower()
    cta = str(ab.get("cta_label_override") or "").strip() or None
    why = str(ent.get("why_it_matters_short") or ent.get("why_it_matters") or "").strip()
    why_ok = bool(why) and why != REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER
    links = ent.get("action_links") if isinstance(ent.get("action_links"), list) else []
    regions = _norm_display_regions(ent)
    cond = ent.get("conditions") if isinstance(ent.get("conditions"), dict) else {}
    planner_types = sorted(plan_types_for_draft_canonical(cc)) if cc else []

    action = _repair_action(registry_key, changelog_by_key)
    in_coverage = registry_key in COVERAGE_REPAIR_KEYS

    return {
        "registry_key": registry_key,
        "canonical_code": cc,
        "scope_key": str(ent.get("scope_key") or "DEFAULT").strip() or "DEFAULT",
        "display_name": name,
        "display_jurisdictions": regions,
        "property_conditions_summary": human_summary_registry_conditions(cond),
        "coverage_repair": "patched" if in_coverage else "not_in_coverage_patch_list",
        "coverage_repair_action": action if in_coverage else "n/a",
        "client_surface_visible": client_vis,
        "primary_action_mode": pam,
        "cta_label_override": cta,
        "action_links_count": len([x for x in links if isinstance(x, dict)]),
        "why_it_matters_present": why_ok,
        "planner_requirement_types_mapped": planner_types,
        "maps_legacy_materialised_rows": (
            "Overlays Mongo requirements / plan rows whose requirement_type is in planner_requirement_types_mapped; "
            "does not rewrite legacy rows."
        ),
    }


def _group_by_jurisdiction(rows: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Jurisdiction group -> list of registry keys that apply there."""
    g: Dict[str, List[str]] = defaultdict(list)
    order = ["ENGLAND", "WALES", "SCOTLAND", "NORTHERN_IRELAND"]
    for ju in order:
        for r in rows:
            if ju in (r.get("display_jurisdictions") or []):
                g[ju].append(r["registry_key"])
        g[ju] = sorted(set(g[ju]))
    return dict(g)


def _plan_type_index(rows: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Lower requirement_type -> registry keys whose canonical maps to it."""
    idx: Dict[str, List[str]] = defaultdict(list)
    for r in rows:
        key = r["registry_key"]
        for t in r.get("planner_requirement_types_mapped") or []:
            idx[str(t).lower()].append(key)
    for k, v in idx.items():
        idx[k] = sorted(set(v))
    return dict(idx)


def _overlap_report(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    idx = _plan_type_index(rows)
    keys = {r["registry_key"]: r for r in rows}

    def multi(slugs: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for s in slugs:
            klist = idx.get(s.lower(), [])
            out[s] = {"registry_keys": klist, "count": len(klist)}
        return out

    return {
        "TENANCY_DEPOSIT_PROTECTION_model": {
            "note": (
                "Four jurisdiction-scoped rows (England, Wales, Scotland, Northern Ireland); "
                "no UK-wide DEFAULT; each row gates on deposit_taken and tenancy_active."
            ),
            "deposit_pi_keys": idx.get("deposit_pi", []),
            "tenancy_deposit_protection_keys": idx.get("tenancy_deposit_protection", []),
        },
        "LANDLORD_REGISTRATION_DEFAULT_vs_LANDLORD_REGISTRATION_NI": {
            "LANDLORD_REGISTRATION|DEFAULT": keys.get("LANDLORD_REGISTRATION|DEFAULT"),
            "LANDLORD_REGISTRATION_NI|DEFAULT": keys.get("LANDLORD_REGISTRATION_NI|DEFAULT"),
            "scotland_slug_keys": idx.get("scotland_landlord_registration", []),
            "ni_slug_keys": idx.get("landlord_registration_ni", []),
            "generic_landlord_registration_slug_keys": idx.get("landlord_registration", []),
        },
        "FIRE_DETECTION_vs_SMOKE_HEAT_partition": multi(
            ["fire_alarm", "fire_detection", "smoke_alarms", "co_alarms", "smoke_heat_alarms"]
        ),
        "HMO_FIRE_vs_FRA_vs_HMO_LICENSING": {
            "hmo_fire_risk": idx.get("hmo_fire_risk", []),
            "hmo_fire_risk_evidence": idx.get("hmo_fire_risk_evidence", []),
            "fire_risk_assessment": idx.get("fire_risk_assessment", []),
            "hmo_license": idx.get("hmo_license", []),
            "property_licence": idx.get("property_licence", []),
            "hmo_licensing": idx.get("hmo_licensing", []),
        },
        "tenancy_pack": {
            "how_to_rent": idx.get("how_to_rent", []),
            "tenancy_agreement": idx.get("tenancy_agreement", []),
            "occupation_contract": idx.get("occupation_contract", []),
            "wales_occupation_contract": idx.get("wales_occupation_contract", []),
        },
        "right_to_rent_family": multi(["right_to_rent", "right_to_rent_checks"]),
    }


async def _build_report(*, post_overlap_only: bool = False) -> Tuple[Dict[str, Any], str]:
    from database import database

    mongo_note = ""
    prev_entries: Dict[str, Any] = {}
    try:
        await database.connect()
        try:
            db = database.get_db()
            prev = await fetch_active_published_registry_entries(db)
            if prev is None:
                mongo_note = "No active published snapshot in Mongo (treated as empty entries map)."
                prev_entries = {}
            else:
                mongo_note = "Loaded active published entries from Mongo."
                prev_entries = dict(prev)
        finally:
            await database.close()
    except Exception as e:  # noqa: BLE001
        mongo_note = f"Mongo unavailable ({type(e).__name__}: {e}); merged against empty entries map for patch preview."
        prev_entries = {}

    overlapped, overlap_changelog = apply_registry_overlap_correction(prev_entries)
    if post_overlap_only:
        merged = overlapped
        changelog: List[Dict[str, Any]] = []
    else:
        merged, changelog = merge_coverage_into_published_entries(overlapped)
    ch_by = {c["registry_key"]: c["action"] for c in changelog}

    rows = [_row_from_entry(k, v, changelog_by_key=ch_by) for k, v in sorted(merged.items(), key=lambda kv: kv[0])]
    if post_overlap_only:
        for r in rows:
            r["coverage_repair"] = "live_active_snapshot"
            r["coverage_repair_action"] = "n/a"
    by_j = _group_by_jurisdiction(rows)
    overlap = _overlap_report(rows)

    report: Dict[str, Any] = {
        "report_kind": "post_overlap_active_registry" if post_overlap_only else "overlap_then_coverage_merge_preview",
        "mongo_load_note": mongo_note,
        "overlap_changelog_note": (
            "In-memory overlap pass removed 0 keys (Mongo snapshot already matches overlap-clean state). "
            "See the last `apply_registry_overlap_correction.py --apply` stdout for the removal list."
            if post_overlap_only and not overlap_changelog
            else None
        ),
        "previous_published_entry_count": len(prev_entries),
        "overlap_correction_removals": overlap_changelog,
        "post_overlap_entry_count": len(overlapped),
        "merged_entry_count": len(merged),
        "coverage_merge_applied": not post_overlap_only,
        "coverage_patch_entry_count": 0 if post_overlap_only else len(COVERAGE_REPAIR_KEYS),
        "rows": rows,
        "grouped_registry_keys_by_jurisdiction": by_j,
        "duplication_overlap_review": overlap,
    }

    title = (
        "# Active published registry (post-overlap correction, no coverage merge)"
        if post_overlap_only
        else "# Published registry: overlap plus coverage-merge preview"
    )
    md_lines = [
        title,
        "",
        f"**Source:** {mongo_note}",
        f"**Counts:** previous keys={len(prev_entries)}, after overlap removal={len(overlapped)}, "
        f"final keys={len(merged)}"
        + (
            " (no coverage merge)."
            if post_overlap_only
            else f" (overlap removal + coverage merge preview); coverage-patched keys={len(COVERAGE_REPAIR_KEYS)}."
        ),
        "",
        "## Grouped by jurisdiction (registry keys)",
        "",
    ]
    for ju, klist in by_j.items():
        md_lines.append(f"### {ju}")
        md_lines.append("")
        md_lines.append("| registry_key |")
        md_lines.append("|---|")
        for k in klist:
            md_lines.append(f"| `{k}` |")
        md_lines.append("")

    md_lines.append("## All entries (detail)")
    md_lines.append("")
    md_lines.append(
        "| registry_key | canonical | display_name | jurisdictions | conditions | repair | client_visible | "
        "action_mode | CTA | links | why? | mapped types (count) |"
    )
    md_lines.append("|---:|---|---|---|---|---|:---:|:---|:---|---:|---:|---:|")
    for r in rows:
        m = r.get("planner_requirement_types_mapped") or []
        md_lines.append(
            f"| `{r['registry_key']}` | {r['canonical_code']} | {r['display_name'][:60]} | "
            f"{', '.join(r['display_jurisdictions'])} | {r['property_conditions_summary'][:70]} | "
            f"{r['coverage_repair_action']} | {r['client_surface_visible']} | {r['primary_action_mode']} | "
            f"{r['cta_label_override'] or '—'} | {r['action_links_count']} | "
            f"{'yes' if r['why_it_matters_present'] else 'no'} | {len(m)} |"
        )
    md_lines.append("")
    md_lines.append("## Duplication / overlap review (automated index)")
    md_lines.append("")
    md_lines.append("```json")
    md_lines.append(json.dumps(overlap, indent=2, default=str))
    md_lines.append("```")

    return report, "\n".join(md_lines)


async def _main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Generate published registry review tables.")
    p.add_argument(
        "--post-overlap-only",
        action="store_true",
        help="Active Mongo snapshot after in-memory overlap pass only (no coverage repair merge).",
    )
    args = p.parse_args()
    report, md = await _build_report(post_overlap_only=bool(args.post_overlap_only))
    out_dir = Path(__file__).resolve().parent
    if args.post_overlap_only:
        json_path = out_dir / "post_overlap_active_registry_review.json"
        md_path = out_dir / "post_overlap_active_registry_review.md"
    else:
        json_path = out_dir / "coverage_repair_final_review.json"
        md_path = out_dir / "coverage_repair_final_review.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    print(json.dumps({"written": [str(json_path), str(md_path)]}, indent=2))
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
