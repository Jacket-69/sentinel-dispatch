"""Tests de integración del minijuego "ambulancia al destino" (bonus, sin RF).

Mismo patrón que la vista de validación: la ruta siempre está registrada
(deep link), pero el link de la nav solo aparece si ``SENTINEL_VISTAS``
incluye ``juego``.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.interfaces.api.main import app


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_vista_juego_ok() -> None:
    async with _cliente() as client:
        response = await client.get("/consola/juego")
    assert response.status_code == 200
    cuerpo = response.text
    assert "AMBULANCIA AL DESTINO" in cuerpo
    assert 'id="juego-canvas"' in cuerpo
    assert "juego.js" in cuerpo


@pytest.mark.asyncio
async def test_juego_fuera_de_la_nav_por_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Bonus de ocio: no aparece en la nav default, pero el deep link funciona
    # y la vista activa siempre se muestra a sí misma en la nav.
    monkeypatch.delenv("SENTINEL_VISTAS", raising=False)
    async with _cliente() as client:
        desde_triaje = await client.get("/consola/triaje")
        directo = await client.get("/consola/juego")
    assert 'href="/consola/juego"' not in desde_triaje.text
    assert directo.status_code == 200
    assert 'href="/consola/juego"' in directo.text


@pytest.mark.asyncio
async def test_juego_en_la_nav_con_sentinel_vistas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENTINEL_VISTAS", "triaje,juego")
    async with _cliente() as client:
        response = await client.get("/consola/triaje")
    cuerpo = response.text
    assert 'href="/consola/juego"' in cuerpo
    assert ">JUEGO</a>" in cuerpo
