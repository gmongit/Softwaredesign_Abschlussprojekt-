from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer


def test_optimizer_does_not_break_connectivity():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 2.0, 0.0, fx=10.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        Spring(1, 2, 100.0),
    ]
    s = Structure(nodes, springs)

    assert s.is_valid_topology() is True

    opt = EnergyBasedOptimizer(remove_fraction=0.9)
    opt.step(s)

    assert s.nodes[0].active is True
    assert s.nodes[2].active is True
    assert s.nodes[1].active is True
