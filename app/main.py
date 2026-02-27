# app/main.py
import streamlit as st
import os
import sys

if "structure" not in st.session_state:
    st.session_state.structure = None
if "history" not in st.session_state:
    st.session_state.history = None
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "intro"

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root not in sys.path:
    sys.path.insert(0, root)

# Landing Page
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "intro"

st.set_page_config(
    page_title="Topology UI", 
    layout="wide",
    initial_sidebar_state="collapsed" if st.session_state.app_mode == "intro" else "expanded"
)

# Seiten definieren
mat_page = st.Page("pages/Material_Manager.py", title="Material Manager", icon="🧪")
struct_page = st.Page("pages/Structure_Creator.py", title="Structure Creator", icon="🏗️")
opt_page = st.Page("pages/Optimizer.py", title="Optimizer", icon="⚡")
dyn_opt_page = st.Page("pages/Dynamic_Optimizer.py", title="Dynamic Optimizer", icon="🌊")
simp_page = st.Page("pages/SIMP_Optimizer.py", title="SIMP Optimizer", icon="📐")

if st.session_state.app_mode == "intro":
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"], [data-testid="stSidebarNav"] {
                display: none;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🔧 Topology Optimization UI")
    st.markdown("### Willkommen!")
    st.write("Dies ist die Startseite. Hier gibt es keine störende Taskleiste links.")
    
    if st.button("Jetzt starten 🚀", type="primary"):
        st.session_state.app_mode = "main_app"
        st.rerun()
else:
    pg = st.navigation({
        "Konfiguration": [mat_page, struct_page],
        "Berechnung": [opt_page, dyn_opt_page, simp_page]
    })
    pg.run()