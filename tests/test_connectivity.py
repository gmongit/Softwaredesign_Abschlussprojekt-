from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure


def test_valid_topology_is_true():
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


def test_invalid_topology_disconnected():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 10.0, 0.0, fx=10.0),
        Node(3, 11.0, 0.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        Spring(2, 3, 100.0),
    ]
    s = Structure(nodes, springs)

    assert s.is_valid_topology() is False


def test_invalid_topology_load_not_reaching_support():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 10.0, 0.0, fx=10.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
    ]
    s = Structure(nodes, springs)

    assert s.is_valid_topology() is False


def test_invalid_topology_exclude_bridge_node():
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

    assert s.is_valid_topology(exclude_nodes={1}) is False


def test_remove_removable_isolated_island():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0, fx=10.0),
        Node(2, 5.0, 0.0),
        Node(3, 6.0, 0.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        Spring(2, 3, 100.0),
    ]
    s = Structure(nodes, springs)
    s._register_special_nodes()

    count = s.remove_removable_nodes()
    assert count == 2
    assert s.nodes[2].active is False
    assert s.nodes[3].active is False
    assert s.nodes[0].active is True
    assert s.nodes[1].active is True


def test_remove_removable_dead_end_chain():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 2.0, 0.0),
        Node(3, 3.0, 0.0, fx=10.0),
        Node(4, 4.0, 0.0),
        Node(5, 5.0, 0.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        Spring(1, 2, 100.0),
        Spring(2, 3, 100.0),
        Spring(3, 4, 100.0),
        Spring(4, 5, 100.0),
    ]
    s = Structure(nodes, springs)
    s._register_special_nodes()

    count = s.remove_removable_nodes()
    assert count == 2
    assert s.nodes[4].active is False
    assert s.nodes[5].active is False
    assert s.nodes[0].active is True
    assert s.nodes[3].active is True


def test_remove_removable_protected_nodes_never_removed():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0, fx=10.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
    ]
    s = Structure(nodes, springs)
    s._register_special_nodes()

    count = s.remove_removable_nodes()
    assert count == 0
    assert s.nodes[0].active is True
    assert s.nodes[1].active is True


def test_remove_removable_component_without_support():
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0, fx=5.0),
        Node(2, 5.0, 0.0, fx=10.0),
        Node(3, 6.0, 0.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        Spring(2, 3, 100.0),
    ]
    s = Structure(nodes, springs)
    s._register_special_nodes()

    count = s.remove_removable_nodes()
    assert count == 2
    assert s.nodes[2].active is False
    assert s.nodes[3].active is False


# ── Tests mit Material (density + beam_area) ─────────────────────────────────
# Eigengewicht wird in assemble_F() dynamisch berechnet und ist NICHT in
# node.fy gespeichert → darf _find_removable_nodes nicht beeinflussen.

def test_remove_removable_isolated_island_with_material():
    """Insel ohne Verbindung zu Lager & Last wird entfernt, auch wenn Material gesetzt ist.

    Topologie:
        Lager(0) -- Knoten(1) -- Last(2)      [Hauptstruktur]
        Insel(3) -- Insel(4)                  [keine Verbindung]
    """
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 2.0, 0.0, fy=-10.0),
        Node(3, 5.0, 0.0),
        Node(4, 6.0, 0.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        Spring(1, 2, 100.0),
        Spring(3, 4, 100.0),
    ]
    s = Structure(nodes, springs)
    s.density = 7850.0
    s.beam_area = 0.01
    s._register_special_nodes()

    count = s.remove_removable_nodes()

    assert count == 2
    assert s.nodes[3].active is False
    assert s.nodes[4].active is False
    assert s.nodes[0].active is True
    assert s.nodes[1].active is True
    assert s.nodes[2].active is True


def test_remove_removable_dead_end_single_connection_with_material():
    """Sackgasse mit genau einer Verbindung zur Hauptstruktur wird entfernt,
    auch wenn Material gesetzt ist.

    Topologie:
        Lager(0) -- Knoten(1) -- Last(2)      [Hauptstruktur]
                        |
                     Knoten(3) -- Knoten(4)   [Sackgasse, hängt an Knoten 1]
    """
    nodes = [
        Node(0, 0.0, 0.0, fix_x=True, fix_y=True),
        Node(1, 1.0, 0.0),
        Node(2, 2.0, 0.0, fy=-10.0),
        Node(3, 1.0, 1.0),
        Node(4, 1.0, 2.0),
    ]
    springs = [
        Spring(0, 1, 100.0),
        Spring(1, 2, 100.0),
        Spring(1, 3, 100.0),
        Spring(3, 4, 100.0),
    ]
    s = Structure(nodes, springs)
    s.density = 7850.0
    s.beam_area = 0.01
    s._register_special_nodes()

    count = s.remove_removable_nodes()

    assert count == 2
    assert s.nodes[3].active is False
    assert s.nodes[4].active is False
    assert s.nodes[0].active is True
    assert s.nodes[1].active is True
    assert s.nodes[2].active is True
