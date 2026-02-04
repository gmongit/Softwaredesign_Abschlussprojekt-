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

    def fixed_dofs(self) -> list[int]:
        fixed: list[int] = []

        for node in self.nodes:
            if not node.active:
                continue
            fixed.extend(node.fixed_dofs())

        return fixed
