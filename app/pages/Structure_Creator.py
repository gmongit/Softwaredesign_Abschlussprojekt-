import streamlit as st
import plotly.graph_objects as go

from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure


def create_rectangular_grid(width: float, height: float, nx: int, ny: int, k: float) -> Structure:
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
                springs.append(Spring(node_i=i, node_j=idx(r, c + 1), k=k))
            if r + 1 < ny:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c), k=k))
            if r + 1 < ny and c + 1 < nx:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c + 1), k=k * 0.7071))
            if r + 1 < ny and c - 1 >= 0:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c - 1), k=k * 0.7071))

    return Structure(nodes=nodes, springs=springs)


def apply_simply_supported_beam(structure: Structure, nx: int, ny: int, load_fy: float):
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


def plot_structure(structure: Structure) -> go.Figure:
    sx, sy = [], []
    for s in structure.springs:
        if not s.active:
            continue
        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]
        sx += [ni.x, nj.x, None]
        sy += [ni.y, nj.y, None]

    nx_vals, ny_vals, colors, symbols, hover = [], [], [], [], []
    for n in structure.nodes:
        nx_vals.append(n.x)
        ny_vals.append(n.y)
        if n.fix_x or n.fix_y:
            colors.append("#FF6B35")
            symbols.append("triangle-up")
            hover.append(f"Knoten {n.id}<br>Auflager: fix_x={n.fix_x}, fix_y={n.fix_y}")
        elif abs(n.fx) > 0 or abs(n.fy) > 0:
            colors.append("#FFD700")
            symbols.append("diamond")
            hover.append(f"Knoten {n.id}<br>Last: Fy={n.fy:.2f}")
        else:
            colors.append("#888888")
            symbols.append("circle")
            hover.append(f"Knoten {n.id}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sx, y=sy,
        mode="lines",
        line=dict(color="#4A90D9", width=1.2),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=nx_vals, y=ny_vals,
        mode="markers",
        marker=dict(color=colors, size=8, symbol=symbols,
                    line=dict(width=0.5, color="#222")),
        text=hover,
        hoverinfo="text",
        showlegend=False,
    ))
    fig.update_layout(
        paper_bgcolor="#1A1A2E",
        plot_bgcolor="#16213E",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=400,
    )
    return fig



st.title("🏗️ Structure Creator")

with st.sidebar:
    st.header("Parameter")
    width   = st.number_input("Breite",             min_value=1.0, value=10.0, step=1.0)
    height  = st.number_input("Höhe",               min_value=0.5, value=2.0,  step=0.5)
    nx      = st.number_input("Knoten X (nx)",      min_value=2,   value=31,   step=2)
    ny      = st.number_input("Knoten Y (ny)",      min_value=2,   value=7,    step=1)
    k       = st.number_input("Federsteifigkeit k", min_value=1.0, value=100.0)
    load_fy = st.number_input("Last Fy [N]",                       value=-10.0)

    if st.button("✅ Struktur erstellen", type="primary"):
        
        s = create_rectangular_grid(float(width), float(height), int(nx), int(ny), float(k))
        apply_simply_supported_beam(s, int(nx), int(ny), float(load_fy))

        import copy                                        # ← neu
        st.session_state.structure = copy.deepcopy(s)     # ← neu (Kopie für Optimizer)
        st.session_state.original_structure = s 
        st.session_state.nx = int(nx)
        st.session_state.ny = int(ny)
        st.session_state.history = None
        st.success(f"Struktur erstellt: {int(nx) * int(ny)} Knoten, {len(s.springs)} Federn")

if st.session_state.get("original_structure"):
    st.plotly_chart(plot_structure(st.session_state.original_structure), ...)
else:
    st.info("Erstelle eine Struktur über die Sidebar.")