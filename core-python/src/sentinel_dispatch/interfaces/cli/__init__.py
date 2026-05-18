"""CLI de Sentinel-Dispatch — borde de entrada del operador.

El entry-point ``sentinel`` (ver ``pyproject.toml [project.scripts]``) apunta
a :data:`sentinel_dispatch.interfaces.cli.app:app`.
"""

from sentinel_dispatch.interfaces.cli.app import app

__all__ = ["app"]
