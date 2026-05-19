"""Entry-point del CLI de Sentinel-Dispatch.

Construye la aplicación Typer raíz y registra los subcomandos disponibles.
La instancia ``app`` es la que ``pyproject.toml`` expone como script
``sentinel`` vía ``[project.scripts]``.

Patrón arquitectónico: borde (Ports & Adapters — ADR-0006). No contiene
lógica de dominio; sólo orquesta entrada del operador, llama a casos de
uso o funciones de dominio, y formatea la salida.
"""

from __future__ import annotations

import typer

from sentinel_dispatch.interfaces.cli import run_dataset_cmd, triaje_cmd

app = typer.Typer(
    name="sentinel",
    no_args_is_help=True,
    add_completion=False,
    help="Sentinel-Dispatch — motor de despacho de ambulancias (IV Región).",
)

app.add_typer(triaje_cmd.app, name="triaje")
app.command("run-dataset")(run_dataset_cmd.run_dataset)


if __name__ == "__main__":  # pragma: no cover
    app()
