"""Access boundary — graph storage must not be imported outside graph service / emit."""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

CEG_ALLOWED_PREFIXES = (
    "services/compliance_evidence_graph/",
    "services/compliance_graph_service/",
    "services/compliance_intelligence/",
    "tests/",
)

CIE_STORAGE_ALLOWED_PREFIXES = (
    "services/compliance_intelligence_engine/",
    "tests/",
)

CIE_FORBIDDEN_AI_IMPORTS = (
    "utils.llm_chat",
    "openai",
    "anthropic",
    "services.compliance_intelligence.investigate",
    "services.compliance_intelligence.narrations",
)


def _imports_ceg_storage_module(file_path: Path) -> bool:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module.replace(".", "/")
            if "compliance_evidence_graph/storage" in mod or mod.endswith("storage/decisions"):
                rel = str(file_path.relative_to(BACKEND)).replace("\\", "/")
                if not any(rel.startswith(p) for p in CEG_ALLOWED_PREFIXES):
                    return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "compliance_evidence_graph.storage" in (alias.name or ""):
                    rel = str(file_path.relative_to(BACKEND)).replace("\\", "/")
                    if not any(rel.startswith(p) for p in CEG_ALLOWED_PREFIXES):
                        return True
    return False


def _imports_cie_internal_module(file_path: Path, module_fragment: str) -> bool:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    rel = str(file_path.relative_to(BACKEND)).replace("\\", "/")
    if any(rel.startswith(p) for p in CIE_STORAGE_ALLOWED_PREFIXES):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if module_fragment in node.module:
                return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if module_fragment in (alias.name or ""):
                    return True
    return False


def _imports_cie_storage_module(file_path: Path) -> bool:
    return _imports_cie_internal_module(file_path, "compliance_intelligence_engine.storage")


def _file_imports_forbidden_ai(file_path: Path) -> list[str]:
    try:
        text = file_path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except Exception:
        return []
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for forbidden in CIE_FORBIDDEN_AI_IMPORTS:
                if node.module == forbidden or node.module.startswith(forbidden + "."):
                    hits.append(forbidden)
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in CIE_FORBIDDEN_AI_IMPORTS:
                    if (alias.name or "") == forbidden or (alias.name or "").startswith(forbidden + "."):
                        hits.append(forbidden)
    return hits


# --- CEG boundaries (regression) ---


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
        if py.name in ("compliance_graph.py", "compliance_intelligence.py"):
            continue
        if _imports_ceg_storage_module(py):
            violations.append(str(py.relative_to(BACKEND)))
    assert violations == [], f"Unauthorized graph storage imports: {violations}"


def test_intelligence_package_no_storage_imports():
    pkg = BACKEND / "services" / "compliance_intelligence"
    violations = []
    for py in pkg.glob("*.py"):
        rel = str(py.relative_to(BACKEND)).replace("\\", "/")
        if rel.startswith("services/compliance_intelligence/"):
            content = py.read_text(encoding="utf-8")
            if "compliance_evidence_graph.storage" in content:
                violations.append(rel)
    assert violations == [], f"Intelligence package must not import graph storage: {violations}"


def test_compliance_intelligence_route_no_storage_imports():
    routes_file = BACKEND / "routes" / "compliance_intelligence.py"
    content = routes_file.read_text(encoding="utf-8")
    assert "compliance_evidence_graph.storage" not in content
    assert "compliance_intelligence" in content


# --- CIE storage boundaries ---


def test_no_cie_route_module_exists():
    cie_route = BACKEND / "routes" / "compliance_intelligence_engine.py"
    assert not cie_route.exists(), "CIE-1 must not add customer-facing routes"


def test_routes_do_not_import_cie_storage():
    violations = []
    for py in (BACKEND / "routes").glob("*.py"):
        if _imports_cie_storage_module(py):
            violations.append(str(py.relative_to(BACKEND)))
    assert violations == [], f"Routes must not import CIE storage: {violations}"


def test_intelligence_service_does_not_import_cie_storage():
    pkg = BACKEND / "services" / "compliance_intelligence_service"
    violations = []
    for py in pkg.rglob("*.py"):
        if _imports_cie_storage_module(py):
            violations.append(str(py.relative_to(BACKEND)))
    assert violations == [], f"ISL must not import CIE storage: {violations}"


def test_intelligence_service_does_not_import_cie_registry():
    pkg = BACKEND / "services" / "compliance_intelligence_service"
    violations = []
    for py in pkg.rglob("*.py"):
        if _imports_cie_internal_module(py, "compliance_intelligence_engine.registry"):
            violations.append(str(py.relative_to(BACKEND)))
    assert violations == [], f"ISL must not import CIE registry: {violations}"


def test_phase5_ai_package_does_not_import_cie_storage():
    pkg = BACKEND / "services" / "compliance_intelligence"
    violations = []
    for py in pkg.glob("*.py"):
        if _imports_cie_storage_module(py):
            violations.append(str(py.relative_to(BACKEND)))
    assert violations == [], f"Phase 5 AI package must not import CIE storage: {violations}"


def test_cie_packages_no_ai_imports():
    violations = []
    for pkg_name in ("compliance_intelligence_engine", "compliance_intelligence_service"):
        pkg = BACKEND / "services" / pkg_name
        for py in pkg.rglob("*.py"):
            hits = _file_imports_forbidden_ai(py)
            if hits:
                violations.append(f"{py.relative_to(BACKEND)}: {hits}")
    assert violations == [], f"CIE packages must not import AI modules: {violations}"


def test_cie_engine_public_init_no_storage_exports():
    init_file = BACKEND / "services" / "compliance_intelligence_engine" / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    assert "storage" not in content
