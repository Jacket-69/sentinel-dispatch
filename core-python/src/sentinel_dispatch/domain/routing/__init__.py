"""Módulo de routing — A* sobre grafo vial OSM.

API pública del módulo. Detalle del algoritmo y la heurística en
:mod:`a_estrella` y :mod:`heuristica`; contrato del puerto en
:mod:`grafo_vial`. Fundamento: SRS sec. 2.6-B y ADR-0010.
"""

from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial
from sentinel_dispatch.domain.routing.heuristica import (
    V_MAX_KMH,
    V_MAX_MS,
    haversine_m,
    haversine_segundos,
)
from sentinel_dispatch.domain.routing.tipos import (
    Arista,
    NodoFueraDeRangoError,
    NodoId,
    NoRutaDisponibleError,
)

__all__ = [
    "V_MAX_KMH",
    "V_MAX_MS",
    "Arista",
    "GrafoVial",
    "NoRutaDisponibleError",
    "NodoFueraDeRangoError",
    "NodoId",
    "haversine_m",
    "haversine_segundos",
]
