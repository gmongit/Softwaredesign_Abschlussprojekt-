import streamlit as st
from app.shared import (
    show_structure_status, show_stop_reason, show_export_buttons,
    gif_generation_dialog, material_sidebar,
    show_heatmap_view, show_deformation_view,
    make_progress_callback,
)
from app.service.optimization_service import (
    optimize_structure,
    run_optimization,
    continue_optimization,
    is_retryable,
    validate_structure,
)
from app.plots import (
    plot_structure,
    plot_replay_structure,
    generate_replay_gif,
)


# --- UI ---
st.title("⚡ Optimizer")

if st.session_state.structure is None:
    st.warning("Bitte zuerst im 'Structure Creator' ein Modell erstellen.")
    st.stop()

_progress_ph = st.empty()
_live_ph     = st.empty()

with st.sidebar:
    st.header("Einstellungen")

    selected_material, mat, beam_area_mm2, max_stress_pa = material_sidebar()

    st.markdown("<br>", unsafe_allow_html=True)
    target_mass     = st.slider("Ziel-Massenanteil", 0.1, 1.0, 0.4, 0.01)
    remove_fraction = st.slider("Entfernungsrate / Iteration", 0.01, 0.2, 0.05, 0.01)
    max_iters       = st.number_input("Max. Iterationen", 10, 500, 120, 10)

    validation = validate_structure(st.session_state.structure)
    show_structure_status(validation)

    if st.button("▶ Optimierung starten", type="primary", disabled=not validation.ok):
        _target = float(target_mass)
        try:
            hist = optimize_structure(
                st.session_state.structure,
                material_name=selected_material if mat else None,
                beam_area_mm2=beam_area_mm2,
                remove_fraction=float(remove_fraction),
                target_mass_fraction=_target,
                max_iters=int(max_iters),
                max_stress=max_stress_pa,
                on_iter=make_progress_callback(_progress_ph, _live_ph, _target, "_live"),
            )
            _progress_ph.empty()
            _live_ph.empty()
            st.session_state.history = hist
            st.session_state.gif_bytes = None
        except ValueError as e:
            st.error(str(e))

    if st.session_state.history is not None and is_retryable(st.session_state.history):
        if st.button("🔄 Weiter optimieren"):
            _target_r = float(target_mass)
            try:
                continue_optimization(
                    st.session_state.structure,
                    st.session_state.history,
                    remove_fraction=float(remove_fraction),
                    target_mass_fraction=_target_r,
                    max_iters=int(max_iters),
                    max_stress=max_stress_pa,
                    on_iter=make_progress_callback(_progress_ph, _live_ph, _target_r, "_retry"),
                )
                _progress_ph.empty()
                _live_ph.empty()
                st.session_state.gif_bytes = None
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    if (st.session_state.history is not None
            and st.session_state.structure is not None
            and st.session_state.structure.current_mass_fraction() > float(target_mass) + 0.01):
        if st.button("⚠️ Trotzdem bis zur Zielmasse entfernen - Nur für Testzwecke!", type="secondary"):
            _target_f = float(target_mass)
            try:
                hist = run_optimization(
                    st.session_state.structure,
                    remove_fraction=float(remove_fraction),
                    target_mass_fraction=_target_f,
                    max_iters=int(max_iters),
                    on_iter=make_progress_callback(_progress_ph, _live_ph, _target_f, "_force"),
                    force=True,
                )
                _progress_ph.empty()
                _live_ph.empty()
                st.session_state.history = hist
                st.session_state.gif_bytes = None
                st.rerun()
            except ValueError as e:
                st.error(str(e))

# --- Status ---
if st.session_state.history is not None and st.session_state.history.stop_reason:
    show_stop_reason(
        st.session_state.history.stop_reason,
        st.session_state.structure.current_mass_fraction(),
    )

# --- Visualisierung ---
if st.session_state.history is not None:
    st.markdown("**Ansicht**")
    view = st.segmented_control(
        "Ansicht",
        options=["Struktur", "Heatmap", "Lastpfade", "Verformung", "Replay"],
        default="Heatmap",
        label_visibility="collapsed",
    )

    fig = None

    if view == "Struktur":
        fig = plot_structure(st.session_state.structure)
        st.plotly_chart(fig, width='stretch')

    elif view == "Heatmap":
        fig = show_heatmap_view(st.session_state.structure)

    elif view == "Lastpfade":
        u = compute_displacement(st.session_state.structure)
        energies = compute_forces(st.session_state.structure)

        if u is None or energies is None:
            st.warning("Lastpfade nicht berechenbar – optimierte Struktur ist singulär.")
        else:
            arrow_scale = st.slider("Pfeil-Skalierung", 0.1, 1.0, 1.0, 0.1)

            n_springs = len(st.session_state.structure.springs)

            show_top = st.slider(
                "Top-Stäbe anzeigen",
                min_value=1,
                max_value=n_springs,
                value=min(80, n_springs),
                step=1
            )

            fig = plot_load_paths_with_arrows(
                st.session_state.structure,
                u=u,
                energies=energies,
                arrow_scale=arrow_scale,
                top_n=show_top,
            )
            st.plotly_chart(fig, width="stretch")

    elif view == "Verformung":
        fig = show_deformation_view(st.session_state.structure)

    elif view == "Replay":
        hist = st.session_state.history
        n_steps = len(hist.removed_nodes_per_iter)

        if n_steps == 0:
            st.info("Keine Iterationsdaten vorhanden. Bitte Optimierung erneut starten.")
        else:
            step = st.slider("Schritt", 0, n_steps, 0, key="replay_slider")

            mass_at_step = hist.mass_fraction[step] if step < len(hist.mass_fraction) else hist.mass_fraction[-1]
            removed_count = sum(len(hist.removed_nodes_per_iter[s]) for s in range(step))
            c1, c2, c3 = st.columns(3)
            c1.metric("Schritt", f"{step} / {n_steps}")
            c2.metric("Massenanteil", f"{mass_at_step:.1%}")
            c3.metric("Entfernte Knoten", removed_count)

            removed_so_far: set = set()
            for s in range(max(0, step - 1)):
                removed_so_far.update(hist.removed_nodes_per_iter[s])
            just_removed: set = set(hist.removed_nodes_per_iter[step - 1]) if step > 0 else set()

            fig = plot_replay_structure(st.session_state.structure, removed_so_far, just_removed)
            st.plotly_chart(fig, width='stretch')

            st.divider()
            if st.button("🎬 GIF generieren"):
                gif_generation_dialog(
                    st.session_state.structure,
                    hist,
                    generate_replay_gif
                )

    if fig is not None and view != "Replay":
        st.divider()
        base = st.session_state.get("case_name") or "struktur"
        show_export_buttons(fig, base)

    # --- Metriken ---
    # --- Metriken ---
    structure = st.session_state.structure
    is_sym, _ = structure.detect_symmetry()

    current_mass = structure.total_mass()
    initial_mass = float(getattr(structure, "_initial_mass", 0.0))
    removed_mass = max(0.0, initial_mass - current_mass)


    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)
    c1.metric("Aktive Knoten", structure.active_node_count())
    c2.metric("Gesamt Knoten", structure.total_node_count())
    c3.metric("Massenanteil", f"{structure.current_mass_fraction():.1%}")
    c4.metric("Masse", f"{current_mass:.3f} kg")
    c5.metric("Entfernte Masse", f"{removed_mass:.3f} kg")
    c6.metric("Symmetrie", "Symmetrisch" if is_sym else "Asymmetrisch")

    # --- Optimierungsverlauf ---
    hist = st.session_state.history
    if hist is not None and len(hist.mass_fraction) > 0:
        st.markdown("**Optimierungsverlauf**")
        st.line_chart(hist.mass_fraction, x_label="Iteration", y_label="Massenanteil")

else:
    st.info("Starte die Optimierung über die Sidebar.")