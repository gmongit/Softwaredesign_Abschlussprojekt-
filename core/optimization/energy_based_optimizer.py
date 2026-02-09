from __future__ import annotations

import numpy as np

from core.model.structure import Structure
from core.solver.solver import solve
from core.optimization.connectivity_check import is_valid_topology


class EnergyBasedOptimizer:
    def __init__(self, remove_fraction: float = 0.05):
        if not (0.0 < remove_fraction < 1.0):
            raise ValueError("remove_fraction must be in (0, 1).")
        self.remove_fraction = remove_fraction

    def step(self, structure: Structure) -> np.ndarray:
        K = structure.assemble_K()
        F = structure.assemble_F()
        fixed = structure.fixed_dofs()

        u = solve(K, F, fixed)
        importance = structure.node_importance_from_energy(u)

        candidates = self._select_removal_candidates(structure, importance)
        self._deactivate_nodes(structure, candidates)

        return importance

    def _select_removal_candidates(self, structure: Structure, importance: np.ndarray) -> list[int]:
        active_ids = [n.id for n in structure.nodes if n.active]
        if len(active_ids) == 0:
            return []

        target_remove = max(1, int(len(active_ids) * self.remove_fraction))

        protected = set(structure.protected_node_ids())
        removable = [i for i in active_ids if i not in protected]
        if len(removable) == 0:
            return []

        removable_sorted = sorted(removable, key=lambda i: importance[i])

        selected: list[int] = []
        exclude = set()

        for nid in removable_sorted:
            if len(selected) >= target_remove:
                break

            trial_exclude = exclude | {nid}

            if is_valid_topology(structure, exclude_nodes=trial_exclude):
                selected.append(nid)
                exclude = trial_exclude

        return selected

    def _deactivate_nodes(self, structure: Structure, node_ids: list[int]) -> None:
        to_remove = set(node_ids)

        for node_id in to_remove:
            structure.nodes[node_id].active = False

        for spring in structure.springs:
            if spring.node_i in to_remove or spring.node_j in to_remove:
                spring.active = False
