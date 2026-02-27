from dataclasses import dataclass, field

from core.model.structure import Structure
from core.db.material_store import material_store
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer, OptimizationHistory
from core.optimization.dynamic_optimizer import DynamicOptimizer, DynamicOptimizationHistory
from core.optimization.simp_optimizer import SIMPOptimizer, SIMPHistory
from core.optimization.support_rebuilder import rebuild_support, RebuildResult, _deactivate_nodes

_TERMINAL_REASONS = {
    "Ziel-Massenanteil erreicht",
    "Max. Iterationen erreicht",
    "Streckgrenze erreicht",
    "Ausgangsspannung überschreitet bereits die Streckgrenze",
}


@dataclass
class StructureValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    removable_count: int = 0

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def validate_structure(structure: Structure) -> StructureValidation:
    """Prüft Topologie, Randbedingungen und Lösbarkeit. Ohne Seiteneffekte."""
    result = StructureValidation()
    structure._register_special_nodes()
    nodes = [n for n in structure.nodes if n.active]

    has_festlager = any(n.fix_x and n.fix_y for n in nodes)
    has_loslager = any(n.fix_y and not n.fix_x for n in nodes)
    has_last = any(abs(n.fx) > 0 or abs(n.fy) > 0 for n in nodes)

    if not has_festlager:
        result.errors.append("Kein Festlager vorhanden")
    if not has_loslager:
        result.errors.append("Kein Loslager vorhanden")
    if not has_last:
        result.errors.append("Keine Last vorhanden")

    if not structure.is_valid_topology():
        result.errors.append("Struktur nicht zusammenhängend oder Lastpfad unterbrochen")

    if result.ok:
        u = structure.compute_displacement()
        if u is None:
            result.errors.append("Struktur ist bereits singulär (nicht lösbar)")

    result.removable_count = len(structure._find_removable_nodes())
    if result.removable_count > 0:
        result.warnings.append(f"{result.removable_count} entfernbare Knoten (Inseln/Sackgassen)")

    return result


def prepare_structure(structure: Structure, material_name: str | None, beam_area_mm2: float) -> None:
    """
    Bereitet die Struktur für die Optimierung vor:
    lädt das Material aus DB, rechnet Einheiten um
    und setzt alle Federsteifigkeiten k = E * A / L.

    Raises:
        ValueError: Wenn kein Material ausgewählt wurde oder keines in der DB hinterlegt ist
    """
    if not material_store.list_materials():
        raise ValueError("Kein Material in der Datenbank hinterlegt.")
    if material_name is None:
        raise ValueError("Kein Material ausgewählt.")
    mat = material_store.load_material(material_name)
    e_pa = mat.e_modul * 1e9        # GPa → Pa
    area_m2 = beam_area_mm2 * 1e-6  # mm² → m²
    density = mat.dichte            # kg/m³
    structure.update_spring_stiffnesses(e_pa, area_m2, density)


def run_optimization(
    structure: Structure,
    remove_fraction: float,
    target_mass_fraction: float,
    max_iters: int,
    max_stress: float | None = None,
    on_iter=None,
    force: bool = False,
):
    """Startet die Topologie-Optimierung und gibt die History zurück."""

    _validate_boundary_conditions(structure)
    opt = EnergyBasedOptimizer(
        remove_fraction=remove_fraction,
        start_factor=0.3,
        ramp_iters=10,
    )
    return opt.run(
        structure,
        target_mass_fraction=target_mass_fraction,
        max_iters=max_iters,
        max_stress=max_stress,
        on_iter=on_iter,
        force=force,
    )


def optimize_structure(
    structure: Structure,
    material_name: str | None,
    beam_area_mm2: float,
    remove_fraction: float,
    target_mass_fraction: float,
    max_iters: int,
    max_stress: float | None = None,
    on_iter=None,
    force: bool = False,
):
    """
    Führt den gesamten Optimierungsprozess durch:
    1. Vorbereitung (Material, Steifigkeiten)
    2. Optimierungsschleife (inkl. Symmetrie-Erkennung)
    """
    prepare_structure(structure, material_name, beam_area_mm2)
    return run_optimization(
        structure, remove_fraction, target_mass_fraction, max_iters,
        max_stress=max_stress, on_iter=on_iter, force=force,
    )


def is_retryable(history) -> bool:
    return bool(history.stop_reason and history.stop_reason not in _TERMINAL_REASONS)


def continue_optimization(
    structure: Structure,
    history: OptimizationHistory,
    remove_fraction: float,
    target_mass_fraction: float,
    max_iters: int,
    max_stress: float | None = None,
    on_iter=None,
) -> None:
    """Setzt die Optimierung fort und merged die History."""
    hist_new = run_optimization(
        structure, remove_fraction, target_mass_fraction, max_iters,
        max_stress=max_stress, on_iter=on_iter,
    )
    history.mass_fraction.extend(hist_new.mass_fraction)
    history.removed_per_iter.extend(hist_new.removed_per_iter)
    history.removed_nodes_per_iter.extend(hist_new.removed_nodes_per_iter)
    history.max_displacement.extend(hist_new.max_displacement)
    history.stop_reason = hist_new.stop_reason


def run_dynamic_optimization(
    structure: Structure,
    omega_excitation: float,
    alpha: float,
    remove_fraction: float,
    target_mass_fraction: float,
    max_iters: int,
    max_stress: float | None = None,
    on_iter=None,
    force: bool = False,
) -> DynamicOptimizationHistory:
    """Startet die dynamische Topologie-Optimierung und gibt die History zurück."""
    _validate_boundary_conditions(structure)
    opt = DynamicOptimizer(
        omega_excitation=omega_excitation,
        alpha=alpha,
        remove_fraction=remove_fraction,
    )
    return opt.run(
        structure,
        target_mass_fraction=target_mass_fraction,
        max_iters=max_iters,
        max_stress=max_stress,
        on_iter=on_iter,
        force=force,
    )


def continue_dynamic_optimization(
    structure: Structure,
    history: DynamicOptimizationHistory,
    omega_excitation: float,
    alpha: float,
    remove_fraction: float,
    target_mass_fraction: float,
    max_iters: int,
    max_stress: float | None = None,
    on_iter=None,
) -> None:
    """Setzt die dynamische Optimierung fort und merged die History."""
    hist_new = run_dynamic_optimization(
        structure, omega_excitation, alpha,
        remove_fraction, target_mass_fraction, max_iters,
        max_stress=max_stress, on_iter=on_iter,
    )
    history.mass_fraction.extend(hist_new.mass_fraction)
    history.removed_per_iter.extend(hist_new.removed_per_iter)
    history.omega_1.extend(hist_new.omega_1)
    history.f_1.extend(hist_new.f_1)
    history.freq_distance.extend(hist_new.freq_distance)
    history.stop_reason = hist_new.stop_reason


def _validate_boundary_conditions(structure: Structure):
    nodes = [n for n in structure.nodes if n.active]

    checks = {
        "Festlager": any(n.fix_x and n.fix_y for n in nodes),
        "Loslager":  any(n.fix_y and not n.fix_x for n in nodes),
        "Last":     any(abs(n.fx) > 0 or abs(n.fy) > 0 for n in nodes)
    }

    missing = [name for name, found in checks.items() if not found]
    if missing:
        raise ValueError(f"Fehlend: {', '.join(missing)}")

    if not structure.is_valid_topology():
        raise ValueError("Struktur ist nicht zusammenhängend oder Lastpfad zu Lager unterbrochen.")


def run_rebuild_support(structure: Structure, **kwargs) -> RebuildResult:
    """Nachverstärkung: reaktiviert Knoten zur Stress-Reduktion."""
    return rebuild_support(structure, **kwargs)


def undo_rebuild(structure: Structure, result: RebuildResult) -> None:
    """Macht die Nachverstärkung rückgängig."""
    if result.reactivated_node_ids:
        _deactivate_nodes(structure, result.reactivated_node_ids)


def run_simp_optimization(
    structure: Structure,
    material_name: str | None,
    beam_area_mm2: float,
    volume_fraction: float = 0.5,
    penalty: float = 3.0,
    max_iters: int = 100,
    eta: float = 0.5,
    move_limit: float = 0.2,
    tol: float = 1e-3,
    on_iter=None,
) -> SIMPHistory:
    _validate_boundary_conditions(structure)

    if not material_store.list_materials():
        raise ValueError("Kein Material in der Datenbank hinterlegt.")
    if material_name is None:
        raise ValueError("Kein Material ausgewählt.")
    mat = material_store.load_material(material_name)

    e_pa = mat.e_modul * 1e9
    area_m2 = beam_area_mm2 * 1e-6
    density = mat.dichte

    structure.update_spring_stiffnesses(e_pa, area_m2, density)

    opt = SIMPOptimizer(
        e_modul_pa=e_pa,
        a_min=area_m2 * 1e-6,
        a_max=area_m2,
        volume_fraction=volume_fraction,
        penalty=penalty,
        eta=eta,
        move_limit=move_limit,
        tol=tol,
    )

    hist = opt.run(structure, max_iters=max_iters, on_iter=on_iter)
    opt.post_process(structure, threshold_fraction=0.01)

    return hist