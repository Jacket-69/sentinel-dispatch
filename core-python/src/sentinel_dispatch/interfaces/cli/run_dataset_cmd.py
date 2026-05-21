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
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

import typer

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial, cargar_grafo_iv_region
from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
from sentinel_dispatch.application.despachar_ambulancia import despachar
from sentinel_dispatch.application.serializacion import serializar_resultado_despacho
from sentinel_dispatch.domain.dispatch.tipos import (
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS
from sentinel_dispatch.ports.repositorio_eventos import EventoLog, TipoEvento

if TYPE_CHECKING:
    from sentinel_dispatch.application.tipos import ResultadoDespacho

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
# Helpers de borde (I/O + parseo)
#
# La serialización canónica del ResultadoDespacho vive en
# `application.serializacion` (ADR-0017), reutilizada también por el
# adapter de log JSONL (ADR-0018) para garantizar bit-exactitud.
# ---------------------------------------------------------------------------


def _validar_path_existente(path: Path, etiqueta: str) -> None:
    """Aborta con exit code 2 si ``path`` no existe.

    El substring ``"no encontrado"`` queda fijo para que los tests del CLI
    puedan asserterlo sin acoplarse a la etiqueta concreta.
    """
    if not path.exists():
        typer.secho(
            f"Error: archivo de {etiqueta} no encontrado: {path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)


def _cargar_json_o_exit(path: Path, etiqueta: str) -> list[dict[str, Any]]:
    """Lee y parsea un JSON; aborta con exit code 2 si el contenido es inválido.

    El substring ``"JSON inválido"`` queda fijo (los tests lo assertean).
    """
    try:
        return cast("list[dict[str, Any]]", json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        typer.secho(
            f"Error: {etiqueta} JSON inválido — {exc.msg} (línea {exc.lineno}).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc


def _emitir_evento_despacho(
    repo: JsonlRepositorioEventos,
    resultado: ResultadoDespacho,
    incidente: Incidente,
    payload: dict[str, Any],
) -> None:
    """Persiste un evento ``despacho_creado`` con el ``payload`` ya serializado.

    Reutiliza el dict producido por :func:`serializar_resultado_despacho`
    como ``payload`` del evento. Esto garantiza bit-exactitud con el
    schema RT-02 (ADR-0017) y evita drift entre el JSONL emitido por
    incidente y el log canónico (ADR-0018).
    """
    despacho_id = (
        f"SD-{incidente.timestamp_iso[:10].replace('-', '')}-{incidente.id.replace('I-', '')}"
    )
    evento = EventoLog(
        evento_id=repo.generar_evento_id(),
        timestamp_iso=incidente.timestamp_iso,
        tipo=TipoEvento.DESPACHO_CREADO,
        despacho_id=despacho_id,
        incidente_id=incidente.id,
        payload=payload,
    )
    repo.append(evento)


def _procesar_incidentes(
    incidentes_raw: list[dict[str, Any]],
    flota: list[Unidad],
    grafo: OsmnxGrafoVial,
    out_dir: Path,
    repo_eventos: JsonlRepositorioEventos | None = None,
) -> int:
    """Itera incidentes, despacha cada uno y escribe un JSONL por incidente.

    Si ``repo_eventos`` es provisto, también persiste un evento
    ``despacho_creado`` por incidente en el log canónico (ADR-0018);
    omitirlo preserva la semántica RT-02 pura del ``run-dataset``.

    Returns:
        Número de incidentes procesados (== len(incidentes_raw) por construcción).
    """
    procesados = 0
    for raw in incidentes_raw:
        incidente = _incidente_desde_dict(raw)
        resultado: ResultadoDespacho = despachar(incidente, flota, grafo)
        salida = serializar_resultado_despacho(resultado)

        out_file = out_dir / f"{incidente.id}.jsonl"
        out_file.write_text(json.dumps(salida, ensure_ascii=False) + "\n", encoding="utf-8")

        if repo_eventos is not None:
            _emitir_evento_despacho(repo_eventos, resultado, incidente, salida)

        procesados += 1
    return procesados


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
    log_eventos_path: Annotated[
        Path | None,
        typer.Option(
            "--log-eventos",
            help=(
                "(Opcional) Path al archivo eventos.jsonl global donde "
                "persistir eventos `despacho_creado` por incidente (ADR-0018, RF-06)."
            ),
        ),
    ] = None,
) -> None:
    """Corre el dataset de despacho y emite un JSONL por incidente.

    Por cada incidente del dataset:

    1. Carga el grafo vial desde ``--graph`` (GraphML).
    2. Construye la flota desde ``--unidades``.
    3. Ejecuta el caso de uso de despacho.
    4. Serializa el :class:`ResultadoDespacho` a ``<out>/<incidente.id>.jsonl``.
    5. (Opcional, si ``--log-eventos`` está presente) persiste un
       evento ``despacho_creado`` por incidente en el log canónico.

    El schema JSONL del paso 4 está congelado en ADR-0017; el del log
    canónico en ADR-0018 (reutiliza el mismo payload).

    Exit codes:

    - **0** si se procesaron todos los incidentes sin error.
    - **2** si alguno de los archivos de entrada no existe o es JSON inválido.
    - **1** si ocurre un error inesperado durante el procesamiento.
    """
    _validar_path_existente(incidentes_path, etiqueta="incidentes")
    _validar_path_existente(unidades_path, etiqueta="unidades")
    _validar_path_existente(graph_path, etiqueta="grafo")

    incidentes_raw = _cargar_json_o_exit(incidentes_path, etiqueta="incidentes")
    unidades_raw = _cargar_json_o_exit(unidades_path, etiqueta="unidades")

    out_dir.mkdir(parents=True, exist_ok=True)

    if not incidentes_raw:
        typer.echo("Dataset vacío; no se generaron archivos de salida.")
        raise typer.Exit(code=0)

    grafo_nx = cargar_grafo_iv_region(ruta_cache=graph_path)
    grafo = OsmnxGrafoVial(grafo=grafo_nx)
    flota = [_unidad_desde_dict(u) for u in unidades_raw]

    repo_eventos = (
        JsonlRepositorioEventos(log_eventos_path) if log_eventos_path is not None else None
    )

    procesados = _procesar_incidentes(incidentes_raw, flota, grafo, out_dir, repo_eventos)

    sufijo = f" · eventos en {log_eventos_path}" if log_eventos_path is not None else ""
    typer.echo(f"Procesados {procesados} incidente(s). Salida en: {out_dir}{sufijo}")
    raise typer.Exit(code=0)
