"""Verallgemeinerter Eigenwertlöser für die Strukturdynamik."""
from __future__ import annotations

import logging
import math

import numpy as np
from scipy.linalg import eigh

logger = logging.getLogger(__name__)


def apply_boundary_conditions_to_matrix(mat: np.ndarray, fixed_dofs: list[int]) -> np.ndarray:
    """Wendet Dirichlet-Randbedingungen auf eine Matrix an (gibt Kopie zurück).

    Für jeden fixierten DOF d: Zeile d und Spalte d werden auf 0 gesetzt,
    Diagonalelement auf 1. Funktioniert sowohl für die Steifigkeitsmatrix K
    als auch für die Massenmatrix M.

    Parameter
    ---------
    mat : np.ndarray
        Quadratische Matrix (n × n). Wird nicht in-place verändert.
    fixed_dofs : list[int]
        Indizes der fixierten Freiheitsgrade.

    Rückgabe
    --------
    np.ndarray
        Veränderte Kopie von mat.
    """
    out = mat.copy()
    for d in fixed_dofs:
        out[d, :] = 0.0
        out[:, d] = 0.0
        out[d, d] = 1.0
    return out


def solve_eigenvalue(
    K: np.ndarray,
    M: np.ndarray,
    fixed_dofs: list[int],
    n_modes: int = 6,
) -> tuple[np.ndarray, np.ndarray]:
    """Löst das verallgemeinerte Eigenwertproblem (K - ω²·M)·û = 0.

    Das System wird vor der Lösung auf freie DOFs reduziert. Dadurch werden
    Randbedingungs-Artefakt-Eigenwerte (λ=1) vermieden, die bei der
    Penalty-Methode am Gesamtsystem die niedrigsten Moden verfälschen würden.

    Eigenvektoren werden in voller Größe (2n,) zurückgegeben, mit Nullen
    an den fixierten DOFs.

    Parameter
    ---------
    K : np.ndarray
        Globale Steifigkeitsmatrix (2n × 2n), ohne aufgeprägte Randbedingungen.
    M : np.ndarray
        Globale Massenmatrix (2n × 2n), ohne aufgeprägte Randbedingungen.
    fixed_dofs : list[int]
        Indizes der fixierten DOFs (Dirichlet-Randbedingungen).
    n_modes : int
        Anzahl der niedrigsten zu berechnenden Moden.

    Rückgabe
    --------
    tuple[np.ndarray, np.ndarray]
        (Eigenwerte, Eigenvektoren)
        Eigenwerte[k]    = ω_k²  (aufsteigend, auf >= 0 beschränkt)
        Eigenvektoren[:,k] = û_k  (volle Größe, Null an fixierten DOFs)
    """
    n = K.shape[0]
    fixed_set = set(fixed_dofs)
    free_dofs = np.array([d for d in range(n) if d not in fixed_set], dtype=int)

    if len(free_dofs) == 0:
        logger.warning("Keine freien DOFs vorhanden — gebe Null-Eigenwerte zurück.")
        return np.zeros(n_modes), np.zeros((n, n_modes))

    n_modes_actual = min(n_modes, len(free_dofs))

    # Reduziertes System: nur freie DOFs
    K_free = K[np.ix_(free_dofs, free_dofs)]
    M_free = M[np.ix_(free_dofs, free_dofs)]

    # Regularisierung analog zu solver.py: verhindert singuläre Matrix
    # bei Mechanismus-Moden (Rechteckgitter ohne Diagonalen).
    eps_reg = max(float(np.max(np.abs(K_free))), 1.0) * 1e-8
    K_reg = K_free + eps_reg * np.eye(len(free_dofs))

    # Wir berechnen mehr Moden als angefordert, damit nach dem Filtern
    # noch genug echte Strukturmoden übrig bleiben.
    n_compute = min(n_modes_actual * 8, len(free_dofs))

    try:
        eigenvalues_raw, eigvecs_raw = eigh(
            K_reg,
            M_free,
            subset_by_index=[0, n_compute - 1],
        )
        eigenvalues_raw = np.maximum(eigenvalues_raw, 0.0)

        # Mechanismus-Moden filtern:
        # Ihre Eigenwerte liegen bei ≈ eps_reg / m_min (durch Regularisierung erzeugt).
        # Echter Strukturmode: λ = k_real / m >> eps_reg / m
        m_diag = np.diag(M_free)
        m_pos = m_diag[m_diag > 0.0]
        m_min = float(np.min(m_pos)) if len(m_pos) > 0 else 1.0
        # Schwellwert = 10x die maximal mögliche Mechanismus-Eigenfrequenz²
        threshold = (eps_reg / m_min) * 10.0

        real_mask = eigenvalues_raw > threshold
        if not np.any(real_mask):
            # Keine echten Moden gefunden — Fallback auf alle
            logger.warning(
                "Keine Strukturmoden oberhalb des Mechanismus-Schwellwerts (%.2e). Verwende rohe Moden.",
                threshold,
            )
            real_mask = np.ones(len(eigenvalues_raw), dtype=bool)

        ev_struct = eigenvalues_raw[real_mask]
        vc_struct = eigvecs_raw[:, real_mask]

        # Auf n_modes kürzen
        n_take = min(n_modes_actual, len(ev_struct))
        eigenvalues_out = np.zeros(n_modes_actual)
        eigenvalues_out[:n_take] = ev_struct[:n_take]

        eigvecs_full = np.zeros((n, n_modes_actual))
        eigvecs_full[free_dofs, :n_take] = vc_struct[:, :n_take]

        return eigenvalues_out, eigvecs_full

    except Exception as exc:
        logger.warning("Eigenwertberechnung fehlgeschlagen: %s. Gebe Nullen zurück.", exc)
        return np.zeros(n_modes_actual), np.zeros((n, n_modes_actual))


def first_natural_frequency(eigenvalues: np.ndarray) -> tuple[float, float]:
    """Extrahiert die erste Eigenfrequenz aus den Eigenwerten.

    Parameter
    ---------
    eigenvalues : np.ndarray
        Array der ω_k²-Werte (aufsteigend sortiert).

    Rückgabe
    --------
    tuple[float, float]
        (omega_1, f_1), wobei omega_1 in rad/s und f_1 in Hz angegeben ist.
    """
    omega_1 = math.sqrt(max(0.0, float(eigenvalues[0])))
    f_1 = omega_1 / (2.0 * math.pi)
    return omega_1, f_1