#!/usr/bin/env python3
"""Post-deploy staging verification for Evidence Readiness operational refinement."""
from __future__ import annotations

import importlib.util
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/evidence_readiness_operational_presentation"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
EXPECTED_COMMIT_PREFIX = "28b6926b"
NANCY_CLIENT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
LEGACY_PACK_ID = "cap_c4758a8185044bf4a2e75387"

_spec = importlib.util.spec_from_file_location("_fc", ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py")
_fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fc)
API = _fc.API

ER_MARKERS = (
    "operational evidence matrix",
    "reference metadata appendix",
    "recommended remediation actions",
    "audit readiness indicators",
)
ER_COMPACT_FOOTER_ANY = ("point-in-time export", "frozen snapshot export")
ER_NEGATIVE = (
    "COMPLIANCE_RECALC_SLA_BREACH",
    "RISK_SIGNAL_REGEN_COMPLETED",
    "HEARTBEAT_",
)
PACK_ARCHIVE = "evidence matrix"
PACK_NEGATIVE = "operational evidence matrix"


def hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def pdf_text_lower(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_bytes)).pages).lower()


def inspect_evidence_readiness_pdf(pdf_bytes: bytes) -> dict:
    if pdf_bytes[:4] != b"%PDF":
        return {"valid_pdf": False, "pass": False}
    text = pdf_text_lower(pdf_bytes)
    raw = "\n".join((p.extract_text() or "") for p in __import__("pypdf").PdfReader(io.BytesIO(pdf_bytes)).pages)
    markers = {m: m in text for m in ER_MARKERS}
    markers["compact_footer"] = any(m in text for m in ER_COMPACT_FOOTER_ANY)
    chronology = "operational activity chronology" in text
    grouped = chronology and any(
        g in text for g in ("evidence lifecycle", "compliance scoring", "risk assessment", "delivery proof")
    )
    no_telemetry = not any(t in raw for t in ER_NEGATIVE)
    matrix_cols = all(c in text for c in ("obligation", "status", "evidence", "expiry", "risk", "action required"))
    frozen_once = text.count("this report is a frozen deterministic snapshot") <= 2
    return {
        "valid_pdf": True,
        "bytes": len(pdf_bytes),
        "page_count": len(__import__("pypdf").PdfReader(io.BytesIO(pdf_bytes)).pages),
        "markers": markers,
        "matrix_six_columns": matrix_cols,
        "chronology_grouped": grouped or not chronology,
        "no_raw_telemetry": no_telemetry,
        "frozen_wording_limited": frozen_once,
        "pass": all(markers.values()) and matrix_cols and no_telemetry and frozen_once and markers["compact_footer"],
    }


def inspect_audit_pack_zip(zip_bytes: bytes) -> dict:
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = zf.namelist()
    trail = "Audit_Evidence_Pack/05_AUDIT_TIMELINE/audit_trail.pdf" in names
    summary_path = "Audit_Evidence_Pack/01_EXECUTIVE_SUMMARY/compliance_summary.pdf"
    summary_text = ""
    if summary_path in names:
        summary_text = pdf_text_lower(zf.read(summary_path))
    return {
        "zip_file_count": len(names),
        "has_audit_trail_pdf": trail,
        "has_archive_evidence_matrix": PACK_ARCHIVE in summary_text,
        "no_operational_matrix_wording": PACK_NEGATIVE not in summary_text,
        "pass": trail and PACK_ARCHIVE in summary_text and PACK_NEGATIVE not in summary_text,
    }


def generate_er(token: str, scope: str, property_id: Optional[str] = None) -> httpx.Response:
    body: dict = {"scope": scope}
    if property_id:
        body["property_id"] = property_id
    return httpx.post(f"{API}/reports/generate", headers=hdr(token), json=body, timeout=300)


def redownload_artifact(token: str, artifact_id: str) -> tuple[bytes, bytes]:
    d1 = httpx.get(f"{API}/reports/artifacts/{artifact_id}/download", headers=hdr(token), timeout=300)
    d2 = httpx.get(f"{API}/reports/artifacts/{artifact_id}/download", headers=hdr(token), timeout=300)
    return d1.content, d2.content


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gates: Dict[str, Any] = {}
    artifact: Dict[str, Any] = {
        "programme": "EVIDENCE-READINESS-OPERATIONAL-STAGING-VERIFY",
        "run_tag": RUN_TAG,
        "expected_commit_prefix": EXPECTED_COMMIT_PREFIX,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    ver = httpx.get(f"{API}/version", timeout=60)
    ver_body = ver.json() if ver.status_code == 200 else {}
    commit = str(ver_body.get("commit_sha") or "")
    artifact["deploy_version"] = ver_body
    gates["deploy_commit_matches"] = {
        "pass": commit.lower().startswith(EXPECTED_COMMIT_PREFIX.lower()),
        "commit_sha": commit,
        "expected_prefix": EXPECTED_COMMIT_PREFIX,
    }

    admin_t, _, step, err = _fc.admin_session()
    if err:
        artifact["error"] = err
        gates["auth"] = {"pass": False, "error": err}
        artifact["gates"] = gates
        artifact["all_gates_pass"] = False
        path = OUT / f"STAGING_EVIDENCE_READINESS_VERIFY_{RUN_TAG}.json"
        path.write_text(json.dumps(artifact, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"artifact": str(path), "all_gates_pass": False, "error": err}, indent=2))
        return 1

    gates["auth"] = {"pass": True}
    nancy_tok, nierr = _fc.impersonate(admin_t, step, NANCY_CLIENT, "er operational staging verify")
    nancy: dict = {}
    if nierr:
        nancy["error"] = nierr
    else:
        props_resp = httpx.get(f"{API}/client/properties", headers=hdr(nancy_tok), timeout=120).json()
        plist = props_resp if isinstance(props_resp, list) else props_resp.get("properties") or []
        nancy["property_count"] = len(plist)

        # Property with most requirements (typical mixed-status)
        prop_req_counts: List[tuple] = []
        for p in plist[:20]:
            pid = p.get("property_id")
            if not pid:
                continue
            reqs = httpx.get(
                f"{API}/client/properties/{pid}/requirements",
                headers=hdr(nancy_tok),
                timeout=120,
            )
            count = len(reqs.json()) if reqs.status_code == 200 and isinstance(reqs.json(), list) else 0
            prop_req_counts.append((count, pid))
        prop_req_counts.sort()
        sparse_pid = prop_req_counts[0][1] if prop_req_counts else (plist[0].get("property_id") if plist else None)
        rich_pid = prop_req_counts[-1][1] if prop_req_counts else sparse_pid

        # Property Evidence Readiness
        prop_gen = generate_er(nancy_tok, "property", rich_pid)
        nancy["property_er"] = {"status": prop_gen.status_code, "property_id": rich_pid}
        if prop_gen.status_code == 200:
            nancy["property_er"]["inspect"] = inspect_evidence_readiness_pdf(prop_gen.content)
            aid = prop_gen.headers.get("x-artifact-id") or prop_gen.headers.get("X-Artifact-Id")
            if aid:
                b1, b2 = redownload_artifact(nancy_tok, aid)
                nancy["property_er"]["redownload_byte_equal"] = b1 == b2 == prop_gen.content
                nancy["property_er"]["artifact_id"] = aid

        # Sparse property
        sparse_gen = generate_er(nancy_tok, "property", sparse_pid)
        nancy["sparse_property_er"] = {"status": sparse_gen.status_code, "property_id": sparse_pid}
        if sparse_gen.status_code == 200:
            nancy["sparse_property_er"]["inspect"] = inspect_evidence_readiness_pdf(sparse_gen.content)

        # Portfolio (large portfolio when many properties)
        port_gen = generate_er(nancy_tok, "portfolio")
        nancy["portfolio_er"] = {"status": port_gen.status_code}
        if port_gen.status_code == 200:
            nancy["portfolio_er"]["inspect"] = inspect_evidence_readiness_pdf(port_gen.content)
            nancy["portfolio_er"]["large_portfolio"] = len(plist) >= 5

        # Audit Evidence Pack unchanged
        if rich_pid:
            pack_gen = httpx.post(
                f"{API}/client/compliance/audit-pack/generate",
                headers=hdr(nancy_tok),
                json={"property_id": rich_pid},
                timeout=300,
            )
            nancy["audit_pack"] = {"generate_status": pack_gen.status_code}
            if pack_gen.status_code == 200:
                pack_id = pack_gen.json().get("pack_id")
                d1 = httpx.get(
                    f"{API}/client/compliance/audit-pack/{pack_id}/download",
                    headers=hdr(nancy_tok),
                    timeout=300,
                )
                d2 = httpx.get(
                    f"{API}/client/compliance/audit-pack/{pack_id}/download",
                    headers=hdr(nancy_tok),
                    timeout=300,
                )
                if d1.status_code == 200:
                    nancy["audit_pack"]["inspect"] = inspect_audit_pack_zip(d1.content)
                    nancy["audit_pack"]["redownload_byte_equal"] = d1.content == d2.content

        # Legacy pack byte stability
        ld1 = httpx.get(
            f"{API}/client/compliance/audit-pack/{LEGACY_PACK_ID}/download",
            headers=hdr(nancy_tok),
            timeout=300,
        )
        ld2 = httpx.get(
            f"{API}/client/compliance/audit-pack/{LEGACY_PACK_ID}/download",
            headers=hdr(nancy_tok),
            timeout=300,
        )
        if ld1.status_code == 200 and ld2.status_code == 200:
            nancy["legacy_pack"] = {
                "redownload_byte_equal": ld1.content == ld2.content,
                "bytes": len(ld1.content),
                "sha256": sha256_bytes(ld1.content),
            }

    artifact["nancy_ops"] = nancy

    gates["property_evidence_readiness"] = {
        "pass": (nancy.get("property_er") or {}).get("inspect", {}).get("pass") is True,
        "detail": nancy.get("property_er"),
    }
    gates["portfolio_evidence_readiness"] = {
        "pass": (nancy.get("portfolio_er") or {}).get("inspect", {}).get("pass") is True,
        "detail": nancy.get("portfolio_er"),
    }
    gates["sparse_property_evidence_readiness"] = {
        "pass": (nancy.get("sparse_property_er") or {}).get("inspect", {}).get("pass") is True,
        "detail": nancy.get("sparse_property_er"),
    }
    gates["large_portfolio_evidence_readiness"] = {
        "pass": (nancy.get("portfolio_er") or {}).get("inspect", {}).get("pass") is True
        and (nancy.get("portfolio_er") or {}).get("large_portfolio") is True,
        "detail": {"property_count": nancy.get("property_count"), "portfolio_er": nancy.get("portfolio_er")},
    }
    gates["audit_pack_archive_wording"] = {
        "pass": (nancy.get("audit_pack") or {}).get("inspect", {}).get("pass") is True,
        "detail": nancy.get("audit_pack"),
    }
    gates["immutable_redownload_property_er"] = {
        "pass": (nancy.get("property_er") or {}).get("redownload_byte_equal") is True,
        "detail": (nancy.get("property_er") or {}).get("redownload_byte_equal"),
    }
    gates["legacy_pack_byte_stable"] = {
        "pass": (nancy.get("legacy_pack") or {}).get("redownload_byte_equal") is True,
        "detail": nancy.get("legacy_pack"),
    }

    all_pass = all(isinstance(v, dict) and v.get("pass") for v in gates.values())
    artifact["gates"] = gates
    artifact["all_gates_pass"] = all_pass
    artifact["push_safe"] = all_pass and gates.get("deploy_commit_matches", {}).get("pass")

    path = OUT / f"STAGING_EVIDENCE_READINESS_VERIFY_{RUN_TAG}.json"
    path.write_text(json.dumps(artifact, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": str(path),
                "all_gates_pass": all_pass,
                "commit_sha": commit,
                "gates": {k: v.get("pass") for k, v in gates.items()},
            },
            indent=2,
        )
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
