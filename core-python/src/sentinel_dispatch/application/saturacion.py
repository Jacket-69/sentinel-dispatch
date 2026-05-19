"""Detección de saturación de flota (SRS sec. 2.7 RN-08, CP-10).

Implementa **RF-10**: dada una flota completa con sus estados y
opcionalmente el progreso de las unidades EnRuta, determina si el
sistema está saturado (no hay Disponibles) y lista las candidatas a
re-dirección manual ordenadas por progreso ascendente.

La saturación de capacidad detectada acá es ortogonal a la "saturación
de idoneidad" que :func:`domain.dispatch.seleccionar_unidad` reporta
cuando todas las Disponibles tienen costo ``inf`` (Echo/Delta + flota
solo Básica). Aquella se maneja con el fallback RN-02 en
:mod:`despachar_ambulancia`; ésta no tiene fallback automático — el
operador debe decidir si redirigir una EnRuta o esperar a que se
libere alguna unidad.

Fuente normativa: SRS sec. 2.7 RN-08, sec. 2.13 CP-10. Decisión
arquitectónica: ADR-0014 §"Separación dominio/aplicación" + ADR-0015.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sentinel_dispatch.application.tipos import (
    CandidataRedireccion,
    EstadoSaturacion,
)
from sentinel_dispatch.domain.dispatch.tipos import EstadoUnidad

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sentinel_dispatch.domain.dispatch.tipos import Unidad


def detectar_saturacion(
    flota: Iterable[Unidad],
    progreso_por_unidad: Mapping[str, float] | None = None,
) -> EstadoSaturacion:
    """Detecta saturación de flota y lista candidatas a re-dirección.

    Args:
        flota: la flota completa a evaluar (cualquier estado).
        progreso_por_unidad: mapeo ``unidad.id -> progreso_pct`` para
            las unidades en estado EnRuta. Las unidades EnRuta sin
            entrada en este mapeo se incluyen con ``progreso_pct=0.0``
            (asunción conservadora: recién partieron, son las más
            redirigibles). Pasar ``None`` equivale a un mapeo vacío.

    Returns:
        :class:`EstadoSaturacion`. ``saturada`` es ``True`` si y solo
        si no existe ninguna unidad en estado ``DISPONIBLE`` en la
        flota. Cuando hay saturación, ``candidatas_redireccion`` trae
        las unidades EnRuta ordenadas por ``progreso_pct`` ascendente
        (las que recién partieron primero, RN-06 §"costo emocional");
        ante empate de progreso, desempate lexicográfico por
        ``unidad.id``. Cuando no hay saturación,
        ``candidatas_redireccion`` es la tupla vacía — no se calcula
        nada si la flota no lo necesita.
    """
    progreso = dict(progreso_por_unidad or {})
    lista = list(flota)

    hay_disponible = any(u.estado is EstadoUnidad.DISPONIBLE for u in lista)
    if hay_disponible:
        return EstadoSaturacion(saturada=False, candidatas_redireccion=())

    enrutas = [u for u in lista if u.estado is EstadoUnidad.EN_RUTA]
    candidatas = [
        CandidataRedireccion(unidad=u, progreso_pct=progreso.get(u.id, 0.0)) for u in enrutas
    ]
    candidatas.sort(key=lambda c: (c.progreso_pct, c.unidad.id))

    return EstadoSaturacion(saturada=True, candidatas_redireccion=tuple(candidatas))
