"""Proyección de un punto sobre una polilínea (snap-to-edge, ADR-0020).

Lógica geométrica pura: solo :mod:`math` de la stdlib. No importa OSMnx,
NetworkX ni shapely. El adapter (:mod:`adapters.grafo_osmnx`) extrae los
vértices de cada arista candidata del grafo y delega aquí el cálculo de la
proyección, manteniéndose delgado y respetando Ports & Adapters.

El cálculo se hace en un plano métrico local equirectangular centrado en el
punto a proyectar: para distancias del orden de cientos de metros (el caso
del snap urbano) el error frente a la geodésica es despreciable, y evita el
sesgo de proyectar en grados crudos sin corregir la escala de la longitud
por el coseno de la latitud.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

METROS_POR_GRADO_LAT: float = 111_320.0
"""Metros por grado de latitud (aprox. constante; WGS84 ≈ 110.6-111.7 km).

Para la longitud se escala este valor por ``cos(latitud)`` localmente. El
error del modelo equirectangular es < 0.5 % en distancias urbanas cortas,
del mismo orden que el ya asumido por :func:`haversine_m`.
"""


def proyectar_en_polilinea(
    lat: float,
    lon: float,
    vertices: Sequence[tuple[float, float]],
) -> tuple[float, float, float, float]:
    """Proyecta ``(lat, lon)`` sobre la polilínea ``vertices``.

    Args:
        lat: latitud del punto a proyectar, en grados.
        lon: longitud del punto a proyectar, en grados.
        vertices: secuencia de ``(lat, lon)`` que describe la polilínea
            (la geometría de una arista vial), en orden desde el nodo origen
            hacia el nodo destino. Debe tener al menos un punto.

    Returns:
        Tupla ``(fraccion, lat_proj, lon_proj, distancia_m)`` donde:

        - ``fraccion`` ∈ ``[0.0, 1.0]`` es la posición del punto proyectado a
          lo largo de la polilínea, medida desde el primer vértice.
        - ``(lat_proj, lon_proj)`` es el punto proyectado, en grados.
        - ``distancia_m`` es la distancia (metros) entre el punto original y
          su proyección sobre la polilínea.

    Raises:
        ValueError: si ``vertices`` está vacía.
    """
    if not vertices:
        raise ValueError("la polilínea debe tener al menos un vértice")

    # Plano métrico local centrado en el punto a proyectar: P_local = (0, 0).
    cos_lat = math.cos(math.radians(lat))

    def a_metros(la: float, lo: float) -> tuple[float, float]:
        x = (lo - lon) * METROS_POR_GRADO_LAT * cos_lat
        y = (la - lat) * METROS_POR_GRADO_LAT
        return (x, y)

    if len(vertices) == 1:
        la0, lo0 = vertices[0]
        x0, y0 = a_metros(la0, lo0)
        return (0.0, la0, lo0, math.hypot(x0, y0))

    puntos_m = [a_metros(la, lo) for la, lo in vertices]

    # Longitudes de cada segmento y total (en el plano métrico local).
    seg_largos: list[float] = []
    for i in range(len(puntos_m) - 1):
        (ax, ay), (bx, by) = puntos_m[i], puntos_m[i + 1]
        seg_largos.append(math.hypot(bx - ax, by - ay))
    largo_total = sum(seg_largos)

    mejor_dist = math.inf
    mejor_acum = 0.0  # distancia métrica acumulada hasta la proyección óptima
    mejor_lat = vertices[0][0]
    mejor_lon = vertices[0][1]

    acum = 0.0
    for i in range(len(puntos_m) - 1):
        (ax, ay), (bx, by) = puntos_m[i], puntos_m[i + 1]
        s_len = seg_largos[i]
        if s_len == 0.0:
            t = 0.0
            proj_x, proj_y = ax, ay
        else:
            abx, aby = bx - ax, by - ay
            # P = (0,0); t = clamp((P - A)·AB / |AB|², 0, 1)
            t = ((-ax) * abx + (-ay) * aby) / (s_len * s_len)
            t = max(0.0, min(1.0, t))
            proj_x, proj_y = ax + t * abx, ay + t * aby

        dist = math.hypot(proj_x, proj_y)
        if dist < mejor_dist:
            mejor_dist = dist
            mejor_acum = acum + t * s_len
            la_a, lo_a = vertices[i]
            la_b, lo_b = vertices[i + 1]
            mejor_lat = la_a + t * (la_b - la_a)
            mejor_lon = lo_a + t * (lo_b - lo_a)
        acum += s_len

    fraccion = mejor_acum / largo_total if largo_total > 0.0 else 0.0
    return (fraccion, mejor_lat, mejor_lon, mejor_dist)
