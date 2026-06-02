"""Tests unitarios para a_estrella_snap_edge (ADR-0020 §3b).

Grafo lineal colineal: tres nodos oeste→este.

    1 ----(1000 m, 36 km/h)----> 2 ----(1000 m, 36 km/h)----> 3
    1 <---(1000 m, 36 km/h)----- 2   (arista inversa 2→1)

Velocidad 36 km/h = 10 m/s, por tanto tiempo = longitud / 10.

Todos los tests usan turn_penalty_s=0.0 para que los tiempos sean exactos.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Permite importar GrafoFake sin instalación adicional.
sys.path.insert(0, str(Path(__file__).parent))

from grafo_fake import GrafoFake

from sentinel_dispatch.domain.routing.a_estrella_snap_edge import a_estrella_snap_edge
from sentinel_dispatch.domain.routing.tipos import Arista, NoRutaDisponibleError, PosicionEnArista

# ---------------------------------------------------------------------------
# Constantes del grafo de prueba
# ---------------------------------------------------------------------------
V_KMH = 36.0  # km/h → 10 m/s
L_M = 1000.0  # longitud de cada segmento en metros


# ---------------------------------------------------------------------------
# Fixture: grafo lineal 1→2→3 con inversa 2→1
# ---------------------------------------------------------------------------
@pytest.fixture
def grafo_lineal() -> GrafoFake:
    """Grafo lineal de 3 nodos colineales (oeste a este)."""
    g = GrafoFake()
    # Nodos: latitudes idénticas, longitudes separadas ~0.009° ≈ 1 km
    g.agregar_nodo(1, lat=-29.900000, lon=-71.300000)
    g.agregar_nodo(2, lat=-29.900000, lon=-71.291000)  # ~1 km al este de 1
    g.agregar_nodo(3, lat=-29.900000, lon=-71.282000)  # ~1 km al este de 2
    # Aristas dirigidas
    g.agregar_arista(1, 2, longitud_m=L_M, velocidad_kmh=V_KMH)
    g.agregar_arista(2, 3, longitud_m=L_M, velocidad_kmh=V_KMH)
    g.agregar_arista(2, 1, longitud_m=L_M, velocidad_kmh=V_KMH)  # inversa
    return g


# ---------------------------------------------------------------------------
# Helper: construir PosicionEnArista a mano
# ---------------------------------------------------------------------------
def _pos(
    grafo: GrafoFake,
    origen_nodo: int,
    destino_nodo: int,
    fraccion: float,
) -> PosicionEnArista:
    """Construye un PosicionEnArista interpolando entre dos nodos del grafo."""
    arista = Arista(
        origen=origen_nodo,
        destino=destino_nodo,
        longitud_m=L_M,
        velocidad_efectiva_kmh=V_KMH,
    )
    lat_u, lon_u = grafo.coords[origen_nodo]
    lat_v, lon_v = grafo.coords[destino_nodo]
    lat = lat_u + fraccion * (lat_v - lat_u)
    lon = lon_u + fraccion * (lon_v - lon_u)
    return PosicionEnArista(
        arista=arista,
        fraccion=fraccion,
        lat=lat,
        lon=lon,
        distancia_snap_m=0.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_misma_arista_destino_adelante(grafo_lineal: GrafoFake) -> None:
    """Origen f=0.25 y destino f=0.75 sobre 1→2: camino directo, 500 m → 50 s."""
    pos_o = _pos(grafo_lineal, 1, 2, fraccion=0.25)
    pos_d = _pos(grafo_lineal, 1, 2, fraccion=0.75)
    eta, ruta = a_estrella_snap_edge(grafo_lineal, pos_o, pos_d, turn_penalty_s=0.0)
    distancia_m = 500.0  # (0.75 - 0.25) * 1000
    esperado_s = distancia_m / (V_KMH * 1000 / 3600)
    assert eta == pytest.approx(esperado_s, rel=1e-6)
    # Ruta directa: origen virtual → destino virtual sin pasar por nodos reales
    assert ruta == [-1, -2]


def test_aristas_adyacentes_pasa_por_nodo_2(grafo_lineal: GrafoFake) -> None:
    """Origen f=0.5 en 1→2, destino f=0.5 en 2→3: 1000 m por nodo 2 → 100 s."""
    pos_o = _pos(grafo_lineal, 1, 2, fraccion=0.5)
    pos_d = _pos(grafo_lineal, 2, 3, fraccion=0.5)
    eta, ruta = a_estrella_snap_edge(grafo_lineal, pos_o, pos_d, turn_penalty_s=0.0)
    # O → nodo2 (500 m) + nodo2 → D (500 m) = 1000 m
    distancia_m = 500.0 + 500.0
    esperado_s = distancia_m / (V_KMH * 1000 / 3600)
    assert eta == pytest.approx(esperado_s, rel=1e-6)
    assert 2 in ruta


def test_sentido_inverso_destino_antes_que_origen(grafo_lineal: GrafoFake) -> None:
    """Origen f=0.75 y destino f=0.25 en la misma arista 1→2 (destino antes que origen).

    Como existe la arista inversa 2→1, el nodo virtual destino es alcanzable
    desde el nodo 2 pagando (1 - 0.25) * 1000 = 750 m hacia atrás.
    El A* elige el camino más corto: O→nodo2 (250 m) + nodo2→D (750 m) = 1000 m → 100 s.
    No hay rodeo innecesario porque la arista 2→1 habilita el tramo inverso.
    """
    pos_o = _pos(grafo_lineal, 1, 2, fraccion=0.75)
    pos_d = _pos(grafo_lineal, 1, 2, fraccion=0.25)
    eta, ruta = a_estrella_snap_edge(grafo_lineal, pos_o, pos_d, turn_penalty_s=0.0)
    # O→nodo2 (250 m) + nodo2→D_virtual (750 m, arista reversa) = 1000 m
    distancia_m = 250.0 + 750.0
    esperado_s = distancia_m / (V_KMH * 1000 / 3600)
    assert eta == pytest.approx(esperado_s, rel=1e-6)
    assert 2 in ruta


def test_sentido_inverso_sin_reversa() -> None:
    """Origen f=0.75 y destino f=0.25 en 1→2, SIN arista inversa 2→1.

    Sin la arista inversa el nodo 2 no puede retroceder al destino virtual
    (que solo es alcanzable desde nodo 1), y el origen tampoco tiene tramo hacia
    atrás. El A* lanza NoRutaDisponibleError porque el destino virtual (-2)
    solo es accesible desde nodo 1 (vía 250 m), pero nodo 1 no es alcanzable
    desde el origen virtual en este grafo estrictamente unidireccional.
    """
    from grafo_fake import GrafoFake as GrafoFakeUni

    g_uni = GrafoFakeUni()
    g_uni.agregar_nodo(1, lat=-29.900000, lon=-71.300000)
    g_uni.agregar_nodo(2, lat=-29.900000, lon=-71.291000)
    g_uni.agregar_nodo(3, lat=-29.900000, lon=-71.282000)
    g_uni.agregar_arista(1, 2, longitud_m=L_M, velocidad_kmh=V_KMH)
    g_uni.agregar_arista(2, 3, longitud_m=L_M, velocidad_kmh=V_KMH)
    # NO se agrega arista 2→1: sin reversa, nodo2 no llega a D_virtual

    pos_o = _pos(g_uni, 1, 2, fraccion=0.75)
    pos_d = _pos(g_uni, 1, 2, fraccion=0.25)

    with pytest.raises(NoRutaDisponibleError):
        a_estrella_snap_edge(g_uni, pos_o, pos_d, turn_penalty_s=0.0)


def test_extremos_en_nodo_recorre_completo(grafo_lineal: GrafoFake) -> None:
    """Origen f=0.0 en 1→2, destino f=1.0 en 2→3: recorre 1→2→3 = 2000 m → 200 s."""
    pos_o = _pos(grafo_lineal, 1, 2, fraccion=0.0)
    pos_d = _pos(grafo_lineal, 2, 3, fraccion=1.0)
    eta, ruta = a_estrella_snap_edge(grafo_lineal, pos_o, pos_d, turn_penalty_s=0.0)
    distancia_m = 2000.0
    esperado_s = distancia_m / (V_KMH * 1000 / 3600)
    assert eta == pytest.approx(esperado_s, rel=1e-6)
    # Ruta debe pasar por nodo 2
    assert 2 in ruta
