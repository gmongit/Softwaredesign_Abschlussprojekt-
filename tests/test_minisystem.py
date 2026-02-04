import numpy as np

from core.model.node import Node
from core.model.spring import Spring
from core.model.structure import Structure
from core.solver.solver import solve


def test_two_nodes_one_diagonal_spring_force_along_spring():
    n0 = Node(id=0, x=0.0, y=0.0, fix_x=True, fix_y=True)
    n1 = Node(id=1, x=1.0, y=1.0)

    k = 100.0
    F_parallel = 10.0

    # Kraft entlang der Federachse (1,1) normiert
    ex = 1.0 / np.sqrt(2.0)
    ey = 1.0 / np.sqrt(2.0)
    n1.fx = F_parallel * ex
    n1.fy = F_parallel * ey

    spring = Spring(node_i=0, node_j=1, k=k)
    s = Structure(nodes=[n0, n1], springs=[spring])

    K = s.assemble_K()
    F = s.assemble_F()
    fixed = s.fixed_dofs()

    u = solve(K, F, fixed)

    # Erwartete Verschiebung: u_parallel = F_parallel / k
    u_parallel = F_parallel / k
    expected = u_parallel / np.sqrt(2.0)

    assert np.isclose(u[n1.dof_x], expected, atol=1e-8)
    assert np.isclose(u[n1.dof_y], expected, atol=1e-8)

    assert np.isclose(u[n0.dof_x], 0.0, atol=1e-8)
    assert np.isclose(u[n0.dof_y], 0.0, atol=1e-8)

def test_two_nodes_one_horizontal_spring():
    # Node 0: fest eingespannt
    n0 = Node(id=0, x=0.0, y=0.0, fix_x=True, fix_y=True)

    # Node 1: Feder rechts davon, Kraft in x-Richtung
    n1 = Node(id=1, x=1.0, y=0.0, fx=10.0)

    # Horizontale Feder mit k=100
    spring = Spring(node_i=0, node_j=1, k=100.0)

    s = Structure(nodes=[n0, n1], springs=[spring])

    K = s.assemble_K()
    F = s.assemble_F()
    fixed = s.fixed_dofs()

    u = solve(K, F, fixed)

    # Erwartung:
    # nur u1x ist frei, und bei 1D-Feder gilt u = F/k = 10/100 = 0.1
    assert np.isclose(u[n1.dof_x], 0.1, atol=1e-8)
    assert np.isclose(u[n1.dof_y], 0.0, atol=1e-8)
    assert np.isclose(u[n0.dof_x], 0.0, atol=1e-8)
    assert np.isclose(u[n0.dof_y], 0.0, atol=1e-8)
