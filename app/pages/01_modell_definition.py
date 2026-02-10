import streamlit as st
from core.model.structure import Structure
from visualization.plot_structure import plot_structure

st.title("Modell definition")

nx = st.sidebar.slider("nx", 5, 60, 20)
ny = st.sidebar.slider("ny", 3, 30, 8)
diagonals = st.sidebar.checkbox("Diagonals", True)

struct = Structure.mbb_beam(nx=nx, ny=ny, diagonals=diagonals)

st.write(f"Nodes: {len(struct.nodes)}")
st.write(f"Springs: {len(struct.springs)}")

fig = plot_structure(struct, show_nodes=False)
st.pyplot(fig)
