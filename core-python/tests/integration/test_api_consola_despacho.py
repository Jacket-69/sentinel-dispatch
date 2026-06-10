"""Tests de integración de la vista de despacho con mapa (ADR-0022, RF-07).

El grafo OSM real (21 MB) se sustituye por un ``GrafoVial`` fake inyectado vía
``app.dependency_overrides[obtener_grafo]``: una arista base→incidente para que
el A* real produzca una ruta de dos nodos, sin cargar el grafo de producción.
"""

from typing import ClassVar

import pytest
from httpx import ASGITransport, AsyncClient

from sentinel_dispatch.domain.dispatch.tipos import EstadoUnidad
from sentinel_dispatch.domain.routing.tipos import Arista, NodoFueraDeRangoError
from sentinel_dispatch.interfaces.api.main import app
from sentinel_dispatch.interfaces.api.web import (
    obtener_grafo,
    obtener_red_vial,
    obtener_repositorio_eventos,
)
from sentinel_dispatch.ports.repositorio_eventos import EventoLog, TipoEvento

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
    _COORDS: ClassVar[dict[int, tuple[float, float]]] = {
        1: (-29.9077, -71.2535),
        99: (_CLICK_LAT, _CLICK_LON),
    }

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


class _RepoFake:
    """Repositorio de eventos en memoria para verificar la escritura al log."""

    def __init__(self) -> None:
        self.eventos: list[EventoLog] = []
        self._seq = 0

    def generar_evento_id(self) -> str:
        self._seq += 1
        return f"EVT-TEST-{self._seq:04d}"

    def append(self, evento: EventoLog) -> None:
        self.eventos.append(evento)


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


@pytest.mark.asyncio
async def test_despacho_marca_unidad_en_ruta() -> None:
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    async with _cliente() as client:
        response = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
    assert response.status_code == 200
    elegida = response.json()["unidad_seleccionada"]["id"]
    # El overlay en app.state quedó con la unidad elegida en EnRuta.
    assert app.state.estados_unidades[elegida] is EstadoUnidad.EN_RUTA


@pytest.mark.asyncio
async def test_despacho_escribe_evento_en_log() -> None:
    repo = _RepoFake()
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    app.dependency_overrides[obtener_repositorio_eventos] = lambda: repo
    async with _cliente() as client:
        response = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
    assert response.status_code == 200
    assert len(repo.eventos) == 1
    evento = repo.eventos[0]
    assert evento.tipo is TipoEvento.DESPACHO_CREADO
    assert evento.incidente_id == "I-CONSOLA"
    assert evento.payload["motivo"] == response.json()["motivo"]


@pytest.mark.asyncio
async def test_panel_refleja_unidad_en_ruta() -> None:
    app.state.estados_unidades = {"U01": EstadoUnidad.EN_RUTA}
    async with _cliente() as client:
        response = await client.get("/consola/unidades")
    assert response.status_code == 200
    cuerpo = response.text
    assert "fila--enruta" in cuerpo
    assert "fila--disponible" in cuerpo  # el resto sigue disponible


@pytest.mark.asyncio
async def test_reset_libera_la_flota() -> None:
    app.state.estados_unidades = {
        "U01": EstadoUnidad.EN_RUTA,
        "U02": EstadoUnidad.EN_RUTA,
    }
    async with _cliente() as client:
        response = await client.post("/consola/despacho/reset")
    assert response.status_code == 200
    assert response.json()["unidades_liberadas"] == 2
    assert app.state.estados_unidades == {}


@pytest.mark.asyncio
async def test_red_vial_devuelve_calles() -> None:
    calles = [[(-29.90, -71.25), (-29.91, -71.26)]]
    app.dependency_overrides[obtener_red_vial] = lambda: calles
    async with _cliente() as client:
        response = await client.get("/consola/despacho/red-vial")
    assert response.status_code == 200
    assert response.json()["calles"] == [[[-29.90, -71.25], [-29.91, -71.26]]]


@pytest.mark.asyncio
async def test_despacho_con_flota_saturada_no_elige_unidad() -> None:
    # Toda la flota EnRuta → no hay Disponibles → saturación.
    ids = [f"U{n:02d}" for n in range(1, 11)]
    app.state.estados_unidades = dict.fromkeys(ids, EstadoUnidad.EN_RUTA)
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    async with _cliente() as client:
        response = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
    assert response.status_code == 200
    body = response.json()
    assert body["unidad_seleccionada"] is None
    assert body["motivo"] == "saturacion"
    assert body["geo"]["ruta"] == []
    assert body["geo"]["unidad_base"] is None


@pytest.mark.asyncio
async def test_despachos_consecutivos_consumen_la_flota() -> None:
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    async with _cliente() as client:
        r1 = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
        r2 = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
    assert r1.status_code == 200
    assert r2.status_code == 200
    u1 = r1.json()["unidad_seleccionada"]["id"]
    u2 = r2.json()["unidad_seleccionada"]["id"]
    # La primera unidad quedó EnRuta y se excluyó de la segunda selección.
    assert u1 != u2
    assert app.state.estados_unidades[u1] is EstadoUnidad.EN_RUTA
    assert app.state.estados_unidades[u2] is EstadoUnidad.EN_RUTA


@pytest.mark.asyncio
async def test_reset_reincorpora_la_flota_al_pool() -> None:
    app.state.estados_unidades = {"U06": EstadoUnidad.EN_RUTA}
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    async with _cliente() as client:
        await client.post("/consola/despacho/reset")
        response = await client.post("/consola/despacho/despachar", data=_DATOS_OK)
    assert response.status_code == 200
    assert response.json()["unidad_seleccionada"] is not None


# --------------------------------------------------------------------------
# Puente triaje → despacho: balizas pendientes (overlay en memoria)
# --------------------------------------------------------------------------

_TRIAJE_BENIGNO = {
    "consciente": "true",
    "respira_normal": "true",
    "dificultad_respiratoria": "false",
    "sangrado": "Ninguno",
    "dolor_toracico": "Ninguno",
    "grupo_etario": "Adulto",
}


@pytest.mark.asyncio
async def test_clasificar_triaje_genera_baliza_pendiente() -> None:
    async with _cliente() as client:
        clasificacion = await client.post("/consola/triaje/clasificar", data=_TRIAJE_BENIGNO)
        listado = await client.get("/consola/despacho/incidentes")
    assert clasificacion.status_code == 200
    # El fragmento enlaza la baliza generada con la vista de despacho.
    assert "I-TRIAJE-001" in clasificacion.text
    incidentes = listado.json()["incidentes"]
    assert len(incidentes) == 1
    baliza = incidentes[0]
    assert baliza["id"] == "I-TRIAJE-001"
    assert baliza["categoria_mpds"] == "Alpha"
    # Sin grafo en app.state, el punto cae crudo dentro del bbox urbano.
    assert -29.98 <= baliza["lat"] <= -29.88
    assert -71.34 <= baliza["lon"] <= -71.22


@pytest.mark.asyncio
async def test_despachar_baliza_la_consume_y_loguea_su_id() -> None:
    repo = _RepoFake()
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    app.dependency_overrides[obtener_repositorio_eventos] = lambda: repo
    async with _cliente() as client:
        await client.post("/consola/triaje/clasificar", data=_TRIAJE_BENIGNO)
        datos = _DATOS_OK | {"incidente_id": "I-TRIAJE-001"}
        despacho = await client.post("/consola/despacho/despachar", data=datos)
        listado = await client.get("/consola/despacho/incidentes")
    assert despacho.status_code == 200
    assert despacho.json()["incidente_id"] == "I-TRIAJE-001"
    # La baliza despachada desaparece del overlay de pendientes...
    assert listado.json()["incidentes"] == []
    # ...y el evento del log queda asociado a su id.
    assert repo.eventos[0].incidente_id == "I-TRIAJE-001"


@pytest.mark.asyncio
async def test_despachar_con_baliza_inexistente_usa_id_consola() -> None:
    app.dependency_overrides[obtener_grafo] = lambda: _GrafoFake()
    async with _cliente() as client:
        datos = _DATOS_OK | {"incidente_id": "I-TRIAJE-999"}
        response = await client.post("/consola/despacho/despachar", data=datos)
    assert response.status_code == 200
    assert response.json()["incidente_id"] == "I-CONSOLA"


@pytest.mark.asyncio
async def test_reset_descarta_las_balizas_pendientes() -> None:
    async with _cliente() as client:
        await client.post("/consola/triaje/clasificar", data=_TRIAJE_BENIGNO)
        reset = await client.post("/consola/despacho/reset")
        listado = await client.get("/consola/despacho/incidentes")
    assert reset.json()["incidentes_descartados"] == 1
    assert listado.json()["incidentes"] == []
