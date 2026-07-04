"""Tests del A* instrumentado para la vista didáctica (application.traza_astar).

La garantía central es la **paridad con el A* operativo del dominio**: misma
ETA y misma ruta sobre el mismo grafo (la traza solo agrega observabilidad).
"""

from typing import ClassVar

import pytest

from sentinel_dispatch.application.traza_astar import trazar_a_estrella
from sentinel_dispatch.domain.routing.a_estrella import a_estrella
from sentinel_dispatch.domain.routing.tipos import Arista, NoRutaDisponibleError


class _GrafoDiamante:
    """Diamante 1 → {2, 3} → 4 con un camino claramente mejor (vía 2).

    Coordenadas casi colineales para que la heurística guíe hacia el 4.
    """

    _COORDS: ClassVar[dict[int, tuple[float, float]]] = {
        1: (-29.9000, -71.2600),
        2: (-29.9000, -71.2550),
        3: (-29.9080, -71.2550),
        4: (-29.9000, -71.2500),
    }

    _ARISTAS: ClassVar[dict[int, list[tuple[int, float, float]]]] = {
        1: [(2, 500.0, 50.0), (3, 900.0, 50.0)],
        2: [(4, 500.0, 50.0)],
        3: [(4, 900.0, 50.0)],
        4: [],
    }

    def vecinos(self, nodo: int) -> list[Arista]:
        return [
            Arista(origen=nodo, destino=d, longitud_m=largo, velocidad_efectiva_kmh=vel)
            for d, largo, vel in self._ARISTAS[nodo]
        ]

    def coordenadas(self, nodo: int) -> tuple[float, float]:
        return self._COORDS[nodo]


def test_traza_paridad_con_astar_operativo() -> None:
    # La traza no altera el resultado: misma ETA y misma ruta que el dominio.
    grafo = _GrafoDiamante()
    eta_dominio, ruta_dominio = a_estrella(grafo, 1, 4, factor_hora=1.0, factor_sirena=1.0)
    traza = trazar_a_estrella(grafo, 1, 4)
    assert traza.eta_segundos == eta_dominio
    assert traza.ruta_nodos == ruta_dominio == [1, 2, 4]


def test_traza_registra_expansiones_en_orden() -> None:
    traza = trazar_a_estrella(_GrafoDiamante(), 1, 4)
    # El origen se expande primero y el destino cierra la traza.
    assert traza.expansiones[0] == 1
    assert traza.expansiones[-1] == 4
    # El camino óptimo (vía 2) se expande antes que el desvío (3).
    assert traza.expansiones.index(2) < len(traza.expansiones)
    # Sin duplicados: cada nodo sale de la frontera a lo más una vez.
    assert len(traza.expansiones) == len(set(traza.expansiones))


def test_traza_h_origen_es_cota_inferior_del_eta() -> None:
    # Admisibilidad observable: h(origen) nunca supera el costo real.
    traza = trazar_a_estrella(_GrafoDiamante(), 1, 4)
    assert 0 < traza.h_origen_segundos <= traza.eta_segundos


def test_traza_origen_igual_destino() -> None:
    traza = trazar_a_estrella(_GrafoDiamante(), 2, 2)
    assert traza.eta_segundos == 0.0
    assert traza.ruta_nodos == [2]
    assert traza.expansiones == [2]
    assert traza.h_origen_segundos == 0.0


def test_traza_sin_ruta_lanza_error() -> None:
    with pytest.raises(NoRutaDisponibleError):
        trazar_a_estrella(_GrafoDiamante(), 4, 1)  # el diamante es dirigido


@pytest.mark.parametrize(("factor_hora", "factor_sirena"), [(0.0, 1.0), (1.0, -1.0)])
def test_traza_rechaza_factores_invalidos(factor_hora: float, factor_sirena: float) -> None:
    with pytest.raises(ValueError, match="debe ser > 0"):
        trazar_a_estrella(
            _GrafoDiamante(), 1, 4, factor_hora=factor_hora, factor_sirena=factor_sirena
        )
