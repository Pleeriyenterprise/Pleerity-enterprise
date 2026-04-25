"""
Machine-readable authority-consumption proof for operational subsystems.

Uses AST (not substring markers) to verify each subsystem file references the
expected authority/expiry helpers by actual call names.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent


def _callable_names(tree: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _import_from_hits(tree: ast.AST, *needles: str) -> List[str]:
    """Return module strings from ImportFrom that contain any needle."""
    hits: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            m = node.module
            if any(n in m for n in needles):
                hits.append(m)
    return hits


def _check_file(
    path: str,
    *,
    required_calls: Sequence[str],
    import_from_contains: Optional[Tuple[str, ...]] = None,
) -> Dict[str, object]:
    fp = ROOT / path
    exists = fp.exists()
    missing_calls: List[str] = []
    missing_imports: List[str] = []
    calls: Set[str] = set()
    if exists:
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(txt)
            calls = _callable_names(tree)
            missing_calls = [x for x in required_calls if x not in calls]
            if import_from_contains:
                hits = _import_from_hits(tree, *import_from_contains)
                if not hits:
                    missing_imports = list(import_from_contains)
        except SyntaxError as e:
            return {
                "path": path,
                "exists": True,
                "ok": False,
                "error": f"syntax_error: {e}",
                "required_calls": list(required_calls),
                "missing_calls": list(required_calls),
                "missing_import_from": list(import_from_contains or ()),
            }
    else:
        missing_calls = list(required_calls)
    ok = exists and not missing_calls and (not import_from_contains or not missing_imports)
    return {
        "path": path,
        "exists": exists,
        "ok": ok,
        "required_calls": list(required_calls),
        "missing_calls": missing_calls,
        "import_from_contains": list(import_from_contains or ()),
        "missing_import_from": missing_imports,
        "calls_found_sample": sorted(c for c in calls if c in set(required_calls))[:12],
    }


def run() -> Dict[str, object]:
    auth_mod = "requirement_evidence_authority"
    exp_mod = "expiry_utils"
    checks = {
        "reminders": _check_file(
            "services/reminder_truth_service.py",
            required_calls=["get_effective_expiry_date", "authority_runtime_requirement_status"],
            import_from_contains=(auth_mod, exp_mod),
        ),
        "scoring": _check_file(
            "services/compliance_scoring_v2.py",
            required_calls=["map_authority_to_scoring_status"],
            import_from_contains=(auth_mod,),
        ),
        "gap_detection": _check_file(
            "services/lead_automation_service.py",
            required_calls=["authority_gap_missing_states"],
            import_from_contains=(auth_mod,),
        ),
        "today": _check_file(
            "services/client_priority_stream.py",
            required_calls=["get_effective_expiry_date"],
            import_from_contains=(exp_mod, auth_mod),
        ),
        "command_centre": _check_file(
            "services/command_center_service.py",
            required_calls=["get_unified_tasks_for_client"],
            import_from_contains=(),
        ),
        "command_centre_authority_delegate": _check_file(
            "services/unified_tasks_service.py",
            required_calls=["authority_runtime_requirement_status"],
            import_from_contains=(auth_mod,),
        ),
        "monthly_digest": _check_file(
            "services/monthly_digest_assembly_service.py",
            required_calls=["get_effective_expiry_date", "authority_runtime_requirement_status"],
            import_from_contains=(auth_mod, exp_mod),
        ),
        "reports": _check_file(
            "services/reporting_service.py",
            required_calls=["get_effective_expiry_date", "authority_runtime_requirement_status"],
            import_from_contains=(auth_mod, exp_mod),
        ),
        "admin_queues": _check_file(
            "routes/admin.py",
            required_calls=["sync_requirement_evidence_authority", "normalize_document_evidence_scope"],
            import_from_contains=(auth_mod,),
        ),
        "client_document_views": _check_file(
            "routes/documents.py",
            required_calls=["normalize_document_evidence_scope"],
            import_from_contains=(auth_mod,),
        ),
        "portfolio_route": _check_file(
            "routes/portfolio.py",
            required_calls=["get_computed_status", "get_effective_expiry_date"],
            import_from_contains=(exp_mod,),
        ),
        "tenant_route": _check_file(
            "routes/tenant.py",
            required_calls=["get_computed_status", "get_effective_expiry_date"],
            import_from_contains=(exp_mod,),
        ),
    }
    ok = all(bool(v.get("ok")) for v in checks.values())
    return {"ok": ok, "subsystems": checks, "proof_mode": "ast_calls_and_import_from"}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
