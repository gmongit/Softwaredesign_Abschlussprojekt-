from __future__ import annotations

import numpy as np

from core.model.structure import Structure
from core.solver.solver import solve
from core.optimization.connectivity_check import is_valid_topology
from core.optimization.optimizer_base import OptimizerBase
from dataclasses import dataclass


@dataclass(slots=True)
class OptimizationHistory:
    mass_fraction: list[float]
    removed_per_iter: list[int]
    active_nodes: list[int]
    max_displacement: list[float]

class EnergyBasedOptimizer(OptimizerBase):
    def __init__(
        self,
        remove_fraction: float = 0.05,
        start_factor: float = 0.3,
        ramp_iters: int = 10,
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

    def _select_removal_candidates(self, structure: Structure, importance: np.ndarray, effective_fraction: float) -> list[int]:
        active_ids = [n.id for n in structure.nodes if n.active]
        if len(active_ids) == 0:
            return []

        target_remove = max(1, int(len(active_ids) * effective_fraction))

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

        history = OptimizationHistory(mass_fraction=[], removed_per_iter=[], active_nodes= [], max_displacement=[])

        for iter_idx in range(max_iters):
            history.mass_fraction.append(structure.current_mass_fraction())

            if structure.current_mass_fraction() <= target_mass_fraction:
                break
            
            effective_fraction = self._effective_remove_fraction(iter_idx)


            K = structure.assemble_K()
            F = structure.assemble_F()
            fixed = structure.fixed_dofs()

            u = solve(K, F, fixed)

            max_u = float(np.max(np.abs(u))) if u.size > 0 else 0.0
            history.max_displacement.append(max_u)

            importance = structure.node_importance_from_energy(u)
            
            effective_fraction = self._effective_remove_fraction(iter_idx)
            candidates = self._select_removal_candidates(structure, importance, effective_fraction)
            
            if len(candidates) == 0:
                history.removed_per_iter.append(0)
                break

            self._deactivate_nodes(structure, candidates)
            history.removed_per_iter.append(len(candidates))

        return history
