"""Re-despacho automático con confirmación humana (SRS sec. 2.6-E, RN-06).

Implementa **RF-08**: evalúa si una unidad en ruta hacia un incidente
puede ser **propuesta** para re-direccionar hacia un incidente nuevo de
mayor criticidad. La función NO ejecuta el re-despacho; emite una
:class:`PropuestaRedespacho` que el operador debe confirmar (RN-06
§"confirmación humana").

Condiciones de RN-06 (las tres deben cumplirse):

1. **Criticidad creciente**: ``incidente_nuevo.categoria_mpds >
   incidente_actual.categoria_mpds`` en el orden Alpha < Bravo <
   Charlie < Delta < Echo.
2. **Progreso ≤ 50%**: la unidad no ha recorrido más de la mitad del
   trayecto original. Más allá de eso, re-direccionar tiene costo
   operativo y emocional (paciente que ya escucha la sirena llegando).
3. **Cobertura alternativa**: existe al menos una unidad de la flota
   disponible (distinta de la actual) con costo finito hacia el
   incidente original. Sin reemplazo, no se re-direcciona — el
   incidente actual no puede quedar sin atención.

Convención de input: el caller pasa el ``progreso_pct`` ya calculado
(fracción ``[0.0, 1.0]``). El dominio dispatch no observa relojes ni
sabe cuándo se despachó la unidad; eso vive en ``application/`` con un
port :class:`RelojSistema` que llegará en PR siguiente.

Fuente normativa: SRS sec. 2.6-E (re-despacho), sec. 2.7 RN-06, sec.
2.13 CP-06 y CP-07. Decisión arquitectónica: ADR-0014.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sentinel_dispatch.domain.dispatch.seleccion import seleccionar_unidad

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sentinel_dispatch.domain.dispatch.seleccion import ResultadoSeleccion
    from sentinel_dispatch.domain.dispatch.tipos import Incidente, Unidad

UMBRAL_PROGRESO_MAXIMO: float = 0.50
"""Progreso máximo de la unidad para que el re-despacho proceda (RN-06).

Fracción del trayecto original recorrido, en ``[0.0, 1.0]``. Inclusivo:
una unidad exactamente al 50% sí puede ser re-direccionada. El umbral
proviene del SRS sec. 2.7 RN-06 y se documenta en ADR-0014.
"""


@dataclass(frozen=True, slots=True)
class PropuestaRedespacho:
    """Resultado de :func:`evaluar_redespacho` — propuesta, no ejecución.

    Inmutable. RN-06 §"confirmación humana": el dominio nunca confirma
    el re-despacho; el operador lo hace en ``interfaces/``.

    Atributos:
        procede: ``True`` si las tres condiciones de RN-06 se cumplen.
        razon: explicación humana del veredicto (en español). Útil para
            el log de auditoría y para mostrar al operador.
        unidad_a_redirigir: la unidad actualmente en ruta cuya
            re-dirección se propone. Misma que el input
            ``unidad_actual``. Se incluye para que el log JSONL sea
            autocontenido sin requerir join con otras tablas.
        unidad_de_reemplazo: la unidad que cubriría el ``incidente_actual``
            si la propuesta se acepta. Es el ganador del ``argmin`` sobre
            la flota disponible (sin contar ``unidad_a_redirigir``).
            ``None`` cuando ``procede`` es ``False`` y la causa del veto
            no involucra el reemplazo.
        incidente_actual: el incidente que la unidad estaba atendiendo.
        incidente_nuevo: el incidente de mayor criticidad que motiva la
            evaluación.
    """

    procede: bool
    razon: str
    unidad_a_redirigir: Unidad
    unidad_de_reemplazo: Unidad | None
    incidente_actual: Incidente
    incidente_nuevo: Incidente


def evaluar_redespacho(
    unidad_actual: Unidad,
    incidente_actual: Incidente,
    incidente_nuevo: Incidente,
    progreso_pct: float,
    flota_disponible: Iterable[Unidad],
    tiempos_viaje_al_incidente_actual: Mapping[str, float],
) -> PropuestaRedespacho:
    """Evalúa si proponer re-despacho de ``unidad_actual`` (RN-06).

    Args:
        unidad_actual: la unidad en ruta hacia ``incidente_actual``.
        incidente_actual: incidente que la unidad estaba atendiendo.
        incidente_nuevo: incidente de mayor criticidad propuesto.
        progreso_pct: fracción del trayecto original recorrido por
            ``unidad_actual`` en ``[0.0, 1.0]``. Calculado por
            ``application/`` con el reloj del sistema.
        flota_disponible: candidatas para cubrir ``incidente_actual``
            si la propuesta procede. ``unidad_actual`` debe estar
            **excluida** por el caller (típicamente porque está en
            estado ``EN_RUTA``, no ``DISPONIBLE``); si igual se cuela,
            :func:`seleccionar_unidad` la maneja correctamente vía la
            función auxiliar.
        tiempos_viaje_al_incidente_actual: mapeo ``unidad.id ->
            t_viaje_s`` para las candidatas hacia ``incidente_actual``.

    Returns:
        :class:`PropuestaRedespacho`. ``procede`` es ``True`` solo si
        las tres condiciones de RN-06 se cumplen. La cadena ``razon``
        describe el primer veredicto fallado en orden Criticidad →
        Progreso → Cobertura, para que el operador entienda el motivo
        sin tener que adivinar qué condición vetó.
    """
    if not (incidente_nuevo.categoria_mpds > incidente_actual.categoria_mpds):
        return PropuestaRedespacho(
            procede=False,
            razon=(
                f"Categoría nueva ({incidente_nuevo.categoria_mpds.value}) no es "
                f"mayor que la actual ({incidente_actual.categoria_mpds.value}); "
                "RN-06 condición 1 no se cumple."
            ),
            unidad_a_redirigir=unidad_actual,
            unidad_de_reemplazo=None,
            incidente_actual=incidente_actual,
            incidente_nuevo=incidente_nuevo,
        )

    if progreso_pct > UMBRAL_PROGRESO_MAXIMO:
        return PropuestaRedespacho(
            procede=False,
            razon=(
                f"Progreso={progreso_pct:.0%} > {UMBRAL_PROGRESO_MAXIMO:.0%}; "
                "RN-06 condición 2 no se cumple."
            ),
            unidad_a_redirigir=unidad_actual,
            unidad_de_reemplazo=None,
            incidente_actual=incidente_actual,
            incidente_nuevo=incidente_nuevo,
        )

    candidatas_reemplazo = [u for u in flota_disponible if u.id != unidad_actual.id]
    seleccion: ResultadoSeleccion = seleccionar_unidad(
        candidatas_reemplazo,
        incidente_actual,
        tiempos_viaje_al_incidente_actual,
    )
    if seleccion.elegida is None:
        return PropuestaRedespacho(
            procede=False,
            razon=(
                f"Sin cobertura alternativa para {incidente_actual.id}; "
                "RN-06 condición 3 no se cumple."
            ),
            unidad_a_redirigir=unidad_actual,
            unidad_de_reemplazo=None,
            incidente_actual=incidente_actual,
            incidente_nuevo=incidente_nuevo,
        )

    return PropuestaRedespacho(
        procede=True,
        razon=(
            f"Re-despacho propuesto: {unidad_actual.id} → {incidente_nuevo.id} "
            f"({incidente_nuevo.categoria_mpds.value}); "
            f"reemplazo para {incidente_actual.id}: {seleccion.elegida.id}; "
            f"progreso={progreso_pct:.0%}."
        ),
        unidad_a_redirigir=unidad_actual,
        unidad_de_reemplazo=seleccion.elegida,
        incidente_actual=incidente_actual,
        incidente_nuevo=incidente_nuevo,
    )
