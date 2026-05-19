"""Fixtures comunes para tests del paquete `adapters`.

Construye `MultiDiGraph` sintéticos en memoria, con coordenadas dentro del
rango IV Región. Evita la dependencia de Overpass/OSMnx y mantiene los
tests rápidos y determinísticos.
"""

from __future__ import annotations

import networkx as nx
import pytest

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial


@pytest.fixture
def grafo_iv_region_sintetico() -> nx.MultiDiGraph:
    """Grafo mínimo con 4 nodos en la conurbación La Serena-Coquimbo.

    Coordenadas reales aproximadas:
        - Hospital San Juan de Dios La Serena: (-29.9077, -71.2535)
        - CESFAM Pedro Aguirre Cerda: (-29.9015, -71.2433)
        - Hospital San Pablo Coquimbo: (-29.9533, -71.3389)
        - CESFAM Tierras Blancas: (-29.9622, -71.3198)

    Dos aristas cortas (vecinas en La Serena, vecinas en Coquimbo) y dos
    aristas largas (cross-city). Suficiente para validar el snap, no
    pensado para A*.
    """
    grafo: nx.MultiDiGraph = nx.MultiDiGraph()
    grafo.add_node(1, y=-29.9077, x=-71.2535)  # La Serena Hospital
    grafo.add_node(2, y=-29.9015, x=-71.2433)  # La Serena CESFAM PAC
    grafo.add_node(3, y=-29.9533, x=-71.3389)  # Coquimbo Hospital
    grafo.add_node(4, y=-29.9622, x=-71.3198)  # Tierras Blancas
    grafo.add_edge(1, 2, length=1500.0, speed_kph=50.0)
    grafo.add_edge(2, 1, length=1500.0, speed_kph=50.0)
    grafo.add_edge(3, 4, length=2200.0, speed_kph=40.0)
    grafo.add_edge(4, 3, length=2200.0, speed_kph=40.0)
    return grafo


@pytest.fixture
def adapter_sintetico(grafo_iv_region_sintetico: nx.MultiDiGraph) -> OsmnxGrafoVial:
    """Adapter `OsmnxGrafoVial` sobre el grafo sintético del fixture anterior."""
    return OsmnxGrafoVial(grafo=grafo_iv_region_sintetico)


@pytest.fixture
def grafo_vacio() -> nx.MultiDiGraph:
    """Grafo sin nodos — caso degenerado para tests de error."""
    return nx.MultiDiGraph()
