from __future__ import annotations

from abc import ABC, abstractmethod

import networkx as nx
import numpy as np

from core.model.structure import Structure


class OptimizerBase(ABC):
    mirror_map: dict[int, int] | None = None

    @abstractmethod
    def step(self, structure: Structure) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def run(self, structure: Structure, target_mass_fraction: float, max_iters: int = 200):
        raise NotImplementedError

    # ── Gemeinsame Hilfsmethoden ──

    def _select_candidates(
        self,
        structure: Structure,
        score: np.ndarray,
        effective_fraction: float,
        blacklist: set[int] | None = None,
    ) -> list[int]:
        active_ids = [n.id for n in structure.nodes if n.active]
        if not active_ids:
            return []

        target_remove = max(1, int(len(active_ids) * effective_fraction))
        protected = set(structure.protected_node_ids())
        if blacklist:
            protected |= blacklist
        removable = [i for i in active_ids if i not in protected]
        if not removable:
            return []

        removable_sorted = sorted(removable, key=lambda i: score[i])

        if self.mirror_map is not None:
            return self._select_symmetric(structure, removable_sorted, target_remove)
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
        return structure.compute_displacement()

    def _exceeds_stress(self, structure: Structure, u: np.ndarray, max_stress: float | None) -> bool:
        if max_stress is None:
            return False
        return structure.max_stress(u) > max_stress

    def _try_stress_redistribution(
        self,
        structure: Structure,
        u: np.ndarray,
        blacklist: set[int],
    ) -> bool:
        protected = set(structure.protected_node_ids()) | blacklist
        pair = structure.most_stressed_spring_nodes(u)
        if pair is None:
            return False

        removable = [nid for nid in pair if nid not in protected]
        if not removable:
            return False

        old_stress = structure.max_stress(u)
        self._deactivate_nodes(structure, removable)
        u_new = self._solve_structure(structure)

        if u_new is not None and structure.max_stress(u_new) < old_stress:
            return True

        self._reactivate_nodes(structure, removable)
        self._blacklist_with_mirror(removable, blacklist)
        return False

    def _blacklist_with_mirror(self, nids: list[int], blacklist: set[int]) -> None:
        for nid in nids:
            blacklist.add(nid)
            if self.mirror_map and nid in self.mirror_map:
                blacklist.add(self.mirror_map[nid])