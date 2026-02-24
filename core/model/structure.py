from __future__ import annotations

import networkx as nx
import numpy as np

from core.model.node import Node
from core.model.spring import Spring


class Structure:
    GRAVITY = 9.81

    def __init__(self, nodes: list[Node], springs: list[Spring]):
        self.nodes = nodes
        self.springs = springs
        self.density: float = 0.0
        self.beam_area: float = 0.0
        self._initial_mass: float = 0.0

    @property
    def ndof(self) -> int:
        return 2 * len(self.nodes)

    def build_graph(self, exclude_nodes: set[int] | None = None) -> nx.Graph:
        """Erzeugt Graph aus aktiven Knoten und Federn."""
        exclude = exclude_nodes or set()
        G = nx.Graph()

        for n in self.nodes:
            if n.active and n.id not in exclude:
                G.add_node(n.id)

        for s in self.springs:
            if not s.active:
                continue
            if s.node_i in exclude or s.node_j in exclude:
                continue
            ni = self.nodes[s.node_i]
            nj = self.nodes[s.node_j]
            if ni.active and nj.active and ni.id in G and nj.id in G:
                G.add_edge(ni.id, nj.id)

        return G

    def is_valid_topology(self, exclude_nodes: set[int] | None = None) -> bool:
        """Prüft Zusammenhang und Lastpfade (Last → Lager)."""
        G = self.build_graph(exclude_nodes)
        exclude = exclude_nodes or set()

        if G.number_of_nodes() <= 1:
            return True
        if not nx.is_connected(G):
            return False

        support_ids = {
            n.id for n in self.nodes
            if n.active and n.id not in exclude and (n.fix_x or n.fix_y)
        }
        load_ids = [
            n.id for n in self.nodes
            if n.active and n.id not in exclude and (abs(n.fx) > 0.0 or abs(n.fy) > 0.0)
        ]

        if len(load_ids) == 0:
            return True
        if len(support_ids) == 0:
            return False

        for lid in load_ids:
            reachable = nx.node_connected_component(G, lid)
            if reachable.isdisjoint(support_ids):
                return False

        return True

    def _find_removable_nodes(self) -> set[int]:
        """Findet strukturell nutzlose Knoten: isolierte Inseln + Sackgassen."""
        protected = self._protected_ids()
        removable: set[int] = set()
        G = self.build_graph()

        # Isolierte Inseln: Komponenten ohne Lager oder ohne Last
        for comp in nx.connected_components(G):
            has_support = any(self.nodes[nid].fix_x or self.nodes[nid].fix_y for nid in comp)
            has_load = any(abs(self.nodes[nid].fx) > 0.0 or abs(self.nodes[nid].fy) > 0.0 for nid in comp)
            if not has_support or not has_load:
                removable |= comp

        # Sackgassen-Ketten: Grad-1-Knoten
        work = G.copy()
        changed = True
        while changed:
            changed = False
            dead_ends = [
                nid for nid in work.nodes()
                if work.degree(nid) <= 1 and nid not in protected and nid not in removable
            ]
            for nid in dead_ends:
                removable.add(nid)
                work.remove_node(nid)
                changed = True

        return removable

    def remove_removable_nodes(self) -> int:
        """Entfernt strukturell nutzlose Knoten. Gibt Anzahl zurück."""
        removable = self._find_removable_nodes()

        for nid in removable:
            self.nodes[nid].active = False

        for spring in self.springs:
            if spring.node_i in removable or spring.node_j in removable:
                spring.active = False

        return len(removable)

    def _protected_ids(self) -> set[int]:
        """Knoten mit Lager oder Last — dürfen nie entfernt werden."""
        protected: set[int] = set()
        for n in self.nodes:
            if not n.active:
                continue
            if (abs(n.fx) > 0.0) or (abs(n.fy) > 0.0) or n.fix_x or n.fix_y:
                protected.add(n.id)
        return protected

    def protected_node_ids(self) -> list[int]:
        """Gibt direkt geschützte Knoten + deren Nachbarn zurück."""
        direct = self._protected_ids()

        G = self.build_graph()
        neighbors: set[int] = set()
        for nid in direct:
            for neighbor in G.neighbors(nid):
                if neighbor not in direct:
                    neighbors.add(neighbor)

        return list(direct | neighbors)

    def assemble_K(self) -> np.ndarray:
        K = np.zeros((self.ndof, self.ndof), dtype=float)

        for spring in self.springs:
            if not spring.active:
                continue

            ni = self.nodes[spring.node_i]
            nj = self.nodes[spring.node_j]

            if not (ni.active and nj.active):
                continue

            Ke = spring.element_stiffness_matrix(ni, nj)

            dofs = [
                ni.dof_x, ni.dof_y,
                nj.dof_x, nj.dof_y,
            ]

            for a in range(4):
                for b in range(4):
                    K[dofs[a], dofs[b]] += Ke[a, b]

        return K

    def assemble_F(self) -> np.ndarray:
        F = np.zeros(self.ndof, dtype=float)

        for node in self.nodes:
            if not node.active:
                continue
            F[node.dof_x] += node.fx
            F[node.dof_y] += node.fy

        for spring in self.springs:
            if not spring.active:
                continue
            ni = self.nodes[spring.node_i]
            nj = self.nodes[spring.node_j]
            if not (ni.active and nj.active):
                continue
            m = spring.compute_mass(ni, nj, self.density, self.beam_area)
            gravity_force = m * 0.5 * self.GRAVITY
            F[ni.dof_y] -= gravity_force
            F[nj.dof_y] -= gravity_force

        return F

    def active_node_ids(self) -> list[int]:
        return [n.id for n in self.nodes if n.active]

    def active_node_count(self) -> int:
        return sum(1 for n in self.nodes if n.active)

    def total_node_count(self) -> int:
        return len(self.nodes)

    def current_mass_fraction(self) -> float:
        if self._initial_mass <= 0.0:
            if self.total_node_count() == 0:
                return 0.0
            return self.active_node_count() / self.total_node_count()
        return self.total_mass() / self._initial_mass

    def node_importance_from_energy(self, u: np.ndarray) -> np.ndarray:
        importance = np.zeros(len(self.nodes), dtype=float)

        for spring in self.springs:
            if not spring.active:
                continue

            ni = self.nodes[spring.node_i]
            nj = self.nodes[spring.node_j]

            if not (ni.active and nj.active):
                continue

            E = spring.strain_energy(ni, nj, u)
            importance[ni.id] += 0.5 * E
            importance[nj.id] += 0.5 * E

        return importance

    def fixed_dofs(self) -> list[int]:
        fixed: list[int] = []

        for node in self.nodes:
            if not node.active:
                fixed.append(node.dof_x)
                fixed.append(node.dof_y)
            else:
                fixed.extend(node.fixed_dofs())

        return fixed

    def update_spring_stiffnesses(self, e_modul_pa: float, beam_area_m2: float, density: float = 0.0) -> None:
        self.beam_area = beam_area_m2
        self.density = density
        for spring in self.springs:
            if not spring.active:
                continue
            ni = self.nodes[spring.node_i]
            nj = self.nodes[spring.node_j]
            spring.k = spring.compute_k(ni, nj, e_modul_pa, beam_area_m2)
        self._initial_mass = self.total_mass()

    def total_mass(self) -> float:
        """Summe der Massen aller aktiven Stäbe."""
        total = 0.0
        for spring in self.springs:
            if not spring.active:
                continue
            ni = self.nodes[spring.node_i]
            nj = self.nodes[spring.node_j]
            if not (ni.active and nj.active):
                continue
            total += spring.compute_mass(ni, nj, self.density, self.beam_area)
        return total

    def _per_spring_values(self, u: np.ndarray, fn) -> np.ndarray:
        values = np.zeros(len(self.springs), dtype=float)
        for i, spring in enumerate(self.springs):
            if not spring.active:
                continue
            ni = self.nodes[spring.node_i]
            nj = self.nodes[spring.node_j]
            if not (ni.active and nj.active):
                continue
            values[i] = fn(spring, ni, nj, u)
        return values

    def spring_energies(self, u: np.ndarray) -> np.ndarray:
        return self._per_spring_values(u, lambda s, ni, nj, u: s.strain_energy(ni, nj, u))

    def spring_forces(self, u: np.ndarray) -> np.ndarray:
        return self._per_spring_values(u, lambda s, ni, nj, u: s.axial_force(ni, nj, u))