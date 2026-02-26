import numpy as np
from dataclasses import dataclass, field

from core.model.structure import Structure
from core.db.material_store import material_store
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer
from core.solver.solver import solve


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
        u = compute_displacement(structure)
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
    return opt.run(structure, target_mass_fraction=target_mass_fraction, max_iters=max_iters, on_iter=on_iter, force=force)


def optimize_structure(
    structure: Structure,
    material_name: str | None,
    beam_area_mm2: float,
    remove_fraction: float,
    target_mass_fraction: float,
    max_iters: int,
    on_iter=None,
    force: bool = False,
):
    """
    Führt den gesamten Optimierungsprozess durch:
    1. Vorbereitung (Material, Steifigkeiten)
    2. Optimierungsschleife (inkl. Symmetrie-Erkennung)
    """
    prepare_structure(structure, material_name, beam_area_mm2)
    return run_optimization(structure, remove_fraction, target_mass_fraction, max_iters, on_iter=on_iter, force=force)


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



def compute_displacement(structure: Structure) -> np.ndarray | None:
    """Löst das Gleichungssystem K·u = F. Gibt None bei singulärer Matrix zurück."""
    K = structure.assemble_K()
    F = structure.assemble_F()
    fixed = structure.fixed_dofs()
    return solve(K, F, fixed)


def compute_energies(structure: Structure) -> np.ndarray | None:
    """Berechnet Formänderungsenergie pro Feder. Gibt None bei singulärer Matrix zurück."""
    u = compute_displacement(structure)
    if u is None:
        return None
    return structure.spring_energies(u)


def compute_forces(structure: Structure) -> np.ndarray | None:
    """Berechnet Axialkraft pro Feder. Gibt None bei singulärer Matrix zurück."""
    u = compute_displacement(structure)
    if u is None:
        return None
    return structure.spring_forces(u)
