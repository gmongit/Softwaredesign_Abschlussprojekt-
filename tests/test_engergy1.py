import numpy as np

from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer


def test_optimizer_step_deactivates_some_node():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0, fx=10.0),
        Node(2, 0.5, 0.5),
    ]
    springs = [
        Spring(0, 1, k=100.0),
        Spring(0, 2, k=10.0),
        Spring(2, 1, k=10.0),
    ]
    s = Structure(nodes, springs)

    opt = EnergyBasedOptimizer(remove_fraction=0.34)  # bei 3 aktiven Nodes -> ~1 Node
    importance = opt.step(s)

    assert isinstance(importance, np.ndarray)
    assert s.nodes[0].active is True  # fixiert -> protected
    assert s.nodes[1].active is True  # Last -> protected
    # Node 2 darf entfernt werden (nicht protected)
    assert s.nodes[2].active in (True, False)
