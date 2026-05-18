"""Subcomandos de triaje MPDS-subset expuestos por el CLI.

Comandos:

- ``sentinel triaje classify`` — clasifica una respuesta puntual del operador
  (entrada por flags o JSON inline) y emite la categoría MPDS por stdout.
- ``sentinel triaje run-dataset`` — corre el dataset de aceptación
  (SRS sec. 2.12, ``data/dataset/incidentes.json``) y reporta una tabla
  comparando la clasificación obtenida con el ``ground_truth`` de cada
  incidente. Exit code 0 si todos coinciden, 1 si hay divergencia.

Lo que vive aquí es exclusivamente lógica de borde: parseo de la entrada,
construcción del DTO de dominio y formateo del output. La clasificación
ocurre en :func:`sentinel_dispatch.domain.triaje.clasificar_mpds`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from sentinel_dispatch.domain.triaje import (
    CategoriaMPDS,
    GrupoEtario,
    NivelDolorToracico,
    NivelSangrado,
    RespuestaTriaje,
    clasificar_mpds,
)

app = typer.Typer(
    name="triaje",
    no_args_is_help=True,
    help="Triaje MPDS-subset (Alpha < Bravo < Charlie < Delta < Echo).",
)

# Path al dataset de aceptación, navegado desde el módulo:
# core-python/src/sentinel_dispatch/interfaces/cli/triaje_cmd.py  →  parents[5] == raíz monorepo.
_DATASET_DEFAULT = Path(__file__).resolve().parents[5] / "data" / "dataset" / "incidentes.json"


def _respuesta_desde_dict(data: dict[str, Any]) -> RespuestaTriaje:
    """Construye un :class:`RespuestaTriaje` a partir de un dict (JSON).

    Cualquier valor inválido propaga ``ValueError`` desde el constructor del
    enum correspondiente; Typer convierte la excepción en exit code != 0.
    Cualquier key faltante propaga ``KeyError`` con el mismo efecto.
    """
    return RespuestaTriaje(
        consciente=bool(data["consciente"]),
        respira_normal=bool(data["respira_normal"]),
        sangrado=NivelSangrado(data["sangrado"]),
        dolor_toracico=NivelDolorToracico(data["dolor_toracico"]),
        dificultad_respiratoria=bool(data["dificultad_respiratoria"]),
        grupo_etario=GrupoEtario(data["grupo_etario"]),
    )


@app.command("classify")
def classify(
    consciente: Annotated[
        bool,
        typer.Option(
            "--consciente/--no-consciente",
            help="¿El paciente está consciente? (default: True)",
        ),
    ] = True,
    respira_normal: Annotated[
        bool,
        typer.Option(
            "--respira-normal/--no-respira-normal",
            help="¿Respira con normalidad? Sólo relevante si --no-consciente.",
        ),
    ] = True,
    sangrado: Annotated[
        NivelSangrado,
        typer.Option(
            "--sangrado",
            help="Nivel de sangrado visible (default: Ninguno).",
            case_sensitive=True,
        ),
    ] = NivelSangrado.NINGUNO,
    dolor_toracico: Annotated[
        NivelDolorToracico,
        typer.Option(
            "--dolor-toracico",
            help="Nivel de dolor torácico (default: Ninguno).",
            case_sensitive=True,
        ),
    ] = NivelDolorToracico.NINGUNO,
    dificultad_respiratoria: Annotated[
        bool,
        typer.Option(
            "--dificultad-respiratoria/--no-dificultad-respiratoria",
            help="Presencia de dificultad respiratoria (default: False).",
        ),
    ] = False,
    grupo_etario: Annotated[
        GrupoEtario,
        typer.Option(
            "--grupo-etario",
            help="Grupo etario del paciente (default: Adulto).",
            case_sensitive=True,
        ),
    ] = GrupoEtario.ADULTO,
    json_input: Annotated[
        str | None,
        typer.Option(
            "--json",
            help=(
                "JSON inline con las 6 keys de RespuestaTriaje. "
                "Si se provee, los flags individuales se ignoran."
            ),
        ),
    ] = None,
) -> None:
    """Clasifica una respuesta de triaje en una categoría MPDS.

    El árbol implementa las 9 reglas del SRS sec. 2.6-A en orden estricto.
    La salida es exactamente el valor del enum :class:`CategoriaMPDS` por
    stdout (Alpha, Bravo, Charlie, Delta o Echo), apta para piping a otras
    herramientas de shell.
    """
    if json_input is not None:
        try:
            data = json.loads(json_input)
        except json.JSONDecodeError as exc:
            typer.secho(
                f"Error: JSON inválido — {exc.msg} (línea {exc.lineno}, col {exc.colno}).",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2) from exc
        respuesta = _respuesta_desde_dict(data)
    else:
        respuesta = RespuestaTriaje(
            consciente=consciente,
            respira_normal=respira_normal,
            sangrado=sangrado,
            dolor_toracico=dolor_toracico,
            dificultad_respiratoria=dificultad_respiratoria,
            grupo_etario=grupo_etario,
        )

    categoria = clasificar_mpds(respuesta)
    typer.echo(categoria.value)


@app.command("run-dataset")
def run_dataset(
    dataset_path: Annotated[
        Path,
        typer.Option(
            "--dataset",
            help="Path al JSON del dataset (default: data/dataset/incidentes.json).",
        ),
    ] = _DATASET_DEFAULT,
) -> None:
    """Corre el dataset de aceptación contra el árbol y reporta divergencias.

    Lee el archivo JSON, clasifica cada incidente con
    :func:`clasificar_mpds` y compara con la categoría declarada en el
    bloque ``ground_truth``. Imprime una tabla rich con ID, categoría
    esperada, categoría obtenida y un indicador de coincidencia.

    Exit code:

    - **0** si los N incidentes coinciden con su ground truth.
    - **1** si al menos uno diverge.
    - **2** si el archivo de dataset no existe o es JSON inválido.
    """
    if not dataset_path.exists():
        typer.secho(
            f"Error: dataset no encontrado en {dataset_path}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        incidentes = json.loads(dataset_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.secho(
            f"Error: dataset JSON inválido — {exc.msg} (línea {exc.lineno}).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from exc

    console = Console()
    table = Table(
        title=f"Triaje MPDS-subset — {len(incidentes)} incidentes",
        title_style="bold",
        show_lines=False,
    )
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Esperada", style="magenta")
    table.add_column("Obtenida", style="white")
    table.add_column("Match", justify="center")

    aciertos = 0
    for incidente in incidentes:
        respuesta = _respuesta_desde_dict(incidente["respuestas_triaje"])
        esperada = CategoriaMPDS(incidente["ground_truth"]["categoria_mpds"])
        obtenida = clasificar_mpds(respuesta)
        coincide = esperada == obtenida
        if coincide:
            aciertos += 1
        table.add_row(
            incidente["id"],
            esperada.value,
            obtenida.value,
            "[green]✔[/green]" if coincide else "[red]✘[/red]",
        )

    console.print(table)
    total = len(incidentes)
    color = "green" if aciertos == total else "red"
    console.print(f"\n[bold {color}]Total: {aciertos}/{total}[/bold {color}]")

    raise typer.Exit(code=0 if aciertos == total else 1)
