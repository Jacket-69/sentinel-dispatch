"""Pre-computa el grafo vial de la IV Región (caché GraphML).

Descarga el grafo de OSM via OSMnx para el bbox La Serena-Coquimbo,
imputa velocidades con el cascade chileno (ADR-0010 §2) y persiste la
caché en ``data/graphs/coquimbo.graphml``.

Pensado para ser invocado por ``make build-graph`` antes de correr el
test IT-01 (``test_routing_vs_osrm``) o el dataset de aceptación. La
caché es committeada al repo para garantizar reproducibilidad del fixture
OSRM oracle (ADR-0010 §3).

Uso:
    uv run --project core-python python core-python/scripts/build_graph.py [--force]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from sentinel_dispatch.adapters.grafo_osmnx import (
    BBOX_IV_REGION,
    GRAPHML_PATH,
    cargar_grafo_iv_region,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-computar grafo OSM IV Región.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forzar re-descarga aunque la caché GraphML ya exista.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    inicio = time.perf_counter()

    grafo = cargar_grafo_iv_region(
        bbox=BBOX_IV_REGION,
        ruta_cache=GRAPHML_PATH,
        forzar_descarga=args.force,
    )
    transcurrido = time.perf_counter() - inicio

    print(
        f"Grafo cargado: nodos={grafo.number_of_nodes()} aristas={grafo.number_of_edges()} "
        f"path={GRAPHML_PATH} ({transcurrido:.1f} s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
