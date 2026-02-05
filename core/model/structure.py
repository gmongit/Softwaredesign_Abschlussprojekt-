from dataclasses import dataclass
from typing import List, Dict, Tuple
from .node import Node
from .spring import Spring

@dataclass
class Structure:
    nodes: List[Node]
    springs: List[Spring]

    def node_by_id(self) -> Dict[int, Node]:
        return {n.id: n for n in self.nodes}

    @staticmethod
    def mbb_beam(nx: int = 20, ny: int = 8, k: float = 1.0, diagonals: bool = True) -> "Structure":
        """
        2d gitterstruktur in form eines mbb-trägers
        """
        nodes: List[Node] = []
        springs: List[Spring] = []

        # create nodes
        def nid(ix: int, iy: int) -> int:
            return iy * (nx + 1) + ix

        for iy in range(ny + 1):
            for ix in range(nx + 1):
                nodes.append(Node(id=nid(ix, iy), x=float(ix), y=float(iy)))

        # helpers to add spring
        sid = 0
        def add(a: int, b: int):
            nonlocal sid
            springs.append(Spring(id=sid, n1=a, n2=b, k=k, active=True))
            sid += 1

        # connect grid (horizontal + vertical + optional diagonals)
        for iy in range(ny + 1):
            for ix in range(nx + 1):
                a = nid(ix, iy)
                if ix < nx:
                    add(a, nid(ix + 1, iy))          # horizontal
                if iy < ny:
                    add(a, nid(ix, iy + 1))          # vertical
                if diagonals and ix < nx and iy < ny:
                    add(a, nid(ix + 1, iy + 1))      # diag /
                    add(nid(ix + 1, iy), nid(ix, iy + 1))  # diag \

        # boundary conditions (simple supported beam):
        # left-bottom: fixed x and y (pin)
        # right-bottom: fixed y only (roller)
        left = nid(0, 0)
        right = nid(nx, 0)
        for n in nodes:
            if n.id == left:
                n.fixed_x = True
                n.fixed_y = True
            if n.id == right:
                n.fixed_y = True

        # load at mid-top
        load_node = nid(nx // 2, ny)
        for n in nodes:
            if n.id == load_node:
                n.fy = -1.0

        return Structure(nodes=nodes, springs=springs)
