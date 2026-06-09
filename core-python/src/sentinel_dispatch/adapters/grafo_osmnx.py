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
from typing import TYPE_CHECKING, Any

import networkx as nx  # noqa: TC002 — usado en runtime como campo del dataclass
import osmnx as ox

from sentinel_dispatch.domain.incidente.validacion import (
    CoordenadasFueraDeRangoError,
    validar_coordenadas_iv_region,
)
from sentinel_dispatch.domain.routing.geometria import proyectar_en_polilinea
from sentinel_dispatch.domain.routing.heuristica import haversine_m
from sentinel_dispatch.domain.routing.tipos import (
    Arista,
    NodoFueraDeRangoError,
    NodoId,
    PosicionEnArista,
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

# ---------------------------------------------------------------------------
# Función de carga con caché
# ---------------------------------------------------------------------------


def cargar_grafo_iv_region(
    *,
    bbox: tuple[float, float, float, float] = BBOX_IV_REGION,
    ruta_cache: Path = GRAPHML_PATH,
    forzar_descarga: bool = False,
    factor_calibracion: float = 1.0,
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
    factor_calibracion:
        Multiplicador aplicado al ``speed_kph`` de cada arista tras la carga
        (ADR-0013 §H4-cal-1). Default ``1.0`` (sin cambio). Usar ``0.85``
        para acercar las velocidades efectivas al perfil ``car.lua`` de OSRM
        (CP-01c). NO se persiste a disco — la calibración vive solo en memoria
        para no contaminar el grafo cacheado ni la paridad RT-02.

    Retorna
    -------
    nx.MultiDiGraph
        Grafo vial con atributo ``speed_kph`` en todas las aristas, opcionalmente
        escalado por ``factor_calibracion``.
    """
    if factor_calibracion <= 0:
        raise ValueError(f"factor_calibracion debe ser > 0, recibido: {factor_calibracion}")

    if ruta_cache.exists() and not forzar_descarga:
        _log.info("Cargando grafo desde caché: %s", ruta_cache)
        grafo: nx.MultiDiGraph = ox.load_graphml(ruta_cache)
        if factor_calibracion != 1.0:
            _aplicar_factor_calibracion(grafo, factor_calibracion)
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

    if factor_calibracion != 1.0:
        _aplicar_factor_calibracion(grafo, factor_calibracion)
    return grafo


def _aplicar_factor_calibracion(grafo: nx.MultiDiGraph, factor: float) -> None:
    """Escala el ``speed_kph`` de cada arista por ``factor`` (in-place).

    Solo afecta el grafo en memoria; el archivo GraphML cacheado en disco no
    se modifica. ADR-0013 §H4-cal-1.
    """
    for _u, _v, data in grafo.edges(data=True):
        speed = data.get("speed_kph", MAXSPEED_FALLBACK_KMH)
        data["speed_kph"] = float(speed) * factor


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
            yield self._arista_desde_data(u, v, data)

    def _arista_desde_data(self, u: int, v: int, data: Any) -> Arista:
        """Construye la :class:`Arista` de dominio desde los atributos OSMnx.

        Resuelve ``speed_kph`` (con :data:`MAXSPEED_FALLBACK_KMH` si falta) y
        ``length`` (con fallback Haversine sobre los endpoints si falta, caso
        de grafos sintéticos o datos corruptos). Punto único de verdad usado
        por :meth:`vecinos` y :meth:`posicion_en_arista`.
        """
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

        return Arista(
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

        Valida que ``(lat, lon)`` esté dentro del bbox IV Región (SRS RN-01)
        delegando en :func:`validar_coordenadas_iv_region` del dominio
        ``incidente``. Si las coordenadas están fuera de rango, atrapa
        :exc:`CoordenadasFueraDeRangoError` y la re-lanza como
        :exc:`NodoFueraDeRangoError` (subclase) para preservar el contrato
        de excepciones del adapter (ADR-0012).

        Implementación: barrido lineal sobre los nodos del grafo con Haversine.
        Para 16-20k nodos del bbox de Coquimbo el costo es < 50 ms por snap,
        despreciable frente a la latencia del A*. Se evita ``ox.nearest_nodes``
        porque sobre un grafo no-proyectado (lat/lon EPSG:4326) requiere
        ``scikit-learn`` como dependencia opcional, y el proyecto restringe
        dependencias pesadas sin ADR previo (anti-patrón documentado).
        """
        try:
            validar_coordenadas_iv_region(lat, lon)
        except CoordenadasFueraDeRangoError as exc:
            raise NodoFueraDeRangoError(str(exc), lat=lat, lon=lon) from exc
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

    # -----------------------------------------------------------------------
    # Snap-to-edge (GrafoVialConSnapEdge — ADR-0020 §H5-cal-3a)
    # -----------------------------------------------------------------------

    def posicion_en_arista(self, lat: float, lon: float) -> PosicionEnArista:
        """Proyecta ``(lat, lon)`` sobre la arista vial más cercana.

        Snap-to-edge: a diferencia de :meth:`nodo_mas_cercano`, no salta al
        nodo OSM más próximo sino que proyecta el punto sobre la geometría de
        la arista más cercana, reportando la fracción a lo largo de ella
        (ADR-0020). Esto replica el snap de OSRM y elimina el sesgo de
        snap-to-node que domina la dispersión de ``duration`` (CP-01c).

        Estrategia de búsqueda: se ancla en :meth:`nodo_mas_cercano` (que
        valida el bbox RN-01) y se consideran como candidatas las aristas
        incidentes a ese nodo y a sus vecinos directos. En una malla urbana
        densa la arista más cercana es casi siempre incidente al nodo más
        cercano o a uno adyacente; acotar así evita proyectar sobre las 42 k
        aristas del grafo manteniendo la precisión. Sobre cada candidata se
        proyecta con :func:`proyectar_en_polilinea` (usando la geometría
        curva ``geometry`` si existe, o el segmento recto entre endpoints) y
        se elige la de menor distancia de snap.

        Raises:
            NodoFueraDeRangoError: si ``(lat, lon)`` cae fuera del bbox
                (delegado a :meth:`nodo_mas_cercano`) o si el nodo ancla no
                tiene aristas incidentes.
        """
        nodo_ancla = self.nodo_mas_cercano(lat, lon)

        mejor: PosicionEnArista | None = None
        for u, v, data in self._aristas_candidatas(nodo_ancla):
            vertices = self._vertices_latlon(u, v, data)
            fraccion, lat_proj, lon_proj, distancia = proyectar_en_polilinea(lat, lon, vertices)
            if mejor is None or distancia < mejor.distancia_snap_m:
                mejor = PosicionEnArista(
                    arista=self._arista_desde_data(u, v, data),
                    fraccion=fraccion,
                    lat=lat_proj,
                    lon=lon_proj,
                    distancia_snap_m=distancia,
                )

        if mejor is None:
            raise NodoFueraDeRangoError(
                f"El nodo más cercano a ({lat}, {lon}) no tiene aristas incidentes.",
                lat=lat,
                lon=lon,
            )
        return mejor

    def _aristas_candidatas(self, nodo: NodoId) -> list[tuple[int, int, Any]]:
        """Aristas incidentes al nodo y a sus vecinos directos, sin duplicados.

        Devuelve tuplas ``(u, v, data)`` para cada arista entrante o saliente
        del nodo ancla y de cada uno de sus sucesores/predecesores. La
        deduplicación es por ``(u, v, key)`` para que las aristas paralelas
        del MultiDiGraph se consideren una sola vez.
        """
        anclas: set[int] = {int(nodo)}
        anclas.update(int(n) for n in self.grafo.successors(nodo))
        anclas.update(int(n) for n in self.grafo.predecessors(nodo))

        vistas: set[tuple[int, int, int]] = set()
        candidatas: list[tuple[int, int, Any]] = []
        for n in anclas:
            for u, v, key, data in self.grafo.out_edges(n, keys=True, data=True):
                if (u, v, key) not in vistas:
                    vistas.add((u, v, key))
                    candidatas.append((u, v, data))
            for u, v, key, data in self.grafo.in_edges(n, keys=True, data=True):
                if (u, v, key) not in vistas:
                    vistas.add((u, v, key))
                    candidatas.append((u, v, data))
        return candidatas

    # -----------------------------------------------------------------------
    # Wireframe de calles principales (ADR-0022)
    # -----------------------------------------------------------------------

    def calles_principales(self) -> list[list[tuple[float, float]]]:
        """Polilíneas de las vías principales del grafo, para el wireframe del mapa.

        Filtra las aristas cuyo tag ``highway`` pertenece al conjunto:
        ``{"motorway", "trunk", "primary", "secondary", "tertiary"}`` y sus
        variantes ``_link``. Las 42 k aristas completas del grafo de Coquimbo
        son prohibitivas en el navegador; este subconjunto (~6,8 k segmentos)
        cubre la trama de calles con nombre sin lagear el mapa (ADR-0022).

        Cada arista que supera el filtro se representa como un **segmento
        recto** de dos puntos ``[(lat_u, lon_u), (lat_v, lon_v)]`` (no se usa
        la geometría curva OSMnx para mantener la respuesta liviana).

        El ``MultiDiGraph`` de OSMnx tiene tanto ``u→v`` como ``v→u``; la
        deduplicación es por ``frozenset({u, v})`` para no dibujar el mismo
        segmento dos veces en el wireframe.

        OSM puede almacenar ``highway`` como un ``str`` o como una ``list[str]``
        (cuando la vía comparte más de un rol). Ambos casos se manejan: si es
        lista, basta que alguno de sus valores sea principal.

        Si un nodo extremo carece de coordenadas, la arista se omite
        silenciosamente.

        Retorna
        -------
        list[list[tuple[float, float]]]
            Lista de polilíneas. Cada elemento es ``[(lat_u, lon_u), (lat_v, lon_v)]``.
        """
        highway_principales: frozenset[str] = frozenset(
            {
                "motorway",
                "motorway_link",
                "trunk",
                "trunk_link",
                "primary",
                "primary_link",
                "secondary",
                "secondary_link",
                "tertiary",
                "tertiary_link",
            }
        )

        def _es_principal(highway: Any) -> bool:
            if isinstance(highway, list):
                return any(h in highway_principales for h in highway)
            return highway in highway_principales

        vistas: set[frozenset[int]] = set()
        resultado: list[list[tuple[float, float]]] = []
        nodos = self.grafo.nodes

        for u, v, data in self.grafo.edges(data=True):
            highway = data.get("highway")
            if not _es_principal(highway):
                continue

            clave = frozenset({int(u), int(v)})
            if clave in vistas:
                continue
            vistas.add(clave)

            try:
                lat_u, lon_u = float(nodos[u]["y"]), float(nodos[u]["x"])
                lat_v, lon_v = float(nodos[v]["y"]), float(nodos[v]["x"])
            except (KeyError, TypeError):
                continue

            resultado.append([(lat_u, lon_u), (lat_v, lon_v)])

        return resultado

    def _vertices_latlon(self, u: int, v: int, data: Any) -> list[tuple[float, float]]:
        """Vértices ``(lat, lon)`` de la arista, en orden ``u → v``.

        Usa la geometría curva ``geometry`` (LineString OSMnx en orden
        ``(lon, lat)``) si está presente; si no, devuelve el segmento recto
        entre los endpoints.
        """
        geom = data.get("geometry")
        if geom is not None:
            return [(float(la), float(lo)) for lo, la in geom.coords]
        nodos = self.grafo.nodes
        return [
            (float(nodos[u]["y"]), float(nodos[u]["x"])),
            (float(nodos[v]["y"]), float(nodos[v]["x"])),
        ]
