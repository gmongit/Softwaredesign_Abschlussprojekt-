"""Nachverstärkung: Reaktiviert gezielt deaktivierte Knoten
um Federn zu entlasten.

Finden von Strukturen über Network und Optimierung der Strukturen (brute-force)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import sqrt
from typing import Callable

import numpy as np
from core.model.structure import Structure


@dataclass(slots=True)
class RebuildResult:
    reactivated_node_ids: list[int] = field(default_factory=list)
    stress_before: float = 0.0
    stress_after: float = 0.0
    n_candidates: int = 0
    n_clusters: int = 0
    n_combos_total: int = 0
    n_combos_tested: int = 0
    message: str = ""


def _activate_nodes(structure: Structure, node_ids: list[int]) -> None:
    nid_set = set(node_ids)
    for nid in nid_set:
        structure.nodes[nid].active = True
    for s in structure.springs:
        if (s.node_i in nid_set or structure.nodes[s.node_i].active) \
                and (s.node_j in nid_set or structure.nodes[s.node_j].active):
            s.active = True


def _deactivate_nodes(structure: Structure, node_ids: list[int]) -> None:
    nid_set = set(node_ids)
    for nid in nid_set:
        structure.nodes[nid].active = False
    for s in structure.springs:
        if s.node_i in nid_set or s.node_j in nid_set:
            s.active = False


def _expand_with_mirrors(
    combo: list[int],
    mirror_map: dict[int, int],
) -> list[int]:
    """Erweitert eine Kombination um gespiegelte Knoten."""
    expanded = set(combo)
    for nid in combo:
        mid = mirror_map.get(nid, nid)
        if mid != nid:
            expanded.add(mid)
    return list(expanded)


def _build_clusters(
    stressed_spring_indices: list[int],
    structure: Structure,
    candidate_to_stressed: dict[int, set[int]],
) -> list[list[int]]:
    """Teilt Kandidaten in Cluster auf, basierend auf verbundenen Stressbereichen.

    Zwei Kandidaten sind im selben Cluster wenn ihre stressed_nodes
     über belastete Federn verbunden sind.
    """
    adj: dict[int, set[int]] = {}
    for idx in stressed_spring_indices:
        s = structure.springs[idx]
        adj.setdefault(s.node_i, set()).add(s.node_j)
        adj.setdefault(s.node_j, set()).add(s.node_i)

    visited: set[int] = set()
    components: list[set[int]] = []
    for start in adj:
        if start in visited:
            continue
        comp: set[int] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            comp.add(node)
            for nb in adj.get(node, set()):
                if nb not in visited:
                    stack.append(nb)
        components.append(comp)

    node_to_comp: dict[int, int] = {}
    for comp_idx, comp in enumerate(components):
        for nid in comp:
            node_to_comp[nid] = comp_idx

    clusters: dict[int, list[int]] = {}
    for candidate, stressed_nbs in candidate_to_stressed.items():
        # Nutze ersten verfügbaren Stress-Nachbarn zur Zuordnung
        first_nb = next(iter(stressed_nbs))
        if first_nb in node_to_comp:
            comp_idx = node_to_comp[first_nb]
            clusters.setdefault(comp_idx, []).append(candidate)

    return list(clusters.values())


def rebuild_support(
    structure: Structure,
    min_improvement: float = 0.05,
    top_percent: float = 0.02,
    min_stress_pct: float = 0.75,
    on_progress: Callable[[int, int, float], None] | None = None,
) -> RebuildResult:
    """Cluster-basierte Nachverstärkung durch Knoten-Reaktivierung."""
    result = RebuildResult()

    u = structure.compute_displacement()
    if u is None:
        result.message = "Struktur nicht lösbar"
        return result

    stress_before = structure.max_stress(u)
    result.stress_before = stress_before
    if stress_before <= 0:
        result.message = "Keine Spannung vorhanden"
        return result

    stresses = structure.spring_stresses(u)
    active_springs = [
        (i, float(stresses[i]))
        for i, s in enumerate(structure.springs)
        if s.active and stresses[i] > 0
    ]
    active_springs.sort(key=lambda x: x[1], reverse=True)

    top_count = max(1, int(len(active_springs) * top_percent))
    min_stress = stress_before * min_stress_pct

    stressed_spring_indices: list[int] = []
    stressed_nodes: set[int] = set()
    for idx, stress_val in active_springs[:top_count]:
        if stress_val >= min_stress:
            stressed_spring_indices.append(idx)
            s = structure.springs[idx]
            stressed_nodes.add(s.node_i)
            stressed_nodes.add(s.node_j)

    if not stressed_nodes:
        result.message = "Keine hochbelasteten Federn gefunden"
        return result

    # Symmetrie-Vorbereitung: Map vervollständigen (bidirektional)
    is_sym, m_orig = structure.detect_symmetry()
    mirror_map = {**m_orig, **{v: k for k, v in m_orig.items()}} if (is_sym and m_orig) else None

    # Deaktivierte Nachbarn finden und Symmetrie-Paare als Repräsentanten nutzen
    candidate_to_stressed: dict[int, set[int]] = {}
    for s in structure.springs:
        ni, nj = s.node_i, s.node_j
        for node_a, node_b in [(ni, nj), (nj, ni)]:
            if node_a in stressed_nodes and not structure.nodes[node_b].active:
                # Nutze immer die kleinere ID des Paares als Repräsentant für den Cluster
                rep = min(node_b, mirror_map.get(node_b, node_b)) if mirror_map else node_b
                candidate_to_stressed.setdefault(rep, set()).add(node_a)

    if not candidate_to_stressed:
        result.message = "Keine deaktivierten Nachbarknoten verfügbar"
        return result

    clusters = _build_clusters(stressed_spring_indices, structure, candidate_to_stressed)

    # Symmetrie-Filterung der Cluster-Inhalte
    if mirror_map:
        reduced_clusters: list[list[int]] = []
        global_seen: set[int] = set()  
        for cluster in clusters:
            one_side: list[int] = []
            for nid in cluster:
                if nid in global_seen: continue
                mid = mirror_map.get(nid, nid)
                global_seen.update([nid, mid])
                one_side.append(min(nid, mid))
            if one_side: reduced_clusters.append(one_side)
        clusters = reduced_clusters

    result.n_candidates = sum(len(c) for c in clusters)
    result.n_clusters = len(clusters)
    total_local_combos = sum((1 << len(c)) - 1 for c in clusters)
    result.n_combos_total = total_local_combos

    cluster_solutions: list[list[int]] = [] # pro Cluster
    tested = 0
    
    # Lokale Optimierung/ pro Cluster
    for cluster in clusters:
        n = len(cluster)
        c_best_combo: list[int] = []
        c_best_score = 0.0
        c_best_stress = stress_before

        for size in range(1, n + 1):
            for combo in combinations(cluster, size):
                tested += 1
                act_list = _expand_with_mirrors(list(combo), mirror_map) if mirror_map else list(combo)
                
               
                to_toggle = [nid for nid in act_list if not structure.nodes[nid].active]
                
                _activate_nodes(structure, to_toggle)
                u_trial = structure.compute_displacement()
                
                if u_trial is not None:
                    t_stress = structure.max_stress(u_trial)
                    reduct = (stress_before - t_stress) / stress_before
                    if reduct >= min_improvement:
                        score = reduct / sqrt(len(combo))
                        if score > c_best_score or (score == c_best_score and t_stress < c_best_stress):
                            c_best_score, c_best_combo, c_best_stress = score, act_list, t_stress

                _deactivate_nodes(structure, to_toggle)
                if on_progress: on_progress(tested, total_local_combos, 0.0)

        if c_best_combo:
            cluster_solutions.append(c_best_combo)

    # Globale Optimierung
    best_final_nodes: list[int] = []
    best_final_stress = stress_before
    
    if cluster_solutions:
        for r in range(1, len(cluster_solutions) + 1):
            for combo in combinations(cluster_solutions, r):
                flat_combo = list(set(nid for sub in combo for nid in sub))
                to_toggle = [nid for nid in flat_combo if not structure.nodes[nid].active]
                
                _activate_nodes(structure, to_toggle)
                u_trial = structure.compute_displacement()
                
                if u_trial is not None:
                    t_stress = structure.max_stress(u_trial)
                    # Nur akzeptieren, wenn es den globalen Bestwert verbessert
                    if t_stress < best_final_stress:
                        best_final_stress = t_stress
                        best_final_nodes = flat_combo
                
                _deactivate_nodes(structure, to_toggle)

    result.n_combos_tested = tested

    # Finale Anwendung und Validierung
    if best_final_nodes and best_final_stress < stress_before:
        _activate_nodes(structure, best_final_nodes)
        result.reactivated_node_ids = best_final_nodes
        result.stress_after = best_final_stress
        reduction = (stress_before - best_final_stress) / stress_before * 100
        result.message = (
            f"{len(best_final_nodes)} Knoten reaktiviert — Stress von "
            f"{stress_before/1e6:.1f} auf {best_final_stress/1e6:.1f} MPa reduziert ({reduction:.1f}%)"
        )
    else:
        result.stress_after = stress_before
        result.message = "Keine Verbesserung erzielt oder Globale Interferenz"

    return result