"""Validation result types for graph integrity checks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CheckFailure:
    check: str
    severity: str  # failure | warning
    entity_type: str
    entity_id: str
    message: str
    decision_id: str | None = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "decision_id": self.decision_id,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class ValidationResult:
    valid: bool
    checks_run: int = 0
    failures: List[CheckFailure] = field(default_factory=list)
    warnings: List[CheckFailure] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def add_failure(self, failure: CheckFailure) -> None:
        if failure.severity == "warning":
            self.warnings.append(failure)
        else:
            self.failures.append(failure)
            self.valid = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid and len(self.failures) == 0,
            "checks_run": self.checks_run,
            "failures": [f.to_dict() for f in self.failures],
            "warnings": [w.to_dict() for w in self.warnings],
            "stats": self.stats,
            "duration_ms": self.duration_ms,
        }

    def merge(self, other: ValidationResult) -> None:
        self.checks_run += other.checks_run
        self.failures.extend(other.failures)
        self.warnings.extend(other.warnings)
        if other.failures:
            self.valid = False
        self.stats.update(other.stats)
