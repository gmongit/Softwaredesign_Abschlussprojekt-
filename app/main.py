# app/main.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import io

from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure
from core.solver.solver import solve
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer


# -----------------------------
# 1) Structure: einfacher Balken als Grid
# -----------------------------
def create_rectangular_grid(width: float, height: float, nx: int, ny: int, k: float) -> Structure:
    nodes: list[Node] = []
    springs: list[Spring] = []

    dx = width / (nx - 1) if nx > 1 else 0.0
    dy = height / (ny - 1) if ny > 1 else 0.0

    # Nodes
    nid = 0
    for row in range(ny):
        for col in range(nx):
            nodes.append(Node(id=nid, x=col * dx, y=row * dy))
            nid += 1

    def idx(r: int, c: int) -> int:
        return r * nx + c

    # Springs: horizontal + vertical + diagonals (gibt Fachwerk-Effekt)
    for r in range(ny):
        for c in range(nx):
            i = idx(r, c)
            if c + 1 < nx:
                springs.append(Spring(node_i=i, node_j=idx(r, c + 1), k=k))
            if r + 1 < ny:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c), k=k))
            if r + 1 < ny and c + 1 < nx:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c + 1), k=k * 0.7071))
            if r + 1 < ny and c - 1 >= 0:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c - 1), k=k * 0.7071))

    return Structure(nodes=nodes, springs=springs)


# -----------------------------
# 2) Randbedingungen + Last (wie dein Bild)
# - links unten: Loslager (fix_y)
# - rechts unten: Festlager (fix_x & fix_y)
# - oben Mitte: Kraft Fy
# -----------------------------
def apply_simply_supported_beam(structure: Structure, nx: int, ny: int, load_fy: float):
    # reset
    for n in structure.nodes:
        n.fix_x = False
        n.fix_y = False
        n.fx = 0.0
        n.fy = 0.0

    # supports (unten = row 0)
    left_bottom = structure.nodes[0]          # row 0 col 0
    right_bottom = structure.nodes[nx - 1]    # row 0 col nx-1

    left_bottom.fix_y = True                 # Loslager
    right_bottom.fix_x = True                # Festlager
    right_bottom.fix_y = True

    # load (oben Mitte)
    mid_col = nx // 2
    top_mid = structure.nodes[(ny - 1) * nx + mid_col]
    top_mid.fy = float(load_fy)


# -----------------------------
# 3) Plot (minimal)
# -----------------------------
def plot_structure(structure: Structure):
    fig, ax = plt.subplots()

    lines = []
    for s in structure.springs:
        if not s.active:
            continue
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        if not (ni.active and nj.active):
            continue
        lines.append([(ni.x, ni.y), (nj.x, nj.y)])

    if lines:
        ax.add_collection(LineCollection(lines, linewidths=1))

    xs = [n.x for n in structure.nodes if n.active]
    ys = [n.y for n in structure.nodes if n.active]
    ax.scatter(xs, ys, s=15)

    # markers for supports/loads
    for n in structure.nodes:
        if not n.active:
            continue
        if n.fix_x or n.fix_y:
            ax.plot(n.x, n.y, "^", markersize=8)  # support marker
        if abs(n.fx) > 0 or abs(n.fy) > 0:
            ax.arrow(n.x, n.y, 0.0, n.fy * 0.02, head_width=0.1, head_length=0.1)

    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    return fig


# -----------------------------
# 4) Streamlit App
# -----------------------------
st.set_page_config(page_title="Simple Topology UI", layout="wide")
st.title("🔧 Simple Topology Optimization UI")

# session init
if "structure" not in st.session_state:
    st.session_state.structure = None
if "history" not in st.session_state:
    st.session_state.history = None

with st.sidebar:
    st.header("Setup")


    width  = st.number_input("Width",  value=10.0, min_value=1.0, max_value=50.0, step=1.0)
    height = st.number_input("Height", value=2.0,  min_value=0.5, max_value=20.0, step=0.5)

    nx = st.number_input("nx (nodes in x)", value=31, min_value=5, max_value=200, step=2)
    ny = st.number_input("ny (nodes in y)", value=7,  min_value=3, max_value=50,  step=1)

    k = st.number_input("spring k", value=100.0, min_value=1.0, max_value=5000.0, step=10.0)
    load_fy = st.number_input("Load Fy (negative down)", value=-10.0, step=1.0)


    if st.button("Create Beam Grid"):
        s = create_rectangular_grid(width, height, int(nx), int(ny), float(k))
        apply_simply_supported_beam(s, int(nx), int(ny), float(load_fy))
        st.session_state.structure = s
        st.session_state.history = None
        st.success("Structure created!")

    st.divider()
    st.header("Optimize")

    target_mass = st.slider("target mass fraction", 0.1, 1.0, 0.4, 0.01)
    remove_fraction = st.slider("remove fraction/iter", 0.01, 0.2, 0.05, 0.01)
    max_iters = st.number_input("max iters", 10, 500, 120, 10)

    if st.button("Run Optimization"):
        if st.session_state.structure is None:
            st.error("Create structure first.")
        else:
            opt = EnergyBasedOptimizer(remove_fraction=float(remove_fraction), start_factor=0.3, ramp_iters=10)
            hist = opt.run(st.session_state.structure, target_mass_fraction=float(target_mass), max_iters=int(max_iters))
            st.session_state.history = hist
            st.success("Done!")


# main view
if st.session_state.structure is None:
    st.info("Create a structure in the sidebar.")
else:
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Structure")
        st.pyplot(plot_structure(st.session_state.structure), clear_figure=True)

    with col2:
        st.subheader("Info")
        st.write("Total nodes:", st.session_state.structure.total_node_count())
        st.write("Active nodes:", st.session_state.structure.active_node_count())
        st.write("Mass fraction:", st.session_state.structure.current_mass_fraction())

        if st.session_state.history is not None:
            st.subheader("History")
            st.write("Iterations:", len(st.session_state.history.mass_fraction))
            st.line_chart(st.session_state.history.mass_fraction)

    # export
    fig = plot_structure(st.session_state.structure)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    buf.seek(0)
    st.download_button("Download PNG", data=buf, file_name="structure.png", mime="image/png")
    plt.close(fig)
