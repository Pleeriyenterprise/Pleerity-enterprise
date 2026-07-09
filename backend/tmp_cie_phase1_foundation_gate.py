"""CIE-1 foundation local validation gate."""
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


async def _validate_isl_envelopes() -> Dict[str, Any]:
    from services.compliance_graph_service.access import ActorContext
    from services.compliance_intelligence_service import generate_recommendations, get_intelligence

    actor = ActorContext(is_admin=False, client_id="client-gate")
    disabled = await generate_recommendations(actor=actor)
    get_stub = await get_intelligence(artefact_id="cia_gate", actor=actor)
    return {
        "disabled_generate": disabled,
        "disabled_get": get_stub,
    }


def main() -> int:
    from services.compliance_intelligence_engine.config import intelligence_engine_mode
    from services.compliance_intelligence_engine.hashing import sha256_digest
    from services.compliance_intelligence_engine.validation import validate_artefact_dict

    report: Dict[str, Any] = {
        "programme": "CIE-1-FOUNDATION-LOCAL-VALIDATION-GATE",
        "run_tag": RUN_TAG,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
        "sections": {},
    }

    def add(name: str, passed: bool, **detail):
        row = {"name": name, "passed": passed}
        row.update({k: v for k, v in detail.items() if k not in ("passed", "name")})
        report["checks"].append(row)

    t0 = time.perf_counter()

    # Feature flag default
    os.environ.pop("COMPLIANCE_INTELLIGENCE_ENGINE_MODE", None)
    mode = intelligence_engine_mode()
    add("feature_flag_defaults_disabled", mode == "disabled", mode=mode)

    # Deterministic hashing
    h1 = sha256_digest({"a": 1, "b": 2})
    h2 = sha256_digest({"b": 2, "a": 1})
    add("hashing_deterministic", h1 == h2, digest=h1)

    # Artefact schema
    sample = {
        "artefact_type": "recommendation",
        "client_id": "client-gate",
        "scope": {
            "client_id": "client-gate",
            "portfolio_root": True,
        },
        "inputs_hash": h1,
        "response_hash": h2,
        "insufficient_evidence": True,
        "payload": {},
    }
    ok, errors = validate_artefact_dict(sample)
    add("artefact_schema_validates", ok, errors=errors)

    # No CIE routes
    cie_route = BACKEND / "routes" / "compliance_intelligence_engine.py"
    add("no_customer_facing_cie_routes", not cie_route.exists())

    # No production flag in render.yaml
    render_yaml = BACKEND.parent / "render.yaml"
    prod_flag_changed = False
    if render_yaml.exists():
        text = render_yaml.read_text(encoding="utf-8")
        prod_flag_changed = "COMPLIANCE_INTELLIGENCE_ENGINE_MODE" in text
    add("no_production_cie_flag_in_render", not prod_flag_changed)

    # ISL envelopes
    import asyncio

    isl = asyncio.run(_validate_isl_envelopes())
    add(
        "isl_disabled_unavailable_envelope",
        isl["disabled_generate"].get("enabled") is False
        and isl["disabled_generate"].get("reason") == "COMPLIANCE_INTELLIGENCE_ENGINE_MODE_DISABLED",
        envelope=isl["disabled_generate"],
    )
    add(
        "isl_get_disabled_safe",
        isl["disabled_get"].get("enabled") is False,
        envelope=isl["disabled_get"],
    )

    # Storage bootstrap safe (stubs raise)
    async def _storage_stub_check():
        from services.compliance_intelligence_engine.storage import artefacts

        try:
            await artefacts.insert_artefact(None, {})
            return False
        except NotImplementedError:
            return True

    add("storage_bootstrap_safe_stub", asyncio.run(_storage_stub_check()))

    # No domain engines module
    engines_dir = BACKEND / "services" / "compliance_intelligence_engine" / "engines"
    add("no_domain_engines_package", not engines_dir.exists())

    # Pytest suites
    cie_tests = _run_pytest(
        [
            "tests/test_compliance_intelligence_engine_cie1.py",
            "tests/test_graph_service_access_boundary.py",
        ]
    )
    add("cie_pytest_suite", cie_tests["exit_code"] == 0, pytest=cie_tests)

    ceg_regression = _run_pytest(
        [
            "tests/test_compliance_graph_service.py",
            "tests/test_compliance_graph_service_phase3.py",
        ]
    )
    add("ceg_regression_pytest", ceg_regression["exit_code"] == 0, pytest=ceg_regression)

    report["sections"]["isl_envelopes"] = isl
    report["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    report["verdict"] = (
        "CIE_1_FOUNDATION_VALIDATED"
        if all(c["passed"] for c in report["checks"])
        else "CIE_1_FOUNDATION_BLOCKED"
    )

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "CIE_1_RUNTIME_VALIDATION.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "path": str(out_path)}, indent=2))
    return 0 if report["verdict"] == "CIE_1_FOUNDATION_VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
