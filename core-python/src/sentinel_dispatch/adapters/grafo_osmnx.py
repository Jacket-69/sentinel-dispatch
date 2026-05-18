"""Adapter OSMnx para el puerto :class:`~sentinel_dispatch.domain.routing.grafo_vial.GrafoVial`.

Envuelve un :class:`networkx.MultiDiGraph` descargado con OSMnx y lo expone
como :class:`GrafoVial`. La función :func:`cargar_grafo_iv_region` gestiona
la descarga y la caché local en GraphML.

Cascade de velocidades (ADR-0010 §2): si la arista tiene tag ``maxspeed``,
OSMnx lo parsea y lo escribe como ``speed_kph``; si no, ``add_edge_speeds``
asigna el default por ``highway`` type según :data:`TABLA_HWY_SPEEDS_CHILE`.
Esto replica el comportamiento de ``osrm-extract`` con ``car.lua`` y es
condición necesaria para cumplir la tolerancia IT-01 (±5% en duration).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import networkx as nx  # noqa: TC002 — usado en runtime como campo del dataclass
import osmnx as ox

from sentinel_dispatch.domain.routing.heuristica import haversine_m
from sentinel_dispatch.domain.routing.tipos import (
    Arista,
    NodoFueraDeRangoError,
    NodoId,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BBOX_IV_REGION: tuple[float, float, float, float] = (-71.45, -30.10, -71.15, -29.85)
"""Bounding box de la conurbación La Serena-Coquimbo.

Formato OSMnx 2.x: ``(left, bottom, right, top)`` = ``(west, south, east, north)``.
Diferente de OSMnx 1.x que usaba ``(north, south, east, west)``.
"""

# Raíz del monorepo: parents[4] desde este archivo.
# adapters/grafo_osmnx.py → [0] adapters/
# → [1] sentinel_dispatch/  → [2] src/
# → [3] core-python/        → [4] sentinel-dispatch/  ← raíz monorepo
_MONOREPO_ROOT: Path = Path(__file__).resolve().parents[4]

GRAPHML_PATH: Path = _MONOREPO_ROOT / "data" / "graphs" / "coquimbo.graphml"
"""Ruta canónica de la caché GraphML del grafo vial."""

MAXSPEED_FALLBACK_KMH: float = 30.0
"""Velocidad efectiva de fallback cuando ``speed_kph`` no está en la arista.

Se aplica en :meth:`OsmnxGrafoVial.vecinos` si ``add_edge_speeds`` no pudo
imputar la velocidad para alguna arista concreta (situación excepcional,
p. ej. grafos sintéticos de test).
"""

TABLA_HWY_SPEEDS_CHILE: dict[str, float] = {
    "motorway": 120.0,
    "motorway_link": 80.0,
    "trunk": 100.0,
    "trunk_link": 60.0,
    "primary": 60.0,
    "primary_link": 40.0,
    "secondary": 50.0,
    "secondary_link": 40.0,
    "tertiary": 40.0,
    "tertiary_link": 30.0,
    "residential": 30.0,
    "living_street": 15.0,
    "unclassified": 30.0,
    "road": 30.0,
    "service": 20.0,
}
"""Defaults de velocidad por tipo de vía para Chile (ADR-0010 §2, tabla)."""

# Límites geográficos para validación de snap (SRS RN-01, IV Región).
_LAT_MIN: float = -30.5
_LAT_MAX: float = -29.5
_LON_MIN: float = -71.7
_LON_MAX: float = -70.5


# ---------------------------------------------------------------------------
# Función de carga con caché
# ---------------------------------------------------------------------------


def cargar_grafo_iv_region(
    *,
    bbox: tuple[float, float, float, float] = BBOX_IV_REGION,
    ruta_cache: Path = GRAPHML_PATH,
    forzar_descarga: bool = False,
) -> nx.MultiDiGraph:
    """Carga el grafo vial de la conurbación La Serena-Coquimbo, con caché local.

    Si ``ruta_cache`` existe y ``forzar_descarga`` es ``False``, carga el grafo
    desde el archivo GraphML. En caso contrario, descarga de Overpass/OSM,
    imputa velocidades y persiste la caché.

    Parámetros
    ----------
    bbox:
        Bounding box ``(left, bottom, right, top)`` en grados decimales.
        Por defecto :data:`BBOX_IV_REGION`.
    ruta_cache:
        Path al archivo ``.graphml`` de caché. Por defecto :data:`GRAPHML_PATH`.
    forzar_descarga:
        Si ``True``, ignora la caché existente y re-descarga.

    Retorna
    -------
    nx.MultiDiGraph
        Grafo vial con atributo ``speed_kph`` en todas las aristas.
    """
    if ruta_cache.exists() and not forzar_descarga:
        _log.info("Cargando grafo desde caché: %s", ruta_cache)
        grafo: nx.MultiDiGraph = ox.load_graphml(ruta_cache)
        return grafo

    _log.info("Descargando grafo vial desde OSM (bbox=%s)…", bbox)
    grafo = ox.graph_from_bbox(
        bbox=bbox,
        network_type="drive",
        simplify=True,
        retain_all=False,
        truncate_by_edge=True,
    )
    ox.routing.add_edge_speeds(
        grafo, hwy_speeds=TABLA_HWY_SPEEDS_CHILE, fallback=MAXSPEED_FALLBACK_KMH
    )

    ruta_cache.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(grafo, filepath=ruta_cache)
    _log.info("Grafo persistido en: %s", ruta_cache)
    return grafo


# ---------------------------------------------------------------------------
# Adapter — implementación del puerto GrafoVial
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OsmnxGrafoVial:
    """Adapter: envuelve un :class:`nx.MultiDiGraph` de OSMnx como GrafoVial.

    El grafo debe tener el atributo ``speed_kph`` en las aristas (cargado
    con :func:`cargar_grafo_iv_region` o equivalente). Si una arista concreta
    carece del atributo, se usa :data:`MAXSPEED_FALLBACK_KMH`.
    """

    grafo: nx.MultiDiGraph

    def vecinos(self, nodo: NodoId) -> Iterable[Arista]:
        """Aristas salientes del nodo dado.

        Incluye todas las aristas paralelas del MultiDiGraph (p. ej. autopista
        + calle de servicio entre los mismos nodos). El A* las consume como
        aristas independientes; el adapter no filtra.

        Si ``data["length"]`` no existe (grafo sintético), se calcula con
        Haversine sobre los endpoints y se loggea una advertencia.
        """
        for u, v, _key, data in self.grafo.out_edges(nodo, keys=True, data=True):
            velocidad_kmh: float = data.get("speed_kph", MAXSPEED_FALLBACK_KMH)

            longitud_raw = data.get("length")
            if longitud_raw is not None:
                longitud_m: float = float(longitud_raw)
            else:
                # Fallback: Haversine sobre los endpoints del segmento.
                # Ocurre solo en grafos sintéticos o datos corruptos.
                nodos = self.grafo.nodes
                lat_u, lon_u = float(nodos[u]["y"]), float(nodos[u]["x"])
                lat_v, lon_v = float(nodos[v]["y"]), float(nodos[v]["x"])
                longitud_m = haversine_m(lat_u, lon_u, lat_v, lon_v)
                _log.warning(
                    "Arista (%s -> %s) sin atributo 'length'; longitud calculada por Haversine: %.1f m",
                    u,
                    v,
                    longitud_m,
                )

            yield Arista(
                origen=NodoId(u),
                destino=NodoId(v),
                longitud_m=longitud_m,
                velocidad_efectiva_kmh=velocidad_kmh,
            )

    def coordenadas(self, nodo: NodoId) -> tuple[float, float]:
        """Coordenadas geográficas del nodo en grados decimales.

        Retorna ``(lat, lon)`` en EPSG:4326. OSMnx almacena ``y`` = lat, ``x`` = lon.
        """
        datos = self.grafo.nodes[nodo]
        return float(datos["y"]), float(datos["x"])

    def nodo_mas_cercano(self, lat: float, lon: float) -> NodoId:
        """Snap de una coordenada arbitraria al nodo OSM más cercano.

        Valida que ``lat in [-30.5, -29.5]`` y ``lon in [-71.7, -70.5]`` (SRS RN-01).
        Si las coordenadas están fuera de rango, lanza :exc:`NodoFueraDeRangoError`.

        Implementación: barrido lineal sobre los nodos del grafo con Haversine.
        Para 16-20k nodos del bbox de Coquimbo el costo es < 50 ms por snap,
        despreciable frente a la latencia del A*. Se evita ``ox.nearest_nodes``
        porque sobre un grafo no-proyectado (lat/lon EPSG:4326) requiere
        ``scikit-learn`` como dependencia opcional, y el proyecto restringe
        dependencias pesadas sin ADR previo (anti-patrón documentado).
        """
        if not (_LAT_MIN <= lat <= _LAT_MAX) or not (_LON_MIN <= lon <= _LON_MAX):
            raise NodoFueraDeRangoError(
                f"Coordenadas ({lat}, {lon}) fuera del area de cobertura "
                f"IV Region (lat in [{_LAT_MIN}, {_LAT_MAX}], lon in [{_LON_MIN}, {_LON_MAX}])."
            )
        mejor_nodo: NodoId | None = None
        mejor_distancia = float("inf")
        for nodo_id, datos in self.grafo.nodes(data=True):
            distancia = haversine_m(lat, lon, float(datos["y"]), float(datos["x"]))
            if distancia < mejor_distancia:
                mejor_distancia = distancia
                mejor_nodo = NodoId(nodo_id)
        if mejor_nodo is None:
            raise NodoFueraDeRangoError("El grafo no contiene nodos.")
        return mejor_nodo

    def distancia_snap_m(self, lat: float, lon: float, nodo: NodoId) -> float:
        """Distancia en metros entre la coordenada original y el nodo snapeado.

        Usada para implementar RN-09 (alerta si > 500 m).
        """
        lat_nodo, lon_nodo = self.coordenadas(nodo)
        return haversine_m(lat, lon, lat_nodo, lon_nodo)
