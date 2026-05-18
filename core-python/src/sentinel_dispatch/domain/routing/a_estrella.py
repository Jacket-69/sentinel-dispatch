"""Algoritmo A* puro sobre el puerto :class:`GrafoVial`.

Implementa :func:`a_estrella` siguiendo el SRS sec. 2.6-B y ADR-0010 §1.
Sin I/O, sin dependencias externas: solo stdlib + dominio propio.
"""

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING

from sentinel_dispatch.domain.routing.heuristica import haversine_segundos
from sentinel_dispatch.domain.routing.tipos import NodoId, NoRutaDisponibleError

if TYPE_CHECKING:
    from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial


def a_estrella(
    grafo: GrafoVial,
    origen: NodoId,
    destino: NodoId,
    factor_hora: float,
    factor_sirena: float,
) -> tuple[float, list[NodoId]]:
    """Retorna (eta_segundos, ruta_de_nodos). Lanza NoRutaDisponibleError.

    Calcula la ruta de menor tiempo entre dos nodos del grafo vial usando
    el algoritmo A* con heurística Haversine admisible.

    Args:
        grafo: Instancia del puerto GrafoVial. Solo lectura.
        origen: NodoId del nodo de partida.
        destino: NodoId del nodo de llegada.
        factor_hora: Multiplicador por franja horaria (> 0). Refleja
            tráfico o condiciones del turno. Actúa como divisor de la
            velocidad efectiva.
        factor_sirena: Multiplicador por estado de sirena (> 0). Actúa
            como divisor de la velocidad efectiva junto a factor_hora.

    Returns:
        Tupla ``(eta_segundos, ruta_de_nodos)`` donde ``eta_segundos`` es
        el tiempo de viaje óptimo y ``ruta_de_nodos`` es la lista ordenada
        de NodoId desde origen hasta destino (ambos incluidos).

    Raises:
        ValueError: Si factor_hora <= 0 o factor_sirena <= 0.
        NoRutaDisponibleError: Si no existe camino entre origen y destino.
    """
    if factor_hora <= 0:
        raise ValueError(f"factor_hora debe ser > 0, recibido: {factor_hora}")
    if factor_sirena <= 0:
        raise ValueError(f"factor_sirena debe ser > 0, recibido: {factor_sirena}")

    if origen == destino:
        return (0.0, [origen])

    lat_destino, lon_destino = grafo.coordenadas(destino)

    # g_score[n] = costo real mínimo conocido desde origen hasta n
    g_score: dict[NodoId, float] = {origen: 0.0}

    # padre[n] = nodo predecesor en el camino óptimo hasta n
    padre: dict[NodoId, NodoId] = {}

    # Heap: (f_score, tie_breaker, nodo)
    contador: int = 0
    lat_origen, lon_origen = grafo.coordenadas(origen)
    h_origen = haversine_segundos(lat_origen, lon_origen, lat_destino, lon_destino)
    heap: list[tuple[float, int, NodoId]] = [(h_origen, contador, origen)]

    while heap:
        f_actual, _, nodo_actual = heapq.heappop(heap)

        # Lazy decrease-key: ignorar entradas obsoletas del heap
        g_actual = g_score.get(nodo_actual, float("inf"))
        lat_actual, lon_actual = grafo.coordenadas(nodo_actual)
        h_actual = haversine_segundos(lat_actual, lon_actual, lat_destino, lon_destino)
        if f_actual > g_actual + h_actual:
            continue

        if nodo_actual == destino:
            return (g_actual, _reconstruir_ruta(padre, origen, destino))

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
                f_vecino = g_tentativo + h_vecino
                contador += 1
                heapq.heappush(heap, (f_vecino, contador, vecino))

    raise NoRutaDisponibleError(f"sin ruta entre {origen} y {destino}")


def _reconstruir_ruta(
    padre: dict[NodoId, NodoId],
    origen: NodoId,
    destino: NodoId,
) -> list[NodoId]:
    """Reconstruye la ruta desde destino hasta origen y la invierte.

    Args:
        padre: Mapa de nodo -> predecesor en el camino óptimo.
        origen: Nodo de partida.
        destino: Nodo de llegada.

    Returns:
        Lista de NodoId en orden origen → destino.
    """
    ruta: list[NodoId] = []
    nodo = destino
    while nodo != origen:
        ruta.append(nodo)
        nodo = padre[nodo]
    ruta.append(origen)
    ruta.reverse()
    return ruta
