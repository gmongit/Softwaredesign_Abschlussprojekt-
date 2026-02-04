from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class Node:
    id: int
    x: float
    y: float
    fx: float = 0.0
    fy: float = 0.0
    fix_x: bool = False
    fix_y: bool = False
    active: bool = True

    @property
    def dof_x(self) -> int:
        return 2 * self.id

    @property
    def dof_y(self) -> int:
        return 2 * self.id + 1

    def fixed_dofs(self) -> list[int]:
        dofs: list[int] = []
        if self.fix_x:
            dofs.append(self.dof_x)
        if self.fix_y:
            dofs.append(self.dof_y)
        return dofs

    def force_vector_entries(self) -> tuple[int, float, int, float]:
        return self.dof_x, self.fx, self.dof_y, self.fy
