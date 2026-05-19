"""Genera el fixture OSRM oracle (tests/fixtures/osrm_oracle.json).

Estrategia ADR-0010 §3 — "100 pares base SAMU → incidente, no aleatorios,
distribución que el sistema verá en producción":

    1. ORÍGENES: las 10 bases SAMU de ``data/dataset/unidades.json``.
    2. DESTINOS: los 12 incidentes de ``data/dataset/incidentes.json``,
       cada uno expandido con ``JITTERS_POR_INCIDENTE`` pequeñas
       perturbaciones (10-150 m, semilla fija) para diversificar la red
       vial recorrida sin salir de la zona urbana real.
    3. Producto cartesiano = 10 × 12 × jitters → muestreado en orden
       determinista hasta juntar :data:`PARES_OBJETIVO` pares válidos.
    4. Por cada par, consulta OSRM ``/route/v1/driving``; descarta pares
       sin ruta o con distancia < ``DISTANCIA_MINIMA_M`` (degenera la
       tolerancia relativa). Guarda ``duration`` (s) + ``distance`` (m).

OSRM debe estar corriendo en ``http://localhost:5000`` (o ``OSRM_BASE_URL``).
Ver ``tools/build_osrm_oracle.sh`` para levantarlo en Docker.

Uso:
    uv run --project core-python python tools/generate_osrm_fixture.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

OSRM_BASE_URL: str = os.environ.get("OSRM_BASE_URL", "http://localhost:5000")

# Mismo bbox que adapters.grafo_osmnx.BBOX_IV_REGION.
BBOX_LEFT: float = -71.45
BBOX_BOTTOM: float = -30.10
BBOX_RIGHT: float = -71.15
BBOX_TOP: float = -29.85

SEED: int = 2026
PARES_OBJETIVO: int = 100
JITTERS_POR_INCIDENTE: int = (
    10  # 10 bases × 12 incidentes × 10 jitters = 1200 candidatos
)
JITTER_GRADOS: float = 0.0013  # ~150 m al sur de Coquimbo (1° lat ≈ 111 km)
DISTANCIA_MINIMA_M: float = 200.0
TIMEOUT_S: float = 10.0

ROOT: Path = Path(__file__).resolve().parents[1]
UNIDADES_PATH: Path = ROOT / "data" / "dataset" / "unidades.json"
INCIDENTES_PATH: Path = ROOT / "data" / "dataset" / "incidentes.json"
FIXTURE_PATH: Path = ROOT / "core-python" / "tests" / "fixtures" / "osrm_oracle.json"


# ---------------------------------------------------------------------------
# Funciones
# ---------------------------------------------------------------------------


def cargar_bases() -> list[tuple[float, float]]:
    """Devuelve la lista de coordenadas (lat, lon) de las 10 bases SAMU."""
    with UNIDADES_PATH.open("r", encoding="utf-8") as f:
        unidades = json.load(f)
    return [(float(u["base_lat"]), float(u["base_lon"])) for u in unidades]


def cargar_incidentes() -> list[tuple[float, float]]:
    """Devuelve la lista de coordenadas (lat, lon) de los 12 incidentes del dataset."""
    with INCIDENTES_PATH.open("r", encoding="utf-8") as f:
        incidentes = json.load(f)
    return [(float(i["lat"]), float(i["lon"])) for i in incidentes]


def generar_candidatos(
    bases: list[tuple[float, float]],
    incidentes: list[tuple[float, float]],
    rng: random.Random,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Producto cartesiano base × incidente + jitter pequeño en el destino.

    Devuelve hasta ``len(bases) * len(incidentes) * JITTERS_POR_INCIDENTE``
    pares ``((lat_origen, lon_origen), (lat_destino, lon_destino))``. El
    jitter mantiene los destinos en la zona urbana real (los incidentes
    del dataset ya están en La Serena-Coquimbo).
    """
    candidatos: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for base in bases:
        for incidente in incidentes:
            for _ in range(JITTERS_POR_INCIDENTE):
                dlat = rng.uniform(-JITTER_GRADOS, JITTER_GRADOS)
                dlon = rng.uniform(-JITTER_GRADOS, JITTER_GRADOS)
                destino = (incidente[0] + dlat, incidente[1] + dlon)
                candidatos.append((base, destino))
    rng.shuffle(candidatos)
    return candidatos


class MotivoDescarte:
    """Etiquetas de descarte para contar separadamente cada causa."""

    RED = "red"  # error de red, timeout, JSON malformado, status no 200
    SIN_RUTA = "sin_ruta"  # OSRM respondió Ok pero sin routes
    DISTANCIA_CORTA = "distancia_corta"  # ruta válida pero < DISTANCIA_MINIMA_M


def consultar_osrm(
    cliente: httpx.Client,
    origen: tuple[float, float],
    destino: tuple[float, float],
) -> tuple[float, float] | str:
    """Consulta /route/v1/driving.

    Returns:
        ``(duration_s, distance_m)`` si OSRM devolvió una ruta válida; en caso
        contrario una etiqueta de :class:`MotivoDescarte` indicando la causa.
    """
    lat1, lon1 = origen
    lat2, lon2 = destino
    url = f"/route/v1/driving/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}"
    params = {
        "alternatives": "false",
        "overview": "false",
        "steps": "false",
        "annotations": "false",
    }
    try:
        resp = cliente.get(url, params=params, timeout=TIMEOUT_S)
        if resp.status_code != 200:
            return MotivoDescarte.RED
        data = resp.json()
    except (httpx.RequestError, json.JSONDecodeError) as exc:
        logging.warning("Error consultando OSRM: %s", exc)
        return MotivoDescarte.RED
    if data.get("code") != "Ok" or not data.get("routes"):
        return MotivoDescarte.SIN_RUTA
    ruta = data["routes"][0]
    return float(ruta["duration"]), float(ruta["distance"])


def generar_fixture() -> dict[str, Any]:
    bases = cargar_bases()
    incidentes = cargar_incidentes()
    rng = random.Random(SEED)
    candidatos = generar_candidatos(bases, incidentes, rng)
    pares: list[dict[str, Any]] = []
    descartes: dict[str, int] = {
        MotivoDescarte.RED: 0,
        MotivoDescarte.SIN_RUTA: 0,
        MotivoDescarte.DISTANCIA_CORTA: 0,
    }

    with httpx.Client(base_url=OSRM_BASE_URL) as cliente:
        # Health-check inicial — falla rápido si OSRM no está arriba.
        try:
            cliente.get(
                "/nearest/v1/driving/-71.2535,-29.9077", timeout=TIMEOUT_S
            ).raise_for_status()
        except httpx.HTTPError as exc:
            raise SystemExit(f"OSRM no responde en {OSRM_BASE_URL}: {exc}") from exc

        for origen, destino in candidatos:
            if len(pares) >= PARES_OBJETIVO:
                break

            resultado = consultar_osrm(cliente, origen, destino)
            if isinstance(resultado, str):
                descartes[resultado] += 1
                continue
            duration, distance = resultado
            if distance < DISTANCIA_MINIMA_M:
                descartes[MotivoDescarte.DISTANCIA_CORTA] += 1
                continue

            pares.append(
                {
                    "id": len(pares),
                    "origen": {"lat": round(origen[0], 6), "lon": round(origen[1], 6)},
                    "destino": {
                        "lat": round(destino[0], 6),
                        "lon": round(destino[1], 6),
                    },
                    "duration_s": round(duration, 3),
                    "distance_m": round(distance, 3),
                }
            )

            # Throttle suave (15 ms): OSRM local lo soporta sin problema, pero
            # mantiene el mismo patrón si en el futuro se apunta al demo público.
            time.sleep(0.015)

    if len(pares) < PARES_OBJETIVO:
        # Si predomina `red`, el problema es OSRM (caído, lento, malformado);
        # si predomina `sin_ruta`, el bbox/SCC no alcanza; si predomina
        # `distancia_corta`, hay que aumentar JITTERS_POR_INCIDENTE.
        raise SystemExit(
            f"Solo {len(pares)} pares válidos de {len(candidatos)} candidatos. "
            f"Descartes por causa: {descartes}. Diagnóstico arriba."
        )

    return {
        "version": "1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "bbox": [BBOX_LEFT, BBOX_BOTTOM, BBOX_RIGHT, BBOX_TOP],
        "osrm": {
            "base_url": OSRM_BASE_URL,
            "profile": "car",
            "algorithm": "mld",
            "endpoint": "/route/v1/driving",
            "seed": SEED,
            "descartes": descartes,
        },
        "pares": pares,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=FIXTURE_PATH,
        help=f"Ruta del fixture JSON (default: {FIXTURE_PATH})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    inicio = time.perf_counter()

    fixture = generar_fixture()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2, ensure_ascii=False)
        f.write("\n")

    transcurrido = time.perf_counter() - inicio
    print(
        f"Fixture generado: {args.output} "
        f"pares={len(fixture['pares'])} descartes={fixture['osrm']['descartes']} "
        f"({transcurrido:.1f} s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
