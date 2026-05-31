#!/usr/bin/env python3
"""Trace Legionella requirement state on staging for Nancy client."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import httpx

API = "https://pleerity-enterprise.onrender.com/api"
EMAIL = "nancy@yopmail.com"
PW = Path(__file__).resolve().parent / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
OUT = Path(__file__).resolve().parent / "docs/audit/prelaunch_customer_operational_language_governance_01/legionella_staging_trace.json"


def _yes(v: Any) -> bool:
    return str(v or "").strip().lower() in ("yes", "true", "y", "1")


def main() -> None:
    pw = PW.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    props_resp = httpx.get(f"{API}/client/properties", headers=h, timeout=120)
    props_resp.raise_for_status()
    props_body = props_resp.json()
    props = props_body if isinstance(props_body, list) else props_body.get("properties") or []
    prop_map = {
        p.get("property_id"): p.get("name") or p.get("address_line_1") or p.get("property_id")
        for p in props
    }

    reqs = httpx.get(
        f"{API}/client/requirements",
        headers=h,
        params={"projection": "full"},
        timeout=180,
    )
    reqs.raise_for_status()
    rows = reqs.json().get("requirements") or []
    leg = [
        row
        for row in rows
        if "legionella" in str(row.get("requirement_type") or row.get("requirement_code") or "").lower()
    ]

    traces: List[Dict[str, Any]] = []
    for row in leg:
        rid = row.get("requirement_id")
        pid = row.get("property_id")
        ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
        comp = row.get("evidence_completeness") if isinstance(row.get("evidence_completeness"), dict) else {}

        cer = httpx.get(
            f"{API}/client/properties/{pid}/requirements/{rid}/compliance-evidence",
            headers=h,
            timeout=120,
        )
        records = cer.json().get("evidence_records") or [] if cer.status_code == 200 else []

        structured_rows = []
        for rec in records[:20]:
            payload = rec.get("evidence_payload") if isinstance(rec.get("evidence_payload"), dict) else {}
            fields = payload.get("structured_fields") if isinstance(payload.get("structured_fields"), dict) else {}
            structured_rows.append(
                {
                    "evidence_record_id": rec.get("evidence_record_id"),
                    "evidence_mode": rec.get("evidence_mode"),
                    "status": rec.get("status"),
                    "created_at": rec.get("created_at"),
                    "is_primary": rec.get("evidence_record_id") == ea.get("primary_evidence_record_id"),
                    "actions_required": fields.get("actions_required"),
                    "assessment_completed": fields.get("assessment_completed"),
                    "next_review_date": fields.get("next_review_date"),
                    "declaration_confirmed": fields.get("declaration_confirmed"),
                    "risk_level": fields.get("risk_level"),
                    "document_id": rec.get("document_id") or payload.get("document_id"),
                }
            )

        stage = str(row.get("truth_presentation_stage") or "")
        has_structured = any(s.get("evidence_mode") == "STRUCTURED_DECLARATION" for s in structured_rows)
        ar_vals = [
            s.get("actions_required")
            for s in structured_rows
            if s.get("evidence_mode") == "STRUCTURED_DECLARATION"
        ]
        diagnosis: List[str] = []
        if not structured_rows:
            diagnosis.append("No compliance evidence records — nothing persisted via structured submit.")
        elif not has_structured:
            diagnosis.append(
                "Only document/supporting uploads on file — structured Legionella assessment not submitted."
            )
        if stage == "followup_required":
            if any(_yes(v) for v in ar_vals):
                diagnosis.append(
                    "Structured record has actions_required=Yes — follow-up is intentionally left open by design."
                )
            elif ar_vals and all(not _yes(v) for v in ar_vals if v is not None):
                diagnosis.append(
                    "actions_required=No but UI still followup_required — investigate authority sync / stale projection."
                )
        if ea.get("state_reason"):
            diagnosis.append(f"evidence_authority.state_reason={ea.get('state_reason')}")
        if row.get("requirement_satisfied") and stage == "followup_required":
            diagnosis.append(
                "requirement_satisfied=true coexists with followup_required — renewal/overdue attention may still show."
            )

        traces.append(
            {
                "property_label": prop_map.get(pid, pid),
                "property_id": pid,
                "requirement_id": rid,
                "jurisdiction": row.get("jurisdiction"),
                "status": row.get("status"),
                "due_date": row.get("due_date"),
                "expiry_date": row.get("expiry_date"),
                "client_lifecycle_state": row.get("client_lifecycle_state"),
                "truth_presentation_stage": row.get("truth_presentation_stage"),
                "truth_presentation_label": row.get("truth_presentation_label"),
                "truth_presentation_subline": row.get("truth_presentation_subline"),
                "truth_presentation_tier_supplement": row.get("truth_presentation_tier_supplement"),
                "governance_family": row.get("governance_family"),
                "semantic_state": row.get("semantic_state"),
                "requirement_satisfied": row.get("requirement_satisfied"),
                "document_upload_required": row.get("document_upload_required"),
                "missing_required_document": row.get("missing_required_document"),
                "requirement_resolution_status": row.get("requirement_resolution_status"),
                "evidence_satisfaction_source": row.get("evidence_satisfaction_source"),
                "evidence_authority": {
                    "state": ea.get("state"),
                    "state_reason": ea.get("state_reason"),
                    "semantic_state": ea.get("semantic_state"),
                    "primary_evidence_record_id": ea.get("primary_evidence_record_id"),
                    "version": ea.get("version"),
                },
                "evidence_completeness": {
                    "is_complete": comp.get("is_complete"),
                    "required_missing_count": comp.get("required_missing_count"),
                    "completeness_reason": comp.get("completeness_reason"),
                },
                "primary_cta": ((row.get("take_action") or {}).get("primary") or {}).get("label"),
                "cer_count": len(records),
                "cer_recent": structured_rows,
                "diagnosis": diagnosis or ["No blocker identified from API trace."],
            }
        )

    out = {
        "client_email": EMAIL,
        "legionella_row_count": len(traces),
        "traces": traces,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
