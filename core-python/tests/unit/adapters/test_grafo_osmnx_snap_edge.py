"""Tests de snap-to-edge en el adapter (`OsmnxGrafoVial.posicion_en_arista`).

ADR-0020 §H5-cal-3a. Usa grafos `nx.MultiDiGraph` sintéticos minúsculos: sin
descargas de red ni GraphML real. Verifica que la proyección use la geometría
curva cuando existe, respete el bbox (RN-01) y elija la arista más cercana.
"""

from __future__ import annotations

import networkx as nx
import pytest
from shapely.geometry import LineString

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial
from sentinel_dispatch.domain.routing.tipos import NodoFueraDeRangoError


def _grafo_recto() -> nx.MultiDiGraph:
    """Dos aristas rectas (sin geometry): 1→2 (este) y 2→3 (sur)."""
    g = nx.MultiDiGraph()
    g.add_node(1, y=-29.9000, x=-71.2500)
    g.add_node(2, y=-29.9000, x=-71.2400)
    g.add_node(3, y=-29.9100, x=-71.2400)
    g.add_edge(1, 2, length=965.0, speed_kph=50.0)
    g.add_edge(2, 3, length=1113.0, speed_kph=50.0)
    return g


def _grafo_curvo() -> nx.MultiDiGraph:
    """Arista 1→2 con geometry en 'V' que baja al sur en el punto medio."""
    g = nx.MultiDiGraph()
    g.add_node(1, y=-29.9000, x=-71.2500)
    g.add_node(2, y=-29.9000, x=-71.2400)
    g.add_node(3, y=-29.9100, x=-71.2400)
    # LineString en orden OSMnx (lon, lat): vértice medio desviado al sur.
    geom = LineString(
        [(-71.2500, -29.9000), (-71.2450, -29.9030), (-71.2400, -29.9000)]
    )
    g.add_edge(1, 2, length=970.0, speed_kph=50.0, geometry=geom)
    g.add_edge(2, 3, length=1113.0, speed_kph=50.0)
    return g


def test_posicion_en_arista_segmento_recto() -> None:
    adapter = OsmnxGrafoVial(grafo=_grafo_recto())
    pos = adapter.posicion_en_arista(-29.9010, -71.2450)
    assert pos.arista.origen == 1
    assert pos.arista.destino == 2
    assert pos.fraccion == pytest.approx(0.5, abs=0.05)
    assert pos.distancia_snap_m < 150.0
    assert pos.arista.longitud_m == 965.0
    assert pos.arista.velocidad_efectiva_kmh == 50.0


def test_posicion_en_arista_usa_geometria_curva() -> None:
    adapter = OsmnxGrafoVial(grafo=_grafo_curvo())
    # El punto coincide con el vértice desviado de la 'V'. Con la geometría
    # curva la distancia de snap es casi nula; con el segmento recto sería
    # ~330 m (Δlat 0.0030°). Eso distingue inequívocamente que usa la curva.
    pos = adapter.posicion_en_arista(-29.9030, -71.2450)
    assert pos.arista.origen == 1
    assert pos.arista.destino == 2
    assert pos.lat == pytest.approx(-29.9030, abs=1e-3)
    assert pos.distancia_snap_m < 20.0
    assert pos.fraccion == pytest.approx(0.5, abs=0.05)


def test_posicion_en_arista_rechaza_fuera_de_bbox() -> None:
    adapter = OsmnxGrafoVial(grafo=_grafo_recto())
    with pytest.raises(NodoFueraDeRangoError):
        adapter.posicion_en_arista(0.0, 0.0)


def test_posicion_en_arista_elige_la_mas_cercana() -> None:
    adapter = OsmnxGrafoVial(grafo=_grafo_recto())
    # Punto pegado a la arista 2→3 (vertical): debe elegir esa, no 1→2.
    pos = adapter.posicion_en_arista(-29.9050, -71.2401)
    assert pos.arista.origen == 2
    assert pos.arista.destino == 3
    assert pos.distancia_snap_m < 150.0
