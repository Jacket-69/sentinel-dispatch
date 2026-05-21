"""Modo simulación (RF-12) — ejecuta el cálculo de despacho sobre flota ficticia.

El SRS sec. RF-12 exige un modo que "ejecuta el cálculo completo sobre
un estado de flota ficticio sin afectar el estado operativo real". Este
módulo implementa la semántica más simple compatible con esa exigencia:

- **Sin evolución temporal entre incidentes**: cada incidente ve la flota
  ficticia en su estado inicial. Equivalente a correr ``run-dataset`` N
  veces sobre el mismo grafo + flota. Esta interpretación literal del
  SRS es suficiente para v1 (academic). Para v2 con reloj virtual y
  liberación de unidades por ``eta_segundos`` se necesitaría un ADR
  nuevo y framework de event-driven simulation.

- **Persistencia opt-in**: por default NO escribe al log canónico
  (modo simulación ≠ modo operativo). Si el caller provee
  ``repositorio_eventos``, se escribe ahí (típicamente un archivo
  separado tipo ``eventos_sim.jsonl`` para no contaminar el log real).

- **Reporte agregado**: el output incluye los resultados crudos +
  métricas porcentuales por motivo y ETA media/p95 para defensa
  académica del módulo.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sentinel_dispatch.application.despachar_ambulancia import despachar
from sentinel_dispatch.application.serializacion import serializar_resultado_despacho
from sentinel_dispatch.application.tipos import MotivoDespacho, ResultadoDespacho
from sentinel_dispatch.ports.repositorio_eventos import EventoLog, TipoEvento

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
    from sentinel_dispatch.domain.dispatch.tipos import Incidente, Unidad
    from sentinel_dispatch.domain.routing.grafo_vial import GrafoVial


@dataclass(frozen=True, slots=True)
class ReporteSimulacion:
    """Resumen inmutable de una corrida de simulación.

    Attributes:
        incidentes_procesados: número de incidentes ejecutados.
        resultados: tupla con un :class:`ResultadoDespacho` por incidente,
            en el orden en que se procesaron.
        pct_optimo: porcentaje de despachos en motivo ``OPTIMO`` (0-100).
        pct_penalizado: porcentaje en motivo ``PENALIZADO``.
        pct_suboptimo_rn02: porcentaje en motivo ``SUBOPTIMO_RN02``.
        pct_saturacion: porcentaje en motivo ``SATURACION``.
        eta_media_s: ETA promedio sobre los despachos no saturados.
            ``None`` si todos los incidentes fueron saturación.
        eta_p95_s: percentil 95 de las ETAs sobre los despachos no
            saturados. ``None`` si N < 1 o todos saturación.
    """

    incidentes_procesados: int
    resultados: tuple[ResultadoDespacho, ...]
    pct_optimo: float
    pct_penalizado: float
    pct_suboptimo_rn02: float
    pct_saturacion: float
    eta_media_s: float | None
    eta_p95_s: float | None


def _calcular_metricas(
    resultados: Sequence[ResultadoDespacho],
) -> tuple[float, float, float, float, float | None, float | None]:
    """Devuelve `(pct_optimo, pct_penalizado, pct_suboptimo_rn02, pct_saturacion, eta_media, eta_p95)`."""
    n = len(resultados)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0, None, None

    conteos = dict.fromkeys(MotivoDespacho, 0)
    for r in resultados:
        conteos[r.motivo] += 1

    pct = {motivo: 100.0 * c / n for motivo, c in conteos.items()}

    etas = [
        r.costo_elegida.t_viaje_s
        for r in resultados
        if r.motivo is not MotivoDespacho.SATURACION
        and r.costo_elegida is not None
        and math.isfinite(r.costo_elegida.t_viaje_s)
    ]
    if etas:
        eta_media: float | None = statistics.fmean(etas)
        # p95 con interpolación lineal estándar; statistics no expone percentile,
        # uso ordered + índice clamp por simplicidad (N pequeño, exacto).
        ordenado = sorted(etas)
        idx_p95 = max(0, math.ceil(0.95 * len(ordenado)) - 1)
        eta_p95: float | None = ordenado[idx_p95]
    else:
        eta_media = None
        eta_p95 = None

    return (
        pct[MotivoDespacho.OPTIMO],
        pct[MotivoDespacho.PENALIZADO],
        pct[MotivoDespacho.SUBOPTIMO_RN02],
        pct[MotivoDespacho.SATURACION],
        eta_media,
        eta_p95,
    )


def _persistir_evento(
    repo: JsonlRepositorioEventos,
    resultado: ResultadoDespacho,
    incidente: Incidente,
) -> None:
    """Persiste un evento ``despacho_creado`` por resultado (ADR-0018)."""
    despacho_id = (
        f"SD-SIM-{incidente.timestamp_iso[:10].replace('-', '')}-{incidente.id.replace('I-', '')}"
    )
    evento = EventoLog(
        evento_id=repo.generar_evento_id(base_ts=datetime.now(UTC)),
        timestamp_iso=incidente.timestamp_iso,
        tipo=TipoEvento.DESPACHO_CREADO,
        despacho_id=despacho_id,
        incidente_id=incidente.id,
        payload=serializar_resultado_despacho(resultado),
    )
    repo.append(evento)


def simular(
    incidentes: Sequence[Incidente],
    flota_ficticia: Sequence[Unidad],
    grafo: GrafoVial,
    *,
    repositorio_eventos: JsonlRepositorioEventos | None = None,
    factor_hora: float = 1.0,
    factor_sirena: float = 1.0,
) -> ReporteSimulacion:
    """Ejecuta el cálculo de despacho sobre cada incidente sin tocar el sistema real.

    Args:
        incidentes: secuencia de incidentes a procesar (deberían ya tener
            la categoría MPDS calculada).
        flota_ficticia: secuencia de unidades **ficticias** a usar como
            estado inicial. Es responsabilidad del caller verificar que
            esta flota no se cruza con la flota operativa real (por
            convención v1, basta con ``id`` distintos).
        grafo: :class:`GrafoVial` ya cargado (usualmente la región
            real — la "ficción" está en la flota, no en el mapa).
        repositorio_eventos: opcional. Si se provee, cada despacho
            persiste un evento ``despacho_creado`` ahí. Default ``None``
            = no persiste; **la simulación no afecta el log canónico
            del modo operativo** (cumple "sin afectar el estado real").
        factor_hora: multiplicador de tráfico horario para el A*.
        factor_sirena: multiplicador de sirena.

    Returns:
        :class:`ReporteSimulacion` con los resultados + métricas.

    Notas semánticas (decisiones v1):
        - **Sin estado evolutivo entre incidentes**: cada incidente ve
          la flota ficticia tal como llegó al inicio. Si una unidad fue
          "despachada" al I-01, sigue ``DISPONIBLE`` al evaluar I-02.
          Equivalente a paralelizar conceptualmente.
        - **Determinismo**: el resultado depende sólo de los inputs,
          no del wall-clock. Apto para tests y para reproducir corridas.
    """
    resultados: list[ResultadoDespacho] = []
    for incidente in incidentes:
        resultado = despachar(
            incidente,
            flota_ficticia,
            grafo,
            factor_hora=factor_hora,
            factor_sirena=factor_sirena,
        )
        resultados.append(resultado)
        if repositorio_eventos is not None:
            _persistir_evento(repositorio_eventos, resultado, incidente)

    pct_opt, pct_pen, pct_sub, pct_sat, eta_media, eta_p95 = _calcular_metricas(resultados)

    return ReporteSimulacion(
        incidentes_procesados=len(resultados),
        resultados=tuple(resultados),
        pct_optimo=pct_opt,
        pct_penalizado=pct_pen,
        pct_suboptimo_rn02=pct_sub,
        pct_saturacion=pct_sat,
        eta_media_s=eta_media,
        eta_p95_s=eta_p95,
    )
