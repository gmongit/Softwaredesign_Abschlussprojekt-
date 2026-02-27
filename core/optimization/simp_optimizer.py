from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field

from core.model.structure import Structure
from core.solver.solver import solve
from core.optimization.optimizer_base import OptimizerBase


@dataclass(slots=True)
class SIMPHistory:
    compliance: list[float] = field(default_factory=list)
    volume_fraction: list[float] = field(default_factory=list)
    area_change: list[float] = field(default_factory=list)
    stop_reason: str = ""


class SIMPOptimizer(OptimizerBase):
    """SIMP-basierte Sizing-Optimierung (Solid Isotropic Material with Penalization).
    Passt Querschnittsflächen der Stäbe an um Compliance zu minimieren."""

    def __init__(
        self,
        e_modul_pa: float,
        a_min: float = 1e-9,
        a_max: float | None = None,
        volume_fraction: float = 0.5,
        penalty: float = 3.0,
        eta: float = 0.5,
        move_limit: float = 0.2,
        tol: float = 1e-3,
    ):
        self.e_modul_pa = e_modul_pa
        self.a_min = a_min
        self.a_max = a_max
        self.volume_fraction = volume_fraction
        self.penalty = penalty
        self.eta = eta
        self.move_limit = move_limit
        self.tol = tol

    def _get_areas(self, structure: Structure) -> np.ndarray:
        return np.array([s.area for s in structure.springs], dtype=float)

    def _set_areas(self, structure: Structure, areas: np.ndarray) -> None:
        for idx, spring in enumerate(structure.springs):
            spring.area = float(areas[idx])
        structure.update_spring_stiffnesses_from_areas(self.e_modul_pa)

    def _apply_simp_penalty(self, structure: Structure, areas: np.ndarray) -> None:
        """k_eff = (rho_e)^p * k_full, wobei rho_e = A_e / A_max."""
        if self.penalty <= 1.0:
            return
        a_max = self.a_max or float(np.max(areas))
        for idx, spring in enumerate(structure.springs):
            if not spring.active:
                continue
            ni = structure.nodes[spring.node_i]
            nj = structure.nodes[spring.node_j]
            rho_e = areas[idx] / a_max
            k_full = self.e_modul_pa * a_max / spring.length(ni, nj)
            spring.k = (rho_e ** self.penalty) * k_full

    def _compute_sensitivities(
        self, structure: Structure, u: np.ndarray, areas: np.ndarray
    ) -> np.ndarray:
        """dc/dA_e pro Stab berechnen."""
        n_springs = len(structure.springs)
        dc = np.zeros(n_springs, dtype=float)
        a_max = self.a_max or float(np.max(areas))

        for idx, spring in enumerate(structure.springs):
            if not spring.active:
                continue
            ni = structure.nodes[spring.node_i]
            nj = structure.nodes[spring.node_j]
            if not (ni.active and nj.active):
                continue

            e = spring.direction_unit(ni, nj)
            ui = np.array([u[ni.dof_x], u[ni.dof_y]], dtype=float)
            uj = np.array([u[nj.dof_x], u[nj.dof_y]], dtype=float)
            delta_e = float(np.dot(e, (uj - ui)))
            L_e = spring.length(ni, nj)

            if self.penalty > 1.0:
                rho_e = areas[idx] / a_max
                dc[idx] = -self.penalty * (rho_e ** (self.penalty - 1)) \
                          * (self.e_modul_pa / L_e) * delta_e ** 2
            else:
                dc[idx] = -(self.e_modul_pa / L_e) * delta_e ** 2

        return dc

    def _oc_update(
        self,
        structure: Structure,
        areas: np.ndarray,
        dc: np.ndarray,
    ) -> np.ndarray:
        """Optimality-Criteria Update mit Bisection für den Lagrange-Multiplikator."""
        a_max = self.a_max or float(np.max(areas))
        a_min = self.a_min
        move = self.move_limit * a_max

        lengths = np.zeros(len(structure.springs), dtype=float)
        for idx, spring in enumerate(structure.springs):
            if spring.active:
                ni = structure.nodes[spring.node_i]
                nj = structure.nodes[spring.node_j]
                lengths[idx] = spring.length(ni, nj)

        v_initial = sum(
            a_max * lengths[i]
            for i in range(len(structure.springs))
            if structure.springs[i].active
        )
        v_target = self.volume_fraction * v_initial

        lam_lo, lam_hi = 1e-20, 1e20

        for _ in range(100):
            lam_mid = 0.5 * (lam_lo + lam_hi)

            areas_new = np.copy(areas)
            for idx in range(len(structure.springs)):
                if not structure.springs[idx].active or lengths[idx] <= 0:
                    continue

                numerator = -dc[idx]
                denominator = lam_mid * lengths[idx]

                if numerator <= 0 or denominator <= 0:
                    b_e = 0.0
                else:
                    b_e = np.sqrt(numerator / denominator)

                a_candidate = areas[idx] * (b_e ** self.eta)

                a_lo = max(a_min, areas[idx] - move)
                a_hi = min(a_max, areas[idx] + move)

                areas_new[idx] = max(a_lo, min(a_hi, a_candidate))

            v_new = sum(areas_new[i] * lengths[i] for i in range(len(structure.springs))
                        if structure.springs[i].active)

            if v_new > v_target:
                lam_lo = lam_mid
            else:
                lam_hi = lam_mid

            if abs(lam_hi - lam_lo) / max(lam_mid, 1e-20) < 1e-10:
                break

        return areas_new

    def _compute_compliance(self, structure: Structure, u: np.ndarray) -> float:
        K = structure.assemble_K()
        return float(u @ K @ u)

    def step(self, structure: Structure) -> np.ndarray:
        areas = self._get_areas(structure)
        self._apply_simp_penalty(structure, areas)

        K = structure.assemble_K()
        F = structure.assemble_F()
        fixed = structure.fixed_dofs()
        u = solve(K, F, fixed)

        if u is None:
            return areas

        dc = self._compute_sensitivities(structure, u, areas)
        areas_new = self._oc_update(structure, areas, dc)

        self._set_areas(structure, areas_new)

        return areas_new

    def run(
        self,
        structure: Structure,
        target_mass_fraction: float = 0.5,
        max_iters: int = 200,
        on_iter=None,
    ) -> SIMPHistory:
        history = SIMPHistory()

        if not structure.is_valid_topology():
            history.stop_reason = "Ungültige Topologie"
            return history

        a_max_val = self.a_max or float(max((s.area for s in structure.springs if s.active), default=1.0))
        self.a_max = a_max_val

        u_init = solve(structure.assemble_K(), structure.assemble_F(), structure.fixed_dofs())
        if u_init is None:
            history.stop_reason = "Struktur ist singulär"
            return history

        prev_compliance = float('inf')
        singular_count = 0
        original_move_limit = self.move_limit

        for iter_idx in range(max_iters):
            areas = self._get_areas(structure)
            areas_backup = np.copy(areas)

            self._apply_simp_penalty(structure, areas)

            K = structure.assemble_K()
            F = structure.assemble_F()
            fixed = structure.fixed_dofs()
            u = solve(K, F, fixed)

            if u is None:
                # Revert und mit kleinerem Move-Limit nochmal
                self._set_areas(structure, areas_backup)
                singular_count += 1
                if singular_count > 3:
                    history.stop_reason = "Struktur wurde singulär"
                    break
                self.move_limit *= 0.5
                self.move_limit = max(self.move_limit, 0.01)
                continue

            singular_count = 0

            compliance = self._compute_compliance(structure, u)
            vol_total = structure.total_volume_from_areas()
            vol_initial = a_max_val * sum(
                structure.springs[i].length(
                    structure.nodes[structure.springs[i].node_i],
                    structure.nodes[structure.springs[i].node_j]
                )
                for i in range(len(structure.springs))
                if structure.springs[i].active
            )
            vol_frac = vol_total / max(vol_initial, 1e-20)

            dc = self._compute_sensitivities(structure, u, areas)
            areas_new = self._oc_update(structure, areas, dc)

            area_change = float(np.max(np.abs(areas_new - areas))) / a_max_val

            history.compliance.append(compliance)
            history.volume_fraction.append(vol_frac)
            history.area_change.append(area_change)

            self._set_areas(structure, areas_new)

            if on_iter is not None:
                on_iter(structure, iter_idx, compliance, vol_frac)

            rel_change = abs(compliance - prev_compliance) / max(abs(prev_compliance), 1e-20)
            if iter_idx > 5 and rel_change < self.tol and area_change < self.tol:
                history.stop_reason = "Konvergiert"
                break

            prev_compliance = compliance
        else:
            history.stop_reason = "Max. Iterationen erreicht"

        self.move_limit = original_move_limit
        return history

    def post_process(self, structure: Structure, threshold_fraction: float = 0.01) -> int:
        """Entfernt Federn mit area < threshold und prüft danach Lösbarkeit."""
        a_max_val = self.a_max or float(max((s.area for s in structure.springs if s.active), default=1.0))
        threshold = threshold_fraction * a_max_val

        thin_springs = [s for s in structure.springs if s.active and s.area < threshold]
        if not thin_springs:
            return 0

        spring_was_active = [s.active for s in structure.springs]
        node_was_active = [n.active for n in structure.nodes]

        def _restore():
            for i, s in enumerate(structure.springs):
                s.active = spring_was_active[i]
            for i, n in enumerate(structure.nodes):
                n.active = node_was_active[i]

        # Alle dünnen auf einmal raus
        for spring in thin_springs:
            spring.active = False

        structure.remove_removable_nodes()

        if self._solve_structure(structure) is not None:
            return len(thin_springs)

        # Ging nicht -> einzeln probieren
        _restore()
        removed = 0
        for spring in thin_springs:
            spring.active = False
            if self._solve_structure(structure) is None:
                spring.active = True
            else:
                removed += 1

        structure.remove_removable_nodes()

        if self._solve_structure(structure) is None:
            _restore()
            removed = 0

        return removed