import copy

import streamlit as st

from core.db.case_store import case_store
from app.service.structure_service import create_rectangular_grid, apply_simply_supported_beam
from app.plots import plot_structure


# --- UI ---
st.title("🏗️ Structure Creator")

with st.sidebar:
    # --- Struktur erstellen ---
    st.header("Parameter")
    width   = st.number_input("Breite",        min_value=1.0, value=10.0, step=1.0)
    height  = st.number_input("Höhe",          min_value=0.5, value=2.0,  step=0.5)
    nx      = st.number_input("Knoten X (nx)", min_value=2,   value=31,   step=2)
    ny      = st.number_input("Knoten Y (ny)", min_value=2,   value=7,    step=1)
    load_fy = st.number_input("Last Fy [N]",                  value=-10.0)

    if st.button("✅ Struktur erstellen", type="primary"):
        s = create_rectangular_grid(float(width), float(height), int(nx), int(ny))
        apply_simply_supported_beam(s, int(nx), int(ny), float(load_fy))

        st.session_state.structure = copy.deepcopy(s)
        st.session_state.original_structure = s
        st.session_state.nx = int(nx)
        st.session_state.ny = int(ny)
        st.session_state.history = None
        st.success(f"Struktur erstellt: {int(nx) * int(ny)} Knoten, {len(s.springs)} Federn")

    case_name = st.text_input("Name", value="Balken", placeholder="Eindeutiger Name", key="case_name")
    if st.button("💾 Speichern"):
        if st.session_state.structure is None:
            st.error("Keine Struktur vorhanden.")
        else:
            try:
                case_store.save_case(case_name, st.session_state.structure, st.session_state.history)
                st.success(f"'{case_name}' gespeichert.")
            except ValueError as e:
                st.error(str(e))

    st.divider()

    # --- Case laden ---
    st.header("Case laden")

    cases = case_store.list_cases()
    if cases:
        case_names = [m.name for m in cases]
        selected = st.selectbox("Case", case_names, label_visibility="collapsed")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("📂 Laden", use_container_width=True):
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
            if st.button("🗑️ Löschen", use_container_width=True):
                case_store.delete_case(selected)
                st.rerun()
    else:
        st.caption("Noch keine Cases gespeichert.")

if st.session_state.get("original_structure"):
    fig = plot_structure(st.session_state.original_structure)
    st.plotly_chart(fig, width='stretch')
    filename = f"{case_name}.png" if case_name else "struktur.png"
    st.download_button(
        label="📥 Als PNG speichern",
        data=fig.to_image(format="png", width=1600, height=600, scale=2),
        file_name=filename,
        mime="image/png",
    )
else:
    st.info("Erstelle eine Struktur über die Sidebar.")
