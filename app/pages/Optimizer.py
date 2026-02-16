import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import io
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer

def plot_structure(structure):
    fig, ax = plt.subplots()
    lines = [[(structure.nodes[s.node_i].x, structure.nodes[s.node_i].y), 
              (structure.nodes[s.node_j].x, structure.nodes[s.node_j].y)] 
             for s in structure.springs if s.active]
    if lines: ax.add_collection(LineCollection(lines, linewidths=1))
    ax.set_aspect("equal")
    return fig

st.title("⚡ Optimizer")

if st.session_state.structure is None:
    st.warning("Bitte zuerst im 'Structure Creator' ein Modell erstellen.")
else:
    with st.sidebar:
        st.header("Einstellungen")
        target_mass = st.slider("Target mass fraction", 0.1, 1.0, 0.4)
        remove_frac = st.slider("Remove fraction/iter", 0.01, 0.2, 0.05)
        max_iters = st.number_input("Max iters", value=120)

        if st.button("Run Optimization"):
            opt = EnergyBasedOptimizer(remove_fraction=float(remove_frac), start_factor=0.3, ramp_iters=10)
            hist = opt.run(st.session_state.structure, target_mass_fraction=float(target_mass), max_iters=int(max_iters))
            st.session_state.history = hist
            st.success("Optimierung abgeschlossen!")

    # Anzeige der Ergebnisse
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Aktuelle Struktur")
        fig = plot_structure(st.session_state.structure)
        st.pyplot(fig)
        
        # Download Button
        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        st.download_button("Download PNG", data=buf.getvalue(), file_name="opt_result.png")

    with col2:
        st.subheader("Info")
        st.write("Masseanteil:", round(st.session_state.structure.current_mass_fraction(), 3))
        if st.session_state.history:
            st.line_chart(st.session_state.history.mass_fraction)