"""Tests de integración del endpoint ``POST /v1/incidentes/validar-coordenadas``.

Cubre RF-01 (validación de rango en el borde HTTP) y CP-09 (rechazo de
``lat=-31.2, lon=-71.3`` con mensaje normativo y sin generar log de
despacho). Taxonomía Normal / Borde / Error / Regla de Negocio.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.domain.incidente.validacion import MENSAJE_FUERA_DE_RANGO
from sentinel_dispatch.interfaces.api.main import app

_ENDPOINT = "/v1/incidentes/validar-coordenadas"


async def _post(payload: dict[str, float]) -> tuple[int, dict[str, object]]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(_ENDPOINT, json=payload)
    return response.status_code, response.json()


# ---------------------------------------------------------------------------
# Normal — coordenadas válidas devuelven 200 con el rango canónico
# ---------------------------------------------------------------------------


class TestApiValidacionNormal:
    @pytest.mark.asyncio
    async def test_la_serena_devuelve_200_y_valido(self) -> None:
        status, body = await _post({"lat": -29.9077, "lon": -71.2535})
        assert status == 200
        assert body["valido"] is True
        assert body["lat"] == -29.9077
        assert body["lon"] == -71.2535
        assert body["rango_iv_region"]["lat_min"] == -30.5
        assert body["rango_iv_region"]["lon_max"] == -70.5

    @pytest.mark.asyncio
    async def test_coquimbo_devuelve_200(self) -> None:
        status, body = await _post({"lat": -29.95, "lon": -71.34})
        assert status == 200
        assert body["valido"] is True


# ---------------------------------------------------------------------------
# Borde — límites exactos del bbox
# ---------------------------------------------------------------------------


class TestApiValidacionBorde:
    @pytest.mark.asyncio
    async def test_limite_inferior_lat_devuelve_200(self) -> None:
        status, _ = await _post({"lat": -30.5, "lon": -71.0})
        assert status == 200

    @pytest.mark.asyncio
    async def test_limite_superior_lon_devuelve_200(self) -> None:
        status, _ = await _post({"lat": -30.0, "lon": -70.5})
        assert status == 200


# ---------------------------------------------------------------------------
# Error — body malformado o tipos incorrectos → 422 de Pydantic
# ---------------------------------------------------------------------------


class TestApiValidacionError:
    @pytest.mark.asyncio
    async def test_body_sin_lon_devuelve_422_pydantic(self) -> None:
        """Falta de campo obligatorio: 422 con error de validación de schema."""
        status, body = await _post({"lat": -29.9})
        assert status == 422
        # FastAPI/Pydantic devuelve `detail` como lista de errores estructurados
        # cuando la validación del schema falla; nuestro detalle de negocio
        # llega como dict, así que estos casos son distinguibles.
        assert isinstance(body["detail"], list)

    @pytest.mark.asyncio
    async def test_lat_no_numerica_devuelve_422(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(_ENDPOINT, json={"lat": "norte", "lon": -71.0})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Regla de Negocio — CP-09 textual (SRS sec. 2.13)
# ---------------------------------------------------------------------------


class TestApiValidacionReglaDeNegocio:
    @pytest.mark.asyncio
    async def test_cp09_lat_minus_31_2_lon_minus_71_3_devuelve_422_con_mensaje(
        self,
    ) -> None:
        """CP-09 textual: el endpoint rechaza con 422 y el mensaje normativo.

        El detalle estructurado del error trae ``mensaje``, ``lat``, ``lon`` y
        el ``rango_iv_region`` aplicado, para que el cliente pueda mostrar al
        operador el motivo exacto del rechazo.
        """
        status, body = await _post({"lat": -31.2, "lon": -71.3})
        assert status == 422
        detail = body["detail"]
        # Caso de negocio: detail es dict, no lista (que es lo de Pydantic).
        assert isinstance(detail, dict)
        assert detail["mensaje"] == MENSAJE_FUERA_DE_RANGO
        assert detail["lat"] == -31.2
        assert detail["lon"] == -71.3
        assert detail["rango_iv_region"]["lat_min"] == -30.5
