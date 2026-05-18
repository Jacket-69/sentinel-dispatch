"""Heurística Haversine para A* sobre el grafo vial.

Distancia ortodrómica entre dos coordenadas geográficas, escalada a tiempo
de viaje por la velocidad máxima del sistema. Es **admisible** (nunca
sobreestima el costo real) porque ningún tramo del grafo se recorre a
velocidad efectiva superior a :data:`V_MAX_MS` (SRS sec. 2.6-B).

Lógica pura: depende solo de math.stdlib.
"""

from __future__ import annotations

import math

V_MAX_KMH: float = 180.0
"""Velocidad máxima absoluta del sistema en km/h.

Cota superior sobre la velocidad efectiva de cualquier arista bajo
cualquier combinación realista de ``factor_hora * factor_sirena``.
Garantiza la admisibilidad de :func:`haversine_segundos` (la heurística
nunca sobreestima el costo real).

Cálculo del techo: arista más rápida en la tabla Chile (ADR-0010 §2) =
``motorway = 120 km/h``. Factor combinado más rápido = ``factor_hora *
factor_sirena`` con ``factor_hora <= 1`` (1.0 es hora valle; valores
menores ralentizan por tráfico) y ``factor_sirena = 1.4`` (SRS sec.
2.6-B, sirena activa). Pico real ``120 * 1.0 * 1.4 = 168 km/h``. Se
adopta ``V_MAX = 180`` con margen del 7 % para absorber outliers del
grafo OSM o futuras variaciones de la tabla horaria.
"""

V_MAX_MS: float = V_MAX_KMH * 1000.0 / 3600.0
"""Velocidad máxima del sistema en m/s (≈ 38.89 m/s)."""

RADIO_TIERRA_M: float = 6_371_000.0
"""Radio medio de la Tierra en metros (esfera ideal, error ≤ 0.5%)."""


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia ortodrómica entre dos coordenadas, en metros.

    Fórmula clásica de Haversine sobre esfera de radio :data:`RADIO_TIERRA_M`.
    El error frente al modelo elipsoidal (WGS84) es < 0.5%, despreciable
    para el orden de magnitud del proyecto.
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = lat2_rad - lat1_rad
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.asin(math.sqrt(a))
    return RADIO_TIERRA_M * c


def haversine_segundos(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Heurística admisible h(n) para el A*: tiempo mínimo posible en segundos.

    Calcula la distancia ortodrómica y la divide por :data:`V_MAX_MS`.
    Como ninguna arista del grafo puede recorrerse a más de ``V_MAX``,
    ``h(n) ≤ costo_real(n, objetivo)`` para todo ``n`` — la condición
    de admisibilidad que A* exige para garantizar optimalidad.
    """
    return haversine_m(lat1, lon1, lat2, lon2) / V_MAX_MS
