from __future__ import annotations

import networkx as nx
import numpy as np

from core.model.structure import Structure
from core.solver.solver import solve
from core.optimization.optimizer_base import OptimizerBase
from dataclasses import dataclass


@dataclass(slots=True)
class OptimizationHistory:
    mass_fraction: list[float]
    removed_per_iter: list[int]
    removed_nodes_per_iter: list[list[int]]
    active_nodes: list[int]
    max_displacement: list[float]

class EnergyBasedOptimizer(OptimizerBase):
    def __init__(
        self,
        remove_fraction: float = 0.05,
        start_factor: float = 0.3,
        ramp_iters: int = 10,
        mirror_map: dict[int, int] | None = None,
    ):
        if not (0.0 < remove_fraction < 1.0):
            raise ValueError("remove_fraction must be in (0, 1).")
        if not (0.0 < start_factor <= 1.0):
            raise ValueError("start_factor must be in (0, 1].")
        if ramp_iters < 0:
            raise ValueError("ramp_iters must be >= 0.")

        self.remove_fraction = remove_fraction
        self.start_factor = start_factor
        self.ramp_iters = ramp_iters
        self.mirror_map = mirror_map

    def step(self, structure: Structure) -> np.ndarray:
        K = structure.assemble_K()
        F = structure.assemble_F()
        fixed = structure.fixed_dofs()

        u = solve(K, F, fixed)
        importance = structure.node_importance_from_energy(u)

        effective_fraction = self.remove_fraction
        candidates = self._select_removal_candidates(structure, importance, effective_fraction)
        self._deactivate_nodes(structure, candidates)

        return importance

    def _select_removal_candidates(
        self,
        structure: Structure,
        importance: np.ndarray,
        effective_fraction: float,
        blacklist: set[int] | None = None,
    ) -> list[int]:
        active_ids = [n.id for n in structure.nodes if n.active]
        if len(active_ids) == 0:
            return []

        target_remove = max(1, int(len(active_ids) * effective_fraction))

        protected = set(structure.protected_node_ids())
        if blacklist:
            protected |= blacklist
        removable = [i for i in active_ids if i not in protected]
        if len(removable) == 0:
            return []

        removable_sorted = sorted(removable, key=lambda i: importance[i])

        if self.mirror_map is not None:
            return self._select_symmetric(structure, removable_sorted, target_remove)
        else:
            return self._select_greedy(structure, removable_sorted, target_remove)

    def _select_greedy(self, structure: Structure, removable_sorted: list[int], target_remove: int) -> list[int]:
        selected: list[int] = []
        G = structure.build_graph()

        for nid in removable_sorted:
            if len(selected) >= target_remove:
                break
            if nid not in G:
                continue

            neighbors = list(G.neighbors(nid))
            G.remove_node(nid)

            if G.number_of_nodes() > 1 and nx.is_connected(G):
                selected.append(nid)
            else:
                G.add_node(nid)
                for nb in neighbors:
                    if nb in G:
                        G.add_edge(nid, nb)

        return selected

    def _select_symmetric(self, structure: Structure, removable_sorted: list[int], target_remove: int) -> list[int]:
        selected: list[int] = []
        processed: set[int] = set()
        assert self.mirror_map is not None
        mm = self.mirror_map
        removable_set = set(removable_sorted)
        G = structure.build_graph()

        def _try_remove(nids: list[int]) -> bool:
            saved: dict[int, list[int]] = {}
            for nid in nids:
                if nid in G:
                    saved[nid] = list(G.neighbors(nid))
                    G.remove_node(nid)

            valid = G.number_of_nodes() > 1 and nx.is_connected(G)

            if not valid:
                for nid, neighbors in saved.items():
                    G.add_node(nid)
                    for nb in neighbors:
                        if nb in G:
                            G.add_edge(nid, nb)
            return valid

        for nid in removable_sorted:
            if len(selected) >= target_remove:
                break
            if nid in processed:
                continue

            mirror_id = mm.get(nid)

            if mirror_id is None or mirror_id == nid:
                if _try_remove([nid]):
                    selected.append(nid)
                    processed.add(nid)
            else:
                if mirror_id in removable_set and mirror_id not in processed:
                    if _try_remove([nid, mirror_id]):
                        selected.append(nid)
                        selected.append(mirror_id)
                        processed.add(nid)
                        processed.add(mirror_id)

        return selected

    def _deactivate_nodes(self, structure: Structure, node_ids: list[int]) -> None:
        to_remove = set(node_ids)

        for node_id in to_remove:
            structure.nodes[node_id].active = False

        for spring in structure.springs:
            if spring.node_i in to_remove or spring.node_j in to_remove:
                spring.active = False

    def _reactivate_nodes(self, structure: Structure, node_ids: list[int]) -> None:
        to_restore = set(node_ids)

        for node_id in to_restore:
            structure.nodes[node_id].active = True

        for spring in structure.springs:
            ni = spring.node_i
            nj = spring.node_j
            if (ni in to_restore or structure.nodes[ni].active) and \
               (nj in to_restore or structure.nodes[nj].active):
                spring.active = True

    def _solve_structure(self, structure: Structure) -> np.ndarray | None:
        K = structure.assemble_K()
        F = structure.assemble_F()
        fixed = structure.fixed_dofs()
        return solve(K, F, fixed)

    def _effective_remove_fraction(self, iter_idx: int) -> float:
        if self.ramp_iters == 0:
            return self.remove_fraction

        t = min(1.0, iter_idx / self.ramp_iters)
        ramp = self.start_factor + (1.0 - self.start_factor) * t
        return self.remove_fraction * ramp

    def run(
        self,
        structure: Structure,
        target_mass_fraction: float,
        max_iters: int = 200,
    ) -> OptimizationHistory:
        if not (0.0 < target_mass_fraction <= 1.0):
            raise ValueError("target_mass_fraction must be in (0, 1].")
        if max_iters <= 0:
            raise ValueError("max_iters must be > 0.")

        history = OptimizationHistory(
            mass_fraction=[], removed_per_iter=[],
            removed_nodes_per_iter=[], active_nodes=[], max_displacement=[],
        )

        structure._register_special_nodes()

        is_sym, mirror_map = structure.detect_symmetry()
        if is_sym:
            self.mirror_map = mirror_map

        blacklist: set[int] = set()
        needs_solve = True
        u: np.ndarray | None = None

        for iter_idx in range(max_iters):
            removed = structure.remove_removable_nodes()
            if removed > 0:
                needs_solve = True

            history.mass_fraction.append(structure.current_mass_fraction())
            if structure.current_mass_fraction() <= target_mass_fraction:
                break

            if needs_solve:
                u = self._solve_structure(structure)
                if u is None:
                    break
                needs_solve = False

            assert u is not None
            max_u = float(np.max(np.abs(u))) if u.size > 0 else 0.0
            history.max_displacement.append(max_u)

            importance = structure.node_importance_from_energy(u)

            effective_fraction = self._effective_remove_fraction(iter_idx)
            candidates = self._select_removal_candidates(
                structure, importance, effective_fraction, blacklist,
            )

            if len(candidates) == 0:
                break

            self._deactivate_nodes(structure, candidates)

            u_check = self._solve_structure(structure)

            if u_check is not None:
                u = u_check
                history.removed_per_iter.append(len(candidates))
                history.removed_nodes_per_iter.append(list(candidates))
                continue

            self._reactivate_nodes(structure, candidates)

            actually_removed: list[int] = []
            for nid in candidates:
                self._deactivate_nodes(structure, [nid])
                u_single = self._solve_structure(structure)

                if u_single is None:
                    self._reactivate_nodes(structure, [nid])
                    blacklist.add(nid)
                    if mirror_map and nid in mirror_map:
                        blacklist.add(mirror_map[nid])
                else:
                    u = u_single
                    actually_removed.append(nid)

            if len(actually_removed) == 0:
                break

            history.removed_per_iter.append(len(actually_removed))
            history.removed_nodes_per_iter.append(actually_removed)

        return history
