"""IT de performance: 50 unidades + 1 incidente Echo ≤ criterio CP-12.

Marker ``slow`` (no corre en ``make test-fast`` ni en CI por default).
Para ejecutar localmente::

    cd core-python && uv run pytest -m slow --no-cov

Criterio actual: ``≤ 2000 ms p95`` (ajustado en ADR-0019 desde el SRS).

El test reusa la misma flota sintética y bbox que
``tools/spike_cp12_performance.py`` para que ambos midan lo mismo.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sentinel_dispatch.adapters.grafo_osmnx import OsmnxGrafoVial, cargar_grafo_iv_region
from sentinel_dispatch.application.despachar_ambulancia import despachar
from sentinel_dispatch.domain.dispatch.tipos import (
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS

pytestmark = pytest.mark.slow

_LAT_MIN, _LAT_MAX = -30.05, -29.85
_LON_MIN, _LON_MAX = -71.45, -71.20
_N_AVANZADAS = 30
_N_BASICAS = 20
_N_REPETICIONES = 10
_CRITERIO_P95_MS = 2000  # Ajustado en ADR-0019.

_PATH_GRAFO = Path(__file__).resolve().parents[3] / "data" / "graphs" / "coquimbo.graphml"


def _generar_flota() -> list[Unidad]:
    flota: list[Unidad] = []
    total = _N_AVANZADAS + _N_BASICAS
    n_lat, n_lon = 5, 10
    paso_lat = (_LAT_MAX - _LAT_MIN) / (n_lat - 1)
    paso_lon = (_LON_MAX - _LON_MIN) / (n_lon - 1)
    for i in range(total):
        fila, col = i // n_lon, i % n_lon
        lat = _LAT_MIN + fila * paso_lat
        lon = _LON_MIN + col * paso_lon
        flota.append(
            Unidad(
                id=f"SIM-{i + 1:02d}",
                patente=f"SIM-{i + 1:03d}",
                tipo=TipoUnidad.AVANZADA if i < _N_AVANZADAS else TipoUnidad.BASICA,
                base_nombre=f"Base sintética {i + 1}",
                base_lat=lat,
                base_lon=lon,
                estado=EstadoUnidad.DISPONIBLE,
            )
        )
    return flota


def test_cp12_50_unidades_p95_bajo_criterio_ajustado() -> None:
    """ADR-0019: p95 ≤ 2000 ms para 50 unidades + 1 Echo."""
    if not _PATH_GRAFO.exists():
        pytest.skip(f"Grafo no disponible: {_PATH_GRAFO}")

    grafo_nx = cargar_grafo_iv_region(ruta_cache=_PATH_GRAFO)
    grafo = OsmnxGrafoVial(grafo=grafo_nx)
    flota = _generar_flota()
    incidente = Incidente(
        id="SIM-INC-01",
        lat=(_LAT_MIN + _LAT_MAX) / 2,
        lon=(_LON_MIN + _LON_MAX) / 2,
        categoria_mpds=CategoriaMPDS.ECHO,
        timestamp_iso=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    despachar(incidente, flota, grafo)  # warm-up

    duraciones_ms: list[float] = []
    for _ in range(_N_REPETICIONES):
        t0 = time.perf_counter()
        despachar(incidente, flota, grafo)
        duraciones_ms.append((time.perf_counter() - t0) * 1000)

    duraciones_ms.sort()
    p95 = duraciones_ms[max(0, int(0.95 * len(duraciones_ms)) - 1)]
    assert p95 <= _CRITERIO_P95_MS, (
        f"CP-12 ajustado falló: p95={p95:.0f} ms > {_CRITERIO_P95_MS} ms. "
        f"Distribución: {duraciones_ms}"
    )
