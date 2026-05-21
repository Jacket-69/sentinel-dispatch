"""Subcomando ``sentinel simular`` — modo simulación con flota ficticia (RF-12).

Equivale a ``run-dataset`` pero con dos garantías adicionales:

1. **Etiqueta semántica explícita**: el comando se llama ``simular``,
   marcando claramente al operador que esto NO es ejecución operativa.
2. **Persistencia opt-in a archivo separado**: si se usa ``--persistir-en``,
   los eventos van a un archivo distinto del log canónico operativo
   (sugerencia: ``data/eventos_sim.jsonl``), preservando "sin afectar
   el estado operativo real" (SRS RF-12).

Uso::

    sentinel simular --flota data/ficticias.json --incidentes data/scenario.json \\
        --graph data/graphs/coquimbo.graphml --out reporte.json

    sentinel simular --flota ... --incidentes ... --persistir-en data/eventos_sim.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003 — Typer inspecciona el tipo en runtime.
from typing import Annotated, Any, cast

import typer

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial, cargar_grafo_iv_region
from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
from sentinel_dispatch.application.serializacion import serializar_resultado_despacho
from sentinel_dispatch.application.simulacion import ReporteSimulacion, simular
from sentinel_dispatch.domain.dispatch.tipos import (
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS


def _validar_path(path: Path, etiqueta: str) -> None:
    if not path.exists():
        typer.secho(
            f"Error: archivo de {etiqueta} no encontrado: {path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)


def _cargar_json_lista(path: Path, etiqueta: str) -> list[dict[str, Any]]:
    try:
        return cast("list[dict[str, Any]]", json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        typer.secho(
            f"Error: {etiqueta} JSON inválido — {exc.msg} (línea {exc.lineno}).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc


def _unidad_desde_dict(data: dict[str, Any]) -> Unidad:
    return Unidad(
        id=data["id"],
        patente=data["patente"],
        tipo=TipoUnidad(data["tipo"]),
        base_nombre=data["base_nombre"],
        base_lat=float(data["base_lat"]),
        base_lon=float(data["base_lon"]),
        estado=EstadoUnidad(data["estado"]),
    )


def _incidente_desde_dict(data: dict[str, Any]) -> Incidente:
    categoria = CategoriaMPDS(data["ground_truth"]["categoria_mpds"])
    return Incidente(
        id=data["id"],
        lat=float(data["lat"]),
        lon=float(data["lon"]),
        categoria_mpds=categoria,
        timestamp_iso=data["timestamp"],
    )


def _serializar_reporte(reporte: ReporteSimulacion) -> dict[str, Any]:
    """Convierte un :class:`ReporteSimulacion` a dict serializable."""
    return {
        "modo": "simulacion",
        "incidentes_procesados": reporte.incidentes_procesados,
        "metricas": {
            "pct_optimo": reporte.pct_optimo,
            "pct_penalizado": reporte.pct_penalizado,
            "pct_suboptimo_rn02": reporte.pct_suboptimo_rn02,
            "pct_saturacion": reporte.pct_saturacion,
            "eta_media_s": reporte.eta_media_s,
            "eta_p95_s": reporte.eta_p95_s,
        },
        "resultados": [serializar_resultado_despacho(r) for r in reporte.resultados],
    }


def simular_cmd(
    incidentes_path: Annotated[
        Path,
        typer.Option(
            "--incidentes",
            help="Path al JSON con los incidentes a simular.",
        ),
    ],
    flota_path: Annotated[
        Path,
        typer.Option(
            "--flota",
            help="Path al JSON con la flota ficticia.",
        ),
    ],
    graph_path: Annotated[
        Path,
        typer.Option(
            "--graph",
            help="Path al GraphML del grafo vial.",
        ),
    ],
    out_path: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Path al JSON de reporte de simulación a crear.",
        ),
    ],
    persistir_en: Annotated[
        Path | None,
        typer.Option(
            "--persistir-en",
            help=(
                "(Opcional) Path a un eventos.jsonl SEPARADO para persistir "
                "los eventos de la simulación. NO debe coincidir con el log "
                "operativo real (RF-12 §'sin afectar el estado operativo')."
            ),
        ),
    ] = None,
) -> None:
    """Ejecuta el modo simulación (RF-12): cálculo completo sobre flota ficticia.

    Por default no escribe al log canónico. Si se provee ``--persistir-en``,
    los eventos se persisten en ese archivo separado.

    Exit codes:

    - **0** si la simulación termina sin error.
    - **2** si algún archivo de entrada no existe o es JSON inválido.
    """
    _validar_path(incidentes_path, etiqueta="incidentes")
    _validar_path(flota_path, etiqueta="flota")
    _validar_path(graph_path, etiqueta="grafo")

    incidentes_raw = _cargar_json_lista(incidentes_path, etiqueta="incidentes")
    flota_raw = _cargar_json_lista(flota_path, etiqueta="flota")

    grafo_nx = cargar_grafo_iv_region(ruta_cache=graph_path)
    grafo = OsmnxGrafoVial(grafo=grafo_nx)

    incidentes = [_incidente_desde_dict(raw) for raw in incidentes_raw]
    flota_ficticia = [_unidad_desde_dict(raw) for raw in flota_raw]

    repositorio = JsonlRepositorioEventos(persistir_en) if persistir_en is not None else None

    reporte = simular(
        incidentes,
        flota_ficticia,
        grafo,
        repositorio_eventos=repositorio,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(_serializar_reporte(reporte), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    sufijo = f" · eventos en {persistir_en}" if persistir_en is not None else ""
    typer.echo(
        f"Simulación completa: {reporte.incidentes_procesados} incidente(s). "
        f"Reporte en {out_path}{sufijo}."
    )
    raise typer.Exit(code=0)
