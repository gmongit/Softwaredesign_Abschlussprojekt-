import streamlit as st
import plotly.graph_objects as go
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer
from core.solver.solver import solve
from heatmap import plot_heatmap

def plot_structure(structure, energies=None) -> go.Figure:
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
        if not n.active:
            continue
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


# --- UI ---
st.title("⚡ Optimizer")

if st.session_state.structure is None:
    st.warning("Bitte zuerst im 'Structure Creator' ein Modell erstellen.")
    st.stop()

with st.sidebar:
    st.header("Einstellungen")

    use_symmetry    = True
    target_mass     = st.slider("Ziel-Massenanteil", 0.1, 1.0, 0.4, 0.01)
    remove_fraction = st.slider("Entfernungsrate / Iteration", 0.01, 0.2, 0.05, 0.01)
    max_iters       = st.number_input("Max. Iterationen", 10, 500, 120, 10)

    if st.button("▶ Optimierung starten", type="primary"):
        opt = EnergyBasedOptimizer(
            remove_fraction=float(remove_fraction),
            start_factor=0.3,
            ramp_iters=10,
            enforce_symmetry=use_symmetry,
            nx=st.session_state.nx if use_symmetry else None,
        )
        hist = opt.run(
            st.session_state.structure,
            target_mass_fraction=float(target_mass),
            max_iters=int(max_iters),
        )
        st.session_state.history = hist
        mode = "symmetrisch" if use_symmetry else "normal"
        st.success(f"✅ Fertig ({mode})! Masse: {st.session_state.structure.current_mass_fraction():.1%}")

# Plot anzeigen (nach Optimierung)
if st.session_state.history is not None:
    K = st.session_state.structure.assemble_K()
    F = st.session_state.structure.assemble_F()
    fixed = st.session_state.structure.fixed_dofs()
    u = solve(K, F, fixed)
    energies = st.session_state.structure.spring_energies(u)
    st.plotly_chart(plot_heatmap(st.session_state.structure, energies=energies), use_container_width=True)
else:
    st.info("Starte die Optimierung über die Sidebar.")