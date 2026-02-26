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


class DynamicOptimizer(OptimizerBase):
    """Topologieoptimierer auf Basis eines kombinierten statisch-dynamischen Wichtigkeitsscores.

    Statisches Kriterium:  Formänderungsenergie pro Knoten (aus statischer FEM-Lösung).
    Dynamisches Kriterium: Rayleigh-Quotient-Sensitivität bezüglich des ersten Eigenmodes.
    Kombinierter Score:    (1 - alpha) * statisch_norm + alpha * dynamisch_norm

    Knoten mit dem niedrigsten Score werden zuerst entfernt.
    """

    def __init__(
        self,
        node_mass: float = 1.0,
        omega_excitation: float = 10.0,
        alpha: float = 0.5,
        remove_fraction: float = 0.05,
        enforce_symmetry: bool = False,
        nx: int | None = None,
    ):
        if not (0.0 < remove_fraction < 1.0):
            raise ValueError("remove_fraction muss im Bereich (0, 1) liegen.")
        if not (0.0 <= alpha <= 1.0):
            raise ValueError("alpha muss im Bereich [0, 1] liegen.")
        if node_mass <= 0.0:
            raise ValueError("node_mass muss größer als 0 sein.")
        if enforce_symmetry and nx is None:
            raise ValueError("nx muss angegeben werden, wenn enforce_symmetry=True gesetzt ist.")

        self.node_mass = node_mass
        self.omega_excitation = omega_excitation
        self.alpha = alpha
        self.remove_fraction = remove_fraction
        self.enforce_symmetry = enforce_symmetry
        self.nx = nx

    # Hilfsmethoden für Spiegelung (identische Logik wie im EnergyBasedOptimizer)

    def _get_mirror_node(self, node_id: int) -> int:
        if self.nx is None:
            raise ValueError("nx muss für die Spiegelberechnung gesetzt sein.")
        row = node_id // self.nx
        col = node_id % self.nx
        mirror_col = (self.nx - 1) - col
        return row * self.nx + mirror_col

    def _is_on_symmetry_line(self, node_id: int) -> bool:
        if self.nx is None:
            raise ValueError("nx muss für die Symmetrieprüfung gesetzt sein.")
        col = node_id % self.nx
        return col == (self.nx - 1) - col

    # Wichtigkeitsberechnung

    def _assemble_and_solve_eigen(self, structure: Structure) -> tuple[float, np.ndarray]:
        """Stellt K und M auf, löst das Eigenwertproblem und gibt (omega_1, eigvec_1) zurück.

        Es werden mehr Moden als benötigt angefordert, damit Mechanismus-Moden
        (Regularisierungsartefakte mit λ ≈ 0) übersprungen werden können und
        der erste echte Strukturmode gefunden wird.
        """
        K = structure.assemble_K()
        M = assemble_M(structure, self.node_mass)
        fixed = structure.fixed_dofs()

        # solve_eigenvalue filtert Mechanismus-Moden intern heraus;
        # eigenvalues[0] ist der erste echte Strukturmode.
        eigenvalues, eigenvectors = solve_eigenvalue(K, M, fixed, n_modes=6)

        omega_1 = float(np.sqrt(max(0.0, float(eigenvalues[0]))))
        eigvec_1 = eigenvectors[:, 0]
        return omega_1, eigvec_1

    def _compute_dynamic_importance(self, structure: Structure, eigvec_1: np.ndarray) -> np.ndarray:
        """Rayleigh-basierte Knotenwichtigkeit aus dem ersten Eigenmode.

        importance[i] = (û₁[dof_x_i]² + û₁[dof_y_i]²) * m_i
        wobei m_i die physikalische Knotenmasse ist (falls Material gesetzt),
        andernfalls self.node_mass. Inaktive Knoten erhalten den Wert 0.
        """
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

    def _combined_score(
        self,
        static_imp: np.ndarray,
        dynamic_imp: np.ndarray,
    ) -> np.ndarray:
        """Rang-normierter gewichteter Score aus statischer und dynamischer Wichtigkeit.

        Verwendet Rangperzentile statt Max-Normierung, sodass beide Kriterien
        unabhängig von ihrer Größenordnung gleich stark diskriminieren.

        score[i] = (1 - alpha) * statisch_rang[i] + alpha * dynamisch_rang[i]
        Niedriger Score → weniger wichtig → Kandidat zur Entfernung.
        """
        n = len(static_imp)
        if n == 0:
            return np.zeros(0)
        denom = max(n - 1, 1)
        static_rank  = np.argsort(np.argsort(static_imp)).astype(float)  / denom
        dynamic_rank = np.argsort(np.argsort(dynamic_imp)).astype(float) / denom
        return (1.0 - self.alpha) * static_rank + self.alpha * dynamic_rank

    # Kandidatenauswahl (analog zum EnergyBasedOptimizer)

    def _select_candidates(
        self,
        structure: Structure,
        score: np.ndarray,
        effective_fraction: float,
        blacklist: set[int] | None = None,
    ) -> list[int]:
        active_ids = [n.id for n in structure.nodes if n.active]
        if not active_ids:
            return []

        target_remove = max(1, int(len(active_ids) * effective_fraction))
        protected = set(structure.protected_node_ids())
        if blacklist:
            protected |= blacklist
        removable = [i for i in active_ids if i not in protected]
        if not removable:
            return []

        removable_sorted = sorted(removable, key=lambda i: score[i])

        if self.enforce_symmetry:
            return self._select_symmetric(structure, removable_sorted, target_remove)
        return self._select_greedy(structure, removable_sorted, target_remove)

    def _select_greedy(
        self,
        structure: Structure,
        removable_sorted: list[int],
        target_remove: int,
    ) -> list[int]:
        selected: list[int] = []
        exclude: set[int] = set()

        for nid in removable_sorted:
            if len(selected) >= target_remove:
                break
            trial = exclude | {nid}
            if structure.is_valid_topology(exclude_nodes=trial):
                selected.append(nid)
                exclude = trial

        return selected

    def _select_symmetric(
        self,
        structure: Structure,
        removable_sorted: list[int],
        target_remove: int,
    ) -> list[int]:
        selected: list[int] = []
        exclude: set[int] = set()
        processed: set[int] = set()

        for nid in removable_sorted:
            if len(selected) >= target_remove:
                break
            if nid in processed:
                continue

            if self._is_on_symmetry_line(nid):
                trial = exclude | {nid}
                if structure.is_valid_topology(exclude_nodes=trial):
                    selected.append(nid)
                    exclude = trial
                    processed.add(nid)
            else:
                mirror_id = self._get_mirror_node(nid)
                if mirror_id in removable_sorted and mirror_id not in exclude and mirror_id not in processed:
                    trial = exclude | {nid, mirror_id}
                    if structure.is_valid_topology(exclude_nodes=trial):
                        selected.extend([nid, mirror_id])
                        exclude = trial
                        processed.update([nid, mirror_id])

        return selected

    def _deactivate_nodes(self, structure: Structure, node_ids: list[int]) -> None:
        to_remove = set(node_ids)
        for nid in to_remove:
            structure.nodes[nid].active = False
        for spring in structure.springs:
            if spring.node_i in to_remove or spring.node_j in to_remove:
                spring.active = False

    def _reactivate_nodes(self, structure: Structure, node_ids: list[int]) -> None:
        to_restore = set(node_ids)
        for node_id in to_restore:
            structure.nodes[node_id].active = True
        for spring in structure.springs:
            ni = spring.node_i
            nj = spring.node_j
            if (ni in to_restore or structure.nodes[ni].active) and \
               (nj in to_restore or structure.nodes[nj].active):
                spring.active = True

    def _solve_structure(self, structure: Structure) -> np.ndarray | None:
        K = structure.assemble_K()
        F = structure.assemble_F()
        fixed = structure.fixed_dofs()
        return solve(K, F, fixed)

    # Öffentliche Schnittstelle

    def step(self, structure: Structure) -> np.ndarray:
        """Führt eine Optimierungsiteration durch. Gibt den kombinierten Score zurück."""
        _, eigvec_1 = self._assemble_and_solve_eigen(structure)
        n = len(structure.nodes)
        static_imp  = self._compute_static_importance(structure) if self.alpha < 1.0 else np.zeros(n)
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

        if force:
            # Erzwungener Modus: alle FEM-Sicherheitschecks deaktiviert
            for iter_idx in range(max_iters):
                structure.remove_removable_nodes()
                history.mass_fraction.append(structure.current_mass_fraction())
                if structure.current_mass_fraction() <= target_mass_fraction:
                    break
                try:
                    omega_1, eigvec_1 = self._assemble_and_solve_eigen(structure)
                except Exception:
                    break
                history.omega_1.append(omega_1)
                history.f_1.append(omega_1 / (2.0 * np.pi))
                history.freq_distance.append(abs(omega_1 - self.omega_excitation))
                n = len(structure.nodes)
                u = self._solve_structure(structure)
                static_imp = structure.node_importance_from_energy(u) if u is not None and self.alpha < 1.0 else np.zeros(n)
                dynamic_imp = self._compute_dynamic_importance(structure, eigvec_1) if self.alpha > 0.0 else np.zeros(n)
                score = self._combined_score(static_imp, dynamic_imp)
                candidates = self._select_candidates(structure, score, self.remove_fraction)
                if not candidates:
                    break
                self._deactivate_nodes(structure, candidates)
                history.removed_per_iter.append(len(candidates))
                if on_iter is not None:
                    on_iter(structure, iter_idx, omega_1, len(candidates))
            return history

        blacklist: set[int] = set()

        for iter_idx in range(max_iters):
            # 1. Nutzlose Knoten entfernen (Inseln / Sackgassen)
            removed_set = structure._find_removable_nodes()
            if removed_set:
                structure.remove_removable_nodes()

            # 2. Zielmasse erreicht?
            history.mass_fraction.append(structure.current_mass_fraction())
            if structure.current_mass_fraction() <= target_mass_fraction:
                break

            # 3. Statischer Solver — Abbruch bei singulärer Matrix
            u = self._solve_structure(structure)
            if u is None:
                if removed_set:
                    self._reactivate_nodes(structure, list(removed_set))
                    u = self._solve_structure(structure)
                if u is None:
                    break

            # 4. Eigenwertproblem — Abbruch bei Fehler
            try:
                omega_1, eigvec_1 = self._assemble_and_solve_eigen(structure)
            except Exception:
                break
            history.omega_1.append(omega_1)
            history.f_1.append(omega_1 / (2.0 * np.pi))
            history.freq_distance.append(abs(omega_1 - self.omega_excitation))

            # 5. Kombinierter Wichtigkeitsscore
            n = len(structure.nodes)
            static_imp  = structure.node_importance_from_energy(u) if self.alpha < 1.0 else np.zeros(n)
            dynamic_imp = self._compute_dynamic_importance(structure, eigvec_1) if self.alpha > 0.0 else np.zeros(n)
            score = self._combined_score(static_imp, dynamic_imp)

            # 6. Kandidaten auswählen (mit Blacklist)
            candidates = self._select_candidates(structure, score, self.remove_fraction, blacklist)
            if not candidates:
                break

            # 7. Alle Kandidaten auf einmal entfernen — check ob noch lösbar
            self._deactivate_nodes(structure, candidates)
            u_check = self._solve_structure(structure)

            if u_check is not None:
                history.removed_per_iter.append(len(candidates))
                if on_iter is not None:
                    on_iter(structure, iter_idx, omega_1, len(candidates))
                continue

            # 8. Batch fehlgeschlagen — einzeln versuchen
            self._reactivate_nodes(structure, candidates)
            actually_removed: list[int] = []
            for nid in candidates:
                self._deactivate_nodes(structure, [nid])
                u_single = self._solve_structure(structure)
                if u_single is None:
                    self._reactivate_nodes(structure, [nid])
                    blacklist.add(nid)
                else:
                    actually_removed.append(nid)

            if not actually_removed:
                break

            history.removed_per_iter.append(len(actually_removed))
            if on_iter is not None:
                on_iter(structure, iter_idx, omega_1, len(actually_removed))

        return history