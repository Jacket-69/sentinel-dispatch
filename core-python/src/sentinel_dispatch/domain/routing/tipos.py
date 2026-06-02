"""Tipos del dominio de routing.

Define el identificador de nodo, la estructura de arista y las excepciones
del dominio. Todo es lógica pura: no importa frameworks, no hace I/O y no
conoce OSMnx ni NetworkX.

Fuente normativa: SRS sec. 2.6-B (Ruteo A*) y ADR-0010 (Routing A* sobre OSM
+ estrategia de validación con OSRM oracle).
"""

from __future__ import annotations

from dataclasses import dataclass

from sentinel_dispatch.domain.incidente.validacion import CoordenadasFueraDeRangoError

NodoId = int
"""Identificador de nodo del grafo vial.

Alias de :class:`int` porque los IDs de nodo OSM son enteros de 64 bits.
El SRS los loggea como enteros en ``ruta_nodos`` (sec. 2.11). Un dataclass
o :class:`typing.NewType` no agrega semántica nueva: los nodos OSM no
tienen comportamiento, solo identidad numérica.
"""


@dataclass(frozen=True, slots=True)
class Arista:
    """Atributos de una arista del grafo vial relevantes para el A*.

    El A* consume aristas a través de :class:`GrafoVial.vecinos`. Los
    valores de ``velocidad_efectiva_kmh`` son el resultado del cascade
    descrito en ADR-0010 §2 (tag ``maxspeed`` de OSM si existe; sino
    default por ``highway`` type según tabla Chile). El dominio no
    convierte unidades hasta el cálculo de peso.

    Atributos:
        origen: nodo del que sale la arista.
        destino: nodo al que llega la arista.
        longitud_m: largo del segmento en metros.
        velocidad_efectiva_kmh: velocidad nominal de la arista en km/h,
            ya resuelta por el cascade. Sin factores dinámicos aplicados.
    """

    origen: NodoId
    destino: NodoId
    longitud_m: float
    velocidad_efectiva_kmh: float


@dataclass(frozen=True, slots=True)
class PosicionEnArista:
    """Proyección de una coordenada arbitraria sobre una arista del grafo.

    Resultado del snap-to-edge (ADR-0020 §H5-cal-3a): en lugar de saltar la
    coordenada al nodo OSM más cercano (snap-to-node), se proyecta sobre la
    arista vial más cercana y se registra *dónde* cae a lo largo de ella.
    OSRM hace exactamente esto; replicarlo elimina el ~68 % de la dispersión
    de ``duration`` atribuida a snap-to-node (ADR-0011 §Diagnóstico).

    El A* con snap-to-edge (:mod:`a_estrella_snap_edge`) usa ``fraccion`` para
    construir los tramos truncados de la arista (origen/destino en mitad de
    calle), reutilizando ``arista`` para conocer longitud y velocidad.

    Atributos:
        arista: la arista ``(origen → destino)`` sobre la que cae el punto,
            con su ``longitud_m`` y ``velocidad_efectiva_kmh`` ya resueltas.
        fraccion: posición a lo largo de la arista en ``[0.0, 1.0]``, medida
            desde ``arista.origen`` hacia ``arista.destino``. ``0.0`` = sobre
            el nodo origen; ``1.0`` = sobre el nodo destino.
        lat: latitud del punto proyectado (sobre la arista), en grados.
        lon: longitud del punto proyectado (sobre la arista), en grados.
        distancia_snap_m: distancia en metros entre la coordenada original y
            el punto proyectado. Análoga a :meth:`GrafoVial.distancia_snap_m`
            pero medida contra la arista, no contra un nodo (RN-09).
    """

    arista: Arista
    fraccion: float
    lat: float
    lon: float
    distancia_snap_m: float


class NoRutaDisponibleError(Exception):
    """No existe camino entre origen y destino en el grafo vial.

    Lanzada por :func:`a_estrella` cuando el destino no es alcanzable
    desde el origen. Casos típicos: nodos en componentes disjuntos,
    destino fuera del bbox cargado, errores de snap.
    """


class NodoFueraDeRangoError(CoordenadasFueraDeRangoError):
    """Coordenadas fuera del área de cobertura detectadas durante el snap.

    Subclase de :class:`CoordenadasFueraDeRangoError` (dominio incidente).
    Se conserva como tipo distinto para que los call-sites del adapter
    sigan capturando ``NodoFueraDeRangoError`` sin cambios, pero los
    handlers genéricos del borde (API/CLI) pueden capturar el padre.

    Acepta un mensaje libre porque también se lanza para el caso
    degenerado "grafo sin nodos", donde ``lat``/``lon`` no aplican; en
    ese caso ambos quedan como ``NaN``.
    """

    def __init__(
        self, mensaje: str, *, lat: float = float("nan"), lon: float = float("nan")
    ) -> None:
        Exception.__init__(self, mensaje)
        self.lat = lat
        self.lon = lon
