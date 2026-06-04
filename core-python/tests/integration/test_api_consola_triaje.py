"""Tests de integración de la consola web de triaje (ADR-0022).

Verifica la vista GET del formulario y el endpoint POST de clasificación que
devuelve el fragmento HTMX. Los casos recorren el árbol MPDS-subset
(domain/triaje/arbol.py) cubriendo Normal / Borde / Error, en paralelo a los
tests unitarios del dominio pero a través de la capa HTTP.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.interfaces.api.main import app

# Respuesta totalmente benigna: paciente consciente, respira, sin hallazgos.
# Mutar uno o dos campos sobre esta base aísla cada regla del árbol.
_BENIGNO = {
    "consciente": "true",
    "respira_normal": "true",
    "dificultad_respiratoria": "false",
    "sangrado": "Ninguno",
    "dolor_toracico": "Ninguno",
    "grupo_etario": "Adulto",
}


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_get_vista_triaje_ok() -> None:
    async with _cliente() as client:
        response = await client.get("/consola/triaje")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # El formulario dispara HTMX contra el endpoint de clasificación y apunta
    # al panel de resultado que se inyecta in-place.
    assert 'hx-post="/consola/triaje/clasificar"' in response.text
    assert 'id="panel-resultado"' in response.text


@pytest.mark.asyncio
async def test_raiz_redirige_a_consola() -> None:
    async with _cliente() as client:
        response = await client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/consola/triaje"


@pytest.mark.asyncio
async def test_post_clasifica_alpha_caso_benigno() -> None:
    async with _cliente() as client:
        response = await client.post("/consola/triaje/clasificar", data=_BENIGNO)
    assert response.status_code == 200
    assert "ALPHA" in response.text.upper()
    assert "resultado--dim" in response.text


@pytest.mark.asyncio
async def test_post_clasifica_echo_inconsciente_sin_respirar() -> None:
    datos = _BENIGNO | {"consciente": "false", "respira_normal": "false"}
    async with _cliente() as client:
        response = await client.post("/consola/triaje/clasificar", data=datos)
    assert response.status_code == 200
    assert "ECHO" in response.text.upper()
    assert "resultado--crit" in response.text


@pytest.mark.asyncio
async def test_post_clasifica_delta_sangrado_peligroso() -> None:
    datos = _BENIGNO | {"sangrado": "Peligroso"}
    async with _cliente() as client:
        response = await client.post("/consola/triaje/clasificar", data=datos)
    assert response.status_code == 200
    assert "DELTA" in response.text.upper()
    assert "resultado--crit" in response.text


@pytest.mark.asyncio
async def test_post_clasifica_charlie_dolor_presente() -> None:
    datos = _BENIGNO | {"dolor_toracico": "Presente"}
    async with _cliente() as client:
        response = await client.post("/consola/triaje/clasificar", data=datos)
    assert response.status_code == 200
    assert "CHARLIE" in response.text.upper()
    assert "resultado--amber" in response.text


@pytest.mark.asyncio
async def test_post_valor_de_enum_invalido_devuelve_422() -> None:
    datos = _BENIGNO | {"sangrado": "Inexistente"}
    async with _cliente() as client:
        response = await client.post("/consola/triaje/clasificar", data=datos)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_campo_faltante_devuelve_422() -> None:
    datos = {k: v for k, v in _BENIGNO.items() if k != "grupo_etario"}
    async with _cliente() as client:
        response = await client.post("/consola/triaje/clasificar", data=datos)
    assert response.status_code == 422
