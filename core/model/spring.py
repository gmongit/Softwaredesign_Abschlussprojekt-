from dataclasses import dataclass

@dataclass
class Spring:
    id: int
    n1: int  # node id
    n2: int  # node id
    k: float = 1.0
    active: bool = True
