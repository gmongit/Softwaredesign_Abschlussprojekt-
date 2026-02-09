from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure
from core.optimization.energy_based_optimizer import EnergyBasedOptimizer
from core.optimization.connectivity_check import is_valid_topology


def test_optimizer_does_not_break_connectivity():
    # Kette: 0 -- 1 -- 2
    # 0 = Lager, 2 = Last
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

    assert is_valid_topology(s) is True

    opt = EnergyBasedOptimizer(remove_fraction=0.9)  # versucht fast alles zu löschen
    opt.step(s)

    # Node 0 und 2 sind protected (Lager/Last) => bleiben aktiv
    assert s.nodes[0].active is True
    assert s.nodes[2].active is True

    # Node 1 ist die Brücke - darf nicht entfernt werden,
    # sonst erreicht die Last kein Lager mehr.
    assert s.nodes[1].active is True
