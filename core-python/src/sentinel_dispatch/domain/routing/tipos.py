"""Tipos del dominio de routing.

Define el identificador de nodo, la estructura de arista y las excepciones
del dominio. Todo es lógica pura: no importa frameworks, no hace I/O y no
conoce OSMnx ni NetworkX.

Fuente normativa: SRS sec. 2.6-B (Ruteo A*) y ADR-0010 (Routing A* sobre OSM
+ estrategia de validación con OSRM oracle).
"""

from __future__ import annotations

from dataclasses import dataclass

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


class NoRutaDisponibleError(Exception):
    """No existe camino entre origen y destino en el grafo vial.

    Lanzada por :func:`a_estrella` cuando el destino no es alcanzable
    desde el origen. Casos típicos: nodos en componentes disjuntos,
    destino fuera del bbox cargado, errores de snap.
    """


class NodoFueraDeRangoError(Exception):
    """Coordenadas fuera del área de cobertura del grafo cargado.

    Aplicación de RN-01 del SRS (rango IV Región) detectada en el borde,
    antes de invocar :class:`GrafoVial.nodo_mas_cercano`.
    """
