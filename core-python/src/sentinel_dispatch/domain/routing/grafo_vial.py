"""Puerto :class:`GrafoVial` (Ports & Adapters — ADR-0006, ADR-0010).

El módulo :mod:`domain.routing` depende únicamente de esta interfaz. Los
adapters concretos (:mod:`adapters.grafo_osmnx`, fakes de test) la
implementan. El A* puro recibe una instancia ``GrafoVial`` y nada más.

Lo que NO debe estar acá: imports de OSMnx/NetworkX/shapely, lectura de
archivos, conversión de unidades, cálculo de Haversine, estado mutable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sentinel_dispatch.domain.routing.tipos import Arista, NodoId


class GrafoVial(Protocol):
    """Vista de solo lectura sobre el grafo vial cargado.

    Métodos mínimos requeridos por el A* (SRS sec. 2.6-B) y por la regla
    de snap (RN-09 — alerta si el nodo más cercano está a > 500 m).
    """

    def vecinos(self, nodo: NodoId) -> Iterable[Arista]:
        """Aristas salientes del nodo dado.

        El A* itera sobre el resultado en cada expansión; debe ser
        idempotente y no efectuar I/O en cada llamada (cachear en el
        adapter si la fuente es lenta).
        """
        ...

    def coordenadas(self, nodo: NodoId) -> tuple[float, float]:
        """Coordenadas geográficas del nodo en grados decimales.

        Returns:
            ``(lat, lon)`` en EPSG:4326. Lat en ``[-90, 90]``, lon en
            ``[-180, 180]``. Para la conurbación La Serena-Coquimbo:
            lat ∈ ``[-30.5, -29.5]``, lon ∈ ``[-71.7, -70.5]``.
        """
        ...

    def nodo_mas_cercano(self, lat: float, lon: float) -> NodoId:
        """Snap de una coordenada arbitraria al nodo OSM más cercano.

        Aplicado en el borde de entrada (interfaces/cli o interfaces/api)
        antes de invocar :func:`a_estrella`. La política RN-09 exige
        alertar al operador si la distancia de snap supera 500 m; el
        valor numérico se obtiene con :meth:`distancia_snap_m`.
        """
        ...

    def distancia_snap_m(self, lat: float, lon: float, nodo: NodoId) -> float:
        """Distancia en metros entre la coordenada original y el nodo snapeado.

        Usada para implementar RN-09 (alerta si > 500 m). Convención:
        retorna 0.0 cuando el snap es exacto (coordenada coincide con
        nodo OSM); valores típicos en zona urbana 5-30 m.
        """
        ...
