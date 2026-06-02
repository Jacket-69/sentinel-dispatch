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

    from sentinel_dispatch.domain.routing.tipos import (
        Arista,
        NodoId,
        PosicionEnArista,
    )


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


class GrafoVialConSnapEdge(GrafoVial, Protocol):
    """Extensión opcional de :class:`GrafoVial` con snap-to-edge (ADR-0020).

    Agrega :meth:`posicion_en_arista` sin tocar el contrato base: los adapters
    y fakes que solo implementan :class:`GrafoVial` siguen siendo válidos para
    el A* operativo. Únicamente el camino experimental de calibración CP-01c
    (:mod:`a_estrella_snap_edge`) exige esta capacidad extendida.

    Esta separación preserva la paridad bit-exacta RT-02 (ADR-0008/0017): el
    A* operativo y ``run-dataset`` no conocen snap-to-edge, solo el test de
    calibración lo usa. Ver ADR-0020 §"Paridad RT-02 tras snap-to-edge".
    """

    def posicion_en_arista(self, lat: float, lon: float) -> PosicionEnArista:
        """Proyecta una coordenada arbitraria sobre la arista vial más cercana.

        Snap-to-edge: en lugar de saltar al nodo OSM más cercano
        (:meth:`nodo_mas_cercano`), proyecta el punto sobre la geometría de la
        arista más próxima y reporta la posición a lo largo de ella. Aplicado
        en el borde antes de invocar :func:`a_estrella_snap_edge`.

        Returns:
            :class:`PosicionEnArista` con la arista, la fracción ``[0, 1]``
            desde su origen, el punto proyectado y la distancia de snap.

        Raises:
            NodoFueraDeRangoError: si ``(lat, lon)`` cae fuera del bbox de
                cobertura (RN-01), igual que :meth:`nodo_mas_cercano`.
        """
        ...
