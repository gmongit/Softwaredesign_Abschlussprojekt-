import streamlit as st
from app.shared import (
    show_structure_status, show_stop_reason, show_export_buttons,
    gif_generation_dialog, material_sidebar,
    show_heatmap_view, show_loadpaths_view, show_deformation_view,
    make_progress_callback,
)
from app.service.optimization_service import (
    optimize_structure,
    run_optimization,
    continue_optimization,
    is_retryable,
    validate_structure,
    run_rebuild_support,
)
from app.plots import (
    plot_structure,
    plot_replay_structure,
    generate_replay_gif,
)


@st.dialog("Nachverstärkung", width="small")
def _rebuild_dialog():
    st.markdown("**Einstellungen**")
    top_pct = st.slider("Top-Federn (%)", 0.1, 10.0, 2.0, 0.1)
    min_stress = st.slider("Min. Last-Schwelle (%)", 60, 99, 75, 1)
    min_imp = st.slider("Min. Verbesserung (%)", 1, 20, 5, 1)

    if st.button("▶ Starten", type="primary", width="stretch"):
        progress = st.progress(0.0, text="Kandidaten werden gesucht...")
        status = st.empty()

        def _on_progress(tested, total, best_pct):
            progress.progress(
                tested / total,
                text=f"Kombination {tested} / {total} | Beste Reduktion: {best_pct:.1f}%",
            )

        result = run_rebuild_support(
            st.session_state.structure,
            min_improvement=min_imp / 100,
            top_percent=top_pct / 100,
            min_stress_pct=min_stress / 100,
            on_progress=_on_progress,
        )
        progress.empty()

        st.session_state.rebuild_result = result
        status.caption(
            f"{result.n_candidates} Kandidaten in {result.n_clusters} Cluster(n) — "
            f"{result.n_combos_tested} / {result.n_combos_total} Kombinationen getestet"
        )
        if result.reactivated_node_ids:
            st.success(result.message)
            st.rerun()
        else:
            st.warning(result.message)


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
            st.session_state.rebuild_result = None
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

    # --- Nachverstärkung ---
    if st.session_state.history is not None:
        st.markdown("---")
        if st.button("🔧 Nachverstärkung (Beta)"):
            _rebuild_dialog()

# --- Status ---
if st.session_state.history is not None and st.session_state.history.stop_reason:
    show_stop_reason(
        st.session_state.history.stop_reason,
        st.session_state.structure.current_mass_fraction(),
    )

# --- Visualisierung ---
if st.session_state.history is not None:
    rb = st.session_state.get("rebuild_result")
    has_rebuild = rb is not None

    # Meldung vom Rebuild anzeigen (auch ohne reaktivierte Knoten)
    if rb is not None and rb.message and not rb.reactivated_node_ids:
        st.warning(rb.message)

    st.markdown("**Ansicht**")
    options = ["Struktur", "Heatmap", "Lastpfade", "Verformung", "Replay"]
    if has_rebuild:
        options.append("Nachverstärkung")
    view = st.segmented_control(
        "Ansicht", options=options,
        default="Nachverstärkung" if has_rebuild else "Heatmap",
        label_visibility="collapsed",
    )

    fig = None

    if view == "Struktur":
        fig = plot_structure(st.session_state.structure)
        st.plotly_chart(fig, width='stretch')

    elif view == "Heatmap":
        fig = show_heatmap_view(st.session_state.structure)

    elif view == "Lastpfade":
        fig = show_loadpaths_view(st.session_state.structure)

    elif view == "Verformung":
        fig = show_deformation_view(st.session_state.structure)

    elif view == "Replay":
        hist = st.session_state.history
        n_steps = len(hist.removed_nodes_per_iter)

        if n_steps == 0:
            st.info("Keine Iterationsdaten vorhanden.")
        else:
            step = st.slider("Schritt", 0, n_steps, 0, key="replay_slider")

            mass_at_step = (
                hist.mass_fraction[step]
                if step < len(hist.mass_fraction)
                else hist.mass_fraction[-1]
            )
            removed_count = sum(
                len(hist.removed_nodes_per_iter[s]) for s in range(step)
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Schritt", f"{step} / {n_steps}")
            c2.metric("Massenanteil", f"{mass_at_step:.1%}")
            c3.metric("Entfernte Knoten", removed_count)

            removed_so_far: set = set()
            for s in range(max(0, step - 1)):
                removed_so_far.update(hist.removed_nodes_per_iter[s])
            just_removed: set = (
                set(hist.removed_nodes_per_iter[step - 1]) if step > 0 else set()
            )

            fig = plot_replay_structure(
                st.session_state.structure, removed_so_far, just_removed,
            )
            st.plotly_chart(fig, width='stretch')

            st.divider()
            if st.button("🎬 GIF generieren"):
                gif_generation_dialog(
                    st.session_state.structure, hist, generate_replay_gif,
                )

    elif view == "Nachverstärkung" and rb is not None:
        fig = plot_structure(
            st.session_state.structure,
            highlight_nodes=rb.reactivated_node_ids,
        )
        st.plotly_chart(fig, width='stretch')

        c1, c2, c3 = st.columns(3)
        c1.metric("Reaktivierte Knoten", len(rb.reactivated_node_ids))
        c2.metric("Stress vorher", f"{rb.stress_before / 1e6:.1f} MPa")
        c3.metric("Stress nachher", f"{rb.stress_after / 1e6:.1f} MPa")

        if rb.message:
            st.info(rb.message)

    if fig is not None and view not in ("Replay", "Nachverstärkung"):
        st.divider()
        base = st.session_state.get("case_name") or "struktur"
        show_export_buttons(fig, base)

    # --- Metriken ---
    structure = st.session_state.structure
    is_sym, _ = structure.detect_symmetry()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Aktive Knoten", structure.active_node_count())
    c2.metric("Gesamt Knoten", structure.total_node_count())
    c3.metric("Massenanteil", f"{structure.current_mass_fraction():.1%}")
    c4.metric("Symmetrie", "Symmetrisch" if is_sym else "Asymmetrisch")

    # --- Optimierungsverlauf ---
    hist = st.session_state.history
    if hist is not None and len(hist.mass_fraction) > 0:
        st.markdown("**Optimierungsverlauf**")
        st.line_chart(
            hist.mass_fraction, x_label="Iteration", y_label="Massenanteil",
        )

else:
    st.info("Starte die Optimierung über die Sidebar.")