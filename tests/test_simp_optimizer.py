import numpy as np
import pytest
from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure
from core.optimization.simp_optimizer import SIMPOptimizer, SIMPHistory
from core.db.case_store import case_store
from core.db.material_store import material_store


@pytest.fixture
def standard_model():
    """Load standard model from database."""
    struct, _ = case_store.load_case("Standarttest")
    return struct


@pytest.fixture
def steel_material():
    """Load steel material from database."""
    materials = material_store.list_materials()
    for m in materials:
        if 'Stahl' in m.name or 'Steel' in m.name or 'stahl' in m.name.lower():
            return m
    return materials[0] if materials else None


def create_simple_two_node():
    """Simple 2-node horizontal spring for testing."""
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0, fx=10.0),
    ]
    springs = [Spring(0, 1, k=100.0, area=1e-4)]
    return Structure(nodes, springs)


def test_simp_area_field():
    """Test that Spring.area field exists and defaults correctly."""
    s = Spring(0, 1, k=100.0, area=1e-4)
    assert s.area == 1e-4

    s2 = Spring(0, 1, k=100.0)
    assert s2.area == 0.0


def test_structure_update_spring_stiffnesses_sets_area():
    """Test that update_spring_stiffnesses sets spring.area."""
    struct = create_simple_two_node()
    E = 210e9
    A = 1e-4

    struct.update_spring_stiffnesses(E, A, density=0.0)

    for spring in struct.springs:
        assert spring.area == A


def test_update_spring_stiffnesses_from_areas():
    """Test that k is recomputed from areas: k = E*A/L."""
    struct = create_simple_two_node()
    E = 210e9
    A_init = 1e-4
    struct.update_spring_stiffnesses(E, A_init, density=0.0)

    k_init = struct.springs[0].k
    struct.springs[0].area = 2e-4
    struct.update_spring_stiffnesses_from_areas(E)
    k_new = struct.springs[0].k

    assert k_new == pytest.approx(2.0 * k_init)


def test_total_volume_from_areas():
    """Test volume calculation: Σ(A_e * L_e)."""
    struct = create_simple_two_node()
    E = 210e9
    A = 1e-4
    struct.update_spring_stiffnesses(E, A, density=0.0)

    vol = struct.total_volume_from_areas()
    expected = A * 1.0

    assert vol == pytest.approx(expected)


def test_simp_optimizer_initialization():
    """Test SIMPOptimizer initialization."""
    opt = SIMPOptimizer(
        e_modul_pa=210e9,
        a_min=1e-9,
        a_max=1e-4,
        volume_fraction=0.5,
        penalty=3.0,
        eta=0.5,
        move_limit=0.2,
        tol=1e-3,
    )

    assert opt.penalty == 3.0
    assert opt.volume_fraction == 0.5
    assert opt.eta == 0.5
    assert opt.a_min == 1e-9


def test_simp_compute_sensitivities():
    """Test that sensitivities have correct shape and are finite."""
    struct = create_simple_two_node()
    E = 210e9
    A = 1e-4
    struct.update_spring_stiffnesses(E, A, density=0.0)

    u = struct.compute_displacement()
    assert u is not None

    opt = SIMPOptimizer(e_modul_pa=E, a_max=A)
    areas = np.array([sp.area for sp in struct.springs])
    dc = opt._compute_sensitivities(struct, u, areas)

    assert dc.shape == (len(struct.springs),)
    assert np.all(np.isfinite(dc))


def test_simp_penalty_no_penalty():
    """Test SIMP penalty with p=1.0 (no penalization)."""
    struct = create_simple_two_node()
    E = 210e9
    A = 1e-4
    struct.update_spring_stiffnesses(E, A, density=0.0)

    k_before = struct.springs[0].k

    opt = SIMPOptimizer(e_modul_pa=E, a_max=A, penalty=1.0)
    areas = np.array([A])
    opt._apply_simp_penalty(struct, areas)

    assert struct.springs[0].k == k_before


def test_simp_penalty_with_penalization():
    """Test SIMP penalty with p=3.0."""
    struct = create_simple_two_node()
    E = 210e9
    A = 1e-4
    struct.update_spring_stiffnesses(E, A, density=0.0)

    k_init = struct.springs[0].k

    opt = SIMPOptimizer(e_modul_pa=E, a_max=A, penalty=3.0)
    areas = np.array([A / 2])
    opt._apply_simp_penalty(struct, areas)

    k_penalized = struct.springs[0].k
    rho = 0.5
    expected = (rho ** 3.0) * k_init

    assert k_penalized == pytest.approx(expected)


def test_simp_oc_update_bounds():
    """Test that OC update respects bounds."""
    struct = create_simple_two_node()
    E = 210e9
    A = 1e-4
    a_min = 1e-9

    struct.update_spring_stiffnesses(E, A, density=0.0)

    opt = SIMPOptimizer(
        e_modul_pa=E,
        a_min=a_min,
        a_max=A,
        volume_fraction=0.5,
    )

    areas = np.array([A])
    dc = np.array([-1.0])
    areas_new = opt._oc_update(struct, areas, dc)

    assert areas_new[0] >= a_min * 0.99
    assert areas_new[0] <= A * 1.01


def test_simp_oc_update_shape():
    """Test OC update returns correct number of areas."""
    struct = create_simple_two_node()
    E = 210e9
    A = 1e-4
    struct.update_spring_stiffnesses(E, A, density=0.0)

    opt = SIMPOptimizer(e_modul_pa=E, a_max=A)
    areas = np.array([A])
    dc = np.array([-1.0])
    areas_new = opt._oc_update(struct, areas, dc)

    assert len(areas_new) == 1


def test_simp_history_dataclass():
    """Test SIMPHistory initialization."""
    hist = SIMPHistory()

    assert hist.compliance == []
    assert hist.volume_fraction == []
    assert hist.area_change == []
    assert hist.stop_reason == ""


def test_simp_run_completes(standard_model, steel_material):
    """Test that run() handles solvable structures."""
    if steel_material is None:
        pytest.skip("No steel material found")

    struct = standard_model
    E_pa = steel_material.e_modul * 1e9

    struct.update_spring_stiffnesses(E_pa, 1e-4, density=0.0)

    opt = SIMPOptimizer(
        e_modul_pa=E_pa,
        a_min=1e-9,
        a_max=1e-4,
        volume_fraction=0.5,
        penalty=1.0,
        eta=0.5,
        move_limit=0.3,
        tol=1e-3,
    )

    hist = opt.run(struct, max_iters=3)

    if "singular" in hist.stop_reason.lower():
        pytest.skip(f"Structure is singular: {hist.stop_reason}")

    assert len(hist.compliance) >= 1
    assert len(hist.volume_fraction) >= 1
    assert hist.stop_reason != ""


def test_simp_post_process_removes_thin(standard_model):
    """Test post_process removes bars below threshold."""
    struct = standard_model
    E = 210e9
    A = 1e-4

    struct.update_spring_stiffnesses(E, A, density=0.0)

    for s in struct.springs[:10]:
        s.area = 1e-10

    opt = SIMPOptimizer(e_modul_pa=E, a_max=A)
    removed = opt.post_process(struct, threshold_fraction=0.01)

    assert removed >= 1


def test_simp_post_process_preserves_thick(standard_model):
    """Test post_process keeps thick bars."""
    struct = standard_model
    E = 210e9
    A = 1e-4

    struct.update_spring_stiffnesses(E, A, density=0.0)

    thick_count = sum(1 for s in struct.springs if s.area >= A * 0.5)

    opt = SIMPOptimizer(e_modul_pa=E, a_max=A)
    opt.post_process(struct, threshold_fraction=0.01)

    kept_count = sum(1 for s in struct.springs if s.active and s.area >= A * 0.5)

    assert kept_count >= thick_count * 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])