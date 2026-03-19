"""
Bootstrap Prompt Manager for non-CVP document generation services.

What it does (in order):
1) Backup existing prompt_templates rows to JSON
2) Seed services + prompts from seed_data_v1.json with activation enabled
3) Verify required ACTIVE prompts exist for non-CVP services

Usage:
  python -m scripts.bootstrap_prompt_manager
  python -m scripts.bootstrap_prompt_manager --skip-backup
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import database  # noqa: E402
from scripts import seed_services_and_prompts  # noqa: E402


EXPECTED: Dict[str, Set[str]] = {
    "AI_WF_BLUEPRINT": {"AI_WF_BLUEPRINT"},
    "AI_PROC_MAP": {"BUSINESS_PROCESS_MAPPING"},
    "AI_TOOL_RECOMMENDATION": {"AI_TOOL_RECOMMENDATION_REPORT"},
    "MR_BASIC": {"MARKET_RESEARCH_BASIC"},
    "MR_ADV": {"MARKET_RESEARCH_ADVANCED"},
    "HMO_COMPLIANCE_AUDIT": {"HMO_COMPLIANCE_AUDIT_REPORT"},
    "FULL_COMPLIANCE_AUDIT": {"FULL_COMPLIANCE_AUDIT_REPORT"},
    "MOVE_IN_OUT_CHECKLIST": {"MOVE_IN_MOVE_OUT_CHECKLIST"},
    "DOC_PACK_ESSENTIAL": {
        "RENT_ARREARS_LETTER",
        "DEPOSIT_REFUND_EXPLANATION_LETTER",
        "TENANT_REFERENCE_LETTER",
        "RENT_RECEIPT",
        "GDPR_NOTICE",
    },
    "DOC_PACK_PLUS": {
        "TENANCY_AGREEMENT_AST",
        "TENANCY_RENEWAL",
        "NOTICE_TO_QUIT",
        "GUARANTOR_AGREEMENT",
        "RENT_INCREASE_NOTICE",
    },
    "DOC_PACK_PRO": {
        "INVENTORY_CONDITION_REPORT",
        "DEPOSIT_INFORMATION_PACK",
        "PROPERTY_ACCESS_NOTICE",
        "ADDITIONAL_LANDLORD_NOTICE",
    },
    # Keep tenancy orchestrator prompt check explicit if used in your flow.
    "DOC_PACK_TENANCY": {"DOC_PACK_ORCHESTRATOR"},
}


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


async def backup_prompt_templates(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"prompt_templates_backup_{_now_tag()}.json"
    await database.connect()
    db = database.get_db()
    rows = await db.prompt_templates.find({}, {"_id": 0}).to_list(length=20000)
    await database.close()
    out_path.write_text(json.dumps(rows, default=str, indent=2), encoding="utf-8")
    return out_path


async def verify_active_prompts() -> Dict[str, object]:
    await database.connect()
    db = database.get_db()
    cursor = db.prompt_templates.find(
        {"status": "ACTIVE"},
        {"_id": 0, "service_code": 1, "doc_type": 1, "template_id": 1, "version": 1},
    )
    active: Dict[str, Set[str]] = {}
    async for row in cursor:
        svc = row.get("service_code")
        dt = row.get("doc_type")
        if not svc or not dt:
            continue
        active.setdefault(svc, set()).add(dt)
    await database.close()

    missing: Dict[str, List[str]] = {}
    counts: Dict[str, Dict[str, int]] = {}
    for svc, required in EXPECTED.items():
        have = active.get(svc, set())
        miss = sorted(required - have)
        counts[svc] = {"required": len(required), "active_found": len(have)}
        if miss:
            missing[svc] = miss
    return {"ok": not bool(missing), "missing": missing, "counts": counts}


async def run(skip_backup: bool = False) -> int:
    print("\n=== Prompt Manager Bootstrap ===")
    print("Step 1/3: Backup current prompt_templates")
    if skip_backup:
        print("  - Skipped backup (--skip-backup)")
    else:
        backup_path = await backup_prompt_templates(Path("backups"))
        print(f"  - Backup written: {backup_path}")

    print("Step 2/3: Seed services + prompts (forced activation)")
    os.environ["SEED_ACTIVATE"] = "true"
    await seed_services_and_prompts.run()

    print("Step 3/3: Verify required ACTIVE prompts")
    report = await verify_active_prompts()
    print(json.dumps(report, indent=2))

    if report["ok"]:
        print("\nResult: PASS - Prompt Manager is ready for non-CVP generation.")
        return 0
    print("\nResult: FAIL - Missing ACTIVE prompts detected.")
    print("Action: Activate or seed the missing service_code/doc_type combinations above.")
    return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap Prompt Manager with backup + seed + verify.")
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip JSON backup export of prompt_templates",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(asyncio.run(run(skip_backup=args.skip_backup)))
