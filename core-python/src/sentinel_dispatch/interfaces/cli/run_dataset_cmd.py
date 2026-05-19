"""Subcomando ``run-dataset`` del CLI de Sentinel-Dispatch.

Ejecuta el caso de uso de despacho sobre un dataset de incidentes JSON y
produce un archivo JSONL por incidente en el directorio de salida. El
schema JSONL está congelado en ADR-0017 y es el contrato de equivalencia
para la validación dual Python-Java (ADR-0008, RT-02).

Uso::

    python -m sentinel_dispatch run-dataset \\
        --in  data/dataset/incidentes.json \\
        --unidades data/dataset/unidades.json \\
        --graph data/graphs/coquimbo.graphml \\
        --out <directorio>

Lo que vive aquí es exclusivamente lógica de borde (Ports & Adapters,
ADR-0006): parseo de entrada, construcción de DTOs de dominio y
serialización de la salida. La lógica de despacho ocurre en
:func:`sentinel_dispatch.application.despachar_ambulancia.despachar`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Annotated, Any

import typer

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial, cargar_grafo_iv_region
from sentinel_dispatch.application.despachar_ambulancia import despachar
from sentinel_dispatch.application.tipos import MotivoDespacho, ResultadoDespacho
from sentinel_dispatch.domain.dispatch.tipos import (
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS

# No app Typer propio: la función se registra directamente en el app raíz
# de app.py con @app.command("run-dataset") para evitar anidamiento doble.
# (Typer registra sub-Typer como grupo de sub-comandos, no como comando directo.)

# Path canónicos relativos al monorepo:
# run_dataset_cmd.py → [0] cli/  → [1] interfaces/  → [2] sentinel_dispatch/
# → [3] src/  → [4] core-python/  → [5] sentinel-dispatch/ (raíz monorepo)
_MONOREPO_ROOT: Path = Path(__file__).resolve().parents[5]
_INCIDENTES_DEFAULT: Path = _MONOREPO_ROOT / "data" / "dataset" / "incidentes.json"
_UNIDADES_DEFAULT: Path = _MONOREPO_ROOT / "data" / "dataset" / "unidades.json"
_GRAPH_DEFAULT: Path = _MONOREPO_ROOT / "data" / "graphs" / "coquimbo.graphml"


# ---------------------------------------------------------------------------
# Constructores de DTOs desde dict (JSON)
# ---------------------------------------------------------------------------


def _unidad_desde_dict(data: dict[str, Any]) -> Unidad:
    """Construye una :class:`Unidad` a partir de un dict de unidades.json."""
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
    """Construye un :class:`Incidente` a partir de un dict de incidentes.json.

    La categoría MPDS se deriva del campo ``ground_truth.categoria_mpds``
    (ya clasificado en el dataset de aceptación). El timestamp se toma
    del campo ``timestamp`` del incidente.
    """
    categoria = CategoriaMPDS(data["ground_truth"]["categoria_mpds"])
    return Incidente(
        id=data["id"],
        lat=float(data["lat"]),
        lon=float(data["lon"]),
        categoria_mpds=categoria,
        timestamp_iso=data["timestamp"],
    )


# ---------------------------------------------------------------------------
# Serialización del ResultadoDespacho → dict (schema ADR-0017)
# ---------------------------------------------------------------------------


def _serializar_resultado(resultado: ResultadoDespacho) -> dict[str, Any]:
    """Convierte un :class:`ResultadoDespacho` al dict del schema ADR-0017.

    Schema congelado (ADR-0017):

    - ``incidente_id``: str.
    - ``categoria_mpds``: str (valor del enum, e.g. "Alpha").
    - ``unidad_seleccionada``: ``{"id": str}`` o ``null`` si saturación.
    - ``despacho_suboptimo``: bool (``true`` solo para SUBOPTIMO_RN02).
    - ``motivo``: str (valor del enum, e.g. "OPTIMO", "SATURACION").
    - ``eta_segundos``: float o ``null`` si saturación.
    - ``costo``: ``{"T_viaje": float, "penalizacion": float, "total": float}``
      o ``null`` si saturación.
    - ``ruta``: list[str] (IDs de nodo como strings; vacío en saturación).
    """
    incidente = resultado.incidente
    motivo = resultado.motivo

    es_saturacion = motivo is MotivoDespacho.SATURACION

    unidad_sel: dict[str, str] | None = None
    eta: float | None = None
    costo_dict: dict[str, float] | None = None

    if not es_saturacion and resultado.elegida is not None and resultado.costo_elegida is not None:
        unidad_sel = {"id": resultado.elegida.id}
        costo_obj = resultado.costo_elegida
        # t_viaje_s es el tiempo ETA; excluir math.inf (no debe ocurrir fuera de saturación)
        eta = costo_obj.t_viaje_s if math.isfinite(costo_obj.t_viaje_s) else None
        t_viaje = costo_obj.t_viaje_s if math.isfinite(costo_obj.t_viaje_s) else 0.0
        pen = costo_obj.penalizacion if math.isfinite(costo_obj.penalizacion) else 0.0
        total = costo_obj.valor_total_s if math.isfinite(costo_obj.valor_total_s) else 0.0
        costo_dict = {
            "T_viaje": t_viaje,
            "penalizacion": pen,
            "total": total,
        }

    # Ruta de nodos de la unidad elegida, serializada como strings para evitar
    # drift de int64 en parsers JSON de otros lenguajes (Java Long, etc.).
    # En saturación ruta_nodos es () → ruta queda []. (ADR-0017 §ruta)
    ruta: list[str] = [str(n) for n in resultado.ruta_nodos]

    return {
        "incidente_id": incidente.id,
        "categoria_mpds": incidente.categoria_mpds.value,
        "unidad_seleccionada": unidad_sel,
        "despacho_suboptimo": resultado.despacho_suboptimo,
        "motivo": motivo.value,
        "eta_segundos": eta,
        "costo": costo_dict,
        "ruta": ruta,
    }


# ---------------------------------------------------------------------------
# Comando principal
# ---------------------------------------------------------------------------


def run_dataset(
    incidentes_path: Annotated[
        Path,
        typer.Option(
            "--in",
            help="Path al JSON con los incidentes del dataset.",
        ),
    ] = _INCIDENTES_DEFAULT,
    unidades_path: Annotated[
        Path,
        typer.Option(
            "--unidades",
            help="Path al JSON con la flota de unidades.",
        ),
    ] = _UNIDADES_DEFAULT,
    graph_path: Annotated[
        Path,
        typer.Option(
            "--graph",
            help="Path al GraphML del grafo vial.",
        ),
    ] = _GRAPH_DEFAULT,
    out_dir: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Directorio de salida para los archivos JSONL (se crea si no existe).",
        ),
    ] = Path("out"),
) -> None:
    """Corre el dataset de despacho y emite un JSONL por incidente.

    Por cada incidente del dataset:

    1. Carga el grafo vial desde ``--graph`` (GraphML).
    2. Construye la flota desde ``--unidades``.
    3. Ejecuta el caso de uso de despacho.
    4. Serializa el :class:`ResultadoDespacho` a ``<out>/<incidente.id>.jsonl``.

    El schema JSONL está congelado en ADR-0017.

    Exit codes:

    - **0** si se procesaron todos los incidentes sin error.
    - **2** si alguno de los archivos de entrada no existe o es JSON inválido.
    - **1** si ocurre un error inesperado durante el procesamiento.
    """
    # --- Validar paths de entrada ---
    if not incidentes_path.exists():
        typer.secho(
            f"Error: archivo de incidentes no encontrado: {incidentes_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    if not unidades_path.exists():
        typer.secho(
            f"Error: archivo de unidades no encontrado: {unidades_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    if not graph_path.exists():
        typer.secho(
            f"Error: archivo de grafo no encontrado: {graph_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    # --- Parsear JSON de entrada ---
    try:
        incidentes_raw: list[dict[str, Any]] = json.loads(
            incidentes_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        typer.secho(
            f"Error: incidentes JSON inválido — {exc.msg} (línea {exc.lineno}).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc

    try:
        unidades_raw: list[dict[str, Any]] = json.loads(unidades_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.secho(
            f"Error: unidades JSON inválido — {exc.msg} (línea {exc.lineno}).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc

    # --- Preparar salida ---
    out_dir.mkdir(parents=True, exist_ok=True)

    if not incidentes_raw:
        typer.echo("Dataset vacío; no se generaron archivos de salida.")
        raise typer.Exit(code=0)

    # --- Cargar grafo ---
    grafo_nx = cargar_grafo_iv_region(ruta_cache=graph_path)
    grafo = OsmnxGrafoVial(grafo=grafo_nx)

    # --- Construir flota ---
    flota = [_unidad_desde_dict(u) for u in unidades_raw]

    # --- Procesar cada incidente ---
    procesados = 0
    for raw in incidentes_raw:
        incidente = _incidente_desde_dict(raw)
        resultado: ResultadoDespacho = despachar(incidente, flota, grafo)
        salida = _serializar_resultado(resultado)

        out_file = out_dir / f"{incidente.id}.jsonl"
        out_file.write_text(json.dumps(salida, ensure_ascii=False) + "\n", encoding="utf-8")
        procesados += 1

    typer.echo(f"Procesados {procesados} incidente(s). Salida en: {out_dir}")
    raise typer.Exit(code=0)
