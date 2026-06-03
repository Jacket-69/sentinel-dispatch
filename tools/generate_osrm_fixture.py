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
JITTERS_POR_INCIDENTE: int = 10  # 10 bases × 12 incidentes × 10 jitters = 1200 candidatos
JITTER_GRADOS: float = 0.0013  # ~150 m al sur de Coquimbo (1° lat ≈ 111 km)
DISTANCIA_MINIMA_M: float = 200.0
TIMEOUT_S: float = 10.0

# Modo cartesiano (Ruta B, ADR-0016): grilla regular sobre el bbox + jitter
# amplio en ambos extremos. Cubre todo el bbox (no solo el clúster urbano de
# bases/incidentes), expone rutas largas inter-comuna que aprietan el IC95 y
# mitiga el sesgo de jitter pequeño de ADR-0011 §V/L#3.
MODO_BASESXINCIDENTES: str = "basesxincidentes"
MODO_CARTESIANO: str = "cartesiano"
JITTER_GRADOS_AMPLIO: float = 0.01  # ~1.1 km (1° lat ≈ 111 km)
GRID_LADO_CARTESIANO: int = 8  # 8×8 = 64 anclas → 64×63 = 4032 pares candidatos

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


def generar_candidatos_cartesiano(
    rng: random.Random,
    *,
    grid_lado: int = GRID_LADO_CARTESIANO,
    jitter_grados: float = JITTER_GRADOS_AMPLIO,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Producto cartesiano de una grilla regular sobre el bbox + jitter amplio.

    Construye ``grid_lado × grid_lado`` anclas equiespaciadas en el bbox
    ``(-71.45, -30.10, -71.15, -29.85)``, forma todos los pares ordenados
    origen≠destino (``grid_lado² · (grid_lado² − 1)`` candidatos) y aplica
    jitter uniforme ``±jitter_grados`` (~1.1 km a 0.01°) a ambos extremos,
    independiente por componente lat/lon. A diferencia de
    :func:`generar_candidatos` —anclada al clúster urbano de bases e
    incidentes—, cubre todo el bbox: incluye rutas largas inter-comuna que
    aprietan el IC95 (Ruta B del ADR-0016) y reduce el sesgo de jitter
    pequeño señalado en ADR-0011 §V/L#3. Las anclas oceánicas del oeste del
    bbox se descartan en :func:`generar_fixture` por ``sin_ruta``.
    """
    lats = [BBOX_BOTTOM + (BBOX_TOP - BBOX_BOTTOM) * i / (grid_lado - 1) for i in range(grid_lado)]
    lons = [BBOX_LEFT + (BBOX_RIGHT - BBOX_LEFT) * j / (grid_lado - 1) for j in range(grid_lado)]
    anclas = [(lat, lon) for lat in lats for lon in lons]
    candidatos: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for origen in anclas:
        for destino in anclas:
            if origen == destino:
                continue
            jittered_o = (
                origen[0] + rng.uniform(-jitter_grados, jitter_grados),
                origen[1] + rng.uniform(-jitter_grados, jitter_grados),
            )
            jittered_d = (
                destino[0] + rng.uniform(-jitter_grados, jitter_grados),
                destino[1] + rng.uniform(-jitter_grados, jitter_grados),
            )
            candidatos.append((jittered_o, jittered_d))
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


def generar_fixture(
    *,
    modo: str = MODO_BASESXINCIDENTES,
    n_objetivo: int = PARES_OBJETIVO,
) -> dict[str, Any]:
    rng = random.Random(SEED)
    if modo == MODO_CARTESIANO:
        candidatos = generar_candidatos_cartesiano(rng)
        version = "3"
        jitter_meta: dict[str, Any] = {
            "radio_grados": JITTER_GRADOS_AMPLIO,
            "radio_metros_aprox": round(JITTER_GRADOS_AMPLIO * 111_000.0, 1),
            "distribucion": "uniform",
            "aplicado_sobre": "ambos extremos (grilla cartesiana sobre el bbox)",
            "generador": (
                "random.Random(seed).uniform(-radio_grados, +radio_grados) por "
                "componente lat y lon, independiente, en origen y destino"
            ),
            "grid_lado": GRID_LADO_CARTESIANO,
        }
    else:
        bases = cargar_bases()
        incidentes = cargar_incidentes()
        candidatos = generar_candidatos(bases, incidentes, rng)
        version = "2"
        jitter_meta = {
            "radio_grados": JITTER_GRADOS,
            "radio_metros_aprox": round(JITTER_GRADOS * 111_000.0, 1),
            "distribucion": "uniform",
            "aplicado_sobre": "destino (incidente); origen sin jitter",
            "generador": (
                "random.Random(seed).uniform(-radio_grados, +radio_grados) por "
                "componente lat y lon, independiente"
            ),
            "jitters_por_incidente": JITTERS_POR_INCIDENTE,
        }

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
            if len(pares) >= n_objetivo:
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

    if len(pares) < n_objetivo:
        # Si predomina `red`, el problema es OSRM (caído, lento, malformado);
        # si predomina `sin_ruta`, el bbox/SCC no alcanza (esperable en modo
        # cartesiano por las anclas oceánicas); si predomina `distancia_corta`,
        # subir el jitter o, en cartesiano, GRID_LADO_CARTESIANO.
        raise SystemExit(
            f"Solo {len(pares)} pares válidos de {len(candidatos)} candidatos "
            f"(modo={modo}). Descartes por causa: {descartes}. Diagnóstico arriba."
        )

    return {
        "version": version,
        "modo": modo,
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
        "jitter": jitter_meta,
        "distancia_minima_m": DISTANCIA_MINIMA_M,
        "n_objetivo": n_objetivo,
        "pares": pares,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modo",
        choices=[MODO_BASESXINCIDENTES, MODO_CARTESIANO],
        default=MODO_BASESXINCIDENTES,
        help=(
            f"Estrategia de generación. '{MODO_BASESXINCIDENTES}' (default): "
            "10 bases × 12 incidentes × jitter pequeño (fixture v2). "
            f"'{MODO_CARTESIANO}': grilla cartesiana sobre el bbox + jitter amplio "
            "(fixture v3, Ruta B del ADR-0016)."
        ),
    )
    parser.add_argument(
        "--n-objetivo",
        type=int,
        default=PARES_OBJETIVO,
        help=f"Objetivo de pares válidos (default: {PARES_OBJETIVO}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=FIXTURE_PATH,
        help=f"Ruta del fixture JSON (default: {FIXTURE_PATH})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    inicio = time.perf_counter()

    fixture = generar_fixture(modo=args.modo, n_objetivo=args.n_objetivo)

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
