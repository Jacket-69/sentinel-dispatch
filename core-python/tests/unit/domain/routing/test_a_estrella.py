"""Tests del algoritmo A* sobre grafos sintéticos.

Taxonomía:
  Normal  — comportamiento correcto en casos esperados.
  Borde   — propiedades de los factores y admisibilidad.
  Error   — entradas inválidas y grafos sin solución.
"""

from __future__ import annotations

import pytest
from grafo_fake import GrafoFake

from sentinel_dispatch.domain.routing.a_estrella import a_estrella
from sentinel_dispatch.domain.routing.heuristica import haversine_segundos
from sentinel_dispatch.domain.routing.tipos import NoRutaDisponibleError

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Normal
# ---------------------------------------------------------------------------


def test_camino_directo_es_optimo(grafo_simple_5nodos: GrafoFake) -> None:
    """El A* encuentra la ruta de menor ETA entre dos nodos conectados.

    Ruta óptima 0->2: 0->1->4->2 (69.6 s) es más rápida que 0->1->2 (86.4 s).
    """
    eta, ruta = a_estrella(grafo_simple_5nodos, 0, 2, 1.0, 1.0)
    assert eta == pytest.approx(69.6, rel=0.001)
    assert ruta == [0, 1, 4, 2]


def test_camino_con_desvio_mas_corto_es_preferido(
    grafo_simple_5nodos: GrafoFake,
) -> None:
    """El A* prefiere el desvío 0->1->4->2 sobre el camino lineal 0->1->2."""
    _, ruta = a_estrella(grafo_simple_5nodos, 0, 2, 1.0, 1.0)
    # El camino directo 0->1->2 tiene ETA 86.4 s; el desvío 69.6 s
    assert ruta != [0, 1, 2], "A* no debería elegir la ruta más lenta"
    assert ruta[0] == 0
    assert ruta[-1] == 2


def test_origen_igual_destino_retorna_cero_y_lista_unitaria(
    grafo_simple_5nodos: GrafoFake,
) -> None:
    """origen == destino retorna (0.0, [origen]) sin expandir el grafo."""
    eta, ruta = a_estrella(grafo_simple_5nodos, 3, 3, 1.0, 1.0)
    assert eta == 0.0
    assert ruta == [3]


def test_tie_breaking_es_deterministico(grafo_simple_5nodos: GrafoFake) -> None:
    """Dos llamadas con los mismos argumentos retornan exactamente la misma ruta."""
    resultado_1 = a_estrella(grafo_simple_5nodos, 0, 2, 1.0, 1.0)
    resultado_2 = a_estrella(grafo_simple_5nodos, 0, 2, 1.0, 1.0)
    assert resultado_1 == resultado_2


# ---------------------------------------------------------------------------
# Borde
# ---------------------------------------------------------------------------


def test_factor_hora_05_duplica_eta(grafo_simple_5nodos: GrafoFake) -> None:
    """factor_hora=0.5 reduce la velocidad efectiva a la mitad, duplicando el ETA."""
    eta_base, _ = a_estrella(grafo_simple_5nodos, 0, 2, 1.0, 1.0)
    eta_lento, _ = a_estrella(grafo_simple_5nodos, 0, 2, 0.5, 1.0)
    assert eta_lento == pytest.approx(eta_base * 2.0, rel=0.001)


def test_factor_sirena_14_reduce_eta() -> None:
    """factor_sirena=1.4 reduce el ETA proporcionalmente en un grafo de un solo camino.

    Grafo lineal 0->1 (sin alternativa) garantiza que A* toma siempre la misma
    ruta; así la proporción eta_sirena/eta_base == 1/1.4 es verificable exactamente.
    """
    g = GrafoFake()
    g.agregar_nodo(0, -29.9027, -71.2519)
    g.agregar_nodo(1, -29.9027, -71.2412)
    g.agregar_arista(0, 1, 1000.0, 50.0)

    eta_base, _ = a_estrella(g, 0, 1, 1.0, 1.0)
    eta_sirena, _ = a_estrella(g, 0, 1, 1.0, 1.4)
    assert eta_sirena == pytest.approx(eta_base / 1.4, rel=0.001)


def test_heuristica_admisible_h_origen_menor_que_eta_real(
    grafo_simple_5nodos: GrafoFake,
) -> None:
    """h(origen) <= eta_real para la ruta óptima calculada (admisibilidad empírica)."""
    eta_real, _ = a_estrella(grafo_simple_5nodos, 0, 2, 1.0, 1.0)
    lat_o, lon_o = grafo_simple_5nodos.coordenadas(0)
    lat_d, lon_d = grafo_simple_5nodos.coordenadas(2)
    h_origen = haversine_segundos(lat_o, lon_o, lat_d, lon_d)
    assert h_origen <= eta_real + 1e-9, (
        f"Heurística no admisible: h={h_origen:.4f} > eta={eta_real:.4f}"
    )


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


def test_sin_camino_lanza_no_ruta_disponible_error() -> None:
    """Si el destino está en un componente aislado, se lanza NoRutaDisponibleError."""
    g = GrafoFake()
    g.agregar_nodo(0, -29.9027, -71.2519)
    g.agregar_nodo(1, -29.9100, -71.2519)
    g.agregar_nodo(99, -29.8000, -71.2000)  # nodo aislado sin aristas entrantes
    g.agregar_arista(0, 1, 800.0, 50.0)

    with pytest.raises(NoRutaDisponibleError):
        a_estrella(g, 0, 99, 1.0, 1.0)


@pytest.mark.parametrize("factor_hora", [0.0, -1.0, -0.001])
def test_factor_hora_invalido_lanza_value_error(
    grafo_simple_5nodos: GrafoFake, factor_hora: float
) -> None:
    """factor_hora <= 0 lanza ValueError antes de cualquier cómputo."""
    with pytest.raises(ValueError, match="factor_hora"):
        a_estrella(grafo_simple_5nodos, 0, 2, factor_hora, 1.0)


@pytest.mark.parametrize("factor_sirena", [0.0, -1.0, -0.001])
def test_factor_sirena_invalido_lanza_value_error(
    grafo_simple_5nodos: GrafoFake, factor_sirena: float
) -> None:
    """factor_sirena <= 0 lanza ValueError antes de cualquier cómputo."""
    with pytest.raises(ValueError, match="factor_sirena"):
        a_estrella(grafo_simple_5nodos, 0, 2, 1.0, factor_sirena)
