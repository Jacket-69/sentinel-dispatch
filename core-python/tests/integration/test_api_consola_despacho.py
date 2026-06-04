"""Tests de integración de la vista de despacho con mapa (ADR-0022, RF-07).

El grafo OSM real (21 MB) se sustituye por un ``GrafoVial`` fake inyectado vía
``app.dependency_overrides[obtener_grafo]``: una arista base→incidente para que
el A* real produzca una ruta de dos nodos, sin cargar el grafo de producción.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.domain.routing.tipos import Arista, NodoFueraDeRangoError
from sentinel_dispatch.interfaces.api.main import app
from sentinel_dispatch.interfaces.api.web import obtener_grafo

_CLICK_LAT = -29.95
_CLICK_LON = -71.30
_DATOS_OK = {"lat": str(_CLICK_LAT), "lon": str(_CLICK_LON), "categoria_mpds": "Charlie"}


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class _GrafoFake:
    """Grafo trivial routeable: toda base snapea al nodo 1, el incidente al 99,
    y una arista 1→99 deja que el A* real encuentre una ruta de dos nodos.
    """

    _NODO_BASE = 1
    _NODO_INCIDENTE = 99
    _COORDS = {1: (-29.9077, -71.2535), 99: (_CLICK_LAT, _CLICK_LON)}

    def nodo_mas_cercano(self, lat: float, lon: float) -> int:
        if abs(lat - _CLICK_LAT) < 1e-4 and abs(lon - _CLICK_LON) < 1e-4:
            return self._NODO_INCIDENTE
        return self._NODO_BASE

    def vecinos(self, nodo: int) -> list[Arista]:
        if nodo == self._NODO_BASE:
            return [Arista(origen=1, destino=99, longitud_m=1000.0, velocidad_efectiva_kmh=50.0)]
        return []

    def coordenadas(self, nodo: int) -> tuple[float, float]:
        return self._COORDS[nodo]

    def distancia_snap_m(self, lat: float, lon: float, nodo: int) -> float:
        return 12.5


class _GrafoFueraDeRango:
    """Snap que siempre rechaza por estar fuera del bbox IV Región."""

    def nodo_mas_cercano(self, lat: float, lon: float) -> int:
        raise NodoFueraDeRangoError(
            "Coordenadas fuera del área de cobertura (IV Región).", lat=lat, lon=lon
        )

    def vecinos(self, nodo: int) -> list[Arista]:
        return []

    def coordenadas(self, nodo: int) -> tuple[float, float]:
        return (0.0, 0.0)

    def distancia_snap_m(self, lat: float, lon: float, nodo: int) -> float:
        return 0.0


@pytest.mark.asyncio
async def test_get_vista_despacho_ok() -> None:
    async with _cliente() as client:
        response = await client.get("/consola/despacho")
    assert response.status_code == 200
    cuerpo = response.text
    assert "CONSOLA DE DESPACHO" in cuerpo
    assert 'id="mapa"' in cuerpo
    assert 'name="categoria_mpds"' in cuerpo
    assert "leaflet" in cuerpo.lower()  # Leaflet vía CDN
    assert 'class="activo"' in cuerpo  # nav marca la vista activa


@pytest.mark.asyncio
async def test_despacho_ok_devuelve_ruta_y_geo() -> None:
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    try:
        async with _cliente() as client:
            response = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["unidad_seleccionada"] is not None
    assert body["eta_segundos"] is not None
    assert body["motivo"] in {"optimo", "penalizado", "suboptimo_rn02"}
    geo = body["geo"]
    assert geo["ruta"]  # polyline no vacía
    assert all(len(par) == 2 for par in geo["ruta"])  # pares [lat, lon]
    assert geo["incidente"][0] == pytest.approx(_CLICK_LAT)
    assert geo["snap_m"] == 12.5


@pytest.mark.asyncio
async def test_despacho_fuera_de_region_devuelve_422() -> None:
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFueraDeRango()
    try:
        async with _cliente() as client:
            response = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "cobertura" in response.json()["detail"]["mensaje"].lower()


@pytest.mark.asyncio
async def test_despacho_categoria_invalida_devuelve_422() -> None:
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    datos = {**_DATOS_OK, "categoria_mpds": "Zeta"}
    try:
        async with _cliente() as client:
            response = await client.post("/consola/despacho/despachar", data=datos)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_despacho_sin_grafo_cargado_devuelve_503() -> None:
    # Sin override y sin lifespan (ASGITransport no lo dispara): app.state.grafo
    # no existe, así que la dependencia obtener_grafo responde 503.
    async with _cliente() as client:
        response = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
    assert response.status_code == 503
