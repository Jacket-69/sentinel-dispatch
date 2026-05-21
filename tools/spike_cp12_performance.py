"""Spike CP-12: medir wall-clock del orquestador con 50 unidades.

Convención ``spike-before-CP`` (CONTRIBUTING.md): verifica empíricamente
que el criterio CP-12 del SRS ("≤ 1000 ms para 50 unidades") sea
alcanzable antes de comprometerse a él. ADR-0019 congela el resultado.

Genera 50 unidades sintéticas distribuidas en la bbox IV Región
(mix 30 Avanzada / 20 Básica), crea un incidente Echo en el centro,
carga el grafo `data/graphs/coquimbo.graphml` (excluido del wall-clock),
corre ``despachar(...)`` 10 veces warm-cache y reporta p50/p95/max.

Uso::

    uv run --project core-python python tools/spike_cp12_performance.py

Salida:
    Estadísticas wall-clock en stdout + un JSON con los números crudos
    en ``tools/_out/spike_cp12_resultado.json`` para ser citado en
    ADR-0019.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Soportar ejecución desde la raíz del monorepo.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "core-python" / "src"))

from sentinel_dispatch.adapters.grafo_osmnx import (  # noqa: E402
    OsmnxGrafoVial,
    cargar_grafo_iv_region,
)
from sentinel_dispatch.application.despachar_ambulancia import despachar  # noqa: E402
from sentinel_dispatch.domain.dispatch.tipos import (  # noqa: E402
    EstadoUnidad,
    Incidente,
    TipoUnidad,
    Unidad,
)
from sentinel_dispatch.domain.triaje.tipos import CategoriaMPDS  # noqa: E402

# Bbox conurbación La Serena-Coquimbo (consistente con grafo coquimbo.graphml).
_LAT_MIN, _LAT_MAX = -30.05, -29.85
_LON_MIN, _LON_MAX = -71.45, -71.20

_N_AVANZADAS = 30
_N_BASICAS = 20
_N_REPETICIONES = 10  # corridas warm-cache para p50/p95/max
_PATH_GRAFO = _REPO_ROOT / "data" / "graphs" / "coquimbo.graphml"
_OUT_PATH = _REPO_ROOT / "tools" / "_out" / "spike_cp12_resultado.json"


def _generar_flota() -> list[Unidad]:
    """50 unidades distribuidas en grilla regular sobre la bbox."""
    flota: list[Unidad] = []
    total = _N_AVANZADAS + _N_BASICAS  # 50
    # Grilla 10×5 para 50 puntos.
    n_lat = 5
    n_lon = 10
    paso_lat = (_LAT_MAX - _LAT_MIN) / (n_lat - 1)
    paso_lon = (_LON_MAX - _LON_MIN) / (n_lon - 1)
    for i in range(total):
        fila = i // n_lon
        col = i % n_lon
        lat = _LAT_MIN + fila * paso_lat
        lon = _LON_MIN + col * paso_lon
        tipo = TipoUnidad.AVANZADA if i < _N_AVANZADAS else TipoUnidad.BASICA
        flota.append(
            Unidad(
                id=f"SIM-{i + 1:02d}",
                patente=f"SIM-{i + 1:03d}",
                tipo=tipo,
                base_nombre=f"Base sintética {i + 1}",
                base_lat=lat,
                base_lon=lon,
                estado=EstadoUnidad.DISPONIBLE,
            )
        )
    return flota


def _incidente_centro() -> Incidente:
    return Incidente(
        id="SIM-INC-01",
        lat=(_LAT_MIN + _LAT_MAX) / 2,
        lon=(_LON_MIN + _LON_MAX) / 2,
        categoria_mpds=CategoriaMPDS.ECHO,
        timestamp_iso=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )


def main() -> int:
    print(f"[spike-cp12] Cargando grafo desde {_PATH_GRAFO} ...", flush=True)
    t0 = time.perf_counter()
    grafo_nx = cargar_grafo_iv_region(ruta_cache=_PATH_GRAFO)
    grafo = OsmnxGrafoVial(grafo=grafo_nx)
    t_carga = time.perf_counter() - t0
    print(f"[spike-cp12] Grafo cargado en {t_carga:.2f} s (excluido del wall-clock).")

    flota = _generar_flota()
    incidente = _incidente_centro()
    print(
        f"[spike-cp12] Flota sintética: {len(flota)} unidades "
        f"({_N_AVANZADAS} Avanzada / {_N_BASICAS} Básica) en bbox IV Región."
    )

    # Warm-up (descarta cache del primer A*).
    despachar(incidente, flota, grafo)

    duraciones_ms: list[float] = []
    for i in range(_N_REPETICIONES):
        t0 = time.perf_counter()
        despachar(incidente, flota, grafo)
        dur_ms = (time.perf_counter() - t0) * 1000
        duraciones_ms.append(dur_ms)
        print(f"[spike-cp12] Run {i + 1:02d}: {dur_ms:.1f} ms", flush=True)

    duraciones_ms.sort()
    p50 = duraciones_ms[len(duraciones_ms) // 2]
    p95 = duraciones_ms[max(0, int(0.95 * len(duraciones_ms)) - 1)]
    pmax = max(duraciones_ms)
    media = statistics.fmean(duraciones_ms)

    print("\n[spike-cp12] === Resumen ===")
    print(f"  N unidades         : {len(flota)}")
    print(f"  Repeticiones       : {_N_REPETICIONES}")
    print(f"  wall-clock p50     : {p50:.1f} ms")
    print(f"  wall-clock p95     : {p95:.1f} ms")
    print(f"  wall-clock max     : {pmax:.1f} ms")
    print(f"  wall-clock media   : {media:.1f} ms")
    print("  Criterio CP-12 SRS : ≤ 1000 ms p95")
    veredicto = "PASA" if p95 <= 1000 else "FALLA"
    print(f"  Veredicto          : {veredicto}")

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(
        json.dumps(
            {
                "fecha_iso": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "n_unidades": len(flota),
                "n_avanzadas": _N_AVANZADAS,
                "n_basicas": _N_BASICAS,
                "n_repeticiones": _N_REPETICIONES,
                "duraciones_ms": duraciones_ms,
                "p50_ms": p50,
                "p95_ms": p95,
                "max_ms": pmax,
                "media_ms": media,
                "criterio_cp12_ms": 1000,
                "veredicto": veredicto,
                "t_carga_grafo_s": t_carga,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\n[spike-cp12] Resultados crudos en {_OUT_PATH}")
    return 0 if p95 <= 1000 else 1


if __name__ == "__main__":
    sys.exit(main())
