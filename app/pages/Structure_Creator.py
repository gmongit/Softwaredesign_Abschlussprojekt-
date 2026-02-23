import copy

import numpy as np
import streamlit as st
from PIL import Image

from core.db.case_store import case_store
from app.service.structure_service import (
    create_rectangular_grid,
    create_structure_from_image,
    image_to_binary_grid,
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
        # Standard: Festlager links unten, Loslager rechts unten, Kraft Mitte oben
        s.nodes[0].fix_x = True                          
        s.nodes[0].fix_y = True
        s.nodes[_nx - 1].fix_y = True                    
        mid_col = _nx // 2
        s.nodes[(_ny - 1) * _nx + mid_col].fy = float(load_fy)  

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
            struct = st.session_state.get("structure")
            node2 = struct.nodes[node_id] if struct else None

            if bc_mode == "Knoten an/aus":
                new_active = not node.active
                node.active = new_active
                if node2:
                    node2.active = new_active
                # Federn an/aus die diesen Knoten betreffen
                for s in orig.springs:
                    if s.node_i == node_id or s.node_j == node_id:
                        ni_active = orig.nodes[s.node_i].active
                        nj_active = orig.nodes[s.node_j].active
                        s.active = ni_active and nj_active
                if struct:
                    for s in struct.springs:
                        if s.node_i == node_id or s.node_j == node_id:
                            ni_active = struct.nodes[s.node_i].active
                            nj_active = struct.nodes[s.node_j].active
                            s.active = ni_active and nj_active
                st.rerun()

            # Für BC-Modi nur aktive Knoten
            if not node.active:
                continue

            if bc_mode == "Festlager":
                toggle = node.fix_x and node.fix_y
                node.fix_x = not toggle
                node.fix_y = not toggle
                node.fx = 0.0
                node.fy = 0.0
                if node2:
                    node2.fix_x = node.fix_x
                    node2.fix_y = node.fix_y
                    node2.fx = 0.0
                    node2.fy = 0.0

            elif bc_mode == "Loslager":
                toggle = node.fix_y and not node.fix_x
                node.fix_y = not toggle
                node.fix_x = False
                node.fx = 0.0
                node.fy = 0.0
                if node2:
                    node2.fix_y = node.fix_y
                    node2.fix_x = False
                    node2.fx = 0.0
                    node2.fy = 0.0

            elif bc_mode == "Last setzen":
                if abs(node.fy) > 0:
                    node.fy = 0.0
                else:
                    node.fy = float(bc_force)
                node.fix_x = False
                node.fix_y = False
                if node2:
                    node2.fy = node.fy
                    node2.fix_x = False
                    node2.fix_y = False

            st.rerun()

    # Validierung
    supports = [n for n in orig.nodes if n.active and (n.fix_x or n.fix_y)]
    loads = [n for n in orig.nodes if n.active and (abs(n.fx) > 0 or abs(n.fy) > 0)]
    has_fix_x = any(n.fix_x for n in supports)
    has_fix_y = any(n.fix_y for n in supports)

    if supports and loads and has_fix_x and has_fix_y:
        st.caption(f"✅ {len(supports)} Lager, {len(loads)} Lastknoten — bereit")
    else:
        missing = []
        if not has_fix_y:
            missing.append("Lager (fix_y)")
        if not has_fix_x:
            missing.append("Lager (fix_x)")
        if not loads:
            missing.append("Lastknoten")
        st.caption(f"⚠️ Fehlend: {', '.join(missing)}")

    # PNG Export
    active_name = st.session_state.get("case_name_main") or "struktur"
    st.download_button(
        label="📥 Als PNG speichern",
        data=fig.to_image(format="png", width=1600, height=600, scale=2),
        file_name=f"{active_name}.png",
        mime="image/png",
    )

    # Struktur speichern — für alle 3 Modi verfügbar
    st.subheader("Struktur speichern")
    case_name = st.text_input("Name", value=active_name or "Balken", placeholder="Eindeutiger Name", key="case_name_save")
    if st.button("💾 Speichern", type="primary", width='stretch'):
        if not st.session_state.get("structure"):
            st.error("Keine Struktur vorhanden.")
        else:
            try:
                case_store.save_case(case_name, st.session_state.structure, st.session_state.history)
                st.success(f"'{case_name}' gespeichert.")
            except ValueError as e:
                st.error(str(e))
else:
    st.info("Erstelle eine Struktur oder lade einen gespeicherten Case.")