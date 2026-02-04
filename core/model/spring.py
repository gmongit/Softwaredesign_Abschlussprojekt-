from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from core.model.node import Node


@dataclass(slots=True)
class Spring:
    node_i: int
    node_j: int
    k: float
    active: bool = True

    def length(self, ni: Node, nj: Node) -> float:
        dx = nj.x - ni.x
        dy = nj.y - ni.y
        return float(np.hypot(dx, dy))

    def direction_unit(self, ni: Node, nj: Node) -> np.ndarray:
        dx = nj.x - ni.x
        dy = nj.y - ni.y
        L = float(np.hypot(dx, dy))
        if L <= 0.0:
            raise ValueError("Spring length must be > 0 (nodes have identical coordinates).")
        return np.array([dx / L, dy / L], dtype=float)

    def element_stiffness_matrix(self, ni: Node, nj: Node) -> np.ndarray:
        """
        Returns the 4x4 stiffness matrix Ke for the spring between nodes ni and nj.
        DOF order: [ni.x, ni.y, nj.x, nj.y]
        """
        e = self.direction_unit(ni, nj)
        O = np.outer(e, e)  # 2x2
        k_local = self.k * np.array([[1.0, -1.0], [-1.0, 1.0]], dtype=float)  # 2x2
        Ke = np.kron(k_local, O)  # (2x2) ⊗ (2x2) -> 4x4
        return Ke
