"""
Async convergence observation hooks (framework; runtime harness supplies reads).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


ReadFn = Callable[[], Dict[str, Any]]


@dataclass
class ConvergenceObservation:
    label: str
    t0: Dict[str, Any] = field(default_factory=dict)
    reads: List[Dict[str, Any]] = field(default_factory=list)
    converged: bool = False
    stale_projection: bool = False
    timeout_seconds: int = 60

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "t0": self.t0,
            "reads": self.reads,
            "converged": self.converged,
            "stale_projection": self.stale_projection,
            "timeout_seconds": self.timeout_seconds,
        }


class ConvergenceObserver:
    def __init__(self, *, default_timeout_seconds: int = 60) -> None:
        self.default_timeout_seconds = default_timeout_seconds
        self.observations: List[ConvergenceObservation] = []

    def observe(
        self,
        label: str,
        read_fn: ReadFn,
        *,
        agree_fn: Optional[Callable[[Dict[str, Any], Dict[str, Any]], bool]] = None,
        timeout_seconds: Optional[int] = None,
        poll_interval_seconds: float = 2.0,
        browser_read_fn: Optional[ReadFn] = None,
        dry_run: bool = True,
    ) -> ConvergenceObservation:
        timeout = timeout_seconds or self.default_timeout_seconds
        obs = ConvergenceObservation(label=label, timeout_seconds=timeout)
        if dry_run:
            obs.t0 = {"dry_run": True}
            obs.reads.append({"dry_run": True, "note": "No runtime observation executed"})
            self.observations.append(obs)
            return obs

        agree = agree_fn or (lambda a, b: a == b)
        obs.t0 = read_fn()
        deadline = time.time() + timeout
        last = obs.t0
        while time.time() < deadline:
            time.sleep(poll_interval_seconds)
            current = read_fn()
            obs.reads.append({"ts": time.time(), "api": current})
            if browser_read_fn:
                browser = browser_read_fn()
                if browser != current:
                    obs.stale_projection = True
            if agree(last, current) and agree(obs.t0, current):
                obs.converged = True
                break
            last = current
        self.observations.append(obs)
        return obs

    def build_artifact(self) -> Dict[str, object]:
        return {
            "observations": [o.to_dict() for o in self.observations],
            "any_stale": any(o.stale_projection for o in self.observations),
            "any_timeout": any(not o.converged and not o.reads for o in self.observations),
        }
