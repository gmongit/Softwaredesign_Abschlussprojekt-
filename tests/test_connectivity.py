from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure
from core.optimization.connectivity_check import (
    is_structure_connected,
    do_loads_reach_supports,
    is_valid_topology,
)


def test_connected_structure_is_true():
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

    assert is_structure_connected(s) is True
    assert do_loads_reach_supports(s) is True
    assert is_valid_topology(s) is True


def test_disconnected_structure_is_false():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 10.0, 0.0, fx=10.0),
        Node(3, 11.0, 0.0),
    ]
    springs = [
        Spring(0, 1, 100.0),  # Komponente A
        Spring(2, 3, 100.0),  # Komponente B
    ]
    s = Structure(nodes, springs)

    assert is_structure_connected(s) is False
    assert is_valid_topology(s) is False


def test_load_not_reaching_support_is_false():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 10.0, 0.0, fx=10.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        # Node 2 hat Last, ist aber isoliert -> darf nicht
    ]
    s = Structure(nodes, springs)

    assert is_structure_connected(s) is False
    assert do_loads_reach_supports(s) is False
    assert is_valid_topology(s) is False


def test_exclude_nodes_allows_checking_candidate_removal():
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

    # Wenn man Node 1 entfernt, werden 0 und 2 getrennt -> ungültig
    assert is_valid_topology(s, exclude_nodes={1}) is False
