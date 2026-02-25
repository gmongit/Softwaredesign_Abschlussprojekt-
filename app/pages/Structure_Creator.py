import copy

import numpy as np
import streamlit as st
from PIL import Image

from core.db.case_store import case_store
from app.shared import png_save_dialog, structure_save_dialog, PNG_EXPORT_SETTINGS, show_structure_status
from app.service.optimization_service import validate_structure
from app.service.structure_service import (
    create_rectangular_grid,
    create_structure_from_image,
    image_to_binary_grid,
    set_festlager,
    set_loslager,
    set_last,
    toggle_node,
    apply_default_boundary_conditions,
)
from app.plots import plot_structure


# --- UI ---
st.title("🏗️ Structure Creator")

view = st.segmented_control(
    "Erstellungsmodus",
    options=["Manuell", "Laden", "Bild hochladen"],
    default="Manuell",
    label_visibility="collapsed",
)

st.divider()

# ── Tab 1: Manuell ──────────────────────────────────────────────────────────
if view == "Manuell":
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        width   = st.number_input("Breite",        min_value=1.0, value=10.0, step=1.0)
    with col2:
        height  = st.number_input("Höhe",          min_value=0.5, value=2.0,  step=0.5)
    with col3:
        nx      = st.number_input("Knoten X (nx)", min_value=2,   value=31,   step=2)
    with col4:
        ny      = st.number_input("Knoten Y (ny)", min_value=2,   value=7,    step=1)

    load_fy = st.number_input("Last Fy [N]", value=-10.0, key="manual_load_fy")

    if st.button("✅ Struktur erstellen", type="primary"):
        _nx, _ny = int(nx), int(ny)
        s = create_rectangular_grid(float(width), float(height), _nx, _ny)
        # Standard-BCs: Festlager links unten, Loslager rechts unten, Kraft Mitte oben
        apply_default_boundary_conditions(s, _nx, _ny, float(load_fy))

        st.session_state.structure = copy.deepcopy(s)
        st.session_state.original_structure = s
        st.session_state.nx = _nx
        st.session_state.ny = _ny
        st.session_state.history = None
        st.success(f"Struktur erstellt: {_nx * _ny} Knoten, {len(s.springs)} Federn")


# ── Tab 2: Laden ─────────────────────────────────────────────────────────────
elif view == "Laden":
    st.subheader("Case laden")
    cases = case_store.list_cases()
    if cases:
        case_names = [m.name for m in cases]
        selected = st.selectbox("Case", case_names, label_visibility="collapsed")

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("📂 Laden", type="primary", width='stretch'):
                try:
                    structure, history = case_store.load_case(selected)
                    st.session_state.structure = structure
                    st.session_state.original_structure = structure
                    st.session_state.history = history
                    st.session_state.nx = None
                    st.session_state.ny = None
                    st.success(f"'{selected}' geladen.")
                except KeyError as e:
                    st.error(str(e))
        with c2:
            if st.button("🗑️ Löschen", width='stretch'):
                case_store.delete_case(selected)
                st.rerun()
    else:
        st.info("Noch keine Cases gespeichert.")

# ── Tab 3: Bild hochladen ────────────────────────────────────────────────────
elif view == "Bild hochladen":
    uploaded = st.file_uploader("Bild wählen", type=["png", "jpg", "jpeg", "bmp", "webp"])
    if uploaded is not None:
        st.session_state.uploaded_image = uploaded

    img_data = st.session_state.get("uploaded_image")
    if img_data is not None:
        # Einstellungen
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            img_nx = st.number_input("Knoten X (nx)", min_value=2, value=31, step=2, key="img_nx")
        with col2:
            img_ny = st.number_input("Knoten Y (ny)", min_value=2, value=7, step=1, key="img_ny")
        with col3:
            brightness = st.slider("Helligkeitsschwelle", 0, 255, 128, key="img_brightness")
        with col4:
            coverage = st.slider("Abdeckung (%)", 0, 100, 50, key="img_coverage")

        col_w, col_h = st.columns(2)
        with col_w:
            img_width = st.number_input("Breite (m)", min_value=1.0, value=10.0, step=1.0, key="img_width")
        with col_h:
            img_height = st.number_input("Höhe (m)", min_value=0.5, value=2.0, step=0.5, key="img_height")

        img_data.seek(0)
        grid = image_to_binary_grid(img_data, int(img_nx), int(img_ny), brightness, coverage / 100.0)

        preview = np.where(grid[::-1], 0, 255).astype(np.uint8)
        preview_img = Image.fromarray(preview, mode="L").resize(
            (int(img_nx) * 8, int(img_ny) * 8), Image.Resampling.NEAREST
        )

        left, right = st.columns(2)
        with left:
            st.caption("Original")
            img_data.seek(0)
            st.image(img_data, width='stretch')
        with right:
            st.caption(f"Erkannt: {int(grid.sum())} / {int(img_nx) * int(img_ny)} Knoten aktiv")
            st.image(preview_img, width='stretch')

        # Struktur erstellen
        if st.button("✅ Struktur aus Bild erstellen", type="primary"):
            img_data.seek(0)
            s = create_structure_from_image(
                img_data,
                int(img_nx), int(img_ny),
                brightness, coverage / 100.0,
                float(img_width), float(img_height),
            )

            st.session_state.structure = copy.deepcopy(s)
            st.session_state.original_structure = s
            st.session_state.nx = int(img_nx)
            st.session_state.ny = int(img_ny)
            st.session_state.history = None
            active = sum(1 for n in s.nodes if n.active)
            active_springs = sum(1 for sp in s.springs if sp.active)
            st.success(f"Struktur erstellt: {active} aktive Knoten, {active_springs} Federn")

st.divider()

# ── Randbedingungen & Visualisierung ─────────────────────────────────────────
orig = st.session_state.get("original_structure")
if orig is not None:

    bc_mode = st.segmented_control(
        "Randbedingung",
        options=["Ansicht", "Festlager", "Loslager", "Last setzen", "Knoten an/aus"],
        default="Ansicht",
        key="bc_mode",
        label_visibility="collapsed",
    )

    bc_force = -10.0
    if bc_mode == "Last setzen":
        bc_force = st.number_input("Kraft Fy [N]", value=-10.0, key="bc_force")

    if bc_mode and bc_mode != "Ansicht":
        st.caption("Klicke auf einen Knoten im Plot.")

    show_inactive = bc_mode == "Knoten an/aus"
    fig = plot_structure(orig, show_inactive=show_inactive)
    event = st.plotly_chart(
        fig, on_select="rerun", selection_mode="points",
        key="structure_plot",
    )

    # Klick verarbeiten
    selection = event["selection"] if event else {}
    points = selection.get("points", []) if selection else []
    if bc_mode and bc_mode != "Ansicht" and points:
        for pt in points:
            curve = pt.get("curve_number")
            # Trace 0 = Linien (skip), Trace 1 = aktive Knoten, Trace 2 = inaktive Knoten
            if curve not in (1, 2):
                continue
            node_id = pt.get("customdata")
            if node_id is None:
                continue
            node_id = int(node_id)

            node = orig.nodes[node_id]
            
            # Änderung am Original vornehmen
            changed = False

            if bc_mode == "Knoten an/aus":
                changed = True
                toggle_node(orig, node_id) # Rückgabewert hier ignoriert, da wir eh resetten

            # Für BC-Modi nur aktive Knoten
            elif not node.active:
                pass # Nichts tun

            elif bc_mode == "Festlager":
                set_festlager(orig, node_id)
                changed = True
            elif bc_mode == "Loslager":
                set_loslager(orig, node_id)
                changed = True
            elif bc_mode == "Last setzen":
                set_last(orig, node_id, bc_force)
                changed = True

            # Wenn sich etwas geändert hat: Arbeitskopie resetten!
            if changed:
                st.session_state.structure = copy.deepcopy(orig)
                st.session_state.history = None
            st.rerun()

    # Struktur-Tools
    col_check, col_sym, col_remove = st.columns(3)
    with col_check:
        if st.button("🔍 Struktur prüfen", width='stretch'):
            show_structure_status(validate_structure(orig))
    with col_sym:
        if st.button("🔄 Symmetrie prüfen", width='stretch'):
            is_sym, _ = orig.detect_symmetry()
            if is_sym:
                st.success("Struktur ist symmetrisch.")
            else:
                st.warning("Struktur ist nicht symmetrisch.")
    with col_remove:
        if st.button("🧹 Bereinigen", width='stretch'):
            orig._register_special_nodes()
            removed_orig = orig.remove_removable_nodes()
            if removed_orig > 0:
                st.session_state.structure = copy.deepcopy(orig)
                st.session_state.history = None
                st.success(f"{removed_orig} entfernbare Knoten bereinigt.")
                st.rerun()
            else:
                st.info("Keine Inseln oder Sackgassen gefunden.")

    # Export-Buttons
    active_name = st.session_state.get("case_name_main") or "struktur"
    col_png, col_save = st.columns(2)
    with col_png:
        if st.button("📥 Als PNG speichern", width='stretch'):
            png_save_dialog(fig.to_image(**PNG_EXPORT_SETTINGS), active_name)
    with col_save:
        if st.button("💾 Struktur speichern", width='stretch'):
            structure_save_dialog(active_name)
else:
    st.info("Erstelle eine Struktur oder lade einen gespeicherten Case.")
