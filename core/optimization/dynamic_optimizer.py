"""Dynamischer Topologieoptimierer – kombiniert statisches und eigenfrequenzbasiertes Kriterium."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass

from core.model.structure import Structure
from core.solver.solver import solve
from core.solver.mass_matrix import assemble_M
from core.solver.eigenvalue_solver import solve_eigenvalue
from core.optimization.optimizer_base import OptimizerBase


@dataclass(slots=True)
class DynamicOptimizationHistory:
    """Speichert die Metriken pro Iteration eines dynamischen Optimierungslaufs."""
    mass_fraction:    list[float]
    removed_per_iter: list[int]
    omega_1:          list[float]  # erste Eigenkreisfrequenz [rad/s]
    f_1:              list[float]  # erste Eigenfrequenz [Hz]
    freq_distance:    list[float]  # |ω₁ - ω_erreger| pro Iteration
    stop_reason:      str = ""


class DynamicOptimizer(OptimizerBase):
    """Topologieoptimierer auf Basis eines kombinierten statisch-dynamischen Wichtigkeitsscores.

    Statisches Kriterium:  Formänderungsenergie pro Knoten (aus statischer FEM-Lösung).
    Dynamisches Kriterium: Rayleigh-Quotient-Sensitivität bezüglich des ersten Eigenmodes.
    Kombinierter Score:    (1 - alpha) * statisch_norm + alpha * dynamisch_norm

    Knoten mit dem niedrigsten Score werden zuerst entfernt.
    Symmetrie wird automatisch erkannt (wie im EnergyBasedOptimizer).
    """

    def __init__(
        self,
        omega_excitation: float = 10.0,
        alpha: float = 0.5,
        remove_fraction: float = 0.05,
        node_mass: float = 1.0,
    ):
        if not (0.0 < remove_fraction < 1.0):
            raise ValueError("remove_fraction muss im Bereich (0, 1) liegen.")
        if not (0.0 <= alpha <= 1.0):
            raise ValueError("alpha muss im Bereich [0, 1] liegen.")
        if node_mass <= 0.0:
            raise ValueError("node_mass muss größer als 0 sein.")

        self.omega_excitation = omega_excitation
        self.alpha = alpha
        self.remove_fraction = remove_fraction
        self.node_mass = node_mass
        self.mirror_map: dict[int, int] | None = None

    # Wichtigkeitsberechnung

    def _assemble_and_solve_eigen(self, structure: Structure) -> tuple[float, np.ndarray]:
        """Stellt K und M auf, löst das Eigenwertproblem und gibt (omega_1, eigvec_1) zurück."""
        K = structure.assemble_K()
        M = assemble_M(structure, self.node_mass)
        fixed = structure.fixed_dofs()
        eigenvalues, eigenvectors = solve_eigenvalue(K, M, fixed, n_modes=6)
        omega_1 = float(np.sqrt(max(0.0, float(eigenvalues[0]))))
        eigvec_1 = eigenvectors[:, 0]
        return omega_1, eigvec_1

    def _compute_dynamic_importance(self, structure: Structure, eigvec_1: np.ndarray) -> np.ndarray:
        """Rayleigh-basierte Knotenwichtigkeit aus dem ersten Eigenmode."""
        M = assemble_M(structure, self.node_mass)
        importance = np.zeros(len(structure.nodes), dtype=float)
        for node in structure.nodes:
            if not node.active:
                continue
            ux = float(eigvec_1[node.dof_x])
            uy = float(eigvec_1[node.dof_y])
            m_i = float(M[node.dof_x, node.dof_x])
            importance[node.id] = (ux * ux + uy * uy) * m_i
        return importance

    def _compute_static_importance(self, structure: Structure) -> np.ndarray:
        """Formänderungsenergie-basierte Knotenwichtigkeit (statische FEM-Lösung)."""
        K = structure.assemble_K()
        F = structure.assemble_F()
        fixed = structure.fixed_dofs()
        u = solve(K, F, fixed)
        if u is None:
            return np.zeros(len(structure.nodes), dtype=float)
        return structure.node_importance_from_energy(u)

    def _combined_score(self, static_imp: np.ndarray, dynamic_imp: np.ndarray) -> np.ndarray:
        """Rang-normierter gewichteter Score aus statischer und dynamischer Wichtigkeit."""
        n = len(static_imp)
        if n == 0:
            return np.zeros(0)
        denom = max(n - 1, 1)
        static_rank = np.argsort(np.argsort(static_imp)).astype(float) / denom
        dynamic_rank = np.argsort(np.argsort(dynamic_imp)).astype(float) / denom
        return (1.0 - self.alpha) * static_rank + self.alpha * dynamic_rank

    # Öffentliche Schnittstelle

    def step(self, structure: Structure) -> np.ndarray:
        """Führt eine Optimierungsiteration durch. Gibt den kombinierten Score zurück."""
        _, eigvec_1 = self._assemble_and_solve_eigen(structure)
        n = len(structure.nodes)
        static_imp = self._compute_static_importance(structure) if self.alpha < 1.0 else np.zeros(n)
        dynamic_imp = self._compute_dynamic_importance(structure, eigvec_1) if self.alpha > 0.0 else np.zeros(n)
        score = self._combined_score(static_imp, dynamic_imp)

        candidates = self._select_candidates(structure, score, self.remove_fraction)
        self._deactivate_nodes(structure, candidates)
        return score

    def run(
        self,
        structure: Structure,
        target_mass_fraction: float,
        max_iters: int = 200,
        max_stress: float | None = None,
        on_iter=None,
        force: bool = False,
    ) -> DynamicOptimizationHistory:
        if not (0.0 < target_mass_fraction <= 1.0):
            raise ValueError("target_mass_fraction muss im Bereich (0, 1] liegen.")
        if max_iters <= 0:
            raise ValueError("max_iters muss größer als 0 sein.")

        history = DynamicOptimizationHistory(
            mass_fraction=[], removed_per_iter=[],
            omega_1=[], f_1=[], freq_distance=[],
        )

        structure._register_special_nodes()

        # Auto-Symmetrie-Erkennung (wie im EnergyBasedOptimizer)
        is_sym, mirror_map = structure.detect_symmetry()
        if is_sym:
            self.mirror_map = mirror_map

        if force:
            for iter_idx in range(max_iters):
                structure.remove_removable_nodes()
                history.mass_fraction.append(structure.current_mass_fraction())
                if structure.current_mass_fraction() <= target_mass_fraction:
                    history.stop_reason = "Ziel-Massenanteil erreicht"
                    break
                try:
                    omega_1, eigvec_1 = self._assemble_and_solve_eigen(structure)
                except Exception:
                    history.stop_reason = "Eigenwertberechnung fehlgeschlagen"
                    break
                history.omega_1.append(omega_1)
                history.f_1.append(omega_1 / (2.0 * np.pi))
                history.freq_distance.append(abs(omega_1 - self.omega_excitation))
                n = len(structure.nodes)
                u = self._solve_structure(structure)
                static_imp = (
                    structure.node_importance_from_energy(u)
                    if u is not None and self.alpha < 1.0
                    else np.zeros(n)
                )
                dynamic_imp = (
                    self._compute_dynamic_importance(structure, eigvec_1)
                    if self.alpha > 0.0
                    else np.zeros(n)
                )
                score = self._combined_score(static_imp, dynamic_imp)
                candidates = self._select_candidates(structure, score, self.remove_fraction)
                if not candidates:
                    history.stop_reason = "Keine entfernbaren Knoten mehr"
                    break
                self._deactivate_nodes(structure, candidates)
                history.removed_per_iter.append(len(candidates))
                if on_iter is not None:
                    on_iter(structure, iter_idx, omega_1, len(candidates))
            else:
                history.stop_reason = "Max. Iterationen erreicht"
            return history

        # Pre-Check: Stress bereits über Limit?
        u = self._solve_structure(structure)
        if max_stress is not None:
            if u is None:
                history.stop_reason = "Struktur ist instabil"
                return history
            if structure.max_stress(u) > max_stress:
                history.stop_reason = "Ausgangsspannung überschreitet bereits die Streckgrenze"
                return history

        blacklist: set[int] = set()
        needs_solve = u is None

        for iter_idx in range(max_iters):
            # 1. Nutzlose Knoten entfernen (Inseln / Sackgassen)
            removed_set = structure._find_removable_nodes()
            if removed_set:
                structure.remove_removable_nodes()
                needs_solve = True

            # 2. Zielmasse erreicht?
            history.mass_fraction.append(structure.current_mass_fraction())
            if structure.current_mass_fraction() <= target_mass_fraction:
                history.stop_reason = "Ziel-Massenanteil erreicht"
                break

            # 3. Statischer Solver
            if needs_solve:
                u = self._solve_structure(structure)
                if u is None:
                    if removed_set:
                        self._reactivate_nodes(structure, list(removed_set))
                        u = self._solve_structure(structure)
                    if u is None:
                        history.stop_reason = "Struktur ist instabil"
                        break
                needs_solve = False

            # 3b. Stress-Check nach Solver
            assert u is not None
            if self._exceeds_stress(structure, u, max_stress):
                assert max_stress is not None
                if not self._try_stress_redistribution(structure, u, blacklist):
                    history.stop_reason = "Streckgrenze erreicht"
                    break
                u = self._solve_structure(structure)
                if u is None:
                    history.stop_reason = "Struktur instabil nach Lastumverteilung"
                    break

            # 4. Eigenwertproblem
            try:
                omega_1, eigvec_1 = self._assemble_and_solve_eigen(structure)
            except Exception:
                history.stop_reason = "Eigenwertberechnung fehlgeschlagen"
                break
            history.omega_1.append(omega_1)
            history.f_1.append(omega_1 / (2.0 * np.pi))
            history.freq_distance.append(abs(omega_1 - self.omega_excitation))

            # 5. Kombinierter Wichtigkeitsscore
            n = len(structure.nodes)
            static_imp = structure.node_importance_from_energy(u) if self.alpha < 1.0 else np.zeros(n)
            dynamic_imp = self._compute_dynamic_importance(structure, eigvec_1) if self.alpha > 0.0 else np.zeros(n)
            score = self._combined_score(static_imp, dynamic_imp)

            # 6. Kandidaten auswählen (mit Blacklist)
            candidates = self._select_candidates(structure, score, self.remove_fraction, blacklist)
            if not candidates:
                history.stop_reason = "Keine entfernbaren Knoten mehr"
                break

            # 7. Alle Kandidaten auf einmal entfernen — check ob noch lösbar
            self._deactivate_nodes(structure, candidates)
            u_check = self._solve_structure(structure)

            if u_check is not None:
                if self._exceeds_stress(structure, u_check, max_stress):
                    self._reactivate_nodes(structure, candidates)
                    history.stop_reason = "Streckgrenze erreicht"
                    break
                u = u_check
                needs_solve = False
                history.removed_per_iter.append(len(candidates))
                if on_iter is not None:
                    on_iter(structure, iter_idx, omega_1, len(candidates))
                continue

            # 8. Batch fehlgeschlagen — gruppiert versuchen (Mirror-Paare)
            self._reactivate_nodes(structure, candidates)

            seen: set[int] = set()
            groups: list[list[int]] = []
            candidate_set = set(candidates)
            for nid in candidates:
                if nid in seen:
                    continue
                mid = self.mirror_map.get(nid) if self.mirror_map else None
                if mid is not None and mid != nid and mid in candidate_set and mid not in seen:
                    groups.append([nid, mid])
                    seen.update([nid, mid])
                else:
                    groups.append([nid])
                    seen.add(nid)

            actually_removed: list[int] = []
            for group in groups:
                self._deactivate_nodes(structure, group)
                u_test = self._solve_structure(structure)

                if u_test is None or self._exceeds_stress(structure, u_test, max_stress):
                    self._reactivate_nodes(structure, group)
                    self._blacklist_with_mirror(group, blacklist)
                else:
                    u = u_test
                    actually_removed.extend(group)

            if not actually_removed:
                history.stop_reason = "Keine weitere Optimierung möglich"
                break

            needs_solve = False
            history.removed_per_iter.append(len(actually_removed))
            if on_iter is not None:
                on_iter(structure, iter_idx, omega_1, len(actually_removed))

        else:
            history.stop_reason = "Max. Iterationen erreicht"

        return history
