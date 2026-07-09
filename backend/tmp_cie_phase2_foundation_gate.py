"""CIE-2 recommendation + priority foundation local validation gate."""
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


async def _validate_generation() -> Dict[str, Any]:
    from unittest.mock import AsyncMock, MagicMock, patch

    from services.compliance_graph_service.access import ActorContext
    from services.compliance_intelligence_service import generate_recommendations

    from tests.test_compliance_intelligence_engine_cie2 import SAMPLE_GRAPH_ENV, _FakeDB

    db = _FakeDB()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda name: db.artefacts if "artefacts" in name else db.provenance)
    os.environ["COMPLIANCE_INTELLIGENCE_ENGINE_MODE"] = "enabled"
    with (
        patch(
            "services.compliance_intelligence_engine.engines.recommendation.engine.fetch_graph_envelope",
            new_callable=AsyncMock,
            return_value=SAMPLE_GRAPH_ENV,
        ),
        patch("services.compliance_intelligence_engine.storage.artefacts.database.get_db", return_value=mock_db),
        patch("services.compliance_intelligence_engine.storage.provenance.database.get_db", return_value=mock_db),
    ):
        result = await generate_recommendations(actor=ActorContext(is_admin=False, client_id="client-cie1"))
    return {
        "artefact_count": len(result.get("artefacts") or []),
        "has_provenance": all(
            (a.get("provenance_id") or "").startswith("cip_") for a in (result.get("artefacts") or [])
        ),
        "engine_version": result.get("engine_version"),
    }


def main() -> int:
    from services.compliance_intelligence_engine.config import intelligence_engine_mode
    from services.compliance_intelligence_engine.constants import ENGINE_VERSION
    from services.compliance_intelligence_engine.provenance_validation import validate_all_registry_seeds_v1

    report: Dict[str, Any] = {
        "programme": "CIE-2-RECOMMENDATION-AND-PRIORITY-FOUNDATION-LOCAL-VALIDATION-GATE",
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
    add("engine_version_cie2", ENGINE_VERSION == "cie-2.0.0", version=ENGINE_VERSION)

    engines_dir = BACKEND / "services" / "compliance_intelligence_engine" / "engines"
    add("domain_engines_package_exists", engines_dir.exists())
    add(
        "recommendation_engine_exists",
        (engines_dir / "recommendation" / "engine.py").exists(),
    )
    add("priority_engine_exists", (engines_dir / "priority" / "engine.py").exists())

    ok_seeds, seed_errors = validate_all_registry_seeds_v1()
    add("registry_v1_seeds_validate", ok_seeds, errors=seed_errors)

    add("no_cie_route", not (BACKEND / "routes" / "compliance_intelligence_engine.py").exists())

    render_yaml = BACKEND.parent / "render.yaml"
    prod_flag = False
    if render_yaml.exists():
        prod_flag = "COMPLIANCE_INTELLIGENCE_ENGINE_MODE" in render_yaml.read_text(encoding="utf-8")
    add("no_production_cie_flag_in_render", not prod_flag)

    import asyncio

    gen = asyncio.run(_validate_generation())
    add(
        "recommendation_generation_with_provenance",
        gen["artefact_count"] >= 1 and gen["has_provenance"],
        detail=gen,
    )

    cie_tests = _run_pytest(
        [
            "tests/test_compliance_intelligence_engine_cie1.py",
            "tests/test_compliance_intelligence_engine_cie1_5.py",
            "tests/test_compliance_intelligence_engine_cie2.py",
            "tests/test_graph_service_access_boundary.py",
        ]
    )
    add("cie_pytest_suite", cie_tests["exit_code"] == 0, pytest=cie_tests)

    report["sections"] = {"generation": gen}
    report["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    report["verdict"] = (
        "CIE_2_FOUNDATION_VALIDATED"
        if all(c["passed"] for c in report["checks"])
        else "CIE_2_FOUNDATION_BLOCKED"
    )

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "CIE_2_RUNTIME_VALIDATION.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "path": str(out_path)}, indent=2))
    return 0 if report["verdict"] == "CIE_2_FOUNDATION_VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
