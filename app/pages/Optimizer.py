import numpy as np
import streamlit as st
from core.db.material_store import material_store
from app.shared import (
    png_save_dialog, structure_save_dialog, gif_save_dialog,
    gif_generation_dialog, PNG_EXPORT_SETTINGS, show_structure_status,
)
from app.plots import plot_load_paths_with_arrows
from app.service.optimization_service import (
    optimize_structure,
    run_optimization,
    compute_displacement,
    compute_forces,
    validate_structure,
)
from app.plots import (
    plot_structure,
    plot_heatmap,
    plot_deformed_structure,
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
    target_mass     = st.slider("Ziel-Massenanteil", 0.1, 1.0, 0.4, 0.01)
    remove_fraction = st.slider("Entfernungsrate / Iteration", 0.01, 0.2, 0.05, 0.01)
    max_iters       = st.number_input("Max. Iterationen", 10, 500, 120, 10)

    validation = validate_structure(st.session_state.structure)
    show_structure_status(validation)

    if st.button("▶ Optimierung starten", type="primary", disabled=not validation.ok):
        _target = float(target_mass)

        def _on_iter(struct, i, n_rem):
            frac = struct.current_mass_fraction()
            prog = max(0.0, min(1.0, (1.0 - frac) / max(1.0 - _target, 1e-9)))
            _progress_ph.progress(
                prog,
                text=f"Iteration {i} | Masse: {frac:.1%} | -{n_rem} Knoten",
            )
            with _live_ph.container():
                st.plotly_chart(plot_structure(struct), use_container_width=True, key=f"_live_{i}")

        try:
            hist = optimize_structure(
                st.session_state.structure,
                material_name=selected_material if mat else None,
                beam_area_mm2=beam_area_mm2,
                remove_fraction=float(remove_fraction),
                target_mass_fraction=_target,
                max_iters=int(max_iters),
                on_iter=_on_iter,
            )
            _progress_ph.empty()
            _live_ph.empty()
            st.session_state.history = hist
            st.session_state.gif_bytes = None
            mf = st.session_state.structure.current_mass_fraction()
            st.success(f"Fertig! Masse: {mf:.1%}")
        except ValueError as e:
            st.error(str(e))

    # Warnung + Force-Button wenn Optimierung zu früh gestoppt wurde
    if (st.session_state.history is not None
            and st.session_state.structure is not None
            and st.session_state.structure.current_mass_fraction() > float(target_mass) + 0.01):
        mf_now = st.session_state.structure.current_mass_fraction()
        st.warning(
            f"Gestoppt bei **{mf_now:.1%}** – weitere Entfernung würde die Struktur singulär machen."
        )
        if st.button("⚠️ Trotzdem bis zur Zielmasse entfernen", type="secondary"):
            _target_f = float(target_mass)

            def _on_iter_force(struct, i, n_rem):
                frac = struct.current_mass_fraction()
                prog = max(0.0, min(1.0, (1.0 - frac) / max(1.0 - _target_f, 1e-9)))
                _progress_ph.progress(prog, text=f"Iteration {i} | Masse: {frac:.1%} | -{n_rem} Knoten")
                with _live_ph.container():
                    st.plotly_chart(plot_structure(struct), use_container_width=True, key=f"_force_{i}")

            try:
                hist = run_optimization(
                    st.session_state.structure,
                    remove_fraction=float(remove_fraction),
                    target_mass_fraction=_target_f,
                    max_iters=int(max_iters),
                    on_iter=_on_iter_force,
                    force=True,
                )
                _progress_ph.empty()
                _live_ph.empty()
                st.session_state.history = hist
                st.session_state.gif_bytes = None
                mf = st.session_state.structure.current_mass_fraction()
                st.success(f"Fertig (erzwungen)! Masse: {mf:.1%}")
            except ValueError as e:
                st.error(str(e))

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
        energies = compute_forces(st.session_state.structure)
        if energies is None:
            st.warning("Kraftverteilung nicht berechenbar – Struktur wird ohne Heatmap angezeigt.")
        fig = plot_heatmap(st.session_state.structure, energies=energies)
        st.plotly_chart(fig, width='stretch')


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
        u = compute_displacement(st.session_state.structure)
        if u is None:
            st.warning("Verschiebung nicht berechenbar (singuläre Matrix).")
            st.stop()

        # Robuste Referenz: 95. Perzentil der nicht-null Verschiebungen
        u_abs = np.abs(u)
        u_nonzero = u_abs[u_abs > 0]
        u_ref = float(np.percentile(u_nonzero, 95)) if len(u_nonzero) > 0 else 1.0

        # Automatischer Vorschlag für den Scale
        nodes_active = [n for n in st.session_state.structure.nodes if n.active]
        x_vals = [n.x for n in nodes_active]
        y_vals = [n.y for n in nodes_active]
        struct_width  = max(x_vals) - min(x_vals) if x_vals else 1.0
        struct_height = max(y_vals) - min(y_vals) if y_vals else 1.0
        auto_scale = 0.15 * max(struct_width, struct_height) / u_ref if u_ref > 0 else 1.0

        scale = st.slider(
            "Skalierungsfaktor Verformung",
            min_value=0.1,
            max_value=float(max(10.0, auto_scale * 3)),
            value=float(round(auto_scale, 2)),
            step=0.1,
            help=f"Automatischer Vorschlag: {auto_scale:.2f} | u_ref (95. Perz.): {u_ref:.2e}",
        )

        fig = plot_deformed_structure(st.session_state.structure, u, scale, u_ref=u_ref)
        st.plotly_chart(fig, width='stretch')

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
        col_png, col_save = st.columns(2)
        with col_png:
            if st.button("📥 Als PNG speichern", width='stretch'):
                png_save_dialog(fig.to_image(**PNG_EXPORT_SETTINGS), base)
        with col_save:
            if st.button("💾 Struktur speichern", width='stretch'):
                structure_save_dialog(base)

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
        st.line_chart(hist.mass_fraction, x_label="Iteration", y_label="Massenanteil")

else:
    st.info("Starte die Optimierung über die Sidebar.")