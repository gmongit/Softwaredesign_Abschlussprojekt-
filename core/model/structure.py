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

        self.support_ids: set[int] = set()
        self.load_ids: set[int] = set()
        self.protected_base: set[int] = set()


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
    
    def _register_special_nodes(self) -> None:
        """Sucht Lager und Lastknoten und Speichert diese"""
        self.support_ids = {n.id for n in self.nodes if n.fix_x or n.fix_y}
        self.load_ids = {n.id for n in self.nodes if abs(n.fx) > 1e-9 or abs(n.fy) > 1e-9}
        self.protected_base = self.support_ids | self.load_ids

    def is_valid_topology(self, exclude_nodes: set[int] | None = None) -> bool:
        """Prüft Zusammenhang und Lastpfade (Last -> Lager)."""
        exclude = exclude_nodes or set()
        G = self.build_graph(exclude)

        if G.number_of_nodes() <= 1:
            return True
        if not nx.is_connected(G):
            return False

        current_supports = self.support_ids - exclude
        current_loads = [lid for lid in self.load_ids if lid not in exclude]

        if not current_loads:
            return True
        if not current_supports:
            return False

        for lid in current_loads: 
            if lid not in G:
                return False
            reachable = nx.node_connected_component(G, lid)
            if reachable.isdisjoint(current_supports):
                return False
            
        return True

    def _find_removable_nodes(self) -> set[int]:
        """Findet strukturell nutzlose Knoten: isolierte Inseln + tote Äste."""
        protected = self._protected_ids()
        removable: set[int] = set()
        G = self.build_graph()

        # Isolierte Inseln keine Verbindung zu Lager & Last
        for comp in nx.connected_components(G):
            has_support = not comp.isdisjoint(self.support_ids)
            has_load = not comp.isdisjoint(self.load_ids)
            if not has_support or not has_load:
                removable |= comp

        # Wenn ein Teilgraph nur über einen Knoten erreichbar ist (Ohne Lager, Last)
        changed = True
        while changed:
            changed = False
            remaining = set(G.nodes()) - removable
            if len(remaining) < 2:
                break
            
            work = G.subgraph(remaining).copy()
            for ap in list(nx.articulation_points(work)):
                work_without = work.copy()
                work_without.remove_node(ap)
                
                for fragment in nx.connected_components(work_without):
                    if fragment.isdisjoint(protected):
                        removable |= fragment
                        if ap not in protected:
                            removable.add(ap)
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

    def detect_symmetry(self, eps: float = 1e-6) -> tuple[bool, dict[int, int] | None]:
        """Prüft vertikale Symmetrie. Gibt (is_symmetric, mirror_map) zurück."""
        active = [n for n in self.nodes if n.active]
        if len(active) < 2:
            return False, None

        # 1) Symmetrieachse aus Lagern
        supports = [n for n in active if n.fix_x or n.fix_y]
        if len(supports) < 2:
            return False, None
        x_center = (min(n.x for n in supports) + max(n.x for n in supports)) / 2

        for s in supports:
            mx = 2 * x_center - s.x
            if not any(abs(n.x - mx) < eps and abs(n.y - s.y) < eps
                       and (n.fix_x or n.fix_y) for n in supports):
                return False, None

        # 2) Lasten auf Achse oder symmetrisch paarweise
        loaded = [n for n in active if abs(n.fx) > 0 or abs(n.fy) > 0]
        for ln in loaded:
            if abs(ln.fx) > eps:
                return False, None
            if abs(ln.x - x_center) > eps:
                mx = 2 * x_center - ln.x
                partner = [n for n in loaded
                           if abs(n.x - mx) < eps and abs(n.y - ln.y) < eps]
                if not partner or abs(partner[0].fy - ln.fy) > eps:
                    return False, None

        # 3) Mirror-Map für alle Knoten
        mirror_map: dict[int, int] = {}
        coord_to_id = {(round(n.x / eps) * eps, round(n.y / eps) * eps): n.id for n in active}

        for n in active:
            mx = 2 * x_center - n.x
            key = (round(mx / eps) * eps, round(n.y / eps) * eps)
            mid = coord_to_id.get(key)
            if mid is None:
                return False, None
            mirror_map[n.id] = mid

        # 4) Springs symmetrisch
        edge_set = set()
        for s in self.springs:
            if not s.active:
                continue
            ni, nj = self.nodes[s.node_i], self.nodes[s.node_j]
            if ni.active and nj.active:
                edge_set.add((min(s.node_i, s.node_j), max(s.node_i, s.node_j)))

        for a, b in list(edge_set):
            ma, mb = mirror_map[a], mirror_map[b]
            if (min(ma, mb), max(ma, mb)) not in edge_set:
                return False, None

        return True, mirror_map