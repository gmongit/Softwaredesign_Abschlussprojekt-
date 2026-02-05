import matplotlib.pyplot as plt
from core.model.structure import Structure

def plot_structure(struct: Structure, show_nodes: bool = False):
    node_map = struct.node_by_id()

    fig, ax = plt.subplots()
    for s in struct.springs:
        if not s.active:
            continue
        a = node_map[s.n1]
        b = node_map[s.n2]
        ax.plot([a.x, b.x], [a.y, b.y])

    if show_nodes:
        xs = [n.x for n in struct.nodes]
        ys = [n.y for n in struct.nodes]
        ax.scatter(xs, ys, s=8)

    ax.set_aspect("equal", adjustable="box")
    ax.invert_yaxis()  # optional: looks more like screen coords
    ax.set_title("Structure (nodes + springs)")
    return fig
