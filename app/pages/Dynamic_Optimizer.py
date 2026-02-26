import copy
import math

import streamlit as st
import plotly.graph_objects as go

import numpy as np

from core.solver.eigenvalue_solver import solve_eigenvalue
from core.solver.mass_matrix import assemble_M
from app.plots import plot_structure, plot_deformed_structure, generate_mode_animation_gif
from app.service.optimization_service import (
    prepare_structure, validate_structure,
    run_dynamic_optimization, continue_dynamic_optimization, is_retryable,
)
from app.shared import (
    material_sidebar, show_structure_status, show_stop_reason,
    show_heatmap_view, show_loadpaths_view, show_deformation_view,
    make_dynamic_progress_callback,
)

# Guard
if st.session_state.get("structure") is None:
    st.warning("Bitte zuerst im 'Structure Creator' ein Modell erstellen.")
    st.stop()

st.title("🌊 Dynamic Optimizer")

# Live-Platzhalter (werden während der Optimierung befüllt)
_progress_ph = st.empty()
_live_ph     = st.empty()

# Sidebar
with st.sidebar:
    st.header("Einstellungen")

    st.subheader("Material")
    selected_material, mat, beam_area_mm2, max_stress_pa = material_sidebar()

    # Dynamik
    st.subheader("Dynamik")

    omega_excitation = st.number_input(
        "Erregerkreisfrequenz ω_E [rad/s]",
        min_value=0.1, max_value=100000.0, value=100.0, step=10.0,
    )
    st.caption(f"≙ {omega_excitation / (2.0 * math.pi):.2f} Hz")

    alpha = st.slider("Gewichtung dynamisch", 0.0, 1.0, 0.5, 0.05)
    st.caption("0 = rein statisch  |  1 = rein dynamisch")

    st.markdown("<br>", unsafe_allow_html=True)

    target_mass     = st.slider("Ziel-Massenanteil", 0.1, 1.0, 0.4, 0.01)
    remove_fraction = st.slider("Entfernungsrate / Iteration", 0.01, 0.2, 0.05, 0.01)
    max_iters       = st.number_input("Max. Iterationen", 10, 500, 120, 10)

    _omega_excitation = float(omega_excitation)
    _alpha            = float(alpha)
    _remove_fraction  = float(remove_fraction)
    _target_mass      = float(target_mass)
    _max_iters        = int(max_iters)

    validation = validate_structure(st.session_state.structure)
    show_structure_status(validation)

    if st.button("▶ Dynamische Optimierung starten", type="primary", disabled=not validation.ok):
        try:
            structure_copy = copy.deepcopy(st.session_state.structure)
            prepare_structure(structure_copy, selected_material, beam_area_mm2)

            hist = run_dynamic_optimization(
                structure_copy,
                omega_excitation=_omega_excitation,
                alpha=_alpha,
                remove_fraction=_remove_fraction,
                target_mass_fraction=_target_mass,
                max_iters=_max_iters,
                max_stress=max_stress_pa,
                on_iter=make_dynamic_progress_callback(_progress_ph, _live_ph, _target_mass, "_live"),
            )
        except ValueError as e:
            st.error(str(e))
        else:
            _progress_ph.empty()
            _live_ph.empty()
            st.session_state.dyn_history   = hist
            st.session_state.dyn_structure = structure_copy
            st.session_state.dyn_omega_e   = _omega_excitation
            st.session_state.mode_gif_bytes = None
            is_sym, _ = structure_copy.detect_symmetry()
            mode = "symmetrisch" if is_sym else "normal"
            st.success(
                f"✅ Fertig ({mode})! "
                f"Masse: {structure_copy.current_mass_fraction():.1%}  |  "
                f"ω₁ = {hist.omega_1[-1]:.2f} rad/s  |  "
                f"f₁ = {hist.f_1[-1]:.3f} Hz"
                if hist.omega_1 else
                f"✅ Fertig ({mode})! Masse: {structure_copy.current_mass_fraction():.1%}"
            )

    # Retry-Button wenn stop_reason nicht terminal
    dyn_hist = st.session_state.get("dyn_history")
    if dyn_hist is not None and is_retryable(dyn_hist):
        if st.button("🔄 Weiter optimieren"):
            try:
                continue_dynamic_optimization(
                    st.session_state.dyn_structure, dyn_hist,
                    omega_excitation=_omega_excitation,
                    alpha=_alpha,
                    remove_fraction=_remove_fraction,
                    target_mass_fraction=_target_mass,
                    max_iters=_max_iters,
                    max_stress=max_stress_pa,
                    on_iter=make_dynamic_progress_callback(_progress_ph, _live_ph, _target_mass, "_retry"),
                )
                _progress_ph.empty()
                _live_ph.empty()
                st.session_state.mode_gif_bytes = None
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    # Force-Button wenn Optimierung zu früh gestoppt wurde
    dyn_struct = st.session_state.get("dyn_structure")
    if (dyn_struct is not None
            and dyn_struct.current_mass_fraction() > _target_mass + 0.01):
        if st.button("⚠️ Trotzdem bis zur Zielmasse entfernen - Nur für Testzwecke!", type="secondary"):
            try:
                hist_force = run_dynamic_optimization(
                    dyn_struct,
                    omega_excitation=_omega_excitation,
                    alpha=_alpha,
                    remove_fraction=_remove_fraction,
                    target_mass_fraction=_target_mass,
                    max_iters=_max_iters,
                    on_iter=make_dynamic_progress_callback(_progress_ph, _live_ph, _target_mass, "_force"),
                    force=True,
                )
                _progress_ph.empty()
                _live_ph.empty()
                st.session_state.dyn_history = hist_force
                st.session_state.mode_gif_bytes = None
                mf = dyn_struct.current_mass_fraction()
                st.success(f"✅ Fertig (erzwungen)! Masse: {mf:.1%}")
            except ValueError as e:
                st.error(str(e))

# --- Status ---
dyn_hist_status = st.session_state.get("dyn_history")
if dyn_hist_status is not None and dyn_hist_status.stop_reason:
    dyn_struct_status = st.session_state.get("dyn_structure")
    mf = dyn_struct_status.current_mass_fraction() if dyn_struct_status else 0.0
    show_stop_reason(dyn_hist_status.stop_reason, mf)

# Visualisierung
if st.session_state.get("dyn_history") is None:
    st.info("Starte die Optimierung über die Sidebar.")
    st.stop()

hist      = st.session_state.dyn_history
structure = st.session_state.dyn_structure
omega_e   = st.session_state.get("dyn_omega_e", omega_excitation)

tab1, tab2, tab3, tab4 = st.tabs([
    "Struktur", "Eigenfrequenz-Verlauf", "Frequenzabstand", "Massenabbau"
])

with tab1:
    view = st.segmented_control(
        "Ansicht",
        options=["Struktur", "Heatmap", "Lastpfade", "Verformung (statisch)", "Eigenmode"],
        default="Struktur",
        label_visibility="collapsed",
    )

    if view == "Struktur":
        fig = plot_structure(structure)
        st.plotly_chart(fig, width='stretch', key="tab_struktur")

    elif view == "Heatmap":
        show_heatmap_view(structure, key="tab_heatmap")

    elif view == "Lastpfade":
        show_loadpaths_view(structure, key="tab_lastpfade")

    elif view == "Verformung (statisch)":
        show_deformation_view(structure, key="tab_verformung")

    elif view == "Eigenmode":
        K     = structure.assemble_K()
        M     = assemble_M(structure, node_mass=1.0)
        fixed = structure.fixed_dofs()
        eigenvalues, eigenvectors = solve_eigenvalue(K, M, fixed, n_modes=1)

        omega_1_vis = float(np.sqrt(max(0.0, float(eigenvalues[0]))))
        eigvec_1    = eigenvectors[:, 0]

        # Normierung auf max|u|=1 für rein visuelle Darstellung
        max_disp = float(np.max(np.abs(eigvec_1)))
        u_ref_ev = max_disp if max_disp > 0.0 else 1.0

        nodes_active = [n for n in structure.nodes if n.active]
        x_vals = [n.x for n in nodes_active]
        y_vals = [n.y for n in nodes_active]
        struct_size = max(
            max(x_vals) - min(x_vals) if x_vals else 1.0,
            max(y_vals) - min(y_vals) if y_vals else 1.0,
        )
        auto_scale_ev = 0.2 * struct_size / u_ref_ev if u_ref_ev > 0.0 else 1.0
        scale_ev = st.slider(
            "Skalierungsfaktor Eigenmode",
            min_value=0.1,
            max_value=float(max(10.0, auto_scale_ev * 3)),
            value=float(round(auto_scale_ev, 2)),
            step=0.1,
        )
        st.caption(f"ω₁ = {omega_1_vis:.2f} rad/s  |  f₁ = {omega_1_vis / (2.0 * math.pi):.3f} Hz  "
                   f"(Darstellung rein qualitativ, keine physikalische Amplitude)")
        fig = plot_deformed_structure(structure, eigvec_1, scale_ev, u_ref=u_ref_ev)
        st.plotly_chart(fig, width='stretch', key="tab_eigenmode")

        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            gif_frames = st.slider("Frames pro Periode", 12, 60, 24, 4, key="mode_gif_frames")
        with col_b:
            gif_fps = st.slider("FPS", 4, 30, 12, 2, key="mode_gif_fps")

        if st.button("🎬 Schwingungsanimation generieren", key="btn_mode_gif"):
            _gif_ph = st.empty()

            def _on_gif_progress(p):
                _gif_ph.progress(p, text=f"Rendere Frame {int(p * gif_frames)}/{gif_frames} ...")

            gif_bytes = generate_mode_animation_gif(
                structure, eigvec_1, scale_ev, u_ref=u_ref_ev,
                n_frames=gif_frames, fps=gif_fps,
                on_progress=_on_gif_progress,
            )
            _gif_ph.empty()
            st.session_state.mode_gif_bytes = gif_bytes

        if st.session_state.get("mode_gif_bytes"):
            st.download_button(
                "⬇️ Schwingungsanimation herunterladen",
                data=st.session_state.mode_gif_bytes,
                file_name="eigenmode_animation.gif",
                mime="image/gif",
                key="dl_mode_gif",
            )

    c1, c2, c3 = st.columns(3)
    c1.metric("Aktive Knoten",  structure.active_node_count())
    c2.metric("Gesamt Knoten",  structure.total_node_count())
    c3.metric("Massenanteil",   f"{structure.current_mass_fraction():.1%}")

with tab2:
    if not hist.omega_1:
        st.info("Keine Eigenfrequenz-Daten vorhanden.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=hist.omega_1,
            mode="lines+markers",
            name="ω₁ [rad/s]",
            line=dict(color="#4A90D9", width=2),
            marker=dict(size=4),
        ))
        fig.add_hline(
            y=omega_e,
            line=dict(color="#FF8C00", width=1.5, dash="dash"),
            annotation_text=f"ω_E = {omega_e:.1f} rad/s",
            annotation_position="top right",
            annotation_font_color="#FF8C00",
        )
        fig.update_layout(
            paper_bgcolor="#1A1A2E", plot_bgcolor="#16213E",
            xaxis=dict(title="Iteration", color="white", gridcolor="#2A2A4A"),
            yaxis=dict(title="ω₁ [rad/s]", color="white", gridcolor="#2A2A4A"),
            legend=dict(font=dict(color="white"), bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig, width='stretch', key="tab2_eigenfreq")

        f_e = omega_e / (2.0 * math.pi)
        c1, c2 = st.columns(2)
        c1.metric("ω₁ final [rad/s]",  f"{hist.omega_1[-1]:.3f}")
        c2.metric("f₁ final [Hz]",      f"{hist.f_1[-1]:.4f}")

with tab3:
    if not hist.freq_distance:
        st.info("Keine Frequenzabstand-Daten vorhanden.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=hist.freq_distance,
            mode="lines+markers",
            name="|ω₁ − ω_E|",
            line=dict(color="#FF4444", width=2),
            marker=dict(size=4),
        ))
        fig.update_layout(
            paper_bgcolor="#1A1A2E", plot_bgcolor="#16213E",
            xaxis=dict(title="Iteration", color="white", gridcolor="#2A2A4A"),
            yaxis=dict(title="|ω₁ − ω_E| [rad/s]", color="white", gridcolor="#2A2A4A"),
            legend=dict(font=dict(color="white"), bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig, width='stretch', key="tab3_freqdist")
        st.metric("Frequenzabstand final", f"{hist.freq_distance[-1]:.3f} rad/s")

with tab4:
    if not hist.mass_fraction:
        st.info("Keine Massendaten vorhanden.")
    else:
        st.line_chart(hist.mass_fraction, x_label="Iteration", y_label="Massenanteil")
        st.metric("Massenanteil final", f"{hist.mass_fraction[-1]:.1%}")