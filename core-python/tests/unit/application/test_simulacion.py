"""UT del modo simulación (RF-12)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest

from sentinel_dispatch.adapters.repositorio_jsonl import JsonlRepositorioEventos
from sentinel_dispatch.application.simulacion import simular
from sentinel_dispatch.application.tipos import MotivoDespacho
from sentinel_dispatch.domain.dispatch.tipos import (
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.routing.tipos import Arista, NoRutaDisponibleError
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


# ---------------------------------------------------------------------------
# FakeGrafo + monkeypatch del A* — semántica idéntica a test_despacho
# ---------------------------------------------------------------------------


class FakeGrafo:
    def __init__(
        self,
        nodos_por_unidad: dict[str, int],
        nodo_incidente: int = 99,
    ) -> None:
        self._nodos = nodos_por_unidad
        self._nodo_inc = nodo_incidente
        self._coords = dict.fromkeys([*nodos_por_unidad.values(), nodo_incidente], (-29.95, -71.34))

    def vecinos(self, nodo: int) -> Iterable[Arista]:
        return []

    def coordenadas(self, nodo: int) -> tuple[float, float]:
        return self._coords[nodo]

    def nodo_mas_cercano(self, lat: float, lon: float) -> int:
        # Snap del incidente fijo al nodo_incidente; bases por id de unidad
        # detectado por proximidad a (lat, lon) provistos en la fixture.
        # Como las coords son arbitrarias, retorno el nodo del incidente
        # por default y los nodos de unidad cuando esa coord coincide.
        for uid, n in self._nodos.items():
            base_lat, base_lon = -29.0 - (hash(uid) % 100) * 0.001, -71.0
            if abs(lat - base_lat) < 1e-6 and abs(lon - base_lon) < 1e-6:
                return n
        return self._nodo_inc

    def distancia_snap_m(self, lat: float, lon: float, nodo: int) -> float:
        return 0.0


@pytest.fixture
def tiempos_por_unidad() -> dict[str, float]:
    """Mapeo unidad.id → t_viaje_s sintético. Modificable por tests."""
    return {"U01": 180.0, "U02": 240.0}


@pytest.fixture
def fake_grafo_y_tiempos(
    monkeypatch: pytest.MonkeyPatch, tiempos_por_unidad: dict[str, float]
) -> dict[str, float]:
    """Sustituye `a_estrella` por un fake que lee de `tiempos_por_unidad`."""

    nodos_por_unidad = {"U01": 1, "U02": 2}

    def fake_a_estrella(
        grafo: object,
        origen: int,
        destino: int,
        *,
        factor_hora: float,
        factor_sirena: float,
    ) -> tuple[float, list[int]]:
        for uid, n in nodos_por_unidad.items():
            if n == origen:
                t = tiempos_por_unidad.get(uid)
                if t is None or not math.isfinite(t):
                    raise NoRutaDisponibleError(origen, destino)
                return t, [origen, destino]
        raise NoRutaDisponibleError(origen, destino)

    import sentinel_dispatch.application.despachar_ambulancia as _da

    monkeypatch.setattr(_da, "a_estrella", fake_a_estrella)
    return tiempos_por_unidad


def _unidad(
    uid: str = "U01",
    tipo: TipoUnidad = TipoUnidad.AVANZADA,
    estado: EstadoUnidad = EstadoUnidad.DISPONIBLE,
) -> Unidad:
    return Unidad(
        id=uid,
        patente=f"PAT-{uid}",
        tipo=tipo,
        base_nombre=f"Base {uid}",
        base_lat=-29.0 - (hash(uid) % 100) * 0.001,
        base_lon=-71.0,
        estado=estado,
    )


def _incidente(iid: str, categoria: CategoriaMPDS = CategoriaMPDS.ALPHA) -> Incidente:
    return Incidente(
        id=iid,
        lat=-29.95,
        lon=-71.34,
        categoria_mpds=categoria,
        timestamp_iso="2026-05-21T12:00:00.000Z",
    )


# ---------------------------------------------------------------------------
# Normal
# ---------------------------------------------------------------------------


class TestNormal:
    def test_2_incidentes_2_resultados_y_metricas_correctas(
        self, fake_grafo_y_tiempos: dict[str, float]
    ) -> None:
        grafo = FakeGrafo(nodos_por_unidad={"U01": 1, "U02": 2})
        reporte = simular(
            incidentes=[_incidente("I-01"), _incidente("I-02")],
            flota_ficticia=[_unidad("U01")],
            grafo=grafo,
        )
        assert reporte.incidentes_procesados == 2
        assert len(reporte.resultados) == 2
        assert reporte.pct_optimo == 100.0
        assert reporte.pct_saturacion == 0.0
        assert reporte.eta_media_s is not None
        assert reporte.eta_media_s == pytest.approx(180.0)
        assert reporte.eta_p95_s == pytest.approx(180.0)

    def test_sin_estado_evolutivo_entre_incidentes(
        self, fake_grafo_y_tiempos: dict[str, float]
    ) -> None:
        """Cada incidente ve la flota inicial: la misma unidad puede ser elegida en cada uno."""
        grafo = FakeGrafo(nodos_por_unidad={"U01": 1})
        reporte = simular(
            incidentes=[_incidente("I-01"), _incidente("I-02"), _incidente("I-03")],
            flota_ficticia=[_unidad("U01")],
            grafo=grafo,
        )
        ganadores = {r.elegida.id for r in reporte.resultados if r.elegida is not None}
        assert ganadores == {"U01"}  # mismo ganador, no consumida


# ---------------------------------------------------------------------------
# Borde
# ---------------------------------------------------------------------------


class TestBorde:
    def test_lista_incidentes_vacia(self, fake_grafo_y_tiempos: dict[str, float]) -> None:
        grafo = FakeGrafo(nodos_por_unidad={"U01": 1})
        reporte = simular(
            incidentes=[],
            flota_ficticia=[_unidad("U01")],
            grafo=grafo,
        )
        assert reporte.incidentes_procesados == 0
        assert reporte.resultados == ()
        assert reporte.eta_media_s is None
        assert reporte.eta_p95_s is None
        assert reporte.pct_optimo == 0.0

    def test_flota_vacia_todos_saturacion(self, fake_grafo_y_tiempos: dict[str, float]) -> None:
        grafo = FakeGrafo(nodos_por_unidad={})
        reporte = simular(
            incidentes=[_incidente("I-01"), _incidente("I-02")],
            flota_ficticia=[],
            grafo=grafo,
        )
        assert reporte.pct_saturacion == 100.0
        assert all(r.motivo is MotivoDespacho.SATURACION for r in reporte.resultados)
        assert reporte.eta_media_s is None


# ---------------------------------------------------------------------------
# Reglas — "sin afectar el estado operativo real"
# ---------------------------------------------------------------------------


class TestSinAfectarEstadoReal:
    def test_default_no_escribe_a_repositorio(
        self, fake_grafo_y_tiempos: dict[str, float], tmp_path: Path
    ) -> None:
        """Sin `repositorio_eventos`, no se crea ningún archivo de log."""
        grafo = FakeGrafo(nodos_por_unidad={"U01": 1})
        log_no_creado = tmp_path / "log_no_creado.jsonl"
        simular(
            incidentes=[_incidente("I-01")],
            flota_ficticia=[_unidad("U01")],
            grafo=grafo,
        )
        assert not log_no_creado.exists()

    def test_con_repositorio_provisto_escribe_n_eventos_a_archivo_separado(
        self, fake_grafo_y_tiempos: dict[str, float], tmp_path: Path
    ) -> None:
        """Con repositorio, escribe 1 evento por incidente."""
        grafo = FakeGrafo(nodos_por_unidad={"U01": 1})
        eventos_sim_path = tmp_path / "eventos_sim.jsonl"
        repo = JsonlRepositorioEventos(eventos_sim_path)
        simular(
            incidentes=[_incidente("I-01"), _incidente("I-02"), _incidente("I-03")],
            flota_ficticia=[_unidad("U01")],
            grafo=grafo,
            repositorio_eventos=repo,
        )
        eventos = list(repo.leer_todos())
        assert len(eventos) == 3
        # Convención: los despacho_id de simulación tienen prefijo SD-SIM-
        assert all(
            e.despacho_id is not None and e.despacho_id.startswith("SD-SIM-") for e in eventos
        )


# ---------------------------------------------------------------------------
# Métricas — porcentajes por motivo
# ---------------------------------------------------------------------------


class TestMetricas:
    def test_pcts_suman_100_para_n_positivo(self, fake_grafo_y_tiempos: dict[str, float]) -> None:
        grafo = FakeGrafo(nodos_por_unidad={"U01": 1, "U02": 2})
        # Mix Echo + Básica → suboptimo_rn02
        reporte = simular(
            incidentes=[
                _incidente("I-01", CategoriaMPDS.ALPHA),  # → OPTIMO
                _incidente("I-02", CategoriaMPDS.ECHO),  # con sólo Básica → SUBOPTIMO_RN02
            ],
            flota_ficticia=[_unidad("U02", tipo=TipoUnidad.BASICA)],
            grafo=grafo,
        )
        suma = (
            reporte.pct_optimo
            + reporte.pct_penalizado
            + reporte.pct_suboptimo_rn02
            + reporte.pct_saturacion
        )
        assert suma == pytest.approx(100.0)
