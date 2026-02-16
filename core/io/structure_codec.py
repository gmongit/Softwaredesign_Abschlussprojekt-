from __future__ import annotations

from typing import Any

from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure


def structure_to_dict(structure: Structure) -> dict[str, Any]:
    n = len(structure.nodes)

    x = [0.0] * n
    y = [0.0] * n
    fx = [0.0] * n
    fy = [0.0] * n
    fix_x = [0] * n
    fix_y = [0] * n
    active = [0] * n

    for node in structure.nodes:
        i = node.id
        x[i] = float(node.x)
        y[i] = float(node.y)
        fx[i] = float(node.fx)
        fy[i] = float(node.fy)
        fix_x[i] = 1 if node.fix_x else 0
        fix_y[i] = 1 if node.fix_y else 0
        active[i] = 1 if node.active else 0

    si: list[int] = []
    sj: list[int] = []
    sk: list[float] = []
    sa: list[int] = []

    for s in structure.springs:
        si.append(int(s.node_i))
        sj.append(int(s.node_j))
        sk.append(float(s.k))
        sa.append(1 if s.active else 0)

    return {
        "format": "structure_v2_arrays",
        "nodes": {
            "x": x,
            "y": y,
            "fx": fx,
            "fy": fy,
            "fix_x": fix_x,
            "fix_y": fix_y,
            "active": active,
        },
        "springs": {
            "i": si,
            "j": sj,
            "k": sk,
            "active": sa,
        },
    }


def structure_from_dict(data: dict[str, Any]) -> Structure:
    fmt = str(data.get("format", "structure_v1_dicts"))

    if fmt == "structure_v2_arrays":
        nd = data["nodes"]
        x = list(nd["x"])
        y = list(nd["y"])
        fx = list(nd.get("fx", [0.0] * len(x)))
        fy = list(nd.get("fy", [0.0] * len(x)))
        fix_x = list(nd.get("fix_x", [0] * len(x)))
        fix_y = list(nd.get("fix_y", [0] * len(x)))
        active = list(nd.get("active", [1] * len(x)))

        nodes: list[Node] = []
        for i in range(len(x)):
            nodes.append(
                Node(
                    id=i,
                    x=float(x[i]),
                    y=float(y[i]),
                    fx=float(fx[i]),
                    fy=float(fy[i]),
                    fix_x=bool(fix_x[i]),
                    fix_y=bool(fix_y[i]),
                    active=bool(active[i]),
                )
            )

        sd = data["springs"]
        si = list(sd["i"])
        sj = list(sd["j"])
        sk = list(sd["k"])
        sa = list(sd.get("active", [1] * len(si)))

        springs: list[Spring] = []
        for t in range(len(si)):
            springs.append(
                Spring(
                    node_i=int(si[t]),
                    node_j=int(sj[t]),
                    k=float(sk[t]),
                    active=bool(sa[t]),
                )
            )

        return Structure(nodes=nodes, springs=springs)

    # Fallback: alter v1 dict-per-node
    nodes_data = data.get("nodes", [])
    springs_data = data.get("springs", [])

    nodes: list[Node] = [
        Node(
            id=int(n["id"]),
            x=float(n["x"]),
            y=float(n["y"]),
            fx=float(n.get("fx", 0.0)),
            fy=float(n.get("fy", 0.0)),
            fix_x=bool(n.get("fix_x", False)),
            fix_y=bool(n.get("fix_y", False)),
            active=bool(n.get("active", True)),
        )
        for n in nodes_data
    ]

    springs: list[Spring] = [
        Spring(
            node_i=int(s["node_i"]),
            node_j=int(s["node_j"]),
            k=float(s["k"]),
            active=bool(s.get("active", True)),
        )
        for s in springs_data
    ]

    return Structure(nodes=nodes, springs=springs)
