import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import sys, os

# Imports aus deinem Core
from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure

# --- Hilfsfunktionen für die Struktur ---
def create_rectangular_grid(width, height, nx, ny, k):
    nodes, springs = [], []
    dx = width / (nx - 1) if nx > 1 else 0.0
    dy = height / (ny - 1) if ny > 1 else 0.0
    nid = 0
    for row in range(ny):
        for col in range(nx):
            nodes.append(Node(id=nid, x=col * dx, y=row * dy))
            nid += 1
    def idx(r, c): return r * nx + c
    for r in range(ny):
        for c in range(nx):
            i = idx(r, c)
            if c + 1 < nx: springs.append(Spring(node_i=i, node_j=idx(r, c + 1), k=k))
            if r + 1 < ny: springs.append(Spring(node_i=i, node_j=idx(r + 1, c), k=k))
            if r + 1 < ny and c + 1 < nx: springs.append(Spring(node_i=i, node_j=idx(r + 1, c + 1), k=k * 0.7071))
            if r + 1 < ny and c - 1 >= 0: springs.append(Spring(node_i=i, node_j=idx(r + 1, c - 1), k=k * 0.7071))
    return Structure(nodes=nodes, springs=springs)

def apply_simply_supported_beam(structure, nx, ny, load_fy):
    for n in structure.nodes:
        n.fix_x, n.fix_y, n.fx, n.fy = False, False, 0.0, 0.0
    structure.nodes[0].fix_y = True
    structure.nodes[nx - 1].fix_x = True
    structure.nodes[nx - 1].fix_y = True
    mid_col = nx // 2
    structure.nodes[(ny - 1) * nx + mid_col].fy = float(load_fy)

def plot_structure(structure):
    fig, ax = plt.subplots()
    lines = [[(structure.nodes[s.node_i].x, structure.nodes[s.node_i].y), 
              (structure.nodes[s.node_j].x, structure.nodes[s.node_j].y)] 
             for s in structure.springs if s.active]
    if lines: ax.add_collection(LineCollection(lines, linewidths=1))
    ax.set_aspect("equal")
    return fig

# --- UI ---
st.title("🏗️ Structure Creator")

with st.sidebar:
    st.header("Parameter")
    width = st.number_input("Width", value=10.0)
    height = st.number_input("Height", value=2.0)
    nx = st.number_input("nx", value=31)
    ny = st.number_input("ny", value=7)
    k = st.number_input("spring k", value=100.0)
    load_fy = st.number_input("Load Fy", value=-10.0)

    if st.button("Create Beam Grid"):
        s = create_rectangular_grid(width, height, int(nx), int(ny), float(k))
        apply_simply_supported_beam(s, int(nx), int(ny), float(load_fy))
        st.session_state.structure = s
        st.session_state.history = None
        st.success("Struktur erstellt!")

if st.session_state.structure:
    st.pyplot(plot_structure(st.session_state.structure))
else:
    st.info("Erstelle eine Struktur in der Sidebar.")