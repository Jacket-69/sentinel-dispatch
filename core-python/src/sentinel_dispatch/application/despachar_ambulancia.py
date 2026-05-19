"""Orquestador de despacho de ambulancia (capa application).

Combina las piezas del dominio en un caso de uso end-to-end: dado un
incidente triado y una flota, calcula tiempos de viaje vía routing,
ejecuta la selección óptima (función de costo + ``argmin``), aplica el
fallback RN-02 cuando corresponde y reporta saturación cuando no hay
unidades elegibles.

**Lo que SÍ vive acá** (capa application — política operativa):

- Snap de origen (base de cada unidad) y destino (incidente) al grafo.
- Cálculo de ``T_viaje`` por unidad vía :func:`a_estrella`.
- Filtrado por estado: solo unidades ``DISPONIBLE`` entran al argmin.
- Política de fallback RN-02: si el argmin del dominio retorna
  ``elegida=None`` porque todas las Disponibles son Básicas para un
  incidente Echo/Delta, despachar igual con la Básica de menor
  ``T_viaje`` y marcar ``despacho_suboptimo=True``.
- Detección de saturación cuando no hay Disponibles (RN-08, vía
  :func:`detectar_saturacion`).

**Lo que NO vive acá** (dominio puro):

- Fórmula del costo (vive en :mod:`domain.dispatch.funcion_costo`).
- Tabla de penalización de idoneidad (ídem).
- Algoritmo A* (vive en :mod:`domain.routing.a_estrella`).
- Validación de coordenadas IV Región (vive en
  :mod:`domain.incidente.validacion`).

La separación está documentada en ADR-0014 y ADR-0015.

Fuente normativa: SRS sec. 2.5 (flujo principal), 2.6-C/D (costo y
selección), 2.7 RN-02 / RN-04 / RN-08, sec. 2.13 CP-04/05/10.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from sentinel_dispatch.application.saturacion import detectar_saturacion
from sentinel_dispatch.application.tipos import (
    MotivoDespacho,
    ResultadoDespacho,
)
from sentinel_dispatch.domain.dispatch.funcion_costo import costo
from sentinel_dispatch.domain.dispatch.seleccion import (
    CandidatoDespacho,
    seleccionar_unidad,
)
from sentinel_dispatch.domain.dispatch.tipos import (
    EstadoUnidad,
    TipoUnidad,
)
from sentinel_dispatch.domain.routing.a_estrella import a_estrella
from sentinel_dispatch.domain.routing.tipos import NoRutaDisponibleError
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sentinel_dispatch.application.tipos import EstadoSaturacion
    from sentinel_dispatch.domain.dispatch.tipos import Incidente, Unidad
    from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial


_CATEGORIAS_CRITICAS_RN02: frozenset[CategoriaMPDS] = frozenset(
    {CategoriaMPDS.ECHO, CategoriaMPDS.DELTA}
)
"""Categorías MPDS sobre las que opera el fallback RN-02.

Son las que la tabla de penalización marca como ``inf`` para Básica.
Coquí está la diferencia con el dominio: el dominio reporta ``inf``,
la política RN-02 decide qué hacer con ese ``inf`` cuando no hay
alternativa.
"""

_log = logging.getLogger(__name__)


def _calcular_tiempos_viaje(
    flota: Iterable[Unidad],
    incidente: Incidente,
    grafo: GrafoVial,
    factor_hora: float,
    factor_sirena: float,
) -> tuple[dict[str, float], dict[str, list[int]]]:
    """Calcula ``T_viaje`` y ruta de nodos desde la base de cada unidad hacia el incidente.

    Snap del incidente y de cada base. Las unidades en TALLER se omiten
    silenciosamente (RN-04). Si A* lanza :exc:`NoRutaDisponibleError`,
    el tiempo se registra como ``math.inf`` y la ruta queda ausente del
    dict ``rutas`` (semántica "sin ruta" del dominio dispatch). Esas
    unidades nunca son elegidas como ganadoras, por lo que la ausencia
    de ruta en ``rutas`` es segura.

    Returns:
        Tupla ``(tiempos, rutas)`` donde ``tiempos`` es un mapping
        ``unidad.id -> T_viaje_s`` y ``rutas`` es un mapping
        ``unidad.id -> lista de nodos`` para las unidades con ruta
        disponible.
    """
    nodo_incidente = grafo.nodo_mas_cercano(incidente.lat, incidente.lon)
    tiempos: dict[str, float] = {}
    rutas: dict[str, list[int]] = {}
    for unidad in flota:
        if unidad.estado is EstadoUnidad.TALLER:
            continue
        try:
            nodo_base = grafo.nodo_mas_cercano(unidad.base_lat, unidad.base_lon)
            eta_s, ruta_nodos = a_estrella(
                grafo,
                nodo_base,
                nodo_incidente,
                factor_hora=factor_hora,
                factor_sirena=factor_sirena,
            )
            tiempos[unidad.id] = eta_s
            rutas[unidad.id] = ruta_nodos
        except NoRutaDisponibleError:
            tiempos[unidad.id] = math.inf
    return tiempos, rutas


def _fallback_rn02_basica(
    disponibles: list[Unidad],
    incidente: Incidente,
    tiempos: Mapping[str, float],
) -> tuple[Unidad, CandidatoDespacho] | None:
    """Si aplica RN-02, elige la Básica disponible de menor ``T_viaje``.

    Returns:
        ``(unidad, candidato)`` con la Básica elegida y su costo
        recalculado con penalización temporal **artificial** (igual a
        Charlie+Básica = 1.0). Esto evita reportar costo ``inf`` en el
        log y permite comparar despachos sub-óptimos entre sí.
        ``None`` si el fallback no aplica (no hay Básicas Disponibles o
        ninguna tiene ``T_viaje`` finito).
    """
    if incidente.categoria_mpds not in _CATEGORIAS_CRITICAS_RN02:
        return None
    basicas = [u for u in disponibles if u.tipo is TipoUnidad.BASICA]
    if not basicas:
        return None
    basicas_con_ruta = [
        (u, tiempos[u.id]) for u in basicas if u.id in tiempos and math.isfinite(tiempos[u.id])
    ]
    if not basicas_con_ruta:
        return None
    basicas_con_ruta.sort(key=lambda x: (x[1], x[0].id))
    unidad_elegida, t_viaje = basicas_con_ruta[0]

    costo_real = costo(unidad_elegida, incidente, t_viaje)
    return unidad_elegida, CandidatoDespacho(
        unidad=unidad_elegida,
        t_viaje_s=t_viaje,
        costo=costo_real,
    )


def despachar(
    incidente: Incidente,
    flota: Iterable[Unidad],
    grafo: GrafoVial,
    *,
    factor_hora: float = 1.0,
    factor_sirena: float = 1.0,
    progreso_por_unidad: Mapping[str, float] | None = None,
) -> ResultadoDespacho:
    """Caso de uso principal: despacha la mejor unidad para un incidente.

    Args:
        incidente: incidente ya triado y con coordenadas validadas.
        flota: lista completa de la flota SAMU (cualquier estado). Las
            unidades en TALLER se excluyen automáticamente (RN-04).
        grafo: implementación del port :class:`GrafoVial` (típicamente
            :class:`OsmnxGrafoVial`; en tests, un fake).
        factor_hora: multiplicador de tráfico horario para el A*
            (SRS sec. 2.6-B). ``1.0`` = sin penalización.
        factor_sirena: multiplicador de sirena para el A* (≤ 1.0
            acelera; ``1.0`` desactivado).
        progreso_por_unidad: mapeo opcional ``unidad.id -> progreso_pct``
            para las unidades EnRuta. Se usa cuando hay saturación para
            ordenar candidatas a re-dirección (RN-08, CP-10).

    Returns:
        :class:`ResultadoDespacho` con el motivo (OPTIMO / PENALIZADO /
        SUBOPTIMO_RN02 / SATURACION), la unidad elegida (o ``None``),
        el desglose del costo, todos los candidatos evaluados y, si
        aplica, el estado de saturación con candidatas a re-dirección.
    """
    flota_lista = list(flota)
    tiempos, rutas = _calcular_tiempos_viaje(
        flota_lista, incidente, grafo, factor_hora, factor_sirena
    )

    disponibles = [u for u in flota_lista if u.estado is EstadoUnidad.DISPONIBLE]
    seleccion = seleccionar_unidad(disponibles, incidente, tiempos)

    if seleccion.elegida is not None and seleccion.costo_elegida is not None:
        motivo = (
            MotivoDespacho.PENALIZADO
            if seleccion.costo_elegida.penalizacion > 0.0
            else MotivoDespacho.OPTIMO
        )
        return ResultadoDespacho(
            incidente=incidente,
            elegida=seleccion.elegida,
            costo_elegida=seleccion.costo_elegida,
            motivo=motivo,
            despacho_suboptimo=False,
            candidatos=seleccion.candidatos,
            saturacion=None,
            ruta_nodos=tuple(rutas.get(seleccion.elegida.id, [])),
        )

    if disponibles:
        fallback = _fallback_rn02_basica(disponibles, incidente, tiempos)
        if fallback is not None:
            elegida, candidato = fallback
            _log.warning(
                "RN-02 fallback aplicado: %s (Básica) → %s (%s); despacho_suboptimo=True",
                elegida.id,
                incidente.id,
                incidente.categoria_mpds.value,
            )
            return ResultadoDespacho(
                incidente=incidente,
                elegida=elegida,
                costo_elegida=candidato.costo,
                motivo=MotivoDespacho.SUBOPTIMO_RN02,
                despacho_suboptimo=True,
                candidatos=seleccion.candidatos,
                saturacion=None,
                ruta_nodos=tuple(rutas.get(elegida.id, [])),
            )

    estado_sat: EstadoSaturacion = detectar_saturacion(flota_lista, progreso_por_unidad)
    return ResultadoDespacho(
        incidente=incidente,
        elegida=None,
        costo_elegida=None,
        motivo=MotivoDespacho.SATURACION,
        despacho_suboptimo=False,
        candidatos=seleccion.candidatos,
        saturacion=estado_sat,
        ruta_nodos=(),
    )
