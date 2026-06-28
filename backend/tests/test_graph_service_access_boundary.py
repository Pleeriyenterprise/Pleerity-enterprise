"""Access boundary — graph storage must not be imported outside graph service / emit."""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ALLOWED_PREFIXES = (
    "services/compliance_evidence_graph/",
    "services/compliance_graph_service/",
    "tests/",
)


def _imports_storage_module(file_path: Path) -> bool:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.replace(".", "/")
            if "compliance_evidence_graph/storage" in mod or mod.endswith("storage/decisions"):
                rel = str(file_path.relative_to(BACKEND)).replace("\\", "/")
                if not any(rel.startswith(p) for p in ALLOWED_PREFIXES):
                    return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "compliance_evidence_graph.storage" in (alias.name or ""):
                    rel = str(file_path.relative_to(BACKEND)).replace("\\", "/")
                    if not any(rel.startswith(p) for p in ALLOWED_PREFIXES):
                        return True
    return False


def test_routes_do_not_import_graph_storage():
    routes_file = BACKEND / "routes" / "compliance_graph.py"
    content = routes_file.read_text(encoding="utf-8")
    assert "compliance_evidence_graph.storage" not in content
    assert "compliance_graph_service" in content


def test_graph_service_does_not_expose_storage_in_public_init():
    init_file = BACKEND / "services" / "compliance_graph_service" / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    assert "storage" not in content


def test_no_unauthorized_storage_imports_in_routes():
    violations = []
    for py in (BACKEND / "routes").glob("*.py"):
        if py.name == "compliance_graph.py":
            continue
        if _imports_storage_module(py):
            violations.append(str(py.relative_to(BACKEND)))
    assert violations == [], f"Unauthorized graph storage imports: {violations}"
