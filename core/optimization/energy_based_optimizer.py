from __future__ import annotations

import numpy as np

from core.model.structure import Structure
from core.optimization.optimizer_base import OptimizerBase
from dataclasses import dataclass, field


@dataclass(slots=True)
class OptimizationHistory:
    mass_fraction: list[float] = field(default_factory=list)
    removed_per_iter: list[int] = field(default_factory=list)
    removed_nodes_per_iter: list[list[int]] = field(default_factory=list)
    active_nodes: list[int] = field(default_factory=list)
    max_displacement: list[float] = field(default_factory=list)
    stop_reason: str = ""

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

        from core.solver.solver import solve
        u = solve(K, F, fixed)
        importance = structure.node_importance_from_energy(u)

        effective_fraction = self.remove_fraction
        candidates = self._select_candidates(structure, importance, effective_fraction)
        self._deactivate_nodes(structure, candidates)

        return importance

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
        max_stress: float | None = None,
        on_iter=None,
        force: bool = False,
    ) -> OptimizationHistory:
        if not (0.0 < target_mass_fraction <= 1.0):
            raise ValueError("target_mass_fraction must be in (0, 1].")
        if max_iters <= 0:
            raise ValueError("max_iters must be > 0.")

        history = OptimizationHistory()

        structure._register_special_nodes()

        is_sym, mirror_map = structure.detect_symmetry()
        if is_sym:
            self.mirror_map = mirror_map

        if force:
            for iter_idx in range(max_iters):
                structure.remove_removable_nodes()
                history.mass_fraction.append(structure.current_mass_fraction())
                if structure.current_mass_fraction() <= target_mass_fraction:
                    history.stop_reason = "Ziel-Massenanteil erreicht"
                    break
                u = self._solve_structure(structure)
                importance = (
                    structure.node_importance_from_energy(u)
                    if u is not None
                    else np.zeros(len(structure.nodes))
                )
                effective_fraction = self._effective_remove_fraction(iter_idx)
                candidates = self._select_candidates(structure, importance, effective_fraction)
                if not candidates:
                    history.stop_reason = "Keine entfernbaren Knoten mehr"
                    break
                self._deactivate_nodes(structure, candidates)
                history.removed_per_iter.append(len(candidates))
                history.removed_nodes_per_iter.append(list(candidates))
                if on_iter is not None:
                    on_iter(structure, iter_idx, len(candidates))
            else:
                history.stop_reason = "Max. Iterationen erreicht"
            return history

        u = self._solve_structure(structure)

        if max_stress is not None:
            if u is None:
                history.stop_reason = "Struktur ist instabil"
                return history
            if structure.max_stress(u) > max_stress:
                history.stop_reason = "Ausgangsspannung überschreitet bereits die Streckgrenze"
                return history

        blacklist: set[int] = set()
        needs_solve = u is None

        for iter_idx in range(max_iters):
            removed_set = structure._find_removable_nodes()
            if removed_set:
                structure.remove_removable_nodes()
                needs_solve = True

            history.mass_fraction.append(structure.current_mass_fraction())
            if structure.current_mass_fraction() <= target_mass_fraction:
                history.stop_reason = "Ziel-Massenanteil erreicht"
                break

            if needs_solve:
                u = self._solve_structure(structure)
                if u is None:
                    if removed_set:
                        self._reactivate_nodes(structure, list(removed_set))
                        u = self._solve_structure(structure)
                    if u is None:
                        history.stop_reason = "Struktur ist instabil"
                        break
                needs_solve = False

            assert u is not None
            max_u = float(np.max(np.abs(u))) if u.size > 0 else 0.0
            history.max_displacement.append(max_u)

            if self._exceeds_stress(structure, u, max_stress):
                assert max_stress is not None
                if not self._try_stress_redistribution(structure, u, blacklist):
                    history.stop_reason = "Streckgrenze erreicht"
                    break
                u = self._solve_structure(structure)
                if u is None:
                    history.stop_reason = "Struktur instabil nach Lastumverteilung"
                    break

            importance = structure.node_importance_from_energy(u)

            effective_fraction = self._effective_remove_fraction(iter_idx)
            candidates = self._select_candidates(
                structure, importance, effective_fraction, blacklist,
            )

            if len(candidates) == 0:
                history.stop_reason = "Keine entfernbaren Knoten mehr"
                break

            self._deactivate_nodes(structure, candidates)
            u_check = self._solve_structure(structure)

            if u_check is not None:
                if self._exceeds_stress(structure, u_check, max_stress):
                    self._reactivate_nodes(structure, candidates)
                    history.stop_reason = "Streckgrenze erreicht"
                    break
                u = u_check
                history.removed_per_iter.append(len(candidates))
                history.removed_nodes_per_iter.append(list(candidates))
                if on_iter is not None:
                    on_iter(structure, iter_idx, len(candidates))
                continue

            self._reactivate_nodes(structure, candidates)

            seen: set[int] = set()
            groups: list[list[int]] = []
            candidate_set = set(candidates)
            for nid in candidates:
                if nid in seen:
                    continue
                mid = self.mirror_map.get(nid) if self.mirror_map else None
                if mid is not None and mid != nid and mid in candidate_set and mid not in seen:
                    groups.append([nid, mid])
                    seen.update([nid, mid])
                else:
                    groups.append([nid])
                    seen.add(nid)

            actually_removed: list[int] = []
            for group in groups:
                self._deactivate_nodes(structure, group)
                u_test = self._solve_structure(structure)

                if u_test is None or self._exceeds_stress(structure, u_test, max_stress):
                    self._reactivate_nodes(structure, group)
                    self._blacklist_with_mirror(group, blacklist)
                else:
                    u = u_test
                    actually_removed.extend(group)

            if len(actually_removed) == 0:
                history.stop_reason = "Keine weitere Optimierung möglich"
                break

            history.removed_per_iter.append(len(actually_removed))
            history.removed_nodes_per_iter.append(actually_removed)
            if on_iter is not None:
                on_iter(structure, iter_idx, len(actually_removed))

        else:
            history.stop_reason = "Max. Iterationen erreicht"

        return history
