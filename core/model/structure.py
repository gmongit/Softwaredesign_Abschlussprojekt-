from __future__ import annotations

import numpy as np

from core.model.node import Node
from core.model.spring import Spring


class Structure:
    def __init__(self, nodes: list[Node], springs: list[Spring]):
        self.nodes = nodes
        self.springs = springs

    @property
    def ndof(self) -> int:
        return 2 * len(self.nodes)

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

        return F
    
    def active_node_ids(self) -> list[int]:
        return [n.id for n in self.nodes if n.active]

    def active_node_count(self) -> int:
        return sum(1 for n in self.nodes if n.active)

    def total_node_count(self) -> int:
        return len(self.nodes)

    def current_mass_fraction(self) -> float:
        if self.total_node_count() == 0:
            return 0.0
        return self.active_node_count() / self.total_node_count()

    
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

            # Energie halb auf beide Endknoten verteilen
            importance[ni.id] += 0.5 * E
            importance[nj.id] += 0.5 * E

        return importance


    def fixed_dofs(self) -> list[int]:
        fixed: list[int] = []

        for node in self.nodes:
            if not node.active:
                continue
            fixed.extend(node.fixed_dofs())

        return fixed

    def protected_node_ids(self) -> list[int]:
        protected: list[int] = []
        for n in self.nodes:
            if not n.active:
                continue
            has_load = (abs(n.fx) > 0.0) or (abs(n.fy) > 0.0)
            has_bc = n.fix_x or n.fix_y
            if has_load or has_bc:
                protected.append(n.id)
        return protected
