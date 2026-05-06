"""Entry point FastAPI de Sentinel-Dispatch.

Stub inicial — solo expone /healthz y /readyz. La lógica real se agrega
conforme avancen los módulos triaje, routing y dispatch.
"""

from fastapi import FastAPI

from sentinel_dispatch import __version__

app = FastAPI(
    title="Sentinel-Dispatch",
    description="Motor de despacho eficiente para unidades de emergencia médica.",
    version=__version__,
)


@app.get("/healthz", tags=["operations"])
async def healthz() -> dict[str, str]:
    """Liveness probe — el proceso responde."""
    return {"status": "alive", "version": __version__}


@app.get("/readyz", tags=["operations"])
async def readyz() -> dict[str, str]:
    """Readiness probe — el proceso está listo para recibir tráfico.

    TODO: chequear conexión a BD y disponibilidad del grafo OSM cargado.
    """
    return {"status": "ready"}
