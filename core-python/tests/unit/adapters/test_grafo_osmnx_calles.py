"""Tests de `OsmnxGrafoVial.calles_principales`.

Verifica el filtrado por tipo de vía (vías principales vs. locales),
el manejo de `highway` como lista, y la deduplicación de segmentos
bidireccionales.
"""

from __future__ import annotations

import networkx as nx

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial


def _grafo_calles() -> nx.MultiDiGraph:
    """Grafo sintético con 5 nodos y aristas de distinto tipo de vía.

    Topología:
        1 ↔ 2   primary          (par bidireccional → debe deduplicar)
        2 → 3   secondary
        3 → 4   residential      (debe quedar EXCLUIDA)
        4 → 5   motorway_link
        1 → 5   ["primary", "residential"]  (lista; primary está → incluida)

    Nodo 5 no tiene coordenadas (caso de error silencioso cuando se usa
    en aristas que SÍ deberían pasar el filtro de highway — testeado por
    separado en `test_nodo_sin_coords_se_omite`). Para el resto de tests
    el nodo 5 tiene coordenadas.
    """
    g = nx.MultiDiGraph()
    g.add_node(1, y=-29.9000, x=-71.2500)
    g.add_node(2, y=-29.9010, x=-71.2400)
    g.add_node(3, y=-29.9020, x=-71.2300)
    g.add_node(4, y=-29.9030, x=-71.2200)
    g.add_node(5, y=-29.9040, x=-71.2100)
    # par bidireccional primary
    g.add_edge(1, 2, length=1000.0, speed_kph=60.0, highway="primary")
    g.add_edge(2, 1, length=1000.0, speed_kph=60.0, highway="primary")
    # secondary
    g.add_edge(2, 3, length=800.0, speed_kph=50.0, highway="secondary")
    # residential — excluida
    g.add_edge(3, 4, length=300.0, speed_kph=30.0, highway="residential")
    # motorway_link
    g.add_edge(4, 5, length=500.0, speed_kph=80.0, highway="motorway_link")
    # highway como lista: contiene "primary" → debe incluirse
    g.add_edge(1, 5, length=600.0, speed_kph=60.0, highway=["primary", "residential"])
    # tertiary — 3ra clase vial con nombre, también principal
    g.add_edge(3, 5, length=700.0, speed_kph=40.0, highway="tertiary")
    return g


def _grafo_nodo_sin_coords() -> nx.MultiDiGraph:
    """Nodo 2 sin atributos de coordenadas; la arista 1→2 (primary) se omite."""
    g = nx.MultiDiGraph()
    g.add_node(1, y=-29.9000, x=-71.2500)
    g.add_node(2)  # sin y/x
    g.add_edge(1, 2, length=500.0, speed_kph=60.0, highway="primary")
    return g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_solo_vias_principales_se_incluyen() -> None:
    """Las vías 'primary', 'secondary', 'motorway_link', 'tertiary' pasan; 'residential' no."""
    adapter = OsmnxGrafoVial(grafo=_grafo_calles())
    polilineas = adapter.calles_principales()

    # Pares representados: 1→2 primary (deduplicado), 2→3 secondary,
    # 4→5 motorway_link, 1→5 lista, 3→5 tertiary. (3→4 residential excluida.)
    assert len(polilineas) == 5


def test_residential_no_aparece() -> None:
    """La arista 3→4 con highway='residential' no está en el resultado."""
    adapter = OsmnxGrafoVial(grafo=_grafo_calles())
    polilineas = adapter.calles_principales()

    # Coordenadas del nodo 3 (origen) y 4 (destino)
    coord_3 = (-29.9020, -71.2300)
    coord_4 = (-29.9030, -71.2200)
    for poly in polilineas:
        assert poly != [coord_3, coord_4], "residential no debe aparecer"


def test_formato_polilinea_dos_pares_lat_lon() -> None:
    """Cada polilínea es una lista de exactamente 2 tuplas (lat, lon)."""
    adapter = OsmnxGrafoVial(grafo=_grafo_calles())
    for poly in adapter.calles_principales():
        assert len(poly) == 2
        for punto in poly:
            assert len(punto) == 2
            lat, lon = punto
            assert isinstance(lat, float)
            assert isinstance(lon, float)


def test_dedup_bidireccional() -> None:
    """El par 1↔2 (primary en ambas direcciones) aparece una sola vez."""
    adapter = OsmnxGrafoVial(grafo=_grafo_calles())
    polilineas = adapter.calles_principales()

    coord_1 = (-29.9000, -71.2500)
    coord_2 = (-29.9010, -71.2400)
    segmentos_12 = [p for p in polilineas if set(p) == {coord_1, coord_2}]
    assert len(segmentos_12) == 1, "el segmento 1-2 debe aparecer exactamente una vez"


def test_coordenadas_correctas_lat_lon() -> None:
    """El segmento 2→3 (secondary) tiene lat=y y lon=x de los nodos."""
    adapter = OsmnxGrafoVial(grafo=_grafo_calles())
    polilineas = adapter.calles_principales()

    coord_2 = (-29.9010, -71.2400)
    coord_3 = (-29.9020, -71.2300)
    # La dirección exacta depende del orden de iteración del grafo; chequeamos
    # que el segmento esté presente independientemente del orden.
    assert [coord_2, coord_3] in polilineas or [coord_3, coord_2] in polilineas


def test_tertiary_se_incluye() -> None:
    """La arista 3→5 con highway='tertiary' está en el resultado."""
    adapter = OsmnxGrafoVial(grafo=_grafo_calles())
    polilineas = adapter.calles_principales()

    coord_3 = (-29.9020, -71.2300)
    coord_5 = (-29.9040, -71.2100)
    assert [coord_3, coord_5] in polilineas or [coord_5, coord_3] in polilineas


def test_highway_lista_se_incluye() -> None:
    """Arista con highway=['primary', 'residential'] debe estar en el resultado."""
    adapter = OsmnxGrafoVial(grafo=_grafo_calles())
    polilineas = adapter.calles_principales()

    coord_1 = (-29.9000, -71.2500)
    coord_5 = (-29.9040, -71.2100)
    assert [coord_1, coord_5] in polilineas, "highway como lista con 'primary' debe incluirse"


def test_nodo_sin_coords_se_omite() -> None:
    """Arista cuyo nodo destino no tiene coordenadas se descarta sin excepción."""
    adapter = OsmnxGrafoVial(grafo=_grafo_nodo_sin_coords())
    # No debe lanzar; debe devolver lista vacía (la única arista se omite).
    polilineas = adapter.calles_principales()
    assert polilineas == []
