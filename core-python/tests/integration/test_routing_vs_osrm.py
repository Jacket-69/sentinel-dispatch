"""IT-01 — Validación del A* propio contra OSRM oracle.

Estrategia ADR-0010 §3 (fixture committeado, CI offline) + criterio
reformulado en ADR-0011 (`distance` como proxy de paridad). El test:

1. Lee ``tests/fixtures/osrm_oracle.json`` (100 pares generados localmente
   con ``tools/build_osrm_oracle.sh`` + ``tools/generate_osrm_fixture.py``).
2. Para cada par: snap origen/destino al grafo Coquimbo, corre A* propio,
   mide ``distance`` (suma de longitudes de aristas) y ``duration``.
3. Asserta **CP-01a** — paridad de ruta — vía distancia.
4. Reporta **CP-01b** — divergencia observacional en duration — vía log.

Criterio CP-01a (ADR-0011):
    ``|Δ_distance| / d_OSRM ≤ 0.30`` en ≥ 75 de 100 pares.

Marcadores ``slow`` + ``integration``: el A* sobre el grafo real toma
unos segundos por par (16 k nodos, snap brute-force). La suite
``test-fast`` no lo corre.
"""

from __future__ import annotations

import json
import logging
import statistics
from pathlib import Path

import pytest

from sentinel_dispatch.adapters.grafo_osmnx import (
    GRAPHML_PATH,
    OsmnxGrafoVial,
    cargar_grafo_iv_region,
)
from sentinel_dispatch.domain.routing.a_estrella import a_estrella

_log = logging.getLogger(__name__)

TOLERANCIA_DISTANCIA: float = 0.30
"""Tolerancia relativa de paridad de ruta (CP-01a, ADR-0011)."""

MINIMO_DENTRO: int = 75
"""Cantidad mínima de pares dentro de tolerancia exigida por CP-01a."""

FIXTURE_PATH: Path = Path(__file__).resolve().parents[1] / "fixtures" / "osrm_oracle.json"


pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture(scope="module")
def fixture_osrm() -> dict[str, object]:
    """Carga el fixture OSRM oracle committeado al repo."""
    if not FIXTURE_PATH.exists():
        pytest.skip(
            f"Fixture OSRM ausente: {FIXTURE_PATH}. "
            "Regenerar con: tools/build_osrm_oracle.sh && "
            "uv run python tools/generate_osrm_fixture.py"
        )
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        data: dict[str, object] = json.load(f)
    return data


@pytest.fixture(scope="module")
def adapter() -> OsmnxGrafoVial:
    """Carga el grafo Coquimbo desde la caché GraphML committeada."""
    if not GRAPHML_PATH.exists():
        pytest.skip(f"GraphML ausente: {GRAPHML_PATH}. Generar con: make build-graph")
    grafo = cargar_grafo_iv_region(ruta_cache=GRAPHML_PATH, forzar_descarga=False)
    return OsmnxGrafoVial(grafo=grafo)


def _distancia_de_ruta(adapter: OsmnxGrafoVial, ruta: list[int]) -> float:
    """Suma las longitudes de las aristas usadas por el A*.

    Para cada par consecutivo ``(u, v)`` busca la arista de menor longitud
    entre ellos (relevante con `MultiDiGraph`, donde pueden haber paralelas).
    """
    total = 0.0
    for i in range(len(ruta) - 1):
        origen, destino = ruta[i], ruta[i + 1]
        longitudes = [a.longitud_m for a in adapter.vecinos(origen) if a.destino == destino]
        assert longitudes, (
            f"A* devolvió una ruta inconsistente con el adapter: "
            f"sin arista directa entre nodos {origen} → {destino}"
        )
        total += min(longitudes)
    return total


def _resumen_distribucion(errores: list[float]) -> str:
    """Devuelve una línea con mediana, p75, p95 y conteos por bin."""
    e = sorted(errores)
    n = len(e)

    def percentil(q: float) -> float:
        return e[min(int(q * n), n - 1)]

    bins = ", ".join(
        f"±{int(tol * 100):2d}%={sum(1 for x in e if x <= tol)}/{n}"
        for tol in (0.05, 0.10, 0.20, 0.30, 0.50)
    )
    return (
        f"median={statistics.median(e):.3f} p75={percentil(0.75):.3f} "
        f"p95={percentil(0.95):.3f}  [{bins}]"
    )


def test_a_estrella_vs_osrm_paridad_distancia(
    fixture_osrm: dict[str, object],
    adapter: OsmnxGrafoVial,
) -> None:
    """CP-01a (ADR-0011): ≥75/100 pares con |Δ_distance| / d_OSRM ≤ 0.30.

    El A* propio se ejecuta con ``factor_hora=1.0`` y ``factor_sirena=1.0``
    para que la comparación sea apples-to-apples contra OSRM (que no aplica
    multiplicadores dinámicos en el perfil ``car.lua``).

    También se reporta la distribución completa de divergencia en duration
    (CP-01b, ADR-0011): no se assertea porque OSRM modela turn penalties
    que el A* del SRS no contempla, lo que produce sesgos sistemáticos.
    """
    pares = fixture_osrm["pares"]
    assert isinstance(pares, list)
    assert len(pares) == 100, f"fixture debe tener 100 pares, tiene {len(pares)}"

    errores_distancia: list[float] = []
    errores_duracion: list[float] = []
    fuera: list[tuple[int, float, float, float]] = []  # (id, d_propio, d_osrm, err_rel)

    for par in pares:
        assert isinstance(par, dict)
        par_id = int(par["id"])
        origen_coord = par["origen"]
        destino_coord = par["destino"]
        assert isinstance(origen_coord, dict)
        assert isinstance(destino_coord, dict)
        t_osrm = float(par["duration_s"])
        d_osrm = float(par["distance_m"])

        nodo_origen = adapter.nodo_mas_cercano(
            float(origen_coord["lat"]), float(origen_coord["lon"])
        )
        nodo_destino = adapter.nodo_mas_cercano(
            float(destino_coord["lat"]), float(destino_coord["lon"])
        )

        t_propio, ruta = a_estrella(
            adapter,
            nodo_origen,
            nodo_destino,
            factor_hora=1.0,
            factor_sirena=1.0,
        )
        d_propio = _distancia_de_ruta(adapter, ruta)

        if d_osrm > 0.0:
            err_dist = abs(d_propio - d_osrm) / d_osrm
            errores_distancia.append(err_dist)
            if err_dist > TOLERANCIA_DISTANCIA:
                fuera.append((par_id, d_propio, d_osrm, err_dist))

        if t_osrm > 0.0:
            errores_duracion.append(abs(t_propio - t_osrm) / t_osrm)

    dentro = sum(1 for e in errores_distancia if e <= TOLERANCIA_DISTANCIA)

    # CP-01b — Distribución observacional reportada al log (no assertable).
    _log.info("CP-01a distance: %s", _resumen_distribucion(errores_distancia))
    _log.info("CP-01b duration: %s", _resumen_distribucion(errores_duracion))

    if fuera:
        _log.info("Top 5 pares fuera de tolerancia (distance):")
        for par_id, d_propio, d_osrm, err in sorted(fuera, key=lambda x: -x[3])[:5]:
            _log.info(
                "  id=%-3d  d_propio=%7.1f m  d_osrm=%7.1f m  err_rel=%.3f",
                par_id,
                d_propio,
                d_osrm,
                err,
            )

    assert dentro >= MINIMO_DENTRO, (
        f"CP-01a falla: solo {dentro}/100 pares con |Δ_distance|/d_OSRM ≤ "
        f"{TOLERANCIA_DISTANCIA}, mínimo exigido: {MINIMO_DENTRO}. "
        f"Distribución observada: {_resumen_distribucion(errores_distancia)}"
    )
