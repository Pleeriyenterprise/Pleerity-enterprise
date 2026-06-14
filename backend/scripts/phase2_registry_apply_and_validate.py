"""
Phase 2: backup production registry v1, apply coverage repair, validate pilot client.
Approved ops script — registry singleton only (no customer requirement mutations).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

PLACEHOLDER = "Draft placeholder: replace with a concise client-facing reason"
PILOT_CLIENT = "a169ee0c-3fd4-42d4-a2a6-8144bc833716"
PROP_A = "817a44d1-309f-44ab-98e1-46b5fa51d895"
PROP_B = "503e3aab-f443-4e7a-80e7-5347277b56f1"
OUT_DIR = ROOT / "docs" / "audit" / "phase2_registry_repair"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def main() -> int:
    from motor.motor_asyncio import AsyncIOMotorClient
    from database import database
    from services.compliance_registry_publish_service import COLLECTION_PUBLISHED, SINGLETON_KEY
    from services.compliance_registry_admin_service import REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER

    uri = os.getenv("MONGO_URI") or os.getenv("MONGO_URL")
    if not uri:
        print(json.dumps({"error": "MONGO_URI not set"}))
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {"started_at": _utc(), "steps": []}

    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=20000)
    prod_db = client["pleerity_production"]
    await prod_db.command("ping")

    # --- Backup v1 ---
    v1_doc = await prod_db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0})
    backup_path = OUT_DIR / f"production_registry_v1_backup_{_utc().replace(':', '').replace('-', '')}.json"
    backup_path.write_text(json.dumps(v1_doc, indent=2, default=str), encoding="utf-8")
    report["steps"].append({"backup_v1": str(backup_path), "version": (v1_doc or {}).get("version")})

    # --- Apply repair (subprocess avoids database.close() from repair script) ---
    import subprocess

    env = os.environ.copy()
    env["MONGO_URL"] = uri
    env["DB_NAME"] = "pleerity_production"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "repair_published_registry_coverage.py"), "--apply"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    apply_stdout = proc.stdout.strip()
    apply_stderr = proc.stderr.strip()
    report["steps"].append(
        {
            "repair_apply_exit_code": proc.returncode,
            "repair_stdout": apply_stdout,
            "repair_stderr": apply_stderr,
        }
    )
    if proc.returncode != 0:
        out_path = OUT_DIR / "production_apply_validation.json"
        out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(json.dumps(report, indent=2, default=str))
        client.close()
        return proc.returncode

    database.db = prod_db
    database.client = client

    # --- Registry validation ---
    pub = await prod_db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0})
    entries = (pub or {}).get("entries") or {}
    placeholder_count = sum(
        1
        for e in entries.values()
        if PLACEHOLDER in str((e or {}).get("why_it_matters_short") or "")
        or str((e or {}).get("why_it_matters_short") or "").strip() == REGISTRY_WHY_SHORT_MANUAL_PLACEHOLDER
    )
    hist = await prod_db["compliance_requirement_registry_published_history"].find(
        {"published_line_version": (pub or {}).get("version")}, {"_id": 0}
    ).sort("recorded_at", -1).limit(1).to_list(1)

    report["registry"] = {
        "version": (pub or {}).get("version"),
        "entry_count": len(entries),
        "placeholder_count": placeholder_count,
        "last_activation_kind": (pub or {}).get("last_activation_kind"),
        "updated_at": (pub or {}).get("updated_at"),
        "history_row_present": bool(hist),
        "history_activation_kind": (hist[0] or {}).get("activation_kind") if hist else None,
    }

    # --- Pilot validation via catalog ---
    from services.catalog_compliance import get_property_compliance_detail, get_portfolio_compliance_from_catalog

    database.db = prod_db

    async def _prop_check(pid: str, name: str) -> dict:
        detail = await get_property_compliance_detail(PILOT_CLIENT, pid)
        kpis = (detail or {}).get("kpis") or {}
        matrix = (detail or {}).get("matrix") or []
        status_valid_filter = [
            m.get("requirement_id")
            for m in matrix
            if str(m.get("status") or "").upper() in ("COMPLIANT", "VALID")
        ]
        placeholders = [
            m.get("requirement_code")
            for m in matrix
            if PLACEHOLDER in str(m.get("why_it_matters_short") or "")
        ]
        editorial_samples = [
            {
                "code": m.get("requirement_code"),
                "why_short": (str(m.get("why_it_matters_short") or "")[:120]),
            }
            for m in matrix[:3]
        ]
        return {
            "property_id": pid,
            "name": name,
            "status_valid_kpi": kpis.get("status_valid"),
            "compliant_kpi": kpis.get("compliant"),
            "valid_filter_count": len(status_valid_filter),
            "valid_filter_ids": status_valid_filter,
            "placeholder_matrix_codes": placeholders,
            "editorial_samples": editorial_samples,
            "parity_ok": kpis.get("status_valid") == len(status_valid_filter),
        }

    report["pilot"] = {
        "client_id": PILOT_CLIENT,
        "cliftonwood": await _prop_check(PROP_A, "Cliftonwood Cottage"),
        "barbican": await _prop_check(PROP_B, "Barbican Harbour Flat"),
    }

    portfolio = await get_portfolio_compliance_from_catalog(PILOT_CLIENT)
    report["portfolio_summary"] = {
        "ok": portfolio is not None,
        "kpis_keys": sorted(((portfolio or {}).get("kpis") or {}).keys()),
        "has_status_valid": "status_valid" in ((portfolio or {}).get("kpis") or {}),
    }

    report["finished_at"] = _utc()
    report["go_gates"] = {
        "registry_version_2": report["registry"].get("version") == 2,
        "registry_placeholder_zero": placeholder_count == 0,
        "registry_entries_19": len(entries) == 19,
        "registry_activation_coverage_repair": report["registry"].get("last_activation_kind") == "coverage_repair",
        "cliftonwood_valid_parity": report["pilot"]["cliftonwood"]["parity_ok"]
        and report["pilot"]["cliftonwood"]["status_valid_kpi"] == 0,
        "cliftonwood_no_placeholders": len(report["pilot"]["cliftonwood"]["placeholder_matrix_codes"]) == 0,
        "barbican_valid_parity": report["pilot"]["barbican"]["parity_ok"]
        and report["pilot"]["barbican"]["status_valid_kpi"] == 3,
        "barbican_no_placeholders": len(report["pilot"]["barbican"]["placeholder_matrix_codes"]) == 0,
    }

    out_path = OUT_DIR / "production_apply_validation.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    client.close()
    return 0 if proc.returncode == 0 else proc.returncode


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
