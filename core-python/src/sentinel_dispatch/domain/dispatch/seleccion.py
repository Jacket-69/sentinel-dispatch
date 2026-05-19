"""Selección óptima de unidad por ``argmin_u Costo(u, i)`` (SRS sec. 2.6-D).

Implementa **RF-05**: dada una flota de unidades disponibles y un
incidente triado, computa el costo de cada unidad y selecciona la de
costo mínimo. Ante empate de costo, **desempata lexicográficamente por
``unidad.id`` ascendente** (CP-11).

Convención de input:

- El caller pasa la flota ya filtrada por estado (Disponibles + EnRuta
  según contexto). El filtrado por RN-04 (Taller) lo refuerza el dominio
  vía :exc:`UnidadInelegibleError` en :func:`costo`; aquí lo respetamos
  silenciosamente excluyendo Taller del cálculo en lugar de propagar la
  excepción — la función está diseñada para evaluar flotas completas
  donde una Taller no debería abortar todo el cálculo.
- Los tiempos de viaje vienen pre-calculados por el caller (snap + A*)
  en un ``Mapping[str, float]`` de ``unidad.id -> t_viaje_s``. El
  dominio dispatch no conoce el adapter de routing (ADR-0014 D3).

Cuando ninguna unidad tiene costo finito (todas son ``inf`` por
penalización ∞, o la flota está vacía / toda en Taller),
:class:`ResultadoSeleccion.elegida` es ``None``. La detección de
saturación y la política de fallback RN-02 (despacho_suboptimo) viven
en ``application/`` (PR siguiente, ADR-0015).

Fuente normativa: SRS sec. 2.6-D (función de selección), 2.13 CP-04,
CP-05, CP-11. Decisión arquitectónica: ADR-0014.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sentinel_dispatch.domain.dispatch.funcion_costo import costo
from sentinel_dispatch.domain.dispatch.tipos import (
    CostoDespacho,
    EstadoUnidad,
    Incidente,
    Unidad,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class CandidatoDespacho:
    """Tupla (unidad, t_viaje, costo) usada para auditar la selección.

    Inmutable. Una lista de :class:`CandidatoDespacho` permite al
    application layer registrar en el log JSONL (RF-06, ADR-0007) todas
    las unidades evaluadas y su costo asociado, no solo la elegida.

    Atributos:
        unidad: la unidad evaluada.
        t_viaje_s: tiempo de viaje del A* hacia el incidente. Mismo
            valor que entró al cálculo del costo.
        costo: :class:`CostoDespacho` con el desglose
            (``valor_total_s``, ``penalizacion``, ``es_infinito``).
    """

    unidad: Unidad
    t_viaje_s: float
    costo: CostoDespacho


@dataclass(frozen=True, slots=True)
class ResultadoSeleccion:
    """Salida de :func:`seleccionar_unidad`.

    Inmutable. ``elegida`` es ``None`` cuando ninguna unidad tiene costo
    finito (saturación de idoneidad, no de capacidad — saturación de
    capacidad la detecta ``application/saturacion.py`` con RN-08).

    Atributos:
        elegida: unidad ganadora del ``argmin``, o ``None``.
        costo_elegida: :class:`CostoDespacho` de la ganadora, o ``None``.
        candidatos: tupla con **todos** los :class:`CandidatoDespacho`
            evaluados, ordenados por ``(valor_total_s, unidad.id)``
            ascendente. Incluye los descartados con costo ``inf`` al
            final, en orden lexicográfico, para que el log refleje la
            flota completa.
    """

    elegida: Unidad | None
    costo_elegida: CostoDespacho | None
    candidatos: tuple[CandidatoDespacho, ...]


def _orden_candidato(c: CandidatoDespacho) -> tuple[float, str]:
    """Clave de ordenamiento: costo asc, luego ``unidad.id`` lex asc (CP-11)."""
    return (c.costo.valor_total_s, c.unidad.id)


def seleccionar_unidad(
    unidades: Iterable[Unidad],
    incidente: Incidente,
    tiempos_viaje: Mapping[str, float],
) -> ResultadoSeleccion:
    """Selecciona la unidad de menor costo para el incidente (RF-05).

    Args:
        unidades: flota a evaluar. Las que estén en estado
            ``EstadoUnidad.TALLER`` se excluyen silenciosamente (RN-04).
            Las que no tengan entrada en ``tiempos_viaje`` también se
            excluyen — el caller es responsable de proveer t_viaje para
            todas las unidades que quiere evaluar.
        incidente: evento triado con :class:`CategoriaMPDS`.
        tiempos_viaje: mapeo ``unidad.id -> t_viaje_s`` en segundos.
            Valor ``math.inf`` se acepta y resulta en costo ``inf``
            (semántica "sin ruta", igual que en :func:`costo`).

    Returns:
        :class:`ResultadoSeleccion`. ``elegida`` es ``None`` cuando
        todos los candidatos finitos están excluidos (todas las
        unidades tienen costo ``inf``, o no hay unidades elegibles).
        Los empates de costo finito se desempatan por
        ``unidad.id`` lexicográfico ascendente (CP-11).
    """
    candidatos: list[CandidatoDespacho] = []
    for unidad in unidades:
        if unidad.estado is EstadoUnidad.TALLER:
            continue
        t = tiempos_viaje.get(unidad.id)
        if t is None:
            continue
        c = costo(unidad, incidente, t)
        candidatos.append(CandidatoDespacho(unidad=unidad, t_viaje_s=t, costo=c))

    candidatos.sort(key=_orden_candidato)
    candidatos_t = tuple(candidatos)

    primera_finita = next((c for c in candidatos_t if not c.costo.es_infinito), None)
    if primera_finita is None:
        return ResultadoSeleccion(elegida=None, costo_elegida=None, candidatos=candidatos_t)

    return ResultadoSeleccion(
        elegida=primera_finita.unidad,
        costo_elegida=primera_finita.costo,
        candidatos=candidatos_t,
    )


def hay_cobertura_alternativa(
    unidad_excluida: Unidad,
    incidente: Incidente,
    flota_disponible: Iterable[Unidad],
    tiempos_viaje: Mapping[str, float],
) -> bool:
    """¿Existe alguna unidad ≠ ``unidad_excluida`` con costo finito para ``incidente``?

    Usado por :mod:`redespacho` para evaluar la tercera condición de
    RN-06: re-despachar a ``unidad_excluida`` hacia un incidente nuevo
    solo si el incidente actual queda cubierto por *otra* unidad de la
    flota disponible.

    Args:
        unidad_excluida: la unidad cuyo re-despacho se está evaluando.
            Se excluye de los candidatos.
        incidente: el incidente que **debe quedar cubierto**.
        flota_disponible: candidatas alternativas (estado
            ``DISPONIBLE`` típicamente; Taller queda excluida por
            :func:`seleccionar_unidad`).
        tiempos_viaje: mapeo ``id -> t_viaje_s`` para las candidatas
            hacia ``incidente``.

    Returns:
        ``True`` si al menos una unidad distinta de ``unidad_excluida``
        tiene costo finito para ``incidente``.
    """
    candidatas = [u for u in flota_disponible if u.id != unidad_excluida.id]
    resultado = seleccionar_unidad(candidatas, incidente, tiempos_viaje)
    return resultado.elegida is not None and not math.isinf(
        resultado.costo_elegida.valor_total_s if resultado.costo_elegida else math.inf
    )
