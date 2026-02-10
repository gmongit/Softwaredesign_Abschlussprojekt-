import numpy as np

from core.model.node import Node
from core.model.spring import Spring


def test_energy_horizontal_spring_known_value():
    n0 = Node(id=0, x=0.0, y=0.0)
    n1 = Node(id=1, x=1.0, y=0.0)

    k = 100.0
    spring = Spring(0, 1, k=k)

    u = np.zeros(4, dtype=float)
    u[n1.dof_x] = 0.1  # delta entlang Feder = 0.1

    E = spring.strain_energy(n0, n1, u)
    assert np.isclose(E, 0.5 * k * (0.1 ** 2), atol=1e-12)
