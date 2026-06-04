"""Tests de integración de las vistas Panel de unidades y Log (ADR-0022).

- Panel (`/consola/unidades`, RF-09): renderiza la flota del dataset.
- Log (`/consola/log`, RF-06): renderiza el log JSONL; se inyectan eventos
  vía ``app.dependency_overrides`` para no depender de un archivo en disco.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.domain.dispatch.tipos import EstadoUnidad
from sentinel_dispatch.interfaces.api.main import app
from sentinel_dispatch.interfaces.api.web import _TOKEN_ESTADO, cargar_eventos_log
from sentinel_dispatch.ports.repositorio_eventos import EventoLog, TipoEvento


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _evento_despacho() -> EventoLog:
    return EventoLog(
        evento_id="EVT-20260521T140311-0001",
        timestamp_iso="2026-05-21T14:03:11Z",
        tipo=TipoEvento.DESPACHO_CREADO,
        despacho_id="SD-0001",
        incidente_id="I-01",
        operador="samu_sistema",
        payload={
            "categoria_mpds": "Echo",
            "unidad_seleccionada": {"id": "U03"},
            "eta_segundos": 312,
            "motivo": "OPTIMO",
        },
    )


# --------------------------------------------------------------------------
# Panel de unidades
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vista_unidades_ok() -> None:
    async with _cliente() as client:
        response = await client.get("/consola/unidades")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    cuerpo = response.text
    assert "PANEL DE UNIDADES" in cuerpo
    # Las 10 unidades del dataset, todas Disponible en v1.
    assert "U01" in cuerpo
    assert "U10" in cuerpo
    assert "fila--disponible" in cuerpo
    # La nav comparte las tres vistas y marca la activa.
    assert 'href="/consola/log"' in cuerpo
    assert 'class="activo"' in cuerpo


def test_token_estado_cubre_los_cuatro_estados() -> None:
    # El dataset solo trae Disponible; este test cubre el mapeo completo.
    assert _TOKEN_ESTADO[EstadoUnidad.DISPONIBLE] == "disponible"
    assert _TOKEN_ESTADO[EstadoUnidad.EN_RUTA] == "enruta"
    assert _TOKEN_ESTADO[EstadoUnidad.EN_ESCENA] == "enescena"
    assert _TOKEN_ESTADO[EstadoUnidad.TALLER] == "taller"
    assert set(_TOKEN_ESTADO) == set(EstadoUnidad)


# --------------------------------------------------------------------------
# Vista de log
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vista_log_con_eventos() -> None:
    app.dependency_overrides[cargar_eventos_log] = lambda: [_evento_despacho()]
    try:
        async with _cliente() as client:
            response = await client.get("/consola/log")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    cuerpo = response.text
    assert "REGISTRO DE EVENTOS" in cuerpo
    assert "despacho_creado" in cuerpo
    assert "I-01" in cuerpo
    assert "U03" in cuerpo  # resumen derivado del payload
    assert "ETA 312" in cuerpo
    assert "evento--ok" in cuerpo


@pytest.mark.asyncio
async def test_get_vista_log_vacio_muestra_placeholder() -> None:
    app.dependency_overrides[cargar_eventos_log] = lambda: []
    try:
        async with _cliente() as client:
            response = await client.get("/consola/log")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "SIN EVENTOS REGISTRADOS" in response.text


@pytest.mark.asyncio
async def test_get_vista_log_sin_archivo_no_revienta() -> None:
    # Sin override y sin archivo de log: el loader real devuelve [] y la
    # vista responde 200 con el estado vacío.
    async with _cliente() as client:
        response = await client.get("/consola/log")
    assert response.status_code == 200
