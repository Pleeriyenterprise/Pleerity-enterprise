"""
Navigation depth analysis for control-plane paths.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from .constants import DEFAULT_MAX_NAVIGATION_DEPTH
from .schemas import NavigationEdge


def normalize_route(route: str) -> str:
    if not route:
        return "/"
    r = route.split("?")[0].rstrip("/") or "/"
    return r


def path_depth(path: List[str]) -> int:
    return len(path)


def exceeds_max_depth(path: List[str], max_depth: int = DEFAULT_MAX_NAVIGATION_DEPTH) -> bool:
    return path_depth(path) > max_depth


def analyze_path(
    path: List[str],
    *,
    max_depth: int = DEFAULT_MAX_NAVIGATION_DEPTH,
) -> Dict[str, object]:
    norm = [normalize_route(p) for p in path]
    return {
        "path": norm,
        "depth": len(norm),
        "max_allowed_navigation_depth": max_depth,
        "depth_exceeded": len(norm) > max_depth,
    }


def build_adjacency(edges: List[NavigationEdge], *, include_exempt: bool = False) -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {}
    for e in edges:
        if e.is_exempt and not include_exempt:
            continue
        fr, to = normalize_route(e.from_route), normalize_route(e.to_route)
        adj.setdefault(fr, []).append(to)
    return adj


def walk_paths(
    start: str,
    adj: Dict[str, List[str]],
    *,
    max_depth: int = DEFAULT_MAX_NAVIGATION_DEPTH,
) -> List[List[str]]:
    start = normalize_route(start)
    results: List[List[str]] = []

    def dfs(node: str, path: List[str], visited: Set[str]) -> None:
        if len(path) > max_depth:
            results.append(list(path))
            return
        if node in visited:
            results.append(list(path) + [node])
            return
        visited.add(node)
        path.append(node)
        neighbors = adj.get(node, [])
        if not neighbors:
            results.append(list(path))
        else:
            for nxt in neighbors:
                dfs(nxt, path, set(visited))
        path.pop()
        visited.discard(node)

    dfs(start, [], set())
    return results
