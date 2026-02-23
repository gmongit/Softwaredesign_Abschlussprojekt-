import streamlit as st
import plotly.graph_objects as go
import numpy as np
from core.db.material_store import material_store
from core.solver.solver import solve
from app.service.optimization_service import prepare_structure, run_optimization, compute_forces
from app.plots import plot_structure, plot_heatmap


def compute_deformed_positions(structure, u: np.ndarray, scale: float = 1.0):
    deformed = {}

    for node in structure.nodes:
        if not node.active:
            continue

        i = node.id
        ux = u[2 * i]
        uy = u[2 * i + 1]

        x_def = node.x + scale * ux
        y_def = node.y + scale * uy

        deformed[i] = (x_def, y_def)

    return deformed


def plot_deformed_structure(structure, u, scale) -> go.Figure:
    fig = go.Figure()
    sx, sy = [], []

    for s in structure.springs:
        if not s.active:
            continue

        ni = structure.nodes[s.node_i]
        nj = structure.nodes[s.node_j]

        if not ni.active or not nj.active:
            continue

        ux_i = u[2 * ni.id]
        uy_i = u[2 * ni.id + 1]

        ux_j = u[2 * nj.id]
        uy_j = u[2 * nj.id + 1]

        x0 = ni.x + scale * ux_i
        y0 = ni.y + scale * uy_i
        x1 = nj.x + scale * ux_j
        y1 = nj.y + scale * uy_j

        sx += [x0, x1, None]
        sy += [y0, y1, None]

    fig.add_trace(go.Scatter(
        x=sx, y=sy,
        mode="lines",
        line=dict(color="red", width=2),
        showlegend=False
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

    beam_diameter_mm = st.number_input("Balkendurchmesser (mm)", 10, 1000, 120, 10)
    beam_area_mm2 = beam_diameter_mm ** 2 * 3.141592653589793 / 4
    st.caption(f"Querschnittsfläche: {beam_area_mm2:.1f} mm²")

    materials = material_store.list_materials()
    if materials:
        selected_material = st.selectbox("Material", [m.name for m in materials])
        mat = next(m for m in materials if m.name == selected_material)
        st.caption(f"E-Modul: {mat.e_modul} GPa  |  Dichte: {mat.dichte} kg/m³")
    else:
        st.warning("Kein Material vorhanden. Bitte zuerst im Material Manager anlegen.")
        selected_material = None
        mat = None

    factor_of_safety = st.slider("Sicherheitsfaktor", 1.0, 10.0, 1.4, 0.1)
    st.markdown("<br>", unsafe_allow_html=True)
    use_symmetry    = True
    target_mass     = st.slider("Ziel-Massenanteil", 0.1, 1.0, 0.4, 0.01)
    remove_fraction = st.slider("Entfernungsrate / Iteration", 0.01, 0.2, 0.05, 0.01)
    max_iters       = st.number_input("Max. Iterationen", 10, 500, 120, 10)

    if st.button("▶ Optimierung starten", type="primary"):
        try:
            prepare_structure(st.session_state.structure, selected_material if mat else None, beam_area_mm2)
        except ValueError as e:
            st.error(str(e))
        else:
            hist = run_optimization(
                st.session_state.structure,
                remove_fraction=float(remove_fraction),
                target_mass_fraction=float(target_mass),
                max_iters=int(max_iters),
                enforce_symmetry=use_symmetry,
                nx=st.session_state.nx if use_symmetry else None,
            )
            st.session_state.history = hist
            mode = "symmetrisch" if use_symmetry else "normal"
            st.success(f"✅ Fertig ({mode})! Masse: {st.session_state.structure.current_mass_fraction():.1%}")

# --- Visualisierung ---
if st.session_state.history is not None:
    st.markdown("**Ansicht**")
    view = st.segmented_control(
        "Ansicht",
        options=["Struktur", "Heatmap", "Lastpfade", "Verformung"],
        default="Heatmap",
        label_visibility="collapsed",
    )

    fig = None

    if view == "Struktur":
        fig = plot_structure(st.session_state.structure)
        st.plotly_chart(fig, width='stretch')

    elif view == "Heatmap":
        energies = compute_forces(st.session_state.structure)
        if energies is None:
            st.warning("Kraftverteilung nicht berechenbar – Struktur wird ohne Heatmap angezeigt.")
        fig = plot_heatmap(st.session_state.structure, energies=energies)
        st.plotly_chart(fig, width='stretch')

    elif view == "Lastpfade":
        st.info("Lastpfade-Visualisierung folgt in einem späteren Schritt.")

    elif view == "Verformung":
        K = st.session_state.structure.assemble_K()
        F = st.session_state.structure.assemble_F()
        fixed = st.session_state.structure.fixed_dofs()
        u = solve(K, F, fixed)

        nodes = [n for n in st.session_state.structure.nodes if n.active]
        x_vals = [n.x for n in nodes]
        y_vals = [n.y for n in nodes]
        width  = max(x_vals) - min(x_vals)
        height = max(y_vals) - min(y_vals)
        u_max = np.max(np.abs(u))
        scale = 0.2 * max(width, height) / u_max if u_max > 0 else 1.0

        fig = plot_deformed_structure(st.session_state.structure, u, scale)
        st.plotly_chart(fig, use_container_width=True)

    if fig is not None:
        st.divider()
        base = st.session_state.get("case_name") or ""
        filename = f"{base}.png" if base else "struktur.png"
        st.download_button(
            label="📥 Als PNG speichern",
            data=fig.to_image(format="png", width=1600, height=600, scale=2),
            file_name=filename,
            mime="image/png",
        )

    # --- Metriken ---
    structure = st.session_state.structure
    c1, c2, c3 = st.columns(3)
    c1.metric("Aktive Knoten", structure.active_node_count())
    c2.metric("Gesamt Knoten", structure.total_node_count())
    c3.metric("Massenanteil", f"{structure.current_mass_fraction():.1%}")

    # --- Optimierungsverlauf ---
    hist = st.session_state.history
    if hist is not None and len(hist.mass_fraction) > 0:
        st.markdown("**Optimierungsverlauf**")
        st.line_chart(hist.mass_fraction, x_label="Iteration", y_label="Massenanteil")

else:
    st.info("Starte die Optimierung über die Sidebar.")
