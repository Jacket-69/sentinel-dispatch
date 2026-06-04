"""Entry point FastAPI de Sentinel-Dispatch.

Expone los probes operacionales (/healthz, /readyz), el validador de
coordenadas RF-01 / RN-01 (CP-09) y la **consola web del operador**
(ADR-0022, rescate de ADR-0004): estáticos en /static y las vistas HTMX
montadas desde :mod:`sentinel_dispatch.interfaces.api.web`.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sentinel_dispatch import __version__
from sentinel_dispatch.domain.incidente.validacion import (
    LAT_MAX_IV_REGION,
    LAT_MIN_IV_REGION,
    LON_MAX_IV_REGION,
    LON_MIN_IV_REGION,
    CoordenadasFueraDeRangoError,
    validar_coordenadas_iv_region,
)
from sentinel_dispatch.interfaces.api import web

app = FastAPI(
    title="Sentinel-Dispatch",
    description="Motor de despacho eficiente para unidades de emergencia médica.",
    version=__version__,
)

# Consola web del operador (ADR-0022): estáticos CRT + vistas HTMX.
app.mount("/static", StaticFiles(directory=str(web.DIRECTORIO_ESTATICOS)), name="static")
app.include_router(web.router)


class CoordenadasIncidente(BaseModel):
    """Payload de coordenadas crudas de un incidente (RF-01)."""

    lat: float = Field(..., description="Latitud EPSG:4326, grados decimales.")
    lon: float = Field(..., description="Longitud EPSG:4326, grados decimales.")


class CoordenadasValidasResponse(BaseModel):
    """Respuesta del validador cuando las coordenadas caen dentro del bbox."""

    valido: bool = True
    lat: float
    lon: float
    rango_iv_region: dict[str, float]


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


@app.post(
    "/v1/incidentes/validar-coordenadas",
    tags=["incidentes"],
    response_model=CoordenadasValidasResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Coordenadas fuera del bbox de la IV Región (RN-01)."
        }
    },
)
async def validar_coordenadas(payload: CoordenadasIncidente) -> CoordenadasValidasResponse:
    """Valida que las coordenadas caigan dentro del bbox IV Región (RF-01).

    Cumple CP-09 del SRS sec. 2.13: si las coordenadas están fuera del
    rango, retorna ``422 Unprocessable Entity`` con el mensaje normativo
    "Coordenadas fuera del área de cobertura (IV Región)." y **no** ejecuta
    cálculos posteriores ni genera log de despacho.
    """
    try:
        validar_coordenadas_iv_region(payload.lat, payload.lon)
    except CoordenadasFueraDeRangoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "mensaje": str(exc),
                "lat": payload.lat,
                "lon": payload.lon,
                "rango_iv_region": {
                    "lat_min": LAT_MIN_IV_REGION,
                    "lat_max": LAT_MAX_IV_REGION,
                    "lon_min": LON_MIN_IV_REGION,
                    "lon_max": LON_MAX_IV_REGION,
                },
            },
        ) from exc
    return CoordenadasValidasResponse(
        lat=payload.lat,
        lon=payload.lon,
        rango_iv_region={
            "lat_min": LAT_MIN_IV_REGION,
            "lat_max": LAT_MAX_IV_REGION,
            "lon_min": LON_MIN_IV_REGION,
            "lon_max": LON_MAX_IV_REGION,
        },
    )
