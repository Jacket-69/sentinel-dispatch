"""Fixtures compartidas por los tests del módulo de routing."""

from __future__ import annotations

import pytest
from grafo_fake import GrafoFake


@pytest.fixture
def grafo_simple_5nodos() -> GrafoFake:
    """Grafo dirigido de 5 nodos en La Serena con redundancia de rutas.

    Topología (dirigida)::

        0 --500m/50-- 1 --700m/50-- 2
        |                 \\
        1000m/30         100m/30
        |                   \\
        3 --300m/50-- 4 --300m/50-- 2

    Rutas posibles 0→2:
      - Directa: 0→1→2 (500 + 700 = 1200 m, todo 50 km/h)
      - Larga: 0→3→4→2 (1000 + 300 + 300 = 1600 m, mixta)
      - Con atajo: 0→1→4→2 (500 + 100 + 300 = 900 m, mixta)
    """
    g = GrafoFake()

    # Nodos: coordenadas reales en área La Serena
    g.agregar_nodo(0, -29.9027, -71.2519)  # centro La Serena
    g.agregar_nodo(1, -29.9027, -71.2474)  # ~400 m al este
    g.agregar_nodo(2, -29.9027, -71.2412)  # ~950 m al este del origen
    g.agregar_nodo(3, -29.9117, -71.2519)  # ~1000 m al sur del origen
    g.agregar_nodo(4, -29.9117, -71.2474)  # ~400 m al este del nodo 3

    # Aristas con las propiedades especificadas
    g.agregar_arista(0, 1, 500.0, 50.0)
    g.agregar_arista(1, 2, 700.0, 50.0)
    g.agregar_arista(0, 3, 1000.0, 30.0)
    g.agregar_arista(3, 4, 300.0, 50.0)
    g.agregar_arista(4, 2, 300.0, 50.0)
    g.agregar_arista(1, 4, 100.0, 30.0)

    return g
