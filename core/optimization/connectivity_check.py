from __future__ import annotations

from collections import deque
from typing import Iterable

from core.model.structure import Structure


def is_structure_connected(structure: Structure, exclude_nodes: set[int] | None = None) -> bool:
    exclude_nodes = exclude_nodes or set()

    active_nodes = [
        n.id for n in structure.nodes
        if n.active and n.id not in exclude_nodes
    ]
    if len(active_nodes) <= 1:
        return True

    adj = _build_adjacency(structure, exclude_nodes)
    start = active_nodes[0]

    visited = _bfs(start, adj)

    return len(visited) == len(active_nodes)


def do_loads_reach_supports(structure: Structure, exclude_nodes: set[int] | None = None) -> bool:
    exclude_nodes = exclude_nodes or set()

    support_ids = [
        n.id for n in structure.nodes
        if n.active and n.id not in exclude_nodes and (n.fix_x or n.fix_y)
    ]
    load_ids = [
        n.id for n in structure.nodes
        if n.active and n.id not in exclude_nodes and ((abs(n.fx) > 0.0) or (abs(n.fy) > 0.0))
    ]

    # keine Lasten -> trivially ok
    if len(load_ids) == 0:
        return True

    # Lasten existieren, aber keine Lager -> nicht ok
    if len(support_ids) == 0:
        return False

    adj = _build_adjacency(structure, exclude_nodes)
    support_set = set(support_ids)

    # Für jeden Lastknoten prüfen, ob er irgendein Lager erreichen kann
    for lid in load_ids:
        visited = _bfs(lid, adj)
        if visited.isdisjoint(support_set):
            return False

    return True


def is_valid_topology(structure: Structure, exclude_nodes: set[int] | None = None) -> bool:
    exclude_nodes = exclude_nodes or set()
    return is_structure_connected(structure, exclude_nodes) and do_loads_reach_supports(structure, exclude_nodes)


def _build_adjacency(structure: Structure, exclude_nodes: set[int]) -> dict[int, list[int]]:
    adj: dict[int, list[int]] = {}

    for n in structure.nodes:
        if n.active and n.id not in exclude_nodes:
            adj[n.id] = []

    for s in structure.springs:
        if not s.active:
            continue
        if s.node_i in exclude_nodes or s.node_j in exclude_nodes:
            continue

        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        if not (ni.active and nj.active):
            continue

        if ni.id in adj and nj.id in adj:
            adj[ni.id].append(nj.id)
            adj[nj.id].append(ni.id)

    return adj


def _bfs(start: int, adj: dict[int, list[int]]) -> set[int]:
    visited: set[int] = set()
    q = deque([start])
    visited.add(start)

    while q:
        v = q.popleft()
        for w in adj.get(v, []):
            if w not in visited:
                visited.add(w)
                q.append(w)

    return visited
