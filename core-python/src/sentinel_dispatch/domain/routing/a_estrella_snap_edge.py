"""A* con snap-to-edge: origen y destino en mitad de arista (ADR-0020 §3b).

El A* normal enruta entre nodos del grafo; el snap-to-node fuerza a saltar
origen y destino al nodo OSM más cercano antes de enrutar, lo que en pares
cortos introduce un sesgo grande en ``duration`` frente a OSRM (~68 % de la
dispersión, ADR-0011 §Diagnóstico). OSRM proyecta el punto sobre la arista y
arranca en mitad de calle; este módulo replica ese comportamiento.

Estrategia: en vez de reescribir el A*, se envuelve el grafo en
:class:`_GrafoConPuntosVirtuales`, que inyecta dos nodos virtuales —origen
``-1`` y destino ``-2``— conectados a los endpoints de sus respectivas
aristas snapeadas con los tramos *truncados* (la fracción de arista que
queda entre el punto proyectado y cada endpoint). Sobre ese grafo aumentado
se corre :func:`a_estrella_calibrado` sin modificarlo, heredando turn penalty
y heurística admisible.

**Aislamiento de producción**: igual que :mod:`a_estrella_calibrado`, este
módulo NO se usa en el orquestador operativo ni en ``run-dataset``. Vive solo
para el camino de calibración CP-01c, preservando la paridad bit-exacta
Java↔Python de RT-02 (ADR-0008/0017/0020).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sentinel_dispatch.domain.routing.a_estrella_calibrado import a_estrella_calibrado
from sentinel_dispatch.domain.routing.tipos import Arista, NodoId

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial
    from sentinel_dispatch.domain.routing.tipos import PosicionEnArista

NODO_ORIGEN_VIRTUAL: NodoId = -1
"""Id del nodo virtual de origen inyectado por el decorador."""

NODO_DESTINO_VIRTUAL: NodoId = -2
"""Id del nodo virtual de destino inyectado por el decorador."""


def _arista_reversa(grafo: GrafoVial, a: NodoId, b: NodoId) -> Arista | None:
    """Arista dirigida ``a → b`` de menor longitud, o ``None`` si no existe.

    Sirve para saber si una calle es transitable en sentido inverso (en la
    representación dirigida de OSMnx, una calle bidireccional son dos aristas
    opuestas; una one-way, solo una). Solo usa el contrato :class:`GrafoVial`.
    """
    candidatas = [ar for ar in grafo.vecinos(a) if ar.destino == b]
    if not candidatas:
        return None
    return min(candidatas, key=lambda ar: ar.longitud_m)


class _GrafoConPuntosVirtuales:
    """Decorador de :class:`GrafoVial` con nodos virtuales origen/destino.

    Envuelve un grafo base y expone el contrato :class:`GrafoVial` extendido
    con dos nodos virtuales situados en mitad de sus aristas snapeadas. Para
    los nodos reales delega íntegramente en el grafo base, añadiendo solo las
    aristas virtuales hacia el destino donde corresponde.

    Las aristas virtuales codifican su costo a través de ``longitud_m`` y
    ``velocidad_efectiva_kmh`` reales del tramo truncado: el A* calcula el
    tiempo con la misma fórmula que para cualquier arista, así que no hay
    costos "mágicos" inyectados fuera del modelo.
    """

    def __init__(
        self,
        grafo: GrafoVial,
        pos_origen: PosicionEnArista,
        pos_destino: PosicionEnArista,
    ) -> None:
        self._grafo = grafo
        self._pos_origen = pos_origen
        self._pos_destino = pos_destino

        self._u_origen = pos_origen.arista.origen
        self._v_origen = pos_origen.arista.destino
        self._u_destino = pos_destino.arista.origen
        self._v_destino = pos_destino.arista.destino

        self._aristas_origen = self._construir_aristas_origen()
        self._aristas_destino_por_nodo = self._construir_aristas_destino()

    def _construir_aristas_origen(self) -> list[Arista]:
        """Aristas salientes del nodo virtual de origen (``-1``)."""
        f = self._pos_origen.fraccion
        arista = self._pos_origen.arista
        salientes: list[Arista] = []

        # Caso especial: origen y destino sobre la MISMA arista dirigida.
        # Si el destino está "más adelante" (f_destino >= f_origen) se puede
        # ir directo sin pasar por ningún endpoint.
        if (
            self._u_origen == self._u_destino
            and self._v_origen == self._v_destino
            and self._pos_destino.fraccion >= f
        ):
            tramo = (self._pos_destino.fraccion - f) * arista.longitud_m
            salientes.append(
                Arista(
                    origen=NODO_ORIGEN_VIRTUAL,
                    destino=NODO_DESTINO_VIRTUAL,
                    longitud_m=tramo,
                    velocidad_efectiva_kmh=arista.velocidad_efectiva_kmh,
                )
            )

        # Hacia adelante: O → v_origen, recorriendo (1 - f) de la arista.
        salientes.append(
            Arista(
                origen=NODO_ORIGEN_VIRTUAL,
                destino=self._v_origen,
                longitud_m=(1.0 - f) * arista.longitud_m,
                velocidad_efectiva_kmh=arista.velocidad_efectiva_kmh,
            )
        )

        # Hacia atrás: O → u_origen, solo si la calle admite el sentido
        # inverso (existe la arista v_origen → u_origen).
        reversa = _arista_reversa(self._grafo, self._v_origen, self._u_origen)
        if reversa is not None:
            salientes.append(
                Arista(
                    origen=NODO_ORIGEN_VIRTUAL,
                    destino=self._u_origen,
                    longitud_m=f * reversa.longitud_m,
                    velocidad_efectiva_kmh=reversa.velocidad_efectiva_kmh,
                )
            )

        return salientes

    def _construir_aristas_destino(self) -> dict[NodoId, Arista]:
        """Aristas virtuales hacia el destino (``-2``), indexadas por origen.

        Un nodo real puede llegar al destino virtual por dos vías: desde
        ``u_destino`` hacia adelante (recorriendo ``f`` de la arista) o desde
        ``v_destino`` hacia atrás (recorriendo ``1 - f``), esta última solo si
        la calle es bidireccional.
        """
        f = self._pos_destino.fraccion
        arista = self._pos_destino.arista
        por_nodo: dict[NodoId, Arista] = {}

        # Desde u_destino hacia adelante.
        por_nodo[self._u_destino] = Arista(
            origen=self._u_destino,
            destino=NODO_DESTINO_VIRTUAL,
            longitud_m=f * arista.longitud_m,
            velocidad_efectiva_kmh=arista.velocidad_efectiva_kmh,
        )

        # Desde v_destino hacia atrás, si existe la arista reversa.
        reversa = _arista_reversa(self._grafo, self._v_destino, self._u_destino)
        if reversa is not None:
            por_nodo[self._v_destino] = Arista(
                origen=self._v_destino,
                destino=NODO_DESTINO_VIRTUAL,
                longitud_m=(1.0 - f) * reversa.longitud_m,
                velocidad_efectiva_kmh=reversa.velocidad_efectiva_kmh,
            )

        return por_nodo

    def vecinos(self, nodo: NodoId) -> Iterable[Arista]:
        if nodo == NODO_ORIGEN_VIRTUAL:
            return list(self._aristas_origen)
        if nodo == NODO_DESTINO_VIRTUAL:
            return []
        salientes = list(self._grafo.vecinos(nodo))
        arista_destino = self._aristas_destino_por_nodo.get(nodo)
        if arista_destino is not None:
            salientes.append(arista_destino)
        return salientes

    def coordenadas(self, nodo: NodoId) -> tuple[float, float]:
        if nodo == NODO_ORIGEN_VIRTUAL:
            return (self._pos_origen.lat, self._pos_origen.lon)
        if nodo == NODO_DESTINO_VIRTUAL:
            return (self._pos_destino.lat, self._pos_destino.lon)
        return self._grafo.coordenadas(nodo)

    def nodo_mas_cercano(self, lat: float, lon: float) -> NodoId:
        return self._grafo.nodo_mas_cercano(lat, lon)

    def distancia_snap_m(self, lat: float, lon: float, nodo: NodoId) -> float:
        return self._grafo.distancia_snap_m(lat, lon, nodo)


def a_estrella_snap_edge(
    grafo: GrafoVial,
    pos_origen: PosicionEnArista,
    pos_destino: PosicionEnArista,
    *,
    factor_hora: float = 1.0,
    factor_sirena: float = 1.0,
    turn_penalty_s: float = 2.0,
    bearing_umbral_grados: float = 30.0,
) -> tuple[float, list[NodoId]]:
    """A* entre dos posiciones interpoladas sobre aristas (snap-to-edge).

    Construye el grafo con nodos virtuales y delega en
    :func:`a_estrella_calibrado`, heredando turn penalty y heurística.

    Returns:
        Tupla ``(eta_segundos, ruta)``. La ``ruta`` empieza en el nodo
        virtual ``-1`` y termina en ``-2``; los nodos intermedios son reales.

    Raises:
        NoRutaDisponibleError: si no existe camino entre las posiciones.
        ValueError: si algún factor es <= 0.
    """
    deco = _GrafoConPuntosVirtuales(grafo, pos_origen, pos_destino)
    return a_estrella_calibrado(
        deco,
        NODO_ORIGEN_VIRTUAL,
        NODO_DESTINO_VIRTUAL,
        factor_hora=factor_hora,
        factor_sirena=factor_sirena,
        turn_penalty_s=turn_penalty_s,
        bearing_umbral_grados=bearing_umbral_grados,
    )
