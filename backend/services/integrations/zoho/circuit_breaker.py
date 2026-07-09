"""Circuit breaker for Zoho API calls."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class CircuitState:
    failures: int = 0
    last_failure_at: float = 0.0
    open_until: float = 0.0


class ZohoCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, open_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._circuits: Dict[str, CircuitState] = {}

    def is_open(self, integration: str = "global") -> bool:
        state = self._circuits.get(integration)
        if not state:
            return False
        if state.open_until and time.time() < state.open_until:
            return True
        if state.open_until and time.time() >= state.open_until:
            state.failures = 0
            state.open_until = 0.0
        return False

    def record_success(self, integration: str = "global") -> None:
        self._circuits[integration] = CircuitState()

    def record_failure(self, integration: str = "global") -> None:
        state = self._circuits.setdefault(integration, CircuitState())
        state.failures += 1
        state.last_failure_at = time.time()
        if state.failures >= self.failure_threshold:
            state.open_until = time.time() + self.open_seconds

    def reset(self, integration: str | None = None) -> None:
        if integration:
            self._circuits.pop(integration, None)
        else:
            self._circuits.clear()


zoho_circuit_breaker = ZohoCircuitBreaker()
