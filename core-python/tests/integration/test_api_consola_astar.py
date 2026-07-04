"""Tests de integración de la vista A* didáctica (demo de defensa).

El grafo real se sustituye por un fake routeable vía
``app.dependency_overrides[obtener_grafo]``, igual que en los tests de la
vista de despacho.
"""

from typing import ClassVar

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.domain.routing.tipos import Arista, NodoFueraDeRangoError
from sentinel_dispatch.interfaces.api.main import app
from sentinel_dispatch.interfaces.api.web import obtener_grafo

# A ~630 m en línea recta: menos que los 1000 m de la arista del fake, para
# que la heurística Haversine siga siendo cota inferior (grafo consistente).
_ORIGEN = (-29.9077, -71.2535)
_DESTINO = (-29.9077, -71.2600)

_DATOS_OK = {
    "lat_origen": str(_ORIGEN[0]),
    "lon_origen": str(_ORIGEN[1]),
    "lat_destino": str(_DESTINO[0]),
    "lon_destino": str(_DESTINO[1]),
}


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class _GrafoFake:
    """Dos nodos y una arista: el origen snapea al 1, el destino al 99."""

    _COORDS: ClassVar[dict[int, tuple[float, float]]] = {1: _ORIGEN, 99: _DESTINO}

    def nodo_mas_cercano(self, lat: float, lon: float) -> int:
        if abs(lat - _DESTINO[0]) < 1e-4 and abs(lon - _DESTINO[1]) < 1e-4:
            return 99
        return 1

    def vecinos(self, nodo: int) -> list[Arista]:
        if nodo == 1:
            return [Arista(origen=1, destino=99, longitud_m=1000.0, velocidad_efectiva_kmh=50.0)]
        return []

    def coordenadas(self, nodo: int) -> tuple[float, float]:
        return self._COORDS[nodo]

    def distancia_snap_m(self, lat: float, lon: float, nodo: int) -> float:
        return 0.0


class _GrafoFueraDeRango:
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
async def test_get_vista_astar_ok() -> None:
    async with _cliente() as client:
        response = await client.get("/consola/astar")
    assert response.status_code == 200
    cuerpo = response.text
    assert "A* PASO A PASO" in cuerpo
    assert 'id="mapa"' in cuerpo
    assert "astar.js" in cuerpo


@pytest.mark.asyncio
async def test_astar_en_la_nav_con_sentinel_vistas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINEL_VISTAS", "triaje,astar")
    async with _cliente() as client:
        response = await client.get("/consola/triaje")
    cuerpo = response.text
    assert 'href="/consola/astar"' in cuerpo
    assert ">A*</a>" in cuerpo


@pytest.mark.asyncio
async def test_trazar_devuelve_expansiones_y_ruta() -> None:
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    try:
        async with _cliente() as client:
            response = await client.post("/consola/astar/trazar", data=_DATOS_OK)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["eta_segundos"] == pytest.approx(72.0)  # 1000 m a 50 km/h
    assert body["nodos_expandidos"] == 2
    assert body["nodos_ruta"] == 2
    # Expansiones en orden: origen primero, destino al final.
    assert body["expansiones"][0] == [pytest.approx(_ORIGEN[0]), pytest.approx(_ORIGEN[1])]
    assert body["expansiones"][-1] == [pytest.approx(_DESTINO[0]), pytest.approx(_DESTINO[1])]
    assert body["ruta"][0] == body["expansiones"][0]
    # Admisibilidad visible en el payload: h(origen) <= ETA real.
    assert 0 < body["h_origen_segundos"] <= body["eta_segundos"]


@pytest.mark.asyncio
async def test_trazar_fuera_de_region_devuelve_422() -> None:
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFueraDeRango()
    try:
        async with _cliente() as client:
            response = await client.post("/consola/astar/trazar", data=_DATOS_OK)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "cobertura" in response.json()["detail"]["mensaje"].lower()


@pytest.mark.asyncio
async def test_trazar_sin_grafo_cargado_devuelve_503() -> None:
    async with _cliente() as client:
        response = await client.post("/consola/astar/trazar", data=_DATOS_OK)
    assert response.status_code == 503
