"""
Operational Evidence Platform — correlation spine via request/job-scoped context.

Downstream operations inherit correlation automatically where appropriate.
Unknown relationships remain explicitly null — never fabricated.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Optional


@dataclass
class OperationalContext:
    correlation_id: Optional[str] = None
    execution_id: Optional[str] = None
    root_execution_id: Optional[str] = None
    job_run_id: Optional[str] = None
    incident_id: Optional[str] = None
    queue_item_id: Optional[str] = None
    workflow_id: Optional[str] = None
    notification_id: Optional[str] = None
    webhook_id: Optional[str] = None
    property_id: Optional[str] = None
    requirement_id: Optional[str] = None
    client_id: Optional[str] = None
    user_id: Optional[str] = None
    document_id: Optional[str] = None
    request_id: Optional[str] = None
    execution_depth: int = 0
    execution_sequence: int = 0
    last_event_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def fork_execution(self, *, depth_delta: int = 1) -> OperationalContext:
        """Child branch within the same root execution (e.g. queue worker claim)."""
        return replace(self, execution_depth=self.execution_depth + depth_delta)

    def with_ids(self, **kwargs: Any) -> OperationalContext:
        clean = {k: v for k, v in kwargs.items() if v is not None}
        return replace(self, **clean)

    def ensure_execution(self) -> OperationalContext:
        if self.execution_id and self.root_execution_id:
            return self
        eid = self.execution_id or str(uuid.uuid4())
        root = self.root_execution_id or eid
        return replace(self, execution_id=eid, root_execution_id=root)

    def next_sequence(self) -> OperationalContext:
        return replace(self, execution_sequence=self.execution_sequence + 1)


_ctx_var: ContextVar[Optional[OperationalContext]] = ContextVar("operational_evidence_ctx", default=None)


def get_operational_context() -> Optional[OperationalContext]:
    return _ctx_var.get()


def set_operational_context(ctx: OperationalContext) -> Token:
    return _ctx_var.set(ctx)


def reset_operational_context(token: Token) -> None:
    _ctx_var.reset(token)


def bind_from_request(
    *,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> OperationalContext:
    ctx = OperationalContext(
        correlation_id=correlation_id,
        request_id=request_id,
        client_id=client_id,
        user_id=user_id,
    ).ensure_execution()
    set_operational_context(ctx)
    return ctx


def merge_context(**overrides: Any) -> OperationalContext:
    base = get_operational_context() or OperationalContext()
    return base.with_ids(**overrides).ensure_execution()
