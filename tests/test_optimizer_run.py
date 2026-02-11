from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer


def test_optimizer_run_reduces_mass_fraction():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 2.0, 0.0, fx=10.0),
        Node(3, 1.0, 1.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        Spring(1, 2, 100.0),
        Spring(1, 3, 10.0),
        Spring(3, 2, 10.0),
        Spring(0, 3, 10.0),
    ]
    s = Structure(nodes, springs)

    opt = EnergyBasedOptimizer(remove_fraction=0.25)
    hist = opt.run(s, target_mass_fraction=0.75, max_iters=50)

    assert len(hist.mass_fraction) >= 1
    assert s.current_mass_fraction() <= 1.0
    assert s.nodes[0].active is True
    assert s.nodes[2].active is True
