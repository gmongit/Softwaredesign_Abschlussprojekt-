import warnings

import numpy as np
import numpy.typing as npt
from scipy import sparse
from scipy.sparse.linalg import spsolve, lsqr


def solve(K, F: npt.NDArray[np.float64], u_fixed_idx: list[int]) -> npt.NDArray[np.float64] | None:
    """Ku = F lösen. Reduziert auf freie DOFs, nutzt Sparse-Solver.
    Fallback auf lsqr bei konsistenter Singularität. Gibt None bei echter Singularität zurück."""

    n = K.shape[0]
    assert K.shape[0] == K.shape[1], "Stiffness matrix K must be square."
    assert n == F.shape[0], "Force vector F must have the same size as K."

    fixed_set = set(u_fixed_idx)
    free = np.array([i for i in range(n) if i not in fixed_set], dtype=np.intp)

    if len(free) == 0:
        return np.zeros(n)

    if sparse.issparse(K):
        K_ff = K[free][:, free].tocsc()
    else:
        K_ff = K[np.ix_(free, free)]

    F_f = F[free]

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("error", category=sparse.linalg.MatrixRankWarning)
            u_f = spsolve(K_ff, F_f) if sparse.issparse(K_ff) else np.linalg.solve(K_ff, F_f)

    except (np.linalg.LinAlgError, sparse.linalg.MatrixRankWarning):
        if not sparse.issparse(K_ff):
            K_ff = sparse.csc_matrix(K_ff)
        result = lsqr(K_ff, F_f)
        u_f = result[0]
        residual_norm = result[3]
        if residual_norm > 1e-6:
            return None

    except RuntimeError:
        return None

    u_f = np.asarray(u_f, dtype=float).ravel()

    if np.any(np.isnan(u_f)) or np.any(np.isinf(u_f)):
        return None

    # Residual-Check: Erfüllt die Lösung K_ff·u_f = F_f?
    r = K_ff @ u_f - F_f
    F_norm = np.linalg.norm(F_f)
    if F_norm > 0 and np.linalg.norm(r) / F_norm > 1e-4:
        return None

    u = np.zeros(n)
    u[free] = u_f
    return u


def test_case_horizontal():
    e_n = np.array([1.0, 0.0])
    e_n = e_n / np.linalg.norm(e_n)

    k = 1.0
    K = k * np.array([[1.0, -1.0], [-1.0, 1.0]])
    print(f"{K=}")

    O = np.outer(e_n, e_n)
    print(f"{O=}")

    Ko = np.kron(K, O)
    print(f"{Ko=}")

    u_fixed_idx = [0, 1]

    F = np.array([0.0, 0.0, 10.0, 0.0])

    u = solve(Ko, F, u_fixed_idx)
    print(f"{u=}")

def test_case_diagonal():
    e_n = np.array([1.0, 1.0])
    e_n = e_n / np.linalg.norm(e_n)

    k = 1.0 / np.sqrt(2.0)
    K = k * np.array([[1.0, -1.0], [-1.0, 1.0]])
    print(f"{K=}")

    O = np.outer(e_n, e_n)
    print(f"{O=}")

    Ko = np.kron(K, O)
    print(f"{Ko=}")

    u_fixed_idx = [0, 1]

    F = np.array([0.0, 0.0, 1.0, 1.0])

    u = solve(Ko, F, u_fixed_idx)
    print(f"{u=}")

if __name__ == "__main__":

    test_case_horizontal()

    test_case_diagonal()
