from dataclasses import dataclass

@dataclass
class Node:
    id: int
    x: float
    y: float

    fx: float = 0.0
    fy: float = 0.0

    fixed_x: bool = False
    fixed_y: bool = False
