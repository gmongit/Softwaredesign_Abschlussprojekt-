"""Gemeinsame UI-Funktionen für Creator und Optimizer."""

import numpy as np
import streamlit as st

from core.db.case_store import case_store
from core.db.material_store import material_store
from app.service.optimization_service import StructureValidation
from app.plots import (
    plot_structure, plot_heatmap, plot_deformed_structure, plot_load_paths_with_arrows,
)


def show_structure_status(v: StructureValidation) -> None:
    if v.errors:
        st.error("**Fehler:** " + " | ".join(v.errors))
    elif v.warnings:
        st.warning("✅ Bereit | " + " | ".join(v.warnings))
    else:
        st.success("✅ Bereit")


PNG_EXPORT_SETTINGS = dict(format="png", width=1600, height=600, scale=2)


@st.dialog("Bild speichern")
def png_save_dialog(png_bytes: bytes, default_name: str = "struktur"):
    name = st.text_input("Dateiname", value=default_name)
    st.download_button(
        label="📥 Herunterladen",
        data=png_bytes,
        file_name=f"{name}.png",
        mime="image/png",
        width='stretch',
    )


@st.dialog("Struktur speichern")
def structure_save_dialog(default_name: str = "Balken"):
    name = st.text_input("Name", value=default_name)
    if st.button("💾 Speichern", type="primary", width='stretch'):
        structure = st.session_state.get("structure")
        if not structure:
            st.error("Keine Struktur vorhanden.")
        else:
            try:
                case_store.save_case(name, structure, st.session_state.history)
                st.success(f"'{name}' gespeichert.")
            except ValueError as e:
                st.error(str(e))


@st.dialog("GIF speichern")
def gif_save_dialog(gif_bytes: bytes, default_name: str = "optimierung"):
    name = st.text_input("Dateiname", value=default_name)
    st.download_button(
        label="📥 Herunterladen",
        data=gif_bytes,
        file_name=f"{name}.gif",
        mime="image/gif",
        width='stretch',
    )


@st.dialog("GIF generieren", width="small")
def gif_generation_dialog(structure, hist, generate_gif_fn):
    st.markdown("**GIF-Einstellungen**")
    fps = st.select_slider("FPS", options=[2, 5, 10, 15], value=5)

    st.markdown("**Dateiname**")
    default_name = st.session_state.get("case_name") or "optimierung"
    filename = st.text_input("Filename (ohne .gif)", value=default_name, key="gif_filename_input")

    if st.button("▶ Rendern", width='stretch', type="primary"):
        progress = st.progress(0.0, text="Frames werden gerendert...")
        gif_bytes = generate_gif_fn(
            structure, hist, fps=fps,
            on_progress=lambda p: progress.progress(
                p, text=f"Frames werden gerendert... {p:.0%}"
            ),
        )
        progress.empty()

        st.success("✅ GIF fertig!")
        st.divider()

        st.download_button(
            label="📥 Herunterladen",
            data=gif_bytes,
            file_name=f"{filename}.gif",
            mime="image/gif",
            width='stretch',
        )


# ---------------------------------------------------------------------------
# Wiederverwendbare Sidebar- und View-Bausteine
# ---------------------------------------------------------------------------

def material_sidebar():
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

    max_stress_pa: float | None = None
    use_stress_limit = st.checkbox("Streckgrenze-Limit", value=False)
    if use_stress_limit and mat:
        factor_of_safety = st.slider("Sicherheitsfaktor", 1.0, 10.0, 1.4, 0.1)
        max_stress_pa = mat.streckgrenze * 1e6 / factor_of_safety
        st.caption(f"Streckgrenze: {mat.streckgrenze} MPa | Zul. Spannung: {max_stress_pa/1e6:.1f} MPa")

    return selected_material, mat, beam_area_mm2, max_stress_pa


def show_heatmap_view(structure, key=None):
    energies = structure.compute_forces()
    if energies is None:
        st.warning("Kraftverteilung nicht berechenbar – Struktur wird ohne Heatmap angezeigt.")
    fig = plot_heatmap(structure, energies=energies)
    st.plotly_chart(fig, width='stretch', key=key)
    return fig


def show_loadpaths_view(structure, key=None):
    u = structure.compute_displacement()
    energies = structure.compute_forces()
    if u is None or energies is None:
        st.warning("Lastpfade nicht berechenbar – optimierte Struktur ist singulär.")
        return None
    arrow_scale = st.slider("Pfeil-Skalierung", 0.1, 1.0, 1.0, 0.1)
    show_top = st.slider("Top-Stäbe anzeigen", 10, 500, 80, 10)
    fig = plot_load_paths_with_arrows(
        structure, u=u, energies=energies,
        arrow_scale=arrow_scale, top_n=show_top,
    )
    st.plotly_chart(fig, width='stretch', key=key)
    return fig


def show_deformation_view(structure, key=None):
    u = structure.compute_displacement()
    if u is None:
        st.warning("Verschiebung nicht berechenbar (singuläre Matrix).")
        st.stop()

    u_abs = np.abs(u)
    u_nonzero = u_abs[u_abs > 0]
    u_ref = float(np.percentile(u_nonzero, 95)) if len(u_nonzero) > 0 else 1.0

    nodes_active = [n for n in structure.nodes if n.active]
    x_vals = [n.x for n in nodes_active]
    y_vals = [n.y for n in nodes_active]
    struct_size = max(
        max(x_vals) - min(x_vals) if x_vals else 1.0,
        max(y_vals) - min(y_vals) if y_vals else 1.0,
    )
    auto_scale = 0.15 * struct_size / u_ref if u_ref > 0 else 1.0

    scale = st.slider(
        "Skalierungsfaktor Verformung",
        min_value=0.1,
        max_value=float(max(10.0, auto_scale * 3)),
        value=float(round(auto_scale, 2)),
        step=0.1,
        help=f"Automatischer Vorschlag: {auto_scale:.2f} | u_ref (95. Perz.): {u_ref:.2e}",
    )

    fig = plot_deformed_structure(structure, u, scale, u_ref=u_ref)
    st.plotly_chart(fig, width='stretch', key=key)
    return fig


def show_export_buttons(fig, default_name):
    col_png, col_save = st.columns(2)
    with col_png:
        if st.button("📥 Als PNG speichern", width='stretch'):
            png_save_dialog(fig.to_image(**PNG_EXPORT_SETTINGS), default_name)
    with col_save:
        if st.button("💾 Struktur speichern", width='stretch'):
            structure_save_dialog(default_name)


def show_stop_reason(reason: str, mass_fraction: float) -> None:
    if reason == "Ziel-Massenanteil erreicht":
        st.success(f"Masse: {mass_fraction:.1%} — {reason}")
    elif "Streckgrenze" in reason or "instabil" in reason or "fehlgeschlagen" in reason:
        st.warning(f"Masse: {mass_fraction:.1%} — {reason}")
    elif reason:
        st.info(f"Masse: {mass_fraction:.1%} — {reason}")


def make_progress_callback(progress_ph, live_ph, target, key_prefix):
    def _on_iter(struct, i, n_rem):
        frac = struct.current_mass_fraction()
        prog = max(0.0, min(1.0, (1.0 - frac) / max(1.0 - target, 1e-9)))
        progress_ph.progress(prog, text=f"Iteration {i} | Masse: {frac:.1%} | -{n_rem} Knoten")
        with live_ph.container():
            st.plotly_chart(plot_structure(struct), width='stretch', key=f"{key_prefix}_{i}")
    return _on_iter


def make_dynamic_progress_callback(progress_ph, live_ph, target, key_prefix):
    def _on_iter(struct, i, om1, n_rem):
        frac = struct.current_mass_fraction()
        prog = max(0.0, min(1.0, (1.0 - frac) / max(1.0 - target, 1e-9)))
        progress_ph.progress(
            prog,
            text=f"Iteration {i} | Masse: {frac:.1%} | \u03c9\u2081 = {om1:.0f} rad/s | -{n_rem} Knoten",
        )
        with live_ph.container():
            st.plotly_chart(plot_structure(struct), width='stretch', key=f"{key_prefix}_{i}")
    return _on_iter