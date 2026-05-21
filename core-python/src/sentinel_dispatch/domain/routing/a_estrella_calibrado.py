"""A* experimental con turn penalty simple (ADR-0013 §H4-cal-2).

Variante calibrada del :func:`a_estrella` que añade un costo aditivo
``turn_penalty_s`` cuando el cambio de bearing entre la arista entrante y
la arista saliente supera ``bearing_umbral_grados``. Modela
groseramente el comportamiento de OSRM `car.lua`, que penaliza giros
fuertes en intersecciones.

**Aislamiento de producción**: esta función NO reemplaza a
:func:`a_estrella` en el orquestador. Vive como módulo separado para
preservar la paridad bit-exacta Java↔Python de RT-02 (ADR-0017). Se
invoca exclusivamente desde el test de calibración CP-01c
(``test_routing_vs_osrm.py::test_cp01c_calibracion_y_turn_penalty``).

Si futura V2 incorpora turn penalty al A* operativo, este módulo se
vuelve obsoleto y se reescribe el A* principal (decisión costosa de
revertir; ameritaría ADR nuevo).
"""

from __future__ import annotations

import heapq
import math
from typing import TYPE_CHECKING

from sentinel_dispatch.domain.routing.heuristica import haversine_segundos
from sentinel_dispatch.domain.routing.tipos import NodoId, NoRutaDisponibleError

if TYPE_CHECKING:
    from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial


def _bearing_grados(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing inicial entre dos coordenadas en grados decimales, [0, 360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _delta_bearing(b1: float, b2: float) -> float:
    """Diferencia angular menor entre dos bearings (en grados, [0, 180])."""
    diff = abs(b2 - b1) % 360.0
    return min(diff, 360.0 - diff)


def a_estrella_calibrado(
    grafo: GrafoVial,
    origen: NodoId,
    destino: NodoId,
    *,
    factor_hora: float = 1.0,
    factor_sirena: float = 1.0,
    turn_penalty_s: float = 2.0,
    bearing_umbral_grados: float = 30.0,
) -> tuple[float, list[NodoId]]:
    """A* con penalización aditiva por giros pronunciados.

    Estado extendido: ``(nodo, nodo_previo)``. La arista entrante se
    representa implícitamente por el nodo previo (suficiente para grafos
    sin múltiples aristas paralelas con bearings distintos — en práctica
    las pocas aristas paralelas de OSMnx comparten dirección general).

    Penalty: si ``|bearing(prev→actual) − bearing(actual→vecino)| > umbral``
    se suma ``turn_penalty_s`` al g_score del vecino. Para el primer paso
    (sin nodo previo) no aplica penalty.

    Args:
        grafo: instancia del port :class:`GrafoVial` (solo lectura).
        origen, destino: NodoIds.
        factor_hora, factor_sirena: idénticos al A* original.
        turn_penalty_s: segundos a sumar por giro pronunciado (default 2.0,
            valor citado en ADR-0013).
        bearing_umbral_grados: umbral de Δbearing para considerar "giro
            pronunciado" (default 30°, valor citado en ADR-0013).

    Returns:
        Tupla ``(eta_segundos, ruta_de_nodos)``.

    Raises:
        NoRutaDisponibleError: si no existe camino.
        ValueError: si los factores son ≤ 0.
    """
    if factor_hora <= 0:
        raise ValueError(f"factor_hora debe ser > 0, recibido: {factor_hora}")
    if factor_sirena <= 0:
        raise ValueError(f"factor_sirena debe ser > 0, recibido: {factor_sirena}")
    if turn_penalty_s < 0:
        raise ValueError(f"turn_penalty_s debe ser >= 0, recibido: {turn_penalty_s}")

    if origen == destino:
        return (0.0, [origen])

    lat_destino, lon_destino = grafo.coordenadas(destino)

    # Estado del open-set: (nodo_actual, nodo_previo). Para el origen, previo=None.
    g_score: dict[tuple[NodoId, NodoId | None], float] = {(origen, None): 0.0}
    padre: dict[tuple[NodoId, NodoId | None], tuple[NodoId, NodoId | None]] = {}

    contador: int = 0
    lat_origen, lon_origen = grafo.coordenadas(origen)
    h_origen = haversine_segundos(lat_origen, lon_origen, lat_destino, lon_destino)
    heap: list[tuple[float, int, NodoId, NodoId | None]] = [(h_origen, contador, origen, None)]

    while heap:
        _, _, nodo_actual, nodo_prev = heapq.heappop(heap)
        estado_actual: tuple[NodoId, NodoId | None] = (nodo_actual, nodo_prev)
        g_actual = g_score.get(estado_actual, math.inf)

        if nodo_actual == destino:
            return (g_actual, _reconstruir_ruta(padre, estado_actual, origen))

        # Pre-calcula bearing de la arista entrante (si existe nodo previo)
        bearing_in: float | None = None
        if nodo_prev is not None:
            lat_prev, lon_prev = grafo.coordenadas(nodo_prev)
            lat_act, lon_act = grafo.coordenadas(nodo_actual)
            bearing_in = _bearing_grados(lat_prev, lon_prev, lat_act, lon_act)

        for arista in grafo.vecinos(nodo_actual):
            velocidad_ms = arista.velocidad_efectiva_kmh * 1000.0 / 3600.0
            peso = arista.longitud_m / (velocidad_ms * factor_hora * factor_sirena)

            penalty = 0.0
            if bearing_in is not None:
                lat_act, lon_act = grafo.coordenadas(nodo_actual)
                lat_vec, lon_vec = grafo.coordenadas(arista.destino)
                bearing_out = _bearing_grados(lat_act, lon_act, lat_vec, lon_vec)
                if _delta_bearing(bearing_in, bearing_out) > bearing_umbral_grados:
                    penalty = turn_penalty_s

            g_tentativo = g_actual + peso + penalty
            estado_vecino: tuple[NodoId, NodoId | None] = (arista.destino, nodo_actual)

            if g_tentativo < g_score.get(estado_vecino, math.inf):
                g_score[estado_vecino] = g_tentativo
                padre[estado_vecino] = estado_actual
                lat_vec, lon_vec = grafo.coordenadas(arista.destino)
                h_vec = haversine_segundos(lat_vec, lon_vec, lat_destino, lon_destino)
                contador += 1
                heapq.heappush(heap, (g_tentativo + h_vec, contador, arista.destino, nodo_actual))

    raise NoRutaDisponibleError(f"sin ruta entre {origen} y {destino}")


def _reconstruir_ruta(
    padre: dict[tuple[NodoId, NodoId | None], tuple[NodoId, NodoId | None]],
    estado_final: tuple[NodoId, NodoId | None],
    origen: NodoId,
) -> list[NodoId]:
    """Reconstruye la ruta de nodos desde el estado final hasta el origen."""
    ruta: list[NodoId] = []
    estado: tuple[NodoId, NodoId | None] | None = estado_final
    while estado is not None and estado[0] != origen:
        ruta.append(estado[0])
        estado = padre.get(estado)
    ruta.append(origen)
    ruta.reverse()
    return ruta
