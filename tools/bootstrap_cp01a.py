"""Bootstrap del criterio CP-01a — IC95 sobre el conteo 78/100.

El ADR-0011 §Verdad/Limitaciones reconoce que CP-01a se cumple por margen
estrecho (78/100 contra mínimo 75/100). Esta herramienta cuantifica la
estabilidad estadística de ese margen mediante un **bootstrap no
paramétrico**: se muestrean con reemplazo los 100 errores relativos del
fixture ``B`` veces, se computa el conteo "dentro de tolerancia" en cada
réplica, y se reporta la distribución resultante (mediana + IC95).

Pregunta empírica:

    *Si el experimento se repitiera con una muestra equivalente (mismo
    proceso generador del jitter, mismo grafo), ¿qué fracción de
    réplicas cumpliría el mínimo de 75/100?*

Interpretación:

- **IC95 inferior ≥ 75** → el margen es defendible matemáticamente: el
  95% inferior de réplicas bootstrap sigue cumpliendo CP-01a.
- **IC95 inferior < 75** → el margen es estrecho; reconocer la
  limitación en ADR-0011 §V/L#5.

El script reusa el mismo cargado de grafo + A* que ``analyze_outliers.py``
y ``test_routing_vs_osrm.py``. La métrica se calcula una sola vez (paso
caro, ~2 s) y luego el bootstrap es resampling puro sobre la lista de
errores (paso barato, ~50 ms para B=1000).

Uso::

    uv run --project core-python python tools/bootstrap_cp01a.py
    uv run --project core-python python tools/bootstrap_cp01a.py \\
        --n-bootstrap 5000 --seed 42
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import statistics
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sentinel_dispatch.adapters.grafo_osmnx import (
    GRAPHML_PATH,
    OsmnxGrafoVial,
    cargar_grafo_iv_region,
)
from sentinel_dispatch.domain.routing.a_estrella import a_estrella

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

ROOT: Path = Path(__file__).resolve().parents[1]
FIXTURE_PATH: Path = ROOT / "core-python" / "tests" / "fixtures" / "osrm_oracle.json"
DEFAULT_OUTPUT_MD: Path = ROOT / "docs" / "quality" / "bootstrap-cp01a.md"

TOLERANCIA_DISTANCIA: float = 0.30
MINIMO_DENTRO: int = 75
DEFAULT_B: int = 1000
DEFAULT_SEED: int = 2026


# ---------------------------------------------------------------------------
# Cálculo de errores (paso caro)
# ---------------------------------------------------------------------------


def _distancia_de_ruta(adapter: OsmnxGrafoVial, ruta: list[int]) -> float:
    """Suma de longitudes de aristas de la ruta — espejo de IT-01."""
    total = 0.0
    for i in range(len(ruta) - 1):
        u, v = ruta[i], ruta[i + 1]
        longitudes = [a.longitud_m for a in adapter.vecinos(u) if a.destino == v]
        if not longitudes:
            continue
        total += min(longitudes)
    return total


def calcular_errores_distancia(
    adapter: OsmnxGrafoVial, pares: Iterable[dict[str, Any]]
) -> list[float]:
    """Recorre los pares y devuelve ``err_rel = |d_propio - d_osrm| / d_osrm``.

    Replica bit-exacto la métrica del test de integración
    ``test_routing_vs_osrm.py`` (CP-01a), con ``factor_hora=1.0`` y
    ``factor_sirena=1.0`` para que la comparación sea idéntica.
    """
    errores: list[float] = []
    for par in pares:
        origen = par["origen"]
        destino = par["destino"]
        nodo_o = adapter.nodo_mas_cercano(float(origen["lat"]), float(origen["lon"]))
        nodo_d = adapter.nodo_mas_cercano(float(destino["lat"]), float(destino["lon"]))
        _, ruta = a_estrella(
            adapter, nodo_o, nodo_d, factor_hora=1.0, factor_sirena=1.0
        )
        d_propio = _distancia_de_ruta(adapter, ruta)
        d_osrm = float(par["distance_m"])
        if d_osrm <= 0.0:
            continue
        errores.append(abs(d_propio - d_osrm) / d_osrm)
    return errores


# ---------------------------------------------------------------------------
# Bootstrap (paso barato)
# ---------------------------------------------------------------------------


@dataclass
class ResultadoBootstrap:
    n_muestra: int
    n_bootstrap: int
    seed: int
    tolerancia: float
    minimo: int
    conteo_real: int
    conteos_bootstrap: list[int]

    @property
    def mediana(self) -> float:
        return statistics.median(self.conteos_bootstrap)

    @property
    def media(self) -> float:
        return statistics.fmean(self.conteos_bootstrap)

    @property
    def desviacion(self) -> float:
        return statistics.pstdev(self.conteos_bootstrap)

    @property
    def ic95(self) -> tuple[int, int]:
        """Intervalo de confianza al 95% (percentiles 2.5 y 97.5)."""
        ordenados = sorted(self.conteos_bootstrap)
        n = len(ordenados)
        lo = ordenados[max(0, int(round(0.025 * n)) - 1)]
        hi = ordenados[min(n - 1, int(round(0.975 * n)) - 1)]
        return lo, hi

    @property
    def pct_cumplen(self) -> float:
        return sum(1 for c in self.conteos_bootstrap if c >= self.minimo) / len(
            self.conteos_bootstrap
        )

    @property
    def rango(self) -> tuple[int, int]:
        return min(self.conteos_bootstrap), max(self.conteos_bootstrap)


def bootstrap_conteo_dentro(
    errores: list[float],
    *,
    n_bootstrap: int = DEFAULT_B,
    seed: int = DEFAULT_SEED,
    tolerancia: float = TOLERANCIA_DISTANCIA,
    minimo: int = MINIMO_DENTRO,
) -> ResultadoBootstrap:
    """Resampling con reemplazo del conteo ``dentro/N``.

    Cada réplica muestrea ``len(errores)`` errores con reemplazo desde la
    lista original y cuenta cuántos cumplen ``err <= tolerancia``. El
    resultado encapsula la distribución empírica del conteo y permite
    derivar mediana, IC95, % de réplicas que cumplen ``minimo``, etc.
    """
    if not errores:
        raise ValueError("La lista de errores está vacía.")
    rng = random.Random(seed)
    n = len(errores)
    conteo_real = sum(1 for e in errores if e <= tolerancia)
    conteos: list[int] = []
    for _ in range(n_bootstrap):
        muestra = rng.choices(errores, k=n)
        conteos.append(sum(1 for e in muestra if e <= tolerancia))
    return ResultadoBootstrap(
        n_muestra=n,
        n_bootstrap=n_bootstrap,
        seed=seed,
        tolerancia=tolerancia,
        minimo=minimo,
        conteo_real=conteo_real,
        conteos_bootstrap=conteos,
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def render_markdown(res: ResultadoBootstrap) -> str:
    lo, hi = res.ic95
    rmin, rmax = res.rango
    defendible = lo >= res.minimo
    veredicto = (
        f"**IC95 inferior = {lo} ≥ {res.minimo} → el margen "
        f"{res.conteo_real}/{res.n_muestra} es defendible matemáticamente.** "
        "El 95% inferior de las réplicas bootstrap mantiene el cumplimiento "
        "de CP-01a."
        if defendible
        else f"**IC95 inferior = {lo} < {res.minimo} → el margen "
        f"{res.conteo_real}/{res.n_muestra} es estrecho.** No se puede "
        "afirmar que el 95% de las réplicas cumple. La limitación queda "
        "cuantificada en ADR-0011 §V/L#5 (no resuelta: el bootstrap "
        "no inventa muestras nuevas, sólo cuantifica la variabilidad "
        "del fixture disponible)."
    )
    lineas = [
        "# Bootstrap CP-01a — estabilidad estadística del conteo 78/100",
        "",
        "Cuantifica la afirmación del ADR-0011 §V/L#5 *CP-01a se cumple por "
        "margen estrecho (78/100 vs mínimo 75/100)* mediante un bootstrap "
        "no paramétrico sobre los 100 errores relativos del fixture "
        "`tests/fixtures/osrm_oracle.json`.",
        "",
        "## Metodología",
        "",
        f"- **Muestra original**: {res.n_muestra} pares (idéntico al test IT-01).",
        f"- **Estadístico**: `dentro_de_tolerancia(err_rel ≤ "
        f"{res.tolerancia:.2f})` → conteo entero en `[0, {res.n_muestra}]`.",
        f"- **Bootstrap**: {res.n_bootstrap} réplicas, muestreo con reemplazo, "
        f"tamaño igual al original ({res.n_muestra}).",
        f"- **Semilla**: `random.Random({res.seed})` — el resultado es "
        "determinista y reproducible.",
        f"- **Criterio CP-01a**: ≥ {res.minimo} de {res.n_muestra} pares "
        "dentro de tolerancia.",
        "",
        "## Resultados",
        "",
        "| métrica | valor |",
        "|---|---:|",
        f"| Conteo real (sin bootstrap) | **{res.conteo_real} / {res.n_muestra}** |",
        f"| Mediana bootstrap | {res.mediana:.1f} |",
        f"| Media bootstrap | {res.media:.2f} |",
        f"| Desviación estándar | {res.desviacion:.2f} |",
        f"| IC95 (p2.5, p97.5) | **[{lo}, {hi}]** |",
        f"| Rango (min, max) | [{rmin}, {rmax}] |",
        f"| % réplicas con conteo ≥ {res.minimo} | **{res.pct_cumplen:.1%}** |",
        "",
        "## Interpretación",
        "",
        veredicto,
        "",
        f"Adicionalmente, el **{res.pct_cumplen:.1%}** de las {res.n_bootstrap} "
        f"réplicas bootstrap obtuvieron un conteo ≥ {res.minimo}, lo que es "
        "una estimación directa de la probabilidad de que una repetición "
        "del experimento (con el mismo proceso generador del jitter y el "
        "mismo grafo) cumpla CP-01a.",
        "",
        "## Limitaciones del bootstrap",
        "",
        "El bootstrap no paramétrico asume que los 100 pares del fixture "
        "son intercambiables y representativos del proceso generador "
        "subyacente. Esta hipótesis es razonable porque el jitter es "
        "uniforme y la semilla determinista (ADR-0011 §Cómo se generan "
        "los pares), pero **no captura sesgos sistemáticos** como el "
        "documentado en V/L#3 (sesgo hacia rutas urbanas cortas por radio "
        "de jitter pequeño). El IC95 mide variabilidad muestral dada esa "
        "distribución, no validez externa frente a una distribución "
        "diferente de orígenes/destinos.",
        "",
        f"Regenerar con `uv run --project core-python python "
        f"tools/bootstrap_cp01a.py --n-bootstrap {res.n_bootstrap} "
        f"--seed {res.seed}`.",
        "",
    ]
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cargar_pares(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    pares = data.get("pares", [])
    if not isinstance(pares, list):
        raise SystemExit(f"Fixture corrupto: 'pares' no es lista en {path}")
    return pares


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--graphml", type=Path, default=GRAPHML_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--n-bootstrap", type=int, default=DEFAULT_B)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--tolerancia", type=float, default=TOLERANCIA_DISTANCIA)
    parser.add_argument("--minimo", type=int, default=MINIMO_DENTRO)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    if not args.fixture.exists():
        raise SystemExit(f"Fixture ausente: {args.fixture}")
    if not args.graphml.exists():
        raise SystemExit(f"GraphML ausente: {args.graphml}")

    logging.info("Cargando grafo desde %s…", args.graphml)
    grafo = cargar_grafo_iv_region(ruta_cache=args.graphml, forzar_descarga=False)
    adapter = OsmnxGrafoVial(grafo=grafo)
    logging.info(
        "Grafo cargado: %d nodos, %d aristas",
        grafo.number_of_nodes(),
        grafo.number_of_edges(),
    )

    pares = cargar_pares(args.fixture)
    logging.info("Calculando errores sobre %d pares (A* propio)…", len(pares))
    errores = calcular_errores_distancia(adapter, pares)
    logging.info("Errores calculados: n=%d", len(errores))

    logging.info("Ejecutando bootstrap: B=%d, semilla=%d…", args.n_bootstrap, args.seed)
    resultado = bootstrap_conteo_dentro(
        errores,
        n_bootstrap=args.n_bootstrap,
        seed=args.seed,
        tolerancia=args.tolerancia,
        minimo=args.minimo,
    )
    lo, hi = resultado.ic95
    logging.info(
        "Resultado: conteo_real=%d, mediana=%.1f, IC95=[%d, %d], P(≥%d)=%.1f%%",
        resultado.conteo_real,
        resultado.mediana,
        lo,
        hi,
        resultado.minimo,
        resultado.pct_cumplen * 100,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(resultado), encoding="utf-8")
    logging.info("Markdown → %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
