"""Tests de integración de la vista de validación dual RT-02 (ADR-0008).

``GET /consola/validacion`` compara las fixtures commiteadas en
``data/validacion/`` (outputs reales de ambos núcleos sobre los 12
incidentes del SRS) en cada render. Los tests usan esas fixtures reales:
no requieren el grafo OSM ni overrides de dependencias.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.interfaces.api.main import app


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_vista_validacion_ok() -> None:
    async with _cliente() as client:
        response = await client.get("/consola/validacion")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    cuerpo = response.text
    assert "VALIDACIÓN DUAL" in cuerpo
    assert "RT-02" in cuerpo


@pytest.mark.asyncio
async def test_vista_validacion_rinde_las_12_filas_en_paridad() -> None:
    async with _cliente() as client:
        response = await client.get("/consola/validacion")
    cuerpo = response.text
    # Las 12 filas del dataset de aceptación del SRS, todas en paridad.
    for i in range(1, 13):
        assert f"I-{i:02d}" in cuerpo
    assert cuerpo.count("veredicto--ok") == 12
    assert "veredicto--fail" not in cuerpo
    assert "veredicto--missing" not in cuerpo
    # Veredicto agregado del banner: paridad 12/12 y deltas reales en 0.000 %.
    assert "12/12" in cuerpo
    assert "0.000" in cuerpo


@pytest.mark.asyncio
async def test_vista_validacion_fuera_de_la_nav_por_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Default presentación (triaje + unidades): el link no aparece desde otra
    # vista, pero la ruta sigue registrada (deep link, mismo patrón que log).
    monkeypatch.delenv("SENTINEL_VISTAS", raising=False)
    async with _cliente() as client:
        desde_triaje = await client.get("/consola/triaje")
        directo = await client.get("/consola/validacion")
    assert 'href="/consola/validacion"' not in desde_triaje.text
    assert directo.status_code == 200
    # La vista activa siempre se muestra en la nav, aunque no esté habilitada.
    assert 'href="/consola/validacion"' in directo.text
    assert ">VALIDACIÓN</a>" in directo.text


@pytest.mark.asyncio
async def test_vista_validacion_en_la_nav_con_sentinel_vistas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENTINEL_VISTAS", "triaje,validacion")
    async with _cliente() as client:
        response = await client.get("/consola/triaje")
    cuerpo = response.text
    assert 'href="/consola/validacion"' in cuerpo
    # Label de nav con tilde aunque el slug sea ASCII.
    assert ">VALIDACIÓN</a>" in cuerpo
