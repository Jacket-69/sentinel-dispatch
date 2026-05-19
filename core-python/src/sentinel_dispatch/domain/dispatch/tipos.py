"""Tipos del dominio de dispatch.

Define las entities y value objects que la lógica de dispatch consume:
:class:`Unidad` (móvil SAMU con base, tipo y estado), :class:`Incidente`
(evento ya triado con categoría MPDS y coordenadas validadas) y los
value objects asociados a la función de costo (:class:`CostoDespacho`).

Todo es lógica pura: no importa frameworks ni I/O. El dominio de
dispatch no conoce el adapter de routing (`OsmnxGrafoVial`) ni el
repositorio de unidades — recibe ``T_viaje`` ya calculado por el caller.

Fuente normativa: SRS sec. 2.5 (Tipos de Unidad), 2.6-C (Función de
Costo), 2.7 (Reglas de Negocio RN-01..RN-10). Decisión arquitectónica:
ADR-0014 (ubicación de la fórmula del costo y separación dominio /
fallback RN-02).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS


class TipoUnidad(StrEnum):
    """Tipo de móvil SAMU según capacidad de soporte vital.

    Referencia: SRS sec. 2.5 (Tipos de Unidad). El mapeo a la realidad
    SAMU Chile se documenta en la tabla del SRS y en ADR-0009.

    - **AVANZADA** (ALS — Advanced Life Support): paramédico + médico
      tripulante, equipamiento para soporte vital avanzado. Apta para
      todas las categorías MPDS (Alpha..Echo).
    - **BASICA** (BLS — Basic Life Support): tripulación TENS sin
      capacidades ALS. Apta para Alpha/Bravo sin penalización;
      penalizada para Charlie; excluida (penalización ∞) para Delta/Echo.
    """

    AVANZADA = "Avanzada"
    BASICA = "Básica"


class EstadoUnidad(StrEnum):
    """Estado operativo del móvil SAMU.

    Referencia: SRS sec. 2.5 + RN-04. La unidad en ``TALLER`` está
    excluida del cálculo bajo cualquier circunstancia (RN-04).

    Transiciones válidas (FSM, no enforced aquí — vive en application/):

    - ``DISPONIBLE``  → ``EN_RUTA`` (despacho confirmado).
    - ``EN_RUTA``     → ``EN_ESCENA`` (llegada al incidente) ó
                        ``EN_RUTA`` (re-despacho RN-06) ó
                        ``DISPONIBLE`` (cancelación).
    - ``EN_ESCENA``   → ``EN_RUTA`` (traslado a hospital) ó
                        ``DISPONIBLE`` (finalización in-situ).
    - ``TALLER``      → ``DISPONIBLE`` (alta de mantención).
    """

    DISPONIBLE = "Disponible"
    EN_RUTA = "EnRuta"
    EN_ESCENA = "EnEscena"
    TALLER = "Taller"


@dataclass(frozen=True, slots=True)
class Unidad:
    """Móvil SAMU con base, tipo y estado actual.

    Inmutable. Las transiciones de estado se modelan como reemplazo del
    value object (``dataclasses.replace``) en el application layer, no
    como mutación in-situ.

    Atributos:
        id: identificador único (``"U01"``..``"U10"`` en el dataset H1).
            Se compara lexicográficamente para el desempate del CP-11.
        patente: matrícula del vehículo (``"AMB-001"``..). Sin uso
            algorítmico; presente por trazabilidad operativa.
        tipo: :class:`TipoUnidad` (Avanzada o Básica). Entra en la
            función de costo vía la tabla de penalización de idoneidad.
        base_nombre: nombre legible del hospital de base.
        base_lat, base_lon: coordenadas de la base SAMU en EPSG:4326.
            Validadas por ``domain.incidente.validar_coordenadas_iv_region``
            en el adapter de carga (no aquí).
        estado: :class:`EstadoUnidad`. ``TALLER`` excluye del cálculo
            por RN-04.
    """

    id: str
    patente: str
    tipo: TipoUnidad
    base_nombre: str
    base_lat: float
    base_lon: float
    estado: EstadoUnidad


@dataclass(frozen=True, slots=True)
class Incidente:
    """Evento médico ya triado, listo para entrar al despacho.

    Inmutable. Combina la coordenada validada (RN-01) con el resultado
    del árbol de triaje (categoría MPDS) y el identificador del evento.

    Atributos:
        id: identificador único (``"I-01"``..``"I-12"`` en el dataset H1).
        lat, lon: coordenadas EPSG:4326 del incidente; ya validadas por
            ``validar_coordenadas_iv_region`` antes de construir este
            objeto.
        categoria_mpds: salida del árbol MPDS (Alpha..Echo). Entra en la
            función de costo vía la tabla de penalización de idoneidad.
        timestamp_iso: marca temporal ISO 8601 con offset (``"...-04:00"``)
            tal como aparece en el dataset. Opaco para el dominio
            dispatch — el cálculo de progreso de trayecto (RN-06) vive
            en application/ donde se compara con ``ahora()``.
    """

    id: str
    lat: float
    lon: float
    categoria_mpds: CategoriaMPDS
    timestamp_iso: str


@dataclass(frozen=True, slots=True)
class CostoDespacho:
    """Resultado de la función de costo, con desglose para auditoría.

    Inmutable. ``valor_total_s`` es el número que entra al ``argmin``
    de la selección; los demás campos sirven para el log JSONL (RF-06,
    ADR-0007) y para la defensa académica (CP-04, CP-05).

    Atributos:
        valor_total_s: ``α · T_viaje + β · Penalización_Idoneidad``,
            en segundos. ``math.inf`` cuando la combinación
            categoría × tipo está prohibida (Echo/Delta + Básica, RN-02).
        t_viaje_s: tiempo de viaje del A* (sin factores dinámicos
            multiplicados), en segundos. Proviene del routing.
        penalizacion: valor de la tabla de idoneidad (0.0, 1.0, ó
            ``math.inf``). Antes de multiplicar por ``β``.
        es_infinito: cache booleano de ``math.isinf(valor_total_s)``.
            Evita re-comparar floats en el ``argmin`` y deja explícito
            el caso "unidad excluida".
    """

    valor_total_s: float
    t_viaje_s: float
    penalizacion: float
    es_infinito: bool
