"""Aufbau der diagonalen Massenmatrix (lumped mass) für 2D-Federstrukturen."""
from __future__ import annotations

import numpy as np

from core.model.structure import Structure


def assemble_M(structure: Structure, node_mass: float) -> np.ndarray:
    """Erstellt die diagonale lumped-mass-Matrix M (2n × 2n).

    Wenn die Struktur Materialeigenschaften besitzt (Dichte > 0, Querschnitt > 0),
    wird die physikalisch korrekte Knotenmasse verwendet: Jeder Knoten erhält
    die halbe Masse jedes anliegenden aktiven Stabs (m_stab = ρ · A · L).

    Andernfalls wird einheitlich `node_mass` pro aktivem Knoten verwendet.

    Inaktive Knoten erhalten die Masse 0 (Randbedingungen werden separat
    im Eigenwertlöser aufgeprägt).

    Parameter
    ---------
    structure : Structure
        Das Strukturmodell.
    node_mass : float
        Fallback-Masse pro aktivem Knoten [kg], falls kein Material gesetzt ist.

    Rückgabe
    --------
    np.ndarray
        Diagonale Massenmatrix der Form (2n, 2n).
    """
    M_diag = np.zeros(structure.ndof, dtype=float)

    if structure.density > 0.0 and structure.beam_area > 0.0:
        # Physikalisch korrekte lumped mass: halbe Stabmasse auf jeden Endknoten
        nodal_masses = np.zeros(len(structure.nodes), dtype=float)
        for spring in structure.springs:
            if not spring.active:
                continue
            ni = structure.nodes[spring.node_i]
            nj = structure.nodes[spring.node_j]
            if not (ni.active and nj.active):
                continue
            m = spring.compute_mass(ni, nj, structure.density, structure.beam_area)
            nodal_masses[ni.id] += 0.5 * m
            nodal_masses[nj.id] += 0.5 * m

        for node in structure.nodes:
            if not node.active:
                continue
            m = nodal_masses[node.id] if nodal_masses[node.id] > 0.0 else node_mass
            M_diag[node.dof_x] = m
            M_diag[node.dof_y] = m
    else:
        # Fallback: einheitliche Knotenmasse
        for node in structure.nodes:
            if not node.active:
                continue
            M_diag[node.dof_x] = node_mass
            M_diag[node.dof_y] = node_mass

    return np.diag(M_diag)