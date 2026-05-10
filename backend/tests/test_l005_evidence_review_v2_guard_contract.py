"""L-005: every Evidence Review V2 HTTP handler calls _v2_guard() before auth or I/O."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

import pytest


def _evidence_review_py_path() -> Path:
    return Path(__file__).resolve().parent.parent / "routes" / "evidence_review.py"


def _decorator_targets_router_http(dec: ast.expr) -> bool:
    func: ast.expr = dec
    if isinstance(dec, ast.Call):
        func = dec.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "router":
        return func.attr in ("get", "post", "put", "delete", "patch", "options", "head")
    return False


def _first_executable_statement(body: List[ast.stmt]) -> Optional[ast.stmt]:
    idx = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            idx = 1
    if idx >= len(body):
        return None
    return body[idx]


def _is_v2_guard_expr(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.Expr):
        return False
    val = stmt.value
    if not isinstance(val, ast.Call):
        return False
    fn = val.func
    return isinstance(fn, ast.Name) and fn.id == "_v2_guard"


def test_every_router_handler_in_evidence_review_calls_v2_guard_first():
    path = _evidence_review_py_path()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        if not any(_decorator_targets_router_http(d) for d in node.decorator_list):
            continue
        first = _first_executable_statement(node.body)
        if first is None or not _is_v2_guard_expr(first):
            offenders.append(node.name)
    assert not offenders, (
        "Each @router handler in routes/evidence_review.py must call _v2_guard() as the first "
        f"statement after any docstring. Offenders: {offenders}"
    )


@pytest.mark.asyncio
async def test_admin_dashboard_includes_evidence_review_v2_server_flag():
    """GET /admin/dashboard exposes server_feature_flags.evidence_review_v2_enabled (L-005 admin UI gate)."""
    import os
    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi import Request
    from routes.admin import get_admin_dashboard

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    db = MagicMock()
    db.clients = MagicMock()
    db.clients.count_documents = AsyncMock(return_value=0)
    db.properties = MagicMock()
    db.properties.count_documents = AsyncMock(return_value=0)
    db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    db.documents = MagicMock()
    db.documents.count_documents = AsyncMock(return_value=0)
    db.job_runs = MagicMock()
    db.job_runs.count_documents = AsyncMock(return_value=0)
    db.provisioning_jobs = MagicMock()
    db.provisioning_jobs.count_documents = AsyncMock(return_value=0)
    db.requirements = MagicMock()
    db.requirements.count_documents = AsyncMock(return_value=0)

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock), patch(
        "routes.admin.database.get_db", return_value=db
    ):
        with patch.dict(os.environ, {"FEATURE_EVIDENCE_REVIEW_V2": "1"}, clear=False):
            on = await get_admin_dashboard(request)
        with patch.dict(os.environ, {"FEATURE_EVIDENCE_REVIEW_V2": "0"}, clear=False):
            off = await get_admin_dashboard(request)

    assert on["server_feature_flags"]["evidence_review_v2_enabled"] is True
    assert off["server_feature_flags"]["evidence_review_v2_enabled"] is False
