"""Subcomando ``sentinel export`` — exporta el log JSONL a CSV/JSON (RF-11).

Lee un ``eventos.jsonl`` producido por :class:`JsonlRepositorioEventos`
y produce un archivo derivado para auditoría externa. El log canónico
no se modifica (RN-03 preservado: este subcomando solo lee).

Uso::

    sentinel export --formato csv  --in data/eventos.jsonl --out reporte.csv
    sentinel export --formato json --in data/eventos.jsonl --out reporte.json
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path  # noqa: TC003 — Typer inspecciona el tipo en runtime.
from typing import Annotated

import typer

from sentinel_dispatch.adapters.exportador import exportar_a_csv, exportar_a_json
from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos


class FormatoExport(StrEnum):
    """Formatos soportados por :func:`export`."""

    CSV = "csv"
    JSON = "json"


def export(
    formato: Annotated[
        FormatoExport,
        typer.Option(
            "--formato",
            help="Formato de salida: 'csv' (utf-8-sig + BOM) o 'json' (array indentado).",
            case_sensitive=False,
        ),
    ],
    entrada_path: Annotated[
        Path,
        typer.Option(
            "--in",
            help="Path al archivo eventos.jsonl producido por --log-eventos.",
        ),
    ],
    salida_path: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Path al archivo de salida CSV o JSON (se crea o sobreescribe).",
        ),
    ],
) -> None:
    """Exporta el log JSONL a CSV o JSON para auditoría externa (RF-11).

    Exit codes:

    - **0** si la exportación fue exitosa.
    - **2** si ``--in`` no existe o contiene JSONL inválido (propagado
      desde el adapter como :exc:`ValidationError` o :exc:`OSError`).
    """
    if not entrada_path.exists():
        typer.secho(
            f"Error: archivo de entrada no encontrado: {entrada_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        repo = JsonlRepositorioEventos(entrada_path)
    except Exception as exc:  # ValidationError de Pydantic, OSError, etc.
        typer.secho(
            f"Error: no se pudo leer el log de eventos: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc

    eventos = list(repo.leer_todos())

    if formato is FormatoExport.CSV:
        n = exportar_a_csv(eventos, salida_path)
    else:
        n = exportar_a_json(eventos, salida_path)

    typer.echo(f"Exportados {n} evento(s) a {salida_path} (formato {formato.value}).")
    raise typer.Exit(code=0)
