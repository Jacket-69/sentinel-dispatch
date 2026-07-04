"""Traza didáctica del A* — instrumentación para la vista demostrativa.

Replica el bucle de :func:`domain.routing.a_estrella.a_estrella` (mismo
peso de arista, misma heurística Haversine y mismo tie-breaker del heap)
registrando además el orden en que los nodos salen de la frontera. El A*
operativo del dominio **no se toca**: la paridad RT-02 con el núcleo Java
depende de él, y esta traza es presentación pura (consola web, ADR-0022).

La duplicación del bucle es deliberada y acotada: instrumentar el A*
operativo con callbacks lo contaminaría con una preocupación de UI.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sentinel_dispatch.domain.routing.heuristica import haversine_segundos
from sentinel_dispatch.domain.routing.tipos import NodoId, NoRutaDisponibleError

if TYPE_CHECKING:
    from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial


@dataclass(frozen=True, slots=True)
class TrazaAstar:
    """Resultado del A* instrumentado para la vista didáctica.

    ``expansiones`` es la lista de nodos en el orden exacto en que el
    algoritmo los extrajo de la frontera (excluyendo entradas obsoletas
    del heap); el último elemento es siempre el destino.
    """

    eta_segundos: float
    ruta_nodos: list[NodoId]
    expansiones: list[NodoId]
    h_origen_segundos: float


def trazar_a_estrella(
    grafo: GrafoVial,
    origen: NodoId,
    destino: NodoId,
    factor_hora: float = 1.0,
    factor_sirena: float = 1.0,
) -> TrazaAstar:
    """A* con registro del orden de expansión (ver docstring del módulo).

    Mismo contrato que :func:`domain.routing.a_estrella.a_estrella`:
    lanza ``ValueError`` con factores no positivos y
    ``NoRutaDisponibleError`` si no hay camino.
    """
    if factor_hora <= 0:
        raise ValueError(f"factor_hora debe ser > 0, recibido: {factor_hora}")
    if factor_sirena <= 0:
        raise ValueError(f"factor_sirena debe ser > 0, recibido: {factor_sirena}")

    lat_destino, lon_destino = grafo.coordenadas(destino)
    lat_origen, lon_origen = grafo.coordenadas(origen)
    h_origen = haversine_segundos(lat_origen, lon_origen, lat_destino, lon_destino)

    if origen == destino:
        return TrazaAstar(
            eta_segundos=0.0,
            ruta_nodos=[origen],
            expansiones=[origen],
            h_origen_segundos=0.0,
        )

    g_score: dict[NodoId, float] = {origen: 0.0}
    padre: dict[NodoId, NodoId] = {}
    expansiones: list[NodoId] = []

    contador: int = 0
    heap: list[tuple[float, int, NodoId]] = [(h_origen, contador, origen)]

    while heap:
        f_actual, _, nodo_actual = heapq.heappop(heap)

        # Lazy decrease-key: ignorar entradas obsoletas del heap
        g_actual = g_score.get(nodo_actual, float("inf"))
        lat_actual, lon_actual = grafo.coordenadas(nodo_actual)
        h_actual = haversine_segundos(lat_actual, lon_actual, lat_destino, lon_destino)
        if f_actual > g_actual + h_actual:
            continue

        expansiones.append(nodo_actual)

        if nodo_actual == destino:
            return TrazaAstar(
                eta_segundos=g_actual,
                ruta_nodos=_reconstruir_ruta(padre, origen, destino),
                expansiones=expansiones,
                h_origen_segundos=h_origen,
            )

        for arista in grafo.vecinos(nodo_actual):
            velocidad_ms = arista.velocidad_efectiva_kmh * 1000.0 / 3600.0
            peso = arista.longitud_m / (velocidad_ms * factor_hora * factor_sirena)

            g_tentativo = g_actual + peso
            vecino = arista.destino

            if g_tentativo < g_score.get(vecino, float("inf")):
                g_score[vecino] = g_tentativo
                padre[vecino] = nodo_actual

                lat_vecino, lon_vecino = grafo.coordenadas(vecino)
                h_vecino = haversine_segundos(lat_vecino, lon_vecino, lat_destino, lon_destino)
                contador += 1
                heapq.heappush(heap, (g_tentativo + h_vecino, contador, vecino))

    raise NoRutaDisponibleError(f"sin ruta entre {origen} y {destino}")


def _reconstruir_ruta(
    padre: dict[NodoId, NodoId],
    origen: NodoId,
    destino: NodoId,
) -> list[NodoId]:
    """Reconstruye la ruta desde destino hasta origen y la invierte."""
    ruta: list[NodoId] = []
    nodo = destino
    while nodo != origen:
        ruta.append(nodo)
        nodo = padre[nodo]
    ruta.append(origen)
    ruta.reverse()
    return ruta
