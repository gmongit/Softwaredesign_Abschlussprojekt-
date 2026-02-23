from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure


def create_rectangular_grid(width: float, height: float, nx: int, ny: int) -> Structure:
    nodes: list[Node] = []
    springs: list[Spring] = []

    dx = width / (nx - 1) if nx > 1 else 0.0
    dy = height / (ny - 1) if ny > 1 else 0.0

    nid = 0
    for row in range(ny):
        for col in range(nx):
            nodes.append(Node(id=nid, x=col * dx, y=row * dy))
            nid += 1

    def idx(r: int, c: int) -> int:
        return r * nx + c

    for r in range(ny):
        for c in range(nx):
            i = idx(r, c)
            if c + 1 < nx:
                springs.append(Spring(node_i=i, node_j=idx(r, c + 1), k=1.0))
            if r + 1 < ny:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c), k=1.0))
            if r + 1 < ny and c + 1 < nx:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c + 1), k=1.0))
            if r + 1 < ny and c - 1 >= 0:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c - 1), k=1.0))

    return Structure(nodes=nodes, springs=springs)


def apply_simply_supported_beam(structure: Structure, nx: int, ny: int, load_fy: float) -> None:
    for n in structure.nodes:
        n.fix_x = False
        n.fix_y = False
        n.fx = 0.0
        n.fy = 0.0

    structure.nodes[0].fix_y = True
    structure.nodes[nx - 1].fix_x = True
    structure.nodes[nx - 1].fix_y = True

    mid_col = nx // 2
    structure.nodes[(ny - 1) * nx + mid_col].fy = float(load_fy)