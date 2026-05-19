"""Value objects de la capa application — orquestación de despacho.

Estructuras que el orquestador (:mod:`despachar_ambulancia`) y el
detector de saturación (:mod:`saturacion`) producen como salida. La
capa application no inventa lógica de dominio: combina las piezas de
:mod:`domain.dispatch`, :mod:`domain.routing` y :mod:`domain.triaje`.

Fuente normativa: SRS sec. 2.6-D / 2.6-E (orquestación), 2.7 RN-02
(despacho sub-óptimo), RN-08 (saturación). Decisión arquitectónica:
ADR-0015 (separación dominio/política operativa).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentinel_dispatch.domain.dispatch.seleccion import CandidatoDespacho
    from sentinel_dispatch.domain.dispatch.tipos import (
        CostoDespacho,
        Incidente,
        Unidad,
    )


class MotivoDespacho(StrEnum):
    """Razón por la que :func:`despachar` retornó este resultado.

    Útil para el log JSONL (RF-06, ADR-0007), la auditoría académica y
    para que el operador entienda el camino tomado por el algoritmo.

    - ``OPTIMO``: unidad seleccionada por argmin con costo finito y
      penalización 0 (combinación ideal MPDS × Tipo).
    - ``PENALIZADO``: la elegida tiene penalización > 0 finita (Charlie
      + Básica). La idoneidad no es ideal pero el costo total sigue
      siendo el mínimo de la flota.
    - ``SUBOPTIMO_RN02``: fallback RN-02 — la idoneidad ideal es ∞
      (Echo/Delta + Básica) pero la única Disponible es Básica; se
      despacha con flag ``despacho_suboptimo`` para no bloquear el
      servicio. Decisión arquitectónica documentada en ADR-0015.
    - ``SATURACION``: no hay unidad Disponible elegible. No se genera
      despacho; el orquestador retorna candidatas EnRuta para que el
      operador evalúe redireccionar manualmente (RN-08, CP-10).
    """

    OPTIMO = "optimo"
    PENALIZADO = "penalizado"
    SUBOPTIMO_RN02 = "suboptimo_rn02"
    SATURACION = "saturacion"


@dataclass(frozen=True, slots=True)
class CandidataRedireccion:
    """Unidad EnRuta candidata a re-dirección en caso de saturación (RN-08).

    Inmutable. Las candidatas se ordenan por ``progreso_pct`` ascendente
    para que el operador vea primero las que recién partieron — son las
    menos costosas operativa y emocionalmente de redirigir (RN-06 §"el
    paciente ya escucha la sirena llegando").

    Atributos:
        unidad: móvil SAMU actualmente en estado EnRuta.
        progreso_pct: fracción del trayecto recorrido en ``[0.0, 1.0]``.
            Calculado por el caller con el reloj del sistema.
    """

    unidad: Unidad
    progreso_pct: float


@dataclass(frozen=True, slots=True)
class EstadoSaturacion:
    """Resultado de :func:`detectar_saturacion` (RN-08, CP-10).

    Inmutable.

    Atributos:
        saturada: ``True`` si no existe ninguna unidad en estado
            DISPONIBLE en la flota evaluada. Coincide con "ninguna
            unidad disponible" del SRS sec. 2.7 RN-08.
        candidatas_redireccion: tupla con las unidades EnRuta ordenadas
            por ``progreso_pct`` ascendente. Vacía cuando ``saturada``
            es ``False`` (no se calculan candidatas si hay flota libre).
    """

    saturada: bool
    candidatas_redireccion: tuple[CandidataRedireccion, ...]


@dataclass(frozen=True, slots=True)
class ResultadoDespacho:
    """Salida del orquestador :func:`despachar` — todo lo necesario para
    persistir el log (RF-06) y mostrarle al operador qué hizo el sistema.

    Inmutable. Cuando ``motivo == SATURACION``, ``elegida`` es ``None``,
    ``costo_elegida`` es ``None`` y ``saturacion`` trae las candidatas
    de re-dirección. En el resto de los casos, ``elegida`` y
    ``costo_elegida`` están poblados y ``saturacion`` puede ser ``None``.

    Atributos:
        incidente: el incidente despachado (o intentado despachar).
        elegida: unidad seleccionada por el ``argmin``, o ``None`` si
            el sistema reportó saturación.
        costo_elegida: :class:`CostoDespacho` de la ganadora, o ``None``.
        motivo: :class:`MotivoDespacho` explicando por qué este
            resultado y no otro. Determina si ``despacho_suboptimo`` se
            marca en el log.
        despacho_suboptimo: ``True`` solo cuando ``motivo`` es
            ``SUBOPTIMO_RN02``. Campo dedicado para que el log JSONL
            (RF-06) lo persista bit-exacto sin re-derivarlo del
            ``motivo`` en cada lectura.
        candidatos: tupla con todos los :class:`CandidatoDespacho`
            evaluados por el ``argmin``, ordenados por ``(costo, id)``.
            Útil para auditoría académica (defensa CP-04 / CP-11).
        saturacion: :class:`EstadoSaturacion` cuando ``motivo`` es
            ``SATURACION``, o ``None``. Contiene las candidatas EnRuta
            que el operador puede redirigir manualmente (CP-10).
        ruta_nodos: tupla de IDs de nodo OSMnx que el A* encontró para
            la unidad **elegida** (no para todas las candidatas
            evaluadas, solo la ganadora). Vacía cuando
            ``motivo == SATURACION`` (no hay ganadora) o cuando la
            unidad elegida no tiene ruta disponible. Los IDs son los
            mismos ``int`` que retorna :func:`a_estrella`; la
            serialización a string para JSONL ocurre en la capa de
            interfaz (ADR-0017 §ruta).
    """

    incidente: Incidente
    elegida: Unidad | None
    costo_elegida: CostoDespacho | None
    motivo: MotivoDespacho
    despacho_suboptimo: bool
    candidatos: tuple[CandidatoDespacho, ...]
    saturacion: EstadoSaturacion | None
    ruta_nodos: tuple[int, ...] = ()
