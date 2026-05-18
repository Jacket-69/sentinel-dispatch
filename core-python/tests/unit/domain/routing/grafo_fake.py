"""Fake in-memory de GrafoVial para tests del A*."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sentinel_dispatch.domain.routing.heuristica import haversine_m
from sentinel_dispatch.domain.routing.tipos import Arista, NodoFueraDeRangoError, NodoId

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass
class GrafoFake:
    """Grafo dirigido in-memory para tests. Implementa GrafoVial estructuralmente."""

    coords: dict[NodoId, tuple[float, float]] = field(default_factory=dict)
    _aristas: dict[NodoId, list[Arista]] = field(default_factory=dict)

    def agregar_nodo(self, nodo: NodoId, lat: float, lon: float) -> None:
        """Registra un nodo con sus coordenadas geográficas."""
        self.coords[nodo] = (lat, lon)
        self._aristas.setdefault(nodo, [])

    def agregar_arista(
        self,
        origen: NodoId,
        destino: NodoId,
        longitud_m: float,
        velocidad_kmh: float,
    ) -> None:
        """Agrega una arista dirigida entre dos nodos."""
        self._aristas.setdefault(origen, []).append(
            Arista(
                origen=origen,
                destino=destino,
                longitud_m=longitud_m,
                velocidad_efectiva_kmh=velocidad_kmh,
            )
        )

    def vecinos(self, nodo: NodoId) -> Iterable[Arista]:
        """Retorna las aristas salientes del nodo dado."""
        return iter(self._aristas.get(nodo, []))

    def coordenadas(self, nodo: NodoId) -> tuple[float, float]:
        """Retorna (lat, lon) del nodo."""
        return self.coords[nodo]

    def nodo_mas_cercano(self, lat: float, lon: float) -> NodoId:
        """Snap brute-force al nodo con coordenadas más cercanas."""
        if not self.coords:
            raise NodoFueraDeRangoError("grafo vacío")
        return min(self.coords, key=lambda n: haversine_m(lat, lon, *self.coords[n]))

    def distancia_snap_m(self, lat: float, lon: float, nodo: NodoId) -> float:
        """Distancia en metros entre la coordenada y el nodo."""
        return haversine_m(lat, lon, *self.coords[nodo])
