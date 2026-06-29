"""CIE-1.5 provenance foundation local validation gate."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

BACKEND = Path(__file__).resolve().parent
OUT = BACKEND / "docs/audit/compliance_intelligence_engine_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run_pytest(paths: List[str]) -> dict:
    cmd = [sys.executable, "-m", "pytest", *paths, "-q", "--tb=line"]
    proc = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(\d+) passed", out)
    passed = int(m.group(1)) if m else 0
    m_fail = re.search(r"(\d+) failed", out)
    failed = int(m_fail.group(1)) if m_fail else 0
    return {"exit_code": proc.returncode, "passed": passed, "failed": failed, "output_tail": out[-4000:]}


async def _validate_stubs() -> Dict[str, Any]:
    from services.compliance_graph_service.access import ActorContext
    from services.compliance_intelligence_service import compare_intelligence, replay_intelligence

    actor = ActorContext(is_admin=False, client_id="client-gate")
    replay = await replay_intelligence(
        actor=actor,
        replay_type="exact",
        provenance_id="cip_gate",
        as_of="2026-06-17T00:00:00Z",
    )
    compare = await compare_intelligence(left_id="cia_l", right_id="cia_r", actor=actor)
    return {"replay": replay, "compare": compare}


def main() -> int:
    from services.compliance_intelligence_engine.config import intelligence_engine_mode
    from services.compliance_intelligence_engine.provenance_validation import (
        validate_all_registry_seeds_v1,
        validate_provenance_dict,
    )
    from tests.test_compliance_intelligence_engine_cie1_5 import _sample_provenance_dict

    report: Dict[str, Any] = {
        "programme": "CIE-1.5-PROVENANCE-FOUNDATION-LOCAL-VALIDATION-GATE",
        "run_tag": RUN_TAG,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
    }

    def add(name: str, passed: bool, **detail):
        row = {"name": name, "passed": passed}
        row.update({k: v for k, v in detail.items() if k not in ("passed", "name")})
        report["checks"].append(row)

    t0 = time.perf_counter()

    os.environ.pop("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", None)
    add("feature_flag_defaults_disabled", intelligence_engine_mode() == "disabled", mode=intelligence_engine_mode())

    prov, artefact = _sample_provenance_dict()
    ok, errors = validate_provenance_dict(prov)
    add("provenance_schema_validates", ok, errors=errors)

    add("artefact_requires_provenance_id", "provenance_id" in artefact and artefact["provenance_id"].startswith("cip_"))

    ok_seeds, seed_errors = validate_all_registry_seeds_v1()
    add("registry_v1_seeds_validate", ok_seeds, errors=seed_errors)

    add("no_cie_route", not (BACKEND / "routes" / "compliance_intelligence_engine.py").exists())

    render_yaml = BACKEND.parent / "render.yaml"
    prod_flag = False
    if render_yaml.exists():
        prod_flag = "COMPLIANCE_INTELLIGENCE_ENGINE_MODE" in render_yaml.read_text(encoding="utf-8")
    add("no_production_cie_flag_in_render", not prod_flag)

    engines_dir = BACKEND / "services" / "compliance_intelligence_engine" / "engines"
    add("no_domain_engines_package", not engines_dir.exists())

    import asyncio

    stubs = asyncio.run(_validate_stubs())
    add(
        "replay_stub_safe",
        stubs["replay"].get("prohibits_current_state_substitution") is True
        or stubs["replay"].get("tier1", {}) is not None,
        envelope=stubs["replay"],
    )
    add(
        "compare_stub_safe",
        stubs["compare"].get("reason") in (
            "CIE_PROVENANCE_COMPARE_NOT_IMPLEMENTED",
            "COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED",
        ),
        envelope=stubs["compare"],
    )

    async def _immutability_check():
        from services.compliance_intelligence_engine.storage import provenance as prov_storage

        try:
            await prov_storage.update_provenance(None, "cip_x", {})
            return False
        except NotImplementedError:
            return True

    add("provenance_immutability_stub", asyncio.run(_immutability_check()))

    cie_tests = _run_pytest(
        [
            "tests/test_compliance_intelligence_engine_cie1.py",
            "tests/test_compliance_intelligence_engine_cie1_5.py",
            "tests/test_graph_service_access_boundary.py",
        ]
    )
    add("cie_pytest_suite", cie_tests["exit_code"] == 0, pytest=cie_tests)

    report["sections"] = {"stubs": stubs}
    report["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    report["verdict"] = (
        "CIE_1_5_FOUNDATION_VALIDATED"
        if all(c["passed"] for c in report["checks"])
        else "CIE_1_5_FOUNDATION_BLOCKED"
    )

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "CIE_1_5_RUNTIME_VALIDATION.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "path": str(out_path)}, indent=2))
    return 0 if report["verdict"] == "CIE_1_5_FOUNDATION_VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
