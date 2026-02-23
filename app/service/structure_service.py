from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image

from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure


def create_rectangular_grid(width: float, height: float, nx: int, ny: int) -> Structure:
    nodes: list[Node] = []
    springs: list[Spring] = []

    dx = width / (nx - 1) if nx > 1 else 0.0
    dy = height / (ny - 1) if ny > 1 else 0.0

    nid = 0
    for row in range(ny):
        for col in range(nx):
            nodes.append(Node(id=nid, x=col * dx, y=row * dy))
            nid += 1

    def idx(r: int, c: int) -> int:
        return r * nx + c

    for r in range(ny):
        for c in range(nx):
            i = idx(r, c)
            if c + 1 < nx:
                springs.append(Spring(node_i=i, node_j=idx(r, c + 1), k=1.0))
            if r + 1 < ny:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c), k=1.0))
            if r + 1 < ny and c + 1 < nx:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c + 1), k=1.0))
            if r + 1 < ny and c - 1 >= 0:
                springs.append(Spring(node_i=i, node_j=idx(r + 1, c - 1), k=1.0))

    return Structure(nodes=nodes, springs=springs)


def apply_simply_supported_beam(structure: Structure, nx: int, ny: int, load_fy: float) -> None:
    for n in structure.nodes:
        n.fix_x = False
        n.fix_y = False
        n.fx = 0.0
        n.fy = 0.0

    structure.nodes[0].fix_y = True
    structure.nodes[nx - 1].fix_x = True
    structure.nodes[nx - 1].fix_y = True

    mid_col = nx // 2
    structure.nodes[(ny - 1) * nx + mid_col].fy = float(load_fy)


# ── Bild → Struktur ─────────────────────────────────────────────────────────

def image_to_binary_grid(
    image_bytes: BytesIO,
    nx: int,
    ny: int,
    brightness_threshold: int,
    coverage_threshold: float,
) -> np.ndarray:
    """Konvertiert ein Bild in ein binäres (nx)x(ny) Grid.

    Returns:
        2D bool-Array (ny, nx) — True = Struktur (dunkel genug).
    """
    img = Image.open(image_bytes).convert("L")
    pixels = np.asarray(img, dtype=np.float32)
    img_h, img_w = pixels.shape

    grid = np.zeros((ny, nx), dtype=bool)

    for row in range(ny):
        for col in range(nx):
            y0 = int(row * img_h / ny)
            y1 = int((row + 1) * img_h / ny)
            x0 = int(col * img_w / nx)
            x1 = int((col + 1) * img_w / nx)

            cell = pixels[y0:y1, x0:x1]
            if cell.size == 0:
                continue

            dark_ratio = float(np.mean(cell < brightness_threshold))
            grid[row, col] = dark_ratio >= coverage_threshold

    return grid


def create_structure_from_image(
    image_bytes: BytesIO,
    nx: int,
    ny: int,
    brightness_threshold: int,
    coverage_threshold: float,
    width: float,
    height: float,
) -> Structure:
    """Erstellt eine Structure aus einem Bild.

    Nutzt create_rectangular_grid für die Basis-Struktur,
    deaktiviert dann Knoten/Federn in hellen Bereichen.
    """
    grid = image_to_binary_grid(image_bytes, nx, ny, brightness_threshold, coverage_threshold)
    structure = create_rectangular_grid(width, height, nx, ny)

    # Knoten deaktivieren wo das Bild hell ist
    inactive = set()
    for row in range(ny):
        for col in range(nx):
            if not grid[row, col]:
                nid = row * nx + col
                structure.nodes[nid].active = False
                inactive.add(nid)

    # Federn deaktivieren wenn ein Endknoten inaktiv ist
    for spring in structure.springs:
        if spring.node_i in inactive or spring.node_j in inactive:
            spring.active = False

    return structure
