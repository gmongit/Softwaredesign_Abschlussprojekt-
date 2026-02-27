import copy
import streamlit as st

from app.shared import (
    material_sidebar, show_structure_status, show_stop_reason,
    show_heatmap_view, show_loadpaths_view, show_deformation_view,
)
from app.service.optimization_service import (
    validate_structure, run_simp_optimization,
)
from app.plots import (
    plot_structure, plot_simp_structure, plot_simp_convergence,
)


st.title("📐 SIMP Optimizer")

if st.session_state.get("structure") is None:
    st.warning("Bitte zuerst im 'Structure Creator' ein Modell erstellen.")
    st.stop()

_progress_ph = st.empty()
_live_ph = st.empty()

with st.sidebar:
    st.header("Einstellungen")

    st.subheader("Material")
    selected_material, mat, beam_area_mm2, max_stress_pa = material_sidebar()

    st.subheader("SIMP Parameter")
    volume_fraction = st.slider("Ziel-Massenanteil", 0.1, 1.0, 0.4, 0.05)
    penalty = st.slider("SIMP Penalty p", 1.0, 5.0, 3.0, 0.5,
                        help="p=1: reine Sizing-Optimierung | p=3: starke 0/1-Penalisierung")

    with st.expander("Erweiterte Einstellungen"):
        max_iters = st.number_input("Max. Iterationen", 10, 500, 100, 10)
        eta = st.slider("OC Dämpfung η", 0.1, 1.0, 0.5, 0.1)
        move_limit = st.slider("Move-Limit", 0.05, 0.5, 0.2, 0.05)
        tol = st.number_input("Konvergenz-Toleranz", 1e-6, 1e-1, 1e-3, format="%.1e")

    validation = validate_structure(st.session_state.structure)
    show_structure_status(validation)

    if st.button("▶ SIMP Optimierung starten", type="primary", disabled=not validation.ok):
        structure_copy = copy.deepcopy(st.session_state.structure)

        def _on_iter(struct, i, compliance, vol_frac):
            prog = min(1.0, (i + 1) / int(max_iters))
            _progress_ph.progress(prog,
                text=f"Iteration {i} | Compliance = {compliance:.2f} | Masse = {vol_frac:.1%}")
            with _live_ph.container():
                st.plotly_chart(
                    plot_simp_structure(struct),
                    width='stretch',
                    key=f"_simp_live_{i}",
                )

        try:
            hist = run_simp_optimization(
                structure_copy,
                material_name=selected_material,
                beam_area_mm2=beam_area_mm2,
                volume_fraction=float(volume_fraction),
                penalty=float(penalty),
                max_iters=int(max_iters),
                eta=float(eta),
                move_limit=float(move_limit),
                tol=float(tol),
                on_iter=_on_iter,
            )
            _progress_ph.empty()
            _live_ph.empty()
            st.session_state.simp_history = hist
            st.session_state.simp_structure = structure_copy
            st.success("Optimierung abgeschlossen!")
        except ValueError as e:
            st.error(str(e))

simp_hist = st.session_state.get("simp_history")
if simp_hist is not None and simp_hist.stop_reason:
    simp_struct = st.session_state.get("simp_structure")
    vol = simp_hist.volume_fraction[-1] if simp_hist.volume_fraction else 0
    show_stop_reason(simp_hist.stop_reason, vol)

if st.session_state.get("simp_history") is None:
    st.info("Starte die SIMP-Optimierung über die Sidebar.")
    st.stop()

hist = st.session_state.simp_history
structure = st.session_state.simp_structure

tab1, tab2 = st.tabs(["Struktur", "Konvergenz"])

with tab1:
    view = st.segmented_control(
        "Ansicht",
        options=["Dicken-Plot", "Struktur", "Heatmap", "Verformung"],
        default="Dicken-Plot",
        label_visibility="collapsed",
    )

    if view == "Dicken-Plot":
        fig = plot_simp_structure(structure)
        st.plotly_chart(fig, width='stretch')
    elif view == "Struktur":
        fig = plot_structure(structure)
        st.plotly_chart(fig, width='stretch')
    elif view == "Heatmap":
        show_heatmap_view(structure, key="simp_heatmap")
    elif view == "Verformung":
        show_deformation_view(structure, key="simp_deform")

    c1, c2, c3 = st.columns(3)
    c1.metric("Compliance", f"{hist.compliance[-1]:.2f}" if hist.compliance else "N/A")
    c2.metric("Massenanteil", f"{hist.volume_fraction[-1]:.1%}" if hist.volume_fraction else "N/A")
    c3.metric("Iterationen", len(hist.compliance))

with tab2:
    fig = plot_simp_convergence(hist)
    st.plotly_chart(fig, width='stretch')
