from __future__ import annotations

import numpy as np

from core.model.structure import Structure
from core.optimization.optimizer_base import OptimizerBase
from core.optimization.energy_based_optimizer import OptimizationHistory


class SpringRemovalOptimizer(OptimizerBase):
    """Entfernt Federn statt Knoten. Gleiche Logik wie EnergyBasedOptimizer."""

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
        self.spring_mirror_map: dict[int, int] | None = None

    def _effective_remove_fraction(self, iter_idx: int) -> float:
        if self.ramp_iters == 0:
            return self.remove_fraction
        t = min(1.0, iter_idx / self.ramp_iters)
        ramp = self.start_factor + (1.0 - self.start_factor) * t
        return self.remove_fraction * ramp

    def _select_spring_candidates(
        self,
        structure: Structure,
        energies: np.ndarray,
        effective_fraction: float,
        blacklist: set[int] | None = None,
    ) -> list[int]:
        active_indices = [
            i for i, s in enumerate(structure.springs)
            if s.active and structure.nodes[s.node_i].active and structure.nodes[s.node_j].active
        ]
        if not active_indices:
            return []

        target_remove = max(1, int(len(active_indices) * effective_fraction))

        skip = blacklist or set()
        removable = [i for i in active_indices if i not in skip]
        if not removable:
            return []

        removable_sorted = sorted(removable, key=lambda i: energies[i])

        if self.spring_mirror_map is not None:
            return self._select_symmetric_springs(removable_sorted, target_remove)
        return removable_sorted[:target_remove]

    def _select_symmetric_springs(
        self, removable_sorted: list[int], target_remove: int,
    ) -> list[int]:
        assert self.spring_mirror_map is not None
        sm = self.spring_mirror_map
        selected: list[int] = []
        processed: set[int] = set()
        removable_set = set(removable_sorted)

        for sidx in removable_sorted:
            if len(selected) >= target_remove:
                break
            if sidx in processed:
                continue

            mirror_idx = sm.get(sidx)

            if mirror_idx is None or mirror_idx == sidx:
                selected.append(sidx)
                processed.add(sidx)
            else:
                if mirror_idx in removable_set and mirror_idx not in processed:
                    selected.append(sidx)
                    selected.append(mirror_idx)
                    processed.add(sidx)
                    processed.add(mirror_idx)

        return selected

    def _build_spring_mirror_map(self, structure: Structure) -> dict[int, int]:
        """Spring-Index → Mirror-Spring-Index aus dem Knoten-Mirror-Map."""
        mm = self.mirror_map
        if mm is None:
            return {}

        edge_to_idx: dict[tuple[int, int], int] = {}
        for i, s in enumerate(structure.springs):
            if not s.active:
                continue
            ni, nj = s.node_i, s.node_j
            if not (structure.nodes[ni].active and structure.nodes[nj].active):
                continue
            edge_to_idx[(min(ni, nj), max(ni, nj))] = i

        spring_mirror: dict[int, int] = {}
        for i, s in enumerate(structure.springs):
            if not s.active:
                continue
            ni, nj = s.node_i, s.node_j
            if not (structure.nodes[ni].active and structure.nodes[nj].active):
                continue
            if ni not in mm or nj not in mm:
                continue
            mi, mj = mm[ni], mm[nj]
            mirror_edge = (min(mi, mj), max(mi, mj))
            mirror_idx = edge_to_idx.get(mirror_edge)
            if mirror_idx is not None:
                spring_mirror[i] = mirror_idx

        return spring_mirror

    def _deactivate_springs(self, structure: Structure, spring_indices: list[int]) -> None:
        for idx in spring_indices:
            structure.springs[idx].active = False

    def _reactivate_springs(self, structure: Structure, spring_indices: list[int], orphans: list[int] | None = None) -> None:
        for idx in spring_indices:
            s = structure.springs[idx]
            s.active = True
            structure.nodes[s.node_i].active = True
            structure.nodes[s.node_j].active = True
        if orphans:
            for nid in orphans:
                structure.nodes[nid].active = True

    def _blacklist_spring_with_mirror(self, spring_indices: list[int], blacklist: set[int]) -> None:
        for sidx in spring_indices:
            blacklist.add(sidx)
            if self.spring_mirror_map and sidx in self.spring_mirror_map:
                blacklist.add(self.spring_mirror_map[sidx])

    def _try_stress_redistribution_springs(
        self,
        structure: Structure,
        u: np.ndarray,
        blacklist: set[int],
    ) -> bool:
        """Entfernt die höchstbelastete Feder zur Lastumverteilung."""
        stresses = structure.spring_stresses(u)
        old_stress = structure.max_stress(u)

        max_idx = -1
        max_val = 0.0
        for i, val in enumerate(stresses):
            if i in blacklist or not structure.springs[i].active:
                continue
            if val > max_val:
                max_val = val
                max_idx = i

        if max_idx < 0:
            return False

        self._deactivate_springs(structure, [max_idx])
        orphans = structure.cleanup_orphan_nodes()
        u_new = self._solve_structure(structure)

        if u_new is not None and structure.max_stress(u_new) < old_stress:
            return True

        self._reactivate_springs(structure, [max_idx], orphans)
        self._blacklist_spring_with_mirror([max_idx], blacklist)
        return False

    def step(self, structure: Structure) -> np.ndarray:
        u = self._solve_structure(structure)
        energies = structure.spring_energies(u)

        candidates = self._select_spring_candidates(structure, energies, self.remove_fraction)
        self._deactivate_springs(structure, candidates)
        structure.cleanup_orphan_nodes()

        return energies

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
            self.spring_mirror_map = self._build_spring_mirror_map(structure)

        if force:
            for iter_idx in range(max_iters):
                structure.remove_removable_nodes()
                history.mass_fraction.append(structure.current_mass_fraction())
                if structure.current_mass_fraction() <= target_mass_fraction:
                    history.stop_reason = "Ziel-Massenanteil erreicht"
                    break
                u = self._solve_structure(structure)
                energies = (
                    structure.spring_energies(u)
                    if u is not None
                    else np.zeros(len(structure.springs))
                )
                effective_fraction = self._effective_remove_fraction(iter_idx)
                candidates = self._select_spring_candidates(structure, energies, effective_fraction)
                if not candidates:
                    history.stop_reason = "Keine entfernbaren Federn mehr"
                    break

                active_before = set(structure.active_node_ids())
                self._deactivate_springs(structure, candidates)
                structure.cleanup_orphan_nodes()
                structure.remove_removable_nodes()
                active_after = set(structure.active_node_ids())
                removed_nodes = list(active_before - active_after)

                history.removed_per_iter.append(len(candidates))
                history.removed_springs_per_iter.append(list(candidates))
                history.removed_nodes_per_iter.append(removed_nodes)
                if on_iter is not None:
                    on_iter(structure, iter_idx, len(candidates))
            else:
                history.stop_reason = "Max. Iterationen erreicht"
            return history

        # Normaler Modus
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
                if not self._try_stress_redistribution_springs(structure, u, blacklist):
                    history.stop_reason = "Streckgrenze erreicht"
                    break
                u = self._solve_structure(structure)
                if u is None:
                    history.stop_reason = "Struktur instabil nach Lastumverteilung"
                    break

            energies = structure.spring_energies(u)

            effective_fraction = self._effective_remove_fraction(iter_idx)
            candidates = self._select_spring_candidates(
                structure, energies, effective_fraction, blacklist,
            )

            if len(candidates) == 0:
                history.stop_reason = "Keine entfernbaren Federn mehr"
                break

            # Batch: alle Kandidaten auf einmal
            active_before = set(structure.active_node_ids())
            self._deactivate_springs(structure, candidates)
            orphans = structure.cleanup_orphan_nodes()
            u_check = self._solve_structure(structure)

            if u_check is not None:
                if self._exceeds_stress(structure, u_check, max_stress):
                    self._reactivate_springs(structure, candidates, orphans)
                    history.stop_reason = "Streckgrenze erreicht"
                    break
                u = u_check
                active_after = set(structure.active_node_ids())
                removed_nodes = list(active_before - active_after)
                history.removed_per_iter.append(len(candidates))
                history.removed_springs_per_iter.append(list(candidates))
                history.removed_nodes_per_iter.append(removed_nodes)
                if on_iter is not None:
                    on_iter(structure, iter_idx, len(candidates))
                continue

            # Batch fehlgeschlagen → einzeln in Mirror-Gruppen versuchen
            self._reactivate_springs(structure, candidates, orphans)

            seen: set[int] = set()
            groups: list[list[int]] = []
            candidate_set = set(candidates)
            for sidx in candidates:
                if sidx in seen:
                    continue
                mid = self.spring_mirror_map.get(sidx) if self.spring_mirror_map else None
                if mid is not None and mid != sidx and mid in candidate_set and mid not in seen:
                    groups.append([sidx, mid])
                    seen.update([sidx, mid])
                else:
                    groups.append([sidx])
                    seen.add(sidx)

            actually_removed_springs: list[int] = []
            all_orphans: list[int] = []
            for group in groups:
                self._deactivate_springs(structure, group)
                group_orphans = structure.cleanup_orphan_nodes()
                u_test = self._solve_structure(structure)

                if u_test is None or self._exceeds_stress(structure, u_test, max_stress):
                    self._reactivate_springs(structure, group, group_orphans)
                    self._blacklist_spring_with_mirror(group, blacklist)
                else:
                    u = u_test
                    actually_removed_springs.extend(group)
                    all_orphans.extend(group_orphans)

            if len(actually_removed_springs) == 0:
                history.stop_reason = "Keine weitere Optimierung möglich"
                break

            active_after = set(structure.active_node_ids())
            removed_nodes = list(active_before - active_after)
            history.removed_per_iter.append(len(actually_removed_springs))
            history.removed_springs_per_iter.append(actually_removed_springs)
            history.removed_nodes_per_iter.append(removed_nodes)
            if on_iter is not None:
                on_iter(structure, iter_idx, len(actually_removed_springs))

        else:
            history.stop_reason = "Max. Iterationen erreicht"

        return history
